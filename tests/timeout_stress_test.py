#!/usr/bin/env python3
"""
Extended timeout test to reproduce CraftyAPITimeoutError under various conditions
"""

import os
import asyncio
import logging
import traceback
import time
from datetime import datetime
from dotenv import load_dotenv
from src.utils.crafty_api import CraftyAPI, CraftyAPITimeoutError, CraftyAPIError

# Configure logging to capture all details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def stress_test_api():
    """Stress test the API to reproduce timeout errors"""
    
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    crafty_url = os.getenv('CRAFTY_URL')
    crafty_token = os.getenv('CRAFTY_TOKEN')
    server_id = os.getenv('SERVER_ID')
    
    logger.info("=== STARTING API STRESS TEST ===")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info(f"Environment Variables:")
    logger.info(f"  CRAFTY_URL: {crafty_url}")
    logger.info(f"  CRAFTY_TOKEN: {'*' * 10}...{crafty_token[-4:] if crafty_token else 'None'}")
    logger.info(f"  SERVER_ID: {server_id}")
    
    if not all([crafty_url, crafty_token, server_id]):
        logger.error("Missing required environment variables")
        return
    
    # Test 1: Rapid concurrent requests
    logger.info("\\n--- Test 1: Concurrent requests ---")
    
    async def make_concurrent_request(request_id):
        try:
            async with CraftyAPI(crafty_url, crafty_token) as api:
                start_time = time.time()
                response = await api.get_server_stats(server_id)
                end_time = time.time()
                logger.info(f"Request {request_id}: {response.success} (took {end_time - start_time:.2f}s)")
                return response.success
        except CraftyAPITimeoutError as e:
            logger.error(f"Request {request_id} TIMEOUT: {e}")
            return False
        except Exception as e:
            logger.error(f"Request {request_id} ERROR: {e}")
            return False
    
    # Launch 10 concurrent requests
    tasks = [make_concurrent_request(i) for i in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    successful = sum(1 for r in results if r is True)
    logger.info(f"Concurrent test: {successful}/{len(tasks)} requests successful")
    
    # Test 2: Rapid sequential requests
    logger.info("\\n--- Test 2: Rapid sequential requests ---")
    
    for i in range(20):
        try:
            async with CraftyAPI(crafty_url, crafty_token) as api:
                start_time = time.time()
                response = await api.get_server_stats(server_id)
                end_time = time.time()
                logger.info(f"Sequential request {i+1}: {response.success} (took {end_time - start_time:.2f}s)")
        except CraftyAPITimeoutError as e:
            logger.error(f"Sequential request {i+1} TIMEOUT: {e}")
        except Exception as e:
            logger.error(f"Sequential request {i+1} ERROR: {e}")
        
        # Small delay to prevent overwhelming the server
        await asyncio.sleep(0.1)
    
    # Test 3: Test with different timeout values
    logger.info("\\n--- Test 3: Different timeout values ---")
    
    timeout_values = [1, 5, 10, 15, 30]
    for timeout_val in timeout_values:
        logger.info(f"Testing with {timeout_val}s timeout...")
        try:
            # Create a custom API instance with different timeout
            import aiohttp
            connector = aiohttp.TCPConnector(limit=10, ssl=False)
            session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout_val),
                connector=connector
            )
            
            # Manual API call to test timeout behavior
            headers = {
                "Authorization": f"Bearer {crafty_token}",
                "Content-Type": "application/json"
            }
            url = f"{crafty_url}/api/v2/servers/{server_id}/stats"
            
            start_time = time.time()
            async with session.get(url, headers=headers) as response:
                await response.json()
                end_time = time.time()
                logger.info(f"Timeout {timeout_val}s: SUCCESS (took {end_time - start_time:.2f}s)")
            
            await session.close()
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout {timeout_val}s: TIMEOUT ERROR")
        except Exception as e:
            logger.error(f"Timeout {timeout_val}s: ERROR {e}")
    
    logger.info("\\n=== API STRESS TEST COMPLETED ===")

async def test_discord_bot_timeout():
    """Test the timeout behavior as it would occur in the Discord bot"""
    
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    crafty_url = os.getenv('CRAFTY_URL')
    crafty_token = os.getenv('CRAFTY_TOKEN')
    server_id = os.getenv('SERVER_ID')
    
    logger.info("\\n=== DISCORD BOT TIMEOUT SIMULATION ===")
    
    # Simulate the bot command timeout behavior (2.5 seconds)
    for i in range(5):
        logger.info(f"\\n--- Bot simulation {i+1} ---")
        try:
            async with CraftyAPI(crafty_url, crafty_token) as api:
                # This matches the timeout used in bot_commands.py
                async with asyncio.timeout(2.5):
                    response = await api.get_server_stats(server_id)
                    logger.info(f"Bot simulation {i+1}: SUCCESS")
        except asyncio.TimeoutError:
            logger.error(f"Bot simulation {i+1}: TIMEOUT (matches bot behavior)")
        except Exception as e:
            logger.error(f"Bot simulation {i+1}: ERROR {e}")
        
        await asyncio.sleep(1)  # Wait between attempts

if __name__ == "__main__":
    asyncio.run(stress_test_api())
    asyncio.run(test_discord_bot_timeout())
