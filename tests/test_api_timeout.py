#!/usr/bin/env python3
"""
Test script to reproduce and capture CraftyAPITimeoutError
This script will attempt to connect to the Crafty API and capture timeout errors.
"""

import os
import asyncio
import logging
import traceback
from datetime import datetime
from dotenv import load_dotenv
from src.utils.crafty_api import CraftyAPI, CraftyAPITimeoutError, CraftyAPIError

# Configure logging to capture all details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_api_timeout():
    """Test function to reproduce API timeout errors"""
    
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    crafty_url = os.getenv('CRAFTY_URL')
    crafty_token = os.getenv('CRAFTY_TOKEN')
    server_id = os.getenv('SERVER_ID')
    
    logger.info("=== STARTING API TIMEOUT TEST ===")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info(f"Environment Variables:")
    logger.info(f"  CRAFTY_URL: {crafty_url}")
    logger.info(f"  CRAFTY_TOKEN: {'*' * 10}...{crafty_token[-4:] if crafty_token else 'None'}")
    logger.info(f"  SERVER_ID: {server_id}")
    
    if not all([crafty_url, crafty_token, server_id]):
        logger.error("Missing required environment variables")
        return
    
    # Test different API endpoints
    endpoints_to_test = [
        ("get_server_stats", lambda api: api.get_server_stats(server_id)),
        ("get_server_info", lambda api: api.get_server_info(server_id)),
        ("start_server", lambda api: api.start_server(server_id)),
    ]
    
    for endpoint_name, endpoint_func in endpoints_to_test:
        logger.info(f"\n--- Testing {endpoint_name} ---")
        try:
            async with CraftyAPI(crafty_url, crafty_token) as api:
                logger.info(f"Making request to {endpoint_name}...")
                response = await endpoint_func(api)
                logger.info(f"Response received: {response.success}")
                if not response.success:
                    logger.error(f"API Error: {response.message}")
                    logger.error(f"Error Code: {response.error_code}")
                    
        except CraftyAPITimeoutError as e:
            logger.error(f"TIMEOUT ERROR on {endpoint_name}:")
            logger.error(f"  Error message: {e}")
            logger.error(f"  Status code: {e.status_code}")
            logger.error(f"  Traceback:\n{traceback.format_exc()}")
            
        except CraftyAPIError as e:
            logger.error(f"API ERROR on {endpoint_name}:")
            logger.error(f"  Error message: {e}")
            logger.error(f"  Status code: {e.status_code}")
            logger.error(f"  Traceback:\n{traceback.format_exc()}")
            
        except Exception as e:
            logger.error(f"UNEXPECTED ERROR on {endpoint_name}:")
            logger.error(f"  Error message: {e}")
            logger.error(f"  Error type: {type(e)}")
            logger.error(f"  Traceback:\n{traceback.format_exc()}")
    
    logger.info("\n=== API TIMEOUT TEST COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(test_api_timeout())
