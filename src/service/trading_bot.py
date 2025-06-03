import ccxt  # For synchronous historical data fetch
import ccxt.pro  # For asynchronous WebSocket connections

from config.logger_config import log
from .renko_calculator import RenkoCalculator
from config.env_config import TRADE_AMOUNT


class TradingBot:
    """
    Manages trading strategy based on Renko bricks and executes orders.
    """

    def __init__(
        self,
        exchange: ccxt.pro.Exchange,
        symbol: str,
        renko_calculator: RenkoCalculator,
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.renko_calculator = renko_calculator
        self.confirmed_bricks_history = []  # Stores recent confirmed Renko bricks
        self.position = None  # 'long', 'short', or None
        self.open_price = None  # Price at which the current position was opened

        log.info(f"[Bot] Initialized TradingBot for {self.symbol}")

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

        last_three_bricks = self.confirmed_bricks_history[-3:]
        directions = [b["direction"] for b in last_three_bricks]

        # Check for 3 consecutive green (up) bricks
        if all(d == "up" for d in directions):
            if self.position != "long":
                log.info(
                    "[Bot] Signal: 3 consecutive GREEN Renko bricks. Attempting to open LONG."
                )
                if self.position == "short":
                    await self._execute_order(
                        "close_short"
                    )  # Close existing short first
                await self._execute_order("long")
            else:
                log.info(
                    "[Bot] Signal: 3 consecutive GREEN Renko bricks. Already LONG."
                )

        # Check for 3 consecutive red (down) bricks
        elif all(d == "down" for d in directions):
            if self.position != "short":
                log.info(
                    "[Bot] Signal: 3 consecutive RED Renko bricks. Attempting to open SHORT."
                )
                if self.position == "long":
                    await self._execute_order("close_long")  # Close existing long first
                await self._execute_order("short")
            else:
                log.info("[Bot] Signal: 3 consecutive RED Renko bricks. Already SHORT.")

        # Simple exit logic: If current position is long and a red brick appears, or vice versa
        # This is very basic; a real bot would have stop-loss, take-profit, etc.
        if self.position == "long" and directions[-1] == "down":
            log.info(
                "[Bot] Exit Signal: Red brick after being LONG. Attempting to close LONG."
            )
            await self._execute_order("close_long")
        elif self.position == "short" and directions[-1] == "up":
            log.info(
                "[Bot] Exit Signal: Green brick after being SHORT. Attempting to close SHORT."
            )
            await self._execute_order("close_short")

    async def _execute_order(self, order_type: str):
        """
        Executes a market order based on the specified order type.
        """
        amount = TRADE_AMOUNT  # Use the configured trade amount

        try:
            if order_type == "long":
                log.info(f"[Order] Placing BUY order for {amount} {self.symbol}...")
                order = await self.exchange.create_market_buy_order(self.symbol, amount)
                self.position = "long"
                self.open_price = order["price"]  # Use the actual filled price
                log.info(f"[Order] LONG position opened at: {self.open_price:.4f}")
            elif order_type == "short":
                log.info(f"[Order] Placing SELL order for {amount} {self.symbol}...")
                order = await self.exchange.create_market_sell_order(
                    self.symbol, amount
                )
                self.position = "short"
                self.open_price = order["price"]  # Use the actual filled price
                log.info(f"[Order] SHORT position opened at: {self.open_price:.4f}")
            elif order_type == "close_long":
                if self.position == "long":
                    log.info(
                        f"[Order] Closing LONG position by selling {amount} {self.symbol}..."
                    )
                    order = await self.exchange.create_market_sell_order(
                        self.symbol, amount
                    )
                    pnl = order["price"] - self.open_price if self.open_price else 0
                    log.info(f"[Order] LONG position closed. PnL: {pnl:.4f}")
                    self.position = None
                    self.open_price = None
                else:
                    log.info("[Order] No active LONG position to close.")
            elif order_type == "close_short":
                if self.position == "short":
                    log.info(
                        f"[Order] Closing SHORT position by buying {amount} {self.symbol}..."
                    )
                    order = await self.exchange.create_market_buy_order(
                        self.symbol, amount
                    )
                    pnl = self.open_price - order["price"] if self.open_price else 0
                    log.info(f"[Order] SHORT position closed. PnL: {pnl:.4f}")
                    self.position = None
                    self.open_price = None
                else:
                    log.info("[Order] No active SHORT position to close.")
            else:
                log.warning(f"[Order] Unknown order type requested: {order_type}")

        except ccxt.NetworkError as e:
            log.error(f"[Order Error] Network error during order execution: {e}")
        except ccxt.ExchangeError as e:
            log.error(f"[Order Error] Exchange error during order execution: {e}")
        except Exception as e:
            log.error(
                f"[Order Error] An unexpected error occurred during order execution: {e}"
            )
