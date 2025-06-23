import requests


class GateRestClient:
    def __init__(self, url, ohlcv_timeframe: str, ohlcv_count: int):
        self.url = url
        self.ohlcv_timeframe = ohlcv_timeframe
        self.ohlcv_count = ohlcv_count
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_futures_candlesticks(self, params):
        """
        Retrieve candlestick data for a specified futures contract.
        See: https://www.gate.com/docs/developers/apiv4/en/#get-futures-candlesticks

        Args:
            params (dict): Dictionary of request parameters. Example keys:
            - 'contract' (str, required): Futures contract (e.g., 'BTC_USDT').
            - 'from' (int, optional): Start time of candlesticks in Unix timestamp (seconds).
            - 'to' (int, optional): End time of candlesticks in Unix timestamp (seconds).
            - 'limit' (int, optional): Maximum number of recent data points to return.
            - 'interval' (str, optional): Interval between data points (e.g., '1m', '5m', '1h', '1d', '1w', '7d', '30d').

        Returns:
            list: List of candlestick data points. Each data point is a dict with:
            - t (float): Unix timestamp in seconds
            - v (int, optional): Size volume (contract size). Only returned if contract is not prefixed
            - c (str): Close price (quote currency)
            - h (str): Highest price (quote currency)
            - l (str): Lowest price (quote currency)
            - o (str): Open price (quote currency)
            - sum (str): Trading volume (unit: Quote currency)
        """
        path = f"/futures/usdt/candlesticks"
        response = requests.get(self.url + path, headers=self.headers, params=params)
        return response.json()

    def get_futures_candlesticks_bulk(self, params):
        """
        If 'limit' is greater than 1000, repeatedly call the API to fetch the desired amount of ohlcv data.

        Args:
            params (dict): Same as get_futures_candlesticks.
                - Enter the total desired count in the 'limit' key.

        Returns:
            list: Accumulated list of candlestick data
        """
        all_data = []
        total_limit = self.ohlcv_count if self.ohlcv_count else 1000
        fetch_limit = 1000
        params["limit"] = min(fetch_limit, total_limit)

        while len(all_data) < total_limit:
            data = self.get_futures_candlesticks(params)
            if not data:
                break
            all_data = data + all_data
            if len(data) < fetch_limit:
                break  # No more data available

            # Update the 'from' parameter for the next request with the last candlestick's timestamp + 1
            first_timestamp = float(data[0]["t"])
            params["to"] = int(first_timestamp) - self.get_seconds_by_timeframe()
            remain = total_limit - len(all_data)
            params["limit"] = min(fetch_limit, remain)

        return all_data[:total_limit]

    def get_seconds_by_timeframe(self) -> int:
        """
        Returns the number of seconds for the current ohlcv_timeframe.
        """
        timeframe_seconds = {
            "1s": 1,
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
            "1w": 604800,
        }
        return timeframe_seconds.get(self.ohlcv_timeframe)
