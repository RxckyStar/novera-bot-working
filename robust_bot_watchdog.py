#!/usr/bin/env python3
"""
ULTRA-RELIABLE BOT WATCHDOG
--------------------------
This script provides an ultra-reliable watchdog that:
1. Monitors the bot's heartbeat
2. Detects if the bot process has crashed
3. Automatically restarts the bot when needed
4. Logs all actions and errors
5. Keeps track of restart attempts to avoid restart loops
6. Handles graceful shutdown and startup
7. Monitors health API endpoint
8. Can force-kill and restart unresponsive bots

Run this alongside your bot to ensure 24/7 uptime.
"""

import os
import sys
import time
import json
import signal
import logging
import datetime
import subprocess
import threading
import traceback
import requests
from typing import Dict, List, Optional, Set, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_watchdog.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("bot_watchdog")

# Configuration
HEARTBEAT_FILE = "bot_heartbeat.json"
HEARTBEAT_MAX_AGE = 120  # 2 minutes
MAX_RESTARTS_PER_HOUR = 5
CHECK_INTERVAL = 30  # seconds between checks
BOT_START_COMMAND = ["python", "bot.py"]
RESTART_COOLDOWN = 10  # seconds between restart attempts
HEALTH_CHECK_URL = "http://localhost:5001/healthz"  # Health check endpoint
FORCE_KILL_AFTER = 300  # Force kill after 5 minutes of unresponsiveness
CRITICAL_ERROR_PATTERNS = [
    "RuntimeError: Timeout context manager should be used inside a task",
    "RuntimeError: This event loop is already running",
    "RuntimeError: asyncio.run() cannot be called from a running event loop",
    "TypeError: 'async_generator' object does not support the asynchronous context manager protocol",
    "IncompleteReadError"
]

class BotWatchdog:
    def __init__(self):
        self.restart_history: List[float] = []
        self.bot_process: Optional[subprocess.Popen] = None
        self.is_shutting_down = False
        self.lock = threading.Lock()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
        logger.info("Bot watchdog initialized")
    
    def handle_signal(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {signum}, shutting down watchdog")
        self.is_shutting_down = True
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Clean up resources before exiting"""
        if self.bot_process and self.bot_process.poll() is None:
            logger.info("Terminating bot process")
            try:
                # Check if bot process exists and has terminate method
                if hasattr(self.bot_process, 'terminate'):
                    self.bot_process.terminate()
                    # Wait for a bit to let it terminate gracefully
                    time.sleep(2)
                    if self.bot_process.poll() is None and hasattr(self.bot_process, 'kill'):
                        self.bot_process.kill()
            except Exception as e:
                logger.error(f"Error terminating bot process: {e}")
    
    def read_heartbeat(self) -> Optional[Dict]:
        """Read the heartbeat file and return the data"""
        try:
            if not os.path.exists(HEARTBEAT_FILE):
                logger.warning(f"Heartbeat file {HEARTBEAT_FILE} does not exist")
                return None
            
            with open(HEARTBEAT_FILE, 'r') as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding heartbeat file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading heartbeat file: {e}")
            return None
    
    def check_heartbeat(self) -> bool:
        """Check if the heartbeat is recent enough"""
        heartbeat_data = self.read_heartbeat()
        if not heartbeat_data:
            return False
        
        try:
            last_timestamp = heartbeat_data.get('timestamp', 0)
            current_time = time.time()
            age = current_time - last_timestamp
            
            if age > HEARTBEAT_MAX_AGE:
                logger.warning(f"Heartbeat is too old: {age:.2f} seconds")
                return False
            
            # Also check status
            status = heartbeat_data.get('status', '')
            if status == 'error':
                logger.warning(f"Heartbeat indicates error status: {status}")
                return False
            
            logger.info(f"Heartbeat is fresh: {age:.2f} seconds old, status: {status}")
            return True
        except Exception as e:
            logger.error(f"Error checking heartbeat: {e}")
            return False
    
    def check_health_endpoint(self) -> bool:
        """Check if the bot's health endpoint is responsive"""
        try:
            response = requests.get(HEALTH_CHECK_URL, timeout=5)
            if response.status_code == 200:
                logger.info("Health check endpoint is responsive")
                return True
            else:
                logger.warning(f"Health check endpoint returned non-200 status: {response.status_code}")
                return False
        except requests.RequestException as e:
            logger.warning(f"Health check endpoint is not responsive: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking health endpoint: {e}")
            return False
    
    def check_for_critical_errors(self) -> bool:
        """Check bot.log for critical errors that indicate a restart is needed"""
        try:
            # Look at the most recent log file
            if not os.path.exists("bot.log"):
                return False
            
            # Read the last 1000 lines (or less if file is smaller)
            with open("bot.log", "r") as f:
                # Move to end of file then go back 100KB
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                seek_size = min(100 * 1024, file_size)  # 100KB or file size
                f.seek(max(0, file_size - seek_size), os.SEEK_SET)
                
                # Read the content
                log_content = f.read()
            
            # Check for critical error patterns
            for pattern in CRITICAL_ERROR_PATTERNS:
                if pattern in log_content:
                    logger.warning(f"Found critical error pattern in logs: {pattern}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking for critical errors: {e}")
            return False
    
    def find_zombie_discord_processes(self) -> List[int]:
        """Find orphaned/zombie Discord bot processes that might be hung"""
        try:
            # Use ps command to find Python processes running discord-related files
            result = subprocess.run(
                ["ps", "-ef"],
                capture_output=True,
                text=True,
                check=False
            )
            
            pids = []
            current_pid = os.getpid()  # Don't kill ourselves
            bot_pid = self.bot_process.pid if self.bot_process else None
            
            for line in result.stdout.splitlines():
                if "python" in line and "bot.py" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1])
                            # Skip our watchdog and the current bot process
                            if pid != current_pid and pid != bot_pid:
                                pids.append(pid)
                        except ValueError:
                            continue
            
            return pids
        except Exception as e:
            logger.error(f"Error finding zombie processes: {e}")
            return []
    
    def kill_zombie_processes(self) -> int:
        """Kill any zombie/orphaned discord bot processes"""
        zombie_pids = self.find_zombie_discord_processes()
        if not zombie_pids:
            return 0
        
        killed_count = 0
        for pid in zombie_pids:
            try:
                logger.warning(f"Killing zombie discord process with PID: {pid}")
                os.kill(pid, signal.SIGKILL)
                killed_count += 1
            except Exception as e:
                logger.error(f"Failed to kill process {pid}: {e}")
        
        return killed_count
    
    def is_bot_process_running(self) -> bool:
        """Check if the bot process is still running"""
        if not self.bot_process:
            return False
        
        # poll() returns None if process is running, otherwise return code
        return self.bot_process.poll() is None
    
    def check_restart_rate(self) -> bool:
        """Check if we're not restarting too frequently"""
        now = time.time()
        one_hour_ago = now - 3600
        
        # Remove restarts older than one hour
        self.restart_history = [t for t in self.restart_history if t > one_hour_ago]
        
        # Check if we've restarted too many times recently
        return len(self.restart_history) < MAX_RESTARTS_PER_HOUR
    
    def start_bot(self) -> bool:
        """Start the bot process"""
        with self.lock:
            try:
                if self.is_bot_process_running():
                    logger.warning("Attempted to start bot, but it's already running")
                    return False
                
                logger.info("Starting bot process")
                self.bot_process = subprocess.Popen(
                    BOT_START_COMMAND,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                # Allow some time for the bot to initialize
                time.sleep(5)
                
                # Check if the process is still running
                if not self.is_bot_process_running():
                    logger.error("Bot process failed to start")
                    return False
                
                logger.info(f"Bot process started with PID {self.bot_process.pid}")
                
                # Record this restart attempt
                self.restart_history.append(time.time())
                return True
            except Exception as e:
                logger.error(f"Error starting bot process: {e}")
                return False
    
    def restart_bot(self) -> bool:
        """Restart the bot process"""
        with self.lock:
            try:
                # Terminate the current process if it's running
                if self.is_bot_process_running():
                    logger.info("Terminating existing bot process")
                    if hasattr(self.bot_process, 'terminate'):
                        self.bot_process.terminate()
                        # Give it a few seconds to terminate gracefully
                        time.sleep(RESTART_COOLDOWN)
                        if self.is_bot_process_running() and hasattr(self.bot_process, 'kill'):
                            logger.warning("Bot process did not terminate gracefully, forcing kill")
                            self.bot_process.kill()
                
                # Kill any zombie processes before starting new one
                killed_zombies = self.kill_zombie_processes()
                if killed_zombies > 0:
                    logger.info(f"Killed {killed_zombies} zombie processes before restart")
                    time.sleep(2)  # Give them time to fully die
                
                # Start a new process
                return self.start_bot()
            except Exception as e:
                logger.error(f"Error restarting bot process: {e}")
                return False
    
    def run(self):
        """Main watchdog loop"""
        logger.info("Starting bot watchdog")
        
        # Start the bot initially
        self.start_bot()
        
        # Variables to track health state
        last_health_check = time.time()
        unresponsive_since = None
        critical_errors_found = False
        
        while not self.is_shutting_down:
            try:
                # Check if the process is running
                process_running = self.is_bot_process_running()
                heartbeat_valid = self.check_heartbeat()
                
                # Check for critical errors occasionally (every 5 minutes)
                if time.time() - last_health_check > 300:
                    last_health_check = time.time()
                    critical_errors_found = self.check_for_critical_errors()
                    
                    # Also try the health endpoint
                    try:
                        health_endpoint_ok = self.check_health_endpoint()
                    except:
                        health_endpoint_ok = False
                        
                    if not health_endpoint_ok and process_running:
                        logger.warning("Health endpoint not responding but process is running")
                        if unresponsive_since is None:
                            unresponsive_since = time.time()
                    else:
                        unresponsive_since = None
                
                # Force restart for critical errors or if unresponsive for too long
                force_restart = critical_errors_found
                if unresponsive_since and (time.time() - unresponsive_since) > FORCE_KILL_AFTER:
                    logger.warning(f"Bot has been unresponsive for {time.time() - unresponsive_since:.1f} seconds, forcing restart")
                    force_restart = True
                    unresponsive_since = None
                
                # Restart if needed
                if not process_running or not heartbeat_valid or force_restart:
                    reason = []
                    if not process_running:
                        reason.append("process not running")
                    if not heartbeat_valid:
                        reason.append("invalid heartbeat")
                    if force_restart:
                        reason.append("critical errors found")
                    
                    logger.warning(f"Bot needs attention: {', '.join(reason)}")
                    
                    # Check if we're allowed to restart
                    if self.check_restart_rate():
                        logger.info("Attempting to restart bot")
                        success = self.restart_bot()
                        if success:
                            logger.info("Bot successfully restarted")
                            critical_errors_found = False
                            unresponsive_since = None
                        else:
                            logger.error("Failed to restart bot")
                    else:
                        logger.error("Too many restarts in the past hour, cooling down")
                        # Kill zombie processes anyway to avoid resource leaks
                        self.kill_zombie_processes()
                        # Wait a bit longer before checking again
                        time.sleep(RESTART_COOLDOWN)
                
                # Wait before checking again
                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
                logger.error(traceback.format_exc())
                time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    watchdog = BotWatchdog()
    try:
        watchdog.run()
    except Exception as e:
        logger.critical(f"Fatal error in watchdog: {e}")
        watchdog.cleanup()
        sys.exit(1)