"""Self-check for the modernized exchange + filter wiring.
Run: python3 src/test_modernization.py   (or: uv run python src/test_modernization.py)
Stubs all network, so it needs neither keys nor connectivity."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the whole graph — fails loudly if the rewiring broke an import.
from exchange import create_exchange  # noqa: F401
from exchange.base import OHLCV, Ticker, ContractInfo, Position, Exchange  # noqa: F401
from exchange.gate import GateExchange  # noqa: F401
from exchange.binance import BinanceExchange, _to_binance
from service import signal_filter
from service.order_handler import OrderHandler  # noqa: F401
from service.renko_calculator import RenkoCalculator  # noqa: F401
from backtest.simulated_order_handler import SimulatedOrderHandler  # noqa: F401

BRICKS = [
    {"open": 100, "close": 102, "direction": "up"},
    {"open": 102, "close": 100, "direction": "down"},
    {"open": 100, "close": 102, "direction": "up"},
]


def _set(cmd):
    if cmd is None:
        os.environ.pop(signal_filter.ENV_VAR, None)
    else:
        os.environ[signal_filter.ENV_VAR] = cmd


def test_filter():
    _set("")  # explicitly disabled
    assert signal_filter.is_enabled() is False
    assert signal_filter.should_skip("BTC_USDT", "sell", 1000, 0, BRICKS) is False

    _set("bash -c 'echo SKIP'")
    assert signal_filter.should_skip("BTC_USDT", "sell", 1000, 0, BRICKS) is True

    _set("bash -c 'echo ENTER'")
    assert signal_filter.should_skip("BTC_USDT", "sell", 1000, 0, BRICKS) is False

    _set("bash -c 'echo \"maybe ENTER... final: SKIP\"'")
    assert signal_filter.should_skip("BTC_USDT", "sell", 1000, 0, BRICKS) is True

    _set("bash -c 'exit 1'")  # failure → fail open
    assert signal_filter.should_skip("BTC_USDT", "sell", 1000, 0, BRICKS) is False

    _set("bash -c 'echo SKIP'")  # too few bricks → no judgement
    assert signal_filter.should_skip("BTC_USDT", "sell", 1000, 0, BRICKS[:2]) is False
    _set(None)


def test_symbol_normalization():
    assert _to_binance("BTC_USDT") == "BTCUSDT"
    assert _to_binance("btc/usdt") == "BTCUSDT"
    assert _to_binance("ETH") == "ETHUSDT"


def test_binance_units_and_mapping():
    bx = BinanceExchange(["BTC_USDT", "ETH_USDT"], network="testnet")

    def fake_get(url, params=None):
        if "exchangeInfo" in url:
            return {"symbols": [{"symbol": "BTCUSDT", "quantityPrecision": 3,
                                 "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001"}]}]}
        if "ticker/price" in url:
            if params:
                return {"symbol": params["symbol"], "price": "60000.0"}
            return [{"symbol": "BTCUSDT", "price": "60000.0"},
                    {"symbol": "ETHUSDT", "price": "3000.0"}]
        if "klines" in url:
            return [[1700000000000, "1", "2", "0.5", "1.5", "10", 1700000899999]]
        raise AssertionError(f"unexpected url {url}")

    bx._get = fake_get

    ci = bx.get_contract("BTC_USDT")
    assert ci.unit_size == 0.001 and ci.last_price == 60000.0

    ticks = {t.contract: t.last for t in bx.get_all_tickers()}
    assert ticks["BTC_USDT"] == 60000.0 and ticks["ETH_USDT"] == 3000.0

    bars = bx.get_candlesticks("BTC_USDT", "15m", 1)
    assert bars[0].c == 1.5 and bars[0].t == 1700000000  # ms → s

    bx._signed = lambda m, p, params=None: [
        {"symbol": "BTCUSDT", "positionAmt": "0.05", "unRealizedProfit": "12.3"}
    ]
    pos = bx.list_positions()
    assert pos[0].contract == "BTC_USDT"
    assert abs(pos[0].size - 50.0) < 1e-9          # 0.05 coin / 0.001 step = 50 units
    assert abs(pos[0].unrealised_pnl - 12.3) < 1e-9


if __name__ == "__main__":
    test_filter()
    test_symbol_normalization()
    test_binance_units_and_mapping()
    print("modernization self-check: PASS")
