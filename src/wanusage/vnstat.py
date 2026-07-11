from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from wanusage.config import ApiCredentials, VnstatConfig
from wanusage.models import DailyUsage, UsagePeriod, UsageReport
from wanusage.reporting import sort_daily_usage

BYTES_PER_UNIT: dict[str, int] = {
    "B": 1,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "TiB": 1024**4,
    "PiB": 1024**5,
}
DAILY_DATE_PATTERN: re.Pattern[str] = re.compile(r"\b\d{2}/\d{2}/\d{2}\b")
MONTH_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+'(?P<year>\d{2})\b"
)
MONTH_NUMBERS: dict[str, int] = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


class VnstatApiError(RuntimeError):
    """Raised when an OPNsense vnStat API request or response parse fails."""


class JsonGetter(Protocol):
    """Interface for retrieving JSON documents from authenticated API endpoints."""

    def get_json(self, url: str, *, key: str, secret: str) -> dict[str, Any]:
        """Return the decoded JSON object from ``url``."""

        ...


@dataclass(frozen=True)
class UrllibJsonGetter:
    """Retrieve JSON over HTTPS using Basic Auth and the standard library."""

    timeout_seconds: int = 30

    def get_json(self, url: str, *, key: str, secret: str) -> dict[str, Any]:
        """Fetch and decode one API response.

        TLS certificate and hostname validation use Python's default HTTPS
        context. The response must be a JSON object.

        Raises:
            VnstatApiError: If the request fails or the response is not a JSON
                object.
        """

        auth_header: str = base64.b64encode(f"{key}:{secret}".encode()).decode("ascii")
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Basic {auth_header}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_response: bytes = response.read()
        except (OSError, urllib.error.URLError) as error:
            raise VnstatApiError(f"Could not fetch vnStat API URL {url}: {error}") from error

        try:
            decoded_response: Any = json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise VnstatApiError(f"vnStat API URL {url} did not return valid JSON") from error

        if not isinstance(decoded_response, dict):
            raise VnstatApiError(f"vnStat API URL {url} returned a non-object JSON value")
        return decoded_response


@dataclass(frozen=True)
class VnstatClient:
    """Retrieve vnStat usage from the OPNsense API and assemble a typed report."""

    json_getter: JsonGetter
    config: VnstatConfig
    credentials: ApiCredentials

    def build_usage_report(
        self,
        today: date,
        *,
        day_count: int = 7,
        month_count: int = 1,
    ) -> UsageReport:
        """Fetch daily and monthly API data and build a report.

        ``day_count`` controls displayed daily history: ``-1`` omits daily rows,
        ``0`` includes only today, and a positive value includes that many
        previous days plus today. ``month_count`` controls how many monthly
        rows before the current vnStat rotated month are shown; the current
        month usage-so-far and its estimate are always shown when monthly
        reporting is enabled. When daily reporting is enabled and API data is
        available, its most recent date becomes the report date; ``today`` is
        the fallback for reports without displayed daily data.
        """

        daily_usage: tuple[DailyUsage, ...] = ()
        if day_count >= 0 or self.config.daily_alert_gb > 0:
            daily_usage = _parse_daily_response(
                _response_text(
                    self.json_getter.get_json(
                        self.config.daily_url,
                        key=self.credentials.key,
                        secret=self.credentials.secret,
                    ),
                    self.config.daily_url,
                )
            )

        report_date: date = today
        if day_count >= 0 and daily_usage:
            report_date = daily_usage[-1].usage_date

        monthly_usage: tuple[UsagePeriod, ...] = ()
        current_month_start: date = today.replace(day=1)
        estimated_current_month_bytes: int = 0
        if month_count >= 0 or self.config.monthly_alert_gb > 0:
            api_months, estimated_current_month_bytes = _parse_monthly_response(
                _response_text(
                    self.json_getter.get_json(
                        self.config.monthly_url,
                        key=self.credentials.key,
                        secret=self.credentials.secret,
                    ),
                    self.config.monthly_url,
                ),
            )
            current_month: UsagePeriod = _current_month_period(api_months)
            current_month_start = current_month.start_date
            monthly_usage = _select_report_monthly_usage(
                api_months,
                current_month=current_month,
                estimated_current_month_bytes=estimated_current_month_bytes,
                month_count=month_count,
            )

        sorted_daily_usage: tuple[DailyUsage, ...] = sort_daily_usage(list(daily_usage))
        return UsageReport(
            generated_for=report_date,
            day_count=day_count,
            month_count=month_count,
            daily_usage=_select_report_daily_usage(sorted_daily_usage, report_date, day_count),
            daily_alert_usage=sorted_daily_usage if self.config.daily_alert_gb > 0 else (),
            monthly_usage=monthly_usage,
            current_month_start=current_month_start,
            estimated_current_month_bytes=estimated_current_month_bytes,
        )


def _response_text(payload: dict[str, Any], url: str) -> str:
    """Extract the vnStat text table from an OPNsense API response object."""

    response: Any = payload.get("response")
    if not isinstance(response, str):
        raise VnstatApiError(f"vnStat API URL {url} response field must be a string")
    return response


def _parse_daily_response(response_text: str) -> tuple[DailyUsage, ...]:
    """Parse the daily vnStat text table into daily usage rows."""

    daily_usage: list[DailyUsage] = []
    for line in response_text.splitlines():
        date_match: re.Match[str] | None = DAILY_DATE_PATTERN.search(line)
        if date_match is None:
            continue

        daily_usage.append(
            DailyUsage(
                usage_date=_parse_daily_date(date_match.group(0)),
                total_bytes=_parse_total_column(line),
            )
        )

    return sort_daily_usage(daily_usage)


def _parse_monthly_response(response_text: str) -> tuple[tuple[UsagePeriod, ...], int]:
    """Parse the monthly vnStat table and current rotated-month estimate."""

    api_months: list[UsagePeriod] = []
    estimated_current_month_bytes: int | None = None

    for line in response_text.splitlines():
        stripped_line: str = line.strip()
        if stripped_line.startswith("estimated"):
            estimated_current_month_bytes = _parse_total_column(line)
            continue

        month_match: re.Match[str] | None = MONTH_PATTERN.search(line)
        if month_match is None:
            continue

        month_start: date = _parse_month_start(month_match)
        api_months.append(
            UsagePeriod(
                name=_format_month_name(month_start),
                start_date=month_start,
                end_date=_next_month_start(month_start),
                total_bytes=_parse_total_column(line),
            )
        )

    if estimated_current_month_bytes is None:
        raise VnstatApiError("vnStat monthly response did not include an estimated row")
    if not api_months:
        raise VnstatApiError("vnStat monthly response did not include any month rows")

    return (
        tuple(sorted(api_months, key=lambda period: period.start_date)),
        estimated_current_month_bytes,
    )


def _select_report_daily_usage(
    daily_usage: tuple[DailyUsage, ...],
    today: date,
    day_count: int,
) -> tuple[DailyUsage, ...]:
    """Select displayed daily rows from the available API history."""

    if day_count < 0:
        return ()

    first_report_date: date = today - timedelta(days=day_count)
    return tuple(
        value
        for value in daily_usage
        if first_report_date <= value.usage_date <= today
    )


def _current_month_period(api_months: tuple[UsagePeriod, ...]) -> UsagePeriod:
    """Return the final API month row, which vnStat reports as the current month."""

    try:
        return api_months[-1]
    except IndexError as error:
        raise VnstatApiError("vnStat monthly response did not include any month rows") from error


def _select_report_monthly_usage(
    api_months: tuple[UsagePeriod, ...],
    *,
    current_month: UsagePeriod,
    estimated_current_month_bytes: int,
    month_count: int,
) -> tuple[UsagePeriod, ...]:
    """Select previous months, current usage so far, and the current estimate."""

    if month_count < 0:
        return ()

    previous_months: tuple[UsagePeriod, ...] = ()
    if month_count > 0:
        previous_months = api_months[:-1][-month_count:]
    estimated_current_month: UsagePeriod = UsagePeriod(
        name="Estimated",
        start_date=current_month.start_date,
        end_date=current_month.end_date,
        total_bytes=estimated_current_month_bytes,
        is_estimated=True,
    )
    return (*previous_months, current_month, estimated_current_month)


def _parse_total_column(line: str) -> int:
    """Parse the total column from one vnStat table row."""

    parts: list[str] = line.split("|")
    if len(parts) < 3:
        raise VnstatApiError(f"Could not parse vnStat total column: {line.strip()}")
    return _parse_byte_value(parts[2].strip())


def _parse_byte_value(value: str) -> int:
    """Convert a vnStat byte value with binary units to bytes."""

    parts: list[str] = value.split()
    if len(parts) != 2:
        raise VnstatApiError(f"Invalid vnStat usage value: {value}")

    amount_text, unit = parts
    if unit not in BYTES_PER_UNIT:
        raise VnstatApiError(f"Unsupported vnStat usage unit: {unit}")

    try:
        amount: Decimal = Decimal(amount_text)
    except InvalidOperation as error:
        raise VnstatApiError(f"Invalid vnStat usage value: {value}") from error

    if not amount.is_finite() or amount < 0:
        raise VnstatApiError(f"Invalid vnStat usage value: {value}")

    return int(amount * BYTES_PER_UNIT[unit])


def _parse_daily_date(value: str) -> date:
    """Parse a vnStat daily ``MM/DD/YY`` date."""

    month_text, day_text, year_text = value.split("/")
    return date(
        year=2000 + int(year_text),
        month=int(month_text),
        day=int(day_text),
    )


def _parse_month_start(match: re.Match[str]) -> date:
    """Parse a vnStat monthly label into the first day of that month."""

    month_name: str = match.group("month")
    year: int = 2000 + int(match.group("year"))
    return date(year, MONTH_NUMBERS[month_name], 1)


def _next_month_start(value: date) -> date:
    """Return the first day of the month after ``value``."""

    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _format_month_name(value: date) -> str:
    """Format a month label for the plain-text report."""

    return f"{value.strftime('%b')} {value.year}"
