# How to Use the Discord Asyncio Fix

This guide explains how to use our comprehensive fix for asyncio-related issues in Discord.py applications.

## Quick Start

If you just want to run the bot:

```bash
python run_bot.py
```

## How to Use in Your Code

### 1. Import the Fix

Always import the fix at the very beginning of your file:

```python
# Import fix FIRST before any other imports
import discord_asyncio_fix
from discord_asyncio_fix import safe_wait_for
```

### 2. For All wait_for Operations

Use safe_wait_for instead of direct bot.wait_for calls:

```python
# Instead of this:
# response = await bot.wait_for('message', check=check, timeout=60)

# Use this:
response = await safe_wait_for(bot.wait_for('message', check=check), timeout=60)

# It returns None on timeout instead of raising an exception
if response is None:
    await ctx.send("You took too long to respond!")
else:
    await ctx.send(f"You said: {response.content}")
```

### 3. Starting the Bot

Use the run_bot function instead of directly calling bot.start():

```python
if __name__ == "__main__":
    # Instead of asyncio.run() or loop.run_until_complete()
    discord_asyncio_fix.run_bot(bot, TOKEN)
```

### 4. Timeouts in General

If you need to use timeouts elsewhere, import and use with_timeout:

```python
from discord_asyncio_fix import with_timeout

async def some_function():
    try:
        result = await with_timeout(some_async_function(), timeout_seconds=10)
        # Process result
    except asyncio.TimeoutError:
        # Handle timeout
```

## Common Issues Fixed

This solution addresses:

1. **"Timeout context manager should be used inside a task" errors**
   - This happens when asyncio.timeout() is used directly in coroutines
   - Our fix ensures proper task context for all timeout operations

2. **"asyncio.run() cannot be called from a running event loop" errors**
   - This happens when trying to use asyncio.run() while a loop is running
   - Our fix detects loop state and uses the appropriate approach

3. **"This event loop is already running" errors**
   - Our fix ensures we never try to run a new event loop when one is already running

## Migrating From Old Code

If you previously used other fixes (e.g., fix_timeout_errors, asyncio_runner, etc.), here's how to migrate:

1. Replace imports:
   ```python
   # OLD
   import fix_timeout_errors
   import asyncio_runner
   from timeout_handlers import wait_for_safe
   
   # NEW
   import discord_asyncio_fix
   from discord_asyncio_fix import safe_wait_for
   ```

2. Replace wait_for calls:
   ```python
   # OLD
   response = await wait_for_safe(bot.wait_for('message', check=check), timeout=60)
   
   # NEW
   response = await safe_wait_for(bot.wait_for('message', check=check), timeout=60)
   ```

3. Replace bot startup:
   ```python
   # OLD
   if __name__ == "__main__":
       loop = asyncio.get_event_loop()
       loop.run_until_complete(bot.start(TOKEN))
   
   # NEW
   if __name__ == "__main__":
       discord_asyncio_fix.run_bot(bot, TOKEN)
   ```

## Development Guidelines

1. Always import discord_asyncio_fix first in any file where you need asyncio features
2. Always use safe_wait_for for all wait_for operations
3. Never use asyncio.run() - use discord_asyncio_fix.run_without_event_loop_conflict instead
4. Never access or manipulate event loops directly
5. For any timeout operation, ensure it's within a proper task context

Following these guidelines will ensure your Discord.py application remains stable and free from asyncio-related errors.