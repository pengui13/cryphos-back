from django.urls import path

from . import views

urlpatterns = [
    path("assets/", views.GetAssets.as_view(), name="assets"),
    path("fng/",
         views.GetFnGValue.as_view(),
         name="fng"),
    path("funding/",
         views.GetFundingRates.as_view(),
         name="funding"),
    path("get_signals/<int:pk>/",
         views.GetSignals.as_view(),
         name="get_signals"),
    
]
