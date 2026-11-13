from django.contrib import admin
from django.urls import include, path
from rest_framework.permissions import AllowAny

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .health import live_health, ready_health


urlpatterns = [
    path(
        "admin/masterdata/",
        include("masterdata.admin_urls"),
    ),
    path("admin/", admin.site.urls),

    # Operational health endpoints
    path("api/health/live/", live_health, name="health-live"),
    path("api/health/ready/", ready_health, name="health-ready"),

    # OpenAPI schema and interactive documentation
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/docs/swagger/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
            permission_classes=[AllowAny],
        ),
        name="swagger-ui",
    ),
    path(
        "api/docs/redoc/",
        SpectacularRedocView.as_view(
            url_name="schema",
            permission_classes=[AllowAny],
        ),
        name="redoc",
    ),

    # Business APIs
    path("api/auth/", include("accounts.urls")),
    path("api/masterdata/", include("masterdata.urls")),
    path("api/demands/", include("demands.urls")),
]
