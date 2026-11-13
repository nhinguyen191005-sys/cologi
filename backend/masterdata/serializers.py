from rest_framework import serializers

from .models import (
    CargoCategory,
    Item,
    Outlet,
    Supplier,
    SupplierItem,
)


class SupplierReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = (
            "id",
            "supplier_code",
            "supplier_name",
            "contact_name",
            "phone",
            "email",
            "address",
            "is_active",
        )
        read_only_fields = fields


class OutletReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outlet
        fields = (
            "id",
            "outlet_code",
            "outlet_name",
            "address",
            "contact_name",
            "phone",
            "is_active",
        )
        read_only_fields = fields


class CargoCategoryReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CargoCategory
        fields = (
            "id",
            "category_code",
            "category_name",
            "description",
            "is_active",
        )
        read_only_fields = fields


class ItemReadSerializer(serializers.ModelSerializer):
    cargo_category_id = serializers.IntegerField(read_only=True)
    category_code = serializers.CharField(
        source="cargo_category.category_code",
        read_only=True,
    )
    category_name = serializers.CharField(
        source="cargo_category.category_name",
        read_only=True,
    )

    class Meta:
        model = Item
        fields = (
            "id",
            "item_code",
            "item_name",
            "cargo_category_id",
            "category_code",
            "category_name",
            "weight_unit",
            "item_description",
            "is_active",
        )
        read_only_fields = fields


class SupplierItemReadSerializer(serializers.ModelSerializer):
    supplier_id = serializers.IntegerField(read_only=True)
    supplier_code = serializers.CharField(
        source="supplier.supplier_code",
        read_only=True,
    )
    supplier_name = serializers.CharField(
        source="supplier.supplier_name",
        read_only=True,
    )
    item_id = serializers.IntegerField(read_only=True)
    item_code = serializers.CharField(
        source="item.item_code",
        read_only=True,
    )
    item_name = serializers.CharField(
        source="item.item_name",
        read_only=True,
    )

    class Meta:
        model = SupplierItem
        fields = (
            "id",
            "supplier_id",
            "supplier_code",
            "supplier_name",
            "item_id",
            "item_code",
            "item_name",
            "unit_price_vnd_per_kg",
            "max_daily_supply_kg",
            "lead_time_hours",
            "minimum_order_kg",
            "offer_status",
            "updated_at",
        )
        read_only_fields = fields
