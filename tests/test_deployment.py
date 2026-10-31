# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise real build/deploy entry points using disposable local installations."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from wanusage import __version__

ROOT: Path = Path(__file__).resolve().parents[1]
DEPLOY_FILES: tuple[str, ...] = ("deploy.sh", "run_python.sh", "distribution.py")


def invoke(script: Path, *arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the public shell entry point with the test environment's Python interpreter."""
    return subprocess.run(
        ["sh", str(script), *arguments],
        cwd=cwd,
        env={**os.environ, "WANUSAGE_PYTHON": sys.executable},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def wheel_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the current sources offline using the actual public build entry point."""
    destination: Path = tmp_path_factory.mktemp("wheels with spaces")
    result: subprocess.CompletedProcess[str] = invoke(
        ROOT / "scripts/build.sh",
        "--no-build-isolation",
        "--output-dir",
        str(destination),
        cwd=destination,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (destination / f"wanusage-{__version__}-py3-none-any.whl").is_file()
    return destination


def deployment_arguments(wheels: Path, destination: Path) -> list[str]:
    """Keep every deployment mutation inside a test-owned temporary directory."""
    return [
        "--wheel-dir",
        str(wheels),
        "--install-dir",
        str(destination / "installation"),
        "--bin-dir",
        str(destination / "bin"),
    ]


def test_artifact_only_deploy_repairs_permissions_and_refreshes_same_version(
    wheel_directory: Path,
    tmp_path: Path,
) -> None:
    """Deploy copied artifacts with readable permissions and refresh damaged same-version code."""
    bundle: Path = tmp_path / "bundle with spaces"
    scripts: Path = bundle / "scripts"
    scripts.mkdir(parents=True)
    for filename in DEPLOY_FILES:
        shutil.copyfile(ROOT / "scripts" / filename, scripts / filename)
    shutil.copytree(wheel_directory, bundle / "dist")
    installation: Path = tmp_path / "installation"
    installation.mkdir()
    private_file: Path = installation / "private-config.toml"
    private_file.write_text("private = true\n")
    private_file.chmod(0o600)
    arguments: list[str] = [
        "--install-dir",
        str(installation),
        "--bin-dir",
        str(tmp_path / "bin"),
    ]
    previous_umask: int = os.umask(0o077)
    try:
        result: subprocess.CompletedProcess[str] = invoke(
            scripts / "deploy.sh",
            *arguments,
            cwd=tmp_path,
        )
    finally:
        os.umask(previous_umask)
    assert result.returncode == 0, result.stdout + result.stderr
    link: Path = tmp_path / "bin/wanusage"
    assert link.is_symlink()
    version: subprocess.CompletedProcess[str] = subprocess.run(
        [str(link), "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert version.returncode == 0, version.stderr
    assert version.stdout.strip() == f"wanusage {__version__}"
    legal: subprocess.CompletedProcess[str] = subprocess.run(
        [str(link), "--license"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert legal.returncode == 0, legal.stderr
    assert (ROOT / "LICENSE").read_text().strip() in legal.stdout
    package: Path = next((installation / ".venv/lib").glob("python*/site-packages/wanusage"))
    cli: Path = package / "cli.py"
    cli.write_text('raise RuntimeError("replace this broken installation")\n')
    cli.chmod(0o600)
    package.chmod(0o700)
    result = invoke(scripts / "deploy.sh", *arguments, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "replace this broken installation" not in cli.read_text()
    for directory in (package, package.parent / f"wanusage-{__version__}.dist-info"):
        for path in (directory, *directory.rglob("*")):
            required: int = 0o555 if path.is_dir() else 0o444
            assert stat.S_IMODE(path.stat().st_mode) & required == required, path
    assert private_file.read_text() == "private = true\n"
    assert stat.S_IMODE(private_file.stat().st_mode) == 0o600


def test_deploy_selects_highest_numeric_version_before_modifying_installation(
    wheel_directory: Path,
    tmp_path: Path,
) -> None:
    """A corrupt 2.2.10 wheel must take precedence over a valid 2.2.9 wheel and stop deployment."""
    wheels: Path = tmp_path / "wheels"
    wheels.mkdir()
    original: Path = next(wheel_directory.glob("*.whl"))
    shutil.copyfile(original, wheels / "wanusage-2.2.9-py3-none-any.whl")
    (wheels / "wanusage-2.2.10-py3-none-any.whl").write_text("not a wheel")
    result: subprocess.CompletedProcess[str] = invoke(
        ROOT / "scripts/deploy.sh",
        *deployment_arguments(wheels, tmp_path),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "File is not a zip file" in result.stderr
    assert not (tmp_path / "installation").exists()


@pytest.mark.parametrize("symlink", [False, True])
def test_deploy_preserves_unrelated_commands(
    wheel_directory: Path,
    tmp_path: Path,
    symlink: bool,
) -> None:
    """A command belonging to another installation must survive without any deployment writes."""
    bin_directory: Path = tmp_path / "bin"
    bin_directory.mkdir()
    command: Path = bin_directory / "wanusage"
    if symlink:
        command.symlink_to(tmp_path / "another-program")
    else:
        command.write_text("another program\n")
    result: subprocess.CompletedProcess[str] = invoke(
        ROOT / "scripts/deploy.sh",
        *deployment_arguments(wheel_directory, tmp_path),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert command.is_symlink() if symlink else command.read_text() == "another program\n"
    assert not (tmp_path / "installation").exists()


def test_missing_wheel_has_no_deployment_side_effects(tmp_path: Path) -> None:
    """Explain the missing build before creating directories or requesting privileges."""
    result: subprocess.CompletedProcess[str] = invoke(
        ROOT / "scripts/deploy.sh",
        *deployment_arguments(tmp_path, tmp_path),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "run scripts/build.sh first" in result.stderr
    assert not (tmp_path / "installation").exists()


def test_failed_build_preserves_previous_wheel(wheel_directory: Path, tmp_path: Path) -> None:
    """A failed backend leaves the last successful wheel intact and removes temporary outputs."""
    checkout: Path = tmp_path / "checkout"
    scripts: Path = checkout / "scripts"
    scripts.mkdir(parents=True)
    for filename in ("build.sh", "run_python.sh", "distribution.py"):
        shutil.copyfile(ROOT / "scripts" / filename, scripts / filename)
    source: Path = checkout / "src/wanusage"
    source.mkdir(parents=True)
    shutil.copyfile(ROOT / "src/wanusage/__init__.py", source / "__init__.py")
    (checkout / "pyproject.toml").write_text(
        '[build-system]\nrequires = []\nbuild-backend = "missing_backend"\n'
    )
    output: Path = checkout / "dist"
    shutil.copytree(wheel_directory, output)
    wheel: Path = next(output.glob("*.whl"))
    original: bytes = wheel.read_bytes()
    result: subprocess.CompletedProcess[str] = invoke(
        scripts / "build.sh",
        "--no-build-isolation",
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert wheel.read_bytes() == original
    assert list(output.iterdir()) == [wheel]
