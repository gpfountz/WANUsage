from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from wanusage.models import DailyUsage

BYTES_PER_GIB: int = 1024**3
ALERT_SUBJECT: str = "daily high usage alert"


@dataclass(frozen=True)
class AlertDecision:
    should_send: bool
    alert_date: date | None


@dataclass(frozen=True)
class AlertStateStore:
    state_path: Path

    def read_last_alert_date(self) -> date | None:
        if not self.state_path.exists():
            return None

        raw_value: str = self.state_path.read_text(encoding="utf-8").strip()
        if not raw_value:
            return None

        return date.fromisoformat(raw_value)

    def write_last_alert_date(self, alert_date: date) -> None:
        self.state_path.write_text(f"{alert_date.isoformat()}\n", encoding="utf-8")


def alert_state_path_for_config(config_path: Path) -> Path:
    return config_path.resolve().with_name("wanusage-alert-state.txt")


def choose_alert(
    daily_usage: tuple[DailyUsage, ...],
    *,
    daily_alert_gb: int,
    last_alert_date: date | None,
) -> AlertDecision:
    threshold_bytes: int = daily_alert_gb * BYTES_PER_GIB
    triggering_dates: list[date] = [
        value.usage_date
        for value in daily_usage
        if value.total_bytes > threshold_bytes
        and (last_alert_date is None or value.usage_date > last_alert_date)
    ]

    if not triggering_dates:
        return AlertDecision(should_send=False, alert_date=None)

    return AlertDecision(should_send=True, alert_date=max(triggering_dates))
