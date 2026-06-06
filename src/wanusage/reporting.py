from __future__ import annotations

from wanusage.models import DailyUsage, UsagePeriod, UsageReport


def format_report(report: UsageReport) -> str:
    lines: list[str] = [
        f"WAN usage report for {report.generated_for.isoformat()}",
        "",
    ]

    lines.extend(_format_period(period) for period in report.billing_periods)
    lines.append(
        "Estimated current billing period usage: "
        f"{format_bytes(report.estimated_current_period_bytes)}"
    )

    if report.day_count >= 0:
        lines.extend(["", _daily_usage_heading(report.day_count)])
        if report.daily_usage:
            for daily_usage in report.daily_usage:
                lines.append(
                    f"  {daily_usage.usage_date.isoformat()}: "
                    f"{format_bytes(daily_usage.total_bytes)}"
                )
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


def _format_period(period: UsagePeriod) -> str:
    return (
        f"{period.name} ({period.start_date.isoformat()} - "
        f"{period.end_date.isoformat()}): {format_bytes(period.total_bytes)}"
    )


def _daily_usage_heading(day_count: int) -> str:
    if day_count == 0:
        return "Current day:"
    return f"Last {day_count} completed day{'s' if day_count != 1 else ''} and current day:"


def sort_daily_usage(values: list[DailyUsage]) -> tuple[DailyUsage, ...]:
    return tuple(sorted(values, key=lambda value: value.usage_date))
