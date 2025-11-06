#!/usr/bin/env python3
"""
Clean entry point for Discord bot with improved event loop handling
-------------------------------------------------------------------
This script provides a clean, reliable way to start the Discord bot
without the asyncio.run() issues that cause event loop errors.
"""

import asyncio
import logging
import os
import sys
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("run_bot.log")
    ]
)
logger = logging.getLogger(__name__)

def get_or_create_event_loop():
    """Get the current event loop or create a new one."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

async def start_bot(token):
    """
    Two-step approach to start the bot - more reliable than bot.run().
    This avoids the use of asyncio.run() which causes conflicts.
    """
    try:
        from bot import bot
        
        # First step: Login to Discord
        logger.info("Logging in to Discord...")
        await bot.login(token)
        
        # Second step: Connect with auto-reconnect
        logger.info("Connecting to Discord gateway...")
        await bot.connect(reconnect=True)
        
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        logger.critical(traceback.format_exc())
        raise

def main():
    """Main entry point with proper event loop handling"""
    try:
        logger.info("Starting Discord bot with clean approach")
        
        # Get token from environment
        token = os.environ.get('DISCORD_TOKEN')
        if not token:
            logger.critical("No Discord token found in environment!")
            sys.exit(1)
            
        # Clean up token
        clean_token = token.strip().strip('"').strip("'")
        logger.info(f"Using token with length: {len(clean_token)}")
        
        # Get or create event loop
        loop = get_or_create_event_loop()
        
        # Start bot based on loop state
        if loop.is_running():
            logger.info("Event loop is already running, creating task")
            asyncio.create_task(start_bot(clean_token))
        else:
            logger.info("Running event loop until complete")
            loop.run_until_complete(start_bot(clean_token))
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.critical(f"Error in main: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()