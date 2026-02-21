from django.contrib import admin

from .models import (
    BollingerBandsIndicator,
    Bot,
    BotBalance,
    BotSignal,
    EmaIndicator,
    FiboIndicator,
    FnGValue,
    FundingRate,
    MaIndicator,
    RsiIndicator,
    RsiValue,
    Signal,
    SupportResistanceIndicator,
    UserBalance,
)

admin.site.register(Bot)
admin.site.register(UserBalance)
admin.site.register(BotSignal)
admin.site.register(FnGValue)
admin.site.register(Signal)
admin.site.register(MaIndicator)
admin.site.register(EmaIndicator)
admin.site.register(FundingRate)
admin.site.register(BotBalance)
admin.site.register(FiboIndicator)
admin.site.register(RsiValue)
admin.site.register(RsiIndicator)
admin.site.register(BollingerBandsIndicator)
admin.site.register(SupportResistanceIndicator)
