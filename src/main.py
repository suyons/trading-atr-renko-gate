import os

from dotenv import load_dotenv

from config.logger_config import log
from service.discord_rest_client import DiscordRestClient
from service.gate_rest_client import GateRestClient
from service.gate_ws_client import GateWsClient
from service.message_handler import MessageHandler
from service.renko_calculator import RenkoCalculator

load_dotenv()
GATE_REST_LIVE_URL = os.getenv("GATE_REST_LIVE_URL")
GATE_REST_TEST_URL = os.getenv("GATE_REST_TEST_URL")
GATE_WS_LIVE_URL = os.getenv("GATE_WS_LIVE_URL")
GATE_WS_TEST_URL = os.getenv("GATE_WS_TEST_URL")
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
SYMBOL = os.getenv("SYMBOL")
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def main():
    log.info("[Init] Starting the Real-time ATR Renko Trading Bot...")

    # Dependencies initialization
    gate_rest_client = GateRestClient(url=GATE_REST_TEST_URL)
    discord_client = DiscordRestClient(url=DISCORD_WEBHOOK_URL)
    renko_calculator = RenkoCalculator(
        symbol=SYMBOL,
        ohlcv_timeframe=OHLCV_TIMEFRAME,
        atr_period=14,
        discord_client=discord_client,
    )
    message_handler = MessageHandler()
    gate_websocket_client = GateWsClient(
        url=GATE_WS_TEST_URL,
        api_key=API_KEY,
        secret_key=SECRET_KEY,
        symbol=SYMBOL,
        message_handler=message_handler,
    )

    # Load the futures historical data
    ohlcv_history = gate_rest_client.get_futures_candlesticks(
        params={
            "contract": SYMBOL,
            "limit": 1000,
            "interval": OHLCV_TIMEFRAME,
        }
    )
    renko_calculator.set_ohlcv_history(ohlcv_history)
    renko_calculator.calculate_brick_size()
    renko_calculator.set_historical_bricks()
    renko_calculator.send_renko_plot_to_discord()

    # Subscribe to the WebSocket for real-time updates
    gate_websocket_client.run_forever()


if __name__ == "__main__":
    main()
