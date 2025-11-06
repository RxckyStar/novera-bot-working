# Discord Bot Token Recovery Guide

If the bot is down due to token issues, follow these recovery procedures.

## Automatic Recovery

The bot is equipped with an ultra-aggressive autonomous recovery system that should automatically detect and fix authentication failures. This includes:

- Detecting 401 errors in real-time
- Cleaning and validating token format
- Restoring from backup token sources
- Restarting the bot when necessary

In most cases, **you don't need to do anything** as the recovery system will handle authentication issues automatically.

## Manual Recovery Methods

If the automatic recovery fails, you can try these manual recovery steps:

### 1. Check Token Validity

```bash
python -c "import config; print(config.validate_token(config.get_token()))"
```

This should output `True` if the token is valid.

### 2. Force Token Refresh

The system will automatically attempt to refresh the token, but you can force it with:

```bash
./auto_401_recovery.py --force
```

### 3. Update Token in .env File

If you have a new token from Discord:

1. Edit the `.env` file:
   ```
   nano .env
   ```

2. Update the DISCORD_TOKEN:
   ```
   DISCORD_TOKEN=your_new_token_here
   ```

3. Save and restart the bot:
   ```
   ./absolute_uptime.sh
   ```

### 4. Check Bot Status

To check if the bot is running and connected:

```bash
./check_status.sh
```

Look for "Bot Health API: HEALTHY" in the output.

## Recovery Process Details

The token recovery system uses these sources in order:

1. Environment variable (DISCORD_TOKEN)
2. .env file
3. Token cache file

## Troubleshooting Authentication Issues

If authentication issues persist:

1. **Generate a new token** in the Discord Developer Portal
2. **Format issues**: Ensure the token doesn't have quotes, extra spaces, or non-printable characters
3. **Permission issues**: Verify the bot has the required permissions
4. **Rate limiting**: If Discord is rate-limiting your requests, the system will automatically back off

## Need More Help?

If all recovery attempts fail, please contact the bot administrator with the following information:

1. Output of `./check_status.sh`
2. Last 20 lines from auto_401_recovery.log:
   ```
   tail -n 20 auto_401_recovery.log
   ```