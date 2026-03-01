from django.contrib import admin

from .models import AssetCryptoCoin, HistQuotes


@admin.register(AssetCryptoCoin)
class AssetCryptoCoinAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'sector', 'rank')
    list_filter = ('sector',)
    search_fields = ('symbol', 'name')


admin.site.register(HistQuotes)
