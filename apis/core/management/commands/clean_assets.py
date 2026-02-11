from django.core.management.base import BaseCommand
from assets.models import AssetCryptoCoin


class Command(BaseCommand):
    def handle(self, *args, **options):
        AssetCryptoCoin.objects.all().delete()
