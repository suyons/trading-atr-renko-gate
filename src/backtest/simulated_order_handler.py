from gate_api import FuturesApi, FuturesOrder
from gate_api.models.contract import Contract

from config.logger_config import log


class SimulatedOrderHandler:
    def __init__(
        self,
        gate_futures_api: FuturesApi,
        symbol_list: list[str],
        leverage: int,
    ):
        self.gate_futures_api = gate_futures_api
        self.symbol_list = symbol_list
        self.leverage = leverage
        self.account_total_balance = 10000.0
        self.symbol_position_list = []
        self.taker_fee_rate = 0.0005

        self.set_symbol_data_to_position_list()

        """Example of symbol_position_list:
        [
            {
                "symbol": "BTC_USDT",
                "last_price": 112233.44,
                "minimum_position_size_in_quantity": 0.0001,
                "minimum_position_size_in_usdt": 11.22,
                "order_size_in_quantity": 100,
                "order_size_in_usdt": 1122.33,
                "current_position_size_in_quantity": -100,
                "current_position_size_in_usdt": -1122.33
                "current_position_side": "sell",
                "unrealised_pnl": 1.23
            }
        ]
        """

    def set_symbol_data_to_position_list(self):
        for symbol in self.symbol_list:
            try:
                contract_info: Contract = self.gate_futures_api.get_futures_contract(
                    settle="usdt", contract=symbol
                )

                # Find existing entry for the symbol
                existing = next(
                    (
                        item
                        for item in self.symbol_position_list
                        if item["symbol"] == symbol
                    ),
                    None,
                )
                minimum_position_size_in_usdt = float(contract_info.last_price) * float(contract_info.quanto_multiplier)
                order_size_in_quantity = int(
                    self.account_total_balance
                    * self.leverage
                    / minimum_position_size_in_usdt
                    / len(self.symbol_list)
                )
                symbol_data = {
                    "symbol": symbol,
                    "last_price": float(contract_info.last_price),
                    "minimum_position_size_in_quantity": float(contract_info.quanto_multiplier),
                    "minimum_position_size_in_usdt": minimum_position_size_in_usdt,
                    "order_size_in_quantity": order_size_in_quantity,
                    "order_size_in_usdt": (
                        self.account_total_balance
                        * self.leverage
                        / len(self.symbol_list)
                    ),
                }
                if existing:
                    existing.update(symbol_data)
                else:
                    self.symbol_position_list.append(symbol_data)
            except Exception as e:
                log.error(f"[Order] Failed to get symbol data for {symbol}: {e}")
                raise e

    def place_market_open_order_after_close(self, symbol: str, side: str):
        symbol_position = next(
            (item for item in self.symbol_position_list if item["symbol"] == symbol),
            None,
        )
        if symbol_position.get("current_position_side") == side:
            return
        if symbol_position.get("current_position_size_in_quantity", 0) != 0:
            self.place_market_close_order(symbol=symbol)
        order_size_in_quantity = (
            symbol_position.get("order_size_in_quantity", 0) if symbol_position else 0
        )
        order_size_in_usdt = (
            symbol_position.get("order_size_in_usdt", 0) if symbol_position else 0
        )
        if side == "sell":
            order_size_in_quantity = -abs(order_size_in_quantity)
            order_size_in_usdt = -abs(order_size_in_usdt)
        elif side == "buy":
            order_size_in_quantity = abs(order_size_in_quantity)
            order_size_in_usdt = abs(order_size_in_usdt)
        else:
            raise ValueError(f"Invalid side: {side}. Must be 'buy' or 'sell'.")
        symbol_position["current_position_side"] = side
        symbol_position["current_position_size_in_quantity"] = order_size_in_quantity
        symbol_position["current_position_size_in_usdt"] = order_size_in_usdt
        symbol_position["unrealised_pnl"] = 0.0
        self.account_total_balance -= abs(order_size_in_usdt) * self.taker_fee_rate
        log.info(f"[Order] Open {side} {symbol}, price: {symbol_position.get('last_price')}, size: {order_size_in_usdt:.2f}, balance: {self.account_total_balance:.2f}")

    def place_market_close_order(self, symbol: str):
        symbol_position = next(
            (item for item in self.symbol_position_list if item["symbol"] == symbol),
            None,
        )
        if (
            not symbol_position
            or symbol_position.get("current_position_size_in_quantity", 0) == 0
        ):
            return
        self.account_total_balance += symbol_position.get("unrealised_pnl", 0.0) - (
            abs(symbol_position.get("current_position_size_in_usdt", 0.0))
            * self.taker_fee_rate
        )
        log.info(
            f"[Order] Closed {symbol_position.get('current_position_side')} {symbol}, price: {symbol_position.get('last_price')}, size: {symbol_position.get('current_position_size_in_usdt'):.2f}, balance: {self.account_total_balance:.2f}, PnL: {symbol_position.get('unrealised_pnl'):.2f}"
        )
        symbol_position["current_position_side"] = None
        symbol_position["current_position_size_in_quantity"] = 0
        symbol_position["current_position_size_in_usdt"] = 0
        symbol_position["unrealised_pnl"] = 0.0
