from config.logger_config import log
from service.gate_rest_client import GateRestClient


class OrderHandler:
    def __init__(
        self, gate_rest_client: GateRestClient, symbol_list: list[str], leverage: int
    ):
        self.gate_rest_client = gate_rest_client
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
            self.gate_rest_client.post_futures_order(futures_order_params)
            log.info(f"[Order] {side.capitalize()} {symbol}, price: {price}, size: ${order_size_in_usdt:.2f}")
        except Exception as e:
            self.discord_rest_client.send_error_message(
                f"Failed to place market order: {e}"
            )
            raise e

    def get_account_total_balance(self):
        try:
            account_info = self.gate_rest_client.get_futures_accounts()
            if "total" not in account_info:
                raise ValueError("Total balance not found in account info")
            total_balance = float(account_info["total"])
            return total_balance
        except Exception as e:
            log.error(f"[Order] Failed to get account balance: {e}")
            raise e
