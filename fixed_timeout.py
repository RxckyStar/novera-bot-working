#!/usr/bin/env python3
"""
Discord Bot Timeout Fix
-----------------------
This module provides a safe approach to starting Discord bots
that prevents common asyncio-related errors including:
- RuntimeError: asyncio.run() cannot be called from a running event loop
- RuntimeError: Timeout context manager should be used inside a task
"""

import asyncio
import sys
import time
import logging
import traceback
from typing import Optional, Any, Coroutine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fixed_timeout.log')
    ]
)

def is_event_loop_running() -> bool:
    """Check if an event loop is currently running in this thread."""
    try:
        return asyncio.get_event_loop().is_running()
    except RuntimeError:
        return False

def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get the current event loop or create a new one if necessary."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop exists for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

def safe_discord_start(bot: Any, token: str, *, reconnect: bool = True) -> None:
    """
    Start a Discord bot safely, handling all known asyncio issues.
    
    This function handles all the common error cases that can occur
    when starting a Discord bot and ensures it starts properly.
    
    Args:
        bot: The Discord bot object to start
        token: The Discord authentication token
        reconnect: Whether to reconnect automatically, defaults to True
    """
    logging.info("Starting Discord bot with SIMPLIFIED safe_discord_start...")
    
    # Get the existing event loop without creating a new one
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Define a single consistent coroutine to run the bot
    async def run_bot():
        try:
            await bot.start(token, reconnect=reconnect)
        except Exception as e:
            logging.error(f"Error in bot.start: {e}")
            traceback.print_exc()
    
    # If loop is already running (e.g., in Replit or Flask context)
    if loop.is_running():
        logging.info("Event loop is already running, creating task")
        # Simply create a task - this is the key fix!
        task = loop.create_task(run_bot())
        logging.info(f"Bot task created: {task}")
    else:
        # If no loop is running, use run_until_complete
        logging.info("No event loop running, using run_until_complete")
        try:
            loop.run_until_complete(run_bot())
        except Exception as e:
            logging.error(f"Error in run_until_complete: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    logging.warning("This module is not meant to be run directly.")