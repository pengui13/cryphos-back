import requests
from loguru import logger
from decimal import Decimal
from django.conf import settings
from django.db.models import QuerySet
from bots.models import FundingRate
from assets.models import AssetCryptoCoin


class TaskUtilsService:

    @classmethod
    def fetch_last_prices(assets: QuerySet[AssetCryptoCoin]) -> list[tuple[AssetCryptoCoin, dict]]:
        results = []


        return results
    
    @classmethod
    def fetch_funding_rates(assets: QuerySet[AssetCryptoCoin]) -> list[tuple[AssetCryptoCoin, dict]]:
        results = []

        with requests.Session() as session:
            for asset in assets:
                try:
                    response = session.get(settings.FUNDING_URL,
                                           params={"symbol": f"{asset.symbol}USDT",
                                           "limit": 1},
                                           timeout=10)
                    response.raise_for_status()
                    result = response.json()[0]
                    results.append((asset, result))
                except Exception as e:
                    logger.error(f"Funding rate error for {asset.symbol}: {e}")
        return results

    @classmethod
    def save_funding_rates(results: list[tuple[AssetCryptoCoin, dict]]) -> None:
        rates = [
            FundingRate(
                    asset=asset,
                    exchange='binance',
                    rate=Decimal(result["fundingRate"]),
                    funding_time=result["fundingTime"],
                )
            for asset, result in results
        ]
        try:
            FundingRate.objects.bulk_create(
                rates,
                update_conflicts=True,
                unique_fields=["asset", "exchange"],
                update_fields=["rate", "funding_time"],
            )

        except Exception as e:
            logger.error(e)
