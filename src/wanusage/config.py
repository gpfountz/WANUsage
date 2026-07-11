from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from stat import S_IMODE
from typing import Any
from urllib.parse import SplitResult, urlsplit


@dataclass(frozen=True)
class VnstatConfig:
    """vnStat API, reporting, and alert settings."""

    daily_url: str
    monthly_url: str
    default_days: int
    default_months: int
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
class ApiCredentials:
    """OPNsense API credentials loaded from the private environment file."""

    key: str
    secret: str = field(repr=False)


@dataclass(frozen=True)
class AppConfig:
    """The complete validated application configuration."""

    vnstat: VnstatConfig
    email: EmailConfig
    api_credentials: ApiCredentials


class ConfigError(ValueError):
    """Raised when the configuration file is missing, unsafe, or invalid."""


def default_env_path() -> Path:
    """Return the fixed credentials file path for the user running the app."""

    return Path.home() / ".config" / "wanusage" / ".env"


def load_config(config_path: Path) -> AppConfig:
    """Load and validate TOML settings and private API credentials.

    The TOML file holds SMTP credentials and the separate ``.env`` file holds
    OPNsense API credentials. Both files must be private to their owner.

    Raises:
        ConfigError: If the file is missing, insecure, malformed, or contains an
            invalid or missing setting.
    """

    _validate_private_file(config_path, "Config file")

    with config_path.open("rb") as config_file:
        raw_config: dict[str, Any] = tomllib.load(config_file)

    vnstat_section: dict[str, Any] = _required_section(raw_config, "vnstat")
    email_section: dict[str, Any] = _optional_section(raw_config, "email")
    _reject_legacy_api_credentials(vnstat_section)

    return AppConfig(
        vnstat=VnstatConfig(
            daily_url=_required_https_url(vnstat_section, "daily_url"),
            monthly_url=_required_https_url(
                vnstat_section,
                "monthly_url",
            ),
            default_days=_bounded_int(
                vnstat_section,
                "default_days",
                minimum=-1,
                maximum=29,
            ),
            default_months=_bounded_optional_int(
                vnstat_section,
                "default_months",
                default=1,
                minimum=-1,
                maximum=11,
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
        api_credentials=load_api_credentials(default_env_path()),
    )


def load_api_credentials(env_path: Path) -> ApiCredentials:
    """Load the required OPNsense credentials from a simple private ``.env`` file.

    The file supports blank lines and whole-line comments. It must define only
    nonempty ``key`` and ``secret`` assignments, each exactly once.
    """

    _validate_private_file(env_path, "Credentials file")
    values: dict[str, str] = {}

    for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), 1):
        line: str = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        name, separator, value = line.partition("=")
        if not separator or name not in {"key", "secret"}:
            raise ConfigError(
                f"Credentials file contains an invalid entry on line {line_number}: {env_path}"
            )
        if name in values:
            raise ConfigError(
                f"Credentials file defines {name} more than once: {env_path}"
            )

        credential_value: str = _unquote_env_value(value.strip())
        if not credential_value:
            raise ConfigError(f"Credentials file has an empty {name} value: {env_path}")
        values[name] = credential_value

    missing_names: list[str] = [
        name for name in ("key", "secret") if name not in values
    ]
    if missing_names:
        missing_text: str = ", ".join(missing_names)
        raise ConfigError(
            f"Credentials file is missing required value(s) {missing_text}: {env_path}"
        )

    return ApiCredentials(key=values["key"], secret=values["secret"])


def _validate_private_file(path: Path, label: str) -> None:
    """Require a regular, owner-only file before reading its credentials."""

    if not path.exists():
        raise ConfigError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ConfigError(f"{label} must be a regular file: {path}")
    if S_IMODE(path.stat().st_mode) & 0o077:
        raise ConfigError(f"{label} permissions must not allow group or other access: {path}")


def _reject_legacy_api_credentials(vnstat_section: dict[str, Any]) -> None:
    """Reject credentials left in TOML after the migration to the ``.env`` file."""

    legacy_keys: set[str] = {"key", "secret"} & vnstat_section.keys()
    if legacy_keys:
        names: str = ", ".join(sorted(legacy_keys))
        raise ConfigError(
            f"Move vnstat {names} to {default_env_path()} and remove it from the config file"
        )


def _unquote_env_value(value: str) -> str:
    """Remove one matching pair of optional quotes from a dotenv value."""

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        return value[1:-1]
    return value


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


def _required_https_url(section: dict[str, Any], key: str) -> str:
    """Return a required HTTPS API URL without embedded credentials.

    Basic Auth credentials are sent to this URL, so accepting cleartext HTTP
    or a URL user-info component could disclose secrets through configuration
    mistakes or error output.
    """

    value: str = _required_str(section, key)
    try:
        parsed_url: SplitResult = urlsplit(value)
        _ = parsed_url.port
    except ValueError as error:
        raise ConfigError(f"Config value must be a valid HTTPS URL: {key}") from error

    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
    ):
        raise ConfigError(f"Config value must be an HTTPS URL without credentials: {key}")
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
