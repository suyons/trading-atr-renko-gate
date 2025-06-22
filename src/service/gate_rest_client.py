import requests


class GateRestClient:
    def __init__(self, url):
        self.url = url
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


# 사용 예시
if __name__ == "__main__":
    client = GateRestClient()
    data = client.get_futures_candlesticks("BTC_USDT")
    print(data)
