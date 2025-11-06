"""
Targeted fix for the specific aiohttp compatibility issue with asyncio.timeout
This module directly addresses the TypeError with async_generator object
"""

import logging
import asyncio
import sys
import inspect
import functools
from typing import Any, Optional

logger = logging.getLogger(__name__)

def fix_aiohttp_timeout_issue():
    """
    Apply a specific fix for the aiohttp timeout issue that causes:
    TypeError: 'async_generator' object does not support the asynchronous context manager protocol
    """
    try:
        # Store original timeout
        original_timeout = asyncio.timeout
        
        # Create a wrapper that ensures the timeout becomes a context manager
        @functools.wraps(original_timeout)
        def wrapped_timeout(delay: Optional[float] = None) -> Any:
            timeout_obj = original_timeout(delay)
            
            # Check if we need to add context manager support
            if not hasattr(timeout_obj, "__aenter__") and hasattr(timeout_obj, "__aiter__"):
                # It's an async generator but not a context manager, we need to wrap it
                logger.info("Converting asyncio.timeout from generator to context manager")
                
                class TimeoutContextManager:
                    """Context manager wrapper for asyncio.timeout"""
                    def __init__(self, generator):
                        self.generator = generator
                        self.iterator = None
                    
                    async def __aenter__(self):
                        # Get the iterator so we can advance it
                        self.iterator = self.generator.__aiter__()
                        # Advance to the first yield
                        try:
                            await self.iterator.__anext__()
                        except StopAsyncIteration:
                            raise RuntimeError("Timeout generator stopped unexpectedly")
                        return self
                    
                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        # If we exited with a CancelledError and timeout occurred,
                        # convert it to a TimeoutError
                        if exc_type is asyncio.CancelledError:
                            try:
                                # Try to advance the generator
                                await self.iterator.__anext__()
                            except StopAsyncIteration:
                                # Generator finished naturally, not a timeout
                                pass
                            except asyncio.TimeoutError:
                                # This is what we expect - the timeout was triggered
                                raise asyncio.TimeoutError from exc_val
                        elif exc_type is None:
                            # Normal exit, just consume the rest of the generator
                            try:
                                await self.iterator.__anext__()
                            except (StopAsyncIteration, asyncio.TimeoutError):
                                pass
                
                return TimeoutContextManager(timeout_obj)
            
            # It already has context manager interface or doesn't have iterator
            return timeout_obj
        
        # Replace the original function
        asyncio.timeout = wrapped_timeout
        logger.info("Successfully patched asyncio.timeout for aiohttp compatibility")
        return True
    
    except Exception as e:
        logger.error(f"Failed to apply aiohttp timeout fix: {e}")
        return False

# Apply the fix when this module is imported
fix_applied = fix_aiohttp_timeout_issue()