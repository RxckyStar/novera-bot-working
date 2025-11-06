"""
Timeout Handlers for Discord Bot
--------------------------------
This module provides reliable timeout handling for use with Discord bots.
It fixes the "Timeout context manager should be used inside a task" error
that commonly occurs in Discord.py applications.
"""

import asyncio
import logging
import functools
from typing import Any, Callable, Coroutine, TypeVar, Optional

T = TypeVar('T')

async def with_timeout(coro: Coroutine[Any, Any, T], timeout_seconds: float = 10) -> T:
    """
    Run a coroutine with a timeout safely by ensuring it runs within a task.
    This is the core fix for the "Timeout context manager should be used inside a task" error.
    
    Args:
        coro: The coroutine to execute with a timeout
        timeout_seconds: Timeout in seconds
        
    Returns:
        The result of the coroutine
    
    Raises:
        asyncio.TimeoutError: If the operation times out
    """
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

async def wait_for_safe(coro: Coroutine[Any, Any, T], timeout: float) -> Optional[T]:
    """
    A simpler version that doesn't raise the timeout error, just returns None.
    This is useful for Discord bot commands where you just want to handle timeout gracefully.
    
    Args:
        coro: The coroutine to execute with a timeout
        timeout: Timeout in seconds
        
    Returns:
        The result of the coroutine, or None if it times out
    """
    try:
        return await with_timeout(coro, timeout_seconds=timeout)
    except asyncio.TimeoutError:
        return None

def ensure_proper_startup(coro_func):
    """
    Decorator to ensure a coroutine runs with proper task context.
    This is critical for bot startup to ensure timeouts work properly.
    
    Args:
        coro_func: The coroutine function to decorate
        
    Returns:
        A wrapped coroutine function
    """
    @functools.wraps(coro_func)
    async def wrapper(*args, **kwargs):
        try:
            # Create a new task for this coroutine
            task = asyncio.create_task(coro_func(*args, **kwargs))
            return await task
        except Exception as e:
            logging.error(f"Error in ensure_proper_startup: {e}")
            raise
    return wrapper

def run_with_task_context(coro):
    """
    Run a coroutine with proper task context handling.
    This is a safer alternative to asyncio.run() for Discord bots.
    
    Args:
        coro: The coroutine to run
        
    Returns:
        The result of the coroutine
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        logging.info("Event loop is already running, using create_task")
        task = loop.create_task(coro)
        return task
    else:
        logging.info("No event loop running, using run_until_complete")
        return loop.run_until_complete(coro)

def safe_task(coro_func):
    """
    Decorator to ensure a coroutine always runs within a proper task context.
    This is useful for any coroutine that might use asyncio.timeout().
    
    Args:
        coro_func: The coroutine function to decorate
        
    Returns:
        A wrapped coroutine function
    """
    @functools.wraps(coro_func)
    async def wrapper(*args, **kwargs):
        # Create a task for this coroutine
        task = asyncio.create_task(coro_func(*args, **kwargs))
        return await task
    return wrapper

def cleanup_loop():
    """
    Clean up the current event loop.
    This is useful for graceful shutdown.
    """
    try:
        loop = asyncio.get_event_loop()
        pending = asyncio.all_tasks(loop)
        if pending:
            logging.info(f"Cancelling {len(pending)} pending tasks")
            for task in pending:
                task.cancel()
    except Exception as e:
        logging.error(f"Error in cleanup_loop: {e}")