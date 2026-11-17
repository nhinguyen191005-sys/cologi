"""Read and validate immutable CP8 snapshots without ORM access."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from django.core.exceptions import ValidationError

from planning.json_validators import validate_demand_snapshot


REQUIRED_RELATED_KEYS = {
    "demand_items",
    "supplier_items",
    "capacity_requests",
    "supplier_confirmations",
}


@dataclass(frozen=True)
class SnapshotDemand:
    demand_id: int
    demand_code: str
    captured_at: str
    demand_values: Mapping
    related_records: Mapping


@dataclass(frozen=True)
class SnapshotRunData:
    demands: tuple[SnapshotDemand, ...]
    capacity_requests: tuple[Mapping, ...]


def _freeze(value):
    """Recursively prevent accidental mutation of snapshot data."""
    if isinstance(value, dict):
        return MappingProxyType({
            key: _freeze(item)
            for key, item in value.items()
        })

    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)

    return value


def read_demand_snapshot(snapshot):
    """Validate one stored snapshot and return immutable snapshot data."""
    if not isinstance(snapshot, dict):
        raise ValidationError("Snapshot must be a JSON object.")

    validate_demand_snapshot(snapshot)

    demand_ref = snapshot["demand_ref"]
    demand_values = snapshot["demand_values"]
    related = snapshot["related_records"]

    if not isinstance(demand_ref, dict):
        raise ValidationError("Invalid snapshot demand_ref.")

    if not isinstance(demand_values, dict):
        raise ValidationError("Invalid snapshot demand_values.")

    if not isinstance(related, dict):
        raise ValidationError("Invalid snapshot related_records.")

    if not REQUIRED_RELATED_KEYS.issubset(related):
        raise ValidationError(
            "Snapshot is missing required related record collections."
        )

    demand_id = demand_ref.get("demand_id")
    demand_code = demand_ref.get("demand_code")

    if not isinstance(demand_id, int) or isinstance(demand_id, bool):
        raise ValidationError("Snapshot demand_id must be an integer.")

    if not isinstance(demand_code, str) or not demand_code:
        raise ValidationError("Snapshot demand_code is required.")

    for key in REQUIRED_RELATED_KEYS:
        if not isinstance(related[key], list):
            raise ValidationError(
                f"Snapshot related_records.{key} must be an array."
            )

    return SnapshotDemand(
        demand_id=demand_id,
        demand_code=demand_code,
        captured_at=snapshot["captured_at"],
        demand_values=_freeze(demand_values),
        related_records=_freeze(related),
    )


def read_run_snapshots(snapshots):
    """
    Read all Demand snapshots belonging to one PlanningRun.

    `snapshots` must be an iterable of raw demand_snapshot dictionaries.
    """
    demands = tuple(
        read_demand_snapshot(snapshot)
        for snapshot in snapshots
    )

    demand_ids = [demand.demand_id for demand in demands]

    if len(demand_ids) != len(set(demand_ids)):
        raise ValidationError(
            "PlanningRun contains duplicate Demand snapshots."
        )

    # Capacity history is repeated in each Demand snapshot.
    # Deduplicate by immutable SupplierRequest primary key.
    requests_by_id = {}

    for demand in demands:
        for request in demand.related_records["capacity_requests"]:
            if not isinstance(request, Mapping):
                raise ValidationError(
                    "Capacity request snapshot must be an object."
                )

            request_id = request.get("id")

            if not isinstance(request_id, int) or isinstance(
                request_id, bool
            ):
                raise ValidationError(
                    "Capacity request snapshot has an invalid ID."
                )

            existing = requests_by_id.get(request_id)

            if existing is not None and dict(existing) != dict(request):
                raise ValidationError(
                    "Conflicting copies of a capacity request were found."
                )

            requests_by_id[request_id] = request

    return SnapshotRunData(
        demands=demands,
        capacity_requests=tuple(
            requests_by_id[key]
            for key in sorted(requests_by_id)
        ),
    )