import logging
import re

logging.basicConfig(level=logging.INFO)

# Simulating a message with "bs" checks
def test_profanity_check():
    messages = [
        "That's bs and you know it",                 # Should block
        "I went to a basketball game yesterday",     # Should allow
        "I need to abseil down the mountain",        # Should allow
        "The absolute value is negative",            # Should allow
        "bs isn't a nice thing to say",              # Should block
        "I'm going to observe the stars tonight"     # Should allow
    ]
    
    print("Testing profanity filter improvements for 'bs'...")
    for message in messages:
        # Check if 'bs' appears as a standalone word
        bs_standalone = re.search(r'\b(bs)\b', message.lower()) is not None
        
        # Check if 'bs' only appears as part of other words
        bs_in_message = 'bs' in message.lower()
        bs_only_in_words = bs_in_message and not bs_standalone
        
        if bs_standalone:
            print(f"❌ BLOCKED: '{message}' - Contains standalone 'bs'")
        elif bs_only_in_words:
            words_with_bs = [word for word in re.findall(r'\b\w+\b', message.lower()) if 'bs' in word]
            print(f"✓ ALLOWED: '{message}' - 'bs' only in longer words: {words_with_bs}")
        else:
            print(f"✓ ALLOWED: '{message}' - No 'bs' found")

if __name__ == "__main__":
    test_profanity_check()
