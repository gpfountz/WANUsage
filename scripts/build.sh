#!/bin/sh
# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only

# Build the current source version, regardless of the caller's working directory.
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
exec sh "$script_dir/run_python.sh" build "$@"
