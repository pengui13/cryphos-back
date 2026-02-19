from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from assets.models import AssetCryptoCoin


class GetAssets(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # assets = AssetCryptoCoin.objects.all()
        # data = serializers.AssetsSerializer(assets, many=True).data
        return Response({"assets": AssetCryptoCoin.objects.all().values_list("symbol", flat=True)})
