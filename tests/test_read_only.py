"""Guard the integration against write calls to the Halo API."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
API = ROOT / "custom_components" / "halo_collar" / "api"
COMPONENT = ROOT / "custom_components" / "halo_collar"

WRITE_WORDS = ("POST", "PUT", "PATCH", "DELETE")


def test_api_client_only_issues_get() -> None:
    """The API client file does not name a write method."""
    text = (API / "client.py").read_text(encoding="utf-8")
    for word in WRITE_WORDS:
        assert word not in text


def test_only_the_token_endpoint_is_a_post() -> None:
    """The only POST in the integration is the OAuth token request."""
    offenders: list[str] = []
    for path in COMPONENT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name == "auth.py":
            assert text.count('"POST"') == 1
            assert "TOKEN_PATH" in text
            continue
        for word in WRITE_WORDS:
            if f'"{word}"' in text or f"'{word}'" in text:
                offenders.append(f"{path.name} contains {word}")
    assert offenders == []
