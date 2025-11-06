#!/usr/bin/env python3
"""
Token Update Utility
-------------------
This utility ensures the Discord token is correctly set in the environment.
It will request the token from the environment, validate it, and update both
the environment variables and any token cache files.
"""
import os
import sys
import time
import json
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("token_update.log")
    ]
)
logger = logging.getLogger(__name__)

def load_token_from_env():
    """Load Discord token from environment variables"""
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        logger.error("No Discord token found in environment variables")
        return None
    
    # Basic validation - check token length and format
    if len(token) < 50:
        logger.error(f"Token seems too short ({len(token)} chars), it may be invalid")
        return None
    
    if not token.startswith("M") and not token.startswith("N"):
        logger.warning("Token doesn't begin with expected characters, it may be invalid")
    
    logger.info(f"Found token in environment (length: {len(token)})")
    return token

def update_token_in_env_file(token):
    """Update the token in the .env file"""
    if not token:
        return False
    
    try:
        # Check if .env exists
        if os.path.exists(".env"):
            # Read existing file
            with open(".env", "r") as f:
                lines = f.readlines()
            
            # Check if token line exists and update it
            token_line_exists = False
            for i, line in enumerate(lines):
                if line.startswith("DISCORD_TOKEN="):
                    lines[i] = f"DISCORD_TOKEN={token}\n"
                    token_line_exists = True
                    break
            
            # Add token line if it doesn't exist
            if not token_line_exists:
                lines.append(f"DISCORD_TOKEN={token}\n")
            
            # Write back to file
            with open(".env", "w") as f:
                f.writelines(lines)
        else:
            # Create new .env file
            with open(".env", "w") as f:
                f.write(f"DISCORD_TOKEN={token}\n")
        
        logger.info("Updated token in .env file")
        return True
    except Exception as e:
        logger.error(f"Error updating token in .env file: {e}")
        return False

def update_token_cache(token):
    """Update the token in any cache files"""
    if not token:
        return False
    
    try:
        # Default token cache paths
        cache_paths = [
            "token_cache.json",
            ".token_cache",
            "config/token_cache.json"
        ]
        
        success = False
        for path in cache_paths:
            if os.path.exists(path):
                try:
                    data = {}
                    # Try to read existing data
                    try:
                        with open(path, "r") as f:
                            data = json.load(f)
                    except:
                        data = {}
                    
                    # Update token
                    data["token"] = token
                    data["updated_at"] = time.time()
                    
                    # Write back to file
                    with open(path, "w") as f:
                        json.dump(data, f)
                    
                    logger.info(f"Updated token in cache file: {path}")
                    success = True
                except Exception as e:
                    logger.error(f"Error updating token in {path}: {e}")
        
        return success
    except Exception as e:
        logger.error(f"Error updating token cache: {e}")
        return False

def main():
    """Main function to update token in all locations"""
    logger.info("Starting token update utility")
    
    # Load token from environment
    token = load_token_from_env()
    
    if not token:
        logger.error("Failed to load a valid token")
        return 1
    
    # Update token in .env file
    update_token_in_env_file(token)
    
    # Update token in cache files
    update_token_cache(token)
    
    logger.info("Token update completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())