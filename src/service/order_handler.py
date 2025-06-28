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

    def place_market_open_order(self, symbol: str, side: str):
        total_balance = self._get_account_total_balance()
        minimum_order_size_in_usdt = self._get_minimum_order_size_in_usdt(symbol)
        order_size_in_usdt = self.leverage * total_balance / len(self.symbol_list)
        order_size_in_quantity = int(order_size_in_usdt / minimum_order_size_in_usdt)
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
            self.discord_client.push_log_buffer(
                f"[Order] {side.capitalize()} {symbol}, price: {order_response.fill_price}, size: ${order_size_in_usdt:.2f}, balance: ${total_balance:.2f}",
                "info",
            )
        except HTTPError as e:
            self.discord_client.push_log_buffer(e, "error")
            raise e
        finally:
            self.discord_client.flush_log_buffer()

    def place_market_close_order_if_position_opened(self, symbol: str):
        current_position_size = self._get_current_position_size(symbol)
        if current_position_size == 0:
            return
        current_position_side = "buy" if current_position_size > 0 else "sell"
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
            self.discord_client.push_log_buffer(
                f"[Order] Exit {current_position_side.upper()} {symbol}, price: {order_response.fill_price}, size: ${order_response.size:.2f}, balance: ${self._get_account_total_balance():.2f}",
                "info",
            )
        except HTTPError as e:
            self.discord_client.push_log_buffer(e)
            raise e
        finally:
            self.discord_client.flush_log_buffer()

    def _get_account_total_balance(self) -> float:
        try:
            futures_account: FuturesAccount = (
                self.gate_futures_api.list_futures_accounts("usdt")
            )
            return float(futures_account.total)
        except Exception as e:
            log.error(f"[Order] Failed to get account balance: {e}")
            raise e

    def _get_minimum_order_size_in_usdt(self, symbol: str) -> float:
        try:
            contract_info: Contract = self.gate_futures_api.get_futures_contract(
                settle="usdt", contract=symbol
            )
            return float(contract_info.last_price) * float(
                contract_info.quanto_multiplier
            )
        except Exception as e:
            log.error(f"[Order] Failed to get minimum order size for {symbol}: {e}")
            raise e

    def _get_current_position_size(self, symbol: str) -> int:
        try:
            current_position_list: list[Position] = (
                self.gate_futures_api.list_positions(settle="usdt", holding=True)
            )
            current_position = next(
                (
                    p
                    for p in current_position_list
                    if getattr(p, "contract", None) == symbol
                ),
                None,
            )
            current_position_size = current_position.size if current_position else 0
            return current_position_size
        except Exception as e:
            log.error(f"[Order] Failed to get position for {symbol}: {e}")
            raise e
