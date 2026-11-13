from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


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

# ---------------------------------------------------------------------------
# CP4.3-D: Supplier sourcing and confirmation
# ---------------------------------------------------------------------------


class DemandSourcingOption(models.Model):
    """
    A supplier offer evaluated as a sourcing option for one DemandItem.

    ALTERNATIVE_ONLY options are read-only suggestions. Persisting an option
    never changes DeliveryDemand.supplier.
    """

    class OptionType(models.TextChoices):
        SELECTED_EXISTING = "SELECTED_EXISTING", "Selected existing supplier"
        ALTERNATIVE_ONLY = "ALTERNATIVE_ONLY", "Alternative only"

    class EvaluationStatus(models.TextChoices):
        ELIGIBLE = "ELIGIBLE", "Eligible"
        INELIGIBLE = "INELIGIBLE", "Ineligible"

    demand_item = models.ForeignKey(
        DemandItem,
        on_delete=models.CASCADE,
        related_name="sourcing_options",
    )
    supplier_item = models.ForeignKey(
        "masterdata.SupplierItem",
        on_delete=models.PROTECT,
        related_name="demand_sourcing_options",
    )
    option_type = models.CharField(
        max_length=24,
        choices=OptionType.choices,
    )
    evaluation_status = models.CharField(
        max_length=12,
        choices=EvaluationStatus.choices,
    )
    rank = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    unit_price_vnd_per_kg_snapshot = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )
    max_daily_supply_kg_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    lead_time_hours_snapshot = models.IntegerField(
        null=True,
        blank=True,
    )
    exclusion_reason = models.TextField(
        blank=True,
        default="",
    )
    evaluated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "demand_sourcing_options"
        ordering = ("demand_item_id", "rank", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("demand_item", "supplier_item"),
                name="dso_demand_offer_uniq",
            ),
            models.CheckConstraint(
                condition=Q(
                    option_type__in=(
                        "SELECTED_EXISTING",
                        "ALTERNATIVE_ONLY",
                    )
                ),
                name="dso_option_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    evaluation_status__in=("ELIGIBLE", "INELIGIBLE"),
                ),
                name="dso_eval_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(rank__isnull=True) | Q(rank__gt=0),
                name="dso_rank_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price_vnd_per_kg_snapshot__gte=0),
                name="dso_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(max_daily_supply_kg_snapshot__isnull=True)
                    | Q(max_daily_supply_kg_snapshot__gt=0)
                ),
                name="dso_capacity_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(lead_time_hours_snapshot__isnull=True)
                    | Q(lead_time_hours_snapshot__gte=0)
                ),
                name="dso_lead_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=("demand_item", "evaluation_status"),
                name="dso_ditem_status_idx",
            ),
            models.Index(
                fields=("supplier_item", "option_type"),
                name="dso_offer_type_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.demand_item_id and self.supplier_item_id:
            if self.demand_item.item_id != self.supplier_item.item_id:
                errors["supplier_item"] = (
                    "Supplier offer must belong to the DemandItem's Item."
                )

            if (
                self.option_type == self.OptionType.SELECTED_EXISTING
                and self.supplier_item.supplier_id
                != self.demand_item.demand.supplier_id
            ):
                errors["supplier_item"] = (
                    "SELECTED_EXISTING must match the Demand's selected Supplier."
                )

        if (
            self.evaluation_status == self.EvaluationStatus.INELIGIBLE
            and not self.exclusion_reason.strip()
        ):
            errors["exclusion_reason"] = (
                "An ineligible sourcing option requires an exclusion reason."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"DemandItem {self.demand_item_id} -> "
            f"SupplierItem {self.supplier_item_id}"
        )


class SupplierConfirmation(models.Model):
    """
    Aggregate supplier response for a Demand and sourcing attempt.

    This entity is independent from SupplierRequest so V7 can represent
    NOT_REQUESTED confirmations without creating a SupplierRequest.
    """

    class ConfirmationStatus(models.TextChoices):
        NOT_REQUESTED = "NOT_REQUESTED", "Not requested"
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PARTIAL = "PARTIAL", "Partial"
        DECLINED = "DECLINED", "Declined"

    class SourceMode(models.TextChoices):
        LIVE_API = "LIVE_API", "Live API"
        SYNTHETIC_V7 = "SYNTHETIC_V7", "Synthetic V7 fixture"
        LEGACY_IMPORT = "LEGACY_IMPORT", "Legacy import"
        MANUAL_ENTRY = "MANUAL_ENTRY", "Manual entry"

    demand = models.ForeignKey(
        DeliveryDemand,
        on_delete=models.PROTECT,
        related_name="supplier_confirmations",
    )
    supplier = models.ForeignKey(
        "masterdata.Supplier",
        on_delete=models.PROTECT,
        related_name="demand_confirmations",
    )
    confirmation_status = models.CharField(
        max_length=20,
        choices=ConfirmationStatus.choices,
        default=ConfirmationStatus.NOT_REQUESTED,
    )
    source_mode = models.CharField(
        max_length=20,
        choices=SourceMode.choices,
        default=SourceMode.LIVE_API,
    )
    ready_date = models.DateField(
        null=True,
        blank=True,
    )
    ready_start_time = models.TimeField(
        null=True,
        blank=True,
    )
    ready_end_time = models.TimeField(
        null=True,
        blank=True,
    )
    pickup_address = models.TextField(
        null=True,
        blank=True,
    )
    recorded_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    confirmation_note = models.TextField(
        blank=True,
        default="",
    )

    # Positive PARTIAL commitments must be explicitly released before
    # the Demand may switch supplier and be submitted again.
    commitment_released_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    commitment_release_note = models.TextField(
        blank=True,
        default="",
    )
    commitment_released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_commitments_released",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_confirmations"
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    confirmation_status__in=(
                    "NOT_REQUESTED", "PENDING", "CONFIRMED",
                    "PARTIAL", "DECLINED",
                )
                ),
                name="sc_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    source_mode__in=(
                        "LIVE_API",
                        "SYNTHETIC_V7",
                        "LEGACY_IMPORT",
                        "MANUAL_ENTRY",
                    )
                ),
                name="sc_source_mode_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(ready_start_time__isnull=True, ready_end_time__isnull=True)
                    | Q(
                        ready_start_time__isnull=False,
                        ready_end_time__isnull=False,
                        ready_start_time__lt=F("ready_end_time"),
                    )
                ),
                name="sc_ready_time_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(commitment_released_at__isnull=True)
                    | Q(confirmation_status="PARTIAL")
                ),
                name="sc_release_only_partial",
            ),
        ]
        indexes = [
            models.Index(
                fields=("demand", "confirmation_status"),
                name="sc_demand_status_idx",
            ),
            models.Index(
                fields=("supplier", "confirmation_status"),
                name="sc_supplier_status_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.confirmation_status == self.ConfirmationStatus.NOT_REQUESTED:
            if self.recorded_at is not None:
                errors["recorded_at"] = (
                    "NOT_REQUESTED cannot have a supplier response timestamp."
                )

        elif self.confirmation_status == self.ConfirmationStatus.PENDING:
            if self.recorded_at is not None:
                errors["recorded_at"] = (
                    "PENDING cannot have a response timestamp."
                )

        elif self.confirmation_status in {
            self.ConfirmationStatus.CONFIRMED,
            self.ConfirmationStatus.PARTIAL,
            self.ConfirmationStatus.DECLINED,
        }:
            if self.recorded_at is None:
                errors["recorded_at"] = (
                    "A supplier response requires recorded_at."
                )

        if self.confirmation_status in {
            self.ConfirmationStatus.CONFIRMED,
            self.ConfirmationStatus.PARTIAL,
        } and self.ready_date is None:
            errors["ready_date"] = (
                "CONFIRMED and PARTIAL responses require a ready date."
            )

        if self.commitment_released_at is not None:
            if not self.commitment_release_note.strip():
                errors["commitment_release_note"] = (
                    "A release note is required when a commitment is released."
                )

        if errors:
            raise ValidationError(errors)

    @property
    def confirmed_weight_kg(self):
        if not self.pk:
            return 0

        request = getattr(self, "supplier_request", None)
        if request is None:
            return 0

        from django.db.models import Sum

        result = request.item_promises.aggregate(
            total=Sum("confirmed_weight_kg")
        )
        return result["total"] or 0

    @property
    def has_unreleased_partial_commitment(self):
        return (
            self.confirmation_status == self.ConfirmationStatus.PARTIAL
            and self.confirmed_weight_kg > 0
            and self.commitment_released_at is None
        )

    def __str__(self):
        return (
            f"Demand {self.demand_id} / Supplier {self.supplier_id}: "
            f"{self.confirmation_status}"
        )



class SupplierRequest(models.Model):
    """
    Immutable request attempt sent to one Supplier for one Demand.

    A resubmission creates a new attempt; previous attempts are retained.
    """

    class RequestStatus(models.TextChoices):
        WAITING = "WAITING", "Waiting for supplier"
        RESPONDED = "RESPONDED", "Supplier responded"
        EXPIRED = "EXPIRED", "Expired / closed without response"

    demand = models.ForeignKey(
        DeliveryDemand,
        on_delete=models.PROTECT,
        related_name="supplier_requests",
    )
    supplier = models.ForeignKey(
        "masterdata.Supplier",
        on_delete=models.PROTECT,
        related_name="demand_supplier_requests",
    )
    supplier_confirmation = models.OneToOneField(
        SupplierConfirmation,
        on_delete=models.PROTECT,
        related_name="supplier_request",
    )
    request_code = models.CharField(
        max_length=50,
        unique=True,
    )
    attempt_no = models.PositiveSmallIntegerField()
    request_status = models.CharField(
        max_length=12,
        choices=RequestStatus.choices,
        default=RequestStatus.WAITING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="supplier_requests_created",
    )
    sent_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_requests"
        ordering = ("demand_id", "attempt_no")
        constraints = [
            models.UniqueConstraint(
                fields=("demand", "attempt_no"),
                name="sr_demand_attempt_uniq",
            ),
            models.CheckConstraint(
                condition=Q(attempt_no__gt=0),
                name="sr_attempt_positive",
            ),
            models.CheckConstraint(
                condition=Q(
                    request_status__in=("WAITING", "RESPONDED", "EXPIRED")
                ),
                name="sr_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        request_status="RESPONDED",
                        responded_at__isnull=False,
                    )
                    | Q(
                        request_status__in=("WAITING", "EXPIRED"),
                        responded_at__isnull=True,
                    )
                ),
                name="sr_response_timestamp_valid",
            ),
            models.UniqueConstraint(
                fields=("demand",),
                condition=Q(request_status="WAITING"),
                name="sr_one_waiting_per_demand",
            ),
        ]
        indexes = [
            models.Index(
                fields=("supplier", "request_status"),
                name="sr_supplier_status_idx",
            ),
            models.Index(
                fields=("demand", "attempt_no"),
                name="sr_demand_attempt_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        pending_statuses = {
            self.RequestStatus.WAITING,
            self.RequestStatus.EXPIRED,
        }

        if self.supplier_confirmation_id:
            confirmation = self.supplier_confirmation

            if confirmation.demand_id != self.demand_id:
                errors["supplier_confirmation"] = (
                    "Confirmation must belong to the same Demand."
                )

            if confirmation.supplier_id != self.supplier_id:
                errors["supplier_confirmation"] = (
                    "Confirmation must belong to the same Supplier."
                )

            if (
                self.request_status in pending_statuses
                and confirmation.confirmation_status
                != SupplierConfirmation.ConfirmationStatus.PENDING
            ):
                errors["request_status"] = (
                    "WAITING or EXPIRED request must have a PENDING "
                    "confirmation because no supplier response was received."
                )

            if (
                self.request_status == self.RequestStatus.RESPONDED
                and confirmation.confirmation_status
                not in {
                    SupplierConfirmation.ConfirmationStatus.CONFIRMED,
                    SupplierConfirmation.ConfirmationStatus.PARTIAL,
                    SupplierConfirmation.ConfirmationStatus.DECLINED,
                }
            ):
                errors["request_status"] = (
                    "RESPONDED request requires a completed supplier response."
                )

        if self.request_status in pending_statuses and self.responded_at is not None:
            errors["responded_at"] = (
                "WAITING or EXPIRED request cannot have responded_at."
            )

        if (
            self.request_status == self.RequestStatus.RESPONDED
            and self.responded_at is None
        ):
            errors["responded_at"] = (
                "RESPONDED request requires responded_at."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.request_code


class SupplierItemPromise(models.Model):
    """
    Supplier's quantity response for one DemandItem in one request attempt.
    """

    class LineStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PARTIAL = "PARTIAL", "Partial"
        DECLINED = "DECLINED", "Declined"

    supplier_request = models.ForeignKey(
        SupplierRequest,
        on_delete=models.PROTECT,
        related_name="item_promises",
    )
    demand_item = models.ForeignKey(
        DemandItem,
        on_delete=models.PROTECT,
        related_name="supplier_promises",
    )
    supplier_item = models.ForeignKey(
        "masterdata.SupplierItem",
        on_delete=models.PROTECT,
        related_name="supplier_promises",
    )
    promised_weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )
    confirmed_weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    line_status = models.CharField(
        max_length=12,
        choices=LineStatus.choices,
        default=LineStatus.PENDING,
    )
    unit_price_vnd_per_kg_snapshot = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )
    lead_time_hours_snapshot = models.IntegerField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_item_promises"
        ordering = ("supplier_request_id", "demand_item_id")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier_request", "demand_item"),
                name="sip_request_ditem_uniq",
            ),
            models.CheckConstraint(
                condition=Q(promised_weight_kg__gt=0),
                name="sip_promised_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(confirmed_weight_kg__gte=0)
                    & Q(confirmed_weight_kg__lte=F("promised_weight_kg"))
                ),
                name="sip_confirmed_in_range",
            ),
            models.CheckConstraint(
                condition=Q(
                    unit_price_vnd_per_kg_snapshot__gte=0,
                ),
                name="sip_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(lead_time_hours_snapshot__isnull=True)
                    | Q(lead_time_hours_snapshot__gte=0)
                ),
                name="sip_lead_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(line_status="PENDING", confirmed_weight_kg=0)
                    | Q(line_status="DECLINED", confirmed_weight_kg=0)
                    | Q(
                        line_status="CONFIRMED",
                        confirmed_weight_kg=F("promised_weight_kg"),
                    )
                    | Q(
                        line_status="PARTIAL",
                        confirmed_weight_kg__gt=0,
                        confirmed_weight_kg__lt=F("promised_weight_kg"),
                    )
                ),
                name="sip_line_status_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=("supplier_request", "line_status"),
                name="sip_request_status_idx",
            ),
            models.Index(
                fields=("demand_item", "supplier_request"),
                name="sip_ditem_request_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.supplier_request_id and self.demand_item_id:
            if (
                self.supplier_request.demand_id
                != self.demand_item.demand_id
            ):
                errors["demand_item"] = (
                    "DemandItem must belong to the SupplierRequest's Demand."
                )

            if self.supplier_request.supplier_id != self.supplier_item.supplier_id:
                errors["supplier_item"] = (
                    "SupplierItem must belong to the SupplierRequest's Supplier."
                )

            if self.demand_item.item_id != self.supplier_item.item_id:
                errors["supplier_item"] = (
                    "SupplierItem must match the DemandItem's Item."
                )

        if (
            self.confirmed_weight_kg is not None
            and self.promised_weight_kg is not None
            and self.confirmed_weight_kg > self.promised_weight_kg
        ):
            errors["confirmed_weight_kg"] = (
                "Confirmed weight cannot exceed promised weight."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.supplier_request.request_code} / "
            f"DemandItem {self.demand_item_id}"
        )


class DemandSupplierSelection(models.Model):
    """
    Audit trail for an explicit Purchasing Staff supplier selection
    after a previous supplier request has been closed.
    """

    class SelectionReason(models.TextChoices):
        RETRY_AFTER_EXPIRED = (
            "RETRY_AFTER_EXPIRED",
            "Retry after expired request",
        )
        REPLACE_AFTER_DECLINED = (
            "REPLACE_AFTER_DECLINED",
            "Replace supplier after decline",
        )
        REPLACE_AFTER_PARTIAL = (
            "REPLACE_AFTER_PARTIAL",
            "Replace supplier after partial confirmation",
        )

    demand = models.ForeignKey(
        DeliveryDemand,
        on_delete=models.PROTECT,
        related_name="supplier_selections",
    )
    previous_request = models.ForeignKey(
        SupplierRequest,
        on_delete=models.PROTECT,
        related_name="supplier_selections",
    )
    previous_supplier = models.ForeignKey(
        "masterdata.Supplier",
        on_delete=models.PROTECT,
        related_name="outgoing_demand_selections",
    )
    selected_supplier = models.ForeignKey(
        "masterdata.Supplier",
        on_delete=models.PROTECT,
        related_name="incoming_demand_selections",
    )
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="demand_supplier_selections",
    )
    selection_no = models.PositiveSmallIntegerField()
    selection_reason = models.CharField(
        max_length=32,
        choices=SelectionReason.choices,
    )
    selected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "demand_supplier_selections"
        ordering = ("demand_id", "selection_no")
        constraints = [
            models.UniqueConstraint(
                fields=("demand", "selection_no"),
                name="dss_demand_selection_uniq",
            ),
            models.CheckConstraint(
                condition=Q(selection_no__gt=0),
                name="dss_selection_positive",
            ),
            models.CheckConstraint(
                condition=Q(
                    selection_reason__in=(
                        "RETRY_AFTER_EXPIRED",
                        "REPLACE_AFTER_DECLINED",
                        "REPLACE_AFTER_PARTIAL",
                    )
                ),
                name="dss_reason_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(selection_reason="RETRY_AFTER_EXPIRED")
                    | ~Q(selected_supplier=F("previous_supplier"))
                ),
                name="dss_supplier_change_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("previous_request",),
                name="dss_previous_req_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.previous_request_id and self.demand_id:
            previous_request = self.previous_request
            confirmation = previous_request.supplier_confirmation

            if previous_request.demand_id != self.demand_id:
                errors["previous_request"] = (
                    "Previous request must belong to the same Demand."
                )

            if previous_request.supplier_id != self.previous_supplier_id:
                errors["previous_supplier"] = (
                    "Previous Supplier must match the previous request."
                )

            if self.selection_reason == self.SelectionReason.RETRY_AFTER_EXPIRED:
                if (
                    previous_request.request_status
                    != SupplierRequest.RequestStatus.EXPIRED
                ):
                    errors["selection_reason"] = (
                        "RETRY_AFTER_EXPIRED requires an EXPIRED request."
                    )

            elif self.selection_reason == self.SelectionReason.REPLACE_AFTER_DECLINED:
                if (
                    previous_request.request_status
                    != SupplierRequest.RequestStatus.RESPONDED
                    or confirmation.confirmation_status
                    != SupplierConfirmation.ConfirmationStatus.DECLINED
                ):
                    errors["selection_reason"] = (
                        "REPLACE_AFTER_DECLINED requires a DECLINED response."
                    )

            elif self.selection_reason == self.SelectionReason.REPLACE_AFTER_PARTIAL:
                if (
                    previous_request.request_status
                    != SupplierRequest.RequestStatus.RESPONDED
                    or confirmation.confirmation_status
                    != SupplierConfirmation.ConfirmationStatus.PARTIAL
                ):
                    errors["selection_reason"] = (
                        "REPLACE_AFTER_PARTIAL requires a PARTIAL response."
                    )

                elif (
                    confirmation.confirmed_weight_kg > 0
                    and confirmation.commitment_released_at is None
                ):
                    errors["previous_request"] = (
                        "A positive PARTIAL commitment must be released "
                        "before selecting another Supplier."
                    )

        if (
            self.demand_id
            and self.selected_supplier_id
            and self.demand.supplier_id != self.selected_supplier_id
        ):
            errors["selected_supplier"] = (
                "Selected Supplier must match the Demand's current Supplier."
            )

        if (
            self.selection_reason
            != self.SelectionReason.RETRY_AFTER_EXPIRED
            and self.previous_supplier_id
            and self.selected_supplier_id == self.previous_supplier_id
        ):
            errors["selected_supplier"] = (
                "A DECLINED or PARTIAL Supplier cannot be selected again."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.demand_id} / selection {self.selection_no}: "
            f"{self.previous_supplier_id} -> {self.selected_supplier_id}"
        )
