from __future__ import annotations

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


def calculate_current_billing_window(today: date, cycle_day: int = 14) -> DateWindow:
    if today.day >= cycle_day:
        start_date: date = date(today.year, today.month, cycle_day)
        end_date: date = _add_month(start_date)
    else:
        end_date = date(today.year, today.month, cycle_day)
        start_date = _subtract_month(end_date)

    return DateWindow(start_date=start_date, end_date=end_date)


def calculate_previous_billing_window(today: date, cycle_day: int = 14) -> DateWindow:
    current_window: DateWindow = calculate_current_billing_window(today, cycle_day)
    start_date: date = _subtract_month(current_window.start_date)
    return DateWindow(start_date=start_date, end_date=current_window.start_date)


def calculate_billing_windows(
    today: date,
    month_count: int,
    cycle_day: int = 14,
) -> tuple[DateWindow, ...]:
    current_window: DateWindow = calculate_current_billing_window(today, cycle_day)
    windows: list[DateWindow] = []
    end_date: date = current_window.end_date

    for _index in range(month_count):
        start_date: date = _subtract_month(end_date)
        windows.append(DateWindow(start_date=start_date, end_date=end_date))
        end_date = start_date

    return tuple(reversed(windows))


def _add_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, value.day)

    return date(value.year, value.month + 1, value.day)


def _subtract_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, value.day)

    return date(value.year, value.month - 1, value.day)
