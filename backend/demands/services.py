import secrets
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from masterdata.models import (
    Item,
    Outlet,
    Supplier,
    SupplierItem,
)

from .models import (
    DeliveryDemand,
    DemandItem,
    DemandStatus,
)


def _generate_demand_code():
    """Return DD-YYYYMMDD-XXXXXXXX using the local creation date."""
    return f"DD-{timezone.localdate(timezone=ZoneInfo(settings.COLOGI_BUSINESS_TIME_ZONE)):%Y%m%d}-{secrets.token_hex(4).upper()}"


def _parse_weight(value, index):
    try:
        weight = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({
            "items": f"Item line {index}: invalid required weight."
        })

    if not weight.is_finite() or weight <= 0:
        raise ValidationError({
            "items": f"Item line {index}: weight must be greater than zero."
        })

    return weight


def _resolve_demand_items(items_data):
    if not isinstance(items_data, (list, tuple)) or not items_data:
        raise ValidationError({
            "items": "A demand must contain at least one item."
        })

    parsed = []
    item_ids = []

    for index, row in enumerate(items_data, start=1):
        if not isinstance(row, dict):
            raise ValidationError({
                "items": f"Item line {index} must be an object."
            })

        item_id = row.get("item_id")
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            raise ValidationError({
                "items": f"Item line {index}: invalid item_id."
            })

        if item_id <= 0:
            raise ValidationError({
                "items": f"Item line {index}: invalid item_id."
            })

        weight = _parse_weight(
            row.get("required_weight_kg"),
            index,
        )

        parsed.append({
            "item_id": item_id,
            "required_weight_kg": weight,
            "unit_of_measure": row.get("unit_of_measure"),
            "item_note": row.get("item_note"),
        })
        item_ids.append(item_id)

    if len(item_ids) != len(set(item_ids)):
        raise ValidationError({
            "items": "An item can appear only once in a demand."
        })

    item_map = Item.objects.select_related(
        "cargo_category"
    ).in_bulk(item_ids)

    missing_ids = set(item_ids) - set(item_map)

    if missing_ids:
        raise ValidationError({
            "items": f"Unknown item IDs: {sorted(missing_ids)}"
        })

    resolved = []

    for index, row in enumerate(parsed, start=1):
        item = item_map[row["item_id"]]

        if not item.is_active:
            raise ValidationError({
                "items": f"Item {item.item_code} is inactive."
            })

        supplied_uom = row["unit_of_measure"]

        if supplied_uom and supplied_uom != item.weight_unit:
            raise ValidationError({
                "items": (
                    f"Item {item.item_code}: unit of measure must match "
                    f"{item.weight_unit}."
                )
            })

        resolved.append({
            "item": item,
            "required_weight_kg": row["required_weight_kg"],
            "unit_of_measure": item.weight_unit,
            "item_note": row["item_note"],
        })

    categories = {
        row["item"].cargo_category_id
        for row in resolved
    }

    if len(categories) != 1:
        raise ValidationError({
            "items": (
                "All items in one demand must belong to the same "
                "cargo category."
            )
        })

    category = resolved[0]["item"].cargo_category

    if not category.is_active:
        raise ValidationError({
            "items": "The cargo category is inactive."
        })

    total_weight = sum(
        (row["required_weight_kg"] for row in resolved),
        Decimal("0"),
    )

    return resolved, category, total_weight


@transaction.atomic
def create_draft_demand(
    *,
    demand_code=None,
    supplier_id,
    outlet_id,
    created_by,
    requested_date,
    items,
    requested_start_time=None,
    requested_end_time=None,
    notes=None,
):
    """
    Create a Draft demand and all its item lines atomically.

    quantity_kg and cargo_category are derived from the item lines.
    Supplier offer validation is intentionally deferred until submission.
    """

    try:
        supplier = Supplier.objects.get(pk=supplier_id)
    except Supplier.DoesNotExist:
        raise ValidationError({
            "supplier_id": "Selected supplier does not exist."
        })

    try:
        outlet = Outlet.objects.get(pk=outlet_id)
    except Outlet.DoesNotExist:
        raise ValidationError({
            "outlet_id": "Selected outlet does not exist."
        })

    if not supplier.is_active:
        raise ValidationError({
            "supplier_id": "Selected supplier is inactive."
        })

    if not outlet.is_active:
        raise ValidationError({
            "outlet_id": "Selected outlet is inactive."
        })

    resolved_items, category, total_weight = (
        _resolve_demand_items(items)
    )

    generated_code = demand_code is None
    max_code_attempts = 10

    for attempt in range(max_code_attempts):
        candidate_code = (
            _generate_demand_code()
            if generated_code
            else demand_code
        )

        demand = DeliveryDemand(
            demand_code=candidate_code,
            supplier=supplier,
            outlet=outlet,
            cargo_category=category,
            quantity_kg=total_weight,
            requested_date=requested_date,
            requested_start_time=requested_start_time,
            requested_end_time=requested_end_time,
            status=DemandStatus.DRAFT,
            notes=notes,
            created_by=created_by,
        )

        try:
            # A savepoint lets the service retry if another transaction
            # inserts the same generated code concurrently.
            with transaction.atomic():
                demand.full_clean(
                    validate_unique=not generated_code,
                )
                demand.save()
            break
        except IntegrityError:
            if not generated_code:
                raise

            # Retry only when the generated code itself collided.
            if not DeliveryDemand.objects.filter(
                demand_code=candidate_code
            ).exists():
                raise
    else:
        raise ValidationError({
            "demand_code": (
                "Could not generate a unique demand code. "
                "Please retry the request."
            )
        })

    for row in resolved_items:
        demand_item = DemandItem(
            demand=demand,
            item=row["item"],
            required_weight_kg=row["required_weight_kg"],
            unit_of_measure=row["unit_of_measure"],
            item_note=row["item_note"],
        )

        demand_item.full_clean()
        demand_item.save()

    return demand



@transaction.atomic
def update_draft_demand(*, demand_id, updated_by, changes):
    """
    Update an existing DRAFT demand atomically.

    Only the creator may edit it. Outlet, creator, demand code, status,
    cargo category, and total quantity are not client-editable.
    Cargo category and total quantity are recalculated when item lines
    are replaced.
    """

    allowed_fields = {
        "supplier_id",
        "requested_date",
        "requested_start_time",
        "requested_end_time",
        "notes",
        "items",
    }

    unknown_fields = set(changes) - allowed_fields
    if unknown_fields:
        raise ValidationError({
            "fields": (
                "Unsupported fields: "
                + ", ".join(sorted(unknown_fields))
            )
        })

    try:
        demand = DeliveryDemand.objects.select_for_update().get(
            pk=demand_id
        )
    except DeliveryDemand.DoesNotExist:
        raise ValidationError({
            "demand": "Demand does not exist."
        })

    if demand.created_by_id != getattr(updated_by, "pk", None):
        raise ValidationError({
            "created_by": "Only the demand creator may edit this demand."
        })

    if demand.status != DemandStatus.DRAFT:
        raise ValidationError({
            "status": "Only DRAFT demands can be edited."
        })

    if "supplier_id" in changes:
        try:
            supplier = Supplier.objects.get(
                pk=changes["supplier_id"]
            )
        except Supplier.DoesNotExist:
            raise ValidationError({
                "supplier_id": "Selected supplier does not exist."
            })

        if not supplier.is_active:
            raise ValidationError({
                "supplier_id": "Selected supplier is inactive."
            })

        demand.supplier = supplier

    for field in (
        "requested_date",
        "requested_start_time",
        "requested_end_time",
        "notes",
    ):
        if field in changes:
            setattr(demand, field, changes[field])

    resolved_items = None

    if "items" in changes:
        resolved_items, category, total_weight = (
            _resolve_demand_items(changes["items"])
        )
        demand.cargo_category = category
        demand.quantity_kg = total_weight

    # Validate the updated header before changing persisted item lines.
    demand.full_clean()
    demand.save()

    if resolved_items is not None:
        # This replacement and all inserts are part of the same transaction.
        demand.items.all().delete()

        for row in resolved_items:
            demand_item = DemandItem(
                demand=demand,
                item=row["item"],
                required_weight_kg=row["required_weight_kg"],
                unit_of_measure=row["unit_of_measure"],
                item_note=row["item_note"],
            )
            demand_item.full_clean()
            demand_item.save()

    return demand


def validate_supplier_offers_for_demand(demand):
    """
    V7-R02 pre-submission check for one demand.

    Does not create a SupplierRequest or switch the selected supplier.
    Cross-demand daily capacity aggregation must be handled by the
    submission workflow before requests are issued.
    """

    if not demand.supplier.is_active:
        raise ValidationError({
            "supplier": "Selected supplier is inactive."
        })

    lines = list(
        demand.items.select_related("item")
    )

    if not lines:
        raise ValidationError({
            "items": "A demand without items cannot be submitted."
        })

    offers = {
        offer.item_id: offer
        for offer in SupplierItem.objects.filter(
            supplier_id=demand.supplier_id,
            item_id__in=[line.item_id for line in lines],
            offer_status=SupplierItem.OfferStatus.ACTIVE,
        )
    }
    errors = []

    for line in lines:
        item = line.item

        if not item.is_active:
            errors.append(
                f"{item.item_code}: item is inactive."
            )
            continue

        offer = offers.get(line.item_id)

        if offer is None:
            errors.append(
                f"{item.item_code}: selected supplier has no ACTIVE offer."
            )
            continue

        if offer.max_daily_supply_kg is None:
            errors.append(
                f"{item.item_code}: supplier daily capacity is unknown."
            )
            continue

        if line.required_weight_kg > offer.max_daily_supply_kg:
            errors.append(
                f"{item.item_code}: requested weight exceeds "
                "supplier daily capacity."
            )

    if errors:
        raise ValidationError({"supplier_offers": errors})

    return True
