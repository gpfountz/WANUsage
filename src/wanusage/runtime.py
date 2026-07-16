from __future__ import annotations

import re
import sys
import tomllib
from importlib.metadata import PackageMetadata, PackageNotFoundError, metadata
from pathlib import Path
from typing import Any

VersionTuple = tuple[int, ...]

_MINIMUM_VERSION_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|,)\s*>=\s*(?P<version>\d+(?:\.\d+){1,2})\s*(?:,|$)"
)


def ensure_supported_python_runtime() -> None:
    """Raise a clear error when the current Python runtime is unsupported."""

    requires_python: str = requires_python_specifier()
    minimum_version: VersionTuple = minimum_python_version(requires_python)
    current_version: VersionTuple = sys.version_info[:3]

    if current_version < minimum_version:
        minimum_text: str = format_python_version(minimum_version)
        current_text: str = format_python_version(current_version)
        raise RuntimeError(
            f"Python {minimum_text} or newer is required; running Python {current_text}"
        )


def requires_python_specifier() -> str:
    """Return the package's ``Requires-Python`` specifier."""

    pyproject_path: Path = _default_pyproject_path()
    if pyproject_path.is_file():
        return requires_python_specifier_from_pyproject(pyproject_path)

    installed_specifier: str | None = _installed_requires_python()
    if installed_specifier is not None:
        return installed_specifier

    raise RuntimeError("Unable to determine the required Python version for wanusage")


def requires_python_specifier_from_pyproject(pyproject_path: Path) -> str:
    """Read ``project.requires-python`` from a ``pyproject.toml`` file."""

    with pyproject_path.open("rb") as pyproject_file:
        pyproject: dict[str, Any] = tomllib.load(pyproject_file)

    project_section: Any = pyproject.get("project")
    if not isinstance(project_section, dict):
        raise RuntimeError(f"pyproject.toml is missing a [project] section: {pyproject_path}")

    requires_python: Any = project_section.get("requires-python")
    if not isinstance(requires_python, str):
        raise RuntimeError(
            f"pyproject.toml is missing project.requires-python: {pyproject_path}"
        )

    return requires_python


def minimum_python_version(requires_python: str) -> VersionTuple:
    """Extract the lower-bound version from a ``Requires-Python`` specifier."""

    match: re.Match[str] | None = _MINIMUM_VERSION_PATTERN.search(requires_python)
    if match is None:
        raise RuntimeError(f"Unsupported requires-python format: {requires_python}")

    return tuple(int(part) for part in match.group("version").split("."))


def format_python_version(version: VersionTuple) -> str:
    """Format a Python version tuple for user-facing messages."""

    return ".".join(str(part) for part in version)


def _installed_requires_python() -> str | None:
    """Return ``Requires-Python`` from installed package metadata when available."""

    try:
        package_metadata: PackageMetadata = metadata("wanusage")
    except PackageNotFoundError:
        return None

    try:
        requires_python: str = package_metadata["Requires-Python"]
    except KeyError:
        return None

    return requires_python


def _default_pyproject_path() -> Path:
    """Return the source-tree pyproject path for editable and direct source runs."""

    return Path(__file__).resolve().parents[2] / "pyproject.toml"
