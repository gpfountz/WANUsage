<!-- SPDX-FileCopyrightText: 2026 Greg Pfountz -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# Third-party materials

This inventory describes the WANUsage source tree and the pure-Python wheel
built from it. It does not describe older wheels already in `dist/`, an entire
development environment, a separately installed Python interpreter, or a future
frozen executable or container.

## Redistributed contents

WANUsage declares no runtime package dependencies. The reviewed source contains
no vendored third-party code, native libraries, fonts, images, or copied upstream
license notices requiring a separate bundled license. The application, tests,
Git versioning and build/deployment scripts, documentation, and
configuration/request examples are project material. JSON editor settings have
adjacent `.license` sidecars.

The GPL text in `LICENSE` is the unmodified Free Software Foundation license
document, copyright 2007 Free Software Foundation, Inc. Its own permission to
copy the license document is preserved. It is not attributed to the project
author. The project selects `GPL-3.0-only`; the illustrative "or later" language
in the license document's appendix does not change that selection.

## External software and data

Python and its standard library are external prerequisites and are not bundled
in this project's wheel. Python retains its own license and third-party notices:
<https://docs.python.org/3/license.html>.

OPNsense and vnStat run on the user's router and are accessed through an API;
their implementations are not included in WANUsage. The request examples contain
request definitions, not those projects' source code. Router responses, local
credentials, and reports are not relicensed merely by being processed by WANUsage.

Hatchling, pytest, Ruff, mypy, pip, CI actions, and their dependencies are build,
test, or development tools. They are not bundled by the WANUsage wheel and are
not assigned the project's copyright or license by these notices. Their own
licenses continue to apply to copies of those tools.

## Changes to distribution scope

Recheck this inventory whenever dependencies, copied code, assets, or packaging
change. Preserve any newly redistributed components' complete upstream notices
and meet their source and build-material requirements. A frozen executable or
container can include Python, native libraries, and other components absent from
the current wheel and needs its own inventory before distribution.
