# ATR Renko Trading Strategy

An automated trading bot that utilizes Renko charts with ATR-based brick sizing to generate trading signals and execute trades on cryptocurrency exchanges via [ccxt](https://github.com/ccxt/ccxt).

## Features

- **ATR-based Renko Bricks:** Dynamically calculates Renko brick size using the Average True Range (ATR) for adaptive trend detection.
- **Real-time Data:** Fetches live trade data via WebSocket for accurate and timely Renko brick formation.
- **Automated Trading:** Executes buy/sell orders based on Renko brick patterns (e.g., 3 consecutive bricks in the same direction).
- **Configurable:** All key parameters (API keys, symbol, ATR period, trade amount, etc.) are managed via environment variables.
- **Logging:** Logs all trading activity and errors to both the console and daily log files.

## How It Works

1. **Historical Data Load:** Loads historical OHLCV data to initialize ATR and Renko brick size.
2. **Real-time Processing:** Listens to live trades, updates Renko bricks, and checks for trading signals.
3. **Trading Logic:** Opens or closes positions based on consecutive Renko brick patterns.

## Project Structure

```
.
├── .env.example           # Example environment variables
├── README.md
├── logs/                  # Log files
├── src/
│   ├── main.py            # Entry point
│   ├── config/
│   │   ├── env_config.py
│   │   └── ...
│   └── service/
│       ├── renko_calculator.py
│       └── ...
└── ...
```

## Getting Started

### 1. Clone the repository

```sh
git clone https://github.com/suyons/trading-strategy-atr-renko
cd trading-strategy-atr-renko
```

### 2. Install dependencies

```sh
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env`:

```sh
cp .env.example .env
```

Fill in your API keys and desired parameters:

```
API_KEY=your_api_key_here
SECRET_KEY=your_secret_key_here
SYMBOL=ETH/USDT:USDT
ATR_PERIOD=14
OHLCV_TIMEFRAME=1m
INITIAL_OHLCV_LIMIT=10000
TRADE_AMOUNT=1
```

### 4. Run the main script

```sh
python src/main.py
```

Or you can run it through watchdog for automatic reloading on changes:

```sh
run.cmd
```

## Disclaimer

This project is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk of loss.
