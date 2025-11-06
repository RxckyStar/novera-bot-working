import asyncio
import discord
from discord.ext import commands
import os
import sys
import logging
import time
import traceback

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("simple_bot.log")
    ]
)
logger = logging.getLogger("simple_bot")

# Import token getter
try:
    from config import get_token
except ImportError:
    logger.error("Failed to import token function")
    
    def get_token():
        """Fallback token getter"""
        token = os.environ.get("DISCORD_TOKEN", "")
        return token.strip().strip('"').strip("'")

# Create bot with minimal requirements
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content
bot = commands.Bot(command_prefix="!", intents=intents)

# Add basic commands
@bot.command(name="ping")
async def ping_command(ctx):
    """Simple ping command to test responsiveness"""
    try:
        await ctx.send(f"Pong! Latency: {round(bot.latency * 1000)}ms")
        logger.info(f"Ping command executed by {ctx.author}")
    except Exception as e:
        logger.error(f"Error in ping command: {e}")
        try:
            await ctx.send("Sorry, I couldn't complete the ping command.")
        except:
            pass

@bot.command(name="hello")
async def hello_command(ctx):
    """Simple greeting command"""
    try:
        await ctx.send("Hello darling! Mommy is here for you! 💖")
        logger.info(f"Hello command executed by {ctx.author}")
    except Exception as e:
        logger.error(f"Error in hello command: {e}")

@bot.event
async def on_ready():
    """Called when the bot is ready"""
    logger.info(f"Bot logged in as {bot.user}")
    
    # Log connected servers
    server_list = [f"{guild.name} (ID: {guild.id})" for guild in bot.guilds]
    logger.info(f"Connected to {len(bot.guilds)} servers: {', '.join(server_list)}")
    
    # Set a status
    try:
        activity = discord.Game(name="!hello | !ping")
        await bot.change_presence(activity=activity)
    except Exception as e:
        logger.error(f"Failed to set presence: {e}")

@bot.event
async def on_message(message):
    """Handle incoming messages"""
    # Don't respond to our own messages
    if message.author == bot.user:
        return
    
    # Log all commands for debugging
    if message.content.startswith('!'):
        logger.info(f"Command received: {message.content} from {message.author} in {message.guild}")
    
    try:
        # Process commands through the command framework
        await bot.process_commands(message)
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        logger.error(traceback.format_exc())
        
        # Try to inform about the error
        try:
            if message.content.startswith('!'):
                await message.channel.send("Sorry darling, Mommy had a little accident processing that command! 💔")
        except:
            pass

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.CommandNotFound):
        try:
            await ctx.send(f"Sorry sweetie, I don't know that command! Try `!help` for a list of commands. 💕")
        except:
            pass
    else:
        logger.error(f"Command error: {error}")
        logger.error(traceback.format_exc())
        try:
            await ctx.send(f"Oh no! Mommy encountered an error: {type(error).__name__}. Please try again later! 💔")
        except:
            pass

async def main():
    """Main function to run the bot"""
    token = get_token()
    if not token:
        logger.critical("No token found. Cannot start bot.")
        return
    
    logger.info(f"Starting bot with token of length: {len(token)}")
    
    try:
        # Start the bot with reconnect enabled
        await bot.start(token, reconnect=True)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        logger.critical(traceback.format_exc())

if __name__ == "__main__":
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shut down by keyboard interrupt")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        logger.critical(traceback.format_exc())