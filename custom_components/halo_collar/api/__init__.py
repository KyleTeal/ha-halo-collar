"""Read-only Halo Collar API.

Request shapes follow the unofficial client by sevenlayercookie:
https://github.com/sevenlayercookie/halo-collar-api

This package performs GET requests against the Halo API, plus the OAuth token
request required to sign in and refresh a session.
"""

from __future__ import annotations

from .auth import password_login, refresh_login
from .client import HaloClient
from .exceptions import HaloApiError, HaloAuthError, HaloConnectionError, HaloError
from .models import AccountSnapshot, Collar, Pet, Telemetry, TokenSet, UserProfile

__all__ = [
    "AccountSnapshot",
    "Collar",
    "HaloApiError",
    "HaloAuthError",
    "HaloClient",
    "HaloConnectionError",
    "HaloError",
    "Pet",
    "Telemetry",
    "TokenSet",
    "UserProfile",
    "password_login",
    "refresh_login",
]
