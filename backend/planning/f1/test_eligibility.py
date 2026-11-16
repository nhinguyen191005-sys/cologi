
"""Pure unit tests for F1 eligibility orchestration."""

import unittest
from datetime import date
from decimal import Decimal

from planning.f1.capacity import (
    CapacityResult,
    CapacityStatus,
)
from planning.f1.eligibility import (
    DemandEligibilityInput,
    EligibilityBlocker,
    EligibilityDemandItem,
    EligibilityStatus,
    EvaluationStatus,
    evaluate_demand_eligibility,
)
from planning.f1.supplier_confirmation import (
    ConfirmationGateResult,
    ConfirmationGateStatus,
)


RUN_DATE = date(2026, 11, 20)


def make_confirmation(
    status=ConfirmationGateStatus.ELIGIBLE,
    diagnostics=(),
):
    return ConfirmationGateResult(
        status=status,
        failure=None,
        diagnostic_codes=diagnostics,
        confirmed_weight_by_demand_item=((101, Decimal("20")),),
        detail="test confirmation",
    )


def make_capacity(
    *,
    item_id=7,
    supplier_id=9,
    delivery_date=RUN_DATE,
    status=CapacityStatus.VERIFIED,
):
    return CapacityResult(
        status=status,
        supplier_id=supplier_id,
        supplier_item_id=50 + item_id,
        item_id=item_id,
        delivery_date=delivery_date,
        committed_weight_kg=Decimal("30"),
        max_daily_supply_kg=Decimal("100"),
        contributing_demand_ids=(10,),
        detail="test capacity",
    )


def make_source(**overrides):
    values = {
        "demand_id": 10,
        "supplier_id": 9,
        "requested_date": RUN_DATE,
        "demand_status": "SUBMITTED",
        "demand_data_valid": True,
        "supplier_active": True,
        "cargo_category_active": True,
        "demand_items": (
            EligibilityDemandItem(
                demand_item_id=101,
                item_id=7,
            ),
        ),
        "supplier_item_offers": ((7, True),),
        "confirmation": make_confirmation(),
        "capacities": (make_capacity(),),
    }
    values.update(overrides)
    return DemandEligibilityInput(**values)


class DemandEligibilityTests(unittest.TestCase):

    def test_all_f1_gates_pass(self):
        result = evaluate_demand_eligibility(make_source())

        self.assertEqual(result.eligibility_status, EligibilityStatus.ELIGIBLE)
        self.assertEqual(result.blockers, ())
        self.assertIsNone(result.primary_reason_code)

    def test_non_submitted_demand_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(demand_status="CANCELLED")
        )

        self.assertEqual(result.eligibility_status, EligibilityStatus.EXCLUDED)
        self.assertIn(
            EligibilityBlocker.DEMAND_NOT_SUBMITTED,
            result.blockers,
        )

    def test_invalid_demand_data_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(demand_data_valid=False)
        )

        self.assertIn(
            EligibilityBlocker.DEMAND_DATA_INVALID,
            result.blockers,
        )

    def test_inactive_supplier_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(supplier_active=False)
        )

        self.assertIn(
            EligibilityBlocker.SUPPLIER_INACTIVE,
            result.blockers,
        )

    def test_inactive_cargo_category_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(cargo_category_active=False)
        )

        self.assertIn(
            EligibilityBlocker.CARGO_CATEGORY_INACTIVE,
            result.blockers,
        )

    def test_missing_or_inactive_supplier_offer_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(supplier_item_offers=((7, False),))
        )

        self.assertIn(
            EligibilityBlocker.SUPPLIER_OFFER_INACTIVE,
            result.blockers,
        )

    def test_confirmation_failure_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(
                confirmation=make_confirmation(
                    ConfirmationGateStatus.EXCLUDED
                )
            )
        )

        self.assertIn(
            EligibilityBlocker.SUPPLIER_CONFIRMATION_FAILED,
            result.blockers,
        )

    def test_missing_capacity_result_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(capacities=())
        )

        self.assertIn(
            EligibilityBlocker.CAPACITY_RESULT_MISSING,
            result.blockers,
        )

    def test_unverified_capacity_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(
                capacities=(make_capacity(status=CapacityStatus.UNVERIFIED),)
            )
        )

        self.assertIn(
            EligibilityBlocker.CAPACITY_UNVERIFIED,
            result.blockers,
        )

    def test_exceeded_capacity_is_excluded(self):
        result = evaluate_demand_eligibility(
            make_source(
                capacities=(make_capacity(status=CapacityStatus.EXCEEDED),)
            )
        )

        self.assertIn(
            EligibilityBlocker.CAPACITY_EXCEEDED,
            result.blockers,
        )

    def test_capacity_for_wrong_supplier_is_invalid(self):
        result = evaluate_demand_eligibility(
            make_source(
                capacities=(make_capacity(supplier_id=77),)
            )
        )

        self.assertIn(
            EligibilityBlocker.INPUT_INCONSISTENT,
            result.blockers,
        )

    def test_capacity_for_wrong_date_is_invalid(self):
        result = evaluate_demand_eligibility(
            make_source(
                capacities=(
                    make_capacity(
                        delivery_date=date(2026, 11, 21)
                    ),
                )
            )
        )

        self.assertIn(
            EligibilityBlocker.INPUT_INCONSISTENT,
            result.blockers,
        )

    def test_partial_confirmation_diagnostic_is_preserved(self):
        result = evaluate_demand_eligibility(
            make_source(
                confirmation=make_confirmation(
                    diagnostics=("CONFIRMATION_STATUS_INCONSISTENT",)
                )
            )
        )

        self.assertEqual(result.eligibility_status, EligibilityStatus.ELIGIBLE)
        self.assertEqual(
            result.diagnostics,
            ("CONFIRMATION_STATUS_INCONSISTENT",),
        )

    def test_plan_guard_and_matching_remain_independent(self):
        result = evaluate_demand_eligibility(make_source())

        self.assertEqual(
            result.plan_guard_status,
            EvaluationStatus.NOT_EVALUATED,
        )
        self.assertEqual(
            result.matching_status,
            EvaluationStatus.NOT_EVALUATED,
        )

    def test_multiple_items_require_offer_and_capacity_for_each(self):
        requirements = (
            EligibilityDemandItem(101, 7),
            EligibilityDemandItem(102, 8),
        )

        result = evaluate_demand_eligibility(
            make_source(
                demand_items=requirements,
                supplier_item_offers=((7, True), (8, True)),
                capacities=(make_capacity(item_id=7),),
            )
        )

        self.assertIn(
            EligibilityBlocker.CAPACITY_RESULT_MISSING,
            result.blockers,
        )

    def test_duplicate_item_in_input_is_invalid(self):
        requirements = (
            EligibilityDemandItem(101, 7),
            EligibilityDemandItem(102, 7),
        )

        result = evaluate_demand_eligibility(
            make_source(demand_items=requirements)
        )

        self.assertIn(
            EligibilityBlocker.INPUT_INCONSISTENT,
            result.blockers,
        )


if __name__ == "__main__":
    unittest.main()
