"""Binary sensors for a Halo pet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import AccountSnapshot, Pet
from .coordinator import HaloCoordinator
from .entity import HaloPetEntity, async_setup_pets

PARALLEL_UPDATES = 0

IsOnFn = Callable[[AccountSnapshot, Pet], bool | None]
AttributesFn = Callable[[AccountSnapshot, Pet], dict[str, bool | None]]


@dataclass(frozen=True, kw_only=True)
class HaloBinaryDescription(BinarySensorEntityDescription):
    """A binary sensor mapped from a pet snapshot."""

    is_on_fn: IsOnFn
    attributes_fn: AttributesFn | None = None


def _flag(telemetry_value: bool | None, fallback: bool | None) -> bool | None:
    if telemetry_value is not None:
        return telemetry_value
    return fallback


def _online(_snapshot: AccountSnapshot, pet: Pet) -> bool | None:
    if pet.telemetry is None:
        return None
    return pet.telemetry.online


def _fences(_snapshot: AccountSnapshot, pet: Pet) -> bool | None:
    telemetry = pet.telemetry.fences_on if pet.telemetry is not None else None
    return _flag(telemetry, pet.fences_on)


def _beacons(_snapshot: AccountSnapshot, pet: Pet) -> bool | None:
    telemetry = pet.telemetry.beacons_on if pet.telemetry is not None else None
    return _flag(telemetry, pet.beacons_on)


def _walk(_snapshot: AccountSnapshot, pet: Pet) -> bool | None:
    if pet.telemetry is None:
        return None
    return pet.telemetry.walk_active


def _walk_attributes(_snapshot: AccountSnapshot, pet: Pet) -> dict[str, bool | None]:
    if pet.telemetry is None or not pet.telemetry.walk_active:
        return {}
    return {"paused": pet.telemetry.walk_paused}


def _fences_synchronized(_snapshot: AccountSnapshot, pet: Pet) -> bool | None:
    return pet.fences_synchronized


def _firmware_update(_snapshot: AccountSnapshot, pet: Pet) -> bool | None:
    if pet.collar is None:
        return None
    if pet.collar.firmware_update_available is not None:
        return pet.collar.firmware_update_available
    installed = pet.collar.firmware_version
    target = pet.collar.firmware_target_version
    if installed is None or target is None:
        return None
    return installed != target


BINARY_SENSORS: tuple[HaloBinaryDescription, ...] = (
    HaloBinaryDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_online,
    ),
    HaloBinaryDescription(
        key="fences",
        translation_key="fences",
        is_on_fn=_fences,
    ),
    HaloBinaryDescription(
        key="beacons",
        translation_key="beacons",
        is_on_fn=_beacons,
    ),
    HaloBinaryDescription(
        key="walk",
        translation_key="walk",
        is_on_fn=_walk,
        attributes_fn=_walk_attributes,
    ),
    HaloBinaryDescription(
        key="fences_synchronized",
        translation_key="fences_synchronized",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_fences_synchronized,
    ),
    HaloBinaryDescription(
        key="firmware_update_available",
        translation_key="firmware_update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_firmware_update,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: object,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for each pet."""
    coordinator: HaloCoordinator = entry.runtime_data  # type: ignore[attr-defined]
    async_setup_pets(coordinator, async_add_entities, _binary_sensors)


def _binary_sensors(coordinator: HaloCoordinator, pet_id: str) -> list[HaloBinarySensor]:
    return [HaloBinarySensor(coordinator, pet_id, description) for description in BINARY_SENSORS]


class HaloBinarySensor(HaloPetEntity, BinarySensorEntity):
    """One binary sensor on a pet device."""

    entity_description: HaloBinaryDescription

    def __init__(
        self,
        coordinator: HaloCoordinator,
        pet_id: str,
        description: HaloBinaryDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, pet_id)
        self.entity_description = description
        self._attr_unique_id = f"{pet_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the binary state."""
        pet = self.pet
        if pet is None or self.coordinator.data is None:
            return None
        return self.entity_description.is_on_fn(self.coordinator.data, pet)

    @property
    def extra_state_attributes(self) -> dict[str, bool | None]:
        """Return extra attributes for this binary sensor."""
        attributes_fn = self.entity_description.attributes_fn
        pet = self.pet
        if attributes_fn is None or pet is None or self.coordinator.data is None:
            return {}
        return attributes_fn(self.coordinator.data, pet)
