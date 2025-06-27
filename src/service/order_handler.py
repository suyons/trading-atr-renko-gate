from requests.exceptions import HTTPError

from config.logger_config import log
from service.discord_client import DiscordClient
from service.gate_client import GateClient


class OrderHandler:
    def __init__(
        self,
        gate_client: GateClient,
        discord_client: DiscordClient,
        symbol_list: list[str],
        leverage: int,
    ):
        self.gate_client = gate_client
        self.discord_client = discord_client
        self.symbol_list = symbol_list
        self.leverage = leverage

    def place_market_entry_order(self, symbol: str, side: str, price: float):
        account_balance = self.get_account_total_balance()
        if account_balance <= 0:
            raise ValueError("Insufficient account balance to place an order")
        # Calculate order size based on account balance and price
        order_size_in_usdt = (account_balance / len(self.symbol_list)) * self.leverage
        futures_order_params = {
            "contract": symbol,
            "size": order_size_in_usdt,
            "price": "0",  # market order
            "text": f"t-renko-{side}",
        }
        try:
            self.gate_client.post_futures_order(futures_order_params)
            log.info(
                f"[Order] {side.capitalize()} {symbol}, price: {price}, size: ${order_size_in_usdt:.2f}"
            )
        except HTTPError as e:
            self.discord_client.push_log_buffer(e)
            self.discord_client.flush_log_buffer()
            raise e

    def get_account_total_balance(self):
        try:
            account_info = self.gate_client.get_futures_accounts()
            if "total" not in account_info:
                raise ValueError("Total balance not found in account info")
            total_balance = float(account_info["total"])
            return total_balance
        except Exception as e:
            log.error(f"[Order] Failed to get account balance: {e}")
            raise e
