#!/usr/bin/env python3
"""
Emergency Reset Script
This script performs a complete emergency reset of the Discord bot
by clearing all token caches, killing all processes, and restarting
with a clean state.
"""

import os
import sys
import time
import json
import logging
import subprocess
import signal
import glob
import psutil
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("emergency_restart.log")
    ]
)
logger = logging.getLogger("emergency_reset")

def kill_all_bot_processes():
    """Kill all bot-related processes"""
    logger.critical("NUCLEAR RESET: Killing all Discord bot processes")
    
    # Method 1: Use kill_processes.py if available
    if os.path.exists("kill_processes.py"):
        logger.info("Executing kill_processes.py")
        try:
            subprocess.run(["python", "kill_processes.py"], timeout=10)
        except Exception as e:
            logger.error(f"Error executing kill_processes.py: {e}")
    
    # Method 2: Use psutil to find and kill specific processes
    bot_process_patterns = [
        "main.py", "bot.py", "gunicorn", "keep_running.py",
        "health_monitor.py", "token_reset_monitor.py",
        "auto_401_recovery.py"
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
        ["pkill", "-9", "-f", "keep_running.py"],
        ["pkill", "-9", "-f", "python"]
    ]
    
    for cmd in shell_commands:
        try:
            subprocess.run(cmd, timeout=3)
        except Exception as e:
            logger.error(f"Error executing {cmd}: {e}")
    
    # Wait for processes to fully terminate
    time.sleep(5)
    
    # Verify all are killed
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            proc_pid = proc.info['pid']
            if proc_pid == current_pid:
                continue
                
            cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
            if any(pattern in cmdline for pattern in bot_process_patterns):
                logger.warning(f"Process still running after kill attempt: {proc_pid}: {cmdline[:50]}...")
                try:
                    # Force kill with SIGKILL
                    os.kill(proc_pid, signal.SIGKILL)
                    logger.info(f"Sent SIGKILL to process {proc_pid}")
                except Exception:
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def clean_lock_files():
    """Remove all lock and pid files"""
    logger.info("Removing lock and pid files")
    
    lock_files = glob.glob("*.lock") + glob.glob("*.pid")
    for lock_file in lock_files:
        try:
            os.remove(lock_file)
            logger.info(f"Removed lock file: {lock_file}")
        except Exception as e:
            logger.error(f"Error removing {lock_file}: {e}")

def reset_token():
    """Reset and validate the Discord token"""
    logger.info("Resetting Discord token")
    
    # First use token_tester if available
    if os.path.exists("token_tester.py"):
        try:
            logger.info("Using token_tester.py to verify and fix token")
            sys.path.append(os.getcwd())
            import token_tester
            if token_tester.fix_token_in_env():
                logger.info("Successfully fixed token with token_tester")
                return True
        except Exception as e:
            logger.error(f"Error using token_tester: {e}")
    
    # Fallback approach - import directly from config
    try:
        logger.info("Using config.py to reset token")
        from config import clean_token, get_token
        
        # Clear any environment cache
        if 'DISCORD_TOKEN' in os.environ:
            logger.info("Clearing cached token from environment")
            os.environ.pop('DISCORD_TOKEN')
        
        # Clear token cache files
        cache_files = ["token_cache.json", ".token_cache", "discord_token.cache"]
        for cache_file in cache_files:
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    logger.info(f"Removed token cache file: {cache_file}")
                except Exception as e:
                    logger.error(f"Error removing {cache_file}: {e}")
        
        # Get fresh token
        token = get_token()
        if token:
            logger.info("Successfully obtained fresh token")
            return True
        else:
            logger.error("Failed to get valid token")
            return False
    except Exception as e:
        logger.error(f"Error resetting token: {e}")
        return False

def restart_bot():
    """Restart the Discord bot"""
    logger.info("Restarting Discord bot")
    
    # Method 1: Use keep_running.py if available
    if os.path.exists("keep_running.py"):
        try:
            logger.info("Restarting with keep_running.py")
            subprocess.Popen(
                ["python", "keep_running.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            return True
        except Exception as e:
            logger.error(f"Error restarting with keep_running.py: {e}")
    
    # Method 2: Use main.py directly
    if os.path.exists("main.py"):
        try:
            logger.info("Restarting with main.py")
            subprocess.Popen(
                ["python", "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            return True
        except Exception as e:
            logger.error(f"Error restarting with main.py: {e}")
    
    # Method 3: Use gunicorn
    try:
        logger.info("Restarting with gunicorn")
        subprocess.Popen(
            ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        return True
    except Exception as e:
        logger.error(f"Error restarting with gunicorn: {e}")
    
    logger.critical("FAILED: All restart methods failed")
    return False

def monitor_restart():
    """Monitor the restart to ensure it was successful"""
    logger.info("Monitoring restart")
    max_attempts = 5
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"Checking bot health (attempt {attempt}/{max_attempts})")
        
        try:
            # Check web health endpoint
            import requests
            response = requests.get("http://127.0.0.1:5000/healthz", timeout=5)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    status = data.get("status")
                    if status == "healthy" or status == "warning":
                        logger.info(f"Bot is healthy! Status: {status}")
                        return True
                except:
                    pass
            
            logger.warning(f"Bot not yet healthy: HTTP {response.status_code}")
        except Exception:
            logger.warning("Bot health check failed: no response from server")
        
        # Try process check as backup
        bot_running = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
                if "main.py" in cmdline or "bot.py" in cmdline or "gunicorn" in cmdline:
                    bot_running = True
                    logger.info(f"Found bot process: {proc.info['pid']}")
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if bot_running:
            logger.info("Bot process is running, but health check failed. Giving it more time.")
        else:
            logger.warning("No bot process found! Attempting to restart again.")
            restart_bot()
        
        # Wait before next check
        time.sleep(5)
    
    logger.warning("Bot restart monitoring timed out")
    return False

def emergency_reset():
    """Perform complete emergency reset"""
    logger.critical("STARTING EMERGENCY RESET PROCEDURE")
    
    # 1. Kill all existing processes
    kill_all_bot_processes()
    
    # 2. Clean up lock files
    clean_lock_files()
    
    # 3. Reset and validate token
    token_reset_success = reset_token()
    if not token_reset_success:
        logger.critical("TOKEN RESET FAILED! Bot may not start properly.")
    
    # 4. Restart bot
    restart_success = restart_bot()
    if not restart_success:
        logger.critical("BOT RESTART FAILED! Manual intervention needed.")
        return False
    
    # 5. Monitor restart
    monitor_success = monitor_restart()
    
    if monitor_success:
        logger.info("EMERGENCY RESET SUCCESSFUL! Bot is now running.")
        return True
    else:
        logger.critical("EMERGENCY RESET MONITORING FAILED! Bot may not be fully functional.")
        return False

if __name__ == "__main__":
    try:
        if emergency_reset():
            logger.info("Emergency reset completed successfully")
            sys.exit(0)
        else:
            logger.error("Emergency reset failed")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Uncaught exception during emergency reset: {e}")
        import traceback
        logger.critical(traceback.format_exc())
        sys.exit(2)