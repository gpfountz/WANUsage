from __future__ import annotations

import argparse

import pytest

from wanusage import __version__
from wanusage.cli import build_parser


def test_top_level_help_lists_global_parameters(capsys: pytest.CaptureFixture[str]) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--help"])

    output: str = capsys.readouterr().out
    assert error.value.code == 0
    assert "-c, --config CONFIG" in output
    assert "--config" in output
    assert "Defaults to wanusage.toml in" in output
    assert "current directory." in output
    assert "--debug" in output
    assert "-D, --debug" in output
    assert "--days" in output
    assert "-d, --days DAYS" in output
    assert "--email" in output
    assert "-e, --email" in output
    assert "email.to_address" in output
    assert "--help" in output
    assert "-h, --help" in output
    assert "--quiet" in output
    assert "-q, --quiet" in output
    assert "--version" in output
    assert "-v, --version" in output
    assert "--months" not in output
    assert "from -1 to" in output
    assert "vnstat.default_days" in output
    assert "hide daily" in output
    assert "usage." in output
    assert output.index("--config") < output.index("--days")
    assert output.index("--days") < output.index("--debug")
    assert output.index("--debug") < output.index("--email")
    assert output.index("--email") < output.index("--help")
    assert output.index("--help") < output.index("--quiet")
    assert output.index("--quiet") < output.index("--version")


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


def test_config_defaults_to_current_directory_wanusage_toml() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args([])

    assert args.config == "wanusage.toml"
    assert args.days is None
    assert args.email is False
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


@pytest.mark.parametrize("value", ["-1", "0", "60"])
def test_days_accepts_values_from_negative_1_to_60(value: str) -> None:
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
        "61",
    ],
)
def test_days_rejects_values_outside_range(value: str) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--days", value])

    assert error.value.code == 2


def test_months_parameter_is_not_supported() -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--months", "3"])

    assert error.value.code == 2
