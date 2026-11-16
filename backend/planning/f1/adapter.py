
"""Translate Django ORM records into pure F1 DTOs."""

from datetime import date
from decimal import Decimal

from planning.f1.capacity import (
    PromiseCommitment,
    SupplierItemCapacity,
    SupplierRequestCommitment,
    evaluate_supplier_item_capacity,
)
from planning.f1.eligibility import (
    DemandEligibilityInput,
    EligibilityDemandItem,
)
from planning.f1.supplier_confirmation import (
    ConfirmationGateResult,
    ConfirmationGateStatus,
    DemandItemRequirement,
    PromiseLine,
    SupplierResponseSnapshot,
    evaluate_supplier_confirmation,
)


ZERO = Decimal("0")


def latest_request_by_demand(requests):
    """Select latest attempt globally per Demand, before Supplier filtering."""
    latest = {}
    for request in requests:
        current = latest.get(request.demand_id)
        if current is None or (
            request.attempt_no,
            request.pk,
        ) > (
            current.attempt_no,
            current.pk,
        ):
            latest[request.demand_id] = request
    return latest




def _promise_links_valid(request, promise):
    demand_item = promise.demand_item
    supplier_item = promise.supplier_item
    confirmation = request.supplier_confirmation

    return (
        promise.supplier_request_id == request.pk
        and request.demand_id == demand_item.demand_id
        and request.supplier_id == supplier_item.supplier_id
        and demand_item.item_id == supplier_item.item_id
        and confirmation.demand_id == request.demand_id
        and confirmation.supplier_id == request.supplier_id
    )


def _confirmation_links_valid(request, demand=None):
    confirmation = request.supplier_confirmation

    links_match = (
        confirmation.demand_id == request.demand_id
        and confirmation.supplier_id == request.supplier_id
    )

    if demand is not None:
        links_match = links_match and (
            request.demand_id == demand.pk
            and request.supplier_id == demand.supplier_id
        )

    return links_match



def _build_promise_line(request, promise):
    return PromiseLine(
        promise_id=promise.pk,
        supplier_request_id=request.pk,
        demand_id=request.demand_id,
        supplier_id=request.supplier_id,
        demand_item_id=promise.demand_item_id,
        item_id=promise.demand_item.item_id,
        promised_weight_kg=promise.promised_weight_kg,
        confirmed_weight_kg=promise.confirmed_weight_kg,
        line_status=promise.line_status,
        links_valid=_promise_links_valid(request, promise),
    )


def build_confirmation_result(demand, latest_request):
    """Evaluate only the latest attempt; never merge promises across attempts."""
    if latest_request is None:
        return ConfirmationGateResult(
            status=ConfirmationGateStatus.NOT_RESPONDED,
            failure=None,
            diagnostic_codes=(),
            confirmed_weight_by_demand_item=(),
            detail="No SupplierRequest exists for this Demand.",
        )

    confirmation = latest_request.supplier_confirmation
    promises = tuple(
        _build_promise_line(latest_request, promise)
        for promise in latest_request.item_promises.all()
    )

    # The pure gate validates request/Demand Supplier identity and Promise
    # links. A broken request-confirmation relationship is represented by
    # marking each Promise invalid; when no Promise exists, reject explicitly.
    links_valid = _confirmation_links_valid(
        latest_request,
        demand=demand,
    )

    if not links_valid:
        return ConfirmationGateResult(
            status=ConfirmationGateStatus.INVALID_INPUT,
            failure=None,
            diagnostic_codes=("INVALID_CONFIRMATION_LINK",),
            confirmed_weight_by_demand_item=(),
            detail="SupplierConfirmation does not match its request Demand/Supplier.",
        )

    snapshot = SupplierResponseSnapshot(
        supplier_request_id=latest_request.pk,
        demand_id=demand.pk,
        demand_supplier_id=demand.supplier_id,
        request_supplier_id=latest_request.supplier_id,
        request_status=latest_request.request_status,
        confirmation_status=confirmation.confirmation_status,
        demand_items=tuple(
            DemandItemRequirement(
                demand_item_id=item.pk,
                demand_id=item.demand_id,
                item_id=item.item_id,
                required_weight_kg=item.required_weight_kg,
            )
            for item in demand.items.all()
        ),
        promises=promises,
    )
    return evaluate_supplier_confirmation(snapshot)


def build_capacity_requests(requests):
    """Map all request attempts; pure capacity logic selects latest per Demand."""
    result = []

    for request in requests:
        confirmation = request.supplier_confirmation
        lines = tuple(
            PromiseCommitment(
                supplier_item_id=promise.supplier_item_id,
                item_id=promise.demand_item.item_id,
                demand_item_id=promise.demand_item_id,
                confirmed_weight_kg=promise.confirmed_weight_kg,
                line_status=promise.line_status,
                links_valid=_promise_links_valid(request, promise),
            )
            for promise in request.item_promises.all()
        )

        result.append(
            SupplierRequestCommitment(
                request_id=request.pk,
                demand_id=request.demand_id,
                supplier_id=request.supplier_id,
                attempt_no=request.attempt_no,
                requested_date=request.demand.requested_date,
                request_status=request.request_status,
                confirmation_status=confirmation.confirmation_status,
                commitment_released=(
                    confirmation.commitment_released_at is not None
                ),
                promises=lines,
                demand_status=request.demand.status,
            )
        )

    return tuple(result)


def demand_data_is_valid(demand):
    """Read-only validation of the Demand data needed by F1."""
    if demand.pk <= 0 or demand.quantity_kg is None or demand.quantity_kg <= ZERO:
        return False

    if demand.requested_date is None:
        return False

    items = tuple(demand.items.all())
    if not items:
        return False

    seen_items = set()
    for demand_item in items:
        item = demand_item.item

        if (
            demand_item.pk <= 0
            or demand_item.required_weight_kg is None
            or demand_item.required_weight_kg <= ZERO
            or demand_item.item_id in seen_items
            or not item.is_active
            or item.cargo_category_id != demand.cargo_category_id
            or demand_item.unit_of_measure != item.weight_unit
        ):
            return False

        seen_items.add(demand_item.item_id)

    return True


def build_eligibility_input(
    *,
    demand,
    supplier_items,
    confirmation_result,
    capacity_requests,
):
    items = tuple(demand.items.all())
    item_ids = {item.item_id for item in items}

    offers_by_item = {}
    for offer in supplier_items:
        if offer.supplier_id == demand.supplier_id and offer.item_id in item_ids:
            offers_by_item[offer.item_id] = (
                offer.offer_status == "ACTIVE"
            )

    demand_items = tuple(
        EligibilityDemandItem(
            demand_item_id=item.pk,
            item_id=item.item_id,
        )
        for item in items
    )

    capacities = []
    for item_id in sorted(item_ids):
        offer = next(
            (
                row for row in supplier_items
                if row.supplier_id == demand.supplier_id
                and row.item_id == item_id
            ),
            None,
        )
        if offer is None:
            continue

        capacity_input = SupplierItemCapacity(
            supplier_item_id=offer.pk,
            supplier_id=offer.supplier_id,
            item_id=offer.item_id,
            max_daily_supply_kg=offer.max_daily_supply_kg,
        )
        capacities.append(
            evaluate_supplier_item_capacity(
                supplier_item=capacity_input,
                delivery_date=demand.requested_date,
                requests=capacity_requests,
            )
        )

    return DemandEligibilityInput(
        demand_id=demand.pk,
        supplier_id=demand.supplier_id,
        requested_date=demand.requested_date,
        demand_status=demand.status,
        demand_data_valid=demand_data_is_valid(demand),
        supplier_active=demand.supplier.is_active,
        cargo_category_active=demand.cargo_category.is_active,
        demand_items=demand_items,
        supplier_item_offers=tuple(
            (item_id, offers_by_item.get(item_id, False))
            for item_id in sorted(item_ids)
        ),
        confirmation=confirmation_result,
        capacities=tuple(capacities),
    )
