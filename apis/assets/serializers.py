from bots.models import FundingRate
from rest_framework import serializers

from assets.models import AssetCryptoCoin, HistQuotes


class AssetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCryptoCoin
        fields = ["symbol"]

    def to_representation(self, instance):
        return instance.symbol


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


class FundingRateSerializer(serializers.ModelSerializer):
    asset = serializers.SerializerMethodField()

    def get_asset(self, obj):
        return obj.asset.symbol

    class Meta:
        model = FundingRate
        fields = ["id", "asset", "rate", "funding_time", "exchange"]