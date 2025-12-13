from gate_api import FuturesApi
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
        self.account_total_balance = 1000.0
        self.symbol_position_list = []
        self.taker_fee_rate = 0.0005

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

    def set_symbol_position_list_last_price(self, symbol: str, last_price: float):
        found = False
        for item in self.symbol_position_list:
            if item["symbol"] == symbol:
                item["last_price"] = last_price
                found = True
                break
        if not found:
            # If symbol not found, append a new entry with minimal required fields
            self.symbol_position_list.append(
                {
                    "symbol": symbol,
                    "last_price": last_price,
                }
            )
        self.update_unrealised_pnl() # Call update after all price setting and appending

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
                last_price = float(contract_info.last_price)
                minimum_position_size_in_usdt = last_price * float(
                    contract_info.quanto_multiplier
                )
                order_size_in_quantity = int(
                    self.account_total_balance
                    * self.leverage
                    / minimum_position_size_in_usdt
                    / len(self.symbol_list)
                )
                
                new_symbol_data = {
                    "symbol": symbol,
                    "last_price": last_price,
                    "minimum_position_size_in_quantity": float(
                        contract_info.quanto_multiplier
                    ),
                    "minimum_position_size_in_usdt": minimum_position_size_in_usdt,
                    "order_size_in_quantity": order_size_in_quantity,
                    "order_size_in_usdt": (
                        self.account_total_balance
                        * self.leverage
                        / len(self.symbol_list)
                    ),
                    "current_position_size_in_quantity": 0,
                    "current_position_size_in_usdt": 0.0,
                    "current_position_side": None,
                    "unrealised_pnl": 0.0,
                    "entry_price": 0.0, # Initialize entry price
                }
                if existing:
                    existing.update(new_symbol_data)
                else:
                    self.symbol_position_list.append(new_symbol_data)
            except Exception as e:
                log.error(f"[Order] Failed to get symbol data for {symbol}: {e}")
                raise e

    def update_unrealised_pnl(self):
        for symbol_position in self.symbol_position_list:
            if symbol_position.get("current_position_size_in_quantity", 0) != 0:
                entry_price = symbol_position.get("entry_price", 0.0)
                last_price = symbol_position.get("last_price", 0.0)
                quantity = symbol_position.get("current_position_size_in_quantity", 0)
                contract_size = symbol_position.get("minimum_position_size_in_quantity", 0.0)
                
                # Calculate unrealised PnL
                symbol_position["unrealised_pnl"] = (last_price - entry_price) * quantity * contract_size
            else:
                symbol_position["unrealised_pnl"] = 0.0


    def place_market_open_order_after_close(self, symbol: str, side: str):
        self.set_symbol_data_to_position_list()
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
        symbol_position["entry_price"] = symbol_position.get("last_price")
        self.account_total_balance -= abs(order_size_in_usdt) * self.taker_fee_rate
        if self.account_total_balance < 50:
            log.info("Account balance below $50, stopping backtest.")
            raise SystemExit()
        log.info(
            f"[Order] Open {side} {symbol}, price: {symbol_position.get('last_price')}, size: {order_size_in_usdt:.2f}, balance: {self.account_total_balance:.2f}"
        )

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
        
        entry_price = symbol_position.get("entry_price", 0.0)
        last_price = symbol_position.get("last_price", 0.0)
        quantity = symbol_position.get("current_position_size_in_quantity", 0)
        contract_size = symbol_position.get("minimum_position_size_in_quantity", 0.0)
        symbol_position["unrealised_pnl"] = (last_price - entry_price) * quantity * contract_size
        
        self.account_total_balance += symbol_position.get("unrealised_pnl", 0.0) - (
            abs(symbol_position.get("current_position_size_in_usdt", 0.0))
            * self.taker_fee_rate
        )
        if self.account_total_balance < 50:
            log.info("Account balance below $50, stopping backtest.")
            raise SystemExit()
        log.info(
            f"[Order] Closed {symbol_position.get('current_position_side')} {symbol}, entry_price: {entry_price}, last_price: {last_price}, quantity: {quantity}, size: {symbol_position.get('current_position_size_in_usdt'):.2f}, balance: {self.account_total_balance:.2f}, PnL: {symbol_position.get('unrealised_pnl'):.2f}"
        )
        symbol_position["unrealised_pnl"] = 0.0
        symbol_position["current_position_side"] = None
        symbol_position["current_position_size_in_quantity"] = 0
        symbol_position["current_position_size_in_usdt"] = 0

