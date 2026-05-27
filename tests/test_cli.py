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
    assert "report" in output


def test_report_help_lists_report_parameters(capsys: pytest.CaptureFixture[str]) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["report", "--help"])

    output: str = capsys.readouterr().out
    assert error.value.code == 0
    assert "--config" in output
    assert "--email" in output
    assert "--debug" in output
    assert "--help" in output


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    parser: argparse.ArgumentParser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--version"])

    output: str = capsys.readouterr().out
    assert error.value.code == 0
    assert output.strip() == f"wanusage {__version__}"
