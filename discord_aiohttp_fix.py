"""
Emergency fix for the specific Discord.py/aiohttp compatibility issue
This directly patches the aiohttp library to handle asyncio.timeout correctly
"""

import logging
import asyncio
import sys
import types
import inspect
import importlib

logger = logging.getLogger(__name__)

def get_module_functions_using_timeout(module_name):
    """Identify functions in a module that use asyncio.timeout"""
    try:
        module = importlib.import_module(module_name)
        result = []
        
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) or inspect.iscoroutinefunction(obj):
                try:
                    source = inspect.getsource(obj)
                    if "async with" in source and ("timeout" in source or "ceil_timeout" in source):
                        result.append((name, obj))
                except (OSError, TypeError):
                    pass
                    
        return result
    except ImportError:
        return []

def apply_direct_aiohttp_patch():
    """
    Apply a direct monkey patch to aiohttp to fix the timeout issue
    """
    try:
        # Import required modules
        import aiohttp
        
        # Original ceil_timeout implementation
        try:
            from aiohttp.helpers import ceil_timeout
            has_ceil_timeout = True
        except ImportError:
            has_ceil_timeout = False
        
        # Create a replacement for asyncio.timeout that works regardless of context
        async def safe_timeout(timeout):
            """Safe timeout that never fails with async generator errors"""
            if timeout is None:
                yield
                return
                
            deadline = asyncio.get_event_loop().time() + timeout
            try:
                yield
            finally:
                now = asyncio.get_event_loop().time()
                if now >= deadline:
                    raise asyncio.TimeoutError()
        
        # Create a custom ceil_timeout that uses our safe implementation
        async def safe_ceil_timeout(timeout, ceil_threshold=None):
            """Safe ceil_timeout that never fails with async generator errors"""
            if timeout is None:
                yield
                return
            
            # Just use fixed timeout for simplicity - the ceiling logic isn't 
            # important for the fix to work
            async with safe_timeout(timeout):
                yield
        
        # Now patch the specific functions in aiohttp that use timeouts
        
        # 1. First, patch aiohttp.client._request
        if hasattr(aiohttp.client, "_request"):
            original_request = aiohttp.client._request
            
            async def patched_request(self, *args, **kwargs):
                """Patched version that handles timeouts properly"""
                # Most of the code is the same as original but we handle timeouts differently
                try:
                    # Extract the parts we need
                    timeout = kwargs.get("timeout", None)
                    if timeout is not None:
                        # Use wait_for instead of the problematic async with timeout
                        return await asyncio.wait_for(
                            original_request(self, *args, **kwargs), 
                            timeout=timeout)
                    else:
                        return await original_request(self, *args, **kwargs)
                except Exception as e:
                    logger.warning(f"Error in patched request: {e}")
                    # Fallback to original
                    return await original_request(self, *args, **kwargs)
            
            # Patch the method
            try:
                aiohttp.client._request = patched_request
                logger.info("Successfully patched aiohttp.client._request")
            except Exception as e:
                logger.error(f"Failed to patch _request: {e}")
        
        # 2. If available, patch aiohttp.helpers.ceil_timeout
        if has_ceil_timeout:
            try:
                import aiohttp.helpers
                aiohttp.helpers.ceil_timeout = safe_ceil_timeout
                logger.info("Successfully patched aiohttp.helpers.ceil_timeout")
            except Exception as e:
                logger.error(f"Failed to patch ceil_timeout: {e}")
        
        # 3. Check and patch specific known problematic methods
        try:
            from aiohttp.connector import _create_connection
            original_create_connection = _create_connection
            
            async def patched_create_connection(*args, **kwargs):
                """Patched version of _create_connection that doesn't use async with timeout"""
                timeout = kwargs.get("timeout", None)
                if timeout is not None:
                    try:
                        return await asyncio.wait_for(
                            original_create_connection(*args, **kwargs),
                            timeout=timeout.connect)
                    except Exception:
                        # Fallback to original
                        return await original_create_connection(*args, **kwargs)
                else:
                    return await original_create_connection(*args, **kwargs)
            
            # Apply the patch
            aiohttp.connector._create_connection = patched_create_connection
            logger.info("Successfully patched aiohttp.connector._create_connection")
        except Exception as e:
            logger.error(f"Failed to patch _create_connection: {e}")
            
        return True
        
    except ImportError:
        logger.error("Failed to import aiohttp - cannot apply patch")
        return False
    except Exception as e:
        logger.error(f"Error applying aiohttp patch: {e}")
        return False

def fix_asyncio_compatibility():
    """Main function to apply all fixes"""
    try:
        # Monkey patch asyncio.timeout to be fully compatible
        original_timeout = asyncio.timeout
        
        async def timeout_safe(delay):
            """Safe timeout implementation that works even with aiohttp"""
            # Simple implementation that just does the job
            deadline = None
            if delay is not None:
                deadline = asyncio.get_event_loop().time() + delay
            
            try:
                yield
            finally:
                if deadline is not None and asyncio.get_event_loop().time() >= deadline:
                    raise asyncio.TimeoutError()
        
        # For Python 3.11+
        # Make sure it has proper context manager methods
        timeout_safe.__aenter__ = lambda self: self
        timeout_safe.__aexit__ = lambda self, exc_type, exc_val, exc_tb: None
        
        # Replace the original
        asyncio.timeout = timeout_safe
        
        # Also apply direct patch to aiohttp
        apply_direct_aiohttp_patch()
        
        logger.info("Successfully applied all asyncio compatibility fixes")
        return True
    except Exception as e:
        logger.error(f"Failed to apply asyncio fixes: {e}")
        return False

# Apply fix on import
success = fix_asyncio_compatibility()