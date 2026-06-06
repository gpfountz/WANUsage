from __future__ import annotations

from pathlib import Path

import pytest

from wanusage.config import AppConfig, ConfigError, load_config


def test_load_config_reads_typed_values(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(
        """
[router]
host = "192.168.1.1"
port = 22
username = "root"
ssh_key_path = "~/router-key"

[vnstat]
database_path = "/var/lib/vnstat/vnstat.db"
interface_name = "eth0"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 50

[email]
smtp_host = "smtp.example.com"
smtp_port = 587
username = "mailer"
password = "secret"
from_address = "wan@example.com"
to_address = "recipient@example.com"
""",
        encoding="utf-8",
    )

    config: AppConfig = load_config(config_path)

    assert config.router.host == "192.168.1.1"
    assert config.router.port == 22
    assert config.router.username == "root"
    assert config.router.ssh_key_path == Path("~/router-key").expanduser()
    assert config.vnstat.database_path == "/var/lib/vnstat/vnstat.db"
    assert config.vnstat.interface_name == "eth0"
    assert config.vnstat.billing_cycle_day == 14
    assert config.vnstat.default_days == 7
    assert config.vnstat.daily_alert_gb == 50
    assert config.email.smtp_host == "smtp.example.com"
    assert config.email.from_address == "wan@example.com"
    assert config.email.to_address == "recipient@example.com"
    assert config.email.use_tls is True


def test_load_config_rejects_missing_required_section(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text("[router]\nhost = '192.168.1.1'\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required"):
        load_config(config_path)


def test_load_config_rejects_default_days_outside_range(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(
        """
[router]
host = "192.168.1.1"
port = 22
username = "root"
ssh_key_path = "~/router-key"

[vnstat]
database_path = "/var/lib/vnstat/vnstat.db"
interface_name = "eth0"
billing_cycle_day = 14
default_days = 61
daily_alert_gb = 50
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="default_days"):
        load_config(config_path)


def test_load_config_rejects_daily_alert_gb_outside_range(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(
        """
[router]
host = "192.168.1.1"
port = 22
username = "root"
ssh_key_path = "~/router-key"

[vnstat]
database_path = "/var/lib/vnstat/vnstat.db"
interface_name = "eth0"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 1000
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="daily_alert_gb"):
        load_config(config_path)


@pytest.mark.parametrize("billing_cycle_day", [0, 32])
def test_load_config_rejects_billing_cycle_day_outside_range(
    tmp_path: Path,
    billing_cycle_day: int,
) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(
        f"""
[router]
host = "192.168.1.1"
port = 22
username = "root"
ssh_key_path = "~/router-key"

[vnstat]
database_path = "/var/lib/vnstat/vnstat.db"
interface_name = "eth0"
billing_cycle_day = {billing_cycle_day}
default_days = 7
daily_alert_gb = 50
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="billing_cycle_day"):
        load_config(config_path)
