"""
Contextual Moderation Explanation Generator for Novera Assistant
Provides educational and appropriate explanations for moderation actions
"""

import random
import logging
from typing import Dict, List, Optional, Tuple

# Educational explanations grouped by category
EXPLANATIONS = {
    "profanity": [
        "Your message contained language that doesn't align with our community standards. "
        "We maintain a respectful environment where everyone feels comfortable.",
        
        "We detected inappropriate language in your message. Our server aims to be a positive "
        "space where everyone can interact without encountering offensive content.",
        
        "This message was flagged for containing words that violate our language policy. "
        "Please keep all communications friendly and suitable for all members."
    ],
    
    "slurs": [
        "Your message contained language that is considered derogatory or harmful to certain groups. "
        "Our community values respect for all people regardless of background, identity, or characteristics.",
        
        "We detected language that is considered a slur, which harms our inclusive environment. "
        "Such terms perpetuate stereotypes and create an unwelcoming atmosphere for other members.",
        
        "The term used in your message is considered offensive to a specific group of people. "
        "Our community stands against language that marginalizes or demeans others."
    ],
    
    "harassment": [
        "Your message was flagged as potentially harassing another member. "
        "We take interpersonal respect seriously to maintain a healthy community.",
        
        "Content that targets or demeans other members isn't permitted in our server. "
        "Please ensure your interactions remain respectful even during disagreements.",
        
        "We detected content that could be interpreted as harassment. "
        "Our community thrives when everyone feels safe and respected in their interactions."
    ],
    
    "self-harm": [
        "Your message contained concerning references to self-harm. "
        "We care about the wellbeing of all our members and don't permit content that "
        "normalizes or encourages harmful behaviors.",
        
        "We removed your message because it contained references to self-harm or suicide. "
        "These topics require careful handling, and we prioritize everyone's mental health and safety.",
        
        "Your message was flagged for containing references to self-harm. If you or someone "
        "you know is struggling, please reach out to mental health resources for support."
    ],
    
    "sexual": [
        "Your message contained inappropriately explicit content. "
        "Our server maintains family-friendly standards for all conversations.",
        
        "We detected sexually explicit content in your message, which isn't appropriate "
        "for our community. Please keep conversations suitable for all ages.",
        
        "Your message was removed for containing sexual content that violates our "
        "community guidelines. We maintain appropriate conversation standards in all channels."
    ],
    
    "spam": [
        "Your message was flagged as potential spam. "
        "Repeated or excessive messages disrupt normal conversation for everyone.",
        
        "We detected message patterns consistent with spam. "
        "Please avoid excessive repetition, all-caps, or rapid-fire messaging.",
        
        "Your message was removed to prevent channel flooding. "
        "Quality conversations are better than quantity for our community."
    ],
    
    "custom_term": [
        "Your message contained a term that's specifically prohibited in our server. "
        "Though this term might be acceptable elsewhere, we've chosen to disallow it here.",
        
        "We detected a prohibited term specified in our server's custom filter list. "
        "Our community has specific language guidelines that may differ from other servers.",
        
        "Your message was removed for containing a term our server has specifically banned. "
        "Some terms have contextual meanings or history within our community that require moderation."
    ],
    
    "default": [
        "Your message was flagged by our moderation system for containing prohibited content. "
        "Please review our server rules to understand our community standards.",
        
        "We detected content that violates our server guidelines. "
        "Our moderation system helps maintain a positive environment for everyone.",
        
        "Your message was removed because it contained content that doesn't align with our "
        "community standards. We appreciate your understanding and cooperation."
    ]
}

# Gentle reminders to add at the end of explanations
REMINDERS = [
    "Please keep this in mind for future messages.",
    "We appreciate your understanding and cooperation.",
    "Thank you for helping maintain our positive community.",
    "We're all responsible for creating a welcoming environment.",
    "Your contribution to a respectful community is valued.",
    "Let's work together to keep conversations enjoyable for everyone."
]

# Category mapping from detected terms to explanation categories
CATEGORY_MAPPING = {
    # Profanity categories
    "f-word": "profanity",
    "f-word (explicit standalone)": "profanity",
    "f-word (explicit pattern)": "profanity",
    "f-word (pattern match)": "profanity",
    "bs": "profanity",
    "direct profanity": "profanity",
    
    # Slur categories
    "r-word (ableist slur)": "slurs",
    "n-word": "slurs",
    "homophobic slur": "slurs",
    "transphobic slur": "slurs",
    "ableist slur": "slurs",
    "racial slur": "slurs",
    
    # Self-harm categories
    "self-harm reference": "self-harm",
    "self-harm reference (direct)": "self-harm",
    "suicide reference": "self-harm",
    "kys": "self-harm",
    
    # Sexual content
    "sexual assault term": "sexual",
    "explicit sexual content": "sexual",
    
    # Custom banned terms
    "custom banned term": "custom_term",
    "sybau": "custom_term"
}

class ModerationExplainer:
    """Generates contextual explanations for moderation actions"""
    
    def __init__(self):
        self.logger = logging.getLogger("moderation_explainer")
        self.logger.info("Initialized Moderation Explanation Generator")
    
    def get_explanation(self, term: str, content: Optional[str] = None, 
                        user_name: Optional[str] = None) -> str:
        """
        Get a contextual explanation for why content was moderated
        
        Args:
            term: The detected term or category that triggered moderation
            content: The filtered content (used for context analysis)
            user_name: The user's name (for personalized messages)
        
        Returns:
            A human-friendly explanation of why the content was moderated
        """
        # Determine the explanation category
        category = self._get_category(term)
        
        # Log the explanation request
        log_msg = f"Generating explanation for term '{term}' (category: {category})"
        if user_name:
            log_msg += f" for user {user_name}"
        self.logger.info(log_msg)
        
        # Get explanation body
        explanation = random.choice(EXPLANATIONS.get(category, EXPLANATIONS["default"]))
        
        # Add gentle reminder
        reminder = random.choice(REMINDERS)
        
        # Form full message
        full_explanation = f"{explanation} {reminder}"
        
        return full_explanation
    
    def get_timeout_explanation(self, term: str, duration_minutes: int, 
                               repetition_count: int = 1) -> str:
        """
        Get an explanation specifically for timeout actions
        
        Args:
            term: The detected term that triggered moderation
            duration_minutes: Timeout duration in minutes
            repetition_count: How many times the user has been warned
        
        Returns:
            An explanation of why the timeout was applied and for how long
        """
        # Determine the explanation category
        category = self._get_category(term)
        
        # Base explanation
        explanation = random.choice(EXPLANATIONS.get(category, EXPLANATIONS["default"]))
        
        # Format duration text
        if duration_minutes < 1:
            duration_text = "a brief moment"
        elif duration_minutes == 1:
            duration_text = "1 minute"
        elif duration_minutes < 60:
            duration_text = f"{duration_minutes} minutes"
        elif duration_minutes == 60:
            duration_text = "1 hour"
        elif duration_minutes < 1440:  # less than a day
            hours = duration_minutes // 60
            duration_text = f"{hours} hours"
        elif duration_minutes == 1440:  # exactly a day
            duration_text = "1 day"
        else:
            days = duration_minutes // 1440
            duration_text = f"{days} days"
        
        # Add timeout-specific explanation
        if repetition_count <= 1:
            timeout_msg = (
                f"As a result, you've been temporarily timed out for {duration_text}. "
                f"This is a gentle reminder about our community standards."
            )
        elif repetition_count == 2:
            timeout_msg = (
                f"Since this is a repeated occurrence, you've been timed out for {duration_text}. "
                f"Please take this time to review our server rules."
            )
        else:
            timeout_msg = (
                f"Due to multiple violations, you've been timed out for {duration_text}. "
                f"Continued violations may result in longer restrictions."
            )
        
        # Form full message
        full_explanation = f"{explanation} {timeout_msg} {random.choice(REMINDERS)}"
        
        return full_explanation
    
    def _get_category(self, term: str) -> str:
        """Map a detected term to its explanation category"""
        # Clean the term for matching
        clean_term = term.lower().strip()
        
        # Direct mapping
        if clean_term in CATEGORY_MAPPING:
            return CATEGORY_MAPPING[clean_term]
        
        # Partial matching for terms that contain these substrings
        if "slur" in clean_term:
            return "slurs"
        elif any(x in clean_term for x in ["f-word", "fuck", "f*ck"]):
            return "profanity"
        elif any(x in clean_term for x in ["harm", "kys", "kill", "suicid"]):
            return "self-harm"
        elif any(x in clean_term for x in ["sex", "explicit"]):
            return "sexual"
        elif "spam" in clean_term:
            return "spam"
        elif "harass" in clean_term:
            return "harassment"
        elif "custom" in clean_term or "banned" in clean_term:
            return "custom_term"
        
        # Default category if no match found
        return "default"

# Instantiate for easy importing
explainer = ModerationExplainer()

def get_explanation(term: str, content: Optional[str] = None, 
                   user_name: Optional[str] = None) -> str:
    """Convenience function to get a moderation explanation"""
    return explainer.get_explanation(term, content, user_name)

def get_timeout_explanation(term: str, duration_minutes: int, 
                           repetition_count: int = 1) -> str:
    """Convenience function to get a timeout explanation"""
    return explainer.get_timeout_explanation(term, duration_minutes, repetition_count)