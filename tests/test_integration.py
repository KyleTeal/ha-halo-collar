"""Integration setup, entities, and diagnostics."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.halo_collar.const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, DOMAIN
from custom_components.halo_collar.diagnostics import async_get_config_entry_diagnostics
from homeassistant.components.diagnostics import REDACTED
from homeassistant.helpers import entity_registry as er
from tests.conftest import entry_data, entry_options
from tests.payloads import COLLARS, TOKEN, account_map

MAP_URL = "https://api.halocollar.com/account/my/map"
COLLAR_URL = "https://api.halocollar.com/collar/my"
TOKEN_URL = "https://auth.halocollar.com/connect/token"


def _mock_reads(aioclient_mock) -> None:
    aioclient_mock.get(MAP_URL, json=account_map())
    aioclient_mock.get(COLLAR_URL, json=COLLARS)


async def _setup(hass, aioclient_mock, *, expired: bool = False) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-1",
        title="owner@example.com",
        data=entry_data(expired=expired),
        options=entry_options(),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entity_id(hass, domain: str, unique_id: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_entities_reflect_the_account(hass, aioclient_mock) -> None:
    """Pets become devices, and a collarless pet is unavailable."""
    _mock_reads(aioclient_mock)
    await _setup(hass, aioclient_mock)

    battery = hass.states.get(_entity_id(hass, "sensor", "pet-1_battery"))
    assert battery is not None
    assert battery.state == "80"

    connection = hass.states.get(_entity_id(hass, "sensor", "pet-1_connection"))
    assert connection is not None
    assert connection.state == "wifi"

    geofence = hass.states.get(_entity_id(hass, "sensor", "pet-1_geofence"))
    assert geofence is not None
    assert geofence.state == "Home"

    online = hass.states.get(_entity_id(hass, "binary_sensor", "pet-1_online"))
    assert online is not None
    assert online.state == "on"

    fences = hass.states.get(_entity_id(hass, "binary_sensor", "pet-1_fences"))
    assert fences is not None
    assert fences.state == "on"

    walk = hass.states.get(_entity_id(hass, "binary_sensor", "pet-1_walk"))
    assert walk is not None
    assert walk.state == "on"
    assert walk.attributes["paused"] is False

    corrections = hass.states.get(_entity_id(hass, "sensor", "pet-1_recent_corrections"))
    assert corrections is not None
    assert corrections.state == "1"

    firmware = hass.states.get(_entity_id(hass, "update", "pet-1_firmware"))
    assert firmware is not None
    assert firmware.attributes["installed_version"] == "03.08.00"
    assert firmware.attributes["latest_version"] == "03.09.00"
    assert firmware.attributes["in_progress"] is True

    tracker = hass.states.get(_entity_id(hass, "device_tracker", "pet-1_location"))
    assert tracker is not None
    assert tracker.attributes["latitude"] == 44.0
    assert tracker.attributes["longitude"] == -92.4
    assert tracker.attributes["geofence"] == "Home"

    ghost = hass.states.get(_entity_id(hass, "sensor", "pet-2_battery"))
    assert ghost is not None
    assert ghost.state == "unavailable"

    methods = [call[0] for call in aioclient_mock.mock_calls]
    assert "post" not in methods
    assert "put" not in methods


async def test_expired_token_is_refreshed_and_saved(hass, aioclient_mock) -> None:
    """Setup refreshes an expired token and writes the new tokens to the entry."""
    aioclient_mock.post(TOKEN_URL, json=TOKEN)
    _mock_reads(aioclient_mock)
    entry = await _setup(hass, aioclient_mock, expired=True)

    assert entry.data[CONF_ACCESS_TOKEN] == "access-token"
    assert entry.data[CONF_REFRESH_TOKEN] == "refresh-token"
    assert hass.states.get(_entity_id(hass, "sensor", "pet-1_battery")).state == "80"


async def test_diagnostics_redact_secrets_and_location(hass, aioclient_mock) -> None:
    """Diagnostics hide tokens, the serial, and coordinates."""
    _mock_reads(aioclient_mock)
    entry = await _setup(hass, aioclient_mock)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["config_entry"]["title"] == REDACTED
    assert result["config_entry"]["data"][CONF_ACCESS_TOKEN] == REDACTED
    assert result["config_entry"]["data"][CONF_REFRESH_TOKEN] == REDACTED
    assert result["config_entry"]["data"]["email"] == REDACTED
    scout = next(pet for pet in result["pets"] if pet["id"] == "pet-1")
    assert scout["latitude"] == REDACTED
    assert scout["longitude"] == REDACTED
    assert scout["serial_number"] == REDACTED
    assert scout["name"] == "Scout"
    assert scout["battery_percent"] == 80
    dumped = str(result)
    assert "old-access" not in dumped
    assert "old-refresh" not in dumped
    assert "SN-1" not in dumped
    assert "secret" not in dumped
