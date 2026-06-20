"""Exchange abstraction — the swap contract.

Every venue implements `Exchange` and returns these normalized types, so the
trading logic (renko_calculator, order_handler) never touches a venue SDK.
Add a venue by writing one `Exchange` subclass; select it with the `EXCHANGE`
env var (see `exchange/__init__.py`). Nothing else changes.

Order size is expressed in integer *units*. One unit = `ContractInfo.unit_size`
coin (Gate's `quanto_multiplier`; Binance's lot `stepSize`). Each adapter
converts units <-> its native size, so the sizing math stays venue-neutral.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OHLCV:
    t: int      # open time, unix seconds
    o: float
    h: float
    l: float
    c: float
    v: float


@dataclass
class Ticker:
    contract: str   # in the caller's symbol format (e.g. BTC_USDT)
    last: float


@dataclass
class ContractInfo:
    symbol: str
    last_price: float
    unit_size: float   # coin per order-unit


@dataclass
class Position:
    contract: str          # caller's symbol format
    size: float            # signed, in order-units (+long / -short)
    unrealised_pnl: float


class Exchange(ABC):
    """A venue. Symbols are always in the caller's format (e.g. BTC_USDT)."""

    def __init__(self, symbol_list: list[str]):
        self.symbol_list = symbol_list

    @abstractmethod
    def get_candlesticks(self, symbol: str, timeframe: str, count: int) -> list[OHLCV]:
        ...

    @abstractmethod
    def get_all_tickers(self) -> list[Ticker]:
        """One ticker per configured symbol, labeled in the caller's format."""
        ...

    @abstractmethod
    def get_contract(self, symbol: str) -> ContractInfo:
        ...

    @abstractmethod
    def get_total_balance(self) -> float:
        ...

    @abstractmethod
    def list_positions(self) -> list[Position]:
        """Only open positions (non-zero size)."""
        ...

    @abstractmethod
    def create_market_order(self, symbol: str, size_units: int, close: bool = False) -> float:
        """Place a market order. `size_units` is signed (+buy / -sell); ignored
        when `close=True` (reduce-only flatten). Returns the fill price."""
        ...
