
"""Pure F1 Demand eligibility orchestration.

Combines already evaluated pure gates. No Django imports or I/O.

Blocker values in this module are internal evaluation labels only.
They are NOT the approved persisted PlanningRunDemand reason-code catalogue.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum

from planning.f1.capacity import CapacityResult, CapacityStatus
from planning.f1.supplier_confirmation import (
    ConfirmationGateResult,
    ConfirmationGateStatus,
)


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"


class EvaluationStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"


class EligibilityBlocker(str, Enum):
    DEMAND_NOT_SUBMITTED = "DEMAND_NOT_SUBMITTED"
    DEMAND_DATA_INVALID = "DEMAND_DATA_INVALID"
    SUPPLIER_INACTIVE = "SUPPLIER_INACTIVE"
    CARGO_CATEGORY_INACTIVE = "CARGO_CATEGORY_INACTIVE"
    SUPPLIER_OFFER_INACTIVE = "SUPPLIER_OFFER_INACTIVE"
    SUPPLIER_CONFIRMATION_FAILED = "SUPPLIER_CONFIRMATION_FAILED"
    CAPACITY_RESULT_MISSING = "CAPACITY_RESULT_MISSING"
    CAPACITY_UNVERIFIED = "CAPACITY_UNVERIFIED"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    CAPACITY_INVALID = "CAPACITY_INVALID"
    INPUT_INCONSISTENT = "INPUT_INCONSISTENT"


@dataclass(frozen=True)
class EligibilityDemandItem:
    demand_item_id: int
    item_id: int


@dataclass(frozen=True)
class DemandEligibilityInput:
    demand_id: int
    supplier_id: int
    requested_date: date
    demand_status: str
    demand_data_valid: bool
    supplier_active: bool
    cargo_category_active: bool
    demand_items: tuple[EligibilityDemandItem, ...]
    # (item_id, is_active_offer)
    supplier_item_offers: tuple[tuple[int, bool], ...]
    confirmation: ConfirmationGateResult
    # One CapacityResult per required Item, for this Supplier and date.
    capacities: tuple[CapacityResult, ...]


@dataclass(frozen=True)
class DemandEligibilityResult:
    demand_id: int
    eligibility_status: EligibilityStatus
    blockers: tuple[EligibilityBlocker, ...]
    diagnostics: tuple[str, ...]
    plan_guard_status: EvaluationStatus
    matching_status: EvaluationStatus
    # Deliberately unset until the persisted reason-code catalogue is approved.
    primary_reason_code: None
    detail: str


def evaluate_demand_eligibility(
    source: DemandEligibilityInput,
) -> DemandEligibilityResult:
    """Combine F1 hard gates for one Demand."""

    blockers: list[EligibilityBlocker] = []
    diagnostics: list[str] = []

    def block(value: EligibilityBlocker) -> None:
        if value not in blockers:
            blockers.append(value)

    if source.demand_id <= 0 or source.supplier_id <= 0:
        block(EligibilityBlocker.INPUT_INCONSISTENT)

    if source.demand_status != "SUBMITTED":
        block(EligibilityBlocker.DEMAND_NOT_SUBMITTED)

    if not source.demand_data_valid:
        block(EligibilityBlocker.DEMAND_DATA_INVALID)

    if not source.supplier_active:
        block(EligibilityBlocker.SUPPLIER_INACTIVE)

    if not source.cargo_category_active:
        block(EligibilityBlocker.CARGO_CATEGORY_INACTIVE)

    if not source.demand_items:
        block(EligibilityBlocker.DEMAND_DATA_INVALID)

    item_ids: set[int] = set()
    demand_item_ids: set[int] = set()

    for item in source.demand_items:
        if (
            item.demand_item_id <= 0
            or item.item_id <= 0
            or item.item_id in item_ids
            or item.demand_item_id in demand_item_ids
        ):
            block(EligibilityBlocker.INPUT_INCONSISTENT)
        item_ids.add(item.item_id)
        demand_item_ids.add(item.demand_item_id)

    offer_map: dict[int, bool] = {}
    for item_id, is_active in source.supplier_item_offers:
        if item_id <= 0 or item_id in offer_map:
            block(EligibilityBlocker.INPUT_INCONSISTENT)
            continue
        offer_map[item_id] = is_active

    for item_id in item_ids:
        if item_id not in offer_map or not offer_map[item_id]:
            block(EligibilityBlocker.SUPPLIER_OFFER_INACTIVE)

    confirmation = source.confirmation

    if confirmation.status != ConfirmationGateStatus.ELIGIBLE:
        block(EligibilityBlocker.SUPPLIER_CONFIRMATION_FAILED)

    diagnostics.extend(confirmation.diagnostic_codes)

    capacity_by_item: dict[int, CapacityResult] = {}

    for capacity in source.capacities:
        if capacity.item_id in capacity_by_item:
            block(EligibilityBlocker.INPUT_INCONSISTENT)
            continue
        capacity_by_item[capacity.item_id] = capacity

    for item_id in item_ids:
        capacity = capacity_by_item.get(item_id)

        if capacity is None:
            block(EligibilityBlocker.CAPACITY_RESULT_MISSING)
            continue

        if (
            capacity.supplier_id != source.supplier_id
            or capacity.item_id != item_id
            or capacity.delivery_date != source.requested_date
        ):
            block(EligibilityBlocker.INPUT_INCONSISTENT)
            continue

        if capacity.status == CapacityStatus.UNVERIFIED:
            block(EligibilityBlocker.CAPACITY_UNVERIFIED)
        elif capacity.status == CapacityStatus.EXCEEDED:
            block(EligibilityBlocker.CAPACITY_EXCEEDED)
        elif capacity.status == CapacityStatus.INVALID_INPUT:
            block(EligibilityBlocker.CAPACITY_INVALID)
        elif capacity.status != CapacityStatus.VERIFIED:
            block(EligibilityBlocker.INPUT_INCONSISTENT)

    eligible = not blockers

    return DemandEligibilityResult(
        demand_id=source.demand_id,
        eligibility_status=(
            EligibilityStatus.ELIGIBLE
            if eligible
            else EligibilityStatus.EXCLUDED
        ),
        blockers=tuple(blockers),
        diagnostics=tuple(dict.fromkeys(diagnostics)),
        plan_guard_status=EvaluationStatus.NOT_EVALUATED,
        matching_status=EvaluationStatus.NOT_EVALUATED,
        primary_reason_code=None,
        detail=(
            "All F1 eligibility gates passed."
            if eligible
            else "One or more F1 eligibility gates did not pass."
        ),
    )
