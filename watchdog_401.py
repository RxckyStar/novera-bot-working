#!/usr/bin/env python3
"""
Watchdog script for auto_401_recovery.py
This script monitors auto_401_recovery.py and restarts it if it's not running.
It's designed to be run as a cron job or via a continuous process.
"""

import os
import time
import sys
import subprocess
import psutil
import logging
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("watchdog_401.log")
    ]
)
logger = logging.getLogger("watchdog_401")

RECOVERY_SCRIPT = "auto_401_recovery.py"
PID_FILE = "auto_401_recovery.pid"
CHECK_INTERVAL = 60  # Check every minute


def is_recovery_running():
    """Check if auto_401_recovery.py is running"""
    # Method 1: Check PID file
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
                try:
                    # Check if process with this PID exists
                    proc = psutil.Process(pid)
                    cmdline = " ".join(proc.cmdline())
                    # Verify it's actually the auto_401_recovery.py process
                    if RECOVERY_SCRIPT in cmdline:
                        logger.info(f"Found {RECOVERY_SCRIPT} running with PID {pid}")
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    logger.warning(f"PID {pid} from {PID_FILE} is not running or not accessible")
        except (ValueError, OSError) as e:
            logger.error(f"Error reading PID file: {e}")
    
    # Method 2: Look for the process directly
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
            if RECOVERY_SCRIPT in cmdline:
                logger.info(f"Found {RECOVERY_SCRIPT} running with PID {proc.info['pid']}")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    logger.warning(f"{RECOVERY_SCRIPT} is not running")
    return False


def start_recovery():
    """Start the auto_401_recovery.py script"""
    logger.info(f"Starting {RECOVERY_SCRIPT}")
    try:
        # Use nohup and redirect output to avoid the process being terminated
        # when the parent process (this watchdog) exits
        subprocess.Popen(
            ["nohup", "python", RECOVERY_SCRIPT],
            stdout=open("auto_401_recovery.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        logger.info(f"Started {RECOVERY_SCRIPT}")
        return True
    except Exception as e:
        logger.error(f"Error starting {RECOVERY_SCRIPT}: {e}")
        return False


def clean_stale_files():
    """Clean up stale PID and lock files"""
    stale_files = []
    
    # Check if PID file is stale
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
                try:
                    # Check if process with this PID exists
                    proc = psutil.Process(pid)
                    cmdline = " ".join(proc.cmdline())
                    # If it exists but is not the auto_401_recovery.py process, the file is stale
                    if RECOVERY_SCRIPT not in cmdline:
                        stale_files.append(PID_FILE)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process doesn't exist, so file is stale
                    stale_files.append(PID_FILE)
        except (ValueError, OSError):
            # Invalid PID in the file, so it's stale
            stale_files.append(PID_FILE)
    
    # Check for 401 recovery lock file
    recovery_lock = "401_recovery_startup.lock"
    if os.path.exists(recovery_lock):
        try:
            with open(recovery_lock, 'r') as f:
                try:
                    pid = int(f.read().strip())
                    try:
                        # Check if process with this PID exists
                        proc = psutil.Process(pid)
                        cmdline = " ".join(proc.cmdline())
                        # If it exists but is not the auto_401_recovery.py process, the file is stale
                        if RECOVERY_SCRIPT not in cmdline:
                            stale_files.append(recovery_lock)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process doesn't exist, so file is stale
                        stale_files.append(recovery_lock)
                except (ValueError, OSError):
                    # Invalid PID in the file, so it's stale
                    stale_files.append(recovery_lock)
        except (ValueError, OSError):
            # Invalid data in the file, so it's stale
            stale_files.append(recovery_lock)
    
    # Remove stale files
    for file in stale_files:
        try:
            os.remove(file)
            logger.info(f"Removed stale file: {file}")
        except OSError as e:
            logger.error(f"Error removing stale file {file}: {e}")


def main():
    """Main watchdog loop"""
    logger.info("Starting auto_401_recovery.py watchdog")
    
    while True:
        try:
            # Clean up stale PID and lock files
            clean_stale_files()
            
            # Check if auto_401_recovery.py is running
            if not is_recovery_running():
                logger.warning(f"{RECOVERY_SCRIPT} is not running, starting it")
                start_recovery()
            
            # Wait for next check
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Error in watchdog loop: {e}")
            time.sleep(10)  # Sleep briefly and try again


if __name__ == "__main__":
    # Check if this script is already running (only one instance allowed)
    this_script = os.path.basename(__file__)
    count = 0
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
            if this_script in cmdline and proc.info['pid'] != os.getpid():
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if count > 0:
        logger.warning(f"Another instance of {this_script} is already running. Exiting.")
        sys.exit(1)
    
    # Start the watchdog
    main()