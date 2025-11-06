#!/usr/bin/env python3
"""
Authentication Error Checker
This script checks for authentication errors in the log files and starts 
the token_refresher.py script if needed.

It's meant to be run periodically by bulletproof.sh.
"""

import os
import re
import sys
import time
import logging
import subprocess
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("auth_checker.log")
    ]
)
logger = logging.getLogger("auth_checker")

# Authentication error patterns
AUTH_ERROR_PATTERNS = [
    r"401 Unauthorized",
    r"Improper token has been passed",
    r"discord\.errors\.LoginFailure",
    r"Authentication failed",
    r"Invalid token",
    r"Token authentication failed"
]

# Log files to check
LOG_FILES = [
    "bot_errors.log",
    "bot.log",
    "logs/gunicorn.log",
    "token_refresher.log",
    "auto_401_recovery.log",
    "ultimate_recovery.log"
]

def check_for_auth_failures():
    """Check log files for recent authentication failures"""
    auth_failures = []
    
    for log_file in LOG_FILES:
        if not os.path.exists(log_file):
            continue
            
        try:
            # Get the file modification time
            mtime = os.path.getmtime(log_file)
            file_age_minutes = (time.time() - mtime) / 60
            
            # Only check files that have been modified in the last 10 minutes
            if file_age_minutes > 10:
                continue
                
            # Read the last 200 lines of the log file
            try:
                result = subprocess.run(
                    ["tail", "-200", log_file],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                log_content = result.stdout
            except:
                # If tail fails, try to read the file directly
                with open(log_file, 'r') as f:
                    log_content = ''.join(f.readlines()[-200:])
            
            # Check for auth error patterns
            for pattern in AUTH_ERROR_PATTERNS:
                matches = re.findall(pattern, log_content)
                if matches:
                    auth_failures.append(f"Found {len(matches)} auth errors in {log_file}: {pattern}")
        except Exception as e:
            logger.error(f"Error checking {log_file}: {e}")
    
    return auth_failures

def is_refresher_running():
    """Check if token_refresher.py is already running"""
    try:
        result = subprocess.run(
            ["ps", "-ef"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Look for token_refresher.py in the process list
        if "token_refresher.py" in result.stdout:
            logger.info("Token refresher is already running")
            return True
    except Exception as e:
        logger.error(f"Error checking if refresher is running: {e}")
    
    return False

def start_401_recovery():
    """Start the 401 recovery system"""
    logger.critical("Auth failures detected! Starting 401_recovery_control.sh")
    
    try:
        # Check if the script exists and is executable
        if os.path.exists("401_recovery_control.sh") and os.access("401_recovery_control.sh", os.X_OK):
            # Run the recovery script
            subprocess.Popen(
                ["bash", "401_recovery_control.sh"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            logger.info("401_recovery_control.sh started successfully")
            return True
        else:
            logger.error("401_recovery_control.sh not found or not executable")
    except Exception as e:
        logger.error(f"Error starting recovery control: {e}")
    
    return False

def start_token_refresher():
    """Start the token refresher process"""
    logger.info("Starting token_refresher.py")
    
    try:
        # Check if the script exists
        if os.path.exists("token_refresher.py"):
            # Run the token refresher with force flag
            subprocess.Popen(
                ["python", "token_refresher.py", "--force"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            logger.info("Token refresher started successfully")
            return True
        else:
            logger.error("token_refresher.py not found")
    except Exception as e:
        logger.error(f"Error starting token refresher: {e}")
    
    return False

# Main execution
if __name__ == "__main__":
    logger.info("Checking for authentication failures")
    
    # Check for auth failures
    auth_failures = check_for_auth_failures()
    
    if auth_failures:
        for failure in auth_failures:
            logger.warning(failure)
        
        # Check if refresher is already running
        if not is_refresher_running():
            # Try to start the token refresher first (lighter weight)
            if not start_token_refresher():
                # If that fails, try the full recovery system
                start_401_recovery()
        else:
            logger.info("Token refresher already running, nothing to do")
    else:
        logger.info("No authentication failures found")
        
    logger.info("Auth checker completed")