import io
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import talib

from gate_api.models.futures_candlestick import FuturesCandlestick
from gate_api.models.futures_ticker import FuturesTicker

from config.logger_config import log
from service.discord_client import DiscordClient
from service.order_handler import OrderHandler


class RenkoCalculator:
    """
    Calculates and generates Renko bricks based on incoming price data and ATR.
    """

    def __init__(
        self,
        symbol_list: list[str],
        ohlcv_timeframe: str,
        atr_period: int,
        ohlcv_count: int,
        discord_client: DiscordClient,
        order_handler: OrderHandler = None,
    ):
        self.symbol_data_list = []
        self.symbol_list = symbol_list
        self.ohlcv_timeframe = ohlcv_timeframe
        self.atr_period = atr_period
        self.ohlcv_count = ohlcv_count
        self.discord_client = discord_client
        self.order_handler = order_handler

    def set_ohlcv_list_into_symbol_data_list(
        self, symbol: str, candlestick_list: list[FuturesCandlestick]
    ):
        """
        Adds new OHLCV bars (list of dicts) to the history and recalculates ATR.
        Updates self.total_symbols_ohlcv_list to maintain per-symbol OHLCV data.
        Each ohlcv_bar should be a dict with keys: 'o', 'h', 'l', 'c', 'v', 't', 'sum'.
        """
        # Parse bars from input
        if not candlestick_list or len(candlestick_list) == 0:
            raise ValueError("[Renko] ohlcv_list must be a non-empty list.")

        parsed_ohlcv_list = []
        for candlestick_row in candlestick_list:
            parsed_ohlcv_row = [
                float(candlestick_row.o),
                float(candlestick_row.h),
                float(candlestick_row.l),
                float(candlestick_row.c),
                float(candlestick_row.v),
                int(candlestick_row.t),
            ]
            parsed_ohlcv_list.append(parsed_ohlcv_row)

        self.symbol_data_list.append(
            {
                "symbol": symbol,
                "ohlcv_list": parsed_ohlcv_list,
            }
        )

    def set_brick_size_into_symbol_data_list(self):
        """
        Iterates over each symbol in symbol_data_list and calculates renko_brick_size
        using the symbol's ohlcv_list and ATR.
        """
        for symbol_data in self.symbol_data_list:
            ohlcv_list = symbol_data.get("ohlcv_list")
            if not ohlcv_list or len(ohlcv_list) < self.atr_period + 1:
                symbol_data["renko_brick_size"] = None
                continue

            highs = [
                bar[1] if isinstance(bar, list) else float(bar["h"])
                for bar in ohlcv_list
            ]
            lows = [
                bar[2] if isinstance(bar, list) else float(bar["l"])
                for bar in ohlcv_list
            ]
            closes = [
                bar[3] if isinstance(bar, list) else float(bar["c"])
                for bar in ohlcv_list
            ]

            atr_values = talib.ATR(
                high=np.array(highs, dtype=np.float64),
                low=np.array(lows, dtype=np.float64),
                close=np.array(closes, dtype=np.float64),
                timeperiod=self.atr_period,
            )

            if atr_values[-1] is not None and not np.isnan(atr_values[-1]):
                symbol_data["renko_brick_size"] = float(atr_values[-1])
                log.info(
                    f"[Renko] {symbol_data.get('symbol')} brick_size: {symbol_data['renko_brick_size']:.4g}"
                )
            else:
                symbol_data["renko_brick_size"] = None

    def set_renko_list_into_symbol_data_list(self):
        """
        For each symbol in symbol_data_list, rebuilds the renko_list from ohlcv_list using the calculated renko_brick_size.
        """
        for symbol_data in self.symbol_data_list:
            ohlcv_list = symbol_data.get("ohlcv_list")
            renko_brick_size = symbol_data.get("renko_brick_size")
            if not ohlcv_list or not renko_brick_size:
                log.warning(
                    f"[Renko] Cannot set historical bricks for {symbol_data.get('symbol')}: missing OHLCV or brick size."
                )
                symbol_data["renko_list"] = []
                continue

            renko_bricks = []
            last_renko_close = None

            for ohlcv_row in ohlcv_list:
                current_price = (
                    ohlcv_row[3]
                    if isinstance(ohlcv_row, list)
                    else float(ohlcv_row["c"])
                )
                if last_renko_close is None:
                    last_renko_close = (
                        round(current_price / renko_brick_size) * renko_brick_size
                    )
                    continue

                price_diff = current_price - last_renko_close
                if price_diff == 0:
                    continue

                direction = "up" if price_diff > 0 else "down"
                last_brick_direction = (
                    renko_bricks[-1]["direction"] if renko_bricks else direction
                )
                threshold_brick_size = (
                    renko_brick_size
                    if last_brick_direction == direction
                    else 2 * renko_brick_size
                )

                if (direction == "up" and price_diff >= threshold_brick_size) or (
                    direction == "down" and price_diff <= -threshold_brick_size
                ):
                    total_diff = abs(price_diff)
                    first_brick_size = threshold_brick_size
                    remaining_diff = total_diff - first_brick_size
                    count_additional_bricks = (
                        1 + int(remaining_diff // renko_brick_size)
                        if remaining_diff >= 0
                        else 1
                    )

                    for i in range(count_additional_bricks):
                        brick_open = last_renko_close
                        if direction == "up":
                            brick_close = brick_open + (
                                first_brick_size if i == 0 else renko_brick_size
                            )
                        else:
                            brick_close = brick_open - (
                                first_brick_size if i == 0 else renko_brick_size
                            )
                        new_brick = {
                            "open": brick_open,
                            "close": brick_close,
                            "direction": direction,
                        }
                        renko_bricks.append(new_brick)
                        last_renko_close = brick_close
                        first_brick_size = renko_brick_size
            if len(renko_bricks) > 200:
                renko_bricks = renko_bricks[-200:]
            symbol_data["renko_list"] = renko_bricks

    def handle_new_ticker_data(self, ticker_data_list: list[FuturesTicker]):
        """
        Processes new incoming ticker data, updates renko_list in self.symbol_data_list.
        Only processes symbols present in self.symbol_data_list.
        If a new brick is formed, appends it to renko_list.
        If a buy/sell signal (brick direction changes), sends order via order_handler.
        """
        # 1. validate ticker_data
        if (
            not ticker_data_list
            or not isinstance(ticker_data_list, list)
            or not isinstance(ticker_data_list[0], FuturesTicker)
        ):
            # If ticker_data_list is empty or not a list
            log.warning("[Renko] Invalid ticker_data_list format.")
            return

        # 2. filter ticker_data to only include valid symbols
        filtered_ticker_data_list = [
            {
                "contract": ticker_data.contract,
                "last": ticker_data.last,
            }
            for ticker_data in ticker_data_list
            if ticker_data.contract in self.symbol_list
        ]

        for filtered_ticker_data in filtered_ticker_data_list:
            symbol = filtered_ticker_data.get("contract")
            last_str = filtered_ticker_data.get("last")
            try:
                current_price = float(last_str)
            except (ValueError, TypeError):
                continue

            # Find symbol_data for this symbol
            symbol_data = next(
                (s for s in self.symbol_data_list if s.get("symbol") == symbol), None
            )
            if not symbol_data:
                continue

            brick_size = symbol_data.get("renko_brick_size")
            if brick_size is None:
                continue

            renko_bricks = symbol_data.setdefault("renko_list", [])
            last_renko_close = (
                renko_bricks[-1]["close"]
                if renko_bricks
                else symbol_data.get("last_renko_close")
            )
            last_brick_direction = (
                renko_bricks[-1]["direction"] if renko_bricks else None
            )

            if last_renko_close is None:
                last_renko_close = round(current_price / brick_size) * brick_size
                symbol_data["last_renko_close"] = last_renko_close
                continue

            price_diff = current_price - last_renko_close
            if price_diff == 0:
                continue

            direction = "up" if price_diff > 0 else "down"
            threshold_brick_size = (
                brick_size
                if last_brick_direction == direction or last_brick_direction is None
                else 2 * brick_size
            )

            if (direction == "up" and price_diff >= threshold_brick_size) or (
                direction == "down" and price_diff <= -threshold_brick_size
            ):
                total_diff = abs(price_diff)
                first_brick_size = threshold_brick_size
                remaining_diff = total_diff - first_brick_size
                count_additional_bricks = (
                    1 + int(remaining_diff // brick_size) if remaining_diff >= 0 else 1
                )

                for i in range(count_additional_bricks):
                    brick_open = last_renko_close
                    if direction == "up":
                        brick_close = brick_open + (
                            first_brick_size if i == 0 else brick_size
                        )
                    else:
                        brick_close = brick_open - (
                            first_brick_size if i == 0 else brick_size
                        )
                    new_brick = {
                        "open": brick_open,
                        "close": brick_close,
                        "direction": direction,
                    }
                    renko_bricks.append(new_brick)
                    # Trade signal processing
                    if (
                        last_brick_direction
                        and direction != last_brick_direction
                        and self.order_handler
                    ):
                        side = "buy" if direction == "up" else "sell"
                        try:
                            self.send_renko_plot_to_discord(symbol)
                            self.order_handler.place_market_close_order_if_position_opened(
                                symbol
                            )
                            self.order_handler.place_market_open_order(symbol, side)
                        except Exception as e:
                            log.error(f"[Renko] Order error for {symbol}: {e}")
                    last_brick_direction = direction
                    last_renko_close = brick_close
                    first_brick_size = brick_size
                symbol_data["last_renko_close"] = last_renko_close

            # Keep only last 200 bricks
            if len(renko_bricks) > 200:
                symbol_data["renko_list"] = renko_bricks[-200:]

    def send_renko_plot_to_discord(self, symbol: str):
        """
        Plots the historical Renko bricks for the given symbol and sends the image to Discord.
        """
        # Find symbol_data for the given symbol
        symbol_data = next(
            (s for s in self.symbol_data_list if s.get("symbol") == symbol), None
        )
        if not symbol_data or not symbol_data.get("renko_list"):
            log.warning(f"[Renko] No Renko bricks to plot for symbol: {symbol}")
            return None

        renko_bricks = symbol_data["renko_list"]
        opens = [brick["open"] for brick in renko_bricks]
        closes = [brick["close"] for brick in renko_bricks]
        directions = [brick["direction"] for brick in renko_bricks]

        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor("black")
        ax.set_facecolor("black")
        for i, (open_price, close_price, direction) in enumerate(
            zip(opens, closes, directions)
        ):
            color = "green" if direction == "up" else "red"
            ax.plot([i, i], [open_price, close_price], color=color, linewidth=2)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ax.set_title(
            f"{symbol}, {self.ohlcv_timeframe} Renko ({self.atr_period}), {current_time}",
            color="white",
            loc="center",
            fontsize=14,
        )
        ax.set_xlabel("Brick Index", color="white")
        ax.set_ylabel("Price", color="white")
        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")
        ax.spines["bottom"].set_color("white")
        ax.spines["top"].set_color("white")
        ax.spines["left"].set_color("white")
        ax.spines["right"].set_color("white")

        buffer = io.BytesIO()
        plt.savefig(buffer, format="jpg", facecolor=fig.get_facecolor())
        plt.close(fig)
        buffer.seek(0)

        self.discord_client.send_image(buffer)
        buffer.close()
