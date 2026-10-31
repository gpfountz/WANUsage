# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only

"""Build and deploy WANUsage wheels locally on macOS and Linux."""

from __future__ import annotations

import argparse
import ast
import email
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

ROOT: Path = Path(__file__).resolve().parents[1]
WHEEL_NAME: re.Pattern[str] = re.compile(r"wanusage-(\d+)\.(\d+)\.(\d+)-py3-none-any\.whl")
LEGAL_FILES: tuple[str, ...] = ("LICENSE", "COPYRIGHT", "THIRD_PARTY_NOTICES.md")


@dataclass(frozen=True)
class Wheel:
    """Describe a validated, platform-independent WANUsage wheel."""

    path: Path
    version: str
    minimum_python: tuple[int, int]


def run(command: list[str], *, capture: bool = False) -> str:
    """Run a command and surface captured diagnostics when it fails."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        command, check=False, text=True, capture_output=capture
    )
    if result.returncode:
        details: str = (result.stdout or "") + (result.stderr or "")
        raise RuntimeError(f"Command failed ({result.returncode}): {command!r}\n{details}")
    return result.stdout or ""


def wheel_version(path: Path) -> tuple[int, int, int]:
    """Read a numeric application version without sorting filenames lexically."""
    match: re.Match[str] | None = WHEEL_NAME.fullmatch(path.name)
    if match is None:
        raise ValueError(f"Expected a wanusage-X.Y.Z-py3-none-any.whl file: {path}")
    return int(match[1]), int(match[2]), int(match[3])


def inspect_wheel(path: Path) -> Wheel:
    """Validate package identity, interpreter requirements, code, and legal resources."""
    version: str = ".".join(str(part) for part in wheel_version(path))
    dist_info: str = f"wanusage-{version}.dist-info"
    with zipfile.ZipFile(path) as archive:
        metadata: email.message.Message = email.message_from_bytes(
            archive.read(f"{dist_info}/METADATA")
        )
        if metadata["Name"] != "wanusage" or metadata["Version"] != version:
            raise ValueError(f"Wheel metadata does not match its filename: {path}")
        requirement: re.Match[str] | None = re.fullmatch(
            r">=\s*(\d+)\.(\d+)", metadata["Requires-Python"] or ""
        )
        if requirement is None:
            raise ValueError(f"Unsupported Requires-Python in {path}")
        required_files: tuple[str, ...] = (
            "wanusage/__init__.py",
            "wanusage/cli.py",
            f"{dist_info}/RECORD",
            *(f"wanusage/legal_texts/{name}" for name in LEGAL_FILES),
            *(f"{dist_info}/licenses/{name}" for name in LEGAL_FILES),
        )
        for filename in required_files:
            if not archive.read(filename):
                raise ValueError(f"Empty wheel resource: {filename}")
        corrupt_member: str | None = archive.testzip()
        if corrupt_member:
            raise ValueError(f"Corrupt wheel resource: {corrupt_member}")
    return Wheel(path.resolve(), version, (int(requirement[1]), int(requirement[2])))


def newest_wheel(directory: Path) -> Wheel:
    """Select the highest application version, then validate that exact artifact."""
    candidates: list[Path] = list(directory.glob("wanusage-*-py3-none-any.whl"))
    if not candidates:
        raise ValueError(f"No WANUsage wheel in {directory}; run scripts/build.sh first.")
    return inspect_wheel(max(candidates, key=wheel_version))


def source_version() -> str:
    """Read the sole application version assignment without importing application code."""
    module: ast.Module = ast.parse((ROOT / "src/wanusage/__init__.py").read_text())
    for statement in module.body:
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "__version__"
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            return statement.value.value
    raise ValueError("Cannot read __version__ from src/wanusage/__init__.py")


def build(output: Path, *, isolated: bool = True) -> Wheel:
    """Build in a temporary directory and publish only a complete current-version wheel."""
    version: str = source_version()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".wanusage-build-", dir=output) as temporary:
        command: list[str] = [sys.executable, "-m", "pip", "wheel", "--no-deps"]
        if not isolated:
            command.extend(("--no-build-isolation", "--check-build-dependencies"))
        command.extend(("--wheel-dir", temporary, str(ROOT)))
        run(command)
        wheel: Wheel = newest_wheel(Path(temporary))
        if wheel.version != version:
            raise ValueError(f"Built version {wheel.version}, expected source version {version}")
        destination: Path = output / wheel.path.name
        wheel.path.chmod(0o644)
        os.replace(wheel.path, destination)
    print(f"Built {destination}", flush=True)
    return inspect_wheel(destination)


def readable_tree(path: Path) -> None:
    """Grant read access and directory traversal without following symlinks or adding writes."""
    if path.is_symlink():
        return
    mode: int = stat.S_IMODE(path.stat().st_mode)
    path.chmod(mode | 0o444 | (0o111 if path.is_dir() else 0))
    if path.is_dir():
        for child in path.iterdir():
            readable_tree(child)


def environment_info(python: Path) -> tuple[Path, tuple[int, int]]:
    """Verify an interpreter belongs to the intended virtual environment and locate its packages."""
    code: str = (
        "import json, sys, sysconfig; "
        "print(json.dumps([sys.prefix, sys.base_prefix, "
        "sysconfig.get_path('purelib'), list(sys.version_info[:2])]))"
    )
    values: list[object] = json.loads(run([str(python), "-I", "-c", code], capture=True))
    if values[0] == values[1] or Path(str(values[0])).resolve() != python.parent.parent.resolve():
        raise ValueError(f"Not an intact virtual environment: {python.parent.parent}")
    version: object = values[3]
    if not isinstance(version, list) or len(version) != 2:
        raise ValueError(f"Cannot determine Python version for {python}")
    return Path(str(values[2])), (int(version[0]), int(version[1]))


def repair_permissions(environment: Path, packages: Path) -> None:
    """Repair access to installation directories and WANUsage's code and metadata only."""
    directory: Path = packages
    while directory.is_relative_to(environment):
        directory.chmod(stat.S_IMODE(directory.stat().st_mode) | 0o555)
        if directory == environment:
            break
        directory = directory.parent
    for directory in (environment.parent, environment / "bin"):
        directory.chmod(stat.S_IMODE(directory.stat().st_mode) | 0o555)
    for candidate in (packages / "wanusage", *packages.glob("wanusage-*.dist-info")):
        if candidate.exists():
            readable_tree(candidate)


def writable_location(path: Path) -> bool:
    """Check the nearest existing ancestor when a target directory does not exist yet."""
    while not path.exists():
        path = path.parent
    return os.access(path, os.W_OK | os.X_OK)


def check_link(link: Path, launcher: Path) -> None:
    """Refuse to replace an unrelated command or symbolic link."""
    if link.is_symlink():
        if link.resolve() != launcher.resolve():
            raise ValueError(f"{link} points elsewhere; choose another --bin-dir.")
    elif link.exists():
        raise ValueError(f"Refusing to overwrite an existing file: {link}")


def publish_link(link: Path, launcher: Path) -> None:
    """Atomically create the command symlink after installation has been verified."""
    check_link(link, launcher)
    if link.is_symlink():
        return
    temporary: Path = link.with_name(f".wanusage-{uuid4().hex}")
    try:
        temporary.symlink_to(launcher)
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)


def verify_installation(launcher: Path, version: str) -> None:
    """Check version and offline legal access as the invoking user, including after sudo."""
    prefix: list[str] = []
    invoking_user: str | None = os.environ.get("SUDO_USER")
    if os.geteuid() == 0 and invoking_user and invoking_user != "root":
        prefix = ["sudo", "-u", invoking_user, "--"]
    actual: str = run([*prefix, str(launcher), "--version"], capture=True).strip()
    if actual != f"wanusage {version}":
        raise ValueError(f"Installed version check failed: {actual!r}")
    run([*prefix, str(launcher), "--license"], capture=True)


def deploy(wheel: Wheel, installation: Path, bin_directory: Path) -> None:
    """Install a selected wheel locally, elevating only when target directories require it."""
    environment: Path = installation / ".venv"
    python: Path = environment / "bin/python"
    launcher: Path = environment / "bin/wanusage"
    link: Path = bin_directory / "wanusage"
    if installation.resolve() == ROOT:
        raise ValueError("Choose an installation directory outside the source checkout.")
    if sys.version_info[:2] < wheel.minimum_python:
        raise ValueError(f"Wheel requires Python {wheel.minimum_python}; choose WANUSAGE_PYTHON.")
    check_link(link, launcher)
    locations: list[Path] = [installation, environment, environment / "bin", bin_directory]
    locations.extend(environment.glob("lib/python*/site-packages/wanusage*"))
    if os.geteuid() != 0 and not all(writable_location(path) for path in locations):
        if shutil.which("sudo") is None:
            raise ValueError(
                "Installation requires write access; run with sudo or choose user paths."
            )
        print("Requesting sudo to install into the selected system directories.", flush=True)
        run(
            [
                "sudo",
                sys.executable,
                str(Path(__file__).resolve()),
                "deploy",
                "--wheel",
                str(wheel.path),
                "--install-dir",
                str(installation),
                "--bin-dir",
                str(bin_directory),
            ]
        )
        return
    installation.mkdir(parents=True, exist_ok=True)
    bin_directory.mkdir(parents=True, exist_ok=True)
    if not python.exists():
        if environment.exists():
            raise ValueError(
                f"Incomplete virtual environment: {environment}; repair it before retrying."
            )
        run([sys.executable, "-m", "venv", str(environment)])
    packages: Path
    version: tuple[int, int]
    packages, version = environment_info(python)
    if version < wheel.minimum_python:
        raise ValueError(
            f"Existing environment uses Python {version}; recreate it with Python 3.14+."
        )
    repair_permissions(environment, packages)
    print(f"Installing WANUsage {wheel.version} from {wheel.path}", flush=True)
    run(
        [
            str(python),
            "-I",
            "-m",
            "pip",
            "--isolated",
            "install",
            "--no-index",
            "--no-deps",
            "--force-reinstall",
            str(wheel.path),
        ]
    )
    repair_permissions(environment, packages)
    run([str(python), "-I", "-m", "pip", "--isolated", "check"])
    verify_installation(launcher, wheel.version)
    publish_link(link, launcher)
    print(f"Deployed wanusage {wheel.version}: {link}", flush=True)


def main() -> int:
    """Dispatch portable build/deployment commands with readable failure messages."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(
        dest="command", required=True
    )
    build_parser: argparse.ArgumentParser = commands.add_parser(
        "build", help="Build current sources"
    )
    build_parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    build_parser.add_argument(
        "--no-build-isolation",
        action="store_true",
        help="Use already-installed build dependencies (also supports offline builds)",
    )
    deploy_parser: argparse.ArgumentParser = commands.add_parser(
        "deploy", help="Install newest wheel"
    )
    source: argparse._MutuallyExclusiveGroup = deploy_parser.add_mutually_exclusive_group()
    source.add_argument("--wheel-dir", type=Path, default=ROOT / "dist")
    source.add_argument("--wheel", type=Path, help="Install this specific wheel instead")
    deploy_parser.add_argument("--install-dir", type=Path, default=Path("/usr/local/wanusage"))
    deploy_parser.add_argument("--bin-dir", type=Path, default=Path("/usr/local/bin"))
    arguments: argparse.Namespace = parser.parse_args()
    previous_umask: int = os.umask(0o022)
    try:
        if sys.platform not in {"darwin", "linux"} or sys.version_info < (3, 14):
            raise ValueError("These scripts require macOS or Linux and Python 3.14 or later.")
        if arguments.command == "build":
            build(
                arguments.output_dir.expanduser().resolve(),
                isolated=not arguments.no_build_isolation,
            )
        else:
            wheel: Wheel = (
                inspect_wheel(arguments.wheel.expanduser().resolve())
                if arguments.wheel
                else newest_wheel(arguments.wheel_dir.expanduser().resolve())
            )
            deploy(
                wheel,
                arguments.install_dir.expanduser().absolute(),
                arguments.bin_dir.expanduser().absolute(),
            )
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        os.umask(previous_umask)


if __name__ == "__main__":
    raise SystemExit(main())
