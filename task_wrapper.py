"""
Task Wrapper - Utilities for ensuring proper task context in asyncio operations
This module provides helper functions to ensure coroutines run in proper task contexts
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Coroutine, TypeVar, Optional, Awaitable

T = TypeVar('T')
logger = logging.getLogger(__name__)

async def safe_timeout(coro, timeout_seconds=10):
    """
    Run a coroutine with a timeout, ensuring it's executed in a proper task context.
    
    Args:
        coro: The coroutine to execute
        timeout_seconds: Number of seconds before timing out
        
    Returns:
        The result of the coroutine, or None if timed out
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

def ensure_task(func):
    """
    Decorator that ensures the decorated coroutine function runs within a proper task context.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if asyncio.current_task() is not None:
            # Already in task context
            return await func(*args, **kwargs)
        else:
            # Create a task to ensure proper context
            task = asyncio.create_task(func(*args, **kwargs))
            return await task
    return wrapper

async def run_with_task_context(coro):
    """
    Run a coroutine ensuring it's in a proper task context
    """
    if asyncio.current_task() is not None:
        # Already in task context
        return await coro
    else:
        # Create a task to ensure proper context
        task = asyncio.create_task(coro)
        return await task