#!/usr/bin/env python3
"""
ULTRA-AGGRESSIVE Auto 401 Recovery Script
This script specifically watches for 401 Unauthorized errors
and automatically triggers a reset_all.py emergency restart.

It provides a relentless approach to error 401 handling,
continually checking and resetting until the issue is resolved,
with no give-up condition.
"""

import os
import sys
import time
import json
import logging
import subprocess
import re
import signal
import traceback
import psutil
import glob
from datetime import datetime, timedelta
import requests

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("auto_401_recovery.log")
    ]
)
logger = logging.getLogger("auto_401_recovery")

# Configuration - Ultra Aggressive Settings
CHECK_INTERVAL = 5  # Check every 5 seconds for maximum responsiveness
MAX_CONSECUTIVE_RESETS = 50  # Allow many more resets before cooling down
COOLDOWN_PERIOD = 60  # Cooldown after reaching max resets (60 seconds)
RESET_TRACKING_WINDOW = 3600  # 1 hour window for tracking consecutive resets
MAX_FAILED_ATTEMPTS = 999  # Virtually unlimited retries - never give up!
HEALTH_CHECK_URL = "http://127.0.0.1:5000/healthz"  # Main health endpoint on port 5000
AUTH_ERROR_PATTERNS = [
    r"discord.errors.LoginFailure",
    r"401 Unauthorized",
    r"Token authentication failed",
    r"Improper token",
    r"Invalid token",
    r"Authentication failed",
    r"token.+failed",
    r"Failed to connect to Discord",
    r"Cannot connect to Discord"
]
ERROR_LOG_FILES = [
    "bot_errors.log", 
    "bot.log",
    "logs/gunicorn.log",
    "emergency_restart.log",
    "token_refresher.log",
    "token_monitor.log",
    "watchdog.log",
    "auto_401_recovery.log"
]
PID_FILE = "auto_401_recovery.pid"
STARTUP_LOCK = "401_recovery_startup.lock"

class Auto401Recovery:
    def __init__(self):
        self.reset_timestamps = []  # Track timestamps of resets
        self.last_reset_time = 0
        self.reset_count = 0
        self.last_check_time = 0

        # Create PID file
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        logger.info(f"Auto 401 Recovery started (PID: {os.getpid()})")
    
    def check_for_auth_failures(self):
        """Check logs for authentication/401 failures"""
        auth_failures = []
        current_time = time.time()
        
        # Only check logs if enough time has passed since last check
        # This prevents excessive log reading
        if current_time - self.last_check_time < 10:  # At least 10 seconds between checks
            return []
            
        self.last_check_time = current_time
        
        for log_file in ERROR_LOG_FILES:
            if not os.path.exists(log_file):
                continue
                
            try:
                with open(log_file, 'r', errors='replace') as f:
                    try:
                        # Get file size
                        f.seek(0, 2)
                        file_size = f.tell()
                        
                        # Only read the last 20KB of large log files
                        if file_size > 20000:
                            f.seek(file_size - 20000)
                            # Skip partial line
                            f.readline()
                        else:
                            f.seek(0)
                            
                        log_content = f.read()
                        
                        # Check for auth failure patterns
                        for pattern in AUTH_ERROR_PATTERNS:
                            matches = re.finditer(pattern, log_content)
                            for match in matches:
                                # Try to extract timestamp context
                                line_start = max(0, match.start() - 100)
                                line_end = min(len(log_content), match.end() + 100)
                                context = log_content[line_start:line_end]
                                
                                # Get timestamp if possible
                                ts_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', context)
                                if ts_match:
                                    try:
                                        ts_str = ts_match.group(0)
                                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
                                        
                                        # Only if VERY recent (within 30 seconds)
                                        if current_time - ts <= 30:
                                            auth_failures.append((ts, context))
                                    except:
                                        # Skip if parsing fails - don't use current time to avoid false positives
                                        pass
                                else:
                                    # No timestamp found, skip to avoid false positives
                                    pass
                    except Exception as e:
                        logger.error(f"Error reading content from {log_file}: {e}")
            except Exception as e:
                logger.error(f"Error opening log file {log_file}: {e}")
        
        # Deduplicate failures
        unique_failures = []
        seen_contexts = set()
        
        for ts, context in auth_failures:
            # Create a signature to detect duplicates (first 20 chars + last 20 chars)
            signature = f"{context[:20]}...{context[-20:]}"
            if signature not in seen_contexts:
                seen_contexts.add(signature)
                unique_failures.append((ts, context))
        
        # Log findings
        if unique_failures:
            logger.warning(f"Found {len(unique_failures)} authentication/401 failures")
            # Log the first 3 unique failures
            for i, (ts, context) in enumerate(unique_failures[:3]):
                dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                logger.warning(f"Auth failure {i+1} at {dt}: {context[:100]}...")
        
        return unique_failures
    
    def check_bot_health(self):
        """Check if the bot is healthy via the health endpoint"""
        try:
            response = requests.get(HEALTH_CHECK_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                bot_connected = data.get("bot_connected", False)
                
                # Consider the bot healthy if either:
                # 1. Status is healthy/warning AND bot_connected is True, or
                # 2. Only status check is available (older API) and it's healthy/warning
                if bot_connected is True:
                    logger.info("Health check: Bot is connected to Discord")
                    return True
                elif (status == "healthy" or status == "warning"):
                    logger.info("Health check: Bot status is healthy/warning")
                    return True
                
                logger.warning(f"Health check: Unhealthy - status={status}, bot_connected={bot_connected}")
                return False
            
            logger.warning(f"Health check: Failed with status code {response.status_code}")
            return False
        except Exception as e:
            logger.warning(f"Health check: Exception - {str(e)}")
            return False
    
    def should_reset_bot(self):
        """Determine if we should reset the bot based on auth failures and health check"""
        # Clean up old reset timestamps outside our tracking window
        current_time = time.time()
        self.reset_timestamps = [ts for ts in self.reset_timestamps if current_time - ts <= RESET_TRACKING_WINDOW]
        
        # Check for consecutive resets
        if len(self.reset_timestamps) >= MAX_CONSECUTIVE_RESETS:
            # If we're in cooldown, don't reset
            if current_time - self.last_reset_time < COOLDOWN_PERIOD:
                logger.warning(f"In cooldown period after {len(self.reset_timestamps)} resets. Waiting.")
                return False
        
        # Check auth failures
        auth_failures = self.check_for_auth_failures()
        if len(auth_failures) >= 1:  # Even a single recent auth failure triggers reset
            logger.warning("Auth failure detected, should reset bot")
            return True
            
        # If bot is unhealthy, check logs more carefully
        if not self.check_bot_health():
            logger.warning("Bot is unhealthy, checking for 401 errors")
            # More thorough check for any auth failures
            for log_file in ERROR_LOG_FILES:
                if not os.path.exists(log_file):
                    continue
                    
                try:
                    # Use grep-like approach to scan for auth errors
                    # This is faster than reading entire files
                    result = subprocess.run(
                        ["grep", "-E", "|".join(AUTH_ERROR_PATTERNS), log_file],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        # Found auth errors
                        lines = result.stdout.strip().split('\n')
                        for line in lines[-5:]:  # Check the last 5 matches
                            # Try to extract timestamp
                            ts_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
                            if ts_match:
                                try:
                                    ts_str = ts_match.group(0)
                                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
                                    
                                    # If error is within the last 30 seconds, trigger reset
                                    if current_time - ts <= 30:
                                        logger.warning(f"Recent auth error found in {log_file}: {line[:100]}...")
                                        return True
                                except:
                                    # If parsing fails, skip it - don't assume it's recent
                                    pass
                            else:
                                # Skip entries without a timestamp to avoid false positives
                                pass
                except Exception as e:
                    logger.error(f"Error grepping {log_file}: {e}")
        
        # If we get here, no auth errors found
        return False
    
    def reset_bot(self):
        """Reset the bot using reset_all.py or fallback methods"""
        current_time = time.time()
        
        # Update tracking
        self.last_reset_time = current_time
        self.reset_timestamps.append(current_time)
        self.reset_count += 1
        
        # Log the reset
        logger.critical(f"AUTO 401 RECOVERY - Reset #{self.reset_count} initiated")
        
        try:
            # First try to trigger token refresher for a normal refresh
            try:
                with open("refresh_token", "w") as f:
                    f.write(str(current_time))
                logger.info("Signaled token_refresher to refresh token")
                
                # Wait briefly to see if normal refresh works
                time.sleep(10)
                
                # Check if bot recovered
                if self.check_bot_health():
                    logger.info("Bot recovered after token refresh signal")
                    return True
            except Exception as e:
                logger.error(f"Failed to signal token refresher: {e}")
            
            # Next, try reset_all.py for a full reset (nuclear option)
            if os.path.exists("reset_all.py"):
                logger.critical("Executing reset_all.py (nuclear reset)")
                try:
                    subprocess.run(["python", "reset_all.py"], timeout=30)
                    logger.info("reset_all.py executed")
                    time.sleep(15)  # Give it time to work
                    return True
                except Exception as e:
                    logger.error(f"Error executing reset_all.py: {e}")
            
            # Fallback: Kill processes and restart via Python
            try:
                logger.critical("Using fallback: Kill processes and restart manually")
                
                # Kill processes
                if os.path.exists("kill_processes.py"):
                    subprocess.run(["python", "kill_processes.py"], timeout=10)
                else:
                    # Fallback kill command
                    subprocess.run(["pkill", "-f", "main.py"], timeout=5)
                    subprocess.run(["pkill", "-f", "bot.py"], timeout=5)
                    subprocess.run(["pkill", "-f", "gunicorn"], timeout=5)
                
                time.sleep(5)  # Wait for processes to die
                
                # Restart using keep_running.py if available
                if os.path.exists("keep_running.py"):
                    subprocess.Popen(
                        ["python", "keep_running.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                    logger.info("Bot restarted via keep_running.py")
                    return True
                
                # Last resort: Start main.py directly
                if os.path.exists("main.py"):
                    subprocess.Popen(
                        ["python", "main.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                    logger.info("Bot restarted via main.py")
                    return True
                
                # Ultimate fallback: Gunicorn
                if os.path.exists("main.py"):
                    subprocess.Popen(
                        ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                    logger.info("Main server restarted via gunicorn on port 5000")
                    return True
                
                logger.critical("FAILED: No method available to restart the bot")
                return False
            except Exception as e:
                logger.critical(f"FAILED: Error during fallback restart: {e}")
                return False
                
        except Exception as e:
            logger.critical(f"FAILED: Reset attempt failed with error: {e}")
            logger.critical(traceback.format_exc())
            return False
    
    def force_refresh_token(self):
        """Force refresh of Discord token using all available methods"""
        logger.critical("ATTEMPTING EMERGENCY TOKEN REFRESH")
        
        # Method 0: Use token_tester (new method) if available
        try:
            if os.path.exists("token_tester.py"):
                logger.info("Using token_tester.py to verify and fix token")
                try:
                    # Run as a subprocess to avoid circular imports with config.py
                    result = subprocess.run(
                        ["python3", "-u", "token_tester.py"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    logger.info(f"token_tester.py output: {result.stdout.strip()}")
                    
                    # Check if it was successful
                    if "Token is VALID" in result.stdout or "Found and fixed token" in result.stdout:
                        logger.info("Successfully verified and fixed token with token_tester")
                        # Minimal pause to let changes take effect
                        time.sleep(2)
                        if self.check_bot_health():
                            logger.info("Bot is healthy after token_tester fix")
                            return True
                        logger.info("Bot still unhealthy after token_tester fix, trying other methods")
                except Exception as tester_err:
                    logger.error(f"Error running token_tester subprocess: {tester_err}")
        except Exception as e:
            logger.error(f"Error checking for token_tester.py: {e}")
        
        # Method 1: Signal the token_refresher.py
        try:
            with open("refresh_token", "w") as f:
                f.write(str(time.time()))
            logger.info("Signaled token_refresher to refresh token")
        except Exception as e:
            logger.error(f"Failed to signal token refresher: {e}")
            
        # Method 2: Clear any token cache files to force re-read from environment
        try:
            cache_files = ["token_cache.json", ".token_cache", "discord_token.cache"]
            for cache_file in cache_files:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    logger.info(f"Removed token cache file: {cache_file}")
        except Exception as e:
            logger.error(f"Error clearing token caches: {e}")
            
        # Method 3: Execute token_refresher.py directly if it exists
        try:
            if os.path.exists("token_refresher.py"):
                subprocess.run(["python3", "-u", "token_refresher.py", "--force"], timeout=10)
                logger.info("Executed token_refresher.py with --force flag")
        except Exception as e:
            logger.error(f"Failed to execute token_refresher.py: {e}")
            
        # Give token refresh a moment to take effect
        time.sleep(5)
        
        # Return whether the bot is now healthy
        return self.check_bot_health()
    
    def kill_all_discord_processes(self):
        """Aggressively kill all Discord-related processes"""
        logger.critical("KILLING ALL DISCORD BOT PROCESSES")
        
        try:
            # Method 1: Use kill_processes.py if available
            if os.path.exists("kill_processes.py"):
                logger.info("Executing kill_processes.py")
                subprocess.run(["python3", "-u", "kill_processes.py"], timeout=10)
            
            # Method 2: Use psutil to find and kill specific processes
            bot_process_patterns = [
                "main.py", "bot.py", "gunicorn", "keep_running.py",
                "health_monitor.py", "token_reset_monitor.py"
            ]
            
            current_pid = os.getpid()
            killed_count = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_pid = proc.info['pid']
                    cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
                    
                    # Skip our own process
                    if proc_pid == current_pid:
                        continue
                        
                    # Check if process matches any pattern
                    if any(pattern in cmdline for pattern in bot_process_patterns):
                        logger.info(f"Killing process {proc_pid}: {cmdline[:50]}...")
                        try:
                            proc.terminate()
                            proc.wait(timeout=3)
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            try:
                                proc.kill()
                            except psutil.NoSuchProcess:
                                pass
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            logger.info(f"Killed {killed_count} processes via psutil")
            
            # Method 3: Use shell commands as last resort
            shell_commands = [
                ["pkill", "-9", "-f", "main.py"],
                ["pkill", "-9", "-f", "bot.py"],
                ["pkill", "-9", "-f", "gunicorn"],
                ["pkill", "-9", "-f", "keep_running.py"]
            ]
            
            for cmd in shell_commands:
                try:
                    subprocess.run(cmd, timeout=3)
                except Exception:
                    pass
            
            # Clean up stale lock files
            lock_files = glob.glob("*.lock") + glob.glob("*.pid")
            for lock_file in lock_files:
                # Don't remove our own PID file
                if lock_file == PID_FILE:
                    continue
                    
                try:
                    os.remove(lock_file)
                    logger.info(f"Removed lock file: {lock_file}")
                except Exception:
                    pass
                    
            # Wait for processes to fully terminate
            time.sleep(5)
            return True
            
        except Exception as e:
            logger.error(f"Error killing Discord processes: {e}")
            return False

    def run(self):
        """Ultra-aggressive main monitoring loop - Never gives up!"""
        logger.critical("STARTING ULTRA-AGGRESSIVE 401 RECOVERY MONITOR")
        logger.critical("This monitor will NEVER give up until the bot is running")
        
        # Create startup lock to prevent multiple instances
        with open(STARTUP_LOCK, 'w') as f:
            f.write(str(os.getpid()))
            
        # Ensure we don't interfere with the bot.lock file created by the bot
        # Remove it only if it's stale
        if os.path.exists('bot.lock'):
            try:
                with open('bot.lock', 'r') as f:
                    try:
                        pid = int(f.read().strip())
                        try:
                            # Check if process with this PID exists
                            os.kill(pid, 0)
                            # If we get here, process exists, don't touch the lock file
                            logger.info(f"Bot process with PID {pid} is running, leaving bot.lock alone")
                        except OSError:
                            # Process doesn't exist, remove stale lock
                            logger.warning(f"Removing stale bot.lock for non-existent PID {pid}")
                            os.remove('bot.lock')
                    except (ValueError, OSError):
                        # Invalid PID in the file
                        logger.warning("Invalid PID in bot.lock, removing it")
                        os.remove('bot.lock')
            except:
                # Can't read the file for some reason
                logger.error("Error reading bot.lock, leaving it alone")
        
        try:
            consecutive_failures = 0
            while True:
                try:
                    # Check if the bot is healthy
                    bot_healthy = self.check_bot_health()
                    
                    if bot_healthy:
                        # Bot is healthy - reset failure counter
                        if consecutive_failures > 0:
                            logger.info(f"Bot has recovered after {consecutive_failures} consecutive failures")
                        consecutive_failures = 0
                        
                        # Normal check interval when healthy
                        time.sleep(CHECK_INTERVAL)
                        continue
                    
                    # Bot is unhealthy or we detected auth failures
                    consecutive_failures += 1
                    logger.warning(f"Bot is unhealthy (failure #{consecutive_failures})")
                    
                    # Determine if this is a 401/auth error
                    auth_failures = self.check_for_auth_failures()
                    is_auth_error = len(auth_failures) > 0 or self.should_reset_bot()
                    
                    # Special handling for auth errors
                    if is_auth_error:
                        logger.critical(f"AUTHENTICATION ERROR DETECTED (failure #{consecutive_failures})")
                        
                        # 1. First try token refresh
                        if self.force_refresh_token():
                            logger.info("Bot recovered after token refresh")
                            consecutive_failures = 0
                            time.sleep(CHECK_INTERVAL)
                            continue
                        
                        # 2. If token refresh failed, do a full reset
                        logger.critical("TOKEN REFRESH FAILED - PERFORMING FULL SYSTEM RESET")
                    else:
                        logger.warning(f"General bot health issue (failure #{consecutive_failures})")
                    
                    # Different recovery strategies based on failure count
                    if consecutive_failures <= 3:
                        # For first few failures, just try regular reset
                        logger.info("Attempting standard reset")
                        reset_success = self.reset_bot()
                    elif consecutive_failures <= 10:
                        # For more persistent issues, kill processes first then reset
                        logger.warning("Attempting aggressive reset with process kill")
                        self.kill_all_discord_processes()
                        time.sleep(2)
                        reset_success = self.reset_bot()
                    else:
                        # For extremely persistent issues, use nuclear approach
                        logger.critical(f"EXTREME PERSISTENCE: Failure #{consecutive_failures} - NUCLEAR RESET")
                        
                        # Kill everything
                        self.kill_all_discord_processes()
                        
                        # Clear all lock files
                        for lock_file in glob.glob("*.lock") + glob.glob("*.pid"):
                            if lock_file != PID_FILE and lock_file != STARTUP_LOCK:
                                try:
                                    os.remove(lock_file)
                                except:
                                    pass
                        
                        # Force token refresh
                        self.force_refresh_token()
                        
                        # Execute reset_all.py if it exists
                        if os.path.exists("reset_all.py"):
                            try:
                                subprocess.run(["python3", "-u", "reset_all.py"], timeout=30)
                            except:
                                pass
                        
                        # Restart with extreme prejudice
                        if os.path.exists("restart_bot.sh"):
                            try:
                                subprocess.run(["bash", "restart_bot.sh"], timeout=60)
                            except:
                                pass
                        
                        # Fallback direct restart
                        reset_success = self.reset_bot()
                    
                    # Wait proportional to failure count, but never more than 60 seconds
                    # This prevents endless rapid-fire restart attempts
                    wait_time = min(3 * consecutive_failures, 60)
                    logger.info(f"Waiting {wait_time} seconds before next check")
                    time.sleep(wait_time)
                    
                except KeyboardInterrupt:
                    logger.info("Auto 401 Recovery shutting down via KeyboardInterrupt")
                    break
                except Exception as e:
                    logger.error(f"Error in main recovery loop: {e}")
                    logger.error(traceback.format_exc())
                    # Still try to keep going
                    time.sleep(CHECK_INTERVAL)
        finally:
            # Clean up
            if os.path.exists(PID_FILE):
                try:
                    os.remove(PID_FILE)
                except:
                    pass
            if os.path.exists(STARTUP_LOCK):
                try:
                    os.remove(STARTUP_LOCK)
                except:
                    pass

def is_already_running():
    """Check if an instance is already running"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                # Check if process is running
                os.kill(pid, 0)
                return True
            except OSError:
                # Process doesn't exist
                return False
        except:
            return False
    return False

if __name__ == "__main__":
    # Ensure we're the only instance running
    if is_already_running():
        print("Auto 401 Recovery is already running")
        sys.exit(1)
        
    # Start the recovery service
    recovery = Auto401Recovery()
    recovery.run()