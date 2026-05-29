from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Callable
from datetime import date
from pathlib import Path

from wanusage import __version__
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the installed wanusage version and exit.",
    )
    parser.add_argument(
        "--config",
        default="wanusage.toml",
        help=(
            "Optional path to local TOML config containing router and credential settings. "
            "Defaults to wanusage.toml in the current directory."
        ),
    )
    parser.add_argument(
        "--email",
        action="store_true",
        help="Send the report to email.to_address from the config file.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print full exception tracebacks when a command fails.",
    )
    parser.add_argument(
        "--days",
        type=_bounded_int("days", minimum=-1, maximum=60),
        help=(
            "Number of previous completed days to show, from -1 to 60. "
            "Defaults to vnstat.default_days from the config file. "
            "Use 0 for current day only, or -1 to hide daily usage."
        ),
    )

    return parser


def main() -> None:
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args()
    _handle_report(args)


def _handle_report(args: argparse.Namespace) -> None:
    config_path = Path(args.config).expanduser()

    try:
        app_config = load_config(config_path)
        command_runner = ParamikoCommandRunner(app_config.router)
        vnstat_client = VnstatClient(command_runner=command_runner, config=app_config.vnstat)
        report = vnstat_client.build_usage_report(
            date.today(),
            day_count=args.days if args.days is not None else app_config.vnstat.default_days,
        )
        formatted_report: str = format_report(report)

        if args.email:
            try:
                EmailSender(app_config.email).send_report(
                    subject=f"WAN usage report for {report.generated_for.isoformat()}",
                    body=formatted_report,
                )
            except EmailError as error:
                _handle_error(error, debug=args.debug)

        print(formatted_report)
    except (ConfigError, RemoteCommandError, OSError, ValueError) as error:
        _handle_error(error, debug=args.debug)


def _handle_error(error: Exception, *, debug: bool) -> None:
    if debug:
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    else:
        print(f"wanusage: {error}", file=sys.stderr)
    raise SystemExit(1) from error


def _bounded_int(name: str, *, minimum: int, maximum: int) -> Callable[[str], int]:
    def parse(value: str) -> int:
        try:
            parsed_value: int = int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from error

        if parsed_value < minimum or parsed_value > maximum:
            raise argparse.ArgumentTypeError(f"{name} must be between {minimum} and {maximum}")

        return parsed_value

    return parse


if __name__ == "__main__":
    main()
