from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from wanusage.config import ConfigError, load_config
from wanusage.emailer import EmailError, EmailSender
from wanusage.reporting import format_report
from wanusage.ssh import ParamikoCommandRunner, RemoteCommandError
from wanusage.vnstat import VnstatClient


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
        help="Optional recipient email address.",
    )

    return parser


def main() -> None:
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args()

    if args.command == "report":
        _handle_report(args)


def _handle_report(args: argparse.Namespace) -> None:
    config_path = Path(args.config).expanduser()

    try:
        app_config = load_config(config_path)
        command_runner = ParamikoCommandRunner(app_config.router)
        vnstat_client = VnstatClient(command_runner=command_runner, config=app_config.vnstat)
        report = vnstat_client.build_usage_report(date.today())
    except (ConfigError, RemoteCommandError, OSError, ValueError) as error:
        print(f"wanusage: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    formatted_report: str = format_report(report)

    if args.email:
        try:
            EmailSender(app_config.email).send_report(
                recipient=args.email,
                subject=f"WAN usage report for {report.generated_for.isoformat()}",
                body=formatted_report,
            )
        except EmailError as error:
            print(f"wanusage: {error}", file=sys.stderr)
            raise SystemExit(1) from error

    print(formatted_report)


if __name__ == "__main__":
    main()
