"""
Error Monitor for Discord Bot
This script monitors the bot process and logs any errors in real-time.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("realtime_monitor.log")
    ]
)
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    """Handle termination signals gracefully"""
    logger.info("Monitor shutting down...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_bot_pid():
    """Find the Discord bot process ID"""
    try:
        # Check for bot.lock file first
        if os.path.exists("bot.lock"):
            with open("bot.lock", "r") as f:
                pid = int(f.read().strip())
                # Verify the process exists
                if os.path.exists(f"/proc/{pid}"):
                    logger.info(f"Found bot process with PID {pid} from lock file")
                    return pid
                else:
                    logger.warning(f"PID {pid} from lock file no longer exists")
        
        # Otherwise try to find the process by command line
        output = subprocess.check_output(["ps", "aux"], text=True)
        for line in output.splitlines():
            if "python" in line and "bot.py" in line and "grep" not in line:
                pid = int(line.split()[1])
                logger.info(f"Found bot process with PID {pid} from ps command")
                return pid
        
        logger.warning("No bot process found")
        return None
    except Exception as e:
        logger.error(f"Error finding bot PID: {e}")
        return None

def tail_log_file(file_path, num_lines=10):
    """Get the last N lines from a log file"""
    try:
        if not os.path.exists(file_path):
            return ["File does not exist"]
        
        output = subprocess.check_output(["tail", "-n", str(num_lines), file_path], text=True)
        return output.splitlines()
    except Exception as e:
        logger.error(f"Error tailing log file {file_path}: {e}")
        return [f"Error: {str(e)}"]

def monitor_bot():
    """Monitor the bot process and check for errors"""
    logger.info("Starting Discord bot monitor")
    
    # Main monitoring loop
    try:
        while True:
            bot_pid = get_bot_pid()
            if bot_pid:
                # Bot is running, check for any new errors in error log
                error_logs = tail_log_file("bot_errors.log", 5)
                if error_logs:
                    for line in error_logs:
                        if "Error" in line or "Exception" in line or "Traceback" in line:
                            logger.warning(f"Recent error detected: {line}")
                
                # Check bot's stdout/stderr logs
                bot_logs = tail_log_file("bot.log", 5)
                if bot_logs:
                    for line in bot_logs:
                        if "Error" in line or "Exception" in line or "Traceback" in line:
                            logger.warning(f"Recent log error: {line}")
                
                # Check if process is still responding
                try:
                    os.kill(bot_pid, 0)  # Signal 0 doesn't kill the process, just checks if it exists
                    logger.info(f"Bot process {bot_pid} is alive")
                except ProcessLookupError:
                    logger.critical(f"Bot process {bot_pid} no longer exists!")
            else:
                logger.warning("Bot is not running")
            
            # Check web health endpoint
            try:
                import requests
                response = requests.get("http://localhost:5001/healthz", timeout=3)
                if response.status_code == 200:
                    logger.info(f"Health check passed: {response.text}")
                else:
                    logger.warning(f"Health check failed: {response.status_code}, {response.text}")
            except Exception as e:
                logger.error(f"Health check request failed: {e}")
            
            # Wait before next check
            time.sleep(10)
    except Exception as e:
        logger.critical(f"Monitor crashed: {e}")
        logger.critical(traceback.format_exc())

if __name__ == "__main__":
    monitor_bot()