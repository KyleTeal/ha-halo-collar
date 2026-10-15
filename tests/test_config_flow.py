"""Config flow tests."""

from __future__ import annotations

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.halo_collar.const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_INSTANCE_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TELEMETRY,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)
from tests.conftest import entry_data, entry_options
from tests.payloads import PROFILE, TOKEN

TOKEN_URL = "https://auth.halocollar.com/connect/token"
PROFILE_URL = "https://api.halocollar.com/user-profile"


async def test_user_flow_creates_an_entry_without_storing_the_password(hass, aioclient_mock) -> None:
    """A valid login creates one entry and drops the password."""
    aioclient_mock.post(TOKEN_URL, json=TOKEN)
    aioclient_mock.get(PROFILE_URL, json=PROFILE)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "owner@example.com", CONF_PASSWORD: "secret-password"},
    )

    assert result["type"] == "create_entry"
    assert result["result"].unique_id == "user-1"
    assert result["title"] == "owner@example.com"
    assert CONF_PASSWORD not in result["result"].data
    assert result["result"].data[CONF_ACCESS_TOKEN] == "access-token"
    assert result["result"].data[CONF_EMAIL] == "owner@example.com"
    assert result["result"].options[CONF_SCAN_INTERVAL] == 120
    assert result["result"].options[CONF_REFRESH_TELEMETRY] is False
    token_calls = [call for call in aioclient_mock.mock_calls if call[0] == "post"]
    assert token_calls
    assert token_calls[0][2]["data"]["password"] == "secret-password"


async def test_user_flow_invalid_auth(hass, aioclient_mock) -> None:
    """A rejected password stays on the form."""
    aioclient_mock.post(TOKEN_URL, status=400, json={"error": "invalid_grant"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "owner@example.com", CONF_PASSWORD: "nope"},
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_flow_cannot_connect(hass, aioclient_mock) -> None:
    """A network failure is reported as cannot_connect."""
    aioclient_mock.post(TOKEN_URL, exc=aiohttp.ClientConnectionError("down"))

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "owner@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_duplicate_account_aborts(hass, aioclient_mock) -> None:
    """The same Halo account cannot be added twice."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="user-1", data=entry_data(), options=entry_options())
    entry.add_to_hass(hass)
    aioclient_mock.post(TOKEN_URL, json=TOKEN)
    aioclient_mock.get(PROFILE_URL, json=PROFILE)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "owner@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_reauth_replaces_tokens(hass, aioclient_mock) -> None:
    """Reauth updates the existing entry and does not create another one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-1",
        data=entry_data(),
        options=entry_options(),
        title="owner@example.com",
    )
    entry.add_to_hass(hass)
    refreshed = {**TOKEN, "access_token": "new-access", "refresh_token": "new-refresh"}
    aioclient_mock.post(TOKEN_URL, json=refreshed)
    aioclient_mock.get(PROFILE_URL, json=PROFILE)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "secret"},
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data[CONF_ACCESS_TOKEN] == "new-access"
    assert entry.data[CONF_APP_INSTANCE_ID] == "instance-1"
    assert CONF_PASSWORD not in entry.data


async def test_reauth_rejects_a_different_account(hass, aioclient_mock) -> None:
    """A password for another Halo account does not replace this entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="user-1", data=entry_data(), options=entry_options())
    entry.add_to_hass(hass)
    aioclient_mock.post(TOKEN_URL, json=TOKEN)
    aioclient_mock.get(PROFILE_URL, json={**PROFILE, "userId": "someone-else"})

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "secret"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "wrong_account"
    assert entry.data[CONF_ACCESS_TOKEN] == "old-access"


async def test_options_flow_updates_interval(hass, aioclient_mock) -> None:
    """Options reload with the new interval."""
    from tests.payloads import COLLARS

    entry = MockConfigEntry(domain=DOMAIN, unique_id="user-1", data=entry_data(), options=entry_options())
    entry.add_to_hass(hass)
    aioclient_mock.get("https://api.halocollar.com/account/my/map", json=__import__("tests.payloads", fromlist=["account_map"]).account_map())
    aioclient_mock.get("https://api.halocollar.com/collar/my", json=COLLARS)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 180, CONF_REFRESH_TELEMETRY: True},
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert entry.options[CONF_SCAN_INTERVAL] == 180
    assert entry.options[CONF_REFRESH_TELEMETRY] is True
    assert entry.runtime_data.update_interval.total_seconds() == 180
