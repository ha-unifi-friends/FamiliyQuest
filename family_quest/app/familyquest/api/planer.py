"""Planer UI backend: a websocket in the Home Assistant message format plus a few Home Assistant pass-throughs.

The planer UI (taken over from Family Planer) talks to Home Assistant through `hass.connection` and a few
REST calls. In Family Quest the page gets a stand-in `hass` (web/planer/host.js) that sends everything here:

- family_planer/*           → the ported websocket commands (planer/websocket.py)
- todo/item/subscribe       → items of a to-do list, again on every change
- weather/subscribe_forecast→ daily forecast of a weather entity
- lovelace/config           → null (no Home Assistant dashboards here)
- REST /api/planer/ha/…     → states, calendar events, todo services (only these)
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import json

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..planer import hacompat, importer
from .auth import INGRESS_IP, KID_MAX_AGE, PARENT_MAX_AGE, Learner, Parent, app_of

log = logging.getLogger("familyquest.planer")
router = APIRouter(prefix="/api/planer")
TODO_SERVICES = {"add_item", "update_item", "remove_item", "remove_completed_items"}


def _host(fq):
    if not fq.planer_host:
        raise HTTPException(503, "Planer is not running")
    return fq.planer_host


@router.websocket("/ws")
async def planer_ws(websocket: WebSocket, token: str = "", parent: str = "") -> None:
    fq = websocket.app.state.fq
    settings = fq.settings
    if settings.ha_enabled and not settings.direct_access and (websocket.client and websocket.client.host) != INGRESS_IP:
        await websocket.close(code=4403)
        return
    # the same rules as for every request: allowed networks, a parent area only from the parent networks
    from .. import loginlog, netfilter
    ip = loginlog.client_ip(websocket)
    if netfilter.check(fq, ip, "/api/planer/ws"):
        await websocket.close(code=4403)
        return
    kid = fq.tokens.read(token, "kid", KID_MAX_AGE)
    par = fq.tokens.read(parent, "parent", PARENT_MAX_AGE)
    if par is not None and (netfilter.check(fq, ip, "/api/parent/") or fq.db.get_setting("parent_ha_only")
                            and (websocket.client and websocket.client.host) != INGRESS_IP):
        par = None                                       # a parent login from outside the parent networks: no admin
    if kid is None and par is None:
        await websocket.close(code=4401)
        return
    # a parent logged in in the app (own profile, PIN or Home Assistant user): changes without the planner's PIN –
    # under the same network rules as the parent area
    if par is None and kid is not None and fq.db.val("SELECT role FROM profile WHERE id=?", kid) == "parent" \
            and not netfilter.check(fq, ip, "/api/parent/") \
            and not (fq.db.get_setting("parent_ha_only") and (websocket.client and websocket.client.host) != INGRESS_IP):
        par = kid
    host = fq.planer_host
    if host is None:
        await websocket.close(code=4503)
        return
    await websocket.accept()
    lock = asyncio.Lock()

    async def send(msg: dict) -> None:
        async with lock:
            try:
                await websocket.send_json(msg)
            except Exception:  # noqa: BLE001 – connection already gone
                pass

    conn = hacompat.ActiveConnection(send, is_admin=par is not None)
    # a child ticks off only the chores of its own person in the planner
    bridge = getattr(host, "bridge", None)
    conn.fq_person = None if par is not None else (bridge.person_of(kid) if bridge else "")
    try:
        while True:
            msg = await websocket.receive_json()
            if not isinstance(msg, dict) or not isinstance(msg.get("id"), int):
                continue
            asyncio.create_task(_handle(fq, host, conn, msg))
    except WebSocketDisconnect:
        pass
    finally:
        conn.close()


async def _handle(fq, host, conn: hacompat.ActiveConnection, msg: dict) -> None:
    t = msg.get("type", "")
    mid = msg["id"]
    if t.startswith("family_planer/"):
        await hacompat.websocket_api.dispatch(host.hass, conn, msg)
    elif t == "todo/item/subscribe":
        await _todo_subscribe(host, conn, mid, str(msg.get("entity_id", "")))
    elif t == "weather/subscribe_forecast":
        await _weather_subscribe(host, conn, mid, str(msg.get("entity_id", "")), msg.get("forecast_type", "daily"))
    elif t == "lovelace/config":
        conn.send_result(mid, None)
    elif t == "unsubscribe_events" or t == "unsubscribe":
        sub = conn.subscriptions.pop(msg.get("subscription"), None)
        if sub:
            sub()
        conn.send_result(mid)
    else:
        conn.send_error(mid, "unknown_command", "Unknown command")


async def _todo_items(host, entity: str) -> list[dict]:
    try:
        res = await host.hass.services.async_call("todo", "get_items", {"entity_id": entity}, return_response=True)
    except Exception:  # noqa: BLE001
        return []
    return (res or {}).get(entity, {}).get("items", [])


async def _todo_subscribe(host, conn, mid: int, entity: str) -> None:
    if not re.fullmatch(r"todo\.[a-z0-9_]+", entity):
        conn.send_error(mid, "invalid_format", "todo entity expected")
        return

    async def push() -> None:
        conn.send_message({"id": mid, "type": "event", "event": {"items": await _todo_items(host, entity)}})

    unsub = hacompat.async_track_state_change_event(host.hass, [entity], lambda _ev: asyncio.ensure_future(push()))
    conn.subscriptions[mid] = unsub
    conn.send_result(mid)
    await push()


async def _weather_subscribe(host, conn, mid: int, entity: str, kind: str) -> None:
    if not re.fullmatch(r"weather\.[a-z0-9_]+", entity):
        conn.send_error(mid, "invalid_format", "weather entity expected")
        return

    async def push() -> None:
        try:
            res = await host.hass.services.async_call("weather", "get_forecasts", {"entity_id": entity, "type": kind},
                                                      return_response=True)
            fc = (res or {}).get(entity, {}).get("forecast", [])
        except Exception:  # noqa: BLE001
            fc = []
        conn.send_message({"id": mid, "type": "event", "event": {"type": kind, "forecast": fc}})

    async def loop() -> None:
        while True:
            await push()
            await asyncio.sleep(1800)
    task = asyncio.ensure_future(loop())
    conn.subscriptions[mid] = task.cancel
    conn.send_result(mid)


# ---------------------------------------------------------------- REST pass-throughs (learner or parent token)
# children see only what the planner shows them – never locations, addresses, cameras, alarms or locks
KID_DOMAINS = ("todo", "calendar", "sun", "weather", "person", "zone")
SECRET_ATTRS = {"latitude", "longitude", "gps_accuracy", "altitude", "course", "speed", "ip", "ip_address", "mac", "mac_address",
                "host_name", "hostname", "access_token", "entity_picture", "user_id", "device_trackers", "source", "source_type"}


def _used_by_planner(host, entity: str) -> bool:
    """An entity the planner itself is set up with (its lists, calendars …) – children may only touch those."""
    try:
        return entity in json.dumps(host.planner.data, default=str)
    except Exception:  # noqa: BLE001
        return False


@router.get("/ha/states")
def ha_states(request: Request, prof: dict = Learner) -> list[dict]:
    host = _host(app_of(request))
    if prof["role"] == "parent":
        return [{"entity_id": s.entity_id, "state": s.state, "attributes": s.attributes} for s in host.hass.states.async_all()]
    out = []
    for s in host.hass.states.async_all():
        if s.entity_id.split(".")[0] not in KID_DOMAINS:
            continue
        attrs = {k: v for k, v in (s.attributes or {}).items() if k not in SECRET_ATTRS}
        out.append({"entity_id": s.entity_id, "state": s.state, "attributes": attrs})
    return out


@router.get("/fq-calendars")
def fq_calendars(request: Request, prof: dict = Learner) -> list[dict]:
    """The family calendars for the «Termine» row of the planner: Family Quest's own calendar and the Home Assistant
    calendars chosen in the parent area (Calendar › Calendars from Home Assistant)."""
    fq = app_of(request)
    return [{"entity": "familyquest", "name": "Family Quest"}] + [{"entity": c} for c in fq.calendar.settings()["ha_calendars"]]


@router.get("/fq-events")
def fq_events(start: str, end: str, request: Request, prof: dict = Learner) -> list[dict]:
    """Family Quest's own events in the shape of the Home Assistant calendar API (all day: end date exclusive)."""
    from datetime import date, timedelta
    s, e = start[:10], end[:10]
    out = []
    for ev in app_of(request).calendar.own(s, e):
        if ev["all_day"]:
            last = date.fromisoformat((ev["end"] or ev["start"])[:10]) + timedelta(days=1)
            out.append({"summary": (ev.get("icon") + " " if ev.get("icon") else "") + ev["title"], "start": {"date": ev["start"][:10]}, "end": {"date": last.isoformat()}})
        else:
            out.append({"summary": (ev.get("icon") + " " if ev.get("icon") else "") + ev["title"], "start": {"dateTime": ev["start"]},
                        "end": {"dateTime": ev["end"] or ev["start"]}})
    return out


@router.get("/ha/calendars/{entity}")
async def ha_calendar(entity: str, start: str, end: str, request: Request, prof: dict = Learner) -> list[dict]:
    host = _host(app_of(request))
    if not re.fullmatch(r"calendar\.[a-z0-9_]+", entity):
        raise HTTPException(400, "calendar entity expected")
    if prof["role"] != "parent" and not _used_by_planner(host, entity) and entity not in app_of(request).calendar.settings()["ha_calendars"]:
        raise HTTPException(403, "This calendar is not part of the planner")
    try:
        res = await host.hass.services.async_call("calendar", "get_events",
                                                  {"entity_id": entity, "start_date_time": start, "end_date_time": end},
                                                  return_response=True)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from None
    out = []
    for ev in (res or {}).get(entity, {}).get("events", []):
        # the REST calendar API of Home Assistant returns start/end as {"dateTime"} or {"date"}
        def wrap(v: str) -> dict:
            return {"date": v} if v and len(v) == 10 else {"dateTime": v}
        out.append({**ev, "start": wrap(ev.get("start", "")), "end": wrap(ev.get("end", ""))})
    return out


class ServiceIn(BaseModel):
    domain: str
    service: str
    data: dict[str, Any] = {}


@router.post("/ha/service")
async def ha_service(body: ServiceIn, request: Request, prof: dict = Learner) -> dict:
    """Only the to-do services the smart lists use."""
    host = _host(app_of(request))
    if body.domain != "todo" or body.service not in TODO_SERVICES:
        raise HTTPException(403, "service not allowed")
    if not re.fullmatch(r"todo\.[a-z0-9_]+", str(body.data.get("entity_id", ""))):
        raise HTTPException(400, "todo entity expected")
    if prof["role"] != "parent" and not _used_by_planner(host, body.data["entity_id"]):
        raise HTTPException(403, "This list is not part of the planner")
    try:
        await host.hass.services.async_call("todo", body.service, body.data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from None
    return {"ok": True}


# ---------------------------------------------------------------- Etappe F: take over an existing Family Planer
@router.get("/import/sources")
def import_sources(request: Request, me: dict = Parent) -> dict:
    """Family Planer files found in the Home Assistant configuration (needs the map homeassistant_config)."""
    return {"config_visible": (importer.HA_CONFIG / ".storage").is_dir(), "sources": importer.sources()}


class ImportIn(BaseModel):
    source: str


@router.post("/import")
async def import_from_ha(body: ImportIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    try:
        data = importer.read_source(body.source)
        return await importer.run(fq, data, importer.HA_CONFIG / "family_planer")
    except (importer.ImportError_, ValueError) as e:
        raise HTTPException(400, str(e)) from None


@router.post("/import/file")
async def import_file(request: Request, file: UploadFile = File(...), me: dict = Parent) -> dict:
    """A store file (family_planer.<id> from /config/.storage) uploaded by a parent – photos are not included."""
    fq = app_of(request)
    raw = await file.read(50 * 1024 * 1024)
    try:
        data = importer.unwrap(json.loads(raw.decode("utf-8")))
        if request.query_params.get("check"):
            return {"summary": importer.summary(data)}
        return await importer.run(fq, data)
    except (importer.ImportError_, ValueError, UnicodeDecodeError) as e:
        raise HTTPException(400, str(e) if isinstance(e, importer.ImportError_) else "This is not a Family Planer file") from None


# ---------------------------------------------------------------- one chore plan: own chores → Planer
@router.post("/chores/take-over")
async def chores_take_over(request: Request, me: dict = Parent) -> dict:
    """Move the chores of the own chore plan into the Planer (see planer/fqchores.py)."""
    from ..planer import fqchores
    fq = app_of(request)
    _host(fq)
    return await fqchores.migrate(fq)


# ---------------------------------------------------------------- shopping lists from Home Assistant (e.g. Bring!)
class ShoppingIn(BaseModel):
    entity: str


@router.get("/shopping")
def shopping_lists(request: Request, me: dict = Parent) -> dict:
    """To-do lists of Home Assistant that can become a smart list of the planner – Bring! lists first."""
    fq = app_of(request)
    if not (fq.ha and fq.ha.connected):
        return {"ha": False, "lists": []}
    planner = fq.planer_host.planner if fq.planer_host else None
    linked = {lst.get("entity"): lid for lid, lst in ((planner.data or {}).get("lists") or {}).items()} if planner else {}
    lists = sorted(fq.ha.todo_lists(), key=lambda x: (x["platform"] != "bring", x["name"].lower()))
    return {"ha": True, "lists": [{**x, "bring": x["platform"] == "bring", "linked": x["entity_id"] in linked} for x in lists]}


@router.post("/shopping")
def shopping_link(body: ShoppingIn, request: Request, me: dict = Parent) -> dict:
    """Show a Home Assistant to-do list (e.g. the Bring! shopping list) as a smart list in the planner. Both stay the
    same list: what is ticked or added in the planner lands in Bring!, and the other way round."""
    fq = app_of(request)
    if not (fq.ha and fq.ha.connected and fq.planer_host):
        raise HTTPException(400, "Home Assistant is not connected")
    found = next((x for x in fq.ha.todo_lists() if x["entity_id"] == body.entity), None)
    if not found:
        raise HTTPException(404, "This list is not in Home Assistant")
    host = fq.planer_host
    if any(lst.get("entity") == body.entity for lst in (host.planner.data.get("lists") or {}).values()):
        return {"ok": True, "already": True}
    icon = "mdi:cart" if found["platform"] == "bring" else "mdi:format-list-checks"
    fut = asyncio.run_coroutine_threadsafe(host.planner.async_save_list(None, {"name": found["name"][:40], "entity": body.entity, "icon": icon}), host.loop)
    fut.result(15)
    return {"ok": True}
