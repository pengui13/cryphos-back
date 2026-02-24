from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

API_PREFIX = 'api/'

urlpatterns = [
    path(API_PREFIX + "admin/", admin.site.urls),
    path(API_PREFIX + "schema/", SpectacularAPIView.as_view(), name="schema"),
    path(API_PREFIX + "docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path(API_PREFIX + "auth/", include("accounts.urls")),
    path(API_PREFIX + "assets/", include("assets.urls")),
    path(API_PREFIX + "bots/", include("bots.urls")),

]
