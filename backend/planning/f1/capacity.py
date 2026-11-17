
"""Pure F1 supplier-capacity evaluation.

This module deliberately has no Django imports and performs no I/O.
Capacity is aggregated by Supplier + Item + Demand requested date.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Iterable


ZERO = Decimal("0")


class CapacityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    EXCEEDED = "EXCEEDED"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class PromiseCommitment:
    supplier_item_id: int
    item_id: int
    demand_item_id: int
    confirmed_weight_kg: Decimal
    line_status: str
    links_valid: bool = True


@dataclass(frozen=True)
class SupplierRequestCommitment:
    """A single SupplierRequest attempt and its captured commitment lines."""

    request_id: int
    demand_id: int
    supplier_id: int
    attempt_no: int
    requested_date: date
    request_status: str
    confirmation_status: str
    commitment_released: bool
    promises: tuple[PromiseCommitment, ...]
    demand_status: str = "SUBMITTED"


@dataclass(frozen=True)
class SupplierItemCapacity:
    supplier_item_id: int
    supplier_id: int
    item_id: int
    max_daily_supply_kg: Decimal | None


@dataclass(frozen=True)
class CapacityResult:
    status: CapacityStatus
    supplier_id: int
    supplier_item_id: int
    item_id: int
    delivery_date: date
    committed_weight_kg: Decimal
    max_daily_supply_kg: Decimal | None
    contributing_demand_ids: tuple[int, ...]
    detail: str


def _latest_request_per_demand(
    requests: Iterable[SupplierRequestCommitment],
) -> dict[int, SupplierRequestCommitment]:
    """Keep only the latest attempt for each Demand.

    A later attempt replaces an earlier attempt even when its Supplier differs.
    This prevents historical SupplierRequest attempts from being double-counted.
    """
    latest: dict[int, SupplierRequestCommitment] = {}

    for request in requests:
        current = latest.get(request.demand_id)

        if current is None or (
            request.attempt_no,
            request.request_id,
        ) > (
            current.attempt_no,
            current.request_id,
        ):
            latest[request.demand_id] = request

    return latest



def _is_effective_commitment(
    request: SupplierRequestCommitment,
) -> bool:
    """Whether the latest request still consumes Supplier capacity."""

    if request.request_status != "RESPONDED":
        return False

    # Released commitments no longer consume capacity,
    # regardless of CONFIRMED or PARTIAL status.
    if request.commitment_released:
        return False

    # Demand cancellation does not itself release a commitment.
    return request.confirmation_status in {"CONFIRMED", "PARTIAL"}



def evaluate_supplier_item_capacity(
    *,
    supplier_item: SupplierItemCapacity,
    delivery_date: date,
    requests: Iterable[SupplierRequestCommitment],
) -> CapacityResult:
    """Evaluate total effective commitments for one Supplier–Item–date.

    The caller must pass the latest source values captured for the run.
    This function does not query or mutate any model/database.
    """
    if (
        supplier_item.supplier_item_id <= 0
        or supplier_item.supplier_id <= 0
        or supplier_item.item_id <= 0
    ):
        return CapacityResult(
            status=CapacityStatus.INVALID_INPUT,
            supplier_id=supplier_item.supplier_id,
            supplier_item_id=supplier_item.supplier_item_id,
            item_id=supplier_item.item_id,
            delivery_date=delivery_date,
            committed_weight_kg=ZERO,
            max_daily_supply_kg=supplier_item.max_daily_supply_kg,
            contributing_demand_ids=(),
            detail="SupplierItem identifiers must be positive.",
        )

    if (
        supplier_item.max_daily_supply_kg is not None
        and supplier_item.max_daily_supply_kg < ZERO
    ):
        return CapacityResult(
            status=CapacityStatus.INVALID_INPUT,
            supplier_id=supplier_item.supplier_id,
            supplier_item_id=supplier_item.supplier_item_id,
            item_id=supplier_item.item_id,
            delivery_date=delivery_date,
            committed_weight_kg=ZERO,
            max_daily_supply_kg=supplier_item.max_daily_supply_kg,
            contributing_demand_ids=(),
            detail="Maximum daily supply cannot be negative.",
        )

    latest_requests = _latest_request_per_demand(requests)

    committed_total = ZERO
    contributing_demands: set[int] = set()

    for request in latest_requests.values():
        if request.supplier_id != supplier_item.supplier_id:
            continue

        if request.requested_date != delivery_date:
            continue

        if not _is_effective_commitment(request):
            continue

        seen_demand_item_ids: set[int] = set()

        for promise in request.promises:
            if promise.supplier_item_id != supplier_item.supplier_item_id:
                continue

            if not promise.links_valid:
                return CapacityResult(
                    status=CapacityStatus.INVALID_INPUT,
                    supplier_id=supplier_item.supplier_id,
                    supplier_item_id=supplier_item.supplier_item_id,
                    item_id=supplier_item.item_id,
                    delivery_date=delivery_date,
                    committed_weight_kg=committed_total,
                    max_daily_supply_kg=supplier_item.max_daily_supply_kg,
                    contributing_demand_ids=tuple(
                        sorted(contributing_demands)
                    ),
                    detail=(
                        "A commitment line has an invalid DemandItem, "
                        "SupplierItem or Supplier relationship."
                    ),
                )

            if promise.item_id != supplier_item.item_id:
                return CapacityResult(
                    status=CapacityStatus.INVALID_INPUT,
                    supplier_id=supplier_item.supplier_id,
                    supplier_item_id=supplier_item.supplier_item_id,
                    item_id=supplier_item.item_id,
                    delivery_date=delivery_date,
                    committed_weight_kg=committed_total,
                    max_daily_supply_kg=supplier_item.max_daily_supply_kg,
                    contributing_demand_ids=tuple(
                        sorted(contributing_demands)
                    ),
                    detail=(
                        "Promise Item does not match its SupplierItem Item."
                    ),
                )

            if promise.demand_item_id in seen_demand_item_ids:
                return CapacityResult(
                    status=CapacityStatus.INVALID_INPUT,
                    supplier_id=supplier_item.supplier_id,
                    supplier_item_id=supplier_item.supplier_item_id,
                    item_id=supplier_item.item_id,
                    delivery_date=delivery_date,
                    committed_weight_kg=committed_total,
                    max_daily_supply_kg=supplier_item.max_daily_supply_kg,
                    contributing_demand_ids=tuple(
                        sorted(contributing_demands)
                    ),
                    detail="Duplicate promise for one DemandItem.",
                )

            seen_demand_item_ids.add(promise.demand_item_id)

            quantity = promise.confirmed_weight_kg

            if quantity < ZERO:
                return CapacityResult(
                    status=CapacityStatus.INVALID_INPUT,
                    supplier_id=supplier_item.supplier_id,
                    supplier_item_id=supplier_item.supplier_item_id,
                    item_id=supplier_item.item_id,
                    delivery_date=delivery_date,
                    committed_weight_kg=committed_total,
                    max_daily_supply_kg=supplier_item.max_daily_supply_kg,
                    contributing_demand_ids=tuple(
                        sorted(contributing_demands)
                    ),
                    detail="Confirmed promise quantity cannot be negative.",
                )

            if quantity == ZERO:
                continue

            if promise.line_status not in {"CONFIRMED", "PARTIAL"}:
                return CapacityResult(
                    status=CapacityStatus.INVALID_INPUT,
                    supplier_id=supplier_item.supplier_id,
                    supplier_item_id=supplier_item.supplier_item_id,
                    item_id=supplier_item.item_id,
                    delivery_date=delivery_date,
                    committed_weight_kg=committed_total,
                    max_daily_supply_kg=supplier_item.max_daily_supply_kg,
                    contributing_demand_ids=tuple(
                        sorted(contributing_demands)
                    ),
                    detail=(
                        "A positive confirmed quantity has an incompatible "
                        "Promise line status."
                    ),
                )

            if (
                request.confirmation_status == "CONFIRMED"
                and promise.line_status != "CONFIRMED"
            ):
                return CapacityResult(
                    status=CapacityStatus.INVALID_INPUT,
                    supplier_id=supplier_item.supplier_id,
                    supplier_item_id=supplier_item.supplier_item_id,
                    item_id=supplier_item.item_id,
                    delivery_date=delivery_date,
                    committed_weight_kg=committed_total,
                    max_daily_supply_kg=supplier_item.max_daily_supply_kg,
                    contributing_demand_ids=tuple(
                        sorted(contributing_demands)
                    ),
                    detail=(
                        "CONFIRMED confirmation contains a non-CONFIRMED "
                        "positive Promise line."
                    ),
                )

            committed_total += quantity
            contributing_demands.add(request.demand_id)


    common = {
        "supplier_id": supplier_item.supplier_id,
        "supplier_item_id": supplier_item.supplier_item_id,
        "item_id": supplier_item.item_id,
        "delivery_date": delivery_date,
        "committed_weight_kg": committed_total,
        "max_daily_supply_kg": supplier_item.max_daily_supply_kg,
        "contributing_demand_ids": tuple(sorted(contributing_demands)),
    }

    if supplier_item.max_daily_supply_kg is None:
        return CapacityResult(
            status=CapacityStatus.UNVERIFIED,
            **common,
            detail=(
                "SupplierItem.max_daily_supply_kg is NULL; "
                "capacity cannot be verified."
            ),
        )

    if committed_total > supplier_item.max_daily_supply_kg:
        return CapacityResult(
            status=CapacityStatus.EXCEEDED,
            **common,
            detail=(
                "Effective commitments exceed SupplierItem daily capacity."
            ),
        )

    return CapacityResult(
        status=CapacityStatus.VERIFIED,
        **common,
        detail="Effective commitments are within SupplierItem daily capacity.",
    )
