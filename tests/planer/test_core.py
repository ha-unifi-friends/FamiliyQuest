"""The ported Family Planer core (planner.py + announce.py) runs inside Family Quest on the hacompat layer."""
import asyncio

import pytest

from familyquest.db import Database
from familyquest.planer import hacompat
from familyquest.planer.planner import FamilyPlanner


def make(tmp_path, db=None):
    db = db or Database(":memory:")
    hass = hacompat.Hass(tmp_path, hacompat.StoreBackend(db))
    entry = hacompat.Entry(data={"persons": ["Lea", "Mia"], "modules": {"week": True, "lists": True}})
    return db, hass, FamilyPlanner(hass, entry)


async def _run(tmp_path):
    db, hass, p = make(tmp_path)
    await p.async_load()
    hass.set_started()
    await asyncio.sleep(0.05)
    assert set(p.data["persons"]) == {"lea", "mia"}
    wd = str(p.today().isoweekday())
    cid = await p.async_save_chore(None, {"title": "Tisch decken", "assign": {"lea": {wd: {"every": 1, "offset": 0, "window": 1}}}})
    await p.async_rollover()
    items = [i for i in p.data["items"].values() if i["chore_id"] == cid]
    assert len(items) == 1 and items[0]["person_id"] == "lea"
    await p.async_set_item(next(k for k, v in p.data["items"].items() if v["chore_id"] == cid), True)
    pts = p.points()
    assert pts["lea"]["balance"] > 0 and pts["mia"]["balance"] == 0
    snap = p.snapshot()
    assert snap["persons"] and "chores" in snap
    # default PIN must be changed before anything else
    assert p.pin_default
    token = await p.async_check_pin("123456")
    assert token
    await p.async_change_pin("123456", "4711")
    assert not p.pin_default
    p.async_shutdown()
    await p._store.async_save(p.data)
    # everything is stored in the Family Quest database and loads again
    _, hass2, p2 = make(tmp_path, db)
    await p2.async_load()
    assert p2.data["chores"][cid]["title"] == "Tisch decken"
    assert p2.points()["lea"]["balance"] == pts["lea"]["balance"]
    p2.async_shutdown()


def test_planner_core_runs_without_home_assistant(tmp_path):
    asyncio.run(_run(tmp_path))


async def _services(tmp_path):
    _, hass, p = make(tmp_path)
    calls = []

    async def caller(domain, service, data, ret):
        calls.append((domain, service, data))
        if (domain, service) == ("calendar", "get_events"):
            return {data["entity_id"]: {"events": [{"summary": "Skiferien", "start": "2026-02-07", "end": "2026-02-15"}]}}
        return {}
    hass.service_caller = caller
    hass.state_changed("calendar.lea", "off", {"friendly_name": "Lea"})
    await p.async_load()
    events = await p._events("calendar.lea", hacompat.dt_util.now(), hacompat.dt_util.now())
    assert events and calls[0][:2] == ("calendar", "get_events")
    assert await p._events("calendar.unknown", hacompat.dt_util.now(), hacompat.dt_util.now()) == []
    p.async_shutdown()


def test_service_calls_go_through_family_quest(tmp_path):
    asyncio.run(_services(tmp_path))
