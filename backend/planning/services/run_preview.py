"""Read-only CP8 F1 run preview; never persists planning results."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from planning.f1.cargo_compatibility import (
    normalize_cargo_compatibility_matrix,
)
from planning.services.snapshot_evaluator import evaluate_f1_snapshots


NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class DemandRunPreview:
    demand_id: int
    eligibility_status: str
    blockers: tuple[str, ...]
    diagnostics: tuple[str, ...]
    primary_reason_code: None
    plan_guard_status: str
    matching_status: str
    detail: str


@dataclass(frozen=True)
class RunPreview:
    captured_at: str
    rule_set_id: int
    rule_set_code: str
    rule_set_version: int
    business_rule_codes: tuple[str, ...]
    demand_results: tuple[DemandRunPreview, ...]
    candidate_groups: tuple
    business_rules_execution: str
    plan_guard_status: str
    matching_status: str
    ready_to_finalize: bool

    @property
    def all_demands_eligible(self):
        return bool(self.demand_results) and all(
            item.eligibility_status == "ELIGIBLE"
            for item in self.demand_results
        )


def _validate_configuration_snapshot(configuration):
    if not isinstance(configuration, Mapping):
        raise ValidationError(
            "RUN_CONFIGURATION_MUST_BE_OBJECT"
        )

    if configuration.get("schema_version") != "1.0":
        raise ValidationError(
            "RUN_CONFIGURATION_SCHEMA_VERSION_INVALID"
        )

    captured_at = configuration.get("captured_at")
    if not isinstance(captured_at, str) or not captured_at:
        raise ValidationError(
            "RUN_CONFIGURATION_CAPTURED_AT_REQUIRED"
        )

    try:
        captured_datetime = datetime.fromisoformat(captured_at)
    except ValueError:
        raise ValidationError(
            "RUN_CONFIGURATION_CAPTURED_AT_INVALID"
        )

    if (
        captured_datetime.tzinfo is None
        or captured_datetime.utcoffset() is None
    ):
        raise ValidationError(
            "RUN_CONFIGURATION_CAPTURED_AT_MUST_BE_AWARE"
        )

    rule_set = configuration.get("rule_set")
    if not isinstance(rule_set, Mapping):
        raise ValidationError(
            "RUN_CONFIGURATION_RULE_SET_INVALID"
        )

    rule_set_id = rule_set.get("id")
    if (
        not isinstance(rule_set_id, int)
        or isinstance(rule_set_id, bool)
        or rule_set_id <= 0
    ):
        raise ValidationError(
            "RUN_CONFIGURATION_RULE_SET_ID_INVALID"
        )

    rule_set_code = rule_set.get("code")
    if not isinstance(rule_set_code, str) or not rule_set_code.strip():
        raise ValidationError(
            "RUN_CONFIGURATION_RULE_SET_CODE_REQUIRED"
        )

    version = rule_set.get("version_no")
    if (
        not isinstance(version, int)
        or isinstance(version, bool)
        or version <= 0
    ):
        raise ValidationError(
            "RUN_CONFIGURATION_RULE_SET_VERSION_INVALID"
        )

    rules = configuration.get("business_rules")
    if not isinstance(rules, (list, tuple)) or not rules:
        raise ValidationError(
            "F1_RULE_CONFIGURATION_MISSING"
        )

    rule_codes = []
    seen_codes = set()

    for rule in rules:
        if not isinstance(rule, Mapping):
            raise ValidationError(
                "RUN_CONFIGURATION_BUSINESS_RULE_INVALID"
            )

        rule_id = rule.get("rule_id")
        if (
            not isinstance(rule_id, int)
            or isinstance(rule_id, bool)
            or rule_id <= 0
        ):
            raise ValidationError(
                "RUN_CONFIGURATION_BUSINESS_RULE_ID_INVALID"
            )

        code = rule.get("rule_code")
        if not isinstance(code, str) or not code.strip():
            raise ValidationError(
                "RUN_CONFIGURATION_BUSINESS_RULE_CODE_REQUIRED"
            )

        if code in seen_codes:
            raise ValidationError(
                "RUN_CONFIGURATION_BUSINESS_RULE_CODE_DUPLICATE"
            )

        seen_codes.add(code)
        rule_codes.append(code)

    if not isinstance(configuration.get("parameters"), Mapping):
        raise ValidationError(
            "RUN_CONFIGURATION_PARAMETERS_INVALID"
        )

    matrix_config = configuration.get("cargo_compatibility_matrix")

    if not isinstance(matrix_config, Mapping):
        raise ValidationError(
            "RUN_CONFIGURATION_CARGO_COMPATIBILITY_MATRIX_INVALID"
        )

    if matrix_config.get("source") != "CoLogi_Dataset_v7":
        raise ValidationError(
            "RUN_CONFIGURATION_CARGO_COMPATIBILITY_SOURCE_INVALID"
        )

    if matrix_config.get("sheet") != "08_Cargo_Compat":
        raise ValidationError(
            "RUN_CONFIGURATION_CARGO_COMPATIBILITY_SHEET_INVALID"
        )

    matrix_rows = matrix_config.get("rows")

    try:
        normalize_cargo_compatibility_matrix(matrix_rows)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    return (
        captured_at,
        rule_set_id,
        rule_set_code,
        version,
        tuple(rule_codes),
        matrix_rows,
    )


def _enum_value(value):
    return value.value if hasattr(value, "value") else str(value)


def preview_f1_run(*, snapshots, configuration_snapshot):
    """Evaluate immutable snapshots without creating or updating DB records.

    Business Rule definitions are validated as configuration data but are
    deliberately not interpreted or executed by this preview service.
    Plan Guard and Matching remain fail-closed until their contracts and
    evaluators are implemented.
    """
    (
        captured_at,
        rule_set_id,
        rule_set_code,
        rule_set_version,
        rule_codes,
        cargo_compatibility_rows,
    ) = _validate_configuration_snapshot(configuration_snapshot)

    snapshots = tuple(snapshots)
    if not snapshots:
        raise ValidationError("RUN_PREVIEW_REQUIRES_DEMAND_SNAPSHOTS")

    evaluation = evaluate_f1_snapshots(
        snapshots,
        cargo_compatibility_rows=cargo_compatibility_rows,
    )

    demand_results = tuple(
        DemandRunPreview(
            demand_id=item.demand_id,
            eligibility_status=_enum_value(
                item.eligibility.eligibility_status
            ),
            blockers=tuple(
                _enum_value(value)
                for value in item.eligibility.blockers
            ),
            diagnostics=tuple(item.eligibility.diagnostics),
            primary_reason_code=None,
            plan_guard_status=NOT_EVALUATED,
            matching_status=NOT_EVALUATED,
            detail=item.eligibility.detail,
        )
        for item in evaluation.demand_evaluations
    )

    return RunPreview(
        captured_at=captured_at,
        rule_set_id=rule_set_id,
        rule_set_code=rule_set_code,
        rule_set_version=rule_set_version,
        business_rule_codes=rule_codes,
        demand_results=demand_results,
        # Fail closed: Candidate Groups are withheld until Plan Guard is PASS.
        candidate_groups=(),
        business_rules_execution=NOT_EVALUATED,
        plan_guard_status=NOT_EVALUATED,
        matching_status=NOT_EVALUATED,
        ready_to_finalize=False,
    )
