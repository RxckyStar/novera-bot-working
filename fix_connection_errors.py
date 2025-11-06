#!/usr/bin/env python3
"""
Fix ConnectionClosedError references in Python files
This script searches for and fixes references to discord.errors.ConnectionClosedError
by replacing them with the correct exception name or adding a proper error handler.
"""

import os
import re
import glob
import logging
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("error_fix.log")
    ]
)
logger = logging.getLogger("fix_connection_errors")

# Parse command line arguments
parser = argparse.ArgumentParser(description='Fix ConnectionClosedError references in Python files')
parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
parser.add_argument('-a', '--all-files', action='store_true', help='Check all Python files, including in subdirectories')
parser.add_argument('-f', '--fix', action='store_true', help='Fix the files (default is just to report)')
args = parser.parse_args()

def fix_connection_closed_error(content):
    """Fix references to ConnectionClosedError in file content"""
    
    # Check for common error pattern
    pattern1 = r"discord\.errors\.ConnectionClosed,\s*discord\.errors\.ConnectionClosedError"
    replacement1 = "discord.errors.ConnectionClosed"
    
    # Alternative pattern
    pattern2 = r"\(discord\.errors\.ConnectionClosed,\s*discord\.errors\.ConnectionClosedError\)"
    replacement2 = "(discord.errors.ConnectionClosed)"
    
    # Fix import pattern
    pattern3 = r"from\s+discord\.errors\s+import\s+ConnectionClosed,\s*ConnectionClosedError"
    replacement3 = "from discord.errors import ConnectionClosed"
    
    # Apply replacements
    fixed_content = re.sub(pattern1, replacement1, content)
    fixed_content = re.sub(pattern2, replacement2, fixed_content)
    fixed_content = re.sub(pattern3, replacement3, fixed_content)
    
    return fixed_content

def process_file(file_path):
    """Process a single file to fix ConnectionClosedError references"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Check if file contains the error reference
        if "ConnectionClosedError" in content:
            logger.info(f"Found ConnectionClosedError reference in {file_path}")
            
            # Fix the content
            fixed_content = fix_connection_closed_error(content)
            
            # Only write back if changes were made
            if fixed_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                logger.info(f"Fixed ConnectionClosedError in {file_path}")
                return True
            else:
                logger.info(f"No fixable ConnectionClosedError pattern in {file_path}")
        
        return False
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return False

def find_and_fix_python_files():
    """Find and fix ConnectionClosedError references in all Python files"""
    fixed_count = 0
    checked_count = 0
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")
    
    # Get list of Python files - search recursively if all-files flag is set
    if args.all_files:
        python_files = glob.glob("**/*.py", recursive=True)
        logger.info(f"Searching recursively for Python files, found {len(python_files)} files")
    else:
        python_files = glob.glob("*.py")
        logger.info(f"Searching current directory for Python files, found {len(python_files)} files")
    
    # Try to find the file where ConnectionClosedError is referenced
    for file_path in python_files:
        checked_count += 1
        
        if args.verbose:
            logger.debug(f"Checking file: {file_path}")
            
        # Skip special directories
        if "/.cache/" in file_path or "/__pycache__/" in file_path:
            if args.verbose:
                logger.debug(f"Skipping cache directory file: {file_path}")
            continue
            
        if "ConnectionClosedError" in open(file_path, 'r', encoding='utf-8', errors='replace').read():
            logger.info(f"Found reference in {file_path}")
            
            if args.fix:
                if process_file(file_path):
                    fixed_count += 1
            else:
                # Just report without fixing
                logger.info(f"Would fix ConnectionClosedError in {file_path} (use --fix to apply changes)")
    
    logger.info(f"Checked {checked_count} files, found and fixed {fixed_count} files with ConnectionClosedError references")
    return fixed_count

if __name__ == "__main__":
    logger.info("Starting ConnectionClosedError fix script")
    
    # If no arguments provided, default to fix mode for backward compatibility
    if len(sys.argv) == 1:
        args.fix = True
        
    find_and_fix_python_files()
    logger.info("ConnectionClosedError fix completed")