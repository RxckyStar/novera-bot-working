# Critical Asyncio Error Prevention

## Common Errors & Fixes

### 1. RuntimeError: asyncio.run() cannot be called from a running event loop

This happens when trying to call `asyncio.run()` inside an already running event loop, particularly in bot.py when attempting to start the Discord bot.

### 2. RuntimeError: Timeout context manager should be used inside a task

This occurs when using asyncio timeouts outside of a proper task context.

## How We Fixed It

Instead of using `nest_asyncio` (which can cause other issues), we implemented robust solutions in:
- `task_wrapper.py` - Added `run_with_task_context()` function
- `timeout_handlers.py` - Enhanced `safe_task` and `ensure_proper_startup` decorators

## IMPORTANT: DO NOT CHANGE THIS APPROACH

If making changes to the bot startup code or asyncio-related functionality:

1. **NEVER** directly call `bot.run(TOKEN)` in environments with existing event loops
2. **ALWAYS** use our helper functions from task_wrapper.py:
   ```python
   from task_wrapper import run_with_task_context
   
   # Use this pattern:
   async def start_bot():
       await bot.start(TOKEN)
       
   run_with_task_context(start_bot())
   ```

3. **ALWAYS** wrap timeout operations in proper task context:
   ```python
   from timeout_handlers import safe_task
   
   @safe_task
   async def my_function_with_timeouts():
       async with asyncio.timeout(10):
           # Your code here
   ```

## Testing Your Changes

After any changes to the bot startup or asyncio-related code:

1. Test that the bot starts properly with both Flask server running and Discord bot connected
2. Verify that commands using timeouts (like `!checkvalue`, `!eval`, etc.) work properly
3. Ensure that button interactions and modals respond correctly

### Last Fixed: April 15, 2025

If these issues return, refer to these files:
- `task_wrapper.py`
- `timeout_handlers.py`
- `bot.py` (startup section)
- `ASYNCIO_NOTES.md` (this file)

**DO NOT REVERT TO OLDER APPROACHES** - these fixes were specifically designed to handle Replit's environment.