from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from wanusage import __version__
from wanusage.alerts import (
    ALERT_SUBJECT,
    MONTHLY_ALERT_SUBJECT,
    AlertStateStore,
    alert_state_path_for_config,
    choose_alert,
    monthly_alert_state_path_for_config,
    should_send_monthly_alert,
)
from wanusage.config import ConfigError, load_config
from wanusage.emailer import EmailError, EmailSender
from wanusage.reporting import format_daily_alert_report, format_date, format_report
from wanusage.ssh import ParamikoCommandRunner, RemoteCommandError
from wanusage.vnstat import VnstatClient


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser and its validated global options."""

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="wanusage",
        description="Report WAN usage from an OPNsense vnStat database.",
        add_help=False,
    )
    parser.add_argument(
        "-c",
        "--config",
        default="wanusage.toml",
        help=(
            "Optional path to local TOML config containing router and credential settings. "
            "Defaults to wanusage.toml in the current directory."
        ),
    )
    parser.add_argument(
        "-d",
        "--days",
        type=_bounded_int("days", minimum=-1, maximum=60),
        help=(
            "Number of previous completed days to show, from -1 to 60. "
            "Defaults to vnstat.default_days from the config file. "
            "Use 0 for current day only, or -1 to hide daily usage."
        ),
    )
    parser.add_argument(
        "-D",
        "--debug",
        action="store_true",
        help="Print full exception tracebacks when a command fails.",
    )
    parser.add_argument(
        "-e",
        "--email",
        action="store_true",
        help="Send the report to email.to_address from the config file.",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress writing the usage report to stdout.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the installed wanusage version and exit.",
    )

    return parser


def main() -> None:
    """Parse command-line arguments and run the WAN usage workflow."""

    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args()
    _handle_report(args)


def _handle_report(args: argparse.Namespace) -> None:
    """Load configuration, collect usage, process alerts, and deliver output."""

    config_path = Path(args.config).expanduser()

    try:
        app_config = load_config(config_path)
        command_runner = ParamikoCommandRunner(app_config.router)
        vnstat_client = VnstatClient(command_runner=command_runner, config=app_config.vnstat)
        report_date: date = datetime.now(app_config.vnstat.reporting_timezone).date()
        report = vnstat_client.build_usage_report(
            report_date,
            day_count=args.days if args.days is not None else app_config.vnstat.default_days,
        )
        formatted_report: str = format_report(report)
        if app_config.vnstat.daily_alert_gb > 0:
            alert_store = AlertStateStore(alert_state_path_for_config(config_path))
            with alert_store.locked():
                alert_decision = choose_alert(
                    report.daily_alert_usage,
                    daily_alert_gb=app_config.vnstat.daily_alert_gb,
                    last_alert_date=alert_store.read_last_alert_date(),
                )

                alert_date: date | None = alert_decision.alert_date
                if alert_decision.should_send and alert_date is not None:
                    try:
                        EmailSender(app_config.email).send_report(
                            subject=ALERT_SUBJECT,
                            body=format_daily_alert_report(
                                report,
                                alert_date,
                            ),
                        )
                    except EmailError as error:
                        _handle_error(error, debug=args.debug)

                    alert_store.write_last_alert_date(alert_date)

        if app_config.vnstat.monthly_alert_gb > 0:
            current_period_start: date = report.billing_periods[-1].start_date
            monthly_alert_store = AlertStateStore(
                monthly_alert_state_path_for_config(config_path)
            )
            with monthly_alert_store.locked():
                if should_send_monthly_alert(
                    report.estimated_current_period_bytes,
                    app_config.vnstat.monthly_alert_gb,
                    current_period_start=current_period_start,
                    last_alert_period_start=monthly_alert_store.read_last_alert_date(),
                ):
                    try:
                        EmailSender(app_config.email).send_report(
                            subject=MONTHLY_ALERT_SUBJECT,
                            body=formatted_report,
                        )
                    except EmailError as error:
                        _handle_error(error, debug=args.debug)
                    monthly_alert_store.write_last_alert_date(current_period_start)

        if args.email:
            try:
                EmailSender(app_config.email).send_report(
                    subject=f"WAN usage report for {format_date(report.generated_for)}",
                    body=formatted_report,
                )
            except EmailError as error:
                _handle_error(error, debug=args.debug)

        if not args.quiet:
            print(formatted_report)
    except (ConfigError, RemoteCommandError, OSError, ValueError) as error:
        _handle_error(error, debug=args.debug)


def _handle_error(error: Exception, *, debug: bool) -> None:
    """Write a concise or diagnostic error message and exit unsuccessfully."""

    if debug:
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    else:
        print(f"wanusage: {error}", file=sys.stderr)
    raise SystemExit(1) from error


def _bounded_int(name: str, *, minimum: int, maximum: int) -> Callable[[str], int]:
    """Create an argparse converter for an integer in an inclusive range."""

    def parse(value: str) -> int:
        """Parse and range-check one command-line value."""

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
