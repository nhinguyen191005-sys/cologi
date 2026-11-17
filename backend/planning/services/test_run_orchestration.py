from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from planning.services.run_orchestration import (
    preview_f1_run_for_actor,
)


class RunOrchestrationTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(is_authenticated=True)
        self.demands = (
            SimpleNamespace(pk=10),
            SimpleNamespace(pk=20),
        )
        self.orm_data = SimpleNamespace(
            selected_demands=self.demands,
        )
        self.configuration = {"schema_version": "1.0"}
        self.snapshots = {
            10: {"demand_ref": {"demand_id": 10}},
            20: {"demand_ref": {"demand_id": 20}},
        }
        self.preview = SimpleNamespace(ready_to_finalize=False)

    @patch("planning.services.run_orchestration.preview_f1_run")
    @patch("planning.services.run_orchestration.build_demand_snapshots")
    @patch("planning.services.run_orchestration.load_run_configuration")
    @patch("planning.services.run_orchestration.load_f1_orm_data")
    @patch("planning.services.run_orchestration.validate_run_scope")
    def test_orchestrates_scope_snapshot_configuration_and_preview(
        self,
        validate_scope,
        load_orm,
        load_configuration,
        build_snapshots,
        evaluate_preview,
    ):
        validate_scope.return_value = ((10, 20), self.demands)
        load_orm.return_value = self.orm_data
        load_configuration.return_value = self.configuration
        build_snapshots.return_value = self.snapshots
        evaluate_preview.return_value = self.preview

        result = preview_f1_run_for_actor(
            actor=self.actor,
            demand_ids=[20, 10],
            rule_set_id=5,
            cost_profile_id=3,
        )

        self.assertIs(result, self.preview)
        validate_scope.assert_called_once_with(
            self.actor,
            [20, 10],
        )
        load_orm.assert_called_once_with((10, 20))
        load_configuration.assert_called_once()
        build_snapshots.assert_called_once()
        evaluate_preview.assert_called_once_with(
            snapshots=(
                self.snapshots[10],
                self.snapshots[20],
            ),
            configuration_snapshot=self.configuration,
        )

        captured_at = load_configuration.call_args.kwargs["captured_at"]
        self.assertIs(
            captured_at,
            build_snapshots.call_args.kwargs["captured_at"],
        )

    @patch("planning.services.run_orchestration.validate_run_scope")
    def test_rejects_inconsistent_scope_result(self, validate_scope):
        validate_scope.return_value = (
            (10, 20),
            (SimpleNamespace(pk=10),),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "RUN_SCOPE_DEMAND_SET_INCONSISTENT",
        ):
            preview_f1_run_for_actor(
                actor=self.actor,
                demand_ids=[10, 20],
                rule_set_id=5,
            )

    @patch("planning.services.run_orchestration.load_f1_orm_data")
    @patch("planning.services.run_orchestration.validate_run_scope")
    def test_rejects_changed_demand_set_before_snapshot(
        self,
        validate_scope,
        load_orm,
    ):
        validate_scope.return_value = ((10, 20), self.demands)
        load_orm.return_value = SimpleNamespace(
            selected_demands=(self.demands[0],),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "RUN_SCOPE_CHANGED_DURING_PREVIEW",
        ):
            preview_f1_run_for_actor(
                actor=self.actor,
                demand_ids=[10, 20],
                rule_set_id=5,
            )

    @patch("planning.services.run_orchestration.build_demand_snapshots")
    @patch("planning.services.run_orchestration.load_run_configuration")
    @patch("planning.services.run_orchestration.load_f1_orm_data")
    @patch("planning.services.run_orchestration.validate_run_scope")
    def test_rejects_incomplete_snapshot_set(
        self,
        validate_scope,
        load_orm,
        load_configuration,
        build_snapshots,
    ):
        validate_scope.return_value = ((10, 20), self.demands)
        load_orm.return_value = self.orm_data
        load_configuration.return_value = self.configuration
        build_snapshots.return_value = {
            10: self.snapshots[10],
        }

        with self.assertRaisesMessage(
            ValidationError,
            "RUN_PREVIEW_SNAPSHOT_DEMAND_SET_INCONSISTENT",
        ):
            preview_f1_run_for_actor(
                actor=self.actor,
                demand_ids=[10, 20],
                rule_set_id=5,
            )
