#!/usr/bin/env python3
"""
Super Monitor Script
-------------------
This script monitors the Discord bot and restarts it if necessary,
checking both the process and the health endpoint.
"""

import os
import sys
import time
import logging
import subprocess
import requests
import signal
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('super_monitor.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
HEALTH_CHECK_URL = "http://127.0.0.1:5001/healthz"
CHECK_INTERVAL = 30  # seconds
MAX_RESTART_ATTEMPTS = 3
HEALTH_CHECK_TIMEOUT = 5  # seconds

def is_bot_process_running():
    """Check if the bot process is running"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'bot.py' in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False
    except Exception as e:
        logger.error(f"Error checking bot process: {e}")
        return False

def is_bot_healthy():
    """Check if the bot is healthy via the health endpoint"""
    try:
        response = requests.get(HEALTH_CHECK_URL, timeout=HEALTH_CHECK_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            return data.get('bot_connected', False) and data.get('status') == 'healthy'
        return False
    except Exception as e:
        logger.error(f"Error checking bot health: {e}")
        return False

def start_bot():
    """Start or restart the Discord bot"""
    try:
        # First, kill any existing bot processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'bot.py' in cmdline:
                    logger.info(f"Terminating existing bot process: {proc.pid}")
                    proc.terminate()
                    time.sleep(2)  # Give it time to shut down
                    if proc.is_running():
                        proc.kill()  # Force kill if still running
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        # Start the bot using our most reliable script
        logger.info("Starting bot...")
        subprocess.Popen([sys.executable, "bot_start.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
        
        # Wait for the bot to start up
        logger.info("Waiting for bot to start...")
        time.sleep(10)
        
        return is_bot_process_running()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return False

def monitor():
    """Main monitoring loop"""
    restart_attempts = 0
    
    while True:
        try:
            # Check if the bot process is running
            process_running = is_bot_process_running()
            
            # Check if the bot is healthy
            health_ok = is_bot_healthy()
            
            if not process_running or not health_ok:
                logger.warning(f"Bot status: Process running: {process_running}, Health OK: {health_ok}")
                
                # Only restart if we haven't exceeded the maximum attempts
                if restart_attempts < MAX_RESTART_ATTEMPTS:
                    logger.warning(f"Restarting bot (attempt {restart_attempts + 1}/{MAX_RESTART_ATTEMPTS})...")
                    success = start_bot()
                    if success:
                        logger.info("Bot restarted successfully")
                        restart_attempts = 0  # Reset counter on successful restart
                    else:
                        logger.error("Failed to restart bot")
                        restart_attempts += 1
                else:
                    logger.critical(f"Maximum restart attempts ({MAX_RESTART_ATTEMPTS}) reached")
                    # Reset counter after a longer wait to try again
                    time.sleep(300)  # 5 minutes
                    restart_attempts = 0
            else:
                logger.info("Bot is running and healthy")
                restart_attempts = 0  # Reset counter when everything is good
                
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in monitor: {e}")
            time.sleep(CHECK_INTERVAL)  # Continue monitoring despite errors

if __name__ == "__main__":
    logger.info("Super Monitor starting...")
    monitor()