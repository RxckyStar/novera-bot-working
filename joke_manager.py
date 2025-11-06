"""
Joke Manager - Tracks joke preferences and adapts joke selection based on server feedback

This module provides functionality to track which jokes receive positive reactions,
allowing the bot to learn the server's humor preferences over time and adapt the
joke selection to match the server's taste.
"""

import json
import os
import random
import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JokeDifficulty(Enum):
    """Enum for joke difficulty/sassiness levels"""
    MILD = 1      # Safe, light humor
    MEDIUM = 2    # Moderate sass
    SPICY = 3     # Higher sass level
    EXTRA_SPICY = 4  # Maximum sass

class JokeCategory(Enum):
    """Categories of jokes"""
    GENERAL = "general"       # General jokes
    SPILL = "spill"           # Gossip jokes
    SHOPPING = "shopping"     # Shopping jokes
    TIPJAR = "tipjar"         # Tipjar jokes
    CONFESS = "confess"       # Confession jokes

class JokeManager:
    """Manages joke preferences and adapts joke selection based on server feedback"""
    
    def __init__(self, data_file: str = "joke_preferences.json"):
        """Initialize the joke manager"""
        self.data_file = data_file
        self.preferences = self._load_preferences()
        self.joke_ratings = self._initialize_joke_ratings()
        
    def _load_preferences(self) -> Dict[str, Any]:
        """Load joke preferences from file or create default"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded joke preferences from {self.data_file}")
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading joke preferences: {e}")
                return self._create_default_preferences()
        else:
            return self._create_default_preferences()
    
    def _save_preferences(self) -> None:
        """Save joke preferences to file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.preferences, f, indent=2)
            logger.info(f"Saved joke preferences to {self.data_file}")
        except IOError as e:
            logger.error(f"Error saving joke preferences: {e}")
    
    def _create_default_preferences(self) -> Dict[str, Any]:
        """Create default joke preferences"""
        default_prefs = {
            "global": {
                "preferred_difficulty": JokeDifficulty.MEDIUM.value,
                "category_weights": {cat.value: 1.0 for cat in JokeCategory},
                "last_updated": time.time()
            },
            "servers": {},
            "joke_ratings": {}
        }
        logger.info("Created default joke preferences")
        return default_prefs
    
    def _initialize_joke_ratings(self) -> Dict[str, Dict[str, Any]]:
        """Initialize or load joke ratings"""
        if "joke_ratings" not in self.preferences:
            self.preferences["joke_ratings"] = {}
        return self.preferences["joke_ratings"]
    
    def get_server_preference(self, server_id: str, default_to_global: bool = True) -> Dict[str, Any]:
        """Get server-specific joke preferences"""
        if server_id in self.preferences["servers"]:
            return self.preferences["servers"][server_id]
        elif default_to_global:
            return self.preferences["global"]
        else:
            # Create new server preference based on global
            self.preferences["servers"][server_id] = {
                "preferred_difficulty": self.preferences["global"]["preferred_difficulty"],
                "category_weights": self.preferences["global"]["category_weights"].copy(),
                "last_updated": time.time()
            }
            self._save_preferences()
            return self.preferences["servers"][server_id]
    
    def register_joke_reaction(self, joke_id: str, rating: int, server_id: str) -> None:
        """
        Register a reaction to a joke
        
        Parameters:
            joke_id: Unique identifier for the joke (hash or index)
            rating: Rating from 1-5 (1=disliked, 5=loved)
            server_id: Discord server ID where the joke was rated
        """
        # Initialize joke in ratings if not exists
        if joke_id not in self.joke_ratings:
            self.joke_ratings[joke_id] = {
                "total_ratings": 0,
                "avg_rating": 0,
                "server_ratings": {}
            }
        
        # Initialize server in joke ratings if not exists
        if server_id not in self.joke_ratings[joke_id]["server_ratings"]:
            self.joke_ratings[joke_id]["server_ratings"][server_id] = {
                "total_ratings": 0,
                "avg_rating": 0
            }
        
        # Update global joke rating
        total = self.joke_ratings[joke_id]["total_ratings"]
        avg = self.joke_ratings[joke_id]["avg_rating"]
        new_total = total + 1
        new_avg = ((avg * total) + rating) / new_total
        
        self.joke_ratings[joke_id]["total_ratings"] = new_total
        self.joke_ratings[joke_id]["avg_rating"] = new_avg
        
        # Update server-specific joke rating
        server_total = self.joke_ratings[joke_id]["server_ratings"][server_id]["total_ratings"]
        server_avg = self.joke_ratings[joke_id]["server_ratings"][server_id]["avg_rating"]
        new_server_total = server_total + 1
        new_server_avg = ((server_avg * server_total) + rating) / new_server_total
        
        self.joke_ratings[joke_id]["server_ratings"][server_id]["total_ratings"] = new_server_total
        self.joke_ratings[joke_id]["server_ratings"][server_id]["avg_rating"] = new_server_avg
        
        # Save updates
        self.preferences["joke_ratings"] = self.joke_ratings
        self._save_preferences()
        
        # Adjust server preferences periodically
        if new_server_total % 5 == 0:  # Every 5 ratings, update server preferences
            self._update_server_preferences(server_id)
    
    def _update_server_preferences(self, server_id: str) -> None:
        """Update server preferences based on joke ratings"""
        # Ensure server preferences exist
        server_prefs = self.get_server_preference(server_id, default_to_global=False)
        
        # Calculate difficulty preference based on ratings
        difficulty_scores = {d.value: 0 for d in JokeDifficulty}
        difficulty_counts = {d.value: 0 for d in JokeDifficulty}
        
        # Calculate category weights based on ratings
        category_scores = {c.value: 0 for c in JokeCategory}
        category_counts = {c.value: 0 for c in JokeCategory}
        
        # Analyze all jokes with ratings from this server
        for joke_id, joke_data in self.joke_ratings.items():
            if server_id in joke_data["server_ratings"]:
                rating = joke_data["server_ratings"][server_id]["avg_rating"]
                
                # Extract joke metadata if available
                # This is a placeholder - in a real implementation, you'd have 
                # a way to look up joke metadata by ID
                joke_difficulty = 2  # Default to medium
                joke_category = "general"  # Default to general
                
                # Update difficulty scores
                difficulty_scores[joke_difficulty] += rating
                difficulty_counts[joke_difficulty] += 1
                
                # Update category scores
                category_scores[joke_category] += rating
                category_counts[joke_category] += 1
        
        # Calculate new preferred difficulty
        best_difficulty = max(
            [d for d in JokeDifficulty], 
            key=lambda d: difficulty_scores[d.value]/max(difficulty_counts[d.value], 1)
        )
        
        # Calculate new category weights
        new_category_weights = {}
        for cat in JokeCategory:
            cat_value = cat.value
            if category_counts[cat_value] > 0:
                new_category_weights[cat_value] = category_scores[cat_value] / category_counts[cat_value]
            else:
                new_category_weights[cat_value] = server_prefs["category_weights"].get(cat_value, 1.0)
        
        # Normalize category weights
        max_weight = max(new_category_weights.values())
        if max_weight > 0:
            for cat in new_category_weights:
                new_category_weights[cat] = new_category_weights[cat] / max_weight
        
        # Update server preferences
        server_prefs["preferred_difficulty"] = best_difficulty.value
        server_prefs["category_weights"] = new_category_weights
        server_prefs["last_updated"] = time.time()
        
        self.preferences["servers"][server_id] = server_prefs
        self._save_preferences()
        
        logger.info(f"Updated joke preferences for server {server_id}")
    
    def select_joke(self, jokes_by_difficulty: Dict[int, List[str]], 
                    category: JokeCategory, server_id: str) -> str:
        """
        Select a joke based on server preferences
        
        Parameters:
            jokes_by_difficulty: Dictionary mapping difficulty levels to lists of jokes
            category: The joke category to select from
            server_id: Discord server ID to use for preference
            
        Returns:
            Selected joke based on server preferences
        """
        server_prefs = self.get_server_preference(server_id)
        preferred_difficulty = server_prefs["preferred_difficulty"]
        
        # Determine if we should vary the difficulty
        # 70% chance to use preferred difficulty, 30% chance to explore others
        if random.random() < 0.7:
            difficulty = preferred_difficulty
        else:
            # Choose a random difficulty, weighted toward those close to preferred
            difficulties = list(jokes_by_difficulty.keys())
            if difficulties:
                weights = [1.0 / (1 + abs(d - preferred_difficulty)) for d in difficulties]
                difficulty = random.choices(difficulties, weights=weights, k=1)[0]
            else:
                difficulty = preferred_difficulty
        
        # Ensure the selected difficulty exists in our jokes
        available_difficulties = list(jokes_by_difficulty.keys())
        if not available_difficulties:
            logger.warning(f"No jokes available for category {category}")
            return "Mommy's drawing a blank right now, darling! Even I need a moment sometimes! 💅"
            
        if difficulty not in available_difficulties:
            # Fall back to closest available difficulty
            difficulty = min(available_difficulties, key=lambda d: abs(d - difficulty))
        
        # Select a joke from the chosen difficulty
        jokes = jokes_by_difficulty[difficulty]
        if not jokes:
            logger.warning(f"No jokes available for difficulty {difficulty}")
            return "Mommy's drawing a blank right now, darling! Even I need a moment sometimes! 💅"
            
        selected_joke = random.choice(jokes)
        return selected_joke
        
    def categorize_jokes_by_difficulty(self, jokes: List[str]) -> Dict[int, List[str]]:
        """
        Categorize jokes by difficulty level
        This is a basic implementation that could be enhanced with NLP or manual tagging
        
        Parameters:
            jokes: List of jokes to categorize
            
        Returns:
            Dictionary mapping difficulty levels to lists of jokes
        """
        joke_difficulty = {}
        
        for joke in jokes:
            # Simple classification based on joke characteristics
            # This is a very basic implementation
            # In practice, you might use sentiment analysis, explicit word detection,
            # or manual tagging for more accurate categorization
            
            # Count emojis as a simple proxy for joke intensity
            emoji_count = sum(1 for char in joke if ord(char) > 127)
            
            # Count mentions of money, value, stealing etc. as proxy for joke spiciness
            spicy_terms = ["stealing", "stole", "value", "money", "wallet", "purse", "funds"]
            spicy_count = sum(1 for term in spicy_terms if term.lower() in joke.lower())
            
            # Calculate a basic difficulty score
            difficulty_score = 1  # Default to mild
            
            if emoji_count > 5 or spicy_count > 2:
                difficulty_score = 4  # Extra spicy
            elif emoji_count > 3 or spicy_count > 1:
                difficulty_score = 3  # Spicy
            elif emoji_count > 1 or spicy_count > 0:
                difficulty_score = 2  # Medium
                
            # Categorize by detected difficulty
            if difficulty_score not in joke_difficulty:
                joke_difficulty[difficulty_score] = []
            joke_difficulty[difficulty_score].append(joke)
        
        return joke_difficulty

# Global instance for ease of use
joke_manager = JokeManager()