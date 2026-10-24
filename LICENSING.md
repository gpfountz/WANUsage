<!-- SPDX-FileCopyrightText: 2026 Greg Pfountz -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# Licensing and contributions

WANUsage's original project material is copyright (C) 2026 Greg Pfountz and is
licensed under **GNU GPL version 3 only**, SPDX `GPL-3.0-only`. The complete terms
are in [LICENSE](LICENSE), with the application notice in [COPYRIGHT](COPYRIGHT)
and the distribution inventory in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The choice is version 3 only. `GPL-3.0-or-later` would additionally let recipients
choose a later GPL version; this project does not grant that additional choice.
The FSF license document is reproduced verbatim, including its illustrative
appendix; this project's notices and package metadata identify the chosen variant.

## Reuse and modifications

You may use WANUsage, modify it privately, and use it commercially. Private
modifications do not have to be published merely because they exist. You may
charge for distributing copies, subject to GPLv3's conditions.

When conveying covered source or modified versions, preserve the applicable
copyright, license, and no-warranty notices; identify modifications and their
relevant dates; and license the covered work as GPLv3 requires. Preserve the
application's appropriate legal notices, including access through `--help` and
`--license`, where GPLv3 requires it. Third-party material keeps its separate
terms. This license does not require advertising credit or assign contributors'
copyright to the maintainer.

When conveying object code, comply with an applicable GPLv3 section 6 method of
providing the corresponding source. Source must cover the exact delivered version
and the scripts and materials needed to build and install it, plus applicable
installation information and third-party source obligations. A moving repository
branch or an archive missing those materials is not a substitute.

WANUsage carries the GPL's standard no-warranty and limitation-of-liability terms,
subject to applicable law. These notes summarize the license; the full license
controls. See [GPLv3](https://www.gnu.org/licenses/gpl-3.0.html) and the
[SPDX identifier record](https://spdx.org/licenses/GPL-3.0-only.html).

## Contributions

Unless explicitly agreed otherwise, contributions intended for inclusion in
WANUsage are offered under `GPL-3.0-only`. Contributors retain their copyright.
Submit only material you have permission to contribute under those terms. Retain
existing author notices and add appropriate notices for independently copyrighted
contributions. Identify separately licensed material and its provenance before
including it. There is no copyright-assignment or CLA requirement.

Original Python files use short SPDX/copyright comments before their module
docstrings and future imports. Commentable configuration files use their own
comment syntax; JSON editor settings use adjacent `.license` sidecars. Do not
apply the project's author notice to vendor code or generated third-party files.
This convention is not a claim of full REUSE-tool certification.

## Packaging and checking a distribution

`src/wanusage/__init__.py` remains the only application version source. Licensing
edits do not manually bump it. Installed commit hooks apply the repository's batch
policy when changes are committed.

Hatchling includes `LICENSE`, `COPYRIGHT`, and `THIRD_PARTY_NOTICES.md` in wheel
license metadata and copies those canonical files to `wanusage/legal_texts/` for
offline runtime access. No separate tracked runtime copies are maintained. The
source distribution also includes the tests, configuration template, documentation,
and versioning script. Source runs read canonical files from the checkout when
packaged resources are absent.

Prepare local verification artifacts in a fresh temporary directory:

```bash
artifacts_dir="$(mktemp -d "${TMPDIR:-/tmp}/wanusage-legal.XXXXXX")"
.venv/bin/python -m hatchling build -t sdist -t wheel -d "$artifacts_dir"
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy src scripts tests
```

The packaging tests build real archives in temporary directories, compare included
legal bytes, check metadata, exercise `--license` from an isolated extracted wheel,
and rebuild a wheel from the extracted source archive. They also check that a
missing packaged legal resource produces a clear error. A new development
environment needs the declared development dependencies installed first.

These local build checks do not authorize a release. Before distributing, record
the exact source revision, final artifacts, build/install commands and tool
versions, and an applicable way for recipients to obtain the corresponding
source. Keep the source for that exact delivery available as required by the
chosen GPLv3 distribution method. Recheck the third-party inventory if bundling
additional components. No frozen executable, interpreter, or native library is
part of this adoption's distribution scope.
