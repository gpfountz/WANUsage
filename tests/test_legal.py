# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only
# See LICENSE for license terms and the warranty disclaimer.

"""Verify offline legal output and recoverable resource failures without running reports."""

from __future__ import annotations

from pathlib import Path

import pytest

from wanusage import __version__, cli, legal


def test_source_legal_notice_contains_the_complete_canonical_files() -> None:
    """Source execution exposes attribution, the full GPL, and the actual distribution scope."""
    root: Path = Path(__file__).resolve().parents[1]
    output: str = legal.legal_notice()
    assert output.startswith(f"WANUsage {__version__}\n")
    for filename in legal.LEGAL_FILES:
        assert (root / filename).read_text(encoding="utf-8").strip() in output
    assert "Copyright (C) 2026 Greg Pfountz" in output
    assert "WITHOUT\nANY WARRANTY" in output
    assert "END OF TERMS AND CONDITIONS" in output


def test_license_command_does_not_start_a_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Legal output works even when the supplied runtime configuration does not exist."""

    def unexpected_report(_args: object) -> None:
        """Fail if legal-only execution attempts router, SMTP, or state work."""
        pytest.fail("A legal command must not start a report")

    monkeypatch.setattr(cli, "_handle_report", unexpected_report)
    monkeypatch.setattr("sys.argv", ["wanusage", "--config", "/missing/config.toml", "--license"])
    cli.main()
    output: str = capsys.readouterr().out
    assert "GNU GENERAL PUBLIC LICENSE" in output
    assert "Third-party materials" in output


def test_license_command_reports_resource_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A damaged installation yields an actionable failure instead of incomplete legal output."""

    def unreadable_notice() -> str:
        """Simulate a missing packaged license without touching canonical files."""
        raise RuntimeError("Unable to read legal resource LICENSE; reinstall WANUsage.")

    monkeypatch.setattr(cli, "legal_notice", unreadable_notice)
    monkeypatch.setattr("sys.argv", ["wanusage", "--license"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    output: str
    error_output: str
    output, error_output = capsys.readouterr()
    assert not output
    assert "reinstall WANUsage" in error_output


def test_help_exposes_copyright_rights_and_license_access() -> None:
    """Users can discover the author, redistribution terms, warranty, and offline license option."""
    output: str = " ".join(cli.build_parser().format_help().split())
    assert "--license" in output
    assert "Greg Pfountz" in output
    assert "GPL-3.0-only" in output
    assert "no warranty" in output
    assert "Redistribution is permitted" in output
