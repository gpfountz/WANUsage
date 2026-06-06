from __future__ import annotations

from datetime import date

import pytest

from wanusage.models import DailyUsage, UsagePeriod, UsageReport
from wanusage.reporting import format_bytes, format_report, sort_daily_usage


def test_format_bytes() -> None:
    assert format_bytes(0) == "0 B"
    assert format_bytes(1023) == "1023 B"
    assert format_bytes(1024) == "1.00 KiB"
    assert format_bytes(1024**3 * 2) == "2.00 GiB"


def test_format_bytes_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="byte_count cannot be negative"):
        format_bytes(-1)


def test_format_report_includes_daily_and_period_totals() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=7,
        daily_usage=(
            DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1024),
            DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2048),
        ),
        billing_periods=(
            UsagePeriod(
                name="Previous billing period",
                start_date=date(2026, 4, 14),
                end_date=date(2026, 5, 14),
                total_bytes=1024**4,
            ),
            UsagePeriod(
                name="Current billing period",
                start_date=date(2026, 5, 14),
                end_date=date(2026, 6, 14),
                total_bytes=1024**3,
            ),
        ),
        estimated_current_period_bytes=3 * 1024**3,
    )

    formatted_report: str = format_report(report)

    assert "WAN usage report for 2026-05-26" in formatted_report
    assert "Billing period usage:" not in formatted_report
    assert "Billing period    | End date   |    Usage" in formatted_report
    assert "Previous          | 2026-05-14 | 1.00 TiB" in formatted_report
    assert "Current           | 2026-06-14 | 1.00 GiB" in formatted_report
    assert "Estimated current | 2026-06-14 | 3.00 GiB" in formatted_report
    assert "Date       |    Usage" in formatted_report
    assert "2026-05-24 | 1.00 KiB" in formatted_report
    assert "2026-05-25 | 2.00 KiB" in formatted_report
    assert formatted_report.index("Previous") < formatted_report.index("Current")
    assert formatted_report.index("Current") < formatted_report.index("Estimated current")
    assert "Last 7 completed days and current day" not in formatted_report
    assert formatted_report.index("Estimated current") < formatted_report.index("Date")


def test_format_report_uses_requested_day_count_in_heading() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=1,
        daily_usage=(),
        billing_periods=(),
        estimated_current_period_bytes=0,
    )

    assert "completed day" not in format_report(report)


def test_format_report_uses_current_day_heading_for_zero_days() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=0,
        daily_usage=(),
        billing_periods=(),
        estimated_current_period_bytes=0,
    )

    assert "Current day:" not in format_report(report)


def test_format_report_omits_daily_section_for_negative_days() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=-1,
        daily_usage=(),
        billing_periods=(),
        estimated_current_period_bytes=0,
    )

    assert "Current day:" not in format_report(report)
    assert "completed day" not in format_report(report)


def test_sort_daily_usage_orders_by_date() -> None:
    values: list[DailyUsage] = [
        DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2),
        DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1),
    ]

    assert sort_daily_usage(values) == (
        DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1),
        DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2),
    )
