# Python

Use Python for new automation. Annotate variables and function signatures, give
functions clear docstrings, and keep functions focused with meaningful names.

# Application versioning

- The only application version source is `src/wanusage/__init__.py`.
- Install clone-local automation with `.venv/bin/python scripts/versioning.py install`.
- Versions advance at nonempty commit time, never on saves, builds, tests, or pushes.
- Main, bug fixes, unclassified branches, and PR repairs use one patch per batch.
  Only successful publication to the designated remote branch closes that batch.
- Classify genuine new feature branches before committing with
  `.venv/bin/python scripts/versioning.py classify feature`; allocate one minor
  and reset patch. Later fixes use patch batches. Explicit `classify fix` wins
  over branch names. Preserve `WANUsage-Versioning` commit trailers.
- Compatible merges preserve the higher version without an additional increment.
  Never lower a version. Major changes require an explicit user request and the
  documented one-command override. Keep build identifiers separate.
- Follow README.md for branch identity recovery, installation limits, and conflict
  recovery. Do not bypass hooks to avoid resolving a versioning error.
- Versioning setup does not authorize commits, pushes, releases, or deployment.
- Validate changes with `.venv/bin/python -m pytest`, `.venv/bin/ruff check .`, and
  `.venv/bin/mypy src scripts tests`.
