from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from wanusage.models import DailyUsage, UsageReport


def format_report(report: UsageReport) -> str:
    lines: list[str] = [
        f"WAN usage report for {format_date(report.generated_for)}",
        f"Billing cycle day is {report.billing_cycle_day}",
    ]

    if report.billing_periods:
        lines.append("")
        lines.extend(_format_billing_table(report))

    if report.day_count >= 0:
        lines.append("")
        if report.daily_usage:
            lines.extend(_format_daily_table(report.daily_usage, report.generated_for))
        else:
            lines.append("  No daily usage records found.")

    return "\n".join(lines)


def format_bytes(byte_count: int) -> str:
    if byte_count < 0:
        raise ValueError("byte_count cannot be negative")

    units: tuple[str, ...] = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    value: float = float(byte_count)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024

    raise RuntimeError("unreachable byte formatting state")


def format_date(value: date) -> str:
    return f"{value.month}/{value.day}/{value.year}"


def _format_billing_table(report: UsageReport) -> list[str]:
    rows: list[tuple[str, str]] = [
        (
            period.name.removesuffix(" billing period"),
            format_bytes(period.total_bytes),
        )
        for period in report.billing_periods
    ]
    rows.append(
        (
            "Estimated",
            format_bytes(report.estimated_current_period_bytes),
        )
    )
    return _format_table(
        headers=("Billing period", "Usage"),
        rows=rows,
        right_aligned_columns=frozenset({1}),
    )


def _format_daily_table(
    daily_usage: tuple[DailyUsage, ...],
    report_date: date,
) -> list[str]:
    rows: list[tuple[str, str]] = [
        (
            "Today" if value.usage_date == report_date else format_date(value.usage_date),
            format_bytes(value.total_bytes),
        )
        for value in daily_usage
    ]
    return _format_table(
        headers=("Date", "Usage"),
        rows=rows,
        right_aligned_columns=frozenset({1}),
    )


def _format_table(
    headers: tuple[str, ...],
    rows: Sequence[tuple[str, ...]],
    right_aligned_columns: frozenset[int],
) -> list[str]:
    column_widths: tuple[int, ...] = tuple(
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    )

    def format_row(row: tuple[str, ...]) -> str:
        cells: list[str] = []
        for index, value in enumerate(row):
            if index in right_aligned_columns:
                cells.append(value.rjust(column_widths[index]))
            else:
                cells.append(value.ljust(column_widths[index]))
        return " | ".join(cells)

    separator: str = "-+-".join("-" * width for width in column_widths)
    return [format_row(headers), separator, *(format_row(row) for row in rows)]


def sort_daily_usage(values: list[DailyUsage]) -> tuple[DailyUsage, ...]:
    return tuple(sorted(values, key=lambda value: value.usage_date))
