#!/usr/bin/env python3
"""
Helper script to apply timeout fixes and restart the bot safely
"""

import os
import sys
import logging
import subprocess
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("apply_timeout_fixes.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("apply_fixes")

def restart_bot():
    """Restart the Discord bot safely"""
    logger.info("Restarting Discord bot with timeout fixes")
    
    # First, run the fix script
    try:
        subprocess.run([sys.executable, "fix_timeout_errors.py"], check=True)
        logger.info("Successfully applied timeout fixes")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to apply timeout fixes: {e}")
        return False
    
    # Kill any existing bot processes
    try:
        subprocess.run([sys.executable, "kill_processes.py"], check=True)
        logger.info("Killed existing bot processes")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to kill existing processes: {e}")
    
    # Wait a moment
    time.sleep(2)
    
    # Start the bot using keep_running.py
    try:
        subprocess.Popen(
            [sys.executable, "keep_running.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        logger.info("Started bot using keep_running.py")
        return True
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        return False

if __name__ == "__main__":
    restart_bot()
