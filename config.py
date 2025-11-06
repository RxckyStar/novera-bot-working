import os
import json
import logging
import re
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token Cache
TOKEN_CACHE_FILE = "token_cache.json"

def save_token_cache(token: str) -> None:
    """Save a valid token to cache."""
    try:
        cache_data = {
            "token": token,
            "timestamp": datetime.now().isoformat()
        }
        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
        logger.info("Token cached successfully.")
    except Exception as e:
        logger.warning(f"Failed to cache token: {e}")

def load_token_from_cache() -> str:
    """Load a previously cached token, if it's less than 12 hours old."""
    try:
        if os.path.exists(TOKEN_CACHE_FILE):
            with open(TOKEN_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                token = cache_data.get("token")
                timestamp = cache_data.get("timestamp")

                # Check if the token is still fresh
                if token and timestamp:
                    age_hours = (datetime.now() - datetime.fromisoformat(timestamp)).total_seconds() / 3600
                    if age_hours < 12:
                        logger.info(f"Using cached token (age: {age_hours:.1f} hours).")
                        return token
                    else:
                        logger.info("Cached token is too old.")
    except Exception as e:
        logger.warning(f"Failed to load cached token: {e}")
    return ""

def refresh_token() -> bool:
    """Force refresh of Discord token from all available sources."""
    try:
        # Clear token cache
        if os.path.exists(TOKEN_CACHE_FILE):
            os.remove(TOKEN_CACHE_FILE)
            logger.info("Token cache cleared for refresh")
            
        # Force reload from environment
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            # Try loading from .env
            try:
                from dotenv import load_dotenv
                load_dotenv(force=True)
                token = os.getenv("DISCORD_TOKEN")
                logger.info("Reloaded token from .env file")
            except ImportError:
                pass
                
        if token and validate_token(clean_token(token)):
            save_token_cache(token)
            logger.info("Token successfully refreshed and cached")
            return True
            
        logger.error("Failed to refresh token from any source")
        return False
    except Exception as e:
        logger.error(f"Error during token refresh: {e}")
        return False

def get_token() -> str:
    """Retrieve the Discord token with enhanced validation and multiple fallbacks."""
    
    # Try multiple sources in order of preference
    token_sources = [
        # 1. Direct environment variable (primary source)
        ("environment", os.getenv("DISCORD_TOKEN")),
        
        # 2. Token cache file
        ("cache", load_token_from_cache()),
        
        # 3. Legacy .env file (if python-dotenv is available)
        ("dotenv", None),
        
        # 4. Raw token file
        ("token_file", None)
    ]

    # Enhanced validation criteria
    def is_valid_token(token: str) -> bool:
        if not token or not isinstance(token, str):
            return False
        
        # Remove any whitespace and quotes
        cleaned = token.strip().strip('"\'')
        
        # Basic length validation (Discord tokens are typically ~70 chars)
        if len(cleaned) < 59:
            logger.warning(f"Token length ({len(cleaned)}) is shorter than expected minimum (59)")
            return False
            
        # Check for common format issues
        if not cleaned.isalnum() and not any(c in cleaned for c in '._-'):
            logger.warning("Token contains unexpected characters")
            return False
            
        return True
    
    # Try to load from .env if dotenv is available
    try:
        try:
            # First try with python-dotenv package
            from dotenv import load_dotenv
            load_dotenv()
            token_sources[2] = ("dotenv", os.getenv("DISCORD_TOKEN"))
            logger.info("Successfully loaded environment from .env using python-dotenv")
        except ImportError:
            # Fallback to manual .env loading
            if os.path.exists(".env"):
                logger.info("Python-dotenv not available, using manual .env parsing")
                with open(".env", "r") as env_file:
                    for line in env_file:
                        if line.strip() and not line.startswith("#"):
                            key, value = line.strip().split("=", 1)
                            if key.strip() == "DISCORD_TOKEN":
                                token_sources[2] = ("dotenv_manual", value.strip())
                                os.environ["DISCORD_TOKEN"] = value.strip()
                                break
    except Exception as e:
        logger.warning(f"Error loading from .env file: {e}")
        pass
    
    # Try to load from token file
    try:
        if os.path.exists("token.txt"):
            with open("token.txt", "r") as f:
                token_sources[3] = ("token_file", f.read().strip())
    except Exception:
        pass
    
    # Try each source until we find a valid token
    working_token = None
    source_used = None
    
    for source_name, token in token_sources:
        if token:
            cleaned_token = clean_token(token)
            if validate_token(cleaned_token):
                working_token = cleaned_token
                source_used = source_name
                logger.info(f"Valid token found from {source_name}")
                break
            else:
                logger.warning(f"Invalid token format from {source_name}")
    
    if not working_token:
        # Emergency fallback: try to extract token from any source, even if it doesn't match the pattern
        for source_name, token in token_sources:
            if token and len(token) > 40:
                cleaned_token = clean_token(token)
                if len(cleaned_token) > 40:
                    logger.warning(f"Using emergency token from {source_name} that doesn't match pattern but has sufficient length")
                    working_token = cleaned_token
                    source_used = f"{source_name}_emergency"
                    break
    
    if not working_token:
        raise ValueError("No valid Discord token found from any source!")
    
    # Always save a working token to cache for future use
    save_token_cache(working_token)
    logger.info(f"Using Discord token from {source_used} (length: {len(working_token)})")
    
    return working_token

def clean_token(token: str) -> str:
    """Clean a token to remove unwanted characters."""
    if not token:
        return ""
    
    # First remove common problematic characters
    cleaned = token.strip().replace('"', '').replace("'", '')
    
    # Handle possible escape sequences
    if '\\' in cleaned:
        try:
            cleaned = cleaned.encode().decode('unicode_escape')
        except Exception:
            pass  # If decode fails, keep as is
    
    # Extract the token if it's part of a larger string (common when copy-pasted)
    token_match = re.search(r'[A-Za-z0-9_\-\.]{40,100}', cleaned)
    if token_match:
        extracted = token_match.group(0)
        if extracted != cleaned and len(extracted) >= 60:  # Only use if it looks like a full token
            cleaned = extracted
            
    # Ensure all characters are printable
    cleaned = ''.join(c for c in cleaned if c.isprintable())
    
    # Log token characteristics (not the token itself)
    if cleaned:
        prefix = cleaned[:6] + "..." if len(cleaned) > 10 else ""
        suffix = "..." + cleaned[-4:] if len(cleaned) > 10 else ""
        is_valid = validate_token(cleaned)
        logger.info(f"Token length: {len(cleaned)}, prefix: {prefix}, suffix: {suffix}, valid format: {is_valid}")
    
    return cleaned

def validate_token(token: str) -> bool:
    """Validate that a token has the correct format and length."""
    if not token or len(token) < 59:  # Discord tokens are typically ~70 chars
        return False

    # More flexible pattern that still catches Discord token format
    # Discord tokens are Base64 encoded strings with some special chars
    pattern = re.compile(r'^[A-Za-z0-9_\-\.]{59,100}$')
    return bool(pattern.match(token))

# Bot configuration
try:
    TOKEN = get_token()
except ValueError as e:
    logger.critical(f"Failed to get Discord token: {e}")
    TOKEN = None

# Activity tracking configuration
INACTIVITY_THRESHOLD_DAYS = 30
VALUE_REDUCTION_AMOUNT = 10
MINIMUM_VALUE = 0
DATA_FILE = "member_data.json"
MESSAGE_WEIGHT = 1
REACTION_WEIGHT = 2
COMMAND_PREFIX = "!"