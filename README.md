# WANUsage

Command line reporting for WAN usage from the OPNsense vnStat API.

The app is designed to run on macOS or Linux, call the OPNsense vnStat REST
endpoints with Basic Auth API credentials, and report:

- the configured number of previous completed days plus the current day
- the configured number of previous months plus the current month usage so far
  and its estimate

The daily API response provides the last 30 daily rows and a current-day
estimate. WANUsage reports the actual daily rows and uses the available daily
history for daily alerts. The monthly API response provides vnStat month rows
using the router's configured month-rotate day. Its final month row is the
current rotated month usage so far, and its `estimated` row is the estimate for
that same rotated month.

## Local Configuration

Copy the tracked template to an owner-only local configuration and edit it for
the machine running the command:

```bash
cp wanusage.toml wanusage-dev.toml
chmod 600 wanusage-dev.toml
```

`wanusage.toml` remains a tracked template. `wanusage-dev.toml` is ignored by
Git because it contains machine-specific SMTP settings. WANUsage rejects config
files that are readable or writable by group or other users. OPNsense and SMTP
authentication credentials are kept separately.

WANUsage uses `wanusage.toml` from the current directory when `--config` is not
specified. Use `--config wanusage-dev.toml` to run with the dev configuration.

Set `vnstat.base_url` to the OPNsense HTTPS origin, such as
`https://opnsense.local`. Set `vnstat.daily_url_path` and
`vnstat.monthly_url_path` to the daily and monthly paths, such as
`/api/vnstat/service/daily` and `/api/vnstat/service/monthly`.

Create the private credentials file outside the repository for the user that
runs WANUsage:

```bash
install -d -m 700 "$HOME/.config/wanusage"
install -m 600 /dev/null "$HOME/.config/wanusage/.env"
```

`~/.config/wanusage/.env` holds the OPNsense Basic Auth and SMTP credentials:

```dotenv
key=YourOPNSenseKey
secret=YourOPNSenseSecret
smtp_username=YourSMTPUsername
smtp_password=YourSMTPPassword
```

WANUsage does not read OPNsense or SMTP authentication credentials from
`wanusage-dev.toml` and rejects a credentials file that is accessible by group
or other users. If SMTP authentication is not required, omit both
`smtp_username` and `smtp_password`. No `.env` file is stored in the source
directory.

## Usage

```bash
wanusage
wanusage --help
wanusage --version
wanusage --config wanusage-dev.toml
wanusage --days 14
wanusage --debug
wanusage --email
wanusage --months 3
wanusage --quiet
```

Short options are also available: `-c`, `-d`, `-D`, `-e`, `-h`, `-m`, `-q`, and
`-v`.

`--days` accepts values from -1 to 29 and overrides `vnstat.default_days` from
`wanusage-dev.toml`. Use `0` to show only the current day, or `-1` to hide the
daily usage section.

`--months` accepts values from -1 to 11 and overrides `vnstat.default_months`
from `wanusage-dev.toml`. Use `0` to show only the current rotated month usage
and estimate, or `-1` to hide the monthly usage section.

`--email` sends the report to `email.to_address` from `wanusage-dev.toml`.
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
monthly alerts. When the estimated current rotated month usage exceeds a
positive threshold, the app sends one email per rotated month with subject
`monthly high usage alert`. The alerted month is stored in
`<config-name>-monthly-alert-state.txt` next to the config file.

For local development without installing the console script globally:

```bash
.venv/bin/wanusage --config wanusage-dev.toml
```

Example cron entry for a daily email report shortly after midnight:

```cron
10 0 * * * /path/to/WANUsage/.venv/bin/wanusage --config /path/to/WANUsage/wanusage-dev.toml --email
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
