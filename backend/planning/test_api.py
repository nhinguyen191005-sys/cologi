from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from planning.services.run_preview import (
    DemandRunPreview,
    NOT_EVALUATED,
    RunPreview,
)
from planning.views import F1RunPreviewView


class F1RunPreviewAPITests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.url = "/api/planning/f1/preview/"
        self.actor = SimpleNamespace(is_authenticated=True)

        self.preview = RunPreview(
            captured_at="2026-11-17T10:00:00+07:00",
            rule_set_id=1,
            rule_set_code="CP8-F1",
            rule_set_version=1,
            business_rule_codes=("F1-RULE-001",),
            demand_results=(
                DemandRunPreview(
                    demand_id=101,
                    eligibility_status="ELIGIBLE",
                    blockers=(),
                    diagnostics=(),
                    primary_reason_code=None,
                    plan_guard_status=NOT_EVALUATED,
                    matching_status=NOT_EVALUATED,
                    detail="Test evaluation",
                ),
            ),
            candidate_groups=(),
            business_rules_execution=NOT_EVALUATED,
            plan_guard_status=NOT_EVALUATED,
            matching_status=NOT_EVALUATED,
            ready_to_finalize=False,
        )

    @patch("planning.views.preview_f1_run_for_actor")
    def test_authenticated_request_returns_read_only_preview(self, preview_service):
        preview_service.return_value = self.preview

        request = self.factory.post(
            self.url,
            {
                "demand_ids": [101],
                "rule_set_id": 1,
            },
            format="json",
        )
        force_authenticate(request, user=self.actor)

        response = F1RunPreviewView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["rule_set_code"], "CP8-F1")
        self.assertEqual(response.data["demand_results"][0]["demand_id"], 101)
        self.assertTrue(response.data["all_demands_eligible"])
        self.assertFalse(response.data["ready_to_finalize"])
        self.assertEqual(response.data["plan_guard_status"], NOT_EVALUATED)
        preview_service.assert_called_once_with(
            actor=self.actor,
            demand_ids=[101],
            rule_set_id=1,
            cost_profile_id=None,
        )

    @patch("planning.views.preview_f1_run_for_actor")
    def test_unknown_request_field_is_rejected(self, preview_service):
        request = self.factory.post(
            self.url,
            {
                "demand_ids": [101],
                "rule_set_id": 1,
                "unexpected": True,
            },
            format="json",
        )
        force_authenticate(request, user=self.actor)

        response = F1RunPreviewView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        preview_service.assert_not_called()

    @patch("planning.views.preview_f1_run_for_actor")
    def test_unauthenticated_request_is_rejected(self, preview_service):
        request = self.factory.post(
            self.url,
            {
                "demand_ids": [101],
                "rule_set_id": 1,
            },
            format="json",
        )

        response = F1RunPreviewView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        preview_service.assert_not_called()
