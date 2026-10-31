#!/bin/sh
# SPDX-FileCopyrightText: 2026 Greg Pfountz
# SPDX-License-Identifier: GPL-3.0-only

# Share interpreter discovery between the two public entry points.
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
if [ -n "${WANUSAGE_PYTHON:-}" ]; then
    exec "$WANUSAGE_PYTHON" "$script_dir/distribution.py" "$@"
fi
for python_command in "$script_dir/../.venv/bin/python" python3.14 python3; do
    if command -v "$python_command" >/dev/null 2>&1 &&
        "$python_command" -c 'import sys; sys.exit(sys.version_info < (3, 14))'
    then
        exec "$python_command" "$script_dir/distribution.py" "$@"
    fi
done
echo "WANUsage build/deployment requires Python 3.14 or later on PATH, or WANUSAGE_PYTHON." >&2
exit 1
