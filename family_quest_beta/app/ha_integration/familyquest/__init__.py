"""Family Quest: the KPIs of the Family Quest add-on as Home Assistant entities, plus a few safe actions.

The actions (add_points, approve_chore, approve_reward) are admin services: only Home Assistant administrators and
automations / scripts may call them. The internet switch of a child follows the same rules as the app (minutes left,
block times) – every Home Assistant user who sees the entity can switch it; hide it from dashboards of other users.

Installed by the add-on into /config/custom_components/familyquest (parent area › Settings ›
«Family Quest HA integration»). Talks only to the add-on API /api/integration/… with the integration token.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError, Unauthorized, UnknownUser
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FamilyQuestApi
from .const import CONF_TOKEN, CONF_URL, DOMAIN, PLATFORMS
from .coordinator import FamilyQuestCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_ENTRY = "config_entry_id"

SERVICE_SCHEMAS = {
    "add_points": vol.Schema({
        vol.Required("child"): cv.string,
        vol.Optional("account", default="coins"): cv.string,
        vol.Required("amount"): vol.All(vol.Coerce(float), vol.Range(min=-10000, max=10000)),
        vol.Optional("reason", default="Home Assistant"): cv.string,
        vol.Optional(ATTR_ENTRY): cv.string,
    }),
    "approve_chore": vol.Schema({
        vol.Required("task_id"): vol.Coerce(int),
        vol.Optional("approve", default=True): cv.boolean,
        vol.Optional(ATTR_ENTRY): cv.string,
    }),
    "approve_reward": vol.Schema({
        vol.Required("redemption_id"): vol.Coerce(int),
        vol.Optional("approve", default=True): cv.boolean,
        vol.Optional(ATTR_ENTRY): cv.string,
    }),
}

type FamilyQuestConfigEntry = ConfigEntry[FamilyQuestCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Services of the domain (they work with the one Family Quest, or the entry given by config_entry_id)."""

    def coordinator_for(call: ServiceCall) -> FamilyQuestCoordinator:
        entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
        wanted = call.data.get(ATTR_ENTRY)
        if wanted:
            entries = [e for e in entries if e.entry_id == wanted]
        if len(entries) != 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_entry" if not entries else "several_entries")
        return entries[0].runtime_data

    async def handle(call: ServiceCall) -> ServiceResponse:
        # admin services (like helpers.service.async_register_admin_service, which cannot return a response): coins and
        # approvals are a parent's decision – a non-admin Home Assistant user may not call them (automations may: no user)
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
            if not user.is_admin:
                raise Unauthorized(context=call.context)
        data = {k: v for k, v in call.data.items() if k != ATTR_ENTRY}
        result = await coordinator_for(call).async_action(call.service, **data)
        return result if call.return_response else None

    for name, schema in SERVICE_SCHEMAS.items():
        hass.services.async_register(DOMAIN, name, handle, schema=schema, supports_response=SupportsResponse.OPTIONAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FamilyQuestConfigEntry) -> bool:
    api = FamilyQuestApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = FamilyQuestCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FamilyQuestConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
