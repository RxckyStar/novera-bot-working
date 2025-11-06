
import os
import sys
import time
import subprocess
import logging
import requests
import psutil
import asyncio
import atexit
import signal

# Import our instance manager
from instance_manager import (
    claim_instance, release_instance, kill_other_instances, write_pid_file,
    WATCHDOG_PID_FILE, BOT_PID_FILE, WEB_PID_FILE
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("watchdog.log")
    ]
)
logger = logging.getLogger("watchdog")

CHECK_INTERVAL = 15  # Check more frequently
HEALTH_CHECK_URL = "http://0.0.0.0:5000/healthz"
HEALTH_CHECK_TIMEOUT = 10  # Longer timeout to prevent false positives
MAX_CONSECUTIVE_FAILS = 2  # Restart sooner on failures
BACKOFF_TIME = 5  # Time to wait between restarts

# Create a function to release instance on exit
def cleanup():
    """Clean up resources and release instance on exit"""
    logger.info("Watchdog shutting down, cleaning up resources")
    release_instance(WATCHDOG_PID_FILE)

# Register cleanup function to run on exit
atexit.register(cleanup)

# Register signal handlers
def signal_handler(sig, frame):
    """Handle termination signals gracefully"""
    logger.info(f"Received signal {sig}, shutting down...")
    cleanup()
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def kill_process_by_name(name, force=False):
    """Kill processes whose cmdline contains the given name.
    
    Args:
        name: Name or pattern to match in command line
        force: If True, use SIGKILL immediately instead of trying SIGTERM first
    """
    return kill_other_instances(name, force)

def is_bot_running():
    """Check if the bot is responsive via its health endpoint."""
    try:
        response = requests.get(HEALTH_CHECK_URL, timeout=HEALTH_CHECK_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', '')
            bot_connected = data.get('bot_connected', False)
            return status in ['healthy', 'warning'] and bot_connected
        return False
    except requests.RequestException:
        return False

def start_web_server():
    """Start the web server using gunicorn."""
    try:
        cmd = ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"]
        logger.info(f"Starting web server: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy())
        time.sleep(5)
        return process if process.poll() is None else None
    except Exception as e:
        logger.error(f"Error starting web server: {e}")
        return None

async def start_discord_bot():
    """Start the Discord bot with proper async handling."""
    try:
        # Import the bot instance without running it
        from bot import bot, TOKEN
        
        logger.info("Starting Discord bot with async handling")
        async with bot:
            await bot.start(TOKEN)
    except Exception as e:
        logger.critical(f"Bot startup failed: {e}")
        raise

def run_bot():
    """Run the bot in the event loop."""
    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Create task and run bot properly
        task = loop.create_task(start_discord_bot())
        loop.run_forever()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

def check_existing_bot_instances():
    """Check if a bot instance is already running via bot.pid file."""
    try:
        if os.path.exists(BOT_PID_FILE):
            with open(BOT_PID_FILE, 'r') as f:
                try:
                    pid = int(f.read().strip())
                    if psutil.pid_exists(pid):
                        # Check if it's actually a bot process
                        process = psutil.Process(pid)
                        if "bot.py" in " ".join(process.cmdline()):
                            logger.info(f"Bot already running with PID: {pid}")
                            return True
                except (ValueError, psutil.NoSuchProcess):
                    # Invalid PID or process doesn't exist
                    pass
        return False
    except Exception as e:
        logger.error(f"Error checking for existing bot instances: {e}")
        return False

def main():
    # Check if watchdog is already running using instance manager
    if not claim_instance(WATCHDOG_PID_FILE, "keep_running.py"):
        logger.error("Bot watchdog already running! Exiting to prevent duplicates.")
        sys.exit(1)
    
    # Check if a bot instance is already running
    if check_existing_bot_instances():
        logger.info("Bot already running! Watchdog will monitor but not start a new instance.")
        # We'll skip starting a new bot instance but continue monitoring
    else:
        # Successfully claimed the instance
        logger.info("Bot watchdog started with improved instance management")
        
        # Kill existing processes to ensure clean state
        kill_process_by_name("gunicorn")
        kill_process_by_name("bot.py")
    
    # Ensure we release our instance on abnormal exit
    try:
        # Start the web server process
        web_server_process = start_web_server()
        
        # Write web server PID if available
        if web_server_process and web_server_process.pid:
            write_pid_file(WEB_PID_FILE, web_server_process.pid)
        
        time.sleep(2)
        
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Main monitoring loop
        while True:
            # First check if a bot instance is already running
            if check_existing_bot_instances():
                logger.info("Detected running bot instance, monitoring only...")
                # Just monitor, don't try to start a new one
                time.sleep(CHECK_INTERVAL)
                continue
                
            try:
                # Run the bot in the event loop only if no instance is already running
                loop.run_until_complete(start_discord_bot())
            except Exception as e:
                logger.error(f"Bot crashed: {e}")
                time.sleep(BACKOFF_TIME)  # Wait before retrying
            
            # Check if the bot is still running
            if not is_bot_running() and not check_existing_bot_instances():
                logger.warning("Bot is not running, restarting...")
                kill_process_by_name("bot.py")
                time.sleep(3)
    except Exception as e:
        logger.critical(f"Watchdog crash: {e}")
        # Clean up
        release_instance(WATCHDOG_PID_FILE)
        sys.exit(1)

if __name__ == "__main__":
    main()
