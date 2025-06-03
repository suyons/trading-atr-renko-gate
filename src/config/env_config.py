import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
ATR_PERIOD = int(os.getenv("ATR_PERIOD", 14))
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME", "1m")
INITIAL_OHLCV_LIMIT = int(os.getenv("INITIAL_OHLCV_LIMIT", 5000))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 1))
BRICK_COUNT = int(os.getenv("BRICK_COUNT", 1))
