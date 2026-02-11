from django.test import TestCase
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from assets.models import AssetCryptoCoin
from . import serializers


class GetAssets(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assets = AssetCryptoCoin.objects.all()
        data = serializers.AssetsSerializer(assets, many=True).data
        return Response({"assets": data})
