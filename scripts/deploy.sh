#!/bin/sh
# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only

# Deploy the newest local wheel on this machine.
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
exec sh "$script_dir/run_python.sh" deploy "$@"
