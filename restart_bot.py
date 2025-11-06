#!/usr/bin/env python3
"""
Manual Bot Restart Utility
-------------------------
This script provides a safe way to restart the Discord bot while preserving
the watchdog and reliability systems.

Usage:
    python restart_bot.py
"""

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
    """Find all Discord bot processes"""
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
    """Find all watchdog processes"""
    try:
        result = subprocess.run(
            ["ps", "-ef"],
            capture_output=True,
            text=True,
            check=False
        )
        
        pids = []
        for line in result.stdout.splitlines():
            if "python" in line and "robust_bot_watchdog.py" in line and "grep" not in line:
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
    """Stop all Discord bot processes gracefully"""
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
    """Restart the bot by letting the watchdog do it"""
    # First, check if the watchdog is running
    watchdog_pids = find_watchdog_processes()
    if not watchdog_pids:
        logger.warning("No watchdog processes found, starting a new one")
        try:
            subprocess.Popen(
                [sys.executable, "robust_bot_watchdog.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            logger.info("Started new watchdog process")
            # Give it a moment to initialize
            time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to start watchdog: {e}")
            return False
    
    # Now stop the bot - the watchdog will restart it
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

def main():
    """Main function"""
    logger.info("Starting bot restart process")
    
    # Restart the bot
    success = restart_bot()
    
    if success:
        logger.info("Bot restart initiated successfully")
        print("Bot restart initiated successfully. The watchdog will restart the bot.")
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
        sys.exit(1)