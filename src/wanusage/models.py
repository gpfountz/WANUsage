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


@dataclass(frozen=True)
class UsageReport:
    """All measured and estimated data needed to render reports and evaluate alerts.

    ``daily_usage`` contains only rows requested for display, while
    ``daily_alert_usage`` may retain a longer history for alert evaluation.
    """

    generated_for: date
    billing_cycle_day: int
    day_count: int
    daily_usage: tuple[DailyUsage, ...]
    daily_alert_usage: tuple[DailyUsage, ...]
    billing_periods: tuple[UsagePeriod, ...]
    estimated_current_period_bytes: int
