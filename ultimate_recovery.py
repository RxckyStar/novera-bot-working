#!/usr/bin/env python3
"""
ULTIMATE RECOVERY SYSTEM
------------------------
This is the final boss of recovery scripts. It aggressively monitors and restarts
the bot with zero tolerance for downtime.

Features:
- Monitors bot health every 10 seconds
- Checks Discord connectivity directly
- Force kills and restarts on ANY sign of trouble
- Ignores cooldowns and retry limits - NEVER gives up
- Multiple parallel recovery mechanisms
- Self-healing capabilities
"""

import os
import sys
import time
import signal
import logging
import requests
import subprocess
import threading
import json
import random
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [ULTIMATE] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ultimate_recovery.log")
    ]
)
logger = logging.getLogger("ultimate_recovery")

# Constants - ULTRA AGGRESSIVE SETTINGS
HEALTH_CHECK_INTERVAL = 10  # Check every 10 seconds
RECONNECT_WAIT = 3  # Wait only 3 seconds between restart attempts
NO_COOLDOWN = True  # Disable all cooldowns
HEALTH_CHECK_ENDPOINTS = [
    "http://127.0.0.1:5001/",
    "http://127.0.0.1:5001/healthz",
    "http://127.0.0.1:5000/",
    "http://127.0.0.1:5000/healthz",
    "http://0.0.0.0:5001/",
    "http://0.0.0.0:5000/"
]
LOG_FILES = [
    "bot_errors.log",
    "bot.log",
    "auto_401_recovery.log",
    "token_refresher.log"
]
RECOVERY_SCRIPTS = [
    "python bot.py",
    "python main.py",
    "bash bulletproof.sh",
    "bash super_recovery.sh",
    "bash never_down.sh"
]
DISCORD_GATEWAY_URL = "https://discord.com/api/v10/gateway"
PID_FILE = "ultimate_recovery.pid"

class UltimateRecovery:
    def __init__(self):
        self.start_time = time.time()
        self.last_restart_time = 0
        self.restart_count = 0
        self.recovery_active = False
        
        # Create PID file
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        logger.info(f"🔥 ULTIMATE RECOVERY SYSTEM ACTIVATED 🔥 (PID: {os.getpid()})")

    def is_discord_accessible(self):
        """Check if Discord API is accessible"""
        try:
            response = requests.get(DISCORD_GATEWAY_URL, timeout=5)
            return response.status_code == 200
        except:
            return False

    def is_bot_healthy(self):
        """Check if the bot is healthy via multiple methods"""
        # Method 1: Check health endpoints
        endpoint_healthy = False
        for endpoint in HEALTH_CHECK_ENDPOINTS:
            try:
                response = requests.get(endpoint, timeout=3)
                if response.status_code == 200:
                    logger.info(f"Bot is responding on {endpoint}")
                    endpoint_healthy = True
                    break
            except:
                pass
        
        # Method 2: Check running processes
        process_healthy = False
        try:
            result = subprocess.run(
                ["ps", "-ef"], 
                capture_output=True,
                text=True
            )
            output = result.stdout.lower()
            if "bot.py" in output or "main.py" in output:
                logger.info("Bot process is running")
                process_healthy = True
        except:
            pass
        
        # Method 3: Check log files for recent activity
        logs_healthy = False
        for log_file in LOG_FILES:
            if not os.path.exists(log_file):
                continue
            try:
                # Check if log file has been modified in the last 2 minutes
                mtime = os.path.getmtime(log_file)
                if time.time() - mtime < 120:
                    logger.info(f"Recent activity in {log_file}")
                    logs_healthy = True
                    break
            except:
                pass
        
        # Need 2 out of 3 checks to pass
        health_score = sum([endpoint_healthy, process_healthy, logs_healthy])
        logger.info(f"Health score: {health_score}/3")
        return health_score >= 2

    def check_for_auth_errors(self):
        """Check logs for authentication errors"""
        for log_file in LOG_FILES:
            if not os.path.exists(log_file):
                continue
            try:
                # Only check recent log entries (last 50 lines)
                result = subprocess.run(
                    ["tail", "-50", log_file],
                    capture_output=True,
                    text=True
                )
                log_content = result.stdout.lower()
                
                # Check for auth error indicators
                auth_error_terms = [
                    "401", "unauthorized", "improper token", "invalid token",
                    "authentication failed", "login failure"
                ]
                
                for term in auth_error_terms:
                    if term in log_content:
                        logger.warning(f"Auth error found in {log_file}: {term}")
                        return True
            except Exception as e:
                logger.error(f"Error checking {log_file}: {e}")
        
        return False

    def force_token_refresh(self):
        """Force refresh of the Discord token using multiple methods"""
        logger.critical("🔄 FORCE REFRESHING TOKEN 🔄")
        
        # Method 1: Execute token_refresher.py if it exists
        if os.path.exists("token_refresher.py"):
            try:
                logger.info("Running token_refresher.py with --force")
                subprocess.run(["python", "token_refresher.py", "--force"], timeout=30)
            except Exception as e:
                logger.error(f"Error running token_refresher.py: {e}")
        
        # Method 2: Clear token caches
        token_caches = ["token_cache.json", ".token_cache", "discord_token.cache"]
        for cache in token_caches:
            if os.path.exists(cache):
                try:
                    logger.info(f"Removing token cache: {cache}")
                    os.remove(cache)
                except Exception as e:
                    logger.error(f"Error removing cache {cache}: {e}")
        
        # Method 3: Create token refresh signal file
        try:
            with open("refresh_token", "w") as f:
                f.write(str(time.time()))
            logger.info("Created refresh_token signal file")
        except Exception as e:
            logger.error(f"Error creating refresh_token file: {e}")

    def kill_all_bot_processes(self):
        """Brutally kill all bot-related processes"""
        logger.warning("⚡ KILLING ALL BOT PROCESSES ⚡")
        
        # Method 1: Kill by process name
        process_names = ["bot.py", "main.py", "gunicorn"]
        for name in process_names:
            try:
                logger.info(f"Killing processes matching: {name}")
                subprocess.run(["pkill", "-f", name], timeout=5)
            except Exception as e:
                logger.error(f"Error killing {name} processes: {e}")
        
        # Method 2: Run kill_processes.py if it exists
        if os.path.exists("kill_processes.py"):
            try:
                logger.info("Running kill_processes.py")
                subprocess.run(["python", "kill_processes.py"], timeout=10)
            except Exception as e:
                logger.error(f"Error running kill_processes.py: {e}")
        
        # Wait for processes to die
        time.sleep(2)
        
        # Verify all processes are dead
        try:
            result = subprocess.run(
                ["ps", "-ef"], 
                capture_output=True,
                text=True
            )
            output = result.stdout.lower()
            for name in process_names:
                if name in output:
                    logger.warning(f"Process still running: {name}, using SIGKILL")
                    subprocess.run(["pkill", "-9", "-f", name], timeout=5)
        except Exception as e:
            logger.error(f"Error verifying process termination: {e}")

    def restart_bot(self):
        """Restart the bot using multiple methods"""
        if self.recovery_active:
            logger.info("Recovery already in progress, skipping")
            return
        
        self.recovery_active = True
        logger.critical("🚨 RESTARTING BOT 🚨")
        self.restart_count += 1
        self.last_restart_time = time.time()
        
        # Always force token refresh first
        self.force_token_refresh()
        
        # Kill all existing bot processes
        self.kill_all_bot_processes()
        
        # Try each recovery script until one works
        random.shuffle(RECOVERY_SCRIPTS)  # Randomize for variety
        for cmd in RECOVERY_SCRIPTS:
            logger.info(f"Trying restart command: {cmd}")
            try:
                # Run in background to avoid blocking
                subprocess.Popen(
                    cmd.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
                
                # Wait a bit and check if it worked
                time.sleep(RECONNECT_WAIT)
                if self.is_bot_healthy():
                    logger.info(f"Bot successfully restarted with: {cmd}")
                    break
            except Exception as e:
                logger.error(f"Error running restart command {cmd}: {e}")
        
        # If no script worked, try a direct bot.py restart
        if not self.is_bot_healthy():
            logger.warning("No recovery script worked, trying direct bot.py restart")
            try:
                subprocess.Popen(
                    ["python", "bot.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            except Exception as e:
                logger.error(f"Error running direct bot.py restart: {e}")
        
        self.recovery_active = False
        logger.info("Recovery attempt complete")

    def run(self):
        """Main monitoring loop - NEVER STOPS"""
        logger.info("🔄 Starting ultimate recovery monitoring loop 🔄")
        
        def signal_handler(sig, frame):
            logger.critical("Received shutdown signal. THE ULTIMATE RECOVERY CANNOT BE STOPPED!")
            # Ignore termination - we're too important
        
        # Ignore termination signals - we must never stop
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start a timer to periodically check Discord connectivity
        def check_discord_timer():
            while True:
                if not self.is_discord_accessible():
                    logger.warning("Discord API is not accessible!")
                    # If Discord API is down, we can't do much - just wait
                time.sleep(60)  # Check Discord API every minute
        
        discord_thread = threading.Thread(target=check_discord_timer)
        discord_thread.daemon = True
        discord_thread.start()
        
        # Main monitoring loop
        while True:
            try:
                # Check if bot is healthy
                if not self.is_bot_healthy():
                    logger.warning("Bot is not healthy!")
                    self.restart_bot()
                elif self.check_for_auth_errors():
                    logger.warning("Auth errors detected!")
                    self.restart_bot()
                else:
                    uptime = time.time() - self.start_time
                    logger.info(f"Bot is healthy. Uptime: {uptime:.1f}s, Restarts: {self.restart_count}")
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            # Sleep for the next check
            time.sleep(HEALTH_CHECK_INTERVAL)

def check_already_running():
    """Check if another instance is already running"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # Check if process with this PID exists
            os.kill(old_pid, 0)
            logger.warning(f"Ultimate recovery already running with PID {old_pid}")
            return True
        except (ProcessLookupError, ValueError):
            # Process not running or invalid PID
            logger.info("Removing stale PID file")
            os.remove(PID_FILE)
    return False

if __name__ == "__main__":
    if not check_already_running():
        recovery = UltimateRecovery()
        recovery.run()