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
        last_7_days=(
            DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1024),
            DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2048),
        ),
        current_period=UsagePeriod(
            name="Current billing period",
            start_date=date(2026, 5, 14),
            end_date=date(2026, 6, 14),
            total_bytes=1024**3,
        ),
        previous_period=UsagePeriod(
            name="Previous billing period",
            start_date=date(2026, 4, 14),
            end_date=date(2026, 5, 14),
            total_bytes=1024**4,
        ),
    )

    formatted_report: str = format_report(report)

    assert "WAN usage report for 2026-05-26" in formatted_report
    assert "2026-05-24: 1.00 KiB" in formatted_report
    assert "Current billing period (2026-05-14 <= date < 2026-06-14): 1.00 GiB" in (
        formatted_report
    )
    assert "Previous billing period (2026-04-14 <= date < 2026-05-14): 1.00 TiB" in (
        formatted_report
    )
    assert formatted_report.index("Previous billing period") < formatted_report.index(
        "Current billing period"
    )


def test_sort_daily_usage_orders_by_date() -> None:
    values: list[DailyUsage] = [
        DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2),
        DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1),
    ]

    assert sort_daily_usage(values) == (
        DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1),
        DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2),
    )
