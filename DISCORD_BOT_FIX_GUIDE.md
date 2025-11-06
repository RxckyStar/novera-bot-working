# Discord Bot Fix Guide

## Problem Solved
We fixed the Discord bot crashing with these errors:
- `RuntimeError: asyncio.run() cannot be called from a running event loop`
- `RuntimeError: Timeout context manager should be used inside a task`

## The Root Cause
The core issue was using the wrong event loop management approach. Specifically:
1. Using `asyncio.run()` in an environment where a loop was already running
2. Using `asyncio.timeout()` outside of task contexts
3. Having multiple conflicting solutions trying to fix the same problem

## The Solution
We implemented a simple, direct approach that follows best practices:

```python
# Get the current event loop
loop = asyncio.get_event_loop()

# Define a simple bot runner function
async def run_bot():
    try:
        await bot.start(token)
    except Exception as e:
        logging.error(f"Error in bot.start: {e}")
        
# CRITICAL FIX: Check if loop is running and use correct approach
if loop.is_running():
    logging.info("Event loop is already running, using create_task")
    # This is the key fix - create a task instead of trying to manage the loop
    task = loop.create_task(run_bot())
else:
    logging.info("No event loop running, using run_until_complete")
    loop.run_until_complete(run_bot())
```

## Key Principles
1. NEVER use `asyncio.run()` when a loop might already be running
2. Use `loop.create_task()` when the loop is already running
3. Use `loop.run_until_complete()` when no loop is running
4. Use `asyncio.wait_for()` instead of `asyncio.timeout()` for timeouts
5. Keep event loop management simple and consistent

## For Timeouts
When you need timeout functionality, use this pattern:

```python
async def safe_timeout(coro, timeout_seconds):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        # Handle timeout gracefully
        return None
```

## Files We Modified
- Modified `bot.py` to use the correct event loop approach
- Created `safe_timeout.py` for proper timeout handling
- Created documentation explaining the fix

## Future Recommendations
1. Avoid multiple event loop management methods
2. Don't use complex patches or monkey-patching for asyncio
3. Keep the startup code simple and focused
4. Test changes in the actual environment (Replit) before deploying