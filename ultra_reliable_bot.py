#!/usr/bin/env python3
"""
Ultra Reliable Bot - Never Crashes, Always Restarts

This script is designed to ensure your Discord bot runs indefinitely without 
ever staying down. It includes sophisticated monitoring, auto-restart capabilities,
and handles all common error conditions with built-in recovery mechanisms.
"""

import os
import sys
import time
import signal
import atexit
import logging
import requests
import subprocess
import psutil
from datetime import datetime, timedelta
import threading

# Configure logging for this monitor
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ultra_reliable_bot.log")
    ]
)
logger = logging.getLogger("ultra_reliable_bot")

# Configuration
CHECK_INTERVAL = 10  # seconds between checks
BOT_CHECK_URL = "http://127.0.0.1:5000/healthz"  # Main health endpoint
BOT_SCRIPT_PATH = "bot.py"
MAX_MEMORY_MB = 500  # Restart if memory usage exceeds this
RESTART_COOLDOWN = 30  # seconds between restart attempts
TOKEN_ERROR_PATTERNS = ["401", "unauthorized", "Authentication failed", "invalid token"]
CONNECTION_ERROR_PATTERNS = ["Failed to connect", "Connection refused", "Cannot connect", "timed out"]
CRITICAL_ERROR_PATTERNS = ["critical", "exception", "error", "fatal", "failed"]

# Global state
last_restart_time = None
monitor_start_time = datetime.now()
restart_count = 0
health_check_count = 0
last_error = None

def is_process_running(name):
    """Check if a process with the given name is running"""
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        if process.info['cmdline']:
            cmd = ' '.join(process.info['cmdline'])
            if name in cmd:
                return True
    return False

def kill_bot_processes():
    """Safely kill bot processes"""
    logger.info("Killing existing bot processes")
    killed_count = 0
    
    # First, try to kill just the bot process
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = process.info['cmdline']
            if cmdline and BOT_SCRIPT_PATH in ' '.join(cmdline):
                logger.info(f"Killing bot process with PID {process.pid}")
                process.terminate()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Give processes time to terminate gracefully
    if killed_count > 0:
        time.sleep(2)
    
    # Force kill any remaining processes
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = process.info['cmdline']
            if cmdline and BOT_SCRIPT_PATH in ' '.join(cmdline):
                logger.warning(f"Force killing bot process with PID {process.pid}")
                process.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    return killed_count

def check_bot_health():
    """Check if the bot is healthy by making a request to its health endpoint"""
    global health_check_count, last_error
    
    health_check_count += 1
    try:
        response = requests.get(BOT_CHECK_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'unknown')
            bot_connected = data.get('bot_connected', False)
            
            # Check both status and bot connection
            if status in ['healthy', 'warning'] and bot_connected:
                # Periodic status logging
                if health_check_count % 10 == 0:
                    logger.info(f"Bot health check successful: status={status}, bot_connected={bot_connected}")
                return True, None
            else:
                error_msg = f"Bot health check failed: status={status}, bot_connected={bot_connected}"
                logger.warning(error_msg)
                last_error = error_msg
                return False, error_msg
        else:
            error_msg = f"Bot health check failed with status code {response.status_code}"
            logger.warning(error_msg)
            last_error = error_msg
            return False, error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Bot health check request failed: {str(e)}"
        logger.warning(error_msg)
        last_error = error_msg
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error in bot health check: {str(e)}"
        logger.error(error_msg)
        last_error = error_msg
        return False, error_msg

def check_memory_usage():
    """Check if any bot processes are using too much memory"""
    for process in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
        try:
            cmdline = process.info['cmdline']
            if cmdline and BOT_SCRIPT_PATH in ' '.join(cmdline):
                # Convert to MB for easy comparison
                memory_mb = process.info['memory_info'].rss / (1024 * 1024)
                if memory_mb > MAX_MEMORY_MB:
                    logger.warning(f"Bot process with PID {process.pid} using {memory_mb:.2f} MB of memory, exceeding limit of {MAX_MEMORY_MB} MB")
                    return False, f"Memory usage too high: {memory_mb:.2f} MB"
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return True, None

def check_log_for_errors():
    """Check log files for recent errors"""
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
                            
                            # Check for token errors
                            for pattern in TOKEN_ERROR_PATTERNS:
                                if pattern.lower() in line_lower:
                                    logger.warning(f"Token error detected in {error_file}: {line.strip()}")
                                    recent_errors.append(("token", line.strip()))
                            
                            # Check for connection errors
                            for pattern in CONNECTION_ERROR_PATTERNS:
                                if pattern.lower() in line_lower:
                                    logger.warning(f"Connection error detected in {error_file}: {line.strip()}")
                                    recent_errors.append(("connection", line.strip()))
                            
                            # Check for critical errors
                            for pattern in CRITICAL_ERROR_PATTERNS:
                                if pattern.lower() in line_lower:
                                    logger.warning(f"Critical error detected in {error_file}: {line.strip()}")
                                    recent_errors.append(("critical", line.strip()))
            except Exception as e:
                logger.error(f"Error reading log file {error_file}: {str(e)}")
    
    # Return True if no errors, False with error info if errors found
    if recent_errors:
        # Extract just the error types
        error_types = set()
        for error_type, _ in recent_errors:
            error_types.add(error_type)
        
        error_msg = f"Found recent errors in logs: {', '.join(error_types)}"
        return False, error_msg
    return True, None

def should_restart_bot():
    """Determine if the bot should be restarted based on various checks"""
    global last_error
    
    # Check if bot process is running
    if not is_process_running(BOT_SCRIPT_PATH):
        last_error = "Bot process not found"
        logger.warning("Bot process not running, restarting...")
        return True
    
    # Check bot health
    is_healthy, health_error = check_bot_health()
    if not is_healthy:
        return True
    
    # Check memory usage
    memory_ok, memory_error = check_memory_usage()
    if not memory_ok:
        last_error = memory_error
        return True
    
    # Check log files for errors
    logs_ok, log_error = check_log_for_errors()
    if not logs_ok:
        last_error = log_error
        # We don't need to iterate through the error message
        # Just return True if it's serious enough to warrant a restart
        return True
    
    return False

def start_bot():
    """Start the Discord bot"""
    global last_restart_time, restart_count
    
    # Update restart metadata
    last_restart_time = datetime.now()
    restart_count += 1
    
    # Kill any existing bot processes
    kill_bot_processes()
    
    # Wait for processes to fully terminate
    time.sleep(2)
    
    # Launch the bot in a new process
    logger.info(f"Starting bot (restart #{restart_count})...")
    try:
        # Use subprocess to run the bot in a new process
        subprocess.Popen(
            [sys.executable, BOT_SCRIPT_PATH], 
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        logger.info("Bot process started successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        return False

def can_restart():
    """Check if we can restart the bot (respect cooldown period)"""
    if last_restart_time is None:
        return True
    
    elapsed = (datetime.now() - last_restart_time).total_seconds()
    return elapsed >= RESTART_COOLDOWN

def save_status():
    """Save the current status to a file for monitoring"""
    status = {
        "start_time": monitor_start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": (datetime.now() - monitor_start_time).total_seconds(),
        "restart_count": restart_count,
        "health_check_count": health_check_count,
        "last_restart": last_restart_time.strftime("%Y-%m-%d %H:%M:%S") if last_restart_time else None,
        "last_error": last_error,
        "status": "running",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        import json
        with open("ultra_reliable_status.json", "w") as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save status: {str(e)}")

def cleanup():
    """Perform cleanup on exit"""
    logger.info("Ultra Reliable Bot monitor shutting down")
    save_status()

def signal_handler(sig, frame):
    """Handle signals gracefully"""
    logger.info(f"Received signal {sig}, shutting down...")
    cleanup()
    sys.exit(0)

def run():
    """Main monitoring loop"""
    logger.info("Starting Ultra Reliable Bot monitor")
    
    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # First, check if the bot is already running
    if not is_process_running(BOT_SCRIPT_PATH):
        logger.info("Bot not running on startup, starting it...")
        start_bot()
    else:
        logger.info("Bot already running on startup")
    
    # Main monitoring loop
    try:
        while True:
            # Periodically save status
            if health_check_count % 10 == 0:
                save_status()
            
            # Check if the bot needs to be restarted
            if should_restart_bot():
                if can_restart():
                    logger.warning(f"Bot needs to be restarted. Last error: {last_error}")
                    start_bot()
                else:
                    elapsed = (datetime.now() - last_restart_time).total_seconds() if last_restart_time else 0
                    logger.info(f"In restart cooldown period ({elapsed:.1f}s / {RESTART_COOLDOWN}s)")
            
            # Sleep until next check
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
    except Exception as e:
        logger.critical(f"Monitor crashed: {str(e)}", exc_info=True)
        raise
    finally:
        cleanup()

if __name__ == "__main__":
    run()