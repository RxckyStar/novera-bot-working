"""
Check what Discord servers the bot is currently connected to
"""
import asyncio
import logging
import discord
from discord.ext import commands
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = config.get_token()

async def check_guilds():
    """Check what guilds (servers) the bot is connected to"""
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        logger.info(f"Bot connected as {bot.user.name}#{bot.user.discriminator} (ID: {bot.user.id})")
        logger.info(f"Connected to {len(bot.guilds)} servers:")
        
        for guild in bot.guilds:
            logger.info(f"- {guild.name} (ID: {guild.id})")
            
            # Check if this has "king" in the name (case insensitive)
            if "king" in guild.name.lower():
                logger.info(f"  *** This server has 'king' in the name! ***")
        
        # Once we've logged the guilds, disconnect
        await bot.close()
    
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Error connecting to Discord: {e}")

if __name__ == "__main__":
    asyncio.run(check_guilds())