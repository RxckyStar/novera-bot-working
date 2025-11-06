#!/usr/bin/env python3
"""
Bot Patch Utility
----------------
This script patches the main bot.py file with the heartbeat mechanism
to ensure it can be properly monitored by ultimate_bot_runner.py.
"""

import sys
import os
import re
import logging
import shutil
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_patch.log')
    ]
)
logger = logging.getLogger("BOT_PATCH")

def backup_file(file_path):
    """Create a backup of the file"""
    try:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.{int(time.time())}.bak"
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
    return None

def insert_heartbeat_import(content):
    """Insert heartbeat manager import at the top of the file"""
    try:
        # Check if the import is already there
        if "import heartbeat_manager" in content:
            logger.info("Heartbeat import already exists")
            return content
            
        # Find a good place to insert the import
        import_pattern = re.compile(r'^import\s+.*$', re.MULTILINE)
        
        # Find the last import statement
        matches = list(import_pattern.finditer(content))
        if matches:
            last_import = matches[-1]
            last_import_end = last_import.end()
            
            # Insert after the last import
            new_content = (
                content[:last_import_end] + 
                "\nimport heartbeat_manager  # For ultra-reliability monitoring" +
                content[last_import_end:]
            )
            logger.info("Inserted heartbeat import")
            return new_content
        else:
            # If no imports found, add after the first few lines
            lines = content.split('\n')
            if len(lines) > 5:
                # Insert after line 5
                lines.insert(5, "import heartbeat_manager  # For ultra-reliability monitoring")
                logger.info("Inserted heartbeat import at line 5")
                return '\n'.join(lines)
            else:
                # Just append
                logger.info("Appended heartbeat import")
                return content + "\nimport heartbeat_manager  # For ultra-reliability monitoring"
    except Exception as e:
        logger.error(f"Error inserting heartbeat import: {e}")
        return content

def insert_heartbeat_start(content):
    """Insert heartbeat start code in the on_ready function"""
    try:
        # Check if we already have the heartbeat start code
        if "heartbeat_manager.start_heartbeat" in content:
            logger.info("Heartbeat start code already exists")
            return content
            
        # Find the on_ready function
        on_ready_pattern = re.compile(r'async\s+def\s+on_ready\s*\(\s*\)\s*:(?:\s*\"\"\".*?\"\"\"\s*)?', re.DOTALL)
        match = on_ready_pattern.search(content)
        
        if match:
            # Find the end of the on_ready function definition
            func_start = match.end()
            
            # Insert the heartbeat start code after the function definition
            indent = '\n    '  # Adjust indentation as needed
            heartbeat_code = f"{indent}# Start heartbeat monitoring for ultra reliability{indent}heartbeat_manager.start_heartbeat_async()"
            
            new_content = content[:func_start] + heartbeat_code + content[func_start:]
            logger.info("Inserted heartbeat start code in on_ready function")
            return new_content
        else:
            logger.warning("Could not find on_ready function")
            return content
    except Exception as e:
        logger.error(f"Error inserting heartbeat start code: {e}")
        return content

def patch_bot_file(file_path="bot.py"):
    """Apply all patches to the bot file"""
    try:
        # Backup the file first
        backup_path = backup_file(file_path)
        if not backup_path:
            logger.error("Failed to create backup, aborting")
            return False
            
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Apply patches
        content = insert_heartbeat_import(content)
        content = insert_heartbeat_start(content)
        
        # Write back the modified content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info(f"Successfully patched {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error patching bot file: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting bot.py patcher")
    
    if len(sys.argv) > 1:
        file_to_patch = sys.argv[1]
    else:
        file_to_patch = "bot.py"
        
    success = patch_bot_file(file_to_patch)
    if success:
        print(f"Successfully patched {file_to_patch}")
        sys.exit(0)
    else:
        print(f"Failed to patch {file_to_patch}")
        sys.exit(1)