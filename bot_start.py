#!/usr/bin/env python3
"""
Bot Starter
-----------
This is a simplified starter script that applies critical fixes
and starts the bot with the most reliable approach possible.
"""

import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_start.log')
    ]
)

def start_bot():
    """Start the Discord bot with ultra-reliability fixes"""
    try:
        # Apply critical fixes first
        logging.info("Applying critical Discord fix now")
        import fix_timeout_errors
        fix_timeout_errors.apply_all_fixes()
        
        # Import configuration
        from config import TOKEN, create_bot
        
        # Verify token
        if not TOKEN:
            logging.critical("No valid token found. Bot cannot start.")
            return
            
        # Clean token if needed
        clean_token = TOKEN.strip()
        
        # Create the bot
        logging.info(f"Starting bot with token length: {len(clean_token)}")
        bot = create_bot()
        
        # Start bot with safe method
        logging.info("Starting Discord bot with safe_discord_start...")
        fix_timeout_errors.safe_discord_start(bot, clean_token)
        
    except Exception as e:
        logging.critical(f"Critical error in bot_start.py: {e}", exc_info=True)
        
if __name__ == "__main__":
    start_bot()