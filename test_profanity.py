import logging
from profanity_filter import ProfanityFilter

class DummyBot:
    def __init__(self):
        self.loop = None
        
class DummyMessage:
    def __init__(self, content):
        self.content = content
        self.author = type('DummyAuthor', (), {'bot': False, 'id': 123456, 'name': 'DummyUser'})
        self.guild = type('DummyGuild', (), {'id': 654321})

logging.basicConfig(level=logging.INFO)
pf = ProfanityFilter(DummyBot())

print('Test for Minecraft:', pf.check_message(DummyMessage('I love playing Minecraft with friends')))
print('Test for af standalone:', pf.check_message(DummyMessage('that was af funny')))
print('Test for af in word:', pf.check_message(DummyMessage('the aircraft is ready')))
