#!/usr/bin/env python3
"""
Real Discord bot deployment script for live testing.
This script runs the actual Discord bot in a test environment to verify
that error handling works correctly under real conditions.
"""

import asyncio
import logging
import os
import sys
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.bot_commands import create_bot

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'test_bot_deployment_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class TestBotDeployment:
    """Test bot deployment with comprehensive error monitoring"""
    
    def __init__(self):
        self.bot = None
        self.deployment_stats = {
            'start_time': None,
            'commands_processed': 0,
            'successful_responses': 0,
            'failed_responses': 0,
            'error_40060_count': 0,
            'error_10062_count': 0,
            'other_errors': 0,
            'interaction_timeouts': 0,
            'command_statistics': {}
        }
        self.error_log = []
        self.monitoring_active = False
    
    def setup_test_bot(self):
        """Setup the test bot with enhanced error monitoring"""
        logger.info("Setting up test bot with error monitoring...")
        
        # Load environment variables
        load_dotenv()
        
        # Validate environment
        required_vars = ['DISCORD_TOKEN', 'CRAFTY_URL', 'CRAFTY_TOKEN', 'SERVER_ID', 'GUILD_ID']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
        
        try:
            # Create bot instance
            self.bot = create_bot()
            
            # Wrap the existing error handler to capture metrics
            original_error_handler = self.bot.tree.error.func if hasattr(self.bot.tree.error, 'func') else self.bot.tree.error
            
            async def monitoring_error_handler(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
                """Enhanced error handler that captures detailed metrics"""
                self.deployment_stats['failed_responses'] += 1
                
                # Extract error details
                error_info = {
                    'timestamp': datetime.now().isoformat(),
                    'interaction_id': interaction.id,
                    'command': getattr(interaction, 'command', {}).name if hasattr(interaction, 'command') else 'unknown',
                    'error_type': type(error).__name__,
                    'error_message': str(error),
                    'guild_id': interaction.guild.id if interaction.guild else None,
                    'channel_id': interaction.channel.id if interaction.channel else None,
                    'user_id': interaction.user.id if interaction.user else None
                }
                
                # Check for specific Discord error codes
                if hasattr(error, 'code'):
                    error_info['error_code'] = error.code
                    if error.code == 40060:
                        self.deployment_stats['error_40060_count'] += 1
                        logger.error(f"🚨 40060 ERROR (Interaction already acknowledged): {error_info}")
                    elif error.code == 10062:
                        self.deployment_stats['error_10062_count'] += 1
                        logger.error(f"🚨 10062 ERROR (Unknown interaction): {error_info}")
                    else:
                        self.deployment_stats['other_errors'] += 1
                        logger.error(f"❌ OTHER ERROR (code {error.code}): {error_info}")
                else:
                    self.deployment_stats['other_errors'] += 1
                    logger.error(f"❌ ERROR (no code): {error_info}")
                
                # Log to error log
                self.error_log.append(error_info)
                
                # Call original error handler
                try:
                    await original_error_handler(interaction, error)
                except Exception as handler_error:
                    logger.error(f"Error in original error handler: {handler_error}")
            
            # Replace the error handler
            self.bot.tree.error = monitoring_error_handler
            
            async def before_command(interaction: discord.Interaction):
                """Monitor command invocation"""
                command_name = interaction.command.name if interaction.command else 'unknown'
                
                self.deployment_stats['commands_processed'] += 1
                
                # Track command statistics
                if command_name not in self.deployment_stats['command_statistics']:
                    self.deployment_stats['command_statistics'][command_name] = {
                        'invoked': 0,
                        'successful': 0,
                        'failed': 0
                    }
                
                self.deployment_stats['command_statistics'][command_name]['invoked'] += 1
                
                logger.info(f"📝 Command invoked: /{command_name} by {interaction.user.name} ({interaction.user.id})")
            
            async def after_command(interaction: discord.Interaction):
                """Monitor command completion"""
                command_name = interaction.command.name if interaction.command else 'unknown'
                
                self.deployment_stats['successful_responses'] += 1
                
                if command_name in self.deployment_stats['command_statistics']:
                    self.deployment_stats['command_statistics'][command_name]['successful'] += 1
                
                logger.info(f"✅ Command completed: /{command_name}")

            # Add command monitoring
            self.bot.before_invoke(before_command)
            self.bot.after_invoke(after_command)
            
            # Add ready event monitoring
            @self.bot.event
            async def on_ready():
                """Enhanced ready event with deployment info"""
                logger.info(f"🤖 Test bot {self.bot.user.name} is ready!")
                logger.info(f"📊 Bot ID: {self.bot.user.id}")
                logger.info(f"🔗 Guilds: {len(self.bot.guilds)}")
                
                # Start monitoring
                self.deployment_stats['start_time'] = datetime.now()
                self.monitoring_active = True
                
                # Start periodic status reporting
                self.status_reporter.start()
                
                # Log all available commands
                commands = self.bot.tree.get_commands()
                logger.info(f"📋 Available commands ({len(commands)}):")
                for cmd in commands:
                    logger.info(f"  /{cmd.name}: {cmd.description}")
            
            logger.info("✅ Test bot setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup test bot: {e}")
            return False
    
    @tasks.loop(minutes=5)
    async def status_reporter(self):
        """Periodic status reporting"""
        if not self.monitoring_active:
            return
        
        uptime = datetime.now() - self.deployment_stats['start_time']
        
        logger.info("📊 DEPLOYMENT STATUS REPORT")
        logger.info(f"  Uptime: {uptime}")
        logger.info(f"  Commands processed: {self.deployment_stats['commands_processed']}")
        logger.info(f"  Successful responses: {self.deployment_stats['successful_responses']}")
        logger.info(f"  Failed responses: {self.deployment_stats['failed_responses']}")
        logger.info(f"  40060 errors: {self.deployment_stats['error_40060_count']}")
        logger.info(f"  10062 errors: {self.deployment_stats['error_10062_count']}")
        logger.info(f"  Other errors: {self.deployment_stats['other_errors']}")
        
        if self.deployment_stats['commands_processed'] > 0:
            success_rate = (self.deployment_stats['successful_responses'] / self.deployment_stats['commands_processed']) * 100
            logger.info(f"  Success rate: {success_rate:.2f}%")
        
        # Save detailed stats to file
        self.save_deployment_stats()
        
        # Check for critical errors
        if self.deployment_stats['error_40060_count'] > 0 or self.deployment_stats['error_10062_count'] > 0:
            logger.warning("⚠️ CRITICAL ERRORS DETECTED - Review error logs")
    
    def save_deployment_stats(self):
        """Save deployment statistics to file"""
        stats_file = f"deployment_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Convert datetime objects to strings for JSON serialization
        stats_copy = self.deployment_stats.copy()
        if stats_copy['start_time']:
            stats_copy['start_time'] = stats_copy['start_time'].isoformat()
        
        try:
            with open(stats_file, 'w') as f:
                json.dump({
                    'deployment_stats': stats_copy,
                    'error_log': self.error_log[-50:]  # Last 50 errors
                }, f, indent=2)
            
            logger.debug(f"📄 Stats saved to {stats_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save stats: {e}")
    
    async def run_deployment_test(self):
        """Run the deployment test"""
        logger.info("🚀 Starting deployment test...")
        
        if not self.setup_test_bot():
            logger.error("❌ Failed to setup test bot")
            return False
        
        try:
            # Get Discord token
            discord_token = os.getenv('DISCORD_TOKEN')
            if not discord_token:
                logger.error("❌ DISCORD_TOKEN not found")
                return False
            
            # Start the bot
            logger.info("🔌 Connecting to Discord...")
            await self.bot.start(discord_token)
            
        except KeyboardInterrupt:
            logger.info("⏹️ Deployment test stopped by user")
        except Exception as e:
            logger.error(f"❌ Deployment test failed: {e}")
        finally:
            # Cleanup
            self.monitoring_active = False
            if self.status_reporter.is_running():
                self.status_reporter.stop()
            
            # Final stats
            self.print_final_stats()
            
            if self.bot:
                await self.bot.close()
        
        return True
    
    def print_final_stats(self):
        """Print final deployment statistics"""
        logger.info("\n" + "="*60)
        logger.info("FINAL DEPLOYMENT TEST RESULTS")
        logger.info("="*60)
        
        if self.deployment_stats['start_time']:
            uptime = datetime.now() - self.deployment_stats['start_time']
            logger.info(f"Total uptime: {uptime}")
        
        logger.info(f"Commands processed: {self.deployment_stats['commands_processed']}")
        logger.info(f"Successful responses: {self.deployment_stats['successful_responses']}")
        logger.info(f"Failed responses: {self.deployment_stats['failed_responses']}")
        
        logger.info("\n🔍 ERROR ANALYSIS:")
        logger.info(f"40060 errors (already acknowledged): {self.deployment_stats['error_40060_count']}")
        logger.info(f"10062 errors (unknown interaction): {self.deployment_stats['error_10062_count']}")
        logger.info(f"Other errors: {self.deployment_stats['other_errors']}")
        
        if self.deployment_stats['commands_processed'] > 0:
            success_rate = (self.deployment_stats['successful_responses'] / self.deployment_stats['commands_processed']) * 100
            logger.info(f"\n📈 Overall success rate: {success_rate:.2f}%")
        
        # Command statistics
        if self.deployment_stats['command_statistics']:
            logger.info("\n📊 COMMAND STATISTICS:")
            for cmd_name, stats in self.deployment_stats['command_statistics'].items():
                logger.info(f"  /{cmd_name}: {stats['invoked']} invoked, {stats['successful']} successful")
        
        # Critical error summary
        total_critical = self.deployment_stats['error_40060_count'] + self.deployment_stats['error_10062_count']
        if total_critical == 0:
            logger.info("\n✅ SUCCESS: No critical 40060 or 10062 errors detected!")
        else:
            logger.error(f"\n❌ FAILURE: {total_critical} critical errors detected!")
            logger.error("Review the error logs for detailed information.")
        
        # Recent errors
        if self.error_log:
            logger.info(f"\n📋 Recent errors ({min(5, len(self.error_log))} of {len(self.error_log)}):")
            for error in self.error_log[-5:]:
                logger.info(f"  - {error['timestamp']}: {error['error_type']} - {error['error_message']}")
        
        logger.info("="*60)
        
        # Save final stats
        self.save_deployment_stats()


async def main():
    """Main function for deployment testing"""
    print("🤖 Discord Bot Deployment Testing")
    print("="*50)
    print("This script will deploy your bot to Discord for live testing.")
    print("Use this in a test guild to verify error handling works correctly.")
    print("Press Ctrl+C to stop the deployment test.")
    print("="*50)
    
    deployment = TestBotDeployment()
    
    try:
        await deployment.run_deployment_test()
    except Exception as e:
        logger.error(f"❌ Deployment test failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Deployment test stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Deployment test failed: {e}")
        sys.exit(1)
