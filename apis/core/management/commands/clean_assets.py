from assets.models import AssetCryptoCoin
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        AssetCryptoCoin.objects.all().delete()
