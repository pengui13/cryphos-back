from decimal import Decimal

from assets.models import AssetCryptoCoin
from rest_framework import serializers

from .models import (
    AtrIndicator,
    BollingerBandsIndicator,
    Bot,
    BotStat,
    EmaIndicator,
    FiboIndicator,
    FundingRate,
    MacdIndicator,
    MaIndicator,
    ObvIndicator,
    RiskSettings,
    RsiIndicator,
    Signal,
    SupportResistanceIndicator,
)

ALLOWED_TFS = {"1MIN", "5MIN", "15MIN", "30MIN", "1HRS", "1DAY"}


class FundingRateSerializer(serializers.ModelSerializer):
    asset = serializers.SerializerMethodField()

    def get_asset(self, obj):
        return obj.asset.symbol

    class Meta:
        model = FundingRate
        fields = ["id", "asset", "rate", "funding_time", "exchange"]


class BotSerializer(serializers.ModelSerializer):
    MAX_ASSETS = 15

    bot_assets = serializers.SlugRelatedField(
        many=True,
        slug_field="symbol",
        queryset=AssetCryptoCoin.objects.all(),
    )

    rsi = serializers.SerializerMethodField()
    bb = serializers.SerializerMethodField()
    sr = serializers.SerializerMethodField()
    ema = serializers.SerializerMethodField()
    ma = serializers.SerializerMethodField()
    fib = serializers.SerializerMethodField()

    def get_rsi(self, obj):
        ind = obj.rsi_indicators.first()
        return RsiIndicatorSerializer(ind).data if ind else None

    def get_bb(self, obj):
        ind = obj.bollinger_bands_indicators.first()
        return BollingerBandsIndicatorSerializer(ind).data if ind else None

    def get_ma(self, obj):
        ind = obj.ma_indicators.first()
        return MaIndicatorSerializer(ind).data if ind else None

    def get_fib(self, obj):
        ind = obj.fibo_indicators.first()
        return FiboSerializer(ind).data if ind else None

    def get_ema(self, obj):
        ind = obj.ema_indicators.first()
        return EmaIndicatorSerializer(ind).data if ind else None

    def get_sr(self, obj):
        ind = obj.sr_indicators.first()
        return SupportResistanceIndicatorSerializer(ind).data if ind else None

    class Meta:
        model = Bot
        fields = [
            "id",
            "created_at",
            "bot_assets",
            "roi",
            "pnl",
            "rsi",
            "bb",
            "sr",
            "ema",
            "ma",
            "last_activated",
            "fib",
        ]
        read_only_fields = [
            "created_at",
            "roi",
            "rsi",
            "bb",
            "sr",
            "pnl",
            "ema",
            "ma",
            "last_activated",
            "id",
            "fib",
        ]



class SignalSerializer(serializers.ModelSerializer):
    asset = serializers.CharField(source="asset.symbol", read_only=True)

    class Meta:
        model = Signal
        fields = ["asset", "bot", "close_price", "closed_at",
                  "created_at", "is_long", "is_open", "open_price"]
        read_only_fields = fields


class SupportResistanceIndicatorSerializer(serializers.ModelSerializer):
    intervals = serializers.ListField(
        child=serializers.ChoiceField(choices=sorted(ALLOWED_TFS)), allow_empty=False
    )

    class Meta:
        model = SupportResistanceIndicator
        fields = [
            "id",
            "mode",
            "intervals",
            "lookback",
            "levels_count",
            "zone_mode",
            "atr_period",
            "atr_mult",
            "fixed_width",
            "merge_dist_atr",
            "pivot_type",
            "pivot_tf",
            "vwap_enabled",
            "vwap_bands",
        ]

    def create(self, validated_data):
        bot = self.context.get("bot")
        if bot is None:
            raise serializers.ValidationError("Bot context is required.")
        return SupportResistanceIndicator.objects.create(bot=bot, **validated_data)


class BotStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotStat
        fields = ["pnl", "roi", "timestamp"]


class ObvIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObvIndicator
        fields = ["intervals"]

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class FiboSerializer(serializers.ModelSerializer):
    VALID_LEVELS = [
        Decimal("0"),
        Decimal("23.6"),
        Decimal("38.2"),
        Decimal("50"),
        Decimal("61.8"),
        Decimal("78.6"),
        Decimal("100"),
    ]

    class Meta:
        model = FiboIndicator
        fields = ["intervals", "period", "levels"]

    def validate_levels(self, values):
        for value in values:
            if value not in self.VALID_LEVELS:
                raise serializers.ValidationError(f"{value} is not a valid Fibonacci level")
        return values

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class RsiIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = RsiIndicator
        fields = ["intervals", "min", "max", "period"]

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class EmaIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmaIndicator
        fields = ["intervals", "period"]

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class MaIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaIndicator
        fields = ["intervals", "period"]

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class MacdIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = MacdIndicator
        fields = ["intervals", "fast_period", "slow_period", "signal_period"]

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class BollingerBandsIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = BollingerBandsIndicator
        fields = ["intervals", "period", "std_dev"]

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class AtrIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = AtrIndicator
        fields = ["intervals", "period"]

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class RiskSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskSettings
        fields = ["take_profit", "stop_loss"]

