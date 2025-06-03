from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
SYMBOL = os.getenv("SYMBOL")
ATR_PERIOD = int(os.getenv("ATR_PERIOD"))
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME")
INITIAL_OHLCV_LIMIT = int(os.getenv("INITIAL_OHLCV_LIMIT"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))
