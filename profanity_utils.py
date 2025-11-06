"""
Direct profanity detection utilities for the Discord bot
"""
import re
import logging

# List of banned words (exact matches)
BANNED_WORDS = [
    "shit", "ass", "damn", "hell", "crap", "bitch",
    "fuck", "fucking", "fuk", "fuking", "f*ck", "f**k",
    "bullshit", "dipshit", "motherfucker",
    "asshole", "dumbass", "smartass",
]

def contains_profanity(text: str) -> bool:
    """
    Direct check if a text contains profanity
    
    Args:
        text: The text to check
        
    Returns:
        bool: True if the text contains profanity
    """
    # Convert to lowercase
    text = text.lower()
    
    # Check for F words specially (most common)
    if ('fuck' in text or 'f*ck' in text or 'f**k' in text or 
        'fuk' in text or 'fuking' in text or 'f u c k' in text):
        logging.warning(f"Found explicit f-word variant: {text}")
        return True
    
    # Check for other banned words
    for word in BANNED_WORDS:
        if word in text:
            logging.warning(f"Found banned word '{word}' in message: {text[:50]}")
            return True
    
    # Check for words with spaces or special chars inserted
    # f.u.c.k or f u c k etc.
    fword_pattern = r"f[\s\.\*\_\-]*u[\s\.\*\_\-]*c[\s\.\*\_\-]*k"
    if re.search(fword_pattern, text):
        logging.warning(f"Found f-word with separators: {text[:50]}")
        return True
    
    return False