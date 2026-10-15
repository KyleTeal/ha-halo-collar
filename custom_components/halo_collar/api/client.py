"""Async read-only Halo API client."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .auth import refresh_login
from .const import (
    ANDROID_APP_VERSION,
    ANDROID_CLIENT_ID,
    API_BASE_URL,
    UNKNOWN_PARALLEL_CALL_VERSION,
)
from .exceptions import HaloApiError, HaloAuthError, HaloConnectionError, HaloError
from .models import (
    AccountSnapshot,
    TokenSet,
    UserProfile,
    parse_account_snapshot,
    parse_user_profile,
)

OnTokensUpdated = Callable[[TokenSet], Awaitable[None]]
_LOGGER = logging.getLogger(__name__)
_ERROR_KEYS = (
    "error",
    "error_description",
    "errorCode",
    "ErrorCode",
    "message",
    "Message",
    "title",
    "detail",
    "code",
)


class HaloClient:
    """GET-only Halo client that refreshes its own access token."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        tokens: TokenSet,
        *,
        app_instance_id: str,
        timezone_name: str,
        on_tokens_updated: OnTokensUpdated | None = None,
    ) -> None:
        self._session = session
        self._tokens = tokens
        self._app_instance_id = app_instance_id
        self._timezone_name = timezone_name or "UTC"
        self._on_tokens_updated = on_tokens_updated
        self._parallel_call_version = UNKNOWN_PARALLEL_CALL_VERSION
        self._amplitude_session_id = str(int(datetime.now(UTC).timestamp() * 1000))
        self._lock = asyncio.Lock()

    async def async_user_profile(self) -> UserProfile:
        """Fetch the signed-in account profile."""
        return parse_user_profile(await self._get_json("/user-profile"))

    async def async_account_snapshot(self, *, refresh_telemetry: bool = False) -> AccountSnapshot:
        """Fetch the map and the collar list."""
        account_map, collars = await asyncio.gather(
            self._get_json(
                "/account/my/map",
                params={
                    "RefreshTelemetry": str(refresh_telemetry),
                    "MaxCorrectionsCount": "20",
                },
            ),
            self._get_json("/collar/my"),
        )
        return parse_account_snapshot(account_map, collars)

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        return await self._request(path, params=params, allow_reauth=True)

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, str] | None,
        allow_reauth: bool,
    ) -> Any:
        headers = await self._headers()
        status = 0
        reauth = False
        detail = ""
        user_agent = headers.get("User-Agent", "(session default)")
        try:
            async with self._session.request(
                "GET",
                f"{API_BASE_URL}{path}",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20, connect=10),
            ) as response:
                self._remember_parallel_version(response)
                status = response.status
                user_agent = _sent_user_agent(response) or user_agent
                if status < 400:
                    try:
                        return await response.json(content_type=None)
                    except (
                        json.JSONDecodeError,
                        aiohttp.ContentTypeError,
                        ValueError,
                        TypeError,
                    ) as err:
                        raise HaloApiError(
                            f"Halo returned a response that was not JSON for {path}.",
                            status_code=status,
                            path=path,
                        ) from err
                detail = await _error_detail(response)
                reauth = status == 401 and allow_reauth
        except HaloError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HaloConnectionError("Could not reach the Halo API.") from err

        if reauth:
            _LOGGER.debug(
                "Halo GET %s returned HTTP 401 (%s); refreshing the login once",
                path,
                detail or "no body",
            )
            await self._ensure_token(force=True)
            return await self._request(path, params=params, allow_reauth=False)
        if status == 401:
            _LOGGER.error("Halo rejected the login on GET %s (%s)", path, detail or "no body")
            raise HaloAuthError("Halo rejected the login.")
        _LOGGER.error(
            "Halo GET %s failed with HTTP %s (%s). user-agent=%s "
            "halo-client=%s parallel-version=%s",
            path,
            status,
            detail or "no body",
            user_agent,
            headers.get("Halo-Client"),
            headers.get("Halo-ParallelCall-Version"),
        )
        raise HaloApiError(
            f"Halo returned HTTP {status} for {path}. {detail}".rstrip(),
            status_code=status,
            path=path,
        )

    async def _headers(self) -> dict[str, str]:
        await self._ensure_token(force=False)
        return {
            "Accept": "application/json",
            "Authorization": f"{self._tokens.token_type} {self._tokens.access_token}",
            "Halo-Client": urlencode(
                {
                    "clientId": ANDROID_CLIENT_ID,
                    "version": ANDROID_APP_VERSION,
                    "appInstanceId": self._app_instance_id,
                    "timezone": self._timezone_name,
                }
            ),
            "Halo-ParallelCall-Version": self._parallel_call_version,
            "Halo-Amplitude-SessionId": self._amplitude_session_id,
        }

    async def _ensure_token(self, *, force: bool) -> None:
        async with self._lock:
            if not force and not self._tokens.is_expired:
                return
            self._tokens = await refresh_login(self._session, self._tokens.refresh_token)
            if self._on_tokens_updated is not None:
                await self._on_tokens_updated(self._tokens)

    def _remember_parallel_version(self, response: aiohttp.ClientResponse) -> None:
        version = response.headers.get("Halo-ParallelCall-Version")
        if version:
            self._parallel_call_version = version


def _sent_user_agent(response: aiohttp.ClientResponse) -> str | None:
    request_info = getattr(response, "request_info", None)
    if request_info is None:
        return None
    user_agent = request_info.headers.get("User-Agent")
    return str(user_agent) if user_agent else None


async def _error_detail(response: aiohttp.ClientResponse) -> str:
    """Describe an error body without tokens, passwords, or coordinates."""
    content_type = response.headers.get("Content-Type", "missing").split(";", 1)[0]
    try:
        payload = await response.json(content_type=None)
    except (json.JSONDecodeError, aiohttp.ContentTypeError, ValueError, TypeError):
        return f"content-type={content_type}"
    if not isinstance(payload, dict):
        return f"content-type={content_type} body={type(payload).__name__}"
    parts = [
        f"content-type={content_type}",
        "fields=" + (",".join(sorted(str(key) for key in payload)) or "none"),
    ]
    for key in _ERROR_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"{key}={_redact(value)}")
        elif isinstance(value, int) and not isinstance(value, bool):
            parts.append(f"{key}={value}")
    validation = payload.get("ValidationErrors")
    if validation is None:
        validation = payload.get("validationErrors")
    if isinstance(validation, dict):
        parts.append("validation=" + ",".join(str(key) for key in validation))
    return " ".join(parts)


def _redact(value: str) -> str:
    value = re.sub(r"\S+://\S+", "<redacted-url>", value)
    value = re.sub(r"\b[A-Za-z0-9_-]{16,}\b", "<redacted-value>", value)
    return " ".join(value.split())[:240]
