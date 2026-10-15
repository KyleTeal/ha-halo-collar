"""The Halo Collar integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.client import HaloClient
from .api.models import TokenSet
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_INSTANCE_ID,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_TYPE,
)
from .coordinator import HaloCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.UPDATE,
]

type HaloConfigEntry = ConfigEntry[HaloCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HaloConfigEntry) -> bool:
    """Set up Halo Collar from a config entry."""
    session = async_get_clientsession(hass)

    async def _persist_tokens(tokens: TokenSet) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: tokens.access_token,
                CONF_REFRESH_TOKEN: tokens.refresh_token,
                CONF_EXPIRES_AT: tokens.expires_at,
                CONF_TOKEN_TYPE: tokens.token_type,
            },
        )

    client = HaloClient(
        session,
        TokenSet(
            access_token=entry.data[CONF_ACCESS_TOKEN],
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
            expires_at=float(entry.data[CONF_EXPIRES_AT]),
            token_type=entry.data.get(CONF_TOKEN_TYPE, "Bearer"),
        ),
        app_instance_id=entry.data[CONF_APP_INSTANCE_ID],
        timezone_name=hass.config.time_zone or "America/Chicago",
        on_tokens_updated=_persist_tokens,
    )
    coordinator = HaloCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HaloConfigEntry) -> bool:
    """Unload a Halo Collar config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
