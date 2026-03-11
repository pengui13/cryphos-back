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
    
]
