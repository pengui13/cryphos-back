from django.urls import path

from . import views

urlpatterns = [
    path("assets/", views.GetAssets.as_view(), name="assets"),
]
