"""The small part of the Home Assistant API the Family Planer core uses – implemented for Family Quest.

planner.py and announce.py were written as a Home Assistant integration. Instead of rewriting them, this
module provides the same names (Store, dt_util, async_track_*, async_call_later, async_at_started,
async_dispatcher_send, slugify, persistent_notification, a `hass` object with states/services/config)
on top of Family Quest: storage in SQLite, timers with asyncio, services and states through the
Home Assistant connection of the app (REST/WebSocket). Without Home Assistant every service call raises
and every state is unknown – the planner already handles both (entities are optional there).
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

log = logging.getLogger("familyquest.planer")

STATE_ON = "on"
EventStateChangedData = dict
HomeAssistant = Any            # type alias for the original annotations
ConfigEntry = Any


def callback(fn):              # HA marks event-loop functions; nothing to do here
    return fn


class HomeAssistantError(Exception):
    pass


# ---------------------------------------------------------------- time
class _DtUtil:
    """dt_util replacement: everything in the local time zone of Home Assistant (or the container)."""

    def __init__(self) -> None:
        self.tz = None

    def set_time_zone(self, name: str | None) -> None:
        if not name:
            return
        try:
            from zoneinfo import ZoneInfo
            self.tz = ZoneInfo(name)
        except Exception:  # noqa: BLE001 – unknown zone: keep the container's local time
            log.warning("unknown time zone %s", name)

    def now(self) -> datetime:
        return datetime.now(self.tz) if self.tz else datetime.now().astimezone()

    def as_local(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.tz) if self.tz else value.astimezone()

    def start_of_local_day(self, value: date | datetime | None = None) -> datetime:
        if value is None:
            d = self.now().date()
        elif isinstance(value, datetime):
            d = self.as_local(value).date()
        else:
            d = value
        start = datetime(d.year, d.month, d.day)
        return start.replace(tzinfo=self.tz) if self.tz else start.astimezone()

    def parse_datetime(self, value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None


dt_util = _DtUtil()


def slugify(text: str | None, *, separator: str = "_") -> str:
    """Like homeassistant.util.slugify: ASCII, lower case, separator between words."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", separator, t).strip(separator).lower()
    return t or "unknown"


# ---------------------------------------------------------------- states, services, config
@dataclass
class State:
    entity_id: str
    state: str
    attributes: dict = field(default_factory=dict)


@dataclass
class Event:
    data: dict


class _States:
    def __init__(self) -> None:
        self._s: dict[str, State] = {}

    def get(self, entity_id: str | None) -> State | None:
        return self._s.get(entity_id or "")

    def async_all(self, domain: str | None = None) -> list[State]:
        return [s for s in self._s.values() if not domain or s.entity_id.startswith(domain + ".")]

    def set(self, entity_id: str, state: str | None, attributes: dict | None = None) -> tuple[State | None, State | None]:
        old = self._s.get(entity_id)
        if state is None:
            self._s.pop(entity_id, None)
            return old, None
        new = State(entity_id, str(state), dict(attributes or {}))
        self._s[entity_id] = new
        return old, new

    def clear(self) -> None:
        self._s.clear()


class _Services:
    def __init__(self, hass: "Hass") -> None:
        self.hass = hass

    async def async_call(self, domain: str, service: str, data: dict | None = None, blocking: bool = False,
                         return_response: bool = False, **_: Any) -> Any:
        caller = self.hass.service_caller
        if caller is None:
            raise HomeAssistantError("Home Assistant is not connected")
        res = await caller(domain, service, data or {}, return_response)
        return res if return_response else None


class _Config:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.language = "de"
        self.time_zone = None

    def path(self, *parts: str) -> str:
        return str(self.base.joinpath(*parts))


class Hass:
    """What planner.py and announce.py see as `hass`."""

    def __init__(self, data_dir: Path, store_backend: "StoreBackend") -> None:
        self.states = _States()
        self.services = _Services(self)
        self.config = _Config(data_dir)
        self.store_backend = store_backend
        # (domain, service, data, return_response) -> response; set by the Home Assistant service of the app
        self.service_caller: Callable[[str, str, dict, bool], Awaitable[Any]] | None = None
        self.started = False
        self._started_cbs: list[Callable] = []
        self._state_listeners: list[tuple[set[str], Callable]] = []
        self._signals: dict[str, list[Callable]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self.config_entries = _ConfigEntries()
        self.planer_host = None        # set by PlanerHost (get_planner)

    # -- loop helpers
    def async_create_task(self, coro: Awaitable, *_: Any, **__: Any) -> asyncio.Task:
        return asyncio.ensure_future(coro)

    async def async_add_executor_job(self, fn: Callable, *args: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(None, fn, *args)

    # -- start
    def set_started(self) -> None:
        if self.started:
            return
        self.started = True
        cbs, self._started_cbs = self._started_cbs, []
        for cb in cbs:
            _run_cb(cb, self)

    # -- states (fed by the app's Home Assistant connection)
    def state_changed(self, entity_id: str, state: str | None, attributes: dict | None = None) -> None:
        old, new = self.states.set(entity_id, state, attributes)
        if old is not None and new is not None and old.state == new.state and old.attributes == new.attributes:
            return
        ev = Event({"entity_id": entity_id, "old_state": old, "new_state": new})
        for ids, cb in list(self._state_listeners):
            if entity_id in ids:
                _run_cb(cb, ev)

    # -- dispatcher
    def connect(self, signal: str, cb: Callable) -> Callable[[], None]:
        self._signals.setdefault(signal, []).append(cb)
        return lambda: self._signals.get(signal, []).remove(cb) if cb in self._signals.get(signal, []) else None

    def dispatch(self, signal: str, *args: Any) -> None:
        for cb in list(self._signals.get(signal, [])):
            _run_cb(cb, *args)


def _run_cb(cb: Callable, *args: Any) -> None:
    try:
        res = cb(*args)
        if inspect.isawaitable(res):
            asyncio.ensure_future(res)
    except Exception:  # noqa: BLE001 – one broken callback must not stop the others
        log.exception("callback failed")


# ---------------------------------------------------------------- timers and listeners
def _task(coro: Awaitable) -> Callable[[], None]:
    t = asyncio.ensure_future(coro)
    return t.cancel


def async_at_started(hass: Hass, cb: Callable) -> Callable[[], None]:
    if hass.started:
        asyncio.get_running_loop().call_soon(_run_cb, cb, hass)
        return lambda: None
    hass._started_cbs.append(cb)
    return lambda: cb in hass._started_cbs and hass._started_cbs.remove(cb)


def async_track_time_change(hass: Hass, cb: Callable, hour: int | None = None, minute: int | None = None,
                            second: int | None = 0) -> Callable[[], None]:
    async def loop() -> None:
        while True:
            now = dt_util.now()
            nxt = now.replace(microsecond=0, second=second or 0)
            if minute is not None:
                nxt = nxt.replace(minute=minute)
            if hour is not None:
                nxt = nxt.replace(hour=hour)
            step = timedelta(days=1) if hour is not None else timedelta(hours=1) if minute is not None else timedelta(minutes=1)
            while nxt <= now:
                nxt += step
            await asyncio.sleep((nxt - now).total_seconds())
            _run_cb(cb, dt_util.now())
    return _task(loop())


def async_track_time_interval(hass: Hass, cb: Callable, interval: timedelta, **_: Any) -> Callable[[], None]:
    async def loop() -> None:
        while True:
            await asyncio.sleep(interval.total_seconds())
            _run_cb(cb, dt_util.now())
    return _task(loop())


def async_track_point_in_time(hass: Hass, cb: Callable, when: datetime) -> Callable[[], None]:
    async def once() -> None:
        await asyncio.sleep(max(0.0, (when - dt_util.now()).total_seconds()))
        _run_cb(cb, dt_util.now())
    return _task(once())


def async_call_later(hass: Hass, delay: float | timedelta, cb: Callable) -> Callable[[], None]:
    secs = delay.total_seconds() if isinstance(delay, timedelta) else float(delay)

    async def once() -> None:
        await asyncio.sleep(secs)
        _run_cb(cb, dt_util.now())
    return _task(once())


def async_track_state_change_event(hass: Hass, entity_ids: str | list[str], cb: Callable) -> Callable[[], None]:
    ids = {entity_ids} if isinstance(entity_ids, str) else set(entity_ids)
    entry = (ids, cb)
    hass._state_listeners.append(entry)
    return lambda: entry in hass._state_listeners and hass._state_listeners.remove(entry)


def async_dispatcher_send(hass: Hass, signal: str, *args: Any) -> None:
    hass.dispatch(signal, *args)


# ---------------------------------------------------------------- storage
class StoreBackend:
    """Key/value JSON documents in the Family Quest database (table kv)."""

    def __init__(self, db) -> None:
        self.db = db

    def load(self, key: str) -> Any:
        row = self.db.q1("SELECT value FROM kv WHERE key=?", key)
        return json.loads(row["value"]) if row else None

    def save(self, key: str, data: Any) -> None:
        self.db.x("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  key, json.dumps(data, ensure_ascii=False))


class Store:
    def __init__(self, hass: Hass, version: int, key: str) -> None:
        self.hass, self.version, self.key = hass, version, key
        self._delay: asyncio.TimerHandle | None = None
        self._pending: Callable[[], Any] | None = None

    async def async_load(self) -> Any:
        return await asyncio.to_thread(self.hass.store_backend.load, self.key)

    async def async_save(self, data: Any) -> None:
        if self._delay:
            self._delay.cancel()
            self._delay = None
        self._pending = None
        await asyncio.to_thread(self.hass.store_backend.save, self.key, data)

    def async_delay_save(self, data_fn: Callable[[], Any], delay: float = 0) -> None:
        self._pending = data_fn
        if self._delay:
            self._delay.cancel()
        loop = asyncio.get_running_loop()
        self._delay = loop.call_later(delay, lambda: asyncio.ensure_future(self._flush()))

    async def _flush(self) -> None:
        fn, self._pending, self._delay = self._pending, None, None
        if fn is not None:
            await asyncio.to_thread(self.hass.store_backend.save, self.key, fn())

    async def async_flush(self) -> None:
        if self._delay:
            self._delay.cancel()
        await self._flush()


# ---------------------------------------------------------------- persistent notifications
class _PersistentNotification:
    @staticmethod
    def async_create(hass: Hass, message: str, title: str | None = None, notification_id: str | None = None) -> None:
        async def go() -> None:
            try:
                await hass.services.async_call("persistent_notification", "create",
                                               {"message": message, "title": title or "Family Quest",
                                                **({"notification_id": notification_id} if notification_id else {})})
            except Exception as e:  # noqa: BLE001
                log.debug("notification not sent: %s", e)
        hass.async_create_task(go())


persistent_notification = _PersistentNotification()


@dataclass
class Entry:
    """Stand-in for the config entry of the integration."""
    entry_id: str = "familyquest"
    title: str = "Family Quest"
    data: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)


# ---------------------------------------------------------------- websocket_api (for websocket.py)
class _WsUser:
    def __init__(self, is_admin: bool) -> None:
        self.is_admin = is_admin


class ActiveConnection:
    """One browser connection of the planer UI (HA websocket message format)."""

    def __init__(self, send: Callable[[dict], Awaitable[None]], is_admin: bool = False) -> None:
        self._send = send
        self.user = _WsUser(is_admin)
        self.subscriptions: dict[int, Callable[[], None]] = {}

    def send_message(self, msg: dict) -> None:
        asyncio.ensure_future(self._send(msg))

    def send_result(self, msg_id: int, result: Any = None) -> None:
        self.send_message({"id": msg_id, "type": "result", "success": True, "result": result})

    def send_error(self, msg_id: int, code: str, message: str) -> None:
        self.send_message({"id": msg_id, "type": "result", "success": False, "error": {"code": code, "message": message}})

    def close(self) -> None:
        for unsub in self.subscriptions.values():
            try:
                unsub()
            except Exception:  # noqa: BLE001
                pass
        self.subscriptions.clear()


class _WebsocketApi:
    ERR_INVALID_FORMAT = "invalid_format"
    ERR_NOT_FOUND = "not_found"
    ERR_UNAUTHORIZED = "unauthorized"
    ERR_UNKNOWN_COMMAND = "unknown_command"
    ActiveConnection = ActiveConnection

    def __init__(self) -> None:
        self.handlers: dict[str, tuple[Callable, Any]] = {}

    @staticmethod
    def websocket_command(schema: dict):
        def deco(fn):
            import voluptuous as vol
            fn._ws_type = schema[next(k for k in schema if str(k) == "type")]
            fn._ws_schema = vol.Schema({vol.Required("id"): int, **schema}, extra=vol.REMOVE_EXTRA)
            return fn
        return deco

    @staticmethod
    def async_response(fn):
        fn._ws_async = True
        return fn

    @staticmethod
    def require_admin(fn):
        if inspect.iscoroutinefunction(fn) or getattr(fn, "_ws_async", False):
            async def wrapped(hass, connection, msg):
                if not connection.user.is_admin:
                    connection.send_error(msg["id"], "unauthorized", "Only administrators may do this")
                    return
                return await fn(hass, connection, msg)
        else:
            def wrapped(hass, connection, msg):
                if not connection.user.is_admin:
                    connection.send_error(msg["id"], "unauthorized", "Only administrators may do this")
                    return
                return fn(hass, connection, msg)
        for attr in ("_ws_type", "_ws_schema", "_ws_async"):
            if hasattr(fn, attr):
                setattr(wrapped, attr, getattr(fn, attr))
        return wrapped

    @staticmethod
    def event_message(msg_id: int, event: Any) -> dict:
        return {"id": msg_id, "type": "event", "event": event}

    def async_register_command(self, hass: Any, handler: Callable) -> None:
        self.handlers[handler._ws_type] = (handler, handler._ws_schema)

    async def dispatch(self, hass: Any, connection: ActiveConnection, msg: dict) -> None:
        import voluptuous as vol
        mid = msg.get("id")
        entry = self.handlers.get(msg.get("type", ""))
        if entry is None:
            connection.send_error(mid, self.ERR_UNKNOWN_COMMAND, "Unknown command")
            return
        handler, schema = entry
        try:
            msg = schema(msg)
        except vol.Invalid as e:
            connection.send_error(mid, self.ERR_INVALID_FORMAT, str(e))
            return
        try:
            res = handler(hass, connection, msg)
            if inspect.isawaitable(res):
                await res
        except Exception as e:  # noqa: BLE001
            log.exception("planer command %s failed", msg.get("type"))
            connection.send_error(mid, "unknown_error", str(e))


websocket_api = _WebsocketApi()


class _ConfigEntries:
    """hass.config_entries: only the reload after some settings is needed."""

    def __init__(self) -> None:
        self.reload_cb: Callable[[], Awaitable[None]] | None = None

    def async_schedule_reload(self, _entry_id: str) -> None:
        if self.reload_cb:
            asyncio.ensure_future(self.reload_cb())
