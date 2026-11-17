from django.urls import path

from .views import (
    ProviderAvailabilityDetailView,
    ProviderAvailabilityListCreateView,
    ProviderProfileView,
    ProviderSupplierCoverageDetailView,
    ProviderSupplierCoverageListCreateView,
    ProviderVehicleOfferDetailView,
    ProviderVehicleOfferListCreateView,
)


urlpatterns = [
    path("me/", ProviderProfileView.as_view(), name="provider-profile"),
    path(
        "me/supplier-coverages/",
        ProviderSupplierCoverageListCreateView.as_view(),
        name="provider-supplier-coverages",
    ),
    path(
        "me/supplier-coverages/<int:pk>/",
        ProviderSupplierCoverageDetailView.as_view(),
        name="provider-supplier-coverage-detail",
    ),
    path(
        "me/vehicle-offers/",
        ProviderVehicleOfferListCreateView.as_view(),
        name="provider-vehicle-offers",
    ),
    path(
        "me/vehicle-offers/<int:pk>/",
        ProviderVehicleOfferDetailView.as_view(),
        name="provider-vehicle-offer-detail",
    ),
    path(
        "me/availability/",
        ProviderAvailabilityListCreateView.as_view(),
        name="provider-availability",
    ),
    path(
        "me/availability/<int:pk>/",
        ProviderAvailabilityDetailView.as_view(),
        name="provider-availability-detail",
    ),
]
