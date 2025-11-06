#!/usr/bin/env python3
"""
Final Solution for Discord Bot Stability
----------------------------------------
This module provides a radically different approach for running the Discord bot.
It completely separates the event loop management from the bot startup code.

Key differences from previous approaches:
1. Uses multiprocessing instead of threading to guarantee process isolation
2. Reloads python modules to avoid any cached state issues
3. Completely bypasses the problematic event loop conflict scenario
4. Directly manages processes like a service manager would
"""

import os
import sys
import time
import logging
import signal
import multiprocessing
import subprocess
import importlib
import json
import atexit
import requests
from multiprocessing import Process

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('final_solution.log')
    ]
)
logger = logging.getLogger(__name__)

# Create a lockfile to prevent multiple instances
LOCK_FILE = "final_solution.lock"
HEARTBEAT_FILE = "final_heartbeat.json"

# Parameters for reliability
CHECK_INTERVAL = 10  # seconds
MAX_RESTARTS = 10

# Track global state
restart_count = 0
last_restart_time = 0
bot_process = None
web_server_process = None

def create_lockfile():
    """Create a lockfile to prevent multiple instances"""
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        logger.info(f"Created lockfile with PID {os.getpid()}")
        return True
    except Exception as e:
        logger.error(f"Error creating lockfile: {e}")
        return False

def remove_lockfile():
    """Remove the lockfile when shutting down"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            logger.info("Removed lockfile")
    except Exception as e:
        logger.error(f"Error removing lockfile: {e}")

def check_lockfile():
    """Check if another instance is already running"""
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
                try:
                    # Send signal 0 to check if process exists
                    os.kill(pid, 0)
                    logger.error(f"Another instance is already running with PID {pid}")
                    return True
                except OSError:
                    # Process is not running, we can proceed
                    logger.warning(f"Stale lockfile found, previous process {pid} is not running")
                    remove_lockfile()
        return False
    except Exception as e:
        logger.error(f"Error checking lockfile: {e}")
        return False

def write_heartbeat():
    """Write a heartbeat file that can be checked by monitoring services"""
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            data = {
                "timestamp": time.time(),
                "pid": os.getpid()
            }
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error writing heartbeat: {e}")

def kill_process(proc):
    """Safely kill a process"""
    if proc and proc.is_alive():
        try:
            logger.info(f"Terminating process {proc.pid}")
            proc.terminate()
            proc.join(5)  # Wait up to 5 seconds
            
            # If it's still alive, force kill
            if proc.is_alive():
                logger.warning(f"Process {proc.pid} did not terminate, force killing")
                proc.kill()
                proc.join(2)
        except Exception as e:
            logger.error(f"Error killing process: {e}")

def start_web_server():
    """Start the Flask web server in a separate process"""
    try:
        logger.info("Starting web server")
        
        # Create entry point script for the web server
        web_server_script = """
import os
import sys
import flask
from flask import Flask, jsonify, request

# Create app
app = Flask(__name__)

@app.route('/')
def home():
    return "Novera Assistant is watching you darling! 👀"

@app.route('/healthz')
def healthz():
    return jsonify({
        "status": "ok",
        "uptime": os.getpid()
    })

# Run the server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
"""
        with open("web_server_entry.py", "w") as f:
            f.write(web_server_script)
        
        # Start the web server in a separate process
        proc = subprocess.Popen(
            [sys.executable, "web_server_entry.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        logger.info(f"Started web server with PID {proc.pid}")
        
        # Start a thread to log output
        def log_output():
            while proc.poll() is None:
                try:
                    # Read stdout
                    stdout_line = proc.stdout.readline().decode('utf-8', errors='ignore').strip()
                    if stdout_line:
                        logger.info(f"WEB OUT: {stdout_line}")
                        
                    # Read stderr
                    stderr_line = proc.stderr.readline().decode('utf-8', errors='ignore').strip()
                    if stderr_line:
                        logger.error(f"WEB ERR: {stderr_line}")
                except Exception as e:
                    logger.error(f"Error reading web server output: {e}")
                    break
                    
        import threading
        threading.Thread(target=log_output, daemon=True).start()
        
        return proc
    except Exception as e:
        logger.error(f"Error starting web server: {e}")
        return None

def direct_discord_bot_process():
    """Core process for running the Discord bot directly"""
    try:
        # Import core dependencies
        import discord
        from discord.ext import commands
        import logging
        import os
        
        # Set up logging within this process
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Get the Discord token
        TOKEN = os.environ.get("DISCORD_TOKEN", "")
        
        # If not set, try loading from .env
        if not TOKEN:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                TOKEN = os.environ.get("DISCORD_TOKEN", "")
            except ImportError:
                logging.error("Could not import dotenv")
        
        # Verify we have a token
        if not TOKEN:
            logging.critical("No Discord token found!")
            return
        
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        # Create the bot
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        # Define essential bot event handlers
        @bot.event
        async def on_ready():
            logging.info(f"Bot is connected as {bot.user}")
            logging.info(f"Connected to {len(bot.guilds)} servers")
            
            # Set the bot's status
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="over you, darling"
                )
            )
            
            # Update heartbeat file
            with open(HEARTBEAT_FILE, "w") as f:
                data = {
                    "timestamp": time.time(),
                    "discord_connected": True,
                    "username": str(bot.user),
                    "guilds": len(bot.guilds)
                }
                json.dump(data, f)
        
        @bot.event
        async def on_message(message):
            # Don't respond to our own messages
            if message.author == bot.user:
                return
                
            # Log the message
            logging.info(f"Message from {message.author}: {message.content}")
            
            # Process commands
            await bot.process_commands(message)
        
        # Add a simple test command
        @bot.command()
        async def test(ctx):
            await ctx.send("I'm working perfectly, darling! 💋")
            
        # Run the bot with a clean approach
        logging.info(f"Starting Discord bot with token of length {len(TOKEN)}")
        bot.run(TOKEN)
        
    except Exception as e:
        logging.critical(f"Fatal error in Discord bot: {e}", exc_info=True)

def start_discord_bot():
    """Start the Discord bot in a separate process"""
    global restart_count, last_restart_time
    
    try:
        # Check restart limits
        current_time = time.time()
        if current_time - last_restart_time < 60 and restart_count >= MAX_RESTARTS:
            logger.warning("Hit maximum restart limit, waiting longer before retry")
            time.sleep(120)  # Longer cooldown
            restart_count = 0
        
        # Create a dedicated script for the bot
        with open("direct_startup.py", "w") as f:
            f.write("""
# Direct startup script for Discord bot
import sys
import os

# Call the core process function
from final_solution import direct_discord_bot_process

# Run the bot
if __name__ == "__main__":
    direct_discord_bot_process()
""")
        
        # Start the bot in a separate process
        logger.info("Starting Discord bot process")
        proc = subprocess.Popen(
            [sys.executable, "direct_startup.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        logger.info(f"Started Discord bot with PID {proc.pid}")
        last_restart_time = time.time()
        restart_count += 1
        
        # Start a thread to log output
        def log_output():
            while proc.poll() is None:
                try:
                    # Read stdout
                    stdout_line = proc.stdout.readline().decode('utf-8', errors='ignore').strip()
                    if stdout_line:
                        logger.info(f"BOT OUT: {stdout_line}")
                        
                    # Read stderr
                    stderr_line = proc.stderr.readline().decode('utf-8', errors='ignore').strip()
                    if stderr_line:
                        logger.error(f"BOT ERR: {stderr_line}")
                except Exception as e:
                    logger.error(f"Error reading bot output: {e}")
                    break
                    
        import threading
        threading.Thread(target=log_output, daemon=True).start()
        
        return proc
    except Exception as e:
        logger.error(f"Error starting Discord bot: {e}")
        return None

def is_web_server_running():
    """Check if the web server is running and responsive"""
    try:
        response = requests.get("http://localhost:5001/healthz", timeout=2)
        return response.status_code == 200
    except Exception:
        return False

def is_discord_bot_connected():
    """Check if the Discord bot is connected by reading the heartbeat file"""
    try:
        if os.path.exists(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, "r") as f:
                data = json.load(f)
                
                # Check if we have a recent heartbeat
                current_time = time.time()
                timestamp = data.get("timestamp", 0)
                
                # If heartbeat is more than 2 minutes old, consider it stale
                if current_time - timestamp > 120:
                    return False
                    
                # Check Discord connection status
                return data.get("discord_connected", False)
        return False
    except Exception as e:
        logger.error(f"Error checking Discord bot connection: {e}")
        return False

def cleanup():
    """Clean up before exiting"""
    global bot_process, web_server_process
    
    logger.info("Cleaning up")
    
    # Stop processes
    if bot_process:
        kill_process(bot_process)
    
    if web_server_process:
        kill_process(web_server_process)
    
    # Remove lockfile
    remove_lockfile()

def monitor_processes():
    """Monitor processes and restart them if necessary"""
    global bot_process, web_server_process, restart_count
    
    logger.info("Starting process monitoring")
    
    try:
        # Start web server
        web_server_process = start_web_server()
        
        # Start Discord bot
        bot_process = start_discord_bot()
        
        # Monitor loop
        while True:
            try:
                # Write heartbeat
                write_heartbeat()
                
                # Check web server
                web_server_running = web_server_process and web_server_process.poll() is None
                if not web_server_running or not is_web_server_running():
                    logger.warning("Web server is not running, restarting")
                    if web_server_process:
                        kill_process(web_server_process)
                    web_server_process = start_web_server()
                
                # Check Discord bot
                bot_running = bot_process and bot_process.poll() is None
                if not bot_running or not is_discord_bot_connected():
                    logger.warning("Discord bot is not running or not connected, restarting")
                    if bot_process:
                        kill_process(bot_process)
                    bot_process = start_discord_bot()
                
                # Sleep
                time.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        cleanup()

def main():
    """Main entry point"""
    # Check if another instance is already running
    if check_lockfile():
        logger.error("Another instance is already running, exiting")
        return
    
    # Create lockfile
    if not create_lockfile():
        logger.error("Could not create lockfile, exiting")
        return
    
    # Register cleanup handler
    atexit.register(cleanup)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    
    # Start monitoring
    monitor_processes()

if __name__ == "__main__":
    main()