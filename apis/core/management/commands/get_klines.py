import time
import requests
from django.core.management.base import BaseCommand

from assets.models import HistQuotes, AssetCryptoCoin

BINANCE_BASE_URL = "https://api.binance.com"

SUPPORTED_TIMEFRAMES = {
    "1m": "1MIN",
    "5m": "5MIN",
    "15m": "15MIN",
    "30m": "30MIN",
    "1h": "1HRS",
    "1d": "1DAY",
}


def fetch_klines(symbol: str, interval: str, limit: int = 200):
    """
    Fetch last N candles for a symbol/interval from Binance.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    resp = requests.get(f"{BINANCE_BASE_URL}/api/v3/klines", params=params)
    resp.raise_for_status()
    data = resp.json()

    return [
        {
            "time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in data
    ]


class Command(BaseCommand):
    help = "Fetch last 200 candles for all assets in DB from Binance"

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbol",
            type=str,
            default=None,
            help="Specific asset symbol. If not set, fetches all assets in DB.",
        )
        parser.add_argument(
            "--interval",
            type=str,
            default=None,
            help="Specific interval to fetch (e.g., 1d). If not set, fetches all.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Number of candles to fetch (default: 200)",
        )

    def handle(self, *args, **options):
        specific_symbol = options["symbol"]
        specific_interval = options["interval"]
        limit = options["limit"]

        # Get assets to process
        if specific_symbol:
            assets = AssetCryptoCoin.objects.filter(symbol=specific_symbol)
            if not assets.exists():
                self.stderr.write(f"Asset {specific_symbol} not found")
                return
        else:
            assets = AssetCryptoCoin.objects.all()

        if not assets.exists():
            self.stderr.write("No assets in database. Run fetch_assets first.")
            return

        self.stdout.write(f"Processing {assets.count()} assets...\n")

        intervals_to_fetch = (
            {specific_interval: SUPPORTED_TIMEFRAMES[specific_interval]}
            if specific_interval
            else SUPPORTED_TIMEFRAMES
        )

        total_saved = 0
        failed_assets = []

        for asset in assets:
            binance_symbol = asset.trading_pair or f"{asset.symbol}USDT"
            self.stdout.write(f"\n[{asset.symbol}] ({binance_symbol})")

            for binance_interval, db_interval in intervals_to_fetch.items():
                try:
                    candles = fetch_klines(binance_symbol, binance_interval, limit)

                    if not candles:
                        self.stderr.write(f"  {db_interval}: No candles returned")
                        continue

                    HistQuotes.objects.filter(
                        symbol=asset,
                        interval=db_interval,
                    ).delete()

                    quotes_to_create = [
                        HistQuotes(
                            symbol=asset,
                            interval=db_interval,
                            time=c["time"] / 1000,
                            volume=c["volume"],
                            open_price=c["open"],
                            high_price=c["high"],
                            low_price=c["low"],
                            close_price=c["close"],
                        )
                        for c in candles
                    ]

                    HistQuotes.objects.bulk_create(quotes_to_create, ignore_conflicts=True)
                    total_saved += len(quotes_to_create)
                    self.stdout.write(f"  {db_interval}: {len(quotes_to_create)} candles")

                except requests.exceptions.HTTPError as e:
                    self.stderr.write(self.style.ERROR(f"  {db_interval}: HTTP error - {e}"))
                    if asset.symbol not in failed_assets:
                        failed_assets.append(asset.symbol)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"  {db_interval}: Error - {e}"))
                    if asset.symbol not in failed_assets:
                        failed_assets.append(asset.symbol)

                time.sleep(0.1)

        # Summary
        self.stdout.write("\n" + "=" * 40)
        self.stdout.write(self.style.SUCCESS(f"Done! Saved {total_saved} total candles"))
        
        if failed_assets:
            self.stdout.write(self.style.WARNING(f"Failed assets: {', '.join(failed_assets)}"))