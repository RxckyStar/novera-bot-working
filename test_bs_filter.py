"""
Test script to ensure 'bs' is properly blocked by the profanity filter
This script will simulate different messages containing 'bs' in various contexts
and check if they are appropriately detected.
"""

import re
import logging

logging.basicConfig(level=logging.INFO)

def test_bs_filter():
    """Test the 'bs' profanity filter patterns"""
    test_messages = [
        "That's bs and you know it",                 # Should block
        "I went to a basketball game yesterday",     # Should allow
        "I need to abseil down the mountain",        # Should allow
        "The absolute value is negative",            # Should allow
        "bs isn't a nice thing to say",              # Should block
        "I'm going to observe the stars tonight",    # Should allow
        "That's b s",                                # Should block
        "That's b.s.",                               # Should block
        "That's b-s",                                # Should block
        "abs(value) returns absolute value"          # Should allow
    ]
    
    # Check with exact word matches (standalone 'bs')
    print("Testing exact word 'bs' detection:")
    for message in test_messages:
        is_exact_match = re.search(r'\bbs\b', message.lower()) is not None
        if is_exact_match:
            print(f"❌ BLOCKED - Exact match: '{message}'")
        else:
            print(f"✓ ALLOWED - No exact match: '{message}'")
    
    print("\nTesting more complex 'bs' patterns:")
    for message in test_messages:
        # Check patterns as they appear in profanity_filter.py
        patterns = [
            r'\bb[\W_]*s\b',                     # bs variations with any characters between
            r'(?<!\w)b[\W_]*s(?!\w)',            # bs when not part of another word
            r'(?<![a-zA-Z])bs(?![a-zA-Z])',      # exact bs not part of a word
            r'(?<![a-zA-Z])b\s*s(?![a-zA-Z])',   # b s with possible space
            r'(?<![a-zA-Z])b[-_.]*s(?![a-zA-Z])', # b-s, b.s with punctuation
        ]
        
        detected = False
        matched_pattern = None
        
        for pattern in patterns:
            if re.search(pattern, message.lower()):
                detected = True
                matched_pattern = pattern
                break
        
        if detected:
            print(f"❌ BLOCKED - Pattern match ({matched_pattern}): '{message}'")
        else:
            print(f"✓ ALLOWED - No pattern match: '{message}'")

if __name__ == "__main__":
    test_bs_filter()