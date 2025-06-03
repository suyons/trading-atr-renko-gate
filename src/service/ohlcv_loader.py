import asyncio


class OHLCVLoader:
    def __init__(self, exchange_public, symbol, timeframe, logger):
        self.exchange_public = exchange_public
        self.symbol = symbol
        self.timeframe = timeframe
        self.logger = logger

    def timeframe_to_milliseconds(self, timeframe: str) -> int:
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        if unit == "s":
            return value * 1000
        elif unit == "m":
            return value * 60 * 1000
        elif unit == "h":
            return value * 60 * 60 * 1000
        elif unit == "d":
            return value * 24 * 60 * 60 * 1000
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

    async def load_ohlcv_data(self, total_limit, limit_per_request=1000):
        since = None
        all_ohlcv = []
        loop = asyncio.get_event_loop()

        while len(all_ohlcv) < total_limit:
            try:
                ohlcv_chunk = await loop.run_in_executor(
                    None,
                    self.exchange_public.fetch_ohlcv,
                    self.symbol,
                    self.timeframe,
                    since,
                    limit_per_request,
                )

                if not ohlcv_chunk:
                    self.logger.info(
                        "[Init] No more historical data to fetch or reached end of available data."
                    )
                    break

                all_ohlcv = ohlcv_chunk + all_ohlcv
                since = all_ohlcv[0][0] - self.timeframe_to_milliseconds(self.timeframe)

                if len(ohlcv_chunk) < limit_per_request:
                    self.logger.info(
                        "[Init] Less than limit_per_request fetched, likely reached end of available data."
                    )
                    break

            except Exception as e:
                self.logger.error(
                    f"[Init Error] Error fetching historical OHLCV: {e}. Retrying in 5 seconds..."
                )
                await asyncio.sleep(5)
                break

        return all_ohlcv
