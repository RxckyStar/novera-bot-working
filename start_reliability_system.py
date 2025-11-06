#!/usr/bin/env python3
"""
Master startup script for the Discord bot reliability system.
This script:
1. Sets up the web server and bot
2. Starts the auto_401_recovery.py monitor
3. Starts the watchdog_401.py to ensure the recovery system itself stays running
4. Sets up any additional monitoring
"""

import os
import sys
import time
import subprocess
import logging
import signal
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("reliability_system.log")
    ]
)
logger = logging.getLogger("reliability_system")

def start_bot():
    """Start the Discord bot"""
    logger.info("Starting Discord bot")
    try:
        # Check if workflows are available
        if os.path.exists("/.replit"):
            # We're in a Replit environment, use workflows
            logger.info("Using Replit workflow to start bot")
            subprocess.run(["kill", "-9", "`pgrep -f 'main.py'`", "2>/dev/null"], shell=True)
            subprocess.run(["kill", "-9", "`pgrep -f 'bot.py'`", "2>/dev/null"], shell=True)
            time.sleep(2)  # Give processes time to fully terminate
            
            # Use Replit's workflow if available
            try:
                subprocess.Popen(
                    ["python", "bot.py"],
                    stdout=open("bot.log", "a"),
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
                logger.info("Started Discord bot via bot.py")
                return True
            except Exception as e:
                logger.error(f"Error starting bot.py: {e}")
                
            # Try main.py as fallback
            try:
                subprocess.Popen(
                    ["python", "main.py"],
                    stdout=open("main.log", "a"),
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
                logger.info("Started Discord bot via main.py")
                return True
            except Exception as e:
                logger.error(f"Error starting main.py: {e}")
                return False
        else:
            # Not in Replit, try standard startup
            subprocess.Popen(
                ["python", "bot.py"],
                stdout=open("bot.log", "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
            logger.info("Started Discord bot")
            return True
    except Exception as e:
        logger.error(f"Error starting Discord bot: {e}")
        return False

def start_recovery_system():
    """Start the auto_401_recovery.py script"""
    logger.info("Starting 401 recovery system")
    try:
        subprocess.Popen(
            ["python", "auto_401_recovery.py"],
            stdout=open("auto_401_recovery.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        logger.info("Started 401 recovery system")
        return True
    except Exception as e:
        logger.error(f"Error starting 401 recovery system: {e}")
        return False

def start_watchdog():
    """Start the watchdog_401.py script"""
    logger.info("Starting recovery watchdog")
    try:
        subprocess.Popen(
            ["python", "watchdog_401.py"],
            stdout=open("watchdog_401.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        logger.info("Started recovery watchdog")
        return True
    except Exception as e:
        logger.error(f"Error starting recovery watchdog: {e}")
        return False

def kill_existing_processes():
    """Kill any existing instances of our scripts"""
    logger.info("Terminating any existing processes")
    process_patterns = [
        "auto_401_recovery.py",
        "watchdog_401.py",
        "token_refresher.py",
        "token_monitor.py"
    ]
    
    current_pid = os.getpid()
    killed_count = 0
    
    # Use psutil to find and kill processes
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            proc_pid = proc.info['pid']
            cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
            
            # Skip our own process
            if proc_pid == current_pid:
                continue
                
            # Check if process matches any pattern
            if any(pattern in cmdline for pattern in process_patterns):
                logger.info(f"Killing process {proc_pid}: {cmdline[:50]}...")
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    try:
                        proc.kill()
                    except psutil.NoSuchProcess:
                        pass
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    logger.info(f"Killed {killed_count} existing processes")
    
    # Remove any stale lock files
    for lock_file in ["auto_401_recovery.pid", "401_recovery_startup.lock", "watchdog_401.pid"]:
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                logger.info(f"Removed stale lock file: {lock_file}")
            except OSError:
                pass


def main():
    """Main entry point"""
    logger.info("Starting Discord bot reliability system")
    
    # Kill any existing processes
    kill_existing_processes()
    
    # Start the main bot
    start_bot()
    
    # Give the bot time to start up
    time.sleep(5)
    
    # Start the 401 recovery system
    start_recovery_system()
    
    # Give the recovery system time to start
    time.sleep(2)
    
    # Start the watchdog
    start_watchdog()
    
    logger.info("All systems started successfully!")
    
    # Keep the script running to maintain child processes
    try:
        while True:
            time.sleep(60)  # Sleep and keep running
    except KeyboardInterrupt:
        logger.info("Received termination signal, exiting")
        sys.exit(0)


if __name__ == "__main__":
    # Handle signals gracefully
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, exiting gracefully")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    main()