#!/usr/bin/env python3
"""
Fix Bot Once And For All
------------------------
This is a completely simplified approach that solves the core issue directly.
It removes all the complexity and just addresses the event loop problem.

The key is:
1. NEVER use asyncio.run()
2. ALWAYS use loop.create_task() when in a running event loop
3. Keep the implementation minimal to avoid introducing new issues
"""

import os
import sys
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('final_fix.log')
    ]
)

def get_token():
    """Get the Discord token from environment or .env file"""
    # First try environment variable
    token = os.environ.get("DISCORD_TOKEN", "")
    
    # If not set, try loading from .env
    if not token:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            token = os.environ.get("DISCORD_TOKEN", "")
        except ImportError:
            pass
            
    return token

def start_bot():
    """Start the Discord bot with proper event loop handling"""
    logging.info("Starting Discord bot with proper event loop handling")
    
    # Import Discord.py
    try:
        import discord
        from discord.ext import commands
    except ImportError:
        logging.error("Discord.py is not installed, please install it first")
        return False
        
    # Get the token
    token = get_token()
    if not token:
        logging.error("No Discord token found, please set the DISCORD_TOKEN environment variable")
        return False
        
    # Set up the bot with intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    # Set up basic event handlers for testing
    @bot.event
    async def on_ready():
        logging.info(f"Bot is connected as {bot.user}")
        logging.info(f"Connected to {len(bot.guilds)} servers")
        
    # Now handle the event loop properly
    try:
        # Get the current event loop
        loop = asyncio.get_event_loop()
        
        # Define the bot runner coroutine
        async def run_bot():
            try:
                await bot.start(token, reconnect=True)
            except Exception as e:
                logging.error(f"Error starting bot: {e}")
        
        # The key fix: check if loop is running and use create_task if it is
        if loop.is_running():
            logging.info("Event loop is already running, using create_task")
            task = loop.create_task(run_bot())
            return True
        else:
            logging.info("No event loop running, using run_until_complete")
            loop.run_until_complete(run_bot())
            return True
    
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
        return False

def run():
    """Run the bot with the fixed approach"""
    success = start_bot()
    if success:
        logging.info("Bot started successfully")
    else:
        logging.error("Failed to start bot")
        
if __name__ == "__main__":
    run()