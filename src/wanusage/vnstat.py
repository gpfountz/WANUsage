from __future__ import annotations

import base64
import shlex
from dataclasses import dataclass
from datetime import date, timedelta

from wanusage.billing import (
    DateWindow,
    calculate_billing_windows,
    estimate_period_usage,
)
from wanusage.config import VnstatConfig
from wanusage.models import DailyUsage, UsagePeriod, UsageReport
from wanusage.reporting import sort_daily_usage
from wanusage.ssh import RemoteCommandRunner

MAX_DAILY_HISTORY_DAYS: int = 60


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
        billing_windows: tuple[DateWindow, ...] = calculate_billing_windows(
            today,
            2,
            self.config.billing_cycle_day,
        )
        queries: list[str] = self._build_report_queries(today, day_count, billing_windows)
        output: str = self.command_runner.run(
            _sqlite_command(self.config.database_path, "\n".join(queries))
        )
        daily_usage, billing_totals = _parse_report_results(output)
        sorted_daily_usage: tuple[DailyUsage, ...] = sort_daily_usage(daily_usage)
        current_period_index: int = len(billing_windows) - 1
        current_period_total: int = _required_billing_total(
            billing_totals,
            current_period_index,
        )

        return UsageReport(
            generated_for=today,
            billing_cycle_day=self.config.billing_cycle_day,
            day_count=day_count,
            daily_usage=_select_report_daily_usage(sorted_daily_usage, today, day_count),
            daily_alert_usage=(
                sorted_daily_usage if self.config.daily_alert_gb > 0 else ()
            ),
            billing_periods=tuple(
                _build_usage_period(
                    window,
                    index,
                    len(billing_windows),
                    _required_billing_total(billing_totals, index),
                )
                for index, window in enumerate(billing_windows)
            ),
            estimated_current_period_bytes=estimate_period_usage(
                current_period_total,
                billing_windows[current_period_index],
                today,
            ),
        )

    def _build_report_queries(
        self,
        today: date,
        day_count: int,
        billing_windows: tuple[DateWindow, ...],
    ) -> list[str]:
        queries: list[str] = []
        daily_history_days: int = _daily_history_days(
            day_count,
            daily_alerts_enabled=self.config.daily_alert_gb > 0,
        )
        if daily_history_days >= 0:
            queries.append(
                _daily_usage_query(
                    DateWindow(
                        start_date=today - timedelta(days=daily_history_days),
                        end_date=today + timedelta(days=1),
                    ),
                    self.config.interface_name,
                )
            )
        queries.extend(
            _billing_total_query(window, self.config.interface_name, index)
            for index, window in enumerate(billing_windows)
        )
        return queries


def _daily_history_days(day_count: int, *, daily_alerts_enabled: bool) -> int:
    report_history_days: int = day_count if day_count >= 0 else -1
    alert_history_days: int = MAX_DAILY_HISTORY_DAYS if daily_alerts_enabled else -1
    return max(report_history_days, alert_history_days)


def _select_report_daily_usage(
    daily_usage: tuple[DailyUsage, ...],
    today: date,
    day_count: int,
) -> tuple[DailyUsage, ...]:
    if day_count < 0:
        return ()

    first_report_date: date = today - timedelta(days=day_count)
    return tuple(
        value
        for value in daily_usage
        if first_report_date <= value.usage_date <= today
    )


def _sqlite_command(database_path: str, query: str) -> str:
    quoted_database_path: str = shlex.quote(database_path)
    encoded_query: str = base64.b64encode(query.encode("utf-8")).decode("ascii")
    return (
        f"printf %s {encoded_query} | base64 -d | "
        f"sqlite3 -readonly -batch -separator '|' {quoted_database_path}"
    )


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _daily_usage_query(window: DateWindow, interface_name: str) -> str:
    return (
        "select 'daily', day.date, sum(day.rx) + sum(day.tx) "
        "from day "
        "join interface on interface.id = day.interface "
        f"where day.date >= '{window.start_date.isoformat()}' "
        f"and day.date < '{window.end_date.isoformat()}' "
        f"and interface.name = {_sql_string(interface_name)} "
        "group by day.date "
        "order by day.date;"
    )


def _billing_total_query(window: DateWindow, interface_name: str, index: int) -> str:
    return (
        f"select 'billing_{index}', '', coalesce(sum(day.rx) + sum(day.tx), 0) "
        "from day "
        "join interface on interface.id = day.interface "
        f"where day.date >= '{window.start_date.isoformat()}' "
        f"and day.date < '{window.end_date.isoformat()}' "
        f"and interface.name = {_sql_string(interface_name)};"
    )


def _parse_report_results(output: str) -> tuple[list[DailyUsage], dict[int, int]]:
    daily_usage: list[DailyUsage] = []
    billing_totals: dict[int, int] = {}

    for line in output.splitlines():
        stripped_line: str = line.strip()
        if not stripped_line:
            continue

        parts: list[str] = stripped_line.split("|")
        if len(parts) != 3:
            raise ValueError(f"Unexpected vnStat report row: {stripped_line}")

        result_type, result_date, total_bytes = parts
        if result_type == "daily":
            daily_usage.append(
                DailyUsage(
                    usage_date=date.fromisoformat(result_date),
                    total_bytes=int(total_bytes),
                )
            )
        elif result_type.startswith("billing_"):
            billing_index: int = int(result_type.removeprefix("billing_"))
            billing_totals[billing_index] = int(total_bytes)
        else:
            raise ValueError(f"Unexpected vnStat result type: {result_type}")

    return daily_usage, billing_totals


def _build_usage_period(
    window: DateWindow,
    index: int,
    period_count: int,
    total_bytes: int,
) -> UsagePeriod:
    return UsagePeriod(
        name=_billing_period_name(index, period_count),
        start_date=window.start_date,
        end_date=window.end_date,
        total_bytes=total_bytes,
    )


def _required_billing_total(billing_totals: dict[int, int], index: int) -> int:
    try:
        return billing_totals[index]
    except KeyError as error:
        raise ValueError(f"Missing vnStat billing result: billing_{index}") from error


def _billing_period_name(index: int, period_count: int) -> str:
    if index == period_count - 1:
        return "Current billing period"
    if index == period_count - 2:
        return "Previous billing period"
    return "Billing period"
