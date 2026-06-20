"""Exchange selection. `create_exchange()` builds the venue named by EXCHANGE.

Env:
  EXCHANGE         gate | binance        (default: gate)
  TRADING_MODE     LIVE | TEST           (default: TEST)
  <PREFIX>_API_KEY / <PREFIX>_API_SECRET   where PREFIX is GATE or BINANCE
                                           and the _LIVE / _TEST suffix follows mode
Gate also reads GATE_URL_HOST_LIVE / GATE_URL_HOST_TEST for the API host.
"""
import os

from exchange.base import Exchange
from exchange.gate import GateExchange
from exchange.binance import BinanceExchange


def _key_secret(prefix: str, is_live: bool):
    suffix = "LIVE" if is_live else "TEST"
    return (
        os.getenv(f"{prefix}_API_KEY_{suffix}") or os.getenv(f"API_KEY_{suffix}"),
        os.getenv(f"{prefix}_API_SECRET_{suffix}") or os.getenv(f"API_SECRET_{suffix}"),
    )


def create_exchange(symbol_list: list[str]) -> Exchange:
    name = os.getenv("EXCHANGE", "gate").strip().lower()
    mode = os.getenv("TRADING_MODE") or os.getenv("GATE_TRADING_MODE") or "TEST"
    is_live = mode.strip().upper() == "LIVE"

    if name == "gate":
        host = os.getenv("GATE_URL_HOST_LIVE") if is_live else os.getenv("GATE_URL_HOST_TEST")
        key, secret = _key_secret("GATE", is_live)
        return GateExchange(symbol_list, host=host, api_key=key, api_secret=secret)

    if name == "binance":
        key, secret = _key_secret("BINANCE", is_live)
        network = "mainnet" if is_live else "testnet"
        return BinanceExchange(symbol_list, network=network, api_key=key, api_secret=secret)

    raise ValueError(f"Unknown EXCHANGE '{name}' (expected: gate | binance)")
