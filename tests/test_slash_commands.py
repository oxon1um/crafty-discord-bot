#!/usr/bin/env python3
"""
Test script to verify slash commands are properly configured
"""

import os
import sys
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.bot_commands import create_bot

def test_slash_commands():
    """Test that slash commands are properly configured"""
    
    # Load environment variables
    load_dotenv()
    
    # Check required environment variables
    required_vars = ['DISCORD_TOKEN', 'CRAFTY_URL', 'CRAFTY_TOKEN', 'SERVER_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    try:
        # Create bot instance
        bot = create_bot()
        
        # Verify bot is using correct Discord.py version
        print(f"✅ Discord.py version: {discord.__version__}")
        
        # Check if bot has proper intents
        print(f"✅ Bot intents configured: {bot.intents}")
        
        # Check if bot has app commands tree
        print(f"✅ Bot has command tree: {bot.tree is not None}")
        
        # List all registered commands
        commands = bot.tree.get_commands()
        print(f"✅ Registered slash commands ({len(commands)}):")
        for cmd in commands:
            description = getattr(cmd, 'description', '')
            print(f"  - /{cmd.name}: {description}")
        
        # Verify command types
        for cmd in commands:
            if isinstance(cmd, app_commands.Command):
                print(f"✅ Command /{cmd.name} is properly configured as app_commands.Command")
            else:
                print(f"❌ Command /{cmd.name} is not properly configured")
                return False
        
        # Check if the bot has the required configuration
        if hasattr(bot, 'crafty_url') and hasattr(bot, 'crafty_token'):
            print("✅ Bot has Crafty configuration")
        else:
            print("❌ Bot missing Crafty configuration")
            return False
        
        # Check server ID format
        if hasattr(bot, 'server_id'):
            print(f"✅ Bot has server ID: {bot.server_id}")
        else:
            print("❌ Bot missing server ID")
            return False
        
        print("\n🎉 All slash command tests passed!")
        print("\nNext steps:")
        print("1. Make sure your bot is invited to Discord with both 'bot' and 'applications.commands' scopes")
        print("2. Ensure the bot has the following permissions:")
        print("   - Send Messages")
        print("   - Use Slash Commands") 
        print("   - Embed Links")
        print("3. Run the bot and check if slash commands appear in Discord")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating bot: {e}")
        return False

if __name__ == "__main__":
    success = test_slash_commands()
    sys.exit(0 if success else 1)
