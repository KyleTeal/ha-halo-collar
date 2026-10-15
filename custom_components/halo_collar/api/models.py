"""Parsed Halo account state.

Only the fields this integration shows are kept. Wi-Fi credentials, signed
report URLs, and other unused payload members are dropped here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .exceptions import HaloApiError

_CONNECTED = "socketconnected"
_TIME_KEYS = (
    "timestamp",
    "updatedAt",
    "receivedAt",
    "lastSeen",
    "telemetryTime",
    "dateTime",
    "recordedAt",
    "time",
    "lastTelemetryAt",
    "telemetryUpdatedAt",
)
_CORRECTION_TIME_KEYS = (
    "occurredAt",
    "createdAt",
    "timestamp",
    "dateTime",
    "appliedAt",
    "correctionDate",
    "date",
)
_CORRECTION_WINDOW = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class TokenSet:
    """OAuth tokens and the local expiry, already reduced by a small slack."""

    access_token: str
    refresh_token: str
    expires_at: float
    token_type: str = "Bearer"
    scope: str = ""

    @property
    def is_expired(self) -> bool:
        """Return whether the access token should be refreshed."""
        return self.expires_at <= datetime.now(timezone.utc).timestamp()


@dataclass(frozen=True, slots=True)
class UserProfile:
    """The account identity used as the config entry unique id."""

    user_id: str
    email: str | None
    first_name: str | None
    last_name: str | None


@dataclass(frozen=True, slots=True)
class Telemetry:
    """Last collar-reported state merged from the map and the collar list."""

    latitude: float | None
    longitude: float | None
    accuracy: float | None
    battery_percent: int | None
    wifi_status: str | None
    cellular_status: str | None
    fences_on: bool | None
    beacons_on: bool | None
    geofence_id: str | None
    geofence_name: str | None
    walk_active: bool
    walk_paused: bool | None
    recorded_at: datetime | None

    @property
    def online(self) -> bool:
        """Return whether Wi-Fi or cellular reports a socket connection."""
        return _is_connected(self.wifi_status) or _is_connected(self.cellular_status)

    @property
    def connection(self) -> str:
        """Return wifi, cellular, or offline."""
        if _is_connected(self.wifi_status):
            return "wifi"
        if _is_connected(self.cellular_status):
            return "cellular"
        return "offline"


@dataclass(frozen=True, slots=True)
class Collar:
    """Account collar identity and read-only firmware state."""

    id: str
    serial_number: str | None
    collar_type: str | None
    configuration_sync_status: str | None
    firmware_version: str | None
    firmware_target_version: str | None
    firmware_update_status: str | None
    firmware_update_available: bool | None


@dataclass(frozen=True, slots=True)
class GeoFence:
    """A fence name used to label the collar's current fence id."""

    id: str
    name: str | None
    enabled: bool | None


@dataclass(frozen=True, slots=True)
class Pet:
    """One pet and the collar currently assigned to it."""

    id: str
    name: str | None
    breed: str | None
    collar: Collar | None
    telemetry: Telemetry | None
    fences_on: bool | None
    beacons_on: bool | None
    fences_synchronized: bool | None
    current_geofence_id: str | None
    recent_correction_count: int | None

    @property
    def has_collar(self) -> bool:
        """Return whether Halo currently assigns a collar to this pet."""
        return self.collar is not None


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """One poll of the account map and collar list."""

    pets: tuple[Pet, ...]
    fences: tuple[GeoFence, ...]

    def pet(self, pet_id: str) -> Pet | None:
        """Return the pet with this id, if it is still on the account."""
        for pet in self.pets:
            if pet.id == pet_id:
                return pet
        return None

    def geofence_name(self, pet: Pet) -> str | None:
        """Return the current fence name from telemetry or the fence list."""
        if pet.telemetry and pet.telemetry.geofence_name:
            return pet.telemetry.geofence_name
        fence_id = pet.current_geofence_id
        if pet.telemetry and pet.telemetry.geofence_id:
            fence_id = pet.telemetry.geofence_id
        if fence_id is None:
            return None
        for fence in self.fences:
            if fence.id == fence_id:
                return fence.name
        return None


def parse_user_profile(payload: Any) -> UserProfile:
    """Parse `/user-profile`."""
    if not isinstance(payload, dict):
        raise HaloApiError("Halo returned an unexpected account profile.")
    user_id = _identifier(payload.get("userId")) or _identifier(payload.get("id"))
    if user_id is None:
        raise HaloApiError("Halo did not return an account id.")
    email = payload.get("email")
    if not isinstance(email, str) or not email.strip():
        email = payload.get("currentEmail")
    return UserProfile(
        user_id=user_id,
        email=email.strip() if isinstance(email, str) and email.strip() else None,
        first_name=_text(payload.get("firstName")),
        last_name=_text(payload.get("lastName")),
    )


def parse_account_snapshot(account_map: Any, collars: Any) -> AccountSnapshot:
    """Parse `/account/my/map` and `/collar/my` into one snapshot."""
    if not isinstance(account_map, dict):
        raise HaloApiError("Halo returned an unexpected account map.")
    if not isinstance(collars, list):
        raise HaloApiError("Halo returned an unexpected collar list.")

    parsed_collars = [_parse_collar(item) for item in collars]
    by_id = {collar.id: collar for collar in parsed_collars if collar is not None}
    by_pet: dict[str, Collar] = {}
    raw_by_id: dict[str, dict[str, Any]] = {}
    for item in collars:
        if not isinstance(item, dict):
            continue
        collar_id = _identifier(item.get("id"))
        if collar_id is None:
            continue
        raw_by_id[collar_id] = item
        pet_info = item.get("petInfo")
        pet_id = _identifier(pet_info.get("id")) if isinstance(pet_info, dict) else None
        collar = by_id.get(collar_id)
        if pet_id is not None and collar is not None:
            by_pet[pet_id] = collar

    fences = _parse_fences(account_map.get("geoFencesInfo"))
    counts = _correction_counts(account_map.get("corrections"))
    pets_payload = account_map.get("pets")
    if pets_payload is None:
        pets_payload = []
    if not isinstance(pets_payload, list):
        raise HaloApiError("Halo returned an unexpected pet list.")

    pets: list[Pet] = []
    for item in pets_payload:
        pet = _parse_pet(item, by_id, by_pet, raw_by_id, counts)
        if pet is not None:
            pets.append(pet)
    pets.sort(key=lambda pet: pet.id)
    return AccountSnapshot(pets=tuple(pets), fences=fences)


def _parse_pet(
    payload: Any,
    by_id: dict[str, Collar],
    by_pet: dict[str, Collar],
    raw_by_id: dict[str, dict[str, Any]],
    counts: dict[str, int] | None,
) -> Pet | None:
    if not isinstance(payload, dict):
        return None
    pet_id = _identifier(payload.get("id"))
    if pet_id is None:
        return None
    collar_info = payload.get("collarInfo")
    if not isinstance(collar_info, dict):
        collar_info = payload.get("collar") if isinstance(payload.get("collar"), dict) else None
    collar_id = _identifier(collar_info.get("id")) if isinstance(collar_info, dict) else None
    collar = by_id.get(collar_id) if collar_id is not None else None
    if collar is None:
        collar = by_pet.get(pet_id)
        if collar is not None:
            collar_id = collar.id
    if collar is None and collar_id is not None:
        collar = Collar(
            id=collar_id,
            serial_number=_text(collar_info.get("serialNumber"))
            if isinstance(collar_info, dict)
            else None,
            collar_type=_text(collar_info.get("type")) if isinstance(collar_info, dict) else None,
            configuration_sync_status=None,
            firmware_version=None,
            firmware_target_version=None,
            firmware_update_status=None,
            firmware_update_available=None,
        )

    collar_raw = raw_by_id.get(collar.id) if collar is not None else None
    merged = _overlay(
        collar_raw.get("telemetry") if isinstance(collar_raw, dict) else None,
        payload.get("telemetry"),
    )
    telemetry = _parse_telemetry(
        merged,
        extra_time=_first_time(payload, "lastTelemetryAt", "telemetryUpdatedAt", "updatedAt"),
    )
    return Pet(
        id=pet_id,
        name=_text(payload.get("name")),
        breed=_text(payload.get("breed")),
        collar=collar,
        telemetry=telemetry,
        fences_on=_fallback_flag(payload, "fencesState", "fencesOn"),
        beacons_on=_fallback_flag(payload, "beaconsState", "beaconsOn"),
        fences_synchronized=_as_bool(payload.get("isFencesSynchronized")),
        current_geofence_id=_identifier(payload.get("currentGeoFenceId")),
        recent_correction_count=None if counts is None else counts.get(pet_id, 0),
    )


def _parse_collar(payload: Any) -> Collar | None:
    if not isinstance(payload, dict):
        return None
    collar_id = _identifier(payload.get("id"))
    if collar_id is None:
        return None
    firmware = payload.get("firmware") if isinstance(payload.get("firmware"), dict) else None
    update = payload.get("firmwareUpdate") if isinstance(payload.get("firmwareUpdate"), dict) else None
    target = update.get("firmware") if isinstance(update, dict) else None
    details = update.get("update") if isinstance(update, dict) else None
    status = details.get("status") if isinstance(details, dict) else None
    return Collar(
        id=collar_id,
        serial_number=_text(payload.get("serialNumber")),
        collar_type=_text(payload.get("type")),
        configuration_sync_status=_text(payload.get("configurationSyncStatus")),
        firmware_version=_firmware_version(firmware),
        firmware_target_version=_firmware_version(target if isinstance(target, dict) else None),
        firmware_update_status=_text(status),
        firmware_update_available=_as_bool(payload.get("hasFirmwareUpdatesAvailable")),
    )


def _parse_fences(info: Any) -> tuple[GeoFence, ...]:
    if not isinstance(info, dict):
        return ()
    raw_fences = info.get("geoFencesToDisplay")
    if not isinstance(raw_fences, list):
        return ()
    fences: list[GeoFence] = []
    for item in raw_fences:
        if not isinstance(item, dict):
            continue
        fence_id = _identifier(item.get("id"))
        if fence_id is None:
            continue
        fences.append(
            GeoFence(
                id=fence_id,
                name=_text(item.get("name")),
                enabled=_as_bool(item.get("isEnabled")),
            )
        )
    fences.sort(key=lambda fence: fence.id)
    return tuple(fences)


def _correction_counts(payload: Any) -> dict[str, int] | None:
    if not isinstance(payload, list) or not payload:
        return {}
    parsed: list[tuple[str | None, datetime | None]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        pet = item.get("pet")
        pet_id = _identifier(item.get("petId"))
        if pet_id is None and isinstance(pet, dict):
            pet_id = _identifier(pet.get("id"))
        parsed.append((pet_id, _first_time(item, *_CORRECTION_TIME_KEYS)))
    if not any(pet_id is not None for pet_id, _occurred in parsed):
        return None
    now = datetime.now(timezone.utc)
    counts: dict[str, int] = {}
    for pet_id, occurred_at in parsed:
        if pet_id is None:
            continue
        if occurred_at is not None and now - occurred_at > _CORRECTION_WINDOW:
            continue
        counts[pet_id] = counts.get(pet_id, 0) + 1
    return counts


def _parse_telemetry(payload: dict[str, Any] | None, *, extra_time: datetime | None) -> Telemetry | None:
    if not payload:
        return None
    latitude, longitude, accuracy = _coordinates(payload)
    wifi = payload.get("wiFi") if isinstance(payload.get("wiFi"), dict) else None
    if wifi is None and isinstance(payload.get("wifi"), dict):
        wifi = payload.get("wifi")
    cellular = payload.get("cellular") if isinstance(payload.get("cellular"), dict) else None
    mode = payload.get("mode") if isinstance(payload.get("mode"), dict) else None
    fence = payload.get("geoFence") if isinstance(payload.get("geoFence"), dict) else None
    walk = payload.get("walk") if isinstance(payload.get("walk"), dict) else None
    return Telemetry(
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        battery_percent=_battery(payload),
        wifi_status=_text(wifi.get("status")) if isinstance(wifi, dict) else None,
        cellular_status=_text(cellular.get("status")) if isinstance(cellular, dict) else None,
        fences_on=_as_bool(mode.get("fencesOn")) if isinstance(mode, dict) else None,
        beacons_on=_as_bool(mode.get("beaconsOn")) if isinstance(mode, dict) else None,
        geofence_id=_identifier(fence.get("id")) if isinstance(fence, dict) else None,
        geofence_name=_text(fence.get("name")) if isinstance(fence, dict) else None,
        walk_active=walk is not None,
        walk_paused=_as_bool(walk.get("isPaused")) if isinstance(walk, dict) else None,
        recorded_at=_first_time(payload, *_TIME_KEYS) or extra_time,
    )


def _overlay(base: Any, extra: Any) -> dict[str, Any] | None:
    if not isinstance(base, dict) and not isinstance(extra, dict):
        return None
    merged: dict[str, Any] = dict(base) if isinstance(base, dict) else {}
    if isinstance(extra, dict):
        for key, value in extra.items():
            current = merged.get(key)
            if isinstance(value, dict) and isinstance(current, dict):
                merged[key] = {**current, **value}
            else:
                merged[key] = value
    return merged


def _coordinates(payload: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    latitude = _degrees(payload.get("latitude"), 90.0)
    longitude = _degrees(payload.get("longitude"), 180.0)
    accuracy = _first_float(
        payload,
        "accuracy",
        "horizontalAccuracy",
        "gpsAccuracy",
        "locationAccuracy",
    )
    if latitude is None or longitude is None:
        for key in ("location", "gps", "position", "coordinate"):
            nested = payload.get(key)
            if not isinstance(nested, dict):
                continue
            if latitude is None:
                latitude = _degrees(nested.get("latitude"), 90.0)
            if longitude is None:
                longitude = _degrees(nested.get("longitude"), 180.0)
            if accuracy is None:
                accuracy = _first_float(
                    nested,
                    "accuracy",
                    "horizontalAccuracy",
                    "gpsAccuracy",
                    "locationAccuracy",
                )
    if latitude is None or longitude is None:
        return None, None, None
    return latitude, longitude, accuracy


def _battery(payload: dict[str, Any]) -> int | None:
    percent = _percent(payload.get("batteryChargePercent"))
    if percent is not None:
        return percent
    battery = payload.get("battery")
    if not isinstance(battery, dict):
        return None
    for key in ("chargePercent", "percent", "percentage"):
        percent = _percent(battery.get(key))
        if percent is not None:
            return percent
    return None


def _fallback_flag(payload: dict[str, Any], state_key: str, mode_key: str) -> bool | None:
    flag = _as_bool(payload.get(state_key))
    if flag is not None:
        return flag
    desired = payload.get("desiredMode")
    if isinstance(desired, dict):
        return _as_bool(desired.get(mode_key))
    return None


def _firmware_version(firmware: dict[str, Any] | None) -> str | None:
    if not isinstance(firmware, dict):
        return None
    for key in ("formattedVersion", "version"):
        value = _text(firmware.get(key))
        if value is not None:
            return value
    return None


def _first_time(payload: dict[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        parsed = _parse_time(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _first_float(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _as_float(payload.get(key))
        if value is not None and value >= 0:
            return value
    return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_connected(status: str | None) -> bool:
    return isinstance(status, str) and status.casefold() == _CONNECTED


def _identifier(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "on", "enabled", "yes", "1"}:
            return True
        if normalized in {"false", "off", "disabled", "no", "0"}:
            return False
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number != number:
            return None
        return number
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        if number != number:
            return None
        return number
    return None


def _degrees(value: Any, limit: float) -> float | None:
    number = _as_float(value)
    if number is None or abs(number) > limit:
        return None
    return number


def _percent(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    else:
        return None
    if 0 <= number <= 100:
        return number
    return None
