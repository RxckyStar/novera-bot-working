"""
Test for the profanity filter's 'bs' detection using the actual filter class
"""

import logging
from profanity_filter import ProfanityFilter

logging.basicConfig(level=logging.INFO)

class MockMessage:
    """Mock Discord message for testing the profanity filter"""
    def __init__(self, content, author_name="test_user", author_id=123456):
        self.content = content
        self.author = MockAuthor(author_name, author_id)
        self.guild = MockGuild()
        
    def __str__(self):
        return f"Message from {self.author.name}: {self.content}"

class MockAuthor:
    """Mock Discord author"""
    def __init__(self, name, id):
        self.name = name
        self.id = id
        self.roles = []
        self.bot = False  # Not a bot
        
class MockGuild:
    """Mock Discord guild/server"""
    def __init__(self, id=789012):
        self.id = id

class MockBot:
    """Mock Discord bot with loop attribute"""
    def __init__(self):
        self.loop = MockLoop()
        
class MockLoop:
    """Mock asyncio loop"""
    def create_task(self, coro):
        # Just ignore task creation for testing
        pass

def main():
    """Test the profanity filter with various 'bs' test cases"""
    # Initialize the filter
    bot = MockBot()
    profanity_filter = ProfanityFilter(bot)
    
    # Define test messages
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
    
    print("Testing actual ProfanityFilter class with 'bs' detection:")
    for message_text in test_messages:
        message = MockMessage(message_text)
        is_banned, reason = profanity_filter.check_message(message)
        
        if is_banned:
            print(f"❌ BLOCKED: '{message_text}' - Reason: {reason}")
        else:
            print(f"✓ ALLOWED: '{message_text}'")

if __name__ == "__main__":
    main()