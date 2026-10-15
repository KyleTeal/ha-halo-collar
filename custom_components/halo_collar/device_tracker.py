"""Location tracking for a Halo pet."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HaloCoordinator
from .entity import HaloPetEntity, async_setup_pets

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: object,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a device tracker for each pet."""
    coordinator: HaloCoordinator = entry.runtime_data  # type: ignore[attr-defined]
    async_setup_pets(coordinator, async_add_entities, _trackers)


def _trackers(coordinator: HaloCoordinator, pet_id: str) -> list[HaloPetTracker]:
    return [HaloPetTracker(coordinator, pet_id)]


class HaloPetTracker(HaloPetEntity, TrackerEntity):
    """GPS position reported by the collar."""

    _attr_name = None
    _attr_translation_key = "location"

    def __init__(self, coordinator: HaloCoordinator, pet_id: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, pet_id)
        self._attr_unique_id = f"{pet_id}_location"

    @property
    def available(self) -> bool:
        """Return whether the collar has a fix."""
        pet = self.pet
        return (
            super().available
            and pet is not None
            and pet.telemetry is not None
            and pet.telemetry.latitude is not None
            and pet.telemetry.longitude is not None
        )

    @property
    def latitude(self) -> float | None:
        """Return the latitude."""
        pet = self.pet
        if pet is None or pet.telemetry is None:
            return None
        return pet.telemetry.latitude

    @property
    def longitude(self) -> float | None:
        """Return the longitude."""
        pet = self.pet
        if pet is None or pet.telemetry is None:
            return None
        return pet.telemetry.longitude

    @property
    def location_accuracy(self) -> int:
        """Return the accuracy in meters."""
        pet = self.pet
        if pet is None or pet.telemetry is None or pet.telemetry.accuracy is None:
            return 0
        return int(pet.telemetry.accuracy)

    @property
    def source_type(self) -> SourceType:
        """Return GPS as the source."""
        return SourceType.GPS

    @property
    def icon(self) -> str:
        """Return the dog icon."""
        return "mdi:dog"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the fence and connection alongside the position."""
        pet = self.pet
        if pet is None or pet.telemetry is None or self.coordinator.data is None:
            return {}
        attributes: dict[str, str] = {"connection": pet.telemetry.connection}
        fence = self.coordinator.data.geofence_name(pet)
        if fence is not None:
            attributes["geofence"] = fence
        return attributes
