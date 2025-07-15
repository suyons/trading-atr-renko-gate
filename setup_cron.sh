#!/bin/bash

# Setup script to configure cron job for trading bot

# Get the absolute path of the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_SCRIPT="$PROJECT_DIR/run_trading_bot.sh"

echo "Setting up trading bot cron job..."
echo "Project directory: $PROJECT_DIR"

# Make the runner script executable
chmod +x "$RUNNER_SCRIPT"
echo "Made run_trading_bot.sh executable"

# Create a temporary cron job file
TEMP_CRON_FILE=$(mktemp)

# Get current crontab (if any) and add our job
crontab -l 2>/dev/null > "$TEMP_CRON_FILE"

# Remove any existing trading bot cron jobs
sed -i '/run_trading_bot.sh/d' "$TEMP_CRON_FILE"

# Add new cron job to run every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)
echo "0 */4 * * * $RUNNER_SCRIPT" >> "$TEMP_CRON_FILE"

# Install the new crontab
crontab "$TEMP_CRON_FILE"

# Clean up
rm "$TEMP_CRON_FILE"

echo "Cron job installed successfully!"

# Start the bot immediately in the current session
echo "Starting trading bot immediately..."
"$RUNNER_SCRIPT"

echo ""
echo "Trading bot is now running!"
echo "The bot will also run automatically every 4 hours at: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC"
echo ""
echo "To verify the cron job was installed, run: crontab -l"
echo "To stop the current bot session, use Ctrl+C"
echo "To remove the cron job, run: crontab -e (and delete the line containing run_trading_bot.sh)"
echo ""
echo "Logs will be saved to: $PROJECT_DIR/logs/trading_bot_runner.log"
