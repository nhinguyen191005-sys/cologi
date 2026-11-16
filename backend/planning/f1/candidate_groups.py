
"""Pure F1 Candidate Group generation.

Generates every valid combination of two or more eligible Demands.
This module has no Django imports, database access, persistence, or I/O.

Candidate Groups are potential combinations, not accepted/final groups.
A Demand may appear in multiple Candidate Groups in the same Planning Run.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from itertools import combinations
from typing import Iterable

from planning.f1.eligibility import EligibilityStatus
from planning.f1.time_eligibility import (
    IntersectionStatus,
    find_common_demand_pickup_window,
)


@dataclass(frozen=True)
class CandidateDemandInput:
    """Minimal, ORM-independent input for Candidate Group generation."""

    demand_id: int
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
    cargo_category_id: int
    common_start_time: time
    common_end_time: time


def generate_candidate_groups(
    demands: Iterable[CandidateDemandInput],
) -> tuple[CandidateGroup, ...]:
    """Generate all valid Candidate Group combinations.

    Rules:
    - Only ELIGIBLE Demands are considered.
    - Members must share requested_date and cargo_category_id.
    - Every member must have a valid Demand requested time window.
    - The whole group must have a strict common time intersection.
    - Every combination of size >= 2 is generated.
    - Subgroups are retained when larger groups are also compatible.
    - Demand membership is not exclusive across Candidate Groups.

    Invalid identifiers and duplicate Demand IDs raise ValueError.
    Missing or invalid dates/windows make a Demand ungroupable; they do
    not change its independently evaluated Eligibility status.
    """
    eligible_demands: list[CandidateDemandInput] = []
    seen_demand_ids: set[int] = set()

    for demand in demands:
        if not isinstance(demand.demand_id, int) or demand.demand_id <= 0:
            raise ValueError("demand_id must be a positive integer")

        if demand.demand_id in seen_demand_ids:
            raise ValueError(f"duplicate demand_id: {demand.demand_id}")

        seen_demand_ids.add(demand.demand_id)

        if (
            not isinstance(demand.cargo_category_id, int)
            or demand.cargo_category_id <= 0
        ):
            raise ValueError("cargo_category_id must be a positive integer")

        if demand.eligibility_status != EligibilityStatus.ELIGIBLE:
            continue

        eligible_demands.append(demand)

    # Invalid or missing dates cannot be used as grouping keys.
    # Datetime is deliberately rejected even though it subclasses date.
    partitions: dict[
        tuple[date, int],
        list[CandidateDemandInput],
    ] = {}

    for demand in eligible_demands:
        requested_date = demand.requested_date

        if (
            not isinstance(requested_date, date)
            or isinstance(requested_date, datetime)
        ):
            continue

        key = (requested_date, demand.cargo_category_id)
        partitions.setdefault(key, []).append(demand)

    candidate_groups: list[CandidateGroup] = []

    # Sorting makes output deterministic regardless of input order.
    for (requested_date, cargo_category_id), members in sorted(
        partitions.items(),
        key=lambda entry: (entry[0][0], entry[0][1]),
    ):
        members.sort(key=lambda demand: demand.demand_id)

        # Generate every combination, not only maximal groups.
        for group_size in range(2, len(members) + 1):
            for combination in combinations(members, group_size):
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

                # COMPATIBLE guarantees these values are present.
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
                        cargo_category_id=cargo_category_id,
                        common_start_time=intersection.start_time,
                        common_end_time=intersection.end_time,
                    )
                )

    return tuple(candidate_groups)
