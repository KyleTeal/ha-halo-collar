"""Shared pet device entity."""

from __future__ import annotations

from collections.abc import Callable
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import Pet
from .const import ATTRIBUTION, DOMAIN
from .coordinator import HaloCoordinator


class HaloPetEntity(CoordinatorEntity[HaloCoordinator]):
    """A Halo pet device."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: HaloCoordinator, pet_id: str) -> None:
        """Initialize the entity for one pet id."""
        super().__init__(coordinator)
        self._pet_id = pet_id

    @property
    def pet(self) -> Pet | None:
        """Return the current pet snapshot."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.pet(self._pet_id)

    @property
    def available(self) -> bool:
        """Return whether this pet still has a collar."""
        pet = self.pet
        return super().available and pet is not None and pet.has_collar

    @property
    def device_info(self) -> DeviceInfo:
        """Return the pet device."""
        pet = self.pet
        collar = pet.collar if pet is not None else None
        name = pet.name if pet is not None and pet.name else "Halo pet"
        return DeviceInfo(
            identifiers={(DOMAIN, self._pet_id)},
            name=name,
            manufacturer="Halo",
            model=collar.collar_type if collar is not None else None,
            serial_number=collar.serial_number if collar is not None else None,
            sw_version=collar.firmware_version if collar is not None else None,
        )


def async_setup_pets(
    coordinator: HaloCoordinator,
    async_add_entities: AddEntitiesCallback,
    factory: Callable[[HaloCoordinator, str], list[Entity]],
) -> None:
    """Add entities for current and future pets."""
    added: set[str] = set()

    @callback
    def _add_pets() -> None:
        snapshot = coordinator.data
        if snapshot is None:
            return
        fresh: list[Entity] = []
        for pet in snapshot.pets:
            if pet.id in added:
                continue
            added.add(pet.id)
            fresh.extend(factory(coordinator, pet.id))
        if fresh:
            async_add_entities(fresh)

    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(_add_pets))
    _add_pets()
