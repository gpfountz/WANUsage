from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DateWindow:
    """A half-open date range that includes ``start_date`` but excludes ``end_date``."""

    start_date: date
    end_date: date


def calculate_last_7_completed_days(today: date) -> DateWindow:
    """Return the seven completed calendar days immediately before ``today``."""

    return calculate_completed_days(today, 7)


def calculate_completed_days(today: date, day_count: int) -> DateWindow:
    """Return a window containing ``day_count`` completed days before ``today``."""

    end_date: date = today
    start_date: date = end_date - timedelta(days=day_count)
    return DateWindow(start_date=start_date, end_date=end_date)


def calculate_current_day(today: date) -> DateWindow:
    """Return the one-day window beginning on ``today``."""

    return DateWindow(start_date=today, end_date=today + timedelta(days=1))


def estimate_period_usage(total_bytes: int, window: DateWindow, today: date) -> int:
    """Project a full-period byte total from usage through ``today``.

    The estimate uses elapsed calendar days, counts the current day as elapsed,
    and rounds to the nearest whole byte. Dates outside the supplied window are
    clamped so the divisor remains between one day and the full period length.
    """

    period_days: int = (window.end_date - window.start_date).days
    elapsed_days: int = min(max((today - window.start_date).days + 1, 1), period_days)
    projected_bytes: int = total_bytes * period_days
    return (projected_bytes + elapsed_days // 2) // elapsed_days


def calculate_current_billing_window(today: date, cycle_day: int) -> DateWindow:
    """Return the billing window containing ``today``.

    A cycle begins on ``cycle_day``. When that day does not exist in a month,
    the boundary is clamped to the month's final day.
    """

    current_month_boundary: date = _billing_boundary(today.year, today.month, cycle_day)

    if today >= current_month_boundary:
        start_date: date = current_month_boundary
        next_year, next_month = _shift_month(today.year, today.month, 1)
        end_date: date = _billing_boundary(next_year, next_month, cycle_day)
    else:
        end_date = current_month_boundary
        previous_year, previous_month = _shift_month(today.year, today.month, -1)
        start_date = _billing_boundary(previous_year, previous_month, cycle_day)

    return DateWindow(start_date=start_date, end_date=end_date)


def calculate_previous_billing_window(today: date, cycle_day: int) -> DateWindow:
    """Return the billing window immediately preceding the window containing ``today``."""

    current_window: DateWindow = calculate_current_billing_window(today, cycle_day)
    previous_year, previous_month = _shift_month(
        current_window.start_date.year,
        current_window.start_date.month,
        -1,
    )
    start_date: date = _billing_boundary(previous_year, previous_month, cycle_day)
    return DateWindow(start_date=start_date, end_date=current_window.start_date)


def calculate_billing_windows(
    today: date,
    month_count: int,
    cycle_day: int,
) -> tuple[DateWindow, ...]:
    """Return ``month_count`` consecutive billing windows, oldest first."""

    current_window: DateWindow = calculate_current_billing_window(today, cycle_day)
    windows: list[DateWindow] = [current_window]

    while len(windows) < month_count:
        end_date: date = windows[-1].start_date
        previous_year, previous_month = _shift_month(end_date.year, end_date.month, -1)
        start_date: date = _billing_boundary(previous_year, previous_month, cycle_day)
        windows.append(DateWindow(start_date=start_date, end_date=end_date))

    return tuple(reversed(windows))


def _billing_boundary(year: int, month: int, cycle_day: int) -> date:
    """Resolve a configured cycle day to a valid boundary in a specific month."""

    last_day: int = monthrange(year, month)[1]
    return date(year, month, min(cycle_day, last_day))


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    """Shift a year and month by ``offset`` months, including across year boundaries."""

    month_index: int = year * 12 + month - 1 + offset
    return divmod(month_index, 12)[0], divmod(month_index, 12)[1] + 1
