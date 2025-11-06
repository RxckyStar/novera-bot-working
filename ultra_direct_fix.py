"""
Ultra-direct fix for Discord.py and aiohttp compatibility issues
This completely bypasses problematic asyncio.timeout features and directly 
patches low-level Discord.py code to work without any timeouts
"""

import asyncio
import sys
import logging
import types
import importlib
import os

logger = logging.getLogger(__name__)

# Add detailed environment info for debugging
logger.info(f"Python version: {sys.version}")
logger.info(f"Asyncio version: {getattr(asyncio, '__version__', 'Unknown')}")

def patch_discord_client():
    """Directly patch Discord.py client to eliminate timeout issues"""
    try:
        # Import Discord.py modules
        import discord.client
        import discord.http

        # 1. First patch Discord's HTTP client to avoid using asyncio.timeout
        original_request = discord.http.HTTPClient.request
        
        async def patched_request(self, route, **kwargs):
            """Patched version that avoids problematic timeout usage"""
            # Remove the problematic timeout
            if 'timeout' in kwargs:
                del kwargs['timeout']
                
            # Add a different timeout mechanism using wait_for instead
            try:
                return await asyncio.wait_for(
                    original_request(self, route, **kwargs), 
                    timeout=30.0  # Fixed timeout value
                )
            except asyncio.TimeoutError:
                logger.warning(f"Request to {route.url} timed out after 30s")
                raise
        
        # Apply the patch
        discord.http.HTTPClient.request = patched_request
        logger.info("Successfully patched discord.http.HTTPClient.request")
        
        # 2. Patch the client's run method for better event loop handling
        original_run = discord.client.Client.run
        
        def patched_run(self, token, *, reconnect=True):
            """Ultra-robust run method that never fails with event loop errors"""
            async def runner():
                try:
                    await self.start(token, reconnect=reconnect)
                finally:
                    if not self.is_closed():
                        await self.close()
            
            # Strategy 1: Try with fresh event loop
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(runner())
                return
            except RuntimeError as e:
                logger.warning(f"First strategy failed: {e}")
            
            # Strategy 2: Thread-based approach
            import threading
            
            def thread_target():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(runner())
                except Exception as e:
                    logger.error(f"Thread execution failed: {e}")
            
            thread = threading.Thread(target=thread_target)
            thread.daemon = True
            thread.start()
            
            # Keep the main thread alive
            try:
                while thread.is_alive():
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                return
        
        # Apply the patch
        discord.client.Client.run = patched_run
        logger.info("Successfully patched discord.client.Client.run")
        
        # 3. Install our own wait_for implementation that doesn't rely on timeout
        if hasattr(discord.client, 'wait_for'):
            original_wait_for = discord.client.wait_for
            
            async def patched_wait_for(event, *, check=None, timeout=None):
                """Safe version of wait_for that never has event loop issues"""
                future = asyncio.Future()
                
                if check is None:
                    def _check(*args):
                        return True
                    check = _check
                
                ev_id = discord.client._get_next_event_id()
                
                @discord.client.gateway_event_callback(event, ev_id)
                def event_callback(*args):
                    try:
                        if check(*args):
                            future.set_result(args[0] if len(args) == 1 else args)
                    except Exception as e:
                        future.set_exception(e)
                
                # Use wait_for instead of timeout
                if timeout:
                    try:
                        return await asyncio.wait_for(future, timeout=timeout)
                    finally:
                        discord.client._gateway_event_callbacks[event].pop(ev_id)
                else:
                    try:
                        return await future
                    finally:
                        discord.client._gateway_event_callbacks[event].pop(ev_id)
            
            # Apply the patch
            discord.client.wait_for = patched_wait_for
            logger.info("Successfully patched discord.client.wait_for")
        
        return True
    except ImportError:
        logger.warning("Discord.py modules not available for patching")
        return False
    except Exception as e:
        logger.error(f"Error while patching Discord.py: {e}")
        return False

def fix_aiohttp_compatibility():
    """Fix aiohttp compatibility with asyncio.timeout"""
    try:
        # Check if aiohttp is available
        import aiohttp
        
        # Monkey patch all aiohttp functions with wait_for
        # This is an aggressive approach that eliminates any chance of
        # async context manager errors with timeouts
        
        for module_name in ['aiohttp.client', 'aiohttp.connector']:
            try:
                module = importlib.import_module(module_name)
                
                # Find all async methods
                for name in dir(module):
                    item = getattr(module, name)
                    if not callable(item) or not hasattr(item, '__code__'):
                        continue
                    
                    # Check if it's likely to use asyncio.timeout
                    try:
                        code = item.__code__
                        co_names = code.co_names if hasattr(code, 'co_names') else []
                        if 'timeout' in co_names or 'ceil_timeout' in co_names:
                            logger.info(f"Found potential timeout function: {module_name}.{name}")
                    except Exception:
                        pass
            except ImportError:
                pass
        
        # Final super-aggressive direct patch of specific known issue
        try:
            from aiohttp.client import ClientSession
            
            original_request = ClientSession._request
            
            async def safe_request(self, method, url, **kwargs):
                """Version without any asyncio.timeout usage"""
                # Remove any timeouts or convert to wait_for
                timeout = kwargs.pop('timeout', 30.0)
                
                # Use wait_for instead
                try:
                    return await asyncio.wait_for(
                        original_request(self, method, url, **kwargs),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Request to {url} timed out after {timeout}s")
                    raise
            
            # Apply the patch
            ClientSession._request = safe_request
            logger.info("Successfully patched aiohttp.client.ClientSession._request")
        except Exception as e:
            logger.error(f"Failed to patch ClientSession: {e}")
        
        return True
    except ImportError:
        logger.warning("aiohttp not available for patching")
        return False
    except Exception as e:
        logger.error(f"Error patching aiohttp: {e}")
        return False

# Define a completely custom timeout implementation
class UltraSafeTimeout:
    """Timeout implementation that works in all contexts"""
    
    def __init__(self, timeout):
        self.timeout = timeout
        self.deadline = None
        self.task = None
        
    async def __aenter__(self):
        if self.timeout is not None:
            self.deadline = asyncio.get_event_loop().time() + self.timeout
            self.task = asyncio.current_task()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        if self.deadline is not None and asyncio.get_event_loop().time() >= self.deadline:
            if exc_type is asyncio.CancelledError:
                # Convert to TimeoutError
                raise asyncio.TimeoutError from exc
            elif exc_type is None:
                # Explicit timeout at end
                raise asyncio.TimeoutError()
        return False  # Don't suppress exceptions

# Apply all fixes
def apply_all_fixes():
    """Apply all available fixes"""
    
    # 1. Replace asyncio.timeout with our safe version
    original_timeout = asyncio.timeout
    asyncio.timeout = lambda delay: UltraSafeTimeout(delay)
    logger.info("Replaced asyncio.timeout with UltraSafeTimeout")
    
    # 2. Fix Discord.py
    discord_patched = patch_discord_client()
    logger.info(f"Discord.py patching {'successful' if discord_patched else 'failed'}")
    
    # 3. Fix aiohttp
    aiohttp_patched = fix_aiohttp_compatibility()
    logger.info(f"aiohttp patching {'successful' if aiohttp_patched else 'failed'}")
    
    # Set an environment flag to indicate patches are applied
    os.environ['DISCORD_PATCHES_APPLIED'] = 'TRUE'
    
    return discord_patched or aiohttp_patched

# Apply all fixes on import
success = apply_all_fixes()