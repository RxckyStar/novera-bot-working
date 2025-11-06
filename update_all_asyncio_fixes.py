#!/usr/bin/env python3
"""
COMPREHENSIVE ASYNCIO FIX UPDATER
--------------------------------
This script updates all asyncio and discord.py related files with the latest fixes.
It makes backups of original files and ensures all components are consistent.

Run this script if you need to update the asyncio fixes in the future.
"""

import os
import sys
import shutil
import logging
import datetime
import subprocess
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("update_asyncio_fixes.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("update_asyncio_fixes")

# Configuration
FILES_TO_UPDATE = [
    "discord_asyncio_fix.py",
    "aiohttp_timeout_fix.py",
    "timeout_handlers.py",
    "run_bot.py"
]

SCRIPTS_TO_CREATE = [
    "NEVER_DOWN.sh",
    "restart_bot.py"
]

def backup_file(file_path: str) -> Optional[str]:
    """Create a backup of the file if it exists"""
    if os.path.exists(file_path):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.{timestamp}.bak"
        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup of {file_path} at {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup of {file_path}: {e}")
    return None

def make_script_executable(script_path: str) -> bool:
    """Make a script executable"""
    try:
        # Check if file exists
        if not os.path.exists(script_path):
            logger.error(f"Script {script_path} does not exist")
            return False
        
        # Make executable (chmod +x)
        os.chmod(script_path, 0o755)  # rwxr-xr-x
        logger.info(f"Made {script_path} executable")
        return True
    except Exception as e:
        logger.error(f"Failed to make {script_path} executable: {e}")
        return False

def update_bot_imports() -> bool:
    """Update the imports in bot.py to use the new fixes"""
    try:
        if not os.path.exists("bot.py"):
            logger.error("bot.py does not exist")
            return False
        
        # Backup first
        backup_file("bot.py")
        
        with open("bot.py", "r") as f:
            content = f.read()
        
        # Check if the imports already exist
        if "import discord_asyncio_fix" in content and "import aiohttp_timeout_fix" in content and "import timeout_handlers" in content:
            logger.info("Bot imports already up to date")
            return True
        
        # Add the imports at the top
        if "# Apply comprehensive fix at the very start" in content:
            # Replace existing import with the new ones
            content = content.replace(
                "# Apply comprehensive fix at the very start - MUST BE FIRST IMPORT\nimport discord_asyncio_fix\nfrom discord_asyncio_fix import safe_wait_for",
                "# Apply comprehensive fixes at the very start - MUST BE FIRST IMPORTS\nimport discord_asyncio_fix\ndiscord_asyncio_fix.apply_all_fixes()  # Explicitly apply all fixes\nfrom discord_asyncio_fix import safe_wait_for\nimport aiohttp_timeout_fix  # Fix for aiohttp compatibility\nimport timeout_handlers  # Additional timeout handling"
            )
        else:
            # Find a suitable insertion point at the top
            first_import_idx = content.find("import ")
            if first_import_idx >= 0:
                import_block = "# Apply comprehensive fixes at the very start - MUST BE FIRST IMPORTS\nimport discord_asyncio_fix\ndiscord_asyncio_fix.apply_all_fixes()  # Explicitly apply all fixes\nfrom discord_asyncio_fix import safe_wait_for\nimport aiohttp_timeout_fix  # Fix for aiohttp compatibility\nimport timeout_handlers  # Additional timeout handling\n\n"
                content = content[:first_import_idx] + import_block + content[first_import_idx:]
            else:
                logger.error("Could not find a suitable place to insert imports in bot.py")
                return False
        
        # Write updated content back to file
        with open("bot.py", "w") as f:
            f.write(content)
        
        logger.info("Updated imports in bot.py")
        return True
    except Exception as e:
        logger.error(f"Failed to update bot imports: {e}")
        return False

def update_main_block() -> bool:
    """Update the main block in bot.py to use the new fixes"""
    try:
        if not os.path.exists("bot.py"):
            logger.error("bot.py does not exist")
            return False
        
        # Backup first
        backup_file("bot.py")
        
        with open("bot.py", "r") as f:
            content = f.read()
        
        # Look for the main block
        main_block_idx = content.find("if __name__ == \"__main__\":")
        if main_block_idx < 0:
            logger.error("Could not find the main block in bot.py")
            return False
        
        # Find the end of the main block
        end_of_file = len(content)
        
        # Extract everything before the main block
        content_before_main = content[:main_block_idx]
        
        # Create the new main block
        new_main_block = """if __name__ == "__main__":
    # Start the Flask web server in the background - but don't start the bot yet
    keep_alive()
    
    # Prepare token
    if not TOKEN:
        logging.critical("No valid token found—bot cannot start.")
        sys.exit(1)
    clean_token_final = TOKEN.strip().strip('"').strip("'")
    logging.info(f"Starting bot with token length: {len(clean_token_final)}")
    
    # Initialize heartbeat
    heartbeat = heartbeat_manager.get_heartbeat_manager("discord_bot")
    heartbeat.update_status("starting")
    
    try:
        # Apply cleanup on exit
        atexit.register(timeout_handlers.cleanup_loop)
        
        # Register signal handlers for cleaner shutdown
        def handle_signal(signum, frame):
            """Handle signal by cleaning up and exiting"""
            logging.info(f"Received signal {signum}, performing cleanup...")
            timeout_handlers.cleanup_loop()
            heartbeat.update_status("shutdown")
            sys.exit(0)
            
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # Use our comprehensive Discord asyncio fix to start the bot
        # This properly handles all event loop and timeout issues
        logging.info("Starting bot with comprehensive fixes applied")
        discord_asyncio_fix.run_bot(bot, clean_token_final, close_previous_loop=True)
    except Exception as e:
        logging.critical(f"Critical error in bot startup: {e}")
        logging.critical(traceback.format_exc())
        heartbeat.update_status("error")
        heartbeat.record_error()
        # Use the timeout_handlers cleanup to ensure no orphaned tasks
        try:
            timeout_handlers.cleanup_loop()
        except:
            pass
        raise"""
        
        # Combine everything
        updated_content = content_before_main + new_main_block
        
        # Write updated content back to file
        with open("bot.py", "w") as f:
            f.write(updated_content)
        
        logger.info("Updated main block in bot.py")
        return True
    except Exception as e:
        logger.error(f"Failed to update main block: {e}")
        return False

def create_executable_shell_script(name: str) -> bool:
    """Create an executable shell script if it doesn't exist"""
    try:
        if os.path.exists(name):
            logger.info(f"Script {name} already exists, making executable")
            return make_script_executable(name)
        
        # Create the script based on its name
        if name == "NEVER_DOWN.sh":
            with open(name, "w") as f:
                f.write("""#!/bin/bash
#
# ULTRA-RELIABLE BOT STARTUP SCRIPT
# ---------------------------------
# This script provides a robust way to start and monitor the bot
# It uses a supervisor approach to ensure the bot stays running
# even if it crashes or encounters errors
#

# Constants
LOG_FILE="never_down.log"
RESTART_DELAY=10
MAX_RESTARTS_PER_HOUR=10
RUN_SCRIPT="run_bot.py"
MONITOR_INTERVAL=60

# Logging function
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Initialize log
log "Starting NEVER_DOWN.sh supervisor"

# Kill existing bot processes to avoid conflicts
kill_existing() {
  log "Checking for existing bot processes..."
  pkill -f "python.*bot\.py" || true
  pkill -f "python.*run_bot\.py" || true
  sleep 2
  log "Existing processes handled"
}

# Start the bot
start_bot() {
  log "Starting bot using $RUN_SCRIPT..."
  python "$RUN_SCRIPT" >> "$LOG_FILE" 2>&1 &
  BOT_PID=$!
  log "Bot started with PID $BOT_PID"
}

# Track restarts to prevent excessive cycling
restart_timestamps=()

# Check if we're restarting too frequently
check_restart_rate() {
  local now=$(date +%s)
  local one_hour_ago=$((now - 3600))
  
  # Remove timestamps older than an hour
  local new_timestamps=()
  for ts in "${restart_timestamps[@]}"; do
    if [ "$ts" -gt "$one_hour_ago" ]; then
      new_timestamps+=("$ts")
    fi
  done
  restart_timestamps=("${new_timestamps[@]}")
  
  # Add current timestamp
  restart_timestamps+=("$now")
  
  # Check if we've exceeded the limit
  if [ "${#restart_timestamps[@]}" -gt "$MAX_RESTARTS_PER_HOUR" ]; then
    log "WARNING: Too many restarts in the past hour (${#restart_timestamps[@]}/$MAX_RESTARTS_PER_HOUR)"
    log "Waiting for a cooling period before continuing..."
    sleep 300  # 5 minute cooling period
    return 1
  fi
  
  return 0
}

# Main supervisor loop
supervisor() {
  kill_existing
  start_bot
  
  # Monitor the bot process
  while true; do
    # Check if process is still running
    if ! ps -p "$BOT_PID" > /dev/null; then
      log "Bot process (PID $BOT_PID) has died"
      
      # Check restart rate
      if check_restart_rate; then
        log "Restarting bot after $RESTART_DELAY second delay..."
        sleep "$RESTART_DELAY"
        kill_existing
        start_bot
      fi
    else
      log "Bot process (PID $BOT_PID) is running normally"
    fi
    
    # Wait before checking again
    sleep "$MONITOR_INTERVAL"
  done
}

# Start the supervisor
supervisor""")
        
        elif name == "restart_bot.py":
            with open(name, "w") as f:
                f.write("""#!/usr/bin/env python3
\"\"\"
Manual Bot Restart Utility
-------------------------
This script provides a safe way to restart the Discord bot while preserving
the watchdog and reliability systems.

Usage:
    python restart_bot.py
\"\"\"

import os
import sys
import time
import json
import signal
import logging
import subprocess
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("restart_bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("restart_bot")

def find_bot_processes() -> List[int]:
    \"\"\"Find all Discord bot processes\"\"\"
    try:
        result = subprocess.run(
            ["ps", "-ef"],
            capture_output=True,
            text=True,
            check=False
        )
        
        pids = []
        for line in result.stdout.splitlines():
            if "python" in line and "bot.py" in line and "grep" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        pids.append(pid)
                    except ValueError:
                        continue
        
        return pids
    except Exception as e:
        logger.error(f"Error finding bot processes: {e}")
        return []

def find_watchdog_processes() -> List[int]:
    \"\"\"Find all watchdog processes\"\"\"
    try:
        result = subprocess.run(
            ["ps", "-ef"],
            capture_output=True,
            text=True,
            check=False
        )
        
        pids = []
        for line in result.stdout.splitlines():
            if "NEVER_DOWN.sh" in line and "grep" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        pids.append(pid)
                    except ValueError:
                        continue
        
        return pids
    except Exception as e:
        logger.error(f"Error finding watchdog processes: {e}")
        return []

def stop_bot_processes() -> bool:
    \"\"\"Stop all Discord bot processes gracefully\"\"\"
    bot_pids = find_bot_processes()
    if not bot_pids:
        logger.info("No bot processes found to stop")
        return True
    
    logger.info(f"Stopping {len(bot_pids)} bot processes: {bot_pids}")
    success = True
    
    for pid in bot_pids:
        try:
            # Try to stop gracefully first
            os.kill(pid, signal.SIGTERM)
            logger.info(f"Sent SIGTERM to bot process {pid}")
        except Exception as e:
            logger.error(f"Error stopping bot process {pid}: {e}")
            success = False
    
    # Wait a bit for processes to terminate
    time.sleep(3)
    
    # Check if any processes are still running
    remaining_pids = find_bot_processes()
    if remaining_pids:
        logger.warning(f"{len(remaining_pids)} bot processes still running after graceful shutdown: {remaining_pids}")
        # Try to force kill
        for pid in remaining_pids:
            try:
                os.kill(pid, signal.SIGKILL)
                logger.info(f"Sent SIGKILL to bot process {pid}")
            except Exception as e:
                logger.error(f"Error killing bot process {pid}: {e}")
                success = False
        
        # Wait a bit more for force kills to complete
        time.sleep(2)
    
    # Final check
    final_pids = find_bot_processes()
    if final_pids:
        logger.error(f"Failed to stop {len(final_pids)} bot processes: {final_pids}")
        success = False
    
    return success

def restart_bot() -> bool:
    \"\"\"Restart the bot, either via watchdog or directly\"\"\"
    # First, check if the watchdog is running
    watchdog_pids = find_watchdog_processes()
    if watchdog_pids:
        logger.info(f"Watchdog is running with PID(s): {watchdog_pids}")
        # Just stop the bot - the watchdog will restart it
        if stop_bot_processes():
            logger.info("Successfully stopped bot processes, watchdog will restart the bot")
            # Update heartbeat file with status=error to force watchdog to act faster
            try:
                if os.path.exists("bot_heartbeat.json"):
                    with open("bot_heartbeat.json", "r") as f:
                        data = json.load(f)
                    
                    data["status"] = "error"
                    data["timestamp"] = 0  # Old timestamp to force restart
                    
                    with open("bot_heartbeat.json", "w") as f:
                        json.dump(data, f)
                    
                    logger.info("Updated heartbeat file to trigger watchdog")
            except Exception as e:
                logger.error(f"Error updating heartbeat file: {e}")
            
            return True
        else:
            logger.error("Failed to stop some bot processes")
            return False
    else:
        # No watchdog, start the bot directly
        logger.info("No watchdog found, starting bot directly")
        try:
            # First stop any existing bot processes
            stop_bot_processes()
            
            # Start the bot using run_bot.py
            if os.path.exists("run_bot.py"):
                logger.info("Starting bot using run_bot.py")
                subprocess.Popen(
                    [sys.executable, "run_bot.py"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            else:
                # Fallback to direct bot.py
                logger.info("Starting bot using bot.py")
                subprocess.Popen(
                    [sys.executable, "bot.py"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            logger.info("Bot started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            return False

def main():
    \"\"\"Main function\"\"\"
    logger.info("Starting bot restart process")
    
    # Restart the bot
    success = restart_bot()
    
    if success:
        logger.info("Bot restart initiated successfully")
        print("Bot restart initiated successfully.")
    else:
        logger.error("Failed to restart bot")
        print("Failed to restart bot. Check restart_bot.log for details.")
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        print(f"Fatal error: {e}")
        sys.exit(1)""")
        
        # Make the script executable
        make_script_executable(name)
        logger.info(f"Created and made executable: {name}")
        return True
    except Exception as e:
        logger.error(f"Failed to create executable script {name}: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting comprehensive asyncio fix update")
    
    # Check if we're in the right directory
    if not os.path.exists("bot.py"):
        logger.error("bot.py not found. Please run this script from the project root directory.")
        return 1
    
    # 1. Backup original files
    for file in FILES_TO_UPDATE:
        if os.path.exists(file):
            backup_file(file)
    
    # 2. Copy files from fixed_bot_extracted if available
    if os.path.exists("fixed_bot_extracted"):
        logger.info("Found fixed_bot_extracted directory, copying files from there")
        for file in FILES_TO_UPDATE:
            source = os.path.join("fixed_bot_extracted", file)
            if os.path.exists(source):
                try:
                    shutil.copy2(source, file)
                    logger.info(f"Copied {source} to {file}")
                except Exception as e:
                    logger.error(f"Failed to copy {source} to {file}: {e}")
    
    # 3. Update bot.py imports
    update_bot_imports()
    
    # 4. Update bot.py main block
    update_main_block()
    
    # 5. Create executable shell scripts
    for script in SCRIPTS_TO_CREATE:
        create_executable_shell_script(script)
    
    # 6. Make run_bot.py executable if it exists
    if os.path.exists("run_bot.py"):
        make_script_executable("run_bot.py")
    
    logger.info("Comprehensive asyncio fix update completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())