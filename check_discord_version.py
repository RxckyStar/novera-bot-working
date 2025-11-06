import discord
import inspect

print(f"Discord.py version: {discord.__version__}")
try:
    from discord.ext import commands
    print(f"Bot.run signature: {inspect.signature(commands.Bot.run)}")
except (ImportError, AttributeError) as e:
    print(f"Error inspecting Bot.run: {e}")
    
# Check client.run signature instead
print(f"Client.run signature: {inspect.signature(discord.Client.run)}")