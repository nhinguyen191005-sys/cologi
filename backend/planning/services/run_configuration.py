"""Resolve and freeze configuration for a CP08 PlanningRun."""

import json
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from planning.models import (
    CostProfile,
    PlanningBusinessRule,
    PlanningParameters,
    PlanningRuleSet,
    PlanningModuleCode,
    RuleSetStatus,
)
from planning.f1.cargo_compatibility import (
    dataset_v7_cargo_compatibility_rows,
    normalize_cargo_compatibility_matrix,
)

def _json_safe(value, context):
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        )
        return json.loads(encoded)
    except (TypeError, ValueError, OverflowError):
        raise ValidationError(
            f"{context} must contain valid JSON data."
        )


def _decimal_string(value):
    if value is None:
        return None
    return str(Decimal(value))



def build_parameters_snapshot(
    *,
    rule_set,
    business_rules,
    parameters,
    cost_profile=None,
    captured_at=None,
):
    """Build an immutable-by-convention JSON-safe configuration snapshot."""

    captured_at = captured_at or timezone.now()

    if timezone.is_naive(captured_at):
        raise ValidationError("captured_at must be timezone-aware.")

    if rule_set.status != RuleSetStatus.ACTIVE:
        raise ValidationError("PLANNING_RULE_SET_NOT_ACTIVE")

    if (
        rule_set.effective_from is not None
        and rule_set.effective_from > captured_at
    ):
        raise ValidationError("PLANNING_RULE_SET_NOT_EFFECTIVE")

    active_f1_rules = [
        rule
        for rule in business_rules
        if (
            rule.module_code == PlanningModuleCode.F1
            and rule.is_active
        )
    ]

    if not active_f1_rules:
        raise ValidationError("F1_RULE_CONFIGURATION_MISSING")

    rules_snapshot = []

    for rule in sorted(
        active_f1_rules,
        key=lambda item: (item.priority, item.rule_code, item.pk),
    ):
        rules_snapshot.append({
            "rule_id": rule.pk,
            "rule_code": rule.rule_code,
            "rule_name": rule.rule_name,
            "priority": rule.priority,
            "rule_definition": _json_safe(
                rule.rule_definition,
                f"Business rule {rule.rule_code}",
            ),
        })

    parameter_snapshot = {}

    for parameter in sorted(
        parameters,
        key=lambda item: item.parameter_key,
    ):
        if parameter.parameter_key in parameter_snapshot:
            raise ValidationError(
                "Duplicate Planning Parameter key detected."
            )

        parameter_snapshot[parameter.parameter_key] = {
            "value": _json_safe(
                parameter.parameter_value,
                f"Parameter {parameter.parameter_key}",
            ),
            "data_type": parameter.data_type,
            "updated_at": (
                parameter.updated_at.isoformat()
                if parameter.updated_at
                else None
            ),
        }

    cost_snapshot = None

    if cost_profile is not None:
        if not cost_profile.is_active:
            raise ValidationError("COST_PROFILE_NOT_ACTIVE")

        if cost_profile.currency_code != "VND":
            raise ValidationError("COST_PROFILE_CURRENCY_INVALID")

        cost_snapshot = {
            "id": cost_profile.pk,
            "profile_code": cost_profile.profile_code,
            "profile_name": cost_profile.profile_name,
            "currency_code": cost_profile.currency_code,
            "fixed_transport_cost": _decimal_string(
                cost_profile.fixed_transport_cost
            ),
            "cost_per_km": _decimal_string(
                cost_profile.cost_per_km
            ),
            "additional_handling_cost": _decimal_string(
                cost_profile.additional_handling_cost
            ),
        }


    cargo_compatibility_rows = (
        dataset_v7_cargo_compatibility_rows()
    )

    try:
        normalize_cargo_compatibility_matrix(
            cargo_compatibility_rows
        )
    except ValueError as exc:
        raise ValidationError(str(exc))
    
    return {
        "schema_version": "1.0",
        "captured_at": captured_at.isoformat(),
        "rule_set": {
            "id": rule_set.pk,
            "code": rule_set.rule_set_code,
            "name": rule_set.rule_set_name,
            "version_no": rule_set.version_no,
        },
        "business_rules": rules_snapshot,
        "parameters": parameter_snapshot,
        "cargo_compatibility_matrix": {
            "source": "CoLogi_Dataset_v7",
            "sheet": "08_Cargo_Compat",
            "rows": _json_safe(
                cargo_compatibility_rows,
                "Cargo compatibility matrix",
            ),
        },
        "cost_profile": cost_snapshot,
    }


def load_run_configuration(
    *,
    rule_set_id,
    cost_profile_id=None,
    captured_at=None,
):
    """Load and validate persisted configuration without modifying records."""

    captured_at = captured_at or timezone.now()

    try:
        rule_set = PlanningRuleSet.objects.get(pk=rule_set_id)
    except PlanningRuleSet.DoesNotExist:
        raise ValidationError("PLANNING_RULE_SET_NOT_FOUND")

    if rule_set.status != RuleSetStatus.ACTIVE:
        raise ValidationError("PLANNING_RULE_SET_NOT_ACTIVE")

    if (
        rule_set.effective_from is not None
        and rule_set.effective_from > captured_at
    ):
        raise ValidationError("PLANNING_RULE_SET_NOT_EFFECTIVE")

    business_rules = tuple(
        PlanningBusinessRule.objects.filter(
            rule_set=rule_set,
            module_code=PlanningModuleCode.F1,
            is_active=True,
        ).order_by("priority", "rule_code", "pk")
    )

    if not business_rules:
        raise ValidationError("F1_RULE_CONFIGURATION_MISSING")

    parameters = tuple(
        PlanningParameters.objects.all().order_by("parameter_key")
    )

    cost_profile = None

    if cost_profile_id is not None:
        try:
            cost_profile = CostProfile.objects.get(pk=cost_profile_id)
        except CostProfile.DoesNotExist:
            raise ValidationError("COST_PROFILE_NOT_FOUND")


    return build_parameters_snapshot(
        rule_set=rule_set,
        business_rules=business_rules,
        parameters=parameters,
        cost_profile=cost_profile,
        captured_at=captured_at,
    )
