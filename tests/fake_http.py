"""In-memory aiohttp stand-in for the Halo client tests."""

from __future__ import annotations

from typing import Any

import aiohttp


class FakeResponse:
    """One scripted HTTP response."""

    def __init__(
        self,
        status: int,
        payload: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.payload = payload
        self.headers = headers or {}

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def json(self, content_type: str | None = None) -> Any:
        if isinstance(self.payload, Exception):
            raise self.payload
        if self.payload is None:
            raise ValueError("response was not JSON")
        return self.payload


class FakeSession:
    """Routes method + URL prefix to a response, once or several times."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self._routes: list[tuple[str, str, list[FakeResponse | Exception]]] = []

    def add(
        self,
        method: str,
        url: str,
        response: FakeResponse | Exception,
        *,
        times: int = 1,
    ) -> None:
        self._routes.append((method.upper(), url, [response] * times))

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method.upper(), url, kwargs))
        method = method.upper()
        for index, (route_method, route_url, responses) in enumerate(self._routes):
            if route_method == method and url.startswith(route_url) and responses:
                response = responses.pop(0)
                if not responses:
                    self._routes.pop(index)
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected {method} {url}")
