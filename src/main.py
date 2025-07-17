import os
import asyncio
import logging
import uuid
from typing import List, NoReturn
from dotenv import load_dotenv
from utils.bot_commands import create_bot
from utils.monitoring import initialize_sentry, capture_exception, get_monitoring_status

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main() -> None:
    """Main function to run the bot"""
    # Initialize monitoring system (optional)
    sentry_enabled = initialize_sentry()
    monitoring_status = get_monitoring_status()
    logging.info(f"Monitoring status: {monitoring_status}")
    
    # Validate environment variables
    required_vars: List[str] = ['DISCORD_TOKEN', 'CRAFTY_URL', 'CRAFTY_TOKEN', 'SERVER_ID', 'GUILD_ID']
    missing_vars: List[str] = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return
    
    # Validate SERVER_ID format
    server_id = os.getenv('SERVER_ID')
    try:
        uuid.UUID(server_id)
    except ValueError:
        logging.error("SERVER_ID must be a valid UUID")
        return
    
    # Initialize and run the bot
    bot = create_bot()
    
    try:
        discord_token = os.getenv('DISCORD_TOKEN')
        if not discord_token:
            logging.error("DISCORD_TOKEN environment variable is required")
            return
        await bot.start(discord_token)
    except KeyboardInterrupt:
        logging.info("Bot shutdown requested by user")
    except Exception as e:
        logging.error(f"Bot crashed with error: {e}")
        capture_exception(e, {
            'component': 'main',
            'stage': 'bot_startup',
            'server_id': server_id if 'server_id' in locals() else None
        })
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
