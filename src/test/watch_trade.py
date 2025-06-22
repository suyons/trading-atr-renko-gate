import asyncio

from config.exchange_config import get_exchange_authenticated
from config.env_config import (
    API_KEY,
    SECRET_KEY,
    SYMBOL,
)
from config.logger_config import log


async def main():
    exchange_authenticated = await get_exchange_authenticated(API_KEY, SECRET_KEY)
    if not exchange_authenticated:
        log.error(
            "[Init Error] Failed to initialize authenticated exchange. Check API keys and permissions."
        )
        return
    log.info(f"[Websocket] Starting WebSocket stream for {SYMBOL} trades...")
    while True:
        try:
            # watch_trades provides individual trade data, which is most granular for Renko
            trades = await exchange_authenticated.watch_trades(SYMBOL)

            if trades:
                # Use only the most recent trade's price
                log.info(f"[Websocket] Received new trade data for {SYMBOL}: {trades}")
            await asyncio.sleep(0.01)  # Small delay to prevent busy-waiting
        except Exception as e:
            log.error(
                f"[Websocket Error] An unexpected error occurred: {e}. Retrying in 5 seconds..."
            )
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
