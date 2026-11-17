from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from planning.services.run_preview import (
    NOT_EVALUATED,
    preview_f1_run,
)

from planning.f1.cargo_compatibility import (
    dataset_v7_cargo_compatibility_rows,
)

def valid_configuration():
    return {
        "schema_version": "1.0",
        "captured_at": "2026-11-17T10:00:00+07:00",
        "rule_set": {
            "id": 1,
            "code": "CP8-F1",
            "name": "CP8 F1",
            "version_no": 1,
        },
        "business_rules": [
            {
                "rule_id": 1,
                "rule_code": "F1-RULE-001",
                "rule_name": "F1 rule",
                "priority": 1,
                "rule_definition": {"uninterpreted": True},
            }
        ],
        "parameters": {},
        "cargo_compatibility_matrix": {
            "source": "CoLogi_Dataset_v7",
            "sheet": "08_Cargo_Compat",
            "rows": list(dataset_v7_cargo_compatibility_rows()),
        },
        "cost_profile": None,
    }


def fake_evaluation(
    *,
    eligibility_status="ELIGIBLE",
    blockers=(),
    diagnostics=(),
    candidate_groups=(),
):
    eligibility = SimpleNamespace(
        eligibility_status=eligibility_status,
        blockers=blockers,
        diagnostics=diagnostics,
        detail="Test evaluation",
    )
    demand = SimpleNamespace(
        demand_id=101,
        eligibility=eligibility,
    )
    return SimpleNamespace(
        demand_evaluations=(demand,),
        candidate_groups=candidate_groups,
    )


class RunPreviewTests(SimpleTestCase):
    def test_missing_cargo_compatibility_matrix_is_rejected(self):
        configuration = valid_configuration()
        del configuration["cargo_compatibility_matrix"]

        with self.assertRaises(ValidationError):
            preview_f1_run(
                snapshots=[{"demand_ref": {"demand_id": 101}}],
                configuration_snapshot=configuration,
            )

    def test_invalid_cargo_compatibility_matrix_is_rejected(self):
        configuration = valid_configuration()
        configuration["cargo_compatibility_matrix"]["rows"] = []

        with self.assertRaises(ValidationError):
            preview_f1_run(
                snapshots=[{"demand_ref": {"demand_id": 101}}],
                configuration_snapshot=configuration,
            )
    @patch("planning.services.run_preview.evaluate_f1_snapshots")
    def test_eligible_demand_keeps_all_unimplemented_gates_closed(
        self, evaluate,
    ):
        evaluate.return_value = fake_evaluation()
        preview = preview_f1_run(
            snapshots=[{"demand_ref": {"demand_id": 101}}],
            configuration_snapshot=valid_configuration(),
        )

        self.assertEqual(preview.demand_results[0].eligibility_status, "ELIGIBLE")
        self.assertEqual(preview.plan_guard_status, NOT_EVALUATED)
        self.assertEqual(preview.matching_status, NOT_EVALUATED)
        self.assertEqual(
            preview.business_rules_execution,
            NOT_EVALUATED,
        )
        self.assertFalse(preview.ready_to_finalize)
        self.assertTrue(preview.all_demands_eligible)
        evaluate.assert_called_once()

    @patch("planning.services.run_preview.evaluate_f1_snapshots")
    def test_excluded_demand_remains_excluded(self, evaluate):
        evaluate.return_value = fake_evaluation(
            eligibility_status="EXCLUDED",
            blockers=("CAPACITY_EXCEEDED",),
            diagnostics=("CAPACITY_DIAGNOSTIC",),
        )
        preview = preview_f1_run(
            snapshots=[{"demand_ref": {"demand_id": 101}}],
            configuration_snapshot=valid_configuration(),
        )

        result = preview.demand_results[0]
        self.assertEqual(result.eligibility_status, "EXCLUDED")
        self.assertEqual(result.blockers, ("CAPACITY_EXCEEDED",))
        self.assertEqual(result.diagnostics, ("CAPACITY_DIAGNOSTIC",))
        self.assertFalse(preview.all_demands_eligible)
        self.assertFalse(preview.ready_to_finalize)

    @patch("planning.services.run_preview.evaluate_f1_snapshots")
    def test_candidate_groups_are_withheld_when_plan_guard_not_evaluated(
        self, evaluate,
    ):
        candidate = object()
        evaluate.return_value = fake_evaluation(
            candidate_groups=(candidate,),
        )

        preview = preview_f1_run(
            snapshots=[{"demand_ref": {"demand_id": 101}}],
            configuration_snapshot=valid_configuration(),
        )

        self.assertEqual(preview.candidate_groups, ())
        self.assertEqual(preview.plan_guard_status, NOT_EVALUATED)
        self.assertFalse(preview.ready_to_finalize)

    def test_missing_business_rule_is_rejected(self):
        configuration = valid_configuration()
        configuration["business_rules"] = []

        with self.assertRaises(ValidationError):
            preview_f1_run(
                snapshots=[{"demand_ref": {"demand_id": 101}}],
                configuration_snapshot=configuration,
            )

    def test_invalid_or_naive_configuration_timestamp_is_rejected(self):
        for value in ("not-a-date", "2026-11-17T10:00:00"):
            configuration = valid_configuration()
            configuration["captured_at"] = value

            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    preview_f1_run(
                        snapshots=[{"demand_ref": {"demand_id": 101}}],
                        configuration_snapshot=configuration,
                    )

    def test_empty_snapshots_are_rejected(self):
        with self.assertRaises(ValidationError):
            preview_f1_run(
                snapshots=[],
                configuration_snapshot=valid_configuration(),
            )

    @patch("planning.services.run_preview.evaluate_f1_snapshots")
    def test_preview_does_not_mutate_inputs(self, evaluate):
        evaluate.return_value = fake_evaluation()
        snapshots = [{"demand_ref": {"demand_id": 101}}]
        configuration = valid_configuration()
        original_snapshots = deepcopy(snapshots)
        original_configuration = deepcopy(configuration)

        preview_f1_run(
            snapshots=snapshots,
            configuration_snapshot=configuration,
        )

        self.assertEqual(snapshots, original_snapshots)
        self.assertEqual(configuration, original_configuration)

    def test_invalid_configuration_object_is_rejected(self):
        with self.assertRaises(ValidationError):
            preview_f1_run(
                snapshots=[{"demand_ref": {"demand_id": 101}}],
                configuration_snapshot=None,
            )
