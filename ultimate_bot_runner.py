#!/usr/bin/env python3
"""
ULTIMATE Bot Runner
-----------------
This script is the ABSOLUTE final attempt to make the bot run reliably.
It uses a completely separate process approach with aggressive monitoring
and restart capabilities. NO EVENT LOOP SHARING AT ALL.
"""

import os
import sys
import time
import logging
import subprocess
import signal
import psutil
import json
import threading
import socket
import importlib
import atexit

# Configure maximum logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ultimate_runner.log')
    ]
)
logger = logging.getLogger("ULTIMATE_RUNNER")

# Check if script is already running to prevent duplicate instances
PID_FILE = "ultimate_runner.pid"
HEARTBEAT_FILE = "bot_heartbeat.json"
TOKEN_FILE = "token_cache.json"

# Atomic execution lock to prevent any potential race conditions
EXECUTION_LOCK = threading.Lock()

# Configuration
CHECK_INTERVAL = 15  # seconds
MAX_RESTART_ATTEMPTS = 5
MAX_CONSECUTIVE_FAILURES = 3
RESTART_COOLDOWN = 120  # seconds after max failures

# For monitoring
last_restart_time = 0
restart_attempts = 0
consecutive_failures = 0

def is_port_in_use(port):
    """Check if a port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def is_discord_connected():
    """Check if the Discord gateway is connected by checking the heartbeat file"""
    try:
        if os.path.exists(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, 'r') as f:
                data = json.load(f)
                last_heartbeat = data.get('last_heartbeat', 0)
                current_time = time.time()
                # If heartbeat is within last 60 seconds, consider connected
                return (current_time - last_heartbeat) < 60
        return False
    except Exception as e:
        logger.error(f"Error checking Discord connection: {e}")
        return False

def kill_all_python_processes():
    """Aggressively kill all conflicting Python processes"""
    try:
        # Get the current process ID to avoid killing ourselves
        current_pid = os.getpid()
        
        # First try to find just bot processes
        bot_processes_killed = False
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Skip our own process
                if proc.pid == current_pid:
                    continue
                    
                # Check if it's a bot-related process
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'bot.py' in cmdline or 'discord' in cmdline or 'bot_start.py' in cmdline:
                    logger.info(f"Killing bot process: PID {proc.pid}, cmdline: {cmdline}")
                    try:
                        proc.terminate()
                        time.sleep(0.5)
                        if proc.is_running():
                            proc.kill()
                        bot_processes_killed = True
                    except Exception as e:
                        logger.error(f"Failed to kill process {proc.pid}: {e}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        # If we didn't kill any specific bot processes, be more aggressive with Python processes
        # but ONLY if we've had consecutive failures (avoid disrupting other Python processes)
        if not bot_processes_killed and consecutive_failures > 1:
            logger.warning("No specific bot processes found, targeting Python processes")
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.pid == current_pid:
                        continue
                        
                    name = proc.info['name'] or ""
                    if 'python' in name.lower():
                        cmdline = ' '.join(proc.info['cmdline'] or [])
                        # Skip critical system processes
                        if 'gunicorn' in cmdline or 'ultimate_runner.py' in cmdline:
                            continue
                            
                        logger.info(f"Killing Python process: PID {proc.pid}, cmdline: {cmdline}")
                        try:
                            proc.terminate()
                            time.sleep(0.5)
                            if proc.is_running():
                                proc.kill()
                        except Exception as e:
                            logger.error(f"Failed to kill process {proc.pid}: {e}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except Exception as e:
        logger.error(f"Error in kill_all_python_processes: {e}")

def clear_asyncio_cache():
    """Attempt to clear any modules or caches that might be causing issues"""
    try:
        # Try to reload critical modules
        modules_to_reload = [
            'asyncio', 
            'discord', 
            'discord.client',
            'discord.gateway',
            'discord.voice_client',
            'discord.state',
            'config',
            'fix_timeout_errors',
            'critical_discord_fix'
        ]
        
        for module_name in modules_to_reload:
            try:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                    logger.info(f"Reloaded module: {module_name}")
            except Exception as e:
                logger.error(f"Error reloading {module_name}: {e}")
                
        # Clear event loop policy if possible
        if hasattr(asyncio, 'get_event_loop_policy'):
            try:
                policy = asyncio.get_event_loop_policy()
                policy._local._loop = None
                logger.info("Reset asyncio local event loop")
            except Exception as e:
                logger.error(f"Failed to reset asyncio event loop policy: {e}")
    except Exception as e:
        logger.error(f"Error in clear_asyncio_cache: {e}")

def refresh_token():
    """Refresh or validate the Discord token"""
    try:
        if os.path.exists(TOKEN_FILE):
            logger.info("Token file exists, validating...")
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
                token = token_data.get('token', '')
                if token and len(token) > 50:
                    logger.info("Token appears valid")
                    # Update the token timestamp
                    token_data['timestamp'] = time.time()
                    with open(TOKEN_FILE, 'w') as f:
                        json.dump(token_data, f)
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")

def ensure_clean_environment():
    """Ensure we have a clean environment for the bot to start in"""
    global consecutive_failures
    
    with EXECUTION_LOCK:
        try:
            # Only do aggressive cleanup if we've had multiple consecutive failures
            if consecutive_failures >= 2:
                logger.warning(f"Consecutive failures: {consecutive_failures}, performing aggressive cleanup")
                
                # Kill conflicting processes
                kill_all_python_processes()
                
                # Clear any potentially problematic state
                clear_asyncio_cache()
                
                # Verify token
                refresh_token()
                
                # Wait for things to settle
                time.sleep(3)
        except Exception as e:
            logger.error(f"Error ensuring clean environment: {e}")

def start_bot_process(command=None):
    """Start the Discord bot as a completely separate process"""
    try:
        ensure_clean_environment()
        
        # Default command if none provided
        if not command:
            command = [sys.executable, "bot.py"]
            
        # Start the process detached from parent
        logger.info(f"Starting bot with command: {command}")
        
        # Use Popen to start the process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setpgrp  # This detaches the process
        )
        
        logger.info(f"Started bot process with PID: {process.pid}")
        
        # Start a thread to log the process's output
        def log_output():
            try:
                while process.poll() is None:
                    try:
                        stdout_line = process.stdout.readline().decode('utf-8', errors='ignore').strip()
                        if stdout_line:
                            logger.info(f"BOT: {stdout_line}")
                            
                        stderr_line = process.stderr.readline().decode('utf-8', errors='ignore').strip()
                        if stderr_line:
                            logger.error(f"BOT ERROR: {stderr_line}")
                    except Exception as e:
                        logger.error(f"Error reading process output: {e}")
                        break
            except Exception as e:
                logger.error(f"Error in log_output thread: {e}")
                
        threading.Thread(target=log_output, daemon=True).start()
        
        # Monitor the process in another thread
        def monitor_process():
            try:
                exit_code = process.wait()
                logger.warning(f"Bot process exited with code: {exit_code}")
                
                # The monitoring loop will detect this and restart if needed
            except Exception as e:
                logger.error(f"Error monitoring process: {e}")
                
        threading.Thread(target=monitor_process, daemon=True).start()
        
        # Wait for the bot to show signs of connecting
        logger.info("Waiting for bot to initialize...")
        time.sleep(10)
        
        # Check if the process is still running
        if process.poll() is not None:
            logger.error(f"Bot process exited prematurely with code: {process.poll()}")
            return False
            
        # Check if the web server is running
        web_server_running = is_port_in_use(5001)
        logger.info(f"Web server running: {web_server_running}")
        
        # Return success status based on process running and web server
        return process.poll() is None and web_server_running
    except Exception as e:
        logger.error(f"Error starting bot process: {e}")
        return False

def write_pid_file():
    """Write the current process ID to a file"""
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Error writing PID file: {e}")

def check_pid_file():
    """Check if the PID file exists and if the process is running"""
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
                try:
                    # Check if the process is running
                    process = psutil.Process(pid)
                    if process.is_running():
                        cmdline = ' '.join(process.cmdline())
                        if "ultimate_bot_runner.py" in cmdline:
                            logger.error(f"Another instance of ULTIMATE_RUNNER is running with PID {pid}")
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process doesn't exist, so we can proceed
                    pass
                    
        # No valid PID file or process isn't running
        return False
    except Exception as e:
        logger.error(f"Error checking PID file: {e}")
        return False

def cleanup_resources():
    """Clean up resources on exit"""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception as e:
        logger.error(f"Error cleaning up resources: {e}")

def monitor_and_restart():
    """Main monitoring function that keeps the bot alive at all costs"""
    global last_restart_time, restart_attempts, consecutive_failures
    
    logger.info("Starting ULTIMATE BOT RUNNER monitoring")
    
    while True:
        try:
            # Check if the Discord bot is connected
            bot_running = is_discord_connected()
            web_server_running = is_port_in_use(5001)
            
            current_time = time.time()
            time_since_last_restart = current_time - last_restart_time
            
            logger.info(f"Status - Bot connected: {bot_running}, Web server: {web_server_running}, "
                      f"Restart attempts: {restart_attempts}, Consecutive failures: {consecutive_failures}")
            
            # If we need to restart the bot
            if not bot_running or not web_server_running:
                # If we've had too many consecutive failures, wait for cooldown
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and time_since_last_restart < RESTART_COOLDOWN:
                    logger.warning(f"Cooling down after multiple failures, waiting {RESTART_COOLDOWN - time_since_last_restart:.0f} more seconds")
                    time.sleep(min(CHECK_INTERVAL, RESTART_COOLDOWN - time_since_last_restart))
                    continue
                
                # Check if we've hit the maximum restart attempts
                if restart_attempts >= MAX_RESTART_ATTEMPTS:
                    logger.critical(f"Reached maximum restart attempts ({MAX_RESTART_ATTEMPTS}), performing aggressive cleanup")
                    kill_all_python_processes()
                    clear_asyncio_cache()
                    refresh_token()
                    time.sleep(10)  # Give more time for things to reset
                    restart_attempts = 0  # Reset restart attempts
                
                logger.warning(f"Bot needs restart (connected: {bot_running}, web server: {web_server_running})")
                
                # Perform the restart
                logger.info(f"Attempting to restart bot (attempt {restart_attempts + 1})")
                
                # Try first with regular bot.py
                success = start_bot_process([sys.executable, "bot.py"])
                
                # If that fails, try with bot_start.py
                if not success:
                    logger.warning("First restart attempt failed, trying with bot_start.py")
                    success = start_bot_process([sys.executable, "bot_start.py"])
                
                # Update tracking variables
                last_restart_time = time.time()
                restart_attempts += 1
                
                if success:
                    logger.info("Bot restart appears successful")
                    consecutive_failures = 0  # Reset consecutive failures
                else:
                    logger.error("Bot restart failed")
                    consecutive_failures += 1
            else:
                # Bot is running correctly
                restart_attempts = 0  # Reset restart attempts when things are working
                logger.info("Bot is running correctly")
                
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
            break
        except Exception as e:
            logger.error(f"Error in monitor_and_restart: {e}")
            time.sleep(CHECK_INTERVAL)  # Continue despite errors

def main():
    """Main entrypoint for the ULTIMATE BOT RUNNER"""
    # Register cleanup handler
    atexit.register(cleanup_resources)
    
    # Check if another instance is running
    if check_pid_file():
        logger.error("Another instance is already running")
        return
        
    # Write our PID file
    write_pid_file()
    
    try:
        # Create initial heartbeat file if it doesn't exist
        if not os.path.exists(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, 'w') as f:
                json.dump({'last_heartbeat': 0}, f)
                
        # Start monitoring the bot
        monitor_and_restart()
    finally:
        # Clean up resources
        cleanup_resources()

if __name__ == "__main__":
    main()