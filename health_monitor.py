#!/usr/bin/env python3
"""
Health monitoring script for Discord bot
This script performs periodic checks on the bot's health and can restart it if necessary
"""

import os
import sys
import json
import time
import logging
import requests
import subprocess
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("health_monitor.log")
    ]
)
logger = logging.getLogger("health_monitor")

# Configuration
CHECK_INTERVAL = 30  # seconds - reduced for faster recovery
MAX_CONSECUTIVE_FAILURES = 3  
RESTART_COOLDOWN = 60  # 1 minute - reduced from 5 minutes for faster recovery
HEALTH_ENDPOINT = "http://127.0.0.1:5000/healthz"  # Main server runs on port 5000
ERROR_MESSAGE_THRESHOLD = 10  # How many concurrent errors to alert about

class HealthMonitor:
    def __init__(self):
        self.consecutive_failures = 0
        self.last_restart_time = None
        self.bot_process = None
        self.last_status = "unknown"
        self.start_time = datetime.now()
        self.check_count = 0
        self.success_count = 0
        self.failure_count = 0
        
    def check_health(self):
        """
        Check the health of the Discord bot by making a request to its health endpoint
        """
        try:
            self.check_count += 1
            response = requests.get(HEALTH_ENDPOINT, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                bot_connected = data.get("bot_connected", False)
                self.last_status = status
                
                # First check if the Discord bot is connected
                if not bot_connected:
                    self.consecutive_failures += 1
                    self.failure_count += 1
                    logger.warning(f"Discord bot is not connected - consecutive failures: {self.consecutive_failures}")
                    return False
                
                # Then check if the status indicates a problem
                if status in ["healthy", "warning"]:
                    self.consecutive_failures = 0
                    self.success_count += 1
                    
                    # Log occasional success information
                    if self.check_count % 10 == 0:
                        logger.info(f"Health check successful: status={status}, bot_connected={bot_connected} - Uptime: {data.get('uptime', 0)}s")
                        
                    if status == "warning":
                        logger.warning(f"Bot status is WARNING: last heartbeat age is {data.get('last_heartbeat_age', 0)}s")
                    
                    return True
                else:
                    # Status is not healthy or warning
                    self.consecutive_failures += 1
                    self.failure_count += 1
                    logger.warning(f"Bot status is {status} - consecutive failures: {self.consecutive_failures}")
                    return False
            else:
                # Non-200 response code
                self.consecutive_failures += 1
                self.failure_count += 1
                logger.warning(f"Health check failed with status code {response.status_code} - consecutive failures: {self.consecutive_failures}")
                return False
                
        except requests.RequestException as e:
            # Request failed (likely connection refused or timeout)
            self.consecutive_failures += 1
            self.failure_count += 1
            logger.warning(f"Health check error: {e} - consecutive failures: {self.consecutive_failures}")
            return False
        except Exception as e:
            # General error
            self.consecutive_failures += 1
            self.failure_count += 1
            logger.error(f"Unexpected error during health check: {e}")
            return False
    
    def should_restart(self):
        """
        Determine if the bot should be restarted based on health check results
        """
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            # Check if we're in the restart cooldown period
            if self.last_restart_time is not None:
                cooldown_elapsed = datetime.now() - self.last_restart_time
                if cooldown_elapsed.total_seconds() < RESTART_COOLDOWN:
                    # Still in cooldown, don't restart yet
                    logger.info(f"In restart cooldown period ({cooldown_elapsed.total_seconds():.1f}s / {RESTART_COOLDOWN}s)")
                    return False
            
            # Enough consecutive failures and not in cooldown - trigger a restart
            return True
        return False
    
    def restart_bot(self):
        """
        Restart the Discord bot
        """
        logger.warning("Attempting to restart the Discord bot")
        try:
            # First, try using the restart endpoint
            try:
                restart_response = requests.post("http://127.0.0.1:5000/restart", timeout=5)  # Main server restart endpoint
                if restart_response.status_code == 200:
                    logger.info("Restart request sent successfully through API endpoint")
                    self.last_restart_time = datetime.now()
                    self.consecutive_failures = 0
                    return True
            except requests.RequestException:
                logger.warning("Failed to restart via API endpoint, trying process restart")
            
            # If API restart fails, try killing and restarting processes
            try:
                # Run the kill_processes.py script if it exists
                if os.path.exists("kill_processes.py"):
                    subprocess.run(["python", "kill_processes.py"], timeout=10)
                    logger.info("Ran kill_processes.py to clean up any stale processes")
                    time.sleep(2)
                
                # Start the bot using keep_running.py
                if os.path.exists("keep_running.py"):
                    subprocess.Popen(
                        ["python", "keep_running.py"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                    logger.info("Started bot using keep_running.py")
                else:
                    # Fallback to starting the main.py directly
                    subprocess.Popen(
                        ["python", "main.py"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                    logger.info("Started bot using main.py")
                
                self.last_restart_time = datetime.now()
                self.consecutive_failures = 0
                return True
                
            except Exception as e:
                logger.error(f"Failed to restart bot processes: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error during bot restart: {e}")
            return False
    
    def save_status(self):
        """
        Save monitor status to a status file
        """
        status = {
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "uptime": (datetime.now() - self.start_time).total_seconds(),
            "check_count": self.check_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "last_status": self.last_status,
            "last_restart": self.last_restart_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_restart_time else None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            with open("health_monitor_status.json", "w") as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save status: {e}")
    
    def check_error_logs(self):
        """
        Check the error log files for recent errors
        """
        try:
            # Check if error logs exist and have recent errors
            if os.path.exists("bot_errors.log"):
                # Get the file modification time
                mod_time = os.path.getmtime("bot_errors.log")
                mod_time_dt = datetime.fromtimestamp(mod_time)
                
                # Check if the file was modified in the last hour
                if datetime.now() - mod_time_dt < timedelta(hours=1):
                    with open("bot_errors.log", "r") as f:
                        errors = f.readlines()
                    
                    # Count errors in the last hour
                    recent_errors = []
                    for error in errors[-ERROR_MESSAGE_THRESHOLD:]:
                        if error.strip():
                            recent_errors.append(error.strip())
                    
                    if recent_errors:
                        logger.warning(f"Found {len(recent_errors)} recent errors in bot_errors.log")
                        for i, error in enumerate(recent_errors[-3:]):  # Log the last 3 errors
                            logger.warning(f"Recent error {i+1}: {error[:150]}...")
        except Exception as e:
            logger.error(f"Error checking error logs: {e}")
    
    def run(self):
        """
        Main monitoring loop
        """
        logger.info("Starting Discord bot health monitor")
        
        try:
            while True:
                # Check the bot's health
                is_healthy = self.check_health()
                
                # Periodically check for errors in logs
                if self.check_count % 5 == 0:
                    self.check_error_logs()
                
                # Save status periodically
                if self.check_count % 10 == 0:
                    self.save_status()
                
                # If unhealthy, check if we should restart the bot
                if not is_healthy and self.should_restart():
                    logger.warning(f"Health check failed {self.consecutive_failures} times in a row. Restarting the bot.")
                    if self.restart_bot():
                        logger.info("Bot restart initiated, waiting for recovery...")
                    else:
                        logger.error("Failed to restart the bot")
                
                # Sleep until the next check
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Health monitor stopped by user")
        except Exception as e:
            logger.critical(f"Health monitor crashed: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    monitor = HealthMonitor()
    monitor.run()