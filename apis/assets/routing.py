from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("api/ws/liquidations/", consumers.LiquidationConsumer.as_asgi()),
]
