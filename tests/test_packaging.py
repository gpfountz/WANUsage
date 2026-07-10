from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast


def test_hatch_uses_package_version_as_the_single_version_source() -> None:
    project_root: Path = Path(__file__).resolve().parents[1]
    with (project_root / "pyproject.toml").open("rb") as pyproject_file:
        pyproject: dict[str, object] = tomllib.load(pyproject_file)

    project: dict[str, object] = cast(dict[str, object], pyproject["project"])
    tool: dict[str, object] = cast(dict[str, object], pyproject["tool"])
    hatch: dict[str, object] = cast(dict[str, object], tool["hatch"])
    version: dict[str, object] = cast(dict[str, object], hatch["version"])

    assert "version" not in project
    assert project["dynamic"] == ["version"]
    assert version["path"] == "src/wanusage/__init__.py"
