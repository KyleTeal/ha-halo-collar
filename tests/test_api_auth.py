"""Tests for Halo password login and refresh."""

from __future__ import annotations

import aiohttp
import pytest

from custom_components.halo_collar.api.auth import password_login, refresh_login
from custom_components.halo_collar.api.exceptions import HaloAuthError, HaloConnectionError
from tests.fake_http import FakeResponse, FakeSession
from tests.payloads import TOKEN

TOKEN_URL = "https://auth.halocollar.com/connect/token"


async def test_password_login_returns_tokens_and_does_not_keep_the_password() -> None:
    """A password grant returns tokens and the password stays in that one request."""
    session = FakeSession()
    session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN))

    tokens = await password_login(session, "owner@example.com", "secret-password")

    assert tokens.access_token == "access-token"
    assert tokens.refresh_token == "refresh-token"
    assert tokens.is_expired is False
    assert session.calls[0][0] == "POST"
    assert session.calls[0][1] == TOKEN_URL
    assert session.calls[0][2]["data"]["password"] == "secret-password"
    assert session.calls[0][2]["data"]["grant_type"] == "password"
    assert "password" not in tokens.access_token


async def test_password_login_rejects_bad_credentials() -> None:
    """Halo invalid_grant on a password grant is an auth error."""
    session = FakeSession()
    session.add("POST", TOKEN_URL, FakeResponse(400, {"error": "invalid_grant"}))

    with pytest.raises(HaloAuthError, match="email or password"):
        await password_login(session, "owner@example.com", "nope")


async def test_refresh_keeps_the_previous_token_when_halo_omits_a_new_one() -> None:
    """A refresh response without a new refresh token keeps the current one."""
    session = FakeSession()
    session.add(
        "POST",
        TOKEN_URL,
        FakeResponse(200, {"access_token": "next-access", "expires_in": 120, "token_type": "Bearer"}),
    )

    tokens = await refresh_login(session, "old-refresh")

    assert tokens.access_token == "next-access"
    assert tokens.refresh_token == "old-refresh"


async def test_refresh_invalid_grant() -> None:
    """A rejected refresh token raises an auth error."""
    session = FakeSession()
    session.add("POST", TOKEN_URL, FakeResponse(400, {"error": "invalid_grant"}))

    with pytest.raises(HaloAuthError, match="refresh token"):
        await refresh_login(session, "dead-refresh")


async def test_login_connection_error() -> None:
    """A network failure talking to the token endpoint is a connection error."""
    session = FakeSession()
    session.add("POST", TOKEN_URL, aiohttp.ClientConnectionError("down"))

    with pytest.raises(HaloConnectionError):
        await password_login(session, "owner@example.com", "secret")
