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

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

## Current Status

This first implementation slice contains the typed project scaffold, date-window
calculation, and report formatting. SSH and email delivery will be added in later
steps.
