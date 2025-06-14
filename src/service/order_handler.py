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
        last_balance: float = 0.0,
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.renko_calculator = renko_calculator
        self.current_position_side = None  # 'long', 'short', or None
        self.current_position_opened_price = None
        self.current_position_size = None
        self.discord_notifier = discord_notifier
        self.last_balance = last_balance
        log.info(f"[Bot] Initialized OrderHandler for {self.symbol}")

    async def process_renko_bricks(self, new_bricks: list):
        """
        Receives newly formed Renko bricks and updates the internal history.
        Then, it checks for trading signals.
        """
        if not new_bricks:
            return

        for brick in new_bricks:
            await self._check_and_trade()

    async def _check_and_trade(self):
        """
        Checks the last 3 confirmed Renko bricks for trading signals and executes trades.
        """
        if len(self.renko_calculator.renko_bricks) < 3:
            return  # Not enough bricks to form a pattern

        last_bricks = self.renko_calculator.renko_bricks[-BRICK_COUNT:]
        directions = [b["direction"] for b in last_bricks]

        # Check for consecutive green (up) bricks
        if all(d == "up" for d in directions):
            if self.current_position_side != "long":
                await self.renko_calculator.send_renko_plot_to_discord(
                    self.discord_notifier
                )
                self.discord_notifier.push_log_buffer(
                    f"[Renko] Renko bricks count: {len(self.renko_calculator.renko_bricks)}, brick size: {self.renko_calculator.brick_size:.4g}, last close: {self.renko_calculator.last_renko_close:.6g}"
                )
                await self.discord_notifier.flush_log_buffer()
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
                await self.renko_calculator.send_renko_plot_to_discord(
                    self.discord_notifier
                )
                self.discord_notifier.push_log_buffer(
                    f"[Renko] Renko bricks count: {len(self.renko_calculator.renko_bricks)}, brick size: {self.renko_calculator.brick_size:.4g}, last close: {self.renko_calculator.last_renko_close:.6g}"
                )
                await self.discord_notifier.flush_log_buffer()
                if self.current_position_side == "long":
                    await self._execute_order("close_long")  # Close existing long first
                await self._execute_order("short")
            else:
                log.info("[Bot] Signal: Already SHORT.")

    async def _execute_order(self, order_type: str):
        """
        Executes a market order based on the specified order type.
        """

        try:
            if order_type == "long":
                order = await self.exchange.create_market_buy_order(
                    self.symbol, TRADE_AMOUNT
                )
                self.current_position_side = "long"
                self.current_position_opened_price = order[
                    "price"
                ]  # Use the actual filled price
                message = f"[Order] Open LONG {TRADE_AMOUNT} {self.symbol} at {self.current_position_opened_price:.6g}."
                self.discord_notifier.push_log_buffer(message)
            elif order_type == "short":
                order = await self.exchange.create_market_sell_order(
                    self.symbol, TRADE_AMOUNT
                )
                self.current_position_side = "short"
                self.current_position_opened_price = order[
                    "price"
                ]  # Use the actual filled price
                message = f"[Order] Open SHORT {TRADE_AMOUNT} {self.symbol} at {self.current_position_opened_price:.6g}."
                self.discord_notifier.push_log_buffer(message)
            elif order_type == "close_long":
                if self.current_position_side == "long":
                    order = await self.exchange.create_market_sell_order(
                        self.symbol, TRADE_AMOUNT, params={"reduceOnly": True}
                    )
                    balance = await self.exchange.fetch_balance()
                    total_wallet_balance = float(
                        balance.get("info", {}).get("totalWalletBalance", 0.0)
                    )
                    pnl = total_wallet_balance - self.last_balance
                    self.last_balance = total_wallet_balance
                    close_price = order["price"]
                    message = f"[Order] Close LONG {TRADE_AMOUNT} {self.symbol} at {close_price:.6g}."
                    self.discord_notifier.push_log_buffer(message)
                    message = f"[Order] PnL: {pnl:.2f}, Balance: {total_wallet_balance:.2f}"
                    self.discord_notifier.push_log_buffer(message)
                    self.current_position_side = None
                    self.current_position_opened_price = None
                else:
                    log.info("[Order] No active LONG position to close.")
            elif order_type == "close_short":
                if self.current_position_side == "short":
                    order = await self.exchange.create_market_buy_order(
                        self.symbol, TRADE_AMOUNT, params={"reduceOnly": True}
                    )
                    balance = await self.exchange.fetch_balance()
                    total_wallet_balance = float(
                        balance.get("info", {}).get("totalWalletBalance", 0.0)
                    )
                    pnl = total_wallet_balance - self.last_balance
                    self.last_balance = total_wallet_balance
                    close_price = order["price"]
                    message = (
                        f"[Order] Close SHORT {TRADE_AMOUNT} {self.symbol} at {close_price:.6g}."
                    )
                    self.discord_notifier.push_log_buffer(message)
                    message = f"[Order] PnL: {pnl:.2f}, Balance: {total_wallet_balance:.2f}"
                    self.discord_notifier.push_log_buffer(message)
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
                    self.current_position_side = pos.get(
                        "side"
                    )  # Use the 'side' field directly from the position dict
                    self.current_position_opened_price = pos.get("entryPrice")
                    self.current_position_size = abs(contracts)
                    log.info(
                        f"[Init] Previous position: {self.current_position_side}, entry price: {self.current_position_opened_price}, amount: {self.current_position_size}"
                    )
                    break
        except Exception as e:
            log.warning(f"[Init] Could not fetch current position from exchange: {e}")
