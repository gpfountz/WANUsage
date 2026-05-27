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
    assert "--months" not in output
    assert "from 1 to" in output
    assert "60. Defaults to 7." in output


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


def test_days_accepts_values_from_1_to_60() -> None:
    parser: argparse.ArgumentParser = build_parser()

    args: argparse.Namespace = parser.parse_args(["--days", "60"])

    assert args.days == 60


@pytest.mark.parametrize(
    "value",
    [
        "0",
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
