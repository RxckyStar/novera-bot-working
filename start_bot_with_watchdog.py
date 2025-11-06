#!/usr/bin/env python3
"""
Start Bot with Watchdog
----------------------
This script launches the Discord bot with the watchdog process to ensure 24/7 uptime.
It handles graceful shutdown and cleanup of both processes.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import threading
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("start_bot_with_watchdog.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("start_bot_with_watchdog")

# Process information
watchdog_process: Optional[subprocess.Popen] = None
is_shutting_down = False

def handle_signal(signum, frame):
    """Handle termination signals"""
    global is_shutting_down
    
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    is_shutting_down = True
    cleanup()
    sys.exit(0)

def cleanup():
    """Clean up resources before exiting"""
    if watchdog_process and watchdog_process.poll() is None:
        logger.info("Terminating watchdog process")
        try:
            watchdog_process.terminate()
            # Wait for a bit to let it terminate gracefully
            time.sleep(3)
            if watchdog_process.poll() is None:
                logger.warning("Watchdog process did not terminate gracefully, forcing kill")
                watchdog_process.kill()
        except Exception as e:
            logger.error(f"Error terminating watchdog process: {e}")
    
    logger.info("Cleanup complete")

def start_watchdog():
    """Start the watchdog process"""
    global watchdog_process
    
    try:
        logger.info("Starting watchdog process")
        watchdog_process = subprocess.Popen(
            [sys.executable, "robust_bot_watchdog.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        logger.info(f"Watchdog process started with PID {watchdog_process.pid}")
        return True
    except Exception as e:
        logger.error(f"Error starting watchdog process: {e}")
        return False

def watch_process_output(process, name):
    """Watch a process's output and log it with proper prefixing"""
    while process.poll() is None and not is_shutting_down:
        try:
            line = process.stdout.readline()
            if line:
                logger.info(f"[{name}] {line.rstrip()}")
        except Exception as e:
            if not is_shutting_down:
                logger.error(f"Error reading {name} output: {e}")
                break
    
    logger.info(f"{name} process has ended")

def main():
    """Main function"""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    logger.info("Starting bot with watchdog")
    
    # Start the watchdog process (which will then start the bot)
    if not start_watchdog():
        logger.error("Failed to start watchdog process, exiting")
        return
    
    # Start a thread to watch the watchdog's output
    if watchdog_process and watchdog_process.stdout:
        watchdog_output_thread = threading.Thread(
            target=watch_process_output,
            args=(watchdog_process, "Watchdog"),
            daemon=True
        )
        watchdog_output_thread.start()
    
    # Monitor the watchdog process
    try:
        while watchdog_process and not is_shutting_down:
            # Check if the watchdog is still running
            if watchdog_process.poll() is not None:
                exit_code = watchdog_process.poll()
                logger.error(f"Watchdog process has exited with code {exit_code}")
                
                # If we're not shutting down, restart the watchdog
                if not is_shutting_down:
                    logger.info("Restarting watchdog process")
                    if not start_watchdog():
                        logger.error("Failed to restart watchdog process, exiting")
                        break
                    
                    # Start a new thread to watch the new watchdog's output
                    if watchdog_process and watchdog_process.stdout:
                        watchdog_output_thread = threading.Thread(
                            target=watch_process_output,
                            args=(watchdog_process, "Watchdog"),
                            daemon=True
                        )
                        watchdog_output_thread.start()
                
            # Sleep to avoid busy waiting
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, initiating graceful shutdown")
        is_shutting_down = True
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        cleanup()
        sys.exit(1)