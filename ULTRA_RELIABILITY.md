# ULTRA RELIABILITY GUIDE

## How to Ensure Your Bot Never Goes Down

The Novera Assistant Discord Bot has been configured with several reliability features to ensure it stays up 24/7. Here's how to use them:

### Standard Operation

For normal operation, simply restart the workflow in the Replit interface.

1. Go to your Replit project
2. Use the "Discord Bot" workflow

This is usually sufficient for regular operation.

### Recovery From Crashes

If the bot crashes or goes offline, there are multiple ways to recover:

#### Method 1: Quick Restart

Run the start_bot.sh script:

```
./start_bot.sh
```

This will:
- Stop any existing bot processes
- Start a fresh instance
- Verify the bot is running

#### Method 2: Bulletproof Mode

For enhanced reliability, use the bulletproof script:

```
./bulletproof.sh
```

This script will:
- Check for authentication errors
- Start the bot if it's not running
- Monitor the bot for 60 seconds, restarting it if needed

#### Method 3: Absolute Uptime (Maximum Reliability)

For mission-critical 24/7 operation, use the absolute uptime script:

```
nohup ./absolute_uptime.sh &
```

This will start a permanent monitoring process that:
- Checks the bot status every 10 seconds
- Automatically restarts the bot if it crashes
- Continues monitoring until the Replit instance is shut down

#### Method 4: Ultra-Aggressive 401 Recovery

If the bot encounters frequent 401 authentication errors, use:

```
python auto_401_recovery.py
```

This aggressively monitors for auth failures and performs token refresh operations.

### Monitoring Bot Health

You can check the bot's health at any time by accessing:

```
curl http://localhost:5001/healthz
```

A healthy response will show:
```json
{"status": "healthy", "bot_connected": true, ...}
```

### Maintenance Tips

1. Regularly check the logs with: `tail -f bot.log`
2. Monitor the webhook connection with: `curl http://localhost:5001/monitor`
3. After making code changes, restart the bot with: `./start_bot.sh`

By following these guides, you'll ensure your Novera Assistant Discord Bot maintains premium uptime and reliability.