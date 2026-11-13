from django.urls import path

from .views import (
    CargoCategoryListView,
    ItemListView,
    OutletListView,
    SupplierItemListView,
    SupplierListView,
)


urlpatterns = [
    path(
        "suppliers/",
        SupplierListView.as_view(),
        name="masterdata-supplier-list",
    ),
    path(
        "outlets/",
        OutletListView.as_view(),
        name="masterdata-outlet-list",
    ),
    path(
        "cargo-categories/",
        CargoCategoryListView.as_view(),
        name="masterdata-cargo-category-list",
    ),
    path(
        "items/",
        ItemListView.as_view(),
        name="masterdata-item-list",
    ),
    path(
        "supplier-items/",
        SupplierItemListView.as_view(),
        name="masterdata-supplier-item-list",
    ),
]
