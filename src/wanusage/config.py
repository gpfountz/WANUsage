from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from stat import S_IMODE
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class RouterConfig:
    """SSH connection settings for the OPNsense router."""

    host: str
    port: int
    username: str
    ssh_key_path: Path


@dataclass(frozen=True)
class VnstatConfig:
    """vnStat query, reporting, billing-cycle, and alert settings."""

    database_path: str
    interface_name: str
    reporting_timezone: ZoneInfo
    billing_cycle_day: int
    default_days: int
    daily_alert_gb: int
    monthly_alert_gb: int


@dataclass(frozen=True)
class EmailConfig:
    """SMTP settings used for requested reports and automatic alerts."""

    smtp_host: str
    smtp_port: int
    username: str
    password: str = field(repr=False)
    from_address: str
    to_address: str
    use_tls: bool


@dataclass(frozen=True)
class AppConfig:
    """The complete validated application configuration."""

    router: RouterConfig
    vnstat: VnstatConfig
    email: EmailConfig


class ConfigError(ValueError):
    """Raised when the configuration file is missing, unsafe, or invalid."""


def load_config(config_path: Path) -> AppConfig:
    """Load and validate an application configuration from a private TOML file.

    The file must not grant any permissions to group or other users because it
    may contain SSH paths and SMTP credentials.

    Raises:
        ConfigError: If the file is missing, insecure, malformed, or contains an
            invalid or missing setting.
    """

    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")
    if S_IMODE(config_path.stat().st_mode) & 0o077:
        raise ConfigError(
            f"Config file permissions must not allow group or other access: {config_path}"
        )

    with config_path.open("rb") as config_file:
        raw_config: dict[str, Any] = tomllib.load(config_file)

    router_section: dict[str, Any] = _required_section(raw_config, "router")
    vnstat_section: dict[str, Any] = _required_section(raw_config, "vnstat")
    email_section: dict[str, Any] = _optional_section(raw_config, "email")

    return AppConfig(
        router=RouterConfig(
            host=_required_str(router_section, "host"),
            port=_bounded_int(router_section, "port", minimum=1, maximum=65535),
            username=_required_str(router_section, "username"),
            ssh_key_path=Path(_required_str(router_section, "ssh_key_path")).expanduser(),
        ),
        vnstat=VnstatConfig(
            database_path=_required_str(vnstat_section, "database_path"),
            interface_name=_required_str(vnstat_section, "interface_name"),
            reporting_timezone=_required_timezone(
                vnstat_section,
                "reporting_timezone",
            ),
            billing_cycle_day=_bounded_int(
                vnstat_section,
                "billing_cycle_day",
                minimum=1,
                maximum=31,
            ),
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
            monthly_alert_gb=_bounded_int(
                vnstat_section,
                "monthly_alert_gb",
                minimum=0,
                maximum=9999,
            ),
        ),
        email=EmailConfig(
            smtp_host=_optional_str(email_section, "smtp_host"),
            smtp_port=_bounded_optional_int(
                email_section,
                "smtp_port",
                default=587,
                minimum=1,
                maximum=65535,
            ),
            username=_optional_str(email_section, "username"),
            password=_optional_str(email_section, "password"),
            from_address=_optional_str(email_section, "from_address"),
            to_address=_optional_str(email_section, "to_address"),
            use_tls=_optional_bool(email_section, "use_tls", default=True),
        ),
    )


def _required_section(raw_config: dict[str, Any], section_name: str) -> dict[str, Any]:
    """Return a required TOML table or raise ``ConfigError``."""

    section: Any = raw_config.get(section_name)
    if not isinstance(section, dict):
        raise ConfigError(f"Missing required [{section_name}] config section")
    return section


def _optional_section(raw_config: dict[str, Any], section_name: str) -> dict[str, Any]:
    """Return an optional TOML table, defaulting to an empty table."""

    section: Any = raw_config.get(section_name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"[{section_name}] config section must be a table")
    return section


def _required_str(section: dict[str, Any], key: str) -> str:
    """Return a required nonempty string setting."""

    value: Any = section.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"Missing required string config value: {key}")
    return value


def _optional_str(section: dict[str, Any], key: str) -> str:
    """Return an optional string setting, defaulting to an empty string."""

    value: Any = section.get(key, "")
    if not isinstance(value, str):
        raise ConfigError(f"Config value must be a string: {key}")
    return value


def _required_int(section: dict[str, Any], key: str) -> int:
    """Return a required integer setting while rejecting booleans."""

    value: Any = section.get(key)
    if type(value) is not int:
        raise ConfigError(f"Missing required integer config value: {key}")
    return value


def _optional_int(section: dict[str, Any], key: str, *, default: int) -> int:
    """Return an optional integer setting or its supplied default."""

    value: Any = section.get(key, default)
    if type(value) is not int:
        raise ConfigError(f"Config value must be an integer: {key}")
    return value


def _bounded_int(section: dict[str, Any], key: str, *, minimum: int, maximum: int) -> int:
    """Return a required integer constrained to an inclusive range."""

    value: int = _required_int(section, key)
    if value < minimum or value > maximum:
        raise ConfigError(f"Config value must be between {minimum} and {maximum}: {key}")
    return value


def _bounded_optional_int(
    section: dict[str, Any],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Return an optional integer constrained to an inclusive range."""

    value: int = _optional_int(section, key, default=default)
    if value < minimum or value > maximum:
        raise ConfigError(f"Config value must be between {minimum} and {maximum}: {key}")
    return value


def _optional_bool(section: dict[str, Any], key: str, *, default: bool) -> bool:
    """Return an optional boolean setting or its supplied default."""

    value: Any = section.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"Config value must be a boolean: {key}")
    return value


def _required_timezone(section: dict[str, Any], key: str) -> ZoneInfo:
    """Return a required IANA timezone as a ``ZoneInfo`` instance."""

    timezone_name: str = _required_str(section, key)
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ConfigError(
            f"Unknown IANA timezone for config value {key}: {timezone_name}"
        ) from error
