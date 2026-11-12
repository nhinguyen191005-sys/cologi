from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class DemandStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    PLANNING = "PLANNING", "Planning"
    PLANNED = "PLANNED", "Planned"
    CANCELLED = "CANCELLED", "Cancelled"


class DeliveryDemand(models.Model):
    demand_code = models.CharField(
        max_length=40,
        unique=True,
    )
    supplier = models.ForeignKey(
        "masterdata.Supplier",
        on_delete=models.PROTECT,
        related_name="delivery_demands",
    )
    outlet = models.ForeignKey(
        "masterdata.Outlet",
        on_delete=models.PROTECT,
        related_name="delivery_demands",
    )
    cargo_category = models.ForeignKey(
        "masterdata.CargoCategory",
        on_delete=models.PROTECT,
        related_name="delivery_demands",
    )
    quantity_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )
    requested_date = models.DateField()
    requested_start_time = models.TimeField(
        null=True,
        blank=True,
    )
    requested_end_time = models.TimeField(
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=DemandStatus.choices,
        default=DemandStatus.DRAFT,
    )
    notes = models.TextField(
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_demands",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "delivery_demands"
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity_kg__gt=0),
                name="dem_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(status__in=DemandStatus.values),
                name="dem_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(requested_start_time__isnull=True)
                    | Q(requested_end_time__isnull=True)
                    | Q(requested_start_time__lt=F("requested_end_time"))
                ),
                name="dem_requested_time_order",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "requested_date"),
                name="dem_status_date_idx",
            ),
            models.Index(
                fields=("supplier", "requested_date"),
                name="dem_supplier_date_idx",
            ),
            models.Index(
                fields=("outlet", "requested_date"),
                name="dem_outlet_date_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.requested_start_time is not None
            and self.requested_end_time is not None
            and self.requested_start_time >= self.requested_end_time
        ):
            raise ValidationError({
                "requested_end_time": (
                    "Requested end time must be later than start time."
                )
            })

    def __str__(self):
        return self.demand_code


class DemandItem(models.Model):
    demand = models.ForeignKey(
        DeliveryDemand,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item = models.ForeignKey(
        "masterdata.Item",
        on_delete=models.PROTECT,
        related_name="demand_items",
    )
    required_weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )
    unit_of_measure = models.CharField(max_length=10)
    item_note = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "demand_items"
        ordering = ("demand_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("demand", "item"),
                name="di_demand_item_uniq",
            ),
            models.CheckConstraint(
                condition=Q(required_weight_kg__gt=0),
                name="di_weight_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=("item", "demand"),
                name="di_item_demand_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if (
            self.required_weight_kg is not None
            and self.required_weight_kg <= 0
        ):
            errors["required_weight_kg"] = (
                "Required weight must be greater than zero."
            )

        if self.demand_id and self.item_id:
            demand = self.demand
            item = self.item

            if not item.is_active:
                errors["item"] = "Inactive items cannot be added to a demand."

            if item.cargo_category_id != demand.cargo_category_id:
                errors["item"] = (
                    "Item cargo category must match the demand cargo category."
                )

            if self.unit_of_measure != item.weight_unit:
                errors["unit_of_measure"] = (
                    "Unit of measure must match the item's weight unit."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.demand.demand_code} -> {self.item.item_code}"
