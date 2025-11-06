# timeout_utils.py
import asyncio

async def safe_timeout(coro, timeout_seconds=10):
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