from django.db.models import QuerySet

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, extend_schema_view

from accounts.models import RoleCode, UserRole
from accounts.permissions import (
    HasCoLogiRole,
    filter_queryset_by_outlet_access,
)

from .models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
)
from .serializers import (
    CargoCategoryReadSerializer,
    ItemReadSerializer,
    OutletReadSerializer,
    SupplierItemReadSerializer,
    SupplierReadSerializer,
)


class MasterdataReadOnlyListView(generics.ListAPIView):
    """
    Shared authorization policy for read-only Masterdata lists.

    Purchasing Staff and Manager may read active Masterdata.
    External actors are denied by the role permission.
    """

    permission_classes = (
        IsAuthenticated,
        HasCoLogiRole,
    )
    required_roles = (
        RoleCode.PURCHASING_STAFF,
        RoleCode.MANAGER,
    )

    @staticmethod
    def user_is_active_manager(user):
        return UserRole.objects.filter(
            user=user,
            is_active=True,
            role__code=RoleCode.MANAGER,
            role__is_active=True,
        ).exists()


@extend_schema_view(
    get=extend_schema(
        operation_id="masterdata_suppliers_list",
        tags=["Masterdata"],
    )
)
class SupplierListView(MasterdataReadOnlyListView):
    serializer_class = SupplierReadSerializer

    def get_queryset(self) -> QuerySet:
        return Supplier.objects.filter(
            is_active=True,
        )


@extend_schema_view(
    get=extend_schema(
        operation_id="masterdata_outlets_list",
        tags=["Masterdata"],
    )
)
class OutletListView(MasterdataReadOnlyListView):
    serializer_class = OutletReadSerializer

    def get_queryset(self) -> QuerySet:
        queryset = Outlet.objects.filter(is_active=True)

        if self.user_is_active_manager(self.request.user):
            return queryset

        return filter_queryset_by_outlet_access(
            queryset,
            self.request.user,
            outlet_lookup="pk",
        )


@extend_schema_view(
    get=extend_schema(
        operation_id="masterdata_cargo_categories_list",
        tags=["Masterdata"],
    )
)
class CargoCategoryListView(MasterdataReadOnlyListView):
    serializer_class = CargoCategoryReadSerializer

    def get_queryset(self) -> QuerySet:
        return CargoCategory.objects.filter(is_active=True)


@extend_schema_view(
    get=extend_schema(
        operation_id="masterdata_items_list",
        tags=["Masterdata"],
    )
)
class ItemListView(MasterdataReadOnlyListView):
    serializer_class = ItemReadSerializer

    def get_queryset(self) -> QuerySet:
        return (
            Item.objects
            .filter(
                is_active=True,
                cargo_category__is_active=True,
            )
            .select_related("cargo_category")
        )


@extend_schema_view(
    get=extend_schema(
        operation_id="masterdata_supplier_items_list",
        tags=["Masterdata"],
    )
)
class SupplierItemListView(MasterdataReadOnlyListView):
    serializer_class = SupplierItemReadSerializer

    def get_queryset(self) -> QuerySet:
        return (
            SupplierItem.objects
            .filter(
                offer_status=SupplierItem.OfferStatus.ACTIVE,
                supplier__is_active=True,
                item__is_active=True,
                item__cargo_category__is_active=True,
            )
            .select_related(
                "supplier",
                "item",
                "item__cargo_category",
            )
        )
