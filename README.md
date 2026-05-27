# WANUsage

Command line reporting for WAN usage from an OPNsense vnStat SQLite database.

The app is designed to run on macOS or Linux, connect to the router over SSH, query
`/var/lib/vnstat/vnstat.db`, and report:

- the last 7 completed days of WAN traffic
- the current billing period, using `>= 14th` and `< next 14th`
- the previous billing period, using the same half-open billing window

## Local Configuration

Copy the example config and edit it for the machine running the command:

```bash
cp wanusage.example.toml wanusage.toml
```

`wanusage.toml` is ignored by Git because it contains authentication details.

The SSH key path may point at the private key used with an OpenSSH certificate.
The router host key must already be trusted in the running user's `known_hosts`
file; the app rejects unknown host keys.

## Usage

```bash
wanusage report --config wanusage.toml
wanusage report --config wanusage.toml --email you@example.com
wanusage report --config wanusage.toml --debug
wanusage --version
wanusage --help
wanusage report --help
```

For local development without installing the console script globally:

```bash
.venv/bin/wanusage report --config wanusage.toml
```

Example cron entry for a daily email report shortly after midnight:

```cron
10 0 * * * /path/to/WANUsage/.venv/bin/wanusage report --config /path/to/WANUsage/wanusage.toml --email you@example.com
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

## Current Status

The app can now load local TOML config, connect over SSH, query vnStat with the
remote `sqlite3` command, print a terminal report, and optionally send the same
report body by SMTP.
