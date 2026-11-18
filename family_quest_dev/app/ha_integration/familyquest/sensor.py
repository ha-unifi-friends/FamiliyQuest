"""Sensors: per child (XP, level, streak, balances, chores, time left …) and for the family."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FamilyQuestEntity, track_new_entities


@dataclass(frozen=True, kw_only=True)
class FQSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    attrs_fn: Callable[[dict], dict] | None = None
    exists_fn: Callable[[dict], bool] = lambda d: True


CHILD_SENSORS: tuple[FQSensorDescription, ...] = (
    FQSensorDescription(key="xp_today", translation_key="xp_today", icon="mdi:star", native_unit_of_measurement="XP",
                        state_class=SensorStateClass.MEASUREMENT, value_fn=lambda c: c["xp_today"],
                        attrs_fn=lambda c: {"daily_goal": c["daily_goal"]}),
    FQSensorDescription(key="total_xp", translation_key="total_xp", icon="mdi:star-circle", native_unit_of_measurement="XP",
                        state_class=SensorStateClass.TOTAL, value_fn=lambda c: c["total_xp"]),
    FQSensorDescription(key="level", translation_key="level", icon="mdi:trophy", value_fn=lambda c: c["level"],
                        attrs_fn=lambda c: {"next_level_at": c["next_level_at"], "xp": c["total_xp"]}),
    FQSensorDescription(key="streak", translation_key="streak", icon="mdi:fire", native_unit_of_measurement=UnitOfTime.DAYS,
                        state_class=SensorStateClass.MEASUREMENT, value_fn=lambda c: c["streak"]),
    FQSensorDescription(key="goal_progress", translation_key="goal_progress", icon="mdi:bullseye-arrow",
                        native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT,
                        value_fn=lambda c: c["goal_percent"]),
    FQSensorDescription(key="chores_open", translation_key="chores_open", icon="mdi:broom",
                        state_class=SensorStateClass.MEASUREMENT, value_fn=lambda c: c["chores_open"],
                        attrs_fn=lambda c: {"chores": c["chores_open_list"], "waiting_for_approval": c["chores_pending"]}),
    FQSensorDescription(key="lessons_today", translation_key="lessons_today", icon="mdi:school",
                        state_class=SensorStateClass.MEASUREMENT, value_fn=lambda c: c["lessons_today"],
                        attrs_fn=lambda c: {"learning_minutes_today": c["learn_minutes_today"]}),
    # None = unlimited (∞): the state is «unknown», the attribute `unlimited` is true
    FQSensorDescription(key="internet_minutes", translation_key="internet_minutes", icon="mdi:web-clock",
                        native_unit_of_measurement=UnitOfTime.MINUTES, state_class=SensorStateClass.MEASUREMENT,
                        exists_fn=lambda c: c.get("internet") is not None,
                        value_fn=lambda c: (c.get("internet") or {}).get("minutes"),
                        attrs_fn=lambda c: {k: (c.get("internet") or {}).get(k) for k in ("unlimited", "running", "reset_at", "block_until")}),
    FQSensorDescription(key="game_time_left", translation_key="game_time_left", icon="mdi:gamepad-variant",
                        native_unit_of_measurement=UnitOfTime.MINUTES, state_class=SensorStateClass.MEASUREMENT,
                        value_fn=lambda c: c["game_left"],
                        attrs_fn=lambda c: {"unlimited": c["game_unlimited"], "used_today": c["game_minutes_today"]}),
    FQSensorDescription(key="learn_time_left", translation_key="learn_time_left", icon="mdi:book-clock",
                        native_unit_of_measurement=UnitOfTime.MINUTES, state_class=SensorStateClass.MEASUREMENT,
                        value_fn=lambda c: c["learn_left"],
                        attrs_fn=lambda c: {"unlimited": c["learn_unlimited"], "used_today": c["learn_minutes_today"]}),
)

FAMILY_SENSORS: tuple[FQSensorDescription, ...] = (
    FQSensorDescription(key="total_xp", translation_key="family_total_xp", icon="mdi:star-circle",
                        native_unit_of_measurement="XP", state_class=SensorStateClass.TOTAL, value_fn=lambda f: f["total_xp"]),
    FQSensorDescription(key="xp_today", translation_key="family_xp_today", icon="mdi:star", native_unit_of_measurement="XP",
                        state_class=SensorStateClass.MEASUREMENT, value_fn=lambda f: f["xp_today"]),
    FQSensorDescription(key="running_games", translation_key="running_games", icon="mdi:dice-multiple",
                        state_class=SensorStateClass.MEASUREMENT, value_fn=lambda f: f["running_games"]),
    FQSensorDescription(key="open_votes", translation_key="open_votes", icon="mdi:vote",
                        state_class=SensorStateClass.MEASUREMENT, value_fn=lambda f: f["open_votes"],
                        attrs_fn=lambda f: {"polls": f["open_polls"]}),
    FQSensorDescription(key="pending_approvals", translation_key="pending_approvals", icon="mdi:check-decagram",
                        state_class=SensorStateClass.MEASUREMENT, value_fn=lambda f: f["pending_approvals"]),
)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data

    def make(data: dict) -> list[FamilyQuestEntity]:
        out: list[FamilyQuestEntity] = [FamilySensor(coordinator, d) for d in FAMILY_SENSORS]
        for child in data.get("children", []):
            out += [ChildSensor(coordinator, child["id"], d) for d in CHILD_SENSORS if d.exists_fn(child)]
            out += [BalanceSensor(coordinator, child["id"], acc) for acc in data.get("accounts", [])]
        return out

    entry.async_on_unload(track_new_entities(coordinator, async_add_entities, make))


class ChildSensor(FamilyQuestEntity, SensorEntity):
    entity_description: FQSensorDescription

    def __init__(self, coordinator, child_id: int, description: FQSensorDescription) -> None:
        super().__init__(coordinator, child_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.exists_fn(self.child)

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.child) if self.child else None

    @property
    def extra_state_attributes(self) -> dict | None:
        fn = self.entity_description.attrs_fn
        return fn(self.child) if fn and self.child else None


class FamilySensor(FamilyQuestEntity, SensorEntity):
    entity_description: FQSensorDescription

    def __init__(self, coordinator, description: FQSensorDescription) -> None:
        super().__init__(coordinator, None, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.family) if self.family else None

    @property
    def extra_state_attributes(self) -> dict | None:
        data = self.coordinator.data or {}
        if self.entity_description.key == "pending_approvals":
            return {"chores": data.get("pending_chores", []), "rewards": data.get("pending_rewards", [])}
        fn = self.entity_description.attrs_fn
        return fn(self.family) if fn and self.family else None


BUILTIN_ACCOUNTS = {"coins": "Coins", "internet": "Internet minutes"}   # default names (English source) of the add-on


class BalanceSensor(FamilyQuestEntity, SensorEntity):
    """Balance of a spendable account (coins, internet minutes, own accounts of the parents)."""

    _attr_translation_key = "balance"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:piggy-bank"

    def __init__(self, coordinator, child_id: int, account: dict) -> None:
        super().__init__(coordinator, child_id, f"balance_{account['key']}")
        self.account = account["key"]
        if BUILTIN_ACCOUNTS.get(self.account) == account["name"]:
            # the built-in accounts with their unchanged default name: in the language of Home Assistant
            self._attr_translation_key = f"balance_{self.account}"
        else:
            self._attr_translation_placeholders = {"account": account["name"]}
        self._attr_native_unit_of_measurement = account.get("unit") or None

    @property
    def available(self) -> bool:
        return super().available and self.account in (self.child.get("balances") or {})

    @property
    def native_value(self):
        return (self.child.get("balances") or {}).get(self.account)
