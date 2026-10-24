# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only
# See LICENSE for license terms and the warranty disclaimer.

"""Load the application's complete legal notices without requiring network access."""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from wanusage import __version__

LEGAL_FILES: tuple[str, ...] = ("COPYRIGHT", "LICENSE", "THIRD_PARTY_NOTICES.md")
LEGAL_SUMMARY: str = (
    "Copyright (C) 2026 Greg Pfountz. GPL-3.0-only; no warranty. "
    "Redistribution is permitted under GPLv3. Run 'wanusage --license' for full legal notices."
)


def legal_resource_text(filename: str) -> str:
    """Read an installed legal resource or its canonical original in a source checkout."""
    if filename not in LEGAL_FILES:
        raise ValueError(f"Unknown legal resource: {filename}")
    try:
        resource: Traversable = files("wanusage").joinpath("legal_texts", filename)
        if resource.is_file():
            text: str = resource.read_text(encoding="utf-8")
        else:
            module: Path = Path(__file__).resolve()
            root: Path = module.parents[2]
            if module.parents[1].name != "src" or not (root / "pyproject.toml").is_file():
                raise FileNotFoundError(filename)
            text = (root / filename).read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("The legal resource is empty")
        return text
    except (OSError, UnicodeError, ValueError) as error:
        raise RuntimeError(
            f"Unable to read legal resource {filename}; "
            "restore the source file or reinstall WANUsage."
        ) from error


def legal_notice() -> str:
    """Return the release, author notice, full GPL, and third-party inventory for the CLI."""
    sections: list[str] = [f"WANUsage {__version__}"]
    for filename in LEGAL_FILES:
        sections.append(legal_resource_text(filename).strip())
    return "\n\n".join(sections) + "\n"
