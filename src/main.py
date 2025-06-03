import os
import asyncio
from datetime import datetime

import ccxt.pro

from config.logger_config import log
from service.renko_calculator import RenkoCalculator
from service.trading_bot import TradingBot
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
    """
    Orchestrates the data fetching, Renko calculation, and trading logic.
    """
    log.info("Starting the Real-time ATR Renko Trading Bot...")

    # 1. Initialize CCXT Exchange for authenticated operations (trading, real-time data)
    # This still requires API keys for trading and watch_trades
    # You can change the exchange to another one supported by ccxt if needed.
    exchange_authenticated = ccxt.pro.gate(
        {
            "apiKey": API_KEY,
            "secret": SECRET_KEY,
            "enableRateLimit": True,  # Respect exchange rate limits
            "options": {
                "defaultType": "swap",  # "spot" or "swap" for perpetual contracts on gate.io
            },
        }
    )

    # Test API credentials (optional but recommended)
    try:
        balance = await exchange_authenticated.fetch_balance()
        log.info(
            f"[Init] Successfully connected to exchange (authenticated). Account balance fetched."
        )
        # log.info(f"Balance: {balance['total']}") # Uncomment to see your balance
    except Exception as e:
        log.error(
            f"[Init Error] Failed to connect to exchange (authenticated) or fetch balance. Check API keys and permissions: {e}"
        )
        await exchange_authenticated.close()
        return

    # 2. Initialize CCXT Exchange for public historical data (no API key needed)
    # This uses the synchronous ccxt library, so we'll run its fetch_ohlcv in an executor.
    # You can change this to another exchange if needed, but ensure it supports the required methods.
    exchange_public = ccxt.gate(
        {
            "enableRateLimit": True,  # Still good practice for public endpoints
        }
    )

    # 3. Initialize Renko Calculator
    renko_calc = RenkoCalculator(atr_period=ATR_PERIOD)

    # 4. Fetch initial historical OHLCV data using the public exchange instance
    log.info(
        f"[Init] Fetching initial historical OHLCV data for {SYMBOL} ({OHLCV_TIMEFRAME}) using public access..."
    )
    total_limit_historical = INITIAL_OHLCV_LIMIT  # Use the configured limit (100000)
    limit_per_request = 1000  # Max per request
    since = None
    all_ohlcv_historical = []

    loop = asyncio.get_event_loop()  # Get the current event loop

    while len(all_ohlcv_historical) < total_limit_historical:
        try:
            # Run the synchronous fetch_ohlcv in a separate thread
            ohlcv_chunk = await loop.run_in_executor(
                None,  # Use the default thread pool executor
                exchange_public.fetch_ohlcv,
                SYMBOL,
                OHLCV_TIMEFRAME,
                since,
                limit_per_request,
            )

            if not ohlcv_chunk:
                log.info(
                    "[Init] No more historical data to fetch or reached end of available data."
                )
                break

            # Prepend new data to maintain chronological order from oldest to newest
            all_ohlcv_historical = ohlcv_chunk + all_ohlcv_historical
            # Update 'since' for the next request to fetch older data
            # Subtract 1ms to ensure we don't fetch the same bar again
            since = all_ohlcv_historical[0][0] - 1

            log.info(
                f"[Init] Fetched {len(ohlcv_chunk)} records, total historical: {len(all_ohlcv_historical)}"
            )

            # If the fetched chunk is less than the limit, it means we've reached the end of available data
            if len(ohlcv_chunk) < limit_per_request:
                log.info(
                    "[Init] Less than limit_per_request fetched, likely reached end of available data."
                )
                break

        except Exception as e:
            log.error(
                f"[Init Error] Error fetching historical OHLCV: {e}. Retrying in 5 seconds..."
            )
            await asyncio.sleep(5)
            # Break to avoid infinite loop if persistent error
            break  # Exit loop on error to prevent indefinite retries

    if not all_ohlcv_historical:
        log.error(
            f"[Init Error] Failed to fetch any historical OHLCV data for {SYMBOL}. Exiting."
        )
        await exchange_authenticated.close()
        return

    # Feed the fetched historical data to the Renko calculator
    for bar in all_ohlcv_historical:
        renko_calc.add_ohlcv_data(bar)
    log.info(
        f"[Init] Loaded {len(all_ohlcv_historical)} historical OHLCV bars for Renko ATR calculation."
    )

    # 5. Initialize Trading Bot with the authenticated exchange
    trading_bot = TradingBot(exchange_authenticated, SYMBOL, renko_calc)

    # 6. Start WebSocket data stream and process prices using the authenticated exchange
    log.info(f"[Data Stream] Starting WebSocket stream for {SYMBOL} trades...")
    while True:
        try:
            # watch_trades provides individual trade data, which is most granular for Renko
            trades = await exchange_authenticated.watch_trades(SYMBOL)
            for trade in trades:
                # 'price' is the most important for Renko calculation
                current_price = trade["price"]
                # log.info(f"[Data] New trade price: {current_price}") # Uncomment for verbose trade data

                # Feed the new price to the Renko calculator
                new_bricks = renko_calc.process_new_price(current_price)

                # If new bricks are formed, pass them to the trading bot
                if new_bricks:
                    await trading_bot.process_renko_bricks(new_bricks)

            await asyncio.sleep(0.01)  # Small delay to prevent busy-waiting

        except ccxt.NetworkError as e:
            log.error(
                f"[Data Stream Error] Network error: {e}. Retrying in 5 seconds..."
            )
            await asyncio.sleep(5)
        except ccxt.ExchangeError as e:
            log.error(
                f"[Data Stream Error] Exchange error: {e}. Retrying in 5 seconds..."
            )
            await asyncio.sleep(5)
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
    # Ensure your API keys are set above before running!
    # asyncio.run() is the entry point for asynchronous programs
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("\nBot stopped manually by user (KeyboardInterrupt).")
    except Exception as e:
        log.error(f"An unhandled error occurred during bot execution: {e}")
