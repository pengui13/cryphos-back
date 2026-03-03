from django.contrib import admin

from .models import BollingerBandsIndicator, Bot, RsiIndicator, Signal, SupportResistanceIndicator


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'owner__email', 'rank')
    search_fields = ('owner__email',)


@admin.register(RsiIndicator)
class RsiIndicatorAdmin(admin.ModelAdmin):
    list_display = ('min', 'max', 'bot__owner__email', 'period')
    search_fields = ('bot__owner__email',)


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ('asset__symbol', 'bot__owner__email',
                    'open_price', 'close_price', 'is_long', 'is_open')
    search_fields = ('bot__owner__email', "asset__symbol")


@admin.register(SupportResistanceIndicator)
class SupportResistanceIndicator(admin.ModelAdmin):
    list_display = ('mode', 'lookback', 'bot__owner__email', 'zone_mode')
    search_fields = ('bot__owner__email',)


@admin.register(BollingerBandsIndicator)
class BollingerBandsIndicatorAdmin(admin.ModelAdmin):
    list_display = ('period', 'std_dev', 'bot__owner__email')
    search_fields = ('bot__owner__email',)
