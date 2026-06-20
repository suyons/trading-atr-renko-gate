"""Binance USDT-M futures adapter — stdlib + requests, no SDK.

  testnet -> https://testnet.binancefuture.com   (demo funds, signed calls)
  mainnet -> https://fapi.binance.com             (real money)

Market data (klines, prices, exchangeInfo) is always read from mainnet —
testnet shares mainnet prices but has thin public data. Auth: HMAC-SHA256
(X-MBX-APIKEY header), keys passed in from env.
"""
import hashlib
import hmac
import time

import requests

from exchange.base import Exchange, OHLCV, Ticker, ContractInfo, Position

HOSTS = {
    "testnet": "https://testnet.binancefuture.com",
    "mainnet": "https://fapi.binance.com",
}
MARKET_DATA = HOSTS["mainnet"]
_INTERVAL_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400,
}


def _to_binance(symbol: str) -> str:
    """BTC_USDT / BTC/USDT / BTCUSDT -> BTCUSDT"""
    s = symbol.upper().replace("/", "").replace("_", "").strip()
    return s if s.endswith("USDT") else s + "USDT"


class BinanceExchange(Exchange):
    def __init__(self, symbol_list, network="testnet", api_key=None, api_secret=None):
        super().__init__(symbol_list)
        self.host = HOSTS.get(network, HOSTS["testnet"])
        self.api_key = api_key
        self.api_secret = api_secret
        # caller-symbol <-> binance-symbol maps (built from the configured list)
        self._to_caller = {_to_binance(s): s for s in symbol_list}
        self._unit_size_cache: dict[str, float] = {}
        self._qty_precision_cache: dict[str, int] = {}

    # ── HTTP ──────────────────────────────────────────────────────────────
    def _get(self, url, params=None):
        r = requests.get(url, params=params or {}, headers={"Accept": "application/json"}, timeout=15)
        r.raise_for_status()
        return r.json()

    def _sign(self, params: dict) -> str:
        from urllib.parse import urlencode
        qs = urlencode(params)
        sig = hmac.new(self.api_secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
        return qs + "&signature=" + sig

    def _signed(self, method, path, params=None):
        if not self.api_key or not self.api_secret:
            raise RuntimeError("Binance API key/secret not configured")
        p = dict(params or {})
        p["timestamp"] = int(time.time() * 1000)
        query = self._sign(p)
        headers = {"Accept": "application/json", "X-MBX-APIKEY": self.api_key}
        if method == "GET":
            r = requests.get(f"{self.host}{path}?{query}", headers=headers, timeout=15)
        elif method == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            r = requests.post(f"{self.host}{path}", data=query, headers=headers, timeout=15)
        else:
            raise ValueError(method)
        r.raise_for_status()
        return r.json()

    # ── exchangeInfo (lot size) ───────────────────────────────────────────
    def _load_symbol_filters(self, binance_symbol):
        if binance_symbol in self._unit_size_cache:
            return
        info = self._get(f"{MARKET_DATA}/fapi/v1/exchangeInfo")
        for s in info["symbols"]:
            if s["symbol"] != binance_symbol:
                continue
            step = next(
                (float(f["stepSize"]) for f in s["filters"] if f["filterType"] == "LOT_SIZE"),
                0.001,
            )
            self._unit_size_cache[binance_symbol] = step
            self._qty_precision_cache[binance_symbol] = int(s.get("quantityPrecision", 3))
            return
        self._unit_size_cache[binance_symbol] = 0.001
        self._qty_precision_cache[binance_symbol] = 3

    # ── Market data ───────────────────────────────────────────────────────
    def get_candlesticks(self, symbol, timeframe, count):
        rows = self._get(
            f"{MARKET_DATA}/fapi/v1/klines",
            {"symbol": _to_binance(symbol), "interval": timeframe, "limit": count},
        )
        return [
            OHLCV(t=int(k[0]) // 1000, o=float(k[1]), h=float(k[2]),
                  l=float(k[3]), c=float(k[4]), v=float(k[5]))
            for k in rows
        ]

    def get_all_tickers(self):
        rows = self._get(f"{MARKET_DATA}/fapi/v1/ticker/price")
        by_symbol = {r["symbol"]: float(r["price"]) for r in rows}
        out = []
        for binance_sym, caller_sym in self._to_caller.items():
            if binance_sym in by_symbol:
                out.append(Ticker(contract=caller_sym, last=by_symbol[binance_sym]))
        return out

    def get_contract(self, symbol):
        b = _to_binance(symbol)
        self._load_symbol_filters(b)
        price = float(self._get(f"{MARKET_DATA}/fapi/v1/ticker/price", {"symbol": b})["price"])
        return ContractInfo(symbol=symbol, last_price=price, unit_size=self._unit_size_cache[b])

    # ── Account / trading (signed, testnet) ───────────────────────────────
    def get_total_balance(self):
        account = self._signed("GET", "/fapi/v2/account")
        usdt = next((a for a in account["assets"] if a["asset"] == "USDT"), None)
        return float(usdt["walletBalance"]) if usdt else 0.0

    def list_positions(self):
        rows = self._signed("GET", "/fapi/v2/positionRisk")
        out = []
        for p in rows:
            amt = float(p["positionAmt"])
            if amt == 0:
                continue
            caller = self._to_caller.get(p["symbol"])
            if not caller:
                continue
            self._load_symbol_filters(p["symbol"])
            unit = self._unit_size_cache[p["symbol"]]
            out.append(Position(
                contract=caller,
                size=amt / unit if unit else amt,            # native coin -> units
                unrealised_pnl=float(p["unRealizedProfit"]),
            ))
        return out

    def create_market_order(self, symbol, size_units, close=False):
        b = _to_binance(symbol)
        self._load_symbol_filters(b)
        prec = self._qty_precision_cache[b]
        unit = self._unit_size_cache[b]

        if close:
            pos = next((p for p in self._signed("GET", "/fapi/v2/positionRisk")
                        if p["symbol"] == b and float(p["positionAmt"]) != 0), None)
            if not pos:
                return 0.0
            amt = float(pos["positionAmt"])
            side = "SELL" if amt > 0 else "BUY"
            qty = round(abs(amt), prec)
            params = {"symbol": b, "side": side, "type": "MARKET",
                      "quantity": qty, "reduceOnly": "true"}
        else:
            side = "BUY" if size_units > 0 else "SELL"
            qty = round(abs(size_units) * unit, prec)
            params = {"symbol": b, "side": side, "type": "MARKET", "quantity": qty}

        resp = self._signed("POST", "/fapi/v1/order", params)
        # avgPrice is 0 until filled; fall back to mark price.
        avg = float(resp.get("avgPrice") or 0.0)
        if avg > 0:
            return avg
        return float(self._get(f"{MARKET_DATA}/fapi/v1/ticker/price", {"symbol": b})["price"])
