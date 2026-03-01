import requests
from django.conf import settings


class FetchingService:

    def __init__(self, symbol: str, interval: str, limit: int = 2):
        self.symbol = symbol.upper() + "USDT"
        self.interval = interval
        self._params = {"symbol": self.symbol, "interval": self.interval, "limit": limit}

    def fetch_klines(self):
        response = requests.get(settings.KLINES_URL, params=self._params)
        data = response.json()

        if isinstance(data, dict) and "code" in data:
            return []

        return data
