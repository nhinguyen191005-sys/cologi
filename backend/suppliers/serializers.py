from collections.abc import Mapping
from decimal import Decimal

from rest_framework import serializers

from demands.models import SupplierItemPromise, SupplierRequest
from masterdata.models import CargoCategory, Item, SupplierItem


class StrictInputMixin:
    """Reject unknown fields, including server-managed fields."""

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


class SupplierDemandSummarySerializer(serializers.Serializer):
    demand_code = serializers.CharField()
    requested_date = serializers.DateField()
    requested_start_time = serializers.TimeField(
        allow_null=True,
    )
    requested_end_time = serializers.TimeField(
        allow_null=True,
    )
    notes = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )
    outlet_name = serializers.CharField(source="outlet.outlet_name")
    outlet_address = serializers.CharField(source="outlet.address")


class SupplierPromiseReadSerializer(serializers.ModelSerializer):
    demand_item_id = serializers.IntegerField(read_only=True)
    item_code = serializers.CharField(
        source="demand_item.item.item_code",
        read_only=True,
    )
    item_name = serializers.CharField(
        source="demand_item.item.item_name",
        read_only=True,
    )
    required_weight_kg = serializers.DecimalField(
        source="demand_item.required_weight_kg",
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )
    item_note = serializers.CharField(
        source="demand_item.item_note",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = SupplierItemPromise
        fields = (
            "id",
            "demand_item_id",
            "item_code",
            "item_name",
            "required_weight_kg",
            "item_note",
            "promised_weight_kg",
            "confirmed_weight_kg",
            "line_status",
            "decline_reason",
            "unit_price_vnd_per_kg_snapshot",
            "lead_time_hours_snapshot",
        )
        read_only_fields = fields


class SupplierRequestReadSerializer(serializers.ModelSerializer):
    demand = SupplierDemandSummarySerializer(read_only=True)
    items = SupplierPromiseReadSerializer(
        source="item_promises",
        many=True,
        read_only=True,
    )
    confirmation_status = serializers.CharField(
        source="supplier_confirmation.confirmation_status",
        read_only=True,
    )
    ready_date = serializers.DateField(
        source="supplier_confirmation.ready_date",
        read_only=True,
        allow_null=True,
    )
    ready_start_time = serializers.TimeField(
        source="supplier_confirmation.ready_start_time",
        read_only=True,
        allow_null=True,
    )
    ready_end_time = serializers.TimeField(
        source="supplier_confirmation.ready_end_time",
        read_only=True,
        allow_null=True,
    )
    pickup_address = serializers.CharField(
        source="supplier_confirmation.pickup_address",
        read_only=True,
        allow_null=True,
    )
    confirmation_note = serializers.CharField(
        source="supplier_confirmation.confirmation_note",
        read_only=True,
        allow_blank=True,
    )
    recorded_at = serializers.DateTimeField(
        source="supplier_confirmation.recorded_at",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = SupplierRequest
        fields = (
            "id",
            "request_code",
            "attempt_no",
            "request_status",
            "sent_at",
            "responded_at",
            "demand",
            "confirmation_status",
            "ready_date",
            "ready_start_time",
            "ready_end_time",
            "pickup_address",
            "confirmation_note",
            "recorded_at",
            "items",
        )
        read_only_fields = fields


class SupplierPromiseResponseInputSerializer(
    StrictInputMixin,
    serializers.Serializer,
):
    promise_id = serializers.IntegerField(min_value=1)
    confirmed_weight_kg = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
    )
    decline_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )


class SupplierRequestResponseInputSerializer(
    StrictInputMixin,
    serializers.Serializer,
):
    items = SupplierPromiseResponseInputSerializer(
        many=True,
        allow_empty=False,
    )
    ready_date = serializers.DateField(required=False, allow_null=True)
    ready_start_time = serializers.TimeField(
        required=False,
        allow_null=True,
    )
    ready_end_time = serializers.TimeField(
        required=False,
        allow_null=True,
    )
    pickup_address = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    confirmation_note = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        start = attrs.get("ready_start_time")
        end = attrs.get("ready_end_time")

        if (start is None) != (end is None):
            raise serializers.ValidationError({
                "ready_start_time": (
                    "Ready start and end times must be provided together."
                )
            })

        if start is not None and end is not None and start >= end:
            raise serializers.ValidationError({
                "ready_end_time": "Ready end time must be later than start time."
            })

        promise_ids = [
            row["promise_id"] for row in attrs["items"]
        ]
        if len(promise_ids) != len(set(promise_ids)):
            raise serializers.ValidationError({
                "items": "A promise may only be included once."
            })

        return attrs


class SupplierCatalogCreateSerializer(StrictInputMixin, serializers.Serializer):
    item_id = serializers.IntegerField(required=False, min_value=1)
    item_name = serializers.CharField(
        required=False,
        max_length=200,
        trim_whitespace=True,
    )
    cargo_category_id = serializers.IntegerField(required=False, min_value=1)
    weight_unit = serializers.CharField(
        required=False,
        max_length=10,
        trim_whitespace=True,
    )
    item_description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        trim_whitespace=True,
    )
    unit_price_vnd_per_kg = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
    )
    max_daily_supply_kg = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
        required=False,
        allow_null=True,
    )
    lead_time_hours = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True,
    )
    minimum_order_kg = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
    )
    offer_status = serializers.ChoiceField(
        choices=SupplierItem.OfferStatus.choices,
        required=False,
        default=SupplierItem.OfferStatus.ACTIVE,
    )

    def validate(self, attrs):
        item_id = attrs.get("item_id")
        new_item_fields = {
            "item_name",
            "cargo_category_id",
            "weight_unit",
            "item_description",
        }
        supplied_new_fields = new_item_fields.intersection(attrs)

        if item_id is not None and supplied_new_fields:
            raise serializers.ValidationError(
                "Chỉ chọn Item có sẵn hoặc khai báo Item mới, không được kết hợp."
            )

        if item_id is None:
            missing = {
                "item_name",
                "cargo_category_id",
                "weight_unit",
            }.difference(attrs)
            if missing:
                raise serializers.ValidationError({
                    field: "Trường này bắt buộc khi tạo Item mới."
                    for field in sorted(missing)
                })
            category = CargoCategory.objects.filter(
                pk=attrs["cargo_category_id"],
                is_active=True,
            ).first()
            if category is None:
                raise serializers.ValidationError({
                    "cargo_category_id": "Danh mục ngành hàng không tồn tại hoặc đã ngừng hoạt động."
                })
        else:
            item = Item.objects.filter(
                pk=item_id,
                is_active=True,
                cargo_category__is_active=True,
            ).first()
            if item is None:
                raise serializers.ValidationError({
                    "item_id": "Item không tồn tại hoặc đã ngừng hoạt động."
                })

        return attrs


class SupplierCatalogUpdateSerializer(StrictInputMixin, serializers.Serializer):
    """Allow suppliers to update only their own offer conditions."""

    unit_price_vnd_per_kg = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
    )
    max_daily_supply_kg = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
        required=False,
        allow_null=True,
    )
    lead_time_hours = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True,
    )
    minimum_order_kg = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
    )
    offer_status = serializers.ChoiceField(
        choices=SupplierItem.OfferStatus.choices,
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Cần cung cấp ít nhất một trường để cập nhật."
            )
        return attrs


class SupplierAvailableItemSerializer(serializers.ModelSerializer):
    cargo_category_id = serializers.IntegerField(read_only=True)
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
            "category_name",
            "weight_unit",
            "item_description",
        )
        read_only_fields = fields


class SupplierCargoCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CargoCategory
        fields = (
            "id",
            "category_code",
            "category_name",
        )
        read_only_fields = fields
