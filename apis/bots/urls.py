from django.urls import path

from . import views

urlpatterns = [
    path("create_bot/",
         views.CreateBot.as_view(),
         name="create_bot"),
    path("fng/",
         views.GetFnGValue.as_view(),
         name="fng"),
    path("funding/",
         views.GetFundingRates.as_view(),
         name="funding"),
    path("delete_bot/<int:pk>/",
         views.DeleteMyBot.as_view(),
         name="delete_bot"),
    path("risk-settings/",
         views.RiskSettingsView.as_view(),
         name="risk-settings"),
    path("get_signals/<int:pk>/",
         views.GetSignals.as_view(),
         name="get_signals"),
    path("ping/",
         views.ping,
         name="ping"),
    path("bots_list/",
         views.GetBotsList.as_view(),
         name="bots_list"),
    path(
        "add_telegram/",
        views.AddTelegram.as_view(),
        name="add_telegram",
    ),
    path(
        "get_tg_info/",
        views.GetTelegramInfo.as_view(),
        name="add_telegram",
    ),
]
