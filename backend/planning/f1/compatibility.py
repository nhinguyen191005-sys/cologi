
"""Pure F1 compatibility helpers.

These helpers do not access Django models or the database.
"""

from datetime import date, time
from typing import Iterable


PickupWindow = tuple[date, time, time]


def intersect_pickup_windows(
    windows: Iterable[PickupWindow],
) -> tuple[time, time] | None:
    """Return the common pickup-window intersection for a candidate group.

    Returns None when dates differ or there is no strict time intersection.
    Raises ValueError when a window is incomplete or invalid.
    """
    windows = list(windows)

    if len(windows) < 2:
        return None

    dates: set[date] = set()
    starts: list[time] = []
    ends: list[time] = []

    for requested_date, start, end in windows:
        if not isinstance(requested_date, date):
            raise ValueError("requested_date must be a date")

        if not isinstance(start, time) or not isinstance(end, time):
            raise ValueError("pickup start and end times are required")

        if start >= end:
            raise ValueError("pickup window start must be earlier than end")

        dates.add(requested_date)
        starts.append(start)
        ends.append(end)

    if len(dates) != 1:
        return None

    intersection_start = max(starts)
    intersection_end = min(ends)

    # Strict inequality: touching endpoints are not an overlap.
    if intersection_start >= intersection_end:
        return None

    return intersection_start, intersection_end


def pickup_windows_overlap(
    first: PickupWindow,
    second: PickupWindow,
) -> bool:
    """Check whether two Demands have a strict common pickup window."""
    return intersect_pickup_windows((first, second)) is not None
