# WANUsage

Command line reporting for WAN usage from an OPNsense vnStat SQLite database.

The app is designed to run on macOS or Linux, connect to the router over SSH, query
`/var/lib/vnstat/vnstat.db`, and report:

- the configured number of previous completed days plus the current day
- the current billing period, using `>= 14th` and `< next 14th`
- the previous billing period, using the same half-open billing window

## Local Configuration

Install the example with owner-only permissions and edit it for the machine
running the command:

```bash
install -m 600 wanusage.example.toml wanusage.toml
```

`wanusage.toml` is ignored by Git because it contains authentication details.
WANUsage rejects config files that are readable or writable by group or other
users.

The SSH key path may point at the private key used with an OpenSSH certificate.
The router host key must already be trusted in the running user's `known_hosts`
file; the app rejects unknown host keys.

Set `vnstat.interface_name` to the interface name stored in vnStat's `interface`
table for the WAN interface.

Set `vnstat.reporting_timezone` to the IANA timezone used by OPNsense, such as
`America/New_York`. Report dates, billing periods, and alerts use this timezone
instead of the local timezone of the macOS or Linux machine running WANUsage.

Set `vnstat.billing_cycle_day` from 1 to 31. When that day does not exist in a
month, the billing boundary uses the last day of that month.

The report SQL statements are batched into one remote `sqlite3` process and one
SSH connection per run.

The report projects current billing-period usage from usage so far, elapsed
calendar days including today, and the total number of days in the billing
period.

## Usage

```bash
wanusage
wanusage --help
wanusage --version
wanusage --config wanusage.toml
wanusage --days 14
wanusage --debug
wanusage --email
wanusage --quiet
```

Short options are also available: `-c`, `-d`, `-D`, `-e`, `-h`, `-q`, and `-v`.

`--days` accepts values from -1 to 60 and overrides `vnstat.default_days` from
`wanusage.toml`. Use `0` to show only the current day, or `-1` to hide the daily
usage section. The billing section always shows the previous billing month and
the current billing month.

`--email` sends the report to `email.to_address` from `wanusage.toml`.
Authenticated SMTP requires `email.use_tls = true`; the SMTP server certificate
and hostname are validated using the operating system's trusted certificate authorities.

`--quiet` suppresses stdout output only. Email reports and alert emails still
process normally.

`vnstat.daily_alert_gb` accepts values from 0 to 999. A value of `0` disables
daily alerts. A positive value sends one alert email per run with subject
`daily high usage alert` when an unalerted daily usage value exceeds the
configured GiB threshold. Alert state is stored next to the config file in
`<config-name>-alert-state.txt`, which records the most recent date that
triggered an alert. Daily alert detection checks all available usage from the previous
60 days plus today, independently of the `--days` report setting. State updates
are locked and written atomically to prevent duplicate alerts from overlapping
cron runs.

`vnstat.monthly_alert_gb` accepts values from 0 to 9999. A value of `0` disables
monthly alerts. When the estimated current billing-period usage exceeds a
positive threshold, the app sends one email per billing period with subject
`monthly high usage alert`. The alerted billing period is stored in
`<config-name>-monthly-alert-state.txt` next to the config file.

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
ruff check .
mypy src tests
```

## Current Status

The app can now load local TOML config, connect over SSH, query vnStat with the
remote `sqlite3` command, print a terminal report, and optionally send the same
report body by SMTP.
