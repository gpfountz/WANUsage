from __future__ import annotations

import shlex
from dataclasses import dataclass
from datetime import date

from wanusage.billing import (
    DateWindow,
    calculate_billing_windows,
    calculate_completed_days,
    calculate_current_day,
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
    ) -> UsageReport:
        billing_windows: tuple[DateWindow, ...] = calculate_billing_windows(today, 2)

        return UsageReport(
            generated_for=today,
            day_count=day_count,
            daily_usage=self.fetch_report_daily_usage(today, day_count),
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

    def fetch_report_daily_usage(self, today: date, day_count: int) -> tuple[DailyUsage, ...]:
        if day_count < 0:
            return ()

        values: list[DailyUsage] = []
        if day_count > 0:
            values.extend(self.fetch_daily_usage(calculate_completed_days(today, day_count)))
        values.extend(self.fetch_daily_usage(calculate_current_day(today)))
        return sort_daily_usage(values)

    def fetch_daily_usage(self, window: DateWindow) -> tuple[DailyUsage, ...]:
        interface_name: str = _sql_string(self.config.interface_name)
        query: str = (
            "select day.date, sum(day.rx) + sum(day.tx) as total "
            "from day "
            "join interface on interface.id = day.interface "
            f"where day.date >= '{window.start_date.isoformat()}' "
            f"and day.date < '{window.end_date.isoformat()}' "
            f"and interface.name = {interface_name} "
            "group by day.date "
            "order by day.date;"
        )
        output: str = self.command_runner.run(_sqlite_command(self.config.database_path, query))
        return sort_daily_usage(_parse_daily_usage(output))

    def fetch_total_usage(self, window: DateWindow) -> int:
        interface_name: str = _sql_string(self.config.interface_name)
        query: str = (
            "select coalesce(sum(day.rx) + sum(day.tx), 0) as total "
            "from day "
            "join interface on interface.id = day.interface "
            f"where day.date >= '{window.start_date.isoformat()}' "
            f"and day.date < '{window.end_date.isoformat()}' "
            f"and interface.name = {interface_name};"
        )
        output: str = self.command_runner.run(_sqlite_command(self.config.database_path, query))
        return _parse_total_usage(output)


def _sqlite_command(database_path: str, query: str) -> str:
    quoted_database_path: str = shlex.quote(database_path)
    quoted_query: str = shlex.quote(query)
    return f"sqlite3 -readonly -batch -separator '|' {quoted_database_path} {quoted_query}"


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


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
