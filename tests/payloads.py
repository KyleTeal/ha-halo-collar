"""Shared Halo payloads for tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

TOKEN = {
    "access_token": "access-token",
    "refresh_token": "refresh-token",
    "expires_in": 3600,
    "token_type": "Bearer",
    "scope": "openid email offline_access",
}

PROFILE = {
    "id": "profile-1",
    "userId": "user-1",
    "email": "owner@example.com",
    "firstName": "Taylor",
    "lastName": "Quinn",
}


def account_map(now: datetime | None = None) -> dict:
    """Return an account map with one recent correction and one old one."""
    moment = now or datetime.now(timezone.utc)
    recent = (moment - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    old = (moment - timedelta(hours=48)).isoformat().replace("+00:00", "Z")
    return {
        "pets": [
            {
                "id": "pet-1",
                "name": "Scout",
                "breed": "goldenretriever",
                "collarInfo": {"id": "collar-1", "serialNumber": "SN-1"},
                "fencesState": "on",
                "beaconsState": "off",
                "isFencesSynchronized": True,
                "currentGeoFenceId": "fence-1",
                "telemetry": {
                    "latitude": 44.0,
                    "longitude": -92.4,
                    "accuracy": 8,
                    "batteryChargePercent": 80,
                    "wiFi": {"status": "socketconnected"},
                    "cellular": {"status": "disconnected"},
                    "mode": {"fencesOn": True, "beaconsOn": False},
                    "geoFence": {"id": "fence-1", "name": "Home"},
                    "walk": {"isPaused": False},
                    "timestamp": recent,
                },
            },
            {
                "id": "pet-2",
                "name": "Ghost",
                "collarInfo": None,
                "telemetry": None,
            },
        ],
        "geoFencesInfo": {
            "geoFencesTotalCount": 1,
            "geoFencesToDisplay": [{"id": "fence-1", "name": "Home", "isEnabled": True}],
        },
        "corrections": [
            {"id": "correction-new", "petId": "pet-1", "occurredAt": recent},
            {"id": "correction-old", "petId": "pet-1", "occurredAt": old},
        ],
    }


COLLARS = [
    {
        "id": "collar-1",
        "serialNumber": "SN-1",
        "type": "version5",
        "configurationSyncStatus": "uptodate",
        "petInfo": {"id": "pet-1", "name": "Scout"},
        "telemetry": {
            "batteryChargePercent": 79,
            "wiFi": {"status": "disconnected"},
            "cellular": {"status": "socketconnected"},
        },
        "firmware": {"version": "03.08.00", "formattedVersion": "03.08.00"},
        "hasFirmwareUpdatesAvailable": True,
        "firmwareUpdate": {
            "firmware": {"version": "03.09.00", "formattedVersion": "03.09.00"},
            "update": {"status": "downloading"},
        },
    }
]
