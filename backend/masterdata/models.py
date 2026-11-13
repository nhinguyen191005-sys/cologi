from django.db import models

class Supplier(models.Model):
    supplier_code = models.CharField(max_length=30, unique=True)
    supplier_name = models.CharField(max_length=200)
    contact_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
    )
    address = models.TextField(
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "suppliers"
        ordering = ("supplier_code",)

    def __str__(self):
        return f"{self.supplier_code} - {self.supplier_name}"


class TransportProvider(models.Model):
    # MVP schema based on worksheet 45_Transport_Providers.
    # Field definitions should be added to the V7 Data Dictionary.
    provider_code = models.CharField(max_length=30, unique=True)
    provider_name = models.CharField(max_length=200)
    provider_type = models.CharField(max_length=30)
    service_region = models.TextField()
    contact_email = models.EmailField(max_length=254)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "transport_providers"
        ordering = ("provider_code",)

    def __str__(self):
        return f"{self.provider_code} - {self.provider_name}"

class Outlet(models.Model):
    outlet_code = models.CharField(max_length=30, unique=True)
    outlet_name = models.CharField(max_length=200)
    address = models.TextField()
    contact_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "outlets"
        ordering = ("outlet_code",)

    def __str__(self):
        return f"{self.outlet_code} - {self.outlet_name}"


class CargoCategory(models.Model):
    category_code = models.CharField(max_length=30, unique=True)
    category_name = models.CharField(max_length=150)
    description = models.TextField(
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "cargo_categories"
        ordering = ("category_code",)

    def __str__(self):
        return f"{self.category_code} - {self.category_name}"

class Item(models.Model):
    item_code = models.CharField(max_length=30, unique=True)
    item_name = models.CharField(max_length=200)
    cargo_category = models.ForeignKey(
        CargoCategory,
        on_delete=models.PROTECT,
        related_name="items",
    )
    weight_unit = models.CharField(max_length=10)
    item_description = models.TextField(
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "items"
        ordering = ("item_code",)
        indexes = [
            models.Index(
                fields=("cargo_category", "is_active"),
                name="md_item_cat_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"


class SupplierItem(models.Model):
    class OfferStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="supplier_items",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="supplier_items",
    )
    unit_price_vnd_per_kg = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )
    max_daily_supply_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    lead_time_hours = models.IntegerField(
        null=True,
        blank=True,
    )
    minimum_order_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    offer_status = models.CharField(
        max_length=20,
        choices=OfferStatus.choices,
        default=OfferStatus.ACTIVE,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_items"
        ordering = ("supplier_id", "item_id")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "item"),
                name="md_sitem_pair_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price_vnd_per_kg__gte=0),
                name="md_sitem_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(max_daily_supply_kg__isnull=True)
                    | models.Q(max_daily_supply_kg__gt=0)
                ),
                name="md_sitem_daily_positive_if_set",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(lead_time_hours__isnull=True)
                    | models.Q(lead_time_hours__gte=0)
                ),
                name="md_sitem_lead_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(minimum_order_kg__isnull=True)
                    | models.Q(minimum_order_kg__gte=0)
                ),
                name="md_sitem_min_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    offer_status__in=("ACTIVE", "INACTIVE"),
                ),
                name="md_sitem_offer_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("supplier", "offer_status"),
                name="md_sitem_supplier_status_idx",
            ),
            models.Index(
                fields=("item", "offer_status"),
                name="md_sitem_item_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.supplier_id} -> {self.item_id}"


class Hub(models.Model):
    hub_code = models.CharField(max_length=30, unique=True)
    hub_name = models.CharField(max_length=150)
    address = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hubs"
        ordering = ("hub_code",)

    def __str__(self):
        return f"{self.hub_code} - {self.hub_name}"


class VehicleType(models.Model):
    vehicle_code = models.CharField(max_length=30, unique=True)
    vehicle_name = models.CharField(max_length=150)
    capacity_kg = models.DecimalField(max_digits=12, decimal_places=3)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "vehicle_types"
        ordering = ("vehicle_code",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity_kg__gt=0),
                name="md_vtype_capacity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.vehicle_code} - {self.vehicle_name}"


class VehicleCargoCompatibility(models.Model):
    pk = models.CompositePrimaryKey(
        "vehicle_type",
        "cargo_category",
    )

    vehicle_type = models.ForeignKey(
        VehicleType,
        on_delete=models.PROTECT,
        db_column="vehicle_type_id",
        related_name="cargo_compatibilities",
    )
    cargo_category = models.ForeignKey(
        CargoCategory,
        on_delete=models.PROTECT,
        db_column="cargo_category_id",
        related_name="vehicle_compatibilities",
    )
    is_supported = models.BooleanField()
    source = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "vehicle_cargo_compatibility"

    def __str__(self):
        return (
            f"{self.vehicle_type_id} - "
            f"{self.cargo_category_id}: {self.is_supported}"
        )
