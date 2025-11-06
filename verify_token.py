#!/usr/bin/env python3
"""
Discord Token Verification Tool
This script tests if a Discord token is valid by making a direct API request.
It will fail fast if the token is invalid to prevent wasting time on startup.
"""

import os
import sys
import requests
import logging
import json
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("verify_token.log")
    ]
)
logger = logging.getLogger("verify_token")

def clean_token(token):
    """Clean a token to remove quotes, whitespace, and non-printable characters"""
    if not token:
        return ""
        
    # Remove quotes, newlines, and other formatting characters
    cleaned = token.strip().replace('"', '').replace("'", '').replace('\n', '').replace('\r', '')
    
    # Remove any unicode non-printable characters that might cause issues
    cleaned = ''.join(c for c in cleaned if c.isprintable() and not c.isspace())
    
    return cleaned

def verify_discord_token(token):
    """Verify a Discord token by making a real API request to Discord"""
    # Clean the token first
    token = clean_token(token)
    
    # Create headers with the token
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "DiscordBot (https://example.com, v1.0)"
    }
    
    # Try making a request to Discord API
    try:
        logger.info("Testing Discord token with API request...")
        response = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            username = user_data.get("username")
            user_id = user_data.get("id")
            logger.info(f"Token is valid! Connected to {username} (ID: {user_id})")
            return True, f"Valid token for {username}"
        elif response.status_code == 401:
            logger.error("Token is invalid: 401 Unauthorized")
            return False, "Invalid token: 401 Unauthorized"
        else:
            logger.warning(f"Unexpected response code: {response.status_code}")
            error_text = response.text[:100] if response.text else "No response text"
            return False, f"Unexpected response: {response.status_code} - {error_text}"
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return False, f"Error: {str(e)}"

def main():
    # Check if token is in environment
    token = os.environ.get('DISCORD_TOKEN')
    
    if not token:
        logger.error("DISCORD_TOKEN environment variable is not set")
        print("ERROR: DISCORD_TOKEN environment variable is not set")
        sys.exit(1)
    
    logger.info(f"Found token in environment (length: {len(token)})")
    
    # Verify the token with Discord
    is_valid, message = verify_discord_token(token)
    
    if is_valid:
        logger.info("Token verification successful!")
        print(f"SUCCESS: {message}")
        
        # Save verification result for recovery systems
        with open("token_verification.json", "w") as f:
            json.dump({
                "valid": True,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }, f)
        
        sys.exit(0)
    else:
        logger.error(f"Token verification failed: {message}")
        print(f"ERROR: {message}")
        
        # Save verification result for recovery systems
        with open("token_verification.json", "w") as f:
            json.dump({
                "valid": False,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }, f)
        
        sys.exit(1)

if __name__ == "__main__":
    main()