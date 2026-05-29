# WANUsage

Command line reporting for WAN usage from an OPNsense vnStat SQLite database.

The app is designed to run on macOS or Linux, connect to the router over SSH, query
`/var/lib/vnstat/vnstat.db`, and report:

- the configured number of previous completed days plus the current day
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
wanusage
wanusage --help
wanusage --version
wanusage --config wanusage.toml
wanusage --days 14
wanusage --debug
wanusage --email
```

Short options are also available: `-c`, `-d`, `-D`, `-e`, `-h`, and `-v`.

`--days` accepts values from -1 to 60 and overrides `vnstat.default_days` from
`wanusage.toml`. Use `0` to show only the current day, or `-1` to hide the daily
usage section. The billing section always shows the previous billing month and
the current billing month.

`--email` sends the report to `email.to_address` from `wanusage.toml`.

`vnstat.daily_alert_gb` sends one alert email per run with subject
`daily high usage alert` when an unalerted daily usage value exceeds the
configured GiB threshold. Alert state is stored next to the config file in
`wanusage-alert-state.txt`, which records the most recent date that triggered an
alert.

For local development without installing the console script globally:

```bash
.venv/bin/wanusage --config wanusage.toml
```

Example cron entry for a daily email report shortly after midnight:

```cron
10 0 * * * /path/to/WANUsage/.venv/bin/wanusage --config /path/to/WANUsage/wanusage.toml --email
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
