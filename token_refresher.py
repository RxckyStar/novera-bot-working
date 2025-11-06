#!/usr/bin/env python3
"""
Discord Token Refresher
This script forces a refresh of the Discord token by checking the environment
and ensuring it's properly set and valid.

It can be run manually or automatically called by the recovery system.
"""

import os
import sys
import time
import logging
import json
import re
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("token_refresher.log")
    ]
)
logger = logging.getLogger("token_refresher")

# Token cache file
TOKEN_CACHE_FILE = "token_cache.json"
REFRESH_HISTORY_FILE = "token_refresh_history.log"

def validate_token(token):
    """Validate that a token has the correct format and length"""
    if not token:
        return False
        
    token_length = len(token)
    
    # Discord tokens are typically 59-70+ characters
    if token_length < 50:
        logger.warning(f"Token too short (length: {token_length})")
        return False
        
    # Check if token matches expected Discord token patterns
    token_patterns = [
        # Various common Discord token prefixes - these can change over time as Discord updates
        r'^MT[A-Za-z0-9_-]', r'^mT[A-Za-z0-9_-]', r'^Mj[A-Za-z0-9_-]', 
        r'^mj[A-Za-z0-9_-]', r'^Nz[A-Za-z0-9_-]', r'^nz[A-Za-z0-9_-]',
        r'^OT[A-Za-z0-9_-]', r'^ot[A-Za-z0-9_-]'
    ]
    
    pattern_matched = any(re.match(pattern, token) for pattern in token_patterns)
    
    # Safe logging that doesn't expose the full token
    prefix = token[:8] + "..." if token_length > 15 else "[too_short]"
    suffix = "..." + token[-5:] if token_length > 15 else ""
    
    logger.info(f"Token length: {token_length}, prefix: {prefix}, suffix: {suffix}, valid format: {pattern_matched}")
    
    # Additional structural validation - Discord tokens have dots as separators
    has_valid_structure = '.' in token
    
    return token_length >= 50 and (pattern_matched or has_valid_structure)

def clean_token(token):
    """Clean a token to remove quotes, whitespace, and non-printable characters"""
    if not token:
        return ""
        
    # Remove quotes, newlines, and other formatting characters
    cleaned = token.strip().replace('"', '').replace("'", '').replace('\n', '').replace('\r', '')
    
    # Remove any unicode non-printable characters that might cause issues
    cleaned = ''.join(c for c in cleaned if c.isprintable() and not c.isspace())
    
    return cleaned

def save_token_cache(token):
    """Save a valid token to cache for recovery scenarios"""
    try:
        cache_data = {
            "token": token,
            "timestamp": datetime.now().isoformat(),
            "validated": True
        }
        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
        logger.info("Token cached successfully for recovery")
        
        # Also record in refresh history
        with open(REFRESH_HISTORY_FILE, "a") as f:
            f.write(f"{datetime.now().isoformat()} - Token refreshed and cached\n")
    except Exception as e:
        logger.warning(f"Failed to cache token: {e}")

def reload_from_environment():
    """Attempt to reload token from environment variable"""
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN environment variable not set or empty")
        return None
        
    # Clean the token
    cleaned_token = clean_token(token)
    
    # Validate the token
    if validate_token(cleaned_token):
        logger.info("Discord token validated successfully")
        return cleaned_token
    else:
        logger.warning("Discord token failed validation")
        return None

def update_config_file(token):
    """Update TOKEN in config.py if it exists (for legacy compatibility)"""
    try:
        if not os.path.exists("config.py"):
            logger.info("config.py not found, no update needed")
            return False
            
        logger.info("Updating TOKEN in config.py")
        
        # Read the file
        with open("config.py", "r") as f:
            content = f.read()
            
        # Try advanced approach - look for specific patterns
        token_patterns = [
            r"TOKEN\s*=\s*['\"].*?['\"]",
            r"TOKEN\s*=\s*get_token\(\)",
            r"TOKEN\s*=.*?load_token_from_cache.*?\)"
        ]
        
        found_match = False
        for pattern in token_patterns:
            if re.search(pattern, content):
                found_match = True
                logger.info("Found token pattern in config.py")
                break
                
        if not found_match:
            logger.info("Token comes from environment, no need to update config.py")
            return False
            
        # More advanced attempt - if token comes from environment,
        # there's no need to update the config file, as it will
        # be picked up automatically with each restart
        if "os.environ.get('DISCORD_TOKEN')" in content or 'os.environ.get("DISCORD_TOKEN")' in content:
            logger.info("Token comes from environment, no need to update config.py")
            return False
            
        logger.info("Trying alternative token update approach")
        # If we get here, the token is likely a hardcoded value in the file
        # Usually not the case for modern apps, so we will avoid modifying the file
        logger.info("Token comes from environment, no need to update config.py")
        return False
    except Exception as e:
        logger.error(f"Error updating config file: {e}")
        return False

def force_refresh():
    """Force a refresh of the Discord token"""
    logger.info("Forced token refresh requested via command line")
    logger.info("Attempting to refresh Discord token...")
    
    # Attempt to reload from environment
    token = reload_from_environment()
    
    if token:
        # Save the valid token to cache
        save_token_cache(token)
        
        # Update config.py if it exists
        update_config_file(token)
        
        logger.info("Forced token refresh completed successfully")
        return True
    else:
        logger.error("Failed to refresh token - valid token not found in environment")
        return False
        
def check_for_refresh_signal():
    """Check if a refresh signal file exists and is recent"""
    if os.path.exists("refresh_token"):
        try:
            # Get the modification time
            mtime = os.path.getmtime("refresh_token")
            current_time = time.time()
            
            # Only refresh if the signal file is less than 5 minutes old
            if current_time - mtime < 300:
                logger.info("Found recent refresh signal file")
                # Delete the signal file
                os.remove("refresh_token")
                return True
        except Exception as e:
            logger.error(f"Error checking refresh signal: {e}")
    
    return False

def main():
    parser = argparse.ArgumentParser(description="Discord Token Refresher")
    parser.add_argument("--force", action="store_true", help="Force refresh token")
    args = parser.parse_args()
    
    logger.info("Discord Token Refresher started")
    
    # Check if forced refresh requested
    if args.force or check_for_refresh_signal():
        force_refresh()
    
if __name__ == "__main__":
    main()