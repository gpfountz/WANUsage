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
    assert "--help" in output
    assert "--version" in output
    assert "--config" in output
    assert "Defaults to wanusage.toml in the" in output
    assert "current directory." in output
    assert "--email" in output
    assert "--debug" in output
    assert "--days" in output
    assert "--months" in output


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--version"])

    output: str = capsys.readouterr().out
    assert error.value.code == 0
    assert output.strip() == f"wanusage {__version__}"


def test_config_defaults_to_current_directory_wanusage_toml() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args([])

    assert args.config == "wanusage.toml"
    assert args.days == 7
    assert args.months == 2


def test_days_and_months_accept_values_from_1_to_99() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["--days", "1", "--months", "99"])

    assert args.days == 1
    assert args.months == 99


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--days", "0"),
        ("--days", "100"),
        ("--months", "0"),
        ("--months", "100"),
    ],
)
def test_days_and_months_reject_values_outside_range(option: str, value: str) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args([option, value])

    assert error.value.code == 2
