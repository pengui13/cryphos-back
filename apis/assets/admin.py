from django.contrib import admin

from .models import AssetCryptoCoin, HistQuotes, Quote

admin.site.register(AssetCryptoCoin)
admin.site.register(HistQuotes)
admin.site.register(Quote)
