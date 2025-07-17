#!/usr/bin/env python3
"""
Live testing script for stress-testing Discord bot commands.
This script helps verify that the bot handles rapid command execution without
encountering 40060 (interaction already acknowledged) or 10062 (unknown interaction) errors.
"""

import asyncio
import logging
import os
import sys
import time
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.bot_commands import create_bot

# Configure logging to capture both bot logs and test logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('live_test_results.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class LiveTestBot:
    """Live testing framework for Discord bot commands"""
    
    def __init__(self):
        self.bot = None
        self.test_results = {
            'commands_executed': 0,
            'successful_responses': 0,
            'failed_responses': 0,
            'errors_40060': 0,
            'errors_10062': 0,
            'other_errors': 0,
            'timeouts': 0
        }
        self.error_log = []
    
    async def setup_bot(self):
        """Setup the bot for testing"""
        logger.info("Setting up bot for live testing...")
        
        # Load environment variables
        load_dotenv()
        
        # Validate required environment variables
        required_vars = ['DISCORD_TOKEN', 'CRAFTY_URL', 'CRAFTY_TOKEN', 'SERVER_ID', 'GUILD_ID']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
        
        try:
            # Create bot instance
            self.bot = create_bot()
            
            # Override the error handler to capture test metrics
            original_error_handler = self.bot.tree.error
            
            async def test_error_handler(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
                """Custom error handler that logs test metrics"""
                self.test_results['failed_responses'] += 1
                
                # Check for specific error codes
                if hasattr(error, 'code'):
                    if error.code == 40060:
                        self.test_results['errors_40060'] += 1
                        logger.error(f"40060 error detected: {error}")
                    elif error.code == 10062:
                        self.test_results['errors_10062'] += 1
                        logger.error(f"10062 error detected: {error}")
                    else:
                        self.test_results['other_errors'] += 1
                        logger.error(f"Other error detected (code {error.code}): {error}")
                else:
                    self.test_results['other_errors'] += 1
                    logger.error(f"Error without code: {error}")
                
                # Log error details
                self.error_log.append({
                    'timestamp': time.time(),
                    'interaction_id': interaction.id,
                    'error_type': type(error).__name__,
                    'error_message': str(error),
                    'error_code': getattr(error, 'code', None)
                })
                
                # Call original error handler
                await original_error_handler(interaction, error)
            
            # Replace the error handler
            self.bot.tree.error = test_error_handler
            
            logger.info("Bot setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup bot: {e}")
            return False
    
    async def run_command_stress_test(self, command_name: str, iterations: int = 10, delay: float = 0.1):
        """Run stress test for a specific command"""
        logger.info(f"Starting stress test for /{command_name} - {iterations} iterations with {delay}s delay")
        
        # Get the command
        command = self.bot.tree.get_command(command_name)
        if not command:
            logger.error(f"Command /{command_name} not found")
            return False
        
        # Create mock interaction for testing
        guild_id = int(os.getenv('GUILD_ID'))
        guild = discord.Object(id=guild_id)
        
        for i in range(iterations):
            try:
                # Create a mock interaction
                interaction = await self.create_mock_interaction(guild, command)
                
                # Execute the command
                logger.info(f"Executing /{command_name} - iteration {i + 1}/{iterations}")
                self.test_results['commands_executed'] += 1
                
                # Run the command with timeout
                try:
                    await asyncio.wait_for(command.callback(interaction), timeout=10.0)
                    self.test_results['successful_responses'] += 1
                    logger.info(f"✅ Command /{command_name} executed successfully - iteration {i + 1}")
                except asyncio.TimeoutError:
                    self.test_results['timeouts'] += 1
                    logger.warning(f"⏱️ Command /{command_name} timed out - iteration {i + 1}")
                
                # Wait before next iteration
                await asyncio.sleep(delay)
                
            except Exception as e:
                self.test_results['failed_responses'] += 1
                logger.error(f"❌ Error executing /{command_name} - iteration {i + 1}: {e}")
                self.error_log.append({
                    'timestamp': time.time(),
                    'command': command_name,
                    'iteration': i + 1,
                    'error': str(e)
                })
        
        logger.info(f"Stress test for /{command_name} completed")
        return True
    
    async def create_mock_interaction(self, guild, command):
        """Create a mock interaction for testing"""
        # This is a simplified mock - in a real test environment,
        # you'd want to use actual Discord interactions
        class MockInteraction:
            def __init__(self, guild, command):
                self.guild = guild
                self.command = command
                self.id = int(time.time() * 1000000)  # Unique ID
                self.is_expired = lambda: False
                self.response = MockResponse()
                self.followup = MockFollowup()
                self.user = MockUser()
                self.channel = MockChannel()
            
            async def response_defer(self, thinking=False):
                """Mock defer response"""
                pass
        
        class MockResponse:
            def __init__(self):
                self.is_done = lambda: False
                self.send_message = self.mock_send_message
            
            async def mock_send_message(self, *args, **kwargs):
                """Mock send message"""
                logger.debug(f"Mock response.send_message called with: {args}, {kwargs}")
                return True
            
            async def defer(self, thinking=False):
                """Mock defer"""
                logger.debug(f"Mock response.defer called with thinking={thinking}")
                return True
        
        class MockFollowup:
            async def send(self, *args, **kwargs):
                """Mock followup send"""
                logger.debug(f"Mock followup.send called with: {args}, {kwargs}")
                return True
        
        class MockUser:
            def __init__(self):
                self.id = 123456789
                self.name = "TestUser"
        
        class MockChannel:
            def __init__(self):
                self.id = 987654321
                self.name = "test-channel"
        
        return MockInteraction(guild, command)
    
    async def run_rapid_fire_test(self, delay: float = 0.05):
        """Run rapid-fire test with multiple commands"""
        logger.info("Starting rapid-fire test with multiple commands")
        
        commands_to_test = ['help', 'status']  # Start with safe commands
        
        for _ in range(5):  # 5 rounds of rapid fire
            for command_name in commands_to_test:
                await self.run_command_stress_test(command_name, iterations=3, delay=delay)
                await asyncio.sleep(delay)
        
        logger.info("Rapid-fire test completed")
    
    async def run_concurrent_test(self, command_name: str, concurrent_count: int = 5):
        """Run concurrent command executions"""
        logger.info(f"Starting concurrent test for /{command_name} - {concurrent_count} concurrent executions")
        
        command = self.bot.tree.get_command(command_name)
        if not command:
            logger.error(f"Command /{command_name} not found")
            return False
        
        guild_id = int(os.getenv('GUILD_ID'))
        guild = discord.Object(id=guild_id)
        
        async def execute_command(iteration):
            try:
                interaction = await self.create_mock_interaction(guild, command)
                logger.info(f"Concurrent execution {iteration} for /{command_name}")
                
                self.test_results['commands_executed'] += 1
                await command.callback(interaction)
                self.test_results['successful_responses'] += 1
                
            except Exception as e:
                self.test_results['failed_responses'] += 1
                logger.error(f"Concurrent execution {iteration} failed: {e}")
        
        # Execute all commands concurrently
        tasks = [execute_command(i) for i in range(concurrent_count)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Concurrent test for /{command_name} completed")
        return True
    
    def print_test_results(self):
        """Print comprehensive test results"""
        logger.info("\n" + "="*50)
        logger.info("LIVE TEST RESULTS")
        logger.info("="*50)
        
        logger.info(f"Commands executed: {self.test_results['commands_executed']}")
        logger.info(f"Successful responses: {self.test_results['successful_responses']}")
        logger.info(f"Failed responses: {self.test_results['failed_responses']}")
        logger.info(f"Timeouts: {self.test_results['timeouts']}")
        
        logger.info("\nError Breakdown:")
        logger.info(f"40060 errors (already acknowledged): {self.test_results['errors_40060']}")
        logger.info(f"10062 errors (unknown interaction): {self.test_results['errors_10062']}")
        logger.info(f"Other errors: {self.test_results['other_errors']}")
        
        if self.test_results['commands_executed'] > 0:
            success_rate = (self.test_results['successful_responses'] / self.test_results['commands_executed']) * 100
            logger.info(f"\nSuccess rate: {success_rate:.2f}%")
        
        if self.error_log:
            logger.info(f"\nDetailed error log ({len(self.error_log)} entries):")
            for error in self.error_log[-5:]:  # Show last 5 errors
                logger.info(f"  - {error}")
        
        # Check for critical errors
        if self.test_results['errors_40060'] > 0 or self.test_results['errors_10062'] > 0:
            logger.error("⚠️ CRITICAL: 40060 or 10062 errors detected!")
        else:
            logger.info("✅ No critical 40060 or 10062 errors detected")
        
        logger.info("="*50)
    
    async def run_full_test_suite(self):
        """Run the complete test suite"""
        logger.info("Starting full test suite...")
        
        # Test 1: Basic command stress test
        await self.run_command_stress_test('help', iterations=20, delay=0.1)
        
        # Test 2: Status command stress test
        await self.run_command_stress_test('status', iterations=15, delay=0.2)
        
        # Test 3: Rapid fire test
        await self.run_rapid_fire_test(delay=0.05)
        
        # Test 4: Concurrent execution test
        await self.run_concurrent_test('help', concurrent_count=10)
        
        logger.info("Full test suite completed")


async def main():
    """Main function to run live tests"""
    print("Discord Bot Live Testing Framework")
    print("=" * 50)
    
    test_bot = LiveTestBot()
    
    # Setup bot
    if not await test_bot.setup_bot():
        print("❌ Failed to setup bot")
        return
    
    try:
        # Run tests
        await test_bot.run_full_test_suite()
        
    except KeyboardInterrupt:
        logger.info("Testing interrupted by user")
    except Exception as e:
        logger.error(f"Testing failed with error: {e}")
    finally:
        # Print results
        test_bot.print_test_results()
        
        # Close bot
        if test_bot.bot:
            await test_bot.bot.close()


if __name__ == "__main__":
    print("⚠️  WARNING: This is a live testing script.")
    print("Make sure you're running this against a test guild, not a production environment.")
    print("Press Ctrl+C to stop at any time.")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTesting stopped by user")
    except Exception as e:
        print(f"\nTesting failed: {e}")
        sys.exit(1)
