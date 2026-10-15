"""Diagnostics that omit account secrets and precise locations."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_INSTANCE_ID,
    CONF_EMAIL,
    CONF_REFRESH_TOKEN,
)
from .coordinator import HaloCoordinator

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_EMAIL,
    CONF_APP_INSTANCE_ID,
    "title",
    "latitude",
    "longitude",
    "accuracy",
    "serial_number",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: object,
) -> dict[str, Any]:
    """Return redacted account and pet state."""
    coordinator: HaloCoordinator = entry.runtime_data  # type: ignore[attr-defined]
    snapshot = coordinator.data
    pets: list[dict[str, Any]] = []
    if snapshot is not None:
        for pet in snapshot.pets:
            collar = pet.collar
            telemetry = pet.telemetry
            pets.append(
                {
                    "id": pet.id,
                    "name": pet.name,
                    "breed": pet.breed,
                    "has_collar": pet.has_collar,
                    "serial_number": collar.serial_number if collar is not None else None,
                    "collar_type": collar.collar_type if collar is not None else None,
                    "firmware_version": collar.firmware_version if collar is not None else None,
                    "firmware_target_version": (
                        collar.firmware_target_version if collar is not None else None
                    ),
                    "firmware_update_status": (
                        collar.firmware_update_status if collar is not None else None
                    ),
                    "online": telemetry.online if telemetry is not None else None,
                    "connection": telemetry.connection if telemetry is not None else None,
                    "battery_percent": telemetry.battery_percent if telemetry is not None else None,
                    "latitude": telemetry.latitude if telemetry is not None else None,
                    "longitude": telemetry.longitude if telemetry is not None else None,
                    "accuracy": telemetry.accuracy if telemetry is not None else None,
                    "geofence": snapshot.geofence_name(pet),
                    "fences_on": telemetry.fences_on if telemetry is not None else pet.fences_on,
                    "beacons_on": telemetry.beacons_on if telemetry is not None else pet.beacons_on,
                    "walk_active": telemetry.walk_active if telemetry is not None else None,
                    "fences_synchronized": pet.fences_synchronized,
                    "recent_correction_count": pet.recent_correction_count,
                }
            )
    return async_redact_data(
        {
            "config_entry": {
                "title": entry.title,  # type: ignore[attr-defined]
                "data": dict(entry.data),  # type: ignore[attr-defined]
                "options": dict(entry.options),  # type: ignore[attr-defined]
            },
            "pets": pets,
        },
        TO_REDACT,
    )
