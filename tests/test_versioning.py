# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only
# See LICENSE for license terms and the warranty disclaimer.

"""Exercise installed version hooks against disposable clones and a local bare remote."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
VERSION_FILE: str = "src/wanusage/__init__.py"


class Checkout:
    """Drive real Git commands while keeping every mutation inside pytest's temporary directory."""

    def __init__(self, path: Path) -> None:
        """Bind command execution to an isolated working checkout."""
        self.path: Path = path
        self.environment: dict[str, str] = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Version Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Version Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
        for name in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "WANUSAGE_ALLOW_MAJOR"):
            self.environment.pop(name, None)

    def run(self, *arguments: str, success: bool = True) -> str:
        """Run Git or Python and include diagnostics when a behavioral expectation fails."""
        result: subprocess.CompletedProcess[str] = subprocess.run(
            arguments,
            cwd=self.path,
            env=self.environment,
            capture_output=True,
            text=True,
        )
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result.stdout + result.stderr

    def git(self, *arguments: str, success: bool = True) -> str:
        """Run a real Git operation through the installed hooks."""
        return self.run("git", *arguments, success=success)

    def tool(self, *arguments: str, success: bool = True) -> str:
        """Invoke the checked-in installer or explicit branch classification command."""
        return self.run(sys.executable, "scripts/versioning.py", *arguments, success=success)

    def write(self, path: str, content: str) -> None:
        """Create or replace a tracked test file without staging it automatically."""
        target: Path = self.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def change(self, name: str) -> None:
        """Commit one independent nonempty change through the installed hooks."""
        self.write(name, name + "\n")
        self.git("add", name)
        self.git("commit", "-m", name)

    def version(self, revision: str = "HEAD") -> str:
        """Read the version that actually reached a commit or the active index."""
        source: str = self.git("show", f"{revision}:{VERSION_FILE}")
        return source.split('__version__: str = "')[1].split('"')[0]

    def set_version(self, version: str) -> None:
        """Stage a deliberate version edit while retaining the source's other content."""
        path: Path = self.path / VERSION_FILE
        source: str = path.read_text(encoding="utf-8")
        old: str = source.split('__version__: str = "')[1].split('"')[0]
        self.write(VERSION_FILE, source.replace(f'"{old}"', f'"{version}"'))
        self.git("add", VERSION_FILE)


@pytest.fixture
def checkout(tmp_path: Path) -> Checkout:
    """Create a published baseline, then install the repository's actual automation."""
    remote: Path = tmp_path / "remote.git"
    path: Path = tmp_path / "checkout with spaces"
    path.mkdir()
    repo: Checkout = Checkout(path)
    repo.git("init", "--bare", str(remote))
    repo.git("init", "-b", "main")
    repo.git("remote", "add", "origin", str(remote))
    repo.write("scripts/versioning.py", (PROJECT_ROOT / "scripts/versioning.py").read_text())
    repo.write(".gitattributes", (PROJECT_ROOT / ".gitattributes").read_text())
    repo.write(VERSION_FILE, '"""A test package."""\n\n__version__: str = "1.0.0"  # keep this\n')
    repo.git("add", ".")
    repo.git("commit", "-m", "baseline")
    repo.git("push", "-u", "origin", "main")
    repo.tool("install")
    return repo


def test_main_batches_real_success_rejection_and_other_pushes(checkout: Checkout) -> None:
    """Only publication of this branch closes its active batch."""
    repo: Checkout = checkout
    repo.change("one")
    repo.change("two")
    assert repo.version() == repo.version("HEAD~1") == "1.0.1"
    repo.git("tag", "test-tag")
    repo.git("push", "origin", "test-tag")
    repo.git("push", "origin", "HEAD:refs/heads/elsewhere")
    repo.change("three")
    assert repo.version() == "1.0.1"
    remote: Path = repo.path.parent / "remote.git"
    rejection: Path = remote / "hooks/pre-receive"
    rejection.write_text("#!/bin/sh\nexit 1\n")
    rejection.chmod(0o755)
    repo.git("push", success=False)
    repo.change("four")
    assert repo.version() == "1.0.1"
    rejection.unlink()
    repo.git("push")
    repo.git("update-ref", "refs/remotes/origin/main", "HEAD~1")
    repo.change("five")
    repo.change("six")
    assert repo.version() == repo.version("HEAD~1") == "1.0.2"


def test_feature_allocation_and_pr_fix_batches(checkout: Checkout) -> None:
    """A feature receives one minor, then patches after each successful push."""
    repo: Checkout = checkout
    repo.change("patch-one")
    repo.git("push")
    repo.change("patch-two")
    repo.git("push")
    repo.git("switch", "-c", "feature/example")
    repo.tool("classify", "feature")
    assert repo.version() == "1.0.2"
    repo.change("feature-one")
    repo.change("feature-two")
    assert repo.version() == repo.version("HEAD~1") == "1.1.0"
    repo.git("push", "-u", "origin", "feature/example")
    repo.change("fix-one")
    repo.change("fix-two")
    assert repo.version() == repo.version("HEAD~1") == "1.1.1"
    repo.git("push")
    repo.change("fix-three")
    assert repo.version() == "1.1.2"


@pytest.mark.parametrize("classification", [None, "fix"])
def test_feature_names_do_not_allocate_minors(
    checkout: Checkout, classification: str | None
) -> None:
    """Unknown branches and explicit fixes both use patches, regardless of their names."""
    checkout.git("switch", "-c", "feature/actually-a-fix")
    if classification:
        checkout.tool("classify", classification)
    checkout.change("repair")
    assert checkout.version() == "1.0.1"


def test_failures_amend_empty_and_retries(checkout: Checkout) -> None:
    """Commit attempts neither consume feature allocations nor create empty version changes."""
    repo: Checkout = checkout
    repo.git("commit", "-m", "empty", success=False)
    repo.git("commit", "--allow-empty", "-m", "allowed empty")
    assert repo.version() == "1.0.0"
    repo.git("switch", "-c", "feature/retry")
    repo.tool("classify", "feature")
    hook: Path = repo.path / ".git/hooks/commit-msg"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    repo.write("retry", "retry\n")
    repo.git("add", "retry")
    repo.git("commit", "-m", "retry", success=False)
    assert repo.version("") == "1.1.0"
    hook.unlink()
    repo.git("commit", "-m", "retry")
    assert repo.version() == "1.1.0"
    repo.git("commit", "--amend", "-m", "amended")
    assert repo.version() == "1.1.0"
    repo.change("another")
    assert repo.version() == "1.1.0"
    repo.git("push", "-u", "origin", "feature/retry")
    repo.git("commit", "--allow-empty", "-m", "empty after publication")
    repo.change("after-empty")
    assert repo.version() == "1.1.1"


def test_partial_staging_selected_files_and_alternate_index(checkout: Checkout) -> None:
    """Index updates include only the version assignment and intended content."""
    repo: Checkout = checkout
    source: str = (repo.path / VERSION_FILE).read_text()
    repo.write(VERSION_FILE, source + "\nstaged_note: str = 'included'\n")
    repo.git("add", VERSION_FILE)
    repo.write(
        VERSION_FILE, source + "\nstaged_note: str = 'included'\nunstaged: str = 'private'\n"
    )
    repo.change("partial")
    assert "staged_note" in repo.git("show", f"HEAD:{VERSION_FILE}")
    assert "unstaged:" not in repo.git("show", f"HEAD:{VERSION_FILE}")
    assert "unstaged:" in repo.git("diff", "--", VERSION_FILE)
    repo.git("push")
    repo.write("selected", "selected\n")
    repo.git("add", "selected")
    repo.write("unselected", "unselected\n")
    repo.git("add", "unselected")
    repo.git("commit", "-m", "selected only", "--only", "selected")
    assert repo.version() == "1.0.2"
    assert "unselected" in repo.git("diff", "--cached", "--name-only")
    assert "unstaged:" not in repo.git("show", f"HEAD:{VERSION_FILE}")
    repo.environment["GIT_INDEX_FILE"] = str(repo.path.parent / "alternate-index")
    repo.git("read-tree", "HEAD")
    repo.change("alternate")
    assert repo.version() == "1.0.2"
    repo.environment.pop("GIT_INDEX_FILE")
    assert "unselected" in repo.git("diff", "--cached", "--name-only")


def test_unstaged_numeric_edit_stops_safely(checkout: Checkout) -> None:
    """An unrelated working version cannot be overwritten or smuggled into the index."""
    repo: Checkout = checkout
    repo.write(VERSION_FILE, '__version__: str = "9.0.0"\n')
    repo.write("change", "change\n")
    repo.git("add", "change")
    output: str = repo.git("commit", "-m", "change", success=False)
    assert "Unstaged version edit" in output
    assert repo.version("") == "1.0.0"
    assert "9.0.0" in (repo.path / VERSION_FILE).read_text()


def test_major_override_is_explicit_and_returns_to_patch_policy(checkout: Checkout) -> None:
    """Only a one-command override permits an intentional staged major change."""
    repo: Checkout = checkout
    repo.set_version("2.0.0")
    assert "WANUSAGE_ALLOW_MAJOR" in repo.git("commit", "-m", "major", success=False)
    repo.environment["WANUSAGE_ALLOW_MAJOR"] = "1"
    repo.git("commit", "-m", "authorized major")
    repo.environment.pop("WANUSAGE_ALLOW_MAJOR")
    assert repo.version() == "2.0.0"
    repo.git("push")
    repo.change("post-major")
    assert repo.version() == "2.0.1"


@pytest.mark.parametrize("fast_forward", [False, True])
def test_merges_retain_feature_version(checkout: Checkout, fast_forward: bool) -> None:
    """Automatic merge commits and fast-forwards retain the incoming feature allocation."""
    repo: Checkout = checkout
    repo.git("switch", "-c", "feature/merge")
    repo.tool("classify", "feature")
    repo.change("feature")
    repo.git("switch", "main")
    if not fast_forward:
        repo.change("main-change")
    repo.git("merge", "--no-edit", "feature/merge")
    assert repo.version() == "1.1.0"
    repo.change("after-merge")
    assert repo.version() == "1.1.0"


def test_older_branch_merge_retains_newer_main_and_nonversion_edits(checkout: Checkout) -> None:
    """A merge driver combines unrelated source edits while keeping the higher version."""
    repo: Checkout = checkout
    repo.git("switch", "-c", "repair")
    repo.write(
        VERSION_FILE,
        '"""An updated package description."""\n\n__version__: str = "1.0.0"  # keep this\n',
    )
    repo.git("add", VERSION_FILE)
    repo.git("commit", "-m", "description")
    repo.git("switch", "main")
    repo.git("switch", "-c", "feature/newer")
    repo.tool("classify", "feature")
    repo.change("larger-feature")
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", "feature/newer")
    repo.git("merge", "--no-edit", "repair")
    assert repo.version() == "1.1.0"
    assert "updated package description" in repo.git("show", f"HEAD:{VERSION_FILE}")


def test_source_conflicts_remain_real_conflicts(checkout: Checkout) -> None:
    """Version reconciliation must not swallow conflicting edits to other source content."""
    repo: Checkout = checkout
    original: str = (repo.path / VERSION_FILE).read_text()
    repo.git("switch", "-c", "repair")
    repo.write(VERSION_FILE, original.replace("A test package", "The repair description"))
    repo.git("add", VERSION_FILE)
    repo.git("commit", "-m", "repair description")
    repo.git("switch", "main")
    repo.write(VERSION_FILE, original.replace("A test package", "The main description"))
    repo.git("add", VERSION_FILE)
    repo.git("commit", "-m", "main description")
    repo.git("merge", "--no-edit", "repair", success=False)
    assert "UU" in repo.git("status", "--short")
    assert "<<<<<<<" in (repo.path / VERSION_FILE).read_text()


def test_rebase_replays_without_another_allocation(checkout: Checkout) -> None:
    """Rebasing an unpublished feature preserves the allocated minor on every replay."""
    repo: Checkout = checkout
    repo.git("switch", "-c", "feature/rebase")
    repo.tool("classify", "feature")
    repo.change("feature-one")
    repo.change("feature-two")
    repo.git("switch", "main")
    repo.change("main-change")
    repo.git("switch", "feature/rebase")
    repo.git("rebase", "main")
    assert repo.version() == repo.version("HEAD~1") == "1.1.0"
    repo.change("post-rebase")
    assert repo.version() == "1.1.0"


def test_clone_rename_and_recreated_feature_preserve_allocation(checkout: Checkout) -> None:
    """Durable commit metadata prevents a feature's second minor in later checkouts."""
    repo: Checkout = checkout
    repo.git("switch", "-c", "feature/durable")
    repo.tool("classify", "feature")
    repo.change("first")
    repo.git("push", "-u", "origin", "feature/durable")
    clone_path: Path = repo.path.parent / "new clone"
    repo.git(
        "clone", "-b", "feature/durable", str(repo.path.parent / "remote.git"), str(clone_path)
    )
    clone: Checkout = Checkout(clone_path)
    clone.tool("install")
    clone.tool("classify", "feature")
    clone.change("new-clone-fix")
    assert clone.version() == "1.1.1"
    clone.git("branch", "-m", "renamed-feature")
    clone.change("rename-fix")
    assert clone.version() == "1.1.1"
    clone.git("switch", "main")
    clone.git("branch", "-D", "renamed-feature")
    clone.git("switch", "-c", "feature/durable", "origin/feature/durable")
    clone.tool("classify", "feature")
    clone.change("recreated-fix")
    assert clone.version() == "1.1.1"


def test_installer_refuses_collisions_and_supports_worktrees(checkout: Checkout) -> None:
    """Repeat installation safely, refusing custom integrations before any overwrite."""
    repo: Checkout = checkout
    repo.tool("install")
    hook: Path = repo.path / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\n# an unrelated hook\nexit 0\n")
    assert "Existing pre-commit" in repo.tool("install", success=False)
    assert "unrelated" in hook.read_text()
    hook.unlink()
    repo.git("config", "core.hooksPath", "custom-hooks")
    assert "core.hooksPath" in repo.tool("install", success=False)
    repo.git("config", "--unset", "core.hooksPath")
    repo.git("config", "merge.wanusage-version.driver", "unrelated-driver")
    assert "merge driver" in repo.tool("install", success=False)
    repo.git("config", "--unset", "merge.wanusage-version.driver")
    repo.tool("install")
    repo.change("before-worktree")
    worktree_path: Path = repo.path.parent / "linked checkout"
    repo.git("worktree", "add", "-b", "linked", str(worktree_path))
    linked: Checkout = Checkout(worktree_path)
    linked.tool("install")
    linked.change("worktree-change")
    assert linked.version() == "1.0.2"


def test_unavailable_remote_mapping_and_live_divergence_stop(checkout: Checkout) -> None:
    """Unsafe publication assumptions fail before changing the staged version."""
    repo: Checkout = checkout
    repo.git("remote", "rename", "origin", "other")
    repo.write("blocked", "blocked\n")
    repo.git("add", "blocked")
    assert "Missing publication remote" in repo.git("commit", "-m", "blocked", success=False)
    repo.git("remote", "rename", "other", "origin")
    repo.git("config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main")
    assert "fetch mapping" in repo.git("commit", "-m", "blocked", success=False)
    repo.git("config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    remote_url: str = repo.git("config", "remote.origin.url").strip()
    repo.git("config", "remote.origin.url", str(repo.path.parent / "missing-remote"))
    assert "Cannot query publication remote" in repo.git("commit", "-m", "offline", success=False)
    repo.git("config", "remote.origin.url", remote_url)
    other_path: Path = repo.path.parent / "another author"
    repo.git("clone", "-b", "main", str(repo.path.parent / "remote.git"), str(other_path))
    other: Checkout = Checkout(other_path)
    other.change("other-author")
    other.git("push")
    assert "objects are missing" in repo.git("commit", "-m", "blocked", success=False)
    repo.git("fetch", "origin")
    assert "behind or diverged" in repo.git("commit", "-m", "blocked", success=False)
    assert repo.version("") == "1.0.0"


def test_missing_initial_primary_is_supported(checkout: Checkout) -> None:
    """An initialized repository need not already have its primary branch published."""
    repo: Checkout = checkout
    repo.git("push", "origin", "--delete", "main")
    repo.change("first-local")
    repo.change("second-local")
    assert repo.version() == repo.version("HEAD~1") == "1.0.1"


def test_merge_across_majors_requires_manual_resolution(checkout: Checkout) -> None:
    """Merging independently changed major versions never makes an automatic major decision."""
    repo: Checkout = checkout
    repo.git("switch", "-c", "major")
    repo.set_version("2.0.0")
    repo.environment["WANUSAGE_ALLOW_MAJOR"] = "1"
    repo.git("commit", "-m", "authorized major")
    repo.environment.pop("WANUSAGE_ALLOW_MAJOR")
    repo.git("switch", "main")
    repo.change("main")
    assert "majors" in repo.git("merge", "--no-edit", "major", success=False)
    assert repo.version("HEAD") == "1.0.1"
    repo.write(VERSION_FILE, '__version__: str = "2.0.0"\n')
    repo.git("add", VERSION_FILE)
    repo.environment["WANUSAGE_ALLOW_MAJOR"] = "1"
    repo.git("commit", "-m", "explicit major merge resolution")
    assert repo.version() == "2.0.0"


def test_selected_commit_preserves_staged_version_source_edits(checkout: Checkout) -> None:
    """Selected-file commits leave unrelated source edits staged and future commits usable."""
    repo: Checkout = checkout
    original: str = (repo.path / VERSION_FILE).read_text()
    repo.write(VERSION_FILE, original + "\nstaged_note: str = 'keep staged'\n")
    repo.git("add", VERSION_FILE)
    repo.write(
        VERSION_FILE,
        original + "\nstaged_note: str = 'keep staged'\nunstaged_note: str = 'keep unstaged'\n",
    )
    repo.write("selected", "selected\n")
    repo.git("add", "selected")
    repo.git("commit", "--only", "selected", "-m", "selected file")
    assert repo.version() == "1.0.1"
    assert "staged_note" not in repo.git("show", f"HEAD:{VERSION_FILE}")
    assert "staged_note" in repo.git("diff", "--cached", "--", VERSION_FILE)
    assert "unstaged_note" not in repo.git("diff", "--cached", "--", VERSION_FILE)
    repo.git("commit", "-m", "remaining staged source")
    assert repo.version() == "1.0.1"
    assert "staged_note" in repo.git("show", f"HEAD:{VERSION_FILE}")
    assert "unstaged_note" in repo.git("diff", "--", VERSION_FILE)


def test_unpublished_recreated_feature_and_explicit_separate_feature(checkout: Checkout) -> None:
    """Recreation recovers an allocation; explicit separate feature work gets a new one."""
    repo: Checkout = checkout
    repo.git("switch", "-c", "feature/local")
    repo.tool("classify", "feature")
    repo.change("local-feature")
    commit: str = repo.git("rev-parse", "HEAD").strip()
    repo.git("switch", "main")
    repo.git("branch", "-D", "feature/local")
    repo.git("switch", "-c", "feature/local", commit)
    repo.tool("classify", "feature")
    repo.change("recreated-local-feature")
    assert repo.version() == "1.1.0"
    repo.tool("classify", "feature", "--new-feature")
    repo.change("separate-feature")
    assert repo.version() == "1.2.0"


def test_version_preparation_preserves_line_endings(checkout: Checkout) -> None:
    """A version edit preserves source whitespace, comments, and Windows line endings."""
    repo: Checkout = checkout
    path: Path = repo.path / VERSION_FILE
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    repo.git("add", VERSION_FILE)
    repo.git("commit", "-m", "line endings")
    assert b'__version__: str = "1.0.1"  # keep this\r\n' in path.read_bytes()
    committed: subprocess.CompletedProcess[bytes] = subprocess.run(
        ["git", "show", f"HEAD:{VERSION_FILE}"],
        cwd=repo.path,
        env=repo.environment,
        capture_output=True,
        check=True,
    )
    assert committed.stdout == path.read_bytes()


def test_stale_index_alone_does_not_create_a_version_only_commit(checkout: Checkout) -> None:
    """An otherwise empty commit cannot turn stale index state into a new batch."""
    repo: Checkout = checkout
    repo.write("selected", "selected\n")
    repo.git("add", "selected")
    repo.git("commit", "--only", "selected", "-m", "selected")
    repo.git("push")
    repo.git("commit", "-m", "no intended changes", success=False)
    assert repo.version() == repo.version("") == "1.0.1"
    assert not repo.git("diff", "--cached", "--name-only").strip()
