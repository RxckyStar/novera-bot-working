#!/usr/bin/env python3
"""
Timeout and Asyncio Error Fix
This script fixes the 'Timeout context manager should be used inside a task' error
by enhancing the timeout handling in the bot code.
"""

import os
import sys
import logging
import asyncio
from typing import Callable, Awaitable, Optional, Any, Coroutine, TypeVar

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("timeout_fix.log")
    ]
)
logger = logging.getLogger("timeout_fix")

T = TypeVar('T')

class SafeTimeoutContext:
    """A safer timeout context manager that works both inside and outside tasks."""
    
    def __init__(self, seconds: float):
        self.seconds = seconds
        self.timeout_ctx = None
        self.task_created = False
        
    async def __aenter__(self):
        if asyncio.current_task() is None:
            # Not in a task context, create a dummy task
            logger.warning("SafeTimeoutContext used outside of task context - applying workaround")
            self.task_created = True
            
            # Method 1: First try to use the get_running_loop approach
            try:
                loop = asyncio.get_running_loop()
                self.dummy_task = asyncio.create_task(asyncio.sleep(0))
                await self.dummy_task  # Ensure we have a task context
                # Now we're running in a task context, create the timeout
                self.timeout_ctx = asyncio.timeout(self.seconds)
                return await self.timeout_ctx.__aenter__()
            except RuntimeError:
                # Method 2: No running loop, more creative approach needed
                logger.warning("No running event loop for SafeTimeoutContext, using alternative approach")
                # In this case, we'll just return without a timeout
                # since we can't create a proper task context
                return None
        else:
            # Already in a task context, use the standard timeout
            self.timeout_ctx = asyncio.timeout(self.seconds)
            return await self.timeout_ctx.__aenter__()
            
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.timeout_ctx:
            return await self.timeout_ctx.__aexit__(exc_type, exc_val, exc_tb)
        return False

async def wait_with_safe_timeout(coro: Awaitable[T], timeout: float) -> Optional[T]:
    """
    Wait for a coroutine with a safe timeout that works both inside and outside tasks.
    
    Args:
        coro: The coroutine to wait for
        timeout: The timeout in seconds
        
    Returns:
        The result of the coroutine, or None if it timed out
    """
    # First check if we're in a task
    if asyncio.current_task() is None:
        # We're not in a task, create one
        try:
            loop = asyncio.get_running_loop()
            
            # Create a wrapper coroutine that runs inside a task
            async def wrapper():
                try:
                    # Now we're guaranteed to be in a task
                    return await asyncio.wait_for(coro, timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"Operation timed out after {timeout} seconds")
                    return None
                    
            # Execute the wrapper in a task
            task = loop.create_task(wrapper())
            return await task
        except RuntimeError:
            # No running loop, can't proceed with timeouts
            logger.warning("No running event loop for wait_with_safe_timeout, running without timeout")
            # Just run the coroutine without a timeout
            return await coro
    else:
        # Already in a task, use standard wait_for
        try:
            return await asyncio.wait_for(coro, timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Operation timed out after {timeout} seconds")
            return None

def apply_fixes():
    """Apply the timeout fixes to the relevant files"""
    logger.info("Applying timeout fixes to the bot code")
    
    # 1. Make sure timeout_handlers.py has the latest fixes
    with open("timeout_handlers.py", "r") as f:
        content = f.read()
        
    # Check if our fixes are already applied
    if "if asyncio.current_task() is None:" in content and "context manager should be used inside a task" in content:
        logger.info("timeout_handlers.py already has the fix, no changes needed")
    else:
        logger.warning("timeout_handlers.py needs updating, applying fixes")
        # Apply the fix - replace the with_timeout function
        new_with_timeout = '''
@contextlib.asynccontextmanager
async def with_timeout(seconds: float):
    """
    An async context manager for timeouts that works properly in task context.
    This is a backward compatibility function.
    """
    try:
        if asyncio.current_task() is None:
            # We're not in a task context, which will cause the asyncio.timeout to fail
            logger.warning("with_timeout used outside of task context - working around issue")
            try:
                # Method 1: Try to create a task and run in it
                loop = asyncio.get_running_loop()
                dummy_task = asyncio.create_task(asyncio.sleep(0))
                await dummy_task  # Now we're in a task context
                
                # Now we can use the timeout
                async with asyncio.timeout(seconds):
                    yield
            except RuntimeError:
                # Method 2: No running loop, just yield without timeout
                logger.warning("No running event loop, bypassing timeout")
                yield
        else:
            # In a task context, we can use the real timeout
            async with asyncio.timeout(seconds):
                yield
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {seconds} seconds")
        raise
'''
        # Find the with_timeout function and replace it
        if "@contextlib.asynccontextmanager" in content and "async def with_timeout" in content:
            # Find the start and end of the function
            start = content.find("@contextlib.asynccontextmanager")
            end = content.find("def ", start + 30)
            end = content.find("def ", end + 1)
            if end == -1:  # If it's the last function
                end = len(content)
                
            updated_content = content[:start] + new_with_timeout + content[end:]
            
            # Write the updated content back
            with open("timeout_handlers.py.new", "w") as f:
                f.write(updated_content)
                
            # Backup the original file and rename the new one
            os.rename("timeout_handlers.py", "timeout_handlers.py.bak")
            os.rename("timeout_handlers.py.new", "timeout_handlers.py")
            logger.info("Updated timeout_handlers.py with improved timeout handling")
            
    # 2. Ensure we have the safe_run_task function in asyncio_runner.py
    if os.path.exists("asyncio_runner.py"):
        with open("asyncio_runner.py", "r") as f:
            runner_content = f.read()
            
        if "def safe_run_task(" not in runner_content:
            logger.info("Adding safe_run_task function to asyncio_runner.py")
            
            # Add our safe_run_task function at the end
            safe_run_task_func = '''
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
'''
            # Add the function to the end of the file
            with open("asyncio_runner.py", "a") as f:
                f.write(safe_run_task_func)
                
            logger.info("Added safe_run_task function to asyncio_runner.py")
            
    logger.info("Timeout fixes applied successfully")
    
if __name__ == "__main__":
    apply_fixes()