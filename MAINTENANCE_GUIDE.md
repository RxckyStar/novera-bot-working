# Discord Bot Maintenance Guide

This guide provides essential information for maintaining and extending the Novera Assistant Discord bot.

## Starting the Bot

### Option 1: Using the Workflow (Recommended)
Start the bot using the Replit workflow system:
```
Click "Run" in the Replit interface
```

### Option 2: Using the Start Script
Start the bot using our custom script with all stability fixes:
```bash
./start_with_fixes.sh
```

## Adding New Commands

When adding new commands that involve waiting for user input:

```python
# ALWAYS use wait_for_safe instead of direct bot.wait_for
from timeout_handlers import wait_for_safe

@bot.command()
async def newcommmand(ctx):
    await ctx.send("Please enter your response:")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    # Safe way to wait for user input - returns None on timeout
    response = await wait_for_safe(bot.wait_for('message', check=check), timeout=60)
    if response is None:
        await ctx.send("You didn't respond in time!")
        return
        
    # Continue processing the response
    await ctx.send(f"You said: {response.content}")
```

## Adding Timeouts to Other Operations

If you need to add a timeout to any async operation:

```python
from timeout_handlers import with_timeout

@bot.command()
async def longoperation(ctx):
    try:
        # This will properly wrap the operation in a task
        result = await with_timeout(some_long_running_coroutine(), timeout_seconds=30)
        await ctx.send(f"Operation completed with result: {result}")
    except asyncio.TimeoutError:
        await ctx.send("Operation timed out!")
```

## Using the Timeout Decorator

For commands that should have an overall timeout:

```python
from discord_asyncio_fix import timeout_after

@bot.command()
@timeout_after(60)  # Command will time out after 60 seconds
async def timelimited(ctx):
    # This entire command will time out after 60 seconds
    # No need for manual timeout handling
    await ctx.send("Starting long process...")
    await asyncio.sleep(10)  # Simulating work
    await ctx.send("Still working...")
    await asyncio.sleep(10)  # More simulation
    await ctx.send("Finished!")
```

## Troubleshooting

### Bot Crashes with Timeout Errors

If you see "Timeout context manager should be used inside a task" errors:
1. Check for direct uses of `bot.wait_for` without `wait_for_safe`
2. Run `python fix_wait_for.py` to fix all instances automatically

### Event Loop Errors

If you see "This event loop is already running" or similar errors:
1. Make sure you're not using `asyncio.run()` directly
2. Use our `discord_asyncio_fix.run_coroutine()` function instead

### Bot Becomes Unresponsive

If the bot stops responding but doesn't crash:
1. Check the heartbeat timestamps in the logs
2. If heartbeats have stopped, restart the bot using `./start_with_fixes.sh`

## Essential Files

- **bot.py** - Main bot implementation
- **timeout_handlers.py** - Safe timeout utilities
- **discord_asyncio_fix.py** - Comprehensive asyncio fixes
- **run_bot.py** - Clean entry point with all fixes applied
- **start_with_fixes.sh** - Script to properly start the bot
- **COMPREHENSIVE_STABILITY_SOLUTION.md** - Details on all the fixes

## Improving Stability Further

1. Add more debugging with `logging.debug()` calls in critical areas
2. Consider adding a command to check bot health:
   ```python
   @bot.command()
   async def health(ctx):
       """Check if the bot is healthy."""
       uptime = datetime.now() - bot_start_time
       await ctx.send(f"Bot is healthy! Uptime: {uptime}")
   ```
3. Make sure all new interactive components use the correct timeout handling