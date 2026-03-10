from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from .models import AssetCryptoCoin
from .serializers import AssetsSerializer


class GetAssets(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetsSerializer
    queryset = AssetCryptoCoin.objects.all()
