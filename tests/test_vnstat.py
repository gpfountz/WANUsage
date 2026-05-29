from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from wanusage.billing import DateWindow
from wanusage.config import VnstatConfig
from wanusage.vnstat import VnstatClient


@dataclass
class FakeCommandRunner:
    outputs: list[str]
    commands: list[str] = field(default_factory=list)

    def run(self, command: str) -> str:
        self.commands.append(command)
        return self.outputs.pop(0)


def test_fetch_daily_usage_queries_window_and_parses_rows() -> None:
    command_runner = FakeCommandRunner(outputs=["2026-05-24|1024\n2026-05-25|2048\n"])
    client = VnstatClient(
        command_runner=command_runner,
        config=VnstatConfig(
            database_path="/var/lib/vnstat/vnstat.db",
            interface_id=1,
            default_days=7,
        ),
    )

    values = client.fetch_daily_usage(
        DateWindow(start_date=date(2026, 5, 19), end_date=date(2026, 5, 26))
    )

    assert [value.total_bytes for value in values] == [1024, 2048]
    assert "sqlite3 -readonly -batch -separator '|'" in command_runner.commands[0]
    assert "2026-05-19" in command_runner.commands[0]
    assert "2026-05-26" in command_runner.commands[0]
    assert "interface = 1" in command_runner.commands[0]


def test_fetch_total_usage_returns_zero_for_empty_output() -> None:
    command_runner = FakeCommandRunner(outputs=["\n"])
    client = VnstatClient(
        command_runner=command_runner,
        config=VnstatConfig(
            database_path="/var/lib/vnstat/vnstat.db",
            interface_id=1,
            default_days=7,
        ),
    )

    assert client.fetch_total_usage(DateWindow(date(2026, 5, 14), date(2026, 6, 14))) == 0


def test_build_usage_report_fetches_all_periods() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "2026-05-24|1024\n",
            "2026-05-26|512\n",
            "8192\n",
            "4096\n",
        ]
    )
    client = VnstatClient(
        command_runner=command_runner,
        config=VnstatConfig(
            database_path="/var/lib/vnstat/vnstat.db",
            interface_id=1,
            default_days=7,
        ),
    )

    report = client.build_usage_report(date(2026, 5, 26), day_count=7)

    assert report.daily_usage[0].total_bytes == 1024
    assert report.daily_usage[1].total_bytes == 512
    assert report.billing_periods[0].total_bytes == 8192
    assert report.billing_periods[0].name == "Previous billing period"
    assert report.billing_periods[1].total_bytes == 4096
    assert report.billing_periods[1].name == "Current billing period"
    assert len(command_runner.commands) == 4


def test_build_usage_report_supports_custom_day_count() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "2026-05-25|1024\n",
            "2026-05-26|512\n",
            "2\n",
            "3\n",
        ]
    )
    client = VnstatClient(
        command_runner=command_runner,
        config=VnstatConfig(
            database_path="/var/lib/vnstat/vnstat.db",
            interface_id=1,
            default_days=7,
        ),
    )

    report = client.build_usage_report(date(2026, 5, 26), day_count=1)

    assert report.day_count == 1
    assert report.billing_periods[0].name == "Previous billing period"
    assert report.billing_periods[1].name == "Current billing period"
    assert len(command_runner.commands) == 4


def test_build_usage_report_with_zero_days_fetches_only_current_day() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "2026-05-26|512\n",
            "2\n",
            "3\n",
        ]
    )
    client = VnstatClient(
        command_runner=command_runner,
        config=VnstatConfig(
            database_path="/var/lib/vnstat/vnstat.db",
            interface_id=1,
            default_days=7,
        ),
    )

    report = client.build_usage_report(date(2026, 5, 26), day_count=0)

    assert [value.usage_date for value in report.daily_usage] == [date(2026, 5, 26)]
    assert len(command_runner.commands) == 3


def test_build_usage_report_with_negative_days_skips_daily_usage() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "2\n",
            "3\n",
        ]
    )
    client = VnstatClient(
        command_runner=command_runner,
        config=VnstatConfig(
            database_path="/var/lib/vnstat/vnstat.db",
            interface_id=1,
            default_days=7,
        ),
    )

    report = client.build_usage_report(date(2026, 5, 26), day_count=-1)

    assert report.daily_usage == ()
    assert len(command_runner.commands) == 2
