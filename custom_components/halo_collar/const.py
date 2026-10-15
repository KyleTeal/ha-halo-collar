"""Halo Collar integration constants."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "halo_collar"

CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_EXPIRES_AT: Final = "expires_at"
CONF_TOKEN_TYPE: Final = "token_type"
CONF_APP_INSTANCE_ID: Final = "app_instance_id"
CONF_USER_ID: Final = "user_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_REFRESH_TELEMETRY: Final = "refresh_telemetry"

DEFAULT_SCAN_INTERVAL: Final = 120
MIN_SCAN_INTERVAL: Final = 60
MAX_SCAN_INTERVAL: Final = 900

ATTRIBUTION: Final = "Data provided by Halo Collar"

FIRMWARE_IN_PROGRESS: Final = frozenset({"downloading", "verifying", "applying"})


def scan_interval_seconds(value: object) -> int:
    """Clamp a configured poll interval to the supported range."""
    try:
        seconds = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        seconds = DEFAULT_SCAN_INTERVAL
    return min(MAX_SCAN_INTERVAL, max(MIN_SCAN_INTERVAL, seconds))


def scan_interval(value: object) -> timedelta:
    """Return the poll interval as a timedelta."""
    return timedelta(seconds=scan_interval_seconds(value))
