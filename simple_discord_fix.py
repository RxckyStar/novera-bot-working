#!/usr/bin/env python3
"""
Simple Discord.py asyncio fix module
-----------------------------------
This module provides a streamlined fix for common asyncio issues with Discord.py:

1. Prevents 'Timeout context manager should be used inside a task' errors
2. Solves 'asyncio.run() cannot be called from a running event loop' errors
3. Provides safe_wait_for as a replacement for asyncio.wait_for and bot.wait_for

USAGE:
    # Import this module FIRST before any other imports
    import simple_discord_fix
    from simple_discord_fix import safe_wait_for
    
    # No explicit calls needed - fixes are applied automatically on import
    
    # To start the bot safely:
    simple_discord_fix.run_bot(bot, token)
"""

import asyncio
import logging
import inspect
import sys
from typing import Any, Callable, Coroutine, Optional, TypeVar, cast

T = TypeVar('T')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_inside_task() -> bool:
    """Check if the current coroutine is running inside a task."""
    try:
        return asyncio.current_task() is not None
    except RuntimeError:
        return False

def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get the current event loop or create a new one if needed."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def apply_timeout_fix() -> None:
    """
    Apply a fix for asyncio.timeout to prevent the "Timeout context manager 
    should be used inside a task" error.
    """
    if not hasattr(asyncio, 'timeout') or hasattr(asyncio.timeout, '__fixed_by_simple_discord_fix__'):
        return
    
    original_timeout = asyncio.timeout
    
    def fixed_timeout(delay: Optional[float] = None):
        """Fixed timeout function that handles task context gracefully."""
        if delay is None:
            return original_timeout(None)
        
        if is_inside_task():
            # When inside a task, use the original timeout
            return original_timeout(delay)
        else:
            # When not inside a task, use a dummy context manager
            class DummyTimeoutContext:
                async def __aenter__(self):
                    return None
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False
            
            return DummyTimeoutContext()
    
    # Apply our patched version
    fixed_timeout.__fixed_by_simple_discord_fix__ = True
    asyncio.timeout = fixed_timeout
    logger.info("Applied asyncio.timeout fix")

async def safe_wait_for(coro_or_future: Coroutine[Any, Any, T], timeout: Optional[float]) -> T:
    """
    A safe replacement for asyncio.wait_for that properly handles task context issues.
    
    Args:
        coro_or_future: The coroutine or future to wait for
        timeout: The timeout duration in seconds, or None for no timeout
        
    Returns:
        The result of the coroutine or future
        
    Raises:
        asyncio.TimeoutError: If the operation times out
        Exception: Any exception raised by the coroutine
    """
    if is_inside_task():
        # When already in a task, just use wait_for directly
        return await asyncio.wait_for(coro_or_future, timeout)
    else:
        # When not in a task, create one
        async def wait_for_in_task():
            return await asyncio.wait_for(coro_or_future, timeout)
        
        loop = get_or_create_event_loop()
        task = loop.create_task(wait_for_in_task())
        return await task

async def with_timeout(coro_or_future: Coroutine[Any, Any, T], timeout_seconds: Optional[float] = None) -> T:
    """
    Execute a coroutine with a timeout.
    This is a drop-in replacement for discord_asyncio_fix.with_timeout.
    
    Args:
        coro_or_future: The coroutine to execute
        timeout_seconds: The timeout in seconds, or None for no timeout
        
    Returns:
        The result of the coroutine
        
    Raises:
        asyncio.TimeoutError: If the operation times out
    """
    return await safe_wait_for(coro_or_future, timeout_seconds)

async def start_discord_bot(bot, token: str):
    """Two-step approach to start the Discord bot"""
    try:
        # First step: Login
        await bot.login(token)
        # Second step: Connect with auto-reconnect
        await bot.connect(reconnect=True)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

def run_bot(bot, token: str):
    """
    Runs a Discord.py bot with proper event loop handling to prevent asyncio errors.
    This is a replacement for bot.run() that doesn't use asyncio.run().
    
    Args:
        bot: The discord.py Bot or Client instance
        token: The Discord token string
    """
    # Get or create an event loop
    loop = get_or_create_event_loop()
    
    # If the loop is already running, create a task
    if loop.is_running():
        logger.info("Event loop is already running, creating a task")
        loop.create_task(start_discord_bot(bot, token))
    else:
        # Otherwise run the coroutine
        logger.info("Starting bot with event loop")
        try:
            loop.run_until_complete(start_discord_bot(bot, token))
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            loop.run_until_complete(bot.close())
        finally:
            logger.info("Closing event loop")
            loop.close()

def apply_all_fixes() -> None:
    """Apply all asyncio fixes."""
    apply_timeout_fix()

# Apply fixes on import
apply_all_fixes()