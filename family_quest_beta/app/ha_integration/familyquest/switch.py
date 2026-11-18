"""Switch per child with internet time managed by Family Quest: on = the internet time runs.

Off pauses it (like «pause» in the app / «stop» in the parent area); on starts it with the child's minutes – the
same rules as in the app (no minutes left, block time or OfflineTime: the add-on refuses and the switch stays off)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FamilyQuestEntity, track_new_entities


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data

    def make(data: dict) -> list[FamilyQuestEntity]:
        return [InternetSwitch(coordinator, c["id"]) for c in data.get("children", []) if c.get("internet") is not None]

    entry.async_on_unload(track_new_entities(coordinator, async_add_entities, make))


class InternetSwitch(FamilyQuestEntity, SwitchEntity):
    _attr_translation_key = "internet"
    _attr_icon = "mdi:web"

    def __init__(self, coordinator, child_id: int) -> None:
        super().__init__(coordinator, child_id, "internet")

    @property
    def available(self) -> bool:
        return super().available and self.child.get("internet") is not None

    @property
    def is_on(self) -> bool | None:
        net = self.child.get("internet")
        return bool(net["running"]) if net else None

    @property
    def extra_state_attributes(self) -> dict | None:
        net = self.child.get("internet") or {}
        return {"minutes_left": net.get("minutes"), "unlimited": net.get("unlimited"), "can_start": net.get("can_start")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_action("internet_start", child=self.child_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_action("internet_stop", child=self.child_id)
