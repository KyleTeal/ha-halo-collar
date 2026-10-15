"""Tests for the read-only Halo client."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiohttp
import pytest

from custom_components.halo_collar.api.client import HaloClient
from custom_components.halo_collar.api.exceptions import HaloApiError, HaloAuthError
from custom_components.halo_collar.api.models import TokenSet
from tests.fake_http import FakeResponse, FakeSession
from tests.payloads import COLLARS, PROFILE, TOKEN, account_map

TOKEN_URL = "https://auth.halocollar.com/connect/token"
MAP_URL = "https://api.halocollar.com/account/my/map"
COLLAR_URL = "https://api.halocollar.com/collar/my"
PROFILE_URL = "https://api.halocollar.com/user-profile"


def _tokens(*, expired: bool) -> TokenSet:
    delta = timedelta(minutes=-5 if expired else 30)
    return TokenSet(
        access_token="old-access",
        refresh_token="old-refresh",
        expires_at=(datetime.now(timezone.utc) + delta).timestamp(),
    )


def _client(session: FakeSession, tokens: TokenSet, saved: list[TokenSet]) -> HaloClient:
    async def _save(updated: TokenSet) -> None:
        saved.append(updated)

    return HaloClient(
        session,  # type: ignore[arg-type]
        tokens,
        app_instance_id="instance-1",
        timezone_name="America/Chicago",
        on_tokens_updated=_save,
    )


async def test_snapshot_is_get_only_when_the_token_is_fresh() -> None:
    """A fresh token polls the map and collars with GET and does not refresh."""
    session = FakeSession()
    session.add("GET", MAP_URL, FakeResponse(200, account_map(), {"Halo-ParallelCall-Version": "7"}))
    session.add("GET", COLLAR_URL, FakeResponse(200, COLLARS))
    saved: list[TokenSet] = []
    client = _client(session, _tokens(expired=False), saved)

    snapshot = await client.async_account_snapshot(refresh_telemetry=False)

    assert snapshot.pet("pet-1") is not None
    assert saved == []
    methods = [call[0] for call in session.calls]
    assert methods == ["GET", "GET"]
    assert all(call[1].startswith("https://api.halocollar.com") for call in session.calls)
    map_call = next(call for call in session.calls if call[1].startswith(MAP_URL))
    assert map_call[2]["params"]["RefreshTelemetry"] == "False"
    assert "Authorization" in map_call[2]["headers"]
    assert "Halo-Client" in map_call[2]["headers"]


async def test_expired_token_refreshes_before_the_poll() -> None:
    """An expired access token is refreshed once and the new tokens are saved."""
    session = FakeSession()
    session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN))
    session.add("GET", MAP_URL, FakeResponse(200, account_map()))
    session.add("GET", COLLAR_URL, FakeResponse(200, COLLARS))
    saved: list[TokenSet] = []
    client = _client(session, _tokens(expired=True), saved)

    await client.async_account_snapshot()

    assert session.calls[0][0] == "POST"
    assert session.calls[0][1] == TOKEN_URL
    assert [call[0] for call in session.calls[1:]] == ["GET", "GET"]
    assert saved[0].access_token == "access-token"
    assert saved[0].refresh_token == "refresh-token"


async def test_unauthorized_get_refreshes_once_and_retries() -> None:
    """A 401 retries a single time after refreshing."""
    session = FakeSession()
    session.add("GET", MAP_URL, FakeResponse(401, {"error": "expired"}))
    session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN))
    session.add("GET", MAP_URL, FakeResponse(200, account_map()))
    session.add("GET", COLLAR_URL, FakeResponse(200, COLLARS))
    saved: list[TokenSet] = []
    client = _client(session, _tokens(expired=False), saved)

    snapshot = await client.async_account_snapshot()

    assert snapshot.pet("pet-1") is not None
    assert [call[0] for call in session.calls] == ["GET", "POST", "GET", "GET"]
    assert len(saved) == 1


async def test_rejected_refresh_raises_auth_error() -> None:
    """invalid_grant on refresh surfaces as an auth error."""
    session = FakeSession()
    session.add("POST", TOKEN_URL, FakeResponse(400, {"error": "invalid_grant"}))
    client = _client(session, _tokens(expired=True), [])

    with pytest.raises(HaloAuthError):
        await client.async_user_profile()


async def test_http_error_includes_halo_error_fields(caplog) -> None:
    """A failed GET keeps Halo's error code and message, not the token."""
    session = FakeSession()
    session.add(
        "GET",
        PROFILE_URL,
        FakeResponse(
            400,
            {
                "errorCode": 3001,
                "message": "Parallel call version is obsolete",
                "access_token": "should-not-be-logged",
            },
        ),
    )
    client = _client(session, _tokens(expired=False), [])

    with pytest.raises(HaloApiError, match="errorCode=3001") as raised:
        await client.async_user_profile()

    text = f"{raised.value} {caplog.text}"
    assert "Parallel call version is obsolete" in text
    assert "should-not-be-logged" not in text
    assert "old-access" not in text


async def test_profile_and_http_error() -> None:
    """The profile parser runs, and an HTTP error becomes an API error."""
    session = FakeSession()
    session.add("GET", PROFILE_URL, FakeResponse(200, PROFILE))
    client = _client(session, _tokens(expired=False), [])
    profile = await client.async_user_profile()
    assert profile.user_id == "user-1"

    session.add("GET", PROFILE_URL, FakeResponse(500, {"error": "nope"}))
    with pytest.raises(HaloApiError, match="HTTP 500"):
        await client.async_user_profile()


async def test_connection_error() -> None:
    """A transport failure is a connection error."""
    session = FakeSession()
    session.add("GET", PROFILE_URL, aiohttp.ClientConnectionError("down"))
    client = _client(session, _tokens(expired=False), [])

    from custom_components.halo_collar.api.exceptions import HaloConnectionError

    with pytest.raises(HaloConnectionError):
        await client.async_user_profile()
