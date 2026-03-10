from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import DestroyAPIView, ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import serializers
from .models import (
    Bot,
    FundingRate,
    RiskSettings,
    Signal,
)
from .utils import RedisService


class GetFnGValue(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        values = ["fng", "fng_class"]
        results = RedisService.get_values(values)
        return Response(results)


class GetSignals(ListAPIView):
    serializer_class = serializers.SignalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Signal.objects.filter(
            bot_id=self.kwargs.get('pk'),
            bot__owner=self.request.user
        ).select_related('asset').order_by('-created_at')


class DeleteMyBot(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Bot.objects.filter(owner=self.request.user)


# TODO rename to /me

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ping(request):
    return Response({"ping": True})


class GetFundingRates(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.FundingRateSerializer
    queryset = FundingRate.objects.all()


class GetBotsList(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.BotSerializer

    def get_queryset(self):
        return Bot.objects.filter(owner=self.request.user)


class RiskSettingsView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.RiskSerializer

    def get_object(self):
        obj, _ = RiskSettings.objects.get_or_create(user=self.request.user)
        return obj


class AddTelegram(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        telegram_nickname = request.data.get("nickname", "")
        user.tg_nickname = telegram_nickname
        user.save()
        return Response({"resp": "all good"})


class GetTelegramInfo(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({"tg": user.tg_nickname, "chat_id": user.chat_id})


serializer_classes = {
    "rsi": serializers.RsiIndicatorSerializer,
    "bb": serializers.BollingerBandsIndicatorSerializer,
    "sr": serializers.SupportResistanceIndicatorSerializer,
    "ema": serializers.EmaIndicatorSerializer,
    "ma": serializers.MaIndicatorSerializer,
    "fib": serializers.FiboSerializer,
}


class CreateBot(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data

        serializer = serializers.BotSerializer(data=data, context={"request": request})

        if not serializer.is_valid():
            return Response({"error": "Invalid bot data", "details": serializer.errors}, status=400)

        with transaction.atomic():
            bot = serializer.save()

            for key, serializer_class in serializer_classes.items():
                if key in data and isinstance(data[key], dict):
                    ind_ser = serializer_class(
                        data=data[key], context={"bot": bot, "request": request}
                    )

                    if not ind_ser.is_valid():
                        return Response(
                            {"error": f"Invalid {key} data", "details": ind_ser.errors}, status=400
                        )

                    ind_ser.save()

            bot.activate()

        return Response(
            {"status": "ok", "message": "Bot created successfully", "id": bot.id}, status=201
        )






def get_timeframe_minutes(timeframe: str) -> int:
    """Convert timeframe string to minutes."""
    mapping = {
        "1MIN": 1,
        "5MIN": 5,
        "15MIN": 15,
        "30MIN": 30,
        "1HRS": 60,
        "1DAY": 1440,
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "1d": 1440,
    }
    return mapping.get(timeframe, 1)
