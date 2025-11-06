import asyncio
import discord
from discord.ext import commands, tasks
import os
import sys
import logging
import time
import traceback
import json
import random
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("novera_simple.log")
    ]
)
logger = logging.getLogger("novera_simple")

# Import token getter
try:
    from config import get_token
except ImportError:
    logger.error("Failed to import token function")
    
    def get_token():
        """Fallback token getter"""
        token = os.environ.get("DISCORD_TOKEN", "")
        return token.strip().strip('"').strip("'")

try:
    from data_manager import DataManager
    data_manager = DataManager("member_data.json")
    logger.info("Loaded data manager")
except Exception as e:
    logger.error(f"Error loading data manager: {e}")
    data_manager = None

# Create bot with required intents
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content
intents.members = True  # Required for member related commands
intents.guilds = True  # Required for guild/server related commands
bot = commands.Bot(command_prefix="!", intents=intents)

# Load response variants from the original bot
MOMMY_SUCCESS_VARIANTS = [
    "🎉 Yay, Mommy is so proud of you, darling! Fantastic work! 💖",
    "👏 Hooray, you've done it, sweetie! Mommy loves your effort! 🌟",
    "🏆 Bravo, my precious! Mommy is absolutely delighted by your performance! 😍",
    "✨ Wonderful, darling—Mommy adores your work! Keep shining! 🌈",
    "💐 Splendid job, sweetheart! Mommy is cheering for you with all her heart! 💝",
]

MOMMY_ERROR_VARIANTS = [
    "😱 Oh dear, Mommy had a little boo boo! Please try again, sweetie! 😢",
    "😓 Oopsie, something went awry, my darling! Mommy is on it! 🌈",
    "😖 Oh no dear, Mommy's system just tripped over a rainbow! Try again, honey! 💕",
    "😞 Yikes, that didn't go as planned, sweetie! Mommy needs a moment! 😇",
    "😬 Whoopsie, Mommy encountered a tiny hiccup there! Please forgive me, darling! 😘",
]

MOMMY_CHECKVALUE_VARIANTS = [
    "💖 Darling, your value sparkles at ¥{value} million! Mommy is so proud of you! ✨",
    "💎 Sweetheart, your value shines at an amazing ¥{value} million—keep dazzling, my star! 🌟",
    "💰 Oh my, your value stands tall at ¥{value} million! Mommy is over the moon for you! 🎉",
    "🌈 Bravo, my precious! Your value is a fabulous ¥{value} million. Mommy loves your shine! 😍",
    "🔥 Darling, you're on fire with a value of ¥{value} million! Keep making Mommy proud! 🥰",
]

MOMMY_LOW_VALUE_VARIANTS = [
    "💸 Only ¥{value} million? Darling, Mommy spends that much on a Gucci bag! You need to aim higher! 👜",
    "🤏 ¥{value} million? Is that all you've got, sweetie? Mommy's manicure costs more than that! 💅",
    "😒 Hmm, ¥{value} million... Mommy spent more than that on breakfast this morning. Do better, darling! 🍳",
]

MOMMY_ZERO_VALUE_VARIANTS = [
    "💖 Oh sweetie, your value is just starting to bloom at ¥0 million! Mommy believes in your potential! ✨",
    "🌱 Darling, everyone starts at ¥0 million! Mommy can't wait to see how you'll grow! 🌿",
    "🤗 No value yet, my precious? That just means you've got nowhere to go but up! Mommy's cheering for you! 📈",
]

# Global variables
start_time = time.time()
last_heartbeat = time.time()

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
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
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

@bot.command(name="status")
async def status_command(ctx):
    """Show bot status information"""
    try:
        uptime = time.time() - start_time
        hours, remainder = divmod(int(uptime), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"
        
        servers = len(bot.guilds)
        members = sum(guild.member_count for guild in bot.guilds)
        
        message = (
            f"🌟 **Bot Status** 🌟\n"
            f"➡️ Uptime: {uptime_str}\n"
            f"➡️ Connected to: {servers} servers\n"
            f"➡️ Serving: {members} members\n"
            f"➡️ Latency: {round(bot.latency * 1000)}ms\n"
            f"➡️ Heartbeat age: {round(time.time() - last_heartbeat)}s"
        )
        
        await ctx.send(message)
        logger.info(f"Status command executed by {ctx.author}")
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@bot.command(name="checkvalue")
async def checkvalue_command(ctx):
    """Check the user's value from the data manager"""
    try:
        if data_manager is None:
            await ctx.send("😔 Oh no darling, Mommy can't access your value records right now! Try again later, sweetie! 💕")
            return
            
        user_id = str(ctx.author.id)
        value = data_manager.get_member_value(user_id)
        
        if value > 10:
            message = random.choice(MOMMY_CHECKVALUE_VARIANTS).format(value=value)
        elif value > 0:
            message = random.choice(MOMMY_LOW_VALUE_VARIANTS).format(value=value)
        else:
            message = random.choice(MOMMY_ZERO_VALUE_VARIANTS).format(value=value)
            
        await ctx.send(message)
        logger.info(f"Checkvalue command executed by {ctx.author} - value: {value}")
    except Exception as e:
        logger.error(f"Error in checkvalue command: {e}")
        logger.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

# Event handlers
@bot.event
async def on_ready():
    """Called when the bot is ready"""
    global last_heartbeat
    last_heartbeat = time.time()
    
    logger.info(f"Bot logged in as {bot.user}")
    
    # Log connected servers
    server_list = [f"{guild.name} (ID: {guild.id})" for guild in bot.guilds]
    logger.info(f"Connected to {len(bot.guilds)} servers: {', '.join(server_list)}")
    
    # Start the heartbeat task
    heartbeat_task.start()
    
    # Set a status
    try:
        activity = discord.Activity(type=discord.ActivityType.listening, name="commands | !help")
        await bot.change_presence(activity=activity)
    except Exception as e:
        logger.error(f"Failed to set presence: {e}")

@bot.event
async def on_message(message):
    """Handle incoming messages"""
    global last_heartbeat
    last_heartbeat = time.time()
    
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
                await message.channel.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.CommandNotFound):
        try:
            await ctx.send("Sorry sweetie, I don't know that command! Try `!help` for a list of commands. 💕")
        except:
            pass
    elif isinstance(error, commands.MissingRequiredArgument):
        try:
            await ctx.send(f"Oh darling, you need to provide more information for that command! Try `!help {ctx.command}` to see how to use it properly. 💖")
        except:
            pass
    else:
        logger.error(f"Command error: {error}")
        logger.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@tasks.loop(seconds=30)
async def heartbeat_task():
    """Heartbeat to ensure the bot stays responsive"""
    global last_heartbeat
    last_heartbeat = time.time()
    logger.info(f"Heartbeat sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Update presence periodically
    try:
        activity = discord.Activity(type=discord.ActivityType.listening, name="commands | !help")
        await bot.change_presence(activity=activity)
    except Exception as e:
        logger.error(f"Error updating presence in heartbeat: {e}")

# Handle starting up the bot
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