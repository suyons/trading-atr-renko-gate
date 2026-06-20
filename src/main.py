import os
import time
import schedule

from dotenv import load_dotenv

from config.logger_config import log
from exchange import create_exchange
from service.discord_client import DiscordClient
from service.order_handler import OrderHandler
from service.renko_calculator import RenkoCalculator

# Load environment variables from .env file
load_dotenv()

TRADING_MODE = (
    os.getenv("TRADING_MODE") or os.getenv("GATE_TRADING_MODE") or "TEST"
).upper()
DISCORD_WEBHOOK_URL = (
    os.getenv("DISCORD_WEBHOOK_URL_LIVE")
    if TRADING_MODE == "LIVE"
    else os.getenv("DISCORD_WEBHOOK_URL_TEST")
)

SYMBOL_LIST = os.getenv("SYMBOL_LIST").split(",")
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME")
ATR_PERIOD = int(os.getenv("ATR_PERIOD"))
OHLCV_COUNT = int(os.getenv("OHLCV_COUNT"))
LEVERAGE = int(os.getenv("LEVERAGE"))


# Dependencies initialization
exchange = create_exchange(symbol_list=SYMBOL_LIST)
discord_client = DiscordClient(url=DISCORD_WEBHOOK_URL)
order_handler = OrderHandler(
    exchange=exchange,
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
        candlestick_list = exchange.get_candlesticks(
            symbol=symbol, timeframe=OHLCV_TIMEFRAME, count=OHLCV_COUNT
        )
        renko_calculator.set_ohlcv_list_into_symbol_data_list(
            symbol=symbol, candlestick_list=candlestick_list
        )
    renko_calculator.set_brick_size_into_symbol_data_list()
    renko_calculator.set_renko_list_into_symbol_data_list()
    discord_client.push_log_buffer(
        f"[Main] Historical data loaded on {len(SYMBOL_LIST)} symbols: {str(SYMBOL_LIST)}"
    )
    discord_client.flush_log_buffer()
    for symbol in SYMBOL_LIST:
        renko_calculator.send_renko_plot_to_discord(symbol=symbol)


def fetch_then_process_ticker_data():
    try:
        ticker_data_list = exchange.get_all_tickers()
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
