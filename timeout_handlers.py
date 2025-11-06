#!/usr/bin/env python3
"""
Timeout Handlers Module
Safe implementations for all timeout-related functions
"""

import asyncio
import logging
from typing import Any, Coroutine, Optional, TypeVar, Callable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar('T')

def is_inside_task() -> bool:
    """Check if current coroutine is running inside a task"""
    try:
        return asyncio.current_task() is not None
    except RuntimeError:
        return False

async def wait_for_safe(coro: Coroutine[Any, Any, T], timeout: Optional[float] = None) -> T:
    """Safely wait for a coroutine with timeout, properly handling task context"""
    if is_inside_task():
        try:
            return await asyncio.wait_for(coro, timeout)
        except asyncio.TimeoutError:
            logger.debug(f"Operation timed out after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Error in wait_for_safe: {e}")
            raise

    async def run_in_task():
        if timeout is None:
            return await coro
        try:
            async with asyncio.timeout(timeout):
                return await coro
        except asyncio.TimeoutError:
            logger.debug(f"Operation timed out after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Error in task: {e}")
            raise

    task = asyncio.create_task(run_in_task())
    return await task

async def with_timeout_safe(coro: Coroutine[Any, Any, T], timeout: Optional[float] = None) -> T:
    """Safe timeout context manager function that works regardless of task context"""
    if is_inside_task():
        try:
            if timeout is None:
                return await coro
            async with asyncio.timeout(timeout):
                return await coro
        except asyncio.TimeoutError:
            logger.debug(f"Operation timed out after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Error in with_timeout_safe: {e}")
            raise
    
    # If we're not in a task, create one
    async def run_in_task():
        if timeout is None:
            return await coro
        try:
            async with asyncio.timeout(timeout):
                return await coro
        except asyncio.TimeoutError:
            logger.debug(f"Operation timed out after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Error in task: {e}")
            raise
    
    task = asyncio.create_task(run_in_task())
    return await task