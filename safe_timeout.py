"""
Safe Timeout Utilities for Discord Bots
---------------------------------------

This module provides safe timeout handling for use in Discord bots or any
asynchronous application. It addresses the "Timeout context manager should
be used inside a task" error by using asyncio.wait_for() instead of
asyncio.timeout() directly.
"""

import asyncio
import logging
from typing import Any, Coroutine, TypeVar, Optional, Callable

T = TypeVar('T')

async def with_timeout(coro: Coroutine[Any, Any, T], timeout: float) -> Optional[T]:
    """
    Run a coroutine with a timeout, safely handling timeout errors.
    This is a safer alternative to asyncio.timeout() which can cause
    "Timeout context manager should be used inside a task" errors.
    
    Args:
        coro: The coroutine to execute with a timeout
        timeout: Timeout in seconds
        
    Returns:
        The result of the coroutine, or None if it times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logging.debug(f"Operation timed out after {timeout} seconds")
        return None
    except Exception as e:
        logging.error(f"Error during operation with timeout: {e}")
        return None

async def with_timeout_callback(
    coro: Coroutine[Any, Any, T],
    timeout: float,
    on_timeout: Callable[[], None] = None,
    on_error: Callable[[Exception], None] = None
) -> Optional[T]:
    """
    Run a coroutine with a timeout and custom callbacks for timeout and error cases.
    
    Args:
        coro: The coroutine to execute with a timeout
        timeout: Timeout in seconds
        on_timeout: Function to call if timeout occurs
        on_error: Function to call if an error occurs
        
    Returns:
        The result of the coroutine, or None if it times out or errors
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logging.debug(f"Operation timed out after {timeout} seconds")
        if on_timeout:
            on_timeout()
        return None
    except Exception as e:
        logging.error(f"Error during operation with timeout: {e}")
        if on_error:
            on_error(e)
        return None

class SafeTimeout:
    """
    A safer alternative to asyncio.timeout that works correctly within tasks.
    This class provides a timeout context manager that can be used
    anywhere without causing "Timeout context manager should be used inside a task" errors.
    
    Example:
    ```python
    async def some_function():
        # This will safely timeout after 5 seconds
        async with SafeTimeout(5) as timeout:
            # Do something that might take too long
            result = await some_long_operation()
            if timeout.expired:
                return None
            return result
    ```
    """
    
    def __init__(self, timeout: float):
        """
        Create a new SafeTimeout context manager.
        
        Args:
            timeout: Timeout in seconds
        """
        self.timeout = timeout
        self._expired = False
        self._task = None
    
    @property
    def expired(self) -> bool:
        """Check if the timeout has expired"""
        return self._expired
    
    async def __aenter__(self) -> 'SafeTimeout':
        # Create a future and a task that will cancel it after timeout
        self._future = asyncio.Future()
        self._task = asyncio.create_task(self._timeout_task())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Make sure to clean up the task
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # If we got a CancelledError and our timer task is done,
        # then this was probably caused by our timeout
        if exc_type is asyncio.CancelledError and self._expired:
            # Suppress the exception
            return True
    
    async def _timeout_task(self):
        """Task that waits for the timeout and then marks as expired"""
        try:
            await asyncio.sleep(self.timeout)
            self._expired = True
            # Create a task to cancel the current task
            task = asyncio.current_task()
            if task:
                task.cancel()
        except asyncio.CancelledError:
            # This is normal when the context exits before timeout
            pass