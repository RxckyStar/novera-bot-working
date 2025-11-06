#!/usr/bin/env python3
import os
import sys
import time
import logging
import subprocess
import signal
import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_runner.log")
    ]
)
logger = logging.getLogger("bot_runner")

def run_bot_with_restarts():
    """Run the bot with automatic restarts if it crashes"""
    max_restarts = 10
    restart_count = 0
    restart_delay = 5  # seconds
    
    logger.info("Starting bot runner script")
    
    while restart_count < max_restarts:
        start_time = time.time()
        logger.info(f"Starting bot (attempt {restart_count + 1}/{max_restarts})")
        
        try:
            # Run the simple bot script as a subprocess
            process = subprocess.Popen([sys.executable, "simple_bot.py"], 
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            
            # Wait for the process to complete
            logger.info(f"Bot process started with PID {process.pid}")
            return_code = process.wait()
            
            # Check if the process exited normally or crashed
            if return_code == 0:
                logger.info("Bot exited normally")
                break
            else:
                run_time = time.time() - start_time
                logger.error(f"Bot crashed with return code {return_code} after running for {run_time:.2f} seconds")
                
                # If the bot ran for more than 1 hour, reset the restart count
                if run_time > 3600:
                    logger.info("Bot ran for over an hour before crashing, resetting restart counter")
                    restart_count = 0
                else:
                    restart_count += 1
                
                # Wait before restarting
                logger.info(f"Waiting {restart_delay} seconds before restarting")
                time.sleep(restart_delay)
                restart_delay = min(restart_delay * 2, 300)  # Exponential backoff with max 5 minutes
        
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
            if 'process' in locals() and process:
                logger.info(f"Terminating bot process with PID {process.pid}")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    logger.warning("Failed to terminate process gracefully, forcing kill")
                    try:
                        process.kill()
                    except:
                        pass
            break
        except Exception as e:
            logger.error(f"Error in runner script: {e}")
            restart_count += 1
            time.sleep(restart_delay)
    
    if restart_count >= max_restarts:
        logger.critical(f"Reached maximum restart attempts ({max_restarts}), giving up")
    
    logger.info("Bot runner script exiting")

if __name__ == "__main__":
    run_bot_with_restarts()