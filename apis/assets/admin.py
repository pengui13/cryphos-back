from django.contrib import admin

from .models import AssetCryptoCoin, HistQuotes


@admin.register(AssetCryptoCoin)
class AssetCryptoCoinAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'sector', 'rank')
    list_filter = ('sector',)
    search_fields = ('symbol', 'name')


@admin.register(HistQuotes)
class HistQuotesAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'interval', 'close_price', 'rank')
    search_fields = ('symbol',)
