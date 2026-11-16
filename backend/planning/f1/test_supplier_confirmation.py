
"""Pure unit tests for F1 Supplier Confirmation Gate."""

import unittest
from dataclasses import replace
from decimal import Decimal

from planning.f1.supplier_confirmation import (
    ConfirmationFailure,
    ConfirmationGateStatus,
    DemandItemRequirement,
    PromiseLine,
    SupplierResponseSnapshot,
    evaluate_supplier_confirmation,
)


def make_requirement(
    demand_item_id=101,
    *,
    demand_id=10,
    item_id=7,
    required="20",
):
    return DemandItemRequirement(
        demand_item_id=demand_item_id,
        demand_id=demand_id,
        item_id=item_id,
        required_weight_kg=Decimal(required),
    )


def make_promise(
    demand_item_id=101,
    *,
    request_id=500,
    demand_id=10,
    supplier_id=9,
    item_id=7,
    promised="20",
    confirmed="20",
    line_status="CONFIRMED",
    promise_id=900,
    links_valid=True,
):
    return PromiseLine(
        promise_id=promise_id,
        supplier_request_id=request_id,
        demand_id=demand_id,
        supplier_id=supplier_id,
        demand_item_id=demand_item_id,
        item_id=item_id,
        promised_weight_kg=Decimal(promised),
        confirmed_weight_kg=Decimal(confirmed),
        line_status=line_status,
        links_valid=links_valid,
    )


def make_response(
    *,
    request_status="RESPONDED",
    confirmation_status="CONFIRMED",
    demand_items=None,
    promises=None,
    demand_supplier_id=9,
    request_supplier_id=9,
):
    if demand_items is None:
        demand_items = (make_requirement(),)
    if promises is None:
        promises = (make_promise(),)

    return SupplierResponseSnapshot(
        supplier_request_id=500,
        demand_id=10,
        demand_supplier_id=demand_supplier_id,
        request_supplier_id=request_supplier_id,
        request_status=request_status,
        confirmation_status=confirmation_status,
        demand_items=tuple(demand_items),
        promises=tuple(promises),
    )


class SupplierConfirmationGateTests(unittest.TestCase):

    def test_confirmed_confirmation_with_full_promises_is_eligible(self):
        result = evaluate_supplier_confirmation(make_response())

        self.assertEqual(result.status, ConfirmationGateStatus.ELIGIBLE)
        self.assertIsNone(result.failure)
        self.assertEqual(result.diagnostic_codes, ())
        self.assertEqual(
            result.confirmed_weight_by_demand_item,
            ((101, Decimal("20")),),
        )

    def test_partial_confirmation_exception_is_eligible_with_diagnostic(self):
        response = make_response(confirmation_status="PARTIAL")

        result = evaluate_supplier_confirmation(response)

        self.assertEqual(result.status, ConfirmationGateStatus.ELIGIBLE)
        self.assertEqual(
            result.diagnostic_codes,
            ("CONFIRMATION_STATUS_INCONSISTENT",),
        )

    def test_missing_promise_uses_promise_missing(self):
        response = make_response(promises=())

        result = evaluate_supplier_confirmation(response)

        self.assertEqual(result.status, ConfirmationGateStatus.EXCLUDED)
        self.assertEqual(
            result.failure,
            ConfirmationFailure.PROMISE_MISSING,
        )

    def test_insufficient_confirmed_quantity_uses_promise_insufficient(self):
        promise = make_promise(
            promised="20",
            confirmed="15",
            line_status="PARTIAL",
        )

        result = evaluate_supplier_confirmation(
            make_response(promises=(promise,))
        )

        self.assertEqual(result.status, ConfirmationGateStatus.EXCLUDED)
        self.assertEqual(
            result.failure,
            ConfirmationFailure.PROMISE_INSUFFICIENT,
        )

    def test_confirmed_quantity_must_cover_required_quantity(self):
        promise = make_promise(
            promised="18",
            confirmed="18",
            line_status="CONFIRMED",
        )

        result = evaluate_supplier_confirmation(
            make_response(promises=(promise,))
        )

        self.assertEqual(result.status, ConfirmationGateStatus.EXCLUDED)
        self.assertEqual(
            result.failure,
            ConfirmationFailure.PROMISE_INSUFFICIENT,
        )

    def test_duplicate_promises_for_one_demand_item_are_invalid(self):
        first = make_promise(promise_id=900)
        second = make_promise(promise_id=901)

        result = evaluate_supplier_confirmation(
            make_response(promises=(first, second))
        )

        self.assertEqual(result.status, ConfirmationGateStatus.INVALID_INPUT)
        self.assertEqual(
            result.failure,
            ConfirmationFailure.DUPLICATE_PROMISE,
        )

    def test_promise_for_unexpected_demand_item_is_invalid(self):
        unexpected = make_promise(demand_item_id=999)

        result = evaluate_supplier_confirmation(
            make_response(promises=(unexpected,))
        )

        self.assertEqual(result.status, ConfirmationGateStatus.INVALID_INPUT)
        self.assertEqual(
            result.failure,
            ConfirmationFailure.UNEXPECTED_PROMISE,
        )

    def test_supplier_mismatch_is_invalid(self):
        response = make_response(request_supplier_id=11)

        result = evaluate_supplier_confirmation(response)

        self.assertEqual(result.status, ConfirmationGateStatus.INVALID_INPUT)
        self.assertEqual(
            result.failure,
            ConfirmationFailure.INVALID_PROMISE_LINK,
        )

    def test_latest_request_must_be_responded(self):
        response = make_response(
            request_status="WAITING",
            confirmation_status="PENDING",
        )

        result = evaluate_supplier_confirmation(response)

        self.assertEqual(result.status, ConfirmationGateStatus.NOT_RESPONDED)

    def test_multiple_demand_items_must_all_be_fully_confirmed(self):
        requirements = (
            make_requirement(101, required="20"),
            make_requirement(102, required="30"),
        )
        promises = (
            make_promise(
                101,
                promised="20",
                confirmed="20",
                line_status="CONFIRMED",
                promise_id=900,
            ),
            make_promise(
                102,
                promised="30",
                confirmed="25",
                line_status="PARTIAL",
                promise_id=901,
            ),
        )

        result = evaluate_supplier_confirmation(
            make_response(
                demand_items=requirements,
                promises=promises,
            )
        )

        self.assertEqual(result.status, ConfirmationGateStatus.EXCLUDED)
        self.assertEqual(
            result.failure,
            ConfirmationFailure.PROMISE_INSUFFICIENT,
        )


if __name__ == "__main__":
    unittest.main()
