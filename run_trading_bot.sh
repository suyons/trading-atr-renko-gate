#!/bin/bash

# Trading Bot Runner Script
# This script stops any existing instance and starts a new one

# Set timezone to UTC
export TZ=UTC

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Log file
LOG_FILE="$SCRIPT_DIR/logs/trading_bot_runner.log"

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"

# Function to log messages
log_message() {
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC'): $1" >> "$LOG_FILE"
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC'): $1"
}

log_message "Starting trading bot restart process..."

# Kill any existing Python processes running main.py
pkill -f "python.*main.py" 2>/dev/null
if [ $? -eq 0 ]; then
    log_message "Killed existing trading bot process"
    sleep 2
else
    log_message "No existing trading bot process found"
fi

# Change to project directory
cd "$SCRIPT_DIR"

# Initialize conda (this is needed for conda activate to work in scripts)
eval "$(conda shell.bash hook)"

# Activate the trading environment
conda activate trading
if [ $? -ne 0 ]; then
    log_message "ERROR: Failed to activate conda environment 'trading'"
    exit 1
fi

log_message "Activated conda environment 'trading'"

# Start the trading bot in the background
nohup python src/main.py >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

if [ $? -eq 0 ]; then
    log_message "Trading bot started successfully with PID: $BOT_PID"
    echo $BOT_PID > "$SCRIPT_DIR/trading_bot.pid"
else
    log_message "ERROR: Failed to start trading bot"
    exit 1
fi

log_message "Trading bot restart process completed"
