from django.urls import path

from .views import (
    DemandDetailView,
    DemandListCreateView,
    DemandStatusView,
)

urlpatterns = [
    path("", DemandListCreateView.as_view(), name="demand-list-create"),
    path("<int:pk>/", DemandDetailView.as_view(), name="demand-detail"),
    path(
        "<int:pk>/status/",
        DemandStatusView.as_view(),
        name="demand-status",
    ),
]
