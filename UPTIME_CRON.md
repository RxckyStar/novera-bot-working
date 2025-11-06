# Setting Up Cron Jobs for 99.99% Uptime

This guide explains how to set up a cron job to regularly check your Discord bot's health and automatically restart it if it's down, ensuring maximum uptime.

## Endpoint Details

The bot has a dedicated cron-friendly endpoint that:
1. Checks if the bot is connected to Discord
2. Automatically restarts the bot if it's not connected
3. Returns a simple JSON response about the current status

**Endpoint URL:** `/cron`

## Response Format

When the bot is healthy:
```json
{
  "bot_connected": true,
  "status": "ok",
  "uptime": 3600
}
```

When the bot is unhealthy and being restarted:
```json
{
  "status": "restarting",
  "message": "Bot was down - restart initiated"
}
```

## Setting Up a Cron Job

### Using an External Cron Service (Recommended)

For maximum reliability, use an external service to monitor your bot:

1. **Cron-job.org**
   - Sign up at https://cron-job.org
   - Create a new cronjob
   - Set the URL to `https://YOUR-REPLIT-NAME.replit.app/cron`
   - Set the execution schedule to every 5 minutes
   - Enable "Save response" to track history

2. **UptimeRobot**
   - Sign up at https://uptimerobot.com
   - Add a new HTTP monitor
   - Set the URL to `https://YOUR-REPLIT-NAME.replit.app/cron`
   - Set the monitoring interval to 5 minutes
   - Add a notification if needed

3. **Freshping**
   - Sign up at https://www.freshworks.com/website-monitoring
   - Add a new check
   - Enter your bot's URL: `https://YOUR-REPLIT-NAME.replit.app/cron`
   - Set check frequency to 5 minutes

### Using Your Own Server

If you have your own server, you can set up a cron job:

**Linux/Mac:**
```bash
# Open crontab for editing
crontab -e

# Add this line to run every 5 minutes
*/5 * * * * curl -s https://YOUR-REPLIT-NAME.replit.app/cron > /dev/null 2>&1
```

**Windows (using Task Scheduler):**
1. Open Task Scheduler
2. Create a new Basic Task
3. Set it to run every 5 minutes
4. Action: Start a program
5. Program/script: `curl` or `powershell`
6. Arguments: `-s https://YOUR-REPLIT-NAME.replit.app/cron` (for curl) or 
   `Invoke-WebRequest -Uri https://YOUR-REPLIT-NAME.replit.app/cron` (for PowerShell)

## Testing Your Cron Job

To verify your cron job is working:
1. Visit `https://YOUR-REPLIT-NAME.replit.app/healthz` to check current status
2. Manually trigger your cron job
3. Check the logs for "Heartbeat updated" messages

## Best Practices

1. **Multiple Monitors**: Set up 2-3 different monitoring services for redundancy
2. **Different Intervals**: Use slightly different intervals (4, 5, and 6 minutes) to prevent simultaneous calls
3. **Log Reviews**: Periodically check the bot's logs for restart patterns
4. **Status Page**: Consider setting up a status page using the `/healthz` endpoint data

## Troubleshooting

If your cron job isn't working:
1. Check the URL is correct (including https://)
2. Verify the endpoint returns a 200 status code
3. Check if your IP might be rate-limited
4. Ensure your Replit project is on a paid plan to avoid sleep mode

For any persistent issues, check the bot's logs for error messages.