"""Pure F1 Candidate Group generation.

Generates every valid combination of two or more eligible Demands.
No Django imports, database access, persistence, or I/O.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from itertools import combinations

from planning.f1.cargo_compatibility import (
    evaluate_cargo_categories_compatibility,
)
from planning.f1.eligibility import EligibilityStatus
from planning.f1.time_eligibility import (
    IntersectionStatus,
    find_common_demand_pickup_window,
)


@dataclass(frozen=True)
class CandidateDemandInput:
    """Minimal, ORM-independent input for Candidate Group generation."""

    demand_id: int
    outlet_id: int
    eligibility_status: EligibilityStatus | str
    requested_date: date | None
    cargo_category_id: int
    requested_start_time: time | None
    requested_end_time: time | None


@dataclass(frozen=True)
class CandidateGroup:
    """One potential group with a strict common Demand pickup window."""

    demand_ids: tuple[int, ...]
    requested_date: date
    cargo_category_ids: tuple[int, ...]
    common_start_time: time
    common_end_time: time


def generate_candidate_groups(
    demands: Iterable[CandidateDemandInput],
    *,
    cargo_compatibility_matrix: Mapping,
) -> tuple[CandidateGroup, ...]:
    """Generate all valid combinations using a frozen compatibility matrix.

    Rules:
    - Only ELIGIBLE Demands are considered.
    - Members must share requested_date.
    - Every distinct Cargo Category pair must be configured and compatible.
    - Every Candidate Group must contain at least two distinct Outlets.
    - Every member must have a valid Demand requested time window.
    - The whole group must have a strict common time intersection.
    - Every combination of size >= 2 is generated, including subgroups.
    - Demand membership is not exclusive across Candidate Groups.

    The matrix must already be normalized by
    normalize_cargo_compatibility_matrix(). Missing pairs fail closed.
    """
    if not isinstance(cargo_compatibility_matrix, Mapping) or not cargo_compatibility_matrix:
        raise ValueError("CARGO_COMPATIBILITY_MATRIX_MISSING")

    eligible_demands: list[CandidateDemandInput] = []
    seen_demand_ids: set[int] = set()

    for demand in demands:
        if (
            isinstance(demand.demand_id, bool)
            or not isinstance(demand.demand_id, int)
            or demand.demand_id <= 0
        ):
            raise ValueError("demand_id must be a positive integer")

        if demand.demand_id in seen_demand_ids:
            raise ValueError(f"duplicate demand_id: {demand.demand_id}")

        seen_demand_ids.add(demand.demand_id)

        if (
            isinstance(demand.outlet_id, bool)
            or not isinstance(demand.outlet_id, int)
            or demand.outlet_id <= 0
        ):
            raise ValueError("outlet_id must be a positive integer")

        if (
            isinstance(demand.cargo_category_id, bool)
            or not isinstance(demand.cargo_category_id, int)
            or demand.cargo_category_id <= 0
        ):
            raise ValueError("cargo_category_id must be a positive integer")

        if demand.eligibility_status != EligibilityStatus.ELIGIBLE:
            continue

        eligible_demands.append(demand)

    # A missing/invalid date cannot be used as a grouping key.
    partitions: dict[date, list[CandidateDemandInput]] = {}

    for demand in eligible_demands:
        requested_date = demand.requested_date

        if (
            not isinstance(requested_date, date)
            or isinstance(requested_date, datetime)
        ):
            continue

        partitions.setdefault(requested_date, []).append(demand)

    candidate_groups: list[CandidateGroup] = []

    for requested_date, members in sorted(partitions.items()):
        members.sort(key=lambda demand: demand.demand_id)

        # Retain every valid subgroup, not only maximal groups.
        for group_size in range(2, len(members) + 1):
            for combination in combinations(members, group_size):
                distinct_outlet_ids = {
                    demand.outlet_id for demand in combination
                }
                if len(distinct_outlet_ids) < 2:
                    continue

                category_ids = tuple(sorted({
                    demand.cargo_category_id for demand in combination
                }))

                compatibility = evaluate_cargo_categories_compatibility(
                    category_ids,
                    cargo_compatibility_matrix,
                )
                if not compatibility.is_compatible:
                    continue

                intersection = find_common_demand_pickup_window(
                    (
                        demand.requested_date,
                        demand.requested_start_time,
                        demand.requested_end_time,
                    )
                    for demand in combination
                )

                if intersection.status is not IntersectionStatus.COMPATIBLE:
                    continue

                if (
                    intersection.requested_date is None
                    or intersection.start_time is None
                    or intersection.end_time is None
                ):
                    raise RuntimeError(
                        "Compatible intersection is missing its window values"
                    )

                candidate_groups.append(
                    CandidateGroup(
                        demand_ids=tuple(
                            demand.demand_id for demand in combination
                        ),
                        requested_date=intersection.requested_date,
                        cargo_category_ids=category_ids,
                        common_start_time=intersection.start_time,
                        common_end_time=intersection.end_time,
                    )
                )

    return tuple(candidate_groups)