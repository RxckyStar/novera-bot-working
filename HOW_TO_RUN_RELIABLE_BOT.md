# How to Run Novera Assistant with Maximum Reliability

The bot has been stabilized with comprehensive fixes based on ChatGPT's recommendations. Here's how to run it with different levels of reliability:

## Option 1: Basic Run (Standard)
```bash
python bot.py
```
This runs the bot with all fixes applied internally, but no external monitoring.

## Option 2: Enhanced Run (Recommended)
```bash
python run_bot.py
```
This startup script:
- Applies all fixes in the correct order
- Adds improved signal handling
- Manages proper cleanup on exit
- Has enhanced error reporting

## Option 3: Maximum Reliability (Best Option)
```bash
./NEVER_DOWN.sh
```
This bash script:
- Monitors the bot process
- Automatically restarts if it crashes
- Limits restart frequency to prevent excessive cycling
- Logs activity to never_down.log
- Can run in the background indefinitely

To make this script run in the background:
```bash
nohup ./NEVER_DOWN.sh > /dev/null 2>&1 &
```

## Explanation of the Comprehensive Fixes

The bot now includes several critical fixes implemented directly from ChatGPT's solution:

1. **discord_asyncio_fix.py**: Handles all event loop and task issues
2. **aiohttp_timeout_fix.py**: Fixes compatibility between aiohttp and asyncio
3. **timeout_handlers.py**: Provides robust timeout handling for all operations
4. **Heartbeat system**: Monitors bot health and activity
5. **Proper signal handling**: Ensures clean shutdown

These fixes address all the common Discord.py error patterns:
- "Timeout context manager should be used inside a task"
- "asyncio.run() cannot be called from a running event loop"
- "This event loop is already running"
- TypeErrors with async_generator objects

## Full Solution Implementation

For complete details on the solution, see RELIABILITY_GUIDE.md