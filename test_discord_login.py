#!/usr/bin/env python3
"""
Test Discord Login

A reliable, focused script to test Discord connection.
This script only attempts to log in and connect to Discord, nothing else.
"""
import os
import sys
import logging
import asyncio
import discord
from dotenv import load_dotenv

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("test_login.log")
    ]
)
logger = logging.getLogger("test-login")

# Set Discord.py's own logger to DEBUG
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
discord_logger.addHandler(handler)

# Load token from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    logger.critical("No Discord token found. Please set DISCORD_TOKEN in .env file.")
    sys.exit(1)

# Clean token (remove any quotes, whitespace)
token_clean = TOKEN.strip().strip('"').strip("'")
logger.info(f"Token length: {len(token_clean)}")

# Create a simple bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)

# Event handlers
@bot.event
async def on_ready():
    """Called when the bot is ready and connected"""
    logger.info(f"Bot connected as: {bot.user.name}#{bot.user.discriminator}")
    
    # Show connected servers
    guild_info = [f"{g.name} (ID: {g.id})" for g in bot.guilds]
    logger.info(f"Connected to {len(bot.guilds)} server(s): {', '.join(guild_info)}")
    
    # Disconnect after 5 seconds to complete the test
    logger.info("Test complete! Shutting down in 5 seconds...")
    await asyncio.sleep(5)
    await bot.close()

@bot.event
async def on_connect():
    """Log when the bot connects to Discord"""
    logger.info("Bot connected to Discord gateway!")

@bot.event
async def on_disconnect():
    """Log when the bot disconnects from Discord"""
    logger.warning("Bot disconnected from Discord")

async def main():
    """Main entry point with error handling"""
    try:
        logger.info("Starting login process...")
        
        # Two-step login process
        # Step 1: Authenticate with Discord
        logger.info("Authenticating with Discord...")
        await bot.login(token_clean)
        logger.info("Authentication successful!")
        
        # Debugging info
        logger.info(f"Bot user: {bot.user.name}#{bot.user.discriminator}")
        logger.info(f"Bot ID: {bot.user.id}")
        
        # Step 2: Connect to the Gateway
        logger.info("Connecting to gateway...")
        await bot.connect(reconnect=True)
        logger.info("Gateway connection complete!")
        
    except Exception as e:
        logger.critical(f"Error connecting to Discord: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    return 0

if __name__ == "__main__":
    # Use a clean, new event loop
    logger.info("Creating a fresh event loop")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run until complete with proper cleanup
    try:
        logger.info("Starting bot connection test")
        exit_code = loop.run_until_complete(main())
        sys.exit(exit_code)
    finally:
        # Clean shutdown
        logger.info("Cleaning up...")
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        logger.info("Test completed")