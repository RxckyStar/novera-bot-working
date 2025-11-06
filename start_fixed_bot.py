#!/usr/bin/env python3
"""
Ultra Simple Discord Bot Starter
--------------------------------
This starter script avoids all the complexity and directly starts the bot
with the simplest possible asyncio handling, without any imports of 
complex fixes that might conflict with each other.
"""

import logging
import asyncio
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("start_fixed_bot.log")
    ]
)
logger = logging.getLogger(__name__)

async def start_bot():
    """Start the bot with the simplest possible method"""
    try:
        # Import the bot (this will set up the Flask server too)
        from bot import bot, TOKEN
        
        if not TOKEN:
            logger.critical("No Discord token found in environment!")
            return
            
        clean_token = TOKEN.strip().strip('"').strip("'")
        logger.info(f"Starting bot with token length: {len(clean_token)}")
        
        # Two-step approach to start the bot - this works better than bot.run()
        logger.info("Logging in...")
        await bot.login(clean_token)
        logger.info("Connecting to gateway...")
        await bot.connect(reconnect=True)
        
    except Exception as e:
        logger.critical(f"Error starting bot: {e}")
        import traceback
        logger.critical(traceback.format_exc())
        sys.exit(1)

def main():
    """Main entry point that handles the event loop properly"""
    try:
        logger.info("Starting bot with ultra simple approach")
        
        # Get or create an event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            logger.info("No event loop found, creating new one")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Check if the loop is already running
        if loop.is_running():
            logger.info("Event loop is already running, creating a task")
            # Create a task in the running loop
            asyncio.create_task(start_bot())
        else:
            logger.info("Running event loop until complete")
            # Run the coroutine using the loop directly
            loop.run_until_complete(start_bot())
            
    except Exception as e:
        logger.critical(f"Critical error in bot startup: {e}")
        import traceback
        logger.critical(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()