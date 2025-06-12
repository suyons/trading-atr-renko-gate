import numpy as np
import talib

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
        if len(self.ohlcv_history) < self.atr_period + 1:
            self.current_atr = None
            self.brick_size = None
            return

        highs = [bar[2] for bar in self.ohlcv_history]
        lows = [bar[3] for bar in self.ohlcv_history]
        closes = [bar[4] for bar in self.ohlcv_history]

        atr_values = talib.ATR(
            high=np.array(highs),
            low=np.array(lows),
            close=np.array(closes),
            timeperiod=self.atr_period,
        )

        if atr_values[-1] is not None:
            self.current_atr = atr_values[-1]
            self.brick_size = self.current_atr
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
                f"[Renko] Initialized last_renko_close: {self.last_renko_close:.6g}"
            )
            return []  # No brick formed yet on initialization

        newly_formed_bricks = []
        price_diff = current_price - self.last_renko_close
        direction = "up" if price_diff > 0 else "down"

        while True:
            diff = current_price - self.last_renko_close
            if direction == "up":
                # Same direction: need brick_size, reversal: need 2*brick_size
                threshold = self.brick_size if (not self.renko_bricks or self.renko_bricks[-1]["direction"] == "up") else 2 * self.brick_size
                if diff >= threshold:
                    brick_open = self.last_renko_close
                    brick_close = self.last_renko_close + threshold
                    new_brick = {
                        "open": brick_open,
                        "close": brick_close,
                        "direction": "up",
                    }
                    self.renko_bricks.append(new_brick)
                    newly_formed_bricks.append(new_brick)
                    self.last_renko_close = brick_close
                    log.info(
                        f"[Renko] Formed new brick up: {brick_open:.6g} -> {brick_close:.6g}"
                    )
                    # For the next brick, threshold=brick_size
                    direction = "up"
                else:
                    break
            else:
                # Same direction: need brick_size, reversal: need 2*brick_size
                threshold = self.brick_size if (not self.renko_bricks or self.renko_bricks[-1]["direction"] == "down") else 2 * self.brick_size
                if diff <= -threshold:
                    brick_open = self.last_renko_close
                    brick_close = self.last_renko_close - threshold
                    new_brick = {
                        "open": brick_open,
                        "close": brick_close,
                        "direction": "down",
                    }
                    self.renko_bricks.append(new_brick)
                    newly_formed_bricks.append(new_brick)
                    self.last_renko_close = brick_close
                    log.info(
                        f"[Renko] Formed new brick down: {brick_open:.6g} -> {brick_close:.6g}"
                    )
                    direction = "down"
                else:
                    break

        return newly_formed_bricks