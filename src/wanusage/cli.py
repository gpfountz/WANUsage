from __future__ import annotations

import argparse
from datetime import date

from wanusage.billing import (
    calculate_current_billing_window,
    calculate_last_7_completed_days,
    calculate_previous_billing_window,
)


def build_parser() -> argparse.ArgumentParser:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="wanusage",
        description="Report WAN usage from an OPNsense vnStat database.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    report_parser: argparse.ArgumentParser = subparsers.add_parser(
        "report",
        help="Generate a WAN usage report.",
    )
    report_parser.add_argument(
        "--config",
        default="wanusage.toml",
        help="Path to local TOML config containing router and credential settings.",
    )
    report_parser.add_argument(
        "--email",
        help="Optional recipient email address. Email delivery will be added later.",
    )

    return parser


def main() -> None:
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args()

    if args.command == "report":
        _handle_report()


def _handle_report() -> None:
    today: date = date.today()
    last_7_days = calculate_last_7_completed_days(today)
    current_period = calculate_current_billing_window(today)
    previous_period = calculate_previous_billing_window(today)

    print("WANUsage project scaffold is ready.")
    print(
        "Last 7 completed days: "
        f"{last_7_days.start_date.isoformat()} <= date < {last_7_days.end_date.isoformat()}"
    )
    print(
        "Current billing period: "
        f"{current_period.start_date.isoformat()} <= date < {current_period.end_date.isoformat()}"
    )
    print(
        "Previous billing period: "
        f"{previous_period.start_date.isoformat()} <= date < {previous_period.end_date.isoformat()}"
    )


if __name__ == "__main__":
    main()
