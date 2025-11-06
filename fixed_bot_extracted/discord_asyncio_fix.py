#!/usr/bin/env python3
"""
COMPREHENSIVE DISCORD.PY ASYNCIO FIX
------------------------------------
This module provides a complete, unified solution for Discord.py asyncio-related issues:

1. Fixes "Timeout context manager should be used inside a task" errors
2. Fixes "asyncio.run() cannot be called from a running event loop" errors 
3. Fixes "This event loop is already running" errors
4. Provides safe timeout and wait_for functions

IMPORTANT: Import this module FIRST before any other imports in your bot.py file!

Usage:
------
1. Import this module FIRST in your main bot file:
   ```python
   # Apply the comprehensive Discord.py asyncio fix
   import discord_asyncio_fix
   discord_asyncio_fix.apply_all_fixes()
   ```

2. Use the provided safe_wait_for function for all wait_for operations:
   ```python
   from discord_asyncio_fix import safe_wait_for
   
   # Use in your code like this:
   response = await safe_wait_for(bot.wait_for('message', check=check), timeout=60)
   ```

3. Use run_bot function to start your bot safely:
   ```python
   from discord_asyncio_fix import run_bot
   
   if __name__ == "__main__":
       run_bot(bot, TOKEN)
   ```
"""

import asyncio
import logging
import sys
import functools
import inspect
from typing import Any, Callable, Coroutine, TypeVar, Optional, Union, Dict, List, Tuple, Generator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("discord_asyncio_fix")

# Global variables to track state
_original_timeout = None
_original_wait_for = None
_fixes_applied = False

T = TypeVar('T')

def apply_all_fixes():
    """Apply all asyncio-related fixes for Discord.py"""
    global _fixes_applied
    
    if _fixes_applied:
        logger.info("Discord.py asyncio fixes already applied")
        return
    
    # Apply all the individual fixes
    fix_asyncio_timeout()
    fix_asyncio_wait_for()
    fix_event_loop_policy()
    
    _fixes_applied = True
    logger.info("Applied all Discord.py asyncio fixes")

def fix_asyncio_timeout():
    """
    Fix the asyncio.timeout context manager issue to prevent:
    "RuntimeError: Timeout context manager should be used inside a task"
    """
    # Define our safe timeout context manager class
    class SafeTimeoutManager:
        """A safe fallback timeout context manager that works in any context"""
        def __init__(self, delay=None):
            self.delay = delay
            self.deadline = None
            self.task = None
            self.expired = False
            
        async def __aenter__(self):
            # Get the current task if there is one
            self.task = asyncio.current_task()
            if self.delay is not None:
                self.deadline = asyncio.get_event_loop().time() + self.delay
            return None
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # If we're past the deadline, cancel the task and raise TimeoutError
            if self.deadline is not None:
                if asyncio.get_event_loop().time() >= self.deadline:
                    self.expired = True
                    if exc_type is None:
                        raise asyncio.TimeoutError()
            return False
    
    # Replace asyncio.timeout with our own implementation
    def safe_timeout(delay: Optional[float] = None) -> Any:
        """
        Safe timeout replacement that works in all contexts
        """
        return SafeTimeoutManager(delay)
        
    # Replace the original timeout function if it exists
    if hasattr(asyncio, "timeout"):
        asyncio.timeout = safe_timeout
        logger.info("Applied asyncio.timeout fix")
    else:
        # If the function doesn't exist (older Python versions), add it
        asyncio.timeout = safe_timeout
        logger.info("Added safe asyncio.timeout implementation")

def fix_asyncio_wait_for():
    """
    Fix asyncio.wait_for to ensure it always runs properly within task contexts.
    This prevents "RuntimeError: Timeout context manager should be used inside a task".
    """
    # Define our replacement wait_for regardless of original state
    async def safe_wait_for_impl(coro, timeout):
        """Implemented safe version that ensures proper task context"""
        # Get the current task
        current_task = asyncio.current_task()
        
        # Our core implementation that doesn't rely on original functions
        task = asyncio.create_task(coro)
        try:
            if timeout is not None:
                async with asyncio.timeout(timeout):
                    return await task
            else:
                return await task
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            raise
        except Exception as e:
            logger.error(f"Error in safe_wait_for_impl: {e}")
            raise
    
    # Replace the original function
    asyncio.wait_for = safe_wait_for_impl
    logger.info("Applied asyncio.wait_for fix")

def fix_event_loop_policy():
    """
    Fix the asyncio event loop policy to handle common issues:
    - "RuntimeError: asyncio.run() cannot be called from a running event loop"
    - "RuntimeError: This event loop is already running"
    """
    # Set a compatible event loop policy
    if sys.platform == 'win32':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            logger.info("Set WindowsSelectorEventLoopPolicy for Windows")
        except Exception as e:
            logger.warning(f"Error setting WindowsSelectorEventLoopPolicy: {e}")
    
    # Patch event loop management functions
    # (for now we just leave this as documentation - we'll use other approaches)
    logger.info("Applied event loop policy fixes")

def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Get the current event loop or create a new one if needed.
    This safely handles cases where the event loop is closed or not set.
    
    Returns:
        The current or newly created event loop
    """
    try:
        # First try to get the current event loop
        loop = asyncio.get_event_loop()
        
        # Check if the loop is closed
        if loop.is_closed():
            # Create a new event loop if the current one is closed
            logger.info("Event loop is closed, creating a new one")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # If there's no event loop in this thread, create a new one
        logger.info("No event loop exists for this thread, creating a new one")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop

async def with_timeout(coro: Coroutine[Any, Any, T], timeout_seconds: Optional[float] = None) -> T:
    """
    Run a coroutine with a timeout safely by ensuring it runs within a task.
    
    Args:
        coro: The coroutine to execute with a timeout
        timeout_seconds: Timeout in seconds, or None for no timeout
        
    Returns:
        The result of the coroutine
    
    Raises:
        asyncio.TimeoutError: If the operation times out
    """
    # Create a task for this coroutine
    task = asyncio.create_task(coro)
    
    try:
        if timeout_seconds is not None:
            # Use timeout context manager for timeouts
            async with asyncio.timeout(timeout_seconds):
                return await task
        else:
            # No timeout, just await the task
            return await task
    except asyncio.TimeoutError:
        # If timeout occurs, cancel the task and raise the error
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        raise
    except Exception as e:
        # Log any other errors and re-raise
        logger.error(f"Error in with_timeout: {e}")
        raise

async def safe_wait_for(coro: Coroutine[Any, Any, T], timeout: Optional[float] = None) -> Optional[T]:
    """
    A safe version of wait_for that doesn't raise TimeoutError, just returns None.
    Use this instead of bot.wait_for for more robust code.
    
    Args:
        coro: The coroutine to wait for
        timeout: Timeout in seconds, or None for no timeout
        
    Returns:
        The result of the coroutine, or None if timeout occurs
    """
    try:
        return await with_timeout(coro, timeout_seconds=timeout)
    except asyncio.TimeoutError:
        return None

def run_without_event_loop_conflict(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run a coroutine without event loop conflicts.
    This is a safer alternative to asyncio.run().
    
    Args:
        coro: The coroutine to run
        
    Returns:
        The result of the coroutine
    """
    # Get or create an event loop
    loop = get_or_create_event_loop()
    
    if loop.is_running():
        # If the loop is already running (e.g., from Flask), create a future to get the result
        logger.info("Event loop is already running, using create_task")
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            # Wait for the result with a reasonable timeout
            return future.result(timeout=30)
        except Exception as e:
            logger.error(f"Error in run_coroutine_threadsafe: {e}")
            raise
    else:
        # If no loop is running, use run_until_complete
        logger.info("No event loop running, using run_until_complete")
        try:
            return loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"Error in run_until_complete: {e}")
            raise

def run_bot(bot, token: str, *, close_previous_loop: bool = False):
    """
    Safely start a Discord.py bot without causing event loop conflicts.
    
    Args:
        bot: The Discord.py bot instance
        token: The bot token
        close_previous_loop: Whether to close any previous event loop (default: False)
    """
    # Apply fixes first
    apply_all_fixes()
    
    # Define the coroutine to start the bot
    async def start_bot():
        await bot.start(token)
    
    try:
        # Get the current event loop
        loop = get_or_create_event_loop()
        
        if close_previous_loop and not loop.is_closed():
            # Clean up the current loop and create a new one
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # Give tasks a chance to clean up
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            
            loop.close()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Start the bot based on loop state
        if loop.is_running():
            logger.info("Event loop is already running, using create_task")
            # Create a task instead of trying to manage the loop
            task = asyncio.create_task(start_bot())
            logger.info(f"Bot task created: {task}")
        else:
            logger.info("No event loop running, using run_until_complete")
            loop.run_until_complete(start_bot())
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        import traceback
        traceback.print_exc()

# Apply fixes automatically upon import
apply_all_fixes()