import secrets
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
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
    DemandSourcingOption,
    DemandSupplierSelection,
    SupplierConfirmation,
    SupplierItemPromise,
    SupplierRequest,
)

from accounts.models import AuditLog

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


def validate_supplier_offers_for_demand(
    demand,
    *,
    offers_by_item=None,
    lines=None,
):
    """
    V7-R02 pre-submission check for one Demand.

    Validates every DemandItem against the Demand's selected Supplier.
    Capacity is checked per DemandItem against the configured offer.

    Cross-Demand daily capacity aggregation is deliberately not inferred
    here: the reservation semantics for pending supplier requests still
    require a separate business-rule decision.
    """

    if not demand.supplier.is_active:
        raise ValidationError({
            "supplier": "Selected supplier is inactive."
        })

    if lines is None:
        lines = list(
            demand.items.select_related("item")
        )

    if not lines:
        raise ValidationError({
            "items": "A demand without items cannot be submitted."
        })

    if offers_by_item is None:
        offer_rows = SupplierItem.objects.filter(
            supplier_id=demand.supplier_id,
            item_id__in=[line.item_id for line in lines],
        )
    elif hasattr(offers_by_item, "values"):
        offer_rows = offers_by_item.values()
    else:
        offer_rows = offers_by_item

    active_offers = {
        offer.item_id: offer
        for offer in offer_rows
        if offer.offer_status == SupplierItem.OfferStatus.ACTIVE
    }

    errors = []

    for line in lines:
        item = line.item

        if not item.is_active:
            errors.append(
                f"{item.item_code}: item is inactive."
            )
            continue

        offer = active_offers.get(line.item_id)

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



def _lock_demand_lines_and_offers(demand, supplier):
    """Lock the current DemandItems, Items and selected Supplier offers."""
    lines = list(
        DemandItem.objects.select_for_update()
        .filter(demand_id=demand.pk)
        .order_by("pk")
    )

    if not lines:
        raise ValidationError({
            "items": "A demand without items cannot be submitted."
        })

    item_ids = [line.item_id for line in lines]
    locked_items = {
        item.pk: item
        for item in Item.objects.select_for_update().filter(pk__in=item_ids)
    }

    for line in lines:
        item = locked_items.get(line.item_id)
        if item is None:
            raise ValidationError({
                "items": f"Item {line.item_id} no longer exists."
            })
        line.item = item

    offers = list(
        SupplierItem.objects.select_for_update().filter(
            supplier_id=supplier.pk,
            item_id__in=item_ids,
        )
    )
    offers_by_item = {offer.item_id: offer for offer in offers}

    # The validator checks the candidate Supplier through demand.supplier.
    demand.supplier = supplier
    validate_supplier_offers_for_demand(
        demand,
        offers_by_item=offers_by_item,
        lines=lines,
    )
    return lines, offers_by_item


def _sync_selected_sourcing_options(demand, lines, offers_by_item, now):
    """
    Maintain one current SELECTED_EXISTING option per DemandItem.
    Previous selected offers remain as ALTERNATIVE_ONLY snapshots.
    """
    for line in lines:
        offer = offers_by_item[line.item_id]

        previous_selected = (
            DemandSourcingOption.objects.select_for_update()
            .filter(
                demand_item=line,
                option_type=DemandSourcingOption.OptionType.SELECTED_EXISTING,
            )
            .exclude(supplier_item_id=offer.pk)
        )

        for previous_option in previous_selected:
            previous_option.option_type = (
                DemandSourcingOption.OptionType.ALTERNATIVE_ONLY
            )
            previous_option.rank = None
            previous_option.full_clean()
            previous_option.save(update_fields=["option_type", "rank"])

        option = (
            DemandSourcingOption.objects.select_for_update()
            .filter(demand_item=line, supplier_item=offer)
            .first()
        )

        values = {
            "option_type": DemandSourcingOption.OptionType.SELECTED_EXISTING,
            "evaluation_status": DemandSourcingOption.EvaluationStatus.ELIGIBLE,
            "rank": 1,
            "unit_price_vnd_per_kg_snapshot": offer.unit_price_vnd_per_kg,
            "max_daily_supply_kg_snapshot": offer.max_daily_supply_kg,
            "lead_time_hours_snapshot": offer.lead_time_hours,
            "exclusion_reason": "",
            "evaluated_at": now,
        }

        if option is None:
            option = DemandSourcingOption(
                demand_item=line,
                supplier_item=offer,
                **values,
            )
        else:
            for field, value in values.items():
                setattr(option, field, value)

        option.full_clean()
        option.save()

@transaction.atomic
def cancel_demand(*, demand_id, cancelled_by, ip_address=None):
    """
    Cancel a DRAFT or eligible SUBMITTED Demand atomically.

    Preserve all SupplierRequest, SupplierConfirmation and
    SupplierItemPromise history.
    """
    try:
        demand = DeliveryDemand.objects.select_for_update().get(
            pk=demand_id
        )
    except DeliveryDemand.DoesNotExist:
        raise ValidationError({"demand": "Demand does not exist."})

    if demand.created_by_id != getattr(cancelled_by, "pk", None):
        raise ValidationError({
            "created_by": "Only the Demand creator may cancel this Demand."
        })

    if demand.status not in {
        DemandStatus.DRAFT,
        DemandStatus.SUBMITTED,
    }:
        raise ValidationError({
            "status": "This Demand cannot be cancelled in its current status."
        })

    # Lock every request belonging to this Demand.
    requests = list(
        SupplierRequest.objects.select_for_update()
        .filter(demand_id=demand.pk)
        .order_by("pk")
    )

    request_ids = [request.pk for request in requests]

    # Lock every confirmation, including standalone NOT_REQUESTED records.
    confirmations = list(
        SupplierConfirmation.objects.select_for_update()
        .filter(demand_id=demand.pk)
        .order_by("pk")
    )

    # Lock all promise rows and calculate confirmed quantities by request.
    promises = list(
        SupplierItemPromise.objects.select_for_update()
        .filter(supplier_request_id__in=request_ids)
        .order_by("pk")
    )

    confirmed_weights = {}
    for promise in promises:
        confirmed_weights[promise.supplier_request_id] = (
            confirmed_weights.get(promise.supplier_request_id, Decimal("0"))
            + promise.confirmed_weight_kg
        )

    confirmations_by_id = {
        confirmation.pk: confirmation
        for confirmation in confirmations
    }

    # Any positive, unreleased CONFIRMED/PARTIAL commitment blocks Cancel.
    for request in requests:
        confirmation = confirmations_by_id.get(
            request.supplier_confirmation_id
        )
        if confirmation is None:
            raise ValidationError({
                "supplier_request": "Supplier confirmation is missing."
            })

        confirmed_weight = confirmed_weights.get(
            request.pk, Decimal("0")
        )

        if confirmation.confirmation_status in {
            SupplierConfirmation.ConfirmationStatus.CONFIRMED,
            SupplierConfirmation.ConfirmationStatus.PARTIAL,
        }:
            if confirmed_weight <= 0:
                raise ValidationError({
                    "commitment": (
                        "Supplier confirmation has no valid confirmed "
                        "quantity. Cancellation is blocked due to "
                        "inconsistent commitment data."
                    )
                })

            if confirmation.commitment_released_at is None:
                raise ValidationError({
                    "commitment": (
                        "An unreleased supplier commitment prevents cancellation."
                    )
                })

    if demand.status == DemandStatus.DRAFT:
        if requests:
            raise ValidationError({
                "supplier_request": (
                    "A DRAFT Demand with SupplierRequest history cannot be cancelled."
                )
            })

    else:
        if not requests:
            raise ValidationError({
                "supplier_request": (
                    "A SUBMITTED Demand must have SupplierRequest history."
                )
            })

        latest_request = max(
            requests,
            key=lambda request: (request.attempt_no, request.pk),
        )
        latest_confirmation = confirmations_by_id[
            latest_request.supplier_confirmation_id
        ]

        if (
            latest_request.request_status
            != SupplierRequest.RequestStatus.RESPONDED
            or latest_confirmation.confirmation_status
            != SupplierConfirmation.ConfirmationStatus.DECLINED
        ):
            raise ValidationError({
                "supplier_request": (
                    "A SUBMITTED Demand can only be cancelled after "
                    "the latest SupplierRequest is RESPONDED and DECLINED."
                )
            })

    old_status = demand.status
    demand.status = DemandStatus.CANCELLED
    demand.save(update_fields=["status", "updated_at"])

    AuditLog.objects.create(
        actor_user=cancelled_by,
        action="DEMAND_CANCELLED",
        entity_type="DEMAND",
        entity_id=str(demand.pk),
        old_values={"status": old_status},
        new_values={"status": DemandStatus.CANCELLED},
        ip_address=ip_address,
    )

    return demand

def _latest_supplier_request_for_update(demand):
    return (
        SupplierRequest.objects.select_for_update()
        .select_related("supplier_confirmation")
        .filter(demand_id=demand.pk)
        .order_by("-attempt_no", "-pk")
        .first()
    )


def _selection_reason_for_closed_request(previous_request):
    """Return the allowed explicit selection reason for the last attempt."""
    confirmation = previous_request.supplier_confirmation

    if previous_request.request_status == SupplierRequest.RequestStatus.EXPIRED:
        if (
            confirmation.confirmation_status
            != SupplierConfirmation.ConfirmationStatus.PENDING
        ):
            raise ValidationError({
                "supplier_request": (
                    "An EXPIRED request must retain a PENDING confirmation."
                )
            })
        return DemandSupplierSelection.SelectionReason.RETRY_AFTER_EXPIRED

    if previous_request.request_status != SupplierRequest.RequestStatus.RESPONDED:
        raise ValidationError({
            "supplier_request": "The previous request is not closed."
        })

    if (
        confirmation.confirmation_status
        == SupplierConfirmation.ConfirmationStatus.DECLINED
    ):
        return DemandSupplierSelection.SelectionReason.REPLACE_AFTER_DECLINED

    if (
        confirmation.confirmation_status
        == SupplierConfirmation.ConfirmationStatus.PARTIAL
    ):
        if (
            confirmation.confirmed_weight_kg > 0
            and confirmation.commitment_released_at is None
        ):
            raise ValidationError({
                "commitment": (
                    "The positive PARTIAL commitment must be released "
                    "before selecting another Supplier."
                )
            })
        return DemandSupplierSelection.SelectionReason.REPLACE_AFTER_PARTIAL

    raise ValidationError({
        "supplier_request": (
            "A fully CONFIRMED Supplier response cannot be resubmitted "
            "through supplier replacement."
        )
    })


@transaction.atomic
def select_supplier_for_submitted_demand(
    *,
    demand_id,
    selected_by,
    selected_supplier_id,
):
    """
    Explicitly select a Supplier after the previous request has closed.

    The Demand remains SUBMITTED. Selection does not issue a new request;
    a separate Submit call is required. Selection history is append-only.
    """
    try:
        demand = DeliveryDemand.objects.select_for_update().get(pk=demand_id)
    except DeliveryDemand.DoesNotExist:
        raise ValidationError({"demand": "Demand does not exist."})

    if demand.created_by_id != getattr(selected_by, "pk", None):
        raise ValidationError({
            "created_by": "Only the Demand creator may select a Supplier."
        })

    if demand.status != DemandStatus.SUBMITTED:
        raise ValidationError({
            "status": "Supplier selection requires a SUBMITTED Demand."
        })

    previous_request = _latest_supplier_request_for_update(demand)
    if previous_request is None:
        raise ValidationError({
            "supplier_request": "No previous SupplierRequest exists."
        })

    if previous_request.request_status == SupplierRequest.RequestStatus.WAITING:
        raise ValidationError({
            "supplier_request": (
                "The current SupplierRequest is still WAITING."
            )
        })

    selection_reason = _selection_reason_for_closed_request(previous_request)

    try:
        selected_supplier = Supplier.objects.select_for_update().get(
            pk=selected_supplier_id
        )
    except Supplier.DoesNotExist:
        raise ValidationError({
            "supplier_id": "Selected Supplier does not exist."
        })

    if not selected_supplier.is_active:
        raise ValidationError({
            "supplier_id": "Selected Supplier is inactive."
        })

    if (
        selection_reason
        != DemandSupplierSelection.SelectionReason.RETRY_AFTER_EXPIRED
        and selected_supplier.pk == previous_request.supplier_id
    ):
        raise ValidationError({
            "supplier_id": (
                "A DECLINED or PARTIAL Supplier must be replaced "
                "with a different Supplier."
            )
        })

    lines, offers_by_item = _lock_demand_lines_and_offers(
        demand,
        selected_supplier,
    )

    # Persist the explicit selection before validating sourcing option
    # cross-relations, within the same transaction.
    demand.supplier = selected_supplier
    demand.full_clean()
    demand.save(update_fields=["supplier", "updated_at"])

    now = timezone.now()
    _sync_selected_sourcing_options(
        demand,
        lines,
        offers_by_item,
        now,
    )

    previous_selection_no = (
        DemandSupplierSelection.objects.filter(demand_id=demand.pk)
        .aggregate(value=Max("selection_no"))["value"]
        or 0
    )

    selection = DemandSupplierSelection(
        demand=demand,
        previous_request=previous_request,
        previous_supplier_id=previous_request.supplier_id,
        selected_supplier=selected_supplier,
        selected_by=selected_by,
        selection_no=previous_selection_no + 1,
        selection_reason=selection_reason,
        selected_at=now,
    )
    selection.full_clean()
    selection.save()

    return selection


@transaction.atomic
def submit_demand(*, demand_id, submitted_by):
    """
    Submit a DRAFT Demand for the first time, or issue a new attempt for
    a SUBMITTED Demand after explicit Supplier selection.

    The Demand remains SUBMITTED for every subsequent attempt.
    """
    try:
        demand = DeliveryDemand.objects.select_for_update().get(pk=demand_id)
    except DeliveryDemand.DoesNotExist:
        raise ValidationError({"demand": "Demand does not exist."})

    if demand.created_by_id != getattr(submitted_by, "pk", None):
        raise ValidationError({
            "created_by": "Only the Demand creator may submit this Demand."
        })

    previous_request = _latest_supplier_request_for_update(demand)

    if demand.status == DemandStatus.DRAFT:
        if previous_request is not None:
            raise ValidationError({
                "supplier_request": (
                    "A DRAFT Demand cannot have a previous SupplierRequest."
                )
            })

    elif demand.status == DemandStatus.SUBMITTED:
        if previous_request is None:
            raise ValidationError({
                "supplier_request": (
                    "A previously submitted Demand must have request history."
                )
            })

        if previous_request.request_status == SupplierRequest.RequestStatus.WAITING:
            raise ValidationError({
                "supplier_request": (
                    "A SupplierRequest is still WAITING. "
                    "It must be closed before another attempt can be issued."
                )
            })

        _selection_reason_for_closed_request(previous_request)

        latest_selection = (
            DemandSupplierSelection.objects.select_for_update()
            .filter(
                demand_id=demand.pk,
                previous_request_id=previous_request.pk,
            )
            .order_by("-selection_no", "-pk")
            .first()
        )

        if (
            latest_selection is None
            or latest_selection.selected_supplier_id != demand.supplier_id
        ):
            raise ValidationError({
                "supplier_selection": (
                    "Purchasing Staff must explicitly select a Supplier "
                    "after the previous request is closed."
                )
            })

        expected_reason = _selection_reason_for_closed_request(previous_request)
        if latest_selection.selection_reason != expected_reason:
            raise ValidationError({
                "supplier_selection": (
                    "Supplier selection does not match the previous response."
                )
            })

    else:
        raise ValidationError({
            "status": "Only DRAFT or eligible SUBMITTED demands can be submitted."
        })

    try:
        supplier = Supplier.objects.select_for_update().get(
            pk=demand.supplier_id
        )
    except Supplier.DoesNotExist:
        raise ValidationError({
            "supplier": "Selected Supplier does not exist."
        })

    if not supplier.is_active:
        raise ValidationError({
            "supplier": "Selected Supplier is inactive."
        })

    lines, offers_by_item = _lock_demand_lines_and_offers(demand, supplier)

    last_attempt = (
        SupplierRequest.objects.filter(demand_id=demand.pk)
        .aggregate(value=Max("attempt_no"))["value"]
        or 0
    )

    if last_attempt >= 32767:
        raise ValidationError({
            "attempt_no": "The maximum number of SupplierRequest attempts has been reached."
        })

    attempt_no = last_attempt + 1
    now = timezone.now()

    confirmation = SupplierConfirmation(
        demand=demand,
        supplier=supplier,
        confirmation_status=SupplierConfirmation.ConfirmationStatus.PENDING,
        source_mode=SupplierConfirmation.SourceMode.LIVE_API,
    )
    confirmation.full_clean()
    confirmation.save()

    request = SupplierRequest(
        demand=demand,
        supplier=supplier,
        supplier_confirmation=confirmation,
        request_code=f"SR-{secrets.token_hex(12).upper()}",
        attempt_no=attempt_no,
        request_status=SupplierRequest.RequestStatus.WAITING,
        created_by=submitted_by,
        sent_at=now,
    )
    request.full_clean()
    request.save()


    for line in lines:
        offer = offers_by_item[line.item_id]
        promise = SupplierItemPromise(
            supplier_request=request,
            demand_item=line,
            supplier_item=offer,
            promised_weight_kg=line.required_weight_kg,
            confirmed_weight_kg=Decimal("0.000"),
            line_status=SupplierItemPromise.LineStatus.PENDING,
            unit_price_vnd_per_kg_snapshot=offer.unit_price_vnd_per_kg,
            lead_time_hours_snapshot=offer.lead_time_hours,
        )
        promise.full_clean()
        promise.save()

    # First submit transitions DRAFT -> SUBMITTED.
    # Retry leaves the Demand SUBMITTED and only creates a new attempt.
    if demand.status == DemandStatus.DRAFT:
        demand.status = DemandStatus.SUBMITTED
        demand.full_clean()
        demand.save(update_fields=["status", "updated_at"])

    return request
