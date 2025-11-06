#!/usr/bin/env python3
"""
Comprehensive Discord.py Asyncio Fix
Handles all timeout and event loop issues in one place
"""

import asyncio
import logging
import sys
import functools
from typing import Any, Callable, Coroutine, TypeVar, Optional
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar('T')
_fixes_applied = False

def is_inside_task() -> bool:
    """Check if current coroutine is running inside a task"""
    try:
        return asyncio.current_task() is not None
    except RuntimeError:
        return False

async def with_timeout(coro: Coroutine[Any, Any, T], timeout: Optional[float] = None) -> T:
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
            logger.error(f"Error in with_timeout: {e}")
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

async def safe_wait_for(coro: Coroutine[Any, Any, T], timeout: Optional[float] = None) -> T:
    """Unified safe wait_for implementation"""
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

def apply_all_fixes():
    """Apply all asyncio fixes"""
    global _fixes_applied
    if _fixes_applied:
        return

    # Override the default event loop policy
    if sys.platform.startswith('win32'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    else:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    _fixes_applied = True
    logger.info("Applied all Discord.py asyncio fixes")

def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get existing loop or create new one safely"""
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_running():
            return loop
    except RuntimeError:
        pass

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop

async def start_discord_bot(bot, token):
    """Start the Discord bot with proper connection handling"""
    try:
        async with bot:
            await bot.start(token)
    except Exception as e:
        logger.error(f"Error in bot startup: {e}")
        raise

def run_bot(bot, token):
    """Run Discord bot with proper error handling"""
    apply_all_fixes()

    loop = get_or_create_event_loop()
    if loop.is_running():
        return loop.create_task(start_discord_bot(bot, token))
    else:
        try:
            loop.run_until_complete(start_discord_bot(bot, token))
        except KeyboardInterrupt:
            loop.run_until_complete(bot.close())

# Apply fixes on module import
apply_all_fixes()