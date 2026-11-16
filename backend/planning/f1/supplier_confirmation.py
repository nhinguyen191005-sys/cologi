
"""Pure F1 Supplier Confirmation Gate.

No Django imports, database access, network access or mutations.
The caller supplies the latest SupplierRequest and its related records.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable


ZERO = Decimal("0")


class ConfirmationGateStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"
    INVALID_INPUT = "INVALID_INPUT"
    NOT_RESPONDED = "NOT_RESPONDED"


class ConfirmationFailure(str, Enum):
    PROMISE_MISSING = "PROMISE_MISSING"
    PROMISE_INSUFFICIENT = "PROMISE_INSUFFICIENT"
    INVALID_PROMISE_LINK = "INVALID_PROMISE_LINK"
    DUPLICATE_PROMISE = "DUPLICATE_PROMISE"
    UNEXPECTED_PROMISE = "UNEXPECTED_PROMISE"
    NO_DEMAND_ITEMS = "NO_DEMAND_ITEMS"


@dataclass(frozen=True)
class DemandItemRequirement:
    demand_item_id: int
    demand_id: int
    item_id: int
    required_weight_kg: Decimal


@dataclass(frozen=True)
class PromiseLine:
    promise_id: int
    supplier_request_id: int
    demand_id: int
    supplier_id: int
    demand_item_id: int
    item_id: int
    promised_weight_kg: Decimal
    confirmed_weight_kg: Decimal
    line_status: str
    links_valid: bool = True


@dataclass(frozen=True)
class SupplierResponseSnapshot:
    """The latest request attempt for one Demand.

    The adapter must select the latest request by (attempt_no, pk)
    before constructing this object. Historical attempts must not be merged.
    """

    supplier_request_id: int
    demand_id: int
    demand_supplier_id: int
    request_supplier_id: int
    request_status: str
    confirmation_status: str
    demand_items: tuple[DemandItemRequirement, ...]
    promises: tuple[PromiseLine, ...]


@dataclass(frozen=True)
class ConfirmationGateResult:
    status: ConfirmationGateStatus
    failure: ConfirmationFailure | None
    diagnostic_codes: tuple[str, ...]
    confirmed_weight_by_demand_item: tuple[tuple[int, Decimal], ...]
    detail: str


def _result(
    status: ConfirmationGateStatus,
    *,
    failure: ConfirmationFailure | None = None,
    diagnostics: tuple[str, ...] = (),
    confirmed: dict[int, Decimal] | None = None,
    detail: str,
) -> ConfirmationGateResult:
    confirmed = confirmed or {}
    return ConfirmationGateResult(
        status=status,
        failure=failure,
        diagnostic_codes=diagnostics,
        confirmed_weight_by_demand_item=tuple(sorted(confirmed.items())),
        detail=detail,
    )


def evaluate_supplier_confirmation(
    response: SupplierResponseSnapshot,
) -> ConfirmationGateResult:
    """Evaluate full Supplier confirmation for every DemandItem.

    PARTIAL confirmation exception:
    confirmation_status=PARTIAL may still pass if every DemandItem has
    exactly one valid Promise, each line is CONFIRMED, confirmed quantity
    equals promised quantity, and promised quantity covers the requirement.

    commitment_released_at is intentionally not an input here.
    Release affects Capacity Gate only, not Promise completeness.
    """
    if (
        response.supplier_request_id <= 0
        or response.demand_id <= 0
        or response.demand_supplier_id <= 0
        or response.request_supplier_id <= 0
    ):
        return _result(
            ConfirmationGateStatus.INVALID_INPUT,
            failure=ConfirmationFailure.INVALID_PROMISE_LINK,
            detail="Request, Demand or Supplier identifiers are invalid.",
        )

    if response.demand_supplier_id != response.request_supplier_id:
        return _result(
            ConfirmationGateStatus.INVALID_INPUT,
            failure=ConfirmationFailure.INVALID_PROMISE_LINK,
            detail="SupplierRequest Supplier does not match Demand Supplier.",
        )

    if response.request_status != "RESPONDED":
        return _result(
            ConfirmationGateStatus.NOT_RESPONDED,
            detail="Only the latest RESPONDED SupplierRequest can be evaluated.",
        )

    if response.confirmation_status not in {"CONFIRMED", "PARTIAL"}:
        return _result(
            ConfirmationGateStatus.EXCLUDED,
            detail=(
                "Supplier Confirmation is neither CONFIRMED nor eligible "
                "for the approved PARTIAL exception."
            ),
        )

    if not response.demand_items:
        return _result(
            ConfirmationGateStatus.INVALID_INPUT,
            failure=ConfirmationFailure.NO_DEMAND_ITEMS,
            detail="Demand has no DemandItem records.",
        )

    requirements: dict[int, DemandItemRequirement] = {}

    for item in response.demand_items:
        if (
            item.demand_item_id <= 0
            or item.demand_id != response.demand_id
            or item.item_id <= 0
            or item.required_weight_kg <= ZERO
        ):
            return _result(
                ConfirmationGateStatus.INVALID_INPUT,
                failure=ConfirmationFailure.INVALID_PROMISE_LINK,
                detail="DemandItem identity or required quantity is invalid.",
            )

        if item.demand_item_id in requirements:
            return _result(
                ConfirmationGateStatus.INVALID_INPUT,
                failure=ConfirmationFailure.DUPLICATE_PROMISE,
                detail="Duplicate DemandItem in the supplied Demand scope.",
            )

        requirements[item.demand_item_id] = item

    promises_by_item: dict[int, list[PromiseLine]] = {}

    for promise in response.promises:
        if (
            promise.supplier_request_id != response.supplier_request_id
            or promise.demand_id != response.demand_id
            or promise.supplier_id != response.request_supplier_id
            or not promise.links_valid
        ):
            return _result(
                ConfirmationGateStatus.INVALID_INPUT,
                failure=ConfirmationFailure.INVALID_PROMISE_LINK,
                detail="Promise has an invalid request, Demand or Supplier link.",
            )

        if promise.demand_item_id not in requirements:
            return _result(
                ConfirmationGateStatus.INVALID_INPUT,
                failure=ConfirmationFailure.UNEXPECTED_PROMISE,
                detail="Promise references a DemandItem outside this Demand.",
            )

        requirement = requirements[promise.demand_item_id]

        if promise.item_id != requirement.item_id:
            return _result(
                ConfirmationGateStatus.INVALID_INPUT,
                failure=ConfirmationFailure.INVALID_PROMISE_LINK,
                detail="Promise Item does not match its DemandItem Item.",
            )

        if (
            promise.promised_weight_kg <= ZERO
            or promise.confirmed_weight_kg < ZERO
            or promise.confirmed_weight_kg > promise.promised_weight_kg
        ):
            return _result(
                ConfirmationGateStatus.INVALID_INPUT,
                failure=ConfirmationFailure.INVALID_PROMISE_LINK,
                detail="Promise quantities violate the expected bounds.",
            )

        promises_by_item.setdefault(
            promise.demand_item_id, []
        ).append(promise)

    confirmed: dict[int, Decimal] = {}

    for demand_item_id, requirement in requirements.items():
        matching = promises_by_item.get(demand_item_id, [])

        if not matching:
            return _result(
                ConfirmationGateStatus.EXCLUDED,
                failure=ConfirmationFailure.PROMISE_MISSING,
                confirmed=confirmed,
                detail=(
                    f"DemandItem {demand_item_id} has no SupplierItemPromise."
                ),
            )

        if len(matching) != 1:
            return _result(
                ConfirmationGateStatus.INVALID_INPUT,
                failure=ConfirmationFailure.DUPLICATE_PROMISE,
                confirmed=confirmed,
                detail=(
                    f"DemandItem {demand_item_id} has multiple Promise records."
                ),
            )

        promise = matching[0]

        if (
            promise.line_status != "CONFIRMED"
            or promise.confirmed_weight_kg != promise.promised_weight_kg
            or promise.confirmed_weight_kg < requirement.required_weight_kg
        ):
            return _result(
                ConfirmationGateStatus.EXCLUDED,
                failure=ConfirmationFailure.PROMISE_INSUFFICIENT,
                confirmed=confirmed,
                detail=(
                    f"DemandItem {demand_item_id} does not have one fully "
                    "confirmed Promise covering its required quantity."
                ),
            )

        confirmed[demand_item_id] = promise.confirmed_weight_kg

    diagnostics = ()
    if response.confirmation_status == "PARTIAL":
        diagnostics = ("CONFIRMATION_STATUS_INCONSISTENT",)

    return _result(
        ConfirmationGateStatus.ELIGIBLE,
        diagnostics=diagnostics,
        confirmed=confirmed,
        detail=(
            "Every DemandItem has exactly one valid, fully confirmed "
            "Promise covering its required quantity."
        ),
    )
