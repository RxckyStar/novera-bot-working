#!/usr/bin/env python3
"""
Update Profanity Filter Script
------------------------------
This script updates the profanity filter in the bot.py file to ensure it properly
blocks problematic terms like "nga" and "shi"
"""
import os
import re
import sys
import shutil
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("filter_update.log")
    ]
)
logger = logging.getLogger(__name__)

# Complete list of problematic terms that must be blocked
BANNED_WORDS = [
    # Must block these with highest priority
    "fuck", "fck", "f*ck", "fuk", "fuking", "fukking", "fking", "fkn", 
    "shit", "shi", "sh*t", "sh1t", "sh!t", "dammmn", "wtf", "stfu", "gtfo", "lmfao", "fml", "lmao",
    "bitch", "btch", "b*tch", "asshole", "dumbass",
    "sybau", "sybau2", "sy bau", "s y b a u", "omfg", "dafuq", "mtf",
    # Racial slurs (CRITICAL - must block)
    "nigger", "nigga", "niga", "nga", "n1gga", "n1gg3r", "n1ga", "negro", "chink", "spic", "kike"
]

def backup_file(file_path):
    """Create a backup of the original file"""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.{timestamp}.bak"
    
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False

def update_banned_words_list(file_path):
    """Update the banned words list in the given file"""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Look for banned words list pattern
        banned_words_pattern = r'BANNED_WORDS\s*=\s*\[([^\]]*)\]'
        match = re.search(banned_words_pattern, content, re.DOTALL)
        
        if match:
            # Found banned words list
            original_list = match.group(0)
            
            # Format new banned words list
            new_list = "BANNED_WORDS = [\n    # Must block these with highest priority\n"
            new_list += "    \"" + "\", \"".join(BANNED_WORDS) + "\"\n]"
            
            # Replace the list in the content
            updated_content = content.replace(original_list, new_list)
            
            # Write updated content back to file
            with open(file_path, 'w') as f:
                f.write(updated_content)
                
            logger.info(f"Updated banned words list in {file_path}")
            return True
        else:
            logger.error(f"Could not find banned words list in {file_path}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating banned words list: {e}")
        return False

def main():
    """Main function to update profanity filter in bot.py"""
    bot_file = "bot.py"
    
    logger.info("Starting profanity filter update")
    
    # Create backup
    if not backup_file(bot_file):
        logger.error("Failed to create backup, aborting")
        return 1
    
    # Update banned words list
    if not update_banned_words_list(bot_file):
        logger.error("Failed to update banned words list")
        return 1
    
    logger.info("Profanity filter update completed successfully")
    logger.info(f"Added {len(BANNED_WORDS)} banned words including 'nga' and 'shi'")
    return 0

if __name__ == "__main__":
    sys.exit(main())