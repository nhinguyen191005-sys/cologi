
from datetime import date, datetime, time, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest import TestCase

from planning.services.plan_guard import (
    FAIL,
    NOT_EVALUATED,
    PASS,
    PlanGuardEvidence,
)
from planning.services.snapshot_builder import build_demand_snapshots


CAPTURED_AT = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)


class FakeRelatedManager:
    def __init__(self, records=()):
        self.records = tuple(records)

    def all(self):
        return self.records


class FakePlanGuardSource:
    source_name = "TEST_FULFILLMENT_PLAN"

    def __init__(self, results):
        self.results = results
        self.calls = []

    def capture(self, *, demand_ids, captured_at):
        self.calls.append((demand_ids, captured_at))
        return self.results


def make_demand(demand_id):
    item = NS(
        item_code="ITEM-001",
        item_name="Test item",
        cargo_category_id=1,
        weight_unit="KG",
        is_active=True,
    )

    demand_item = NS(
        pk=400 + demand_id,
        item_id=301,
        required_weight_kg=Decimal("10"),
        unit_of_measure="KG",
        item=item,
    )

    return NS(
        pk=demand_id,
        demand_code=f"DD-{demand_id}",
        supplier_id=201,
        outlet_id=100 + demand_id,
        cargo_category_id=1,
        cargo_category=NS(is_active=True),
        supplier=NS(is_active=True),
        quantity_kg=Decimal("10"),
        requested_date=date(2026, 12, 1),
        requested_start_time=time(8, 0),
        requested_end_time=time(12, 0),
        status="SUBMITTED",
        items=FakeRelatedManager([demand_item]),
        supplier_confirmations=FakeRelatedManager(),
    )


def make_orm_data(*demand_ids):
    return NS(
        selected_demands=tuple(make_demand(i) for i in demand_ids),
        supplier_items=(
            NS(
                pk=501,
                supplier_id=201,
                item_id=301,
                unit_price_vnd_per_kg=Decimal("1000"),
                max_daily_supply_kg=Decimal("100"),
                lead_time_hours=2,
                minimum_order_kg=Decimal("1"),
                offer_status="ACTIVE",
            ),
        ),
        capacity_requests=(),
    )


class SnapshotBuilderPlanGuardTests(TestCase):

    def test_unavailable_source_is_not_evaluated(self):
        snapshots = build_demand_snapshots(
            make_orm_data(101),
            captured_at=CAPTURED_AT,
        )

        snapshot = snapshots[101]
        evidence = snapshot["related_records"]["plan_guard"]

        self.assertEqual(evidence["status"], NOT_EVALUATED)
        self.assertEqual(evidence["source"], "UNAVAILABLE")
        self.assertEqual(evidence["demand_id"], 101)
        self.assertEqual(
            evidence["captured_at"],
            CAPTURED_AT.isoformat(),
        )

    def test_complete_negative_evidence_is_snapshotted(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(
                query_complete=True,
                has_finalized_plan=False,
            ),
        })

        snapshots = build_demand_snapshots(
            make_orm_data(101),
            captured_at=CAPTURED_AT,
            plan_guard_source=source,
        )

        evidence = snapshots[101]["related_records"]["plan_guard"]

        self.assertEqual(evidence["status"], PASS)
        self.assertEqual(evidence["source"], source.source_name)
        self.assertEqual(evidence["finalized_plan_ids"], [])
        self.assertEqual(
            evidence["captured_at"],
            snapshots[101]["captured_at"],
        )
        self.assertEqual(
            source.calls,
            [((101,), CAPTURED_AT.isoformat())],
        )

    def test_finalized_plan_evidence_is_snapshotted(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(
                query_complete=False,
                has_finalized_plan=True,
                finalized_plan_ids=(9001,),
            ),
        })

        snapshots = build_demand_snapshots(
            make_orm_data(101),
            captured_at=CAPTURED_AT,
            plan_guard_source=source,
        )

        evidence = snapshots[101]["related_records"]["plan_guard"]

        self.assertEqual(evidence["status"], FAIL)
        self.assertEqual(evidence["reason_code"], "DEMAND_IN_FINALIZED_PLAN")
        self.assertEqual(evidence["finalized_plan_ids"], [9001])

    def test_multiple_demands_keep_separate_evidence(self):
        source = FakePlanGuardSource({
            101: PlanGuardEvidence(True, False),
            102: PlanGuardEvidence(
                False,
                True,
                (9002,),
            ),
        })

        snapshots = build_demand_snapshots(
            make_orm_data(101, 102),
            captured_at=CAPTURED_AT,
            plan_guard_source=source,
        )

        first = snapshots[101]["related_records"]["plan_guard"]
        second = snapshots[102]["related_records"]["plan_guard"]

        self.assertEqual(first["status"], PASS)
        self.assertEqual(first["demand_id"], 101)
        self.assertEqual(second["status"], FAIL)
        self.assertEqual(second["demand_id"], 102)
        self.assertEqual(second["finalized_plan_ids"], [9002])
        self.assertEqual(
            set(snapshots),
            {101, 102},
        )
