from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DailyUsage:
    usage_date: date
    total_bytes: int


@dataclass(frozen=True)
class UsagePeriod:
    name: str
    start_date: date
    end_date: date
    total_bytes: int


@dataclass(frozen=True)
class UsageReport:
    generated_for: date
    billing_cycle_day: int
    day_count: int
    daily_usage: tuple[DailyUsage, ...]
    billing_periods: tuple[UsagePeriod, ...]
    estimated_current_period_bytes: int
