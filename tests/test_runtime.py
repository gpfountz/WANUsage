from __future__ import annotations

from pathlib import Path

import pytest

from wanusage.runtime import (
    format_python_version,
    minimum_python_version,
    requires_python_specifier_from_pyproject,
)


def test_reads_requires_python_from_pyproject(tmp_path: Path) -> None:
    pyproject_path: Path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "wanusage"
requires-python = ">=3.14"
""".strip(),
        encoding="utf-8",
    )

    assert requires_python_specifier_from_pyproject(pyproject_path) == ">=3.14"


@pytest.mark.parametrize(
    ("requires_python", "expected"),
    [
        (">=3.14", (3, 14)),
        (">=3.14,<4", (3, 14)),
        (">=3.14.1", (3, 14, 1)),
    ],
)
def test_extracts_minimum_python_version(
    requires_python: str,
    expected: tuple[int, ...],
) -> None:
    assert minimum_python_version(requires_python) == expected


def test_rejects_requires_python_without_minimum_version() -> None:
    with pytest.raises(RuntimeError, match="Unsupported requires-python format"):
        minimum_python_version("<4")


def test_formats_python_version() -> None:
    assert format_python_version((3, 14, 6)) == "3.14.6"
