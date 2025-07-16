#!/bin/bash

# Trading Bot Runner Script
# This script stops any existing instance and starts a new one

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to log messages
log_message() {
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC'): $1"
}

log_message "Starting trading bot restart process..."

PID_FILE="$SCRIPT_DIR/trading_bot.pid"

# Kill any existing Python processes running main.py
if [ -f "$PID_FILE" ]; then
    EXISTING_PID=$(cat "$PID_FILE")
    if kill -0 $EXISTING_PID 2>/dev/null; then
        log_message "Killing existing trading bot process with PID: $EXISTING_PID"
        kill $EXISTING_PID
        sleep 2
    else
        log_message "No existing trading bot process found with PID: $EXISTING_PID"
    fi
    rm "$PID_FILE"
else
    log_message "No PID file found. Assuming no existing process."
fi

# Change to project directory
cd "$SCRIPT_DIR"

# Start the trading bot in the background
# set PATH to include the Python environment
export PATH="/opt/homebrew/Caskroom/miniconda/base/envs/trading/bin:$PATH"
nohup python "$SCRIPT_DIR/src/main.py" >> "$SCRIPT_DIR/logs/trading_bot.log" 2>&1 &
BOT_PID=$!

if [ $? -eq 0 ]; then
    log_message "Trading bot started successfully with PID: $BOT_PID"
    echo $BOT_PID > "$SCRIPT_DIR/trading_bot.pid"
else
    log_message "ERROR: Failed to start trading bot"
    exit 1
fi

log_message "Trading bot restart process completed"
