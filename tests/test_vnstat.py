from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import date
from zoneinfo import ZoneInfo

from wanusage.config import VnstatConfig
from wanusage.vnstat import VnstatClient


@dataclass
class FakeCommandRunner:
    outputs: list[str]
    commands: list[str] = field(default_factory=list)

    def run(self, command: str) -> str:
        self.commands.append(command)
        return self.outputs.pop(0)


def _config(*, daily_alert_gb: int = 50) -> VnstatConfig:
    return VnstatConfig(
        database_path="/var/lib/vnstat/vnstat.db",
        interface_name="eth0",
        reporting_timezone=ZoneInfo("America/New_York"),
        billing_cycle_day=14,
        default_days=7,
        daily_alert_gb=daily_alert_gb,
        monthly_alert_gb=1000,
    )


def _sql_from_command(command: str) -> str:
    encoded_query: str = command.split("printf %s ", 1)[1].split(" | base64", 1)[0]
    return base64.b64decode(encoded_query).decode("utf-8")


def test_build_usage_report_executes_all_queries_in_one_remote_command() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "\n".join(
                [
                    "daily|2026-04-01|2048",
                    "daily|2026-05-24|1024",
                    "daily|2026-05-26|512",
                    "billing_0||8192",
                    "billing_1||4096",
                ]
            )
        ]
    )
    client = VnstatClient(command_runner=command_runner, config=_config())

    report = client.build_usage_report(date(2026, 5, 26), day_count=7)

    assert [value.total_bytes for value in report.daily_usage] == [1024, 512]
    assert [value.total_bytes for value in report.daily_alert_usage] == [2048, 1024, 512]
    assert report.billing_cycle_day == 14
    assert report.billing_periods[0].total_bytes == 8192
    assert report.billing_periods[0].name == "Previous billing period"
    assert report.billing_periods[1].total_bytes == 4096
    assert report.billing_periods[1].name == "Current billing period"
    assert report.estimated_current_period_bytes == 9767
    assert len(command_runner.commands) == 1

    command: str = command_runner.commands[0]
    query: str = _sql_from_command(command)
    assert command.count("sqlite3 ") == 1
    assert query.count("select ") == 3
    assert query.count("join interface on interface.id = day.interface") == 3
    assert "2026-03-27" in query
    assert "2026-05-27" in query
    assert "interface.name" in query
    assert "eth0" in query


def test_build_usage_report_supports_custom_day_count_in_one_command() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "\n".join(
                [
                    "daily|2026-05-25|1024",
                    "daily|2026-05-26|512",
                    "billing_0||2",
                    "billing_1||3",
                ]
            )
        ]
    )
    client = VnstatClient(command_runner=command_runner, config=_config())

    report = client.build_usage_report(date(2026, 5, 26), day_count=1)

    assert report.day_count == 1
    assert report.billing_periods[0].name == "Previous billing period"
    assert report.billing_periods[1].name == "Current billing period"
    assert len(command_runner.commands) == 1
    query: str = _sql_from_command(command_runner.commands[0])
    assert query.count("select ") == 3
    assert "2026-03-27" in query


def test_zero_report_days_still_fetches_history_for_daily_alerts() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "\n".join(
                [
                    "daily|2026-05-20|1024",
                    "daily|2026-05-26|512",
                    "billing_0||2",
                    "billing_1||3",
                ]
            )
        ]
    )
    client = VnstatClient(command_runner=command_runner, config=_config())

    report = client.build_usage_report(date(2026, 5, 26), day_count=0)

    assert [value.usage_date for value in report.daily_usage] == [date(2026, 5, 26)]
    assert [value.usage_date for value in report.daily_alert_usage] == [
        date(2026, 5, 20),
        date(2026, 5, 26),
    ]
    assert len(command_runner.commands) == 1
    assert _sql_from_command(command_runner.commands[0]).count("select ") == 3


def test_negative_report_days_still_fetches_history_for_daily_alerts() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "\n".join(
                [
                    "daily|2026-05-20|1024",
                    "daily|2026-05-26|512",
                    "billing_0||2",
                    "billing_1||3",
                ]
            )
        ]
    )
    client = VnstatClient(command_runner=command_runner, config=_config())

    report = client.build_usage_report(date(2026, 5, 26), day_count=-1)

    assert report.daily_usage == ()
    assert [value.usage_date for value in report.daily_alert_usage] == [
        date(2026, 5, 20),
        date(2026, 5, 26),
    ]
    assert len(command_runner.commands) == 1
    query: str = _sql_from_command(command_runner.commands[0])
    assert query.count("select ") == 3
    assert "2026-03-27" in query


def test_negative_report_days_skips_daily_query_when_alerts_are_disabled() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "\n".join(
                [
                    "billing_0||2",
                    "billing_1||3",
                ]
            )
        ]
    )
    client = VnstatClient(
        command_runner=command_runner,
        config=_config(daily_alert_gb=0),
    )

    report = client.build_usage_report(date(2026, 5, 26), day_count=-1)

    assert report.daily_usage == ()
    assert report.daily_alert_usage == ()
    query: str = _sql_from_command(command_runner.commands[0])
    assert query.count("select ") == 2
    assert "'daily'" not in query
