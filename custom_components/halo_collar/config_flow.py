"""Config flow for Halo Collar."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api.auth import password_login
from .api.client import HaloClient
from .api.exceptions import HaloAuthError, HaloConnectionError, HaloError
from .api.models import TokenSet, UserProfile
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_INSTANCE_ID,
    CONF_EMAIL,
    CONF_EXPIRES_AT,
    CONF_PASSWORD,
    CONF_REFRESH_TELEMETRY,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_TYPE,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    scan_interval_seconds,
)

_LOGGER = logging.getLogger(__name__)

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)
_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)


def _entry_data(
    email: str,
    tokens: TokenSet,
    app_instance_id: str,
    user_id: str,
) -> dict[str, Any]:
    return {
        CONF_EMAIL: email,
        CONF_ACCESS_TOKEN: tokens.access_token,
        CONF_REFRESH_TOKEN: tokens.refresh_token,
        CONF_EXPIRES_AT: tokens.expires_at,
        CONF_TOKEN_TYPE: tokens.token_type,
        CONF_APP_INSTANCE_ID: app_instance_id,
        CONF_USER_ID: user_id,
    }


class HaloCollarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Email and password login for a Halo account."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the Halo email and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = str(user_input[CONF_EMAIL]).strip()
            app_instance_id = str(uuid.uuid4())
            try:
                tokens, profile = await self._async_login(
                    email,
                    user_input[CONF_PASSWORD],
                    app_instance_id,
                )
            except HaloAuthError:
                errors["base"] = "invalid_auth"
            except HaloConnectionError:
                errors["base"] = "cannot_connect"
            except HaloError:
                _LOGGER.exception("Halo login failed")
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected Halo login failure")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(profile.user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data=_entry_data(email, tokens, app_instance_id, profile.user_id),
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_REFRESH_TELEMETRY: False,
                    },
                )
        return self.async_show_form(step_id="user", data_schema=_USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start a fresh login after Halo rejects the refresh token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Ask for the password again."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            email = str(entry.data[CONF_EMAIL])
            try:
                tokens, profile = await self._async_login(
                    email,
                    user_input[CONF_PASSWORD],
                    str(entry.data[CONF_APP_INSTANCE_ID]),
                )
            except HaloAuthError:
                errors["base"] = "invalid_auth"
            except HaloConnectionError:
                errors["base"] = "cannot_connect"
            except HaloError:
                _LOGGER.exception("Halo reauthentication failed")
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected Halo reauthentication failure")
                errors["base"] = "unknown"
            else:
                return await self._async_finish_reauth(
                    email,
                    tokens,
                    profile,
                    str(entry.data[CONF_APP_INSTANCE_ID]),
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"email": str(entry.data.get(CONF_EMAIL, ""))},
        )

    async def _async_finish_reauth(
        self,
        email: str,
        tokens: TokenSet,
        profile: UserProfile,
        app_instance_id: str,
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(profile.user_id)
        self._abort_if_unique_id_mismatch(reason="wrong_account")
        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates=_entry_data(email, tokens, app_instance_id, profile.user_id),
        )

    async def _async_login(
        self,
        email: str,
        password: str,
        app_instance_id: str,
    ) -> tuple[TokenSet, UserProfile]:
        session = async_get_clientsession(self.hass)
        tokens = await password_login(session, email, password)
        client = HaloClient(
            session,
            tokens,
            app_instance_id=app_instance_id,
            timezone_name=self.hass.config.time_zone or "America/Chicago",
        )
        return tokens, await client.async_user_profile()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HaloCollarOptionsFlow:
        """Return the options flow."""
        return HaloCollarOptionsFlow()


class HaloCollarOptionsFlow(OptionsFlowWithReload):
    """Update interval and telemetry refresh."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit poll options."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: scan_interval_seconds(user_input[CONF_SCAN_INTERVAL]),
                    CONF_REFRESH_TELEMETRY: bool(user_input[CONF_REFRESH_TELEMETRY]),
                }
            )
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_SCAN_INTERVAL): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_SCAN_INTERVAL,
                                max=MAX_SCAN_INTERVAL,
                                step=1,
                                mode=NumberSelectorMode.BOX,
                                unit_of_measurement="s",
                            )
                        ),
                        vol.Required(CONF_REFRESH_TELEMETRY): BooleanSelector(),
                    }
                ),
                {
                    CONF_SCAN_INTERVAL: options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_REFRESH_TELEMETRY: options.get(CONF_REFRESH_TELEMETRY, False),
                },
            ),
        )
