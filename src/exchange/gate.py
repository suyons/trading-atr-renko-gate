"""Gate.io USDT-M futures adapter — wraps the gate_api SDK."""
from gate_api import Configuration, ApiClient, FuturesApi, UnifiedApi, FuturesOrder
from gate_api.models.contract import Contract
from gate_api.models.position import Position as GatePosition
from gate_api.models.unified_account import UnifiedAccount

from exchange.base import Exchange, OHLCV, Ticker, ContractInfo, Position

SETTLE = "usdt"


class GateExchange(Exchange):
    def __init__(self, symbol_list, host, api_key=None, api_secret=None):
        super().__init__(symbol_list)
        config = Configuration(host=host, key=api_key, secret=api_secret)
        client = ApiClient(configuration=config)
        self.futures_api = FuturesApi(api_client=client)
        self.unified_api = UnifiedApi(api_client=client)

    def get_candlesticks(self, symbol, timeframe, count):
        rows = self.futures_api.list_futures_candlesticks(
            settle=SETTLE, contract=symbol, limit=count, interval=timeframe
        )
        return [
            OHLCV(t=int(r.t), o=float(r.o), h=float(r.h), l=float(r.l), c=float(r.c), v=float(r.v))
            for r in rows
        ]

    def get_all_tickers(self):
        rows = self.futures_api.list_futures_tickers(settle=SETTLE)
        wanted = set(self.symbol_list)
        return [
            Ticker(contract=r.contract, last=float(r.last))
            for r in rows
            if r.contract in wanted
        ]

    def get_contract(self, symbol):
        info: Contract = self.futures_api.get_futures_contract(settle=SETTLE, contract=symbol)
        return ContractInfo(
            symbol=symbol,
            last_price=float(info.last_price),
            unit_size=float(info.quanto_multiplier),
        )

    def get_total_balance(self):
        account: UnifiedAccount = self.unified_api.list_unified_accounts()
        return float(account.unified_account_total)

    def list_positions(self):
        rows: list[GatePosition] = self.futures_api.list_positions(settle=SETTLE, holding=True)
        return [
            Position(
                contract=p.contract,
                size=float(p.size),
                unrealised_pnl=float(p.unrealised_pnl),
            )
            for p in rows
        ]

    def create_market_order(self, symbol, size_units, close=False):
        order = FuturesOrder(
            contract=symbol,
            size=0 if close else int(size_units),
            close=close,
            price="0",
            tif="ioc",
        )
        resp: FuturesOrder = self.futures_api.create_futures_order(settle=SETTLE, futures_order=order)
        return float(resp.fill_price)
