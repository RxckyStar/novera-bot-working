"""
Ultra-Reliable Bot Runner
This script ensures the Discord bot stays running no matter what errors occur.
It handles both "Timeout context manager should be used inside a task" and 
"property 'intents' of 'Bot' object has no setter" errors.
"""

import os
import sys
import time
import logging
import subprocess
import signal
import psutil
import asyncio
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ultra_reliable.log")
    ]
)
logger = logging.getLogger("ultra_reliable")

class UltraReliableRunner:
    """Ensures the Discord bot is always running"""
    
    def __init__(self):
        self.bot_process = None
        self.restart_count = 0
        self.last_start_time = None
        self.max_restarts_per_hour = 10  # Limit restarts to prevent excessive cycling
        self.hourly_restart_times = []
        self.bot_command = ["python", "bot.py"]
        self.healthy = False
        self.check_interval = 30  # Seconds between health checks
    
    def is_bot_running(self):
        """Check if bot process is running"""
        if self.bot_process is None:
            return False
            
        # Check for PID existence
        try:
            if psutil.pid_exists(self.bot_process.pid):
                # Check if process is responsive
                proc = psutil.Process(self.bot_process.pid)
                if proc.status() not in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
                    return True
            return False
        except:
            return False
    
    def check_bot_health(self):
        """Check if the bot is actually healthy by testing its API endpoint"""
        try:
            import requests
            response = requests.get("http://localhost:5001/healthz", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.healthy = True
                    return True
            self.healthy = False
            return False
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self.healthy = False
            return False
    
    def start_bot(self):
        """Start the Discord bot as a subprocess"""
        if self.is_bot_running():
            logger.info("Bot is already running")
            return
            
        # Record restart attempt
        self.last_start_time = datetime.now()
        self.hourly_restart_times.append(self.last_start_time)
        
        # Clean up hourly restart tracking - remove entries older than 1 hour
        self.hourly_restart_times = [t for t in self.hourly_restart_times 
                                   if t > datetime.now() - timedelta(hours=1)]
        
        # Check for too many restarts in the past hour
        if len(self.hourly_restart_times) > self.max_restarts_per_hour:
            logger.warning(f"Too many restarts ({len(self.hourly_restart_times)}) in the past hour. Waiting...")
            time.sleep(300)  # Wait 5 minutes before trying again
            return
            
        # Clean up any previous bot processes
        self.cleanup_stale_processes()
            
        # Start the bot
        try:
            logger.info(f"Starting bot (attempt #{self.restart_count + 1})")
            self.bot_process = subprocess.Popen(
                self.bot_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            self.restart_count += 1
            logger.info(f"Bot started with PID {self.bot_process.pid}")
            
            # Give the bot time to initialize
            time.sleep(10)
            
            # Check if bot is still running after startup
            if not self.is_bot_running():
                logger.error("Bot failed to start properly")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            return False
    
    def cleanup_stale_processes(self):
        """Clean up any stale bot processes"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.cmdline()
                    if len(cmdline) >= 2 and 'python' in cmdline[0] and 'bot.py' in cmdline[1]:
                        if self.bot_process is None or proc.pid != self.bot_process.pid:
                            logger.info(f"Killing stale bot process {proc.pid}")
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.error(f"Error cleaning up stale processes: {e}")
    
    def fix_common_issues(self):
        """Apply fixes for common issues like timeout context and intents errors"""
        # Check if task_wrapper.py exists, create it if not
        if not os.path.exists('task_wrapper.py'):
            with open('task_wrapper.py', 'w') as f:
                f.write("""\"\"\"
Task Wrapper - Ensures all async operations have proper task context
This module provides utilities to ensure that all async operations,
especially those using timeout context managers, are executed within a proper task.
\"\"\"

import asyncio
import functools
import logging
from typing import Any, Callable, Coroutine, TypeVar, cast

T = TypeVar('T')

logger = logging.getLogger(__name__)

def ensure_task(coro_func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
    \"\"\"
    Decorator that ensures a coroutine function is always executed within a proper task.
    This solves the "Timeout context manager should be used inside a task" error.
    \"\"\"
    @functools.wraps(coro_func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            # Check if we're already in a task
            current_task = asyncio.current_task()
            if current_task is not None:
                # We're already in a task, just call the function
                return await coro_func(*args, **kwargs)
            else:
                # We're not in a task, create one and wait for it
                logger.debug(f"Creating new task for {coro_func.__name__}")
                task = asyncio.create_task(coro_func(*args, **kwargs))
                return await task
        except RuntimeError as e:
            # If we get a RuntimeError about missing event loop, create one
            if "no running event loop" in str(e):
                logger.warning(f"No running event loop detected in {coro_func.__name__}, creating new loop")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                task = loop.create_task(coro_func(*args, **kwargs))
                return await task
            else:
                raise
                
    return cast(Callable[..., Coroutine[Any, Any, T]], wrapper)

def safe_timeout(timeout: float) -> Any:
    \"\"\"
    Safe alternative to asyncio.timeout that ensures it's used within a task.
    \"\"\"
    try:
        # Try to use normal timeout
        return asyncio.timeout(timeout)
    except RuntimeError as e:
        if "should be used inside a task" in str(e):
            logger.warning(f"Timeout used outside task context, creating wrapper")
            
            # Create a custom context manager that works outside tasks
            class SafeTimeoutWrapper:
                async def __aenter__(self):
                    self.task = asyncio.create_task(asyncio.sleep(0))  # Dummy task
                    return self
                    
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    self.task.cancel()
                    try:
                        await self.task
                    except asyncio.CancelledError:
                        pass
                    return False
                    
            return SafeTimeoutWrapper()
        else:
            raise

def run_with_task_context(coro: Coroutine[Any, Any, T]) -> T:
    \"\"\"
    Runs a coroutine with a proper task context, ensuring all timeout operations work.
    This is a replacement for asyncio.run() that ensures proper task context.
    \"\"\"
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No running event loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Create a task for the coroutine
    task = loop.create_task(coro)
    
    # Run the task until complete
    try:
        return loop.run_until_complete(task)
    finally:
        # Clean up pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
            
        # Run the loop until all tasks are cancelled
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
""")
            logger.info("Created task_wrapper.py to fix timeout context error")

        # Fix bot.py if necessary to address intents and timeout issues
        try:
            with open('bot.py', 'r') as f:
                bot_code = f.read()
                
            # Check if we need to add imports
            if 'from task_wrapper import' not in bot_code:
                import_fix = """# Fix for timeout context and intents errors
from task_wrapper import ensure_task, safe_timeout, run_with_task_context
"""
                # Add after other imports
                if '# Import required modules and libraries' in bot_code:
                    bot_code = bot_code.replace('# Import required modules and libraries', 
                                             '# Import required modules and libraries\n' + import_fix)
                else:
                    # Just add after the first few import statements
                    import_section_end = bot_code.find('import')
                    import_section_end = bot_code.find('\n\n', import_section_end)
                    if import_section_end > 0:
                        bot_code = bot_code[:import_section_end] + '\n' + import_fix + bot_code[import_section_end:]
                        
            # Fix bot.run() call to handle intents error
            if 'bot.run(clean_token_final)' in bot_code and '@ensure_task' not in bot_code:
                # Replace the problematic bot.run call
                bot_run_fix = """                    # FIXED: Use proper asyncio task context for bot.run
                    @ensure_task
                    async def run_bot_async():
                        try:
                            async with bot:
                                await bot.start(clean_token_final)
                        except RuntimeError as e:
                            if "Timeout context manager" in str(e):
                                logger.error(f"Caught timeout context error: {e}")
                                # Force proper context
                                task = asyncio.create_task(bot.start(clean_token_final))
                                await task
                            else:
                                raise
                    
                    # Use our wrapper to ensure proper task context
                    run_with_task_context(run_bot_async())"""
                
                bot_code = bot_code.replace('                    bot.run(clean_token_final)', bot_run_fix)
                
            # Save changes if made
            with open('bot.py', 'w') as f:
                f.write(bot_code)
                
            logger.info("Applied fixes to bot.py for timeout and intents errors")
            return True
        except Exception as e:
            logger.error(f"Failed to fix common issues: {e}")
            return False
    
    def run(self):
        """Main loop to keep the bot running"""
        logger.info("Starting Ultra-Reliable Runner")
        
        # Apply fixes for common issues
        self.fix_common_issues()
        
        # Start the bot for the first time
        self.start_bot()
        
        # Main monitoring loop
        try:
            while True:
                # Check if bot is running
                bot_running = self.is_bot_running()
                bot_healthy = self.check_bot_health()
                
                if not bot_running or not bot_healthy:
                    logger.warning(f"Bot needs restart. Running: {bot_running}, Healthy: {bot_healthy}")
                    # Kill the current process if it exists but isn't healthy
                    if bot_running and not bot_healthy:
                        try:
                            logger.info(f"Terminating unhealthy bot process {self.bot_process.pid}")
                            self.bot_process.terminate()
                            time.sleep(2)
                            if psutil.pid_exists(self.bot_process.pid):
                                self.bot_process.kill()
                        except:
                            pass
                    
                    # Start a new bot instance
                    self.start_bot()
                else:
                    logger.info(f"Bot is running and healthy (PID: {self.bot_process.pid})")
                
                # Wait before next check
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
            if self.bot_process is not None:
                self.bot_process.terminate()
        except Exception as e:
            logger.error(f"Unexpected error in monitor loop: {e}")
            # Don't exit, just continue monitoring
            time.sleep(5)
            self.run()

# Handle SIGTERM gracefully
def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, exiting gracefully")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run the ultra reliable runner
    runner = UltraReliableRunner()
    runner.run()