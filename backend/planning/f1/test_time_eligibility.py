import unittest
from datetime import date, time

from .time_eligibility import (
    IntersectionStatus,
    WindowStatus,
    find_common_demand_pickup_window,
    validate_demand_pickup_window,
)


class DemandPickupWindowTests(unittest.TestCase):
    def test_complete_valid_window(self):
        result = validate_demand_pickup_window(
            date(2026, 11, 17),
            time(8, 0),
            time(10, 0),
        )

        self.assertIs(result.status, WindowStatus.VALID)
        self.assertIsNotNone(result.window)

    def test_missing_start_time_is_not_eligible_for_grouping(self):
        result = validate_demand_pickup_window(
            date(2026, 11, 17),
            None,
            time(10, 0),
        )

        self.assertIs(result.status, WindowStatus.MISSING)

    def test_missing_end_time_is_not_eligible_for_grouping(self):
        result = validate_demand_pickup_window(
            date(2026, 11, 17),
            time(8, 0),
            None,
        )

        self.assertIs(result.status, WindowStatus.MISSING)

    def test_invalid_reversed_window(self):
        result = validate_demand_pickup_window(
            date(2026, 11, 17),
            time(10, 0),
            time(8, 0),
        )

        self.assertIs(result.status, WindowStatus.INVALID)

    def test_common_intersection_for_two_demands(self):
        result = find_common_demand_pickup_window([
            (date(2026, 11, 17), time(8, 0), time(12, 0)),
            (date(2026, 11, 17), time(9, 0), time(11, 0)),
        ])

        self.assertIs(result.status, IntersectionStatus.COMPATIBLE)
        self.assertEqual(result.start_time, time(9, 0))
        self.assertEqual(result.end_time, time(11, 0))

    def test_three_demands_need_one_common_intersection(self):
        result = find_common_demand_pickup_window([
            (date(2026, 11, 17), time(8, 0), time(10, 0)),
            (date(2026, 11, 17), time(9, 0), time(11, 0)),
            (date(2026, 11, 17), time(10, 30), time(12, 0)),
        ])

        self.assertIs(
            result.status,
            IntersectionStatus.NO_COMMON_OVERLAP,
        )

    def test_touching_endpoints_are_not_overlap(self):
        result = find_common_demand_pickup_window([
            (date(2026, 11, 17), time(8, 0), time(9, 0)),
            (date(2026, 11, 17), time(9, 0), time(10, 0)),
        ])

        self.assertIs(
            result.status,
            IntersectionStatus.NO_COMMON_OVERLAP,
        )

    def test_different_dates_are_not_compatible(self):
        result = find_common_demand_pickup_window([
            (date(2026, 11, 17), time(8, 0), time(10, 0)),
            (date(2026, 11, 18), time(8, 0), time(10, 0)),
        ])

        self.assertIs(
            result.status,
            IntersectionStatus.DIFFERENT_DATES,
        )

    def test_missing_window_blocks_the_whole_candidate_group(self):
        result = find_common_demand_pickup_window([
            (date(2026, 11, 17), time(8, 0), time(10, 0)),
            (date(2026, 11, 17), None, time(10, 0)),
        ])

        self.assertIs(
            result.status,
            IntersectionStatus.MISSING_WINDOW,
        )

    def test_single_demand_cannot_form_a_candidate_group(self):
        result = find_common_demand_pickup_window([
            (date(2026, 11, 17), time(8, 0), time(10, 0)),
        ])

        self.assertIs(
            result.status,
            IntersectionStatus.NOT_ENOUGH_DEMANDS,
        )


if __name__ == "__main__":
    unittest.main()