from collections.abc import Mapping
from decimal import Decimal

from rest_framework import serializers

from masterdata.models import Item, Outlet, Supplier

from .models import DeliveryDemand, DemandItem


class StrictInputMixin:
    """
    Reject unknown input fields instead of silently ignoring them.
    This prevents clients from attempting to set server-managed fields.
    """

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data.keys()) - set(self.fields.keys())

            if unknown_fields:
                raise serializers.ValidationError({
                    "non_field_errors": [
                        "Unsupported fields: "
                        + ", ".join(sorted(str(field) for field in unknown_fields))
                    ]
                })

        return super().to_internal_value(data)


class DemandItemInputSerializer(
    StrictInputMixin,
    serializers.Serializer,
):
    item_id = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.filter(is_active=True),
    )
    required_weight_kg = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    unit_of_measure = serializers.CharField(
        max_length=10,
        required=False,
    )
    item_note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class DemandCreateSerializer(
    StrictInputMixin,
    serializers.Serializer,
):
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.filter(is_active=True),
    )
    outlet_id = serializers.PrimaryKeyRelatedField(
        queryset=Outlet.objects.filter(is_active=True),
    )
    requested_date = serializers.DateField()
    requested_start_time = serializers.TimeField(
        required=False,
        allow_null=True,
    )
    requested_end_time = serializers.TimeField(
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    items = DemandItemInputSerializer(many=True)


class DemandPatchSerializer(
    StrictInputMixin,
    serializers.Serializer,
):
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
    )
    requested_date = serializers.DateField(required=False)
    requested_start_time = serializers.TimeField(
        required=False,
        allow_null=True,
    )
    requested_end_time = serializers.TimeField(
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    items = DemandItemInputSerializer(
        many=True,
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one editable field must be provided."
            )
        return attrs


class DemandItemReadSerializer(serializers.ModelSerializer):
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
        model = DemandItem
        fields = (
            "id",
            "item_id",
            "item_code",
            "item_name",
            "required_weight_kg",
            "unit_of_measure",
            "item_note",
        )
        read_only_fields = fields


class DeliveryDemandReadSerializer(serializers.ModelSerializer):
    supplier_id = serializers.IntegerField(read_only=True)
    supplier_code = serializers.CharField(
        source="supplier.supplier_code",
        read_only=True,
    )
    supplier_name = serializers.CharField(
        source="supplier.supplier_name",
        read_only=True,
    )

    outlet_id = serializers.IntegerField(read_only=True)
    outlet_code = serializers.CharField(
        source="outlet.outlet_code",
        read_only=True,
    )
    outlet_name = serializers.CharField(
        source="outlet.outlet_name",
        read_only=True,
    )

    cargo_category_id = serializers.IntegerField(read_only=True)
    cargo_category_code = serializers.CharField(
        source="cargo_category.category_code",
        read_only=True,
    )
    cargo_category_name = serializers.CharField(
        source="cargo_category.category_name",
        read_only=True,
    )

    created_by_id = serializers.IntegerField(read_only=True)
    items = DemandItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = DeliveryDemand
        fields = (
            "id",
            "demand_code",
            "supplier_id",
            "supplier_code",
            "supplier_name",
            "outlet_id",
            "outlet_code",
            "outlet_name",
            "cargo_category_id",
            "cargo_category_code",
            "cargo_category_name",
            "quantity_kg",
            "requested_date",
            "requested_start_time",
            "requested_end_time",
            "status",
            "notes",
            "created_by_id",
            "created_at",
            "updated_at",
            "items",
        )
        read_only_fields = fields
