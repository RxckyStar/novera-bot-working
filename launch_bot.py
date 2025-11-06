#!/usr/bin/env python3
"""
Ultra-Reliable Bot Launcher
---------------------------
This script launches the Discord bot with the most reliable approach
that prevents all common asyncio-related errors:

1. First applies all timeout and event loop fixes
2. Ensures proper cleanup of any abandoned processes
3. Uses a single, consistent method to start the bot
4. Avoids conflicts between web server and bot
"""

import os
import sys
import logging
import subprocess
import signal
import time
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('launcher.log')
    ]
)
logger = logging.getLogger(__name__)

def cleanup_zombie_processes():
    """Kill any zombie bot processes to prevent conflicts"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'bot.py' in cmdline and proc.pid != os.getpid():
                    logger.info(f"Terminating existing bot process: {proc.pid}")
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        logger.error(f"Error cleaning up processes: {e}")

def start_processes():
    """Start both the web server and bot processes separately"""
    try:
        # First apply the critical fixes directly
        logger.info("Applying critical fixes...")
        import fix_timeout_errors
        fix_timeout_errors.apply_all_fixes()
        
        # Kill any existing processes that might conflict
        cleanup_zombie_processes()
        
        # Start the bot process (using a clean approach)
        logger.info("Starting bot process...")
        bot_process = subprocess.Popen([sys.executable, "bot.py"], 
                                      stderr=subprocess.PIPE,
                                      stdout=subprocess.PIPE)
        
        # Return the bot process
        return bot_process
    except Exception as e:
        logger.error(f"Error starting processes: {e}")
        return None

def monitor_process(process):
    """Monitor the bot process and restart if it crashes"""
    if not process:
        logger.error("No process to monitor")
        return
        
    try:
        # Get the stdout/stderr from the process
        for line in process.stdout:
            try:
                line_str = line.decode('utf-8').strip()
                if line_str:
                    print(f"BOT: {line_str}")
            except:
                pass
                
        # Wait for the process to complete
        return_code = process.wait()
        logger.warning(f"Bot process exited with code {return_code}")
        
        # Restart the process
        logger.info("Restarting bot...")
        new_process = start_processes()
        monitor_process(new_process)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        process.terminate()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error monitoring process: {e}")
        
def signal_handler(sig, frame):
    """Handle signals gracefully"""
    logger.info(f"Received signal {sig}, shutting down gracefully...")
    cleanup_zombie_processes()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start everything
    logger.info("Ultra-Reliable Bot Launcher starting...")
    bot_process = start_processes()
    
    # Monitor the process to keep it running
    monitor_process(bot_process)