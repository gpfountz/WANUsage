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
        config=VnstatConfig(database_path="/var/lib/vnstat/vnstat.db", interface_id=1),
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
        config=VnstatConfig(database_path="/var/lib/vnstat/vnstat.db", interface_id=1),
    )

    assert client.fetch_total_usage(DateWindow(date(2026, 5, 14), date(2026, 6, 14))) == 0


def test_build_usage_report_fetches_all_periods() -> None:
    command_runner = FakeCommandRunner(
        outputs=[
            "2026-05-24|1024\n",
            "4096\n",
            "8192\n",
        ]
    )
    client = VnstatClient(
        command_runner=command_runner,
        config=VnstatConfig(database_path="/var/lib/vnstat/vnstat.db", interface_id=1),
    )

    report = client.build_usage_report(date(2026, 5, 26))

    assert report.last_7_days[0].total_bytes == 1024
    assert report.current_period.total_bytes == 4096
    assert report.previous_period.total_bytes == 8192
    assert len(command_runner.commands) == 3
