#!/usr/bin/env python3
"""
Ultra Direct Bot Runner
----------------------
This script starts the Discord bot directly without any complex methods
or keep_alive_and_run_bot function. It uses only ONE approach to start
the bot to avoid conflicting event loop issues.
"""

import os
import sys
import asyncio
import logging
import time
import re
import signal

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ultra_direct.log')
    ]
)

# Apply critical fixes BEFORE importing any other modules
import critical_discord_fix
critical_discord_fix.diagnose_and_fix()
asyncio._is_timeout_fixed = True

# Import Discord.py
import discord

# Import token and bot creation from config
from config import TOKEN, create_bot
from fixed_timeout import safe_discord_start

def signal_handler(sig, frame):
    """Handle SIGTERM and SIGINT gracefully"""
    logging.info(f"Received signal {sig}, shutting down gracefully...")
    sys.exit(0)

def start_bot():
    """Start the bot with ultimate simplicity"""
    try:
        # Ensure token is valid
        if not TOKEN:
            logging.critical("No valid token found—bot cannot start.")
            sys.exit(1)
            
        # Clean token
        clean_token = TOKEN.strip().strip('"').strip("'")
        if '\\' in clean_token:
            try:
                clean_token = clean_token.encode().decode('unicode_escape')
            except Exception as e:
                logging.warning(f"Failed to decode escape sequences: {e}")
                
        # Extract token if it's embedded in a larger string
        token_match = re.search(r'[A-Za-z0-9_\-\.]{59,100}', clean_token)
        if token_match:
            extracted = token_match.group(0)
            if extracted != clean_token:
                logging.info("Extracted token from larger string")
                clean_token = extracted
                
        logging.info(f"Starting bot with token of length: {len(clean_token)}")
        
        # Create bot with all permissions
        bot = create_bot()
        
        # Register extra cleanup for SIGTERM or SIGINT
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Start bot with safe method that handles all asyncio issues
        safe_discord_start(bot, clean_token)
        
    except Exception as e:
        logging.critical(f"Critical error in ultra_direct_run.py: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    start_bot()