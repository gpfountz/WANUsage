# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only
# See LICENSE for license terms and the warranty disclaimer.

"""Inspect actual Hatchling artifacts and exercise legal access outside the source checkout."""

from __future__ import annotations

import email
import hashlib
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from wanusage import __version__
from wanusage.legal import LEGAL_FILES

ROOT: Path = Path(__file__).resolve().parents[1]
LICENSE_SHA256: str = "fb981668c18a279e285fc4d83fba1e836cc84dd4daa73c9697d3cfd2d8aca6e0"


@dataclass(frozen=True)
class Distribution:
    """Locate a real wheel, source archive, and isolated extracted verification copies."""

    wheel: Path
    sdist: Path
    unpacked_wheel: Path
    unpacked_source: Path


def build_artifacts(root: Path, destination: Path, *targets: str) -> None:
    """Build through the declared backend's CLI, with no installation or publication."""
    command: list[str] = [sys.executable, "-m", "hatchling", "build", "-d", str(destination)]
    for target in targets:
        command.extend(("-t", target))
    result: subprocess.CompletedProcess[str] = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module")
def distribution(tmp_path_factory: pytest.TempPathFactory) -> Distribution:
    """Build both deliverables once and extract them away from the real checkout."""
    temporary: Path = tmp_path_factory.mktemp("wanusage-legal-distribution")
    build_artifacts(ROOT, temporary, "sdist", "wheel")
    wheel: Path = next(temporary.glob("*.whl"))
    sdist: Path = next(temporary.glob("*.tar.gz"))
    unpacked_wheel: Path = temporary / "unpacked-wheel"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(unpacked_wheel)
    unpacked_source: Path = temporary / "unpacked-source"
    with tarfile.open(sdist) as source_archive:
        source_archive.extractall(unpacked_source, filter="data")
    source_root: Path = next(unpacked_source.iterdir())
    return Distribution(wheel, sdist, unpacked_wheel, source_root)


def run_extracted_cli(package_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Import the extracted package first in an isolated interpreter and run its real CLI."""
    code: str = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from wanusage.cli import main; "
        "sys.argv = ['wanusage', *sys.argv[2:]]; main()"
    )
    return subprocess.run(
        [sys.executable, "-I", "-c", code, str(package_root), *arguments],
        cwd=package_root.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def test_wheel_metadata_and_offline_legal_bytes(distribution: Distribution) -> None:
    """The wheel carries exact legal notices and the shared application version."""
    assert hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest() == LICENSE_SHA256
    with zipfile.ZipFile(distribution.wheel) as archive:
        metadata_path: str = next(name for name in archive.namelist() if name.endswith("/METADATA"))
        metadata: email.message.Message = email.message_from_bytes(archive.read(metadata_path))
        assert metadata["License-Expression"] == "GPL-3.0-only"
        assert metadata["Author"] == "Greg Pfountz"
        assert metadata["Version"] == __version__
        assert set(metadata.get_all("License-File", [])) == set(LEGAL_FILES)
        dist_info: str = metadata_path.rsplit("/", 1)[0]
        for filename in LEGAL_FILES:
            canonical: bytes = (ROOT / filename).read_bytes()
            assert archive.read(f"{dist_info}/licenses/{filename}") == canonical
            assert archive.read(f"wanusage/legal_texts/{filename}") == canonical
        assert not any(
            name.endswith((".so", ".dylib", ".dll", ".exe", ".pyc")) for name in archive.namelist()
        )
        assert not any(
            Path(name).name in {".env", "opencollection.yml", "wanusage-dev.toml"}
            for name in archive.namelist()
        )
        assert not any(
            Path(name).name in {"pytest", "hatchling", "mypy", "ruff"}
            for name in archive.namelist()
        )
    result: subprocess.CompletedProcess[str] = run_extracted_cli(
        distribution.unpacked_wheel, "--config", "/missing/config.toml", "--license"
    )
    assert result.returncode == 0, result.stderr
    for filename in LEGAL_FILES:
        assert (ROOT / filename).read_text(encoding="utf-8").strip() in result.stdout
    version_result: subprocess.CompletedProcess[str] = run_extracted_cli(
        distribution.unpacked_wheel, "--version"
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == f"wanusage {__version__}"


def test_source_archive_rebuilds_with_identical_legal_resources(distribution: Distribution) -> None:
    """The source artifact includes build/install materials and reproduces all wheel notices."""
    with tarfile.open(distribution.sdist) as archive:
        prefix: str = archive.getnames()[0].split("/")[0]
        for filename in (
            *LEGAL_FILES,
            "LICENSING.md",
            "README.md",
            "versioning.md",
            "pyproject.toml",
            "scripts/versioning.py",
            "wanusage.toml",
            "tests/test_distribution.py",
        ):
            member = archive.extractfile(f"{prefix}/{filename}")
            assert member is not None
            with member:
                assert member.read() == (ROOT / filename).read_bytes()
        assert not any(
            Path(name).name in {".env", "opencollection.yml", "wanusage-dev.toml"}
            for name in archive.getnames()
        )
    rebuilt: Path = distribution.unpacked_source.parent / "rebuilt"
    build_artifacts(distribution.unpacked_source, rebuilt, "wheel")
    with zipfile.ZipFile(next(rebuilt.glob("*.whl"))) as wheel:
        for filename in LEGAL_FILES:
            assert wheel.read(f"wanusage/legal_texts/{filename}") == (ROOT / filename).read_bytes()


@pytest.mark.parametrize("filename", LEGAL_FILES)
@pytest.mark.parametrize("empty", [False, True])
def test_extracted_installation_rejects_missing_or_empty_legal_resources(
    distribution: Distribution, tmp_path: Path, filename: str, empty: bool
) -> None:
    """A damaged deliverable reports the specific missing resource without checkout fallback."""
    with zipfile.ZipFile(distribution.wheel) as archive:
        archive.extractall(tmp_path)
    resource: Path = tmp_path / "wanusage/legal_texts" / filename
    if empty:
        resource.write_text("", encoding="utf-8")
    else:
        resource.unlink()
    result: subprocess.CompletedProcess[str] = run_extracted_cli(tmp_path, "--license")
    assert result.returncode == 1
    assert not result.stdout
    assert filename in result.stderr
    assert "reinstall WANUsage" in result.stderr
