import logging
import re

logging.basicConfig(level=logging.INFO)

# Simulating a message with "minecraft" and "af" checks
def test_profanity_check():
    messages = [
        "I love playing Minecraft with friends",  # Should allow
        "that was af funny",                      # Should block
        "the aircraft is ready",                  # Should allow
        "I'm setting up a new server for Minecraft", # Should allow
        "that's kinda af not cool",               # Should block
        "I really enjoy crafting in Minecraft"    # Should allow
    ]
    
    print("Testing profanity filter improvements for 'af'...")
    for message in messages:
        # First check if it's Minecraft related
        if "minecraft" in message.lower():
            print(f"✓ ALLOWED: '{message}' - Contains 'minecraft'")
            continue
            
        # Special handling for "af"
        if "af" in message.lower():
            # Extract all words containing "af"
            af_containing_words = [word for word in re.findall(r'\b\w+\b', message.lower()) if "af" in word]
            
            # If "af" only appears as part of longer words (like "minecraft", "crafting", etc.)
            # and never as a standalone "af", then it's safe
            if af_containing_words and all(len(word) > 2 for word in af_containing_words):
                print(f"✓ ALLOWED: '{message}' - 'af' only in longer words: {af_containing_words}")
                continue
                
            # If "af" appears standalone or the phrase "as f" appears
            if "af" in re.findall(r'\b\w+\b', message.lower()) or "as f" in message.lower():
                print(f"❌ BLOCKED: '{message}' - Contains standalone 'af' or 'as f'")
                continue
                
        # If we reach here, the message is allowed
        print(f"✓ ALLOWED: '{message}'")

if __name__ == "__main__":
    test_profanity_check()
