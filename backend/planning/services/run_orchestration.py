"""Read-only end-to-end orchestration for a CP8 F1 run preview."""

from django.core.exceptions import ValidationError
from django.utils import timezone

from planning.f1.orm_reader import load_f1_orm_data
from planning.services.run_configuration import load_run_configuration
from planning.services.run_preview import preview_f1_run
from planning.services.run_scope import validate_run_scope
from planning.services.snapshot_builder import build_demand_snapshots


def preview_f1_run_for_actor(
    *,
    actor,
    demand_ids,
    rule_set_id,
    cost_profile_id=None,
):
    """Validate scope, capture inputs and return an F1 preview.

    This function performs SELECT-only ORM access. It does not create a
    PlanningRun, PlanningRunDemand, CollaborationGroup or GroupDemand.
    """
    normalized_ids, scoped_demands = validate_run_scope(
        actor,
        demand_ids,
    )

    scoped_ids = tuple(demand.pk for demand in scoped_demands)
    if scoped_ids != normalized_ids:
        raise ValidationError(
            "RUN_SCOPE_DEMAND_SET_INCONSISTENT"
        )

    captured_at = timezone.now()

    orm_data = load_f1_orm_data(normalized_ids)

    loaded_ids = tuple(
        demand.pk
        for demand in orm_data.selected_demands
    )
    if loaded_ids != normalized_ids:
        raise ValidationError(
            "RUN_SCOPE_CHANGED_DURING_PREVIEW"
        )

    configuration_snapshot = load_run_configuration(
        rule_set_id=rule_set_id,
        cost_profile_id=cost_profile_id,
        captured_at=captured_at,
    )

    snapshots_by_id = build_demand_snapshots(
        orm_data,
        captured_at=captured_at,
    )

    if set(snapshots_by_id) != set(normalized_ids):
        raise ValidationError(
            "RUN_PREVIEW_SNAPSHOT_DEMAND_SET_INCONSISTENT"
        )

    return preview_f1_run(
        snapshots=tuple(
            snapshots_by_id[demand_id]
            for demand_id in normalized_ids
        ),
        configuration_snapshot=configuration_snapshot,
    )
