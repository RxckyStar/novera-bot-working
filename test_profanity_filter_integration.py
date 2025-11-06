"""
Integration test for profanity filter with the "bs" detection
This simulates how the actual filter would process messages
"""

import logging
import re
from profanity_filter import CUSTOM_BANNED_PATTERNS, BANNED_WORDS

logging.basicConfig(level=logging.INFO)

class MockMessage:
    """Mock Discord message for testing"""
    def __init__(self, content, author_name="test_user", author_id=12345):
        self.content = content
        self.author = MockAuthor(author_name, author_id)

class MockAuthor:
    """Mock Discord author for testing"""
    def __init__(self, name, id):
        self.name = name
        self.id = id

def simulated_filter_check(message_content):
    """Simulate the core detection logic in profanity_filter.py"""
    content = message_content.lower()
    
    # Implement our smart 'bs' detection logic that only catches standalone instances
    
    # First check for exact "bs" matches
    bs_standalone = re.search(r'\bbs\b', content) is not None
    
    if bs_standalone:
        return True, "bs (exact standalone)"
    
    # Check for variations with spaces or punctuation
    bs_variations = [
        r'(?<!\w)b[\W_]*s(?!\w)',         # bs when not part of another word
        r'(?<![a-zA-Z])bs(?![a-zA-Z])',   # exact bs not part of a word
        r'(?<![a-zA-Z])b\s*s(?![a-zA-Z])', # b s with possible space
        r'(?<![a-zA-Z])b[-_.]*s(?![a-zA-Z])' # b-s, b.s with punctuation
    ]
    
    for pattern in bs_variations:
        match = re.search(pattern, content)
        if match:
            return True, f"bs variation ({match.group(0)})"
    
    # Check direct matches against BANNED_WORDS (only if not part of longer words)
    for word in BANNED_WORDS:
        if word == "bs" or word == "b.s" or word == "b-s" or word == "b s":
            # Skip these as we already checked with our improved patterns
            continue
            
        if word in content:
            # For direct bs check, make sure it's not part of another word
            if word == "bs":
                # Skip if it's part of a longer word
                continue
            return True, word
    
    # If we get here, the message is allowed
    return False, None

def test_bs_integration():
    """Test messages with the simulated filter"""
    test_messages = [
        "That's bs",                      # Should block
        "What bs is this",                # Should block
        "That's absolute bs",             # Should block
        "That's b s",                     # Should block
        "That's b.s.",                    # Should block
        "That's b-s",                     # Should block
        "jobs are awesome",               # Should allow
        "basketball is fun",              # Should allow
        "absolutely fantastic",           # Should allow
        "I need to abseil down",          # Should allow
        "I observed the stars"            # Should allow
    ]
    
    print("Testing 'bs' detection with core profanity filter logic:")
    for message in test_messages:
        is_banned, reason = simulated_filter_check(message)
        
        if is_banned:
            print(f"❌ BLOCKED: '{message}' - Reason: {reason}")
        else:
            print(f"✓ ALLOWED: '{message}'")

if __name__ == "__main__":
    test_bs_integration()