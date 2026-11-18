"""Polls the Family Quest add-on every 30 seconds (and right after every action)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FamilyQuestApi, FamilyQuestAuthError, FamilyQuestError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class FamilyQuestCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: FamilyQuestApi) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.state()
        except FamilyQuestAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FamilyQuestError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def instance(self) -> str:
        return (self.data or {}).get("instance") or self.config_entry.entry_id

    def child(self, child_id: int) -> dict | None:
        return next((c for c in (self.data or {}).get("children", []) if c["id"] == child_id), None)

    async def async_action(self, action: str, **data: Any) -> dict:
        """Send an action to the add-on, then refresh the entities."""
        try:
            result = await self.api.action(action, **data)
        except FamilyQuestError as err:
            raise HomeAssistantError(f"Family Quest: {err}") from err
        await self.async_request_refresh()
        return result
