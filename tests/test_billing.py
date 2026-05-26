from __future__ import annotations

from datetime import date

from wanusage.billing import (
    DateWindow,
    calculate_current_billing_window,
    calculate_last_7_completed_days,
    calculate_previous_billing_window,
)


def test_last_7_completed_days_excludes_today() -> None:
    assert calculate_last_7_completed_days(date(2026, 5, 26)) == DateWindow(
        start_date=date(2026, 5, 19),
        end_date=date(2026, 5, 26),
    )


def test_current_billing_window_after_cycle_day() -> None:
    assert calculate_current_billing_window(date(2026, 5, 26)) == DateWindow(
        start_date=date(2026, 5, 14),
        end_date=date(2026, 6, 14),
    )


def test_current_billing_window_before_cycle_day() -> None:
    assert calculate_current_billing_window(date(2026, 5, 5)) == DateWindow(
        start_date=date(2026, 4, 14),
        end_date=date(2026, 5, 14),
    )


def test_current_billing_window_on_cycle_day_starts_new_period() -> None:
    assert calculate_current_billing_window(date(2026, 5, 14)) == DateWindow(
        start_date=date(2026, 5, 14),
        end_date=date(2026, 6, 14),
    )


def test_previous_billing_window_after_cycle_day() -> None:
    assert calculate_previous_billing_window(date(2026, 5, 26)) == DateWindow(
        start_date=date(2026, 4, 14),
        end_date=date(2026, 5, 14),
    )


def test_billing_window_handles_year_boundary() -> None:
    assert calculate_current_billing_window(date(2026, 1, 2)) == DateWindow(
        start_date=date(2025, 12, 14),
        end_date=date(2026, 1, 14),
    )
