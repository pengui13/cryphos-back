from bots.models import RsiValue
from rest_framework import serializers

from assets.models import AssetCryptoCoin, HistQuotes


class AssetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCryptoCoin
        fields = ["symbol"]


class RsiSerializer(serializers.ModelSerializer):
    class Meta:
        model = RsiValue
        fields = ["value"]


class HistQuotesSerializer(serializers.ModelSerializer):

    symbol = serializers.CharField(source="symbol.symbol", read_only=True)

    class Meta:
        model = HistQuotes
        fields = [
            "symbol",
            "time",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
        ]
