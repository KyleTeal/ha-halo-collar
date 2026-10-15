"""Tests for account snapshot parsing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.halo_collar.api.exceptions import HaloApiError
from custom_components.halo_collar.api.models import parse_account_snapshot, parse_user_profile
from tests.payloads import COLLARS, PROFILE, account_map


def test_snapshot_prefers_pet_telemetry_and_counts_recent_corrections() -> None:
    """Pet telemetry wins over the collar list, and old corrections drop out."""
    snapshot = parse_account_snapshot(account_map(), COLLARS)

    scout = snapshot.pet("pet-1")
    assert scout is not None
    assert scout.name == "Scout"
    assert scout.has_collar is True
    assert scout.collar is not None
    assert scout.collar.firmware_version == "03.08.00"
    assert scout.collar.firmware_target_version == "03.09.00"
    assert scout.collar.firmware_update_status == "downloading"
    assert scout.collar.configuration_sync_status == "uptodate"
    assert scout.telemetry is not None
    assert scout.telemetry.battery_percent == 80
    assert scout.telemetry.connection == "wifi"
    assert scout.telemetry.online is True
    assert scout.telemetry.fences_on is True
    assert scout.telemetry.walk_active is True
    assert scout.telemetry.walk_paused is False
    assert snapshot.geofence_name(scout) == "Home"
    assert scout.recent_correction_count == 1
    assert scout.fences_synchronized is True

    ghost = snapshot.pet("pet-2")
    assert ghost is not None
    assert ghost.has_collar is False
    assert ghost.telemetry is None
    assert ghost.recent_correction_count == 0


def test_unattributed_corrections_are_not_given_to_every_pet() -> None:
    """Corrections with no pet id do not become a count on each pet."""
    payload = account_map()
    payload["corrections"] = [{"id": "correction-1"}]
    snapshot = parse_account_snapshot(payload, COLLARS)
    scout = snapshot.pet("pet-1")
    assert scout is not None
    assert scout.recent_correction_count is None


def test_out_of_range_battery_and_coordinates_are_dropped() -> None:
    """Impossible battery and coordinates are ignored."""
    payload = account_map()
    payload["pets"][0]["telemetry"]["batteryChargePercent"] = 140
    payload["pets"][0]["telemetry"]["latitude"] = 95
    snapshot = parse_account_snapshot(payload, COLLARS)
    scout = snapshot.pet("pet-1")
    assert scout is not None
    assert scout.telemetry is not None
    assert scout.telemetry.battery_percent is None
    assert scout.telemetry.latitude is None
    assert scout.telemetry.longitude is None


def test_future_correction_outside_window_is_excluded() -> None:
    """A correction older than a day is not counted."""
    now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    payload = account_map(now)
    payload["corrections"] = [
        {
            "id": "old",
            "petId": "pet-1",
            "occurredAt": (now - timedelta(days=3)).isoformat().replace("+00:00", "Z"),
        }
    ]
    snapshot = parse_account_snapshot(payload, COLLARS)
    scout = snapshot.pet("pet-1")
    assert scout is not None
    assert scout.recent_correction_count == 0


def test_profile_requires_an_account_id() -> None:
    """A profile without an id cannot become a config entry."""
    with pytest.raises(HaloApiError):
        parse_user_profile({"firstName": "Taylor"})


def test_profile_uses_user_id() -> None:
    """The profile unique id prefers userId."""
    profile = parse_user_profile(PROFILE)
    assert profile.user_id == "user-1"
    assert profile.email == "owner@example.com"
