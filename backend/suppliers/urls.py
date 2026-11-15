from django.urls import path

from .views import (
    SupplierAvailableItemListView,
    SupplierCargoCategoryListView,
    SupplierCatalogListView,
    SupplierCatalogUpdateView,
    SupplierRequestConfirmView,
    SupplierRequestListView,
)


urlpatterns = [
    path(
        "api/suppliers/me/items",
        SupplierCatalogListView.as_view(),
        name="supplier-my-items",
    ),
    path(
        "api/suppliers/me/available-items",
        SupplierAvailableItemListView.as_view(),
        name="supplier-available-items",
    ),
    path(
        "api/suppliers/me/cargo-categories",
        SupplierCargoCategoryListView.as_view(),
        name="supplier-cargo-categories",
    ),
    path(
        "api/suppliers/me/items/<int:pk>",
        SupplierCatalogUpdateView.as_view(),
        name="supplier-item-update",
    ),
    path(
        "api/suppliers/me/requests",
        SupplierRequestListView.as_view(),
        name="supplier-my-requests",
    ),
    path(
        "api/supply-requests/<int:pk>/confirm",
        SupplierRequestConfirmView.as_view(),
        name="supplier-request-confirm",
    ),
]
