"""Config flow: the address of the Family Quest add-on and the integration token from its parent area."""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FamilyQuestApi, FamilyQuestAuthError, FamilyQuestError
from .const import CONF_TOKEN, CONF_URL, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _suggested_url() -> str:
    """The add-on writes its own address (http://<add-on hostname>:8099) into addon.json when it installs us."""
    try:
        return json.loads((Path(__file__).parent / "addon.json").read_text(encoding="utf-8")).get("url") or DEFAULT_URL
    except (OSError, ValueError):
        return DEFAULT_URL


class FamilyQuestConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _check(self, url: str, token: str) -> tuple[dict | None, dict[str, str]]:
        api = FamilyQuestApi(async_get_clientsession(self.hass), url, token)
        try:
            return await api.state(), {}
        except FamilyQuestAuthError:
            return None, {"base": "invalid_auth"}
        except FamilyQuestError as err:
            _LOGGER.debug("Family Quest not reachable: %s", err)
            return None, {"base": "cannot_connect"}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            token = user_input[CONF_TOKEN].strip()
            state, errors = await self._check(url, token)
            if state is not None:
                await self.async_set_unique_id(state.get("instance") or url)
                self._abort_if_unique_id_configured(updates={CONF_URL: url, CONF_TOKEN: token})
                return self.async_create_entry(title="Family Quest", data={CONF_URL: url, CONF_TOKEN: token})
        suggested = (user_input or {}).get(CONF_URL) or await self.hass.async_add_executor_job(_suggested_url)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_URL, default=suggested): str, vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """New token (made again in the parent area, or the integration was switched off and on)."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            state, errors = await self._check(entry.data[CONF_URL], token)
            if state is not None:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
                                    errors=errors)
