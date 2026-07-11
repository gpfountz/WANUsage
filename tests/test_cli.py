from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pytest

from wanusage import __version__
from wanusage.cli import _handle_report, build_parser
from wanusage.config import (
    ApiCredentials,
    AppConfig,
    EmailConfig,
    SmtpCredentials,
    VnstatConfig,
)
from wanusage.models import DailyUsage, UsagePeriod, UsageReport
from wanusage.vnstat import VnstatClient


class RecordingEmailSender:
    sent_messages: list[tuple[str, str]] = []

    def __init__(self, _config: EmailConfig, _credentials: SmtpCredentials) -> None:
        pass

    def send_report(self, subject: str, body: str) -> None:
        self.sent_messages.append((subject, body))


class FixedDate:
    @classmethod
    def today(cls) -> date:
        return date(2026, 5, 26)


class RecordingJsonGetter:
    def get_json(self, _url: str, *, key: str, secret: str) -> dict[str, object]:
        del key, secret
        return {}


def _app_config(*, daily_alert_gb: int, monthly_alert_gb: int) -> AppConfig:
    return AppConfig(
        vnstat=VnstatConfig(
            daily_url="https://router.example.com/api/vnstat/service/daily/",
            monthly_url="https://router.example.com/api/vnstat/service/monthly/",
            default_days=7,
            default_months=1,
            daily_alert_gb=daily_alert_gb,
            monthly_alert_gb=monthly_alert_gb,
        ),
        email=EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            from_address="wan@example.com",
            to_address="recipient@example.com",
            use_tls=True,
        ),
        api_credentials=ApiCredentials(key="api-key", secret="api-secret"),
        smtp_credentials=SmtpCredentials(username="mailer", password="secret"),
    )


def _usage_report(
    *,
    day_count: int,
    daily_usage: tuple[DailyUsage, ...],
    daily_alert_usage: tuple[DailyUsage, ...],
    estimated_current_period_bytes: int,
) -> UsageReport:
    return UsageReport(
        generated_for=date(2026, 5, 26),
        day_count=day_count,
        month_count=1,
        daily_usage=daily_usage,
        daily_alert_usage=daily_alert_usage,
        monthly_usage=(
            UsagePeriod(
                name="Apr 2026",
                start_date=date(2026, 4, 1),
                end_date=date(2026, 5, 1),
                total_bytes=500 * 1024**3,
            ),
            UsagePeriod(
                name="May 2026 estimated",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 6, 1),
                total_bytes=estimated_current_period_bytes,
                is_estimated=True,
            ),
        ),
        current_month_start=date(2026, 5, 1),
        estimated_current_month_bytes=estimated_current_period_bytes,
    )


def test_top_level_help_lists_global_parameters(capsys: pytest.CaptureFixture[str]) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--help"])

    output: str = capsys.readouterr().out
    assert error.value.code == 0
    assert "--config" in output
    assert "Defaults to wanusage-dev.toml in" in output
    assert "current directory." in output
    assert "--debug" in output
    assert "--days" in output
    assert "--email" in output
    assert "email.to_address" in output
    assert "--help" in output
    assert "--months" in output
    assert "--quiet" in output
    assert "--version" in output
    assert "from -1 to" in output
    assert "vnstat.default_days" in output
    assert "vnstat.default_months" in output
    assert "hide daily" in output
    assert "usage." in output
    assert output.index("--config") < output.index("--days")
    assert output.index("--days") < output.index("--debug")
    assert output.index("--debug") < output.index("--email")
    assert output.index("--email") < output.index("--help")
    assert output.index("--help") < output.index("--months")
    assert output.index("--months") < output.index("--quiet")
    assert output.index("--quiet") < output.index("--version")

    option_strings: set[tuple[str, ...]] = {
        tuple(action.option_strings) for action in parser._actions
    }
    assert ("-c", "--config") in option_strings
    assert ("-d", "--days") in option_strings
    assert ("-D", "--debug") in option_strings
    assert ("-e", "--email") in option_strings
    assert ("-h", "--help") in option_strings
    assert ("-m", "--months") in option_strings
    assert ("-q", "--quiet") in option_strings
    assert ("-v", "--version") in option_strings


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--version"])

    output: str = capsys.readouterr().out
    assert error.value.code == 0
    assert output.strip() == f"wanusage {__version__}"


def test_short_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["-v"])

    output: str = capsys.readouterr().out
    assert error.value.code == 0
    assert output.strip() == f"wanusage {__version__}"


def test_config_defaults_to_current_directory_wanusage_dev_toml() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args([])

    assert args.config == "wanusage-dev.toml"
    assert args.days is None
    assert args.email is False
    assert args.months is None
    assert args.quiet is False


def test_short_config_flag_sets_config_path() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["-c", "custom.toml"])

    assert args.config == "custom.toml"


def test_email_flag_accepts_no_value() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["--email"])

    assert args.email is True


def test_short_email_flag_accepts_no_value() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["-e"])

    assert args.email is True


def test_email_flag_rejects_value() -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--email", "recipient@example.com"])

    assert error.value.code == 2


@pytest.mark.parametrize("value", ["-1", "0", "29"])
def test_days_accepts_values_from_negative_1_to_29(value: str) -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["--days", value])

    assert args.days == int(value)


def test_short_days_flag_accepts_value() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["-d", "14"])

    assert args.days == 14


def test_short_debug_flag_sets_debug() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["-D"])

    assert args.debug is True


def test_quiet_flag_accepts_no_value() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["--quiet"])

    assert args.quiet is True


def test_short_quiet_flag_accepts_no_value() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["-q"])

    assert args.quiet is True


@pytest.mark.parametrize(
    "value",
    [
        "-2",
        "30",
    ],
)
def test_days_rejects_values_outside_range(value: str) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--days", value])

    assert error.value.code == 2


@pytest.mark.parametrize("value", ["-1", "0", "11"])
def test_months_accepts_values_from_negative_1_to_11(value: str) -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["--months", value])

    assert args.months == int(value)


def test_short_months_flag_accepts_value() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["-m", "3"])

    assert args.months == 3


@pytest.mark.parametrize("value", ["-2", "12"])
def test_months_rejects_values_outside_range(value: str) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--months", value])

    assert error.value.code == 2


def test_daily_alert_workflow_includes_hidden_triggering_day(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path: Path = tmp_path / "router-a.toml"
    triggering_usage = DailyUsage(
        usage_date=date(2026, 5, 20),
        total_bytes=20 * 1024**3,
    )
    report: UsageReport = _usage_report(
        day_count=-1,
        daily_usage=(),
        daily_alert_usage=(triggering_usage,),
        estimated_current_period_bytes=0,
    )
    captured_report_date: list[date] = []

    def build_usage_report(
        _client: VnstatClient,
        report_date: date,
        *,
        day_count: int = 7,
        month_count: int = 1,
    ) -> UsageReport:
        del day_count, month_count
        captured_report_date.append(report_date)
        return report

    RecordingEmailSender.sent_messages = []
    monkeypatch.setattr("wanusage.cli.load_config", lambda _path: _app_config(
        daily_alert_gb=15,
        monthly_alert_gb=0,
    ))
    monkeypatch.setattr("wanusage.cli.date", FixedDate)
    monkeypatch.setattr("wanusage.cli.UrllibJsonGetter", RecordingJsonGetter)
    monkeypatch.setattr(VnstatClient, "build_usage_report", build_usage_report)
    monkeypatch.setattr("wanusage.cli.EmailSender", RecordingEmailSender)

    _handle_report(
        argparse.Namespace(
            config=str(config_path),
            days=-1,
            debug=False,
            email=False,
            months=1,
            quiet=True,
        )
    )

    assert captured_report_date == [date(2026, 5, 26)]
    assert RecordingEmailSender.sent_messages[0][0] == "daily high usage alert"
    assert "5/20/2026 | 20.00 GiB" in RecordingEmailSender.sent_messages[0][1]
    assert (tmp_path / "router-a-alert-state.txt").read_text(
        encoding="utf-8"
    ) == "2026-05-20\n"


def test_monthly_alert_workflow_sends_once_per_billing_period(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path: Path = tmp_path / "router-b.toml"
    report: UsageReport = _usage_report(
        day_count=-1,
        daily_usage=(),
        daily_alert_usage=(),
        estimated_current_period_bytes=1001 * 1024**3,
    )

    def build_usage_report(
        _client: VnstatClient,
        _report_date: date,
        *,
        day_count: int = 7,
        month_count: int = 1,
    ) -> UsageReport:
        del day_count, month_count
        return report

    RecordingEmailSender.sent_messages = []
    monkeypatch.setattr("wanusage.cli.load_config", lambda _path: _app_config(
        daily_alert_gb=0,
        monthly_alert_gb=1000,
    ))
    monkeypatch.setattr("wanusage.cli.date", FixedDate)
    monkeypatch.setattr("wanusage.cli.UrllibJsonGetter", RecordingJsonGetter)
    monkeypatch.setattr(VnstatClient, "build_usage_report", build_usage_report)
    monkeypatch.setattr("wanusage.cli.EmailSender", RecordingEmailSender)
    args = argparse.Namespace(
        config=str(config_path),
        days=-1,
        debug=False,
        email=False,
        months=1,
        quiet=True,
    )

    _handle_report(args)
    _handle_report(args)

    assert [subject for subject, _body in RecordingEmailSender.sent_messages] == [
        "monthly high usage alert"
    ]
    assert (tmp_path / "router-b-monthly-alert-state.txt").read_text(
        encoding="utf-8"
    ) == "2026-05-01\n"
