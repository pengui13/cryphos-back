from assets.models import AssetCryptoCoin
from rest_framework import serializers

from .models import (
    AtrIndicator,
    BollingerBandsIndicator,
    Bot,
    BotBalance,
    BotStat,
    EmaIndicator,
    FundingRate,
    MacdIndicator,
    MainBotSettings,
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

    def get_rsi(self, obj):
        ind = obj.rsi_indicators.first()
        return RsiIndicatorSerializer(ind).data if ind else None

    def get_bb(self, obj):
        ind = obj.bollinger_bands_indicators.first()
        return BollingerBandsIndicatorSerializer(ind).data if ind else None

    def get_ma(self, obj):
        ind = obj.ma_indicators.first()
        return MaIndicatorSerializer(ind).data if ind else None

    def get_ema(self, obj):
        ind = obj.ema_indicators.first()
        return EmaIndicatorSerializer(ind).data if ind else None

    def get_sr(self, obj):
        ind = obj.sr_indicators.first()
        return SupportResistanceIndicatorSerializer(ind).data if ind else None

    class Meta:
        model = Bot
        fields = [
            "created_at",
            "bot_assets",
            "is_active",
            "description",
            "roi",
            "pnl",
            "rsi",
            "bb",
            "sr",
            "ema",
            "ma",
            "accuracy",
            "frequency",
            "max_drawdown",
            "risk",
            "last_activated",
            "runtime",
            "last_heartbeat",
            "id",
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
            "runtime",
            "last_heartbeat",
            "id",
        ]

    def create(self, validated_data):
        assets = validated_data.pop("bot_assets", [])
        validated_data["owner"] = self.context["request"].user
        bot = Bot.objects.create(**validated_data)
        bot.bot_assets.set(assets)
        return bot


class SignalSerializer(serializers.ModelSerializer):
    asset = serializers.SerializerMethodField()

    def get_asset(self, obj):
        return obj.asset.symbol

    class Meta:
        model = Signal
        fields = "__all__"


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


class MainBotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MainBotSettings
        fields = "__all__"


class RsiIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = RsiIndicator
        fields = ["intervals", "min", "max", "period"]

    def create(self, validated_data):
        bot = self.context["bot"]
        validated_data["bot"] = bot
        return super().create(validated_data)


class BotBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotBalance
        fields = ["bot", "initial_balance"]

    def create(self, validated_data):
        validated_data["current_balance"] = validated_data["initial_balance"]
        validated_data["user"] = self.context["request"].user
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


class GetBotSubscribers(serializers.ModelSerializer):
    class Meta:
        model = BotBalance
        fields = ["initial_balance", "current_balance", "unrealised_pnl"]


class RiskSerializer(serializers.ModelSerializer):
    take_profit = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0.01,
        max_value=100,
        required=False,
        allow_null=True,
    )
    stop_loss = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0.01,
        max_value=100,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = RiskSettings
        fields = ["take_profit", "stop_loss"]

    def validate_take_profit(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Take profit must be greater than 0")
        return value

    def validate_stop_loss(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Stop loss must be greater than 0")
        return value
