
from datetime import date, time

from django.test import SimpleTestCase

from planning.f1.compatibility import (
    intersect_pickup_windows,
    pickup_windows_overlap,
)


class PickupWindowCompatibilityTests(SimpleTestCase):
    def setUp(self):
        self.day = date(2026, 11, 20)

    def test_overlapping_windows_are_compatible(self):
        first = (self.day, time(8, 0), time(11, 0))
        second = (self.day, time(9, 0), time(12, 0))

        self.assertTrue(pickup_windows_overlap(first, second))

    def test_touching_endpoints_are_not_compatible(self):
        first = (self.day, time(8, 0), time(9, 0))
        second = (self.day, time(9, 0), time(12, 0))

        self.assertFalse(pickup_windows_overlap(first, second))

    def test_different_dates_are_not_compatible(self):
        first = (self.day, time(8, 0), time(11, 0))
        second = (date(2026, 11, 21), time(9, 0), time(12, 0))

        self.assertFalse(pickup_windows_overlap(first, second))

    def test_group_intersection_returns_common_window(self):
        windows = [
            (self.day, time(8, 0), time(12, 0)),
            (self.day, time(9, 0), time(11, 0)),
            (self.day, time(9, 30), time(13, 0)),
        ]

        self.assertEqual(
            intersect_pickup_windows(windows),
            (time(9, 30), time(11, 0)),
        )

    def test_pairwise_overlap_does_not_guarantee_group_intersection(self):
        windows = [
            (self.day, time(8, 0), time(10, 0)),
            (self.day, time(9, 0), time(11, 0)),
            (self.day, time(10, 30), time(12, 0)),
        ]

        self.assertIsNone(intersect_pickup_windows(windows))

    def test_invalid_window_raises_value_error(self):
        windows = [
            (self.day, time(11, 0), time(8, 0)),
            (self.day, time(9, 0), time(12, 0)),
        ]

        with self.assertRaises(ValueError):
            intersect_pickup_windows(windows)
