from django.test import TestCase
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from assets.models import AssetCryptoCoin
from . import serializers
from django.conf import settings


class GetAssets(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # assets = AssetCryptoCoin.objects.all()
        # data = serializers.AssetsSerializer(assets, many=True).data
        return Response({"assets": AssetCryptoCoin.objects.all().values_list('symbol', flat=True)})
