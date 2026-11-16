"""Runs the Family Planer core inside Family Quest and connects it to Home Assistant."""
from __future__ import annotations

import asyncio
import logging

from datetime import timedelta

from . import hacompat
from .hacompat import dt_util
from .planner import FamilyPlanner

log = logging.getLogger("familyquest.planer")
START_WITHOUT_HA_AFTER = 90      # seconds: if Home Assistant does not answer, the planner starts anyway


class FQPlanner(FamilyPlanner):
    """The planner inside Family Quest: its parent PIN is the PIN of any Family Quest parent profile."""

    fq = None

    @property
    def pin_default(self) -> bool:
        return False

    async def async_check_pin(self, pin: str | None) -> str:
        from ..api.auth import check_pin
        now = dt_util.now()
        self._pin_fail = [t for t in self._pin_fail if now - t < timedelta(minutes=5)]
        if len(self._pin_fail) >= 5:
            return "locked"
        if pin:
            hashes = [r["pin_hash"] for r in self.fq.db.q(
                "SELECT pin_hash FROM profile WHERE role='parent' AND archived=0 AND pin_hash IS NOT NULL")]
            ok = await self.hass.async_add_executor_job(lambda: any(check_pin(pin, h) for h in hashes))
            if ok:
                self._pin_fail.clear()
                return "ok"
            self._pin_fail.append(now)
        return "wrong"

    async def async_change_pin(self, old: str, new: str) -> str:
        return "fq_pin"          # parent PINs are changed in Family Quest (parent area → Profiles)


class PlanerHost:
    def __init__(self, fq) -> None:
        self.fq = fq
        self.hass = hacompat.Hass(fq.settings.data_dir, hacompat.StoreBackend(fq.db))
        self.planner = self._new_planner()
        self._fallback: asyncio.Task | None = None
        self.hass.planer_host = self
        self.hass.config_entries.reload_cb = self.reload_saved
        from . import websocket
        if not hacompat.websocket_api.handlers:
            websocket.async_register_websocket(self.hass)

    def _new_planner(self) -> FQPlanner:
        planner = FQPlanner(self.hass, hacompat.Entry(data={"modules": {"week": True, "lists": True}}))
        planner.fq = self.fq
        return planner

    async def start(self, ha_expected: bool) -> None:
        self.loop = asyncio.get_running_loop()
        await self.planner.async_load()
        from .bridge import Bridge
        self.bridge = Bridge(self)
        self.bridge.start()
        if not ha_expected:
            self.hass.set_started()
        else:
            self._fallback = asyncio.create_task(self._start_later())

    async def _start_later(self) -> None:
        await asyncio.sleep(START_WITHOUT_HA_AFTER)
        if not self.hass.started:
            log.warning("Home Assistant not reachable – planner starts without calendars and lists")
            self.hass.set_started()

    async def on_ha_connect(self, client) -> None:
        """Mirror the states, language and time zone of Home Assistant, route service calls, then start."""
        async def call(domain: str, service: str, data: dict, ret: bool):
            if ret:
                return await client.call_response(domain, service, data)
            return await client.call(domain, service, data)
        self.hass.service_caller = call
        try:
            cfg = await client.config()
            self.hass.config.language = cfg.get("language") or "de"
            hacompat.dt_util.set_time_zone(cfg.get("time_zone"))
            states = await client.states()
        except Exception as e:  # noqa: BLE001
            log.warning("cannot read Home Assistant states: %s", e)
            states = []
        self.hass.states.clear()
        for s in states:
            self.hass.states.set(s["entity_id"], s.get("state"), s.get("attributes"))
        self.hass.set_started()

    def on_ha_disconnect(self) -> None:
        self.hass.service_caller = None

    def on_state_event(self, event: dict) -> None:
        data = event.get("data") or {}
        eid = data.get("entity_id")
        if not eid:
            return
        new = data.get("new_state")
        self.hass.state_changed(eid, new.get("state") if new else None, (new or {}).get("attributes"))

    # ---------------------------------------------------------------- chores for the Family Quest dashboard
    def chores_for(self, profile_id: int) -> list[dict]:
        """Today's Planer chores of a profile, in the shape of the dashboard (like the own chore plan)."""
        bridge = getattr(self, "bridge", None)
        person = bridge.person_of(profile_id) if bridge else None
        planner = self.planner
        if not person or not planner.data:
            return []
        from . import engine
        try:
            pts = planner.item_points()
        except Exception:  # noqa: BLE001
            pts = {}
        acc = bridge.account() or "coins"
        def split(title: str) -> tuple[str, str]:
            """«🛏️ Bett machen» → ("🛏️", "Bett machen") – the dashboard shows the icon on its own."""
            first, _, rest = title.partition(" ")
            if rest and first and not any(c.isalnum() for c in first):
                return first, rest
            return "🧹", title
        return [{"uid": f"fp:{iid}", "summary": split(it.get("title", ""))[1], "icon": split(it.get("title", ""))[0],
                 "done": bool(it.get("done")),
                 "pending": False, "redo": False, "points": pts.get(iid, 0), "account": acc, "kind": "duty",
                 "weekly": it.get("due", "") > it.get("start", ""), "source": "planer"}
                for iid, it in engine.active_items(planner.data["items"], person, planner.today())]

    def set_item(self, profile_id: int, item_id: str, done: bool = True) -> bool:
        """Tick off a Planer chore from the dashboard (any thread). Only the child's own chores."""
        bridge = getattr(self, "bridge", None)
        item = self.planner.data.get("items", {}).get(item_id)
        if not bridge or not item or item.get("person_id") != bridge.person_of(profile_id):
            return False
        fut = asyncio.run_coroutine_threadsafe(self.planner.async_set_item(item_id, done), self.loop)
        fut.result(10)
        return True

    # ---------------------------------------------------------------- to-dos from Family Quest (Wichteln)
    def add_todo(self, profile_id: int, title: str) -> str | None:
        """A to-do for the profile's Planer person (any thread); None when the profile has no person."""
        bridge = getattr(self, "bridge", None)
        person = bridge.person_of(profile_id) if bridge else None
        if not person or not self.planner.data or person not in self.planner.data.get("persons", {}) or not self.loop:
            return None
        fut = asyncio.run_coroutine_threadsafe(self.planner.async_save_todo(None, {"title": title, "person_id": person}, False), self.loop)
        return fut.result(10)

    def todo_done(self, todo_id: str) -> bool | None:
        t = (self.planner.data or {}).get("todos", {}).get(todo_id)
        return None if t is None else bool(t.get("done"))

    def set_todo(self, todo_id: str, done: bool) -> None:
        if self.todo_done(todo_id) is not None and self.todo_done(todo_id) != done and self.loop:
            asyncio.run_coroutine_threadsafe(self.planner.async_set_todo(todo_id, done), self.loop).result(10)

    def delete_todo(self, todo_id: str) -> None:
        if self.todo_done(todo_id) is not None and self.loop:
            asyncio.run_coroutine_threadsafe(self.planner.async_delete_todo(todo_id), self.loop).result(10)

    async def save_now(self) -> None:
        """Write the planner state to the database right away (before a backup)."""
        await self.planner._store.async_save(self.planner.data)

    async def reload_saved(self) -> None:
        """Settings that need new schedules (like the entry reload in Home Assistant): save, then reload."""
        await self.save_now()
        await self.reload()

    async def reload(self) -> None:
        """After a restore: drop the in-memory planner without saving and load it again from the database."""
        self.planner.closing = True
        self.planner.async_shutdown()
        self.planner._store._pending = None
        if self.planner._store._delay:
            self.planner._store._delay.cancel()
        self.planner = self._new_planner()
        started = self.hass.started
        self.hass.started = False
        await self.planner.async_load()
        if getattr(self, "bridge", None):
            self.bridge.attach()
            self.bridge.request()
        if started:
            self.hass.set_started()

    async def stop(self) -> None:
        if getattr(self, "bridge", None):
            self.bridge.stop()
        if self._fallback:
            self._fallback.cancel()
        self.planner.async_shutdown()
        await self.planner._store.async_save(self.planner.data)
