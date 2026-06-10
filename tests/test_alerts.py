from __future__ import annotations

from datetime import date
from pathlib import Path

from wanusage.alerts import (
    AlertStateStore,
    alert_state_path_for_config,
    choose_alert,
    should_send_monthly_alert,
)
from wanusage.models import DailyUsage


def test_choose_alert_selects_most_recent_unalerted_high_usage_day() -> None:
    decision = choose_alert(
        (
            DailyUsage(usage_date=date(2026, 5, 24), total_bytes=10 * 1024**3),
            DailyUsage(usage_date=date(2026, 5, 25), total_bytes=20 * 1024**3),
            DailyUsage(usage_date=date(2026, 5, 26), total_bytes=30 * 1024**3),
        ),
        daily_alert_gb=15,
        last_alert_date=date(2026, 5, 24),
    )

    assert decision.should_send is True
    assert decision.alert_date == date(2026, 5, 26)


def test_choose_alert_skips_days_already_covered_by_state() -> None:
    decision = choose_alert(
        (
            DailyUsage(usage_date=date(2026, 5, 24), total_bytes=20 * 1024**3),
            DailyUsage(usage_date=date(2026, 5, 25), total_bytes=20 * 1024**3),
        ),
        daily_alert_gb=15,
        last_alert_date=date(2026, 5, 25),
    )

    assert decision.should_send is False
    assert decision.alert_date is None


def test_choose_alert_uses_strictly_greater_than_threshold() -> None:
    decision = choose_alert(
        (DailyUsage(usage_date=date(2026, 5, 24), total_bytes=15 * 1024**3),),
        daily_alert_gb=15,
        last_alert_date=None,
    )

    assert decision.should_send is False


def test_choose_alert_is_disabled_when_threshold_is_zero() -> None:
    decision = choose_alert(
        (DailyUsage(usage_date=date(2026, 5, 24), total_bytes=100 * 1024**3),),
        daily_alert_gb=0,
        last_alert_date=None,
    )

    assert decision.should_send is False
    assert decision.alert_date is None


def test_alert_state_store_reads_and_writes_single_date(tmp_path: Path) -> None:
    state_path: Path = tmp_path / "wanusage-alert-state.txt"
    store = AlertStateStore(state_path)

    assert store.read_last_alert_date() is None

    store.write_last_alert_date(date(2026, 5, 26))

    assert state_path.read_text(encoding="utf-8") == "2026-05-26\n"
    assert store.read_last_alert_date() == date(2026, 5, 26)


def test_alert_state_path_lives_next_to_config() -> None:
    config_path = Path("/tmp/example/wanusage.toml")

    state_path: Path = alert_state_path_for_config(config_path)

    assert state_path.name == "wanusage-alert-state.txt"
    assert state_path.parent == config_path.resolve().parent


def test_monthly_alert_is_disabled_when_threshold_is_zero() -> None:
    assert should_send_monthly_alert(2000 * 1024**3, 0) is False


def test_monthly_alert_requires_estimate_over_threshold() -> None:
    assert should_send_monthly_alert(1000 * 1024**3, 1000) is False
    assert should_send_monthly_alert(1000 * 1024**3 + 1, 1000) is True
