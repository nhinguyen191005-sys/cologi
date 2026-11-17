
"""Validation for explicit CP8 PlanningRun demand scope."""

from django.core.exceptions import PermissionDenied, ValidationError

from accounts.permissions import get_active_user_outlet_accesses
from demands.models import DeliveryDemand


def normalize_demand_ids(demand_ids):
    """Validate, deduplicate-check and deterministically sort Demand IDs."""
    if not isinstance(demand_ids, (list, tuple)):
        raise ValidationError({
            "demand_ids": "Demand IDs must be a non-empty list."
        })

    if not demand_ids:
        raise ValidationError({
            "demand_ids": "At least one Demand ID is required."
        })

    normalized = []

    for value in demand_ids:
        if isinstance(value, bool):
            raise ValidationError({
                "demand_ids": "Demand IDs must be positive integers."
            })

        try:
            demand_id = int(value)
        except (TypeError, ValueError):
            raise ValidationError({
                "demand_ids": "Demand IDs must be positive integers."
            })

        if demand_id <= 0 or str(value).strip() != str(demand_id):
            raise ValidationError({
                "demand_ids": "Demand IDs must be positive integers."
            })

        normalized.append(demand_id)

    if len(normalized) != len(set(normalized)):
        raise ValidationError({
            "demand_ids": "Duplicate Demand IDs are not allowed."
        })

    return tuple(sorted(normalized))


def validate_run_scope(actor, demand_ids):
    """
    Validate explicit Demand IDs and purchasing staff Outlet access.

    Returns:
        (sorted_demand_ids, selected_demands)
    """
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentication is required.")

    ids = normalize_demand_ids(demand_ids)

    outlet_ids = set(
        get_active_user_outlet_accesses(actor)
        .values_list("outlet_id", flat=True)
    )

    if not outlet_ids:
        raise PermissionDenied(
            "Active PURCHASING_STAFF role and Outlet access are required."
        )

    demands = tuple(
        DeliveryDemand.objects
        .filter(pk__in=ids)
        .select_related(
            "supplier",
            "outlet",
            "cargo_category",
        )
        .prefetch_related("items__item")
        .order_by("pk")
    )

    found_ids = {demand.pk for demand in demands}
    missing_ids = sorted(set(ids) - found_ids)

    if missing_ids:
        raise ValidationError({
            "demand_ids": f"Unknown Demand IDs: {missing_ids}"
        })

    unauthorized = [
        demand.demand_code
        for demand in demands
        if demand.outlet_id not in outlet_ids
    ]

    if unauthorized:
        raise PermissionDenied(
            "You do not have access to every selected Demand."
        )

    return ids, demands
