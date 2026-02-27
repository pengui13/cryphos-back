from django.contrib import admin

from . import models

models_to_register = [models.Bot,
                      models.FnGValue,
                      models.Signal,
                      models.MaIndicator,
                      models.EmaIndicator,
                      models.FundingRate,
                      models.FiboIndicator,
                      models.RsiIndicator,
                      models.BollingerBandsIndicator,
                      models.SupportResistanceIndicator]

admin.site.register(models_to_register)
