#!/usr/bin/env python3
"""
This utility script updates bot.py to use the new, comprehensive discord_asyncio_fix
instead of multiple competing and conflicting fixes.

It makes a backup of the original file before modifying it.
"""

import os
import re
import sys
import time
import logging
from typing import Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("apply_discord_fix.log")
    ]
)

BOT_FILE = 'bot.py'

def backup_file(file_path: str) -> Tuple[bool, str]:
    """Create a backup of the original file"""
    backup_path = f"{file_path}.{int(time.time())}.bak"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as src_file:
            content = src_file.read()
            
        with open(backup_path, 'w', encoding='utf-8') as backup_file:
            backup_file.write(content)
            
        logging.info(f"Created backup of {file_path} at {backup_path}")
        return True, content
    except Exception as e:
        logging.error(f"Failed to create backup: {e}")
        return False, ""

def update_imports(content: str) -> str:
    """Replace the multiple fix imports with our single comprehensive fix"""
    
    # Patterns to match and remove various asyncio fix imports
    fix_patterns = [
        r'import\s+aiohttp_timeout_fix',
        r'import\s+asyncio_runner',
        r'import\s+discord_aiohttp_fix',
        r'from\s+discord_aiohttp_fix\s+import.*?\n',
        r'import\s+fix_timeout_errors',
        r'from\s+fix_timeout_errors\s+import.*?\n',
        r'import\s+timeout_fix',
        r'from\s+timeout_fix\s+import.*?\n',
        r'import\s+simple_discord_fix',
        r'from\s+simple_discord_fix\s+import.*?\n',
    ]
    
    # Remove all the old imports
    for pattern in fix_patterns:
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
        
    # Check if our fix is already imported
    if 'import discord_asyncio_fix' in content or 'from discord_asyncio_fix import' in content:
        logging.info("discord_asyncio_fix already imported, leaving as-is")
    else:
        # Add our comprehensive fix at the top of the file
        header_comment = "# Apply comprehensive Discord.py asyncio fixes to prevent various errors\n"
        fix_import = "import discord_asyncio_fix\nfrom discord_asyncio_fix import safe_wait_for, with_timeout\ndiscord_asyncio_fix.apply_all_fixes()\n\n"
        
        # Insert after any module docstring and shebang
        if re.match(r'^#!/usr/bin/env python', content):
            # Has shebang, add after it and any docstring
            if '"""' in content[:500] or "'''" in content[:500]:
                # Has docstring, add after it
                content = re.sub(r'("""|\'\'\'.*?"""|\'\'\')', r'\1\n\n' + header_comment + fix_import, content, count=1, flags=re.DOTALL)
            else:
                # No docstring, add after shebang
                content = re.sub(r'^(#!/usr/bin/env python.*?\n)', r'\1\n' + header_comment + fix_import, content, count=1)
        elif '"""' in content[:500] or "'''" in content[:500]:
            # Has docstring but no shebang, add after docstring
            content = re.sub(r'("""|\'\'\'.*?"""|\'\'\')', r'\1\n\n' + header_comment + fix_import, content, count=1, flags=re.DOTALL)
        else:
            # No shebang or docstring, add at the beginning
            content = header_comment + fix_import + content
            
        logging.info("Added discord_asyncio_fix import to the top of the file")
    
    return content

def update_main_block(content: str) -> str:
    """Update the __main__ block to use our fixed startup approach"""
    
    # Look for the __main__ block
    main_block = re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"].*?:', content)
    if not main_block:
        logging.warning("Could not find __main__ block, leaving as-is")
        return content
        
    # Replace the contents of the main block with our safe startup
    new_main_content = """if __name__ == "__main__":
    try:
        # Get token from environment
        if not TOKEN:
            logger.critical("No Discord token found!")
            sys.exit(1)
            
        # Clean up token if needed
        clean_token = TOKEN.strip().strip('"').strip("'")
        
        # Run the bot using our safe approach (avoids asyncio.run)
        discord_asyncio_fix.run_bot(bot, clean_token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by keyboard interrupt")
    except Exception as e:
        logger.critical(f"Error starting bot: {e}")
        import traceback
        logger.critical(traceback.format_exc())
"""

    # Replace the entire main block with our version
    content = re.sub(r'if\s+__name__\s*==\s*[\'"]__main__[\'"].*?:(.*?)(?=\n\S|\Z)', 
                    lambda m: new_main_content, 
                    content, 
                    flags=re.DOTALL)
    
    logging.info("Updated __main__ block with safe startup approach")
    return content

def update_bot_file() -> bool:
    """Update the bot.py file with our fixes"""
    success, content = backup_file(BOT_FILE)
    if not success:
        logging.error("Failed to create backup, aborting")
        return False
        
    try:
        # Update imports and main block
        content = update_imports(content)
        content = update_main_block(content)
        
        # Write the updated content back to the file
        with open(BOT_FILE, 'w', encoding='utf-8') as file:
            file.write(content)
            
        logging.info(f"Successfully updated {BOT_FILE}")
        return True
    except Exception as e:
        logging.error(f"Error updating bot file: {e}")
        return False

def main():
    """Apply the fixed Discord asyncio solution"""
    print("Applying comprehensive Discord.py asyncio fix to bot.py...")
    
    if update_bot_file():
        print("✓ Successfully updated bot.py to use the comprehensive discord_asyncio_fix")
        print("✓ This will prevent various asyncio-related errors")
        return 0
    else:
        print("✗ Failed to update bot.py")
        print("See apply_discord_fix.log for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())