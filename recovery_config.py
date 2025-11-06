#!/usr/bin/env python3
"""
CENTRAL RECOVERY CONFIGURATION
This file provides a single source of truth for all recovery scripts
"""

import os
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("recovery_config.log")
    ]
)
logger = logging.getLogger("recovery_config")

# PORT CONFIGURATION
# This is critical - all scripts must use the same port!
BOT_PORT = 5001  # The port that bot.py runs on
HEALTH_CHECK_URL = f"http://127.0.0.1:{BOT_PORT}/healthz"
HOME_URL = f"http://127.0.0.1:{BOT_PORT}/"

# MONITORING CONFIGURATION
CHECK_INTERVAL = 10  # Check every 10 seconds
MAX_CONSECUTIVE_FAILURES = 2  # Only 2 failures before restarting
NO_COOLDOWN = True  # Disable all cooldowns

# AUTH ERROR PATTERNS
AUTH_ERROR_PATTERNS = [
    r"discord.errors.LoginFailure",
    r"401 Unauthorized",
    r"Token authentication failed",
    r"Improper token",
    r"Invalid token",
    r"Authentication failed"
]

# LOG FILES
LOG_FILES = [
    "bot_errors.log", 
    "bot.log",
    "logs/gunicorn.log",
    "emergency_restart.log",
    "token_refresher.log",
    "token_monitor.log",
    "watchdog.log",
    "auto_401_recovery.log",
    "ultimate_recovery.log"
]

# RECOVERY COMMANDS - In order of preference
RECOVERY_COMMANDS = [
    ["python", "bot.py"],
    ["python", "main.py"],
    ["bash", "bulletproof.sh"],
    ["bash", "super_recovery.sh"],
    ["bash", "never_down.sh"]
]

# Function to read the config
def get_config():
    return {
        "bot_port": BOT_PORT,
        "health_check_url": HEALTH_CHECK_URL,
        "home_url": HOME_URL,
        "check_interval": CHECK_INTERVAL,
        "max_consecutive_failures": MAX_CONSECUTIVE_FAILURES,
        "no_cooldown": NO_COOLDOWN,
        "auth_error_patterns": AUTH_ERROR_PATTERNS,
        "log_files": LOG_FILES,
        "recovery_commands": RECOVERY_COMMANDS
    }

# Export config for bash scripts
def export_config_json():
    config = get_config()
    try:
        with open("recovery_config.json", "w") as f:
            json.dump(config, f, indent=2)
        logger.info("Exported recovery config to JSON")
    except Exception as e:
        logger.error(f"Error exporting config: {e}")

# Load the config
def load_config():
    try:
        with open("recovery_config.json", "r") as f:
            config = json.load(f)
        logger.info("Loaded recovery config from JSON")
        return config
    except Exception as e:
        logger.error(f"Error loading config, using defaults: {e}")
        return get_config()

# Apply port configuration to environment
def set_port_env():
    os.environ["BOT_PORT"] = str(BOT_PORT)
    logger.info(f"Set BOT_PORT environment variable to {BOT_PORT}")

# Run when imported
set_port_env()
export_config_json()

# When run directly
if __name__ == "__main__":
    logger.info("Recovery config initialized")
    print(f"BOT_PORT = {BOT_PORT}")
    print(f"HEALTH_CHECK_URL = {HEALTH_CHECK_URL}")
    print("Config exported to recovery_config.json")