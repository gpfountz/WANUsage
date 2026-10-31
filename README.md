<!-- SPDX-FileCopyrightText: 2026 Greg Pfountz -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

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
wanusage --alerts
wanusage --help
wanusage --version
wanusage --license
wanusage --config /path/to/router.toml
wanusage --days 14
wanusage --debug
wanusage --email
wanusage --months 3
wanusage --onetime
wanusage --quiet
```

Short options are also available: `-a`, `-c`, `-d`, `-D`, `-e`, `-h`, `-m`, `-o`, `-q`, and
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

`--alerts` sends configured daily and monthly alert emails. Alerts are not sent
unless this option is specified, even when an alert threshold is configured.

`--quiet` suppresses stdout output only. Email reports and alert emails still
process normally.

`--onetime` (or `-o`) runs the complete workflow only once per calendar day.
After a successful run, WANUsage writes that date to
`<config-name>-daily-state.txt` next to the selected TOML file. Further runs
with this option on the same day exit silently. The state transaction is locked
so overlapping scheduled runs cannot both execute.

`vnstat.daily_alert_gb` accepts values from 0 to 999. A value of `0` disables
daily alerts. With `--alerts`, a positive value sends one alert email per run with subject
`daily high usage alert` when an unalerted daily usage value exceeds the
configured GiB threshold. Alert state is stored next to the config file in
`<config-name>-alert-state.txt`, which records the most recent date that
triggered an alert. Daily alert detection checks all daily rows returned by the
API, independently of the `--days` report setting. State updates are locked and
written atomically to prevent duplicate alerts from overlapping cron runs.

`vnstat.monthly_alert_gb` accepts values from 0 to 9999. A value of `0` disables
monthly alerts. With `--alerts`, when the estimated current rotated month usage exceeds a
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
mypy src scripts tests
```

## License

Copyright (C) 2026 Greg Pfountz. WANUsage is licensed under **GPL-3.0-only**,
with no warranty. Redistribution and modification are permitted under the
[full license](LICENSE). Run `wanusage --license` to read the license and notices
offline. See [reuse and contribution guidance](LICENSING.md) and the
[third-party inventory](THIRD_PARTY_NOTICES.md) for scope and distribution details.

## Deployment

### Requires Python 3.14 or later.

Build the current source version from the checkout on macOS or Linux:

```bash
sh ./scripts/build.sh
```

The build reads the version from `src/wanusage/__init__.py`, uses an isolated
build environment, and writes the completed wheel to `dist/`. Rebuilding the
same version replaces that wheel only after the new build has succeeded.
Builds and deployments do not advance the application version.

Deploy the newest wheel locally on each Mac or Linux machine:

```bash
sh ./scripts/deploy.sh
```

Use the `sh` prefix on both platforms: copied or synced files may lose their
execute permissions, as observed on the DiskStation. The scripts only need
to be readable when launched this way. To enable direct `./scripts/...`
invocation on a machine, run `chmod u+x scripts/build.sh scripts/deploy.sh`
there; a later sync may require repeating it.

Deployment selects the highest numeric version in `dist/`, installs it into
`/usr/local/wanusage/.venv`, and creates `/usr/local/bin/wanusage`. It requests
`sudo` when those directories require elevated access. A repeated deployment
refreshes the same version, so it also installs a rebuilt wheel whose version
has not changed. The scripts work from any current directory.

When building on the Mac in the Synology Drive folder, wait for the new wheel
in `dist/` to finish syncing, then run `sh ./scripts/deploy.sh` on the DiskStation.
For separate, unsynchronized checkouts, copy the wheel into the target's `dist/`
directory first.
Deployment does not rebuild the wheel or require development dependencies.
For a machine without a source checkout, copy `scripts/deploy.sh`,
`scripts/run_python.sh`, and `scripts/distribution.py` together into a `scripts/`
directory alongside `dist/`. Copy `wanusage.toml` too for a first installation.

Deployment sets readable permissions on installed application files and legal
resources, including repairing older restrictive installations. It verifies the
installed version and offline `--license` access as the invoking user before
creating the command symlink. Existing runtime configuration, credentials, and
alert state remain in the user's configuration directory.

Both entry points look for the checkout's `.venv/bin/python`, then `python3.14`
and `python3` on `PATH`, requiring Python 3.14 or later. Select a different
interpreter explicitly when needed:

```bash
WANUSAGE_PYTHON=/path/to/python3.14 sh ./scripts/deploy.sh
```

Optional paths support a different wheel directory or a user-owned installation:

```bash
sh ./scripts/deploy.sh --wheel-dir /path/to/wheels
sh ./scripts/deploy.sh --install-dir "$HOME/.local/share/wanusage" --bin-dir "$HOME/.local/bin"
```

Use `--wheel /path/to/wanusage-X.Y.Z-py3-none-any.whl` to select an exact artifact.
Deployment refuses to overwrite an unrelated command at the selected symlink
path. Add a custom `--bin-dir` to `PATH` when using a user-owned installation.

For offline builds, first install the development dependencies, then run
`sh ./scripts/build.sh --no-build-isolation`. `--output-dir /path/to/wheels` selects
a different build destination. Run either script with `--help` for its options.

After deployment, run interactively as your normal user:

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
