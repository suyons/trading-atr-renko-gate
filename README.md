# Trading Strategy: ATR Renko (Gate / Binance)

An automated trading bot that uses Renko charts with ATR-based brick sizing to
generate signals and execute crypto-futures trades. Runs on **Gate.io** or
**Binance USDT-M (testnet)** through a one-file exchange adapter, with an
optional LLM veto on reversals.

## Features

- **ATR-based Renko bricks:** brick size from the Average True Range for adaptive trend detection.
- **Real-time:** polls live price via REST **every second** for timely brick formation; trades on a brick direction reversal (close-and-reverse).
- **Pluggable exchange:** `Gate` and `Binance testnet` behind one `Exchange` interface — switch with `EXCHANGE=gate|binance`, no code change. Add a venue = one file in `src/exchange/`.
- **Optional LLM filter:** a runtime-agnostic veto on reversals (`FILTER_AGENT_CMD`, e.g. `claude -p`) that can skip likely false signals from sideways chop. Opt-in (unset/empty = off); fails open.
- **Configurable:** all parameters via environment variables.
- **Logging:** console, daily log files, and Discord.

## How it works

1. **Historical load:** fetch OHLCV to initialize ATR and brick size.
2. **Real-time:** poll price each second, update Renko bricks.
3. **Trading:** on a brick **direction reversal**, optionally ask the LLM filter, then close any opposite position and open the new side.

## Architecture

```
main.py ─▶ Exchange (src/exchange/{gate,binance}.py)  ─▶ Gate / Binance API
   │           selected by EXCHANGE env via create_exchange()
   ├─▶ RenkoCalculator ─▶ signal_filter.py (optional LLM veto, FILTER_AGENT_CMD)
   └─▶ OrderHandler ─▶ Exchange  (sizing in integer "units"; adapter converts to native)
```

Order size is expressed in integer *units* (1 unit = Gate `quanto_multiplier` /
Binance lot `stepSize`); each adapter converts units ↔ native size, so the
sizing logic is venue-neutral.

## Project structure

```
.
├── pyproject.toml / uv.lock   # uv project + locked deps
├── .env.example
├── src/
│   ├── main.py                # live entry point (1s polling loop)
│   ├── start_backtest.py      # offline backtest from data/*.csv
│   ├── exchange/              # Exchange interface + gate/binance adapters
│   ├── service/
│   │   ├── renko_calculator.py
│   │   ├── order_handler.py
│   │   ├── signal_filter.py   # optional LLM reversal veto
│   │   └── discord_client.py
│   └── backtest/
└── data/                      # CSV history for backtest
```

## Getting started

This project uses [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/suyons/trading-strategy-atr-renko
cd trading-strategy-atr-renko
uv sync                    # create .venv and install locked deps
cp .env.example .env       # then fill in keys + parameters
uv run python src/main.py  # live trader
```

Backtest (offline, from `data/*.csv`): `uv run python src/start_backtest.py`.
Self-check (no keys/network): `uv run python src/test_modernization.py`.

## Configuration (`.env`)

| Variable | Meaning |
|----------|---------|
| `EXCHANGE` | `gate` or `binance` |
| `TRADING_MODE` | `TEST` (testnet/demo) or `LIVE` (real money) |
| `GATE_URL_HOST_LIVE` / `GATE_URL_HOST_TEST` | Gate API host (Gate only) |
| `GATE_API_KEY_*` / `BINANCE_API_KEY_*` (+ `_SECRET_`) | keys per exchange and mode |
| `SYMBOL_LIST`, `OHLCV_TIMEFRAME`, `ATR_PERIOD`, `OHLCV_COUNT`, `LEVERAGE` | strategy params |
| `FILTER_AGENT_CMD` | LLM filter command (e.g. `claude -p`). Opt-in; unset/empty disables it. |
| `DISCORD_WEBHOOK_URL_*` | notifications |

## Disclaimer

For educational purposes only. Use at your own risk. Cryptocurrency trading
involves significant risk of loss.
