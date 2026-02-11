from django.urls import path, include
from . import views

urlpatterns = [
    path("assets/", views.GetAssets.as_view(), name="assets"),
]
