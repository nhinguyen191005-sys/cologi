"""Pure F1 Demand pickup-window validation.

This module deliberately uses only DeliveryDemand's requested date/time.
SupplierConfirmation.ready_start_time and ready_end_time are not inputs.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Iterable


class WindowStatus(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    INVALID = "INVALID"


class IntersectionStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    NOT_ENOUGH_DEMANDS = "NOT_ENOUGH_DEMANDS"
    MISSING_WINDOW = "MISSING_WINDOW"
    INVALID_WINDOW = "INVALID_WINDOW"
    DIFFERENT_DATES = "DIFFERENT_DATES"
    NO_COMMON_OVERLAP = "NO_COMMON_OVERLAP"


@dataclass(frozen=True)
class DemandPickupWindow:
    requested_date: date
    requested_start_time: time
    requested_end_time: time


@dataclass(frozen=True)
class WindowValidation:
    status: WindowStatus
    window: DemandPickupWindow | None = None


@dataclass(frozen=True)
class IntersectionResult:
    status: IntersectionStatus
    requested_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None


def validate_demand_pickup_window(
    requested_date: date | None,
    requested_start_time: time | None,
    requested_end_time: time | None,
) -> WindowValidation:
    """Validate only the pickup/receiving window requested by the Demand."""
    if requested_start_time is None or requested_end_time is None:
        return WindowValidation(status=WindowStatus.MISSING)

    # datetime is a subclass of date, but is not a valid requested_date value.
    if (
        not isinstance(requested_date, date)
        or isinstance(requested_date, datetime)
        or not isinstance(requested_start_time, time)
        or not isinstance(requested_end_time, time)
    ):
        return WindowValidation(status=WindowStatus.INVALID)

    try:
        if requested_start_time >= requested_end_time:
            return WindowValidation(status=WindowStatus.INVALID)
    except TypeError:
        # For example, comparing incompatible timezone-aware and naive times.
        return WindowValidation(status=WindowStatus.INVALID)

    return WindowValidation(
        status=WindowStatus.VALID,
        window=DemandPickupWindow(
            requested_date=requested_date,
            requested_start_time=requested_start_time,
            requested_end_time=requested_end_time,
        ),
    )


def find_common_demand_pickup_window(
    windows: Iterable[
        tuple[date | None, time | None, time | None]
    ],
) -> IntersectionResult:
    """Find a strict common time intersection for two or more Demands.

    Every tuple must contain:
        (DeliveryDemand.requested_date,
         DeliveryDemand.requested_start_time,
         DeliveryDemand.requested_end_time)

    Supplier readiness times must never be passed to this function.
    """
    raw_windows = list(windows)

    if len(raw_windows) < 2:
        return IntersectionResult(
            status=IntersectionStatus.NOT_ENOUGH_DEMANDS
        )

    validated: list[DemandPickupWindow] = []

    for requested_date, start_time, end_time in raw_windows:
        result = validate_demand_pickup_window(
            requested_date=requested_date,
            requested_start_time=start_time,
            requested_end_time=end_time,
        )

        if result.status is WindowStatus.MISSING:
            return IntersectionResult(
                status=IntersectionStatus.MISSING_WINDOW
            )

        if result.status is WindowStatus.INVALID or result.window is None:
            return IntersectionResult(
                status=IntersectionStatus.INVALID_WINDOW
            )

        validated.append(result.window)

    dates = {window.requested_date for window in validated}
    if len(dates) != 1:
        return IntersectionResult(
            status=IntersectionStatus.DIFFERENT_DATES
        )

    common_start = max(
        window.requested_start_time for window in validated
    )
    common_end = min(
        window.requested_end_time for window in validated
    )

    # Strict overlap: touching endpoints do not constitute an intersection.
    if common_start >= common_end:
        return IntersectionResult(
            status=IntersectionStatus.NO_COMMON_OVERLAP
        )

    return IntersectionResult(
        status=IntersectionStatus.COMPATIBLE,
        requested_date=validated[0].requested_date,
        start_time=common_start,
        end_time=common_end,
    )