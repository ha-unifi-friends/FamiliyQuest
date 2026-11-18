"""Base entity: one device per child plus one «Family» device; stable unique ids from the add-on's instance id."""
from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import FamilyQuestCoordinator


class FamilyQuestEntity(CoordinatorEntity[FamilyQuestCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: FamilyQuestCoordinator, child_id: int | None, key: str) -> None:
        super().__init__(coordinator)
        self.child_id = child_id
        inst = coordinator.instance
        self._attr_unique_id = f"{inst}_{'family' if child_id is None else child_id}_{key}"
        family = (DOMAIN, f"{inst}_family")
        version = (coordinator.data or {}).get("version")
        if child_id is None:
            self._attr_device_info = DeviceInfo(identifiers={family}, name="Family Quest", manufacturer=MANUFACTURER,
                                                model="Family", sw_version=version)
        else:
            child = coordinator.child(child_id) or {}
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{inst}_child_{child_id}")},
                                                name=child.get("name") or f"Child {child_id}", manufacturer=MANUFACTURER,
                                                model="Child", sw_version=version, via_device=family)

    @property
    def child(self) -> dict:
        return self.coordinator.child(self.child_id) or {}

    @property
    def family(self) -> dict:
        return (self.coordinator.data or {}).get("family") or {}

    @property
    def available(self) -> bool:
        return super().available and (self.child_id is None or self.coordinator.child(self.child_id) is not None)


def track_new_entities(coordinator: FamilyQuestCoordinator, add: Callable[[list[Entity]], None],
                       make: Callable[[dict], Iterable[FamilyQuestEntity]]) -> Callable[[], None]:
    """Add the entities of the current data now and those of new children / accounts after every update.
    Returns the function that stops listening (for entry.async_on_unload)."""
    known: set[str] = set()

    @callback
    def check() -> None:
        new = [e for e in make(coordinator.data or {}) if e.unique_id not in known]
        if new:
            known.update(e.unique_id for e in new)
            add(new)

    check()
    return coordinator.async_add_listener(check)
