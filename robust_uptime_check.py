#!/usr/bin/env python3
"""
Robust Uptime Check Script
This script implements multiple checks and recovery mechanisms to ensure
the Discord bot stays running, handling various failure cases with intelligent
recovery strategies.
"""

import os
import sys
import time
import json
import logging
import signal
import requests
import psutil
import asyncio
import threading
import subprocess
from datetime import datetime, timedelta

# Configure logging with robust format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("robust_uptime_check.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("robust_uptime")

# Configuration
CHECK_INTERVAL = 20  # seconds
MAX_CONSECUTIVE_FAILURES = 2
RESTART_COOLDOWN = 60  # seconds
HEALTH_CHECK_URL = "http://127.0.0.1:5000/healthz"
BOT_PID_FILE = "bot.pid"
RESTART_LOCK_FILE = "restart.lock"
LOG_CHECK_FILES = [
    "bot.log", 
    "bot_errors.log", 
    "health_monitor.log",
    "timeout_fix.log"
]

class RobustUptimeMonitor:
    """Monitors and maintains bot uptime with enhanced error recovery"""
    
    def __init__(self):
        self.consecutive_failures = 0
        self.last_restart_time = None
        self.start_time = datetime.now()
        self.check_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.recovery_attempts = 0
        self.last_log_check_time = datetime.now() - timedelta(hours=1)  # Force initial check
        self.restart_in_progress = False
        
    def check_health(self):
        """
        Check the health of the Discord bot by making a request to its health endpoint.
        Returns True if healthy, False otherwise.
        """
        try:
            self.check_count += 1
            response = requests.get(HEALTH_CHECK_URL, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                bot_connected = data.get("bot_connected", False)
                
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
                        logger.info(f"Health check successful: status={status}, bot_connected={bot_connected}")
                        
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
                logger.warning(f"Health check failed with status code {response.status_code}")
                return False
                
        except requests.RequestException as e:
            # Request failed (likely connection refused or timeout)
            self.consecutive_failures += 1
            self.failure_count += 1
            logger.warning(f"Health check error: {e}")
            return False
        except Exception as e:
            # General error
            self.consecutive_failures += 1
            self.failure_count += 1
            logger.error(f"Unexpected error during health check: {e}")
            return False
    
    def should_restart(self):
        """
        Determine if the bot should be restarted based on health check results and cooldown.
        Returns True if restart is needed, False otherwise.
        """
        # Check for restart lock file to prevent concurrent restarts
        if os.path.exists(RESTART_LOCK_FILE):
            try:
                mtime = os.path.getmtime(RESTART_LOCK_FILE)
                age = time.time() - mtime
                
                # If lock file is recent, don't restart
                if age < 300:  # 5 minutes
                    logger.info(f"Restart lock file exists (age: {age:.1f}s), skipping restart")
                    return False
                    
                # Lock file is old, remove it
                logger.warning(f"Found stale restart lock file (age: {age:.1f}s), removing")
                os.remove(RESTART_LOCK_FILE)
            except Exception as e:
                logger.error(f"Error checking restart lock file: {e}")
        
        # Check consecutive failures
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            # Check if we're in the restart cooldown period
            if self.last_restart_time is not None:
                cooldown_elapsed = (datetime.now() - self.last_restart_time).total_seconds()
                if cooldown_elapsed < RESTART_COOLDOWN:
                    # Still in cooldown, don't restart yet
                    logger.info(f"In restart cooldown period ({cooldown_elapsed:.1f}s / {RESTART_COOLDOWN}s)")
                    return False
            
            # Enough consecutive failures and not in cooldown - trigger a restart
            return True
        return False
    
    def check_logs_for_errors(self):
        """
        Check log files for recent errors.
        Returns a list of critical errors found, if any.
        """
        # Only check logs every 5 minutes
        if (datetime.now() - self.last_log_check_time).total_seconds() < 300:
            return []
        
        self.last_log_check_time = datetime.now()
        critical_errors = []
        
        for log_file in LOG_CHECK_FILES:
            if not os.path.exists(log_file):
                continue
                
            try:
                # Get file modification time
                mtime = os.path.getmtime(log_file)
                age = time.time() - mtime
                
                # Only check recently modified logs
                if age > 600:  # 10 minutes
                    continue
                    
                with open(log_file, 'r', errors='replace') as f:
                    # Read the last 100 lines
                    lines = f.readlines()[-100:]
                    
                    # Check for critical error patterns
                    for line in lines:
                        if any(pattern in line.lower() for pattern in [
                            "critical", "fatal", "timeout context manager", 
                            "asyncio.run() cannot be called", "event loop is closed",
                            "runtimeerror", "connectionclosed", "unauthorized", "401"
                        ]):
                            critical_errors.append((log_file, line.strip()))
            except Exception as e:
                logger.error(f"Error checking log file {log_file}: {e}")
                
        return critical_errors
    
    def check_bot_process(self):
        """
        Check if the bot process is running properly.
        Returns True if the process is healthy, False otherwise.
        """
        try:
            # First check if the PID file exists
            if not os.path.exists(BOT_PID_FILE):
                logger.warning("Bot PID file not found")
                return False
                
            # Read the PID from the file
            with open(BOT_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
                
            # Check if the process exists
            if not psutil.pid_exists(pid):
                logger.warning(f"Bot process with PID {pid} not found")
                return False
                
            # Check if the process is a Python process running bot.py
            process = psutil.Process(pid)
            cmd = " ".join(process.cmdline())
            
            if "python" not in cmd.lower() or "bot.py" not in cmd:
                logger.warning(f"Process with PID {pid} is not the bot: {cmd}")
                return False
                
            # Check CPU and memory usage for signs of issues
            try:
                cpu_percent = process.cpu_percent(interval=0.1)
                memory_percent = process.memory_percent()
                
                if cpu_percent > 95:  # Extremely high CPU usage
                    logger.warning(f"Bot process has very high CPU usage: {cpu_percent}%")
                    return False
                    
                if memory_percent > 90:  # Extremely high memory usage
                    logger.warning(f"Bot process has very high memory usage: {memory_percent}%")
                    return False
            except Exception as e:
                logger.error(f"Error checking process resources: {e}")
                
            return True
        except Exception as e:
            logger.error(f"Error checking bot process: {e}")
            return False
    
    def restart_bot(self):
        """
        Restart the Discord bot using multiple strategies.
        Returns True if restart was initiated successfully, False otherwise.
        """
        if self.restart_in_progress:
            logger.warning("Restart already in progress, skipping")
            return False
            
        self.restart_in_progress = True
        logger.warning("Attempting to restart the Discord bot")
        
        try:
            # Create restart lock file
            with open(RESTART_LOCK_FILE, 'w') as f:
                f.write(str(datetime.now()))
                
            # First, try using the restart endpoint
            try:
                restart_response = requests.post("http://127.0.0.1:5000/restart", timeout=5)
                if restart_response.status_code == 200:
                    logger.info("Restart request sent successfully through API endpoint")
                    self.last_restart_time = datetime.now()
                    self.recovery_attempts += 1
                    self.restart_in_progress = False
                    return True
            except requests.RequestException:
                logger.warning("Failed to restart via API endpoint, trying process restart")
            
            # Kill any existing bot processes
            self._kill_bot_processes()
            
            # Try different restart strategies based on recovery attempts
            if self.recovery_attempts < 2:
                # Strategy 1: Use keep_running.py (standard approach)
                self._restart_with_keep_running()
            elif self.recovery_attempts < 4:
                # Strategy 2: Apply timeout fixes first, then restart
                self._restart_with_timeout_fixes()
            else:
                # Strategy 3: Full reset with all fixes
                self._full_reset_restart()
                
            self.last_restart_time = datetime.now()
            self.recovery_attempts += 1
            self.restart_in_progress = False
            return True
                
        except Exception as e:
            logger.error(f"Error during bot restart: {e}")
            self.restart_in_progress = False
            return False
    
    def _kill_bot_processes(self):
        """Kill all bot-related processes"""
        try:
            # Try using the kill_processes.py script if it exists
            if os.path.exists("kill_processes.py"):
                logger.info("Running kill_processes.py")
                subprocess.run([sys.executable, "kill_processes.py"], timeout=10)
                time.sleep(2)
                return
                
            # Fallback: Find and kill Python processes running bot.py
            killed = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and 'python' in cmdline[0].lower() and any('bot.py' in cmd for cmd in cmdline):
                        logger.info(f"Killing bot process: PID {proc.info['pid']}")
                        psutil.Process(proc.info['pid']).terminate()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
            logger.info(f"Killed {killed} bot processes")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error killing bot processes: {e}")
    
    def _restart_with_keep_running(self):
        """Restart using the keep_running.py script"""
        logger.info("Restarting bot using keep_running.py")
        try:
            subprocess.Popen(
                [sys.executable, "keep_running.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to restart with keep_running.py: {e}")
            return False
    
    def _restart_with_timeout_fixes(self):
        """Apply timeout fixes and restart"""
        logger.info("Applying timeout fixes before restart")
        try:
            # Run the timeout fix script
            subprocess.run([sys.executable, "fix_timeout_errors.py"], timeout=30)
            time.sleep(1)
            
            # Then start with keep_running.py
            return self._restart_with_keep_running()
        except Exception as e:
            logger.error(f"Failed to apply timeout fixes: {e}")
            return self._restart_with_keep_running()  # Fallback
    
    def _full_reset_restart(self):
        """Full reset with all fixes applied"""
        logger.info("Performing full reset with all fixes")
        try:
            # Run all fix scripts
            subprocess.run([sys.executable, "fix_timeout_errors.py"], timeout=30)
            time.sleep(1)
            subprocess.run([sys.executable, "timeout_fix.py"], timeout=30)
            time.sleep(1)
            
            # Then restart the bot using absolute_uptime.sh if it exists
            if os.path.exists("absolute_uptime.sh"):
                logger.info("Running absolute_uptime.sh for guaranteed restart")
                subprocess.Popen(
                    ["bash", "absolute_uptime.sh"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
                return True
            else:
                return self._restart_with_keep_running()  # Fallback
        except Exception as e:
            logger.error(f"Failed full reset: {e}")
            return self._restart_with_keep_running()  # Fallback
    
    def run(self):
        """Main monitoring loop"""
        logger.info("Starting robust Discord bot uptime monitor")
        
        try:
            while True:
                # Check if bot is healthy
                is_healthy = self.check_health()
                
                # Check for critical errors in logs (every 5 minutes)
                critical_errors = self.check_logs_for_errors()
                if critical_errors:
                    logger.warning(f"Found {len(critical_errors)} critical errors in logs")
                    for log_file, error in critical_errors[:3]:  # Show first 3 errors
                        logger.warning(f"Error in {log_file}: {error}")
                    
                    # Force health check failure if critical errors are found
                    is_healthy = False
                    self.consecutive_failures += 1
                
                # If unhealthy, check if we should restart
                if not is_healthy and self.should_restart():
                    logger.warning(f"Health check failed {self.consecutive_failures} times. Restarting the bot.")
                    if self.restart_bot():
                        logger.info("Bot restart initiated")
                    else:
                        logger.error("Failed to restart the bot")
                
                # Sleep until the next check
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Uptime monitor stopped by user")
        except Exception as e:
            logger.critical(f"Uptime monitor crashed: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    monitor = RobustUptimeMonitor()
    monitor.run()