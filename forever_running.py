#!/usr/bin/env python3
"""
Forever Running Bot
------------------
This script is designed to be the simplest, most direct way to run
the Discord bot, with maximum error handling and recovery capabilities.

It's specifically designed to avoid all the asyncio-related problems
that other parts of the codebase might encounter.
"""

import os
import sys
import time
import json
import logging
import traceback
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('forever_running.log')
    ]
)

# Constants
MAX_RESTARTS = 10
RESTART_COOLDOWN = 120  # seconds
RESTART_WINDOW = 600  # 10 minutes
HEARTBEAT_FILE = "forever_heartbeat.json"

# Tracking variables
restart_times = []
last_restart = 0

def write_heartbeat(status="running"):
    """Write a heartbeat file that can be checked by monitoring services"""
    try:
        data = {
            "timestamp": time.time(),
            "status": status,
            "pid": os.getpid()
        }
        with open(HEARTBEAT_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Error writing heartbeat: {e}")

def should_restart():
    """Check if we should restart based on our rate limiting"""
    global restart_times, last_restart
    
    # Always allow restart if we haven't restarted recently
    current_time = time.time()
    if current_time - last_restart > RESTART_COOLDOWN:
        return True
    
    # Clean old restart times
    now = datetime.now()
    cutoff = now - timedelta(seconds=RESTART_WINDOW)
    restart_times = [t for t in restart_times if t > cutoff]
    
    # Check if we've restarted too many times recently
    if len(restart_times) >= MAX_RESTARTS:
        logging.warning(f"Hit maximum restart limit ({MAX_RESTARTS} in {RESTART_WINDOW}s), cooling down")
        time.sleep(RESTART_COOLDOWN)
        restart_times = []  # Reset after cooldown
        return True
    
    return True

def run_bot():
    """Run the Discord bot directly"""
    try:
        # Import Discord library
        import discord
        from discord.ext import commands
        
        # Get token
        TOKEN = os.environ.get("DISCORD_TOKEN", "")
        
        # If not set, try loading from .env
        if not TOKEN:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                TOKEN = os.environ.get("DISCORD_TOKEN", "")
            except ImportError:
                logging.error("Could not import dotenv")
        
        # Verify we have a token
        if not TOKEN:
            logging.critical("No Discord token found!")
            return False
        
        # Create bot with intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        # Define essential event handlers
        @bot.event
        async def on_ready():
            logging.info(f"Bot connected as {bot.user}")
            logging.info(f"Connected to {len(bot.guilds)} servers")
            
            # Set status
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="over you, darling"
                )
            )
            
            # Update heartbeat
            write_heartbeat("connected")
        
        @bot.event
        async def on_message(message):
            # Don't respond to our own messages
            if message.author == bot.user:
                return
                
            # Process commands
            await bot.process_commands(message)
        
        # Run the bot
        logging.info(f"Starting Discord bot with token length {len(TOKEN)}")
        bot.run(TOKEN)
        return True
    
    except Exception as e:
        logging.critical(f"Fatal error in bot: {e}")
        traceback.print_exc()
        return False

def main():
    """Main entry point"""
    global restart_times, last_restart
    
    logging.info("=== Starting Forever Running Bot ===")
    
    while True:
        try:
            # Check if we should restart
            if should_restart():
                # Update tracking
                restart_times.append(datetime.now())
                last_restart = time.time()
                
                # Run the bot
                logging.info("Starting bot...")
                write_heartbeat("starting")
                success = run_bot()
                
                if not success:
                    logging.error("Bot failed to start")
                    time.sleep(10)  # Short delay before retry
            
            # If we get here, the bot has stopped
            logging.warning("Bot has stopped, restarting...")
            write_heartbeat("restarting")
            time.sleep(5)  # Short delay before restart
            
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt, exiting")
            break
        except Exception as e:
            logging.critical(f"Unhandled exception in main loop: {e}")
            traceback.print_exc()
            time.sleep(10)  # Delay before retry

if __name__ == "__main__":
    main()