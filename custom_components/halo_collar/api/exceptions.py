"""Errors raised by the read-only Halo client."""

from __future__ import annotations


class HaloError(Exception):
    """Base error for Halo requests."""


class HaloAuthError(HaloError):
    """Halo rejected the login or the refresh token."""


class HaloConnectionError(HaloError):
    """The Halo service could not be reached."""


class HaloApiError(HaloError):
    """Halo returned a response this client cannot use."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path
