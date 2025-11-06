"""
Discord Token Tester - Version 2.0 (No Circular Dependencies)
This script verifies if a Discord token is valid without attempting to start a full bot.
It provides a more lightweight and reliable way to check token validity than the validation regex.
This version is designed to completely eliminate circular dependencies with config.py.
"""

import os
import logging
import requests
import time
import json
import re
from typing import Tuple, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token utilities duplicated here to avoid circular imports with config.py
def clean_token(token: str) -> str:
    """Clean a token to remove quotes, whitespace, and non-printable characters"""
    if not token:
        return ""
        
    # Remove quotes, newlines, and other formatting characters
    cleaned = token.strip().replace('"', '').replace("'", '').replace('\n', '').replace('\r', '')
    
    # Remove any unicode non-printable characters that might cause issues
    cleaned = ''.join(c for c in cleaned if c.isprintable() and not c.isspace())
    
    # Fix common formatting issues that can cause "Improper token" errors
    # Some systems add unwanted whitespace or encoding characters
    if cleaned.startswith("\\u") or cleaned.startswith("u'"):
        # Handle unicode escape sequence at the beginning
        logger.warning("Detected possible unicode escape sequence in token, fixing...")
        # Try to extract the actual token part
        parts = re.findall(r'[A-Za-z0-9_\-\.]{50,100}', cleaned)
        if parts:
            cleaned = parts[0]
            logger.info("Successfully extracted token from unicode sequence")
            
    return cleaned

def validate_token(token: str) -> bool:
    """Validate that a token has the correct format and length"""
    if not token:
        return False
        
    token_length = len(token)
    
    # Discord tokens are typically 59-70+ characters
    if token_length < 40:  # Lowered threshold to be more permissive
        logger.warning(f"Token too short (length: {token_length})")
        return False
        
    # Extract the base token if it has any additional characters
    # This helps with tokens copied from different sources (web, mobile, etc.)
    base_token_match = re.search(r'[A-Za-z0-9_\-\.]{40,100}', token)
    if base_token_match:
        extracted_token = base_token_match.group(0)
        if extracted_token != token:
            logger.warning(f"Extracted clean token from complex string (original len: {token_length}, extracted len: {len(extracted_token)})")
            token = extracted_token
            token_length = len(token)
    
    # Check if token matches expected Discord token patterns
    token_patterns = [
        # Various common Discord token prefixes - these can change over time as Discord updates
        r'^MT[A-Za-z0-9_\-\.]', r'^mT[A-Za-z0-9_\-\.]', r'^Mj[A-Za-z0-9_\-\.]', 
        r'^mj[A-Za-z0-9_\-\.]', r'^Nz[A-Za-z0-9_\-\.]', r'^nz[A-Za-z0-9_\-\.]',
        r'^OT[A-Za-z0-9_\-\.]', r'^ot[A-Za-z0-9_\-\.]',
        # Add more modern Discord token patterns (2025 format)
        r'^NT[A-Za-z0-9_\-\.]', r'^nt[A-Za-z0-9_\-\.]', r'^OD[A-Za-z0-9_\-\.]',
        r'^od[A-Za-z0-9_\-\.]', r'^MT[A-Za-z0-9_\-\.]', r'^md[A-Za-z0-9_\-\.]'
    ]
    
    pattern_matched = any(re.search(pattern, token) for pattern in token_patterns)
    
    # Safe logging that doesn't expose the full token
    prefix = token[:8] + "..." if token_length > 15 else "[too_short]"
    suffix = "..." + token[-5:] if token_length > 15 else ""
    
    logger.info(f"Token validation: length={token_length}, prefix={prefix}, suffix={suffix}, pattern_matched={pattern_matched}")
    
    # Additional structural validation - Discord tokens typically have dots as separators
    has_valid_structure = '.' in token
    
    # If the token is long enough and has alphanumeric characters, assume it's valid
    # This is a more permissive approach for ultra-reliability
    looks_like_token = re.match(r'^[A-Za-z0-9_\-\.]+$', token) is not None
    
    # More permissive validation - if it's long enough and looks like a token, accept it
    return (token_length >= 40 and looks_like_token) or pattern_matched or has_valid_structure

def token_from_env() -> str:
    """Get token from environment variables and files"""
    # Try getting token from environment variable
    token = os.environ.get('DISCORD_TOKEN')
    
    # If not found in environment, try loading from .env file directly
    if not token and os.path.exists('.env'):
        try:
            logger.info("Attempting to load token from .env file")
            with open('.env', 'r') as env_file:
                for line in env_file:
                    line = line.strip()
                    if line.startswith('DISCORD_TOKEN='):
                        # Extract token value, handling possible quotes
                        env_token = line[len('DISCORD_TOKEN='):]
                        # Remove any surrounding quotes
                        env_token = env_token.strip('"\'')
                        if env_token.startswith('${') and env_token.endswith('}'):
                            # This is a variable reference like ${DISCORD_TOKEN}, not an actual token
                            logger.warning("Found variable reference in .env, not an actual token")
                        else:
                            logger.info("Found token in .env file")
                            token = env_token
        except Exception as e:
            logger.warning(f"Error reading .env file: {e}")
    
    # If still not found, try from token cache
    if not token and os.path.exists('token_cache.json'):
        try:
            with open('token_cache.json', 'r') as f:
                cache_data = json.load(f)
                token = cache_data.get('token')
                if token:
                    logger.info("Found token in token_cache.json")
        except Exception as e:
            logger.warning(f"Error reading token cache: {e}")
    
    return token if token else ""

def test_token(token: str) -> Tuple[bool, Optional[str]]:
    """
    Test if a Discord token is valid by making a simple API request
    
    Args:
        token: The Discord token to test
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not token:
        return False, "Token is empty"
        
    # Clean the token first
    token = clean_token(token)
    
    # Discord API endpoint for getting the current application
    url = "https://discord.com/api/v10/applications/@me"
    
    # Set up headers with the token
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Make the request
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if the request was successful
        if response.status_code == 200:
            app_info = response.json()
            app_name = app_info.get('name', 'Unknown')
            logger.info(f"Token is valid for application: {app_name}")
            return True, None
        elif response.status_code == 401:
            logger.error("Token authentication failed (401 Unauthorized)")
            return False, "Authentication failed (401 Unauthorized)"
        else:
            error_msg = f"API request failed with status code {response.status_code}"
            logger.error(error_msg)
            return False, error_msg
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Request exception: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def get_token_from_env() -> str:
    """Get token from environment variables and files"""
    # Try getting token from environment variable
    token = os.environ.get('DISCORD_TOKEN')
    
    # If not found in environment, try loading from .env file directly
    if not token and os.path.exists('.env'):
        try:
            logger.info("Attempting to load token from .env file")
            with open('.env', 'r') as env_file:
                for line in env_file:
                    line = line.strip()
                    if line.startswith('DISCORD_TOKEN='):
                        # Extract token value, handling possible quotes
                        env_token = line[len('DISCORD_TOKEN='):]
                        # Remove any surrounding quotes
                        env_token = env_token.strip('"\'')
                        if env_token.startswith('${') and env_token.endswith('}'):
                            # This is a variable reference like ${DISCORD_TOKEN}, not an actual token
                            logger.warning("Found variable reference in .env, not an actual token")
                        else:
                            logger.info("Found token in .env file")
                            token = env_token
        except Exception as e:
            logger.warning(f"Error reading .env file: {e}")
    
    return token if token else ""

def find_valid_token() -> Optional[str]:
    """
    Try multiple sources to find a valid Discord token
    
    Returns:
        A valid token if found, otherwise None
    """
    # First try from environment variable directly
    env_token = os.environ.get('DISCORD_TOKEN')
    if env_token:
        is_valid, _ = test_token(env_token)
        if is_valid:
            return clean_token(env_token)
    
    # Try from .env file
    if os.path.exists('.env'):
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('DISCORD_TOKEN='):
                        token_value = line[len('DISCORD_TOKEN='):].strip().strip('"\'')
                        if not token_value.startswith('${'):  # Ignore variable references
                            is_valid, _ = test_token(token_value)
                            if is_valid:
                                return clean_token(token_value)
        except Exception as e:
            logger.error(f"Error reading .env file: {e}")
    
    # Try from token cache
    if os.path.exists('token_cache.json'):
        try:
            with open('token_cache.json', 'r') as f:
                cache_data = json.load(f)
                token = cache_data.get('token')
                if token:
                    is_valid, _ = test_token(token)
                    if is_valid:
                        return clean_token(token)
        except Exception as e:
            logger.error(f"Error reading token cache: {e}")
    
    # No valid token found
    return None

def fix_token_in_env():
    """
    Try to find a valid token and update the environment variable if needed
    """
    valid_token = find_valid_token()
    if valid_token:
        # Update the environment variable with the valid token
        os.environ['DISCORD_TOKEN'] = valid_token
        logger.info("Updated DISCORD_TOKEN environment variable with valid token")
        
        # Also update .env file
        try:
            env_lines = []
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
                    env_lines = f.readlines()
            
            token_line_updated = False
            for i, line in enumerate(env_lines):
                if line.startswith('DISCORD_TOKEN='):
                    env_lines[i] = f'DISCORD_TOKEN={valid_token}\n'
                    token_line_updated = True
                    break
            
            if not token_line_updated:
                env_lines.append(f'DISCORD_TOKEN={valid_token}\n')
            
            with open('.env', 'w') as f:
                f.writelines(env_lines)
                
            logger.info("Updated .env file with valid token")
        except Exception as e:
            logger.error(f"Error updating .env file: {e}")
        
        # Create a new token cache file
        try:
            from datetime import datetime
            with open('token_cache.json', 'w') as f:
                json.dump({
                    "token": valid_token,
                    "timestamp": datetime.now().isoformat(),
                    "validated": True,
                    "tested": True
                }, f)
            logger.info("Created new token cache with validated token")
        except Exception as e:
            logger.error(f"Error creating token cache: {e}")
        
        return True
    else:
        logger.critical("Could not find a valid token in any location")
        return False

if __name__ == "__main__":
    print("Discord Token Tester")
    print("--------------------")
    token = get_token_from_env()
    if not token:
        print("No token found. Checking all possible sources...")
        token = find_valid_token()
    
    if token:
        is_valid, error = test_token(token)
        if is_valid:
            print("✅ Token is VALID")
            fix_token_in_env()
        else:
            print(f"❌ Token is INVALID: {error}")
            print("Attempting to find a valid token from all sources...")
            if fix_token_in_env():
                print("✅ Found and fixed token in environment")
            else:
                print("❌ Could not find a valid token")
    else:
        print("❌ No token found")