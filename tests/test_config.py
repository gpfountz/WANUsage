from __future__ import annotations

from pathlib import Path

import pytest

from wanusage.config import AppConfig, ConfigError, default_env_path, load_config


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


@pytest.fixture(autouse=True)
def use_private_test_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    env_path: Path = tmp_path / ".env"
    env_path.write_text(
        "key=api-key\nsecret=api-secret\nsmtp_username=mailer\nsmtp_password=secret\n",
        encoding="utf-8",
    )
    env_path.chmod(0o600)
    monkeypatch.setattr("wanusage.config.default_env_path", lambda: env_path)
    return env_path


def _config_text(**overrides: str) -> str:
    values: dict[str, str] = {
        "base_url": '"https://router.example.com"',
        "daily_url_path": '"/api/vnstat/service/daily"',
        "monthly_url_path": '"/api/vnstat/service/monthly"',
        "default_days": "7",
        "default_months": "1",
        "daily_alert_gb": "50",
        "monthly_alert_gb": "1000",
        "smtp_port": "587",
    }
    values.update(overrides)
    return f"""
[vnstat]
base_url = {values["base_url"]}
daily_url_path = {values["daily_url_path"]}
monthly_url_path = {values["monthly_url_path"]}
default_days = {values["default_days"]}
default_months = {values["default_months"]}
daily_alert_gb = {values["daily_alert_gb"]}
monthly_alert_gb = {values["monthly_alert_gb"]}

[email]
smtp_host = "smtp.example.com"
smtp_port = {values["smtp_port"]}
from_address = "wan@example.com"
to_address = "recipient@example.com"
"""


def test_load_config_reads_typed_values(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_path.write_text(_config_text(), encoding="utf-8")

    config: AppConfig = load_config(config_path)

    assert config.vnstat.base_url == "https://router.example.com"
    assert config.vnstat.daily_url_path == "/api/vnstat/service/daily"
    assert config.vnstat.monthly_url_path == "/api/vnstat/service/monthly"
    assert config.vnstat.daily_url == "https://router.example.com/api/vnstat/service/daily"
    assert config.vnstat.monthly_url == "https://router.example.com/api/vnstat/service/monthly"
    assert config.api_credentials.key == "api-key"
    assert config.api_credentials.secret == "api-secret"
    assert config.smtp_credentials.username == "mailer"
    assert config.smtp_credentials.password == "secret"
    assert config.vnstat.default_days == 7
    assert config.vnstat.default_months == 1
    assert config.vnstat.daily_alert_gb == 50
    assert config.vnstat.monthly_alert_gb == 1000
    assert config.email.smtp_host == "smtp.example.com"
    assert config.email.from_address == "wan@example.com"
    assert config.email.to_address == "recipient@example.com"
    assert config.email.use_tls is True
    assert "api-secret" not in repr(config.api_credentials)
    assert "secret" not in repr(config.smtp_credentials)
    assert "secret" not in repr(config.email)


def test_default_env_path_uses_the_wanusage_config_directory() -> None:
    assert default_env_path() == Path.home() / ".config" / "wanusage" / ".env"


def test_load_config_defaults_default_months_to_one(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_text: str = _config_text().replace("default_months = 1\n", "")
    config_path.write_text(config_text, encoding="utf-8")

    config: AppConfig = load_config(config_path)

    assert config.vnstat.default_months == 1


def test_load_config_rejects_legacy_api_credentials_in_toml(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_text: str = _config_text().replace(
        "default_days = 7",
        'key = "api-key"\nsecret = "api-secret"\ndefault_days = 7',
    )
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ConfigError, match="Move vnstat"):
        load_config(config_path)


def test_load_config_rejects_legacy_smtp_credentials_in_toml(tmp_path: Path) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    config_text: str = _config_text().replace(
        'from_address = "wan@example.com"',
        'username = "mailer"\npassword = "secret"\nfrom_address = "wan@example.com"',
    )
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ConfigError, match="Move email"):
        load_config(config_path)


@pytest.mark.parametrize(
    "env_text",
    [
        "key=api-key\n",
        "key=api-key\nsecret=\n",
        "key=api-key\nkey=other\nsecret=api-secret\n",
        "username=api-key\nsecret=api-secret\n",
        "key=api-key\nsecret=api-secret\nsmtp_username=mailer\n",
    ],
)
def test_load_config_rejects_invalid_credentials_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_text: str,
) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    env_path: Path = tmp_path / ".env"
    config_path.write_text(_config_text(), encoding="utf-8")
    env_path.write_text(env_text, encoding="utf-8")
    monkeypatch.setattr("wanusage.config.default_env_path", lambda: env_path)

    with pytest.raises(ConfigError, match="Credentials file"):
        load_config(config_path)


def test_load_config_rejects_group_readable_credentials_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path: Path = tmp_path / "wanusage.toml"
    env_path: Path = tmp_path / ".env"
    config_path.write_text(_config_text(), encoding="utf-8")
    env_path.write_text("key=api-key\nsecret=api-secret\n", encoding="utf-8")
    env_path.chmod(0o640)
    monkeypatch.setattr("wanusage.config.default_env_path", lambda: env_path)

    with pytest.raises(ConfigError, match="Credentials file permissions"):
        load_config(config_path)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("base_url", '"http://router.example.com"'),
        ("base_url", '"https://key:secret@router.example.com"'),
        ("base_url", '"https:///api"'),
        ("base_url", '"https://router.example.com/api"'),
        ("daily_url_path", '"vnstat/service/daily"'),
        ("monthly_url_path", '"https://router.example.com/api/vnstat/service/monthly"'),
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
