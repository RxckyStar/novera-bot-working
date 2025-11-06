#!/usr/bin/env python3
"""
Check and Run Discord Bot
------------------------
This script checks the bot status and runs it with the comprehensive fix.
It's designed for reliability and proper error handling.
"""

import os
import sys
import time
import logging
import subprocess
import json
import asyncio
import traceback
import requests
from typing import Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("check_and_run_bot.log")
    ]
)
logger = logging.getLogger(__name__)

def check_discord_connection() -> Tuple[bool, str]:
    """Check Discord connection by actually hitting their API"""
    try:
        # Use requests to check discord.com connectivity
        response = requests.get("https://discord.com/api/v10/gateway", timeout=5)
        if response.status_code == 200:
            return True, "Discord API gateway is accessible"
        else:
            return False, f"Discord API returned status code {response.status_code}"
    except requests.RequestException as e:
        return False, f"Could not connect to Discord API: {e}"

def check_bot_health() -> Dict[str, Any]:
    """Check health of the bot via its API"""
    try:
        response = requests.get("http://localhost:5001/healthz", timeout=2)
        if response.status_code == 200:
            try:
                return response.json()
            except:
                return {"status": "unknown", "error": "Failed to parse health data"}
        else:
            return {"status": "error", "error": f"Health endpoint returned {response.status_code}"}
    except requests.RequestException as e:
        return {"status": "unavailable", "error": str(e)}

def check_bot_processes() -> bool:
    """Check if any Discord bot processes are already running"""
    try:
        result = subprocess.run(
            ["ps", "-ef"], 
            capture_output=True, 
            text=True
        )
        
        if "python" in result.stdout and "bot.py" in result.stdout:
            logger.info("Found existing bot.py process")
            return True
        if "python" in result.stdout and "run_bot.py" in result.stdout:
            logger.info("Found existing run_bot.py process")
            return True
            
        logger.info("No existing bot processes found")
        return False
    except Exception as e:
        logger.error(f"Error checking processes: {e}")
        return False
        
def run_bot_safe() -> int:
    """Run the Discord bot using the safe approach"""
    try:
        # Try to check Discord connectivity before starting
        discord_connected, message = check_discord_connection()
        if not discord_connected:
            logger.warning(f"Discord connectivity issue: {message}")
            print(f"Warning: Discord connectivity issue detected: {message}")
            print("Continuing anyway, but bot might have trouble connecting...")
        
        # Check if bot is already running
        if check_bot_processes():
            logger.info("Bot already running, checking health")
            health = check_bot_health()
            
            if health.get("status") == "connected" and health.get("bot_connected", False):
                logger.info("Bot is already running and connected to Discord")
                print("✓ Bot is already running and connected to Discord")
                return 0
            else:
                logger.warning("Bot is running but not properly connected. Will restart.")
                print("⚠ Bot is running but not properly connected. Will restart.")
                
                # Kill existing processes
                subprocess.run(["pkill", "-f", "python.*bot\\.py"], capture_output=True)
                subprocess.run(["pkill", "-f", "python.*run_bot\\.py"], capture_output=True)
                time.sleep(2)
        
        # Start the bot with our safe approach
        logger.info("Starting Discord bot with safe approach...")
        print("▶ Starting Discord bot with safe approach...")
        
        bot_process = subprocess.Popen(
            ["python", "run_bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it some time to start
        time.sleep(5)
        
        # Check if process is still running
        if bot_process.poll() is None:
            logger.info("Bot started successfully and is still running")
            print("✓ Bot started successfully")
            return 0
        else:
            stdout, stderr = bot_process.communicate()
            logger.error(f"Bot process terminated with exit code {bot_process.returncode}")
            logger.error(f"Stdout: {stdout}")
            logger.error(f"Stderr: {stderr}")
            print(f"✗ Bot process terminated with exit code {bot_process.returncode}")
            print(f"Error: {stderr.splitlines()[0] if stderr else 'Unknown error'}")
            return 1
    except Exception as e:
        logger.critical(f"Error starting bot: {e}")
        logger.critical(traceback.format_exc())
        print(f"✗ Error starting bot: {e}")
        return 1

def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print(" Discord Bot Status Check and Run ".center(60, "="))
    print("=" * 60 + "\n")
    
    result = run_bot_safe()
    
    if result == 0:
        print("\n" + "=" * 60)
        print(" Bot Running Successfully ".center(60, "="))
        print("=" * 60)
        print("\nYour Discord bot is now running with the comprehensive fix applied.")
        print("To check on the bot status, use: python check_bot_status.py")
    else:
        print("\n" + "=" * 60)
        print(" Bot Startup Failed ".center(60, "="))
        print("=" * 60)
        print("\nThe bot could not be started properly. Check the logs for details.")
        print("For manual startup, try: python run_bot.py")
    
    return result

if __name__ == "__main__":
    sys.exit(main())