#!/usr/bin/env python3
"""
Test Discord Connection
A simple script to test Discord connection
"""

import os
import logging
import asyncio
import discord
from discord.ext import commands
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Using DEBUG level to see all connection details
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get token from .env
TOKEN = None
try:
    from dotenv import load_dotenv
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")
    logging.info(f"Loaded token from .env (length: {len(TOKEN) if TOKEN else 0})")
except ImportError:
    logging.warning("python-dotenv not installed, reading .env manually")
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('DISCORD_TOKEN='):
                    TOKEN = line.strip().split('=', 1)[1].strip().strip('"').strip("'")
                    logging.info(f"Read token manually from .env (length: {len(TOKEN) if TOKEN else 0})")
                    break
    except Exception as e:
        logging.error(f"Error reading .env file: {e}")

if not TOKEN:
    logging.critical("No Discord token found - cannot continue")
    sys.exit(1)

# Clean token
TOKEN = TOKEN.strip().strip('"').strip("'")
logging.info(f"Token is {len(TOKEN)} characters long")
logging.info(f"Token starts with: {TOKEN[:10]}... ends with: ...{TOKEN[-5:]}")

# Create a simple bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Called when the bot is ready and connected"""
    logging.info(f"Bot connected successfully! Logged in as {bot.user.name}#{bot.user.discriminator}")
    logging.info(f"Bot ID: {bot.user.id}")
    logging.info(f"Connected to {len(bot.guilds)} server(s):")
    
    for guild in bot.guilds:
        logging.info(f"  - {guild.name} (ID: {guild.id})")
    
    # Disconnect after successful connection
    await bot.close()
    logging.info("Test completed successfully - bot disconnected")

@bot.event
async def on_error(event, *args, **kwargs):
    """Log any errors that occur"""
    logging.error(f"Error in {event}: {sys.exc_info()[1]}")
    traceback = sys.exc_info()[2]
    while traceback:
        logging.error(f"  File {traceback.tb_frame.f_code.co_filename}, line {traceback.tb_lineno}")
        traceback = traceback.tb_next

@bot.event
async def on_connect():
    """Log when the bot connects to Discord"""
    logging.info("Bot connected to Discord gateway")

@bot.event
async def on_disconnect():
    """Log when the bot disconnects from Discord"""
    logging.info("Bot disconnected from Discord gateway")

async def main():
    """Run the bot"""
    try:
        logging.info("Starting Discord connection test...")
        await bot.start(TOKEN)
    except Exception as e:
        logging.critical(f"Critical error occurred: {e}")
    finally:
        logging.info("Test completed")

# Main entry point
if __name__ == "__main__":
    # Run the bot without using asyncio.run()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt - exiting")
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}")
    finally:
        loop.close()
        logging.info("Event loop closed")