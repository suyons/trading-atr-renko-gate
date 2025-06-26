import os

from dotenv import load_dotenv

from service.discord_rest_client import DiscordRestClient
from service.gate_rest_client import GateRestClient
from service.order_handler import OrderHandler
from service.renko_calculator import RenkoCalculator
import sched
import time

load_dotenv()

GATE_URL_HOST_LIVE = os.getenv("GATE_URL_HOST_LIVE")
GATE_URL_HOST_TEST = os.getenv("GATE_URL_HOST_TEST")
GATE_URL_PREFIX = os.getenv("GATE_URL_PREFIX")

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

SYMBOL_LIST = os.getenv("SYMBOL_LIST").split(",")
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME")
ATR_PERIOD = int(os.getenv("ATR_PERIOD"))
OHLCV_COUNT = int(os.getenv("OHLCV_COUNT"))

LEVERAGE = int(os.getenv("LEVERAGE"))  # Default to 2 if not set

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Dependencies initialization
gate_rest_client = GateRestClient(
    url_host=GATE_URL_HOST_TEST,
    url_prefix=GATE_URL_PREFIX,
    api_key=API_KEY,
    secret_key=SECRET_KEY,
    ohlcv_timeframe=OHLCV_TIMEFRAME,
    ohlcv_count=OHLCV_COUNT,
)
order_handler = OrderHandler(
    gate_rest_client=gate_rest_client, symbol_list=SYMBOL_LIST, leverage=LEVERAGE
)
discord_client = DiscordRestClient(url=DISCORD_WEBHOOK_URL)
renko_calculator = RenkoCalculator(
    symbol_list=SYMBOL_LIST,
    ohlcv_timeframe=OHLCV_TIMEFRAME,
    atr_period=ATR_PERIOD,
    ohlcv_count=OHLCV_COUNT,
    discord_client=discord_client,
    order_handler=order_handler,
)


def main():
    # Load the futures historical data
    for symbol in SYMBOL_LIST:
        ohlcv_list = gate_rest_client.get_futures_candlesticks_bulk(
            params={
                "contract": symbol,
                "limit": OHLCV_COUNT,
                "interval": OHLCV_TIMEFRAME,
            }
        )
        renko_calculator.set_ohlcv_list_into_symbol_data_list(symbol, ohlcv_list)
    renko_calculator.set_brick_size_into_symbol_data_list()
    renko_calculator.set_renko_list_into_symbol_data_list()
    for symbol in SYMBOL_LIST:
        renko_calculator.send_renko_plot_to_discord(symbol)

    # Start the stream for the real-time data
    scheduler = sched.scheduler(time.time, time.sleep)

    def fetch_then_process_ticker_data_scheduled():
        ticker_data = gate_rest_client.get_futures_tickers()
        renko_calculator.handle_new_ticker_data(ticker_data)
        scheduler.enter(1, 1, fetch_then_process_ticker_data_scheduled)

    scheduler.enter(1, 1, fetch_then_process_ticker_data_scheduled)
    scheduler.run()


def test():
    # This function is a placeholder for testing purposes.
    order_handler.place_market_entry_order(symbol="BTC_USDT", side="buy", price=99999.9)
    pass


if __name__ == "__main__":
    main()
    # test()
