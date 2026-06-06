from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DateWindow:
    start_date: date
    end_date: date


def calculate_last_7_completed_days(today: date) -> DateWindow:
    return calculate_completed_days(today, 7)


def calculate_completed_days(today: date, day_count: int) -> DateWindow:
    end_date: date = today
    start_date: date = end_date - timedelta(days=day_count)
    return DateWindow(start_date=start_date, end_date=end_date)


def calculate_current_day(today: date) -> DateWindow:
    return DateWindow(start_date=today, end_date=today + timedelta(days=1))


def estimate_period_usage(total_bytes: int, window: DateWindow, today: date) -> int:
    period_days: int = (window.end_date - window.start_date).days
    elapsed_days: int = min(max((today - window.start_date).days + 1, 1), period_days)
    projected_bytes: int = total_bytes * period_days
    return (projected_bytes + elapsed_days // 2) // elapsed_days


def calculate_current_billing_window(today: date, cycle_day: int) -> DateWindow:
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
    current_window: DateWindow = calculate_current_billing_window(today, cycle_day)
    windows: list[DateWindow] = [current_window]

    while len(windows) < month_count:
        end_date: date = windows[-1].start_date
        previous_year, previous_month = _shift_month(end_date.year, end_date.month, -1)
        start_date: date = _billing_boundary(previous_year, previous_month, cycle_day)
        windows.append(DateWindow(start_date=start_date, end_date=end_date))

    return tuple(reversed(windows))


def _billing_boundary(year: int, month: int, cycle_day: int) -> date:
    last_day: int = monthrange(year, month)[1]
    return date(year, month, min(cycle_day, last_day))


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    month_index: int = year * 12 + month - 1 + offset
    return divmod(month_index, 12)[0], divmod(month_index, 12)[1] + 1
