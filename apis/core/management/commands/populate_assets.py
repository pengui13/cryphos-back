import requests
from django.core.management.base import BaseCommand
from assets.models import AssetCryptoCoin

BINANCE_BASE_URL = "https://api.binance.com"


def get_top_symbols(limit: int = 50):
    """
    Fetch top N symbols by 24h volume from Binance.
    Returns list of base symbols (e.g., ['BTC', 'ETH', ...])
    """
    resp = requests.get(f"{BINANCE_BASE_URL}/api/v3/ticker/24hr")
    resp.raise_for_status()
    data = resp.json()

    # Filter only USDT pairs and sort by quote volume
    usdt_pairs = [
        t for t in data 
        if t["symbol"].endswith("USDT") 
        and not t["symbol"].endswith("DOWNUSDT")
        and not t["symbol"].endswith("UPUSDT")
        and "BEAR" not in t["symbol"]
        and "BULL" not in t["symbol"]
    ]
    
    sorted_pairs = sorted(
        usdt_pairs, 
        key=lambda x: float(x["quoteVolume"]), 
        reverse=True
    )

    top_symbols = []
    for pair in sorted_pairs[:limit]:
        symbol = pair["symbol"].replace("USDT", "")
        top_symbols.append({
            "symbol": symbol,
            "binance_symbol": pair["symbol"],
            "volume_24h": float(pair["quoteVolume"]),
        })

    return top_symbols


class Command(BaseCommand):
    help = "Fetch top 50 tokens by volume from Binance"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Number of top tokens to fetch (default: 50)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Just print symbols without saving",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        dry_run = options["dry_run"]

        self.stdout.write(f"Fetching top {limit} tokens from Binance...")

        symbols = get_top_symbols(limit)

        if dry_run:
            self.stdout.write("\nDry run - would save these symbols:\n")
            for i, s in enumerate(symbols, 1):
                self.stdout.write(f"  {i:2}. {s['symbol']:8} (${s['volume_24h']:,.0f} 24h vol)")
            return

        created_count = 0
        for s in symbols:
            _, created = AssetCryptoCoin.objects.get_or_create(symbol=s["symbol"])
            if created:
                created_count += 1
                self.stdout.write(f"  + {s['symbol']}")
            else:
                self.stdout.write(f"  • {s['symbol']} (exists)")

        self.stdout.write(
            self.style.SUCCESS(f"\nDone! Created {created_count} new, {len(symbols) - created_count} existed.")
        )