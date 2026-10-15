"""Read-only firmware update status for a Halo collar."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import FIRMWARE_IN_PROGRESS
from .coordinator import HaloCoordinator
from .entity import HaloPetEntity, async_setup_pets

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: object,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a firmware entity for each pet."""
    coordinator: HaloCoordinator = entry.runtime_data  # type: ignore[attr-defined]
    async_setup_pets(coordinator, async_add_entities, _updates)


def _updates(coordinator: HaloCoordinator, pet_id: str) -> list[HaloFirmwareUpdate]:
    return [HaloFirmwareUpdate(coordinator, pet_id)]


class HaloFirmwareUpdate(HaloPetEntity, UpdateEntity):
    """Installed and pending collar firmware. Installation stays in the Halo app."""

    _attr_translation_key = "firmware"
    _attr_supported_features = 0

    def __init__(self, coordinator: HaloCoordinator, pet_id: str) -> None:
        """Initialize the firmware entity."""
        super().__init__(coordinator, pet_id)
        self._attr_unique_id = f"{pet_id}_firmware"

    @property
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        pet = self.pet
        if pet is None or pet.collar is None:
            return None
        return pet.collar.firmware_version

    @property
    def latest_version(self) -> str | None:
        """Return the server target version, or the installed version when there is none."""
        pet = self.pet
        if pet is None or pet.collar is None:
            return None
        return pet.collar.firmware_target_version or pet.collar.firmware_version

    @property
    def in_progress(self) -> bool:
        """Return whether Halo reports an active download, verify, or apply."""
        pet = self.pet
        if pet is None or pet.collar is None or pet.collar.firmware_update_status is None:
            return False
        return pet.collar.firmware_update_status.casefold() in FIRMWARE_IN_PROGRESS
