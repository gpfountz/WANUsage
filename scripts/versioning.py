"""Prepare application versions as branch-specific, successfully published Git batches."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

VERSION_FILE: str = "src/wanusage/__init__.py"
TRAILER: str = "WANUsage-Versioning: "
ASSIGNMENT: re.Pattern[str] = re.compile(
    r"""(?m)^__version__(?:\s*:\s*str)?\s*=\s*(["'])(?P<value>[^"'\n]+)\1(?=\s*(?:#.*)?$)"""
)
INSTALL_MARKER: str = "# WANUsage versioning hook v1"


@dataclass(frozen=True, order=True)
class Version:
    """Represent a canonical application release, independently of build identifiers."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> Version:
        """Require exactly three canonical nonnegative numeric components."""
        if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
            raise ValueError(f"Invalid application version: {value!r}")
        return cls(*map(int, value.split(".")))

    def __str__(self) -> str:
        """Format the package and CLI release string."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, feature: bool) -> Version:
        """Allocate a minor for a new feature or a patch for another batch."""
        return (
            Version(self.major, self.minor + 1, 0)
            if feature
            else Version(self.major, self.minor, self.patch + 1)
        )


@dataclass(frozen=True)
class Batch:
    """Persist successful allocation evidence in the commit that contains the version."""

    identity: str
    branch: str
    batch: str
    kind: str
    feature: str
    version: str

    @classmethod
    def read(cls, message: str) -> Batch | None:
        """Recover the last machine trailer without interpreting ordinary commit prose."""
        lines: list[str] = [line for line in message.splitlines() if line.startswith(TRAILER)]
        if not lines:
            return None
        try:
            values: object = json.loads(lines[-1][len(TRAILER) :])
            if not isinstance(values, dict) or set(values) != set(cls.__dataclass_fields__):
                raise ValueError("Unexpected versioning fields")
            if not all(isinstance(value, str) for value in values.values()):
                raise ValueError("Non-string versioning field")
            result: Batch = cls(**values)
            Version.parse(result.version)
            if result.kind not in {"feature", "fix"}:
                raise ValueError("Unknown branch classification")
            return result
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Invalid WANUsage-Versioning trailer; repair the commit metadata."
            ) from error

    def trailer(self) -> str:
        """Serialize durable branch identity, feature allocation, and batch information."""
        return TRAILER + json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)


class Repository:
    """Run Git in the active checkout while honoring Git's selected or alternate index."""

    def __init__(self, root: Path) -> None:
        """Bind automation to one checkout, including linked worktrees."""
        self.root: Path = root
        self.publications: dict[str, str] = {}

    def git(self, *arguments: str, input_text: str | None = None, optional: bool = False) -> str:
        """Run a checked Git command without changing the caller's index environment."""
        result: subprocess.CompletedProcess[bytes] = subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            input=input_text.encode("utf-8") if input_text is not None else None,
            capture_output=True,
            check=False,
        )
        if result.returncode and not optional:
            raise ValueError(
                result.stderr.decode("utf-8").strip() or f"Git command failed: {arguments[0]}"
            )
        return result.stdout.decode("utf-8") if result.returncode == 0 else ""

    def config(self, name: str, value: str | None = None) -> str:
        """Read effective configuration or write a clone-local versioning setting."""
        if value is not None:
            return self.git("config", "--local", name, value).strip()
        return self.git("config", "--get", name, optional=True).strip()

    def path(self, name: str) -> Path:
        """Resolve per-worktree administrative paths without assuming a .git directory."""
        return Path(self.git("rev-parse", "--path-format=absolute", "--git-path", name).strip())

    def ancestor(self, older: str, newer: str) -> bool:
        """Check publication ancestry using commit objects, rather than version arithmetic."""
        result: subprocess.CompletedProcess[str] = subprocess.run(
            ["git", "-C", str(self.root), "merge-base", "--is-ancestor", older, newer],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise ValueError("Cannot establish publication ancestry; fetch the configured remote.")
        return result.returncode == 0

    def source(self, revision: str) -> str:
        """Read only the authoritative version source at an index or commit revision."""
        return self.git("show", f"{revision}:{VERSION_FILE}")

    def version(self, revision: str) -> Version:
        """Parse the source version without importing application dependencies."""
        return source_version(self.source(revision))

    def published(self, branch: str) -> str:
        """Query the actual designated branch, including pushes made outside this tool."""
        if branch in self.publications:
            return self.publications[branch]
        remote: str = self.config("wanusage.remote")
        if not remote or not self.config(f"remote.{remote}.url"):
            raise ValueError(
                "Missing publication remote; rerun install --remote NAME --primary BRANCH."
            )
        mapping: str = self.config(f"remote.{remote}.fetch")
        if mapping != f"+refs/heads/*:refs/remotes/{remote}/*":
            raise ValueError("Unsupported remote fetch mapping; use the standard heads mapping.")
        branch_remote: str = self.config(f"branch.{branch}.remote")
        push_remote: str = self.config(f"branch.{branch}.pushRemote") or self.config(
            "remote.pushDefault"
        )
        if (branch_remote and branch_remote != remote) or (push_remote and push_remote != remote):
            raise ValueError(
                "Branch remote differs from wanusage.remote; reconcile configuration first."
            )
        if self.config(f"remote.{remote}.push"):
            raise ValueError("Explicit remote push refspecs are unsupported; use branch upstreams.")
        target: str = self.config(f"branch.{branch}.merge") or f"refs/heads/{branch}"
        if not target.startswith("refs/heads/"):
            raise ValueError("Publication target must be a branch under refs/heads/.")
        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "ls-remote",
                    "--exit-code",
                    "--heads",
                    remote,
                    target,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("Publication remote timed out; restore access and retry.") from error
        if result.returncode == 2:
            self.publications[branch] = ""
            return ""
        if result.returncode:
            raise ValueError(
                "Cannot query publication remote; restore access and retry the commit."
            )
        lines: list[str] = result.stdout.splitlines()
        if len(lines) != 1 or lines[0].split()[1] != target:
            raise ValueError("Ambiguous publication branch; check the configured upstream.")
        commit: str = lines[0].split()[0]
        if not self.git("rev-parse", "--verify", f"{commit}^{{commit}}", optional=True):
            raise ValueError(f"Publication objects are missing; run git fetch {remote} and retry.")
        self.publications[branch] = commit
        return commit

    def latest_batch(self, revision: str = "HEAD") -> tuple[str, Batch] | None:
        """Find the latest first-parent allocation, retaining identity through amendments."""
        entry: str = self.git(
            "log",
            "-1",
            "--first-parent",
            "--fixed-strings",
            f"--grep={TRAILER}",
            "--format=%H%n%B",
            revision,
            optional=True,
        )
        if not entry:
            return None
        commit, _, message = entry.partition("\n")
        batch: Batch | None = Batch.read(message)
        return (commit, batch) if batch else None

    def identity(self, branch: str, published: str) -> tuple[str, str, str]:
        """Recover published branch intent or establish a distinct local branch identity."""
        prefix: str = f"branch.{branch}.wanusage"
        identity: str = self.config(prefix + "Identity")
        previous: tuple[str, Batch] | None = self.latest_batch(published) if published else None
        if not previous and not published:
            local: tuple[str, Batch] | None = self.latest_batch()
            if local and local[1].branch == branch:
                previous = local
        if not identity:
            identity = (
                previous[1].identity
                if previous and previous[1].branch == branch
                else uuid.uuid4().hex
            )
            self.config(prefix + "Identity", identity)
        kind: str = self.config(prefix + "Kind")
        feature: str = self.config(prefix + "Feature")
        if previous and previous[1].identity == identity:
            kind = kind or previous[1].kind
            feature = feature or previous[1].feature
        if feature:
            self.config(prefix + "Feature", feature)
        return identity, kind or "fix", feature


def source_match(source: str) -> re.Match[str]:
    """Locate exactly one version assignment, retaining annotations and surrounding text."""
    matches: list[re.Match[str]] = list(ASSIGNMENT.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"Expected one __version__ assignment in {VERSION_FILE}.")
    return matches[0]


def source_version(source: str) -> Version:
    """Validate the authoritative assignment's semantic version."""
    return Version.parse(source_match(source).group("value"))


def replace_version(source: str, version: Version) -> str:
    """Replace only the numeric assignment value, preserving all unrelated source bytes."""
    match: re.Match[str] = source_match(source)
    return source[: match.start("value")] + str(version) + source[match.end("value") :]


def replaying(repo: Repository) -> bool:
    """Identify Git replays whose already allocated versions must not advance."""
    return any(repo.path(name).exists() for name in ("rebase-merge", "rebase-apply"))


def stage_version(repo: Repository, staged: str, desired: Version) -> None:
    """Update only the version value in the active index and working source independently."""
    path: Path = repo.root / VERSION_FILE
    if path.is_symlink():
        raise ValueError("The version source must be a regular file, not a symlink.")
    working: str = path.read_bytes().decode("utf-8")
    allowed: set[Version] = {source_version(staged), desired}
    if repo.git("rev-parse", "--verify", "HEAD", optional=True):
        allowed.add(repo.version("HEAD"))
    if source_version(working) not in allowed:
        raise ValueError(
            "Unstaged version edit differs from the index; reconcile it before committing."
        )
    updated: str = replace_version(staged, desired)
    mode: str = repo.git("ls-files", "--stage", "--", VERSION_FILE).split()[0]
    if mode != "100644":
        raise ValueError("Expected a regular nonexecutable version source in the index.")
    blob: str = repo.git("hash-object", "-w", "--stdin", input_text=updated).strip()
    repo.git("update-index", "--cacheinfo", f"{mode},{blob},{VERSION_FILE}")
    path.write_bytes(replace_version(working, desired).encode("utf-8"))


def allocate(repo: Repository, branch: str, head: str, staged: Version, merging: bool) -> Batch:
    """Compute a stable branch batch from live publication and successful commit evidence."""
    published: str = repo.published(branch)
    if published and (not head or not repo.ancestor(published, head)):
        raise ValueError(
            "Branch is behind or diverged from publication; fetch and merge/rebase first."
        )
    identity, kind, feature = repo.identity(branch, published)
    previous: tuple[str, Batch] | None = repo.latest_batch() if head else None
    published_batch: tuple[str, Batch] | None = repo.latest_batch(published) if published else None
    head_version: Version = repo.version("HEAD") if head else staged
    desired: Version
    batch_id: str = uuid.uuid4().hex
    if merging:
        parents: list[str] = (
            repo.path("MERGE_HEAD").read_text().splitlines()
            if repo.path("MERGE_HEAD").exists()
            else []
        )
        versions: list[Version] = [head_version, staged, *(repo.version(p) for p in parents)]
        if len({version.major for version in versions}) != 1 and (
            os.environ.get("WANUSAGE_ALLOW_MAJOR") != "1" or staged != max(versions)
        ):
            raise ValueError(
                "Merging majors requires manual resolution to the higher version and "
                "explicit authorization with WANUSAGE_ALLOW_MAJOR=1."
            )
        desired = max(versions)
    else:
        open_batch: bool = bool(
            previous
            and previous[1].identity == identity
            and previous[1].feature == feature
            and previous[1].version == str(head_version)
            and (not published or not repo.ancestor(previous[0], published))
            and (not published_batch or published_batch[1].batch != previous[1].batch)
        )
        transferred: bool = bool(
            previous
            and published
            and branch == repo.config("wanusage.primary")
            and previous[1].version == str(head_version)
            and head_version > repo.version(published)
            and not repo.ancestor(previous[0], published)
        )
        if (open_batch or transferred) and previous:
            desired = head_version
            batch_id = previous[1].batch
        else:
            allocated: bool = bool(
                feature
                and repo.git(
                    "log",
                    "-1",
                    "--fixed-strings",
                    f'--grep="feature":"{feature}"',
                    "--format=%H",
                    "HEAD",
                    optional=True,
                )
            )
            desired = head_version.bump(kind == "feature" and bool(feature) and not allocated)
    if staged.major != head_version.major:
        if os.environ.get("WANUSAGE_ALLOW_MAJOR") != "1" or staged <= head_version:
            raise ValueError(
                "Major changes require explicit authorization and WANUSAGE_ALLOW_MAJOR=1."
            )
        desired = staged
    elif staged not in {head_version, desired} and not merging:
        working_version: Version = source_version((repo.root / VERSION_FILE).read_text("utf-8"))
        if staged > head_version or working_version != head_version:
            raise ValueError(
                f"Unexpected staged version {staged}; expected {head_version} or {desired}."
            )
    if desired < head_version:
        raise ValueError("Refusing to lower the application version.")
    return Batch(identity, branch, batch_id, kind, feature, str(desired))


def prepare(repo: Repository, merging: bool = False) -> None:
    """Prepare only nonempty commits and preserve evidence until the commit message is written."""
    pending: Path = repo.path("wanusage-versioning-pending.json")
    pending.unlink(missing_ok=True)
    if replaying(repo):
        return
    head: str = repo.git("rev-parse", "--verify", "HEAD", optional=True).strip()
    changes: str = repo.git("diff", "--cached", "--name-only", *([head] if head else []))
    if not changes:
        return
    source: str = repo.source("")
    if head and changes.strip() == VERSION_FILE:
        current: Version = repo.version("HEAD")
        indexed: Version = source_version(source)
        if (
            indexed < current
            and indexed.major == current.major
            and replace_version(source, current) == repo.source("HEAD")
            and source_version((repo.root / VERSION_FILE).read_text("utf-8")) == current
        ):
            stage_version(repo, source, current)
            raise ValueError(
                "Reconciled the stale index version; no staged changes remain. "
                "Stage an intended change or retry with --allow-empty."
            )
    branch: str = repo.git("symbolic-ref", "--quiet", "--short", "HEAD", optional=True).strip()
    if not branch:
        raise ValueError("Detached commits are unsupported; switch to a classified branch first.")
    if not repo.published(branch) and branch != repo.config("wanusage.primary"):
        primary: str = repo.config("wanusage.primary")
        baseline: str = repo.published(primary)
        if not baseline:
            raise ValueError(
                "Primary publication branch is missing; publish it or configure a baseline."
            )
        if not repo.git("merge-base", baseline, "HEAD", optional=True):
            raise ValueError("Branch has no common history with the primary publication branch.")
    batch: Batch = allocate(
        repo, branch, head, source_version(source), merging or repo.path("MERGE_HEAD").exists()
    )
    stage_version(repo, source, Version.parse(batch.version))
    payload: dict[str, object] = {
        "tree": repo.git("write-tree").strip(),
        "batch": asdict(batch),
    }
    pending.write_text(json.dumps(payload), encoding="utf-8")


def message(repo: Repository, path: Path, source: str) -> None:
    """Attach allocation evidence only when the prepared index still matches the commit."""
    pending: Path = repo.path("wanusage-versioning-pending.json")
    if replaying(repo):
        return
    batch: Batch | None = None
    if pending.exists():
        payload: dict[str, object] = json.loads(pending.read_text(encoding="utf-8"))
        if payload["tree"] != repo.git("write-tree").strip():
            raise ValueError("Index changed after version preparation; retry the commit.")
        batch = Batch(**cast(dict[str, str], payload["batch"]))
    elif (
        source == "commit"
        or repo.git("write-tree").strip()
        == repo.git("rev-parse", "--verify", "HEAD^{tree}", optional=True).strip()
    ):
        batch = Batch.read(repo.git("log", "-1", "--format=%B"))
    if batch is None:
        return
    original: str = path.read_text(encoding="utf-8")
    lines: list[str] = [line for line in original.splitlines() if not line.startswith(TRAILER)]
    path.write_text("\n".join(lines).rstrip() + "\n\n" + batch.trailer() + "\n", encoding="utf-8")
    pending.unlink(missing_ok=True)


def classify(repo: Repository, kind: str, new_feature: bool = False) -> None:
    """Set explicit branch intent without modifying the tracked application version."""
    branch: str = repo.git("symbolic-ref", "--short", "HEAD").strip()
    if kind == "feature" and branch == repo.config("wanusage.primary"):
        raise ValueError("Create a genuine feature branch before classifying it as a feature.")
    if new_feature and kind != "feature":
        raise ValueError("--new-feature is only valid with classify feature.")
    published: str = repo.published(branch)
    _, _, feature = repo.identity(branch, published)
    previous: tuple[str, Batch] | None = repo.latest_batch()
    identity: str = repo.config(f"branch.{branch}.wanusageIdentity")
    if (
        kind == "feature"
        and not feature
        and not new_feature
        and previous
        and previous[1].feature
        and previous[1].identity != identity
    ):
        raise ValueError(
            "Inherited feature metadata belongs to another branch. Use classify fix to continue "
            "its release, or classify feature --new-feature for a separate genuine feature."
        )
    if previous and previous[1].identity == identity:
        feature = feature or previous[1].feature
    if kind == "feature" and (not feature or new_feature):
        feature = uuid.uuid4().hex
        repo.config(f"branch.{branch}.wanusageFeature", feature)
    repo.config(f"branch.{branch}.wanusageKind", kind)
    print(f"{branch}: {kind}; version will be prepared on the next nonempty commit.")


def merge_version(base: Path, ours: Path, theirs: Path) -> int:
    """Merge non-version edits normally while selecting the highest compatible version."""
    texts: list[str] = [path.read_bytes().decode("utf-8") for path in (base, ours, theirs)]
    versions: list[Version] = [source_version(source) for source in texts]
    if len({version.major for version in versions}) != 1:
        raise ValueError("Version merge crosses majors; resolve the version source manually.")
    desired: Version = max(versions)
    with tempfile.TemporaryDirectory(prefix="wanusage-version-merge-") as temporary:
        paths: list[Path] = [Path(temporary) / name for name in ("base", "ours", "theirs")]
        for path, source in zip(paths, texts, strict=True):
            path.write_bytes(replace_version(source, desired).encode("utf-8"))
        result: subprocess.CompletedProcess[bytes] = subprocess.run(
            [
                "git",
                "merge-file",
                "-p",
                "-L",
                "ours",
                "-L",
                "base",
                "-L",
                "theirs",
                str(paths[1]),
                str(paths[0]),
                str(paths[2]),
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode < 0 or result.returncode > 127:
            raise ValueError("Git could not merge the version source.")
        ours.write_bytes(result.stdout)
        return 0 if result.returncode == 0 else 1


def install(repo: Repository, remote: str, primary: str) -> None:
    """Install owned hooks and a version merge driver, refusing unrelated existing integrations."""
    if not repo.config(f"remote.{remote}.url"):
        raise ValueError(f"Remote {remote!r} is missing; configure it before installation.")
    hook_setting: str = repo.config("core.hooksPath")
    if hook_setting:
        raise ValueError(
            "Custom core.hooksPath detected; integrate versioning there explicitly first."
        )
    executable: str = str(Path(sys.executable).absolute())
    command: str = (
        f'{shlex.quote(executable)} "$(git rev-parse --show-toplevel)/scripts/versioning.py"'
    )
    hooks: dict[str, str] = {
        "pre-commit": f"{command} prepare",
        "pre-merge-commit": f"{command} prepare --merge",
        "prepare-commit-msg": f'{command} message "$1" "${{2-}}"',
    }
    contents: dict[Path, str] = {}
    for name, action in hooks.items():
        path: Path = repo.path(f"hooks/{name}")
        if path.exists() and INSTALL_MARKER not in path.read_text(encoding="utf-8"):
            raise ValueError(f"Existing {name} hook; integrate it explicitly before installing.")
        contents[path] = f"#!/bin/sh\n{INSTALL_MARKER}\nexec {action}\n"
    driver: str = command + ' merge "%O" "%A" "%B"'
    existing: str = repo.config("merge.wanusage-version.driver")
    owned: str = repo.config("wanusage.driver")
    if existing and existing not in {driver, owned}:
        raise ValueError("Existing wanusage-version merge driver; resolve the integration first.")
    for path, content in contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
    repo.config("merge.wanusage-version.name", "WANUsage compatible application versions")
    repo.config("merge.wanusage-version.driver", driver)
    repo.config("wanusage.driver", driver)
    repo.config("wanusage.remote", remote)
    repo.config("wanusage.primary", primary)
    print(f"Installed hooks and merge driver using {executable}; publication: {remote}/{primary}.")


def main() -> int:
    """Dispatch local setup, branch intent, installed hooks, and the Git merge driver."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(
        dest="command", required=True
    )
    installer: argparse.ArgumentParser = commands.add_parser("install")
    installer.add_argument("--remote", default="origin")
    installer.add_argument("--primary", default="main")
    classifier: argparse.ArgumentParser = commands.add_parser("classify")
    classifier.add_argument("kind", choices=("feature", "fix"))
    classifier.add_argument("--new-feature", action="store_true")
    preparer: argparse.ArgumentParser = commands.add_parser("prepare")
    preparer.add_argument("--merge", action="store_true")
    messenger: argparse.ArgumentParser = commands.add_parser("message")
    messenger.add_argument("path", type=Path)
    messenger.add_argument("source", nargs="?", default="")
    merger: argparse.ArgumentParser = commands.add_parser("merge")
    for argument in ("base", "ours", "theirs"):
        merger.add_argument(argument, type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    try:
        if arguments.command == "merge":
            return merge_version(arguments.base, arguments.ours, arguments.theirs)
        root: Path = Path(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        )
        repo: Repository = Repository(root)
        if arguments.command == "install":
            install(repo, arguments.remote, arguments.primary)
        elif arguments.command == "classify":
            classify(repo, arguments.kind, arguments.new_feature)
        elif arguments.command == "prepare":
            prepare(repo, arguments.merge)
        elif arguments.command == "message":
            message(repo, arguments.path, arguments.source)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Versioning: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
