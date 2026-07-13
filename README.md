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
`router-monthly-alert-state.txt`.

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
wanusage --quiet
```

Short options are also available: `-c`, `-d`, `-D`, `-e`, `-h`, `-m`, `-q`, and
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
10 0 * * * /path/to/WANUsage -c /path/to/wanusage.toml -q -e
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

### Requires python 3.14 or later.

- Create folder /usr/local/wanusage and copy .py files there.

- Create file wanusage in /usr/local/bin containing the following.  Modify #! as needed for your python installation.
  ```bash
  #!/opt/homebrew/bin/python3
  import sys
  sys.path.append('/usr/local')
  from wanusage.cli import main
  if __name__ == '__main__':
      sys.argv[0] = sys.argv[0].removesuffix('.exe')
      sys.exit(main())
  ```

- Create folder ~/.config/wanusage and copy file wanusage.toml there and edit for your environment.  Create file .env there and edit for your credentials.
  ```bash
  key=YourOPNSenseKey
  secret=YourOPNSenseSecret
  smtp_username=YourSMTPUsername
  smtp_password=YourSMTPPassword
  ```

- Set access control for config files
  ```
  sudo chmod 600 ~/.config/wanusage/wanusage.toml
  sudo chmod 600 ~/.config/wanusage/.env
  ```