"""Home Assistant fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

from custom_components.halo_collar.const import (  # noqa: E402
    CONF_ACCESS_TOKEN,
    CONF_APP_INSTANCE_ID,
    CONF_EMAIL,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TELEMETRY,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_TYPE,
    CONF_USER_ID,
    DOMAIN,
)
from tests.payloads import account_map  # noqa: E402


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading the custom integration from this repository."""
    yield


def entry_data(*, expired: bool = False) -> dict:
    """Return config entry data with a fresh or expired access token."""
    delta = timedelta(minutes=-5 if expired else 30)
    return {
        CONF_EMAIL: "owner@example.com",
        CONF_ACCESS_TOKEN: "old-access",
        CONF_REFRESH_TOKEN: "old-refresh",
        CONF_EXPIRES_AT: (datetime.now(timezone.utc) + delta).timestamp(),
        CONF_TOKEN_TYPE: "Bearer",
        CONF_APP_INSTANCE_ID: "instance-1",
        CONF_USER_ID: "user-1",
    }


def entry_options() -> dict:
    """Return default poll options."""
    return {CONF_SCAN_INTERVAL: 120, CONF_REFRESH_TELEMETRY: False}


def mock_account_reads(aioclient_mock) -> None:
    """Register the two GET polls."""
    aioclient_mock.get(
        "https://api.halocollar.com/account/my/map",
        json=account_map(),
    )
    aioclient_mock.get(
        "https://api.halocollar.com/collar/my",
        json=__import__("tests.payloads", fromlist=["COLLARS"]).COLLARS,
    )


__all__ = ["DOMAIN"]
