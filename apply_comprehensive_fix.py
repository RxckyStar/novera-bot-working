#!/usr/bin/env python3
"""
Apply Comprehensive Discord Bot Fix
----------------------------------
This script applies all the fixes to make the Discord bot stable, including:

1. Fixing all asyncio timeout-related issues
2. Applying safe timeout handling throughout the codebase
3. Fixing event loop management
4. Creating a reliable bot entry point

It applies fixes to ALL files, ensuring the fix is comprehensive.
"""

import os
import sys
import subprocess
import time
import logging
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("apply_comprehensive_fix.log")
    ]
)

def run_command(command: List[str], description: str) -> bool:
    """Run a command and return whether it succeeded"""
    try:
        logging.info(f"Running {description}...")
        print(f"▶ {description}...")
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info(f"✓ {description} completed successfully")
            print(f"✓ {description} completed successfully")
            return True
        else:
            logging.error(f"✗ {description} failed with exit code {result.returncode}")
            logging.error(f"Error output: {result.stderr}")
            print(f"✗ {description} failed with exit code {result.returncode}")
            print(f"Error: {result.stderr.splitlines()[0] if result.stderr else 'Unknown error'}")
            return False
    except Exception as e:
        logging.error(f"✗ {description} failed with exception: {e}")
        print(f"✗ {description} failed: {e}")
        return False

def restart_discord_bot():
    """Restart the Discord bot workflow"""
    try:
        # Find the bot process
        ps_result = subprocess.run(
            ["ps", "-ef"], 
            capture_output=True, 
            text=True
        )
        
        if "discord bot.py" in ps_result.stdout.lower():
            logging.info("Found Discord bot process, will restart it")
            
            # Kill the current process
            subprocess.run(
                ["pkill", "-f", "python.*bot\\.py"], 
                capture_output=True
            )
            
            # Wait for the process to terminate
            time.sleep(2)
            
            # Restart the process
            logging.info("Starting Discord bot with safe approach...")
            subprocess.Popen(
                ["python", "run_bot.py"], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logging.info("Discord bot restarted with safe approach")
            print("✓ Discord bot restarted with safe approach")
            return True
        else:
            logging.info("Discord bot not currently running, will start it")
            
            # Start the process
            logging.info("Starting Discord bot with safe approach...")
            subprocess.Popen(
                ["python", "run_bot.py"], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logging.info("Discord bot started with safe approach")
            print("✓ Discord bot started with safe approach")
            return True
            
    except Exception as e:
        logging.error(f"Failed to restart Discord bot: {e}")
        print(f"✗ Failed to restart Discord bot: {e}")
        return False

def apply_all_fixes() -> bool:
    """Apply all the fixes in the correct order"""
    
    steps = [
        {
            "command": ["python", "fix_wait_for.py"],
            "description": "Fixing all bot.wait_for usages in the codebase"
        },
        {
            "command": ["python", "apply_discord_fix.py"],
            "description": "Applying comprehensive Discord asyncio fix to bot.py"
        }
    ]
    
    # Run each step
    for step in steps:
        if not run_command(step["command"], step["description"]):
            return False
            
    # Restart the Discord bot
    return restart_discord_bot()

def main():
    """Main entry point for the script"""
    print("\n" + "=" * 60)
    print(" Apply Comprehensive Fix for Discord Bot ".center(60, "="))
    print("=" * 60 + "\n")
    
    logging.info("Starting comprehensive fix application")
    
    if apply_all_fixes():
        print("\n" + "=" * 60)
        print(" All Fixes Successfully Applied ".center(60, "="))
        print("=" * 60)
        print("\nYour Discord bot should now be running stably with all timeout issues fixed.")
        print("Check 'run_bot.log' for Discord bot logs.")
        print("\nTo restart the bot at any time, run: python run_bot.py")
        return 0
    else:
        print("\n" + "=" * 60)
        print(" Fix Application Failed ".center(60, "="))
        print("=" * 60)
        print("\nSome fixes could not be applied. Check the logs for details.")
        print("See 'apply_comprehensive_fix.log' for more information.")
        return 1

if __name__ == "__main__":
    sys.exit(main())