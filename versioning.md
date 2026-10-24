<!-- SPDX-FileCopyrightText: 2026 Greg Pfountz -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# Automatic application versioning

`src/wanusage/__init__.py` is the single application version source. Hatch reads
it for package metadata, and the CLI reads it for `--version`. Saving files,
testing, building, and attempting a push do not change the version. There is no
separate platform build identifier in this project.

Install the local Git hooks and merge driver after cloning or creating the
virtual environment:

```bash
.venv/bin/python scripts/versioning.py install
```

The installer uses `origin` and `main` by default; `--remote NAME --primary BRANCH`
selects a different publication destination. Each branch's upstream selects its
remote branch; otherwise its own branch name is used. Installation is repeatable.
It refuses existing unrelated hooks, a custom `core.hooksPath`, or a conflicting
merge driver rather than overwriting them. Reinstall after moving the checkout
or changing its Python environment. Linked worktrees share the installed hooks;
the hooks locate the script in the active checkout.

The first nonempty commit on main increments patch once. More commits keep that
version until their batch is successfully pushed to its designated remote branch.
The next commit then starts another patch batch. Failed pushes, tag pushes, and
pushes to another branch leave the batch open. The hook queries the remote at
commit time, so commits require remote access. If publication objects are missing,
fetch and retry; if history diverged, fetch and merge or rebase before committing.
No push wrapper is required, and installation never pushes anything.

Unknown branches use patch batches, including branches whose names contain
`feature`. Explicitly classify a genuine new feature before its first commit:

```bash
git switch -c codex/my-feature
.venv/bin/python scripts/versioning.py classify feature
```

That feature receives one minor increment, with patch reset to zero. Its later
commits share the version until publication. Follow-up fixes to the same feature
or PR receive patch increments per successful push batch. To classify a repair:

```bash
.venv/bin/python scripts/versioning.py classify fix
```

Classification does not edit the version. Local configuration stores the branch's
identity and intent; `WANUsage-Versioning` commit trailers preserve its allocations
through clones, amendments, rebases, and branch recreation. Keep those trailers
when editing commit messages. Local branch renames retain their configuration.
For a renamed branch cloned without that configuration, use `classify fix` to
continue its existing release. If a separate genuine feature inherits another
feature's metadata, use `classify feature --new-feature` to explicitly allocate a
new minor. This flag is also the deliberate way to start separate feature work
on an existing branch; do not use it for PR repairs.

To correct classification before the first successful commit, rerun `classify`
with the correct kind. If an aborted commit already staged a version, restore
only its numeric assignment to the HEAD value in both the index and working file
before retrying; preserve other staged and unstaged edits. A successful feature
allocation remains allocated even if its branch is subsequently classified as a
fix. To correct an already committed mistaken allocation, reconcile that version
and its commit metadata explicitly before publication; classification alone does
not rewrite history.

The hooks preserve unrelated staged and unstaged source edits and respect
selected-file commits and `GIT_INDEX_FILE`. A conflicting unstaged version edit
stops the commit. A rejected commit can be retried without consuming another
increment. If a selected-file or alternate-index commit leaves an older version
in the original index while the working version matches HEAD, the next commit
reconciles that assignment while preserving the remaining staged source edits.
Empty commits do not introduce version changes. Amend only unpublished
commits; rebases replay their existing allocations. Compatible merges retain the
highest incoming or main version, including fast-forwards, and leave genuine
non-version conflicts for normal resolution. Version numbers identify batches;
concurrent branches can share the same number.

A major increment requires explicit authorization. After that authorization,
edit only `__version__`, stage the intended changes, and apply a one-command
override:

```bash
WANUSAGE_ALLOW_MAJOR=1 git commit -m "Release the explicitly requested major version"
```

Normal commits reject manual major edits and unexpected manual minor/patch edits.
A conflicting merge across different majors requires manual resolution to the higher version
and the same explicitly authorized one-command override. Neither path permits a
downgrade. No override changes a platform build identifier.

Hooks are clone-local and can be bypassed. They do not enforce this policy in
GitHub web edits, other clones, or CI-created commits. Detached commits, custom
hook paths, explicit remote push refspecs, and nonstandard fetch mappings require
manual integration; the default installer/hooks stop with recovery instructions.
Repository CI exercises the installed workflow in temporary repositories against
a local bare remote; it does not push test branches to the hosted repository.
