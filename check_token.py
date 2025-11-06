#!/usr/bin/env python3
"""
Simple script to check if the Discord token is valid.
This script is very basic, using only standard libraries.
"""
import os
import json
import sys
import http.client
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

def check_token():
    """Check if token is valid by making a simple API request"""
    if not TOKEN:
        logger.error("No Discord token found in environment variables")
        return False
    
    try:
        # Connect to Discord API
        conn = http.client.HTTPSConnection("discord.com")
        headers = {
            "Authorization": f"Bot {TOKEN}",
            "User-Agent": "DiscordBot (https://github.com/discord/discord-api-docs, 1.0.0)"
        }
        
        # Make a request to get current user (bot) information
        conn.request("GET", "/api/v10/users/@me", headers=headers)
        response = conn.getresponse()
        
        # Read response
        data = response.read()
        conn.close()
        
        if response.status == 200:
            bot_info = json.loads(data)
            logger.info(f"Token is valid for bot: {bot_info.get('username')}#{bot_info.get('discriminator')}")
            logger.info(f"Bot ID: {bot_info.get('id')}")
            return True
        else:
            error_data = json.loads(data)
            logger.error(f"Invalid token: Status {response.status}, Message: {error_data}")
            return False
            
    except Exception as e:
        logger.error(f"Error checking token: {e}")
        return False

if __name__ == "__main__":
    if check_token():
        print("✅ Discord token is valid")
        sys.exit(0)
    else:
        print("❌ Discord token is invalid")
        sys.exit(1)