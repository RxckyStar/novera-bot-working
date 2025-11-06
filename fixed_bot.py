#!/usr/bin/env python3
"""
Novera Assistant Discord Bot - CLEAN VERSION
----------------------------
A simplified version designed for reliable operation with proper asyncio handling.
"""

import os
import sys
import logging
import discord
from discord.ext import commands
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional
import json
import traceback
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

# Command prefix
COMMAND_PREFIX = "!"

# Create bot instance
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Banned words for profanity filter - COMPLETE LIST
BANNED_WORDS = [
    # Must block these with highest priority
    "fuck", "fck", "f*ck", "fuk", "fuking", "fukking", "fking", "fkn", 
    "shit", "shi", "sh*t", "sh1t", "sh!t", "dammmn", "wtf", "stfu", "gtfo", "lmfao", "fml", "lmao",
    "bitch", "btch", "b*tch", "asshole", "dumbass",
    "sybau", "sybau2", "sy bau", "s y b a u", "omfg", "dafuq", "mtf",
    # Racial slurs (CRITICAL - must block)
    "nigger", "nigga", "niga", "nga", "n1gga", "n1gg3r", "n1ga", "negro", "chink", "spic", "kike"
]

# Owner ID for DM notifications
OWNER_ID = 654338875736588288

# Owner role ID
OWNER_ROLE_ID = 1350175902738419734

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    logger.info(f"Bot is ready! Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guilds with {sum(g.member_count for g in bot.guilds)} members")
    
@bot.event
async def on_message(message):
    """Handle incoming messages and process commands"""
    if message.author.bot:
        return
    
    # Check for profanity in server channels (not DMs)
    if message.guild and not isinstance(message.channel, discord.DMChannel):
        # Owner is exempt from filter
        is_exempt = False
        if message.author.id == OWNER_ID:
            is_exempt = True
            
        # Admin/mod exemption
        if not is_exempt and (message.author.guild_permissions.administrator or message.author.guild_permissions.manage_messages):
            is_exempt = True
        
        # Owner role exemption
        if not is_exempt:
            for role in message.author.roles:
                if role.id == OWNER_ROLE_ID:
                    is_exempt = True
                    break
        
        # If not exempt, check for banned words
        if not is_exempt:
            content = message.content.lower()
            
            # Check for exact matches of banned words
            for word in BANNED_WORDS:
                if word in content:
                    logger.warning(f"BANNED WORD DETECTED: '{word}' from {message.author.name}: {message.content}")
                    try:
                        await message.delete()
                        warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                        await message.channel.send(f"{message.author.mention} {warning}", delete_after=60)
                        
                        # Notify owner
                        try:
                            owner = await bot.fetch_user(OWNER_ID)
                            if owner:
                                owner_msg = f"🛑 **Banned Word Alert**\n\nUser: {message.author} ({message.author.id})\nChannel: {message.channel.name}\nWord: '{word}'\nMessage: {message.content}"
                                await owner.send(owner_msg)
                        except Exception as e:
                            logger.error(f"Failed to notify owner: {e}")
                        
                        return
                    except Exception as e:
                        logger.error(f"Failed to handle banned word: {e}")
    
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

@bot.command(name="confess")
async def confess_command(ctx):
    """Mommy confesses"""
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
    confession = f"**Mommy's Confession** 🙊\n\n{confessions[int(time.time()) % len(confessions)]}"
    await ctx.send(confession)

@bot.command(name="cleanserver")
@commands.has_permissions(administrator=True)
async def cleanserver_command(ctx):
    """Owner-only command to scan and delete all profanity in the server"""
    if ctx.author.id != OWNER_ID:
        await ctx.send("Only the server owner can use this command!")
        return
    
    await ctx.send("🧹 Beginning server cleanup... scanning all recent messages for profanity.")
    
    total_channels = 0
    total_deleted = 0
    
    for channel in ctx.guild.text_channels:
        try:
            deleted_in_channel = 0
            messages_checked = 0
            
            async for message in channel.history(limit=100):
                messages_checked += 1
                
                if message.author.bot:
                    continue
                    
                # Check if author is exempt
                is_exempt = False
                if message.author.id == OWNER_ID:
                    is_exempt = True
                
                if message.author.guild_permissions.administrator or message.author.guild_permissions.manage_messages:
                    is_exempt = True
                
                for role in message.author.roles:
                    if role.id == OWNER_ROLE_ID:
                        is_exempt = True
                        break
                
                if is_exempt:
                    continue
                
                # Check message content
                content = message.content.lower()
                for word in BANNED_WORDS:
                    if word in content:
                        try:
                            await message.delete()
                            deleted_in_channel += 1
                            total_deleted += 1
                            logger.info(f"Deleted message with banned word '{word}' from {message.author.name} in {channel.name}")
                            break
                        except Exception as e:
                            logger.error(f"Failed to delete message: {e}")
            
            if deleted_in_channel > 0:
                total_channels += 1
                await ctx.send(f"✅ Cleaned {deleted_in_channel} messages from {channel.mention}")
                
        except discord.Forbidden:
            await ctx.send(f"⚠️ No permission to scan {channel.mention}")
        except Exception as e:
            await ctx.send(f"⚠️ Error scanning {channel.mention}: {str(e)}")
    
    summary = f"🧹 **Server Cleanup Complete**\n\n"
    summary += f"Scanned messages in {total_channels} channels\n"
    summary += f"Deleted {total_deleted} messages containing profanity"
    
    await ctx.send(summary)

# Start the bot without using asyncio.run()
def run_bot():
    """Run the bot with proper event loop handling"""
    try:
        loop = asyncio.get_event_loop()
        
        # Check if we got a valid token
        if not TOKEN:
            logger.critical("No Discord token found!")
            return
        
        # Start the bot
        try:
            loop.run_until_complete(bot.start(TOKEN))
        except KeyboardInterrupt:
            loop.run_until_complete(bot.close())
        except Exception as e:
            logger.critical(f"Error starting bot: {e}")
            logger.critical(traceback.format_exc())
    except Exception as e:
        logger.critical(f"Fatal error in run_bot: {e}")
        logger.critical(traceback.format_exc())

if __name__ == "__main__":
    run_bot()