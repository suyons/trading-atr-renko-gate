import ccxt  # For synchronous historical data fetch
import ccxt.pro  # For asynchronous WebSocket connections

from config.logger_config import log
from config.env_config import TRADE_AMOUNT, BRICK_COUNT
from .renko_calculator import RenkoCalculator
from .discord_notifier import DiscordNotifier


class OrderHandler:
    """
    Manages trading strategy based on Renko bricks and executes orders.
    """

    def __init__(
        self,
        exchange: ccxt.pro.Exchange,
        symbol: str,
        renko_calculator: RenkoCalculator,
        discord_notifier: DiscordNotifier,
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.renko_calculator = renko_calculator
        self.confirmed_bricks_history = []  # Stores recent confirmed Renko bricks
        self.current_position_side = None  # 'long', 'short', or None
        self.current_position_opened_price = None
        self.current_position_size = None
        self.discord_notifier = discord_notifier
        log.info(f"[Bot] Initialized OrderHandler for {self.symbol}")

    async def process_renko_bricks(self, new_bricks: list):
        """
        Receives newly formed Renko bricks and updates the internal history.
        Then, it checks for trading signals.
        """
        if not new_bricks:
            return

        for brick in new_bricks:
            self.confirmed_bricks_history.append(brick)
            # Keep only the last few bricks relevant for the strategy (e.g., 3 + some buffer)
            if len(self.confirmed_bricks_history) > 5:
                self.confirmed_bricks_history.pop(0)  # Remove the oldest brick

            await self._check_and_trade()

    async def _check_and_trade(self):
        """
        Checks the last 3 confirmed Renko bricks for trading signals and executes trades.
        """
        if len(self.confirmed_bricks_history) < 3:
            return  # Not enough bricks to form a pattern

        last_bricks = self.confirmed_bricks_history[-BRICK_COUNT:]
        directions = [b["direction"] for b in last_bricks]

        # Check for consecutive green (up) bricks
        if all(d == "up" for d in directions):
            if self.current_position_side != "long":
                log.info(f"[Bot] Signal: Attempting to open LONG.")
                if self.current_position_side == "short":
                    await self._execute_order(
                        "close_short"
                    )  # Close existing short first
                await self._execute_order("long")
            else:
                log.info("[Bot] Signal: Already LONG.")

        # Check for consecutive red (down) bricks
        elif all(d == "down" for d in directions):
            if self.current_position_side != "short":
                log.info("[Bot] Signal: Attempting to open SHORT.")
                if self.current_position_side == "long":
                    await self._execute_order("close_long")  # Close existing long first
                await self._execute_order("short")
            else:
                log.info("[Bot] Signal: Already SHORT.")

        # Simple exit logic: If current position is long and a red brick appears, or vice versa
        # This is very basic; a real bot would have stop-loss, take-profit, etc.
        # if BRICK_COUNT > 1:
        #     if self.position == "long" and directions[-1] == "down":
        #         log.info(
        #             "[Bot] Exit Signal: Red brick after being LONG. Attempting to close LONG."
        #         )
        #         await self._execute_order("close_long")
        #     elif self.position == "short" and directions[-1] == "up":
        #         log.info(
        #             "[Bot] Exit Signal: Green brick after being SHORT. Attempting to close SHORT."
        #         )
        #         await self._execute_order("close_short")

    async def _execute_order(self, order_type: str):
        """
        Executes a market order based on the specified order type.
        """
        amount = TRADE_AMOUNT  # Use the configured trade amount

        try:
            if order_type == "long":
                log.info(f"[Order] Placing BUY order for {amount} {self.symbol}...")
                order = await self.exchange.create_market_buy_order(self.symbol, amount)
                self.current_position_side = "long"
                self.current_position_opened_price = order["price"]  # Use the actual filled price
                message = f"[Order] LONG position opened at: {self.current_position_opened_price:.6g}"
                log.info(message)
                self.discord_notifier.push_log_buffer(message)
            elif order_type == "short":
                log.info(f"[Order] Placing SELL order for {amount} {self.symbol}...")
                order = await self.exchange.create_market_sell_order(
                    self.symbol, amount
                )
                self.current_position_side = "short"
                self.current_position_opened_price = order["price"]  # Use the actual filled price
                message = f"[Order] SHORT position opened at: {self.current_position_opened_price:.6g}"
                log.info(message)
                self.discord_notifier.push_log_buffer(message)
            elif order_type == "close_long":
                if self.current_position_side == "long":
                    log.info(
                        f"[Order] Closing LONG position by selling {amount} {self.symbol}..."
                    )
                    order = await self.exchange.create_market_sell_order(
                        self.symbol, amount
                    )
                    pnl_price = (
                        order["price"] - self.current_position_opened_price if self.current_position_opened_price else 0
                    )
                    pnl_amount = amount * pnl_price
                    message = f"[Order] LONG position closed. PnL: {pnl_amount:.6g}"
                    self.discord_notifier.push_log_buffer(message)
                    log.info(message)
                    self.current_position_side = None
                    self.current_position_opened_price = None
                else:
                    log.info("[Order] No active LONG position to close.")
            elif order_type == "close_short":
                if self.current_position_side == "short":
                    log.info(
                        f"[Order] Closing SHORT position by buying {amount} {self.symbol}..."
                    )
                    order = await self.exchange.create_market_buy_order(
                        self.symbol, amount
                    )
                    pnl_price = (
                        self.current_position_opened_price - order["price"] if self.current_position_opened_price else 0
                    )
                    pnl_amount = amount * pnl_price
                    message = f"[Order] SHORT position closed. PnL: {pnl_amount:.6g}"
                    self.discord_notifier.push_log_buffer(message)
                    log.info(message)
                    self.current_position_side = None
                    self.current_position_opened_price = None
                else:
                    log.info("[Order] No active SHORT position to close.")
            else:
                log.warning(f"[Order] Unknown order type requested: {order_type}")
            await self.discord_notifier.flush_log_buffer()

        except ccxt.NetworkError as e:
            log.error(f"[Order Error] Network error during order execution: {e}")
        except ccxt.ExchangeError as e:
            log.error(f"[Order Error] Exchange error during order execution: {e}")
        except Exception as e:
            log.error(
                f"[Order Error] An unexpected error occurred during order execution: {e}"
            )

    async def close_all_positions(self):
        """
        Closes any open position (long or short) at market price.
        """
        if self.current_position_side == "long":
            log.info("[Order] Closing all: Detected open LONG position. Closing...")
            await self._execute_order("close_long")
        elif self.current_position_side == "short":
            log.info("[Order] Closing all: Detected open SHORT position. Closing...")
            await self._execute_order("close_short")
        else:
            log.info("[Order] No open positions to close.")

    async def set_initial_position_and_price(self):
        """
        Sets the initial position and open price from the exchange if possible.
        """
        try:
            positions = await self.exchange.fetch_positions([self.symbol])
            if not positions:
                log.info("[Init] No open positions found on exchange.")
                return
            for pos in positions:
                # Check if the symbol matches the configured SYMBOL exactly
                if (
                    pos.get("symbol") == self.symbol
                    and abs(pos.get("contracts", 0)) > 0
                ):
                    contracts = pos.get("contracts", 0)
                    self.current_position_side = pos.get("side")  # Use the 'side' field directly from the position dict
                    self.current_position_opened_price = pos.get("entryPrice")
                    self.current_position_size = abs(contracts)
                    log.info(
                        f"[Init] Previous position: {self.current_position_side}, entry price: {self.current_position_opened_price}, amount: {self.current_position_size}"
                    )
                    break
        except Exception as e:
            log.warning(f"[Init] Could not fetch current position from exchange: {e}")
