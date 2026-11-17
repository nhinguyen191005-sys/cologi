
from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest import TestCase

from planning.f1.eligibility import (
    EligibilityBlocker,
    EligibilityStatus,
)
from planning.f1.supplier_confirmation import ConfirmationGateStatus
from planning.services.snapshot_evaluator import evaluate_f1_snapshots


class SnapshotEvaluatorTests(TestCase):
    DELIVERY_DATE = "2026-12-01"

    def make_request(
        self,
        *,
        request_id=601,
        demand_id=1,
        supplier_id=201,
        attempt_no=1,
        demand_item_id=401,
        item_id=301,
        supplier_item_id=501,
        confirmed_weight="10",
        promised_weight="10",
        request_status="RESPONDED",
        confirmation_status="CONFIRMED",
        commitment_released=False,
        supplier_item_supplier_id=None,
        supplier_item_item_id=None,
    ):
        return {
            "id": request_id,
            "demand_id": demand_id,
            "requested_date": self.DELIVERY_DATE,
            "demand_status": "SUBMITTED",
            "supplier_id": supplier_id,
            "attempt_no": attempt_no,
            "request_status": request_status,
            "confirmation": {
                "id": request_id + 1000,
                "demand_id": demand_id,
                "supplier_id": supplier_id,
                "confirmation_status": confirmation_status,
                "commitment_released": commitment_released,
            },
            "promises": [
                {
                    "id": request_id + 2000,
                    "supplier_request_id": request_id,
                    "demand_item_id": demand_item_id,
                    "demand_item_demand_id": demand_id,
                    "supplier_item_id": supplier_item_id,
                    "item_id": item_id,
                    "promised_weight_kg": promised_weight,
                    "confirmed_weight_kg": confirmed_weight,
                    "line_status": "CONFIRMED",
                    "supplier_item_supplier_id": (
                        supplier_item_supplier_id
                        if supplier_item_supplier_id is not None
                        else supplier_id
                    ),
                    "supplier_item_item_id": (
                        supplier_item_item_id
                        if supplier_item_item_id is not None
                        else item_id
                    ),
                }
            ],
        }

    def make_demand(
        self,
        demand_id=1,
        *,
        outlet_id=None,
        request_list=None,
        max_daily_supply="100",
        quantity="10",
        start_time="08:00:00",
        end_time="12:00:00",
    ):
        demand_item_id = 400 + demand_id
        if outlet_id is None:
            outlet_id = 100 + demand_id

        return {
            "schema_version": "1.0",
            "captured_at": "2026-11-17T08:00:00+07:00",
            "demand_ref": {
                "demand_id": demand_id,
                "demand_code": f"DM-{demand_id:04d}",
            },
            "demand_values": {
                "supplier_id": 201,
                "outlet_id": outlet_id,
                "cargo_category_id": 1,
                "cargo_category_active": True,
                "supplier_active": True,
                "quantity_kg": quantity,
                "requested_date": self.DELIVERY_DATE,
                "requested_start_time": start_time,
                "requested_end_time": end_time,
                "status": "SUBMITTED",
            },
            "related_records": {
                "demand_items": [
                    {
                        "id": demand_item_id,
                        "item_id": 301,
                        "required_weight_kg": quantity,
                        "unit_of_measure": "KG",
                        "item": {
                            "item_code": "ITEM-001",
                            "item_name": "Test item",
                            "cargo_category_id": 1,
                            "weight_unit": "KG",
                            "is_active": True,
                        },
                    }
                ],
                "supplier_items": [
                    {
                        "id": 501,
                        "supplier_id": 201,
                        "item_id": 301,
                        "unit_price_vnd_per_kg": "1000",
                        "max_daily_supply_kg": max_daily_supply,
                        "lead_time_hours": 2,
                        "minimum_order_kg": "1",
                        "offer_status": "ACTIVE",
                    }
                ],
                "capacity_requests": deepcopy(request_list or []),
                "supplier_confirmations": [],
            },
        }

    @staticmethod
    def valid_cargo_compatibility_rows():
        from planning.f1.cargo_compatibility import (
            dataset_v7_cargo_compatibility_rows,
        )

        return dataset_v7_cargo_compatibility_rows()

    def evaluate(self, *demands):
        return evaluate_f1_snapshots(
            demands,
            cargo_compatibility_rows=self.valid_cargo_compatibility_rows(),
        )

    def test_valid_snapshot_is_eligible(self):
        request = self.make_request()
        demand = self.make_demand(request_list=[request])

        result = self.evaluate(demand)

        self.assertEqual(len(result.demand_evaluations), 1)
        evaluation = result.demand_evaluations[0]

        self.assertEqual(evaluation.demand_id, 1)
        self.assertEqual(
            evaluation.eligibility.eligibility_status,
            EligibilityStatus.ELIGIBLE,
        )
        self.assertEqual(result.candidate_groups, ())

    def test_missing_request_is_not_responded(self):
        snapshot = self.make_demand(
            demand_id=1,
            request_list=[],
        )

        result = evaluate_f1_snapshots(
            [snapshot],
            cargo_compatibility_rows=self.valid_cargo_compatibility_rows(),
        )
        eligibility = result.demand_evaluations[0].eligibility

        self.assertEqual(
            eligibility.eligibility_status,
            EligibilityStatus.EXCLUDED,
        )
        self.assertIn(
            EligibilityBlocker.SUPPLIER_CONFIRMATION_FAILED,
            eligibility.blockers,
        )


    def test_latest_request_supersedes_older_request_globally(self):
        older_request = self.make_request(
            request_id=601,
            demand_id=1,
            supplier_id=201,
            attempt_no=1,
        )
        newer_request = self.make_request(
            request_id=602,
            demand_id=1,
            supplier_id=202,
            attempt_no=2,
        )

        snapshot = self.make_demand(
            demand_id=1,
            request_list=[older_request, newer_request],
        )   

        result = evaluate_f1_snapshots(
            [snapshot],
            cargo_compatibility_rows=self.valid_cargo_compatibility_rows(),
        )
        eligibility = result.demand_evaluations[0].eligibility

        self.assertEqual(
            eligibility.eligibility_status,
            EligibilityStatus.EXCLUDED,
        )
        self.assertIn(
            EligibilityBlocker.SUPPLIER_CONFIRMATION_FAILED,
            eligibility.blockers,
        )

    def test_out_of_scope_demand_commitment_consumes_capacity(self):
        selected_request = self.make_request(
            request_id=601,
            demand_id=1,
            demand_item_id=401,
            confirmed_weight="10",
        )
        outside_request = self.make_request(
            request_id=602,
            demand_id=2,
            demand_item_id=402,
            confirmed_weight="20",
        )

        selected_demand = self.make_demand(
            demand_id=1,
            request_list=[selected_request, outside_request],
            max_daily_supply="25",
        )

        result = self.evaluate(selected_demand)
        eligibility = result.demand_evaluations[0].eligibility

        self.assertEqual(
            eligibility.eligibility_status,
            EligibilityStatus.EXCLUDED,
        )

    def test_released_commitment_does_not_consume_capacity(self):
        request = self.make_request(
            commitment_released=True,
        )
        demand = self.make_demand(
            request_list=[request],
            max_daily_supply="10",
        )

        result = self.evaluate(demand)

        self.assertEqual(
            result.demand_evaluations[0].eligibility.eligibility_status,
            EligibilityStatus.ELIGIBLE,
        )

    def test_invalid_promise_supplier_link_excludes_demand(self):
        request = self.make_request(
            supplier_item_supplier_id=999,
        )
        demand = self.make_demand(request_list=[request])

        result = self.evaluate(demand)

        self.assertEqual(
            result.demand_evaluations[0].eligibility.eligibility_status,
            EligibilityStatus.EXCLUDED,
        )

    def test_two_eligible_demands_generate_candidate_group(self):
        request_1 = self.make_request(
            request_id=601,
            demand_id=1,
            demand_item_id=401,
        )
        request_2 = self.make_request(
            request_id=602,
            demand_id=2,
            demand_item_id=402,
        )

        all_requests = [request_1, request_2]

        demand_1 = self.make_demand(
            demand_id=1,
            request_list=all_requests,
        )
        demand_2 = self.make_demand(
            demand_id=2,
            request_list=all_requests,
        )

        result = self.evaluate(demand_1, demand_2)

        self.assertEqual(
            [
                item.eligibility.eligibility_status
                for item in result.demand_evaluations
            ],
            [
                EligibilityStatus.ELIGIBLE,
                EligibilityStatus.ELIGIBLE,
            ],
        )
        self.assertEqual(len(result.candidate_groups), 1)
        self.assertEqual(
            result.candidate_groups[0].demand_ids,
            (1, 2),
        )
