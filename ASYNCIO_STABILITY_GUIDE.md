# Discord Bot Stability Guide: Fixing Asyncio and Timeout Issues

This document explains the comprehensive approach we've taken to fix stability issues with the Novera Assistant Discord bot.

## Core Stability Issues Fixed

1. **"Timeout context manager should be used inside a task" Error**
   - **Cause**: Using `asyncio.timeout()` directly in coroutines that are not properly wrapped in tasks
   - **Fix**: Implemented a `wait_for_safe` wrapper that properly runs timeouts within task contexts

2. **"This event loop is already running" Error**
   - **Cause**: Multiple attempts to start an event loop when one is already running
   - **Fix**: Implemented intelligent loop detection and proper startup approaches

3. **"asyncio.run() cannot be called from a running event loop" Error**
   - **Cause**: Using `asyncio.run()` within code that's already running in an event loop
   - **Fix**: Properly detecting loop state and using the appropriate approach (create_task vs run_until_complete)

## Key Components of the Solution

### 1. Safe Timeout Handling

The `timeout_handlers.py` module provides safe wrappers for timeout operations:

```python
async def with_timeout(coro: Coroutine[Any, Any, T], timeout_seconds: float = 10) -> T:
    """Run a coroutine with a timeout safely by ensuring it runs within a task."""
    task = asyncio.create_task(coro)
    try:
        async with asyncio.timeout(timeout_seconds):
            return await task
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        raise

async def wait_for_safe(coro: Coroutine[Any, Any, T], timeout: float) -> Optional[T]:
    """A simpler version that doesn't raise the timeout error, just returns None."""
    try:
        return await with_timeout(coro, timeout_seconds=timeout)
    except asyncio.TimeoutError:
        return None
```

### 2. Proper Event Loop Management

The bot startup code now uses the proper approach for detecting and managing event loops:

```python
def start_bot():
    """Start the Discord bot with proper event loop handling."""
    loop = asyncio.get_event_loop()
    
    async def run_bot():
        async with bot:
            await bot.start(TOKEN)
    
    if loop.is_running():
        # If we're already in an event loop, use create_task
        loop.create_task(run_bot())
    else:
        # Otherwise, run until complete
        loop.run_until_complete(run_bot())
```

### 3. Consistent Use of Safe Wrappers

All instances of `bot.wait_for` have been updated to use our safe wrapper:

```python
# Before:
response = await bot.wait_for('message', check=check, timeout=60)

# After:
response = await wait_for_safe(bot.wait_for('message', check=check), timeout=60)
```

## Maintenance Guidelines

1. **Never use direct `asyncio.timeout()` calls** - Always use `with_timeout` or `wait_for_safe`
2. **Never use `asyncio.run()`** - Use the proper event loop approach shown above
3. **Be careful with `bot.wait_for()`** - Always wrap with `wait_for_safe`
4. **Avoid competing fix solutions** - Stick with the approach in `timeout_handlers.py` and `discord_asyncio_fix.py`

## Testing Stability

The bot now includes a heartbeat system that regularly updates a timestamp. If the bot stops updating this timestamp, the monitoring system will detect it and restart the bot.

## Future Improvements

1. **Automatic Runtime Analysis**: Implement more sophisticated monitoring that can detect problematic patterns at runtime
2. **Static Analysis**: Use tools like mypy with asyncio plugins to catch potential asyncio issues during development
3. **Command Timeout Safety**: Apply timeout safety to all command handlers that might block for extended periods

---

These fixes provide a comprehensive solution to the asyncio-related stability issues. By following these guidelines, future development should maintain this stability.