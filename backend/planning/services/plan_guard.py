
"""Fail-closed adapter contract for the external Fulfillment Plan module."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

PASS = "PASS"
FAIL = "FAIL"
NOT_EVALUATED = "NOT_EVALUATED"

SOURCE_UNAVAILABLE = "PLAN_GUARD_SOURCE_UNAVAILABLE"
SOURCE_ERROR = "PLAN_GUARD_SOURCE_ERROR"
SOURCE_RESULT_INVALID = "PLAN_GUARD_SOURCE_RESULT_INVALID"
SOURCE_RESULT_MISSING = "PLAN_GUARD_SOURCE_RESULT_MISSING"


@dataclass(frozen=True)
class PlanGuardEvidence:
    """Evidence returned by the authoritative Fulfillment Plan source."""

    query_complete: bool
    has_finalized_plan: bool | None
    finalized_plan_ids: tuple[int, ...] = ()


class PlanGuardSource(Protocol):
    """Contract implemented by the module owning Fulfillment Plans."""

    source_name: str

    def capture(
        self,
        *,
        demand_ids: tuple[int, ...],
        captured_at: str,
    ) -> Mapping[int, PlanGuardEvidence]:
        """Return authoritative Plan evidence for every requested Demand."""
        ...


class UnavailablePlanGuardSource:
    """Default adapter until the authoritative module is integrated."""

    source_name = "UNAVAILABLE"

    def capture(
        self,
        *,
        demand_ids: tuple[int, ...],
        captured_at: str,
    ) -> Mapping[int, PlanGuardEvidence]:
        return {
            demand_id: PlanGuardEvidence(
                query_complete=False,
                has_finalized_plan=None,
            )
            for demand_id in demand_ids
        }


def _unknown_snapshot(
    *,
    demand_id: int,
    captured_at: str,
    source: str,
    reason_code: str,
) -> dict:
    return {
        "schema_version": "1.0",
        "demand_id": demand_id,
        "captured_at": captured_at,
        "source": source,
        "query_complete": False,
        "has_finalized_plan": None,
        "finalized_plan_ids": [],
        "status": NOT_EVALUATED,
        "reason_code": reason_code,
    }


def _positive_ids(value) -> tuple[int, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("Plan IDs must be an array.")

    if any(
        not isinstance(item, int)
        or isinstance(item, bool)
        or item <= 0
        for item in value
    ):
        raise ValueError("Plan IDs must be positive integers.")

    if len(value) != len(set(value)):
        raise ValueError("Duplicate Plan IDs are not allowed.")

    return tuple(sorted(value))


def _serialize_evidence(
    *,
    demand_id: int,
    evidence: PlanGuardEvidence,
    captured_at: str,
    source: str,
) -> dict:
    if not isinstance(evidence, PlanGuardEvidence):
        raise ValueError("Unexpected Plan Guard evidence type.")

    if not isinstance(evidence.query_complete, bool):
        raise ValueError("query_complete must be boolean.")

    if evidence.has_finalized_plan not in (True, False, None):
        raise ValueError("has_finalized_plan must be boolean or None.")

    plan_ids = _positive_ids(evidence.finalized_plan_ids)

    # Positive evidence is sufficient to block, even if the query
    # was not complete.
    if evidence.has_finalized_plan is True or plan_ids:
        if evidence.has_finalized_plan is False:
            raise ValueError("Conflicting finalized Plan evidence.")

        return {
            "schema_version": "1.0",
            "demand_id": demand_id,
            "captured_at": captured_at,
            "source": source,
            "query_complete": evidence.query_complete,
            "has_finalized_plan": True,
            "finalized_plan_ids": list(plan_ids),
            "status": FAIL,
            "reason_code": "DEMAND_IN_FINALIZED_PLAN",
        }

    # PASS requires an explicit negative result from a complete query.
    if (
        evidence.query_complete is True
        and evidence.has_finalized_plan is False
    ):
        return {
            "schema_version": "1.0",
            "demand_id": demand_id,
            "captured_at": captured_at,
            "source": source,
            "query_complete": True,
            "has_finalized_plan": False,
            "finalized_plan_ids": [],
            "status": PASS,
            "reason_code": None,
        }

    return _unknown_snapshot(
        demand_id=demand_id,
        captured_at=captured_at,
        source=source,
        reason_code="PLAN_GUARD_QUERY_INCOMPLETE",
    )


def build_plan_guard_snapshots(
    *,
    source: PlanGuardSource | None,
    demand_ids,
    captured_at: str,
) -> dict[int, dict]:
    """Capture immutable JSON-safe Plan Guard evidence per Demand.

    Any unavailable, incomplete, missing, or invalid source result
    remains NOT_EVALUATED. This function never infers PASS from absence.
    """
    if not isinstance(demand_ids, (tuple, list)) or not demand_ids:
        raise ValueError("Demand IDs must be a non-empty array.")

    if any(
        not isinstance(item, int)
        or isinstance(item, bool)
        or item <= 0
        for item in demand_ids
    ):
        raise ValueError("Demand IDs must be positive integers.")

    if len(demand_ids) != len(set(demand_ids)):
        raise ValueError("Duplicate Demand IDs are not allowed.")

    normalized_ids = tuple(sorted(demand_ids))

    if not isinstance(captured_at, str) or not captured_at:
        raise ValueError("captured_at is required.")

    if source is None:
        source = UnavailablePlanGuardSource()

    source_name = getattr(source, "source_name", None)
    if not isinstance(source_name, str) or not source_name.strip():
        source_name = "UNKNOWN"

    try:
        results = source.capture(
            demand_ids=normalized_ids,
            captured_at=captured_at,
        )
    except Exception:
        return {
            demand_id: _unknown_snapshot(
                demand_id=demand_id,
                captured_at=captured_at,
                source=source_name,
                reason_code=SOURCE_ERROR,
            )
            for demand_id in normalized_ids
        }

    if not isinstance(results, Mapping):
        return {
            demand_id: _unknown_snapshot(
                demand_id=demand_id,
                captured_at=captured_at,
                source=source_name,
                reason_code=SOURCE_RESULT_INVALID,
            )
            for demand_id in normalized_ids
        }

    snapshots = {}

    for demand_id in normalized_ids:
        if demand_id not in results:
            snapshots[demand_id] = _unknown_snapshot(
                demand_id=demand_id,
                captured_at=captured_at,
                source=source_name,
                reason_code=SOURCE_RESULT_MISSING,
            )
            continue

        try:
            snapshots[demand_id] = _serialize_evidence(
                demand_id=demand_id,
                evidence=results[demand_id],
                captured_at=captured_at,
                source=source_name,
            )
        except (TypeError, ValueError):
            snapshots[demand_id] = _unknown_snapshot(
                demand_id=demand_id,
                captured_at=captured_at,
                source=source_name,
                reason_code=SOURCE_RESULT_INVALID,
            )

    return snapshots


@dataclass(frozen=True)
class PlanGuardEvaluation:
    demand_id: int
    status: str
    reason_code: str | None
    finalized_plan_ids: tuple[int, ...]


def evaluate_plan_guard_snapshot(
    snapshot,
    *,
    expected_demand_id: int,
    expected_captured_at: str,
) -> PlanGuardEvaluation:
    """Evaluate stored evidence without trusting its stored status."""
    def unknown(reason):
        return PlanGuardEvaluation(
            demand_id=expected_demand_id,
            status=NOT_EVALUATED,
            reason_code=reason,
            finalized_plan_ids=(),
        )

    if not isinstance(snapshot, Mapping):
        return unknown(SOURCE_RESULT_INVALID)

    if snapshot.get("schema_version") != "1.0":
        return unknown(SOURCE_RESULT_INVALID)

    if snapshot.get("demand_id") != expected_demand_id:
        return unknown(SOURCE_RESULT_INVALID)

    if snapshot.get("captured_at") != expected_captured_at:
        return unknown(SOURCE_RESULT_INVALID)

    source = snapshot.get("source")
    if not isinstance(source, str) or not source.strip():
        return unknown(SOURCE_RESULT_INVALID)

    query_complete = snapshot.get("query_complete")
    has_finalized_plan = snapshot.get("has_finalized_plan")

    if not isinstance(query_complete, bool):
        return unknown(SOURCE_RESULT_INVALID)

    if has_finalized_plan not in (True, False, None):
        return unknown(SOURCE_RESULT_INVALID)

    try:
        plan_ids = _positive_ids(snapshot.get("finalized_plan_ids"))
    except (TypeError, ValueError):
        return unknown(SOURCE_RESULT_INVALID)

    if has_finalized_plan is False and plan_ids:
        return unknown(SOURCE_RESULT_INVALID)

    if has_finalized_plan is True or plan_ids:
        return PlanGuardEvaluation(
            demand_id=expected_demand_id,
            status=FAIL,
            reason_code="DEMAND_IN_FINALIZED_PLAN",
            finalized_plan_ids=plan_ids,
        )

    if query_complete and has_finalized_plan is False:
        return PlanGuardEvaluation(
            demand_id=expected_demand_id,
            status=PASS,
            reason_code=None,
            finalized_plan_ids=(),
        )

    return unknown("PLAN_GUARD_QUERY_INCOMPLETE")


def evaluate_plan_guard_snapshots(snapshots):
    """Return one fail-closed Plan Guard evaluation per Demand snapshot."""
    evaluations = {}

    for demand_snapshot in snapshots:
        if not isinstance(demand_snapshot, Mapping):
            continue

        demand_ref = demand_snapshot.get("demand_ref")
        if not isinstance(demand_ref, Mapping):
            continue

        demand_id = demand_ref.get("demand_id")
        captured_at = demand_snapshot.get("captured_at")

        if (
            not isinstance(demand_id, int)
            or isinstance(demand_id, bool)
            or demand_id <= 0
        ):
            continue

        if not isinstance(captured_at, str) or not captured_at:
            evaluations[demand_id] = PlanGuardEvaluation(
                demand_id=demand_id,
                status=NOT_EVALUATED,
                reason_code=SOURCE_RESULT_INVALID,
                finalized_plan_ids=(),
            )
            continue

        related = demand_snapshot.get("related_records")
        plan_guard = (
            related.get("plan_guard")
            if isinstance(related, Mapping)
            else None
        )

        evaluations[demand_id] = evaluate_plan_guard_snapshot(
            plan_guard,
            expected_demand_id=demand_id,
            expected_captured_at=captured_at,
        )

    return evaluations
