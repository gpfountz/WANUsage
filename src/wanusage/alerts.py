from __future__ import annotations

import fcntl
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from wanusage.models import DailyUsage

BYTES_PER_GIB: int = 1024**3
ALERT_SUBJECT: str = "daily high usage alert"
MONTHLY_ALERT_SUBJECT: str = "monthly high usage alert"


@dataclass(frozen=True)
class AlertDecision:
    """The result of evaluating daily usage against the alert policy."""

    should_send: bool
    alert_date: date | None


@dataclass(frozen=True)
class AlertStateStore:
    """Persist the latest alerted date and serialize access across processes."""

    state_path: Path

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Hold an exclusive advisory lock for a complete alert transaction.

        Callers should read state, send any required email, and write updated
        state inside this context to prevent duplicate alerts from concurrent
        application runs.
        """

        lock_path: Path = self.state_path.with_suffix(f"{self.state_path.suffix}.lock")
        lock_descriptor: int = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_descriptor, "r+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def read_last_alert_date(self) -> date | None:
        """Read the stored ISO date, quarantining invalid state for recovery."""

        if not self.state_path.exists():
            return None

        raw_value: str = self.state_path.read_text(encoding="utf-8").strip()
        if not raw_value:
            return None

        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            invalid_path: Path = self.state_path.with_suffix(
                f"{self.state_path.suffix}.invalid"
            )
            os.replace(self.state_path, invalid_path)
            return None

    def write_last_alert_date(self, alert_date: date) -> None:
        """Atomically replace the state file with ``alert_date``.

        A temporary file in the same directory is flushed and then renamed over
        the destination so readers never observe a partially written value.
        """

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.state_path.parent,
                prefix=f".{self.state_path.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(f"{alert_date.isoformat()}\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, self.state_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def alert_state_path_for_config(config_path: Path) -> Path:
    """Return the daily-alert state path associated with ``config_path``."""

    resolved_path: Path = config_path.resolve()
    return resolved_path.with_name(f"{resolved_path.stem}-alert-state.txt")


def monthly_alert_state_path_for_config(config_path: Path) -> Path:
    """Return the monthly-alert state path associated with ``config_path``."""

    resolved_path: Path = config_path.resolve()
    return resolved_path.with_name(f"{resolved_path.stem}-monthly-alert-state.txt")


def choose_alert(
    daily_usage: tuple[DailyUsage, ...],
    *,
    daily_alert_gb: int,
    last_alert_date: date | None,
) -> AlertDecision:
    """Choose the most recent unalerted day whose usage exceeds the threshold.

    A nonpositive threshold disables daily alerts. Usage must be strictly
    greater than the configured GiB value to trigger an alert.
    """

    if daily_alert_gb <= 0:
        return AlertDecision(should_send=False, alert_date=None)

    threshold_bytes: int = daily_alert_gb * BYTES_PER_GIB
    triggering_dates: list[date] = [
        value.usage_date
        for value in daily_usage
        if value.total_bytes > threshold_bytes
        and (last_alert_date is None or value.usage_date > last_alert_date)
    ]

    if not triggering_dates:
        return AlertDecision(should_send=False, alert_date=None)

    return AlertDecision(should_send=True, alert_date=max(triggering_dates))


def should_send_monthly_alert(
    estimated_bytes: int,
    monthly_alert_gb: int,
    *,
    current_period_start: date,
    last_alert_period_start: date | None,
) -> bool:
    """Return whether the current billing-period estimate needs an alert.

    Monthly alerts are disabled by a nonpositive threshold and are emitted at
    most once per billing period. The estimate must strictly exceed the limit.
    """

    if monthly_alert_gb <= 0:
        return False
    if (
        last_alert_period_start is not None
        and current_period_start <= last_alert_period_start
    ):
        return False
    return estimated_bytes > monthly_alert_gb * BYTES_PER_GIB
