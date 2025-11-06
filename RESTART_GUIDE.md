# Bot Restart Guide

If you're experiencing issues with the Discord bot, follow this guide to restart it properly.

## Option 1: Use the Workflow Interface (Recommended)

1. Go to the Workflows tab in the Replit interface
2. Click on the "Discord Bot" workflow
3. Click "Stop" if it's running
4. Wait a few seconds
5. Click "Run" to start it again

## Option 2: Use the Recovery Script

If the bot is stuck or not responding, you can use the recovery script:

```bash
# Stop all Python processes
pkill -f python

# Clear out any lock files
rm -f *.lock

# Start the bot with the simplified runner
python run_bot.py
```

## Option 3: Manual Restart with Fixes

If the above options don't work, try this full reset:

```bash
# Kill all Python processes
pkill -f python

# Remove any lock files
rm -f *.lock

# Start the bot using the original file with fixes
python bot.py
```

## If All Else Fails

1. Make a full reset of the Replit environment
2. Start the bot with `python bot.py`

## Common Issues and Solutions

### Timeout Context Manager Errors

If you see errors like "Timeout context manager should be used inside a task", it means the event loop management is not working correctly. Make sure you're using the proper startup methods shown in the HOW_WE_FIXED_EVENT_LOOP_ERRORS.md file.

### Bot Not Responding to Commands

Check the logs for any connection errors. Sometimes the Discord gateway needs a few minutes to fully connect.

### Flask Web Server Issues

The bot runs a Flask web server for monitoring. If this crashes, it can sometimes affect the bot. Restarting should fix this.

### Authentication Failures (401 Errors)

If you see 401 Unauthorized errors, it might mean the Discord token needs to be refreshed. Contact the administrator to update the token.