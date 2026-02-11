from django.core.management.base import BaseCommand
from core.service import ApiService
from bots.models import FnGValue

api = ApiService()


class Command(BaseCommand):
    def handle(self, *args, **options):
        result = api.get_fear_and_greed_index()
        FnGValue.objects.create(
            value=int(result["value"]),
            classification=result["value_classification"],
            timestamp=int(result["timestamp"]),
            time_until_update=int(result["time_until_update"]),
        )
