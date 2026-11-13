from django.contrib import admin

from accounts.models import RoleCode, UserRole

from .models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
    TransportProvider,
    Hub,
    VehicleType,
)


class ManagerOnlyMasterdataAdminMixin:
    """
    Django Admin access for Masterdata requires both:
    - technical Django Admin access (is_staff);
    - an active CoLogi MANAGER business role.

    Superuser status alone does not grant the CoLogi business role.
    Masterdata records must be deactivated, not hard-deleted.
    """

    actions = None

    def _has_active_manager_role(self, request):
        user = getattr(request, "user", None)

        if (
            not getattr(user, "is_authenticated", False)
            or not getattr(user, "is_active", False)
            or not getattr(user, "is_staff", False)
        ):
            return False

        return UserRole.objects.filter(
            user=user,
            role__code=RoleCode.MANAGER,
            role__is_active=True,
        ).exists()

    def has_module_permission(self, request):
        return self._has_active_manager_role(request)

    def has_view_permission(self, request, obj=None):
        return self._has_active_manager_role(request)

    def has_add_permission(self, request):
        return self._has_active_manager_role(request)

    def has_change_permission(self, request, obj=None):
        return self._has_active_manager_role(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Supplier)
class SupplierAdmin(
    ManagerOnlyMasterdataAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "supplier_code",
        "supplier_name",
        "phone",
        "email",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = (
        "supplier_code",
        "supplier_name",
        "contact_name",
        "phone",
        "email",
    )
    ordering = ("supplier_code",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(TransportProvider)
class TransportProviderAdmin(
    ManagerOnlyMasterdataAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "provider_code",
        "provider_name",
        "provider_type",
        "is_active",
    )
    list_filter = ("provider_type", "is_active")
    search_fields = (
        "provider_code",
        "provider_name",
        "contact_email",
        "service_region",
    )
    ordering = ("provider_code",)


@admin.register(Outlet)
class OutletAdmin(
    ManagerOnlyMasterdataAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "outlet_code",
        "outlet_name",
        "contact_name",
        "phone",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = (
        "outlet_code",
        "outlet_name",
        "address",
        "contact_name",
        "phone",
    )
    ordering = ("outlet_code",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(CargoCategory)
class CargoCategoryAdmin(
    ManagerOnlyMasterdataAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "category_code",
        "category_name",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = (
        "category_code",
        "category_name",
        "description",
    )
    ordering = ("category_code",)


@admin.register(Item)
class ItemAdmin(
    ManagerOnlyMasterdataAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "item_code",
        "item_name",
        "cargo_category",
        "weight_unit",
        "is_active",
    )
    list_filter = (
        "is_active",
        "cargo_category",
    )
    search_fields = (
        "item_code",
        "item_name",
        "cargo_category__category_code",
        "cargo_category__category_name",
    )
    autocomplete_fields = ("cargo_category",)
    list_select_related = ("cargo_category",)
    ordering = ("item_code",)


@admin.register(SupplierItem)
class SupplierItemAdmin(
    ManagerOnlyMasterdataAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "supplier",
        "item",
        "unit_price_vnd_per_kg",
        "max_daily_supply_kg",
        "lead_time_hours",
        "minimum_order_kg",
        "offer_status",
        "updated_at",
    )
    list_filter = (
        "offer_status",
        "supplier",
        "item",
    )
    search_fields = (
        "supplier__supplier_code",
        "supplier__supplier_name",
        "item__item_code",
        "item__item_name",
    )
    autocomplete_fields = ("supplier", "item")
    list_select_related = ("supplier", "item")
    ordering = ("supplier__supplier_code", "item__item_code")
    readonly_fields = ("updated_at",)

@admin.register(Hub)
class HubAdmin(
    ManagerOnlyMasterdataAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "hub_code",
        "hub_name",
        "address",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("hub_code", "hub_name", "address")
    ordering = ("hub_code",)
    readonly_fields = ("created_at",)


@admin.register(VehicleType)
class VehicleTypeAdmin(
    ManagerOnlyMasterdataAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "vehicle_code",
        "vehicle_name",
        "capacity_kg",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = (
        "vehicle_code",
        "vehicle_name",
        "description",
    )
    ordering = ("vehicle_code",)

    change_list_template = (
    "admin/masterdata/vehicletype/change_list.html"
    )