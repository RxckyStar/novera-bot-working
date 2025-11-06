# Novera Assistant Discord Bot Reliability Guide

This guide explains how to run the Novera Assistant Discord bot with maximum reliability. The bot has been configured with comprehensive stability fixes to prevent common Discord.py issues.

## Issues Addressed

1. **Timeout Context Manager Issues**: Fixed the "Timeout context manager should be used inside a task" error
2. **Event Loop Conflicts**: Fixed the "asyncio.run() cannot be called from a running event loop" error
3. **Connection Reliability**: Added a two-step connection approach with proper error handling
4. **Safe Shutdown**: Implemented proper cleanup to prevent orphaned processes and tasks
5. **Automatic Recovery**: Added monitoring and auto-restart capabilities

## Running the Bot Reliably

### Option 1: Direct Execution (Recommended for Development)

The most reliable way to run the bot is with the new run_bot.py script:

```bash
python run_bot.py
```

This script:
- Uses a clean event loop 
- Implements the proven two-step connection approach
- Includes proper exception handling
- Sets up detailed logging

### Option 2: Continuous Operation (Recommended for Production)

For continuous operation with automatic restart capabilities, use the NEVER_DOWN.sh script:

```bash
chmod +x NEVER_DOWN.sh
./NEVER_DOWN.sh
```

This script:
- Continuously monitors the bot's health
- Automatically restarts the bot if it goes down
- Maintains detailed logs
- Applies a maximum retry policy to prevent infinite restart loops

### Option 3: Legacy Method (Not Recommended)

The original bot.py can still be run directly, but it doesn't include all the reliability improvements:

```bash
python bot.py
```

## Troubleshooting

If you encounter connection issues:

1. **Check the Discord token**: Ensure your DISCORD_TOKEN in .env is valid
2. **Verify internet connectivity**: The bot needs reliable internet to connect to Discord
3. **Check for rate limiting**: If restarting too frequently, Discord may rate-limit connections
4. **Review logs**: Check bot_runner.log or bot_startup.log for specific errors

## Architecture

The solution uses a multi-layered reliability approach:

1. **Core Fixes (discord_asyncio_fix.py)**: Patches Discord.py's asyncio implementation
2. **Safe Runner (run_bot.py)**: Implements a reliable startup sequence
3. **Monitoring (NEVER_DOWN.sh)**: Provides continuous operation with health checks

## How This Solution Works

The solution uses a two-step connection approach:
1. **Login**: First authenticate with Discord's API
2. **Connect**: Then establish the gateway connection

By separating these steps and implementing them with proper asyncio handling, we avoid the common timeout and event loop issues that plague many Discord.py bots.

The monitoring script provides an additional layer of resilience by automatically restarting the bot if it loses connection to Discord.

## Further Improvements

For even more reliability, consider:
- Setting up automated Replit pings to keep the project alive
- Implementing Discord webhook alerts for critical errors
- Adding more detailed telemetry to the health check endpoint