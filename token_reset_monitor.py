#!/usr/bin/env python
"""
Token Reset Monitor

This script specifically monitors for Discord token authentication failures
and automatically restarts the entire bot system when token issues are detected.
It works alongside the existing recovery systems but is focused on addressing
token-specific problems that might cause those systems to fail.

Unlike other monitoring solutions, this one:
1. Only focuses on token authentication issues
2. Has a more aggressive restart approach for token problems
3. Can run independently even if other monitors fail
4. Uses a different health check mechanism to avoid the same failure points
"""

import os
import sys
import time
import subprocess
import logging
import re
import signal
import datetime
import requests
import psutil
import traceback
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("token_monitor.log")
    ]
)
logger = logging.getLogger("token_monitor")

# Configuration
CHECK_INTERVAL = 60  # Check every minute
LOG_FILES = ["bot_errors.log", "bot.log"]
AUTH_ERROR_PATTERNS = [
    r"Authentication failed.*token",
    r"LoginFailure.*token",
    r"401 Unauthorized",
    r"Improper token"
]
MAX_RETRY_COUNT = 3
RETRY_COOLDOWN = 300  # 5 minutes between full restarts
LOCK_FILE = "token_monitor.lock"
PID_FILE = "token_monitor.pid"

class TokenMonitor:
    def __init__(self):
        """Initialize the token monitor."""
        self.last_restart_time = None
        self.restart_count = 0
        self.create_lock_file()
        self.save_pid()
        
    def create_lock_file(self):
        """Create a lock file to prevent multiple instances."""
        if os.path.exists(LOCK_FILE):
            try:
                # Check if the process is still running
                with open(PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                if self.is_process_running(pid):
                    logger.error(f"Another instance is already running (PID: {pid})")
                    sys.exit(1)
                else:
                    logger.warning("Found stale lock file, removing it")
                    os.remove(LOCK_FILE)
            except Exception as e:
                logger.warning(f"Error checking lock file: {e}")
                # Remove the lock file if we can't check it
                try:
                    os.remove(LOCK_FILE)
                except:
                    pass

        # Create the lock file
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
            
    def save_pid(self):
        """Save the current process ID."""
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    
    def is_process_running(self, pid):
        """Check if a process with the given PID is running."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def check_for_token_issues(self):
        """Check logs for token authentication issues."""
        found_issues = False
        recent_auth_errors = []
        
        for log_file in LOG_FILES:
            if not os.path.exists(log_file):
                continue
                
            try:
                # Get file size and read only the last 50KB if file is large
                file_size = os.path.getsize(log_file)
                read_size = min(50 * 1024, file_size)  # Read at most 50KB
                
                with open(log_file, 'r') as f:
                    if read_size < file_size:
                        f.seek(file_size - read_size)
                        # Discard partial line
                        f.readline()
                    
                    log_content = f.read()
                    
                    # Check for authentication error patterns
                    for pattern in AUTH_ERROR_PATTERNS:
                        matches = re.findall(pattern, log_content)
                        if matches:
                            found_issues = True
                            # Get timestamp if available (looking for patterns like 2025-03-25 11:24:36)
                            timestamp_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', log_content)
                            timestamp = timestamp_match.group(0) if timestamp_match else "unknown_time"
                            
                            # Extract context around the error
                            for match in matches:
                                error_index = log_content.find(match)
                                start_index = max(0, error_index - 100)
                                end_index = min(len(log_content), error_index + 200)
                                context = log_content[start_index:end_index]
                                
                                # Clean up context for logging
                                context = re.sub(r'\s+', ' ', context).strip()
                                recent_auth_errors.append(f"{timestamp}: {context}")
            except Exception as e:
                logger.error(f"Error reading log file {log_file}: {e}")
        
        # If issues were found, log the details
        if found_issues:
            logger.warning("Found token authentication issues in logs")
            for i, error in enumerate(recent_auth_errors[-3:]):  # Show last 3 errors
                logger.warning(f"Auth error {i+1}: {error}")
        
        return found_issues
    
    def kill_all_bot_processes(self):
        """Kill all bot-related processes."""
        logger.warning("Killing all bot processes")
        process_patterns = [
            "main.py", "gunicorn", "bot.py", 
            "health_monitor.py", "keep_running.py"
        ]
        
        for pattern in process_patterns:
            self.kill_process_by_pattern(pattern)
        
        # Wait for processes to terminate
        time.sleep(5)
    
    def kill_process_by_pattern(self, pattern):
        """Kill processes whose cmdline contains the given pattern."""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
                if pattern in cmdline and proc.info['pid'] != os.getpid():
                    logger.info(f"Killing process {proc.info['pid']}: {cmdline}")
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    def clean_lock_files(self):
        """Remove lock files that might prevent restarts."""
        lock_files = ["bot.lock", "watchdog.lock", "monitor.lock"]
        for lock_file in lock_files:
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                    logger.info(f"Removed lock file: {lock_file}")
                except Exception as e:
                    logger.error(f"Failed to remove lock file {lock_file}: {e}")
    
    def restart_bot_system(self):
        """Perform a full restart of the bot system."""
        current_time = datetime.datetime.now()
        
        # Check if we're in cooldown period
        if self.last_restart_time:
            cooldown_seconds = (current_time - self.last_restart_time).total_seconds()
            if cooldown_seconds < RETRY_COOLDOWN:
                logger.info(f"In cooldown period ({cooldown_seconds:.1f}s / {RETRY_COOLDOWN}s), skipping restart")
                return False
        
        logger.warning("===== INITIATING FULL SYSTEM RESTART =====")
        self.restart_count += 1
        self.last_restart_time = current_time
        
        try:
            # 1. Kill all processes
            self.kill_all_bot_processes()
            
            # 2. Clean up lock files
            self.clean_lock_files()
            
            # 3. Wait for everything to settle
            time.sleep(5)
            
            # 4. Start the primary bot system
            logger.info("Starting bot using keep_running.py")
            if os.path.exists("keep_running.py"):
                subprocess.Popen(
                    ["python", "keep_running.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            elif os.path.exists("main.py"):
                # Fallback to direct start
                logger.info("Starting bot directly using main.py")
                subprocess.Popen(
                    ["python", "main.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            else:
                logger.error("Could not find bot starting script")
                return False
            
            # 5. Wait and then start health monitor if available
            time.sleep(10)
            if os.path.exists("health_monitor.py"):
                logger.info("Starting health monitor")
                subprocess.Popen(
                    ["python", "health_monitor.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            
            # Log success
            logger.info(f"Bot system restarted successfully (attempt {self.restart_count})")
            
            # Write status to file
            with open("token_monitor_status.log", "a") as f:
                f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - "
                        f"Restart #{self.restart_count} completed\n")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to restart bot system: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def run(self):
        """Main monitoring loop."""
        logger.info("===== Token Authentication Monitor Started =====")
        logger.info(f"PID: {os.getpid()}, monitoring for token issues every {CHECK_INTERVAL} seconds")
        
        check_count = 0
        
        try:
            while True:
                check_count += 1
                
                # Perform the check
                if check_count % 5 == 0:
                    logger.info(f"Performing check #{check_count}")
                
                if self.check_for_token_issues():
                    logger.warning("Token authentication issues detected")
                    self.restart_bot_system()
                
                # Sleep until next check
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Token monitor stopped by user")
        except Exception as e:
            logger.error(f"Error in token monitor: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Clean up lock file
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
            logger.info("Token monitor shut down")

def signal_handler(sig, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {sig}, shutting down")
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    monitor = TokenMonitor()
    monitor.run()