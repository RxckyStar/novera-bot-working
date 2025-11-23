# ---------- safe-shutdown helper (added) ----------
async def _close_down():
    logger.info("[shutdown] flushing data to disk…")
    try:
        # force write of current member_data.json
        data_manager._save_data()
    except Exception as e:
        logger.exception("shutdown save failed: %s", e)
    # give OS time to sync buffers
    try:
        await asyncio.sleep(0.5)
    except Exception:
        pass
    logger.info("[shutdown] flush complete – safe to exit")

# ---------- signal handler (added) ----------
def _install_shutdown_handler(loop):
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(_close_down()))
        except NotImplementedError:
            # not available on this platform/event loop
            pass

#!/usr/bin/env python3
"""
Novera Assistant Discord Bot
----------------------------
A sophisticated Discord bot infrastructure designed to enhance server management.

---------------------------------------------------------------------------
| COMPREHENSIVE ASYNCIO FIX APPLIED                                        |
---------------------------------------------------------------------------
| - Fixed: Timeout context manager should be used inside a task            |
| - Fixed: asyncio.run() cannot be called from a running event loop        |
| - Fixed: This event loop is already running                              |
| - Fixed: Proper task creation and event loop management                  |
---------------------------------------------------------------------------
"""

# Apply comprehensive fix at the very start - MUST BE FIRST IMPORT
import discord_asyncio_fix
from discord_asyncio_fix import safe_wait_for, with_timeout
from timeout_handlers import wait_for_safe, with_timeout_safe
discord_asyncio_fix.apply_all_fixes()


import os
import sys
import logging
import discord
from discord.ext import commands, tasks
from discord import app_commands
import discord.ui as ui
import asyncio
import time
import math
import random
import re
import psutil
from typing import Optional, List, Union, Dict, Any, Tuple
from flask import Flask, jsonify
import threading
import utils
import atexit
import signal
from datetime import datetime, timedelta
import json
import subprocess
import traceback
from profanity_filter import ProfanityFilter
import moderation_tooltips  # Import our new moderation tooltips module
import importlib
import loading_animations
from data_manager import data_manager

# IMPORTANT: wait until bot = commands.Bot(...) is created before attaching
# DO NOT put bot.data_manager = data_manager here - bot doesn't exist yet

# Import proper connection error handling for Discord.py websocket connections
# Discord.py 2.0+ uses discord.errors.ConnectionClosed
try:
    from discord.errors import ConnectionClosed
    HAS_DISCORD_CONNECTION_CLOSED = True
except ImportError:
    ConnectionClosed = None
    HAS_DISCORD_CONNECTION_CLOSED = False

# For older versions or direct websocket handling, try these imports
try:
    # Try websockets v10+
    from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
    HAS_WEBSOCKETS_EXCEPTIONS = True
except ImportError:
    try:
        # Try websockets older versions
        from websockets.exceptions import ConnectionClosed as WebSocketConnectionClosed
        ConnectionClosedError = WebSocketConnectionClosed
        ConnectionClosedOK = WebSocketConnectionClosed
        HAS_WEBSOCKETS_EXCEPTIONS = True
    except ImportError:
        # Fallback option if imports fail
        ConnectionClosedError = None
        ConnectionClosedOK = None
        HAS_WEBSOCKETS_EXCEPTIONS = False
        
# Create a combined tuple of all the different connection error types 
# that might be used by Discord.py or websockets
ALL_CONNECTION_ERRORS = tuple(
    filter(None, [ConnectionClosed, ConnectionClosedError, ConnectionClosedOK])
)
# Note: We're using safe_wait_for from simple_discord_fix instead of the old implementation

# Import the moderation tooltip system
try:
    import moderation_tooltips
    MODERATION_TOOLTIPS_AVAILABLE = True
    logging.info("Moderation tooltips module loaded successfully")
except ImportError:
    logging.warning("Moderation tooltips module not available")
    MODERATION_TOOLTIPS_AVAILABLE = False

# Import our instance manager
from instance_manager import (
    claim_instance, release_instance, kill_other_instances, write_pid_file,
    WATCHDOG_PID_FILE, BOT_PID_FILE, WEB_PID_FILE
)

# Define global variables
bot_thread = None
bot_thread_alive = False

# Configure logging for better error tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

# Define command prefix
COMMAND_PREFIX = "!"

# Create bot instance with intents
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# ATTACH DATA MANAGER TO BOT - CRITICAL FIX
bot.data_manager = data_manager

# Then load your extensions...

# Enhanced token validation and import with fallback mechanism
try:
    # Check for token cache refresh flag first (from token_refresher.py)
    token_cache_refresh = os.path.exists("refresh_token_cache")
    if token_cache_refresh:
        try:
            os.remove("refresh_token_cache")
            logger.info("Token cache refresh flag detected - forcing token reload")
        except Exception:
            pass

    # Import from config with our enhanced token handling
    from config import TOKEN, COMMAND_PREFIX, DATA_FILE, get_token, load_token_from_cache, clean_token, validate_token

    if TOKEN is None:
        logger.critical("TOKEN is None from config, attempting emergency retrieval")
        try:
            # First try from environment with advanced validation
            TOKEN = get_token()
            logger.info("Successfully retrieved token from get_token()")
        except Exception as e:
            logger.critical(f"Emergency token retrieval failed: {e}")

            # Try loading directly from cache as last resort
            try:
                cached_token = load_token_from_cache()
                if cached_token:
                    TOKEN = cached_token
                    logger.warning("Using emergency cached token after get_token() failure")
                else:
                    logger.critical("No cached token available for emergency recovery")
                    TOKEN = None
            except Exception as cache_err:
                logger.critical(f"Cache retrieval also failed: {cache_err}")
                TOKEN = None

    # Final validation
    if TOKEN:
        # Clean the token to ensure it's correctly formatted
        TOKEN = clean_token(TOKEN)
        # Validate token format
        if not validate_token(TOKEN):
            logger.critical(f"Invalid token format: length={len(TOKEN)}, validation failed")
            # Seek a direct environment token as absolute last resort
            raw_token = os.environ.get('DISCORD_TOKEN')
            if raw_token and len(raw_token) >= 50:
                logger.warning("Using raw environment token as last resort")
                TOKEN = clean_token(raw_token)
            else:
                TOKEN = None

except ImportError as e:
    logger.critical(f"Failed to import config: {e}")
    # Fallback to direct env var with minimal validation
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN:
        TOKEN = TOKEN.strip().replace('"', '').replace("'", '')
    COMMAND_PREFIX = "!"
    DATA_FILE = "member_data.json"

    # Create very simple token cache if we have a valid token
    if TOKEN and len(TOKEN) >= 50:
        try:
            import json
            from datetime import datetime
            with open("token_cache.json", 'w') as f:
                json.dump({
                    "token": TOKEN,
                    "timestamp": datetime.now().isoformat(),
                    "validated": True,
                    "emergency": True
                }, f)
            logger.info("Created emergency token cache during import failure")
        except Exception as cache_err:
            logger.warning(f"Failed to create emergency token cache: {cache_err}")

from data_manager import DataManager
from activity_tracker import ActivityTracker
from utils import (
    has_value_management_role, format_ranking_message,
    get_random_spank_response, get_random_headpat_response,
    get_spank_warning_response, get_headpat_warning_response
)
from leaving_messages import LEAVING_MESSAGES  # Import leaving messages
# Import tryouts module for player evaluations
# We'll import only the module, not specific functions to avoid circular imports
import tryouts
import heartbeat_manager  # For ultra-reliability monitoring
logger.info("Successfully imported tryouts module")

# Initialize the active_tryouts dictionary and share it with the tryouts module
active_tryouts = {}
tryouts.set_active_tryouts(active_tryouts)

# Initialize the data manager and activity tracker
# data_manager = DataManager(DATA_FILE)  # old ctor – removed
activity_tracker = ActivityTracker(data_manager)
logger.info("Initialized data manager and activity tracker")

# =============================
# MOMMY PHRASE VARIANTS WITH EMOJIS
# =============================
MOMMY_ERROR_VARIANTS = [
    "😱 Oh dear, Mommy had a little boo boo! Please try again, sweetie! 😢",
    "😓 Oopsie, something went awry, my darling! Mommy is on it! 🌈",
    "😖 Oh no dear, Mommy's system just tripped over a rainbow! Try again, honey! 💕",
    "😞 Yikes, that didn't go as planned, sweetie! Mommy needs a moment! 😇",
    "😬 Whoopsie, Mommy encountered a tiny hiccup there! Please forgive me, darling! 😘",
    "🥺 Aww no, something went wrong in Mommy's circuits! Let's try that again, precious! 💫",
    "😅 Oops! Mommy stumbled a bit there! Give me another chance, sweetie! 🌸",
    "😔 Oh my, that didn't work quite right! Mommy needs to fix her makeup, darling! 🎀",
    "🤕 Ouchie! Mommy had a small accident! Let's give it another shot, love! 💝",
    "😳 Oh goodness, that wasn't supposed to happen! Mommy will do better, sweetheart! ✨"
]

MOMMY_SUCCESS_VARIANTS = [
    "🎉 Yay, Mommy is so proud of you, darling! Fantastic work! 💖",
    "👏 Hooray, you've done it, sweetie! Mommy loves your effort! 🌟",
    "🏆 Bravo, my precious! Mommy is absolutely delighted by your performance! 😍",
    "✨ Wonderful, darling—Mommy adores your work! Keep shining! 🌈",
    "💐 Splendid job, sweetheart! Mommy is cheering for you with all her heart! 💝",
    "🌺 You're making Mommy's heart flutter with joy, darling! Outstanding! 💫",
    "🎈 That's my talented little star! Mommy couldn't be more pleased! 🥰",
    "🌟 Look at you go, precious! Mommy's heart is bursting with pride! 💕",
    "🏅 Simply perfect, my love! You always know how to make Mommy smile! 🤗",
    "🌸 Magnificent work, sweetie! You're everything Mommy hoped for and more! 💖"
]

MOMMY_PERMISSION_DENIED = [
    "🚫 Oh dear, you don't have permission for that, my love! Please ask a staff member, darling! 🙅",
    "❌ Oopsie, you're not allowed to do that, sweetheart! Mommy says no, try again later! 🙇",
    "🙅 Oh no, darling, that command is off limits for you! Please be patient, sweetie! 🤗",
    "🛑 Yikes, permission denied, my dear! Mommy is sorry but you can't do that now! 😔",
    "❎ Oh dear, you lack the required permission, my love! Please check with staff, darling! 🤷",
    "🔒 Not so fast, precious! That's for special permissions only! Ask staff for help! 💕",
    "⛔ Aww honey, Mommy can't let you do that just yet! Speak with staff first! 🎀",
    "🚧 Hold on sweetie, that area is restricted! Let's get proper permission first! 💫",
    "⚠️ Sorry darling, but Mommy must protect her special commands! Ask staff nicely! 🌸",
    "🔐 That's under lock and key, my love! Get staff approval first! ✨"
]

MOMMY_CHECKVALUE_VARIANTS = [
    "💖 Darling, your value sparkles at ¥{value} million! Mommy is so proud of you! ✨",
    "💎 Sweetheart, your value shines at an amazing ¥{value} million—keep dazzling, my star! 🌟",
    "💰 Oh my, your value stands tall at ¥{value} million! Mommy is over the moon for you! 🎉",
    "🌈 Bravo, my precious! Your value is a fabulous ¥{value} million. Mommy loves your shine! 😍",
    "🔥 Darling, you're on fire with a value of ¥{value} million! Keep making Mommy proud! 🥰",
    "💫 Look at that gorgeous value of ¥{value} million! You're growing so beautifully! 🎀",
    "💝 Oh sweetie, ¥{value} million looks absolutely stunning on you! Keep climbing! 🌸",
    "✨ What a precious value of ¥{value} million! Mommy's little star is shining bright! 💖",
    "🌟 Darling, ¥{value} million suits you perfectly! You're becoming so valuable! 💫",
    "💅 Serving elegance with that ¥{value} million value! Mommy is living for it! 🎭",
    "💫 Oh la la! ¥{value} million value? Mommy thinks you're absolutely fabulous! 💃",
    "🌠 Sweetheart, your value of ¥{value} million has Mommy absolutely swooning! 😍",
    "💝 With a value of ¥{value} million, you're making Mommy's heart flutter! So proud! 🦋",
    "🏆 Darling, a value of ¥{value} million? You're becoming Mommy's champion! 🎖️",
    "💎 Mommy is blown away by your ¥{value} million value! You're becoming such a gem! 💍",
    "✨ Precious one, your ¥{value} million value has Mommy seeing stars! Keep shining! ⭐",
    "🌈 With ¥{value} million in value, you're painting Mommy's world with color! 🎨",
    "🚀 Shooting to the stars with that ¥{value} million value! Mommy's so impressed! 🌠",
    "👑 Wearing that ¥{value} million value like royalty! Mommy bows to you, my liege! 🧎‍♀️",
    "🌺 Blooming beautifully with a ¥{value} million value! Mommy loves watching you grow! 🌱"
]

MOMMY_LOW_VALUE_VARIANTS = [
    "💸 Only ¥{value} million? Darling, Mommy spends that much on a Gucci bag! You need to aim higher! 👜",
    "🤏 ¥{value} million? Is that all you've got, sweetie? Mommy's manicure costs more than that! 💅",
    "😒 Hmm, ¥{value} million... Mommy spent more than that on breakfast this morning. Do better, darling! 🍳",
    "🧐 ¥{value} million? Oh, bless your heart! That's barely enough to buy Mommy's favorite lipstick! 💄",
    "🙄 Darling, ¥{value} million is what Mommy tips her hairstylist! You're going to need to work harder! 💇‍♀️",
    "😬 Oh sweetie... ¥{value} million? Mommy's champagne costs more than that! Time to level up! 🍾",
    "👠 ¥{value} million wouldn't even buy one of Mommy's Louboutins, darling! Keep grinding! 👠",
    "🥱 Mommy yawns at your ¥{value} million value. That's pocket change for a bad bitch like me! 💰",
    "💳 ¥{value} million? Mommy spends that much on a single swipe of her credit card! Try harder, precious! 💳",
    "🤷‍♀️ ¥{value} million? Darling, Mommy misplaces more than that in her couch cushions! Do better! 🛋️",
    "👛 Oh honey, ¥{value} million is just the loose change in Mommy's purse! You're going to need more to impress me! 💵",
    "🍸 ¥{value} million? That's barely enough for Mommy's martini, sweetie! Keep hustling! 🍸",
    "👑 ¥{value} million is what Mommy pays her assistant to fetch coffee, darling! Aim higher! ☕",
    "💍 Oh dear, ¥{value} million wouldn't even buy the box for Mommy's jewelry! We need to work on this! 💎",
    "🧠 Mommy's thinking... ¥{value} million is cute, but it's giving 'allowance' not 'income'! Level up, sweetie! 📈",
    "👜 ¥{value} million? Mommy wouldn't even bend down to pick that up off the sidewalk! Try harder, love! 🚶‍♀️",
    "🎭 With ¥{value} million, you're still in the nosebleed section of life, darling! Mommy sits front row! 🎟️",
    "🛍️ Oh sweetie, ¥{value} million is what Mommy spends at duty-free! You've got potential though! ✈️",
    "🕶️ ¥{value} million? Mommy's sunglasses cost more, darling! But keep working, Mommy believes in you! 😎",
    "🥂 Hmm, ¥{value} million... That wouldn't even cover Mommy's weekend brunch! Keep grinding, sweetie! 🍽️"
]

# Responses for the !mommy command
MOMMY_RESPONSE_VARIANTS = [
    "💖 Yes, my darling? Mommy's here for you! 🥰",
    "💅 Did someone call for Mommy? How can I help you, sweetie? 💕",
    "👑 Mommy's attention is all yours, precious! What does my little one need? 💖",
    "🌸 Mommy heard her name! What can I do for you, my love? 💫",
    "💎 Yes, my treasure? Mommy's listening with her full attention! 🤗",
    "✨ Mommy's here, darling! Tell me what's on your mind! 💝",
    "🥂 You summoned Mommy, sweetheart? I'm all ears! 💓",
    "👠 Mommy has arrived! What can I assist you with, darling? 💞",
    "🧚‍♀️ Your wish is Mommy's command, precious! What do you need? 💗",
    "💋 Mommy's here now, sweetie! Let me take care of you! 💘"
]

MOMMY_ZERO_VALUE_VARIANTS = [
    "💖 Oh sweetie, your value is just starting to bloom at ¥0 million! Mommy believes in your potential! ✨",
    "🌱 Darling, everyone starts at ¥0 million! Mommy can't wait to see how you'll grow! 🌿",
    "🤗 No value yet, my precious? That just means you've got nowhere to go but up! Mommy's cheering for you! 📈",
    "💎 Value isn't just a number, sweetie! Your ¥0 million is just the beginning of your journey! 🚀",
    "🌟 Zero today, hero tomorrow! Mommy believes your value will skyrocket soon! 💫",
    "🔮 Mommy sees great value in your future, darling! Your ¥0 million is just temporary! ⏳",
    "💕 Sometimes the most precious gems start unpolished! Your ¥0 million value won't stay that way for long! 💍",
    "🌈 Don't worry about that ¥0 million, sweetie! Mommy knows you're priceless already! 💝",
    "🌠 Your star is just beginning to shine with ¥0 million! Mommy knows you'll be dazzling soon! ✨",
    "🤩 Oh darling, your value of ¥0 million just means you're a blank canvas ready for greatness! 🎨",
    "😂 ¥0 million? Oh honey, that's not a value, that's a void! Did you even try yet, sweetie? 🤭",
    "👻 ¥0 million? Darling, ghosts have more substance than your value right now! Time to materialize something! 💨",
    "🧮 Mommy's calculator is broken - it keeps saying your value is ¥0 million! Have you considered actually doing something? 🔧",
    "🔍 Mommy's looking for your value but all she sees is ¥0 million! Are you playing hide and seek with your potential? 🙈",
    "🏜️ Your value is like a desert mirage - Mommy can see ¥0 million when she gets close! Let's find some real water, shall we? 💦",
    "📉 With ¥0 million, your value chart is flatter than Mommy's champagne after a week! Let's add some bubbles, darling! 🍾",
    "🪫 Your value battery is showing ¥0 million! Have you tried turning yourself off and on again, sweetie? 🔌",
    "🦖 Your ¥0 million value is so extinct, it belongs in a museum with the dinosaurs! Let's evolve, shall we? 🧪",
    "👑 With ¥0 million, you're the undisputed monarch of the Nothing Kingdom! Ready to expand your territories, darling? 🗺️",
    "🌵 Your value of ¥0 million is like a cactus without spines - not even interesting enough to hurt! Add some personality, sweetie! 🌸",
    "🧊 ¥0 million? Mommy's seen more value in melting ice cubes! At least they become water eventually! ❄️",
    "🎮 ¥0 million? Darling, even NPCs have more utility than that! Are you playing the game or just decorating the screen? 🕹️",
    "📱 Your value of ¥0 million reminds Mommy of her phone at 1% - barely registering and about to disappear! Plug in, sweetie! 🔋",
    "🚫 ¥0 million? That's not a value, that's an error message! Have you tried actually participating, darling? 🔄",
    "🎭 With ¥0 million, you're playing the role of 'extra' in your own life story! Ready for a speaking part yet, sweetie? 🎬"
]

MOMMY_ACTIVITY_VARIANTS = [
    "🌟 Darling, your activity score is {activity}! Mommy loves your energy! 🔥",
    "🚀 Sweetheart, you've been super active with a score of {activity}! Mommy is impressed! 💪",
    "🎊 Oh my, you're buzzing with an activity score of {activity}! Keep it up, my love! 😘",
    "⚡ Bravo, my precious! Your activity level is {activity}! Mommy is cheering you on! 👏",
    "🌈 Darling, you're rocking it with an activity score of {activity}! Mommy is so proud! 🎉",
    "💫 Look at you go with an activity score of {activity}! Such a busy bee! 🐝",
    "🎯 Target achieved with {activity} activity points! Mommy loves your dedication! 💕",
    "🌺 Blooming beautifully with {activity} activity! You're growing so well! 🌱",
    "⭐ Shining bright with {activity} activity points! Keep sparkling, sweetie! ✨",
    "🎨 Painting the server active with a score of {activity}! Mommy's little artist! 🖌️"
]

# =============================
# GLOBAL DICTIONARIES FOR MATCHES & RESULTS
# =============================
active_matches = {}         # For match creation flows (keyed by creator id)
active_server_messages = {} # For server message interactive flows (keyed by author id)
active_matches_by_ad = {}   # {ad_message_id: MatchState} – live matches waiting for team joins
pending_results = {}        # {creator_id: MatchState} – finished matches pending result submission
pending_join_requests = {}  # For DM join requests

# =============================
# WEB SERVER FOR REPLIT AUTOSCALE
# =============================
app = Flask(__name__)
start_time = time.time()  # For uptime tracking
last_heartbeat = time.time()  # Track last activity for health checks

@app.route('/')
def home():
    return "🌟 Novera Assistant is up and running, darling! 🌟"

@app.route('/healthz')
def healthz():
    """Health check endpoint for monitoring"""
    bot_connected = bot is not None and bot.is_ready()
    last_heartbeat_age = time.time() - last_heartbeat if 'last_heartbeat' in globals() else 9999

    if not bot_connected:
        status = "disconnected"
    elif last_heartbeat_age > 120:
        status = "stalled"
    elif last_heartbeat_age > 60:
        status = "warning"
    else:
        status = "healthy"

    error_count = 0
    try:
        if os.path.exists("bot_errors.log"):
            file_mod_time = os.path.getmtime("bot_errors.log")
            if time.time() - file_mod_time < 3600:
                with open("bot_errors.log", "r") as f:
                    errors = f.readlines()
                    error_count = sum(1 for line in errors[-100:] if line.strip())
    except Exception as e:
        logging.error(f"Error counting recent errors: {e}")

    latency = -1
    try:
        if bot is not None and bot.is_ready() and bot.latency > 0:
            latency = round(bot.latency * 1000)
    except Exception as e:
        logging.error(f"Error getting bot latency: {e}")

    status_data = {
        "status": status,
        "uptime": int(time.time() - start_time),
        "bot_connected": bot_connected,
        "last_heartbeat_age": int(last_heartbeat_age),
        "pid": os.getpid(),
        "recent_errors": error_count,
        "latency_ms": latency,
        "guilds_count": len(bot.guilds) if bot is not None and bot.is_ready() else 0,
        "diagnostics": {
            "memory_usage_mb": psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024) if 'psutil' in sys.modules else -1,
            "cpu_percent": psutil.Process(os.getpid()).cpu_percent() if 'psutil' in sys.modules else -1,
            "thread_count": threading.active_count(),
            "connection_state": "connected" if bot_connected and hasattr(bot, 'ws') else "disconnected",
            "event_loop_active": True if bot_connected else False
        }
    }
    return jsonify(status_data)

@app.route('/monitor')
def monitor():
    """Monitoring endpoint for processed messages and bot state"""
    last_heartbeat_age = time.time() - last_heartbeat if 'last_heartbeat' in globals() else 9999

    if not bot.is_ready():
        bot_status = "disconnected"
    elif last_heartbeat_age > 120:
        bot_status = "stalled"
    elif last_heartbeat_age > 60:
        bot_status = "warning"
    else:
        bot_status = "healthy"

    status = {
        "status": bot_status,
        "uptime": int(time.time() - start_time),
        "pid": os.getpid(),
        "time": datetime.now().isoformat(),
        "last_heartbeat": last_heartbeat if 'last_heartbeat' in globals() else None,
        "heartbeat_age": int(last_heartbeat_age)
    }

    if hasattr(bot, "_processed_commands"):
        current_time = time.time()
        recent_messages = {}
        for msg_id, data in bot._processed_commands.items():
            msg_time = data.get('timestamp', 0)
            if current_time - msg_time < 60:
                recent_messages[msg_id] = data

        recent_entries = sorted(
            [(msg_id, data.get('timestamp', 0)) for msg_id, data in bot._processed_commands.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        recent_details = []
        for msg_id, _ in recent_entries:
            data = bot._processed_commands[msg_id]
            recent_details.append({
                "id": msg_id,
                "time": datetime.fromtimestamp(data.get('timestamp', 0)).isoformat(),
                "pid": data.get('pid', 'unknown'),
                "command": data.get('command', None)
            })

        status["processed_messages"] = {
            "total_count": len(bot._processed_commands),
            "recent_count": len(recent_messages),
            "recent_samples": recent_details
        }

    lock_files = [f for f in os.listdir('.') if f.startswith('message_') and f.endswith('.lock')]
    status["lock_files"] = {
        "count": len(lock_files),
        "samples": lock_files[:5] if lock_files else []
    }

    status["cache_file"] = {
        "exists": os.path.exists("processed_messages_cache.json"),
        "size": os.path.getsize("processed_messages_cache.json") if os.path.exists("processed_messages_cache.json") else 0,
        "modified": datetime.fromtimestamp(os.path.getmtime("processed_messages_cache.json")).isoformat() if os.path.exists("processed_messages_cache.json") else None
    }

    return jsonify(status)

@app.route('/restart', methods=['POST'])
def restart_bot_endpoint():
    """Endpoint to restart the bot"""
    try:
        if bot is not None:
            asyncio.create_task(bot.close())
        return jsonify({"status": "restarting", "message": "Bot restart initiated"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to restart: {str(e)}"}), 500

@app.route('/test_spill')
def test_spill():
    """Test the spill command with debug logging"""
    logging.info("Testing spill command via web route")
    guild = None
    for g in bot.guilds:
        guild = g
        break
    if not guild:
        return "No guilds found"
    try:
        from player_drama import PlayerDramaGenerator
        all_values = data_manager.get_all_member_values()
        if all_values:
            sorted_members = sorted(all_values.items(), key=lambda x: x[1], reverse=True)
            top_5 = sorted_members[:5]
            top_players = ', '.join([f'{member_id}: {value}' for member_id, value in top_5])
            logging.info(f"Top 5 highest value players: {top_players}")
        drama_generator = PlayerDramaGenerator(data_manager)
        logging.info(f"Generating drama for server {guild.id} with high-value threshold {drama_generator.high_value_threshold}")
        drama_scenario = drama_generator.generate_drama(guild)
        return f"<h1>Test Spill Command</h1><p>{drama_scenario}</p>"
    except Exception as e:
        logging.error(f"Error generating player drama: {e}", exc_info=True)
        return f"<h1>Error</h1><p>Failed to generate drama: {str(e)}</p>"

@app.route('/cron')
def cron_endpoint():
    """Cron-friendly endpoint that will restart the bot if it's not running
    This endpoint is designed to be called by a cron job every few minutes.
    If the bot is down, it will automatically restart it.
    """
    last_heartbeat_age = time.time() - last_heartbeat if 'last_heartbeat' in globals() else 9999
    is_healthy = False
    if bot is not None and bot.is_ready() and last_heartbeat_age < 120:
        is_healthy = True
        uptime = int(time.time() - start_time)
    else:
        uptime = None

    logging.info(f"Cron health check: Connected={bot is not None and bot.is_ready()}, Heartbeat age={int(last_heartbeat_age)}s, Healthy={is_healthy}")

    if not is_healthy:
        try:
            logging.warning("Cron endpoint detected unhealthy bot - triggering restart")
            def restart_thread():
                try:
                    if bot is not None:
                        asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
                    time.sleep(5)
                    for lock_file in ["bot.lock", "auto_401_recovery.pid", "401_recovery_startup.lock"]:
                        if os.path.exists(lock_file):
                            os.remove(lock_file)
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                except Exception as e:
                    logging.error(f"Failed in restart thread: {e}")
            threading.Thread(target=restart_thread, daemon=True).start()
            return jsonify({
                "status": "restarting",
                "message": "Bot was down - restart initiated"
            })
        except Exception as e:
            logging.error(f"Error restarting bot from cron endpoint: {e}")
            return jsonify({
                "status": "error",
                "message": f"Failed to restart bot: {str(e)}"
            }), 500

    return jsonify({
        "status": "ok",
        "bot_connected": True,
        "uptime": uptime
    })

def run_webserver():
    app.run(host="0.0.0.0", port=5001, debug=False)

def keep_alive():
    """Start the Flask server in a separate thread"""
    def run():
        app.run(host='0.0.0.0', port=5001)
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

# =============================
# SINGLE INSTANCE CHECK & CLEANUP
# =============================
LOCK_FILE = BOT_PID_FILE
PID_FILE = BOT_PID_FILE

def remove_lock_files():
    """Remove bot lock files with safety checks to prevent removing active locks"""
    current_pid = os.getpid()
    for file in [LOCK_FILE, PID_FILE]:
        if os.path.exists(file):
            try:
                with open(file, 'r') as f:
                    content = f.read().strip()
                    if content.isdigit():
                        file_pid = int(content)
                        if file_pid == current_pid:
                            logging.info(f"Removing our own lock file {file} with PID {file_pid}")
                            os.remove(file)
                        else:
                            try:
                                os.kill(file_pid, 0)
                                logging.warning(f"Lock file {file} with PID {file_pid} belongs to a running process, not removing (our PID: {current_pid})")
                            except OSError:
                                logging.info(f"Removing stale lock file {file} with PID {file_pid}")
                                os.remove(file)
                    else:
                        logging.info(f"Removing lock file {file} with non-PID content")
                        os.remove(file)
            except Exception as e:
                logging.error(f"Error processing lock file {file}: {e}")
                if "--force-remove-locks" in sys.argv:
                    try:
                        os.remove(file)
                        logging.warning(f"Forcibly removed lock file {file} due to --force-remove-locks flag")
                    except Exception as e2:
                        logging.error(f"Failed to forcibly remove {file}: {e2}")

def cleanup():
    """Perform any cleanup tasks before shutdown with ultra-reliability focus."""
    global bot_instance_claimed
    try:
        logging.info("Performing bot cleanup with enhanced reliability checks...")
        try:
            if os.path.exists("bot_running.lock"):
                os.remove("bot_running.lock")
                logging.info("Removed bot_running.lock during cleanup")
        except Exception as lock_err:
            logging.warning(f"Failed to remove running lock during cleanup: {lock_err}")
        try:
            if "DISCORDSDK_PROCESS_ID" in os.environ:
                del os.environ["DISCORDSDK_PROCESS_ID"]
                logging.info("Cleared DISCORDSDK_PROCESS_ID environment variable")
        except Exception as env_err:
            logging.warning(f"Failed to clear environment variable: {env_err}")
        try:
            release_instance(BOT_PID_FILE)
            bot_instance_claimed = False
            logging.info("Released bot instance in cleanup function")
        except Exception as release_err:
            logging.warning(f"Failed to release instance during cleanup: {release_err}")
        try:
            remove_lock_files()
            logging.info("Removed legacy lock files")
        except Exception as lock_removal_err:
            logging.warning(f"Error removing lock files: {lock_removal_err}")
        try:
            loop = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else None
            if loop:
                tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
                if tasks:
                    logging.info(f"Cancelling {len(tasks)} remaining asyncio tasks")
                    for task in tasks:
                        task.cancel()
        except Exception as task_err:
            logging.warning(f"Failed to cancel asyncio tasks: {task_err}")
        logging.info("Cleanup completed successfully, darling!")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

def start_bot_background():
    """Starts the Discord bot. This call is blocking so run it in a separate thread."""
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        from timeout_handlers import safe_task
        @safe_task
        async def start_bot():
            try:
                async with bot:
                    await bot.start(TOKEN)  # Removed reconnect=True parameter to fix intents error
            # Handle all known connection errors using the tuple we created
            except ALL_CONNECTION_ERRORS as e:
                logging.warning(f"Websocket connection closed unexpectedly: {e}")
                logging.info("Will automatically attempt to reconnect...")
                await asyncio.sleep(5)
            # Fallback for string-based error detection for unknown/future connection errors
            except Exception as e:
                error_type_str = str(type(e))
                if any(err_text in error_type_str for err_text in ["ConnectionClosed", "WebSocketClosed", "WebsocketClosed"]):
                    logging.warning(f"Websocket connection closed (string match): {e}")
                    logging.info("Will automatically attempt to reconnect...")
                    await asyncio.sleep(5)
                # Handle asyncio runtime errors
                elif "asyncio.run() cannot be called from a running event loop" in str(e):
                    logging.warning(f"Asyncio runtime error detected: {e}")
                    logging.info("This is expected in some cases, continuing execution...")
                    # Don't raise - allow the program to continue
                elif "This event loop is already running" in str(e):
                    logging.warning(f"Event loop is already running: {e}")
                    logging.info("This is expected in some environments, continuing execution...")
                    # Don't raise - allow the program to continue
                else:
                    logging.critical(f"Bot startup failed: {e}")
                    raise
        loop.create_task(start_bot())
        loop.run_forever()
    except Exception as e:
        logging.critical(f"Bot encountered an error: {e}")
        raise

def keep_alive_and_run_bot():
    """Start the Flask web server ONLY - bot startup is handled in __main__
    This function has been refactored to prevent event loop conflicts.
    """
    error_log_file = f"bot_errors.log"
    error_logger = logging.getLogger("bot_errors")
    error_logger.setLevel(logging.ERROR)
    if not error_logger.handlers:
        error_handler = logging.FileHandler(error_log_file)
        error_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        error_logger.addHandler(error_handler)
    from task_wrapper import ensure_task, safe_timeout
    @ensure_task
    async def check_bot_health_async():
        try:
            import aiohttp
            async with safe_timeout(3.0):
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:5001/healthz") as response:
                        if response.status == 200:
                            data = await response.json()
                            bot_pid = data.get("pid")
                            if bot_pid and psutil.pid_exists(bot_pid):
                                logging.info(f"Found healthy bot instance running with PID {bot_pid}")
                                return True
                        return False
        except Exception as e:
            logging.error(f"Error checking bot health: {e}")
            return False
    def is_bot_responding():
        try:
            import requests
            response = requests.get("http://localhost:5001/healthz", timeout=3)
            if response.status_code == 200:
                data = response.json()
                bot_pid = data.get("pid")
                if bot_pid and psutil.pid_exists(bot_pid):
                    logging.info(f"Found healthy bot instance running with PID {bot_pid}")
                    return True
            return False
        except Exception:
            return False
    if is_bot_responding():
        logging.info("Bot is already running and responding to health checks. Exiting to prevent duplicates.")
        return
    try:
        killed_pids = kill_other_instances(r"python.*bot\.py", force=True)
        if killed_pids:
            logging.info(f"Killed stale bot processes: {killed_pids}")
            time.sleep(2)
    except Exception as e:
        logging.warning(f"Error when trying to kill stale processes: {e}")
    while True:
        bot_instance_claimed = False
        try:
            if not claim_instance(BOT_PID_FILE, "bot.py"):
                logging.error(f"Bot already running with PID in {BOT_PID_FILE}, exiting to prevent duplicates.")
                try:
                    with open(BOT_PID_FILE, 'r') as f:
                        pid = int(f.read().strip())
                    if not psutil.pid_exists(pid):
                        logging.warning(f"Found stale PID file for non-existent process {pid}. Removing.")
                        os.remove(BOT_PID_FILE)
                        continue
                except (FileNotFoundError, ValueError, PermissionError) as e:
                    logging.warning(f"Error checking PID file: {e}")
                time.sleep(30)
                continue
            bot_instance_claimed = True
            logging.info(f"Bot claimed instance with PID: {os.getpid()} using improved instance management")
            debug_pid = os.getpid()
            logging.debug(f"Bot initialization with process ID: {debug_pid}")
            keep_alive()
            logging.info("Flask web server started on port 5001, darling!")
            time.sleep(1)
            retry_count = 0
            backoff_time = 5
            try:
                if not TOKEN:
                    logging.warning("TOKEN is missing, attempting emergency token retrieval")
                    from importlib import reload
                    import config as config_module
                    reload(config_module)
                    clean_token_final = config_module.TOKEN
                    if not clean_token_final:
                        raise ValueError("Failed to retrieve token after reload")
                else:
                    clean_token_final = TOKEN
                if isinstance(clean_token_final, str):
                    clean_token_final = clean_token_final.strip().strip('"').strip("'")
                    if '\\' in clean_token_final:
                        try:
                            clean_token_final = clean_token_final.encode().decode('unicode_escape')
                            logging.info("Successfully decoded escape sequences in token")
                        except Exception as e:
                            logging.warning(f"Failed to decode escape sequences: {e}")
                    token_match = re.search(r'[A-Za-z0-9_\-\.]{59,100}', clean_token_final)
                    if token_match:
                        extracted = token_match.group(0)
                        if extracted != clean_token_final:
                            logging.info("Extracted token from larger string")
                            clean_token_final = extracted
                logging.info(f"Starting bot with token of length: {len(clean_token_final) if clean_token_final else 0}")
                logging.info("Starting Discord bot with robust event loop and task handling")
                time.sleep(1)
                
                try:
                    # Use the specially designed timeout handlers for safer operation
                    from timeout_handlers import safe_task, ensure_proper_startup, wait_for_safe, cleanup_loop
                    
                    # Use our robust task_wrapper module to handle all event loop and task context issues
                    from task_wrapper import run_with_task_context
                    from timeout_handlers import ensure_proper_startup
                    
                    @ensure_proper_startup
                    async def start_bot_properly():
                        """Start the bot with proper task context and error handling"""
                        try:
                            logging.info("Starting bot with robust task context handling")
                            await bot.start(clean_token_final)
                        except Exception as start_error:
                            logging.critical(f"Error in bot startup: {start_error}", exc_info=True)
                            raise
                    
                    try:
                        # Use our advanced runner that handles all asyncio edge cases
                        logging.info("Using robust task_wrapper.run_with_task_context to avoid event loop issues")
                        run_with_task_context(start_bot_properly())
                    except RuntimeError as e:
                        # If we still somehow get an error, handle it
                        logging.error(f"RuntimeError despite robust handling: {e}")
                        if "Timeout context manager should be used inside a task" in str(e):
                            logging.error(f"Timeout context manager error detected: {e}")
                            logging.info("Attempting recovery with proper task context")
                            
                            # Try the task-aware approach
                            @ensure_proper_startup
                            async def start_bot_with_task_context():
                                try:
                                    async with bot:
                                        await bot.start(clean_token_final)
                                except Exception as inner_e:
                                    logging.error(f"Error in task-context startup: {inner_e}")
                                    raise
                            
                            # Execute with proper task context
                            start_bot_with_task_context()
                            
                        elif "asyncio.run() cannot be called from a running event loop" in str(e):
                            logging.warning("Event loop error detected; using thread-based approach")
                            
                            # Use a separate thread with its own event loop
                            def run_bot_in_thread():
                                try:
                                    # Create a fresh event loop in this thread
                                    new_loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(new_loop)
                                    
                                    @safe_task
                                    async def start_in_thread():
                                        try:
                                            async with bot:
                                                await bot.start(clean_token_final)
                                        except Exception as thread_e:
                                            logging.error(f"Error in threaded bot startup: {thread_e}")
                                    
                                    # Run until complete (will block this thread)
                                    logging.info("Starting bot with dedicated thread and event loop")
                                    new_loop.run_until_complete(start_in_thread())
                                except Exception as thread_err:
                                    logging.error(f"Thread startup error: {thread_err}")
                                    
                            # Start thread and setup watchdog
                            global bot_thread, bot_thread_alive
                            bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
                            bot_thread_alive = True
                            bot_thread.start()
                            
                            # Create watchdog in separate thread
                            def bot_watchdog():
                                check_interval = 30
                                max_downtime = 60
                                while True:
                                    try:
                                        if not bot_thread.is_alive():
                                            logging.warning("Bot thread died; restarting")
                                            # Restart the thread
                                            bot_thread = threading.Thread(
                                                target=run_bot_in_thread, daemon=True)
                                            bot_thread.start()
                                        
                                        # Check heartbeat
                                        current_time = time.time()
                                        if hasattr(bot, 'last_heartbeat'):
                                            age = current_time - bot.last_heartbeat
                                            if age > max_downtime:
                                                logging.warning(f"Heartbeat too old: {age}s; restarting")
                                                # Force restart
                                                bot_thread = threading.Thread(
                                                    target=run_bot_in_thread, daemon=True)
                                                bot_thread.start()
                                    except Exception as watchdog_err:
                                        logging.error(f"Watchdog error: {watchdog_err}")
                                    
                                    # Sleep between checks
                                    time.sleep(check_interval)
                            
                            # Start watchdog
                            watchdog_thread = threading.Thread(target=bot_watchdog, daemon=True)
                            watchdog_thread.start()
                        else:
                            # For other runtime errors, raise
                            raise
                    
                except Exception as outer_e:
                    logging.critical(f"Critical bot startup error: {outer_e}", exc_info=True)
                    raise
                
                # This function was moved outside the block to avoid indentation issues
                logging.info("Bot.run() completed normally - likely due to intentional shutdown")
                try:
                    if os.path.exists("bot_running.lock"):
                        os.remove("bot_running.lock")
                except Exception as unlock_err:
                    logging.warning(f"Failed to remove running lock file: {unlock_err}")
                cleanup()
                break
            except discord.errors.HTTPException as e:
                error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                error_logger.error(f"HTTP error: {e}")
                if e.status == 429:
                    logging.critical(f"Discord rate limit hit: {e} - implementing exponential backoff")
                    last_error = f"{error_time} - Rate limit error: {e}"
                    retry_count += 1
                    time.sleep(min(backoff_time * 2, 300))
                else:
                    logging.critical(f"Discord HTTP error: {e}")
                    last_error = f"{error_time} - HTTP error: {e}"
                    retry_count += 1
            except discord.errors.LoginFailure as e:
                error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                error_logger.error(f"Authentication failed: {e}")
                logging.critical(f"Discord login failed (token issue): {e}")
                try:
                    with open("refresh_token_cache", "w") as f:
                        f.write(str(time.time()))
                    logging.info("Created refresh_token_cache flag to force token refresh")
                except Exception as write_err:
                    logging.warning(f"Failed to create token refresh flag: {write_err}")
                try:
                    new_token = os.environ.get("DISCORD_TOKEN", "")
                    if new_token and new_token != clean_token_final:
                        logging.info("Found new token in environment, will use on next attempt")
                except Exception:
                    pass
                last_error = f"{error_time} - Authentication failed: {e}"
                retry_count += 1
                time.sleep(backoff_time)
            except Exception as e:
                error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if ALL_CONNECTION_ERRORS and isinstance(e, ALL_CONNECTION_ERRORS):
                    error_logger.warning(f"ConnectionClosed error: {e}")
                    logging.warning(f"Websocket connection closed: {e}")
                    last_error = f"{error_time} - Connection closed: {e}"
                    time.sleep(3)
                # Fallback for string-based error detection
                elif any(err_text in str(type(e)) for err_text in ["ConnectionClosed", "WebSocketClosed", "WebsocketClosed"]):
                    error_logger.warning(f"ConnectionClosed error (string match): {e}")
                    logging.warning(f"Websocket connection closed (string match): {e}")
                    last_error = f"{error_time} - Connection closed: {e}"
                    time.sleep(3)
                else:
                    error_logger.error(f"Unexpected error: {e}")
                    error_logger.error(traceback.format_exc())
                    logging.critical(f"Unexpected error in bot.run(): {e}", exc_info=True)
                    last_error = f"{error_time} - Unexpected error: {e}"
                    retry_count += 1
            finally:
                try:
                    if os.path.exists("bot_running.lock"):
                        os.remove("bot_running.lock")
                        logging.info("Removed bot_running.lock in finally block")
                except Exception as lock_err:
                    logging.warning(f"Failed to remove lock file in finally: {lock_err}")
                try:
                    loop = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else None
                    if loop:
                        tasks = asyncio.all_tasks(loop=loop) if hasattr(asyncio, 'all_tasks') else asyncio.Task.all_tasks(loop=loop)
                        for task in tasks:
                            if task != asyncio.current_task(loop=loop):
                                task.cancel()
                        logging.debug(f"Waiting for {len(tasks)} tasks to cancel")
                        try:
                            pending_tasks = [t for t in tasks if not t.done() and t != asyncio.current_task(loop=loop)]
                            if pending_tasks:
                                wait_task = asyncio.gather(*pending_tasks, return_exceptions=True)
                                async def wait_task_with_timeout(task, timeout):
                                    try:
                                        return await safe_wait_for(task, timeout)
                                    except (asyncio.TimeoutError, Exception):
                                        return None
                                loop.run_until_complete(wait_task_with_timeout(wait_task, 2.0))
                        except (asyncio.CancelledError, asyncio.TimeoutError, Exception) as wait_err:
                            logging.debug(f"Task cancellation wait completed: {wait_err}")
                except Exception as task_err:
                    logging.warning(f"Error during task cleanup: {task_err}")
                cleanup()
                if bot_instance_claimed:
                    try:
                        release_instance(BOT_PID_FILE)
                        bot_instance_claimed = False
                        logging.info("Successfully released bot instance in finally block")
                    except Exception as e:
                        logging.error(f"Failed to release instance: {e}")
            backoff_time = min(backoff_time * 1.5, max_backoff)
            logging.warning(f"Retry {retry_count} - Waiting {backoff_time:.1f}s before next attempt. Last error: {last_error}")
            time.sleep(backoff_time)
        except Exception as outer_e:
            error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_logger.critical(f"Critical error in restart loop: {outer_e}")
            error_logger.critical(traceback.format_exc())
            logging.critical(f"Critical error in bot restart logic: {outer_e}", exc_info=True)
            if bot_instance_claimed:
                try:
                    release_instance(BOT_PID_FILE)
                    bot_instance_claimed = False
                except Exception:
                    pass
            time.sleep(60)
    # End of keep_alive_and_run_bot()

# Define a heartbeat task that updates the last_heartbeat time
@tasks.loop(seconds=30)
async def update_heartbeat():
    """Update the bot heartbeat timestamp periodically to show it's alive"""
    global last_heartbeat
    last_heartbeat = time.time()
    logging.debug(f"Heartbeat updated at {datetime.now().strftime('%H:%M:%S')}")

@bot.event
async def on_ready():
    # Start heartbeat monitoring for ultra reliability
    heartbeat_manager.start_heartbeat_async()
    global last_heartbeat, profanity_filter
    logging.info(f"Bot connected as {bot.user}")
    last_heartbeat = time.time()
    guild_list = []
    for guild in bot.guilds:
        guild_list.append(f"{guild.name} (ID: {guild.id})")
    logging.info(f"Connected to {len(bot.guilds)} servers: {', '.join(guild_list)}")
    
    # Initialize profanity filter
    if not hasattr(bot, 'profanity_filter'):
        bot.profanity_filter = ProfanityFilter(bot)
        logging.info("Initialized profanity filter for language moderation")
    
    # Initialize team tickets system
    try:
        import team_tickets
        team_tickets.setup(bot)
        logging.info("Team tickets system initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize team tickets system: {e}")
    
    # Register persistent views
    try:
        from team_tickets import TeamRequestView
        from server_walkthrough import ServerGuideView
        
        # Add persistent views
        bot.add_view(TeamRequestView())
        logging.info("Registered persistent TeamRequestView for ticket buttons")
        
        # Register WagerMatchView for persistence (with default empty parameters and unique wager_id)
        timestamp = int(datetime.now().timestamp())
        for match_type in ["1v1", "2v2", "3v3", "5v5"]:
            # Create a unique persistent view for each match type
            try:
                wager_id = f"persistent_{match_type}_{timestamp}"
                dummy_view = WagerMatchView(
                    creator=bot.user,
                    match_type=match_type,
                    amount=0,
                    region="Any",
                    abilities=True
                )
                # Add specific buttons for each match type's persistent view
                for team_id in [1, 2]:
                    max_slots = 1  # Default for 1v1
                    if match_type == "2v2":
                        max_slots = 2
                    elif match_type == "3v3":
                        max_slots = 3
                    elif match_type == "5v5":
                        max_slots = 5
                    
                    for slot_id in range(1, max_slots + 1):
                        # Add dummy buttons with unique custom_ids for each slot position
                        dummy_button = JoinWagerButton(
                            slot_id=slot_id,
                            team_id=team_id,
                            match_type=match_type,
                            wager_id=timestamp,
                            filled=(team_id == 1 and slot_id == 1),  # Creator's slot is filled
                            user=(bot.user if team_id == 1 and slot_id == 1 else None)
                        )
                        dummy_view.add_item(dummy_button)
                
                bot.add_view(dummy_view)
                logging.info(f"Registered persistent WagerMatchView for {match_type} matches")
                
                # Also register TeamSelectView and ModVerifyView for the match results system
                try:
                    # Add a persistent TeamSelectView with a unique ID
                    # Set persistent=True to ensure proper registration
                    team_select_dummy = TeamSelectView(bot.user, persistent=True)
                    bot.add_view(team_select_dummy)
                    logging.info(f"Registered persistent TeamSelectView for match results")
                except Exception as team_select_error:
                    logging.error(f"Failed to register TeamSelectView: {team_select_error}")
                    
                try:
                    # Add a persistent ModVerifyView with dummy match info
                    dummy_match_info = {
                        "submitter_id": str(bot.user.id),
                        "submitter_name": bot.user.name,
                        "winner": 1,
                        "screenshot_url": "",
                        "timestamp": datetime.now().isoformat(),
                        "match_type": match_type,
                        "amount": 0,
                        "teams": {
                            "team1": [str(bot.user.id)],
                            "team2": []
                        }
                    }
                    # Set persistent=True to ensure proper registration with stable IDs
                    mod_verify_dummy = ModVerifyView(dummy_match_info, persistent=True)
                    bot.add_view(mod_verify_dummy)
                    logging.info(f"Registered persistent ModVerifyView for match verification")
                except Exception as mod_verify_error:
                    logging.error(f"Failed to register ModVerifyView: {mod_verify_error}")
            except Exception as e:
                logging.error(f"Error registering persistent WagerMatchView for {match_type}: {e}")
        
       # ------------------------------------------------------------
        logging.info("ServerGuideView is registered per-user via welcome messages")
        
        # Look for existing team tickets message
        try:
            ticket_channel = bot.get_channel(1350177702778245172)
            if ticket_channel:
                async for message in ticket_channel.history(limit=50):
                    if message.author == bot.user and "Team Creation Requests" in message.content:
                        logging.info(f"Found existing ticket message with ID {message.id}")
                        break
        except Exception as e:
            logging.error(f"Error finding ticket message: {e}")
            
    except Exception as view_error:
        logging.error(f"Error registering persistent views: {view_error}")
    
    if not update_heartbeat.is_running():
        update_heartbeat.start()

# ---------- safe shutdown (top-level) ----------
try:
    _install_shutdown_handler(bot.loop)
    logging.info("Shutdown handler installed")
except Exception as e:
    logging.error(f"Failed to install shutdown handler: {e}")

@bot.command(name="checkvalue")
async def checkvalue_command(ctx, member: Optional[discord.Member] = None):
    """Check the user's yen value."""
    logging.info(f"Processing checkvalue command for message ID {ctx.message.id}")

    try:
        # --- Load the SAME DataManager instance used by everything else ---
        from data_manager import data_manager as mgr

        if mgr is None:
            await ctx.send(
                "😔 Oh no darling, Mommy can't access your value records right now! Try again later, sweetie! 💕"
            )
            return

        if not member:
            member = ctx.author

        # start loading animation
        animator = loading_animations.LoadingAnimator(ctx)
        await animator.start()

        user_id = str(member.id)

        # ✔️ FIX: use sync methods (NO await)
        value = mgr.get_member_value(user_id)

        # ranking data
        try:
            rank, total, _ = mgr.get_member_ranking(user_id)
            percentile = max(1, min(99, int((rank / max(total, 1)) * 100)))
            ranking_text = (
                format_ranking_message(rank, total, value, True)
                + f"\n*Top {percentile}% of all players*"
            )
        except Exception as e:
            logging.error(f"Ranking error: {e}")
            ranking_text = "Ranking information not available right now."

        # mommy text logic
        if value == 0 and ctx.guild and str(ctx.guild.id) == "1350165280940228629":
            evaluator_channel = ctx.guild.get_channel(1350182132043223090)
            chan = evaluator_channel.mention if evaluator_channel else "#evaluator"
            message = (
                f"Your value is **0**!\n\n"
                f"Oh sweetie, you don't have any value yet! "
                f"Please head over to {chan} and ask an evaluator for a tryout~ 💕"
            )
        elif value > 10:
            message = random.choice(MOMMY_CHECKVALUE_VARIANTS).format(value=value)
        elif value > 0:
            message = random.choice(MOMMY_LOW_VALUE_VARIANTS).format(value=value)
        else:
            message = random.choice(MOMMY_ZERO_VALUE_VARIANTS).format(value=value)

        # embed
        embed = discord.Embed(
            title=f"✨ {member.display_name}'s Value ✨",
            description=message,
            color=discord.Color.purple()
        )
        embed.add_field(name="Ranking", value=ranking_text, inline=False)

        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        # finish animation with embed
        await animator.stop(final_embed=embed)

        logging.info(
            f"Checkvalue OK for {user_id} — value {value}"
        )

    except Exception as e:
        logging.error(f"Error in checkvalue: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(
                f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*"
            )
        except:
            pass

@bot.command(name="checkgold")
async def checkgold_command(ctx, member: Optional[discord.Member] = None):
    """Check the user's gold balance from the data manager"""
    logging.info(f"Checkgold command received from {ctx.author.name} (ID: {ctx.author.id})")
    
    try:
        if member is None:
            member = ctx.author
            
        user_id = str(member.id)
        
        animator = loading_animations.LoadingAnimator(ctx, "💰", f"Checking gold balance for {member.display_name}...")
        await animator.start()
        
        gold = data_manager.get_member_gold(user_id)
        
        possessive = "your" if member == ctx.author else member.display_name + "'s"
        embed = discord.Embed(
            title="💰 Gold Balance 💰",
            description=f"Here's {possessive} current gold balance, darling~",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Gold", value=f"{gold:,} 💰", inline=True)
        
        if gold > 10000:
            embed.add_field(name="Status", value="🤑 Incredibly wealthy!", inline=False)
        elif gold > 5000:
            embed.add_field(name="Status", value="💎 Very rich!", inline=False)
        elif gold > 1000:
            embed.add_field(name="Status", value="💵 Well-off", inline=False)
        elif gold > 500:
            embed.add_field(name="Status", value="💰 Comfortable", inline=False)
        elif gold > 100:
            embed.add_field(name="Status", value="👛 Getting by", inline=False)
        elif gold > 0:
            embed.add_field(name="Status", value="🪙 Just starting out", inline=False)
        else:
            embed.add_field(name="Status", value="📉 Broke...", inline=False)
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
            
        await animator.stop(final_embed=embed)
        logging.info(f"Checkgold command executed by {ctx.author} for {user_id} - gold: {gold}")
        
    except Exception as e:
        error_msg = f"Error in checkgold command: {e}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        try:
            await ctx.send(f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*")
        except:
            pass

@bot.command(name="goldrush")
async def goldrush_command(ctx):
    """Show the top gold holders in the server for the Gold Rush Marathon"""
    logging.info(f"Gold Rush rankings command received from {ctx.author.name} (ID: {ctx.author.id})")
    
    tasks = []
    loading_msg = None
    
    try:
        if not ctx.guild:
            await ctx.send("This command can only be used in a server, sweetie~ 💖")
            return
        
        try:
            loading_msg = await ctx.send("🔄 Calculating Gold Rush leaderboard...")
        except Exception as send_error:
            logging.error(f"Failed to send loading message: {send_error}")
        
        async def fetch_gold_data():
            return data_manager.get_all_member_gold()
        
        gold_task = asyncio.create_task(fetch_gold_data())
        tasks.append(gold_task)
        
        member_gold = await simple_discord_fix.with_timeout(gold_task, timeout_seconds=10)
        
        if not member_gold:
            msg = "No members have any gold yet, darling~ 💖\nParticipate in events to earn gold during the Gold Rush Marathon!"
            if loading_msg:
                await loading_msg.edit(content=msg)
            else:
                await ctx.send(msg)
            return
            
        guild_member_gold = {}
        for member_id, gold in member_gold.items():
            if gold <= 0:
                continue
            try:
                member = ctx.guild.get_member(int(member_id))
                if member:
                    guild_member_gold[member_id] = gold
            except ValueError:
                logging.warning(f"Invalid member ID in gold data: {member_id}")
                continue
            
        if not guild_member_gold:
            msg = "No members in this server have any gold yet, sweetie~ 💖\nParticipate in events to earn gold during the Gold Rush Marathon!"
            if loading_msg:
                await loading_msg.edit(content=msg)
            else:
                await ctx.send(msg)
            return
            
        sorted_members = sorted(guild_member_gold.items(), key=lambda x: x[1], reverse=True)
        
        embed = discord.Embed(
            title="🏆 Gold Rush Marathon Leaderboard 🏆",
            description=f"The richest gold miners in **{ctx.guild.name}**:",
            color=discord.Color.gold()
        )
        
        rank_emojis = {1: "👑", 2: "💰", 3: "💎", 4: "🌟", 5: "✨",
                       6: "💫", 7: "🏅", 8: "🪙", 9: "💵", 10: "🔮"}
        
        count = 0
        for member_id, gold in sorted_members[:10]:
            count += 1
            try:
                member = ctx.guild.get_member(int(member_id))
                if member:
                    emoji = rank_emojis.get(count, "⭐")
                    embed.add_field(
                        name=f"{emoji} #{count}: {member.display_name}",
                        value=f"**{gold:,}** gold coins",
                        inline=False
                    )
            except Exception as field_error:
                logging.error(f"Error adding field for member {member_id}: {field_error}")
                continue
        
        if count >= 10:
            embed.set_footer(text="The Gold Rush is heating up! Many miners are competing for glory! • Gold Rush Marathon 2025")
        elif count >= 5:
            embed.set_footer(text="The Gold Rush is going strong! Will you climb the ranks? • Gold Rush Marathon 2025")
        else:
            embed.set_footer(text="The Gold Rush has just begun! Now's your chance to take the lead! • Gold Rush Marathon 2025")
        
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
            
        async def send_embed():
            await ctx.send(embed=embed)
            
        send_task = asyncio.create_task(send_embed())
        tasks.append(send_task)
        await simple_discord_fix.with_timeout(send_task, timeout_seconds=10)
        
        if loading_msg:
            try:
                delete_task = asyncio.create_task(loading_msg.delete())
                tasks.append(delete_task)
                await simple_discord_fix.with_timeout(delete_task, timeout_seconds=5)
            except Exception as delete_error:
                logging.warning(f"Error deleting loading message: {delete_error}")
        
    except asyncio.TimeoutError:
        logging.error("Timeout in goldrush_command")
        msg = "The Gold Rush leaderboard is taking too long to calculate. Please try again later, darling~"
        if loading_msg:
            await loading_msg.edit(content=msg)
        else:
            await ctx.send(msg)
    except Exception as e:
        logging.error(f"Error in goldrush_command: {e}", exc_info=True)
        msg = "Oops! Something went wrong with the Gold Rush leaderboard. Please try again later, darling~"
        try:
            if loading_msg:
                await loading_msg.edit(content=msg)
            else:
                await ctx.send(msg)
        except Exception as send_error:
            logging.error(f"Failed to send error message: {send_error}")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as cleanup_error:
                logging.error(f"Error during task cleanup: {cleanup_error}")
@bot.command(name="confess")
async def confess_command(ctx):
    """Mommy confesses what she's been up to"""
    # Debug logging
    logging.warning(f"CONFESS COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id})")
        
    try:
        # Start loading animation
        animator = loading_animations.LoadingAnimator(ctx)
        await animator.start()
        
        # Get server-specific response
        server_id = None
        if ctx.guild:
            server_id = str(ctx.guild.id)
            
        # Get a server-appropriate response
        response = utils.get_confess_response(ctx.message, data_manager)
        
        # Create a visually appealing embed for the confession
        embed = discord.Embed(
            title="💋 Mommy's Secret Confession 💋",
            description=response,
            color=discord.Color.dark_magenta()
        )
        
        # Add random emoji decorations to make it more dynamic
        decorative_emojis = ["💖", "✨", "💅", "👑", "💎", "🔮", "🍸", "💄", "👠", "🌹"]
        random_emoji = random.choice(decorative_emojis)
        
        # Add author image if bot has an avatar
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
            
        # Add footer with timestamp
        embed.set_footer(text=f"{random_emoji} Mommy's little secrets... {random_emoji}")
        embed.timestamp = ctx.message.created_at
        
        # Stop animation and show the result
        await animator.stop(final_embed=embed)
        logging.info(f"Confess command executed by {ctx.author}")
    except Exception as e:
        logging.error(f"Error in confess command: {e}")
        logging.error(traceback.format_exc())
        try:
            # Use embed for errors too
            error_embed = discord.Embed(
                title="❌ Oh no!",
                description=random.choice(MOMMY_ERROR_VARIANTS),
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"Error details: {str(e)[:100]}")
            await ctx.send(embed=error_embed)
        except Exception as send_error:
            logging.error(f"Failed to send error message: {send_error}")
            # Last resort plain text
            try:
                await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
            except:
                pass

@bot.command(name="shopping")
async def shopping_command(ctx):
    """Reveal Mommy's latest luxury purchases"""
    # Debug logging
    logging.warning(f"SHOPPING COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id})")
        
    try:
        # Start loading animation
        animator = loading_animations.LoadingAnimator(ctx)
        await animator.start()
        
        response = utils.get_shopping_response(ctx.message, data_manager)
        
        # Create a luxurious embed for the shopping response
        embed = discord.Embed(
            title="💎 Mommy's Luxury Shopping Spree 💎",
            description=response,
            color=discord.Color.teal()
        )
        
        # Add decorative elements for a luxury feel
        luxury_emojis = ["👑", "💰", "💎", "💄", "👠", "👜", "💍", "🛍️", "🏆", "🥂"]
        random_emoji = random.choice(luxury_emojis)
        
        # Add bot avatar if available
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
            
        # Add sophisticated footer with timestamp
        embed.set_footer(text=f"{random_emoji} Only the finest for Mommy {random_emoji}")
        embed.timestamp = ctx.message.created_at
        
        # Stop animation and show the result
        await animator.stop(final_embed=embed)
        logging.info(f"Shopping command executed by {ctx.author}")
    except Exception as e:
        logging.error(f"Error in shopping command: {e}")
        logging.error(traceback.format_exc())
        try:
            # Enhanced error handling with embed
            error_embed = discord.Embed(
                title="❌ Shopping Error",
                description=random.choice(MOMMY_ERROR_VARIANTS),
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"Error details: {str(e)[:100]}")
            await ctx.send(embed=error_embed)
        except Exception as send_error:
            logging.error(f"Failed to send error message: {send_error}")
            # Last resort plain text
            try:
                await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
            except:
                pass
@bot.command(hidden=True)
@commands.is_owner()
async def load(ctx, ext):
    await bot.load_extension(f"cogs.{ext}")
    await ctx.send(f"✅ `{ext}` loaded")

@bot.command(hidden=True)
@commands.is_owner()
async def reload(ctx, ext):
    await bot.reload_extension(f"cogs.{ext}")
    await ctx.send(f"🔄 `{ext}` reloaded")
    
@bot.command(name="spill")
async def spill_command(ctx):
    """Share juicy gossip about Novarians"""
    # Debug logging
    logging.warning(f"SPILL COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id})")
        
    try:
        # Start loading animation
        animator = loading_animations.LoadingAnimator(ctx)
        await animator.start()
        
        response = utils.get_spill_response(ctx.message, data_manager)
        
        # Create a gossip-themed embed for the spill response
        embed = discord.Embed(
            title="🍵 Mommy's Juicy Gossip 🍵",
            description=response,
            color=discord.Color.dark_purple()
        )
        
        # Add gossip-themed decorative elements
        gossip_emojis = ["👀", "💅", "🤫", "😏", "🔍", "📝", "💬", "🗣️", "📢", "🤭"]
        random_emoji = random.choice(gossip_emojis)
        
        # Add bot avatar if available
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
            
        # Add secretive footer with timestamp
        embed.set_footer(text=f"{random_emoji} Don't tell anyone Mommy told you this {random_emoji}")
        embed.timestamp = ctx.message.created_at
        
        # Stop animation and show the result
        await animator.stop(final_embed=embed)
        logging.info(f"Spill command executed by {ctx.author}")
    except Exception as e:
        logging.error(f"Error in spill command: {e}")
        logging.error(traceback.format_exc())
        try:
            # Enhanced error handling with embed
            error_embed = discord.Embed(
                title="❌ Gossip Error",
                description=random.choice(MOMMY_ERROR_VARIANTS),
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"Error details: {str(e)[:100]}")
            await ctx.send(embed=error_embed)
        except Exception as send_error:
            logging.error(f"Failed to send error message: {send_error}")
            # Last resort plain text
            try:
                await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
            except:
                pass

@bot.command(name="tipjar")
async def tipjar_command(ctx):
    """Check Mommy's special fund status"""
    # Debug logging
    logging.warning(f"TIPJAR COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id})")
    
    try:
        # Start loading animation
        animator = loading_animations.LoadingAnimator(ctx)
        await animator.start()
        
        response = utils.get_tipjar_response(ctx.message, data_manager)
        
        # Create a money-themed embed for the tipjar response
        embed = discord.Embed(
            title="💰 Mommy's Tip Jar 💰",
            description=response,
            color=discord.Color.green()
        )
        
        # Add money-themed decorative elements
        money_emojis = ["💵", "💸", "🤑", "💲", "💰", "👛", "🪙", "💎", "🏦", "💳"]
        random_emoji = random.choice(money_emojis)
        
        # Add bot avatar if available 
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
            
        # Add sophisticated footer with timestamp
        embed.set_footer(text=f"{random_emoji} Donations always welcome, darling {random_emoji}")
        embed.timestamp = ctx.message.created_at
        
        # Stop animation and show the result
        await animator.stop(final_embed=embed)
        logging.info(f"Tipjar command executed by {ctx.author}")
    except Exception as e:
        logging.error(f"Error in tipjar command: {e}")
        logging.error(traceback.format_exc())
        try:
            # Enhanced error handling with embed
            error_embed = discord.Embed(
                title="❌ Tipjar Error",
                description=random.choice(MOMMY_ERROR_VARIANTS),
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"Error details: {str(e)[:100]}")
            await ctx.send(embed=error_embed)
        except Exception as send_error:
            logging.error(f"Failed to send error message: {send_error}")
            # Last resort plain text
            try:
                await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
            except:
                pass

@bot.command(name="testcmd")
async def test_command(ctx):
    """Simple test command with improved wait_for testing"""
    logging.info(f"Test command received from {ctx.author.name} (ID: {ctx.author.id})")
    
    try:
        # Send initial message
        initial_message = await ctx.send("Mommy is here and ready to listen. Say something to me~ 💋")
        
        # Define check function
        def check(m):
            # Check if the message is from the command author and in the same channel
            is_valid = m.author == ctx.author and m.channel == ctx.channel
            logging.info(f"Test command check: Message from {m.author.name}, valid: {is_valid}")
            return is_valid
        
        # Send a message explaining what we're doing
        await ctx.send("I'll wait for your message for 30 seconds using the fixed wait_for...")
        
        # Use the fixed wait_for approach
        logging.info(f"Test command: Waiting for message from {ctx.author.name}")
        try:
            # Use the proper asyncio.wait_for pattern that works with Discord.py
            response = await asyncio.wait_for(bot.wait_for('message', check=check), timeout=30.0)
            logging.info(f"Test command: Received response: {response.content}")
            
            # Send a confirmation message
            await ctx.send(f"Mommy heard you say: '{response.content}' 💕")
        except asyncio.TimeoutError:
            logging.info("Test command: Timeout occurred")
            await ctx.send("Oh darling, you took too long to respond! Mommy got bored~ 💤")
    
    except Exception as e:
        logging.error(f"Error in test command: {e}")
        logging.error(traceback.format_exc())
        await ctx.send(f"Mommy had a little accident~ 💔 Error: {e}")

@bot.command(name="mommy")
async def mommy_command(ctx):
    """Mommy shows help information about available commands"""
    # Debug logging
    logging.warning(f"MOMMY COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id})")
        
    try:
        # Create an embed with command information
        embed = discord.Embed(
            title="✨ Mommy's Command List ✨",
            description="Here's what Mommy can do for you, sweetie! 💖",
            color=discord.Color.purple()
        )
        
        # Add command categories
        embed.add_field(
            name="🎀 Fun Commands",
            value=(
                "• `!mommy` - Show this help message\n"
                "• `!headpat` - Give Mommy headpats\n"
                "• `!spank` - Spank someone or get spanked\n"
                "• `!confess` - Mommy confesses what she's been up to\n"
                "• `!spill` - Mommy shares some juicy gossip\n"
                "• `!shopping` - See Mommy's luxury purchases\n"
                "• `!tipjar` - Check Mommy's special fund"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Value Commands",
            value=(
                "• `!checkvalue` - Check your or someone else's value\n"
                "• `!rankings` - See the top valued members\n"
                "• `!activity` - Check your activity stats"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🏅 Gold Rush Commands",
            value=(
                "• `!checkgold` - Check your or someone else's gold balance\n"
                "• `!addgold` - Add or subtract gold (trainers only)\n"
                "• `!reset` - Reset someone's gold (trainers only)\n"
                "• `!resetall` - Reset everyone's gold (trainers only)"
            ),
            inline=False
        )
        
        # Show BLR-specific commands if in the BLR server
        if ctx.guild and str(ctx.guild.id) == "1345538548027232307":  # OFFICIAL BL:R E-SPORTS | [NATIONAL]
            embed.add_field(
                name="🎮 BLR Match Commands",
                value=(
                    "• `!matchresults` - Submit match results\n"
                    "• `!matchcancel` - Cancel a pending match\n"
                    "• `!anteup` - Ante up for a match\n"
                    "• `!tryoutsresults` - Submit tryouts results\n"
                    "• `!eval` - Evaluate player performance"
                ),
                inline=False
            )
        
        # Check if user has appropriate permissions for mod commands
        is_moderator = False
        if ctx.guild:
            # Check for admin or moderator permissions
            if ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.moderate_members:
                is_moderator = True
            
            # Check for specific moderator roles
            moderator_role_ids = [
                1350499731612110929,  # Evaluator role
                1350475555483512903   # Trainer role
            ]
            for role in ctx.author.roles:
                if role.id in moderator_role_ids:
                    is_moderator = True
                    break
        
        # Owner can always see moderation commands
        if ctx.author.id == 654338875736588288:  # Owner ID
            is_moderator = True
            
        # Show moderation commands if user is a moderator
        if is_moderator:
            embed.add_field(
                name="🛡️ Moderation Commands",
                value=(
                    "• `!modhelp` - Show interactive moderation tooltips\n"
                    "• `!untimeout` - Remove a timeout from a member\n"
                    "• `!cleanserver` - Delete profanity in the server"
                ),
                inline=False
            )
        
        # Add footer and thumbnail
        embed.set_footer(text="Mommy is always here for you! 💕")
        if ctx.guild and ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        
        await ctx.send(embed=embed)
        logging.info(f"Mommy command executed by {ctx.author}")
    except Exception as e:
        logging.error(f"Error in mommy command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@bot.command(name="headpat")
async def headpat_command(ctx):
    """Give mommy headpats"""
    # Debug logging
    logging.warning(f"HEADPAT COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id})")
    
    try:
        # Check if someone is trying to headpat the bot or themselves
        if ctx.message.mentions and bot.user in ctx.message.mentions:
            embed = discord.Embed(
                title="❌ Oh my~",
                description="Oh darling, you can't headpat Mommy! Mommy gives the headpats around here~ 💖",
                color=discord.Color.purple()
            )
            await ctx.send(embed=embed)
            return
        elif ctx.author.mentioned_in(ctx.message):
            embed = discord.Embed(
                title="❤️ Self Love?",
                description="Trying to headpat yourself, sweetie? That's not how it works! Here, let Mommy do it for you~ 💕",
                color=discord.Color.purple()
            )
            await ctx.send(embed=embed)
            return
        
        # Check if user has permission (specific role required)
        has_permission = False
        headpat_role_id = 1350547213717209160  # Headpat role ID
        
        # Allow if the user has the headpat role
        if ctx.guild and any(role.id == headpat_role_id for role in ctx.author.roles):
            has_permission = True
        
        # Deny if no permission
        if not has_permission and not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Oh darling, you don't have permission to give headpats! Only certain special members can do that~ 💕")
            return
        
        # Start loading animation
        animator = loading_animations.LoadingAnimator(ctx)
        await animator.start()
            
        # Get a headpat response properly formatted with the user's mention
        response_template = utils.get_random_headpat_response()
        response = response_template.format(member=ctx.author)
        
        # List of headpat GIFs - using reliable tenor and giphy links
        headpat_gifs = [
            "https://media.tenor.com/L3AHB7-hygQAAAAC/anime-headpat.gif",
            "https://media.tenor.com/N41zKEDABuUAAAAC/anime-head-pat.gif", 
            "https://media.tenor.com/rZhTPXELEfUAAAAC/pat-head-gakuen-babysitters.gif",
            "https://media.tenor.com/8DaE6qzF0DwAAAAC/neet-anime.gif",
            "https://media.tenor.com/wLJALtRxDdUAAAAC/head-pat-anime.gif",
            "https://media.tenor.com/RlR2Biu-JpsAAAAC/anime-head-pat.gif",
            "https://media.tenor.com/jnndDMKAenMAAAAC/anime-headpat.gif",
            "https://media.tenor.com/edHJ-l_MWqgAAAAC/anime-head-pat.gif",
            "https://media.tenor.com/YroVxwiL2dcAAAAC/azumanga-daioh-azumanga.gif",
            "https://media.tenor.com/Sy4CBfXAQYEAAAAC/anime-headpat.gif"
        ]
        
        # Create an attractive embed
        embed = discord.Embed(
            title="✨ Headpats from Mommy ✨",
            description=response,
            color=discord.Color.gold()
        )
        
        # Add random headpat GIF
        embed.set_image(url=random.choice(headpat_gifs))
        
        # Set a footer with a timestamp
        embed.set_footer(text="Mommy loves giving headpats!")
        embed.timestamp = ctx.message.created_at
        
        # Stop the animation and display the final result
        await animator.stop(final_embed=embed)
        
        # Track headpat count for the user in the current day
        user_id = str(ctx.author.id)
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Initialize or update headpat tracking
        headpat_data = data_manager.get_member_data(user_id, "headpats", {})
        if current_date not in headpat_data:
            headpat_data[current_date] = 0
        
        # Increment headpat count for today
        headpat_data[current_date] += 1
        data_manager.set_member_data(user_id, "headpats", headpat_data)
        
        # Check for 3 headpats in a day to award special role
        if headpat_data[current_date] >= 3 and ctx.guild:
            # Special goodboy role ID
            goodboy_role_id = 1350875622875857037  # This is the "Goodboy" role ID
            goodboy_role = ctx.guild.get_role(goodboy_role_id)
            
            if goodboy_role:
                # Check if the user already has the role
                user_has_role = False
                if ctx.author.roles and goodboy_role in ctx.author.roles:
                    user_has_role = True
                
                # If user doesn't have the role yet, give it to them
                if not user_has_role:
                    # Remove role from anyone who currently has it
                    for member in ctx.guild.members:
                        if goodboy_role in member.roles and member.id != ctx.author.id:
                            try:
                                await member.remove_roles(goodboy_role)
                                logging.info(f"Removed goodboy role from {member.name}")
                            except Exception as e:
                                logging.error(f"Error removing goodboy role: {e}")
                    
                    # Add role to current user
                    try:
                        await ctx.author.add_roles(goodboy_role)
                        
                        # Send special message for 3 headpats
                        goodboy_embed = discord.Embed(
                            title="🌟 Good Boy Champion! 🌟",
                            description=f"{ctx.author.mention} has received 3 headpats today and has earned the special **Goodboy** role!",
                            color=discord.Color.gold()
                        )
                        goodboy_embed.set_footer(text="This special role shows you've been a very good boy today!")
                        
                        # Add a special GIF for the goodboy award
                        goodboy_gifs = [
                            "https://media.tenor.com/xvFtxVmfaXMAAAAC/anime-good-boy.gif",
                            "https://media.tenor.com/FjtwMn6SQboAAAAC/headpat-anime-headpat.gif",
                            "https://media.tenor.com/3T3-sTlpbHwAAAAC/anime-good-boy.gif",
                            "https://media.tenor.com/o0re-t5T3bMAAAAC/anime-pet.gif",
                            "https://media.tenor.com/1YMrMsCtxLQAAAAC/anime-head-pat.gif"
                        ]
                        goodboy_embed.set_image(url=random.choice(goodboy_gifs))
                        
                        await ctx.send(embed=goodboy_embed)
                        
                        logging.info(f"Added goodboy role to {ctx.author.name} for getting 3 headpats")
                    except Exception as e:
                        logging.error(f"Error adding goodboy role: {e}")
        
        logging.info(f"Headpat command executed by {ctx.author}")
    except Exception as e:
        logging.error(f"Error in headpat command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@bot.command(name="eval")
async def eval_command(ctx, member: Optional[discord.Member] = None):
    """Evaluate player performance"""
    # Debug logging
    logging.warning(f"EVAL COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id})")
        
    try:
        # Only allow this command in BLR server
        if not ctx.guild or str(ctx.guild.id) != "1345538548027232307":  # OFFICIAL BL:R E-SPORTS | [NATIONAL]
            await ctx.send("This command is only available in the BLR server, sweetie~ 💖")
            return
            
        # Need to specify a member to evaluate
        if not member:
            await ctx.send("Oh darling, you need to specify which player you want to evaluate! 💖\nUse `!eval @player`")
            return
            
        # Don't allow evaluating the bot
        if member.id == bot.user.id:
            await ctx.send("Oh sweetie, Mommy doesn't need evaluation~ I'm always perfect! 💋")
            return
            
        # Don't allow self-evaluation
        if member.id == ctx.author.id:
            await ctx.send("Darling, you can't evaluate yourself! That would be biased~ 💕")
            return
            
        # Start DM for evaluation
        try:
            dm_channel = await ctx.author.create_dm()
            
            # Create initial embed with instructions
            embed = discord.Embed(
                title=f"🎮 Player Evaluation: {member.display_name}",
                description="Let's evaluate this player's performance, darling! 💖",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📋 Instructions",
                value=(
                    "Mommy will ask you a series of questions about this player.\n"
                    "Please answer honestly to help improve the team! 💕\n\n"
                    "Let's begin with your first assessment..."
                ),
                inline=False
            )
            
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
                
            await dm_channel.send(embed=embed)
            
            # First question - Player skill
            first_question = discord.Embed(
                title="Question 1: Player Skill",
                description=f"How would you rate {member.display_name}'s overall skill level?",
                color=discord.Color.purple()
            )
            
            first_question.add_field(
                name="📊 Rating Scale",
                value=(
                    "1️⃣ - Beginner: Still learning the basics\n"
                    "2️⃣ - Developing: Shows potential but inconsistent\n"
                    "3️⃣ - Average: Competent in most situations\n"
                    "4️⃣ - Above Average: Skilled and reliable\n"
                    "5️⃣ - Expert: Outstanding performance consistently"
                ),
                inline=False
            )
            
            first_question.set_footer(text="Please enter a number from 1-5")
            await dm_channel.send(embed=first_question)
            
            # Store the evaluation state
            if not hasattr(bot, "_player_evaluations"):
                bot._player_evaluations = {}
                
            bot._player_evaluations[ctx.author.id] = {
                "step": "skill_rating",
                "target_id": str(member.id),
                "target_name": member.display_name,
                "channel_id": str(ctx.channel.id),
                "guild_id": str(ctx.guild.id),
                "timestamp": time.time()
            }
            
            # Send confirmation in original channel
            await ctx.send(f"Check your DMs, sweetie~ I've sent you the evaluation form for {member.mention}! 💖")
            
        except discord.Forbidden:
            await ctx.send("Oh no, darling! I couldn't send you a DM. Please make sure your privacy settings allow messages from server members~ 💕")
            return
            
        logging.info(f"Eval command executed by {ctx.author} for {member}")
    except Exception as e:
        logging.error(f"Error in eval command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@bot.command(name="activity")
async def activity_command(ctx, member: Optional[discord.Member] = None):
    """Check your or someone else's activity stats"""
    # Debug logging
    logging.warning(f"ACTIVITY COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id})")
        
    try:
        # If no member is specified, show the author's activity
        target_member = member or ctx.author
        
        # Get the activity data
        activity_data = data_manager.get_activity(str(target_member.id))
        
        if not activity_data:
            if target_member == ctx.author:
                await ctx.send("Oh sweetie, you don't have any activity recorded yet! Start chatting more~ 💖")
            else:
                await ctx.send(f"Oh darling, {target_member.mention} doesn't have any activity recorded yet! 💖")
            return
            
        # Create an embed with the activity info
        embed = discord.Embed(
            title=f"📊 Activity Stats for {target_member.display_name}",
            description="Here's what Mommy has been tracking~",
            color=discord.Color.purple()
        )
        
        # Add activity fields
        messages = activity_data.get("messages", 0)
        reactions = activity_data.get("reactions", 0)
        last_active = activity_data.get("last_active")
        
        embed.add_field(
            name="💬 Messages",
            value=f"{messages:,}",
            inline=True
        )
        
        embed.add_field(
            name="🎭 Reactions",
            value=f"{reactions:,}",
            inline=True
        )
        
        # Total activity
        total = messages + reactions
        embed.add_field(
            name="✨ Total Activity",
            value=f"{total:,}",
            inline=True
        )
        
        # Last active timestamp
        if last_active:
            try:
                # Convert to datetime and format
                last_active_dt = datetime.datetime.fromtimestamp(last_active)
                formatted_time = last_active_dt.strftime("%Y-%m-%d %H:%M:%S")
                embed.add_field(
                    name="⏰ Last Active",
                    value=formatted_time,
                    inline=False
                )
            except Exception as e:
                logging.error(f"Error formatting last_active timestamp: {e}")
        
        # Add footer and thumbnail
        embed.set_footer(text="Mommy's always watching~ 💕")
        if target_member.avatar:
            embed.set_thumbnail(url=target_member.avatar.url)
            
        await ctx.send(embed=embed)
        logging.info(f"Activity command executed by {ctx.author} for {target_member}")
    except Exception as e:
        logging.error(f"Error in activity command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@bot.command(name="sm")
async def sm_command(ctx, *, message=None):
    """Enhanced command for Rxcky to send custom messages through the bot"""
    # Debug logging
    logging.warning(f"SM COMMAND RECEIVED from {ctx.author} (ID: {ctx.author.id})")
    
    # Bot owner ID for Rxcky
    RXCKY_ID = 654338875736588288
    
    try:
        # Check if user has permission (only Rxcky or the original bot owner)
        has_permission = False
        
        # Allow Rxcky as the bot owner and original owner too
        if ctx.author.id == RXCKY_ID or ctx.author.id == 859413883420016640:
            has_permission = True
        # Check for trainers role in Novera server
        elif ctx.guild and str(ctx.guild.id) == "1350165280940228629":  # Novera Team Hub
            trainer_role_id = "1350175902738419734"  # Trainers role in Novera server
            has_permission = any(str(role.id) == trainer_role_id for role in ctx.author.roles)
        # Check for trainers/management role in BLR server
        elif ctx.guild and str(ctx.guild.id) == "1345538548027232307":  # BLR server
            trainer_role_ids = ["1345539263042687016", "1360251493252333821"]  # Manager and Evaluator roles
            has_permission = any(str(role.id) in trainer_role_ids for role in ctx.author.roles)
            
        if not has_permission:
            await ctx.send(random.choice(MOMMY_PERMISSION_DENIED))
            return
        
        # If a message is provided directly, use the legacy functionality
        if message and ' ' in message:
            parts = message.split(' ', 1)
            if parts[0].startswith('<@') and parts[0].endswith('>'):
                # Extract member ID from mention
                member_id = parts[0].replace('<@', '').replace('>', '')
                if '!' in member_id:  # Handle legacy mentions
                    member_id = member_id.replace('!', '')
                
                # Try to convert to member object
                try:
                    member = await ctx.guild.fetch_member(int(member_id))
                    value_str = parts[1].strip()
                    if value_str.isdigit():
                        value = int(value_str)
                        
                        # Set the member's value
                        user_id = str(member.id)
                        old_value = data_manager.get_member_value(user_id)
                        data_manager.set_member_value(user_id, value)
                        
                        # Confirm the change
                        if old_value == value:
                            await ctx.send(f"Mommy didn't change anything, darling! {member.mention}'s value was already {value}! 💕")
                        else:
                            await ctx.send(f"Mommy has updated {member.mention}'s value from {old_value} to {value}, darling! 💖")
                        
                        logging.info(f"SM command executed by {ctx.author} to set {member}'s value to {value}")
                        return
                except:
                    pass
        
        # If we get here, or if no message was provided, use the new enhanced functionality
        # This will be an interactive process
        
        # Get the list of servers the bot is in - now it should only be Novera
        guild_list = []
        for guild in bot.guilds:
            # Only include the Novera server
            if str(guild.id) == "1350165280940228629":  # Novera Team Hub
                guild_list.append((guild.id, guild.name))
        
        # If no valid guilds found, inform the user
        if not guild_list:
            await ctx.send("Oh darling, Mommy seems to have lost connection to the Novera server! Please try again later~ 💋")
            return
            
        # Now we have the guild list with just the Novera server
        guild_id, guild_name = guild_list[0]  # There's only one server now
        guild = bot.get_guild(guild_id)
        
        # Check if in DM - if not, suggest moving to DM
        if ctx.guild:
            confirmation = await ctx.send("Mommy will help you send a message, darling! Let's continue in DMs for privacy~ 💖")
            try:
                dm_channel = await ctx.author.create_dm()
                await dm_channel.send(f"Hello sweetheart~ Let's set up a message for Mommy to send to **{guild_name}**! 💋")
            except discord.Forbidden:
                await ctx.send("Oh no, darling! I can't DM you. Please enable your DMs for this server! 💔")
                return
        else:
            dm_channel = ctx.channel
            await dm_channel.send(f"Hello sweetheart~ Let's set up a message for Mommy to send to **{guild_name}**! 💋")
        
        def check(m):
            is_valid = m.author == ctx.author and m.channel == dm_channel
            logging.info(f"SM command check: Message from {m.author.name} in {m.channel.name if hasattr(m.channel, 'name') else 'DM'}, valid: {is_valid}")
            return is_valid
            
        try:
            # Get available channels in the selected server
            channels = []
            for channel in guild.text_channels:
                # Check if the bot can send messages in the channel
                if channel.permissions_for(guild.me).send_messages:
                    channels.append((channel.id, channel.name))
            
            # Ask which channel
            channel_embed = discord.Embed(
                title="Step 2: Choose a Channel",
                description=f"Which channel in **{guild_name}** should Mommy send this message to?",
                color=discord.Color.purple()
            )
            
            channel_text = ""
            for i, (channel_id, channel_name) in enumerate(channels, 1):
                channel_text += f"{i}. #{channel_name} (ID: {channel_id})\n"
            
            # Split into multiple fields if needed (Discord has a 1024 character limit per field)
            if len(channel_text) > 1000:
                chunks = [channel_text[i:i+1000] for i in range(0, len(channel_text), 1000)]
                for i, chunk in enumerate(chunks):
                    channel_embed.add_field(name=f"Available Channels (Part {i+1})", value=chunk, inline=False)
            else:
                channel_embed.add_field(name="Available Channels", value=channel_text, inline=False)
                
            channel_embed.set_footer(text="Please enter the number of the channel (e.g., '1')")
            
            await dm_channel.send(embed=channel_embed)
            
            # Wait for channel choice
            logging.info(f"SM command: Waiting for channel choice from {ctx.author.name}")
            # Use direct wait_for method from Discord.py which handles timeouts internally
            channel_response = await wait_for_safe(bot.wait_for('message', check=check), timeout=60.0)
            logging.info(f"SM command: Received channel choice: {channel_response.content if channel_response else 'None'}")
                
            choice = channel_response.content.strip()
            
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(channels):
                await dm_channel.send("Oops! That's not a valid choice, darling. Let's start over~ 💕\nUse `!sm` again.")
                return
                
            channel_id, channel_name = channels[int(choice) - 1]
            channel = guild.get_channel(channel_id)
            
            # Ask about pinging
            ping_embed = discord.Embed(
                title="Step 3: Ping Options",
                description="Who should Mommy ping with this message?",
                color=discord.Color.purple()
            )
            
            ping_options = [
                "1. No one",
                "2. @everyone",
                "3. @here",
                "4. A specific role (will ask for role ID)",
                "5. A specific member (will ask for member ID)"
            ]
            
            ping_embed.add_field(name="Ping Options", value="\n".join(ping_options), inline=False)
            ping_embed.set_footer(text="Please enter the number of your choice (e.g., '1')")
            
            await dm_channel.send(embed=ping_embed)
            
            # Wait for ping choice
            logging.info(f"SM command: Waiting for ping choice from {ctx.author.name}")
            # Use direct wait_for method from Discord.py which handles timeouts internally
            ping_response = await wait_for_safe(bot.wait_for('message', check=check), timeout=60.0)
            logging.info(f"SM command: Received ping choice: {ping_response.content if ping_response else 'None'}")
                
            ping_choice = ping_response.content.strip()
            
            ping_text = ""
            if ping_choice == "1":
                # No ping
                ping_text = ""
            elif ping_choice == "2":
                # @everyone
                ping_text = "@everyone"
            elif ping_choice == "3":
                # @here
                ping_text = "@here"
            elif ping_choice == "4":
                # Specific role
                await dm_channel.send("Please enter the ID of the role to ping, darling~ 💕")
                logging.info(f"SM command: Waiting for role ID from {ctx.author.name}")
                # Use direct wait_for method from Discord.py which handles timeouts internally
                role_response = await wait_for_safe(bot.wait_for('message', check=check), timeout=60.0)
                logging.info(f"SM command: Received role ID: {role_response.content if role_response else 'None'}")
                role_id = role_response.content.strip()
                if role_id.isdigit():
                    ping_text = f"<@&{role_id}>"
                else:
                    await dm_channel.send("That doesn't look like a valid role ID, sweetie. I'll proceed without pinging anyone.")
                    ping_text = ""
            elif ping_choice == "5":
                # Specific member
                await dm_channel.send("Please enter the ID of the member to ping, darling~ 💕")
                logging.info(f"SM command: Waiting for member ID from {ctx.author.name}")
                # Use direct wait_for method from Discord.py which handles timeouts internally
                member_response = await wait_for_safe(bot.wait_for('message', check=check), timeout=60.0)
                logging.info(f"SM command: Received member ID: {member_response.content if member_response else 'None'}")
                
                member_id = member_response.content.strip()
                if member_id.isdigit():
                    ping_text = f"<@{member_id}>"
                else:
                    await dm_channel.send("That doesn't look like a valid member ID, sweetie. I'll proceed without pinging anyone.")
                    ping_text = ""
            else:
                await dm_channel.send("That's not a valid choice, darling. I'll proceed without pinging anyone.")
                ping_text = ""
            
            # Ask for the message content
            await dm_channel.send("Finally, what message should Mommy send? Please type your message now, darling~ 💖")
            
            # Wait for message content
            logging.info(f"SM command: Waiting for message content from {ctx.author.name}")
            # Use direct wait_for method from Discord.py which handles timeouts internally
            message_response = await wait_for_safe(bot.wait_for('message', check=check), timeout=300.0)  # 5 minute timeout for longer messages
            logging.info(f"SM command: Received message content (length: {len(message_response.content) if message_response else 0})")
                
            message_content = message_response.content
            
            # Combine ping and message
            full_message = f"{ping_text}\n{message_content}" if ping_text else message_content
            
            # Send the message
            await channel.send(full_message)
            
            # Confirm to the user
            confirmation = f"Mommy has sent your message to #{channel_name} in {guild_name}, darling~ 💋"
            await dm_channel.send(confirmation)
            
            logging.info(f"SM command: {ctx.author} sent a message to {guild_name} #{channel_name}")
            
        except asyncio.TimeoutError:
            await dm_channel.send("Oh sweetie, you took too long to respond. Let's try again later~ 💕")
        
    except Exception as e:
        logging.error(f"Error in sm command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@bot.command(name="addvalue")
async def addvalue_command(ctx, *, args=""):
    """Trainer-only command to add or subtract value from a member"""
    logging.info(f"Processing addvalue command for message ID {ctx.message.id}")
    
    try:
        # Check if user has permission (trainers role or owner)
        has_permission = False
        
        # Allow bot owner or Rxcky
        if ctx.author.id == 859413883420016640 or ctx.author.id == 654338875736588288:
            has_permission = True
        # Check for trainers role in Novera server
        elif ctx.guild and str(ctx.guild.id) == "1350165280940228629":  # Novera Team Hub
            trainer_role_id = "1350175902738419734"  # Trainers role in Novera server
            has_permission = any(str(role.id) == trainer_role_id for role in ctx.author.roles)
            
        if not has_permission:
            await ctx.send(random.choice(MOMMY_PERMISSION_DENIED))
            return
            
        # Parse the arguments
        args_parts = args.split()
        if len(args_parts) < 2:
            await ctx.send("Oh darling, you need to specify both a member and an amount! 💖\nUse `!addvalue @user +5` or `!addvalue @user -5`")
            return
            
        # First argument should be the member mention
        if not ctx.message.mentions:
            await ctx.send("Oh sweetie, you need to mention the member you want to add value to! 💖\nUse `!addvalue @user +5` or `!addvalue @user -5`")
            return
            
        member = ctx.message.mentions[0]
        amount_str = args_parts[-1]  # Last argument should be the amount
        
        # Parse the amount value
        try:
            # Check if the amount is in the format +X or -X
            if amount_str.startswith('+'):
                amount = int(amount_str[1:])
            elif amount_str.startswith('-'):
                amount = -int(amount_str[1:])
            else:
                # Try to parse as a simple integer
                amount = int(amount_str)
                
            # Validate amount
            if amount == 0:
                await ctx.send("Oh sweetie, the amount needs to be a non-zero value! Use `+X` to add or `-X` to subtract value~ 💕")
                return
        except ValueError:
            await ctx.send("Oh darling, that's not a valid number! Please use `+X` to add or `-X` to subtract value~ 💕")
            return
            
        # Get the member's current value and update it
        user_id = str(member.id)
        # Get the member's current value and update it
mgr = getattr(ctx.bot, "data_manager", None)
if mgr is None:
    await ctx.send("😔 Mommy can’t adjust values right now, sweetie~ Try again later 💕")
    return

user_id = str(member.id)

old_value = mgr.get_member_value(user_id)
new_value = old_value + amount

await mgr.set_member_value(user_id, new_value)
        
        # Create an embed for better presentation with varied messages
        embed = discord.Embed(
            color=discord.Color.gold() if amount > 0 else discord.Color.purple()
        )
        
        # Set the member's avatar as thumbnail if available
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
            
        # Generate a varied title and description based on whether we're adding or subtracting
        if amount > 0:
            titles = [
                f"✨ Value Boost for {member.display_name}! ✨",
                f"💰 {member.display_name}'s Value Increased! 💰",
                f"🌟 Rising Star: {member.display_name}! 🌟",
                f"💎 Value Investment in {member.display_name}! 💎",
                f"📈 {member.display_name}'s Stocks Going Up! 📈"
            ]
            
            descriptions = [
                f"Mommy has generously added **{amount}** to {member.mention}'s value! They must have been such a good baby~ 💖",
                f"Oooh, {member.mention} gets a nice boost of **{amount}**! Mommy is feeling generous today~ 💕",
                f"Mommy thinks {member.mention} deserves **{amount}** more! Keep making Mommy proud, sweetie~ 💖",
                f"{member.mention}'s value just went up by **{amount}**! What a good little worker you are~ 💋",
                f"Mommy is so impressed with {member.mention} that she's adding **{amount}** to their value! 💓",
                f"Such a good performance from {member.mention}! Here's **{amount}** more to your value, darling~ ✨",
                f"Mommy loves to reward her good babies! {member.mention} gets **{amount}** added to their value~ 💝",
                f"Look at {member.mention} rising in Mommy's eyes! **+{amount}** value for you, sweetie~ 🎀"
            ]
        else:
            titles = [
                f"📉 Value Adjustment for {member.display_name} 📉",
                f"💸 {member.display_name}'s Value Decreased 💸",
                f"⚠️ Value Correction: {member.display_name} ⚠️",
                f"🔻 {member.display_name}'s Performance Review 🔻",
                f"📊 Value Reassessment: {member.display_name} 📊"
            ]
            
            descriptions = [
                f"Oh dear, Mommy had to subtract **{abs(amount)}** from {member.mention}'s value. Do better next time, sweetie~ 💔",
                f"{member.mention} has been a bit naughty, so Mommy is taking away **{abs(amount)}** from their value! 😈",
                f"Mommy is disappointed and has to reduce {member.mention}'s value by **{abs(amount)}**. Try harder, darling~ 💔",
                f"Looks like {member.mention} needs to work harder! Mommy is subtracting **{abs(amount)}** from your value~ 📉",
                f"Mommy doesn't like to punish her babies, but {member.mention} loses **{abs(amount)}** value. Make it up to Mommy~ 💋",
                f"Not your best work, {member.mention}. Mommy is taking **{abs(amount)}** from your value. Do better~ 🎀",
                f"{member.mention} has disappointed Mommy a little. **-{abs(amount)}** from your value, darling~ 💭",
                f"Mommy expects more from you, {member.mention}! Your value is reduced by **{abs(amount)}**~ 🔻"
            ]
            
        # Select a random title and description
        embed.title = random.choice(titles)
        embed.description = random.choice(descriptions)
        
        # Add fields showing the value change
        embed.add_field(
            name="Previous Value",
            value=f"{old_value} million",
            inline=True
        )
        
        embed.add_field(
            name="New Value",
            value=f"{new_value} million",
            inline=True
        )
        
        embed.add_field(
            name="Change",
            value=f"+{amount} million" if amount > 0 else f"{amount} million",
            inline=True
        )
        
        # Add footer
        embed.set_footer(text=f"Adjusted by {ctx.author.display_name} • {datetime.now().strftime('%Y-%m-%d')}")
        
        # Send the embed
        await ctx.send(embed=embed)
            
        logging.info(f"Addvalue command executed by {ctx.author} to change {member}'s value by {amount} from {old_value} to {new_value}")
        
    except Exception as e:
        error_msg = f"Error in addvalue command: {e}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        try:
            await ctx.send(f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*")
        except:
            pass

@bot.command(name="addgold")
async def addgold_command(ctx, *, args=""):
    """Trainer-only command to add or subtract gold from a member"""
    logging.info(f"Processing addgold command for message ID {ctx.message.id}")
    
    try:
        # Check if user has permission (trainers role or owner)
        has_permission = False
        
        # Allow bot owner or Rxcky
        if ctx.author.id == 859413883420016640 or ctx.author.id == 654338875736588288:
            has_permission = True
            
        # Allow Trainers role in Novera server
        if ctx.guild and str(ctx.guild.id) == "1350165280940228629" and any(str(role.id) == "1350175902738419734" for role in ctx.author.roles):
            has_permission = True
            
        if not has_permission:
            await ctx.send("Sorry darling, only trainers can use this command~ 💋")
            return
            
        # Check that args are provided (should be mention and amount)
        args_parts = args.split()
        if len(args_parts) < 2:
            await ctx.send("Oh darling, you need to specify both a member and an amount! 💖\nUse `!addgold @user +5` or `!addgold @user -5`")
            return
            
        # First argument should be the member mention
        if not ctx.message.mentions:
            await ctx.send("Oh sweetie, you need to mention the member you want to add gold to! 💖\nUse `!addgold @user +5` or `!addgold @user -5`")
            return
            
        member = ctx.message.mentions[0]
        amount_str = args_parts[-1]  # Last argument should be the amount
        
        # Parse the amount value
        try:
            # Check if the amount is in the format +X or -X
            if amount_str.startswith('+'):
                amount = int(amount_str[1:])
            elif amount_str.startswith('-'):
                amount = -int(amount_str[1:])
            else:
                # Try to parse as a simple integer
                amount = int(amount_str)
                
            # Validate amount
            if amount == 0:
                await ctx.send("Oh sweetie, the amount needs to be a non-zero value! Use `+X` to add or `-X` to subtract gold~ 💕")
                return
        except ValueError:
            await ctx.send("Oh darling, that's not a valid number! Please use `+X` to add or `-X` to subtract gold~ 💕")
            return
            
        # Get the member's current gold and update it
        user_id = str(member.id)
        old_gold = data_manager.get_member_gold(user_id)
        new_gold = data_manager.add_member_gold(user_id, amount)
        
        # Create an embed for better presentation with varied messages
        embed = discord.Embed(
            color=discord.Color.gold() if amount > 0 else discord.Color.purple()
        )
        
        # Set the member's avatar as thumbnail if available
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
            
        # Generate a varied title and description based on whether we're adding or subtracting
        if amount > 0:
            titles = [
                f"✨ Gold Rush Boost for {member.display_name}! ✨",
                f"💰 {member.display_name}'s Gold Increased! 💰",
                f"🤑 Gold Fortune Grows for {member.display_name}! 🤑",
                f"💎 Gold Investment in {member.display_name}! 💎",
                f"📈 {member.display_name}'s Gold Stocks Rising! 📈"
            ]
            
            descriptions = [
                f"Mommy has generously added **{amount}** gold to {member.mention}'s stash! They must have been such a good baby~ 💖",
                f"Oooh, {member.mention} gets a nice boost of **{amount}** gold! Mommy is feeling generous today~ 💕",
                f"Mommy thinks {member.mention} deserves **{amount}** more gold! Keep making Mommy proud, sweetie~ 💖",
                f"{member.mention}'s gold just went up by **{amount}**! What a good little worker you are~ 💋",
                f"Mommy is so impressed with {member.mention} that she's adding **{amount}** to their gold stash! 💓",
                f"Such a good performance from {member.mention}! Here's **{amount}** more gold, darling~ ✨",
                f"Mommy loves to reward her good babies! {member.mention} gets **{amount}** added to their gold~ 💝",
                f"Look at {member.mention} shining in the Gold Rush! **+{amount}** gold for you, sweetie~ 🎀"
            ]
        else:
            titles = [
                f"📉 Gold Adjustment for {member.display_name} 📉",
                f"💸 {member.display_name}'s Gold Decreased 💸",
                f"⚠️ Gold Correction: {member.display_name} ⚠️",
                f"🔻 {member.display_name}'s Gold Review 🔻",
                f"📊 Gold Reassessment: {member.display_name} 📊"
            ]
            
            descriptions = [
                f"Oh dear, Mommy had to subtract **{abs(amount)}** from {member.mention}'s gold. Do better next time, sweetie~ 💔",
                f"{member.mention} has been a bit naughty, so Mommy is taking away **{abs(amount)}** from their gold! 😈",
                f"Mommy is disappointed and has to reduce {member.mention}'s gold by **{abs(amount)}**. Try harder, darling~ 💔",
                f"Looks like {member.mention} needs to work harder! Mommy is subtracting **{abs(amount)}** from your gold~ 📉",
                f"Mommy doesn't like to punish her babies, but {member.mention} loses **{abs(amount)}** gold. Make it up to Mommy~ 💋",
                f"Not your best work, {member.mention}. Mommy is taking **{abs(amount)}** from your gold. Do better~ 🎀",
                f"{member.mention} has disappointed Mommy a little. **-{abs(amount)}** from your gold, darling~ 💭",
                f"Mommy expects more from you, {member.mention}! Your gold is reduced by **{abs(amount)}**~ 🔻"
            ]
            
        # Select a random title and description
        embed.title = random.choice(titles)
        embed.description = random.choice(descriptions)
        
        # Add fields showing the gold change
        embed.add_field(
            name="Previous Gold",
            value=f"{old_gold} 💰",
            inline=True
        )
        
        embed.add_field(
            name="New Gold",
            value=f"{new_gold} 💰",
            inline=True
        )
        
        embed.add_field(
            name="Change",
            value=f"+{amount} 💰" if amount > 0 else f"{amount} 💰",
            inline=True
        )
        
        # Add a randomized gold message
        if amount > 0:
            gold_messages = [
                f"💰 {member.mention} is getting richer in the Gold Rush! Keep it up!",
                f"🤑 Look at all that gold {member.mention} is collecting! Mommy is impressed!",
                f"✨ {member.mention} is shining bright in the Gold Rush! So much potential!",
                f"💎 {member.mention}'s gold fortune is growing! Mommy loves ambitious babies!",
                f"🌟 {member.mention} is a rising star in the Gold Rush! Keep collecting!",
                f"🏆 {member.mention} is on their way to the top of the Gold Rush! Well done!",
                f"👑 {member.mention} is building their gold empire! Mommy is so proud!",
                f"🔥 {member.mention} is on fire in the Gold Rush! Nobody can stop you now!"
            ]
        else:
            gold_messages = [
                f"💸 {member.mention} lost some gold in the Rush! Don't worry, you can earn it back!",
                f"📉 {member.mention}'s gold fortune took a hit! Time to work harder, darling!",
                f"🪙 {member.mention} dropped some gold coins! Pick yourself up and try again!",
                f"⚠️ {member.mention} needs to be more careful with their gold stash!",
                f"💔 Mommy had to take some gold from {member.mention}. Make it up to her!",
                f"😔 {member.mention}'s gold pouch got lighter! Time to refill it, sweetie!",
                f"🌧️ Rainy day for {member.mention}'s gold rush! Sunshine comes after rain!",
                f"🕳️ {member.mention} fell into a gold pit! Climb back up and keep going!"
            ]
            
        embed.add_field(
            name="Gold Rush Marathon",
            value=random.choice(gold_messages),
            inline=False
        )
        
        # Add footer
        embed.set_footer(text=f"Adjusted by {ctx.author.display_name} • {datetime.now().strftime('%Y-%m-%d')}")
        
        # Send the embed
        await ctx.send(embed=embed)
            
        logging.info(f"Addgold command executed by {ctx.author} to change {member}'s gold by {amount} from {old_gold} to {new_gold}")
        
    except Exception as e:
        error_msg = f"Error in addgold command: {e}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        try:
            await ctx.send(f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*")
        except:
            pass

@bot.command(name="reset")
async def reset_command(ctx, member: Optional[discord.Member] = None):
    """Reset a player's gold - trainer role only"""
    logging.info(f"Reset command received from {ctx.author.name} (ID: {ctx.author.id})")
    
    try:
        # Check if user has permission (trainers role or owner)
        has_permission = False
        
        # Allow bot owner or Rxcky
        if ctx.author.id == 859413883420016640 or ctx.author.id == 654338875736588288:
            has_permission = True
            
        # Allow Trainers role in Novera server
        if ctx.guild and str(ctx.guild.id) == "1350165280940228629" and any(str(role.id) == "1350175902738419734" for role in ctx.author.roles):
            has_permission = True
            
        if not has_permission:
            await ctx.send("Sorry darling, only trainers can use this command~ 💋")
            return
        
        # If no member is specified, tell the user to specify one
        if member is None:
            await ctx.send("Oh sweetie, you need to mention the member whose gold you want to reset! 💖\nUse `!reset @user`")
            return
            
        # Get the member's ID and reset their gold
        user_id = str(member.id)
        old_gold = data_manager.get_member_gold(user_id)
        data_manager.reset_member_gold(user_id)
        
        # Create a response embed
        embed = discord.Embed(
            title=f"💰 Gold Reset for {member.display_name} 💰",
            description=f"Mommy has reset {member.mention}'s gold to 0! Their previous gold balance was **{old_gold}** 💰",
            color=discord.Color.red()
        )
        
        # Add member avatar if available
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
            
        # Add footer
        embed.set_footer(text=f"Reset by {ctx.author.display_name} • {datetime.now().strftime('%Y-%m-%d')}")
        
        # Send the embed
        await ctx.send(embed=embed)
        
        logging.info(f"Reset command executed by {ctx.author} to reset {member}'s gold from {old_gold} to 0")
        
    except Exception as e:
        error_msg = f"Error in reset command: {e}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        try:
            await ctx.send(f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*")
        except:
            pass

@bot.command(name="resetall")
async def resetall_command(ctx):
    """Reset all players' gold - trainer role only"""
    logging.info(f"Resetall command received from {ctx.author.name} (ID: {ctx.author.id})")
    
    try:
        # Check if user has permission (trainers role or owner)
        has_permission = False
        
        # Allow bot owner or Rxcky
        if ctx.author.id == 859413883420016640 or ctx.author.id == 654338875736588288:
            has_permission = True
            
        # Allow Trainers role in Novera server
        if ctx.guild and str(ctx.guild.id) == "1350165280940228629" and any(str(role.id) == "1350175902738419734" for role in ctx.author.roles):
            has_permission = True
            
        if not has_permission:
            await ctx.send("Sorry darling, only trainers can use this command~ 💋")
            return
            
        # Create confirmation message with buttons
        embed = discord.Embed(
            title="⚠️ Gold Rush Reset Confirmation ⚠️",
            description="Are you **absolutely sure** you want to reset **ALL** members' gold to 0? This action cannot be undone!",
            color=discord.Color.red()
        )
        
        class ConfirmationView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                
            @discord.ui.button(label="Yes, Reset All Gold", style=discord.ButtonStyle.red)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                # Only allow the command author to click the button
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This button is not for you, sweetie~ 💖", ephemeral=True)
                    return
                    
                # Reset all gold using our data manager method
                count = data_manager.reset_all_gold()
                
                # Update the message to show completion
                result_embed = discord.Embed(
                    title="💰 Gold Rush Reset Complete 💰",
                    description=f"Mommy has reset the gold for **{count}** members to 0! The Gold Rush can start anew!",
                    color=discord.Color.green()
                )
                
                result_embed.set_footer(text=f"Reset by {ctx.author.display_name} • {datetime.now().strftime('%Y-%m-%d')}")
                
                await interaction.response.edit_message(embed=result_embed, view=None)
                
                logging.info(f"Resetall command executed by {ctx.author} - reset gold for {count} members")
                
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.green)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                # Only allow the command author to click the button
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("This button is not for you, sweetie~ 💖", ephemeral=True)
                    return
                    
                # Cancel the reset
                cancel_embed = discord.Embed(
                    title="❌ Gold Rush Reset Cancelled ❌",
                    description="Mommy has cancelled the gold reset. Everyone's gold is safe!",
                    color=discord.Color.green()
                )
                
                await interaction.response.edit_message(embed=cancel_embed, view=None)
                
            async def on_timeout(self):
                # Create a timeout embed
                timeout_embed = discord.Embed(
                    title="⏱️ Gold Rush Reset Timed Out ⏱️",
                    description="The reset confirmation has timed out. No gold was reset.",
                    color=discord.Color.grey()
                )
                
                # Try to edit the message
                try:
                    await self.message.edit(embed=timeout_embed, view=None)
                except:
                    pass
        
        # Send the confirmation message with buttons
        await ctx.send(embed=embed, view=ConfirmationView())
        
    except Exception as e:
        error_msg = f"Error in resetall command: {e}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        try:
            await ctx.send(f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*")
        except:
            pass

from data_manager import data_manager   # ✅ FIXED IMPORT

@bot.command(name="rankings")
async def rankings_command(ctx):
    logging.info(f"Rankings command received from {ctx.author.name} (ID: {ctx.author.id})")

    try:
        if not ctx.guild:
            await ctx.send("This command can only be used in a server, sweetie~ 💖")
            return
        
        # ✅ USE THE INSTANCE, NOT THE MODULE
      mgr = getattr(ctx.bot, "data_manager", None)
if mgr is None:
    await ctx.send("Mommy can't access values right now, sweetie~ 💕")
    return

member_values = mgr.get_all_member_values()
        if not member_values:
            await ctx.send("No members have a value yet, darling~ 💖")
            return

        guild_member_values = {}
        for member_id, value in member_values.items():
            member = ctx.guild.get_member(int(member_id))
            if member:
                guild_member_values[member_id] = value
        
        if not guild_member_values:
            await ctx.send("No members in this server have a value yet, sweetie~ 💖")
            return
        
        sorted_members = sorted(guild_member_values.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="👑 Value Rankings 👑",
            description=f"Here are Mommy's most valuable members in **{ctx.guild.name}**:",
            color=discord.Color.gold()
        )

        # your entire ranking code continues here unchanged...
        
        # Define the ranking roles IDs
        ranking_roles = {
            1: "1350533269229408267",  # #1 role
            2: "1350533900119703644",  # #2 role
            3: "1350534045947396297",  # #3 role
            # Roles for ranks 4-10 will be created dynamically if they don't exist
        }
        
        # Define rank emojis
        rank_emojis = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
            4: "💎",
            5: "🏆",
            6: "🔮",
            7: "⚡",
            8: "🌟",
            9: "✨",
            10: "💫"
        }
        
        # Track all ranking roles to clear from unranked members
        all_ranking_roles = []
        
        # First, collect or create all needed ranking roles
        for rank in range(1, 11):
            if rank in ranking_roles:
                # Get existing role for top 3
                role_id = ranking_roles[rank]
                role = ctx.guild.get_role(int(role_id))
                if role:
                    all_ranking_roles.append(role)
            else:
                # For ranks 4-10, check if roles exist or create them
                role_name = f"Rank {rank} {rank_emojis.get(rank, '')}"
                role = discord.utils.get(ctx.guild.roles, name=role_name)
                
                if not role:
                    # Create the role if it doesn't exist
                    try:
                        # Create a role with a color based on the rank
                        hue = 40 - (rank - 4) * 5  # Golden for 4, declining to purple for 10
                        color = discord.Color.from_hsv(hue/360, 0.8, 0.8)
                        role = await ctx.guild.create_role(
                            name=role_name,
                            color=color,
                            hoist=True,  # Display separately in member list
                            mentionable=True,
                            reason=f"Created rank {rank} role for value rankings"
                        )
                        logging.info(f"Created new rank role: {role_name}")
                    except Exception as e:
                        logging.error(f"Error creating rank role: {e}")
                        # Continue without the role
                        continue
                
                all_ranking_roles.append(role)
                ranking_roles[rank] = str(role.id)
        
        # Now show the top 10 and assign roles
        status_message = await ctx.send("🔄 Updating rankings and roles...")
        roles_updated = []
        
        # Add top 10 members to the embed
        try:
            for i, (member_id, value) in enumerate(sorted_members[:10], 1):
                try:
                    member = ctx.guild.get_member(int(member_id))
                    if not member:
                        logging.warning(f"Member {member_id} not found in guild {ctx.guild.id}, skipping")
                        continue
                    
                    # Assign the appropriate rank role
                    if i in ranking_roles:
                        try:
                            role_id = ranking_roles[i]
                            role = ctx.guild.get_role(int(role_id))
                            
                            if role and role not in member.roles:
                                # Member doesn't have this rank role - add it
                                try:
                                    await member.add_roles(role, reason=f"Assigned rank {i} role for value rankings")
                                    roles_updated.append(f"Added {role.name} to {member.display_name}")
                                except Exception as e:
                                    logging.error(f"Error adding rank role to {member.display_name}: {e}")
                        except Exception as role_error:
                            logging.error(f"Error processing role for rank {i}: {role_error}")
                    
                    # Remove any other ranking roles
                    try:
                        for rank, r_id in ranking_roles.items():
                            if rank != i:  # Not the current rank
                                r = ctx.guild.get_role(int(r_id))
                                if r and r in member.roles:
                                    try:
                                        await member.remove_roles(r, reason=f"Removed incorrect rank role")
                                        roles_updated.append(f"Removed {r.name} from {member.display_name}")
                                    except Exception as e:
                                        logging.error(f"Error removing rank role from {member.display_name}: {e}")
                    except Exception as remove_error:
                        logging.error(f"Error removing roles for {member.display_name}: {remove_error}")
                    
                    # Add to embed
                    try:
                        prefix = rank_emojis.get(i, f"{i}. ")
                        embed.add_field(
                            name=f"{prefix} {member.display_name}",
                            value=f"**Value:** {value} million",
                            inline=True
                        )
                    except Exception as embed_error:
                        logging.error(f"Error adding field to embed for {member.display_name}: {embed_error}")
                        
                except Exception as member_error:
                    logging.error(f"Error processing member {member_id} for rankings: {member_error}")
        except Exception as top10_error:
            logging.error(f"Error processing top 10 members for rankings: {top10_error}")
            await ctx.send("There was an error processing the top players. Mommy will try to continue anyway~ 💖")
        
        # Remove ranking roles from anyone not in top 10
        ranked_member_ids = [member_id for member_id, _ in sorted_members[:10]]
        for member in ctx.guild.members:
            if str(member.id) not in ranked_member_ids:
                # Check if they have any ranking roles
                for role in all_ranking_roles:
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="No longer in top 10 rankings")
                            roles_updated.append(f"Removed {role.name} from {member.display_name} (not in top 10)")
                        except Exception as e:
                            logging.error(f"Error removing rank role: {e}")
        
        # Add footer
        total_members = len(guild_member_values)
        embed.set_footer(text=f"Showing top {min(10, total_members)} of {total_members} members with value")
        
        # Add thumbnail if in a guild
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
            
        # Edit the status message to show the rankings
        await status_message.edit(content=None, embed=embed)
        
        # Send a summary of role changes if there were any
        if roles_updated:
            roles_message = "\n".join(roles_updated[:15])  # Show first 15 changes
            if len(roles_updated) > 15:
                roles_message += f"\n...and {len(roles_updated) - 15} more changes"
                
            roles_embed = discord.Embed(
                title="👑 Roles Updated",
                description=roles_message,
                color=discord.Color.blue()
            )
            await ctx.send(embed=roles_embed)
            
        logging.info(f"Rankings command executed by {ctx.author} - {len(roles_updated)} role changes made")
        
    except Exception as e:
        logging.error(f"Error in rankings command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*")
        except:
            pass

# Dictionary to track active evaluations in progress
active_evaluations = {}

class PositionSelect(discord.ui.Select):
    """Position selection dropdown for player evaluation"""
    def __init__(self):
        options = [
            discord.SelectOption(label="CF (Center Forward)", value="CF", emoji="⚽"),
            discord.SelectOption(label="LW/RW (Winger)", value="LW/RW", emoji="🏃"),
            discord.SelectOption(label="CM (Center Midfielder)", value="CM", emoji="🧠"),
            discord.SelectOption(label="GK (Goalkeeper)", value="GK", emoji="🧤")
        ]
        super().__init__(placeholder="Select player position...", options=options, min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        # Store the selected position in the evaluation state
        eval_id = f"{interaction.user.id}-{self.view.player_id}"
        active_evaluations[eval_id]["position"] = self.values[0]
        
        await interaction.response.defer()
        
        # Move to the ratings questions based on position
        position = self.values[0]
        self.view.disable_all_items()
        await interaction.message.edit(view=self.view)
        
        # Send the appropriate rating questions based on position
        if position == "GK":
            await self.view.ask_gk_ratings(interaction)
        else:
            await self.view.ask_field_player_ratings(interaction, position)

class TryoutsView(discord.ui.View):
    """Interactive view for tryouts evaluation"""
    def __init__(self, ctx, player, evaluator):
        super().__init__(timeout=1800)  # 30 minute timeout
        self.ctx = ctx
        self.player = player
        self.player_id = player.id
        self.evaluator = evaluator
        self.guild = ctx.guild
        self.add_item(PositionSelect())
    
    async def ask_field_player_ratings(self, interaction, position):
        """Ask ratings for field players (CF, LW/RW, CM)"""
        eval_id = f"{interaction.user.id}-{self.player_id}"
        ratings = active_evaluations[eval_id]["ratings"]
        
        # Create embed for shooting rating
        embed = discord.Embed(
            title="🎯 Shooting Rating",
            description=f"On a scale of 1-10, how would you rate {self.player.display_name}'s shooting ability?",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Please respond with a number from 1 to 10")
        await interaction.user.send(embed=embed)
        
        try:
            # Wait for the evaluator's response
            def check(m):
                return m.author.id == interaction.user.id and m.channel.type == discord.ChannelType.private
            
            # Get shooting rating
            shooting_msg = await safe_wait_for(bot.wait_for('message', check=check), timeout=300)
            shooting = await self.validate_rating(interaction.user, shooting_msg.content)
            ratings["shooting"] = shooting
            
            # Create embed for dribbling rating
            embed = discord.Embed(
                title="🦶 Dribbling Rating",
                description=f"On a scale of 1-10, how would you rate {self.player.display_name}'s dribbling ability?",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Please respond with a number from 1 to 10")
            await interaction.user.send(embed=embed)
            
            # Get dribbling rating
            dribbling_msg = await safe_wait_for(bot.wait_for('message', check=check), timeout=300)
            dribbling = await self.validate_rating(interaction.user, dribbling_msg.content)
            ratings["dribbling"] = dribbling
            
            # Create embed for passing rating
            embed = discord.Embed(
                title="🎯 Passing Rating",
                description=f"On a scale of 1-10, how would you rate {self.player.display_name}'s passing ability?",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Please respond with a number from 1 to 10")
            await interaction.user.send(embed=embed)
            
            # Get passing rating
            passing_msg = await safe_wait_for(bot.wait_for('message', check=check), timeout=300)
            passing = await self.validate_rating(interaction.user, passing_msg.content)
            ratings["passing"] = passing
            
            # Only ask for defending if not CF
            if position != "CF":
                embed = discord.Embed(
                    title="🛡️ Defending Rating",
                    description=f"On a scale of 1-10, how would you rate {self.player.display_name}'s defending ability?",
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Please respond with a number from 1 to 10")
                await interaction.user.send(embed=embed)
                
                # Get defending rating
                defending_msg = await safe_wait_for(bot.wait_for('message', check=check), timeout=300)
                defending = await self.validate_rating(interaction.user, defending_msg.content)
                ratings["defending"] = defending
            else:
                # For CF, defending is less important, set a default rating
                ratings["defending"] = 5
            
            # Finish the evaluation and calculate the value
            await self.complete_evaluation(interaction.user)
            
        except asyncio.TimeoutError:
            await interaction.user.send("The evaluation timed out. Please start again with the !tryoutsresults command.")
            # Remove from active evaluations
            if eval_id in active_evaluations:
                del active_evaluations[eval_id]
    
    async def ask_gk_ratings(self, interaction):
        """Ask ratings specifically for goalkeepers"""
        eval_id = f"{interaction.user.id}-{self.player_id}"
        ratings = active_evaluations[eval_id]["ratings"]
        
        # Create embed for goalkeeping rating
        embed = discord.Embed(
            title="🧤 Goalkeeping Rating",
            description=f"On a scale of 1-10, how would you rate {self.player.display_name}'s goalkeeping ability?",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Please respond with a number from 1 to 10")
        await interaction.user.send(embed=embed)
        
        try:
            # Wait for the evaluator's response
            def check(m):
                return m.author.id == interaction.user.id and m.channel.type == discord.ChannelType.private
            
            # Get goalkeeping rating
            goalkeeping_msg = await safe_wait_for(bot.wait_for('message', check=check), timeout=300)
            goalkeeping = await self.validate_rating(interaction.user, goalkeeping_msg.content)
            ratings["goalkeeping"] = goalkeeping
            
            # Create embed for passing rating (GKs need passing too)
            embed = discord.Embed(
                title="🎯 Passing Rating",
                description=f"On a scale of 1-10, how would you rate {self.player.display_name}'s passing ability?",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Please respond with a number from 1 to 10")
            await interaction.user.send(embed=embed)
            
            # Get passing rating
            passing_msg = await safe_wait_for(bot.wait_for('message', check=check), timeout=300)
            passing = await self.validate_rating(interaction.user, passing_msg.content)
            ratings["passing"] = passing
            
            # For GK position, set default values for other categories
            ratings["shooting"] = 5
            ratings["dribbling"] = 5
            ratings["defending"] = 7
            
            # Finish the evaluation and calculate the value
            await self.complete_evaluation(interaction.user)
            
        except asyncio.TimeoutError:
            await interaction.user.send("The evaluation timed out. Please start again with the !tryoutsresults command.")
            # Remove from active evaluations
            if eval_id in active_evaluations:
                del active_evaluations[eval_id]
    
    async def validate_rating(self, user, rating_str):
        """Validate and normalize rating input"""
        try:
            rating = int(rating_str.strip())
            if rating < 1:
                await user.send("Rating cannot be less than 1. Setting rating to 1.")
                return 1
            elif rating > 10:
                await user.send("Rating cannot be more than 10. Setting rating to 10.")
                return 10
            return rating
        except ValueError:
            await user.send("Invalid rating. Please enter a number between 1 and 10. Setting to default rating of 5.")
            return 5
    
    async def calculate_value(self, position, ratings):
        """Calculate player value based on position and ratings"""
        # Base value calculation - 5 million per point with all 10s = 50 million
        total_points = 0
        max_points = 0
        
        if position == "CF":
            # Center Forward - Shooting and dribbling are most important
            weights = {
                "shooting": 0.4,
                "dribbling": 0.3,
                "passing": 0.2,
                "defending": 0.1,
                "goalkeeping": 0
            }
        elif position == "LW/RW":
            # Winger - Dribbling, shooting, and passing are important
            weights = {
                "shooting": 0.3,
                "dribbling": 0.4,
                "passing": 0.2,
                "defending": 0.1,
                "goalkeeping": 0
            }
        elif position == "CM":
            # Center Midfielder - Passing and defending are most important
            weights = {
                "shooting": 0.15,
                "dribbling": 0.2,
                "passing": 0.4,
                "defending": 0.25,
                "goalkeeping": 0
            }
        else:  # GK
            # Goalkeeper - Goalkeeping is by far most important
            weights = {
                "shooting": 0,
                "dribbling": 0,
                "passing": 0.2,
                "defending": 0.1,
                "goalkeeping": 0.7
            }
        
        # Calculate weighted score
        for category, weight in weights.items():
            if category in ratings:
                total_points += ratings[category] * weight * 10
                max_points += 10 * weight * 10
        
        # Normalize to get a value out of 50 million (all 10s)
        value = int((total_points / max_points if max_points > 0 else 0) * 50)
        
        return value
    
    async def complete_evaluation(self, user):
        """Complete the evaluation process and post results"""
        eval_id = f"{user.id}-{self.player_id}"
        eval_data = active_evaluations[eval_id]
        position = eval_data["position"]
        ratings = eval_data["ratings"]
        
        # Calculate player value
        value = await self.calculate_value(position, ratings)
        
        # Create the results embed for the evaluator
        embed = discord.Embed(
            title="🏆 Evaluation Complete!",
            description=f"You've completed the evaluation for {self.player.display_name}.",
            color=discord.Color.green()
        )
        
        # Add rating fields
        for category, rating in ratings.items():
            if rating > 0:  # Only show ratings that were actually provided
                emoji = "⭐" * min(5, max(1, round(rating / 2)))
                embed.add_field(
                    name=f"{category.capitalize()} Rating",
                    value=f"{rating}/10 {emoji}",
                    inline=True
                )
        
        # Add position and value
        embed.add_field(
            name="Position",
            value=position,
            inline=False
        )
        
        embed.add_field(
            name="Calculated Value",
            value=f"{value} million",
            inline=False
        )
        
        # Add footer with timestamp
        embed.set_footer(text=f"Evaluation completed on {datetime.now().strftime('%Y-%m-%d at %H:%M')}")
        
        # Send final results to evaluator
        await user.send(embed=embed)
        
        # Now send the results to the tryout results channel
        try:
            if self.guild:
                # Send the ratings to the results channel
                results_channel_id = "1350182176007917739"  # Channel for tryout results
                results_channel = self.guild.get_channel(int(results_channel_id))
                
                if results_channel:
                    # Create results embed without value
                    results_embed = discord.Embed(
                        title=f"🎮 Tryouts Results for {self.player.display_name}",
                        description=f"Evaluated by {user.mention} on {datetime.now().strftime('%Y-%m-%d at %H:%M')}",
                        color=discord.Color.blue()
                    )
                    
                    # Add player position
                    results_embed.add_field(
                        name="Position",
                        value=position,
                        inline=False
                    )
                    
                    # Add ratings
                    for category, rating in ratings.items():
                        if rating > 0 and category != "goalkeeping" or position == "GK":
                            emoji = "⭐" * min(5, max(1, round(rating / 2)))
                            results_embed.add_field(
                                name=f"{category.capitalize()}",
                                value=f"{rating}/10 {emoji}",
                                inline=True
                            )
                    
                    if self.player.avatar:
                        results_embed.set_thumbnail(url=self.player.avatar.url)
                    
                    # Send to results channel
                    await results_channel.send(embed=results_embed)
                
                # Send the value to the value channel
                value_channel_id = "1350172182038446184"  # Channel for player values
                value_channel = self.guild.get_channel(int(value_channel_id))
                
                if value_channel:
                    # Create value embed
                    value_embed = discord.Embed(
                        title=f"💰 Player Value: {self.player.display_name}",
                        description=f"Based on tryout performance evaluated by {user.mention}",
                        color=discord.Color.gold()
                    )
                    
                    value_embed.add_field(
                        name="Position",
                        value=position,
                        inline=True
                    )
                    
                    value_embed.add_field(
                        name="Calculated Value",
                        value=f"{value} million",
                        inline=True
                    )
                    
                    if self.player.avatar:
                        value_embed.set_thumbnail(url=self.player.avatar.url)
                    
                    # Send to value channel
                    await value_channel.send(embed=value_embed)
                
                # Update player roles
                try:
                    # Remove tryout role
                    tryout_role_id = "1350864967674630144"
                    tryout_role = self.guild.get_role(int(tryout_role_id))
                    if tryout_role and tryout_role in self.player.roles:
                        await self.player.remove_roles(tryout_role)
                    
                    # Add player role
                    player_role_id = "1350863646187716640"
                    player_role = self.guild.get_role(int(player_role_id))
                    if player_role and player_role not in self.player.roles:
                        await self.player.add_roles(player_role)
                    
                    # Set the player's value in the data manager
                    data_manager.set_member_value(str(self.player.id), value)
                    
                    # Notify in the channel where the command was used
                    await self.ctx.send(f"✅ Tryout evaluation for {self.player.mention} has been completed! Their value has been set to **{value} million**.")
                    
                except Exception as e:
                    logging.error(f"Error updating roles: {e}")
                    logging.error(traceback.format_exc())
                    await self.ctx.send(f"There was an issue updating roles for {self.player.mention}. Please adjust their roles manually.")
        
        except Exception as e:
            logging.error(f"Error posting evaluation results: {e}")
            logging.error(traceback.format_exc())
            await self.ctx.send(f"There was an issue posting the evaluation results for {self.player.mention}. Please try again.")
        
        # Remove from active evaluations
        if eval_id in active_evaluations:
            del active_evaluations[eval_id]
    
    def disable_all_items(self):
        """Disable all items in the view"""
        for item in self.children:
            item.disabled = True

@bot.command(name="getevaluated")
async def getevaluated_command(ctx):
    """Request to be evaluated by a trainer in the Novera server"""
    # Channel ID for evaluation requests in Novera server
    eval_requests_channel_id = 1360251844907106365
    
    try:
        # Get the evaluation requests channel
        guild = ctx.guild
        if not guild:
            await ctx.send("This command can only be used in a server, sweetie~ 💖")
            return
            
        # Make sure this is the Novera server
        if guild.id == 1350165280940228629:  # Novera Team Hub server ID
            eval_channel = bot.get_channel(eval_requests_channel_id)
            if not eval_channel:
                await ctx.send("The evaluation requests channel could not be found. Please contact Mommy or an administrator. 💋")
                return
                
            # Start loading animation
            animation_task = asyncio.create_task(
                loading_animations.animate_loading(ctx.channel, ctx.author, "eval_request")
            )
            
            try:
                # Simulate some processing time
                await asyncio.sleep(1.5)
                
                # Cancel the animation
                animation_task.cancel()
                
                # Create view with accept button
                class EvaluationRequestButton(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=None)  # No timeout for this view
                        # Add unique identifier to avoid button conflicts
                        timestamp = int(datetime.now().timestamp())
                        self.custom_id = f"eval_request_{timestamp}_{ctx.author.id}"
                    
                    @discord.ui.button(label="Accept Evaluation Request", style=discord.ButtonStyle.primary, 
                                     custom_id="accept_eval_request", emoji="✅")
                    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        """Handle evaluation request acceptance"""
                        evaluator = interaction.user
                        requester = ctx.author
                        
                        # Check if the user has the Trainers role or is the owner
                        trainer_role_id = 1350175902738419734  # Trainers role in Novera server
                        if not any(role.id == trainer_role_id for role in evaluator.roles) and evaluator.id != 654338875736588288:  # Rxcky's ID
                            await interaction.response.send_message(
                                "Oh darling, you don't have permission to accept evaluation requests. Only evaluators can accept. 💕",
                                ephemeral=True
                            )
                            return
                        
                        # Prevent evaluator from accepting their own request
                        if evaluator.id == requester.id:
                            await interaction.response.send_message(
                                "You cannot evaluate yourself, sweetie~ Please wait for another evaluator to accept. 💋",
                                ephemeral=True
                            )
                            return
                            
                        try:
                            # Disable the button
                            button.disabled = True
                            button.label = "Request Accepted"
                            await interaction.response.edit_message(view=self)
                            
                            # Create temporary evaluation channel
                            overwrites = {
                                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                                requester: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                                evaluator: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                            }
                            
                            # Get evaluator category if it exists
                            evaluation_category = None
                            for category in guild.categories:
                                if category.name.lower() == "evaluations":
                                    evaluation_category = category
                                    break
                            
                            channel_name = f"eval-{requester.name.lower()}-{evaluator.name.lower()}"
                            # Remove any invalid characters from channel name
                            channel_name = ''.join(c for c in channel_name if c.isalnum() or c == '-')
                            channel_name = channel_name[:90]  # Limit length to avoid errors
                            
                            # Create the channel
                            eval_channel = await guild.create_text_channel(
                                name=channel_name,
                                overwrites=overwrites,
                                category=evaluation_category,
                                reason=f"Evaluation channel for {requester.name}"
                            )
                            
                            # Notify in the request channel
                            await interaction.followup.send(
                                f"✅ {evaluator.mention} has accepted the evaluation request from {requester.mention}.\n"
                                f"A private channel has been created: {eval_channel.mention}"
                            )
                            
                            # Send initial message in the evaluation channel
                            class TryoutsPositionSelect(discord.ui.Select):
                                def __init__(self):
                                    options = [
                                        discord.SelectOption(label="CF (Center Forward)", value="CF", emoji="⚽"),
                                        discord.SelectOption(label="LW/RW (Winger)", value="Winger", emoji="🏃"),
                                        discord.SelectOption(label="CM (Center Midfielder)", value="CM", emoji="🧠"),
                                        discord.SelectOption(label="GK (Goalkeeper)", value="GK", emoji="🧤")
                                    ]
                                    super().__init__(
                                        placeholder="Select player position...",
                                        min_values=1,
                                        max_values=1,
                                        options=options,
                                    )
                                
                                async def callback(self, interaction: discord.Interaction):
                                    position = self.values[0]
                                    
                                    # Only allow the evaluator to use this
                                    if interaction.user.id != evaluator.id:
                                        await interaction.response.send_message(
                                            "Only the evaluator can select the position, darling~ 💕",
                                            ephemeral=True
                                        )
                                        return
                                    
                                    await interaction.response.defer()
                                    
                                    # Create prompt based on position
                                    if position in ["CF", "Winger", "CM"]:
                                        await eval_channel.send(
                                            f"## {position} Evaluation for {requester.mention}\n\n"
                                            f"Please rate the following skills from 1-10:\n\n"
                                            f"1. **Pace**: \n"
                                            f"2. **Shooting**: \n"
                                            f"3. **Passing**: \n"
                                            f"4. **Dribbling**: \n"
                                            f"5. **IQ**: \n"
                                            f"6. **Teamwork**: \n\n"
                                            f"{evaluator.mention} please fill in the ratings and submit to calculate final value."
                                        )
                                    elif position == "GK":
                                        await eval_channel.send(
                                            f"## GK Evaluation for {requester.mention}\n\n"
                                            f"Please rate the following skills from 1-10:\n\n"
                                            f"1. **Handling**: \n"
                                            f"2. **Positioning**: \n"
                                            f"3. **Reflexes**: \n"
                                            f"4. **Diving**: \n"
                                            f"5. **Speed**: \n"
                                            f"6. **Distribution**: \n\n"
                                            f"{evaluator.mention} please fill in the ratings and submit to calculate final value."
                                        )
                                    
                                    # Disable the select menu
                                    self.disabled = True
                                    await interaction.message.edit(view=self.view)
                            
                            # Create the position selection view
                            position_view = discord.ui.View(timeout=None)
                            position_view.add_item(TryoutsPositionSelect())
                            
                            await eval_channel.send(
                                f"# Player Evaluation Session\n\n"
                                f"👤 **Player:** {requester.mention}\n"
                                f"📊 **Evaluator:** {evaluator.mention}\n\n"
                                f"This channel will be used for your evaluation session. The evaluator will guide you through the process.\n"
                                f"When complete, the evaluator can close this channel.\n\n"
                                f"Please select the player's position below:",
                                view=position_view
                            )
                            
                            # Auto-delete the channel after 1 hour (running in background)
                            bot.loop.create_task(self.delete_channel_after_delay(eval_channel, 3600))
                                
                        except Exception as e:
                            logging.error(f"Error creating evaluation channel: {e}", exc_info=True)
                            await interaction.followup.send(
                                f"There was an error creating the evaluation channel: {str(e)}. Please try again later.",
                                ephemeral=True
                            )
                    
                    async def delete_channel_after_delay(self, channel, delay):
                        """Delete the channel after a specified delay"""
                        await asyncio.sleep(delay)
                        try:
                            await channel.delete(reason="Evaluation session complete (auto cleanup)")
                        except:
                            # Channel may already be deleted or we might not have permission
                            pass
                
                # Create the request view
                view = EvaluationRequestButton()
                
                # Send request to evaluation channel
                await eval_channel.send(
                    f"# New Evaluation Request\n\n"
                    f"👤 **Player:** {ctx.author.mention}\n"
                    f"🕒 **Requested:** <t:{int(datetime.now().timestamp())}:R>\n\n"
                    f"Click the button below to accept this player evaluation request:",
                    view=view
                )
                
                # Confirm to the user
                await ctx.send(
                    f"✅ Your evaluation request has been submitted to {eval_channel.mention}, darling~\n"
                    f"A lovely evaluator will accept your request soon. You'll be pinged when it's accepted. 💕"
                )
            except Exception as e:
                # Ensure animation is cancelled even if there's an error
                if not animation_task.done():
                    animation_task.cancel()
                logging.error(f"Error in getevaluated command: {e}")
                await ctx.send("There was an error submitting your evaluation request, sweetie. Please try again later. 💔")
        else:
            await ctx.send("The evaluation system is only available in the Novera server, darling~ 💖")
            
    except Exception as e:
        logging.error(f"Error in getevaluated command: {e}", exc_info=True)
        await ctx.send(f"There was an error processing your request: {str(e)}")

@bot.command(name="tryoutsresults", aliases=["tryoutrsresults", "tryoutresults"])
async def tryouts_results_command(ctx, member: Optional[discord.Member] = None, *args):
    """Submit tryouts results for a player - Trainers role only (role ID: 1350175902738419734)"""
    # EXTENSIVE LOGGING FOR DEBUGGING
    logging.info(f"*** TRYOUTS COMMAND RECEIVED from {ctx.author.name} (ID: {ctx.author.id}) ***")
    
    # Check for the case where there is no space between command and mention
    # e.g., !tryoutsresults@player instead of !tryoutsresults @player
    if member is None and '<@' in ctx.message.content:
        logging.info(f"[TRYOUTS FIX] No space detected between command and mention, attempting to extract mention")
        try:
            # Look for mention patterns
            mention_pattern = r'<@!?(\d+)>'
            mentions = re.findall(mention_pattern, ctx.message.content)
            
            if mentions:
                user_id = int(mentions[0])
                logging.info(f"[TRYOUTS FIX] Found user ID in command: {user_id}")
                member = ctx.guild.get_member(user_id)
                logging.info(f"[TRYOUTS FIX] Resolved member: {member}")
        except Exception as e:
            logging.error(f"[TRYOUTS FIX] Error trying to extract mention: {e}")
            # Continue with the command anyway, it will fail gracefully later if member is still None
    
    # Check if this message has already been processed to avoid duplicates
    message_id = str(ctx.message.id)
    if hasattr(bot, "_processed_commands") and message_id in bot._processed_commands:
        logging.warning(f"Duplicate tryoutsresults command detected for message {message_id}, ignoring.")
        return
    
    # Initialize _processed_commands if it doesn't exist
    if not hasattr(bot, "_processed_commands"):
        bot._processed_commands = {}
    # Mark this message as processed to avoid duplicates - IMPORTANT: do this EARLY
    bot._processed_commands[message_id] = time.time()
    
    # We already checked for mentions above, no need to do it again
        
    try:
        
        # Check if user has evaluator permission
        has_permission = False
        
        # HIGHEST PRIORITY - Special users who ALWAYS have permission no matter what
        # These overrides should be applied BEFORE any other permission checks
        SPECIAL_USER_IDS = [
            338378410637090818,  # Kiyora 
            1123805924885278720,  # ryguy02391
            1078879700753068103,  # RaidTheFox - to test
            1137137535567536188   # Another test account
        ]
        
        # Allow special users immediately
        if ctx.author.id in SPECIAL_USER_IDS:
            has_permission = True
            logging.info(f"[TRYOUTS AUTH] Applied special override for {ctx.author.name} (ID: {ctx.author.id})")
            
        # Debug information - log roles for troubleshooting
        if ctx.guild:
            user_roles = [f"{role.name} (ID: {role.id})" for role in ctx.author.roles]
            logging.info(f"[TRYOUTS AUTH] User {ctx.author.name} (ID: {ctx.author.id}) has roles: {', '.join(user_roles)}")
        
        # Allow bot owner
        if not has_permission and ctx.author.id == 859413883420016640:
            has_permission = True
            logging.info(f"[TRYOUTS AUTH] Granting access to {ctx.author.name} as bot owner")
        # Detailed role checking with explicit logging
        elif not has_permission and ctx.guild:
            # Try by EXACT ID MATCH first - Evaluator role in Novera server
            evaluator_role_id = 1350175902738419734  # Trainers role in Novera server (they do evaluations)
            
            # Log all user role IDs for comparison
            role_ids = [role.id for role in ctx.author.roles]
            logging.info(f"[TRYOUTS AUTH] User role IDs: {role_ids}")
            logging.info(f"[TRYOUTS AUTH] Looking for evaluator role ID: {evaluator_role_id}")
            
            # Check if evaluator role ID is in user's roles
            if evaluator_role_id in role_ids:
                has_permission = True
                logging.info(f"[TRYOUTS AUTH] Found exact role ID match")
            else:
                # Try string comparison as fallback
                has_permission = any(str(role.id) == str(evaluator_role_id) for role in ctx.author.roles)
                if has_permission:
                    logging.info(f"[TRYOUTS AUTH] Found role ID match through string comparison")
                    
            # If that didn't work, try by name (more flexible)
            if not has_permission:
                role_names = [role.name.lower() for role in ctx.author.roles]
                logging.info(f"[TRYOUTS AUTH] User role names (lowercase): {role_names}")
                target_names = ["evaluator", "tryouts", "tryouter", "tryout", "evaluators", "trainer", "trainers"]
                logging.info(f"[TRYOUTS AUTH] Looking for role names: {target_names}")
                
                for role in ctx.author.roles:
                    if role.name.lower() in target_names:
                        has_permission = True
                        logging.info(f"[TRYOUTS AUTH] Found name match: {role.name.lower()}")
                        break
            
            # Final check - if user is an admin or has manage roles permission
            if not has_permission:
                # Use the ctx.author directly for permissions checking
                author_member = ctx.author
                if hasattr(author_member, 'guild_permissions'):
                    admin_perm = author_member.guild_permissions.administrator
                    manage_roles_perm = author_member.guild_permissions.manage_roles
                    
                    logging.info(f"[TRYOUTS AUTH] User has admin permission: {admin_perm}")
                    logging.info(f"[TRYOUTS AUTH] User has manage roles permission: {manage_roles_perm}")
                    
                    if admin_perm or manage_roles_perm:
                        has_permission = True
            
            # Special user check is already done at the top of the function
            # No need to check again here
                
            # Final permission status
            if has_permission:
                logging.info(f"[TRYOUTS AUTH] User {ctx.author.name} has evaluator role or permission, granting access")
            else:
                logging.info(f"[TRYOUTS AUTH] User {ctx.author.name} does not have evaluator role or permission")
            
        if not has_permission:
            await ctx.send(random.choice(MOMMY_PERMISSION_DENIED))
            return
            
        # Make sure member is specified
        if not member:
            await ctx.send("Oh darling, you need to specify which player you're submitting tryouts results for! 💖\nUse `!tryoutsresults @player`")
            return
            
        # Don't allow self-evaluation
        if member.id == ctx.author.id:
            await ctx.send("Sweetie, you can't evaluate yourself! That would be a conflict of interest~ 💕")
            return
        
        # Check if this evaluation is already in progress
        eval_id = f"{ctx.author.id}-{member.id}"
        if eval_id in active_evaluations:
            await ctx.send(f"You're already evaluating {member.mention}! Please check your DMs to continue the evaluation or start a new one later.")
            return
        
        # Initialize the evaluation state
        active_evaluations[eval_id] = {
            "position": None,
            "ratings": {
                "shooting": 0,
                "dribbling": 0,
                "passing": 0,
                "defending": 0,
                "goalkeeping": 0
            },
            "started_at": datetime.now()
        }
        
        # Prepare the confirmation message but don't send it yet
        dm_sent_confirmation = f"✅ I've sent you a DM to start the evaluation for {member.mention}. Please check your direct messages! 💌"
        
        # Send a notification to the player being evaluated
        try:
            player_embed = discord.Embed(
                title="🎮 Tryout Evaluation Started",
                description=f"{ctx.author.mention} is evaluating your gameplay right now. Please wait for the results!",
                color=discord.Color.blue()
            )
            player_embed.set_footer(text="The evaluator will rate your performance in different categories")
            if member.avatar:
                player_embed.set_thumbnail(url=member.avatar.url)
            await member.send(embed=player_embed)
            logging.info(f"Sent evaluation notification to player {member.display_name}")
        except discord.Forbidden:
            logging.warning(f"Could not DM {member.display_name} about their evaluation.")
            # Add a note to the confirmation
            dm_sent_confirmation += f"\n(Note: I couldn't send a notification to {member.mention} - their DMs may be closed)"
        
        # Start the evaluation process via DM
        try:
            # Create position selection embed
            embed = discord.Embed(
                title="🏆 Player Evaluation",
                description=f"You're evaluating **{member.display_name}**. First, what position does this player play?",
                color=discord.Color.purple()
            )
            embed.set_footer(text="Select the player's primary position from the dropdown menu")
            
            # If player has an avatar, add it to the embed
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            
            # Send the position selection view
            view = TryoutsView(ctx, member, ctx.author)
            await ctx.author.send(embed=embed, view=view)
            
            # Now send the confirmation to the channel that the DM was sent
            await ctx.send(dm_sent_confirmation)
            
            logging.info(f"Tryouts evaluation started by {ctx.author} for {member}")
            
        except discord.Forbidden:
            await ctx.send("I can't send you a DM! Please make sure your privacy settings allow direct messages from server members.")
            # Clean up since we couldn't start the evaluation
            if eval_id in active_evaluations:
                del active_evaluations[eval_id]
        
    except Exception as e:
        logging.error(f"Error in tryoutsresults command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*")
        except:
            pass

@bot.command(name="utm")
async def untimeout_command(ctx, member: Optional[discord.Member] = None):
    """Remove a timeout from a member - owner only"""
    try:
        # Check if the command user is the owner
        if ctx.author.id != 654338875736588288:  # Owner ID
            embed = discord.Embed(
                title="⚠️ Permission Denied",
                description="This command is restricted to the server owner only.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        # If no member mentioned, show error
        if not member:
            embed = discord.Embed(
                title="❌ Missing User",
                description="Please mention the user you want to remove the timeout from.\nUsage: `!utm @username`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
            
        # Remove timeout using the profanity filter's function
        if hasattr(bot, 'profanity_filter'):
            success, message = await bot.profanity_filter.remove_timeout(ctx.guild, member.id)
            
            if success:
                embed = discord.Embed(
                    title="✅ Timeout Removed",
                    description=f"Successfully removed timeout from {member.mention}.\nTheir warnings have been reset.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to remove timeout: {message}",
                    color=discord.Color.red()
                )
                
            await ctx.send(embed=embed)
        else:
            # If profanity filter not initialized, just try to remove timeout directly
            try:
                await member.timeout(None, reason="Timeout manually removed by administrator")
                embed = discord.Embed(
                    title="✅ Timeout Removed",
                    description=f"Successfully removed timeout from {member.mention}.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to remove timeout: {str(e)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
    except Exception as e:
        logging.error(f"Error in untimeout command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(f"{random.choice(MOMMY_ERROR_VARIANTS)}\n\n*Error: {str(e)}*")
        except:
            pass

@bot.command(name="spank")
async def spank_command(ctx, member: Optional[discord.Member] = None):
    """Spank a user or get spanked yourself"""
    # Check if this message has already been processed to avoid duplicates
    message_id = str(ctx.message.id)
    if hasattr(bot, "_processed_commands") and isinstance(bot._processed_commands, dict) and message_id in bot._processed_commands:
        logging.warning(f"Duplicate spank command detected for message {message_id}, ignoring.")
        return
    
    # Initialize _processed_commands if it doesn't exist
    if not hasattr(bot, "_processed_commands"):
        bot._processed_commands = {}
    # Mark this message as processed to avoid duplicates - IMPORTANT: do this EARLY
    bot._processed_commands[message_id] = time.time()
        
    try:
        # Check if user has permission (specific role required)
        has_permission = False
        spank_role_id = 1350743813143924800  # Spank role ID
        
        # Allow if the user has the spank role
        if ctx.guild and any(role.id == spank_role_id for role in ctx.author.roles):
            has_permission = True
        
        # Deny if no permission
        if not has_permission:
            await ctx.send("Oh darling, you don't have permission to use this command! Only special members can spank others~ 💋")
            return
            
        # Check if someone is trying to spank the bot
        if member and member.id == bot.user.id:
            await ctx.send("Oh darling, you'd better not try to spank Mommy~ You might regret it! 😈💢")
            return
        
        # Permission check is already handled above
        
        # If no member is specified, Mommy spanks the sender
        if not member:
            response = utils.get_random_spank_response(None, ctx.author)
        else:
            response = utils.get_random_spank_response(ctx.author, member)
        
        # List of anime spanking GIFs - using reliable tenor links
        spank_gifs = [
            "https://media.tenor.com/6sLkGSp3wyIAAAAC/anime-spank.gif",
            "https://media.tenor.com/XGWFt1x7J-kAAAAC/spank-anime.gif",
            "https://media.tenor.com/BwTKGTzx0SEAAAAC/anime-spank.gif",
            "https://media.tenor.com/nXVpUaJJQKwAAAAC/anime-spanking.gif",
            "https://media.tenor.com/sG0mcfKEpF0AAAAC/anime-spank.gif",
            "https://media.tenor.com/J-MJKd9pZ_wAAAAC/spanking-spank.gif",
            "https://media.tenor.com/HuoVitvS8vQAAAAC/anime-spank.gif",
            "https://media.tenor.com/b4c__o_7cGgAAAAC/anime-spank.gif",
            "https://media.tenor.com/FMC3OWRcVSEAAAAC/anime-spanking.gif",
            "https://media.tenor.com/WyRNm0VL9yQAAAAC/anime-spank.gif"
        ]
        
        # Create an attractive embed with the response and a random GIF
        embed = discord.Embed(
            title="👋 SPANK! 👋",
            description=response,
            color=discord.Color.red()
        )
        
        # Add a random spank GIF
        embed.set_image(url=random.choice(spank_gifs))
        
        # Set a footer with a timestamp
        embed.set_footer(text="Naughty members get spanked by Mommy!")
        embed.timestamp = ctx.message.created_at
        
        await ctx.send(embed=embed)
        logging.info(f"Spank command executed by {ctx.author}")
    except Exception as e:
        logging.error(f"Error in spank command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

# Anteup command moved below to avoid duplication
        
@bot.command(name="cleanserver", aliases=["clearserver", "purgeserver"])
async def cleanserver_command(ctx):
    """Owner-only command to scan and delete all profanity in the server"""
    # Check if user is owner
    if ctx.author.id != 654338875736588288:  # Owner ID
        await ctx.send("Sorry darling, only my owner can use this command~ 💔")
        return
        
    # Send initial status message
    status_message = await ctx.send("🔍 **URGENT: Starting server-wide scan for profanity**. This will remove ALL offensive content. Please wait...")
    
    # Track statistics
    total_channels = 0
    total_messages_scanned = 0
    total_messages_deleted = 0
    deleted_by_channel = {}
    
    try:
        # Get all text channels in the server
        text_channels = [ch for ch in ctx.guild.channels if isinstance(ch, discord.TextChannel) and ch.permissions_for(ctx.guild.me).read_messages]
        total_channels = len(text_channels)
        
        # Create a progress embed
        progress_embed = discord.Embed(
            title="🧹 Server Cleaning in Progress",
            description="Scanning through all channels for inappropriate content...",
            color=0xFF9900
        )
        progress_embed.add_field(name="Total Channels", value=f"{total_channels}", inline=True)
        progress_embed.add_field(name="Channels Scanned", value="0", inline=True)
        progress_embed.add_field(name="Messages Deleted", value="0", inline=True)
        progress_embed.set_footer(text="This process may take several minutes. Please wait.")
        
        # Update the status message with the embed
        await status_message.edit(content=None, embed=progress_embed)
        
        # Process each channel
        for i, channel in enumerate(text_channels):
            channel_messages_scanned = 0
            channel_messages_deleted = 0
            
            try:
                # Get message history from the channel (limit to last 500 messages per channel)
                async for message in channel.history(limit=500):
                    channel_messages_scanned += 1
                    total_messages_scanned += 1
                    
                    # Skip messages from the bot itself
                    if message.author.id == bot.user.id:
                        continue
                    
                    # Check if the message contains profanity using the profanity filter
                    contains_profanity, matched_term = profanity_filter.check_message(message)
                    
                    if contains_profanity:
                        try:
                            # Delete the message
                            await message.delete()
                            channel_messages_deleted += 1
                            total_messages_deleted += 1
                            
                            # Log to console
                            logging.warning(f"DELETED in channel #{channel.name}: {message.content} from {message.author.name}")
                            
                        except Exception as delete_error:
                            logging.error(f"Failed to delete message in {channel.name}: {delete_error}")
                
                # Store channel stats
                if channel_messages_deleted > 0:
                    deleted_by_channel[channel.name] = channel_messages_deleted
                
                # Update progress every 3 channels
                if i % 3 == 0 or i == len(text_channels) - 1:
                    progress_embed.set_field_at(1, name="Channels Scanned", value=f"{i+1}/{total_channels}", inline=True)
                    progress_embed.set_field_at(2, name="Messages Deleted", value=f"{total_messages_deleted}", inline=True)
                    await status_message.edit(embed=progress_embed)
                    
            except Exception as channel_error:
                logging.error(f"Error scanning channel {channel.name}: {channel_error}")
                continue
        
        # Create completion embed
        completion_embed = discord.Embed(
            title="✅ Server Cleaning Complete",
            description=f"**URGENT CLEANING FINISHED**\n\nScanned {total_messages_scanned} messages across {total_channels} channels.\nDeleted {total_messages_deleted} messages containing inappropriate content.",
            color=0x00FF00
        )
        
        # Add channel-specific stats (top 10 most affected channels)
        if deleted_by_channel:
            sorted_channels = sorted(deleted_by_channel.items(), key=lambda x: x[1], reverse=True)
            channels_report = "\n".join([f"#{channel}: {count} message(s)" for channel, count in sorted_channels[:10]])
            
            if channels_report:
                completion_embed.add_field(
                    name="Messages Deleted by Channel",
                    value=channels_report if channels_report else "None",
                    inline=False
                )
        
        # Update final status
        if total_messages_deleted == 0:
            completion_embed.add_field(
                name="Status",
                value="✅ No inappropriate content found! The server is clean.",
                inline=False
            )
        else:
            completion_embed.add_field(
                name="Status",
                value=f"✅ Successfully removed {total_messages_deleted} instances of inappropriate content.",
                inline=False
            )
            
        completion_embed.set_footer(text=f"Operation completed at {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # Send completion message
        await status_message.edit(content=None, embed=completion_embed)
        
    except Exception as e:
        logging.error(f"Error in cleanserver command: {e}")
        error_embed = discord.Embed(
            title="❌ Error During Server Cleaning",
            description=f"An error occurred while cleaning the server:\n```{str(e)}```\n\nPartial results: Scanned {total_messages_scanned} messages, deleted {total_messages_deleted} messages.",
            color=0xFF0000
        )
        await status_message.edit(content=None, embed=error_embed)
# Wager Match System - Interactive Components
class MatchTypeSelect(discord.ui.Select):
    """Match type selection dropdown for wager matches"""
    def __init__(self, view_id):
        # Create a unique timestamp-based ID
        timestamp = int(datetime.now().timestamp() * 1000)
        options = [
            discord.SelectOption(label="1v1", description="One versus one match", emoji="🥊"),
            discord.SelectOption(label="2v2", description="Two versus two match", emoji="👥"),
            discord.SelectOption(label="3v3", description="Three versus three match", emoji="👥"),
            discord.SelectOption(label="5v5", description="Five versus five match", emoji="👨‍👩‍👧‍👦")
        ]
        super().__init__(
            placeholder="Select match type...", 
            min_values=1, 
            max_values=1, 
            options=options, 
            custom_id=f"match_type_select_{view_id}_{timestamp}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            logging.info(f"Match type selection callback from user {interaction.user.name} - Selected: {self.values[0]}")
            
            # Verify it's the right user
            if interaction.user.id != self.view.user.id:
                await interaction.response.send_message("This wager setup is not yours to control!", ephemeral=True)
                return
                
            # Store the selected match type in the view's state
            self.view.match_type = self.values[0]
            # Update the view based on the match type
            await self.view.update_for_match_type(interaction)
            logging.info(f"User {interaction.user.id} selected match type {self.values[0]}")
        except Exception as e:
            logging.error(f"Error in match type selection: {e}", exc_info=True)
            try:
                await interaction.response.send_message("There was an error processing your selection. Please try again.", ephemeral=True)
            except:
                try:
                    await interaction.followup.send("There was an error processing your selection. Please try again.", ephemeral=True)
                except:
                    logging.error(f"Failed to send any error message for match type selection")
                    pass

class RegionSelect(discord.ui.Select):
    """Region selection dropdown for wager matches"""
    def __init__(self, view_id):
        # Create a unique timestamp-based ID
        timestamp = int(datetime.now().timestamp() * 1000)
        options = [
            discord.SelectOption(label="NA", description="North America", emoji="🌎"),
            discord.SelectOption(label="EU", description="Europe", emoji="🌍")
        ]
        super().__init__(
            placeholder="Select region...", 
            min_values=1, 
            max_values=1, 
            options=options, 
            custom_id=f"region_select_{view_id}_{timestamp}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            logging.info(f"Region selection callback from user {interaction.user.name} - Selected: {self.values[0]}")
            
            # Verify it's the right user
            if interaction.user.id != self.view.user.id:
                await interaction.response.send_message("This wager setup is not yours to control!", ephemeral=True)
                return
                
            # Store the selected region in the view's state
            self.view.region = self.values[0]
            await interaction.response.send_message(f"Region set to: {self.values[0]}", ephemeral=True)
            self.view.update_completion_status()
            # Update the message view to reflect the changes
            if self.view.message:
                await self.view.message.edit(view=self.view)
            logging.info(f"User {interaction.user.id} selected region {self.values[0]}")
        except Exception as e:
            logging.error(f"Error in region selection: {e}", exc_info=True)
            try:
                await interaction.response.send_message("There was an error processing your selection. Please try again.", ephemeral=True)
            except:
                try:
                    await interaction.followup.send("There was an error processing your selection. Please try again.", ephemeral=True)
                except:
                    logging.error(f"Failed to send any error message for region selection")
                    pass

class AbilitiesSelect(discord.ui.Select):
    """Abilities toggle selection for wager matches"""
    def __init__(self, view_id):
        # Create a unique timestamp-based ID
        timestamp = int(datetime.now().timestamp() * 1000)
        options = [
            discord.SelectOption(label="Yes", description="Abilities allowed", emoji="✅"),
            discord.SelectOption(label="No", description="No abilities", emoji="❌")
        ]
        super().__init__(
            placeholder="Abilities allowed?", 
            min_values=1, 
            max_values=1, 
            options=options, 
            custom_id=f"abilities_select_{view_id}_{timestamp}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            logging.info(f"Abilities selection callback from user {interaction.user.name} - Selected: {self.values[0]}")
            
            # Verify it's the right user
            if interaction.user.id != self.view.user.id:
                await interaction.response.send_message("This wager setup is not yours to control!", ephemeral=True)
                return
                
            # Store the selection in the view's state
            self.view.abilities = self.values[0] == "Yes"
            await interaction.response.send_message(f"Abilities set to: {self.values[0]}", ephemeral=True)
            self.view.update_completion_status()
            # Update the message view to reflect the changes
            if self.view.message:
                await self.view.message.edit(view=self.view)
            logging.info(f"User {interaction.user.id} set abilities to {self.values[0]}")
        except Exception as e:
            logging.error(f"Error in abilities selection: {e}", exc_info=True)
            try:
                await interaction.response.send_message("There was an error processing your selection. Please try again.", ephemeral=True)
            except:
                try:
                    await interaction.followup.send("There was an error processing your selection. Please try again.", ephemeral=True)
                except:
                    logging.error(f"Failed to send any error message for abilities selection")
                    pass

class RealGKSelect(discord.ui.Select):
    """Real GK selection for wager matches (only for 2v2 and 3v3)"""
    def __init__(self, view_id):
        # Create a unique timestamp-based ID
        timestamp = int(datetime.now().timestamp() * 1000)
        options = [
            discord.SelectOption(label="Yes", description="Real goalkeeper", emoji="🧤"),
            discord.SelectOption(label="No", description="No real goalkeeper", emoji="🚫")
        ]
        super().__init__(
            placeholder="Real goalkeeper?", 
            min_values=1, 
            max_values=1, 
            options=options, 
            custom_id=f"real_gk_select_{view_id}_{timestamp}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            logging.info(f"Real GK selection callback from user {interaction.user.name} - Selected: {self.values[0]}")
            
            # Verify it's the right user
            if interaction.user.id != self.view.user.id:
                await interaction.response.send_message("This wager setup is not yours to control!", ephemeral=True)
                return
                
            # Store the selection in the view's state
            self.view.real_gk = self.values[0] == "Yes"
            await interaction.response.send_message(f"Real goalkeeper set to: {self.values[0]}", ephemeral=True)
            self.view.update_completion_status()
            # Update the message view to reflect the changes
            if self.view.message:
                await self.view.message.edit(view=self.view)
            logging.info(f"User {interaction.user.id} set real GK to {self.values[0]}")
        except Exception as e:
            logging.error(f"Error in real GK selection: {e}", exc_info=True)
            try:
                await interaction.response.send_message("There was an error processing your selection. Please try again.", ephemeral=True)
            except:
                try:
                    await interaction.followup.send("There was an error processing your selection. Please try again.", ephemeral=True)
                except:
                    logging.error(f"Failed to send any error message for real GK selection")
                    pass

class WagerSetupView(discord.ui.View):
    """Interactive view for setting up a wager match"""
    def __init__(self, ctx, amount):
        super().__init__(timeout=300)  # 5 minute timeout
        self.ctx = ctx
        self.amount = amount
        self.user = ctx.author
        self.message = None
        self.roblox_username = None
        self.roblox_link = None
        self.match_type = None
        self.region = None
        self.abilities = None
        self.real_gk = None
        self.is_complete = False
        
        # Add the match type selection dropdown first with user ID
        self.add_item(MatchTypeSelect(self.user.id))
        # Other dropdowns will be added after match type is selected
        
    async def update_for_match_type(self, interaction):
        """Update the view based on the selected match type"""
        # Clear items except match type selection which is the first item
        while len(self.children) > 1:
            self.remove_item(self.children[-1])
            
        # Add common selectors with user ID
        self.add_item(RegionSelect(self.user.id))
        self.add_item(AbilitiesSelect(self.user.id))
        
        # Add real GK selector only for 2v2 and 3v3
        if self.match_type in ["2v2", "3v3"]:
            self.add_item(RealGKSelect(self.user.id))
        
        # Add username submission button with callback
        username_button = discord.ui.Button(
            label="Submit Roblox Username",
            custom_id=f"roblox_username_btn_{self.user.id}",
            style=discord.ButtonStyle.primary
        )
        username_button.callback = self.username_button_callback
        self.add_item(username_button)
        
        # Add optional Roblox link button with callback
        link_button = discord.ui.Button(
            label="Add Roblox Link (Optional)",
            custom_id=f"roblox_link_btn_{self.user.id}",
            style=discord.ButtonStyle.secondary
        )
        link_button.callback = self.link_button_callback
        self.add_item(link_button)
        
        # Add confirm button with callback
        confirm_button = discord.ui.Button(
            label="Create Wager Match",
            custom_id=f"confirm_wager_btn_{self.user.id}",
            style=discord.ButtonStyle.success, 
            disabled=True
        )
        confirm_button.callback = self.confirm_button_callback
        self.add_item(confirm_button)
        
        await interaction.response.edit_message(
            content=f"Setting up a {self.match_type} wager match for {self.amount} million. Please complete all selections:",
            view=self
        )
        
    async def username_button_callback(self, interaction):
        """Handle Roblox username button click"""
        try:
            # Log interaction attempt
            logging.info(f"Username button clicked by {interaction.user.name} (ID: {interaction.user.id})")
            
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("This wager setup is not yours to control!", ephemeral=True)
                return
                
            # Create a timestamp-based unique ID
            timestamp = int(datetime.now().timestamp())
            
            # Create a modal for username input with unique custom_id
            modal = discord.ui.Modal(
                title="Roblox Username",
                custom_id=f"username_modal_{interaction.user.id}_{timestamp}"
            )
            
            username_input = discord.ui.TextInput(
                label="Your Roblox Username",
                custom_id=f"username_input_{timestamp}",
                style=discord.TextStyle.short,
                placeholder="Enter your Roblox username",
                required=True
            )
            modal.add_item(username_input)
            
            # Define what happens when the modal is submitted
            async def modal_callback(modal_interaction):
                try:
                    self.roblox_username = username_input.value
                    logging.info(f"Username set to {self.roblox_username} for user {interaction.user.name}")
                    await modal_interaction.response.send_message(
                        f"Roblox username set to: {self.roblox_username}", 
                        ephemeral=True
                    )
                    self.update_completion_status()
                    await self.message.edit(view=self)
                except Exception as modal_error:
                    logging.error(f"Error in username modal callback: {modal_error}")
                    try:
                        await modal_interaction.response.send_message(
                            "There was an error processing your username. Please try again.",
                            ephemeral=True
                        )
                    except:
                        try:
                            await modal_interaction.followup.send(
                                "There was an error processing your username. Please try again.",
                                ephemeral=True
                            )
                        except:
                            logging.error("Failed to send error message for username modal")
                
            # Set the callback
            modal.callback = modal_callback
            
            # Send the modal with better error handling
            try:
                await interaction.response.send_modal(modal)
                logging.info(f"Successfully sent username modal to {interaction.user.name}")
            except discord.errors.NotFound as nf_error:
                logging.error(f"Interaction not found when sending username modal: {nf_error}")
                try:
                    await interaction.followup.send(
                        "The interaction expired. Please try clicking the button again.",
                        ephemeral=True
                    )
                except:
                    logging.error("Failed to send followup message after NotFound error")
            except discord.errors.InteractionResponded as ir_error:
                logging.error(f"Interaction already responded error: {ir_error}")
                try:
                    await interaction.followup.send(
                        "There was an error with your request. Please try again.",
                        ephemeral=True
                    )
                except:
                    logging.error("Failed to send followup message after InteractionResponded error")
        except Exception as e:
            logging.error(f"Error in username button callback: {e}")
            # Try to respond
            try:
                await interaction.response.send_message(
                    "Sorry, there was an error. Please try again.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        "Sorry, there was an error. Please try again.",
                        ephemeral=True
                    )
                except:
                    logging.error("All attempts to respond to username button failed")
        
    async def link_button_callback(self, interaction):
        """Handle Roblox link button click"""
        try:
            # Log interaction attempt
            logging.info(f"Link button clicked by {interaction.user.name} (ID: {interaction.user.id})")
            
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("This wager setup is not yours to control!", ephemeral=True)
                return
                
            # Create a timestamp-based unique ID
            timestamp = int(datetime.now().timestamp())
            
            # Create a modal for link input with unique custom_id
            modal = discord.ui.Modal(
                title="Roblox Link (Optional)",
                custom_id=f"link_modal_{interaction.user.id}_{timestamp}"
            )
            
            link_input = discord.ui.TextInput(
                label="Your Roblox Profile Link",
                custom_id=f"link_input_{timestamp}",
                style=discord.TextStyle.short,
                placeholder="https://www.roblox.com/users/...",
                required=False
            )
            modal.add_item(link_input)
            
            # Define what happens when the modal is submitted
            async def modal_callback(modal_interaction):
                try:
                    self.roblox_link = link_input.value
                    logging.info(f"Link set to {self.roblox_link} for user {interaction.user.name}")
                    await modal_interaction.response.send_message(
                        f"Roblox link added: {self.roblox_link}", 
                        ephemeral=True
                    )
                    self.update_completion_status()
                    await self.message.edit(view=self)
                except Exception as modal_error:
                    logging.error(f"Error in link modal callback: {modal_error}")
                    try:
                        await modal_interaction.response.send_message(
                            "There was an error processing your link. Please try again.",
                            ephemeral=True
                        )
                    except:
                        try:
                            await modal_interaction.followup.send(
                                "There was an error processing your link. Please try again.",
                                ephemeral=True
                            )
                        except:
                            logging.error("Failed to send error message for link modal")
                
            # Set the callback
            modal.callback = modal_callback
            
            # Send the modal with better error handling
            try:
                await interaction.response.send_modal(modal)
                logging.info(f"Successfully sent link modal to {interaction.user.name}")
            except discord.errors.NotFound as nf_error:
                logging.error(f"Interaction not found when sending link modal: {nf_error}")
                try:
                    await interaction.followup.send(
                        "The interaction expired. Please try clicking the button again.",
                        ephemeral=True
                    )
                except:
                    logging.error("Failed to send followup message after NotFound error")
            except discord.errors.InteractionResponded as ir_error:
                logging.error(f"Interaction already responded error: {ir_error}")
                try:
                    await interaction.followup.send(
                        "There was an error with your request. Please try again.",
                        ephemeral=True
                    )
                except:
                    logging.error("Failed to send followup message after InteractionResponded error")
        except Exception as e:
            logging.error(f"Error in link button callback: {e}")
            # Try to respond
            try:
                await interaction.response.send_message(
                    "Sorry, there was an error. Please try again.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        "Sorry, there was an error. Please try again.",
                        ephemeral=True
                    )
                except:
                    logging.error("All attempts to respond to link button failed")
        
    async def confirm_button_callback(self, interaction):
        """Handle confirm button click"""
        try:
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("This wager setup is not yours to control!", ephemeral=True)
                return
                
            # Check if setup is complete
            if not self.is_complete:
                await interaction.response.send_message(
                    "Please complete all required information before creating the wager match.",
                    ephemeral=True
                )
                return
                
            # Create and post the wager match
            # Get the right channel ID based on match type
            channel_ids = {
                "1v1": 1351037569592328293,
                "2v2": 1351037618606964849,
                "3v3": 1351037659455295570,
                "5v5": 1351037705961607168
            }
            
            # Get the appropriate channel
            channel_id = channel_ids.get(self.match_type)
            if not channel_id:
                await interaction.response.send_message(
                    "Error: Invalid match type. Please start over with the !anteup command.",
                    ephemeral=True
                )
                return
                
            channel = interaction.client.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message(
                    "Error: Couldn't find the appropriate channel for this match type. Please contact an admin.",
                    ephemeral=True
                )
                return
            
            # Create an embed for the wager match
            embed = discord.Embed(
                title=f"💰 {self.match_type} Wager Match",
                description=f"{self.user.mention} has created a {self.match_type} wager for {self.amount} million!",
                color=discord.Color.gold()
            )
            
            # Add match details
            embed.add_field(name="Match Type", value=self.match_type, inline=True)
            embed.add_field(name="Amount", value=f"{self.amount} million", inline=True)
            embed.add_field(name="Region", value=self.region, inline=True)
            embed.add_field(name="Abilities", value="Enabled" if self.abilities else "Disabled", inline=True)
            
            if self.match_type in ["2v2", "3v3"] and self.real_gk is not None:
                embed.add_field(name="Real GK", value="Yes" if self.real_gk else "No", inline=True)
            
            embed.add_field(name="Created By", value=self.user.display_name, inline=False)
            
            if self.user.avatar:
                embed.set_thumbnail(url=self.user.avatar.url)
            
            try:
                # Create the wager match view
                match_view = WagerMatchView(
                    creator=self.user,
                    match_type=self.match_type,
                    amount=self.amount,
                    region=self.region,
                    abilities=self.abilities,
                    real_gk=self.real_gk,
                    roblox_username=self.roblox_username,
                    roblox_link=self.roblox_link
                )
                
                # Post the wager match in the appropriate channel
                await channel.send(embed=embed, view=match_view)
                
                # Notify the user
                await interaction.response.send_message(
                    f"Your {self.match_type} wager match for {self.amount} million has been posted in the appropriate channel!",
                    ephemeral=True
                )
                
                # Clean up the setup message
                try:
                    for item in self.children:
                        item.disabled = True
                    if self.message:
                        await self.message.edit(
                            content=f"Your {self.match_type} wager match for {self.amount} million has been posted!",
                            view=self
                        )
                except Exception as e:
                    logging.error(f"Error updating setup message: {e}", exc_info=True)
                    
                logging.info(f"User {interaction.user.id} successfully created a {self.match_type} wager match for {self.amount} million")
                
            except Exception as posting_error:
                logging.error(f"Error posting wager match: {posting_error}", exc_info=True)
                await interaction.response.send_message(
                    "There was an error creating your wager match. Please try again or contact an admin.",
                    ephemeral=True
                )
                
        except Exception as e:
            logging.error(f"Error in confirm button callback: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "There was an error creating your wager match. Please try again or use the !anteup command to start over.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        "There was an error creating your wager match. Please try again or use the !anteup command to start over.",
                        ephemeral=True
                    )
                except:
                    pass
    
    def update_completion_status(self):
        """Update the 'Create Wager Match' button based on completion status"""
        # Get the confirm button (last button)
        confirm_button = self.children[-1]
        
        # Basic requirements for all match types
        requirements_met = all([
            self.match_type,
            self.region,
            self.abilities is not None,
            self.roblox_username
        ])
        
        # Add requirement for real_gk if match type is 2v2 or 3v3
        if self.match_type in ["2v2", "3v3"]:
            requirements_met = requirements_met and self.real_gk is not None
            
        # Update button state
        confirm_button.disabled = not requirements_met
        self.is_complete = requirements_met
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can interact with this view"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This wager setup is not yours to control!", 
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self):
        """Handle timeout by disabling all items"""
        for item in self.children:
            item.disabled = True
        
        try:
            await self.message.edit(
                content="⏱️ Wager setup timed out. Please start over with the `!anteup` command.", 
                view=self
            )
        except:
            pass

class JoinWagerButton(discord.ui.Button):
    """Button for joining a wager match"""
    def __init__(self, slot_id, team_id, match_type="1v1", wager_id=None, filled=False, user=None):
        self.slot_id = slot_id
        self.team_id = team_id
        self.user = user
        
        # Generate a more unique ID using milliseconds timestamp
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Generate a unique ID for this wager/button if not provided
        if not wager_id:
            wager_id = timestamp
        
        try:
            if filled:
                display_name = user.display_name if user else "Filled"
                # Even filled buttons need custom_ids for persistent views with timestamp for uniqueness
                super().__init__(
                    label=f"Slot {slot_id} (Team {team_id}): {display_name}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"filled_wager_{match_type}_{team_id}_{slot_id}_{wager_id}_{timestamp}",
                    disabled=True
                )
            else:
                super().__init__(
                    label=f"Join Slot {slot_id} (Team {team_id})",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"join_wager_{match_type}_{team_id}_{slot_id}_{wager_id}_{timestamp}"
                )
                
            # Store timestamp for debugging
            self.created_at = timestamp
            
        except Exception as e:
            logging.error(f"Error initializing JoinWagerButton: {e}", exc_info=True)
            # Default initialization in case of error - still needs a unique custom_id
            super().__init__(
                label=f"Slot {slot_id}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"error_wager_{match_type}_{team_id}_{slot_id}_{wager_id}_{timestamp}",
                disabled=True
            )
    
    async def callback(self, interaction: discord.Interaction):
        try:
            logging.info(f"Join button clicked by {interaction.user.name} (ID: {interaction.user.id}) for team {self.team_id}, slot {self.slot_id}")
            
            # Additional debug info
            logging.debug(f"Button ID: {self.custom_id}, Created at: {self.created_at}")
            
            # Make sure the view exists
            if not hasattr(self, 'view') or self.view is None:
                logging.error(f"View not found in JoinWagerButton for team {self.team_id}, slot {self.slot_id}")
                await interaction.response.send_message(
                    "There was an error with this match. Please try a different one or use !anteup to create a new match.",
                    ephemeral=True
                )
                return
                
            # Call the view's handler
            await self.view.handle_join(interaction, self.team_id, self.slot_id)
            logging.info(f"User {interaction.user.id} joined wager match team {self.team_id}, slot {self.slot_id}")
            
        except Exception as e:
            logging.error(f"Error in JoinWagerButton callback: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "There was an error joining the wager match. Please try again.",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                try:
                    await interaction.followup.send(
                        "There was an error joining the wager match. Please try again.",
                        ephemeral=True
                    )
                except:
                    logging.error(f"Failed to send followup message after join button click")
            except discord.errors.NotFound:
                logging.error(f"Interaction not found when responding to join button click")
            except Exception as resp_error:
                logging.error(f"Unexpected error when responding to join button: {resp_error}")
                try:
                    await interaction.followup.send(
                        "There was an error joining the wager match. Please try again.",
                        ephemeral=True
                    )
                except:
                    logging.error(f"Failed to send any error message for wager button click")
                    pass

class WagerMatchView(discord.ui.View):
    """View for a posted wager match with join buttons"""
    def __init__(self, creator, match_type, amount, region, abilities, real_gk=None, roblox_username=None, roblox_link=None):
        super().__init__(timeout=None)  # No timeout for wager posts
        self.creator = creator
        self.match_type = match_type
        self.amount = amount
        self.region = region
        self.abilities = abilities
        self.real_gk = real_gk
        self.roblox_username = roblox_username
        self.roblox_link = roblox_link
        
        # Initialize slots for the teams based on match type
        self.slots = {}
        self.create_slots()
        
        # Add join buttons based on match type
        self.create_buttons()
    
    def create_slots(self):
        """Create team slots based on match type"""
        match self.match_type:
            case "1v1":
                # 2 slots: Creator in team 1, one open slot in team 2
                self.slots = {
                    1: {1: self.creator},  # Team 1, Slot 1: Creator
                    2: {1: None}            # Team 2, Slot 1: Open
                }
            case "2v2":
                # 4 slots: Creator in team 1, rest are open
                self.slots = {
                    1: {1: self.creator, 2: None},  # Team 1: Creator + open
                    2: {1: None, 2: None}          # Team 2: Both open
                }
            case "3v3":
                # 6 slots: Creator in team 1, rest are open
                self.slots = {
                    1: {1: self.creator, 2: None, 3: None},  # Team 1: Creator + 2 open
                    2: {1: None, 2: None, 3: None}          # Team 2: All open
                }
            case "5v5":
                # 10 slots: Creator in team 1, rest are open
                self.slots = {
                    1: {1: self.creator, 2: None, 3: None, 4: None, 5: None},  # Team 1: Creator + 4 open
                    2: {1: None, 2: None, 3: None, 4: None, 5: None}          # Team 2: All open
                }
    
    def create_buttons(self):
        """Create buttons for joining the match"""
        try:
            # Clear existing buttons
            self.clear_items()
            
            # Create a unique ID for this wager match with millisecond precision
            wager_id = int(datetime.now().timestamp() * 1000)
            logging.info(f"Creating buttons for wager match ID: {wager_id}")
            
            # Add buttons for each slot
            for team_id, slots in self.slots.items():
                for slot_id, user in slots.items():
                    try:
                        # Skip creator's slot
                        if team_id == 1 and slot_id == 1:
                            button = JoinWagerButton(
                                slot_id=slot_id, 
                                team_id=team_id, 
                                match_type=self.match_type,
                                wager_id=wager_id,
                                filled=True, 
                                user=self.creator
                            )
                            self.add_item(button)
                            logging.debug(f"Added creator button: {button.custom_id}")
                        else:
                            if user:  # Slot is filled
                                button = JoinWagerButton(
                                    slot_id=slot_id, 
                                    team_id=team_id, 
                                    match_type=self.match_type,
                                    wager_id=wager_id,
                                    filled=True, 
                                    user=user
                                )
                                self.add_item(button)
                                logging.debug(f"Added filled slot button: {button.custom_id}")
                            else:  # Slot is open
                                button = JoinWagerButton(
                                    slot_id=slot_id, 
                                    team_id=team_id,
                                    match_type=self.match_type,
                                    wager_id=wager_id
                                )
                                self.add_item(button)
                                logging.debug(f"Added open slot button: {button.custom_id}")
                    except Exception as slot_error:
                        logging.error(f"Error adding button for team {team_id}, slot {slot_id}: {slot_error}")
                        # Continue with other slots to maintain functionality
                        continue
        except Exception as e:
            logging.error(f"Error in create_buttons: {e}", exc_info=True)
    
    async def handle_join(self, interaction: discord.Interaction, team_id, slot_id):
        """Handle a user clicking to join a slot"""
        try:
            logging.info(f"Processing join request from {interaction.user.name} (ID: {interaction.user.id}) for team {team_id}, slot {slot_id}")
            
            # Validate key parameters
            if not isinstance(team_id, int) or not isinstance(slot_id, int):
                logging.error(f"Invalid team_id or slot_id type: team_id={type(team_id)}, slot_id={type(slot_id)}")
                await interaction.response.send_message(
                    "There was an error with this match. Please try a different one.",
                    ephemeral=True
                )
                return
                
            # Check if team_id and slot_id are valid for this match
            if team_id not in self.slots:
                logging.error(f"Invalid team_id: {team_id} not in {list(self.slots.keys())}")
                await interaction.response.send_message(
                    "This team doesn't exist in the current match.",
                    ephemeral=True
                )
                return
                
            if slot_id not in self.slots[team_id]:
                logging.error(f"Invalid slot_id: {slot_id} not in {list(self.slots[team_id].keys())}")
                await interaction.response.send_message(
                    "This slot doesn't exist in the selected team.",
                    ephemeral=True
                )
                return
                
            # Check if the slot is already filled
            if self.slots[team_id][slot_id] is not None:
                logging.warning(f"Slot already filled: team {team_id}, slot {slot_id} by {self.slots[team_id][slot_id].name}")
                await interaction.response.send_message(
                    "This slot is already filled by someone else.",
                    ephemeral=True
                )
                return
                
            # Make sure the user isn't already in the match
            for t_id, slots in self.slots.items():
                for s_id, user in slots.items():
                    if user and user.id == interaction.user.id:
                        await interaction.response.send_message(
                            "You're already in this match!", 
                            ephemeral=True
                        )
                        return
            
            # Check if user has enough value for this wager
            user_id = str(interaction.user.id)
            try:
                current_value = data_manager.get_member_value(user_id)
                logging.info(f"User {interaction.user.name} has value: {current_value}, wager amount: {self.amount}")
                
                if current_value < self.amount:
                    await interaction.response.send_message(
                        f"Sorry, you don't have enough value to join this match. You need at least {self.amount} million.", 
                        ephemeral=True
                    )
                    return
            except Exception as value_error:
                logging.error(f"Error checking user value: {value_error}")
                # Use a safe default approach - let them join even if we can't verify value
                logging.warning(f"Allowing user {interaction.user.name} to join despite value check error")
            
            # Update the slot
            self.slots[team_id][slot_id] = interaction.user
            logging.info(f"Updated slot data: team {team_id}, slot {slot_id} filled by {interaction.user.name}")
            
            # Recreate the buttons to reflect the changes
            try:
                self.create_buttons()
                logging.info(f"Successfully recreated buttons after {interaction.user.name} joined")
            except Exception as button_error:
                logging.error(f"Error recreating buttons: {button_error}")
                # Continue anyway since the data is already updated
            
            # Update the message
            try:
                await interaction.response.edit_message(view=self)
                logging.info(f"Successfully updated message view after {interaction.user.name} joined")
            except discord.errors.NotFound:
                logging.error(f"Interaction not found when updating message for {interaction.user.name}")
                await interaction.followup.send(
                    "You've joined the match, but I couldn't update the message. The slot has been reserved for you.",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                logging.error(f"Interaction already responded when updating message for {interaction.user.name}")
                try:
                    await interaction.followup.send(
                        "You've joined the match!",
                        ephemeral=True
                    )
                except:
                    logging.error(f"Failed to send followup for {interaction.user.name}")
            except Exception as response_error:
                logging.error(f"Error responding to interaction: {response_error}")
                try:
                    await interaction.followup.send(
                        "You've joined the match, but I couldn't update the message. The slot has been reserved for you.",
                        ephemeral=True
                    )
                except:
                    logging.error(f"Failed to send followup after response error for {interaction.user.name}")
            
            # Notify the user they joined successfully
            try:
                await interaction.user.send(
                    f"You've joined a {self.match_type} wager match for {self.amount} million! " +
                    f"Please wait for all slots to be filled. You'll be notified when the match is ready."
                )
                logging.info(f"Sent join confirmation DM to {interaction.user.name}")
            except Exception as dm_error:
                logging.warning(f"Failed to DM user {interaction.user.name}: {dm_error}")
                # Failed to DM user, not a critical error
            
            # Check if the match is full
            if self.is_match_full():
                # All slots filled, notify participants
                logging.info(f"Match is now full after {interaction.user.name} joined, notifying participants")
                await self.notify_match_ready(interaction)
                
            logging.info(f"User {interaction.user.id} successfully joined wager match in team {team_id}, slot {slot_id}")
        
        except Exception as e:
            logging.error(f"Error in handle_join: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "There was an error joining the match. Please try again or contact an admin.",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                try:
                    await interaction.followup.send(
                        "There was an error joining the match. Please try again or contact an admin.",
                        ephemeral=True
                    )
                except Exception as followup_error:
                    logging.error(f"Failed to send followup error message: {followup_error}")
            except discord.errors.NotFound:
                logging.error(f"Interaction not found when sending error message")
            except Exception as resp_error:
                logging.error(f"Unexpected error when sending error message: {resp_error}")
    
    def is_match_full(self):
        """Check if all slots are filled"""
        for team_id, slots in self.slots.items():
            for slot_id, user in slots.items():
                if user is None:
                    return False
        return True
    
    async def notify_match_ready(self, interaction):
        """Notify all participants that the match is ready"""
        try:
            channel = interaction.channel
            
            if not channel:
                logging.error("Channel not found in interaction when trying to notify match ready")
                return
            
            # Create embed for match notification
            embed = discord.Embed(
                title="🎮 Wager Match Ready!",
                description=f"A {self.match_type} wager match for {self.amount} million has been filled!",
                color=discord.Color.green()
            )
            
            # Add match details
            embed.add_field(name="Match Type", value=self.match_type, inline=True)
            embed.add_field(name="Region", value=self.region, inline=True)
            embed.add_field(name="Abilities", value="Enabled" if self.abilities else "Disabled", inline=True)
            
            if self.match_type in ["2v2", "3v3"] and self.real_gk is not None:
                embed.add_field(name="Real GK", value="Yes" if self.real_gk else "No", inline=True)
            
            # Add creator's Roblox info
            embed.add_field(
                name="Creator's Roblox Username",
                value=self.roblox_username or "Not provided",
                inline=False
            )
            
            if self.roblox_link:
                embed.add_field(
                    name="Creator's Roblox Link",
                    value=self.roblox_link,
                    inline=False
                )
            
            # Prepare team member mentions safely
            try:
                team1_mentions = [user.mention for user in self.slots[1].values() if user]
                team2_mentions = [user.mention for user in self.slots[2].values() if user]
                
                team1_members = ", ".join(team1_mentions) if team1_mentions else "None"
                team2_members = ", ".join(team2_mentions) if team2_mentions else "None"
            except Exception as e:
                logging.error(f"Error preparing team mentions: {e}", exc_info=True)
                team1_members = "Error loading team members"
                team2_members = "Error loading team members"
            
            embed.add_field(name="Team 1", value=team1_members, inline=False)
            embed.add_field(name="Team 2", value=team2_members, inline=False)
            
            # Add instructions
            embed.add_field(
                name="Next Steps",
                value="All participants should add the match creator in Roblox and join their private server.",
                inline=False
            )
            
            # Add instructions for reporting results
            embed.add_field(
                name="Reporting Results",
                value="After the match is completed, the creator should use the `!mr` command to report the results.",
                inline=False
            )
            
            # Send the notification
            try:
                await channel.send(embed=embed)
                logging.info(f"Match ready notification sent to channel {channel.id}")
            except Exception as e:
                logging.error(f"Failed to send match ready notification: {e}", exc_info=True)
            
            # DM all participants
            for team_id, slots in self.slots.items():
                for slot_id, user in slots.items():
                    if user and user.id != self.creator.id:  # Don't DM the creator
                        try:
                            await user.send(
                                f"Your wager match is ready! Please add the creator ({self.creator.display_name}) " +
                                f"on Roblox: {self.roblox_username or 'Username not provided'}" +
                                (f"\nRoblox Link: {self.roblox_link}" if self.roblox_link else "")
                            )
                            logging.info(f"Sent match ready DM to user {user.id}")
                        except Exception as e:
                            logging.error(f"Failed to DM participant {user.id}: {e}")
                            # Continue with others
                            continue
            
            # DM the creator
            try:
                players = []
                for team_id, slots in self.slots.items():
                    for slot_id, user in slots.items():
                        if user and user.id != self.creator.id:
                            players.append(user.display_name)
                
                if players:
                    player_list = ", ".join(players)
                    await self.creator.send(
                        f"Your wager match is now full! The following players will be joining: {player_list}. " +
                        "They have been notified to add you on Roblox."
                    )
                    logging.info(f"Sent match ready DM to creator {self.creator.id}")
                else:
                    logging.warning(f"No players found in match for creator {self.creator.id}")
            except Exception as e:
                logging.error(f"Failed to DM creator {self.creator.id}: {e}")
                # Not a critical error, continue
        
        except Exception as e:
            logging.error(f"Error in notify_match_ready: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "There was an error notifying participants about the match. Please contact them manually.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        "There was an error notifying participants about the match. Please contact them manually.",
                        ephemeral=True
                    )
                except:
                    pass
                    
@bot.command(name="mr")
async def mr_command(ctx):
    """Submit match results for wager matches"""
    # Check if this message has already been processed to avoid duplicates
    message_id = str(ctx.message.id)
    if hasattr(bot, "_processed_commands") and isinstance(bot._processed_commands, dict) and message_id in bot._processed_commands:
        logging.warning(f"Duplicate mr command detected for message {message_id}, ignoring.")
        return
    
    # Initialize _processed_commands if it doesn't exist
    if not hasattr(bot, "_processed_commands"):
        bot._processed_commands = {}
    # Mark this message as processed to avoid duplicates - IMPORTANT: do this EARLY
    bot._processed_commands[message_id] = time.time()
    
    try:
        # Send initial DM to the user asking for match results
        # Use non-persistent view for interactive user session
        team_select_view = TeamSelectView(ctx.author, persistent=False)
        
        # Add logging for debugging
        logging.info(f"Creating TeamSelectView for user {ctx.author.name} with ID {ctx.author.id}")
        
        await ctx.author.send(
            content="Please select which team won the wager match:",
            view=team_select_view
        )
        
        # Let the user know to check DMs
        await ctx.send(f"{ctx.author.mention}, I've sent you a DM to submit your match results! 💖")
        
        # Wait for screenshot to be uploaded
        try:
            def check(message):
                # Check if the message is from the same user and has attachments
                return message.author.id == ctx.author.id and message.attachments and len(message.attachments) > 0 and isinstance(message.channel, discord.DMChannel)
            
            # Wait for a message with attachments
            screenshot_message = await safe_wait_for(bot.wait_for('message', check=check), timeout=300)
            
            # Get the screenshot URL
            screenshot_url = screenshot_message.attachments[0].url
            
            # Check if the team was selected
            if team_select_view.winner is None:
                await ctx.author.send("You haven't selected a winning team yet. Please use the buttons above to select which team won.")
                return
            
            # Confirm the submission
            confirmation_embed = discord.Embed(
                title="🏆 Match Results Submitted",
                description="Your match results have been submitted for verification.",
                color=discord.Color.gold()
            )
            
            confirmation_embed.add_field(name="Winner", value=f"Team {team_select_view.winner}", inline=True)
            confirmation_embed.set_image(url=screenshot_url)
            
            await ctx.author.send(embed=confirmation_embed)
            
            # Submit to the mod channel for verification
            mod_channel_id = 1351221346192982046  # The channel for mod verification
            mod_channel = bot.get_channel(mod_channel_id)
            
            if not mod_channel:
                await ctx.author.send("Error: Couldn't find the moderation channel. Please contact an admin.")
                return
            
            # Create match info dictionary
            match_info = {
                "submitter_id": str(ctx.author.id),
                "submitter_name": ctx.author.display_name,
                "winner": team_select_view.winner,
                "screenshot_url": screenshot_url,
                "timestamp": datetime.datetime.now().isoformat(),
                "match_type": "Unknown",  # Since we don't have this info
                "amount": 0,  # Since we don't have this info
                "teams": {
                    "team1": [str(ctx.author.id)],  # Placeholder, we don't know who's in which team
                    "team2": []
                }
            }
            
            # Create the verification embed
            verification_embed = discord.Embed(
                title="🔍 Match Results Verification",
                description=f"**{ctx.author.display_name}** has submitted match results for verification.",
                color=discord.Color.blue()
            )
            
            verification_embed.add_field(name="Submitter", value=f"{ctx.author.mention} ({ctx.author.id})", inline=True)
            verification_embed.add_field(name="Claimed Winner", value=f"Team {team_select_view.winner}", inline=True)
            verification_embed.add_field(name="Timestamp", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
            verification_embed.set_image(url=screenshot_url)
            
            # Create the verification view
            verify_view = ModVerifyView(match_info)
            
            # Send to mod channel
            await mod_channel.send(embed=verification_embed, view=verify_view)
            
        except asyncio.TimeoutError:
            await ctx.author.send("⏱️ You didn't upload a screenshot in time. Please try the `!mr` command again.")
        
    except discord.errors.Forbidden:
        await ctx.send(f"{ctx.author.mention}, I couldn't send you a DM. Please make sure your DMs are open and try again!")
    except Exception as e:
        logging.error(f"Error in mr command: {e}")
        logging.error(traceback.format_exc())
        try:
            await ctx.send(random.choice(MOMMY_ERROR_VARIANTS))
        except:
            pass

@bot.command(name="modhelp")
async def modhelp_command(ctx):
    """Show the interactive moderation tooltip wizard"""
    # Check if this message has already been processed to avoid duplicates
    message_id = str(ctx.message.id)
    if hasattr(bot, "_processed_commands") and isinstance(bot._processed_commands, dict) and message_id in bot._processed_commands:
        logging.warning(f"Duplicate modhelp command detected for message {message_id}, ignoring.")
        return
    
    # Initialize _processed_commands if it doesn't exist
    if not hasattr(bot, "_processed_commands"):
        bot._processed_commands = {}
    # Mark this message as processed to avoid duplicates - IMPORTANT: do this EARLY
    bot._processed_commands[message_id] = time.time()
    
    try:
        # Check if user has appropriate permissions
        is_moderator = False
        if ctx.guild:
            # Check for admin or moderator permissions
            if ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.moderate_members:
                is_moderator = True
            
            # Check for specific moderator roles if needed
            moderator_role_ids = [
                1350499731612110929,  # Evaluator role
                1350475555483512903   # Trainer role
            ]
            for role in ctx.author.roles:
                if role.id in moderator_role_ids:
                    is_moderator = True
                    break
        
        # Owner can always access moderation help
        if ctx.author.id == 654338875736588288:  # Owner ID
            is_moderator = True
        
        # Only allow moderators to access this command
        if not is_moderator:
            await ctx.send(random.choice(MOMMY_PERMISSION_DENIED))
            return
        
        # Check if moderation tooltips are available
        if not MODERATION_TOOLTIPS_AVAILABLE:
            await ctx.send("💔 Oh my, Mommy's moderation guide isn't quite ready yet, sweetie! Try again later! 💖")
            return
            
        # Send the moderation tooltip wizard
        await moderation_tooltips.send_moderation_tooltip_wizard(ctx)
        logging.info(f"Sent moderation tooltip wizard to {ctx.author.name}")
        
    except Exception as e:
        # Handle any exceptions
        error_message = random.choice(MOMMY_ERROR_VARIANTS)
        await ctx.send(f"{error_message}\n\n```{str(e)}```")
        logging.error(f"Error in modhelp command: {e}", exc_info=True)

@bot.event
async def on_message(message):
    """Handle incoming messages and process commands - FIXED VERSION"""
    # IMPORTANT DEBUG - log every message to help diagnose command issues
    logging.info(f"[PID:{os.getpid()}][MID:{message.id}][CMD:{'!' in message.content}] Processing message from {message.author.name}: {message.content}")
    global last_heartbeat
    last_heartbeat = time.time()
    try:
        if message.author.bot:
            return
            
        pid = os.getpid()
        is_command = message.content.startswith(COMMAND_PREFIX)
        logging.info(f"[PID:{pid}][MID:{message.id}][CMD:{is_command}] Processing message from {message.author} in {message.channel}: {message.content}")
        
        # NUCLEAR LEVEL PROFANITY FILTER - HIGHEST PRIORITY - NO EXCEPTIONS
        if message.guild and not isinstance(message.channel, discord.DMChannel):
            # Owner is exempt from filter - CRITICAL - Owner ID with direct decimal comparison
            # This must happen before any profanity checks
            is_exempt = False
            if message.author.id == 654338875736588288:  # Owner ID direct comparison
                is_exempt = True
                logging.info(f"OWNER MESSAGE: {message.author.name} ({message.author.id}) is EXEMPT from filter")
            
            # Admin/mod exemption
            if not is_exempt and (message.author.guild_permissions.administrator or message.author.guild_permissions.manage_messages):
                is_exempt = True
                logging.info(f"ADMIN/MOD EXEMPT: {message.author.name} has admin permissions - exempt from filter")
            
            # Owner role exemption
            if not is_exempt:
                OWNER_ROLE_ID = 1350175902738419734
                for role in message.author.roles:
                    if role.id == OWNER_ROLE_ID:
                        is_exempt = True
                        logging.info(f"OWNER ROLE EXEMPT: {message.author.name} has owner role - exempt from filter")
                        break
            
            # If not exempt, check for profanity with maximum scrutiny
            if not is_exempt:
                content = message.content.lower()
                
                # ABSOLUTELY CRITICAL - Check for bad words with no exceptions
                bad_words = [
                    # Must block these with highest priority
                    "fuck", "fck", "f*ck", "fuk", "fuking", "fukking", "fking", "fkn", 
                    "shit", "shi", "sh*t", "sh1t", "sh!t", "dammmn", "wtf", "stfu", "gtfo", "lmfao", "fml", "lmao",
                    "bitch", "btch", "b*tch", "asshole", "dumbass",
                    "sybau", "sybau2", "sy bau", "s y b a u", "omfg", "dafuq", "mtf",
                    # Racial slurs (CRITICAL - must block)
                    "nigger", "nigga", "niga", "nga", "n1gga", "n1gg3r", "n1ga", "negro", "chink", "spic", "kike"
                ]
                
                # The profanity filter is completely redesigned to ONLY use direct exact matches
                # No more false positives by stripped all the complex checks
                
                # These bad words will be checked as WHOLE WORDS ONLY (with word boundaries)
                exact_check_words = [
                    "fuck", "shit", "shi", "bitch", "ass", "asshole", "damn", "hell", 
                    "crap", "bullshit", "dipshit", "nga", "nigga", "niga", "chink", "spic", "kike"
                ]
                
                # We ONLY check for exact matches with word boundaries
                words_in_msg = content.lower().split()
                for word in words_in_msg:
                    # Clean the word by removing punctuation
                    clean_word = word.strip('.,!?:;()[]{}\'"`~-_')
                    
                    if clean_word in exact_check_words:
                        # Only exact match, nothing else
                        logging.warning(f"DIRECT PROFANITY BLOCK: '{clean_word}' from {message.author.name}: {message.content}")
                        try:
                            await message.delete()
                            warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                            await message.channel.send(f"{message.author.mention} {warning}", delete_after=60)
                            
                            # Notify owner
                            try:
                                owner = await bot.fetch_user(654338875736588288)
                                if owner:
                                    owner_msg = f"🔴 **PROFANITY ALERT**\n\nUser: {message.author} ({message.author.id})\nChannel: {message.channel.name}\nBad Word: '{clean_word}'\nMessage: {message.content}"
                                    await owner.send(owner_msg)
                            except Exception as e:
                                logging.error(f"Failed to notify owner: {e}")
                            
                            return
                        except Exception as e:
                            logging.error(f"Failed to handle profanity: {e}")
                            
                # CHECK FOR SPECIFIC BANNED TERMS EXACTLY AS WRITTEN
                dangerous_terms = ["sybau", "kys", "kill yourself", "sy bau", "wtf", "stfu", "gtfo", "nga", "shi", "niga", "nigga", "chink", "spic", "kike"]
                for term in dangerous_terms:
                    if term in content.lower():
                        logging.warning(f"DANGEROUS TERM BLOCK: '{term}' from {message.author.name}: {message.content}")
                        try:
                            await message.delete()
                            warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                            await message.channel.send(f"{message.author.mention} {warning}", delete_after=60)
                            
                            # Notify owner
                            try:
                                owner = await bot.fetch_user(654338875736588288)
                                if owner:
                                    owner_msg = f"🔴 **DANGEROUS TERM ALERT**\n\nUser: {message.author} ({message.author.id})\nChannel: {message.channel.name}\nTerm: '{term}'\nMessage: {message.content}"
                                    await owner.send(owner_msg)
                            except Exception as e:
                                logging.error(f"Failed to notify owner: {e}")
                            
                            return
                        except Exception as e:
                            logging.error(f"Failed to handle dangerous term: {e}")
                            
        # Process team creation messages via team_tickets module if it's loaded
        try:
            import team_tickets
            if hasattr(team_tickets, 'process_team_creation_message'):
                # Check if this is a team creation message and process it first
                if await team_tickets.process_team_creation_message(message, bot):
                    logging.info(f"Processed team creation message from {message.author.name}")
                    return
        except ImportError:
            pass  # Module not loaded, continue normal processing
        
        # DIRECT PROFANITY CHECK - EXTREME PRIORITY - Must happen immediately
        # Skip all other processing until this is checked
        if not isinstance(message.channel, discord.DMChannel) and message.content:
            # Log every message for debugging
            logging.warning(f"[PRIORITY CHECK] Checking message from {message.author.name}: '{message.content}'")
            content = message.content.lower()
            
            # ULTRA PRIORITY CHECK - Top of the line check for specific user-requested banned words
            ultra_banned_words = ["sybau", "sybau2", "sy bau", "s y b a u", "nga", "shi", "nigga", "niga", "chink", "spic", "kike"]
            
            # SPECIAL CARE FOR WTF/STFU - only if it's exactly those letters as a word
            special_acronyms = ["wtf", "stfu", "gtfo", "lmfao"]
            
            # First check exact ultra banned words (no word boundaries)
            for ultra_word in ultra_banned_words:
                if ultra_word in content:
                    logging.critical(f"ULTRA PRIORITY BANNED WORD: '{ultra_word}' from {message.author.name}")
                    try:
                        await message.delete()
                        warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                        await message.channel.send(f"{message.author.mention} {warning}")
                        
                        # Try to notify owner separately
                        try:
                            owner = await bot.fetch_user(654338875736588288)  # Hard-coded owner ID
                            if owner:
                                owner_msg = f"🛑 **Ultra Priority Banned Word Alert**\n\nUser: {message.author} ({message.author.id})\nChannel: {message.channel.name}\nWord: '{ultra_word}'\nContent: {message.content}"
                                await owner.send(owner_msg)
                        except Exception as e:
                            logging.error(f"Failed to notify owner about ultra banned word: {e}")
                        
                        return  # Stop all processing
                    except Exception as e:
                        logging.error(f"Failed to handle ultra banned word: {e}")
            
            # Then check special acronyms with word boundaries
            words_in_msg = content.split()
            for word in words_in_msg:
                # Clean the word
                clean_word = word.strip('.,!?:;()[]{}\'"`~-_').lower()
                if clean_word in special_acronyms:
                    logging.critical(f"SPECIAL ACRONYM BANNED WORD: '{clean_word}' from {message.author.name}")
                    try:
                        await message.delete()
                        warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                        await message.channel.send(f"{message.author.mention} {warning}")
                        
                        # Try to notify owner separately
                        try:
                            owner = await bot.fetch_user(654338875736588288)  # Hard-coded owner ID
                            if owner:
                                owner_msg = f"🛑 **Banned Acronym Alert**\n\nUser: {message.author} ({message.author.id})\nChannel: {message.channel.name}\nWord: '{clean_word}'\nContent: {message.content}"
                                await owner.send(owner_msg)
                        except Exception as e:
                            logging.error(f"Failed to notify owner about banned acronym: {e}")
                        
                        return  # Stop all processing
                    except Exception as e:
                        logging.error(f"Failed to handle banned acronym: {e}")
            
            # CRITICAL: Check for announcements and exempt them completely
            if message.content.startswith("📢") or message.content.startswith("⚠️"):
                # Check if this looks like a community announcement
                announcement_checks = [
                    "community safety" in content,
                    "safety notice" in content,
                    "official notice" in content,
                    "toxic behavior" in content,
                    "disciplinary action" in content,
                    "violate our rules" in content,
                    "integrity of our space" in content
                ]
                
                if any(announcement_checks):
                    logging.info(f"ANNOUNCEMENT DETECTED - EXEMPT FROM FILTER: {message.author.name}")
                    return  # Skip ALL profanity checking for announcements
            
            # EXEMPT WORDS IN CONTEXT: Check for specific contexts like "harassment"
            exempt_contexts = {
                "ass": ["harassment", "harass", "class", "classes", "passing", "passport", "assignment", "mass", "passive", "assem", "assistant", "assoc", "assure", "ambassador", "assembl", "assurance", "assumption"]
            }
            
            # Check each potential bad word
            for bad_word, contexts in exempt_contexts.items():
                if bad_word in content:
                    # Check if any exemption context applies
                    is_exempt = any(context in content for context in contexts)
                    
                    if is_exempt:
                        logging.info(f"Exempted '{bad_word}' due to context: {' '.join(context for context in contexts if context in content)}")
                        # Don't return, keep checking other bad words
                    else:
                        # Only if it's a standalone bad word with no exemption context
                        words = content.split()
                        if bad_word in words:
                            logging.warning(f"DIRECT PROFANITY BLOCK: '{bad_word}' from {message.author.name}: {message.content}")
                            try:
                                await message.delete()
                                warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                                await message.channel.send(f"{message.author.mention} {warning}")
                                return  # Stop further processing
                            except Exception as e:
                                logging.error(f"Failed to handle profanity: {e}")
            
            # DIRECT F-WORD CHECK - Block without regex for reliability - PRIORITY CHECK
            f_word_patterns = [
                'fuck', 'fuk', 'fuking', 'fukin', 'fukk', 'fuc', 'phuck', 'phuk',  # Exact matches
                'f*ck', 'f**k', 'f***', 'f*k', 'f**', 'fu*k', 'fu**',  # Censored versions
                'f u c k', 'f.u.c.k', 'f-u-c-k', 'f_u_c_k', 'f(u)c(k)',  # Spaced/punctuated
                'fu ck', 'f uck', 'f uc k', 'f. u. c. k'  # Partial spacing
            ]
            
            # Check all word boundaries to find standalone f-words
            words = content.split()
            is_f_word = False
            
            # First check standalone words
            for word in words:
                clean_word = word.strip('.,!?:;()[]{}\'"`~-_')  # Strip punctuation
                if clean_word in f_word_patterns:
                    is_f_word = True
                    break
            
            # Then check full content for patterns that might be hidden
            if not is_f_word:
                for pattern in f_word_patterns:
                    if pattern in content:
                        is_f_word = True
                        break
            
            if is_f_word:
                logging.warning(f"URGENT PRIORITY - DIRECT PROFANITY BLOCK: F-word from {message.author.name}: {message.content}")
                
                # Delete message immediately with high priority
                try:
                    await message.delete()
                    
                    # Send warning
                    warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                    warning_msg = await message.channel.send(f"{message.author.mention} {warning}")
                    
                    # Timeout user (2 minutes)
                    try:
                        until = discord.utils.utcnow() + timedelta(minutes=2)
                        await message.author.timeout(until, reason=f"Automatic timeout for profanity: f-word")
                        logging.info(f"Applied 2-minute timeout to {message.author.name} for profanity")
                    except Exception as e:
                        logging.error(f"Failed to timeout user: {e}")
                    
                    # Notify owner (if possible)
                    try:
                        owner = await bot.fetch_user(654338875736588288)  # Hard-coded owner ID
                        if owner:
                            owner_msg = f"🛑 **Profanity Alert**\n\nUser: {message.author} ({message.author.id})\nChannel: {message.channel.name}\nContent: {message.content}"
                            await owner.send(owner_msg)
                    except Exception as e:
                        logging.error(f"Failed to notify owner: {e}")
                        
                    return  # Stop further processing
                except Exception as e:
                    logging.error(f"Failed to handle profanity: {e}")
            
            # Check for additional self-harm related terms and other strong profanity
            # List of direct bad words to catch (removing "ass" since it's checked with contexts above)
            bad_words = [
                # Basic profanity
                "shit", "damn", "crap", "bitch", "bullshit", "dipshit", 
                # Self-harm terms
                "kys", "kill yourself", "killing yourself", "kill urself", "suicide", "hang yourself", "hang urself",
                # Additional variants - removing WTF/STFU which are checked with word boundaries above
                "fck", "fcking", "fking", "fkn"
            ]
            for word in bad_words:
                if word in content:
                    logging.warning(f"DIRECT PROFANITY BLOCK: '{word}' from {message.author.name}: {message.content}")
                    try:
                        await message.delete()
                        warning = "🚫 **Inappropriate Language Detected**\n\nThis server maintains a respectful environment. Please keep conversations appropriate."
                        await message.channel.send(f"{message.author.mention} {warning}")
                        return  # Stop further processing
                    except Exception as e:
                        logging.error(f"Failed to handle profanity: {e}")
        
        # Continue with remaining message processing
        # Skip profanity check for DMs and if the user is an admin/mod or has the owner role
        if message.guild and hasattr(bot, 'profanity_filter') and not isinstance(message.channel, discord.DMChannel):
            is_exempt = False
            # Owner role ID that should be exempt from profanity filter
            OWNER_ROLE_ID = 1350175902738419734

            # Check if user has admin or mod permissions
            if message.author.guild_permissions.administrator or message.author.guild_permissions.manage_messages:
                is_exempt = True
            
            # Check if user has the owner role
            if not is_exempt:
                for role in message.author.roles:
                    if role.id == OWNER_ROLE_ID:
                        is_exempt = True
                        logging.info(f"User {message.author.name} exempt from profanity filter due to owner role")
                        break
                
            # If not exempt, check for banned words
            if not is_exempt:
                is_banned, matched_term = bot.profanity_filter.check_message(message)
                if is_banned:
                    logging.warning(f"[PROFANITY] Detected banned term '{matched_term}' from {message.author.name}")
                    # Handle the profanity (delete message, apply timeout, etc.)
                    await bot.profanity_filter.handle_profanity(message, matched_term)
                    return  # Skip further processing for this message
        
        if is_command:
            logging.debug("=== COMMAND DEBUG INFO ===")
            logging.debug(f"Message ID: {message.id}")
            logging.debug(f"Process ID: {pid}")
            logging.debug(f"Author: {message.author.id} ({message.author.name})")
            logging.debug(f"Command: {message.content}")
            logging.debug(f"Channel: {message.channel.id} ({message.channel.name if hasattr(message.channel, 'name') else 'DM'})")
            logging.debug(f"Server: {message.guild.id if message.guild else 'DM'}")
            logging.debug("==========================")
        await activity_tracker.track_message(str(message.author.id))
        
        # Process commands
        await bot.process_commands(message)
        
        # Log this message to the processed commands tracker
        if hasattr(bot, "_processed_commands"):
            message_id = str(message.id)
            if message_id not in bot._processed_commands:
                bot._processed_commands[message_id] = {
                    "timestamp": time.time(),
                    "pid": pid,
                    "command": message.content if is_command else None
                }
                
        # Check for player evaluation DM responses
        if isinstance(message.channel, discord.DMChannel) and hasattr(bot, "_player_evaluations") and message.author.id in bot._player_evaluations:
            try:
                eval_state = bot._player_evaluations[message.author.id]
                content = message.content.strip()
                
                # Handle skill rating
                if eval_state["step"] == "skill_rating":
                    if not content.isdigit() or int(content) < 1 or int(content) > 5:
                        await message.channel.send("Please enter a valid rating from 1-5, darling~ 💖")
                        return
                        
                    # Store the skill rating
                    skill_rating = int(content)
                    eval_state["skill_rating"] = skill_rating
                    eval_state["step"] = "teamwork_rating"
                    
                    # Send teamwork question
                    teamwork_question = discord.Embed(
                        title="Question 2: Teamwork",
                        description=f"How would you rate {eval_state['target_name']}'s teamwork and communication?",
                        color=discord.Color.purple()
                    )
                    
                    teamwork_question.add_field(
                        name="📊 Rating Scale",
                        value=(
                            "1️⃣ - Poor: Rarely communicates or works with team\n"
                            "2️⃣ - Below Average: Inconsistent teamwork\n"
                            "3️⃣ - Average: Satisfactory teamwork and communication\n"
                            "4️⃣ - Good: Consistently good team player\n"
                            "5️⃣ - Excellent: Outstanding teamwork, leadership, and communication"
                        ),
                        inline=False
                    )
                    
                    teamwork_question.set_footer(text="Please enter a number from 1-5")
                    await message.channel.send(embed=teamwork_question)
                    return
                
                # Handle teamwork rating
                elif eval_state["step"] == "teamwork_rating":
                    if not content.isdigit() or int(content) < 1 or int(content) > 5:
                        await message.channel.send("Please enter a valid rating from 1-5, darling~ 💖")
                        return
                        
                    # Store the teamwork rating
                    teamwork_rating = int(content)
                    eval_state["teamwork_rating"] = teamwork_rating
                    eval_state["step"] = "consistency_rating"
                    
                    # Send consistency question
                    consistency_question = discord.Embed(
                        title="Question 3: Consistency",
                        description=f"How consistent is {eval_state['target_name']}'s performance?",
                        color=discord.Color.purple()
                    )
                    
                    consistency_question.add_field(
                        name="📊 Rating Scale",
                        value=(
                            "1️⃣ - Very Inconsistent: Highly variable performance\n"
                            "2️⃣ - Somewhat Inconsistent: Often varies in performance\n"
                            "3️⃣ - Moderately Consistent: Reliable most of the time\n"
                            "4️⃣ - Consistent: Reliable performance in most matches\n"
                            "5️⃣ - Highly Consistent: Dependable performance in all situations"
                        ),
                        inline=False
                    )
                    
                    consistency_question.set_footer(text="Please enter a number from 1-5")
                    await message.channel.send(embed=consistency_question)
                    return
                
                # Handle consistency rating
                elif eval_state["step"] == "consistency_rating":
                    if not content.isdigit() or int(content) < 1 or int(content) > 5:
                        await message.channel.send("Please enter a valid rating from 1-5, darling~ 💖")
                        return
                        
                    # Store the consistency rating
                    consistency_rating = int(content)
                    eval_state["consistency_rating"] = consistency_rating
                    eval_state["step"] = "comments"
                    
                    # Ask for additional comments
                    comments_question = discord.Embed(
                        title="Final Question: Additional Comments",
                        description=f"Do you have any additional comments about {eval_state['target_name']}?",
                        color=discord.Color.purple()
                    )
                    
                    comments_question.add_field(
                        name="✏️ Instructions",
                        value=(
                            "Please provide any additional feedback, observations, or suggestions for improvement.\n\n"
                            "This is optional - if you don't have any comments, just type 'none'."
                        ),
                        inline=False
                    )
                    
                    await message.channel.send(embed=comments_question)
                    return
                
                # Handle comments
                elif eval_state["step"] == "comments":
                    # Store the comments
                    comments = content
                    eval_state["comments"] = comments if comments.lower() != "none" else ""
                    eval_state["step"] = "completed"
                    
                    # Calculate average rating
                    skill = eval_state.get("skill_rating", 0)
                    teamwork = eval_state.get("teamwork_rating", 0)
                    consistency = eval_state.get("consistency_rating", 0)
                    average_rating = (skill + teamwork + consistency) / 3
                    
                    # Create summary embed
                    summary = discord.Embed(
                        title="✅ Evaluation Complete!",
                        description=f"Thank you for evaluating {eval_state['target_name']}, darling! 💖",
                        color=discord.Color.green()
                    )
                    
                    summary.add_field(
                        name="📊 Summary",
                        value=(
                            f"**Skill Rating:** {skill}/5\n"
                            f"**Teamwork Rating:** {teamwork}/5\n"
                            f"**Consistency Rating:** {consistency}/5\n"
                            f"**Average Rating:** {average_rating:.1f}/5"
                        ),
                        inline=False
                    )
                    
                    if eval_state["comments"]:
                        summary.add_field(
                            name="💬 Your Comments",
                            value=eval_state["comments"],
                            inline=False
                        )
                    
                    summary.set_footer(text="Mommy has shared this evaluation with the server managers~ 💕")
                    await message.channel.send(embed=summary)
                    
                    # Try to send results to the original channel
                    try:
                        guild = bot.get_guild(int(eval_state["guild_id"]))
                        channel = guild.get_channel(int(eval_state["channel_id"]))
                        target_member = guild.get_member(int(eval_state["target_id"]))
                        
                        if channel and target_member:
                            # Create result embed for server
                            result = discord.Embed(
                                title=f"📝 Player Evaluation Results: {target_member.display_name}",
                                description=f"Evaluation by {message.author.mention}",
                                color=discord.Color.blue()
                            )
                            
                            result.add_field(
                                name="📊 Ratings",
                                value=(
                                    f"**Skill:** {skill}/5\n"
                                    f"**Teamwork:** {teamwork}/5\n"
                                    f"**Consistency:** {consistency}/5\n"
                                    f"**Average:** {average_rating:.1f}/5"
                                ),
                                inline=False
                            )
                            
                            if eval_state["comments"]:
                                result.add_field(
                                    name="💬 Additional Comments",
                                    value=eval_state["comments"],
                                    inline=False
                                )
                                
                            if target_member.avatar:
                                result.set_thumbnail(url=target_member.avatar.url)
                                
                            await channel.send(embed=result)
                    except Exception as e:
                        logging.error(f"Error sending evaluation results to channel: {e}")
                        
                    # Remove the evaluation state
                    del bot._player_evaluations[message.author.id]
                    return
            except Exception as e:
                logging.error(f"Error processing player evaluation: {e}")
                logging.error(traceback.format_exc())

        # Processing of commands is already handled earlier (at line ~2803)
        # Do not call bot.process_commands(message) again here to prevent duplicate command execution
        logging.info(f"[COMMAND PROCESSING] Finished processing command from {message.author.name}")
        
        if not isinstance(message.channel, discord.DMChannel):
            exact_command_names = ['checkvalue', 'matchresults', 'anteup', 'headpat', 'spank', 
                                   'rankings', 'activity', 'matchcancel', 'spill', 'shopping', 
                                   'tipjar', 'confess', 'giveaway', 'mommy', 'eval', 
                                   'tryoutsresults', 'sm', 'addvalue']
            content = message.content.strip().lower()
            first_word = content.split()[0] if content else ""
            if ((first_word in exact_command_names and (len(content.split()) == 1 or content.split()[1].startswith("@"))) or
                (content in exact_command_names)):
                common_prefixes = ["i ", "the ", "a ", "this ", "that ", "my ", "our ", "their ", "his ", "her ", "its "]
                preceding_words = message.content.split(first_word)[0].lower()
                if not any(preceding_words.endswith(prefix) for prefix in common_prefixes):
                    await message.channel.send("Sweetie, did you forget to add `!` before the command? 🎀 Mommy needs that to understand what you want! 💖")
                    return
        if isinstance(message.channel, discord.DMChannel):
            if message.author.id in active_server_messages:
                try:
                    msg_state = active_server_messages[message.author.id]
                    content = message.content.strip()
                    if msg_state["step"] == "server_selection":
                        servers = []
                        for i, guild in enumerate(bot.guilds, 1):
                            servers.append((str(i), str(guild.id), guild.name))
                        if not content.isdigit() or int(content) < 1 or int(content) > len(servers):
                            await message.channel.send("❌ Oh darling, please enter a valid server number from the list! 💖")
                            return
                        selected_num = int(content)
                        selected_server_id = servers[selected_num-1][1]
                        selected_server_name = servers[selected_num-1][2]
                        msg_state["server_id"] = selected_server_id
                        msg_state["step"] = "channel_selection"
                        guild = bot.get_guild(int(selected_server_id))
                        text_channels = guild.text_channels
                        embed = discord.Embed(
                            title="💬 Channel Selection 💬",
                            description=f"Now, which channel in **{selected_server_name}** do you want to send your message to?",
                            color=discord.Color.purple()
                        )
                        channels_per_page = 10
                        channel_count = len(text_channels)
                        for i, channel in enumerate(text_channels[:channels_per_page]):
                            embed.add_field(
                                name=f"#{i+1} {channel.name}",
                                value=f"ID: {channel.id}",
                                inline=False
                            )
                        if channel_count > channels_per_page:
                            embed.set_footer(text=f"Showing 1-{channels_per_page} of {channel_count} channels. Type 'more' to see more channels.")
                        else:
                            embed.set_footer(text="Please enter the channel number or ID from the list above")
                        await message.channel.send(embed=embed)
                    elif msg_state["step"] == "channel_selection":
                        guild = bot.get_guild(int(msg_state["server_id"]))
                        text_channels = guild.text_channels
                        if content.lower() == 'more':
                            more_embed = discord.Embed(
                                title="💬 Channel Selection (Continued) 💬",
                                description=f"Additional channels in **{guild.name}**:",
                                color=discord.Color.purple()
                            )
                            already_shown = 10
                            additional = min(10, len(text_channels) - already_shown)
                            for i in range(already_shown, already_shown + additional):
                                channel = text_channels[i]
                                more_embed.add_field(
                                    name=f"#{i+1} {channel.name}",
                                    value=f"ID: {channel.id}",
                                    inline=False
                                )
                            more_embed.set_footer(text="Please enter the channel number or ID from either list")
                            await message.channel.send(embed=more_embed)
                            return
                        selected_channel = None
                        if content.isdigit():
                            channel_num = int(content)
                            if 1 <= channel_num <= len(text_channels):
                                selected_channel = text_channels[channel_num-1]
                        if not selected_channel and content.isdigit():
                            selected_channel = guild.get_channel(int(content))
                        if not selected_channel:
                            await message.channel.send("❌ Oh sweetie, I couldn't find that channel! Please choose a valid channel number or ID. 💖")
                            return
                        msg_state["channel_id"] = str(selected_channel.id)
                        msg_state["step"] = "message_input"
                        await message.channel.send(
                            "✨ **Message Creation** ✨\n\n"
                            f"Perfect, darling! Now compose your beautiful message to send to **#{selected_channel.name}**.\n\n"
                            "Type your message below. If you want to tag everyone, include @everyone in your message and I'll handle it!"
                        )
                    elif msg_state["step"] == "message_input":
                        if not content:
                            await message.channel.send("❌ Oh darling, you can't send an empty message! Please type something gorgeous! 💖")
                            return
                        msg_state["message"] = content
                        msg_state["step"] = "ping_selection"
                        guild = bot.get_guild(int(msg_state["server_id"]))
                        embed = discord.Embed(
                            title="🔔 Ping Options 🔔",
                            description="Would you like to ping anyone with this message, darling?",
                            color=discord.Color.gold()
                        )
                        embed.add_field(
                            name="📋 Options",
                            value=(
                                "1️⃣ **No ping** - Just send the message\n"
                                "2️⃣ **@everyone** - Ping everyone in the channel\n"
                                "3️⃣ **@here** - Ping only online members\n"
                                "4️⃣ **Specific role** - Ping a specific role\n"
                                "5️⃣ **Specific user** - Ping an individual user"
                            ),
                            inline=False
                        )
                        embed.set_footer(text="Please enter the number of your choice (1-5)")
                        await message.channel.send(embed=embed)
                    elif msg_state["step"] == "ping_selection":
                        if not content.isdigit() or int(content) < 1 or int(content) > 5:
                            await message.channel.send("❌ Please enter a valid option (1-5), sweetheart! 💖")
                            return
                        option = int(content)
                        guild = bot.get_guild(int(msg_state["server_id"]))
                        if option == 1:
                            msg_state["ping_target"] = None
                            msg_state["step"] = "confirmation"
                            channel = guild.get_channel(int(msg_state["channel_id"]))
                        elif option == 2:
                            msg_state["ping_target"] = "@everyone"
                            msg_state["step"] = "confirmation"
                            channel = guild.get_channel(int(msg_state["channel_id"]))
                        elif option == 3:
                            msg_state["ping_target"] = "@here"
                            msg_state["step"] = "confirmation"
                            channel = guild.get_channel(int(msg_state["channel_id"]))
                        elif option == 4:
                            msg_state["step"] = "role_selection"
                            embed = discord.Embed(
                                title="👑 Role Selection 👑",
                                description=f"Which role in **{guild.name}** would you like to ping?",
                                color=discord.Color.gold()
                            )
                            roles = [role for role in guild.roles if role.mentionable and not role.is_default()]
                            display_roles = roles[:15]
                            for i, role in enumerate(display_roles, 1):
                                embed.add_field(
                                    name=f"{i}: @{role.name}",
                                    value=f"ID: {role.id}",
                                    inline=True
                                )
                            if len(roles) > 15:
                                embed.set_footer(text=f"Showing 15 of {len(roles)} roles. Enter a role number, name, or ID.")
                            else:
                                embed.set_footer(text="Enter the role number, name, or ID")
                            await message.channel.send(embed=embed)
                            return
                        elif option == 5:
                            msg_state["step"] = "user_selection"
                            embed = discord.Embed(
                                title="👤 User Selection 👤",
                                description=f"Which user in **{guild.name}** would you like to ping?",
                                color=discord.Color.gold()
                            )
                            embed.add_field(
                                name="ℹ️ Instructions",
                                value="Please enter the user's ID, username, or nickname.\n\nYou can find a user's ID by enabling Developer Mode in Discord settings, then right-clicking on their name and selecting 'Copy ID'.",
                                inline=False
                            )
                            embed.set_footer(text="Enter a user ID, username, or nickname")
                            await message.channel.send(embed=embed)
                            return
                        guild = bot.get_guild(int(msg_state["server_id"]))
                        channel = guild.get_channel(int(msg_state["channel_id"]))
                        embed = discord.Embed(
                            title="📝 Message Preview 📝",
                            description="Here's a preview of your message, sweetheart!",
                            color=discord.Color.gold()
                        )
                        embed.add_field(
                            name="📍 Destination",
                            value=f"Server: **{guild.name}**\nChannel: **#{channel.name}**",
                            inline=False
                        )
                        if "ping_target" in msg_state and msg_state["ping_target"]:
                            ping_display = msg_state["ping_target"]
                            if ping_display.startswith("<@&"):
                                role_id = ping_display.replace("<@&", "").replace(">", "")
                                role = discord.utils.get(guild.roles, id=int(role_id))
                                if role:
                                    ping_display = f"@{role.name}"
                            elif ping_display.startswith("<@"):
                                user_id = ping_display.replace("<@", "").replace(">", "")
                                member_obj = guild.get_member(int(user_id))
                                if member_obj:
                                    ping_display = f"@{member_obj.display_name}"
                            embed.add_field(
                                name="🔔 Ping",
                                value=f"This message will ping: **{ping_display}**",
                                inline=False
                            )
                        preview = msg_state["message"]
                        if len(preview) > 1000:
                            preview = preview[:997] + "..."
                        embed.add_field(
                            name="💌 Message",
                            value=preview,
                            inline=False
                        )
                        embed.set_footer(text="Type 'send' to send this message, 'edit' to make changes, or 'cancel' to abort")
                        await message.channel.send(embed=embed)
                    elif msg_state["step"] == "role_selection":
                        guild = bot.get_guild(int(msg_state["server_id"]))
                        selected_role = None
                        roles = [role for role in guild.roles if role.mentionable and not role.is_default()]
                        if content.isdigit() and 1 <= int(content) <= len(roles):
                            selected_role = roles[int(content)-1]
                        else:
                            for role in roles:
                                if role.name.lower() == content.lower() or str(role.id) == content:
                                    selected_role = role
                                    break
                        if not selected_role:
                            await message.channel.send("❌ I couldn't find that role, sweetie! Please try again with a valid role number, name, or ID. 💖")
                            return
                        msg_state["ping_target"] = f"<@&{selected_role.id}>"
                        msg_state["step"] = "confirmation"
                        channel = guild.get_channel(int(msg_state["channel_id"]))
                        await message.channel.send(f"✅ I'll ping the **@{selected_role.name}** role with your message, darling!")
                    elif msg_state["step"] == "user_selection":
                        guild = bot.get_guild(int(msg_state["server_id"]))
                        selected_user = None
                        if content.isdigit():
                            selected_user = guild.get_member(int(content))
                        if not selected_user:
                            for m in guild.members:
                                if (m.name.lower() == content.lower() or 
                                    (m.nick and m.nick.lower() == content.lower())):
                                    selected_user = m
                                    break
                        if not selected_user:
                            await message.channel.send("❌ I couldn't find that user, sweetie! Please try again with a valid user ID, username, or nickname. 💖")
                            return
                        msg_state["ping_target"] = f"<@{selected_user.id}>"
                        msg_state["step"] = "confirmation"
                        channel = guild.get_channel(int(msg_state["channel_id"]))
                        await message.channel.send(f"✅ I'll ping **{selected_user.display_name}** with your message, darling!")
                    elif msg_state["step"] == "confirmation":
                        if content.lower() == "send":
                            guild = bot.get_guild(int(msg_state["server_id"]))
                            if not guild:
                                await message.channel.send("❌ Oh no, sweetie! Mommy can't find that server anymore! Maybe Mommy got disconnected? 💔")
                                del active_server_messages[message.author.id]
                                return
                            channel = guild.get_channel(int(msg_state["channel_id"]))
                            if not channel:
                                await message.channel.send("❌ Oh darling, Mommy can't find that channel anymore! It might have been deleted or Mommy doesn't have access to it! 🚫")
                                del active_server_messages[message.author.id]
                                return
                            bot_member = guild.get_member(bot.user.id)
                            if not channel.permissions_for(bot_member).send_messages:
                                await message.channel.send("❌ Oh honey! Mommy doesn't have permission to send messages in that channel! Please check Mommy's permissions! 🔒")
                                del active_server_messages[message.author.id]
                                return
                            try:
                                if msg_state["ping_target"]:
                                    if msg_state["ping_target"] in ["@everyone", "@here"]:
                                        if not channel.permissions_for(bot_member).mention_everyone:
                                            await message.channel.send("❌ Oh darling! Mommy doesn't have permission to mention everyone in that channel! 🔔")
                                            del active_server_messages[message.author.id]
                                            return
                                        allowed_mentions = discord.AllowedMentions(everyone=True)
                                        complete_message = f"{msg_state['ping_target']} {msg_state['message']}"
                                        if len(complete_message) > 2000:
                                            await message.channel.send("❌ Oopsie! Your message is too long (over 2000 characters). Discord has a message length limit. Please edit your message to make it shorter! 💫")
                                            msg_state["step"] = "message_input"
                                            return
                                        await channel.send(complete_message, allowed_mentions=allowed_mentions)
                                    else:
                                        complete_message = f"{msg_state['ping_target']} {msg_state['message']}"
                                        if len(complete_message) > 2000:
                                            await message.channel.send("❌ Oopsie! Your message is too long (over 2000 characters). Discord has a message length limit. Please edit your message to make it shorter! 💫")
                                            msg_state["step"] = "message_input"
                                            return
                                        allowed_mentions = discord.AllowedMentions(users=True, roles=True)
                                        await channel.send(complete_message, allowed_mentions=allowed_mentions)
                                else:
                                    if len(msg_state["message"]) > 2000:
                                        await message.channel.send("❌ Oopsie! Your message is too long (over 2000 characters). Discord has a message length limit. Please edit your message to make it shorter! 💫")
                                        msg_state["step"] = "message_input"
                                        return
                                    allowed_mentions = discord.AllowedMentions(users=False, roles=False, everyone=False)
                                    await channel.send(msg_state["message"], allowed_mentions=allowed_mentions)
                                ping_info = f"with {msg_state['ping_target']} mention" if msg_state["ping_target"] else "without any pings"
                                await message.channel.send(
                                    f"✅ **Message Sent Successfully!** ✅\n\n"
                                    f"Your message has been delivered to **#{channel.name}** in **{guild.name}** {ping_info}.\n\n"
                                    "Anything else you need help with, darling? 💖"
                                )
                            except discord.Forbidden:
                                await message.channel.send("❌ Oh no, sweetie! Mommy doesn't have permission to send messages in that channel! 🔒")
                            except discord.HTTPException as e:
                                await message.channel.send(f"❌ Oopsie! Something went wrong when sending the message: {str(e)} 💫")
                                logging.error(f"HTTP error when sending server message: {e}", exc_info=True)
                            except Exception as e:
                                await message.channel.send("❌ Oh dear, something unexpected happened! Mommy apologizes for the trouble! 🌈")
                                logging.error(f"Unexpected error when sending server message: {e}", exc_info=True)
                            finally:
                                if message.author.id in active_server_messages:
                                    del active_server_messages[message.author.id]
                        elif content.lower() == "edit":
                            msg_state["step"] = "message_input"
                            await message.channel.send("💫 Let's revise that message, darling! Please type your new message now:")
                        elif content.lower() == "cancel":
                            await message.channel.send("🌸 Message canceled, my precious! Your secret's safe with Mommy! 💖")
                            del active_server_messages[message.author.id]
                        else:
                            await message.channel.send("❓ Please type 'send', 'edit', or 'cancel', sweetie!")
                    return
                except Exception as e:
                    logging.error(f"Error processing server message: {e}", exc_info=True)
                    await message.channel.send(random.choice(MOMMY_ERROR_VARIANTS))
                    if message.author.id in active_server_messages:
                        del active_server_messages[message.author.id]
            elif message.author.id in active_matches:
                try:
                    match_state = active_matches[message.author.id]
                    await process_match_creation_step(match_state, message)
                except Exception as e:
                    logging.error(f"Error processing match creation step: {e}", exc_info=True)
                    await message.channel.send(random.choice(MOMMY_ERROR_VARIANTS))
            elif message.author.id in active_tryouts:
                try:
                    player = active_tryouts[message.author.id]["member"]
                    def check(m):
                        return m.author.id == message.author.id and isinstance(m.channel, discord.DMChannel)
                    if "step" not in active_tryouts[message.author.id]:
                        active_tryouts[message.author.id]["step"] = "position"
                        position = message.content
                        if position not in ["1", "2", "3", "4"]:
                            await message.channel.send("❌ Please select a valid position (1-4):")
                            await message.channel.send(
                                "> Type `1` for GK (Goalkeeper)\n"
                                "> Type `2` for CM (Central Midfielder)\n"
                                "> Type `3` for LW/RW (Winger)\n"
                                "> Type `4` for CF (Center Forward)"
                            )
                            return
                        is_goalkeeper = position == "1"
                        position_name = {
                            "1": "GK (Goalkeeper)",
                            "2": "CM (Central Midfielder)",
                            "3": "LW/RW (Winger)",
                            "4": "CF (Center Forward)"
                        }.get(position, "Unknown")
                        logging.info(f"Received position response: {position}, position_name: {position_name}, is_goalkeeper: {is_goalkeeper}")
                        active_tryouts[message.author.id]["is_goalkeeper"] = is_goalkeeper
                        active_tryouts[message.author.id]["position"] = position
                        active_tryouts[message.author.id]["position_name"] = position_name
                        active_tryouts[message.author.id]["ratings"] = {}
                        active_tryouts[message.author.id]["step"] = "skills"
                        active_tryouts[message.author.id]["current_skill"] = 0
                        await asyncio.sleep(1)
                        await message.channel.send(
                            "**🎯 Player Skills Evaluation**\n\n"
                            "Let's rate their skills on a scale from 0 to 10!\n"
                            "For each skill, please enter a number between 0 and 10."
                        )
                        skills = [
                            ('shooting', '⚽ Rate their shooting ability (0-10):'),
                            ('dribbling', '👟 Rate their dribbling ability (0-10):'),
                            ('passing', '🎯 Rate their passing ability (0-10):'),
                            ('defense', '🛡️ Rate their defensive ability (0-10):'),
                            ('goalkeeping', '🧤 Rate their goalkeeping ability (0-10) or type "skip":')
                        ]
                        skill_name, prompt = skills[0]
                        await message.channel.send(f"**{prompt}**")
                        return
                    if active_tryouts[message.author.id]["step"] == "skills":
                        skills = [
                            ('shooting', '⚽ Rate their shooting ability (0-10):'),
                            ('dribbling', '👟 Rate their dribbling ability (0-10):'),
                            ('passing', '🎯 Rate their passing ability (0-10):'),
                            ('defense', '🛡️ Rate their defensive ability (0-10):'),
                            ('goalkeeping', '🧤 Rate their goalkeeping ability (0-10) or type "skip":')
                        ]
                        current_skill = active_tryouts[message.author.id].get("current_skill", 0)
                        if current_skill >= len(skills):
                            logging.warning(f"Attempted to process skill index {current_skill} but only {len(skills)} skills exist")
                            active_tryouts[message.author.id]["step"] = "finalizing"
                        else:
                            skill_name, _ = skills[current_skill]
                            if skill_name == "goalkeeping" and message.content.lower() == "skip":
                                active_tryouts[message.author.id]["ratings"][skill_name] = None
                                logging.info(f"Goalkeeping rating skipped for {player}")
                            else:
                                try:
                                    rating = int(message.content)
                                    if 0 <= rating <= 10:
                                        active_tryouts[message.author.id]["ratings"][skill_name] = rating
                                        logging.info(f"Received valid {skill_name} rating: {rating} for {player}")
                                    else:
                                        await message.channel.send("❌ Please enter a number between 0 and 10!")
                                        return
                                except ValueError:
                                    await message.channel.send("❌ Please enter a valid number!")
                                    return
                            active_tryouts[message.author.id]["current_skill"] += 1
                            next_skill = active_tryouts[message.author.id]["current_skill"]
                            is_goalkeeper = active_tryouts[message.author.id]["is_goalkeeper"]
                            position_name = active_tryouts[message.author.id]["position_name"]
                            ratings = active_tryouts[message.author.id]["ratings"]
                            evaluation = {
                                "ratings": ratings,
                                "feedback": "Player evaluation completed.",
                                "is_goalkeeper": is_goalkeeper,
                                "position_name": position_name
                            }
                            if next_skill < len(skills):
                                skill_name, prompt = skills[next_skill]
                                await message.channel.send(f"**{prompt}**")
                                return
                            else:
                                active_tryouts[message.author.id]["step"] = "finalizing"
                            from server_config import get_channel_id
                            player = active_tryouts[message.author.id]["member"]
                            server_id = active_tryouts[message.author.id]["server_id"]
                            guild = active_tryouts[message.author.id]["guild"]
                            player_eval = PlayerEvaluation(
                                ratings=evaluation["ratings"],
                                feedback=evaluation["feedback"],
                                is_goalkeeper=evaluation["is_goalkeeper"],
                                position_name=evaluation["position_name"]
                            )
                            value = player_eval.calculate_value()
                            tryouts_channel_id = get_channel_id("tryout_results", server_id)
                            tryouts_channel = None
                            player_values_channel = None
                            if tryouts_channel_id and tryouts_channel_id.isdigit():
                                tryouts_channel = guild.get_channel(int(tryouts_channel_id))
                            player_values_channel_id = get_channel_id("values", server_id)
                            if player_values_channel_id and player_values_channel_id.isdigit():
                                player_values_channel = guild.get_channel(int(player_values_channel_id))
                            results_message = (
                                f"# 📊 Player Evaluation Results\n\n"
                                f"## {player.mention} as {evaluation['position_name']}\n\n"
                                f"**Rating Details:**\n"
                                f"⚽ Shooting: {evaluation['ratings'].get('shooting', 'N/A')}/10\n"
                                f"👟 Dribbling: {evaluation['ratings'].get('dribbling', 'N/A')}/10\n"
                                f"🎯 Passing: {evaluation['ratings'].get('passing', 'N/A')}/10\n"
                                f"🛡️ Defense: {evaluation['ratings'].get('defense', 'N/A')}/10\n"
                                f"🧤 Goalkeeping: {evaluation['ratings'].get('goalkeeping', 'N/A')}/10\n\n"
                                f"💰 **Calculated Value:** ¥{value}m"
                            )
                            if tryouts_channel:
                                await tryouts_channel.send(results_message)
                                logging.info(f"[TRYOUTS] Posted results in tryout results channel for {player}")
                            else:
                                await message.channel.send("⚠️ Tryouts results channel not found. Posting results here:")
                                await message.channel.send(results_message)
                                logging.warning(f"[TRYOUTS] Could not find tryouts channel for server {server_id}")
                            if player_values_channel:
                                await player_values_channel.send(f"{player.mention}, your player value has been set to ¥{value} million! 💰")
                                logging.info(f"[TRYOUTS] Posted value update in player values channel")
                            member_id = str(player.id)
                            data_manager.set_member_value(member_id, value)
                            logging.info(f"[TRYOUTS] Set player {member_id} value to {value}")
                            try:
                                tryout_role_id = 1350864967674630144  # Tryout Squad role
                                player_role_id = 1350863646187716640  # Regular Player role
                                tryout_role = discord.utils.get(guild.roles, id=tryout_role_id)
                                player_role = discord.utils.get(guild.roles, id=player_role_id)
                                if tryout_role and player_role:
                                    if tryout_role in player.roles:
                                        await player.remove_roles(tryout_role)
                                        logging.info(f"[TRYOUTS] Removed tryout role from {player.id}")
                                    await player.add_roles(player_role)
                                    logging.info(f"[TRYOUTS] Added player role to {player.id}")
                                else:
                                    logging.error(f"[TRYOUTS] Could not find roles: tryout_role={tryout_role}, player_role={player_role}")
                            except Exception as e:
                                logging.error(f"[TRYOUTS] Error updating roles: {e}", exc_info=True)
                            from_command = active_tryouts[message.author.id].get("from_command", False)
                            if not from_command:
                                try:
                                    player_dm = await player.create_dm()
                                    await player_dm.send(
                                        f"# 🎉 Your Evaluation is Complete!\n\n"
                                        f"Darling, Mommy has the results of your evaluation! 💖\n\n"
                                        f"Your value has been set to **¥{value} million**!\n\n"
                                        f"Check the tryouts channel to see your full evaluation! 📋"
                                    )
                                    logging.info(f"[TRYOUTS] Sent completion DM to player {member_id}")
                                except Exception as e:
                                    logging.warning(f"[TRYOUTS] Failed to send DM to player {member_id}: {e}")
                            else:
                                logging.info(f"[TRYOUTS] Skipped sending completion DM to player {member_id} (tryout initiated via command)")
                            del active_tryouts[message.author.id]
                            await message.channel.send(
                                "✅ **Evaluation Complete!**\n\n"
                                f"Mommy has posted the results in the tryouts channel and set {player.mention}'s value to ¥{value} million!\n\n"
                                "Thank you for helping evaluate our players, darling! 💋"
                            )
                            return
                except Exception as e:
                    logging.error(f"Error processing tryout evaluation step: {e}", exc_info=True)
                    await message.channel.send(random.choice(MOMMY_ERROR_VARIANTS))
        message_details = f"ID:{message.id}, Content:'{message.content[:30]}...', From:{message.author.name}"
        current_pid = os.getpid()
        if not hasattr(bot, "_processed_commands"):
            bot._processed_commands = {}
            logging.info(f"Initialized _processed_commands tracking dictionary for PID: {current_pid}")
        message_id_str = str(message.id)
        if message_id_str in bot._processed_commands:
            processed_data = bot._processed_commands[message_id_str]
            # Handle both formats: timestamp (float) or dictionary
            if isinstance(processed_data, dict):
                time_ago = time.time() - processed_data.get('timestamp', 0)
                original_pid = processed_data.get('pid', 'unknown')
            else:
                # If it's just a timestamp (float)
                time_ago = time.time() - processed_data
                original_pid = "unknown"
            
            # Check if this is a rankings command - always allow these through
            if is_command and message.content.lower().strip().startswith("!ranking"):
                logging.info(f"Allowing rankings command to proceed despite being processed before: {message.id}")
            elif is_command:
                logging.warning(
                    f"[DUPLICATE-INSTANCE] Message {message.id} already processed {time_ago:.2f}s ago "
                    f"by PID:{original_pid}, current PID:{current_pid}, content:'{message.content[:30]}...'"
                )
                return
            else:
                return
        current_time = time.time()
        bot._processed_commands[message_id_str] = {
            'timestamp': current_time,
            'pid': current_pid,
            'is_command': is_command
        }
        logging.info(f"[PROCESSING] {message_details} with PID {current_pid}")
        try:
            # Removed duplicate process_commands call - we already do this in the main on_message handler
            # This prevents double command processing
            if len(bot._processed_commands) > 1000:
                cutoff_time = time.time() - 3600
                keys_to_delete = []
                for msg_id, data in bot._processed_commands.items():
                    if isinstance(data, dict):
                        msg_time = data.get('timestamp', 0)
                    else:
                        # If it's just a timestamp (float)
                        msg_time = data
                    
                    if msg_time < cutoff_time:
                        keys_to_delete.append(msg_id)
                        
                for key in keys_to_delete:
                    del bot._processed_commands[key]
                    
                if keys_to_delete:
                    logging.debug(f"Cleaned up {len(keys_to_delete)} old command entries (older than 1 hour)")
        except Exception as e:
            logging.error(f"Error processing message: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"Error in on_message event: {e}", exc_info=True)

@bot.event
async def on_member_join(member):
    """Handles new member joins with animated welcome and interactive onboarding"""
    global last_heartbeat
    last_heartbeat = time.time()
    try:
        from server_config import get_new_member_role_id, get_server_config, get_channel_id, get_role_id, get_server_name
        import server_walkthrough  # Import our new walkthrough module
        
        server_id = str(member.guild.id)
        logging.info(f"New member {member.id} joined server {server_id}")
        
        # Get server configuration
        server_config = get_server_config(server_id)
        if not server_config:
            logging.warning(f"No configuration found for server {server_id}, using defaults")
            server_config = {}
            
        server_name = get_server_name(server_id)
        server_config["name"] = server_name  # Add name to config for walkthrough
        
        # Get welcome channel ID
        welcome_channel_id = get_channel_id("welcome", server_id)
        if welcome_channel_id and welcome_channel_id.isdigit():
            server_config["welcome_channel_id"] = int(welcome_channel_id)
            
        # Get new member role ID
        new_member_role_id = get_new_member_role_id(server_id)
        if new_member_role_id:
            server_config["new_member_role_id"] = int(new_member_role_id)
        
        # Use the new server walkthrough module to handle the welcome
        try:
            welcome_channel = None
            if "welcome_channel_id" in server_config:
                welcome_channel = member.guild.get_channel(server_config["welcome_channel_id"])
                
            if not welcome_channel:
                # Try to find a channel with 'welcome' in the name
                for channel in member.guild.text_channels:
                    if 'welcome' in channel.name.lower():
                        welcome_channel = channel
                        server_config["welcome_channel_id"] = channel.id
                        break
                        
            if welcome_channel:
                # Send animated welcome message
                await server_walkthrough.send_animated_welcome(welcome_channel, member, server_name)
                logging.info(f"Sent animated welcome message for {member.id} in server {server_id}")
                
                # Send interactive welcome DM
                await server_walkthrough.send_welcome_dm(member, server_config)
            else:
                logging.warning(f"Welcome channel not found for server {server_id}")
                # Try to send DM even if welcome channel not found
                await server_walkthrough.send_welcome_dm(member, server_config)
                
        except Exception as e:
            logging.error(f"Error in server walkthrough welcome: {e}", exc_info=True)
            
            # Fallback to original welcome message if walkthrough fails
            try:
                # Find welcome channel if not found earlier
                if not welcome_channel:
                    welcome_channel_id = get_channel_id("welcome", server_id)
                    if welcome_channel_id and welcome_channel_id.isdigit():
                        welcome_channel = member.guild.get_channel(int(welcome_channel_id))
                    else:
                        welcome_channel = discord.utils.get(member.guild.text_channels, name="welcome-to-novera")
                
                if welcome_channel:
                    from server_config import uses_sassy_language
                    use_sassy = uses_sassy_language(server_id)
                    
                    # Select appropriate welcome messages based on server config
                    if use_sassy:
                        welcome_messages = [
                            f"Welcome, my precious {server_name} member! Mommy is so proud to have you here!",
                            f"Aww, look who just joined! Let's make some magic together, darling!",
                            f"Oh, my sweet one, welcome to {server_name}! Mommy is excited to see you shine!"
                        ]
                    else:
                        welcome_messages = [
                            f"Welcome to {server_name}! We're glad to have you here.",
                            f"Welcome! Thank you for joining {server_name}.",
                            f"You've joined {server_name}! Welcome to the community."
                        ]
                    
                    # Create a simple welcome embed as fallback
                    welcome_message = random.choice(welcome_messages)
                    
                    embed = discord.Embed(
                        title=f"✨ Welcome to {server_name}! ✨",
                        description=f"{welcome_message}\n\n{member.mention}, we're excited to have you join us!",
                        color=discord.Color.gold()
                    )
                    
                    # Add member's avatar if available
                    if member.avatar:
                        embed.set_thumbnail(url=member.avatar.url)
                    
                    # Add footer with timestamp
                    embed.set_footer(text=f"Member #{len(member.guild.members)}")
                    embed.timestamp = datetime.now()
                    
                    await welcome_channel.send(content=f"🎉 {member.mention} has joined!", embed=embed)
                    logging.info(f"Sent fallback welcome message for {member.id} in server {server_id}")
                    
                    # Try to send a simple DM as fallback
                    try:
                        dm_channel = await member.create_dm()
                        await dm_channel.send(f"Welcome to {server_name}, {member.name}! We're glad to have you here. Use `!mommy` to see available commands!")
                    except:
                        pass
            except Exception as e2:
                logging.error(f"Error in fallback welcome message: {e2}", exc_info=True)
        
        # Add new member role regardless of walkthrough success/failure
        if new_member_role_id:
            try:
                new_member_role = discord.utils.get(member.guild.roles, id=int(new_member_role_id))
                if new_member_role:
                    await member.add_roles(new_member_role)
                    logging.info(f"Added new member role {new_member_role.name} to {member.id} in server {server_id}")
                else:
                    logging.warning(f"New member role with ID {new_member_role_id} not found in server {server_id}")
            except Exception as e:
                logging.error(f"Error adding new member role: {e}", exc_info=True)
                
    except Exception as e:
        logging.error(f"Error in on_member_join: {e}", exc_info=True)

# Note: The nuke command has been completely removed as requested.

# -----------------------------
# END OF COMMAND DEFINITIONS
# -----------------------------
# (All commands such as checkvalue, addvalue, activity, spank, headpat, eval, tryoutcancel, spill, shopping, tipjar, confess, sm, update, rankings, and mommy are defined above)
#
# -----------------------------
#

# Initialize heartbeat system
import heartbeat_manager

@tasks.loop(seconds=30)
async def update_heartbeat():
    """Update the bot's heartbeat to show it's still running"""
    try:
        # Get the global instance
        hb = heartbeat_manager.get_heartbeat_manager("discord_bot")
        
        # Update some stats
        guild_count = len(bot.guilds)
        member_count = sum(g.member_count for g in bot.guilds)
        
        # Add custom data
        hb.add_custom_data("guild_count", guild_count)
        hb.add_custom_data("member_count", member_count)
        hb.add_custom_data("commands_enabled", True)
        
        # Record status
        hb.update_status("running")
        
        logging.debug("Updated heartbeat successfully")
    except Exception as e:
        logging.error(f"Error updating heartbeat: {e}")

@bot.event
async def on_ready():
    """Called when the bot successfully connects to Discord"""
    logging.info(f"Bot is ready! Logged in as {bot.user.name} ({bot.user.id})")
    logging.info(f"Connected to {len(bot.guilds)} guilds with {sum(g.member_count for g in bot.guilds)} members")

    # Start the heartbeat system
    heartbeat = heartbeat_manager.get_heartbeat_manager("discord_bot")
    await heartbeat.start()

    # Start the heartbeat update task
    if not update_heartbeat.is_running():
        update_heartbeat.start()
        logging.info("Started heartbeat update task")

    # --- remove duplicates that live in bot.py so cogs can register ---
    bot.remove_command("addvalue")
    bot.remove_command("help")
    # ------------------------------------------------------------------

    # 🔴 IMPORTANT: load data_manager FIRST so the singleton exists
    cog_list = (
        "data_manager",            # <- NEW, must be first
        "cogs.tryouts",
        "cogs.anteup",
        "cogs.value_admin",
        "cogs.help_public",
        "cogs.roast_clanker",
        "cogs.janitor",
        "roast_rotator.py",
        "db_check.py",
    )

    for cog in cog_list:
        try:
            await bot.load_extension(cog)
            logging.info(f"✅ Loaded {cog}")
        except Exception as e:
            logging.error(f"⚠️ Failed to load {cog}: {e}")

    # Safe-shutdown hook (flush JSON etc. on SIGTERM/SIGINT if you use it)
    _install_shutdown_handler(bot.loop)
    logging.info("Shutdown handler installed")

    # Final confirmation
    print(f"🤖 Logged in as {bot.user} and all systems are running.")


@bot.event
async def on_disconnect():
    """Called when the bot disconnects from Discord"""
    logging.warning("Bot has disconnected from Discord")
    
    # Update heartbeat status
    heartbeat = heartbeat_manager.get_heartbeat_manager("discord_bot")
    heartbeat.update_status("disconnected")

if __name__ == "__main__":
    try:
        # Get token from environment
        if not TOKEN:
            logger.critical("No Discord token found!")
            sys.exit(1)
            
        # Clean up token if needed
        clean_token = TOKEN.strip().strip('"').strip("'")
        
        # Run the bot using our safe approach (avoids asyncio.run)
        discord_asyncio_fix.run_bot(bot, clean_token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by keyboard interrupt")
    except Exception as e:
        logger.critical(f"Error starting bot: {e}")
        import traceback
        logger.critical(traceback.format_exc())
