"""
Example of how to use safe_timeout.py in a Discord bot context.
This shows proper timeout handling that won't cause
"Timeout context manager should be used inside a task" errors.
"""

import asyncio
import discord
from discord.ext import commands
import logging
from safe_timeout import with_timeout, SafeTimeout

# Configure logging
logging.basicConfig(level=logging.INFO)

# Create bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Example 1: Using with_timeout for a potentially slow API call
@bot.command()
async def api_example(ctx):
    """Example command that makes an API call with a timeout"""
    await ctx.send("Fetching data from API (with 5 second timeout)...")
    
    async def fetch_data():
        # Simulate a slow API call
        await asyncio.sleep(10)  # This would normally be an actual API call
        return {"data": "example content"}
    
    # Use our safe timeout function
    result = await with_timeout(fetch_data(), timeout=5.0)
    
    if result is None:
        await ctx.send("API request timed out after 5 seconds!")
    else:
        await ctx.send(f"API response: {result}")


# Example 2: Using SafeTimeout context manager
@bot.command()
async def process_example(ctx):
    """Example command that processes data with a timeout context"""
    await ctx.send("Processing data (with 3 second timeout)...")
    
    async def process_data():
        async with SafeTimeout(3.0) as timeout:
            # Start processing in steps
            await ctx.send("Step 1: Processing...")
            await asyncio.sleep(1)
            
            await ctx.send("Step 2: Analyzing...")
            await asyncio.sleep(1)
            
            await ctx.send("Step 3: Finalizing...")
            # This step would time out
            await asyncio.sleep(2)
            
            if timeout.expired:
                await ctx.send("Processing timed out during step 3!")
                return None
            
            return "Processed data result"
    
    result = await process_data()
    if result:
        await ctx.send(f"Final result: {result}")
    else:
        await ctx.send("Process did not complete in time.")


# Example 3: Using with_timeout_callback
@bot.command()
async def interactive_example(ctx):
    """Example of an interactive command with timeout callbacks"""
    await ctx.send("Please respond within 10 seconds...")
    
    # Define what happens on timeout
    def on_timeout():
        asyncio.create_task(ctx.send("You took too long to respond!"))
    
    # Define what happens on error
    def on_error(e):
        asyncio.create_task(ctx.send(f"An error occurred: {e}"))
    
    # Wait for a message
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    # Use our safe timeout with callbacks
    from safe_timeout import with_timeout_callback
    message = await with_timeout_callback(
        bot.wait_for('message', check=check),
        timeout=10.0,
        on_timeout=on_timeout,
        on_error=on_error
    )
    
    if message:
        await ctx.send(f"You responded: {message.content}")

# Example of proper bot startup with event loop management
async def run_bot(token):
    """Run the bot with proper async handling"""
    try:
        await bot.start(token)
    except Exception as e:
        logging.error(f"Error starting bot: {e}")

def main():
    """Main entry point with proper event loop handling"""
    # Get token from environment
    import os
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logging.error("No token found in environment variables")
        return
    
    # Get the current event loop
    loop = asyncio.get_event_loop()
    
    # Run the bot with proper loop handling
    if loop.is_running():
        logging.info("Event loop is already running, using create_task")
        # If loop is already running, create a task
        task = loop.create_task(run_bot(token))
    else:
        logging.info("No event loop running, using run_until_complete")
        # If no loop is running, run until complete
        loop.run_until_complete(run_bot(token))

if __name__ == "__main__":
    main()