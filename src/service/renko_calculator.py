import io

import matplotlib.pyplot as plt
import numpy as np
import talib

from config.logger_config import log
from config.env_config import SYMBOL, OHLCV_TIMEFRAME, ATR_PERIOD
import aiohttp


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
        if len(self.ohlcv_history) > 1000:
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
        if price_diff > 0:
            direction = "up"
        elif price_diff < 0:
            direction = "down"
        else:
            return []  # No price change, no brick formed

        if direction == "up":
            last_brick_direction = self.renko_bricks[-1]["direction"] if self.renko_bricks else "up"
            threshold_brick_size = self.brick_size if last_brick_direction == "up" else 2 * self.brick_size
            if price_diff >= threshold_brick_size:
                remaining_diff = price_diff - threshold_brick_size
                count_additional_bricks = (
                    int(remaining_diff // self.brick_size) if remaining_diff >= 0 else 0
                )

                for i in range(count_additional_bricks):
                    brick_open = self.last_renko_close
                    brick_close = brick_open + (
                        threshold_brick_size if i == 0 else self.brick_size
                    )
                    new_brick = {
                        "open": brick_open,
                        "close": brick_close,
                        "direction": "up",
                    }
                    self.renko_bricks.append(new_brick)
                    newly_formed_bricks.append(new_brick)
                    self.last_renko_close = brick_close
                direction = "up"

        elif direction == "down":
            last_brick_direction = (
                self.renko_bricks[-1]["direction"] if self.renko_bricks else "down"
            )
            threshold_brick_size = self.brick_size if last_brick_direction == "down" else 2 * self.brick_size
            if price_diff <= -threshold_brick_size:
                remaining_diff = -price_diff - threshold_brick_size
                count_additional_bricks = (
                    int(remaining_diff // self.brick_size) if remaining_diff >= 0 else 0
                )

                for i in range(count_additional_bricks):
                    brick_open = self.last_renko_close
                    brick_close = brick_open - (
                        threshold_brick_size if i == 0 else self.brick_size
                    )
                    new_brick = {
                        "open": brick_open,
                        "close": brick_close,
                        "direction": "down",
                    }
                    self.renko_bricks.append(new_brick)
                    newly_formed_bricks.append(new_brick)
                    self.last_renko_close = brick_close
                direction = "down"

        while len(self.renko_bricks) > 100:
            self.renko_bricks.pop(0)  # Remove the oldest brick

        return newly_formed_bricks

    def set_historical_bricks(self):
        """
        Rebuilds the renko_bricks list from ohlcv_history using the calculated ATR (brick size).
        This is useful for initializing the Renko structure from existing OHLCV data.
        """
        if not self.ohlcv_history or self.brick_size is None:
            log.warning(
                "[Renko] Cannot set historical bricks: missing OHLCV or ATR/brick size."
            )
            return

        self.renko_bricks = []
        self.last_renko_close = None

        for bar in self.ohlcv_history:
            current_price = bar[4]
            self.process_new_price(current_price)

    async def send_renko_plot_to_discord(self, notifier, message=""):
        """
        Plots the historical Renko bricks and sends the image to Discord using the provided DiscordNotifier.
        """
        if not self.renko_bricks:
            log.warning("[Renko] No Renko bricks to plot.")
            return None

        opens = [brick["open"] for brick in self.renko_bricks]
        closes = [brick["close"] for brick in self.renko_bricks]
        directions = [brick["direction"] for brick in self.renko_bricks]

        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor("black")
        ax.set_facecolor("black")
        for i, (open_price, close_price, direction) in enumerate(
            zip(opens, closes, directions)
        ):
            color = "green" if direction == "up" else "red"
            ax.plot([i, i], [open_price, close_price], color=color, linewidth=2)

        ax.set_title(f"{SYMBOL}, {OHLCV_TIMEFRAME} Renko ({ATR_PERIOD})", color="white")
        ax.set_xlabel("Brick Index", color="white")
        ax.set_ylabel("Price", color="white")
        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")
        ax.spines["bottom"].set_color("white")
        ax.spines["top"].set_color("white")
        ax.spines["left"].set_color("white")
        ax.spines["right"].set_color("white")

        buf = io.BytesIO()
        plt.savefig(buf, format="jpg", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)

        if notifier and notifier.webhook_url:
            try:
                data = aiohttp.FormData()
                data.add_field(
                    "file", buf, filename="renko.jpg", content_type="image/jpeg"
                )
                data.add_field("content", message)
                async with aiohttp.ClientSession() as session:
                    async with session.post(notifier.webhook_url, data=data) as resp:
                        if resp.status == 200:
                            log.info("[Discord] Renko plot sent successfully.")
                        else:
                            log.error(
                                f"[Discord] Failed to send plot. Status: {resp.status}"
                            )
                        return resp
            except Exception as e:
                log.error(f"[Discord Error] An error occurred: {e}")
                return None
        else:
            log.warning("[Discord] No webhook URL configured.")
            return buf
