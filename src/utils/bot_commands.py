import discord
import os
import logging
import uuid
import traceback
import asyncio
import time
from discord.ext import commands
from discord import app_commands
from utils.crafty_api import CraftyAPI, ServerStats, ApiResponse, CraftyAPIError
from utils.token_manager import TokenManager, TokenManagerError
from utils.monitoring import capture_exception, add_breadcrumb
from typing import Dict, Any, Optional, List, Tuple, Callable

from typing_extensions import Annotated  # Use typing_extensions for Python 3.8+ compatibility

from utils.discord_utils import can_respond, safe_respond_async, safe_followup_async

logger = logging.getLogger(__name__)

def _has_valid_credentials(bot) -> bool:
    """Check if bot has valid Crafty Controller credentials"""
    if not bot.crafty_url:
        return False
    # Either token OR both username and password
    return bool(bot.crafty_token) or bool(bot.crafty_username and bot.crafty_password)

def _get_auth_for_api(bot):
    """Get authentication method for CraftyAPI - either static token or TokenManager instance
    
    Returns:
        Either a token string or TokenManager instance for CraftyAPI
        
    Raises:
        ValueError: If no valid authentication method is available
    """
    # If we have a direct token, use it (static token mode)
    if bot.crafty_token:
        return bot.crafty_token
    
    # If we have TokenManager, use it for dynamic token management
    if bot.token_manager:
        return bot.token_manager
    
    # Fallback: no valid authentication
    raise ValueError("No valid authentication method available")

# Constants
SERVER_ID_FIELD = "Server ID"
TIMEOUT_MESSAGE = "⚠️ Crafty API timed-out."
BOT_FOOTER_TEXT = "Crafty Controller Bot"
START_COMMAND_COOLDOWN = 120  # 2 minutes in seconds

class CraftyBot(commands.Bot):
    """Extended Bot class with Crafty API configuration"""
    
    MISSING_CONFIG_ERROR = "Bot configuration is missing"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.crafty_url: Optional[str] = None
        self.crafty_token: Optional[str] = None
        self.crafty_username: Optional[str] = None
        self.crafty_password: Optional[str] = None
        self.server_id: str = self._get_server_id()
        self.token_manager: Optional[TokenManager] = None
        self.auth_mode: str = "unknown"
        self.last_start_command: Dict[int, float] = {}  # user_id -> timestamp
    
    def _get_server_id(self) -> str:
        """Get SERVER_ID from environment"""
        server_id_str = os.getenv('SERVER_ID')
        if not server_id_str:
            raise ValueError("SERVER_ID environment variable is required")
        # Validate UUID format
        try:
            uuid_obj = uuid.UUID(server_id_str)
        except ValueError:
            raise ValueError("SERVER_ID must be a valid UUID")
        return str(uuid_obj)
    
    async def cleanup(self) -> None:
        """Clean up resources, including TokenManager if present"""
        if self.token_manager:
            logger.info("Cleaning up TokenManager...")
            try:
                await self.token_manager.close()
                logger.debug("TokenManager cleanup completed")
            except Exception as e:
                logger.error(f"Error during TokenManager cleanup: {e}")

def _add_success_fields(embed: discord.Embed, response: ApiResponse, server_id: str):
    embed.add_field(name=SERVER_ID_FIELD, value=str(server_id), inline=True)
    if response.data and isinstance(response.data, dict):
        for key, value in response.data.items():
            if key not in ['server_id'] and value is not None:
                embed.add_field(name=key.replace('_', ' ').title(), value=str(value), inline=True)

def _add_failure_fields(embed: discord.Embed, response: ApiResponse, server_id: str):
    embed.add_field(name=SERVER_ID_FIELD, value=str(server_id), inline=True)
    if response.error_code:
        embed.add_field(name="Error Code", value=str(response.error_code), inline=True)

def create_response_embed(bot, response: ApiResponse, action: str, server_id: str) -> discord.Embed:
    """Create a formatted embed for API responses"""
    if response.success:
        embed = discord.Embed(
            title=f"✅ {action} Successful",
            description=response.message,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        _add_success_fields(embed, response, server_id)
    else:
        embed = discord.Embed(
            title=f"❌ {action} Failed",
            description=response.message,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        _add_failure_fields(embed, response, server_id)
    embed.set_footer(text=BOT_FOOTER_TEXT, icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None)
    return embed

def _safe_get_attr_multi(obj, attr_names: List[str], fallback: Any = None) -> Any:
    """Safely get attribute from object trying multiple names with fallback"""
    for attr_name in attr_names:
        try:
            value = getattr(obj, attr_name, None)
            if value is not None:
                return value
        except AttributeError:
            continue
    return fallback

def _derive_server_state(stats: ServerStats) -> Tuple[str, str, discord.Color]:
    """Derive server state from stats object
    
    Returns:
        Tuple of (status_emoji, status_text, color)
    """
    running = _safe_get_attr_multi(stats, ['running'], False)
    crashed = _safe_get_attr_multi(stats, ['crashed'], False)
    updating = _safe_get_attr_multi(stats, ['updating'], False)
    
    if crashed:
        return ("💥", "Crashed", discord.Color.orange())
    elif updating:
        return ("🔄", "Updating", discord.Color.blue())
    elif running:
        return ("🟢", "Running", discord.Color.green())
    else:
        return ("🔴", "Stopped", discord.Color.red())

def _format_players(stats: ServerStats) -> str:
    """Format player count display with multi-name support
    
    Returns:
        Formatted player string (e.g. "5/20")
    """
    online_players = _safe_get_attr_multi(
        stats, 
        ['online_players', 'players_online', 'online', 'current_players']
    )
    max_players = _safe_get_attr_multi(
        stats, 
        ['max_players', 'players_max', 'max', 'maximum_players']
    )
    
    if online_players is not None and max_players is not None:
        try:
            return f"{int(online_players)}/{int(max_players)}"
        except (ValueError, TypeError):
            return f"{online_players}/{max_players}"
    elif online_players is not None:
        return f"{online_players}/?"
    elif max_players is not None:
        return f"?/{max_players}"
    else:
        return "Unknown"

def create_status_embed(bot, server_stats: ServerStats) -> discord.Embed:
    """Create a formatted embed for server status
    
    This function creates a Discord embed using ServerStats data retrieved from
    the Crafty Controller API's /stats endpoint. It handles field name changes
    gracefully and provides fallbacks for missing or optional fields.
    
    Args:
        bot: The Discord bot instance
        server_stats: ServerStats object containing server information
        
    Returns:
        A formatted Discord embed with server status information
    """
    # Get basic server state
    status_emoji, status_text, color = _derive_server_state(server_stats)
    
    # Get core server info
    server_name = _safe_get_attr_multi(server_stats, ['server_name'], 'Unknown Server')
    server_id = _safe_get_attr_multi(server_stats, ['server_id'], 'Unknown')
    
    # Create embed
    embed = discord.Embed(
        title=f"📊 Server Status: {server_name}",
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    # Prepare fields data
    fields = [
        ("Status", f"{status_emoji} {status_text}", True),
        (SERVER_ID_FIELD, str(server_id), True),
        ("Version", _safe_get_attr_multi(server_stats, ['version'], 'Unknown'), True),
    ]
    
    # CPU usage
    cpu = _safe_get_attr_multi(server_stats, ['cpu'], 0.0)
    try:
        cpu_value = f"{float(cpu):.1f}%"
    except (ValueError, TypeError):
        cpu_value = "Unknown"
    fields.append(("CPU Usage", cpu_value, True))
    
    # Memory usage
    memory = _safe_get_attr_multi(server_stats, ['memory'], 'Unknown')
    mem_percent = _safe_get_attr_multi(server_stats, ['mem_percent'], 0.0)
    try:
        mem_percent_value = f"{float(mem_percent):.1f}%"
        memory_display = f"{memory} ({mem_percent_value})"
    except (ValueError, TypeError):
        memory_display = str(memory) if memory != 'Unknown' else "Unknown"
    fields.append(("Memory Usage", memory_display, True))
    
    # Players
    fields.append(("Players Online", _format_players(server_stats), True))
    
    # Optional world info
    world_name = _safe_get_attr_multi(server_stats, ['world_name'], 'Unknown')
    if world_name and world_name != 'Unknown':
        fields.append(("World Name", world_name, True))
    
    world_size = _safe_get_attr_multi(server_stats, ['world_size'])
    if world_size and world_size != 'Unknown' and world_size != '0MB':
        fields.append(("World Size", str(world_size), True))
    
    # Server start time (only show if running)
    running = _safe_get_attr_multi(server_stats, ['running'], False)
    if running:
        started = _safe_get_attr_multi(server_stats, ['started'])
        if started and started != "Unknown":
            fields.append(("Started", started, True))
    
    # Add all fields to embed
    for name, value, inline in fields:
        embed.add_field(name=name, value=value, inline=inline)
    
    # Set footer
    embed.set_footer(
        text=BOT_FOOTER_TEXT, 
        icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
    )
    
    return embed

def create_startup_logs_embed(bot, server_stats: ServerStats, logs_data: Dict[str, Any], server_id: str) -> discord.Embed:
    """Create a formatted embed showing server startup with logs
    
    Args:
        bot: The Discord bot instance
        server_stats: ServerStats object containing server information
        logs_data: Dictionary containing server logs
        server_id: The server ID
        
    Returns:
        A formatted Discord embed with server status and logs
    """
    # Get basic server state
    status_emoji, status_text, color = _derive_server_state(server_stats)
    
    # Get core server info
    server_name = _safe_get_attr_multi(server_stats, ['server_name'], 'Unknown Server')
    
    # Create embed
    embed = discord.Embed(
        title=f"🚀 Server Started: {server_name}",
        description=f"{status_emoji} Server is now {status_text.lower()}",
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    # Add basic server info
    embed.add_field(name="Status", value=f"{status_emoji} {status_text}", inline=True)
    embed.add_field(name=SERVER_ID_FIELD, value=str(server_id), inline=True)
    embed.add_field(name="Version", value=_safe_get_attr_multi(server_stats, ['version'], 'Unknown'), inline=True)
    
    # Add player count
    embed.add_field(name="Players Online", value=_format_players(server_stats), inline=True)
    
    # Add world info if available
    world_name = _safe_get_attr_multi(server_stats, ['world_name'], 'Unknown')
    if world_name and world_name != 'Unknown':
        embed.add_field(name="World Name", value=world_name, inline=True)
    
    # Add server start time
    started = _safe_get_attr_multi(server_stats, ['started'])
    if started and started != "Unknown":
        embed.add_field(name="Started", value=started, inline=True)
    
    # Format and add logs
    if logs_data:
        # Extract log lines from the response
        log_lines: List[Any] = []
        if isinstance(logs_data, dict):
            # Handle different possible log data structures
            if 'logs' in logs_data and isinstance(logs_data['logs'], list):
                log_lines = logs_data['logs']
            elif 'data' in logs_data and isinstance(logs_data['data'], list):
                log_lines = logs_data['data']
        elif isinstance(logs_data, list):
            log_lines = logs_data
        
        if log_lines and isinstance(log_lines, list):
            # Take the last 10 lines and format them
            recent_logs = log_lines[-10:] if len(log_lines) > 10 else log_lines
            log_text = "\n".join(str(line) for line in recent_logs)
            
            # Truncate if too long for Discord (field value limit is 1024)
            if len(log_text) > 1000:
                log_text = log_text[-1000:]
                log_text = "..." + log_text[log_text.find("\n") + 1:]
            
            embed.add_field(
                name="📄 Recent Server Logs",
                value=f"```\n{log_text}\n```",
                inline=False
            )
        else:
            embed.add_field(
                name="📄 Server Logs",
                value="No recent logs available",
                inline=False
            )
    
    # Set footer
    embed.set_footer(
        text=BOT_FOOTER_TEXT, 
        icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
    )
    
    return embed

class LogScrollView(discord.ui.View):
    """A view for scrolling through server logs"""
    
    def __init__(self, bot, server_stats: ServerStats, server_id: str, base_url: str, token_or_manager):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
        self.server_stats = server_stats
        self.server_id = server_id
        self.base_url = base_url
        self.token_or_manager = token_or_manager
        self.current_offset = 0
        self.logs_per_page = 10
        
    async def get_logs_embed(self, lines: int = 10) -> discord.Embed:
        """Get logs embed with specified number of lines"""
        try:
            # Create a new API instance for each request to avoid session issues
            async with CraftyAPI(self.base_url, self.token_or_manager) as api:
                logs_response = await api.get_server_logs(
                    self.server_id, 
                    lines=lines
                )
                
                if logs_response.success and logs_response.data:
                    logs_data = logs_response.data if isinstance(logs_response.data, dict) else {'logs': logs_response.data if isinstance(logs_response.data, list) else [str(logs_response.data)]}
                    return create_startup_logs_embed(self.bot, self.server_stats, logs_data, self.server_id)
                else:
                    # Fallback to status embed if logs fail
                    return create_status_embed(self.bot, self.server_stats)
        except Exception as e:
            logger.error(f"Error getting logs for scroll view: {e}")
            return create_status_embed(self.bot, self.server_stats)
    
    @discord.ui.button(label='📄 More Logs', style=discord.ButtonStyle.secondary)
    async def more_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show more logs (increase line count)"""
        self.logs_per_page = min(50, self.logs_per_page + 10)  # Cap at 50 lines
        embed = await self.get_logs_embed(self.logs_per_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='🔄 Refresh', style=discord.ButtonStyle.primary)
    async def refresh_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh current logs"""
        embed = await self.get_logs_embed(self.logs_per_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='📄 Less Logs', style=discord.ButtonStyle.secondary)
    async def less_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show fewer logs (decrease line count)"""
        self.logs_per_page = max(5, self.logs_per_page - 10)  # Minimum 5 lines
        embed = await self.get_logs_embed(self.logs_per_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """Disable buttons when view times out"""
        for item in self.children:
            item.disabled = True
        # Note: We can't edit the message here since we don't have the message reference

def check_start_command_cooldown(bot, user_id: int) -> Tuple[bool, Optional[float]]:
    """Check if user is on cooldown for start command
    
    Returns:
        Tuple of (is_on_cooldown, time_remaining)
    """
    current_time = time.time()
    last_command_time = bot.last_start_command.get(user_id, 0)
    time_since_last = current_time - last_command_time
    
    if time_since_last < START_COMMAND_COOLDOWN:
        time_remaining = START_COMMAND_COOLDOWN - time_since_last
        return True, time_remaining
    
    return False, None

def update_start_command_timestamp(bot, user_id: int):
    """Update the timestamp for when user last used start command"""
    bot.last_start_command[user_id] = time.time()

async def wait_for_logs_availability(api: CraftyAPI, server_id: str, max_wait: int = 30, check_interval: int = 2) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Wait for server logs to become available
    
    Args:
        api: CraftyAPI instance
        server_id: Server ID
        max_wait: Maximum time to wait in seconds
        check_interval: How often to check in seconds
        
    Returns:
        Tuple of (logs_available, logs_data)
    """
    waited = 0
    while waited < max_wait:
        try:
            logs_response = await api.get_server_logs(server_id, lines=10)
            logger.debug(f"Logs response: success={logs_response.success}, data_type={type(logs_response.data)}, data={logs_response.data}")
            
            if logs_response.success:
                # Check if logs contain meaningful data
                logs_data = logs_response.data
                
                # Be more flexible about log data structures
                log_lines = []
                if isinstance(logs_data, dict):
                    # Try multiple possible keys
                    for key in ['logs', 'data', 'content', 'lines', 'log_lines']:
                        if key in logs_data and isinstance(logs_data[key], list):
                            log_lines = logs_data[key]
                            logger.debug(f"Found logs under key '{key}': {len(log_lines)} lines")
                            break
                    # If no list found in dict, check if any values are strings (could be raw log content)
                    if not log_lines:
                        for key, value in logs_data.items():
                            if isinstance(value, str) and value.strip():
                                # Split string content into lines
                                log_lines = value.strip().split('\n')
                                logger.debug(f"Found string logs under key '{key}': {len(log_lines)} lines")
                                break
                elif isinstance(logs_data, list):
                    log_lines = logs_data
                    logger.debug(f"Logs data is directly a list: {len(log_lines)} lines")
                elif isinstance(logs_data, str) and logs_data.strip():
                    # Raw string response
                    log_lines = logs_data.strip().split('\n')
                    logger.debug(f"Logs data is string: {len(log_lines)} lines")
                
                # Check if we have any meaningful log content
                if log_lines and len(log_lines) > 0:
                    # Filter out empty lines
                    meaningful_lines = [line for line in log_lines if str(line).strip()]
                    if meaningful_lines:
                        logger.debug(f"Logs became available after {waited} seconds with {len(meaningful_lines)} meaningful lines")
                        # Return the processed data in a consistent format
                        return True, {'logs': log_lines}
            else:
                logger.debug(f"Logs API call failed: {logs_response.message}")
            
            await asyncio.sleep(check_interval)
            waited += check_interval
            logger.debug(f"Waiting for logs... {waited}/{max_wait} seconds")
            
        except Exception as e:
            logger.error(f"Error while waiting for logs: {e}")
            await asyncio.sleep(check_interval)
            waited += check_interval
    
    logger.debug(f"Logs did not become available after {max_wait} seconds")
    return False, None

async def perform_startup_auth_check(bot) -> bool:
    """Perform initial authentication check at startup
    
    This function tests the authentication method by making a harmless API call
    to verify that the bot can successfully authenticate with Crafty Controller.
    
    Args:
        bot: The CraftyBot instance
        
    Returns:
        True if authentication is successful, False otherwise
    """
    logger.info(f"Performing startup authentication check using {bot.auth_mode} mode")
    
    if not _has_valid_credentials(bot):
        logger.error("Startup authentication check failed - no valid credentials")
        return False
    
    try:
        # Get authentication method (token string or TokenManager instance)
        auth_method = _get_auth_for_api(bot)
        
        # Test authentication by making a simple API call (get server stats)
        async with CraftyAPI(bot.crafty_url, auth_method) as api:
            try:
                async with asyncio.timeout(15):  # Slightly longer timeout for startup
                    response = await api.get_server_stats(bot.server_id)
                    
                if response.success:
                    logger.info("Startup authentication check successful - server stats retrieved")
                    return True
                else:
                    logger.error(f"Startup authentication check failed - API returned error: {response.message}")
                    return False
                    
            except asyncio.TimeoutError:
                logger.error("Startup authentication check failed - API timeout")
                return False
                
    except TokenManagerError as e:
        logger.error(f"Startup authentication check failed - TokenManager error: {e}")
        return False
    except CraftyAPIError as e:
        logger.error(f"Startup authentication check failed - API error: {e}")
        return False
    except Exception as e:
        logger.error(f"Startup authentication check failed - unexpected error: {e}")
        return False

async def on_ready_handler(bot):
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info('Bot is ready to manage Crafty Controller servers')
    
    # Force guild-specific command registration for instant visibility
    guild_id = os.getenv("GUILD_ID")
    if guild_id:
        try:
            guild = discord.Object(id=int(guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} slash commands to guild {guild_id}")
        except Exception:
            logger.error("Guild sync failed:\n%s", traceback.format_exc())
    
    # Keep existing global sync in try/except after guild sync
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands globally")
    except Exception:
        logger.error("Global sync failed:\n%s", traceback.format_exc())
    
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="Crafty Controller servers"
    )
    await bot.change_presence(activity=activity)

def handle_missing_permissions(interaction: discord.Interaction) -> str:
    return "❌ You don't have permission to use this command."

def handle_command_on_cooldown(original_error: app_commands.CommandOnCooldown) -> str:
    return f"❌ Command is on cooldown. Try again in {original_error.retry_after:.2f} seconds."

def handle_transformer_error() -> str:
    return "❌ Invalid argument provided. Please check your input."

def handle_value_error(original_error: ValueError) -> str:
    return f"❌ Invalid value: {str(original_error)}"

def log_error_breadcrumb(interaction: discord.Interaction, original_error: Exception) -> None:
    """Log a breadcrumb for the error with relevant context."""
    add_breadcrumb(
        message="Application command error occurred",
        category="discord_command",
        level="error",
        data={
            "command": interaction.command.name if interaction.command else "unknown",
            "error_type": type(original_error).__name__,
            "user_id": interaction.user.id if interaction.user else None,
            "guild_id": interaction.guild.id if interaction.guild else None
        }
    )

async def send_error_response(interaction: discord.Interaction, error_message: str) -> None:
    """Send an error response to the user, handling both response and followup cases."""
    if can_respond(interaction):
        await safe_respond_async(interaction, error_message, ephemeral=True)
    else:
        await safe_followup_async(interaction, error_message, ephemeral=True)

async def handle_secondary_error(interaction: discord.Interaction, secondary_error: Exception) -> None:
    """Handle errors that occur within the error handler itself."""
    logger.error(f"Secondary error in error handler: {secondary_error}")
    logger.error(f"Error handler traceback:\n{traceback.format_exc()}")
    
    try:
        generic_message = "❌ An error occurred while processing your command."
        await send_error_response(interaction, generic_message)
    except Exception:
        logger.error(f"Failed to send any error response for interaction {interaction.id}")

def handle_unexpected_error(interaction: discord.Interaction, original_error: Exception) -> str:
    logger.error(f"Unexpected error in application command: {original_error}")
    capture_exception(original_error, {
        "component": "discord_command",
        "command": interaction.command.name if interaction.command else "unknown",
        "user_id": interaction.user.id if interaction.user else None,
        "guild_id": interaction.guild.id if interaction.guild else None,
        "channel_id": interaction.channel.id if interaction.channel else None
    })
    error_message = "❌ " + str(original_error)
    if len(error_message) > 2000:
        error_message = "❌ An unexpected error occurred. Please try again later."
    return error_message

async def on_app_command_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    try:
        original_error = error
        if isinstance(error, app_commands.CommandInvokeError):
            original_error = error.original

        log_error_breadcrumb(interaction, original_error)

        error_handlers: Dict[type, Callable[..., str]] = {
            app_commands.MissingPermissions: handle_missing_permissions,
            app_commands.CommandOnCooldown: handle_command_on_cooldown,
            app_commands.TransformerError: handle_transformer_error,
            ValueError: handle_value_error
        }

        handler = error_handlers.get(type(original_error), handle_unexpected_error)
        
        # Call the appropriate handler with the correct arguments
        if handler is handle_missing_permissions:
            error_message = handler(interaction)
        elif handler is handle_transformer_error:
            error_message = handler()
        elif handler is handle_unexpected_error:
            error_message = handler(interaction, original_error)
        else:
            error_message = handler(original_error)

        await send_error_response(interaction, error_message)

    except Exception as secondary_error:
        await handle_secondary_error(interaction, secondary_error)

def get_start_command(bot):
    @app_commands.command(name="start", description="Start the Crafty Controller server")
    async def start_server(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not _has_valid_credentials(bot):
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        
        # Check cooldown
        user_id = interaction.user.id
        is_on_cooldown, time_remaining = check_start_command_cooldown(bot, user_id)
        
        if is_on_cooldown:
            minutes = int(time_remaining // 60)
            seconds = int(time_remaining % 60)
            cooldown_message = f"⏰ Start command was recently used. Please wait {minutes}m {seconds}s before using it again."
            await safe_followup_async(interaction, cooldown_message, ephemeral=True)
            return
        
        # Get authentication method (token string or TokenManager instance)
        auth_method = _get_auth_for_api(bot)
        async with CraftyAPI(bot.crafty_url, auth_method) as api:
            try:
                async with asyncio.timeout(10):
                    response = await api.start_server(bot.server_id)
            except asyncio.TimeoutError:
                await safe_followup_async(interaction, TIMEOUT_MESSAGE, ephemeral=True)
                return
            
            # Update cooldown timestamp on successful API call
            update_start_command_timestamp(bot, user_id)
            
            # Send initial confirmation embed
            initial_embed = create_response_embed(bot, response, "Server Start", bot.server_id)
            message = await interaction.followup.send(embed=initial_embed)
            
            # If start was successful, wait for logs and show them with scrollable interface
            if response.success:
                logger.debug("Server start command successful, waiting for server to boot...")
                
                # Wait a bit for the server to start up
                await asyncio.sleep(5)
                
                try:
                    async with asyncio.timeout(60):  # Longer timeout for full startup process
                        # Check server status first
                        logger.debug("Checking server status after start command...")
                        stats_response = await api.get_server_stats(bot.server_id)
                        
                        if stats_response.success and isinstance(stats_response.data, ServerStats):
                            server_stats = stats_response.data
                            logger.debug(f"Server running status: {server_stats.running}")
                            
                            if server_stats.running:
                                # Server is running, immediately try to get logs
                                logger.debug("Server is running, attempting to get logs immediately...")
                                logs_response = await api.get_server_logs(bot.server_id, lines=10)
                                logger.debug(f"Initial logs attempt: success={logs_response.success}, data={logs_response.data}")
                                
                                if logs_response.success and logs_response.data:
                                    # We got logs! Create logs embed and scrollable view
                                    logs_data = logs_response.data if isinstance(logs_response.data, dict) else {'logs': logs_response.data if isinstance(logs_response.data, list) else [str(logs_response.data)]}
                                    updated_embed = create_startup_logs_embed(bot, server_stats, logs_data, bot.server_id)
                                    
                                    # Add scrollable view for logs
                                    view = LogScrollView(bot, server_stats, bot.server_id, bot.crafty_url, auth_method)
                                    await message.edit(embed=updated_embed, view=view)
                                    return
                                else:
                                    # First attempt failed, wait a bit and try waiting for logs
                                    logger.debug("Initial logs attempt failed, waiting for logs to become available...")
                                    logs_available, logs_data = await wait_for_logs_availability(api, bot.server_id, max_wait=20)
                                    
                                    if logs_available and logs_data:
                                        # Create scrollable logs view
                                        logger.debug("Logs became available after waiting, creating scrollable logs interface...")
                                        updated_embed = create_startup_logs_embed(bot, server_stats, logs_data, bot.server_id)
                                        
                                        # Add scrollable view for logs
                                        view = LogScrollView(bot, server_stats, bot.server_id, bot.crafty_url, auth_method)
                                        await message.edit(embed=updated_embed, view=view)
                                        return
                            else:
                                logger.debug("Server not running yet, showing status embed")
                        
                        # Fallback: show server status if logs failed or server not running
                        if stats_response.success and isinstance(stats_response.data, ServerStats):
                            logger.debug("Showing status embed as fallback")
                            status_embed = create_status_embed(bot, stats_response.data)
                            await message.edit(embed=status_embed)
                        
                except asyncio.TimeoutError:
                    logger.debug("Timeout waiting for server startup, keeping original message")
                    # If we timeout, keep the original message
                    pass
                except Exception as e:
                    logger.error(f"Error during enhanced startup process: {e}")
                    # If anything else fails, keep the original message
                    pass
    return start_server

def get_stop_command(bot):
    @app_commands.command(name="stop", description="Stop the Crafty Controller server")
    async def stop_server(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not _has_valid_credentials(bot):
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        
        # Get authentication method (token string or TokenManager instance)
        auth_method = _get_auth_for_api(bot)
        async with CraftyAPI(bot.crafty_url, auth_method) as api:
            try:
                async with asyncio.timeout(10):
                    response = await api.stop_server(bot.server_id)
            except asyncio.TimeoutError:
                await safe_followup_async(interaction, TIMEOUT_MESSAGE, ephemeral=True)
                return
            embed = create_response_embed(bot, response, "Server Stop", bot.server_id)
            await interaction.followup.send(embed=embed)
    return stop_server

def get_restart_command(bot):
    @app_commands.command(name="restart", description="Restart the Crafty Controller server")
    async def restart_server(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not _has_valid_credentials(bot):
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        
        # Get authentication method (token string or TokenManager instance)
        auth_method = _get_auth_for_api(bot)
        async with CraftyAPI(bot.crafty_url, auth_method) as api:
            try:
                async with asyncio.timeout(10):
                    response = await api.restart_server(bot.server_id)
            except asyncio.TimeoutError:
                await safe_followup_async(interaction, TIMEOUT_MESSAGE, ephemeral=True)
                return
            embed = create_response_embed(bot, response, "Server Restart", bot.server_id)
            await interaction.followup.send(embed=embed)
    return restart_server

def get_kill_command(bot):
    @app_commands.command(name="kill", description="Force kill the Crafty Controller server")
    async def kill_server(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not _has_valid_credentials(bot):
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        
        # Get authentication method (token string or TokenManager instance)
        auth_method = _get_auth_for_api(bot)
        async with CraftyAPI(bot.crafty_url, auth_method) as api:
            try:
                async with asyncio.timeout(10):
                    response = await api.kill_server(bot.server_id)
            except asyncio.TimeoutError:
                await safe_followup_async(interaction, TIMEOUT_MESSAGE, ephemeral=True)
                return
            embed = create_response_embed(bot, response, "Server Kill", bot.server_id)
            await interaction.followup.send(embed=embed)
    return kill_server

def get_status_command(bot):
    @app_commands.command(name="status", description="Check server status and statistics via the /stats endpoint")
    async def check_status(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not _has_valid_credentials(bot):
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        
        # Get authentication method (token string or TokenManager instance)
        auth_method = _get_auth_for_api(bot)
        async with CraftyAPI(bot.crafty_url, auth_method) as api:
            try:
                async with asyncio.timeout(10):
                    response = await api.get_server_stats(bot.server_id)
            except asyncio.TimeoutError:
                await safe_followup_async(interaction, TIMEOUT_MESSAGE, ephemeral=True)
                return
            if response.success and isinstance(response.data, ServerStats):
                embed = create_status_embed(bot, response.data)
                await interaction.followup.send(embed=embed)
            else:
                embed = create_response_embed(bot, response, "Server Status", bot.server_id)
                await interaction.followup.send(embed=embed)
    return check_status

def get_help_command(bot):
    @app_commands.command(name="help", description="Show available commands")
    async def help_command(interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=f"🤖 {BOT_FOOTER_TEXT} Commands",
            description="Available slash commands for managing your Minecraft servers",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        commands_info: List[Tuple[str, str]] = [
            ("/start", "Start the server"),
            ("/stop", "Stop the server"),
            ("/restart", "Restart the server"),
            ("/kill", "Force kill the server"),
            ("/status", "Check server status and statistics"),
            ("/help", "Show this help message")
        ]
        for cmd, desc in commands_info:
            embed.add_field(name=cmd, value=desc, inline=False)
        embed.set_footer(text=f"Managing server ID: {bot.server_id}")
        await interaction.response.send_message(embed=embed)
    return help_command

def create_bot() -> CraftyBot:
    """Create and configure the Discord bot"""
    intents = discord.Intents.default()
    intents.message_content = True  # Enable message content intent
    bot = CraftyBot(command_prefix=None, intents=intents, help_command=None)
    
    # Load Crafty Controller configuration
    bot.crafty_url = os.getenv('CRAFTY_URL')
    bot.crafty_token = os.getenv('CRAFTY_TOKEN')
    bot.crafty_username = os.getenv('CRAFTY_USERNAME')
    bot.crafty_password = os.getenv('CRAFTY_PASSWORD')
    
    if not bot.crafty_url:
        raise ValueError("CRAFTY_URL environment variable is required")
    
    # Validate credentials - either token or both username and password
    if not bot.crafty_token and not (bot.crafty_username and bot.crafty_password):
        raise ValueError(
            "Invalid Crafty Controller credentials. "
            "Either CRAFTY_TOKEN must be provided, or both CRAFTY_USERNAME and CRAFTY_PASSWORD must be provided."
        )
    
    # Detect and log authentication mode
    if bot.crafty_token:
        logger.info("Authentication mode: Static Token")
        bot.auth_mode = "static_token"
    elif bot.crafty_username and bot.crafty_password:
        logger.info("Authentication mode: Username/Password with TokenManager")
        bot.auth_mode = "credentials"
        # Initialize TokenManager for dynamic token management
        bot.token_manager = TokenManager(bot.crafty_url, bot.crafty_username, bot.crafty_password)
        logger.info("Initialized TokenManager for persistent token storage")
    else:
        # This shouldn't happen due to validation above, but keeping for completeness
        logger.error("Unknown authentication mode")
        bot.auth_mode = "unknown"

    @bot.event
    async def on_ready():
        await on_ready_handler(bot)

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        await on_app_command_error_handler(interaction, error)

    bot.tree.add_command(get_start_command(bot))
    bot.tree.add_command(get_stop_command(bot))
    bot.tree.add_command(get_restart_command(bot))
    bot.tree.add_command(get_kill_command(bot))
    bot.tree.add_command(get_status_command(bot))
    bot.tree.add_command(get_help_command(bot))

    return bot
