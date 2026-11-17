
from unittest import TestCase

from planning.services.plan_guard import (
    FAIL,
    NOT_EVALUATED,
    PASS,
    PlanGuardEvidence,
    UnavailablePlanGuardSource,
    build_plan_guard_snapshots,
    evaluate_plan_guard_snapshot,
    evaluate_plan_guard_snapshots,
)


CAPTURED_AT = "2026-11-17T10:00:00+07:00"


class FakePlanGuardSource:
    source_name = "TEST_FULFILLMENT_PLAN"

    def __init__(self, results=None, error=None):
        self.results = results
        self.error = error

    def capture(self, *, demand_ids, captured_at):
        if self.error:
            raise self.error
        return self.results


class PlanGuardTests(TestCase):
    def test_unavailable_source_is_not_evaluated(self):
        result = build_plan_guard_snapshots(
            source=UnavailablePlanGuardSource(),
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], NOT_EVALUATED)
        self.assertFalse(result[101]["query_complete"])
        self.assertIsNone(result[101]["has_finalized_plan"])

    def test_complete_query_without_finalized_plan_passes(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(
                query_complete=True,
                has_finalized_plan=False,
            ),
        })

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], PASS)
        self.assertEqual(result[101]["finalized_plan_ids"], [])

    def test_finalized_plan_fails(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(
                query_complete=True,
                has_finalized_plan=True,
                finalized_plan_ids=(9,),
            ),
        })

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], FAIL)
        self.assertEqual(result[101]["finalized_plan_ids"], [9])

    def test_positive_evidence_blocks_even_if_query_incomplete(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(
                query_complete=False,
                has_finalized_plan=True,
                finalized_plan_ids=(9,),
            ),
        })

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], FAIL)

    def test_incomplete_negative_query_is_not_evaluated(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(
                query_complete=False,
                has_finalized_plan=False,
            ),
        })

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], NOT_EVALUATED)

    def test_missing_demand_result_is_not_evaluated(self):
        source = FakePlanGuardSource({})

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], NOT_EVALUATED)
        self.assertEqual(
            result[101]["reason_code"],
            "PLAN_GUARD_SOURCE_RESULT_MISSING",
        )

    def test_source_exception_is_not_evaluated(self):
        source = FakePlanGuardSource(error=RuntimeError("source unavailable"))

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], NOT_EVALUATED)
        self.assertEqual(
            result[101]["reason_code"],
            "PLAN_GUARD_SOURCE_ERROR",
        )

    def test_invalid_evidence_is_not_evaluated(self):
        source = FakePlanGuardSource({101: {"status": "PASS"}})

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], NOT_EVALUATED)
        self.assertEqual(
            result[101]["reason_code"],
            "PLAN_GUARD_SOURCE_RESULT_INVALID",
        )

    def test_conflicting_evidence_is_not_evaluated(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(
                query_complete=True,
                has_finalized_plan=False,
                finalized_plan_ids=(9,),
            ),
        })

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], NOT_EVALUATED)

    def test_each_demand_gets_independent_result(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(True, False),
            102: PlanGuardEvidence(True, True, (9,)),
        })

        result = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101, 102),
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(result[101]["status"], PASS)
        self.assertEqual(result[102]["status"], FAIL)


    def _snapshot(self, plan_guard):
        return {
            "schema_version": "1.0",
            "captured_at": CAPTURED_AT,
            "demand_ref": {
                "demand_id": 101,
                "demand_code": "DD0101",
            },
            "demand_values": {},
            "related_records": {
                "demand_items": [],
                "supplier_items": [],
                "capacity_requests": [],
                "supplier_confirmations": [],
                "plan_guard": plan_guard,
            },
        }

    def test_snapshot_evaluator_accepts_complete_negative_evidence(self):
        evidence = {
            "schema_version": "1.0",
            "demand_id": 101,
            "captured_at": CAPTURED_AT,
            "source": "TEST_FULFILLMENT_PLAN",
            "query_complete": True,
            "has_finalized_plan": False,
            "finalized_plan_ids": [],
            "status": FAIL,
            "reason_code": "TAMPERED_STATUS",
        }

        result = evaluate_plan_guard_snapshot(
            evidence,
            expected_demand_id=101,
            expected_captured_at=CAPTURED_AT,
        )

        self.assertEqual(result.status, PASS)
        self.assertIsNone(result.reason_code)

    def test_snapshot_evaluator_rejects_missing_evidence(self):
        result = evaluate_plan_guard_snapshot(
            None,
            expected_demand_id=101,
            expected_captured_at=CAPTURED_AT,
        )

        self.assertEqual(result.status, NOT_EVALUATED)

    def test_snapshot_evaluator_rejects_wrong_demand_id(self):
        evidence = {
            "schema_version": "1.0",
            "demand_id": 102,
            "captured_at": CAPTURED_AT,
            "source": "TEST_FULFILLMENT_PLAN",
            "query_complete": True,
            "has_finalized_plan": False,
            "finalized_plan_ids": [],
        }

        result = evaluate_plan_guard_snapshot(
            evidence,
            expected_demand_id=101,
            expected_captured_at=CAPTURED_AT,
        )

        self.assertEqual(result.status, NOT_EVALUATED)

    def test_snapshot_evaluator_rejects_wrong_capture_time(self):
        evidence = {
            "schema_version": "1.0",
            "demand_id": 101,
            "captured_at": "2026-11-16T10:00:00+07:00",
            "source": "TEST_FULFILLMENT_PLAN",
            "query_complete": True,
            "has_finalized_plan": False,
            "finalized_plan_ids": [],
        }

        result = evaluate_plan_guard_snapshot(
            evidence,
            expected_demand_id=101,
            expected_captured_at=CAPTURED_AT,
        )

        self.assertEqual(result.status, NOT_EVALUATED)

    def test_snapshot_evaluator_blocks_finalized_plan(self):
        evidence = {
            "schema_version": "1.0",
            "demand_id": 101,
            "captured_at": CAPTURED_AT,
            "source": "TEST_FULFILLMENT_PLAN",
            "query_complete": False,
            "has_finalized_plan": True,
            "finalized_plan_ids": [9],
        }

        result = evaluate_plan_guard_snapshot(
            evidence,
            expected_demand_id=101,
            expected_captured_at=CAPTURED_AT,
        )

        self.assertEqual(result.status, FAIL)
        self.assertEqual(result.finalized_plan_ids, (9,))

    def test_snapshot_collection_reads_plan_guard_per_demand(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(True, False),
        })
        captured = build_plan_guard_snapshots(
            source=source,
            demand_ids=(101,),
            captured_at=CAPTURED_AT,
        )

        result = evaluate_plan_guard_snapshots([
            self._snapshot(captured[101]),
        ])

        self.assertEqual(result[101].status, PASS)

    def test_snapshot_collection_missing_plan_guard_fails_closed(self):
        result = evaluate_plan_guard_snapshots([
            self._snapshot(None),
        ])

        self.assertEqual(result[101].status, NOT_EVALUATED)
