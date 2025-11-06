"""
Ultra-simplified Discord bot fix
-------------------------------
This completely replaces all the complex fixes with ONE simple solution
that actually works.
"""

import asyncio
import logging

async def safe_timeout(coro, timeout_seconds=10):
    """Core fix for the timeout context manager error"""
    task = asyncio.create_task(coro)
    try:
        async with asyncio.timeout(timeout_seconds):
            return await task
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        raise

# Core function to start a Discord bot properly
def start_bot_properly(bot, token):
    """Start a Discord bot with the correct event loop approach"""
    # Define the simple bot runner
    async def run_bot():
        try:
            await bot.start(token)
        except Exception as e:
            logging.error(f"Error in bot.start: {e}")
            import traceback
            traceback.print_exc()
    
    # Get the current loop
    loop = asyncio.get_event_loop()
    
    # Run it properly based on loop state
    if loop.is_running():
        logging.info("Event loop is already running, using create_task")
        task = loop.create_task(run_bot())
        return task
    else:
        logging.info("No event loop running, using run_until_complete")
        return loop.run_until_complete(run_bot())