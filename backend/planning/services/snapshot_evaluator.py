"""Evaluate immutable CP8 Demand snapshots through the pure F1 gates.

This module does not query or mutate ORM records. All evaluation inputs are
constructed from the snapshots captured for a PlanningRun.
"""

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from planning.f1.capacity import (
    PromiseCommitment,
    SupplierItemCapacity,
    SupplierRequestCommitment,
    evaluate_supplier_item_capacity,
)
from planning.f1.candidate_groups import (
    CandidateDemandInput,
    generate_candidate_groups,
)
from planning.f1.eligibility import (
    DemandEligibilityInput,
    EligibilityDemandItem,
    EligibilityStatus,
    evaluate_demand_eligibility,
)
from planning.f1.orchestration import (
    F1DemandEvaluation,
    F1Evaluation,
)
from planning.f1.supplier_confirmation import (
    ConfirmationGateResult,
    ConfirmationGateStatus,
    DemandItemRequirement,
    PromiseLine,
    SupplierResponseSnapshot,
    evaluate_supplier_confirmation,
)
from planning.f1.cargo_compatibility import (
    normalize_cargo_compatibility_matrix,
)
from planning.services.snapshot_reader import (
    read_run_snapshots,
)


ZERO = Decimal("0")


def _required_int(source, key, context):
    value = source.get(key)

    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            f"{context}.{key} must be an integer."
        )

    return value


def _decimal_value(value, context, *, allow_none=False):
    if value is None and allow_none:
        return None

    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            f"{context} must be a valid decimal value."
        )

    if not result.is_finite():
        raise ValidationError(
            f"{context} must be a finite decimal value."
        )

    return result


def _date_value(value, context, *, allow_none=False):
    if value is None and allow_none:
        return None

    if isinstance(value, datetime):
        raise ValidationError(
            f"{context} must be a date, not a datetime."
        )

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise ValidationError(
            f"{context} must be an ISO date string."
        )

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError(
            f"{context} must be an ISO date string."
        )


def _time_value(value, context):
    if value is None:
        return None

    if isinstance(value, time):
        return value

    if not isinstance(value, str):
        raise ValidationError(
            f"{context} must be an ISO time string or null."
        )

    try:
        return time.fromisoformat(value)
    except ValueError:
        raise ValidationError(
            f"{context} must be an ISO time string."
        )


def _mapping(value, context):
    if not hasattr(value, "get"):
        raise ValidationError(
            f"{context} must be an object."
        )
    return value


def _confirmation_status(request):
    confirmation = _mapping(
        request.get("confirmation"),
        "capacity_request.confirmation",
    )
    status = confirmation.get("confirmation_status")

    if not isinstance(status, str):
        raise ValidationError(
            "Supplier confirmation status must be a string."
        )

    return status


def _promise_links_valid(request, promise):
    confirmation = request.get("confirmation")

    if not hasattr(confirmation, "get"):
        return False

    request_id = request.get("id")
    demand_id = request.get("demand_id")
    supplier_id = request.get("supplier_id")

    return (
        promise.get("supplier_request_id") == request_id
        and promise.get("demand_item_demand_id") == demand_id
        and promise.get("supplier_item_supplier_id") == supplier_id
        and promise.get("item_id") == promise.get(
            "supplier_item_item_id"
        )
        and confirmation.get("demand_id") == demand_id
        and confirmation.get("supplier_id") == supplier_id
    )


def _build_capacity_requests(request_snapshots):
    """Convert every captured Request attempt into capacity DTOs."""
    result = []

    for request in request_snapshots:
        request = _mapping(request, "capacity_request")
        request_id = _required_int(request, "id", "capacity_request")
        demand_id = _required_int(
            request, "demand_id", "capacity_request"
        )
        supplier_id = _required_int(
            request, "supplier_id", "capacity_request"
        )
        attempt_no = _required_int(
            request, "attempt_no", "capacity_request"
        )

        requested_date = _date_value(
            request.get("requested_date"),
            "capacity_request.requested_date",
        )

        request_status = request.get("request_status")
        demand_status = request.get("demand_status")

        if not isinstance(request_status, str):
            raise ValidationError(
                "capacity_request.request_status must be a string."
            )

        if not isinstance(demand_status, str):
            raise ValidationError(
                "capacity_request.demand_status must be a string."
            )

        confirmation_status = _confirmation_status(request)
        confirmation = request["confirmation"]

        released = confirmation.get("commitment_released")
        if not isinstance(released, bool):
            raise ValidationError(
                "commitment_released must be a boolean."
            )

        raw_promises = request.get("promises")
        if not isinstance(raw_promises, (list, tuple)):
            raise ValidationError(
                "capacity_request.promises must be an array."
            )

        promises = []

        for raw_promise in raw_promises:
            promise = _mapping(raw_promise, "capacity_request.promise")

            promises.append(
                PromiseCommitment(
                    supplier_item_id=_required_int(
                        promise,
                        "supplier_item_id",
                        "capacity_request.promise",
                    ),
                    item_id=_required_int(
                        promise,
                        "item_id",
                        "capacity_request.promise",
                    ),
                    demand_item_id=_required_int(
                        promise,
                        "demand_item_id",
                        "capacity_request.promise",
                    ),
                    confirmed_weight_kg=_decimal_value(
                        promise.get("confirmed_weight_kg"),
                        "promise.confirmed_weight_kg",
                    ),
                    line_status=promise.get("line_status"),
                    links_valid=_promise_links_valid(
                        request,
                        promise,
                    ),
                )
            )

        result.append(
            SupplierRequestCommitment(
                request_id=request_id,
                demand_id=demand_id,
                supplier_id=supplier_id,
                attempt_no=attempt_no,
                requested_date=requested_date,
                request_status=request_status,
                confirmation_status=confirmation_status,
                commitment_released=released,
                promises=tuple(promises),
                demand_status=demand_status,
            )
        )

    return tuple(result)


def _latest_request_by_demand(request_snapshots):
    """Select the latest attempt globally, before filtering by Supplier."""
    latest = {}

    for request in request_snapshots:
        demand_id = _required_int(
            request, "demand_id", "capacity_request"
        )
        attempt_no = _required_int(
            request, "attempt_no", "capacity_request"
        )
        request_id = _required_int(
            request, "id", "capacity_request"
        )

        current = latest.get(demand_id)

        if current is None or (
            attempt_no,
            request_id,
        ) > (
            current["attempt_no"],
            current["id"],
        ):
            latest[demand_id] = request

    return latest


def _build_confirmation_result(demand, latest_request):
    if latest_request is None:
        return ConfirmationGateResult(
            status=ConfirmationGateStatus.NOT_RESPONDED,
            failure=None,
            diagnostic_codes=(),
            confirmed_weight_by_demand_item=(),
            detail="No SupplierRequest exists for this Demand.",
        )

    demand_id = demand.demand_id
    values = demand.demand_values
    supplier_id = values["supplier_id"]

    request_id = _required_int(
        latest_request, "id", "latest_request"
    )
    request_demand_id = _required_int(
        latest_request, "demand_id", "latest_request"
    )
    request_supplier_id = _required_int(
        latest_request, "supplier_id", "latest_request"
    )

    confirmation = _mapping(
        latest_request.get("confirmation"),
        "latest_request.confirmation",
    )

    if (
        request_demand_id != demand_id
        or request_supplier_id != supplier_id
        or confirmation.get("demand_id") != request_demand_id
        or confirmation.get("supplier_id") != request_supplier_id
    ):
        return ConfirmationGateResult(
            status=ConfirmationGateStatus.INVALID_INPUT,
            failure=None,
            diagnostic_codes=("INVALID_CONFIRMATION_LINK",),
            confirmed_weight_by_demand_item=(),
            detail=(
                "SupplierConfirmation does not match its request "
                "Demand/Supplier."
            ),
        )

    demand_items = []
    for raw_item in demand.related_records["demand_items"]:
        item = _mapping(raw_item, "demand_item")

        demand_items.append(
            DemandItemRequirement(
                demand_item_id=_required_int(
                    item, "id", "demand_item"
                ),
                demand_id=demand_id,
                item_id=_required_int(
                    item, "item_id", "demand_item"
                ),
                required_weight_kg=_decimal_value(
                    item.get("required_weight_kg"),
                    "demand_item.required_weight_kg",
                ),
            )
        )

    raw_promises = latest_request.get("promises")
    if not isinstance(raw_promises, (list, tuple)):
        raise ValidationError(
            "latest_request.promises must be an array."
        )

    promises = []

    for raw_promise in raw_promises:
        promise = _mapping(raw_promise, "latest_request.promise")

        promises.append(
            PromiseLine(
                promise_id=_required_int(
                    promise, "id", "latest_request.promise"
                ),
                supplier_request_id=request_id,
                demand_id=request_demand_id,
                supplier_id=request_supplier_id,
                demand_item_id=_required_int(
                    promise,
                    "demand_item_id",
                    "latest_request.promise",
                ),
                item_id=_required_int(
                    promise, "item_id", "latest_request.promise"
                ),
                promised_weight_kg=_decimal_value(
                    promise.get("promised_weight_kg"),
                    "promise.promised_weight_kg",
                ),
                confirmed_weight_kg=_decimal_value(
                    promise.get("confirmed_weight_kg"),
                    "promise.confirmed_weight_kg",
                ),
                line_status=promise.get("line_status"),
                links_valid=_promise_links_valid(
                    latest_request,
                    promise,
                ),
            )
        )

    response = SupplierResponseSnapshot(
        supplier_request_id=request_id,
        demand_id=demand_id,
        demand_supplier_id=supplier_id,
        request_supplier_id=request_supplier_id,
        request_status=latest_request.get("request_status"),
        confirmation_status=confirmation.get(
            "confirmation_status"
        ),
        demand_items=tuple(demand_items),
        promises=tuple(promises),
    )

    return evaluate_supplier_confirmation(response)


def _build_demand_items(demand):
    result = []

    for raw_item in demand.related_records["demand_items"]:
        item = _mapping(raw_item, "demand_item")

        result.append(
            (
                item,
                _mapping(item.get("item"), "demand_item.item"),
            )
        )

    return tuple(result)


def _demand_data_is_valid(demand, demand_items):
    values = demand.demand_values

    if demand.demand_id <= 0:
        return False

    quantity = _decimal_value(
        values.get("quantity_kg"),
        "demand.quantity_kg",
        allow_none=True,
    )

    if quantity is None or quantity <= ZERO:
        return False

    requested_date = _date_value(
        values.get("requested_date"),
        "demand.requested_date",
        allow_none=True,
    )

    if requested_date is None or not demand_items:
        return False

    seen_item_ids = set()
    total_required_weight = ZERO
    cargo_category_id = values.get("cargo_category_id")

    for raw_item, item in demand_items:
        demand_item_id = raw_item.get("id")
        item_id = raw_item.get("item_id")
        required_weight = _decimal_value(
            raw_item.get("required_weight_kg"),
            "demand_item.required_weight_kg",
            allow_none=True,
        )

        if (
            not isinstance(demand_item_id, int)
            or isinstance(demand_item_id, bool)
            or demand_item_id <= 0
            or not isinstance(item_id, int)
            or isinstance(item_id, bool)
            or item_id <= 0
            or required_weight is None
            or required_weight <= ZERO
            or item_id in seen_item_ids
            or not item.get("is_active")
            or item.get("cargo_category_id") != cargo_category_id
            or raw_item.get("unit_of_measure") != item.get("weight_unit")
        ):
            return False

        seen_item_ids.add(item_id)
        total_required_weight += required_weight

    return total_required_weight == quantity


def _build_eligibility(demand, capacity_requests, confirmation):
    values = demand.demand_values
    demand_items = _build_demand_items(demand)
    item_ids = {item.get("item_id") for item, _ in demand_items}

    supplier_id = values["supplier_id"]
    requested_date = _date_value(
        values.get("requested_date"),
        "demand.requested_date",
        allow_none=True,
    )

    eligibility_items = tuple(
        EligibilityDemandItem(
            demand_item_id=item["id"],
            item_id=item["item_id"],
        )
        for item, _ in demand_items
    )

    offers = []
    offer_by_item = {}

    for raw_offer in demand.related_records["supplier_items"]:
        offer = _mapping(raw_offer, "supplier_item")

        if (
            offer.get("supplier_id") == supplier_id
            and offer.get("item_id") in item_ids
        ):
            item_id = offer["item_id"]
            offers.append(
                (
                    item_id,
                    offer.get("offer_status") == "ACTIVE",
                )
            )
            offer_by_item.setdefault(item_id, offer)

    capacities = []

    for item_id in sorted(
        value for value in item_ids
        if isinstance(value, int) and not isinstance(value, bool)
    ):
        offer = offer_by_item.get(item_id)

        if offer is None:
            continue

        capacities.append(
            evaluate_supplier_item_capacity(
                supplier_item=SupplierItemCapacity(
                    supplier_item_id=_required_int(
                        offer, "id", "supplier_item"
                    ),
                    supplier_id=_required_int(
                        offer, "supplier_id", "supplier_item"
                    ),
                    item_id=_required_int(
                        offer, "item_id", "supplier_item"
                    ),
                    max_daily_supply_kg=_decimal_value(
                        offer.get("max_daily_supply_kg"),
                        "supplier_item.max_daily_supply_kg",
                        allow_none=True,
                    ),
                ),
                delivery_date=requested_date,
                requests=capacity_requests,
            )
        )

    eligibility_input = DemandEligibilityInput(
        demand_id=demand.demand_id,
        supplier_id=supplier_id,
        requested_date=requested_date,
        demand_status=values.get("status"),
        demand_data_valid=_demand_data_is_valid(
            demand,
            demand_items,
        ),
        supplier_active=values.get("supplier_active") is True,
        cargo_category_active=(
            values.get("cargo_category_active") is True
        ),
        demand_items=eligibility_items,
        supplier_item_offers=tuple(offers),
        confirmation=confirmation,
        capacities=tuple(capacities),
    )

    return evaluate_demand_eligibility(eligibility_input)


def evaluate_f1_snapshots(
    snapshots,
    *,
    cargo_compatibility_rows,
):
    """Evaluate a PlanningRun's immutable Demand snapshots.

    Args:
        snapshots: Iterable of raw demand_snapshot JSON objects.

    Returns:
        F1Evaluation containing per-Demand eligibility and Candidate Groups.

    Raises:
        ValidationError: If snapshots or required source values are invalid.
    """
    try:
        cargo_compatibility_matrix = (
            normalize_cargo_compatibility_matrix(
                cargo_compatibility_rows
            )
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    run_data = read_run_snapshots(snapshots)

    capacity_requests = _build_capacity_requests(
        run_data.capacity_requests
    )
    latest_requests = _latest_request_by_demand(
        run_data.capacity_requests
    )

    evaluations = []
    candidate_inputs = []

    for demand in run_data.demands:
        latest_request = latest_requests.get(demand.demand_id)

        confirmation = _build_confirmation_result(
            demand,
            latest_request,
        )

        eligibility = _build_eligibility(
            demand,
            capacity_requests,
            confirmation,
        )

        values = demand.demand_values

        candidate_input = CandidateDemandInput(
            outlet_id=values["outlet_id"],
            demand_id=demand.demand_id,
            eligibility_status=eligibility.eligibility_status,
            requested_date=_date_value(
                values.get("requested_date"),
                "demand.requested_date",
                allow_none=True,
            ),
            cargo_category_id=values["cargo_category_id"],
            requested_start_time=_time_value(
                values.get("requested_start_time"),
                "demand.requested_start_time",
            ),
            requested_end_time=_time_value(
                values.get("requested_end_time"),
                "demand.requested_end_time",
            ),
        )

        evaluations.append(
            F1DemandEvaluation(
                demand_id=demand.demand_id,
                eligibility=eligibility,
                candidate_input=candidate_input,
            )
        )
        candidate_inputs.append(candidate_input)

    candidate_groups = generate_candidate_groups(
        tuple(candidate_inputs),
        cargo_compatibility_matrix=cargo_compatibility_matrix,
    )

    return F1Evaluation(
        demand_evaluations=tuple(evaluations),
        candidate_groups=tuple(candidate_groups),
    )