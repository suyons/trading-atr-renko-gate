#!/bin/bash

# Setup script to configure cron job for trading bot

# Get the absolute path of the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_SCRIPT="$PROJECT_DIR/start_trading_bot.sh"

echo "Setting up trading bot cron job..."
echo "Project directory: $PROJECT_DIR"

# Make the runner script executable
chmod +x "$RUNNER_SCRIPT"
echo "Made start_trading_bot.sh executable"

# Create a temporary cron job file
TEMP_CRON_FILE=$(mktemp)

# Get current crontab (if any) and add our job
crontab -l 2>/dev/null > "$TEMP_CRON_FILE"

# Remove any existing trading bot cron jobs
crontab -r 2>/dev/null
if [ $? -eq 0 ]; then
    echo "Removed existing cron jobs"
else
    echo "No existing cron jobs found"
fi

# Add new cron job to run every 4 hours in UTC
echo "CRON_TZ=UTC" > "$TEMP_CRON_FILE"
echo "*/1 * * * * $RUNNER_SCRIPT" >> "$TEMP_CRON_FILE"

# Install the new crontab
crontab "$TEMP_CRON_FILE"

# Clean up
rm "$TEMP_CRON_FILE"

echo "Cron job installed successfully!"
