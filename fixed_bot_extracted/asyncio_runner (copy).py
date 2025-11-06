"""
Robust asyncio runner for Discord bots
This module handles asyncio event loop management to prevent common errors:
- "asyncio.run() cannot be called from a running event loop"
- "This event loop is already running"

It provides a robust way to start asyncio tasks regardless of the current event loop state.
"""
import asyncio
import logging
import sys
import threading
import time
from typing import Callable, Any, Coroutine, Optional

logger = logging.getLogger(__name__)

def is_event_loop_running() -> bool:
    """Check if an event loop is currently running in this thread."""
    try:
        loop = asyncio.get_event_loop()
        return loop.is_running()
    except RuntimeError:
        # No event loop exists yet
        return False

def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get the current event loop or create a new one if necessary."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop exists, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

def run_async_function(coro_func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs) -> Any:
    """
    Run an async function in the most appropriate way based on the current event loop state.
    This handles all the common scenarios and prevents event loop errors.
    """
    async def wrapper():
        """Wrapper coroutine to call the target function with arguments."""
        try:
            return await coro_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in async function {coro_func.__name__}: {e}", exc_info=True)
            raise

    # Check current event loop state
    if is_event_loop_running():
        # We're already in a running event loop, create a task
        logger.info(f"Creating task for {coro_func.__name__} in existing event loop")
        loop = asyncio.get_event_loop()
        future = asyncio.run_coroutine_threadsafe(wrapper(), loop)
        return future.result()
    else:
        # No running event loop, use asyncio.run()
        try:
            logger.info(f"Running {coro_func.__name__} with asyncio.run()")
            return asyncio.run(wrapper())
        except RuntimeError as e:
            # Handle edge cases where there might be a running loop that we couldn't detect
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                logger.warning(f"Event loop detection failed, using alternative startup for {coro_func.__name__}")
                loop = get_or_create_event_loop()
                future = asyncio.run_coroutine_threadsafe(wrapper(), loop)
                return future.result()
            else:
                # Some other error occurred
                logger.error(f"Unexpected error running async function: {e}", exc_info=True)
                raise

def start_background_loop(stop_event: Optional[threading.Event] = None) -> asyncio.AbstractEventLoop:
    """
    Start an event loop in the background that runs forever until stopped.
    Returns the running loop.
    """
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    
    def _run_loop_forever():
        """Set the event loop for this thread and run it forever."""
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            loop.close()
            logger.info("Background event loop closed")
    
    if stop_event is not None:
        # Set up a task to check for the stop event
        async def monitor_stop_event():
            while not stop_event.is_set():
                await asyncio.sleep(0.1)
            logger.info("Stop event detected, stopping background loop")
            loop.stop()
        
        loop.create_task(monitor_stop_event())
    
    # Start the loop in a background thread
    thread = threading.Thread(target=_run_loop_forever, daemon=True)
    thread.start()
    
    # Allow a short time for the thread to start the loop
    time.sleep(0.1)
    
    logger.info("Background event loop started")
    return loop

def run_discord_bot(start_func: Callable[[], Coroutine[Any, Any, Any]]) -> None:
    """
    Run a Discord bot with proper asyncio handling.
    This function contains extra safeguards specifically for Discord.py bots.
    
    Args:
        start_func: Async function that starts the bot (e.g., bot.start(token))
    """
    try:
        logger.info("Starting Discord bot with robust asyncio handling")
        run_async_function(start_func)
    except Exception as e:
        # If we get here, all primary and fallback methods failed
        logger.critical(f"All methods to start the bot failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    async def example_bot_start():
        """Example async function that mimics a bot start function"""
        logger.info("Bot is starting...")
        await asyncio.sleep(2)  # Simulate bot startup time
        logger.info("Bot has started!")
        
        # Keep the bot running
        while True:
            await asyncio.sleep(1)
            logger.info("Bot is still running...")
    
    # Start the example bot using our robust runner
    run_discord_bot(example_bot_start)
def safe_run_task(coro: Coroutine[Any, Any, T]) -> Optional[T]:
    """
    Run a coroutine in a task with proper error handling.
    This ensures the coroutine runs in a task context, which is required for timeouts.
    
    Args:
        coro: The coroutine to run
        
    Returns:
        The result of the coroutine, or None if an error occurred
    """
    try:
        # Check if we're already in a running event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in a running loop, create a task
            task = loop.create_task(coro)
            return loop.run_until_complete(task)
        except RuntimeError:
            # No running loop, use asyncio.run
            return asyncio.run(coro)
    except Exception as e:
        logger.error(f"Error in safe_run_task: {e}", exc_info=True)
        return None
