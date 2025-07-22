import os
from dotenv import load_dotenv
from gate_api import Configuration, ApiClient, FuturesApi
from gate_api.models.futures_candlestick import FuturesCandlestick
from gate_api.models.futures_ticker import FuturesTicker

from backtest.simulated_order_handler import SimulatedOrderHandler
from config.logger_config import log
from service.renko_calculator import RenkoCalculator
import pandas as pd

load_dotenv()

GATE_URL_HOST_LIVE = os.getenv("GATE_URL_HOST_LIVE")
SYMBOL_LIST = os.getenv("SYMBOL_LIST").split(",")
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME")
ATR_PERIOD = int(os.getenv("ATR_PERIOD"))
OHLCV_COUNT = int(os.getenv("OHLCV_COUNT"))
LEVERAGE = int(os.getenv("LEVERAGE"))


log.info("Starting backtest...")

gate_configuration = Configuration(host=GATE_URL_HOST_LIVE)
gate_client = ApiClient(configuration=gate_configuration)
gate_futures_api = FuturesApi(api_client=gate_client)

simulated_order_handler = SimulatedOrderHandler(
    gate_futures_api=gate_futures_api,
    symbol_list=SYMBOL_LIST,
    leverage=LEVERAGE,
)

renko_calculator = RenkoCalculator(
    symbol_list=SYMBOL_LIST,
    ohlcv_timeframe=OHLCV_TIMEFRAME,
    atr_period=ATR_PERIOD,
    ohlcv_count=OHLCV_COUNT,
    discord_client=None,
    order_handler=simulated_order_handler,
)


def fetch_historical_data(symbol):
    for symbol in SYMBOL_LIST:
        log.info(f"Fetching historical data for {symbol}...")
        csv_path = f"src/backtest/{symbol}_1h_candlesticks.csv"
        if os.path.exists(csv_path):
            df_1h = pd.read_csv(csv_path)
            candlestick_list = [
                FuturesCandlestick(
                    t=int(row["t"]),
                    o=float(row["o"]),
                    h=float(row["h"]),
                    l=float(row["l"]),
                    c=float(row["c"]),
                    v=float(row["v"]),
                )
                for _, row in df_1h.iterrows()
            ]
        else:
            log.info(f"CSV file for {symbol} not found. Skipping...")
            continue
        renko_calculator.set_ohlcv_list_into_symbol_data_list(
            symbol=symbol, candlestick_list=candlestick_list
        )

    renko_calculator.set_brick_size_into_symbol_data_list()
    renko_calculator.set_renko_list_into_symbol_data_list()

    log.info("Historical data loaded and Renko charts generated.")


def fetch_and_process_test_data():
    for symbol in SYMBOL_LIST:
        csv_1m_path = f"src/backtest/{symbol}_1m_candlesticks.csv"
        if os.path.exists(csv_1m_path):
            df_1m = pd.read_csv(csv_1m_path)
            log.info(f"Processing 1-minute data for {symbol}...")
        else:
            log.info(f"1-minute CSV file for {symbol} not found. Skipping...")
            continue

        for _, row in df_1m.iterrows():
            ticker_data = FuturesTicker(
                contract=symbol,
                last=float(row["c"]),
            )
            renko_calculator.handle_new_ticker_data([ticker_data])


def run_backtest():
    log.info("Running backtest...")
    fetch_historical_data(SYMBOL_LIST)
    fetch_and_process_test_data()


if __name__ == "__main__":
    run_backtest()
    log.info("Backtest completed successfully.")
