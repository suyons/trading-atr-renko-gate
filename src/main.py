import os
import asyncio
from datetime import datetime

from config.logger_config import log
from service.ohlcv_loader import OHLCVLoader
from service.renko_calculator import RenkoCalculator
from service.order_handler import OrderHandler
from config.exchange_config import get_exchange_authenticated, get_exchange_public
from config.env_config import (
    API_KEY,
    SECRET_KEY,
    SYMBOL,
    OHLCV_TIMEFRAME,
    ATR_PERIOD,
    INITIAL_OHLCV_LIMIT,
)

# Logging configuration
os.makedirs("../logs", exist_ok=True)
log_filename = datetime.now().strftime("../logs/%Y-%m-%d.log")


async def main():
    log.info("Starting the Real-time ATR Renko Trading Bot...")

    # 1. Initialize authenticated & public exchange using exchange_config
    exchange_authenticated = await get_exchange_authenticated(API_KEY, SECRET_KEY, log)
    if not exchange_authenticated:
        return
    exchange_public = get_exchange_public()

    # 2. Initialize Renko Calculator
    renko_calc = RenkoCalculator(atr_period=ATR_PERIOD)

    # 3. Fetch initial historical OHLCV data using the public exchange instance
    log.info(
        f"[Init] Fetching initial historical OHLCV data for {SYMBOL} ({OHLCV_TIMEFRAME}) using public access..."
    )
    ohlcv_loader = OHLCVLoader(exchange_public, SYMBOL, OHLCV_TIMEFRAME, log)
    all_ohlcv_historical = await ohlcv_loader.load_ohlcv_data(INITIAL_OHLCV_LIMIT)

    if not all_ohlcv_historical:
        log.error(
            f"[Init Error] Failed to fetch any historical OHLCV data for {SYMBOL}. Exiting."
        )
        await exchange_authenticated.close()
        return

    # 4. Add historical OHLCV data to the Renko calculator
    for bar in all_ohlcv_historical:
        renko_calc.add_ohlcv_data(bar)
    log.info(
        f"[Init] Loaded {len(all_ohlcv_historical)} historical OHLCV bars for Renko ATR calculation. Brick size: {renko_calc.brick_size:.4g}"
    )

    # 5. Initialize Trading Bot with the authenticated exchange
    order_handler = OrderHandler(exchange_authenticated, SYMBOL, renko_calc)

    # 6. Start WebSocket data stream and process prices using the authenticated exchange
    log.info(f"[Data Stream] Starting WebSocket stream for {SYMBOL} trades...")
    while True:
        try:
            # watch_trades provides individual trade data, which is most granular for Renko
            trades = await exchange_authenticated.watch_trades(SYMBOL)
            for trade in trades:
                # 'price' is the most important for Renko calculation
                current_price = trade["price"]
                # Uncomment for verbose trade data
                # log.info(f"[Data] New trade price: {current_price}")

                # Feed the new price to the Renko calculator
                new_bricks = renko_calc.process_new_price(current_price)

                # If new bricks are formed, pass them to the trading bot
                if new_bricks:
                    await order_handler.process_renko_bricks(new_bricks)

            await asyncio.sleep(0.01)  # Small delay to prevent busy-waiting
        except Exception as e:
            log.error(
                f"[Data Stream Error] An unexpected error occurred: {e}. Retrying in 5 seconds..."
            )
            await asyncio.sleep(5)
        finally:
            # Ensure connection is closed on exit or error
            pass  # await exchange_authenticated.close() # This might close prematurely if in a loop


# --- Run the bot ---
if __name__ == "__main__":
    # asyncio.run() is the entry point for asynchronous programs
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("\nBot stopped manually by user (KeyboardInterrupt).")
    except Exception as e:
        log.error(f"An unhandled error occurred during bot execution: {e}")
