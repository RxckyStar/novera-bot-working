"""
Joke Reactions - Handles reaction-based feedback for jokes

This module provides functionality to track and process user reactions to jokes,
allowing the bot to learn which jokes are appreciated more by the server.
"""

import discord
import logging
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from joke_manager import joke_manager, JokeCategory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reaction to rating mapping
REACTION_RATINGS = {
    "😂": 5,  # Laughing face = 5/5 (loved it)
    "🤣": 5,  # Rolling on the floor laughing = 5/5
    "😆": 4,  # Laughing = 4/5 (really liked it)
    "😄": 4,  # Smiling face with open mouth = 4/5
    "😊": 3,  # Smiling face = 3/5 (liked it)
    "🙂": 3,  # Slightly smiling face = 3/5
    "😐": 2,  # Neutral face = 2/5 (it was okay)
    "😶": 2,  # Face without mouth = 2/5
    "😒": 1,  # Unamused face = 1/5 (didn't like it)
    "🙄": 1,  # Face with rolling eyes = 1/5
    "👎": 1,  # Thumbs down = 1/5
    "👍": 4,  # Thumbs up = 4/5
    "❤️": 5,  # Heart = 5/5
    "💖": 5,  # Sparkling heart = 5/5
}

# Track joke messages to know which reactions to monitor
joke_messages: Dict[int, Dict[str, Any]] = {}

def register_joke_message(message: discord.Message, joke_text: str, category: JokeCategory) -> None:
    """
    Register a joke message for tracking reactions
    
    Parameters:
        message: The Discord message containing the joke
        joke_text: The text of the joke
        category: The category of the joke
    """
    # Generate a unique ID for the joke
    joke_id = hashlib.md5(joke_text.encode('utf-8')).hexdigest()
    
    # Register the joke message
    joke_messages[message.id] = {
        "joke_id": joke_id,
        "joke_text": joke_text,
        "category": category,
        "server_id": str(message.guild.id) if message.guild else "DM",
        "timestamp": message.created_at.timestamp(),
        "processed_reactions": set()
    }
    
    logger.info(f"Registered joke message {message.id} with joke_id {joke_id}")

async def process_reaction(reaction: discord.Reaction, user: discord.User) -> None:
    """
    Process a reaction to a joke
    
    Parameters:
        reaction: The Discord reaction
        user: The user who reacted
    """
    # Skip reactions from bots
    if user.bot:
        return
        
    # Check if this is a reaction to a tracked joke message
    message_id = reaction.message.id
    if message_id not in joke_messages:
        return
        
    # Get joke data
    joke_data = joke_messages[message_id]
    joke_id = joke_data["joke_id"]
    server_id = joke_data["server_id"]
    
    # Skip if already processed this user's reaction for this joke
    reaction_key = f"{user.id}:{reaction.emoji}"
    if reaction_key in joke_data["processed_reactions"]:
        return
    
    # Get rating for reaction
    emoji = str(reaction.emoji)
    if emoji in REACTION_RATINGS:
        rating = REACTION_RATINGS[emoji]
        
        # Register the rating with the joke manager
        joke_manager.register_joke_reaction(joke_id, rating, server_id)
        
        # Mark this reaction as processed
        joke_data["processed_reactions"].add(reaction_key)
        
        logger.info(f"Processed reaction {emoji} from user {user.id} for joke {joke_id} with rating {rating}")
    
def get_joke_with_difficulty(jokes: List[str], category: JokeCategory, server_id: str) -> str:
    """
    Get a joke appropriate for the server's humor preferences
    
    Parameters:
        jokes: List of jokes to choose from
        category: The category of jokes
        server_id: The Discord server ID
        
    Returns:
        A joke selected based on the server's preferences
    """
    # Categorize jokes by difficulty
    jokes_by_difficulty = joke_manager.categorize_jokes_by_difficulty(jokes)
    
    # Select a joke based on server preferences
    return joke_manager.select_joke(jokes_by_difficulty, category, server_id)