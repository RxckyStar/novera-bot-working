import os
import sys
import time
import json
import logging
import asyncio
import threading
import signal
import subprocess
import atexit
from datetime import datetime

import discord
from discord.ext import commands
from flask import Flask, jsonify, render_template, request, redirect, url_for

# Intents defined AFTER importing discord
intents = discord.Intents.default()
intents.message_content = True

# Import our instance manager
from instance_manager import (
    claim_instance, release_instance, kill_other_instances, write_pid_file,
    WATCHDOG_PID_FILE, BOT_PID_FILE, WEB_PID_FILE
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.start_time = time.time()
app.last_heartbeat = time.time()

@app.route('/')
def home():
    try:
        bot_status = check_bot_status()
        uptime = int(time.time() - app.start_time)
        uptime_formatted = f"{uptime // 86400}d {(uptime % 86400) // 3600}h {(uptime % 3600) // 60}m {uptime % 60}s"
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Novera Assistant - System Status</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    color: #333;
                    background: #f5f5f5;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }}
                h1 {{ color: #2c3e50; text-align: center; }}
                .status {{ padding: 15px; margin: 15px 0; border-radius: 5px; }}
                .status.online {{
                    background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;
                }}
                .status.offline {{
                    background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;
                }}
                .info {{ background-color: #e2f0fb; padding: 10px; border-radius: 5px; margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Novera Assistant - System Status</h1>
                <div class="status {'online' if bot_status.get('truly_healthy', False) else 'offline'}">
                    <h2>Discord Bot: {'ONLINE' if bot_status.get('truly_healthy', False) else 'OFFLINE'}</h2>
                    <p>The Novera Assistant is {'connected and responding' if bot_status.get('truly_healthy', False) else ('stalled: no recent activity' if bot_status.get('bot_connected', False) else 'currently offline')}</p>
                </div>
                
                <div class="info">
                    <h3>System Information</h3>
                    <p><strong>System Uptime:</strong> {uptime_formatted}</p>
                    <p><strong>Status:</strong> {bot_status.get('status', 'Unknown')}</p>
                    <p><strong>Bot Process Running:</strong> {'Yes' if is_bot_running() else 'No'}</p>
                </div>
                
                <div class="info">
                    <h3>Health Endpoints</h3>
                    <p><a href="/healthz">System Health Check</a></p>
                </div>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        logger.error(f"Error generating home page: {e}")
        return f"<h1>System Status</h1><p>Error retrieving status: {str(e)}</p>"

def check_bot_status():
    """Check the status of the bot by querying its health endpoint"""
    try:
        import requests
        response = requests.get("http://localhost:5001/healthz", timeout=2)
        if response.status_code == 200:
            data = response.json()
            last_heartbeat_age = data.get("last_heartbeat_age", 9999)
            data["truly_healthy"] = bool(data.get("bot_connected", False) and last_heartbeat_age < 120)
            return data
        else:
            return {"status": "error", "bot_connected": False, "truly_healthy": False}
    except Exception as e:
        logger.error(f"Error checking bot status: {e}")
        return {"status": "error", "bot_connected": False, "truly_healthy": False}

@app.route('/healthz')
def healthz():
    app.last_heartbeat = time.time()
    current_time = time.time()
    heartbeat_age = current_time - app.last_heartbeat
    status = "healthy" if heartbeat_age < 30 else "warning" if heartbeat_age < 60 else "unhealthy"
    bot_status = check_bot_status()
    bot_connected = bot_status.get("bot_connected", False)
    truly_healthy = bot_status.get("truly_healthy", False)
    overall_status = "healthy"
    if status != "healthy" or not truly_healthy:
        if not bot_connected:
            overall_status = "critical"
        elif not truly_healthy:
            overall_status = "stalled"
        else:
            overall_status = "warning"
    return jsonify({
        "status": overall_status,
        "web_status": status,
        "uptime": int(current_time - app.start_time),
        "last_heartbeat_age": int(heartbeat_age),
        "process_id": os.getpid(),
        "bot_connected": bot_connected,
        "bot_active": truly_healthy,
        "bot_status": bot_status.get("status", "unknown"),
        "bot_heartbeat_age": bot_status.get("last_heartbeat_age", -1)
    })

def cleanup():
    """Clean up resources and release instance on exit"""
    logger.info("Web server shutting down, cleaning up resources")
    release_instance(WEB_PID_FILE)

atexit.register(cleanup)

def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}. Shutting down gracefully...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def is_bot_running():
    """Check if a bot process is already running"""
    try:
        # Raw string to avoid escape warnings
        result = subprocess.run(
            ["pgrep", "-f", r"python.*bot\.py"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            logger.info(f"Bot already running with PID(s): {result.stdout.strip()}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking for running bot: {e}")
        return False

def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    # Check if web server is already running using instance manager
    if not claim_instance(WEB_PID_FILE, "main.py"):
        logger.error("Web server already running! Exiting to prevent duplicates.")
        sys.exit(1)

    # Record our PID
    write_pid_file(WEB_PID_FILE)

    # Only run the Flask health endpoint from this file.
    logger.info("Running Flask health endpoint only with improved instance management")
    try:
        run_flask()
    except Exception as e:
        logger.critical(f"Web server crashed: {e}")
        release_instance(WEB_PID_FILE)
        sys.exit(1)
