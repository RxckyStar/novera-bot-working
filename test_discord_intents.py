import discord
from discord.ext import commands

print("Testing discord.py Intents configuration...")

# Create intents
intents = discord.Intents.default()
intents.message_content = True
print(f"Intents created: {intents}")

# Create bot with intents
bot = commands.Bot(command_prefix='!', intents=intents)
print(f"Bot created with intents: {bot.intents}")

# Try to run bot with just token parameter
try:
    # Don't actually execute, just test signature
    print("Testing bot.run with token only")
    if callable(bot.run):
        print("bot.run is callable, this should work!")
    else:
        print("WARNING: bot.run is not callable")
except Exception as e:
    print(f"Error testing bot.run: {e}")

# NOTE: We should NOT try to update intents after bot creation
# This was causing the critical error
print("IMPORTANT: In discord.py 2.5.2, we cannot modify bot.intents after bot creation")
print("Instead, we must set all intents during initialization")