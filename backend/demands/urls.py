from django.urls import path

from .views import (
    DemandDetailView,
    DemandListCreateView,
    DemandStatusView,
    DemandSubmitView,
    DemandSelectSupplierView,
    DemandCancelView,
)

urlpatterns = [
    path("", DemandListCreateView.as_view(), name="demand-list-create"),
    path(
        "<int:pk>/submit",
        DemandSubmitView.as_view(),
        name="demand-submit",
    ),
    path(
        "<int:pk>/select-supplier",
        DemandSelectSupplierView.as_view(),
        name="demand-select-supplier",
    ),
    path("<int:pk>/", DemandDetailView.as_view(), name="demand-detail"),
    path(
        "<int:pk>/status/",
        DemandStatusView.as_view(),
        name="demand-status",
    ),
    path(
        "<int:pk>/cancel",
        DemandCancelView.as_view(),
        name="demand-cancel",
    ),
]
