from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RouterConfig:
    host: str
    port: int
    username: str
    ssh_key_path: Path


@dataclass(frozen=True)
class VnstatConfig:
    database_path: str
    interface_name: str
    default_days: int
    daily_alert_gb: int


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    from_address: str
    to_address: str
    use_tls: bool


@dataclass(frozen=True)
class AppConfig:
    router: RouterConfig
    vnstat: VnstatConfig
    email: EmailConfig


class ConfigError(ValueError):
    pass


def load_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")

    with config_path.open("rb") as config_file:
        raw_config: dict[str, Any] = tomllib.load(config_file)

    router_section: dict[str, Any] = _required_section(raw_config, "router")
    vnstat_section: dict[str, Any] = _required_section(raw_config, "vnstat")
    email_section: dict[str, Any] = _optional_section(raw_config, "email")

    return AppConfig(
        router=RouterConfig(
            host=_required_str(router_section, "host"),
            port=_required_int(router_section, "port"),
            username=_required_str(router_section, "username"),
            ssh_key_path=Path(_required_str(router_section, "ssh_key_path")).expanduser(),
        ),
        vnstat=VnstatConfig(
            database_path=_required_str(vnstat_section, "database_path"),
            interface_name=_required_str(vnstat_section, "interface_name"),
            default_days=_bounded_int(
                vnstat_section,
                "default_days",
                minimum=-1,
                maximum=60,
            ),
            daily_alert_gb=_bounded_int(
                vnstat_section,
                "daily_alert_gb",
                minimum=0,
                maximum=999,
            ),
        ),
        email=EmailConfig(
            smtp_host=_optional_str(email_section, "smtp_host"),
            smtp_port=_optional_int(email_section, "smtp_port", default=587),
            username=_optional_str(email_section, "username"),
            password=_optional_str(email_section, "password"),
            from_address=_optional_str(email_section, "from_address"),
            to_address=_optional_str(email_section, "to_address"),
            use_tls=_optional_bool(email_section, "use_tls", default=True),
        ),
    )


def _required_section(raw_config: dict[str, Any], section_name: str) -> dict[str, Any]:
    section: Any = raw_config.get(section_name)
    if not isinstance(section, dict):
        raise ConfigError(f"Missing required [{section_name}] config section")
    return section


def _optional_section(raw_config: dict[str, Any], section_name: str) -> dict[str, Any]:
    section: Any = raw_config.get(section_name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"[{section_name}] config section must be a table")
    return section


def _required_str(section: dict[str, Any], key: str) -> str:
    value: Any = section.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"Missing required string config value: {key}")
    return value


def _optional_str(section: dict[str, Any], key: str) -> str:
    value: Any = section.get(key, "")
    if not isinstance(value, str):
        raise ConfigError(f"Config value must be a string: {key}")
    return value


def _required_int(section: dict[str, Any], key: str) -> int:
    value: Any = section.get(key)
    if not isinstance(value, int):
        raise ConfigError(f"Missing required integer config value: {key}")
    return value


def _optional_int(section: dict[str, Any], key: str, *, default: int) -> int:
    value: Any = section.get(key, default)
    if not isinstance(value, int):
        raise ConfigError(f"Config value must be an integer: {key}")
    return value


def _bounded_int(section: dict[str, Any], key: str, *, minimum: int, maximum: int) -> int:
    value: int = _required_int(section, key)
    if value < minimum or value > maximum:
        raise ConfigError(f"Config value must be between {minimum} and {maximum}: {key}")
    return value


def _optional_bool(section: dict[str, Any], key: str, *, default: bool) -> bool:
    value: Any = section.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"Config value must be a boolean: {key}")
    return value
