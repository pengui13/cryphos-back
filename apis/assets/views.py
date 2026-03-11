from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from .models import AssetCryptoCoin
from .serializers import AssetsSerializer
from bots.services import RedisService
from rest_framework.views import APIView
from rest_framework.response import Response
from assets.serializers import FundingRateSerializer
from bots.models import FundingRate
from bots.serializers import SignalSerializer
from bots.models import Signal


class GetAssets(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetsSerializer
    queryset = AssetCryptoCoin.objects.all()


class GetSignals(ListAPIView):
    serializer_class = SignalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Signal.objects.filter(
            bot_id=self.kwargs.get('pk'),
            bot__owner=self.request.user
        ).select_related('asset').order_by('-created_at')


class GetFnGValue(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        values = ["fng", "fng_class"]
        results = RedisService.get_values(values)
        return Response(results)


class GetFundingRates(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FundingRateSerializer
    queryset = FundingRate.objects.all()
