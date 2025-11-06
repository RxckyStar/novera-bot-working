"""
Scan all channels for profanity and delete messages
"""
import logging
import asyncio
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load token from environment
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create bot instance
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# List of offensive words to scan for
BANNED_WORDS = [
    "fuck", "fucking", "fuk", "fuking", "f*ck", "f**k", "fvck",
    "sh*t", "shit", "bullshit", "dipshit", "motherfucker",
    "ass", "asshole", "dumbass", "smartass",
    "bitch", "damn", "hell", "crap"
]

@bot.event
async def on_ready():
    """When bot is ready, scan all channels"""
    logger.info(f"Logged in as {bot.user.name}")
    for guild in bot.guilds:
        logger.info(f"Scanning guild: {guild.name}")
        await scan_guild(guild)
    
    # Exit after scanning all guilds
    await bot.close()

async def scan_guild(guild):
    """Scan all channels in a guild"""
    # Report start
    logger.info(f"Starting scan of guild: {guild.name} (ID: {guild.id})")
    
    # Track statistics
    deleted_count = 0
    channel_count = 0
    
    # Scan each channel
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            channel_count += 1
            logger.info(f"Scanning channel: {channel.name}")
            try:
                # Get messages from the channel
                deleted_in_channel = 0
                async for message in channel.history(limit=1000):
                    # Skip bot messages
                    if message.author.bot:
                        continue
                    
                    # Check for profanity
                    content = message.content.lower()
                    for word in BANNED_WORDS:
                        if word in content:
                            try:
                                logger.info(f"Deleting message from {message.author.name}: {content}")
                                await message.delete()
                                deleted_count += 1
                                deleted_in_channel += 1
                                # Small delay to avoid rate limits
                                await asyncio.sleep(0.5)
                                break
                            except Exception as e:
                                logger.error(f"Error deleting message: {e}")
                
                logger.info(f"Deleted {deleted_in_channel} messages from {channel.name}")
                
            except Exception as e:
                logger.error(f"Error scanning channel {channel.name}: {e}")
    
    # Report completion
    logger.info(f"Scan complete for {guild.name}")
    logger.info(f"Scanned {channel_count} channels")
    logger.info(f"Deleted {deleted_count} offensive messages")

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)