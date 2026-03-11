from rest_framework.generics import DestroyAPIView, ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .services import BotService
from rest_framework import status
from . import serializers
from loguru import logger
from .models import (
    Bot,
    RiskSettings,
)


class RiskSettingsView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.RiskSerializer

    def get_object(self):
        obj, _ = RiskSettings.objects.get_or_create(user=self.request.user)
        return obj


class GetBotsList(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.BotSerializer

    def get_queryset(self):
        return Bot.objects.filter(owner=self.request.user)


class DeleteMyBot(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Bot.objects.filter(owner=self.request.user)


class CreateBot(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            bot = BotService.create_with_indicators(request)
        except Exception as e:
            logger.error(e)
            return Response({"error": "Something went wrong"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "ok", "id": bot.id}, status=201)
