
"""Unit tests for pure F1 Candidate Group generation."""

import unittest
from datetime import date, time

from planning.f1.candidate_groups import (
    CandidateDemandInput,
    generate_candidate_groups,
)
from planning.f1.eligibility import EligibilityStatus

from planning.f1.cargo_compatibility import (
    dataset_v7_cargo_compatibility_rows,
    normalize_cargo_compatibility_matrix,
)
class CandidateGroupTests(unittest.TestCase):
    def setUp(self):
        self.delivery_date = date(2026, 11, 20)
        self.cargo_compatibility_matrix = (
            normalize_cargo_compatibility_matrix(
                dataset_v7_cargo_compatibility_rows()
            )
        )

    def generate(self, demands):
        return generate_candidate_groups(
            demands,
            cargo_compatibility_matrix=self.cargo_compatibility_matrix,
        )

    def demand(
        self,
        demand_id,
        start=time(8, 0),
        end=time(12, 0),
        *,
        status=EligibilityStatus.ELIGIBLE,
        requested_date=None,
        cargo_category_id=1,
        outlet_id=None,
    ):
        return CandidateDemandInput(
            demand_id=demand_id,
            outlet_id=outlet_id if outlet_id is not None else demand_id,
            eligibility_status=status,
            requested_date=(
                requested_date
                if requested_date is not None
                else self.delivery_date
            ),
            cargo_category_id=cargo_category_id,
            requested_start_time=start,
            requested_end_time=end,
            
        )

    def test_generates_all_combinations_not_only_maximal_groups(self):
        demands = [
            self.demand(1),
            self.demand(2),
            self.demand(3),
        ]

        groups = self.generate(demands)

        self.assertEqual(
            [group.demand_ids for group in groups],
            [
                (1, 2),
                (1, 3),
                (2, 3),
                (1, 2, 3),
            ],
        )

    def test_demand_can_appear_in_multiple_candidate_groups(self):
        demands = [
            self.demand(1),
            self.demand(2),
            self.demand(3),
        ]

        groups = self.generate(demands)

        appearances = [
            group.demand_ids.count(1)
            for group in groups
        ]

        self.assertGreater(sum(appearances), 1)

    def test_only_eligible_demands_are_grouped(self):
        demands = [
            self.demand(1),
            self.demand(
                2,
                status=EligibilityStatus.EXCLUDED,
            ),
            self.demand(3),
        ]

        groups = self.generate(demands)

        self.assertEqual(
            [group.demand_ids for group in groups],
            [(1, 3)],
        )

    def test_different_dates_are_not_grouped(self):
        demands = [
            self.demand(1),
            self.demand(
                2,
                requested_date=date(2026, 11, 21),
            ),
        ]

        self.assertEqual(self.generate(demands), ())

    def test_different_cargo_categories_are_not_grouped(self):
        demands = [
            self.demand(1, cargo_category_id=1),
            self.demand(2, cargo_category_id=2),
        ]

        self.assertEqual(self.generate(demands), ())

    def test_missing_demand_window_excludes_demand_from_grouping(self):
        demands = [
            self.demand(1),
            self.demand(2, start=None),
            self.demand(3),
        ]

        groups = self.generate(demands)

        self.assertEqual(
            [group.demand_ids for group in groups],
            [(1, 3)],
        )

    def test_invalid_demand_window_excludes_demand_from_grouping(self):
        demands = [
            self.demand(
                1,
                start=time(12, 0),
                end=time(8, 0),
            ),
            self.demand(2),
            self.demand(3),
        ]

        groups = self.generate(demands)

        self.assertEqual(
            [group.demand_ids for group in groups],
            [(2, 3)],
        )

    def test_touching_endpoints_are_not_overlap(self):
        demands = [
            self.demand(
                1,
                start=time(8, 0),
                end=time(10, 0),
            ),
            self.demand(
                2,
                start=time(10, 0),
                end=time(12, 0),
            ),
        ]

        self.assertEqual(self.generate(demands), ())

    def test_common_intersection_is_calculated_for_entire_group(self):
        # Every pair overlaps, but all three do not share one common window.
        demands = [
            self.demand(
                1,
                start=time(8, 0),
                end=time(10, 0),
            ),
            self.demand(
                2,
                start=time(9, 0),
                end=time(11, 0),
            ),
            self.demand(
                3,
                start=time(10, 0),
                end=time(12, 0),
            ),
        ]

        groups = self.generate(demands)

        self.assertEqual(
            [group.demand_ids for group in groups],
            [(1, 2), (2, 3)],
        )

    def test_common_intersection_values_are_returned(self):
        demands = [
            self.demand(
                1,
                start=time(8, 0),
                end=time(11, 0),
            ),
            self.demand(
                2,
                start=time(9, 0),
                end=time(12, 0),
            ),
            self.demand(
                3,
                start=time(9, 30),
                end=time(10, 30),
            ),
        ]

        groups = self.generate(demands)

        triple = next(
            group
            for group in groups
            if group.demand_ids == (1, 2, 3)
        )

        self.assertEqual(triple.common_start_time, time(9, 30))
        self.assertEqual(triple.common_end_time, time(10, 30))

    def test_single_demand_does_not_create_group(self):
        self.assertEqual(
            self.generate([self.demand(1)]),
            (),
        )

    def test_output_is_deterministic_regardless_of_input_order(self):
        demands = [
            self.demand(3),
            self.demand(1),
            self.demand(2),
        ]

        first = self.generate(demands)
        second = self.generate(reversed(demands))

        self.assertEqual(first, second)

    def test_duplicate_demand_ids_raise_value_error(self):
        demands = [
            self.demand(1),
            self.demand(1),
        ]

        with self.assertRaises(ValueError):
            self.generate(demands)

    def test_invalid_demand_id_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.generate([self.demand(0)])

    def test_invalid_cargo_category_id_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.generate([
                self.demand(1, cargo_category_id=0)
            ])

    def test_empty_input_returns_no_groups(self):
        self.assertEqual(self.generate([]), ())

    def test_same_outlet_demands_do_not_form_candidate_group(self):
        demands = [
            self.demand(1, outlet_id=10),
            self.demand(2, outlet_id=10),
            self.demand(3, outlet_id=10),
        ]

        self.assertEqual(self.generate(demands), ())

    def test_candidate_group_requires_two_distinct_outlets(self):
        demands = [
            self.demand(1, outlet_id=10),
            self.demand(2, outlet_id=10),
            self.demand(3, outlet_id=20),
        ]

        groups = self.generate(demands)

        self.assertEqual(
            [group.demand_ids for group in groups],
            [(1, 3), (2, 3), (1, 2, 3)],
        )


if __name__ == "__main__":
    unittest.main()
