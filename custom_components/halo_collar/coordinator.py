"""Polling coordinator for a Halo account."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.client import HaloClient
from .api.exceptions import HaloAuthError, HaloError
from .api.models import AccountSnapshot
from .const import CONF_REFRESH_TELEMETRY, CONF_SCAN_INTERVAL, scan_interval

if TYPE_CHECKING:
    from . import HaloConfigEntry

_LOGGER = logging.getLogger(__name__)


class HaloCoordinator(DataUpdateCoordinator[AccountSnapshot]):
    """Poll Halo for every pet on one account."""

    config_entry: HaloConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HaloConfigEntry,
        client: HaloClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Halo Collar",
            config_entry=entry,
            update_interval=scan_interval(entry.options.get(CONF_SCAN_INTERVAL)),
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> AccountSnapshot:
        """Fetch pets, collars, and locations."""
        try:
            return await self.client.async_account_snapshot(
                refresh_telemetry=bool(self.config_entry.options.get(CONF_REFRESH_TELEMETRY, False))
            )
        except HaloAuthError as err:
            _LOGGER.error("Halo rejected the saved login: %s", err)
            raise ConfigEntryAuthFailed("Halo login expired. Sign in again.") from err
        except HaloError as err:
            _LOGGER.error("Halo poll failed: %s", err)
            raise UpdateFailed(str(err)) from err
