# WANUsage

Command line reporting for WAN usage from the OPNsense vnStat API.

The app is designed to run on macOS or Linux, call the OPNsense vnStat REST
endpoints with Basic Auth API credentials, and report:

- the configured number of previous completed days plus the current day
- the configured number of previous months plus the current month estimate

The daily API response provides the last 30 daily rows and a current-day
estimate. WANUsage reports the actual daily rows and uses the available daily
history for daily alerts. The monthly API response provides 12 completed months
and the current month estimate, which is used for the monthly report and monthly
alerts.

## Local Configuration

Install the example with owner-only permissions and edit it for the machine
running the command:

```bash
install -m 600 wanusage.example.toml wanusage.toml
```

`wanusage.toml` is ignored by Git because it contains API and SMTP credentials.
WANUsage rejects config files that are readable or writable by group or other
users.

Set `vnstat.daily_url` and `vnstat.monthly_url` to the OPNsense vnStat daily and
monthly API endpoints. Set `vnstat.key` to the Basic Auth username/API key and
`vnstat.secret` to the Basic Auth password/API secret.

## Usage

```bash
wanusage
wanusage --help
wanusage --version
wanusage --config wanusage.toml
wanusage --days 14
wanusage --debug
wanusage --email
wanusage --months 3
wanusage --quiet
```

Short options are also available: `-c`, `-d`, `-D`, `-e`, `-h`, `-m`, `-q`, and
`-v`.

`--days` accepts values from -1 to 29 and overrides `vnstat.default_days` from
`wanusage.toml`. Use `0` to show only the current day, or `-1` to hide the daily
usage section.

`--months` accepts values from -1 to 12 and overrides `vnstat.default_months`
from `wanusage.toml`. Use `0` to show only the current month estimate, or `-1`
to hide the monthly usage section.

`--email` sends the report to `email.to_address` from `wanusage.toml`.
Authenticated SMTP requires `email.use_tls = true`; the SMTP server certificate
and hostname are validated using the operating system's trusted certificate
authorities.

`--quiet` suppresses stdout output only. Email reports and alert emails still
process normally.

`vnstat.daily_alert_gb` accepts values from 0 to 999. A value of `0` disables
daily alerts. A positive value sends one alert email per run with subject
`daily high usage alert` when an unalerted daily usage value exceeds the
configured GiB threshold. Alert state is stored next to the config file in
`<config-name>-alert-state.txt`, which records the most recent date that
triggered an alert. Daily alert detection checks all daily rows returned by the
API, independently of the `--days` report setting. State updates are locked and
written atomically to prevent duplicate alerts from overlapping cron runs.

`vnstat.monthly_alert_gb` accepts values from 0 to 9999. A value of `0` disables
monthly alerts. When the estimated current month usage exceeds a positive
threshold, the app sends one email per month with subject
`monthly high usage alert`. The alerted month is stored in
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
