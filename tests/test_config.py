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


def _config_text(**overrides: str) -> str:
    values: dict[str, str] = {
        "daily_url": '"https://router.example.com/api/vnstat/service/daily/"',
        "monthly_url": '"https://router.example.com/api/vnstat/service/monthly/"',
        "key": '"api-key"',
        "secret": '"api-secret"',
        "default_days": "7",
        "default_months": "1",
        "daily_alert_gb": "50",
        "monthly_alert_gb": "1000",
        "smtp_port": "587",
    }
    values.update(overrides)
    return f"""
[vnstat]
daily_url = {values["daily_url"]}
monthly_url = {values["monthly_url"]}
key = {values["key"]}
secret = {values["secret"]}
default_days = {values["default_days"]}
default_months = {values["default_months"]}
daily_alert_gb = {values["daily_alert_gb"]}
monthly_alert_gb = {values["monthly_alert_gb"]}

[email]
smtp_host = "smtp.example.com"
smtp_port = {values["smtp_port"]}
username = "mailer"
password = "secret"
from_address = "wan@example.com"
to_address = "recipient@example.com"
"""


def test_load_config_reads_typed_values(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(_config_text(), encoding="utf-8")

    config: AppConfig = load_config(config_path)

    assert config.vnstat.daily_url == "https://router.example.com/api/vnstat/service/daily/"
    assert config.vnstat.monthly_url == (
        "https://router.example.com/api/vnstat/service/monthly/"
    )
    assert config.vnstat.key == "api-key"
    assert config.vnstat.secret == "api-secret"
    assert config.vnstat.default_days == 7
    assert config.vnstat.default_months == 1
    assert config.vnstat.daily_alert_gb == 50
    assert config.vnstat.monthly_alert_gb == 1000
    assert config.email.smtp_host == "smtp.example.com"
    assert config.email.from_address == "wan@example.com"
    assert config.email.to_address == "recipient@example.com"
    assert config.email.use_tls is True
    assert "api-secret" not in repr(config.vnstat)
    assert "secret" not in repr(config.email)


def test_load_config_defaults_default_months_to_one(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_text: str = _config_text().replace("default_months = 1\n", "")
    config_path.write_text(config_text, encoding="utf-8")

    config: AppConfig = load_config(config_path)

    assert config.vnstat.default_months == 1


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("daily_url", '"http://router.example.com/api/vnstat/service/daily/"'),
        ("monthly_url", '"https://key:secret@router.example.com/api/vnstat/service/monthly/"'),
        ("daily_url", '"https:///api/vnstat/service/daily/"'),
    ],
)
def test_load_config_rejects_insecure_or_invalid_api_urls(
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(_config_text(**{key: value}), encoding="utf-8")

    with pytest.raises(ConfigError, match=key):
        load_config(config_path)


def test_load_config_rejects_missing_required_section(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text("[email]\nsmtp_host = 'smtp.example.com'\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required"):
        load_config(config_path)


def test_load_config_rejects_group_readable_file(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text("[vnstat]\n", encoding="utf-8")
    config_path.chmod(0o640)

    with pytest.raises(ConfigError, match="permissions"):
        load_config(config_path)


@pytest.mark.parametrize("smtp_port", [0, 65536])
def test_load_config_rejects_smtp_port_outside_range(
    tmp_path: Path,
    smtp_port: int,
) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(_config_text(smtp_port=str(smtp_port)), encoding="utf-8")

    with pytest.raises(ConfigError, match="smtp_port"):
        load_config(config_path)


@pytest.mark.parametrize(
    ("key", "original_value"),
    [
        ("default_days", "7"),
        ("default_months", "1"),
        ("daily_alert_gb", "50"),
        ("monthly_alert_gb", "1000"),
        ("smtp_port", "587"),
    ],
)
def test_load_config_rejects_boolean_integer_values(
    tmp_path: Path,
    key: str,
    original_value: str,
) -> None:
    config_text: str = _config_text().replace(
        f"{key} = {original_value}",
        f"{key} = true",
        1,
    )
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ConfigError, match=key):
        load_config(config_path)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("default_days", "30"),
        ("default_months", "12"),
        ("daily_alert_gb", "1000"),
        ("monthly_alert_gb", "10000"),
    ],
)
def test_load_config_rejects_bounded_values_outside_range(
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(_config_text(**{key: value}), encoding="utf-8")

    with pytest.raises(ConfigError, match=key):
        load_config(config_path)
