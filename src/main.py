import os
import time
import schedule

from dotenv import load_dotenv
from gate_api import Configuration, ApiClient, FuturesApi
from gate_api.models.futures_candlestick import FuturesCandlestick
from gate_api.models.futures_ticker import FuturesTicker

from config.logger_config import log
from service.discord_client import DiscordClient
from service.order_handler import OrderHandler
from service.renko_calculator import RenkoCalculator

# Load environment variables from .env file
load_dotenv()

TRADING_MODE = os.getenv("GATE_TRADING_MODE").upper()
GATE_URL_HOST = (
    os.getenv("GATE_URL_HOST_LIVE")
    if TRADING_MODE == "LIVE"
    else os.getenv("GATE_URL_HOST_TEST")
)

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

SYMBOL_LIST = os.getenv("SYMBOL_LIST").split(",")
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME")
ATR_PERIOD = int(os.getenv("ATR_PERIOD"))
OHLCV_COUNT = int(os.getenv("OHLCV_COUNT"))

LEVERAGE = int(os.getenv("LEVERAGE"))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Dependencies initialization
gate_configuration = Configuration(
    host=GATE_URL_HOST,
    key=API_KEY,
    secret=API_SECRET,
)
gate_client = ApiClient(configuration=gate_configuration)
gate_futures_api = FuturesApi(api_client=gate_client)
discord_client = DiscordClient(url=DISCORD_WEBHOOK_URL)
order_handler = OrderHandler(
    gate_futures_api=gate_futures_api,
    discord_client=discord_client,
    symbol_list=SYMBOL_LIST,
    leverage=LEVERAGE,
)
renko_calculator = RenkoCalculator(
    symbol_list=SYMBOL_LIST,
    ohlcv_timeframe=OHLCV_TIMEFRAME,
    atr_period=ATR_PERIOD,
    ohlcv_count=OHLCV_COUNT,
    discord_client=discord_client,
    order_handler=order_handler,
)


def initialize_historical_data():
    discord_client.push_log_buffer("[Main] Renko trader started")
    for symbol in SYMBOL_LIST:
        candlestick_list: list[FuturesCandlestick] = (
            gate_futures_api.list_futures_candlesticks(
                settle="usdt",
                contract=symbol,
                limit=OHLCV_COUNT,
                interval=OHLCV_TIMEFRAME,
            )
        )
        renko_calculator.set_ohlcv_list_into_symbol_data_list(
            symbol=symbol, candlestick_list=candlestick_list
        )
    renko_calculator.set_brick_size_into_symbol_data_list()
    renko_calculator.set_renko_list_into_symbol_data_list()
    discord_client.push_log_buffer(
        f"[Main] Historial data loaded on {len(SYMBOL_LIST)} symbols: {str(SYMBOL_LIST)}"
    )
    discord_client.flush_log_buffer()
    for symbol in SYMBOL_LIST:
        renko_calculator.send_renko_plot_to_discord(symbol=symbol)


def fetch_then_process_ticker_data():
    try:
        ticker_data_list: FuturesTicker = gate_futures_api.list_futures_tickers(
            settle="usdt"
        )
        renko_calculator.handle_new_ticker_data(ticker_data_list)
    except Exception as e:
        log.error(f"[Main] Error fetching ticker data: {e}")
        time.sleep(5)
        fetch_then_process_ticker_data()


def main():
    initialize_historical_data()
    schedule.every(1).seconds.do(fetch_then_process_ticker_data)
    schedule.every().hour.at(":00").do(
        order_handler.send_symbol_position_list_to_discord
    )
    schedule.every().saturday.at("09:00").do(initialize_historical_data)
    while True:
        schedule.run_pending()
        time.sleep(1)


def test():
    pass


if __name__ == "__main__":
    main()
    # test()
