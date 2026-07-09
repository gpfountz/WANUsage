from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DailyUsage:
    """The combined received and transmitted byte count for one calendar day."""

    usage_date: date
    total_bytes: int


@dataclass(frozen=True)
class UsagePeriod:
    """The measured byte total and boundaries for a named billing period."""

    name: str
    start_date: date
    end_date: date
    total_bytes: int
    is_estimated: bool = False


@dataclass(frozen=True)
class UsageReport:
    """All API usage data needed to render reports and evaluate alerts.

    ``daily_usage`` contains only rows requested for display, while
    ``daily_alert_usage`` may retain a longer history for alert evaluation.
    """

    generated_for: date
    day_count: int
    month_count: int
    daily_usage: tuple[DailyUsage, ...]
    daily_alert_usage: tuple[DailyUsage, ...]
    monthly_usage: tuple[UsagePeriod, ...]
    current_month_start: date
    estimated_current_month_bytes: int
