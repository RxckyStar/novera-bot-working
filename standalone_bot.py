#!/usr/bin/env python3
"""
Standalone Discord Bot - Optimized for reliability
---------------------------------------------------
This version focuses on maintaining a stable connection with proper error handling
and reconnection logic.
"""
import os
import sys
import logging
import asyncio
import discord
from discord.ext import commands, tasks
import time
import signal
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("standalone_bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Default command prefix
COMMAND_PREFIX = "!"

# Banned words to filter, including problematic terms
BANNED_WORDS = [
    # High priority blocks
    "fuck", "fck", "f*ck", "fuk", "shi", "shit", "sh*t", "sh1t", "bitch", "nga", "nigga", "nigger",
    "ass", "wtf", "stfu", "gtfo", "lmfao", "sybau", "sybau2", "chink", "spic", "kike", "negro"
]

# Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

# Create bot instance with explicit help command disabled (we'll create our own)
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# Flag to track if the bot should be running
should_run = True
restart_delay = 5  # seconds between restart attempts

# Handle signals for graceful shutdown
def handle_exit(signum, frame):
    """Handle exit signals gracefully"""
    global should_run
    logger.info(f"Received exit signal {signum}, shutting down gracefully")
    should_run = False

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# Define event handlers
@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    logger.info(f"Bot is ready! Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guilds with {sum(g.member_count for g in bot.guilds)} members")
    
    # Start maintenance tasks
    if not heartbeat_task.is_running():
        heartbeat_task.start()

@tasks.loop(minutes=5)
async def heartbeat_task():
    """Send a heartbeat every 5 minutes to keep the connection alive"""
    try:
        logger.info(f"Heartbeat: Bot is still connected as {bot.user.name}")
        # Check guild connections
        guild_list = [f"{g.name} ({g.member_count} members)" for g in bot.guilds]
        logger.info(f"Connected to {len(guild_list)} guilds: {', '.join(guild_list)}")
    except Exception as e:
        logger.error(f"Error in heartbeat task: {e}")

@bot.event
async def on_disconnect():
    """Called when the bot disconnects from Discord"""
    logger.warning("Bot disconnected from Discord")

@bot.event
async def on_message(message):
    """Handle incoming messages"""
    if message.author.bot:
        return
    
    # Check for profanity in server channels (not DMs)
    if message.guild and not isinstance(message.channel, discord.DMChannel):
        # Skip for admins and moderators
        if not (message.author.guild_permissions.administrator or 
                message.author.guild_permissions.manage_messages):
                
            content = message.content.lower()
            
            # Check for banned words
            for word in BANNED_WORDS:
                if word in content:
                    try:
                        await message.delete()
                        warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                        await message.channel.send(f"{message.author.mention} {warning}", delete_after=60)
                        logger.info(f"Deleted message with banned word from {message.author.name}")
                        return
                    except Exception as e:
                        logger.error(f"Failed to delete message: {e}")
                        break
    
    # Process commands
    await bot.process_commands(message)

@bot.command(name="mommy")
async def mommy_command(ctx):
    """Show help information"""
    help_text = (
        "# Mommy's Commands\n\n"
        "🌟 `!mommy` - Show this help message\n"
        "💰 `!checkvalue` - Check your player value\n"
        "🧹 `!cleanserver` - Clean up profanity (Owner only)\n"
        "👋 `!headpat` - Give Mommy headpats\n"
        "✨ `!confess` - Mommy confesses what she's been up to\n"
        "🛍️ `!shopping` - Reveal Mommy's latest purchases\n"
        "🙊 `!spill` - Share juicy gossip about Novarians\n"
        "💅 `!tipjar` - Check Mommy's special fund status\n"
    )
    await ctx.send(help_text)

@bot.command(name="ping")
async def ping_command(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    response = f"🏓 Pong! Bot latency: **{latency}ms**"
    await ctx.send(response)

@bot.command(name="confess")
async def confess_command(ctx):
    """Mommy confesses what she's been up to"""
    confessions = [
        "I've been secretly judging everyone's fashion choices in the server! 💅",
        "I spent your father's credit card on designer shoes last weekend! 👠",
        "I've been drinking wine while moderating the server! 🍷",
        "I pretend to listen to your problems but I'm really just thinking about my next shopping spree! 🛍️",
        "I told everyone I was at a PTA meeting but I was actually at a spa! 💆‍♀️",
        "I deleted some messages that criticized my moderating style! 🤫",
        "I have favorites among you all, but don't tell anyone! 🤭",
        "I sometimes mute the voice chat when you're talking too much about boring things! 🔇",
        "I've been using the server funds for my personal shopping! 💰",
        "I pretended to be sick to avoid that boring community event last week! 🤒"
    ]
    import random
    confession = f"**Mommy's Confession** 🙊\n\n{random.choice(confessions)}"
    await ctx.send(confession)

def run_bot_with_restarts():
    """Run the bot with automatic reconnection on failure"""
    global should_run
    
    if not TOKEN:
        logger.critical("No Discord token found! Please provide a valid token.")
        return
    
    logger.info("Starting bot with reconnection handling")
    
    while should_run:
        try:
            # Run the bot
            bot.run(TOKEN)
        except discord.errors.LoginFailure as e:
            logger.critical(f"Login failure: {e}")
            logger.critical("Token is invalid or expired. Please check your token.")
            should_run = False  # No point retrying with bad token
        except Exception as e:
            if not should_run:
                break  # Clean exit if shutdown was requested
                
            logger.error(f"Bot crashed with error: {e}")
            logger.error(traceback.format_exc())
            logger.info(f"Restarting bot in {restart_delay} seconds...")
            time.sleep(restart_delay)
            continue
    
    logger.info("Bot has been shut down.")

if __name__ == "__main__":
    run_bot_with_restarts()