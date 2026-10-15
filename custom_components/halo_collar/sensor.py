"""Sensors for a Halo pet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import AccountSnapshot, Pet
from .coordinator import HaloCoordinator
from .entity import HaloPetEntity, async_setup_pets

PARALLEL_UPDATES = 0

ValueFn = Callable[[AccountSnapshot, Pet], datetime | int | str | None]
AvailableFn = Callable[[AccountSnapshot, Pet], bool]
AttributesFn = Callable[[AccountSnapshot, Pet], dict[str, str | None]]


@dataclass(frozen=True, kw_only=True)
class HaloSensorDescription(SensorEntityDescription):
    """A sensor mapped from a pet snapshot."""

    value_fn: ValueFn
    available_fn: AvailableFn = lambda _snapshot, _pet: True
    attributes_fn: AttributesFn | None = None


def _battery(_snapshot: AccountSnapshot, pet: Pet) -> int | None:
    if pet.telemetry is None:
        return None
    return pet.telemetry.battery_percent


def _has_battery(_snapshot: AccountSnapshot, pet: Pet) -> bool:
    return _battery(_snapshot, pet) is not None


def _connection(_snapshot: AccountSnapshot, pet: Pet) -> str | None:
    if pet.telemetry is None:
        return None
    return pet.telemetry.connection


def _connection_attributes(_snapshot: AccountSnapshot, pet: Pet) -> dict[str, str | None]:
    if pet.telemetry is None:
        return {}
    return {
        "wifi_status": pet.telemetry.wifi_status,
        "cellular_status": pet.telemetry.cellular_status,
    }


def _geofence(snapshot: AccountSnapshot, pet: Pet) -> str | None:
    return snapshot.geofence_name(pet)


def _geofence_attributes(snapshot: AccountSnapshot, pet: Pet) -> dict[str, str | None]:
    fence_id = pet.current_geofence_id
    if pet.telemetry is not None and pet.telemetry.geofence_id is not None:
        fence_id = pet.telemetry.geofence_id
    if fence_id is None:
        return {}
    return {"geofence_id": fence_id}


def _sync_status(_snapshot: AccountSnapshot, pet: Pet) -> str | None:
    if pet.collar is None:
        return None
    return pet.collar.configuration_sync_status


def _has_text(value_fn: ValueFn) -> AvailableFn:
    def _available(snapshot: AccountSnapshot, pet: Pet) -> bool:
        return value_fn(snapshot, pet) is not None

    return _available


def _recorded_at(_snapshot: AccountSnapshot, pet: Pet) -> datetime | None:
    if pet.telemetry is None:
        return None
    return pet.telemetry.recorded_at


def _firmware_status(_snapshot: AccountSnapshot, pet: Pet) -> str | None:
    if pet.collar is None:
        return None
    return pet.collar.firmware_update_status


def _corrections(_snapshot: AccountSnapshot, pet: Pet) -> int | None:
    return pet.recent_correction_count


SENSORS: tuple[HaloSensorDescription, ...] = (
    HaloSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery,
        available_fn=_has_battery,
    ),
    HaloSensorDescription(
        key="connection",
        translation_key="connection",
        device_class=SensorDeviceClass.ENUM,
        options=["wifi", "cellular", "offline"],
        value_fn=_connection,
        available_fn=_has_text(_connection),
        attributes_fn=_connection_attributes,
    ),
    HaloSensorDescription(
        key="geofence",
        translation_key="geofence",
        value_fn=_geofence,
        attributes_fn=_geofence_attributes,
    ),
    HaloSensorDescription(
        key="configuration_sync",
        translation_key="configuration_sync",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_sync_status,
        available_fn=_has_text(_sync_status),
    ),
    HaloSensorDescription(
        key="last_telemetry",
        translation_key="last_telemetry",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_recorded_at,
        available_fn=_has_text(_recorded_at),
    ),
    HaloSensorDescription(
        key="firmware_update_status",
        translation_key="firmware_update_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_firmware_status,
        available_fn=_has_text(_firmware_status),
    ),
    HaloSensorDescription(
        key="recent_corrections",
        translation_key="recent_corrections",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_corrections,
        available_fn=_has_text(_corrections),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: object,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for each pet."""
    coordinator: HaloCoordinator = entry.runtime_data  # type: ignore[attr-defined]
    async_setup_pets(coordinator, async_add_entities, _sensors)


def _sensors(coordinator: HaloCoordinator, pet_id: str) -> list[HaloSensor]:
    return [HaloSensor(coordinator, pet_id, description) for description in SENSORS]


class HaloSensor(HaloPetEntity, SensorEntity):
    """One sensor on a pet device."""

    entity_description: HaloSensorDescription

    def __init__(
        self,
        coordinator: HaloCoordinator,
        pet_id: str,
        description: HaloSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, pet_id)
        self.entity_description = description
        self._attr_unique_id = f"{pet_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return whether this sensor has a value."""
        pet = self.pet
        if not super().available or pet is None or self.coordinator.data is None:
            return False
        return self.entity_description.available_fn(self.coordinator.data, pet)

    @property
    def native_value(self) -> datetime | int | str | None:
        """Return the sensor value."""
        pet = self.pet
        if pet is None or self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data, pet)

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return extra attributes for this sensor."""
        attributes_fn = self.entity_description.attributes_fn
        pet = self.pet
        if attributes_fn is None or pet is None or self.coordinator.data is None:
            return {}
        return attributes_fn(self.coordinator.data, pet)
