from __future__ import annotations

import shlex
from dataclasses import dataclass
from datetime import date

from wanusage.billing import (
    DateWindow,
    calculate_current_billing_window,
    calculate_last_7_completed_days,
    calculate_previous_billing_window,
)
from wanusage.config import VnstatConfig
from wanusage.models import DailyUsage, UsagePeriod, UsageReport
from wanusage.reporting import sort_daily_usage
from wanusage.ssh import RemoteCommandRunner


@dataclass(frozen=True)
class VnstatClient:
    command_runner: RemoteCommandRunner
    config: VnstatConfig

    def build_usage_report(self, today: date) -> UsageReport:
        last_7_days_window: DateWindow = calculate_last_7_completed_days(today)
        current_window: DateWindow = calculate_current_billing_window(today)
        previous_window: DateWindow = calculate_previous_billing_window(today)

        return UsageReport(
            generated_for=today,
            last_7_days=self.fetch_daily_usage(last_7_days_window),
            current_period=UsagePeriod(
                name="Current billing period",
                start_date=current_window.start_date,
                end_date=current_window.end_date,
                total_bytes=self.fetch_total_usage(current_window),
            ),
            previous_period=UsagePeriod(
                name="Previous billing period",
                start_date=previous_window.start_date,
                end_date=previous_window.end_date,
                total_bytes=self.fetch_total_usage(previous_window),
            ),
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
