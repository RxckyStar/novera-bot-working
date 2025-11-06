#!/usr/bin/env python3
"""
Debug Discord Connection
A more detailed script to debug Discord connection issues
"""

import os
import logging
import asyncio
import discord
from discord.ext import commands
import sys
import time
import traceback

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("discord_debug.log"),
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

# Create a simple bot with detailed debug options
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Enable this for member tracking
intents.guilds = True  # Make sure guild tracking is enabled

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Called when the bot is ready and connected"""
    logging.info(f"Bot connected successfully! Logged in as {bot.user.name}#{bot.user.discriminator}")
    logging.info(f"Bot ID: {bot.user.id}")
    logging.info(f"Connected to {len(bot.guilds)} server(s):")
    
    for guild in bot.guilds:
        logging.info(f"  - {guild.name} (ID: {guild.id})")
        logging.info(f"    Member count: {guild.member_count}")
        logging.info(f"    Channel count: {len(guild.channels)}")
        
        # List some channels
        logging.info(f"    Channels sample:")
        for i, channel in enumerate(list(guild.channels)[:5]):
            logging.info(f"      - {channel.name} (ID: {channel.id}, Type: {channel.type})")
            if i >= 4:
                break
    
    # Stay connected for a minute
    logging.info("Bot will stay connected for 60 seconds to collect data...")
    await asyncio.sleep(60)
    
    # Disconnect after monitoring
    await bot.close()
    logging.info("Test completed successfully - bot disconnected")

@bot.event
async def on_error(event, *args, **kwargs):
    """Log any errors that occur"""
    logging.error(f"Error in {event}: {sys.exc_info()[1]}")
    logging.error(traceback.format_exc())
    return False  # Don't suppress the error

@bot.event
async def on_connect():
    """Log when the bot connects to Discord"""
    logging.info("Bot connected to Discord gateway")

@bot.event
async def on_disconnect():
    """Log when the bot disconnects from Discord"""
    logging.info("Bot disconnected from Discord gateway")

@bot.event
async def on_socket_raw_receive(msg):
    """Log raw socket messages - useful for detailed debugging"""
    if len(msg) < 1000:  # Only log reasonably-sized messages
        logging.debug(f"Socket RAW RECV: {msg[:100]}...")
    else:
        logging.debug(f"Socket RAW RECV: (large message - {len(msg)} bytes)")

@bot.event
async def on_socket_raw_send(payload):
    """Log outgoing socket messages"""
    if len(payload) < 1000:  # Only log reasonably-sized messages
        logging.debug(f"Socket RAW SEND: {payload[:100]}...")
    else:
        logging.debug(f"Socket RAW SEND: (large payload - {len(payload)} bytes)")

async def main():
    """Run the bot with detailed error handling"""
    try:
        logging.info("Starting detailed Discord connection test...")
        # Use a more cautious approach to connect
        await bot.login(TOKEN)
        logging.info("Login successful, now connecting to gateway...")
        await bot.connect(reconnect=True)
    except discord.errors.LoginFailure as e:
        logging.critical(f"Discord login failed: {e}")
        logging.critical("This usually means the token is invalid or expired")
    except discord.errors.ConnectionClosed as e:
        logging.error(f"Discord connection closed: {e}")
        logging.error(f"Code: {e.code}, Reason: {e.reason}")
    except discord.errors.GatewayNotFound as e:
        logging.error(f"Discord gateway not found: {e}")
    except discord.errors.HTTPException as e:
        logging.error(f"Discord HTTP error: {e}")
        logging.error(f"Status: {e.status}, Code: {e.code}, Text: {e.text}")
    except Exception as e:
        logging.critical(f"Critical error occurred: {type(e).__name__}: {e}")
        logging.critical(traceback.format_exc())
    finally:
        logging.info("Test completed")
        if not bot.is_closed():
            await bot.close()

# Main entry point
if __name__ == "__main__":
    # Run the bot without using asyncio.run()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt - exiting")
    except Exception as e:
        logging.critical(f"Unhandled exception: {type(e).__name__}: {e}")
        logging.critical(traceback.format_exc())
    finally:
        loop.close()
        logging.info("Event loop closed")