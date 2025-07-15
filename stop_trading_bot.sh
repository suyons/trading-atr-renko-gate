#!/bin/bash

# Stop Trading Bot Script

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/trading_bot_runner.log"
PID_FILE="$SCRIPT_DIR/trading_bot.pid"

# Function to log messages
log_message() {
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC'): $1" >> "$LOG_FILE"
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC'): $1"
}

log_message "Stopping trading bot..."

# Try to kill using PID file first
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        log_message "Killed trading bot process with PID: $PID"
        rm "$PID_FILE"
    else
        log_message "Process with PID $PID not found, removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# Kill any remaining Python processes running main.py
pkill -f "python.*main.py" 2>/dev/null
if [ $? -eq 0 ]; then
    log_message "Killed additional trading bot processes"
else
    log_message "No additional trading bot processes found"
fi

log_message "Trading bot stop process completed"
