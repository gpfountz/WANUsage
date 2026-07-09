from __future__ import annotations

from datetime import date

import pytest

from wanusage.models import DailyUsage, UsagePeriod, UsageReport
from wanusage.reporting import (
    format_bytes,
    format_daily_alert_report,
    format_date,
    format_report,
    sort_daily_usage,
)


def test_format_bytes() -> None:
    assert format_bytes(0) == "0 B"
    assert format_bytes(1023) == "1023 B"
    assert format_bytes(1024) == "1.00 KiB"
    assert format_bytes(1024**3 * 2) == "2.00 GiB"


def test_format_bytes_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="byte_count cannot be negative"):
        format_bytes(-1)


def test_format_date_uses_month_day_year_without_padding() -> None:
    assert format_date(date(2026, 5, 6)) == "5/6/2026"


def test_format_report_includes_daily_and_period_totals() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=7,
        month_count=1,
        daily_usage=(
            DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1024),
            DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2048),
            DailyUsage(usage_date=date(2026, 5, 26), total_bytes=4096),
        ),
        daily_alert_usage=(),
        monthly_usage=(
            UsagePeriod(
                name="Apr 2026",
                start_date=date(2026, 4, 1),
                end_date=date(2026, 5, 1),
                total_bytes=1024**4,
            ),
            UsagePeriod(
                name="May 2026",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 6, 1),
                total_bytes=2 * 1024**3,
            ),
            UsagePeriod(
                name="May 2026 estimated",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 6, 1),
                total_bytes=3 * 1024**3,
                is_estimated=True,
            ),
        ),
        current_month_start=date(2026, 5, 1),
        estimated_current_month_bytes=3 * 1024**3,
    )

    formatted_report: str = format_report(report)

    assert "WAN usage report for 5/26/2026" in formatted_report
    assert "Billing cycle day" not in formatted_report
    assert "Billing period usage:" not in formatted_report
    assert "Month              |    Usage" in formatted_report
    assert "Apr 2026           | 1.00 TiB" in formatted_report
    assert "May 2026           | 2.00 GiB" in formatted_report
    assert "May 2026 estimated | 3.00 GiB" in formatted_report
    assert "Date      |    Usage" in formatted_report
    assert "5/24/2026 | 1.00 KiB" in formatted_report
    assert "5/25/2026 | 2.00 KiB" in formatted_report
    assert "Today     | 4.00 KiB" in formatted_report
    assert formatted_report.index("Apr 2026") < formatted_report.index(
        "May 2026           |"
    )
    assert formatted_report.index("May 2026           |") < formatted_report.index(
        "May 2026 estimated"
    )
    assert "Last 7 completed days and current day" not in formatted_report
    assert formatted_report.index("May 2026 estimated") < formatted_report.index(
        "\n\nDate      |"
    )


def test_format_report_uses_requested_day_count_in_heading() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=1,
        month_count=-1,
        daily_usage=(),
        daily_alert_usage=(),
        monthly_usage=(),
        current_month_start=date(2026, 5, 1),
        estimated_current_month_bytes=0,
    )

    assert "completed day" not in format_report(report)


def test_format_report_uses_current_day_heading_for_zero_days() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=0,
        month_count=-1,
        daily_usage=(),
        daily_alert_usage=(),
        monthly_usage=(),
        current_month_start=date(2026, 5, 1),
        estimated_current_month_bytes=0,
    )

    assert "Current day:" not in format_report(report)


def test_format_report_omits_daily_section_for_negative_days() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=-1,
        month_count=-1,
        daily_usage=(),
        daily_alert_usage=(),
        monthly_usage=(),
        current_month_start=date(2026, 5, 1),
        estimated_current_month_bytes=0,
    )

    assert "Current day:" not in format_report(report)
    assert "completed day" not in format_report(report)


def test_format_report_omits_monthly_section_for_negative_months() -> None:
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=-1,
        month_count=-1,
        daily_usage=(),
        daily_alert_usage=(),
        monthly_usage=(),
        current_month_start=date(2026, 5, 1),
        estimated_current_month_bytes=0,
    )

    assert "Month" not in format_report(report)


def test_format_daily_alert_report_includes_hidden_triggering_day() -> None:
    triggering_usage = DailyUsage(
        usage_date=date(2026, 5, 24),
        total_bytes=20 * 1024**3,
    )
    report = UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=-1,
        month_count=-1,
        daily_usage=(),
        daily_alert_usage=(triggering_usage,),
        monthly_usage=(),
        current_month_start=date(2026, 5, 1),
        estimated_current_month_bytes=0,
    )

    formatted_report: str = format_daily_alert_report(
        report,
        triggering_usage.usage_date,
    )

    assert "5/24/2026 | 20.00 GiB" in formatted_report


def test_sort_daily_usage_orders_by_date() -> None:
    values: list[DailyUsage] = [
        DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2),
        DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1),
    ]

    assert sort_daily_usage(values) == (
        DailyUsage(usage_date=date(2026, 5, 24), total_bytes=1),
        DailyUsage(usage_date=date(2026, 5, 25), total_bytes=2),
    )
