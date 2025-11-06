"""
Heartbeat Manager for Discord Bot
---------------------------------
This module handles the heartbeat functionality to monitor the bot's health.
The watchdog script uses these heartbeats to determine if the bot is still running.
"""

import os
import time
import json
import logging
import threading
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Configuration
HEARTBEAT_FILE = "bot_heartbeat.json"
HEARTBEAT_INTERVAL = 30  # seconds

class HeartbeatManager:
    def __init__(self, bot_id: str = "main"):
        """
        Initialize the heartbeat manager.
        
        Args:
            bot_id: Identifier for this bot instance
        """
        self.bot_id = bot_id
        self.data: Dict[str, Any] = {
            "timestamp": time.time(),
            "bot_id": bot_id,
            "status": "starting",
            "uptime": 0,
            "start_time": time.time(),
            "message_count": 0,
            "command_count": 0,
            "error_count": 0
        }
        self.running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self.lock = threading.Lock()
        
        # Create an initial heartbeat file
        self._write_heartbeat()
        logger.info(f"Heartbeat manager initialized for bot ID: {bot_id}")
    
    def _write_heartbeat(self) -> None:
        """Write the heartbeat data to the heartbeat file"""
        try:
            with self.lock:
                # Update timestamp
                self.data["timestamp"] = time.time()
                self.data["uptime"] = time.time() - self.data["start_time"]
                
                # Create a copy of the data to avoid long file operations inside the lock
                data_copy = self.data.copy()
                
            # Write to file outside the lock to prevent blocking
            with open(HEARTBEAT_FILE, 'w') as f:
                json.dump(data_copy, f)
        except Exception as e:
            logger.error(f"Error writing heartbeat: {e}")
    
    def update_status(self, status: str) -> None:
        """
        Update the bot's status in the heartbeat data.
        
        Args:
            status: New status string (e.g., "running", "error", "restarting")
        """
        # Use a non-blocking approach to prevent Discord heartbeat issues
        try:
            with self.lock:
                self.data["status"] = status
            
            # Schedule the heartbeat write in a separate thread to avoid blocking
            threading.Thread(target=self._write_heartbeat, daemon=True).start()
        except Exception as e:
            logger.error(f"Error updating status: {e}")
    
    def increment_counter(self, counter_name: str) -> None:
        """
        Increment a counter in the heartbeat data.
        
        Args:
            counter_name: Name of the counter to increment
        """
        try:
            with self.lock:
                if counter_name in self.data:
                    self.data[counter_name] += 1
                else:
                    self.data[counter_name] = 1
                
            # Schedule a non-blocking heartbeat update
            threading.Thread(target=self._write_heartbeat, daemon=True).start()
        except Exception as e:
            logger.error(f"Error incrementing counter: {e}")
    
    def record_message(self) -> None:
        """Record a processed message in the heartbeat data"""
        self.increment_counter("message_count")
    
    def record_command(self) -> None:
        """Record a processed command in the heartbeat data"""
        self.increment_counter("command_count")
    
    def record_error(self) -> None:
        """Record an error in the heartbeat data"""
        self.increment_counter("error_count")
    
    def add_custom_data(self, key: str, value: Any) -> None:
        """
        Add custom data to the heartbeat.
        
        Args:
            key: Data key
            value: Data value
        """
        try:
            with self.lock:
                self.data[key] = value
                
            # Use a non-blocking write
            threading.Thread(target=self._write_heartbeat, daemon=True).start()
        except Exception as e:
            logger.error(f"Error adding custom data: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Asynchronous loop to update the heartbeat periodically"""
        try:
            while self.running:
                # Use a non-blocking write in a separate thread
                threading.Thread(target=self._write_heartbeat, daemon=True).start()
                await asyncio.sleep(HEARTBEAT_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Heartbeat task cancelled")
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")
    
    async def start(self) -> None:
        """Start the heartbeat manager"""
        if self.running:
            return
        
        self.running = True
        with self.lock:
            self.data["status"] = "running"
        
        # Use non-blocking write in a thread
        threading.Thread(target=self._write_heartbeat, daemon=True).start()
        
        # Start the heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat manager started")
    
    async def stop(self) -> None:
        """Stop the heartbeat manager"""
        if not self.running:
            return
        
        self.running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        
        with self.lock:
            self.data["status"] = "stopped"
        
        # Use non-blocking write in a thread for the final update
        threading.Thread(target=self._write_heartbeat, daemon=True).start()
        logger.info("Heartbeat manager stopped")

# Global instance for convenience
_global_instance: Optional[HeartbeatManager] = None

def get_heartbeat_manager(bot_id: str = "main") -> HeartbeatManager:
    """
    Get the global heartbeat manager instance.
    
    Args:
        bot_id: Identifier for this bot instance
        
    Returns:
        The global heartbeat manager instance
    """
    global _global_instance
    if _global_instance is None:
        _global_instance = HeartbeatManager(bot_id)
    return _global_instance