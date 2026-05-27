from __future__ import annotations

import shlex
from dataclasses import dataclass
from datetime import date

from wanusage.billing import (
    DateWindow,
    calculate_billing_windows,
    calculate_completed_days,
)
from wanusage.config import VnstatConfig
from wanusage.models import DailyUsage, UsagePeriod, UsageReport
from wanusage.reporting import sort_daily_usage
from wanusage.ssh import RemoteCommandRunner


@dataclass(frozen=True)
class VnstatClient:
    command_runner: RemoteCommandRunner
    config: VnstatConfig

    def build_usage_report(
        self,
        today: date,
        *,
        day_count: int = 7,
        month_count: int = 2,
    ) -> UsageReport:
        completed_days_window: DateWindow = calculate_completed_days(today, day_count)
        billing_windows: tuple[DateWindow, ...] = calculate_billing_windows(today, month_count)

        return UsageReport(
            generated_for=today,
            day_count=day_count,
            daily_usage=self.fetch_daily_usage(completed_days_window),
            billing_periods=tuple(
                self._build_usage_period(window, index, len(billing_windows))
                for index, window in enumerate(billing_windows)
            ),
        )

    def _build_usage_period(self, window: DateWindow, index: int, period_count: int) -> UsagePeriod:
        return UsagePeriod(
            name=_billing_period_name(index, period_count),
            start_date=window.start_date,
            end_date=window.end_date,
            total_bytes=self.fetch_total_usage(window),
        )

    def fetch_daily_usage(self, window: DateWindow) -> tuple[DailyUsage, ...]:
        query: str = (
            "select date, sum(rx) + sum(tx) as total "
            "from day "
            f"where date >= '{window.start_date.isoformat()}' "
            f"and date < '{window.end_date.isoformat()}' "
            f"and interface = {self.config.interface_id} "
            "group by date "
            "order by date;"
        )
        output: str = self.command_runner.run(_sqlite_command(self.config.database_path, query))
        return sort_daily_usage(_parse_daily_usage(output))

    def fetch_total_usage(self, window: DateWindow) -> int:
        query: str = (
            "select coalesce(sum(rx) + sum(tx), 0) as total "
            "from day "
            f"where date >= '{window.start_date.isoformat()}' "
            f"and date < '{window.end_date.isoformat()}' "
            f"and interface = {self.config.interface_id};"
        )
        output: str = self.command_runner.run(_sqlite_command(self.config.database_path, query))
        return _parse_total_usage(output)


def _sqlite_command(database_path: str, query: str) -> str:
    quoted_database_path: str = shlex.quote(database_path)
    quoted_query: str = shlex.quote(query)
    return f"sqlite3 -readonly -batch -separator '|' {quoted_database_path} {quoted_query}"


def _parse_daily_usage(output: str) -> list[DailyUsage]:
    values: list[DailyUsage] = []
    for line in output.splitlines():
        stripped_line: str = line.strip()
        if not stripped_line:
            continue

        parts: list[str] = stripped_line.split("|")
        if len(parts) != 2:
            raise ValueError(f"Unexpected vnStat daily usage row: {stripped_line}")

        values.append(
            DailyUsage(
                usage_date=date.fromisoformat(parts[0]),
                total_bytes=int(parts[1]),
            )
        )

    return values


def _parse_total_usage(output: str) -> int:
    stripped_output: str = output.strip()
    if not stripped_output:
        return 0

    first_line: str = stripped_output.splitlines()[0].strip()
    return int(first_line)


def _billing_period_name(index: int, period_count: int) -> str:
    if index == period_count - 1:
        return "Current billing period"
    if index == period_count - 2:
        return "Previous billing period"
    return "Billing period"
