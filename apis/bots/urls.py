from django.urls import path

from . import views

urlpatterns = [
    path("create_bot/",
         views.CreateBot.as_view(),
         name="create_bot"),
    path("delete_bot/<int:pk>/",
         views.DeleteMyBot.as_view(),
         name="delete_bot"),
    path("risk-settings/",
         views.RiskSettingsView.as_view(),
         name="risk-settings"),
    path("bots_list/",
         views.GetBotsList.as_view(),
         name="bots_list"),

]
