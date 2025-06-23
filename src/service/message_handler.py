import json

from config.logger_config import log
from service.renko_calculator import RenkoCalculator


class MessageHandler:
    def __init__(self, renko_calculator: RenkoCalculator):
        self.renko_calculator = renko_calculator
        self.channel_handlers = {
            "futures.tickers": self.handle_futures_tickers,
        }

    def handle_message(self, message: str):
        """
        Handles incoming messages by parsing JSON and storing the message.
        """
        try:
            message = json.loads(message)

            channel = message.get("channel")
            handler = self.channel_handlers.get(channel)
            if handler:
                handler(message)
            else:
                log.info(f"[MessageHandler] Unknown channel: {channel}")
        except json.JSONDecodeError as e:
            log.error(f"[MessageHandler] JSON decode error: {e}")

    def handle_futures_tickers(self, message: dict):
        if message.get("event") == "update":
            result = message.get("result", [])
            for ticker_info in result:
                if ticker_info.get("contract") == "BTC_USDT":
                    last_price = float(ticker_info.get("last"))
                    self.renko_calculator.handle_new_price(last_price)
                    break
