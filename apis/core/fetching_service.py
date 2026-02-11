import requests


class FetchingService:

    URL = "https://api.binance.com/api/v3/klines"

    def __init__(self, symbol: str, interval: str, limit: int = 2):
        self.symbol = symbol.upper() + "USDT"
        self.interval = interval
        self._params = {"symbol": self.symbol, "interval": self.interval, "limit": limit}

    def fetch_klines(self):
        response = requests.get(self.URL, params=self._params)
        data = response.json()

        if isinstance(data, dict) and "code" in data:
            print(f"Binance error for {self.symbol}: {data}")
            return []

        return data
