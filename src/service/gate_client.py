import hashlib
import hmac
import json
import time

import requests
from requests.exceptions import HTTPError


class GateClient:
    def __init__(
        self,
        url_host: str,
        url_prefix: str,
        api_key: str,
        secret_key: str,
        ohlcv_timeframe: str,
        ohlcv_count: int,
    ):
        self.url_host = url_host
        self.url_prefix = url_prefix
        self.api_key = api_key
        self.secret_key = secret_key
        self.ohlcv_timeframe = ohlcv_timeframe
        self.ohlcv_count = ohlcv_count
        self.request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _convert_timeframe_to_seconds(timeframe: str) -> int:
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
        return timeframe_seconds.get(timeframe, 60)

    def _generate_signature(self, method, url, query_string=None, payload_string=None):
        t = int(time.time())
        m = hashlib.sha512()
        m.update((payload_string or "").encode("utf-8"))
        hashed_payload = m.hexdigest()
        s = "%s\n%s\n%s\n%s\n%s" % (method, url, query_string or "", hashed_payload, t)
        sign = hmac.new(
            self.secret_key.encode("utf-8"), s.encode("utf-8"), hashlib.sha512
        ).hexdigest()
        return {"KEY": self.api_key, "Timestamp": str(t), "SIGN": sign}

    def get_futures_accounts(self):
        """
        Retrieve futures account information.
        See: https://www.gate.com/docs/developers/apiv4/en/#get-futures-accounts

        Returns:
            dict: Futures account information including:
            - id (str): Account ID
            - type (str): Account type (e.g., 'futures')
            - balance (str): Total balance in quote currency
            - available (str): Available balance in quote currency
            - hold (str): Held balance in quote currency
            - risk_limit (int): Risk limit for the account
            - position_margin (str): Margin used for positions in quote currency
            - unrealised_pnl (str): Unrealized profit and loss in quote currency
        """
        path = "/futures/usdt/accounts"
        sign_headers = self._generate_signature(
            "GET",
            self.url_prefix + path,
            "",
        )
        request_headers = {**self.request_headers, **sign_headers}
        response = requests.get(
            self.url_host + self.url_prefix + path, headers=request_headers
        )
        if response.status_code != 200:
            raise HTTPError(
                f"[Gate] Error fetching futures accounts: {response.status_code} - {response.text}"
            )
        return response.json()

    def get_futures_tickers(self, params=None):
        """
        List futures tickers.

        Parameters:
            settle (str, required, in path): Settle currency ('btc', 'usdt').
            contract (str, optional, in query): Futures contract, return related data only if specified.

        Returns:
            list: List of futures tickers. Each ticker is a dict with:
            - contract (str): Futures contract
            - last (str): Last trading price
            - change_percentage (str): Change percentage
            - total_size (str): Contract total size
            - low_24h (str): Lowest trading price in recent 24h
            - high_24h (str): Highest trading price in recent 24h
            - volume_24h (str): Trade size in recent 24h
            - volume_24h_btc (str): Trade volumes in recent 24h in BTC (deprecated)
            - volume_24h_usd (str): Trade volumes in recent 24h in USD (deprecated)
            - volume_24h_base (str): Trade volume in recent 24h, in base currency
            - volume_24h_quote (str): Trade volume in recent 24h, in quote currency
            - volume_24h_settle (str): Trade volume in recent 24h, in settle currency
            - mark_price (str): Recent mark price
            - funding_rate (str): Funding rate
            - funding_rate_indicative (str): Indicative Funding rate in next period (deprecated)
            - index_price (str): Index price
            - quanto_base_rate (str): Exchange rate of base and settlement currency in Quanto contract
            - lowest_ask (str): Recent lowest ask
            - lowest_size (str): Latest seller's lowest price order quantity
            - highest_bid (str): Recent highest bid
            - highest_size (str): Latest buyer's highest price order volume
        """
        path = "/futures/usdt/tickers"
        response = requests.get(
            self.url_host + self.url_prefix + path,
            headers=self.request_headers,
            params=params or {},
        )
        if response.status_code != 200:
            raise HTTPError(
                f"[Gate] Error fetching futures tickers: {response.status_code} - {response.text}"
            )
        return response.json()

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
        response = requests.get(
            self.url_host + self.url_prefix + path,
            headers=self.request_headers,
            params=params,
        )
        if response.status_code != 200:
            raise HTTPError(
                f"[Gate] Error fetching futures candlesticks: {response.status_code} - {response.text}"
            )
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
            params["to"] = int(first_timestamp) - self._convert_timeframe_to_seconds(
                self.ohlcv_timeframe
            )
            remain = total_limit - len(all_data)
            if remain < 1:
                break
            params["limit"] = min(fetch_limit, remain)

        return all_data[:total_limit]

    # TODO: fix 401 INVALID_SIGNATURE error
    def post_futures_order(self, params):
        """
        Place a futures order.

        Parameters:
            params (dict): Dictionary of request parameters. Keys:
            - contract (str, required): Futures contract (e.g., 'BTC_USDT').
            - size (int, required): Order size. Positive for buy, negative for sell.
            - iceberg (int, optional): Display size for iceberg order. 0 for non-iceberg.
            - price (str, optional): Order price. 0 for market order with tif='ioc'.
            - close (bool, optional): Set True to close the position (size=0).
            - reduce_only (bool, optional): Set True for reduce-only order.
            - tif (str, optional): Time in force. One of ['gtc', 'ioc', 'poc', 'fok'].
            - text (str, optional): Custom order info. Must start with 't-' and max 28 bytes if not reserved. Only numbers, letters, '_', '-', '.' allowed.
            - auto_size (str, optional): For dual-mode close. 'close_long' or 'close_short'. Requires size=0.
            - stp_act (str, optional): Self-Trading Prevention Action. One of ['co', 'cn', 'cb', '-'].
            - settle (str, required in path): Settle currency, e.g., 'usdt' or 'btc'.

        Returns:
            dict: API response with order details.

        Notes:
            - 'tif' (Time in force):
            'gtc': GoodTillCancelled,
            'ioc': ImmediateOrCancelled,
            'poc': PendingOrCancelled (post-only),
            'fok': FillOrKill.
            - 'text': Custom info for order identification. Reserved values: 'web', 'api', 'app', 'auto_deleveraging', 'liquidation', 'liq-xxx', 'hedge-liq-xxx', 'pm_liquidate', 'comb_margin_liquidate', 'scm_liquidate', 'insurance'.
            - 'stp_act': Self-trade prevention. Only for users in STP group.
        """
        path = "/futures/usdt/orders"
        sign_headers = self._generate_signature(
            "POST",
            self.url_prefix + path,
            "",
            payload_string=json.dumps(params),
        )
        sign_headers.update(self.request_headers)
        response = requests.post(
            self.url_host + self.url_prefix + path,
            headers=sign_headers,
            data=params,
        )
        if response.status_code != 201:
            raise HTTPError(
                f"[Gate] Error placing futures order: {response.status_code} - {response.text}"
            )
        return response.json()
