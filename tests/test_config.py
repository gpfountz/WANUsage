from __future__ import annotations

from pathlib import Path

import pytest

from wanusage.config import AppConfig, ConfigError, load_config


@pytest.fixture(autouse=True)
def write_private_test_configs(monkeypatch: pytest.MonkeyPatch) -> None:
    original_write_text = Path.write_text

    def write_text(
        path: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        written_characters: int = original_write_text(
            path,
            data,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )
        path.chmod(0o600)
        return written_characters

    monkeypatch.setattr(Path, "write_text", write_text)


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
reporting_timezone = "America/New_York"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 50
monthly_alert_gb = 1000

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
    assert config.vnstat.reporting_timezone.key == "America/New_York"
    assert config.vnstat.billing_cycle_day == 14
    assert config.vnstat.default_days == 7
    assert config.vnstat.daily_alert_gb == 50
    assert config.vnstat.monthly_alert_gb == 1000
    assert config.email.smtp_host == "smtp.example.com"
    assert config.email.from_address == "wan@example.com"
    assert config.email.to_address == "recipient@example.com"
    assert config.email.use_tls is True
    assert "secret" not in repr(config.email)


def test_load_config_rejects_missing_required_section(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text("[router]\nhost = '192.168.1.1'\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required"):
        load_config(config_path)


def test_load_config_rejects_group_readable_file(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text("[router]\n", encoding="utf-8")
    config_path.chmod(0o640)

    with pytest.raises(ConfigError, match="permissions"):
        load_config(config_path)


def test_load_config_rejects_unknown_reporting_timezone(tmp_path: Path) -> None:
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
reporting_timezone = "Not/A_Timezone"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 50
monthly_alert_gb = 1000
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Unknown IANA timezone"):
        load_config(config_path)


@pytest.mark.parametrize("port", [0, 65536])
def test_load_config_rejects_router_port_outside_range(
    tmp_path: Path,
    port: int,
) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(
        f"""
[router]
host = "192.168.1.1"
port = {port}
username = "root"
ssh_key_path = "~/router-key"

[vnstat]
database_path = "/var/lib/vnstat/vnstat.db"
interface_name = "eth0"
reporting_timezone = "America/New_York"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 50
monthly_alert_gb = 1000
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="port"):
        load_config(config_path)


@pytest.mark.parametrize("smtp_port", [0, 65536])
def test_load_config_rejects_smtp_port_outside_range(
    tmp_path: Path,
    smtp_port: int,
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
reporting_timezone = "America/New_York"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 50
monthly_alert_gb = 1000

[email]
smtp_port = {smtp_port}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="smtp_port"):
        load_config(config_path)


@pytest.mark.parametrize(
    ("key", "original_value"),
    [
        ("port", 22),
        ("billing_cycle_day", 14),
        ("default_days", 7),
        ("daily_alert_gb", 50),
        ("monthly_alert_gb", 1000),
        ("smtp_port", 587),
    ],
)
def test_load_config_rejects_boolean_integer_values(
    tmp_path: Path,
    key: str,
    original_value: int,
) -> None:
    config_text: str = """
[router]
host = "192.168.1.1"
port = 22
username = "root"
ssh_key_path = "~/router-key"

[vnstat]
database_path = "/var/lib/vnstat/vnstat.db"
interface_name = "eth0"
reporting_timezone = "America/New_York"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 50
monthly_alert_gb = 1000

[email]
smtp_port = 587
"""
    config_text = config_text.replace(
        f"{key} = {original_value}",
        f"{key} = true",
        1,
    )
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ConfigError, match=key):
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
reporting_timezone = "America/New_York"
billing_cycle_day = 14
default_days = 61
daily_alert_gb = 50
monthly_alert_gb = 1000
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
reporting_timezone = "America/New_York"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 1000
monthly_alert_gb = 1000
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="daily_alert_gb"):
        load_config(config_path)


def test_load_config_rejects_monthly_alert_gb_outside_range(tmp_path: Path) -> None:
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
reporting_timezone = "America/New_York"
billing_cycle_day = 14
default_days = 7
daily_alert_gb = 50
monthly_alert_gb = 10000
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="monthly_alert_gb"):
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
reporting_timezone = "America/New_York"
billing_cycle_day = {billing_cycle_day}
default_days = 7
daily_alert_gb = 50
monthly_alert_gb = 1000
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="billing_cycle_day"):
        load_config(config_path)
