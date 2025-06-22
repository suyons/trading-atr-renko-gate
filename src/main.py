import asyncio

from config.logger_config import log
from service.ohlcv_loader import OHLCVLoader
from service.renko_calculator import RenkoCalculator
from service.order_handler import OrderHandler
from service.discord_notifier import DiscordNotifier
from config.exchange_config import get_exchange_authenticated, get_exchange_public
from config.env_config import (
    API_KEY,
    SECRET_KEY,
    SYMBOL,
    OHLCV_TIMEFRAME,
    ATR_PERIOD,
    INITIAL_OHLCV_LIMIT,
)


async def main():
    log.info("[Init] Starting the Real-time ATR Renko Trading Bot...")

    # 1. Initialize authenticated & public exchange using exchange_config
    exchange_authenticated = await get_exchange_authenticated(API_KEY, SECRET_KEY)
    if not exchange_authenticated:
        log.error(
            "[Init Error] Failed to initialize authenticated exchange. Check API keys and permissions."
        )
        return
    exchange_public = get_exchange_public()

    # 2. Initialize Renko Calculator
    renko_calculator = RenkoCalculator(atr_period=ATR_PERIOD)

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
        renko_calculator.add_ohlcv_data(bar)
    log.info(
        f"[Init] Loaded {len(all_ohlcv_historical)} historical OHLCV bars for Renko ATR calculation. Brick size: {renko_calculator.brick_size:.4g}"
    )

    renko_calculator.set_historical_bricks()
    balance = await exchange_authenticated.fetch_balance()
    total_wallet_balance = float(balance.get("info", {}).get("totalWalletBalance", 0.0))

    # 5. Initialize Trading Bot with the authenticated exchange
    discord_notifier = DiscordNotifier()
    order_handler = OrderHandler(
        exchange_authenticated,
        SYMBOL,
        renko_calculator,
        discord_notifier,
        total_wallet_balance,
    )

    await renko_calculator.send_renko_plot_to_discord(discord_notifier)
    discord_notifier.push_log_buffer(
        f"[Init] Renko trading bot initialized for {SYMBOL}, {OHLCV_TIMEFRAME}"
    )
    discord_notifier.push_log_buffer(
        f"[Renko] Renko bricks count: {len(renko_calculator.renko_bricks)}, brick size: {renko_calculator.brick_size:.4g}, last close: {renko_calculator.last_renko_close:.6g}"
    )
    await discord_notifier.flush_log_buffer()
    await order_handler.set_initial_position_and_price()
    await order_handler.close_all_positions()

    # 6. Start WebSocket data stream and process prices using the authenticated exchange
    log.info(f"[Websocket] Starting WebSocket stream for {SYMBOL} trades...")
    while True:
        try:
            # watch_trades provides individual trade data, which is most granular for Renko
            trades = await exchange_authenticated.watch_trades(SYMBOL)

            if trades:
                # Use only the most recent trade's price
                current_price = trades[-1]["price"]

                # Feed the new price to the Renko calculator
                new_bricks = renko_calculator.process_new_price(current_price)
                await order_handler.process_renko_bricks(new_bricks)

            await asyncio.sleep(0.01)  # Small delay to prevent busy-waiting
        except Exception as e:
            log.error(
                f"[Websocket Error] An unexpected error occurred: {e}. Retrying in 5 seconds..."
            )
            await asyncio.sleep(5)


# --- Run the bot ---
if __name__ == "__main__":
    # asyncio.run() is the entry point for asynchronous programs
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("\nBot stopped manually by user (KeyboardInterrupt).")
    except Exception as e:
        log.error(f"An unhandled error occurred during bot execution: {e}")
