"""Pure unit tests for the F1 supplier-capacity engine."""

import unittest
from datetime import date
from decimal import Decimal

from planning.f1.capacity import (
    CapacityStatus,
    PromiseCommitment,
    SupplierItemCapacity,
    SupplierRequestCommitment,
    evaluate_supplier_item_capacity,
)


DELIVERY_DATE = date(2026, 11, 20)


def make_promise(
    *,
    quantity="10",
    line_status="CONFIRMED",
    demand_item_id=100,
    item_id=7,
    links_valid=True,
):
    return PromiseCommitment(
        supplier_item_id=50,
        item_id=item_id,
        demand_item_id=demand_item_id,
        confirmed_weight_kg=Decimal(quantity),
        line_status=line_status,
        links_valid=links_valid,
    )


def make_request(
    *,
    request_id,
    demand_id,
    attempt_no=1,
    request_status="RESPONDED",
    confirmation_status="CONFIRMED",
    released=False,
    quantity="10",
    line_status="CONFIRMED",
    requested_date=DELIVERY_DATE,
    demand_status="SUBMITTED",
):
    return SupplierRequestCommitment(
        request_id=request_id,
        demand_id=demand_id,
        supplier_id=9,
        attempt_no=attempt_no,
        requested_date=requested_date,
        request_status=request_status,
        confirmation_status=confirmation_status,
        commitment_released=released,
        promises=(
            make_promise(
                quantity=quantity,
                line_status=line_status,
                demand_item_id=demand_id * 100,
            ),
        ),
        demand_status=demand_status,
    )


def make_supplier_item(maximum="100"):
    return SupplierItemCapacity(
        supplier_item_id=50,
        supplier_id=9,
        item_id=7,
        max_daily_supply_kg=(
            None if maximum is None else Decimal(maximum)
        ),
    )


class SupplierCapacityTests(unittest.TestCase):
    def test_invalid_link_is_checked_before_item_mismatch_is_skipped(self):
        request = make_request(
            request_id=1,
            demand_id=1,
            quantity="20",
        )

        invalid_promise = make_promise(
            quantity="20",
            demand_item_id=100,
            item_id=8,
            links_valid=False,
        )

        request = SupplierRequestCommitment(
            request_id=request.request_id,
            demand_id=request.demand_id,
            supplier_id=request.supplier_id,
            attempt_no=request.attempt_no,
            requested_date=request.requested_date,
            request_status=request.request_status,
            confirmation_status=request.confirmation_status,
            commitment_released=request.commitment_released,
            promises=(invalid_promise,),
            demand_status=request.demand_status,
        )

        result = self.evaluate([request])

        self.assertEqual(result.status, CapacityStatus.INVALID_INPUT)

    def evaluate(self, requests, maximum="100"):
        return evaluate_supplier_item_capacity(
            supplier_item=make_supplier_item(maximum),
            delivery_date=DELIVERY_DATE,
            requests=requests,
        )

    def test_aggregates_commitments_across_demands(self):
        result = self.evaluate([
            make_request(request_id=1, demand_id=1, quantity="40"),
            make_request(request_id=2, demand_id=2, quantity="35"),
        ])

        self.assertEqual(result.status, CapacityStatus.VERIFIED)
        self.assertEqual(result.committed_weight_kg, Decimal("75"))
        self.assertEqual(result.contributing_demand_ids, (1, 2))

    def test_exceeded_capacity_is_not_verified(self):
        result = self.evaluate([
            make_request(request_id=1, demand_id=1, quantity="60"),
            make_request(request_id=2, demand_id=2, quantity="50"),
        ])

        self.assertEqual(result.status, CapacityStatus.EXCEEDED)
        self.assertEqual(result.committed_weight_kg, Decimal("110"))

    def test_null_capacity_is_unverified_not_unlimited(self):
        result = self.evaluate([
            make_request(request_id=1, demand_id=1, quantity="10"),
        ], maximum=None)

        self.assertEqual(result.status, CapacityStatus.UNVERIFIED)
        self.assertEqual(result.committed_weight_kg, Decimal("10"))

    def test_unreleased_partial_confirmation_consumes_capacity(self):
        result = self.evaluate([
            make_request(
                request_id=1,
                demand_id=1,
                confirmation_status="PARTIAL",
                quantity="30",
                line_status="PARTIAL",
            ),
        ])

        self.assertEqual(result.status, CapacityStatus.VERIFIED)
        self.assertEqual(result.committed_weight_kg, Decimal("30"))

    def test_released_partial_confirmation_does_not_consume_capacity(self):
        result = self.evaluate([
            make_request(
                request_id=1,
                demand_id=1,
                confirmation_status="PARTIAL",
                released=True,
                quantity="30",
                line_status="PARTIAL",
            ),
        ])

        self.assertEqual(result.status, CapacityStatus.VERIFIED)
        self.assertEqual(result.committed_weight_kg, Decimal("0"))
        self.assertEqual(result.contributing_demand_ids, ())

    def test_cancelled_demand_still_consumes_unreleased_commitment(self):
        result = self.evaluate([
            make_request(
                request_id=1,
                demand_id=1,
                quantity="30",
                demand_status="CANCELLED",
            ),
        ])

        self.assertEqual(result.status, CapacityStatus.VERIFIED)
        self.assertEqual(result.committed_weight_kg, Decimal("30"))
        self.assertEqual(result.contributing_demand_ids, (1,))

    def test_only_latest_request_attempt_is_counted(self):
        result = self.evaluate([
            make_request(
                request_id=1,
                demand_id=1,
                attempt_no=1,
                quantity="80",
            ),
            make_request(
                request_id=2,
                demand_id=1,
                attempt_no=2,
                quantity="25",
            ),
        ])

        self.assertEqual(result.status, CapacityStatus.VERIFIED)
        self.assertEqual(result.committed_weight_kg, Decimal("25"))

    def test_latest_waiting_attempt_supersedes_old_confirmation(self):
        result = self.evaluate([
            make_request(
                request_id=1,
                demand_id=1,
                attempt_no=1,
                quantity="80",
            ),
            make_request(
                request_id=2,
                demand_id=1,
                attempt_no=2,
                request_status="WAITING",
                confirmation_status="PENDING",
                quantity="0",
                line_status="PENDING",
            ),
        ])

        self.assertEqual(result.status, CapacityStatus.VERIFIED)
        self.assertEqual(result.committed_weight_kg, Decimal("0"))

    def test_other_delivery_date_does_not_consume_this_date_capacity(self):
        result = self.evaluate([
            make_request(
                request_id=1,
                demand_id=1,
                quantity="80",
                requested_date=date(2026, 11, 21),
            ),
        ])

        self.assertEqual(result.status, CapacityStatus.VERIFIED)
        self.assertEqual(result.committed_weight_kg, Decimal("0"))

    def test_invalid_commitment_link_stops_capacity_evaluation(self):
        request = make_request(
            request_id=1,
            demand_id=1,
            quantity="20",
        )
        invalid_promise = make_promise(
            quantity="20",
            demand_item_id=100,
            links_valid=False,
        )
        request = SupplierRequestCommitment(
            request_id=request.request_id,
            demand_id=request.demand_id,
            supplier_id=request.supplier_id,
            attempt_no=request.attempt_no,
            requested_date=request.requested_date,
            request_status=request.request_status,
            confirmation_status=request.confirmation_status,
            commitment_released=request.commitment_released,
            promises=(invalid_promise,),
            demand_status=request.demand_status,
        )

        result = self.evaluate([request])

        self.assertEqual(result.status, CapacityStatus.INVALID_INPUT)


if __name__ == "__main__":
    unittest.main()
