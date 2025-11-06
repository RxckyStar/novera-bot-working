#!/usr/bin/env python3
"""
Ultra-minimal Discord bot - NO CUSTOM FIXES, just pure Discord.py functionality
"""
import os
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(), logging.FileHandler("minimal_bot.log")])
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(command_prefix="!", intents=intents)

# Banned words - including nga and shi
BANNED_WORDS = [
    "fuck", "shit", "bitch", "nga", "nigga", "niga", "shi", "kys", "sybau", "sybau2", 
    "chink", "spic", "kike"
]

@bot.event
async def on_ready():
    """When the bot has connected to Discord"""
    logger.info(f"Minimal bot is connected as {bot.user.name} ({bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guilds with {sum(g.member_count for g in bot.guilds)} members")
    await bot.change_presence(activity=discord.Game(name="Filtering profanity"))

@bot.event
async def on_message(message):
    """Process messages for profanity and commands"""
    if message.author.bot:
        return

    # Check for profanity in non-DM channels
    if message.guild and not isinstance(message.channel, discord.DMChannel):
        # Skip for admin/moderator users
        if not (message.author.guild_permissions.administrator or 
                message.author.guild_permissions.manage_messages):
            content = message.content.lower()
            
            # Check for banned words
            for word in BANNED_WORDS:
                if word in content:
                    try:
                        await message.delete()
                        logger.info(f"Deleted message with banned word '{word}' from {message.author.name}")
                        
                        warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                        await message.channel.send(f"{message.author.mention} {warning}", delete_after=60)
                        return
                    except Exception as e:
                        logger.error(f"Failed to delete message: {e}")
                        break
    
    # Process commands
    await bot.process_commands(message)

@bot.command(name="test")
async def test_command(ctx):
    """Test command to verify bot is working"""
    await ctx.send("✅ Bot is working correctly!")

@bot.command(name="testfilter")
async def test_filter_command(ctx):
    """Test the profanity filter (admin only)"""
    if ctx.author.guild_permissions.administrator:
        await ctx.send("Testing profanity filter - ONLY ADMINS WILL SEE THIS MESSAGE")
        
        # Send list of words being filtered (admin eyes only)
        word_list = ", ".join(f"`{word}`" for word in BANNED_WORDS)
        await ctx.send(f"Currently filtering these words: {word_list}")
        
        await ctx.send("Please verify these words are being properly filtered.")
    else:
        await ctx.send("⚠️ This command is for admins only.")

# Run the bot using the standard method
bot.run(TOKEN)