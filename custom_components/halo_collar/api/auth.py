"""Halo OAuth password grant and refresh.

The password is sent once to Halo's token endpoint and is not returned or stored.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import (
    ANDROID_CLIENT_ID,
    ANDROID_CLIENT_SECRET,
    ANDROID_TOKEN_USER_AGENT,
    AUTH_BASE_URL,
    SCOPE,
    TOKEN_EXPIRY_SLACK_SECONDS,
    TOKEN_PATH,
)
from .exceptions import HaloAuthError, HaloConnectionError
from .models import TokenSet


async def password_login(
    session: aiohttp.ClientSession,
    email: str,
    password: str,
) -> TokenSet:
    """Exchange a Halo email and password for a token set."""
    username = email.strip()
    if not username or not password:
        raise HaloAuthError("Halo account email and password are required.")
    return await _token_request(
        session,
        {
            "grant_type": "password",
            "client_id": ANDROID_CLIENT_ID,
            "client_secret": ANDROID_CLIENT_SECRET,
            "scope": SCOPE,
            "username": username,
            "password": password,
        },
    )


async def refresh_login(session: aiohttp.ClientSession, refresh_token: str) -> TokenSet:
    """Rotate a refresh token."""
    if not refresh_token:
        raise HaloAuthError("Halo did not provide a refresh token.")
    return await _token_request(
        session,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": ANDROID_CLIENT_ID,
            "client_secret": ANDROID_CLIENT_SECRET,
        },
        previous_refresh_token=refresh_token,
    )


async def _token_request(
    session: aiohttp.ClientSession,
    form: dict[str, str],
    *,
    previous_refresh_token: str | None = None,
) -> TokenSet:
    try:
        async with session.request(
            "POST",
            f"{AUTH_BASE_URL}{TOKEN_PATH}",
            data=form,
            headers={
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": ANDROID_TOKEN_USER_AGENT,
            },
            timeout=aiohttp.ClientTimeout(total=20, connect=10),
        ) as response:
            payload = await _json_object(response)
            status = response.status
    except (aiohttp.ClientError, TimeoutError) as err:
        raise HaloConnectionError("Could not reach Halo's authentication service.") from err

    if status >= 400:
        error = payload.get("error")
        if error == "invalid_grant":
            if form.get("grant_type") == "password":
                raise HaloAuthError("Halo rejected the email or password.")
            raise HaloAuthError("Halo rejected the refresh token.")
        if error == "invalid_client":
            raise HaloAuthError("Halo rejected the Android application credential.")
        raise HaloAuthError(f"Halo authentication failed with HTTP {status}.")

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token") or previous_refresh_token
    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        raise HaloAuthError("Halo returned an incomplete token response.")
    try:
        expires_in = max(0, int(payload.get("expires_in", 0)))
    except (TypeError, ValueError) as err:
        raise HaloAuthError("Halo returned an invalid token expiry.") from err
    return TokenSet(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=_expires_at(expires_in),
        token_type=str(payload.get("token_type") or "Bearer"),
        scope=str(payload.get("scope") or ""),
    )


def _expires_at(expires_in: int) -> float:
    slack = min(TOKEN_EXPIRY_SLACK_SECONDS, expires_in)
    return datetime.now(timezone.utc).timestamp() + (expires_in - slack)


async def _json_object(response: aiohttp.ClientResponse) -> dict[str, Any]:
    try:
        payload = await response.json(content_type=None)
    except (json.JSONDecodeError, aiohttp.ContentTypeError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}
