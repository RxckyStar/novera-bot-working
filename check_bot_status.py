#!/usr/bin/env python3
"""
Discord Bot Status Checker
--------------------------
This script checks the status of various components and helps diagnose issues.
"""

import os
import sys
import logging
import asyncio
import json
import requests
import psutil
import time
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 50)
    print(f" {title} ".center(50, "="))
    print("=" * 50)

def check_token():
    """Check if the Discord token is present and valid format."""
    print_section("Discord Token Check")
    
    # First check env directly
    token = os.environ.get('DISCORD_TOKEN')
    if token:
        print(f"✅ DISCORD_TOKEN found in environment, length: {len(token)}")
        token_prefix = token[:5] + "..." if len(token) > 10 else token
        token_suffix = "..." + token[-5:] if len(token) > 10 else token
        print(f"   Format: {token_prefix}...{token_suffix}")
        
        # Check format
        if token.startswith("MTM") and len(token) > 50:
            print("✅ Token appears to have correct format (starts with MT and length >50)")
        else:
            print("⚠️ Token may have unusual format, check if it's valid")
    else:
        print("❌ DISCORD_TOKEN not found in environment")
    
    # Check for .env file
    if os.path.exists('.env'):
        print("✅ .env file exists")
        try:
            with open('.env', 'r') as f:
                env_content = f.read()
            if 'DISCORD_TOKEN' in env_content:
                print("✅ DISCORD_TOKEN appears in .env file")
            else:
                print("❌ DISCORD_TOKEN not found in .env file")
        except Exception as e:
            print(f"❌ Error reading .env file: {e}")
    else:
        print("❌ .env file not found")
        
    # Check token_cache.json
    if os.path.exists('token_cache.json'):
        print("✅ token_cache.json exists")
        try:
            with open('token_cache.json', 'r') as f:
                cache = json.load(f)
            token = cache.get('token')
            if token:
                print(f"✅ Token found in cache, length: {len(token)}")
            else:
                print("❌ No token in cache file")
        except Exception as e:
            print(f"❌ Error reading token cache: {e}")
    else:
        print("❌ token_cache.json not found")

def check_event_loop():
    """Check the event loop status."""
    print_section("Event Loop Status")
    
    try:
        loop = asyncio.get_event_loop()
        print(f"✅ Successfully got event loop: {loop}")
        
        if loop.is_running():
            print("ℹ️ Event loop is currently running")
        else:
            print("ℹ️ Event loop is not running")
            
        if loop.is_closed():
            print("⚠️ Event loop is closed!")
        else:
            print("✅ Event loop is open")
    except RuntimeError as e:
        print(f"⚠️ Error getting event loop: {e}")
        print("ℹ️ This might be normal if called from a thread without a loop")

def check_http_endpoints():
    """Check if HTTP endpoints are responding."""
    print_section("Web Endpoints Check")
    
    # Check main website
    try:
        response = requests.get("http://localhost:5000", timeout=2)
        print(f"✅ Main website (port 5000) status: {response.status_code}")
    except Exception as e:
        print(f"❌ Main website (port 5000) not responding: {e}")
        
    # Check bot health endpoint
    try:
        response = requests.get("http://localhost:5001/healthz", timeout=2)
        print(f"✅ Bot health endpoint (port 5001) status: {response.status_code}")
        try:
            data = response.json()
            print(f"   Bot status: {data.get('status', 'unknown')}")
            print(f"   Connected: {data.get('bot_connected', False)}")
            print(f"   Guilds: {data.get('guilds_count', 0)}")
            print(f"   Uptime: {data.get('uptime', 0)} seconds")
            print(f"   Latency: {data.get('latency_ms', -1)}ms")
        except Exception as e:
            print(f"⚠️ Error parsing health data: {e}")
    except Exception as e:
        print(f"❌ Bot health endpoint (port 5001) not responding: {e}")

def check_processes():
    """Check running python processes."""
    print_section("Running Processes")
    
    bot_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'python' or proc.info['name'] == 'python3':
                cmdline = proc.info['cmdline']
                if cmdline and len(cmdline) > 1:
                    if 'bot.py' in cmdline[1] or 'start_fixed_bot.py' in cmdline[1]:
                        bot_processes.append(proc)
                        print(f"✅ Bot process found: PID {proc.pid}, Command: {' '.join(cmdline)}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if not bot_processes:
        print("❌ No bot processes found!")
    else:
        print(f"Total bot processes: {len(bot_processes)}")

def check_files():
    """Check key files status."""
    print_section("Critical Files Check")
    
    key_files = [
        ('bot.py', "Main bot file"),
        ('simple_discord_fix.py', "Simplified asyncio fix"),
        ('start_fixed_bot.py', "Fixed bot starter"),
        ('data_manager.py', "Data manager"),
        ('config.py', "Configuration"),
        ('.env', "Environment variables"),
        ('bot_heartbeat.json', "Heartbeat data"),
        ('SIMPLIFIED_BOT_GUIDE.md', "Guide to simplified fixes")
    ]
    
    for file_path, description in key_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path)
            mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
            print(f"✅ {file_path:<25} | {size:>8} bytes | {mtime_str} | {description}")
        else:
            print(f"❌ {file_path:<25} | {'MISSING':>8} | {'N/A':>19} | {description}")

def main():
    """Run all checks."""
    try:
        print("\n" + "#" * 80)
        print(" Discord Bot Diagnostic Tool ".center(80, "#"))
        print("#" * 80)
        
        # Run all checks
        check_token()
        check_event_loop()
        check_http_endpoints()
        check_processes()
        check_files()
        
        print("\n" + "#" * 80)
        print(" Diagnostic Complete ".center(80, "#"))
        print("#" * 80 + "\n")
    except Exception as e:
        print(f"Error during diagnostics: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()