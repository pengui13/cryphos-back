from .models import Bot
from . import serializers
from rest_framework.exceptions import ValidationError
from django.db import transaction


class BotService:

    @staticmethod
    def create_with_indicators(request):
        serializer = serializers.BotSerializer(
                     data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        validated_data = serializer.validated_data
        with transaction.atomic():
            assets = validated_data.pop("bot_assets", [])
            bot = Bot.objects.create(owner=request.user, **validated_data)
            bot.assets.set(assets)
            IndicatorService.create_for_bot(bot, request.data)
            bot.activate()
        return bot


serializer_classes = {
    "rsi": serializers.RsiIndicatorSerializer,
    "bb": serializers.BollingerBandsIndicatorSerializer,
    "sr": serializers.SupportResistanceIndicatorSerializer,
    "ema": serializers.EmaIndicatorSerializer,
    "ma": serializers.MaIndicatorSerializer,
    "fib": serializers.FiboSerializer,
}


class IndicatorService:
    @staticmethod
    def create_for_bot(bot, raw_data: dict):
        for key, serializer_class in serializer_classes.items():
            if key in raw_data and isinstance(raw_data[key], dict):
                ind_ser = serializer_class(
                    data=raw_data[key], context={"bot": bot}
                )
                if not ind_ser.is_valid():
                    raise ValidationError({key: ind_ser.errors})
                ind_ser.save()
