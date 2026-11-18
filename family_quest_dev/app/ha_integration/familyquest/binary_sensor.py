"""Binary sensors per child: daily goal met, internet blocked, game time used up, OfflineTime active."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FamilyQuestEntity, track_new_entities


@dataclass(frozen=True, kw_only=True)
class FQBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict], bool]
    attrs_fn: Callable[[dict], dict] | None = None
    exists_fn: Callable[[dict], bool] = lambda c: True


CHILD_BINARY: tuple[FQBinaryDescription, ...] = (
    FQBinaryDescription(key="goal_met", translation_key="goal_met", icon="mdi:bullseye-arrow", value_fn=lambda c: c["goal_met"]),
    FQBinaryDescription(key="internet_blocked", translation_key="internet_blocked", icon="mdi:web-off",
                        exists_fn=lambda c: c.get("internet") is not None,
                        value_fn=lambda c: bool((c.get("internet") or {}).get("blocked")),
                        attrs_fn=lambda c: {"block_until": (c.get("internet") or {}).get("block_until"),
                                            "can_start": (c.get("internet") or {}).get("can_start")}),
    FQBinaryDescription(key="game_time_used_up", translation_key="game_time_used_up", icon="mdi:timer-off",
                        value_fn=lambda c: c["game_used_up"]),
    FQBinaryDescription(key="offline_time", translation_key="offline_time", icon="mdi:power-sleep",
                        value_fn=lambda c: c["offline_time"], attrs_fn=lambda c: {"title": c.get("offline_title") or None}),
)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data

    def make(data: dict) -> list[FamilyQuestEntity]:
        return [ChildBinary(coordinator, c["id"], d) for c in data.get("children", []) for d in CHILD_BINARY if d.exists_fn(c)]

    entry.async_on_unload(track_new_entities(coordinator, async_add_entities, make))


class ChildBinary(FamilyQuestEntity, BinarySensorEntity):
    entity_description: FQBinaryDescription

    def __init__(self, coordinator, child_id: int, description: FQBinaryDescription) -> None:
        super().__init__(coordinator, child_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.exists_fn(self.child)

    @property
    def is_on(self) -> bool | None:
        return bool(self.entity_description.value_fn(self.child)) if self.child else None

    @property
    def extra_state_attributes(self) -> dict | None:
        fn = self.entity_description.attrs_fn
        return fn(self.child) if fn and self.child else None
