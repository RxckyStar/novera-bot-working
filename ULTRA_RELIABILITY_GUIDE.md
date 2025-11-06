# Ultra-Reliability System for Discord Bot

This system is designed to ensure your Discord bot **never** goes offline and runs with maximum uptime, just like professional Discord bots. It includes multiple layers of reliability, automatic recovery, and self-healing capabilities.

## Features

- **Automated Monitoring**: Continuously monitors bot health and status
- **Self-Healing**: Automatically detects and fixes issues
- **Crash Recovery**: Instantly restarts the bot if it crashes
- **Token Management**: Handles token refresh and authentication issues
- **Resource Management**: Monitors memory usage and prevents resource exhaustion
- **Cron Integration**: Runs periodic checks to ensure continuous operation

## Getting Started

1. **One-time setup**: Run the setup script to install the cron job

```bash
./setup_bot_cron.sh
```

2. **Start the bot**: Start the Ultra-Reliability System

```bash
./start_ultra_reliable_bot.sh
```

3. **That's it!** Your bot will now run continuously and recover automatically from any issues

## How It Works

The Ultra-Reliability System provides multiple layers of protection:

1. **Primary Layer**: The bot's internal error handling and recovery
2. **Secondary Layer**: The `ultra_reliability.py` monitoring process checks health and restarts if needed
3. **Tertiary Layer**: A cron job runs every 5 minutes to ensure the monitoring process itself is running
4. **Background Processes**: Token refresh, memory monitoring, and other specialized recovery mechanisms

## Logs and Monitoring

- **Main log**: `ultra_reliability.log` contains detailed information
- **Start log**: `ultra_start.log` tracks when the system was started
- **Auto-restart log**: `auto_restart.log` records when cron restarts the system
- **Status file**: `ultra_reliability_status.json` contains the current system status

## Customization

You can customize the reliability settings by editing `ultra_reliability.py`:

- `CHECK_INTERVAL`: How frequently to check the bot's health (seconds)
- `RESTART_COOLDOWN_BASE`: Minimum time between restart attempts (seconds)
- `MAX_RESTART_COOLDOWN`: Maximum time between restart attempts (seconds)
- `MAX_MEMORY_MB`: Maximum allowed memory usage (MB)

## Troubleshooting

If you experience any issues:

1. Check the logs in `ultra_reliability.log`
2. Ensure all scripts are executable (`chmod +x script_name.sh`)
3. Make sure the Discord bot token is valid
4. Verify that port 5001 is available for the health endpoint

## Advanced Usage

### Manual Restart

To manually restart the entire system:

```bash
pkill -f "python.*ultra_reliability.py"
./start_ultra_reliable_bot.sh
```

### Checking Status

To check the current status:

```bash
cat ultra_reliability_status.json
```

### Disabling Cron Job

To disable the automatic cron checks:

```bash
crontab -l | grep -v "ensure_bot_running.sh" | crontab -
```

## System Requirements

- Python 3.6 or higher
- Discord.py library
- psutil library
- requests library
