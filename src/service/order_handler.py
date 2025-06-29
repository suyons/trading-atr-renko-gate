from gate_api import FuturesApi, FuturesOrder
from gate_api.models.contract import Contract
from gate_api.models.futures_account import FuturesAccount
from gate_api.models.position import Position
from requests.exceptions import HTTPError

from config.logger_config import log
from service.discord_client import DiscordClient


class OrderHandler:
    def __init__(
        self,
        gate_futures_api: FuturesApi,
        discord_client: DiscordClient,
        symbol_list: list[str],
        leverage: int,
    ):
        self.gate_futures_api = gate_futures_api
        self.discord_client = discord_client
        self.symbol_list = symbol_list
        self.leverage = leverage
        self.account_total_balance = 0.0
        self.symbol_position_list = []

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

        self.set_account_total_balance()
        self.set_symbol_data_to_position_list()
        self.set_account_data_to_position_list()

    def set_account_total_balance(self) -> float:
        try:
            futures_account: FuturesAccount = (
                self.gate_futures_api.list_futures_accounts("usdt")
            )
            self.account_total_balance = float(futures_account.total) + float(
                futures_account.unrealised_pnl
            )
        except Exception as e:
            log.error(f"[Order] Failed to get account balance: {e}")
            raise e

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
                symbol_data = {
                    "symbol": symbol,
                    "last_price": float(contract_info.last_price),
                    "minimum_position_size_in_quantity": float(
                        contract_info.quanto_multiplier
                    ),
                    "minimum_position_size_in_usdt": float(contract_info.last_price)
                    * float(contract_info.quanto_multiplier),
                }
                if existing:
                    existing.update(symbol_data)
                else:
                    self.symbol_position_list.append(symbol_data)
            except Exception as e:
                log.error(f"[Order] Failed to get quanto multiplier for {symbol}: {e}")
                raise e

    def set_account_data_to_position_list(self):
        current_position_list: list[Position] = self.gate_futures_api.list_positions(
            settle="usdt", holding=True
        )
        for symbol_data in self.symbol_position_list:
            symbol = symbol_data["symbol"]
            try:
                current_position = next(
                    (
                        p
                        for p in current_position_list
                        if getattr(p, "contract", None) == symbol
                    ),
                    None,
                )
                current_position_size = current_position.size if current_position else 0
                unrealised_pnl = (
                    float(current_position.unrealised_pnl) if current_position else 0.0
                )

                symbol_data.update(
                    {
                        "order_size_in_quantity": (
                            int(
                                self.account_total_balance
                                * self.leverage
                                / symbol_data["minimum_position_size_in_usdt"]
                                / len(self.symbol_list)
                            )
                        ),
                        "order_size_in_usdt": (
                            self.account_total_balance
                            * self.leverage
                            / len(self.symbol_list)
                        ),
                        "current_position_size_in_quantity": current_position_size,
                        "current_position_size_in_usdt": current_position_size
                        * symbol_data["minimum_position_size_in_usdt"],
                        "current_position_side": (
                            "buy"
                            if current_position_size > 0
                            else "sell" if current_position_size < 0 else None
                        ),
                        "unrealised_pnl": unrealised_pnl,
                    }
                )
            except Exception as e:
                log.error(f"[Order] Failed to get position for {symbol}: {e}")
                raise e

    def place_market_open_order_after_close(self, symbol: str, side: str):
        self.set_symbol_data_to_position_list()
        self.set_account_data_to_position_list()
        symbol_position = next(
            (item for item in self.symbol_position_list if item["symbol"] == symbol),
            None,
        )
        if symbol_position.get("current_position_side") == side:
            return
        self.place_market_close_order(symbol=symbol)
        order_size_in_quantity = (
            symbol_position.get("order_size_in_quantity", 0) if symbol_position else 0
        )
        order_size_in_usdt = (
            symbol_position.get("order_size_in_usdt", 0) if symbol_position else 0
        )
        futures_order = FuturesOrder(
            contract=symbol,
            size=order_size_in_quantity,
            price="0",
            tif="ioc",
        )
        try:
            order_response: FuturesOrder = self.gate_futures_api.create_futures_order(
                settle="usdt",
                futures_order=futures_order,
            )
            self.set_account_total_balance()
            self.discord_client.push_log_buffer(
                f"[Order] Open {side} {symbol}, price: {order_response.fill_price}, size: {order_size_in_usdt:.2f}, balance: {self.account_total_balance:.2f}",
                "info",
            )
        except HTTPError as e:
            self.discord_client.push_log_buffer(e, "error")
            raise e
        finally:
            self.discord_client.flush_log_buffer()

    def place_market_close_order(self, symbol: str):
        futures_order = FuturesOrder(
            contract=symbol,
            size=0,
            close=True,
            price="0",
            tif="ioc",
        )
        try:
            order_response: FuturesOrder = self.gate_futures_api.create_futures_order(
                settle="usdt",
                futures_order=futures_order,
            )
            self.set_account_total_balance()
            symbol_position = next(
                (
                    item
                    for item in self.symbol_position_list
                    if item["symbol"] == symbol
                ),
                None,
            )
            self.discord_client.push_log_buffer(
                f"[Order] Closed {symbol_position.get('current_position_side')} {symbol}, price: {order_response.fill_price}, size: {symbol_position.get('current_position_size_in_usdt'):.2f}, balance: {self.account_total_balance:.2f}, PnL: {symbol_position.get('unrealised_pnl'):.2f}",
                "info",
            )
            self.set_account_data_to_position_list()
        except HTTPError as e:
            self.discord_client.push_log_buffer(e)
            raise e
        finally:
            self.discord_client.flush_log_buffer()
