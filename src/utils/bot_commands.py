import discord
import os
import logging
import uuid
import traceback
import asyncio
from discord.ext import commands
from discord import app_commands
from utils.crafty_api import CraftyAPI, ServerStats, ApiResponse
from utils.monitoring import capture_exception, add_breadcrumb
from typing import Dict, Any, Optional, List, Tuple

from typing_extensions import Annotated  # Use typing_extensions for Python 3.8+ compatibility

from utils.discord_utils import can_respond, safe_respond_async, safe_followup_async

logger = logging.getLogger(__name__)

# Constants
SERVER_ID_FIELD = "Server ID"
TIMEOUT_MESSAGE = "⚠️ Crafty API timed-out."
BOT_FOOTER_TEXT = "Crafty Controller Bot"

class CraftyBot(commands.Bot):
    """Extended Bot class with Crafty API configuration"""
    
    MISSING_CONFIG_ERROR = "Bot configuration is missing"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.crafty_url: Optional[str] = None
        self.crafty_token: Optional[str] = None
        self.server_id: str = self._get_server_id()
    
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

async def on_app_command_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    try:
        original_error = error
        if isinstance(error, app_commands.CommandInvokeError):
            original_error = error.original
        
        # Add breadcrumb for error context
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
        
        # Handle specific error types
        if isinstance(original_error, app_commands.MissingPermissions):
            error_message = "❌ You don't have permission to use this command."
        elif isinstance(original_error, app_commands.CommandOnCooldown):
            error_message = f"❌ Command is on cooldown. Try again in {original_error.retry_after:.2f} seconds."
        elif isinstance(original_error, app_commands.TransformerError):
            error_message = "❌ Invalid argument provided. Please check your input."
        elif isinstance(original_error, ValueError):
            error_message = f"❌ Invalid value: {str(original_error)}"
        else:
            logger.error(f"Unexpected error in application command: {original_error}")
            # Capture unexpected errors for monitoring
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
        
        # Use helper functions to safely respond
        if can_respond(interaction):
            await safe_respond_async(interaction, error_message, ephemeral=True)
        else:
            await safe_followup_async(interaction, error_message, ephemeral=True)
    
    except Exception as secondary_error:
        # Prevent secondary failures with broad try/except
        logger.error(f"Secondary error in error handler: {secondary_error}")
        logger.error(f"Error handler traceback:\n{traceback.format_exc()}")
        
        # Last resort: attempt to send a generic error message
        try:
            generic_message = "❌ An error occurred while processing your command."
            if can_respond(interaction):
                await safe_respond_async(interaction, generic_message, ephemeral=True)
            else:
                await safe_followup_async(interaction, generic_message, ephemeral=True)
        except Exception:
            # If even the generic message fails, just log it
            logger.error(f"Failed to send any error response for interaction {interaction.id}")

def get_start_command(bot):
    @app_commands.command(name="start", description="Start the Crafty Controller server")
    async def start_server(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not bot.crafty_url or not bot.crafty_token:
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        async with CraftyAPI(bot.crafty_url, bot.crafty_token) as api:
            try:
                async with asyncio.timeout(10):
                    response = await api.start_server(bot.server_id)
            except asyncio.TimeoutError:
                await safe_followup_async(interaction, TIMEOUT_MESSAGE, ephemeral=True)
                return
            embed = create_response_embed(bot, response, "Server Start", bot.server_id)
            await interaction.followup.send(embed=embed)
    return start_server

def get_stop_command(bot):
    @app_commands.command(name="stop", description="Stop the Crafty Controller server")
    async def stop_server(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not bot.crafty_url or not bot.crafty_token:
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        async with CraftyAPI(bot.crafty_url, bot.crafty_token) as api:
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
        if not bot.crafty_url or not bot.crafty_token:
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        async with CraftyAPI(bot.crafty_url, bot.crafty_token) as api:
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
        if not bot.crafty_url or not bot.crafty_token:
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        async with CraftyAPI(bot.crafty_url, bot.crafty_token) as api:
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
        if not bot.crafty_url or not bot.crafty_token:
            raise ValueError(bot.MISSING_CONFIG_ERROR)
        async with CraftyAPI(bot.crafty_url, bot.crafty_token) as api:
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
    bot.crafty_url = os.getenv('CRAFTY_URL')
    bot.crafty_token = os.getenv('CRAFTY_TOKEN')
    if not bot.crafty_url or not bot.crafty_token:
        raise ValueError("CRAFTY_URL and CRAFTY_TOKEN environment variables are required")

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
