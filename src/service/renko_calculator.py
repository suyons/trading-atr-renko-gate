import numpy as np
from config.logger_config import log


class RenkoCalculator:
    """
    Calculates and generates Renko bricks based on incoming price data and ATR.
    """

    def __init__(self, atr_period: int):
        self.atr_period = atr_period
        self.ohlcv_history = (
            []
        )  # Stores OHLCV bars for ATR calculation: [timestamp, open, high, low, close, volume]
        self.current_atr = None
        self.brick_size = None
        self.renko_bricks = (
            []
        )  # Stores confirmed Renko bricks: {'open': float, 'close': float, 'direction': 'up'/'down'}
        self.last_renko_close = (
            None  # The closing price of the last confirmed Renko brick
        )

        log.info(
            f"[Renko] Initialized RenkoCalculator with ATR period: {self.atr_period}"
        )

    def add_ohlcv_data(self, ohlcv_bar: list):
        """
        Adds a new OHLCV bar to the history and recalculates ATR.
        This is crucial for keeping the ATR (and thus brick size) updated.
        """
        if len(ohlcv_bar) != 6:
            (f"[Renko] Warning: Invalid OHLCV bar format received: {ohlcv_bar}")
            return

        self.ohlcv_history.append(ohlcv_bar)
        # Keep history size manageable, but ensure enough for ATR calculation
        if len(self.ohlcv_history) > self.atr_period * 2:
            self.ohlcv_history.pop(0)  # Remove oldest bar

        self._calculate_atr()

    def _calculate_atr(self):
        """
        Calculates the Average True Range (ATR) based on the OHLCV history.
        """
        if (
            len(self.ohlcv_history) < self.atr_period + 1
        ):  # Need at least ATR_PERIOD + 1 bars for initial TR
            self.current_atr = None
            self.brick_size = None
            return

        true_ranges = []
        # Iterate from the second bar to calculate True Range
        for i in range(1, len(self.ohlcv_history)):
            high_curr = self.ohlcv_history[i][2]
            low_curr = self.ohlcv_history[i][3]
            close_prev = self.ohlcv_history[i - 1][4]

            tr1 = high_curr - low_curr
            tr2 = abs(high_curr - close_prev)
            tr3 = abs(low_curr - close_prev)
            true_ranges.append(max(tr1, tr2, tr3))

        # Calculate ATR as the simple moving average of True Ranges
        if len(true_ranges) >= self.atr_period:
            self.current_atr = np.mean(true_ranges[-self.atr_period :])
            # Set brick size directly to ATR. You might want to multiply by a factor (e.g., 0.5)
            # to get smaller bricks, or round it for cleaner price levels.
            self.brick_size = self.current_atr * 2
            log.info(
                f"[Renko] Updated ATR: {self.current_atr:.4f}, Calculated Brick Size: {self.brick_size:.4f}"
            )
        else:
            self.current_atr = None
            self.brick_size = None

    def process_new_price(self, current_price: float) -> list:
        """
        Processes a new incoming price and generates new Renko bricks if formed.
        Returns a list of newly formed bricks.
        """
        if self.brick_size is None:
            # Cannot form bricks without a calculated brick size (needs initial ATR)
            return []

        if self.last_renko_close is None:
            # Initialize the last_renko_close to the nearest multiple of brick_size
            # This ensures the first brick starts aligned with the grid.
            self.last_renko_close = (
                round(current_price / self.brick_size) * self.brick_size
            )
            log.info(
                f"[Renko] Initialized last_renko_close: {self.last_renko_close:.4f}"
            )
            return []  # No brick formed yet on initialization

        newly_formed_bricks = []
        price_diff = current_price - self.last_renko_close
        num_bricks = int(abs(price_diff) / self.brick_size)

        if num_bricks >= 1:
            # Determine the direction of the new brick(s)
            direction = "up" if price_diff > 0 else "down"

            # If the direction changes, we need to reverse the previous brick(s)
            # This is a common Renko rule: if price reverses, the previous brick is 'erased'
            # and new bricks are formed in the opposite direction.
            # For simplicity, this example just forms new bricks. A more advanced Renko
            # might remove previous bricks if direction changes significantly.
            # Here, we'll just ensure the new bricks are in the correct direction.

            for _ in range(num_bricks):
                if direction == "up":
                    brick_open = self.last_renko_close
                    brick_close = self.last_renko_close + self.brick_size
                else:  # direction == 'down'
                    brick_open = self.last_renko_close
                    brick_close = self.last_renko_close - self.brick_size

                new_brick = {
                    "open": brick_open,
                    "close": brick_close,
                    "direction": direction,
                }
                self.renko_bricks.append(new_brick)
                newly_formed_bricks.append(new_brick)
                self.last_renko_close = (
                    brick_close  # Update for the next potential brick
                )

                log.info(
                    f"[Renko] Formed new brick: {new_brick['direction']} from {new_brick['open']:.2f} to {new_brick['close']:.2f}"
                )

        return newly_formed_bricks
