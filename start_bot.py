#!/usr/bin/env python3
"""
Discord Bot Launcher
-------------------
This is the ONLY correct way to start the Discord bot.
It ensures all asyncio-related fixes are properly applied
and the bot is started with the right event loop approach.
"""

# Import our comprehensive fix module FIRST - before any other imports
import discord_asyncio_fix

# Standard library imports
import os
import sys
import logging
import threading
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

# Import the bot and Flask server
from bot import bot, TOKEN, keep_alive

def main():
    """Main entry point to start the bot with all fixes applied"""
    try:
        # Start the Flask web server in the background
        keep_alive()
        
        # Validate and clean the token
        if not TOKEN:
            logging.critical("No valid token found—bot cannot start.")
            sys.exit(1)
        
        clean_token = TOKEN.strip().strip('"').strip("'")
        logging.info(f"Starting bot with token length: {len(clean_token)}")
        
        # Use our fixed function to start the bot
        # This is the right way that handles all event loop issues
        discord_asyncio_fix.start_discord_bot(bot, clean_token)
        
    except Exception as e:
        logging.critical(f"Error starting bot: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Apply our fixes again just to be safe
    discord_asyncio_fix.apply_all_fixes()
    
    # Start the bot
    main()