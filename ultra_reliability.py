#!/usr/bin/env python3
"""
Ultra-Reliability System for Discord Bot

This comprehensive system ensures the bot never goes down by implementing:
1. Proactive monitoring with health checks
2. Auto-recovery for all error conditions
3. Aggressive restart capabilities with exponential backoff
4. Token refresh and authentication problem handling
5. Complete process management and cleanup
6. Persistent logging and status tracking

The goal: A bot that runs forever without manual intervention.
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
import signal
import atexit
import requests
import psutil
from datetime import datetime, timedelta
import traceback
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ultra_reliability.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("UltraReliability")

# Constants
BOT_SCRIPT_PATH = "bot.py"
WEB_SCRIPT_PATH = "main.py"
CHECK_INTERVAL = 30  # Seconds between health checks
RESTART_COOLDOWN_BASE = 30  # Minimum seconds between restart attempts
MAX_RESTART_COOLDOWN = 600  # Maximum backoff for restart attempts (10 minutes)
MAX_CONSECUTIVE_RESTARTS = 5  # After this many restarts, increase cooldown
COOLDOWN_MULTIPLIER = 2  # For exponential backoff
HEALTH_PORT = 5001  # Bot's health endpoint port
BOT_PID_FILE = "bot.pid"  # PID file for the bot process
WEB_PID_FILE = "web.pid"  # PID file for the web process
MAX_MEMORY_MB = 500  # Maximum allowed memory usage in MB

# Error patterns to look for in logs
TOKEN_ERROR_PATTERNS = [
    "unauthorized",
    "token",
    "cannot connect to websocket",
    "401",
    "forbidden",
    "authentication failed",
    "invalid token",
    "not authenticated"
]

CONNECTION_ERROR_PATTERNS = [
    "connection closed",
    "cannot connect",
    "connection reset",
    "disconnected",
    "websocket closed",
    "connection error",
    "failed to connect",
    "timeout",
    "timed out"
]

CRITICAL_ERROR_PATTERNS = [
    "critical error",
    "fatal",
    "exception",
    "error",
    "crashed",
    "killed",
    "terminated",
    "segmentation fault",
    "cannot import",
    "module not found"
]

# Global state tracking
start_time = datetime.now()
last_restart_time = None
last_restart_attempt_time = None
last_error = None
restart_count = 0
consecutive_restarts = 0
check_count = 0
is_shutdown = False


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""
    def signal_handler(sig, frame):
        global is_shutdown
        logger.info(f"Received signal {sig}, shutting down gracefully...")
        is_shutdown = True
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def is_process_running(pid_file):
    """Check if a process identified by a PID file is running"""
    if not os.path.exists(pid_file):
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
    except (IOError, ValueError):
        logger.error(f"Failed to read PID from {pid_file}")
        return False
    
    try:
        # Check if process exists
        process = psutil.Process(pid)
        return process.is_running()
    except psutil.NoSuchProcess:
        logger.warning(f"Process with PID {pid} not found")
        return False
    except Exception as e:
        logger.error(f"Error checking process status: {e}")
        return False


def check_bot_health():
    """Check the health of the bot via its health endpoint"""
    try:
        response = requests.get(f"http://localhost:{HEALTH_PORT}/healthz", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # Get detailed health information
            bot_connected = data.get("bot_connected", False)
            last_heartbeat_age = data.get("last_heartbeat_age", 9999)
            
            # Bot is truly healthy if it's connected and has a recent heartbeat
            if bot_connected and last_heartbeat_age < 120:
                logger.info(f"Bot is healthy: connected with heartbeat age {last_heartbeat_age}s")
                return True, None
            else:
                error_msg = f"Bot is not fully healthy: connected={bot_connected}, heartbeat_age={last_heartbeat_age}s"
                logger.warning(error_msg)
                return False, error_msg
        else:
            error_msg = f"Health check failed with status code: {response.status_code}"
            logger.warning(error_msg)
            return False, error_msg
    except requests.RequestException as e:
        error_msg = f"Error connecting to bot health endpoint: {str(e)}"
        logger.warning(error_msg)
        return False, error_msg


def check_memory_usage():
    """Check if any bot processes are using too much memory"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if BOT_SCRIPT_PATH in cmdline:
                    memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
                    if memory_mb > MAX_MEMORY_MB:
                        error_msg = f"Bot process (PID: {proc.info['pid']}) using {memory_mb:.1f}MB exceeds limit of {MAX_MEMORY_MB}MB"
                        logger.warning(error_msg)
                        return False, error_msg
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return True, None
    except Exception as e:
        logger.error(f"Error checking memory usage: {e}")
        return True, None  # Don't trigger restart on monitoring errors


def check_log_for_errors():
    """Check log files for recent critical errors"""
    error_files = ["bot_errors.log", "bot.log", "error.log"]
    recent_errors = []
    
    for error_file in error_files:
        if os.path.exists(error_file):
            try:
                # Check if the file was modified recently
                mod_time = os.path.getmtime(error_file)
                if datetime.now().timestamp() - mod_time < 300:  # Within the last 5 minutes
                    # Read the last 20 lines of the file
                    with open(error_file, 'r') as f:
                        lines = f.readlines()
                        last_lines = lines[-20:] if len(lines) > 20 else lines
                        
                        # Check for error patterns
                        for line in last_lines:
                            line_lower = line.lower()
                            
                            # Check for different error types
                            for pattern in TOKEN_ERROR_PATTERNS:
                                if pattern.lower() in line_lower:
                                    logger.warning(f"Token error detected in {error_file}: {line.strip()}")
                                    recent_errors.append(("token", line.strip()))
                            
                            for pattern in CONNECTION_ERROR_PATTERNS:
                                if pattern.lower() in line_lower:
                                    logger.warning(f"Connection error detected in {error_file}: {line.strip()}")
                                    recent_errors.append(("connection", line.strip()))
                            
                            for pattern in CRITICAL_ERROR_PATTERNS:
                                if pattern.lower() in line_lower:
                                    logger.warning(f"Critical error detected in {error_file}: {line.strip()}")
                                    recent_errors.append(("critical", line.strip()))
            except Exception as e:
                logger.error(f"Error reading log file {error_file}: {str(e)}")
    
    # Return True if no errors, False with error info if errors found
    if recent_errors:
        # Extract error types
        error_types = set()
        for error_type, _ in recent_errors:
            error_types.add(error_type)
        
        error_msg = f"Found recent errors in logs: {', '.join(error_types)}"
        return False, error_msg
    return True, None


def is_bot_running():
    """Check if the bot process is running"""
    # First check the PID file
    if is_process_running(BOT_PID_FILE):
        return True
    
    # Then do a more thorough check using process name
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if BOT_SCRIPT_PATH in cmdline:
                    logger.info(f"Found bot process: PID {proc.info['pid']}")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    except Exception as e:
        logger.error(f"Error searching for bot process: {e}")
        return False


def is_web_running():
    """Check if the web server process is running"""
    # Check the PID file first
    if is_process_running(WEB_PID_FILE):
        return True
    
    # Then do a more thorough check
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if WEB_SCRIPT_PATH in cmdline:
                    logger.info(f"Found web server process: PID {proc.info['pid']}")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    except Exception as e:
        logger.error(f"Error searching for web server process: {e}")
        return False


def kill_bot_processes():
    """Kill all bot processes"""
    try:
        # First try graceful termination
        killed_pids = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if BOT_SCRIPT_PATH in cmdline:
                    pid = proc.info['pid']
                    logger.info(f"Attempting to terminate bot process with PID {pid}")
                    psutil.Process(pid).terminate()
                    killed_pids.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # If we found and tried to kill any processes, wait a moment for them to exit
        if killed_pids:
            time.sleep(2)
            
            # Check if any are still alive and kill them forcefully
            for pid in killed_pids:
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        logger.warning(f"Process {pid} still running after terminate, sending SIGKILL")
                        process.kill()
                except psutil.NoSuchProcess:
                    logger.info(f"Process {pid} has exited")
                except Exception as e:
                    logger.error(f"Error killing process {pid}: {e}")
            
        # Clean up the PID file
        if os.path.exists(BOT_PID_FILE):
            try:
                os.remove(BOT_PID_FILE)
                logger.info(f"Removed PID file {BOT_PID_FILE}")
            except Exception as e:
                logger.error(f"Failed to remove PID file {BOT_PID_FILE}: {e}")
                
        return True
    except Exception as e:
        logger.error(f"Error killing bot processes: {e}")
        return False


def should_restart_bot():
    """Determine if the bot should be restarted based on various checks"""
    global last_error
    
    # Check if bot process is running
    if not is_bot_running():
        last_error = "Bot process not found"
        logger.warning("Bot process not running, needs restart")
        return True
    
    # Check bot health
    is_healthy, health_error = check_bot_health()
    if not is_healthy:
        last_error = health_error
        logger.warning(f"Bot health check failed: {health_error}")
        return True
    
    # Check memory usage
    memory_ok, memory_error = check_memory_usage()
    if not memory_ok:
        last_error = memory_error
        logger.warning(f"Memory check failed: {memory_error}")
        return True
    
    # Check log files for errors
    logs_ok, log_error = check_log_for_errors()
    if not logs_ok:
        last_error = log_error
        logger.warning(f"Log check failed: {log_error}")
        return True
    
    return False


def should_restart_web():
    """Determine if the web server should be restarted"""
    if not is_web_running():
        logger.warning("Web server not running, needs restart")
        return True
    
    # You can add more checks here if needed
    
    return False


def calculate_restart_cooldown():
    """Calculate the restart cooldown with exponential backoff"""
    global consecutive_restarts
    
    if consecutive_restarts <= 1:
        return RESTART_COOLDOWN_BASE
    
    # Apply exponential backoff with jitter
    cooldown = min(
        RESTART_COOLDOWN_BASE * (COOLDOWN_MULTIPLIER ** (consecutive_restarts - 1)),
        MAX_RESTART_COOLDOWN
    )
    
    # Add some randomness to prevent thundering herd problem
    jitter = random.uniform(0.8, 1.2)
    cooldown = cooldown * jitter
    
    return min(cooldown, MAX_RESTART_COOLDOWN)


def can_restart_bot():
    """Check if we can restart the bot (respect cooldown period)"""
    global last_restart_attempt_time, consecutive_restarts
    
    if last_restart_attempt_time is None:
        return True
    
    cooldown = calculate_restart_cooldown()
    elapsed = (datetime.now() - last_restart_attempt_time).total_seconds() if last_restart_attempt_time else float('inf')
    
    if elapsed >= cooldown:
        return True
    else:
        logger.info(f"In restart cooldown period: {elapsed:.1f}s / {cooldown:.1f}s")
        return False


def start_bot():
    """Start the Discord bot"""
    global last_restart_time, last_restart_attempt_time, restart_count, consecutive_restarts
    
    # Update restart metadata
    last_restart_attempt_time = datetime.now()
    restart_count += 1
    consecutive_restarts += 1
    
    # Kill any existing bot processes
    kill_bot_processes()
    
    # Wait for processes to fully terminate
    time.sleep(2)
    
    # Launch the bot in a new process
    logger.info(f"Starting bot (restart #{restart_count}, consecutive #{consecutive_restarts})...")
    try:
        # Use subprocess to run the bot in a new process
        process = subprocess.Popen(
            [sys.executable, BOT_SCRIPT_PATH], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # Wait a bit to make sure process started successfully
        time.sleep(3)
        
        if process.poll() is None:
            logger.info(f"Bot process started successfully with PID {process.pid}")
            last_restart_time = datetime.now()
            return True
        else:
            # Process exited immediately
            stdout, stderr = process.communicate()
            logger.error(f"Bot process exited immediately with code {process.returncode}")
            logger.error(f"STDOUT: {stdout.decode('utf-8', errors='ignore')}")
            logger.error(f"STDERR: {stderr.decode('utf-8', errors='ignore')}")
            return False
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        return False


def start_web_server():
    """Start the web server"""
    logger.info("Starting web server...")
    try:
        # Use subprocess to run the web server in a new process
        process = subprocess.Popen(
            [sys.executable, WEB_SCRIPT_PATH], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # Wait a bit to make sure process started successfully
        time.sleep(3)
        
        if process.poll() is None:
            logger.info(f"Web server process started successfully with PID {process.pid}")
            return True
        else:
            # Process exited immediately
            stdout, stderr = process.communicate()
            logger.error(f"Web server process exited immediately with code {process.returncode}")
            logger.error(f"STDOUT: {stdout.decode('utf-8', errors='ignore')}")
            logger.error(f"STDERR: {stderr.decode('utf-8', errors='ignore')}")
            return False
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")
        return False


def save_status():
    """Save the current status to a file for monitoring"""
    status = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": (datetime.now() - start_time).total_seconds(),
        "restart_count": restart_count,
        "consecutive_restarts": consecutive_restarts,
        "check_count": check_count,
        "last_restart": last_restart_time.strftime("%Y-%m-%d %H:%M:%S") if last_restart_time else None,
        "last_error": last_error,
        "bot_running": is_bot_running(),
        "web_running": is_web_running(),
        "status": "running",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        with open("ultra_reliability_status.json", "w") as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save status: {str(e)}")


def run():
    """Main monitoring loop"""
    global check_count, consecutive_restarts, is_shutdown
    
    logger.info("Starting Ultra-Reliability System")
    logger.info(f"Bot script: {BOT_SCRIPT_PATH}")
    logger.info(f"Web script: {WEB_SCRIPT_PATH}")
    logger.info(f"Check interval: {CHECK_INTERVAL}s")
    
    # First, check if processes are running and start them if needed
    if not is_bot_running():
        logger.info("Bot not running on startup, starting it...")
        start_bot()
    else:
        logger.info("Bot already running on startup")
    
    if not is_web_running():
        logger.info("Web server not running on startup, starting it...")
        start_web_server()
    else:
        logger.info("Web server already running on startup")
    
    # Reset consecutive restarts counter after successful startup
    if is_bot_running() and is_web_running():
        consecutive_restarts = 0
    
    # Main monitoring loop
    try:
        while not is_shutdown:
            check_count += 1
            
            # Periodically save status
            if check_count % 10 == 0:
                save_status()
            
            # Check if the bot needs to be restarted
            if should_restart_bot():
                if can_restart_bot():
                    logger.warning(f"Bot needs to be restarted. Last error: {last_error}")
                    if start_bot():
                        logger.info("Bot restart successful")
                    else:
                        logger.error("Bot restart failed")
                # No else here - can_restart_bot already logs the cooldown message
            else:
                # Reset consecutive restarts counter if bot is running well
                if check_count % 5 == 0:  # Check every 5 cycles
                    consecutive_restarts = 0
            
            # Check if the web server needs to be restarted
            if should_restart_web():
                logger.warning("Web server needs to be restarted")
                if start_web_server():
                    logger.info("Web server restart successful")
                else:
                    logger.error("Web server restart failed")
            
            # Sleep until next check
            logger.debug(f"Check #{check_count} complete, sleeping for {CHECK_INTERVAL}s")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Ultra-Reliability System stopped by user")
    except Exception as e:
        logger.critical(f"Ultra-Reliability System crashed: {str(e)}")
        logger.critical(traceback.format_exc())
    finally:
        save_status()
        logger.info("Ultra-Reliability System shutting down")


def cleanup():
    """Perform cleanup on exit"""
    global is_shutdown
    is_shutdown = True
    logger.info("Ultra-Reliability System shutting down, saving final status")
    save_status()


if __name__ == "__main__":
    # Register cleanup handler
    atexit.register(cleanup)
    
    # Set up signal handlers
    setup_signal_handlers()
    
    # Run the main monitoring loop
    run()