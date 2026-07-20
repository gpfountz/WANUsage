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

The tracked `wanusage.toml` is a template. For a first installation, create the
private runtime configuration directory and copy the template into it:

```bash
install -d -m 700 "$HOME/.config/wanusage"
install -m 600 wanusage.toml "$HOME/.config/wanusage/wanusage.toml"
```

WANUsage reads `~/.config/wanusage/wanusage.toml` when `--config` is not
specified. It contains machine-specific router and SMTP transport settings and
must not be readable or writable by group or other users. OPNsense and SMTP
authentication credentials are kept separately.

When using `--config /path/to/wanusage.toml`, WANUsage reads `/path/to/.env` and
stores alert state next to that TOML file as `router-alert-state.txt` and
`router-monthly-alert-state.txt`. The `--onetime` run state is stored there as
`router-daily-state.txt`.

Set `vnstat.base_url` to the OPNsense HTTPS origin, such as
`https://opnsense.local`. Set `vnstat.daily_url_path` and
`vnstat.monthly_url_path` to the daily and monthly paths, such as
`/api/vnstat/service/daily` and `/api/vnstat/service/monthly`.

Create the private credentials file in the same directory as the TOML file:

```bash
[ -e "$HOME/.config/wanusage/.env" ] || install -m 600 /dev/null "$HOME/.config/wanusage/.env"
chmod 600 "$HOME/.config/wanusage/.env"
```

`~/.config/wanusage/.env` holds the OPNsense Basic Auth and SMTP credentials:

```dotenv
key=YourOPNSenseKey
secret=YourOPNSenseSecret
smtp_username=YourSMTPUsername
smtp_password=YourSMTPPassword
```

WANUsage does not read OPNsense or SMTP authentication credentials from
`~/.config/wanusage/wanusage.toml` and rejects a credentials file that is
accessible by group or other users. If SMTP authentication is not required, omit both
`smtp_username` and `smtp_password`. No `.env` file is stored in the source
directory.

## Usage

```bash
wanusage
wanusage --help
wanusage --version
wanusage --config /path/to/router.toml
wanusage --days 14
wanusage --debug
wanusage --email
wanusage --months 3
wanusage --onetime
wanusage --quiet
```

Short options are also available: `-c`, `-d`, `-D`, `-e`, `-h`, `-m`, `-o`, `-q`, and
`-v`.

`--days` accepts values from -1 to 29 and overrides `vnstat.default_days` from
the selected TOML configuration. Use `0` to show only the current day, or `-1`
to hide the daily usage section.

`--months` accepts values from -1 to 11 and overrides `vnstat.default_months`
from the selected TOML configuration. Use `0` to show only the current rotated
month usage and estimate, or `-1` to hide the monthly usage section.

`--email` sends the report to `email.to_address` from the selected TOML configuration.
Authenticated SMTP requires `email.use_tls = true`; the SMTP server certificate
and hostname are validated using the operating system's trusted certificate
authorities.

`--quiet` suppresses stdout output only. Email reports and alert emails still
process normally.

`--onetime` (or `-o`) runs the complete workflow only once per calendar day.
After a successful run, WANUsage writes that date to
`<config-name>-daily-state.txt` next to the selected TOML file. Further runs
with this option on the same day exit silently. The state transaction is locked
so overlapping scheduled runs cannot both execute.

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
.venv/bin/wanusage
```

Example cron entry for a daily email report shortly after midnight:

```cron
10 0 * * * /usr/local/wanusage/.venv/bin/wanusage -q -e -o
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
## Deployment

### Requires Python 3.14 or later.

Do not deploy WANUsage by copying `.py` files or maintaining a handwritten
wrapper script. Build a wheel from the source checkout, copy that wheel to each
server, and install it into a dedicated virtual environment.

Build the wheel on the development Mac from the WANUsage project directory:

```bash
cd /Users/greg/Library/CloudStorage/SynologyDrive-home/Codex/WANUsage
.venv/bin/python -m pip wheel . -w dist
```

Copy the generated wheel to each server:

```text
dist/wanusage-<version>-py3-none-any.whl
```

On each server, install or upgrade WANUsage in its dedicated virtual
environment:

```bash
sudo install -d -m 755 /usr/local/wanusage
sudo chown "$USER:$(id -gn)" /usr/local/wanusage
python3.14 -m venv /usr/local/wanusage/.venv
/usr/local/wanusage/.venv/bin/python -m pip install --upgrade /path/to/wanusage-<version>-py3-none-any.whl
```

Create or update a symlink so WANUsage can be run by typing `wanusage`:

```bash
sudo ln -sfn /usr/local/wanusage/.venv/bin/wanusage /usr/local/bin/wanusage
```

Use the symlink for interactive runs:

```bash
wanusage --version
wanusage -q -e
```

The generated console command remains available at its full path:

```bash
/usr/local/wanusage/.venv/bin/wanusage --version
/usr/local/wanusage/.venv/bin/wanusage -q -e
```

For cron, run the generated command with an absolute path:

```cron
10 0 * * * /usr/local/wanusage/.venv/bin/wanusage -q -e
```

Create or maintain the per-server runtime files for the same user that runs
WANUsage:

```bash
install -d -m 700 "$HOME/.config/wanusage"
install -m 600 /path/to/wanusage.toml "$HOME/.config/wanusage/wanusage.toml"
[ -e "$HOME/.config/wanusage/.env" ] || install -m 600 /dev/null "$HOME/.config/wanusage/.env"
chmod 600 "$HOME/.config/wanusage/wanusage.toml"
chmod 600 "$HOME/.config/wanusage/.env"
```

For a new server, copy the tracked `wanusage.toml` template from the project
alongside the wheel, then use that copied template as `/path/to/wanusage.toml`
in the command above. For an existing server, keep the current
`~/.config/wanusage/wanusage.toml` and update it only when the template gains a
new setting.

Edit `~/.config/wanusage/wanusage.toml` for that server's OPNsense and SMTP
settings. Edit `~/.config/wanusage/.env` for that server's credentials:

```dotenv
key=YourOPNSenseKey
secret=YourOPNSenseSecret
smtp_username=YourSMTPUsername
smtp_password=YourSMTPPassword
```

Alert state is stored next to the selected config file as
`wanusage-alert-state.txt` and `wanusage-monthly-alert-state.txt`; one-time
execution uses `wanusage-daily-state.txt`. These files are created
automatically. Copy them only when migrating an existing server and preserving
alert history or one-time run history matters.
