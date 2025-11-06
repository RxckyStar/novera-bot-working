"""
Instance Manager - Simple and effective process management
Prevents multiple instances of the bot or web server from running
"""
import os
import time
import logging
import psutil
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants for PID files - centralized instance management
WATCHDOG_PID_FILE = "bot_watchdog.pid"  # For keep_running.py
BOT_PID_FILE = "bot.pid"                # For bot.py
WEB_PID_FILE = "web_server.pid"         # For main.py / Flask server


def get_pid_from_file(pid_file):
    """Get PID from a PID file if it exists and is valid"""
    if not os.path.exists(pid_file):
        return None
    
    try:
        with open(pid_file, 'r') as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
            return None
    except Exception as e:
        logger.error(f"Error reading PID file {pid_file}: {e}")
        return None


def is_pid_running(pid):
    """Check if a process with the given PID is running"""
    try:
        if pid is None:
            return False
        
        # Check if process exists without sending signal
        os.kill(pid, 0)
        return True
    except OSError:
        # Process doesn't exist
        return False


def is_process_matching(pid, name_pattern):
    """Check if a process matches a specific pattern in its command line"""
    try:
        if not is_pid_running(pid):
            return False
        
        process = psutil.Process(pid)
        cmdline = " ".join(process.cmdline()) if process.cmdline() else ""
        return name_pattern in cmdline
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    except Exception as e:
        logger.error(f"Error checking process {pid} for pattern '{name_pattern}': {e}")
        return False


def write_pid_file(pid_file, pid=None):
    """Write PID to file"""
    try:
        pid = pid or os.getpid()
        with open(pid_file, 'w') as f:
            f.write(str(pid))
        logger.info(f"Wrote PID {pid} to file {pid_file}")
        return True
    except Exception as e:
        logger.error(f"Error writing PID file {pid_file}: {e}")
        return False


def claim_instance(pid_file, process_pattern):
    """Claim this instance, preventing duplicates
    
    Returns:
        bool: True if instance claimed successfully, False if another instance is running
    """
    current_pid = os.getpid()
    logger.info(f"Attempting to claim instance with PID {current_pid} (pattern: {process_pattern})")
    
    # Check if another instance is already running
    old_pid = get_pid_from_file(pid_file)
    if old_pid:
        logger.info(f"Found existing PID file with PID {old_pid}")
        
        # Check if process is running and matches our pattern
        if is_pid_running(old_pid) and is_process_matching(old_pid, process_pattern):
            logger.error(f"Another instance is already running with PID {old_pid}, cannot claim")
            return False
        
        # Process is not running or doesn't match pattern - stale PID file
        logger.info(f"PID {old_pid} is not running or doesn't match pattern '{process_pattern}', removing stale PID file")
        
        # Try to remove the stale PID file
        try:
            os.remove(pid_file)
            logger.info(f"Successfully removed stale PID file: {pid_file}")
        except Exception as e:
            logger.warning(f"Failed to remove stale PID file {pid_file}: {e}")
    
    # Write our PID to the file
    write_pid_file(pid_file, current_pid)
    logger.info(f"Successfully claimed instance with PID {current_pid}")
    return True


def release_instance(pid_file):
    """Release instance claim by removing PID file"""
    current_pid = os.getpid()
    logger.info(f"Releasing instance with PID {current_pid}")
    
    # Only remove if it's our PID file
    if not os.path.exists(pid_file):
        logger.info(f"PID file {pid_file} does not exist, nothing to release")
        return
    
    try:
        old_pid = get_pid_from_file(pid_file)
        if old_pid == current_pid:
            logger.info(f"Removing our own PID file: {pid_file}")
            os.remove(pid_file)
        # Also clean up if file exists but doesn't contain a valid PID
        elif old_pid is None:
            logger.warning(f"PID file {pid_file} contains invalid data, cleaning up")
            os.remove(pid_file)
        # Also clean up if the process doesn't exist anymore
        elif not is_pid_running(old_pid):
            logger.warning(f"PID file {pid_file} points to non-existent process {old_pid}, cleaning up")
            os.remove(pid_file)
        else:
            logger.warning(f"PID file {pid_file} contains PID {old_pid}, not our PID {current_pid}, not removing")
    except Exception as e:
        logger.error(f"Error releasing instance {pid_file}: {e}")
        # Try one more time to force removal if possible
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
                logger.warning(f"Forced removal of PID file {pid_file} after error")
        except Exception as e2:
            logger.error(f"Final attempt to remove PID file {pid_file} failed: {e2}")


def kill_other_instances(pattern, force=False):
    """Kill other processes matching the given pattern
    
    Args:
        pattern: The pattern to match in process command lines
        force: If True, use SIGKILL immediately instead of trying SIGTERM first
    
    Returns:
        List of killed process PIDs
    """
    current_pid = os.getpid()
    killed_processes = []
    
    # Safety check - don't allow empty pattern which could kill too many processes
    if not pattern or len(pattern) < 3:
        logger.error(f"Pattern '{pattern}' is too short or empty, refusing to kill processes")
        return []
    
    logger.info(f"Looking for processes matching '{pattern}' to terminate")
    
    try:
        matching_processes = []
        
        # First, collect all matching processes
        for proc in psutil.process_iter(['pid', 'cmdline', 'name']):
            try:
                if proc.pid == current_pid:
                    continue
                
                # Skip system processes that we should never kill
                if proc.pid < 10:
                    continue
                
                cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
                proc_name = proc.info['name'] if proc.info['name'] else ""
                
                # Check if process matches the pattern
                if pattern in cmdline:
                    matching_processes.append((proc.pid, cmdline))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Log how many processes we're about to kill
        if matching_processes:
            logger.info(f"Found {len(matching_processes)} processes matching '{pattern}'")
        else:
            logger.info(f"No processes found matching '{pattern}'")
        
        # Now kill them
        for pid, cmdline in matching_processes:
            try:
                process = psutil.Process(pid)
                logger.info(f"Killing process {pid}: {cmdline}")
                
                if force:
                    # Force kill immediately
                    process.kill()
                    killed_processes.append(pid)
                else:
                    # Try graceful termination first
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                        killed_processes.append(pid)
                    except psutil.TimeoutExpired:
                        logger.warning(f"Process {pid} didn't terminate gracefully, forcing kill")
                        process.kill()
                        killed_processes.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                logger.warning(f"Process {pid} disappeared before it could be killed")
            except Exception as kill_err:
                logger.error(f"Error killing process {pid}: {kill_err}")
    except Exception as e:
        logger.error(f"Error killing processes matching '{pattern}': {e}")
    
    # Report how many were killed
    if killed_processes:
        logger.info(f"Successfully killed {len(killed_processes)} processes matching '{pattern}'")
    
    return killed_processes