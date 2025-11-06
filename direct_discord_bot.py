#!/usr/bin/env python3
"""
Direct Discord Bot Runner
------------------------
This is a stripped-down, self-contained version of the Discord bot
that runs completely independently from the main bot.py.

This version:
1. Has its own event loop management
2. Doesn't share any state with the main bot
3. Has minimal dependencies for maximum stability
4. Serves as a failsafe option for when other approaches fail
"""

import os
import sys
import time
import json
import logging
import asyncio
import threading
import importlib
import traceback
import subprocess
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('direct_discord_bot.log')
    ]
)

# Flask web server for health checks
def start_web_server():
    try:
        from flask import Flask, jsonify
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return "Novera Assistant is online, darling! 💋"
        
        @app.route('/healthz')
        def healthz():
            return jsonify({
                "status": "ok",
                "timestamp": time.time()
            })
        
        # Run in a separate thread
        def run_flask():
            app.run(host='0.0.0.0', port=5001)
        
        threading.Thread(target=run_flask, daemon=True).start()
        logging.info("Started web server on port 5001")
        
    except Exception as e:
        logging.error(f"Failed to start web server: {e}")

# Define a standalone function to update the heartbeat
def update_heartbeat(connected=False, user=None, guilds=None):
    try:
        data = {
            "timestamp": time.time(),
            "connected": connected
        }
        
        if user:
            data["username"] = str(user)
        
        if guilds:
            data["guilds"] = len(guilds)
        
        with open("bot_heartbeat.json", "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Failed to update heartbeat: {e}")

# Main bot function
def run_discord_bot():
    try:
        import discord
        from discord.ext import commands, tasks
        
        # Get token
        TOKEN = os.environ.get("DISCORD_TOKEN", "")
        
        # If not set, try loading from .env
        if not TOKEN:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                TOKEN = os.environ.get("DISCORD_TOKEN", "")
            except ImportError:
                logging.error("Could not import dotenv")
        
        # Create bot with intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        @bot.event
        async def on_ready():
            logging.info(f"Direct bot connected as {bot.user}")
            logging.info(f"Connected to {len(bot.guilds)} servers")
            
            for guild in bot.guilds:
                logging.info(f"- {guild.name} (ID: {guild.id})")
            
            # Set status
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="over you, darling"
                )
            )
            
            # Start heartbeat task
            heartbeat_task.start()
            
            # Update heartbeat file
            update_heartbeat(connected=True, user=bot.user, guilds=bot.guilds)
        
        @tasks.loop(seconds=30)
        async def heartbeat_task():
            logging.info("HEARTBEAT: Bot is still running")
            update_heartbeat(connected=True, user=bot.user, guilds=bot.guilds)
        
        @bot.event
        async def on_message(message):
            # Don't respond to our own messages
            if message.author == bot.user:
                return
            
            # Log message
            logging.info(f"Message from {message.author.name} in {message.guild.name if message.guild else 'DM'}: {message.content}")
            
            # Process commands
            await bot.process_commands(message)
        
        # Basic commands for functionality verification
        @bot.command()
        async def ping(ctx):
            await ctx.send(f"Pong! Latency: {round(bot.latency * 1000)}ms")
        
        @bot.command()
        async def status(ctx):
            embed = discord.Embed(
                title="Bot Status",
                description="Direct bot is running in fallback mode",
                color=discord.Color.green()
            )
            embed.add_field(name="Connected servers", value=len(bot.guilds))
            embed.add_field(name="Uptime", value="Running since startup")
            embed.add_field(name="Mode", value="Direct mode (maximum reliability)")
            await ctx.send(embed=embed)
        
        # Run the bot
        logging.info(f"Starting Discord bot with token of length {len(TOKEN)}")
        
        # Run in a special way to handle asyncio exceptions
        bot.run(TOKEN)
        
    except Exception as e:
        logging.critical(f"Fatal error in Discord bot: {e}")
        traceback.print_exc()

def main():
    """Main entry point"""
    logging.info("Starting direct Discord bot")
    
    # Start web server in background
    start_web_server()
    
    # Run the bot
    run_discord_bot()

if __name__ == "__main__":
    main()