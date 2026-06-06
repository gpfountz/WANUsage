from __future__ import annotations

from datetime import date

from wanusage.billing import (
    DateWindow,
    calculate_billing_windows,
    calculate_completed_days,
    calculate_current_billing_window,
    calculate_last_7_completed_days,
    calculate_previous_billing_window,
    estimate_period_usage,
)


def test_last_7_completed_days_excludes_today() -> None:
    assert calculate_last_7_completed_days(date(2026, 5, 26)) == DateWindow(
        start_date=date(2026, 5, 19),
        end_date=date(2026, 5, 26),
    )


def test_completed_days_uses_requested_day_count() -> None:
    assert calculate_completed_days(date(2026, 5, 26), 14) == DateWindow(
        start_date=date(2026, 5, 12),
        end_date=date(2026, 5, 26),
    )


def test_current_billing_window_after_cycle_day() -> None:
    assert calculate_current_billing_window(date(2026, 5, 26), 14) == DateWindow(
        start_date=date(2026, 5, 14),
        end_date=date(2026, 6, 14),
    )


def test_current_billing_window_before_cycle_day() -> None:
    assert calculate_current_billing_window(date(2026, 5, 5), 14) == DateWindow(
        start_date=date(2026, 4, 14),
        end_date=date(2026, 5, 14),
    )


def test_current_billing_window_on_cycle_day_starts_new_period() -> None:
    assert calculate_current_billing_window(date(2026, 5, 14), 14) == DateWindow(
        start_date=date(2026, 5, 14),
        end_date=date(2026, 6, 14),
    )


def test_previous_billing_window_after_cycle_day() -> None:
    assert calculate_previous_billing_window(date(2026, 5, 26), 14) == DateWindow(
        start_date=date(2026, 4, 14),
        end_date=date(2026, 5, 14),
    )


def test_billing_window_handles_year_boundary() -> None:
    assert calculate_current_billing_window(date(2026, 1, 2), 14) == DateWindow(
        start_date=date(2025, 12, 14),
        end_date=date(2026, 1, 14),
    )


def test_billing_windows_returns_requested_months_oldest_first() -> None:
    assert calculate_billing_windows(date(2026, 5, 26), 3, 14) == (
        DateWindow(start_date=date(2026, 3, 14), end_date=date(2026, 4, 14)),
        DateWindow(start_date=date(2026, 4, 14), end_date=date(2026, 5, 14)),
        DateWindow(start_date=date(2026, 5, 14), end_date=date(2026, 6, 14)),
    )


def test_cycle_day_31_clamps_each_month_independently() -> None:
    assert calculate_billing_windows(date(2026, 5, 10), 2, 31) == (
        DateWindow(start_date=date(2026, 3, 31), end_date=date(2026, 4, 30)),
        DateWindow(start_date=date(2026, 4, 30), end_date=date(2026, 5, 31)),
    )


def test_cycle_day_30_clamps_april_boundary() -> None:
    assert calculate_billing_windows(date(2026, 5, 10), 2, 30) == (
        DateWindow(start_date=date(2026, 3, 30), end_date=date(2026, 4, 30)),
        DateWindow(start_date=date(2026, 4, 30), end_date=date(2026, 5, 30)),
    )


def test_cycle_day_31_clamps_non_leap_year_february() -> None:
    assert calculate_billing_windows(date(2026, 3, 10), 2, 31) == (
        DateWindow(start_date=date(2026, 1, 31), end_date=date(2026, 2, 28)),
        DateWindow(start_date=date(2026, 2, 28), end_date=date(2026, 3, 31)),
    )


def test_cycle_day_31_clamps_leap_year_february() -> None:
    assert calculate_billing_windows(date(2024, 3, 10), 2, 31) == (
        DateWindow(start_date=date(2024, 1, 31), end_date=date(2024, 2, 29)),
        DateWindow(start_date=date(2024, 2, 29), end_date=date(2024, 3, 31)),
    )


def test_estimate_period_usage_projects_from_elapsed_calendar_days() -> None:
    window = DateWindow(start_date=date(2026, 5, 14), end_date=date(2026, 6, 14))

    assert estimate_period_usage(13 * 1024**3, window, date(2026, 5, 26)) == 31 * 1024**3
