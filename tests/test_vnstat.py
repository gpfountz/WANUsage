from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest

from wanusage.config import VnstatConfig
from wanusage.vnstat import VnstatApiError, VnstatClient

DAILY_RESPONSE: str = """
 igc0  /  daily

          day        rx      |     tx      |    total    |   avg. rate
     ------------------------+-------------+-------------+---------------
      07/07/26     27.05 GiB |    1.75 GiB |   28.80 GiB |    2.86 Mbit/s
      07/08/26     39.78 GiB |    1.49 GiB |   41.26 GiB |    4.10 Mbit/s
      07/09/26      8.53 GiB |    1.00 GiB |    9.53 GiB |    1.25 Mbit/s
     ------------------------+-------------+-------------+---------------
     estimated     11.22 GiB |    1.32 GiB |   12.53 GiB |
"""

MONTHLY_RESPONSE: str = """
 igc0  /  monthly

        month        rx      |     tx      |    total    |   avg. rate
     ------------------------+-------------+-------------+---------------
       May '26    922.43 GiB |   68.72 GiB |  991.15 GiB |    3.18 Mbit/s
       Jun '26    734.49 GiB |   44.38 GiB |  778.87 GiB |    2.58 Mbit/s
     ------------------------+-------------+-------------+---------------
     estimated    883.89 GiB |   53.40 GiB |  937.29 GiB |
"""


@dataclass
class FakeJsonGetter:
    payloads_by_url: dict[str, dict[str, Any]]
    requests: list[tuple[str, str, str]] = field(default_factory=list)

    def get_json(self, url: str, *, key: str, secret: str) -> dict[str, Any]:
        self.requests.append((url, key, secret))
        return self.payloads_by_url[url]


def _config(*, daily_alert_gb: int = 50, monthly_alert_gb: int = 1000) -> VnstatConfig:
    return VnstatConfig(
        daily_url="https://router.example.com/api/vnstat/service/daily/",
        monthly_url="https://router.example.com/api/vnstat/service/monthly/",
        key="api-key",
        secret="api-secret",
        default_days=7,
        default_months=1,
        daily_alert_gb=daily_alert_gb,
        monthly_alert_gb=monthly_alert_gb,
    )


def _client(config: VnstatConfig | None = None) -> tuple[VnstatClient, FakeJsonGetter]:
    json_getter = FakeJsonGetter(
        payloads_by_url={
            "https://router.example.com/api/vnstat/service/daily/": {
                "response": DAILY_RESPONSE
            },
            "https://router.example.com/api/vnstat/service/monthly/": {
                "response": MONTHLY_RESPONSE
            },
        }
    )
    return VnstatClient(json_getter=json_getter, config=config or _config()), json_getter


def test_build_usage_report_uses_daily_and_monthly_api_responses() -> None:
    client, json_getter = _client()

    report = client.build_usage_report(date(2026, 7, 9), day_count=1, month_count=1)

    assert [value.usage_date for value in report.daily_usage] == [
        date(2026, 7, 8),
        date(2026, 7, 9),
    ]
    assert [value.total_bytes for value in report.daily_usage] == [
        int(41.26 * 1024**3),
        int(9.53 * 1024**3),
    ]
    assert [value.usage_date for value in report.daily_alert_usage] == [
        date(2026, 7, 7),
        date(2026, 7, 8),
        date(2026, 7, 9),
    ]
    assert [period.name for period in report.monthly_usage] == [
        "May 2026",
        "Jun 2026",
        "Jun 2026 estimated",
    ]
    assert report.monthly_usage[1].total_bytes == int(778.87 * 1024**3)
    assert report.monthly_usage[2].is_estimated is True
    assert report.current_month_start == date(2026, 6, 1)
    assert report.estimated_current_month_bytes == int(937.29 * 1024**3)
    assert json_getter.requests == [
        (
            "https://router.example.com/api/vnstat/service/daily/",
            "api-key",
            "api-secret",
        ),
        (
            "https://router.example.com/api/vnstat/service/monthly/",
            "api-key",
            "api-secret",
        ),
    ]


def test_zero_months_includes_current_month_and_estimate() -> None:
    client, _json_getter = _client()

    report = client.build_usage_report(date(2026, 7, 9), day_count=0, month_count=0)

    assert [period.name for period in report.monthly_usage] == [
        "Jun 2026",
        "Jun 2026 estimated",
    ]


def test_negative_months_hides_monthly_usage_but_still_supports_monthly_alerts() -> None:
    client, _json_getter = _client()

    report = client.build_usage_report(date(2026, 7, 9), day_count=-1, month_count=-1)

    assert report.monthly_usage == ()
    assert report.estimated_current_month_bytes == int(937.29 * 1024**3)
    assert report.current_month_start == date(2026, 6, 1)


def test_negative_report_days_still_fetches_history_for_daily_alerts() -> None:
    client, _json_getter = _client()

    report = client.build_usage_report(date(2026, 7, 9), day_count=-1, month_count=-1)

    assert report.daily_usage == ()
    assert [value.usage_date for value in report.daily_alert_usage] == [
        date(2026, 7, 7),
        date(2026, 7, 8),
        date(2026, 7, 9),
    ]


def test_negative_report_days_skips_daily_api_when_alerts_are_disabled() -> None:
    client, json_getter = _client(_config(daily_alert_gb=0, monthly_alert_gb=0))

    report = client.build_usage_report(date(2026, 7, 9), day_count=-1, month_count=-1)

    assert report.daily_usage == ()
    assert report.daily_alert_usage == ()
    assert json_getter.requests == []


def test_monthly_response_must_include_estimate() -> None:
    json_getter = FakeJsonGetter(
        payloads_by_url={
            "https://router.example.com/api/vnstat/service/daily/": {
                "response": DAILY_RESPONSE
            },
            "https://router.example.com/api/vnstat/service/monthly/": {
                "response": "Jun '26 1.00 GiB | 1.00 GiB | 2.00 GiB |"
            },
        }
    )
    client = VnstatClient(json_getter=json_getter, config=_config())

    with pytest.raises(VnstatApiError, match="estimated row"):
        client.build_usage_report(date(2026, 7, 9))


def test_monthly_response_must_include_at_least_one_month_row() -> None:
    json_getter = FakeJsonGetter(
        payloads_by_url={
            "https://router.example.com/api/vnstat/service/daily/": {
                "response": DAILY_RESPONSE
            },
            "https://router.example.com/api/vnstat/service/monthly/": {
                "response": "estimated 1.00 GiB | 1.00 GiB | 2.00 GiB |"
            },
        }
    )
    client = VnstatClient(json_getter=json_getter, config=_config())

    with pytest.raises(VnstatApiError, match="month rows"):
        client.build_usage_report(date(2026, 7, 9))
