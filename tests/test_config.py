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
interface_id = 1
default_days = 7

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
    assert config.vnstat.interface_id == 1
    assert config.vnstat.default_days == 7
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
interface_id = 1
default_days = 61
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="default_days"):
        load_config(config_path)
