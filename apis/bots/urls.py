from django.urls import path

from . import views

urlpatterns = [
    path("create_bot/", views.CreateBot.as_view(), name="create_bot"),
    path("fng/", views.GetFnGValue.as_view(), name="fng"),
    path("create_balance/", views.CreateBotBalance.as_view(), name="create_balance"),
    path("funding/", views.GetFundingRates.as_view(), name="funding"),
    path("bot_metrics/", views.BotMetrics.as_view(), name="bot_metrics"),
    path("get_info/<int:bot_id>/", views.GetBotsDetail.as_view(), name="get_bots"),
    path("delete_bot/<int:bot_id>/", views.DeleteMyBot.as_view(), name="delete_bot"),
    path("risk-settings/", views.RiskSettingsView.as_view(), name="risk-settings"),
    path("leave_bot/<int:id>/", views.LeaveBot.as_view(), name="leave_bot"),
    path("get_signals/<int:id>/", views.GetSignals.as_view(), name="get_signals"),
    path("ping/", views.GetPing.as_view(), name="ping"),
    path(
        "available_amount/",
        views.GetAvailableBalance.as_view(),
        name="available_amount",
    ),
    path(
        "get_bot_subscribers/<int:bot_id>/",
        views.GetBotSubscribers.as_view(),
        name="get_bot_subscribers",
    ),
    path("backtest/<int:bot_id>/", views.Backtest.as_view(), name="backtest"),
    path("bots_list/", views.GetBotsList.as_view(), name="bots_list"),
    path("close_signal/<int:id>/", views.CloseBotPosition.as_view(), name="close_signal"),
    path(
        "toggle_verification/<int:bot_id>/",
        views.ToggleVerification.as_view(),
        name="toggle_verification",
    ),
    path(
        "get_all_bots/",
        views.GetAllBots.as_view(),
        name="get_all_bots",
    ),
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
