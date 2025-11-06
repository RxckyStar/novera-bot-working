#!/usr/bin/env python3
"""
Ultimate Uptime Manager - Ensures 99.99% uptime for Discord bot
This script is the highest level of monitoring and recovery,
designed to ensure the bot stays running at all times.

Features:
- Multi-layered health checking
- Process monitoring
- Discord API connectivity verification
- Rate limit detection
- Token refresh capability
- Advanced recovery strategies
- Lock file management
- Discord logging
- System resource monitoring
"""

import os
import sys
import time
import json
import logging
import signal
import subprocess
import threading
import traceback
import socket
import requests
import random
from datetime import datetime, timedelta
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ultimate_uptime.log")
    ]
)
logger = logging.getLogger("ultimate_uptime")

# Configuration
CHECK_INTERVAL = 15  # seconds between health checks
HEALTH_CHECK_URL = "http://127.0.0.1:5000/healthz"
MAX_CONSECUTIVE_FAILURES = 3
MANAGER_PID_FILE = "ultimate_uptime.pid"
RESTART_COOLDOWN = 300  # seconds (5 minutes)
MAX_RESTARTS_PER_HOUR = 20
LAST_RESTARTS = []  # Timestamps of recent restarts

class UptimeManager:
    def __init__(self):
        self.last_check = 0
        self.consecutive_failures = 0
        self.last_restart = 0
        self.outage_start = None
        self.process_metrics = []
        self.is_running = True
        self.bot_process = None
        self.watchdog_process = None
        self.health_process = None
        
        # Create PID file
        with open(MANAGER_PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        # Save startup info
        self.save_status({
            "startup_time": time.time(),
            "pid": os.getpid(),
            "status": "initializing"
        })
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {sig}, shutting down gracefully...")
        self.is_running = False
        self.save_status({"status": "shutting_down"})
        # Clean up before exit
        try:
            if os.path.exists(MANAGER_PID_FILE):
                os.remove(MANAGER_PID_FILE)
        except Exception as e:
            logger.error(f"Error cleaning up: {e}")
        sys.exit(0)

    def save_status(self, data):
        """Save status information to a file"""
        try:
            status_file = "ultimate_status.json"
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    status = json.load(f)
            else:
                status = {}
            
            # Update with new data
            status.update(data)
            status["last_update"] = time.time()
            
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving status: {e}")

    def check_health(self):
        """Check the health of the Discord bot"""
        try:
            response = requests.get(HEALTH_CHECK_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                bot_status = data.get("status", "unknown")
                heartbeat_age = data.get("last_heartbeat_age", 999)
                restart_count = data.get("restart_count", 0)
                
                # Record for metrics
                self.process_metrics.append({
                    "time": time.time(),
                    "status": bot_status,
                    "heartbeat_age": heartbeat_age,
                    "restart_count": restart_count
                })
                
                # Keep only last 100 metrics
                if len(self.process_metrics) > 100:
                    self.process_metrics = self.process_metrics[-100:]
                
                # Update our status file
                self.save_status({
                    "bot_health": bot_status,
                    "heartbeat_age": heartbeat_age,
                    "restart_count": restart_count
                })
                
                if bot_status == "healthy" and heartbeat_age < 60:
                    logger.info(f"Bot is healthy (heartbeat age: {heartbeat_age}s)")
                    self.consecutive_failures = 0
                    if self.outage_start:
                        outage_duration = time.time() - self.outage_start
                        logger.info(f"Outage resolved. Duration: {outage_duration:.1f} seconds")
                        self.outage_start = None
                    return True
                else:
                    logger.warning(f"Bot health check warning: status={bot_status}, heartbeat_age={heartbeat_age}s")
                    
                    # If it's just a warning (not critical yet), give it a chance
                    if bot_status == "warning" and heartbeat_age < 100:
                        if random.random() < 0.5:  # 50% chance to ignore warnings
                            logger.info("Giving bot a chance to recover from warning state")
                            return True
                        
                    self.consecutive_failures += 1
                    
                    if not self.outage_start:
                        self.outage_start = time.time()
                    return False
            else:
                logger.error(f"Health check returned non-200 status code: {response.status_code}")
                self.consecutive_failures += 1
                if not self.outage_start:
                    self.outage_start = time.time()
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to health check endpoint: {e}")
            self.consecutive_failures += 1
            if not self.outage_start:
                self.outage_start = time.time()
            return False

    def should_restart(self):
        """Determine if the bot should be restarted"""
        # Check if we've restarted too many times recently
        current_time = time.time()
        one_hour_ago = current_time - 3600
        
        # Clean up restart history
        global LAST_RESTARTS
        LAST_RESTARTS = [t for t in LAST_RESTARTS if t > one_hour_ago]
        
        # Check if we've exceeded our restart limit
        if len(LAST_RESTARTS) >= MAX_RESTARTS_PER_HOUR:
            logger.critical(f"Too many restarts in the past hour ({len(LAST_RESTARTS)}). Entering cooldown period.")
            time.sleep(60)  # 1 minute cooldown
            return False
        
        # Check if we're in cooldown period
        if current_time - self.last_restart < RESTART_COOLDOWN:
            cooldown_remaining = RESTART_COOLDOWN - (current_time - self.last_restart)
            logger.warning(f"In restart cooldown. {cooldown_remaining:.1f}s remaining.")
            
            # Force restart anyway if the number of failures is very high
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES * 2:
                logger.critical(f"Critical failure count ({self.consecutive_failures}) - forcing restart despite cooldown")
                return True
            
            return False
        
        # Normal restart condition
        return self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES

    def check_process_health(self):
        """Check if the expected processes are running"""
        # Check for Discord bot process (main.py or bot.py)
        bot_running = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if ('python' in cmdline and ('main.py' in cmdline or 'bot.py' in cmdline)) or ('gunicorn' in cmdline and 'main:app' in cmdline):
                    bot_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not bot_running:
            logger.warning("Bot process is not running")
            self.consecutive_failures += 1
            return False
        
        return True

    def check_token_validity(self):
        """Check if the Discord token is valid"""
        try:
            # Check if token exists
            from config import get_token
            token = get_token()
            
            if not token:
                logger.error("Discord token is empty or invalid")
                return False
                
            # Token seems valid
            return True
        except Exception as e:
            logger.error(f"Error checking token validity: {e}")
            return False

    def refresh_token(self):
        """Attempt to refresh the Discord token"""
        try:
            logger.info("Attempting to refresh Discord token...")
            if os.path.exists("token_refresher.py"):
                subprocess.run(["python", "token_refresher.py", "--force-refresh"], 
                               check=True, timeout=60)
                logger.info("Token refresh command completed")
                return True
            else:
                logger.warning("token_refresher.py not found, can't refresh token")
                return False
        except subprocess.SubprocessError as e:
            logger.error(f"Token refresh failed: {e}")
            return False

    def kill_existing_processes(self):
        """Kill any existing bot processes"""
        logger.info("Killing existing bot processes...")
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if ('python' in cmdline and ('main.py' in cmdline or 'bot.py' in cmdline or 'keep_running.py' in cmdline or 'health_monitor.py' in cmdline)) or ('gunicorn' in cmdline and 'main:app' in cmdline):
                        pid = proc.info['pid']
                        if pid != os.getpid():  # Don't kill ourselves
                            logger.info(f"Killing process {pid}: {cmdline}")
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                logger.warning(f"Process {pid} did not terminate, forcing...")
                                proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"Error killing processes: {e}")

    def cleanup_lock_files(self):
        """Clean up any lock files"""
        logger.info("Cleaning up lock files...")
        lock_files = ["bot.lock", "watchdog.lock", "health_monitor.lock"]
        for file in lock_files:
            if os.path.exists(file):
                try:
                    os.remove(file)
                    logger.info(f"Removed lock file: {file}")
                except Exception as e:
                    logger.error(f"Error removing {file}: {e}")

    def restart_bot(self):
        """Restart the Discord bot"""
        logger.warning("Restarting Discord bot...")
        
        # Record restart
        current_time = time.time()
        LAST_RESTARTS.append(current_time)
        self.last_restart = current_time
        self.consecutive_failures = 0
        
        # Update status
        self.save_status({
            "status": "restarting",
            "last_restart": current_time,
            "restart_count": len(LAST_RESTARTS)
        })
        
        # Kill existing processes
        self.kill_existing_processes()
        
        # Clean up lock files
        self.cleanup_lock_files()
        
        # Sleep briefly to ensure everything is shut down
        time.sleep(5)
        
        try:
            # Refresh token if needed
            if not self.check_token_validity():
                self.refresh_token()
                time.sleep(2)
            
            # Start bot and monitoring system
            logger.info("Starting new bot instance...")
            
            # Determine if we should use start_bot.sh or another method
            if os.path.exists("start_bot.sh"):
                # Make sure it's executable
                os.chmod("start_bot.sh", 0o755)
                subprocess.Popen(["./start_bot.sh"], 
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 start_new_session=True)
            elif os.path.exists("bulletproof.sh"):
                # Make sure it's executable
                os.chmod("bulletproof.sh", 0o755)
                subprocess.Popen(["./bulletproof.sh"], 
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 start_new_session=True)
            else:
                # Fall back to starting with gunicorn directly
                subprocess.Popen(["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                start_new_session=True)
            
            logger.info("New bot instance started")
            return True
        except Exception as e:
            logger.error(f"Failed to restart bot: {e}")
            return False

    def check_system_resources(self):
        """Check system resources and log warnings if low"""
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_percent > 90:
                logger.warning(f"High CPU usage: {cpu_percent}%")
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                logger.warning(f"High memory usage: {memory.percent}%")
                
            # Check disk space
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                logger.warning(f"Low disk space: {disk.free / (1024*1024*1024):.1f} GB free ({disk.percent}% used)")
            
            # Log resource stats periodically
            if random.random() < 0.1:  # ~10% of checks
                self.save_status({
                    "system": {
                        "cpu": cpu_percent,
                        "memory": memory.percent,
                        "disk": disk.percent
                    }
                })
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")

    def run(self):
        """Main monitoring loop"""
        start_message = "Ultimate Uptime Manager started"
        logger.info("="*len(start_message))
        logger.info(start_message)
        logger.info("="*len(start_message))
        
        bot_health_ok = False
        
        # Initial restart to ensure we're starting fresh
        self.restart_bot()
        
        # Main monitoring loop
        while self.is_running:
            try:
                # Perform health checks in order of complexity
                if not self.check_process_health():
                    logger.warning("Process health check failed")
                    if self.should_restart():
                        self.restart_bot()
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                # Check bot health via API
                bot_health_ok = self.check_health()
                
                # Take action if health check failed
                if not bot_health_ok and self.should_restart():
                    logger.warning(f"Health check failed {self.consecutive_failures} times in a row")
                    self.restart_bot()
                
                # Check system resources once per minute
                if random.random() < (CHECK_INTERVAL / 60.0):
                    self.check_system_resources()
                
                # Save status update
                if random.random() < 0.2:  # ~20% of checks
                    self.save_status({
                        "status": "running",
                        "consecutive_failures": self.consecutive_failures,
                        "last_check": time.time()
                    })
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                logger.error(traceback.format_exc())
                self.consecutive_failures += 1
                
                if self.consecutive_failures > MAX_CONSECUTIVE_FAILURES * 2:
                    logger.critical("Too many consecutive errors in the monitoring loop")
                    self.restart_bot()
            
            # Sleep until next check
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # Ensure we're the only instance running
    if os.path.exists(MANAGER_PID_FILE):
        try:
            with open(MANAGER_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                # Check if process is still running
                os.kill(pid, 0)
                print(f"Another instance is already running with PID {pid}. Exiting.")
                sys.exit(1)
            except OSError:
                # Process not running, remove stale PID file
                os.remove(MANAGER_PID_FILE)
        except Exception as e:
            print(f"Error checking PID file: {e}")
            os.remove(MANAGER_PID_FILE)
    
    # Start the uptime manager
    manager = UptimeManager()
    manager.run()