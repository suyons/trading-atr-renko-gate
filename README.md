# Trading Strategy: ATR Renko (Gate.com)

An automated trading bot that utilizes Renko charts with ATR-based brick sizing to generate trading signals and execute trades on [Gate.com](https://www.gate.com/).

## Features

- **ATR-based Renko Bricks:** Dynamically calculates Renko brick size using the Average True Range (ATR) for adaptive trend detection.
- **Real-time Data:** Fetches live trade data via REST API secondly for timely Renko brick formation.
- **Automated Trading:** Executes buy/sell orders based on Renko brick patterns (e.g., brick directions switch).
- **Configurable:** All key parameters (API keys, symbol, ATR period, trade amount, etc.) are managed via environment variables.
- **Logging:** Logs all trading activity and errors to both the console and daily log files, and discord.

## How It Works

1. **Historical Data Load:** Loads historical OHLCV data to initialize ATR and Renko brick size.
2. **Real-time Processing:** Listens to live trades, updates Renko bricks, and checks for trading signals.
3. **Trading Logic:** Opens or closes positions based on Renko brick patterns.

## Project Structure

```
.
├── .env.example           # Example environment variables
├── README.md
├── logs/                  # Log files
├── src/
│   ├── main.py            # Entry point
│   ├── config/
│   │   ├── logger_config.py
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

Fill in your API keys and desired parameters

### 4. Run the main script

```sh
python src/main.py
```

## Disclaimer

This project is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk of loss.
