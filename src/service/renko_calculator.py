import os
import io

import numpy as np
import matplotlib.pyplot as plt
import talib
import requests

from config.logger_config import log

SYMBOL = os.getenv("SYMBOL")
OHLCV_TIMEFRAME = os.getenv("OHLCV_TIMEFRAME")
ATR_PERIOD = os.getenv("ATR_PERIOD")


class RenkoCalculator:
    """
    Calculates and generates Renko bricks based on incoming price data and ATR.
    """

    def __init__(self):
        self.current_atr = None
        self.brick_size = None
        self.last_renko_close = None
        self.ohlcv_history = []
        self.renko_bricks = []

    def set_ohlcv_history(self, ohlcv_history: list):
        """
        Adds new OHLCV bars (list of dicts) to the history and recalculates ATR.
        Each ohlcv_bar should be a dict with keys: 'o', 'h', 'l', 'c', 'v', 't', 'sum'.
        """
        required_keys = {"o", "h", "l", "c", "v", "t"}
        for ohlcv_bar in ohlcv_history:
            if not isinstance(ohlcv_bar, dict) or not required_keys.issubset(ohlcv_bar):
                log.warning(
                    f"[Renko] Warning: Invalid OHLCV bar format received: {ohlcv_bar}"
                )
                continue

            try:
                bar = [
                    float(ohlcv_bar["o"]),
                    float(ohlcv_bar["h"]),
                    float(ohlcv_bar["l"]),
                    float(ohlcv_bar["c"]),
                    float(ohlcv_bar["v"]),
                    int(ohlcv_bar["t"]),
                ]
            except Exception as e:
                log.warning(f"[Renko] Error parsing OHLCV bar: {ohlcv_bar} ({e})")
                continue

            self.ohlcv_history.append(bar)
            # Keep history size manageable, but ensure enough for ATR calculation
            if len(self.ohlcv_history) > 1000:
                self.ohlcv_history.pop(0)  # Remove oldest bar

    def calculate_atr(self):
        if len(self.ohlcv_history) < int(ATR_PERIOD) + 1:
            self.current_atr = None
            self.brick_size = None
            return

        highs = [bar[1] for bar in self.ohlcv_history]
        lows = [bar[2] for bar in self.ohlcv_history]
        closes = [bar[3] for bar in self.ohlcv_history]

        atr_values = talib.ATR(
            high=np.array(highs, dtype=np.float64),
            low=np.array(lows, dtype=np.float64),
            close=np.array(closes, dtype=np.float64),
            timeperiod=int(ATR_PERIOD),
        )

        if atr_values[-1] is not None and not np.isnan(atr_values[-1]):
            self.current_atr = atr_values[-1]
            self.brick_size = float(self.current_atr)
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
            last_brick_direction = (
                self.renko_bricks[-1]["direction"] if self.renko_bricks else "up"
            )
            threshold_brick_size = (
                self.brick_size if last_brick_direction == "up" else 2 * self.brick_size
            )
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
            threshold_brick_size = (
                self.brick_size
                if last_brick_direction == "down"
                else 2 * self.brick_size
            )
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

    def send_renko_plot_to_discord(self, notifier, message=""):
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
                data = {"content": message}
                files = {"file": ("renko.jpg", buf, "image/jpeg")}
                response = requests.post(notifier.webhook_url, data=data, files=files)
                if response.status_code == 200:
                    log.info("[Discord] Renko plot sent successfully.")
                else:
                    log.error(
                        f"[Discord] Failed to send plot. Status: {response.status_code}"
                    )
                return response
            except Exception as e:
                log.error(f"[Discord Error] An error occurred: {e}")
                return None
        else:
            log.warning("[Discord] No webhook URL configured.")
            return buf
