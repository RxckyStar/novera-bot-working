#!/usr/bin/env python3
"""
Profanity Filter for Novera Assistant
------------------------------------
Handles detection and removal of inappropriate content in the Discord server.
"""
import logging
import discord
import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Optional, Any, Union

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProfanityFilter:
    """Advanced profanity filter with racial slur detection and warning system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.warning_counts = {}  # {user_id: count}
        self.last_warnings = {}   # {user_id: timestamp}
        
        # Configure banned word lists with different severity levels
        # Basic banned words that trigger a warning
        self.banned_words = [
            "fuck", "fck", "f*ck", "fuk", "fuking", "fukking", "fking", "fkn", 
            "shit", "shi", "sh*t", "sh1t", "sh!t", "dammmn", "wtf", "stfu", "gtfo", 
            "bitch", "btch", "b*tch", "asshole", "dumbass",
            "sybau", "sybau2", "sy bau", "s y b a u", "omfg", "dafuq"
        ]
        
        # More dangerous terms that trigger stronger responses
        self.dangerous_terms = [
            "kys", "kill yourself", "suicide", "die", "neck yourself", "nga", "niga"
        ]
        
        # Ultra-banned words that trigger immediate timeout (racial slurs, etc.)
        self.ultra_banned_words = [
            "nigger", "nigga", "niga", "nga", "n1gga", "n1gg3r", "n1ga", 
            "negro", "chink", "spic", "kike"
        ]
        
        # Timeout durations based on warning count
        self.timeout_durations = {
            1: 300,      # 5 minutes
            2: 3600,     # 1 hour
            3: 86400,    # 1 day
            4: 604800,   # 1 week
            5: 2419200   # 28 days (maximum Discord allows)
        }
        
        logger.info(f"Initialized profanity filter with {len(self.banned_words)} banned words, " +
                   f"{len(self.dangerous_terms)} dangerous terms, and " +
                   f"{len(self.ultra_banned_words)} ultra-banned words")
    
    def check_message(self, message: discord.Message) -> Tuple[bool, str]:
        """Check if a message contains profanity
        
        Returns:
            (bool, str): (is_banned, matched_term)
        """
        if not message.content:
            return False, ""
            
        content = message.content.lower()
        
        # Check for ultra-banned words first (highest priority)
        for word in self.ultra_banned_words:
            if word in content:
                return True, word
        
        # Check for dangerous terms
        for term in self.dangerous_terms:
            if term in content:
                return True, term
                
        # Check for regular banned words
        for word in self.banned_words:
            if word in content:
                return True, word
        
        return False, ""
    
    async def handle_profanity(self, message: discord.Message, matched_term: str) -> None:
        """Handle a message containing profanity"""
        try:
            # Delete the message
            await message.delete()
            logger.info(f"Deleted message with banned term '{matched_term}' from {message.author.name}")
            
            # Get current warning count
            user_id = str(message.author.id)
            warning_count = self.get_warning_count(user_id)
            
            # Determine timeout duration based on warning count and matched term severity
            timeout_duration = self.get_timeout_duration(warning_count, matched_term)
            
            # Issue warning in channel
            warning_msg = await self.send_warning(message.channel, message.author, matched_term, warning_count, timeout_duration)
            
            # Apply timeout if needed
            if timeout_duration > 0:
                await self.timeout_user(message.guild, message.author, timeout_duration, matched_term, warning_count)
            
            # Update warning count
            self.add_warning(user_id)
            
            # Delete warning message after 30 seconds
            if warning_msg:
                await asyncio.sleep(30)
                try:
                    await warning_msg.delete()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error handling profanity: {e}")
    
    def get_warning_count(self, user_id: str) -> int:
        """Get the current warning count for a user"""
        return self.warning_counts.get(user_id, 0)
    
    def add_warning(self, user_id: str) -> None:
        """Add a warning to a user's count"""
        self.warning_counts[user_id] = self.get_warning_count(user_id) + 1
        self.last_warnings[user_id] = time.time()
        
    def reset_warnings(self, user_id: str) -> None:
        """Reset warnings for a user"""
        if user_id in self.warning_counts:
            del self.warning_counts[user_id]
        if user_id in self.last_warnings:
            del self.last_warnings[user_id]
            
    def get_timeout_duration(self, warning_count: int, matched_term: str) -> int:
        """Get timeout duration in seconds based on warning count and term severity"""
        # Ultra-banned words trigger immediate stronger timeout
        if matched_term in self.ultra_banned_words:
            # Racial slurs get at least a day timeout
            warning_count = max(warning_count, 3)
        
        # Dangerous terms trigger stronger timeout
        elif matched_term in self.dangerous_terms:
            # Upgrade warning count by 1 for dangerous terms
            warning_count = max(warning_count, 2)
            
        # For first warning, just delete the message
        if warning_count == 0:
            return 0
            
        # Cap at maximum timeout duration
        warning_count = min(warning_count, 5)
        
        return self.timeout_durations.get(warning_count, 0)
    
    async def send_warning(self, channel, user, matched_term, warning_count, timeout_duration):
        """Send a warning message to the channel"""
        try:
            embed = discord.Embed(
                title="🚫 Inappropriate Language Detected",
                description=f"{user.mention} your message has been removed.",
                color=discord.Color.red()
            )
            
            reason = "Using inappropriate language"
            if matched_term in self.ultra_banned_words:
                reason = "Using racial slurs or extremely inappropriate language"
            elif matched_term in self.dangerous_terms:
                reason = "Using harmful or dangerous language"
                
            embed.add_field(name="Reason", value=reason, inline=False)
            
            if timeout_duration > 0:
                # Convert seconds to readable format
                if timeout_duration < 60:
                    duration_text = f"{timeout_duration} seconds"
                elif timeout_duration < 3600:
                    duration_text = f"{timeout_duration // 60} minutes"
                elif timeout_duration < 86400:
                    duration_text = f"{timeout_duration // 3600} hours"
                else:
                    duration_text = f"{timeout_duration // 86400} days"
                
                embed.add_field(
                    name="Action Taken", 
                    value=f"Timeout for {duration_text}", 
                    inline=False
                )
                
                embed.add_field(
                    name="Warning Count", 
                    value=f"{warning_count}/{len(self.timeout_durations)}", 
                    inline=False
                )
            else:
                embed.add_field(
                    name="Action Taken", 
                    value="Message deleted", 
                    inline=False
                )
                
            embed.set_footer(text="This server maintains a respectful environment. Please keep conversations appropriate.")
            
            return await channel.send(embed=embed, delete_after=30)
        except Exception as e:
            logger.error(f"Error sending warning: {e}")
            return None
    
    async def timeout_user(self, guild, user, duration, matched_term, warning_count):
        """Apply a timeout to a user"""
        try:
            reason = "Using inappropriate language"
            if matched_term in self.ultra_banned_words:
                reason = f"Using racial slurs (term: '{matched_term}') - Warning #{warning_count}"
            elif matched_term in self.dangerous_terms:
                reason = f"Using harmful language (term: '{matched_term}') - Warning #{warning_count}"
            else:
                reason = f"Using inappropriate language (term: '{matched_term}') - Warning #{warning_count}"
                
            # Calculate end time
            until = discord.utils.utcnow() + timedelta(seconds=duration)
            
            # Apply timeout
            await user.timeout(until, reason=reason)
            
            logger.info(f"Timed out user {user.name} for {duration} seconds due to term '{matched_term}'")
            
            # Notify server owner or admins about timeouts for serious offenses
            if matched_term in self.ultra_banned_words:
                await self.notify_admins(guild, user, matched_term, duration, warning_count)
                
        except Exception as e:
            logger.error(f"Error applying timeout: {e}")
    
    async def notify_admins(self, guild, user, matched_term, duration, warning_count):
        """Notify admins about serious offenses"""
        try:
            # Try to find a mod-log channel or default to sending to owner
            log_channel = None
            for channel in guild.text_channels:
                if channel.name.lower() in ["mod-log", "modlog", "admin-log", "adminlog", "server-log", "serverlog"]:
                    log_channel = channel
                    break
            
            embed = discord.Embed(
                title="⚠️ Serious Moderation Action Taken",
                description=f"User: {user.mention} ({user.name})\nID: {user.id}",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Reason", value=f"Using racial slur: '{matched_term}'", inline=False)
            
            # Convert seconds to readable format
            if duration < 60:
                duration_text = f"{duration} seconds"
            elif duration < 3600:
                duration_text = f"{duration // 60} minutes"
            elif duration < 86400:
                duration_text = f"{duration // 3600} hours"
            else:
                duration_text = f"{duration // 86400} days"
                
            embed.add_field(name="Action Taken", value=f"Timeout for {duration_text}", inline=False)
            embed.add_field(name="Warning Count", value=f"{warning_count}/{len(self.timeout_durations)}", inline=False)
            
            if log_channel:
                await log_channel.send(embed=embed)
            else:
                # If no log channel found, try to DM server owner
                try:
                    await guild.owner.send(embed=embed)
                except:
                    # If that fails too, just log it
                    logger.warning(f"Could not notify admins about serious moderation action against {user.name}")
                    
        except Exception as e:
            logger.error(f"Error notifying admins: {e}")
    
    async def remove_timeout(self, guild, user_id):
        """Remove timeout from a user and reset warnings"""
        try:
            # Get user from ID
            user = await guild.fetch_member(user_id)
            if not user:
                return False, "User not found in server"
                
            # Remove timeout
            await user.timeout(None, reason="Timeout manually removed by administrator")
            
            # Reset warnings
            str_id = str(user_id)
            self.reset_warnings(str_id)
            
            logger.info(f"Removed timeout and reset warnings for user {user.name} ({user_id})")
            return True, "Timeout removed and warnings reset"
            
        except Exception as e:
            logger.error(f"Error removing timeout: {e}")
            return False, str(e)