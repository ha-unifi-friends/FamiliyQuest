"""Home Assistant integration: Family Planer adapter, sensors/events, reward actions,
approval notifications and learning reminders.

Runs inside the FastAPI event loop; the sync API handlers call into it through
`_sync()` (run_coroutine_threadsafe) with a short timeout, so a slow or missing
Home Assistant never blocks learning.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime

from ..db import profile_settings
from ..packs.schema import slug
from ..rewards.engine import today
from .client import HAClient, HAError

log = logging.getLogger("familyquest.ha")

# Texts that go straight to phones or speakers (no browser to translate them).
NOTIFY_TEXT = {
    "de": {"title": "Family Quest", "redeem": "{name} möchte «{reward}» einlösen ({cost}).", "ok": "OK", "no": "Nein",
           "remind": "{name}, dein Lernziel für heute wartet noch auf dich!",
           "chore": "{name} hat «{chore}» erledigt.", "again": "Nochmals",
           "chores_open": "{name}, deine Ämtli warten noch: {list}.",
           "sad": "{name} fühlt sich gerade traurig. Vielleicht magst du kurz nachfragen.",
           "feel": "{name}: «Heute fühle ich mich {text}»"},
    "fr": {"title": "Family Quest", "redeem": "{name} aimerait échanger « {reward} » ({cost}).", "ok": "OK", "no": "Non",
           "remind": "{name}, ton objectif d'apprentissage du jour t'attend encore !",
           "chore": "{name} a terminé « {chore} ».", "again": "À refaire",
           "chores_open": "{name}, tes tâches t'attendent encore : {list}.",
           "sad": "{name} se sent triste en ce moment. Tu pourrais peut-être lui demander comment ça va.",
           "feel": "{name} : « Aujourd'hui je me sens {text} »"},
    "it": {"title": "Family Quest", "redeem": "{name} vorrebbe riscattare «{reward}» ({cost}).", "ok": "OK", "no": "No",
           "remind": "{name}, il tuo obiettivo di oggi ti aspetta ancora!",
           "chore": "{name} ha finito «{chore}».", "again": "Da rifare",
           "chores_open": "{name}, le tue faccende ti aspettano ancora: {list}.",
           "sad": "{name} si sente triste in questo momento. Forse puoi chiedergli come sta.",
           "feel": "{name}: «Oggi mi sento {text}»"},
    "en": {"title": "Family Quest", "redeem": "{name} would like to redeem “{reward}” ({cost}).", "ok": "OK", "no": "No",
           "remind": "{name}, today's learning goal is still waiting for you!",
           "chore": "{name} has done “{chore}”.", "again": "Again",
           "chores_open": "{name}, your chores are still waiting: {list}.",
           "sad": "{name} is feeling sad right now. Maybe ask how they are doing.",
           "feel": "{name}: “Today I feel {text}”"},
}


class HAService:
    def __init__(self, fq, client: HAClient, loop: asyncio.AbstractEventLoop):
        self.fq = fq
        self.client = client
        self.px = getattr(getattr(fq, "settings", None), "entity_prefix", "family_quest")
        self.loop = loop
        self.persons: dict[str, dict] = {}            # planer person id → {name, chores, reliability, points}
        self.language = "de"
        self._dirty: set[int] = set()
        self._publish_task: asyncio.Task | None = None
        self._chore_cache: dict[str, tuple[float, list[dict]]] = {}
        self._reminded: set[tuple[int, str]] = set()
        client.subscribe("state_changed", self._on_state)
        client.subscribe("mobile_app_notification_action", self._on_action)
        client.on_connect.append(self._on_connect)
        fq.rewards.listeners.append(self._on_reward)
        fq.learning.listeners.append(self._on_learning)
        fq.shop.executor = self.execute
        fq.shop.on_pending.append(self._on_pending)
        fq.shop.on_change.append(self.profile_changed)
        fq.internet.switcher = self._switch_rule
        fq.internet.on_change.append(self.profile_changed)
        fq.chores.on_pending.append(self._on_chore_pending)
        fq.on_mood.append(self._on_mood)
        fq.chores.on_change.append(self.profile_changed)

    # ---------------------------------------------------------------- helpers
    @property
    def connected(self) -> bool:
        return self.client.connected.is_set()

    @property
    def planer_available(self) -> bool:
        return bool(self.persons)

    def _sync(self, coro, timeout: float = 8):
        if not self.connected:
            coro.close()
            raise HAError("not connected")
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def _soon(self, coro) -> None:
        def go():
            asyncio.create_task(self._guard(coro))
        self.loop.call_soon_threadsafe(go)

    @staticmethod
    async def _guard(coro) -> None:
        try:
            await coro
        except Exception as e:  # noqa: BLE001
            log.warning("Home Assistant call failed: %s", e)

    def _text(self) -> dict:
        return NOTIFY_TEXT.get(self.language[:2], NOTIFY_TEXT["en"])

    # ---------------------------------------------------------------- connect
    async def _on_connect(self) -> None:
        try:
            self.language = (await self.client.config()).get("language", "de") or "de"
        except Exception:  # noqa: BLE001
            pass
        if getattr(self.fq, "planer_host", None):
            await self.fq.planer_host.on_ha_connect(self.client)
        await self.refresh_planer()
        await self._seed_chores()
        # internet time: idle profiles blocked, running sessions continue (minutes of the downtime are booked)
        await asyncio.to_thread(self.fq.internet.block_all_idle)
        await asyncio.to_thread(self.fq.internet.tick)
        self.all_changed()
        if not getattr(self, "_ticker", None):
            self._ticker = asyncio.create_task(self._tick())

    async def refresh_planer(self) -> None:
        try:
            entities = await self.client.command({"type": "config/entity_registry/list"})
            devices = await self.client.command({"type": "config/device_registry/list"})
        except Exception as e:  # noqa: BLE001
            log.warning("registry not readable: %s", e)
            return
        dev_person: dict[str, tuple[str, str]] = {}
        for d in devices or []:
            for ident in d.get("identifiers") or []:
                if ident and ident[0] == "family_planer":
                    entry = (d.get("config_entries") or [""])[0]
                    pid = ident[1][len(entry) + 1:] if entry and ident[1].startswith(entry + "_") else ident[1]
                    dev_person[d["id"]] = (pid, d.get("name_by_user") or d.get("name") or pid)
        persons: dict[str, dict] = {}
        for e in entities or []:
            if e.get("platform") != "family_planer" or e.get("device_id") not in dev_person:
                continue
            pid, name = dev_person[e["device_id"]]
            p = persons.setdefault(pid, {"id": pid, "name": name})
            uid = e.get("unique_id") or ""
            key = uid.rsplit("_", 1)[-1] if uid else (e.get("translation_key") or "")
            domain = e["entity_id"].split(".", 1)[0]
            if domain == "todo":
                p["chores"] = e["entity_id"]
            elif key in ("reliability", "points"):
                p[key] = e["entity_id"]
        self.persons = persons
        log.info("Family Planer persons: %s", ", ".join(p["name"] for p in persons.values()) or "none")

    # ---------------------------------------------------------------- Family Planer
    def planer_persons(self) -> list[dict]:
        linked = {r["planer_person_id"]: r["name"] for r in self.fq.db.q(
            "SELECT planer_person_id, name FROM profile WHERE planer_person_id IS NOT NULL AND archived=0")}
        return [{**p, "linked_to": linked.get(p["id"])} for p in self.persons.values()]

    def _person(self, prof: dict) -> dict | None:
        pid = prof.get("planer_person_id")
        return self.persons.get(pid) if pid else None

    async def _items(self, entity_id: str) -> list[dict]:
        res = await self.client.command({"type": "todo/item/list", "entity_id": entity_id})
        return [{"uid": i.get("uid"), "summary": i.get("summary", ""), "done": i.get("status") == "completed",
                 "description": i.get("description") or ""} for i in (res or {}).get("items", [])]

    def chores(self, prof: dict) -> list[dict] | None:
        p = self._person(prof)
        if not p or not p.get("chores") or not self.connected:
            return None
        cached = self._chore_cache.get(p["chores"])
        if cached and time.time() - cached[0] < 15:
            return cached[1]
        try:
            items = self._sync(self._items(p["chores"]), 4)
        except Exception as e:  # noqa: BLE001
            log.warning("chores not readable: %s", e)
            # remember the failure for a while too: a slow Home Assistant must not make every start page wait
            self._chore_cache[p["chores"]] = (time.time(), cached[1] if cached else None)
            return cached[1] if cached else None
        self._chore_cache[p["chores"]] = (time.time(), items)
        return items

    def complete_chore(self, prof: dict, uid: str) -> bool:
        p = self._person(prof)
        if not p or not p.get("chores"):
            return False
        try:
            # only an open chore of this very person can be ticked off (no points for made-up ids)
            item = next((i for i in self._sync(self._items(p["chores"])) if i["uid"] == uid), None)
            if not item or item["done"]:
                return False
            self._sync(self.client.call("todo", "update_item", {"entity_id": p["chores"], "item": uid, "status": "completed"}))
        except Exception as e:  # noqa: BLE001
            log.warning("chore not updated: %s", e)
            return False
        self._chore_cache.pop(p["chores"], None)
        self._award_chore(prof["id"], uid, p, item["summary"])
        return True

    def _award_chore(self, profile_id: int, uid: str, person: dict, summary: str = "") -> None:
        n = self.fq.db.x("INSERT OR IGNORE INTO chore_seen(profile_id, uid, day) VALUES(?,?,?)",
                         profile_id, uid, today().isoformat())
        if not n:
            return
        self.fq.rewards.emit(profile_id, "chore_done", ref=f"chore:{uid}", ctx={"chore": summary})
        prof = self.fq.db.q1("SELECT name FROM profile WHERE id=?", profile_id) or {}
        self._soon(self.client.fire(f"{self.px}_aemtli_erledigt",
                                    {"profile": prof.get("name"), "profile_id": profile_id, "chore": summary, "uid": uid}))

    async def _seed_chores(self) -> None:
        """Chores already done at start are remembered without points (no double booking after a restart)."""
        for prof in self.fq.kids():
            p = self._person(prof)
            if not p or not p.get("chores"):
                continue
            try:
                for it in await self._items(p["chores"]):
                    if it["done"] and it["uid"]:
                        self.fq.db.x("INSERT OR IGNORE INTO chore_seen(profile_id, uid, day) VALUES(?,?,?)",
                                     prof["id"], it["uid"], today().isoformat())
            except Exception:  # noqa: BLE001
                pass

    async def _on_state(self, event: dict) -> None:
        if getattr(self.fq, "planer_host", None):
            self.fq.planer_host.on_state_event(event)
        eid = (event.get("data") or {}).get("entity_id", "")
        if not eid.startswith("todo."):
            return
        for prof in self.fq.kids():
            p = self._person(prof)
            if p and p.get("chores") == eid:
                self._chore_cache.pop(eid, None)
                try:
                    items = await self._items(eid)
                except Exception:  # noqa: BLE001
                    return
                for it in items:
                    if it["done"] and it["uid"]:
                        await asyncio.to_thread(self._award_chore, prof["id"], it["uid"], p, it["summary"])

    def chore_stats(self, prof: dict) -> dict | None:
        p = self._person(prof)
        if not p or not p.get("reliability") or not self.connected:
            return None
        cache = self.__dict__.setdefault("_stats_cache", {})
        hit = cache.get(p["reliability"])
        if hit and time.time() - hit[0] < 30:             # the family page asks for every child – at most every 30 s
            st = hit[1]
        else:
            try:
                st = self._sync(self.client.get_state(p["reliability"]), 4)
            except Exception:  # noqa: BLE001
                st = None
            cache[p["reliability"]] = (time.time(), st)
        if not st:
            return None
        a = st.get("attributes") or {}
        wt = a.get("week_total") or 0
        try:
            rel = float(st.get("state"))
        except (TypeError, ValueError):
            rel = None
        return {"reliability": rel, "open_today": a.get("open_today"), "done_today": a.get("done_today"),
                "streak": a.get("streak"), "week_percent": round(100 * (a.get("week_done") or 0) / wt) if wt else None}

    # ---------------------------------------------------------------- publishing sensors
    def profile_changed(self, pid: int) -> None:
        self._dirty.add(pid)
        self.loop.call_soon_threadsafe(self._schedule_publish)

    def all_changed(self) -> None:
        for k in self.fq.kids():
            self._dirty.add(k["id"])
        self.loop.call_soon_threadsafe(self._schedule_publish)

    def _schedule_publish(self) -> None:
        if self._publish_task is None or self._publish_task.done():
            self._publish_task = asyncio.create_task(self._publish_soon())

    async def _publish_soon(self) -> None:
        await asyncio.sleep(1.5)                       # debounce: a lesson books many small amounts
        while self._dirty:
            pid = self._dirty.pop()
            try:
                await self._publish(pid)
            except Exception as e:  # noqa: BLE001
                log.warning("publish failed: %s", e)

    async def _publish(self, pid: int) -> None:
        if not self.connected:
            return
        fq = self.fq
        prof = await asyncio.to_thread(fq.db.q1, "SELECT * FROM profile WHERE id=?", pid)
        if not prof or prof["role"] != "kid" or prof["archived"]:
            return
        s = slug(prof["name"]).replace("-", "_")
        data = await asyncio.to_thread(self._profile_numbers, prof)
        base = {"friendly_name": "", "profile": prof["name"], "icon": "mdi:school"}
        await self.client.set_state(f"sensor.{self.px}_{s}_xp_heute", int(data["xp_today"]),
                                    {**base, "friendly_name": f"{prof['name']} XP heute", "unit_of_measurement": "XP",
                                     "daily_goal": data["goal"], "state_class": "measurement", "icon": "mdi:star"})
        await self.client.set_state(f"sensor.{self.px}_{s}_streak", data["streak"],
                                    {**base, "friendly_name": f"{prof['name']} Streak", "unit_of_measurement": "d",
                                     "icon": "mdi:fire"})
        await self.client.set_state(f"sensor.{self.px}_{s}_level", data["level"]["level"],
                                    {**base, "friendly_name": f"{prof['name']} Level", "xp": data["level"]["xp"],
                                     "next_level_at": data["level"]["next"], "icon": "mdi:trophy"})
        for acc in data["accounts"]:
            if not acc["spendable"]:
                continue
            await self.client.set_state(f"sensor.{self.px}_{s}_{acc['key']}", round(data["balances"].get(acc["key"], 0), 1),
                                        {**base, "friendly_name": f"{prof['name']} {acc['name']}",
                                         "unit_of_measurement": acc["unit"] or acc["name"], "state_class": "measurement",
                                         "icon": "mdi:piggy-bank"})
        await self.client.set_state(f"sensor.{self.px}_{s}_aemtli_offen", len(data["chores_open"]),
                                    {**base, "friendly_name": f"{prof['name']} Ämtli offen", "icon": "mdi:broom",
                                     "chores": data["chores_open"]})
        if data["internet"] is not None:
            await self.client.set_state(f"sensor.{self.px}_{s}_internetminuten", data["internet"]["minutes"],
                                        {**base, "friendly_name": f"{prof['name']} Internetminuten", "unit_of_measurement": "min",
                                         "icon": "mdi:web-clock", "running": data["internet"]["running"]})
        await self.client.set_state(f"binary_sensor.{self.px}_{s}_tagesziel", "on" if data["goal_met"] else "off",
                                    {**base, "friendly_name": f"{prof['name']} Tagesziel", "icon": "mdi:bullseye-arrow"})

    def _profile_numbers(self, prof: dict) -> dict:
        r = self.fq.rewards
        pid = prof["id"]
        goal = int(profile_settings(prof)["daily_goal"])
        xp = r.xp_today(pid)
        open_chores = [t["name"] for t in self.fq.chores.tasks(pid=pid) if t["status"] != "done"]
        return {"internet": self.fq.internet.state(prof), "chores_open": open_chores, "xp_today": xp, "goal": goal, "goal_met": xp >= goal, "streak": r.streak(pid), "level": r.level(pid),
                "balances": r.balances(pid), "accounts": r.accounts()}

    # ---------------------------------------------------------------- listeners
    def _on_reward(self, kind: str, pid: int, data: dict) -> None:
        self.profile_changed(pid)
        if kind == "badge":
            prof = self.fq.db.q1("SELECT name FROM profile WHERE id=?", pid) or {}
            self._soon(self.client.fire(f"{self.px}_abzeichen", {"profile": prof.get("name"), "profile_id": pid, **data}))
        if kind == "chore":
            prof = self.fq.db.q1("SELECT name FROM profile WHERE id=?", pid) or {}
            self._soon(self.client.fire(f"{self.px}_aemtli_erledigt",
                                        {"profile": prof.get("name"), "profile_id": pid, "chore": data.get("chore"), "source": "family_quest"}))
        if kind == "ledger" and self.fq.db.get_setting("planer_points"):
            self._forward_points(pid, data)

    def _forward_points(self, pid: int, data: dict) -> None:
        """Option: book learning coins in the Family Planer too (never chores – they come from there)."""
        if data.get("event") in ("chore_done", "redeem", "refund", "manual"):
            return
        prof = self.fq.db.q1("SELECT * FROM profile WHERE id=?", pid)
        if not prof or not prof["planer_person_id"]:
            return
        factor = float(self.fq.db.get_setting("planer_points_factor") or 1)
        pts = round(sum(b["amount"] for b in data.get("bookings", []) if b.get("account") == "coins") * factor)
        if pts > 0:
            self._soon(self.client.call("family_planer", "add_points",
                                        {"person": prof["planer_person_id"], "points": pts, "reason": "Family Quest"}))

    def _on_learning(self, kind: str, pid: int, data: dict) -> None:
        self.profile_changed(pid)
        if kind == "lesson" and data.get("completed"):
            prof = self.fq.db.q1("SELECT name FROM profile WHERE id=?", pid) or {}
            self._soon(self.client.fire(f"{self.px}_lektion_fertig", {"profile": prof.get("name"), "profile_id": pid, **data}))

    # ---------------------------------------------------------------- shop actions
    def execute(self, kind: str, profile: dict, reward: dict, rid: int) -> tuple[bool, str]:
        cfg = reward.get("config") or {}
        if kind == "internet_minutes":
            entity = profile_settings(profile).get("internet_entity")
            if not entity:
                return False, "no internet budget entity set for this profile"
            minutes = float(cfg.get("minutes", reward["cost"]))
            st = self._sync(self.client.get_state(entity))
            if not st:
                return False, f"{entity} not found"
            try:
                cur = float(st["state"])
            except (TypeError, ValueError):
                cur = 0.0
            mx = st.get("attributes", {}).get("max")
            value = cur + minutes if mx is None else min(float(mx), cur + minutes)
            domain = entity.split(".", 1)[0]
            self._sync(self.client.call(domain, "set_value", {"entity_id": entity, "value": value}))
            return True, f"+{minutes:g} min"
        if kind == "planer_points":
            if not profile.get("planer_person_id"):
                return False, "profile is not linked to the Family Planer"
            self._sync(self.client.call("family_planer", "add_points", {
                "person": profile["planer_person_id"], "points": int(cfg.get("points", reward["cost"])),
                "reason": reward["name"]}))
            return True, ""
        if kind == "ha_script":
            script = cfg.get("script", "")
            if not re.fullmatch(r"script\.[a-z0-9_]+", script or ""):
                return False, "no script chosen"
            self._sync(self.client.call("script", "turn_on", {"entity_id": script, "variables": {
                "profile": profile["name"], "reward": reward["name"], "redemption": rid}}))
            return True, ""
        return False, f"unknown reward type {kind}"

    def _switch_rule(self, entity_id: str, on: bool) -> None:
        """Turn the firewall/traffic rule switch on or off (called from the internet time module)."""
        domain = entity_id.split(".", 1)[0]
        self._sync(self.client.call(domain, "turn_on" if on else "turn_off", {"entity_id": entity_id}))

    def _notify_services(self) -> list[str]:
        """Global notify service plus the one of every parent profile (each phone once)."""
        out = []
        cands = [self.fq.db.get_setting("notify_service") or ""]
        for r in self.fq.db.q("SELECT settings FROM profile WHERE role='parent' AND archived=0"):
            try:
                cands.append(json.loads(r["settings"] or "{}").get("notify_service") or "")
            except ValueError:
                pass
        for svc in cands:
            svc = svc.strip()
            if re.fullmatch(r"notify\.[a-z0-9_]+", svc) and svc not in out:
                out.append(svc)
        return out

    def _on_mood(self, prof: dict, sad: bool = True, text: str | None = None) -> None:
        """Quiet note to the parents – no buttons, the child does not see it."""
        t = self._text()
        parts = []
        if sad:
            parts.append(t["sad"].format(name=prof["name"]))
        if text:
            parts.append(t["feel"].format(name=prof["name"], text=text))
        msg = "\n".join(parts)
        if not msg:
            return
        self._soon(self.client.call("persistent_notification", "create",
                                    {"title": t["title"], "message": msg, "notification_id": f"{self.px}_mood_{prof['id']}"}))
        for svc in self._notify_services():
            self._soon(self.client.call("notify", svc.split(".", 1)[1], {"title": t["title"], "message": msg,
                                                                         "data": {"tag": f"{self.px}_mood_{prof['id']}"}}))
        self._soon(self.client.fire(f"{self.px}_stimmung", {"profile": prof["name"], "profile_id": prof["id"],
                                                             "mood": "sad" if sad else "", "text": text or ""}))

    def _on_chore_pending(self, task: dict) -> None:
        t = self._text()
        msg = t["chore"].format(name=task["profile_name"], chore=task["name"])
        self._soon(self.client.call("persistent_notification", "create",
                                    {"title": t["title"], "message": msg, "notification_id": f"{self.px}_chore_{task['id']}"}))
        for svc in self._notify_services():
            self._soon(self.client.call("notify", svc.split(".", 1)[1], {
                "title": t["title"], "message": msg,
                "data": {"tag": f"{self.px}_chore_{task['id']}", "actions": [
                    {"action": f"FQ_CHORE_OK_{task['id']}", "title": t["ok"]},
                    {"action": f"FQ_CHORE_AGAIN_{task['id']}", "title": t["again"]}]}}))

    def _on_pending(self, red: dict) -> None:
        t = self._text()
        cost = f"{red['cost']:g}"
        msg = t["redeem"].format(name=red["profile_name"], reward=red["name"], cost=cost)
        self._soon(self.client.call("persistent_notification", "create",
                                    {"title": t["title"], "message": msg, "notification_id": f"{self.px}_{red['id']}"}))
        for svc in self._notify_services():
            self._soon(self.client.call("notify", svc.split(".", 1)[1], {
                "title": t["title"], "message": msg,
                "data": {"tag": f"{self.px}_{red['id']}", "actions": [
                    {"action": f"FQ_APPROVE_{red['id']}", "title": t["ok"]},
                    {"action": f"FQ_REJECT_{red['id']}", "title": t["no"]}]}}))

    async def _on_action(self, event: dict) -> None:
        action = (event.get("data") or {}).get("action", "")
        c = re.fullmatch(r"FQ_CHORE_(OK|AGAIN)_(\d+)", action)
        if c:
            tid = int(c.group(2))
            await asyncio.to_thread(self.fq.chores.decide, tid, c.group(1) == "OK")
            await self._guard(self.client.call("persistent_notification", "dismiss", {"notification_id": f"{self.px}_chore_{tid}"}))
            return
        m = re.fullmatch(r"FQ_(APPROVE|REJECT)_(\d+)", action)
        if not m:
            return
        rid = int(m.group(2))
        await asyncio.to_thread(self.fq.shop.decide, rid, m.group(1) == "APPROVE")
        await self._guard(self.client.call("persistent_notification", "dismiss", {"notification_id": f"{self.px}_{rid}"}))

    # ---------------------------------------------------------------- reminders
    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(20)
            try:
                await asyncio.to_thread(self.fq.internet.tick)
            except Exception:  # noqa: BLE001
                log.exception("internet tick failed")
            try:
                await asyncio.to_thread(self._remind)
            except Exception:  # noqa: BLE001
                log.exception("reminder failed")

    def _remind(self) -> None:
        if not self.connected:
            return
        now = datetime.now().strftime("%H:%M")
        if now == getattr(self, "_last_remind", None):
            return
        self._last_remind = now
        if (self.fq.db.get_setting("chore_reminder_time") or "").strip() == now:
            self._remind_chores()
        at = (self.fq.db.get_setting("reminder_time") or "").strip()
        if not at or now != at:
            return
        t = self._text()
        for prof in self.fq.kids():
            key = (prof["id"], today().isoformat())
            if key in self._reminded:
                continue
            self._reminded.add(key)
            if self.fq.rewards.xp_today(prof["id"]) >= self.fq.rewards.daily_goal(prof["id"]):
                continue
            msg = t["remind"].format(name=prof["name"])
            if self.persons:
                self._soon(self.client.call("family_planer", "queue_announcement",
                                            {"message": msg, "key": f"{self.px}_{prof['id']}", "expires": 120}))
            self._soon(self.client.fire(f"{self.px}_erinnerung", {"profile": prof["name"], "profile_id": prof["id"], "message": msg}))

    def _remind_chores(self) -> None:
        t = self._text()
        for prof in self.fq.kids():
            key = (prof["id"], "chores-" + today().isoformat())
            if key in self._reminded:
                continue
            self._reminded.add(key)
            names = [x["name"] for x in self.fq.chores.tasks(pid=prof["id"]) if x["status"] == "open"]
            if not names:
                continue
            msg = t["chores_open"].format(name=prof["name"], list=", ".join(names))
            if self.persons:
                self._soon(self.client.call("family_planer", "queue_announcement",
                                            {"message": msg, "key": f"{self.px}_chores_{prof['id']}", "expires": 120}))
            self._soon(self.client.fire(f"{self.px}_aemtli_erinnerung",
                                        {"profile": prof["name"], "profile_id": prof["id"], "chores": names, "message": msg}))

    # ---------------------------------------------------------------- entity pickers for the parent UI
    def create_input_number(self, name: str, maximum: int = 600) -> str:
        """Create a helper for the internet minutes (like Settings › Helpers › Number in Home Assistant)."""
        res = self._sync(self.client.command({"type": "input_number/create", "name": name[:60], "min": 0, "max": maximum,
                                              "step": 1, "mode": "box", "unit_of_measurement": "min", "icon": "mdi:web-clock"}))
        return f"input_number.{(res or {}).get('id')}"

    def device_states(self, entity_ids: list[str]) -> list[dict]:
        """The devices a profile may control, in the shape the app shows (devices.view)."""
        from ..devices import view
        if not entity_ids:
            return []
        try:
            states = {s["entity_id"]: s for s in self._sync(self.client.states())}
        except Exception:  # noqa: BLE001
            states = {}
        return [view(states[e]) if e in states else {"entity_id": e, "domain": e.split(".")[0], "name": e, "state": None,
                                                       "on": False, "dimmable": False, "brightness": None, "available": False}
                for e in entity_ids]

    def control(self, entity_id: str, action: str, value: int | None = None) -> None:
        from ..devices import service_call
        domain, service, data = service_call(entity_id, action, value)
        self._sync(self.client.call(domain, service, data))

    def entities(self, domain: str) -> list[dict]:
        if domain not in ("input_number", "number", "script", "notify", "switch", "input_boolean", "light", "fan", "cover", "scene",
                          "calendar", "weather"):
            return []
        if domain == "notify":
            try:
                services = self._sync(self.client.http.get("/api/services"))
                services.raise_for_status()
                for s in services.json():
                    if s["domain"] == "notify":
                        return [{"entity_id": f"notify.{k}", "name": k} for k in sorted(s["services"])]
            except Exception:  # noqa: BLE001
                return []
            return []
        try:
            states = self._sync(self.client.states())
        except Exception:  # noqa: BLE001
            return []
        return [{"entity_id": s["entity_id"], "name": s.get("attributes", {}).get("friendly_name", s["entity_id"])}
                for s in states if s["entity_id"].startswith(domain + ".")]


    def calendar_events(self, entities: list[str], hours: int = 36) -> list[dict]:
        """Events of some calendars from today on (for the kiosk dashboard), sorted by start."""
        from datetime import datetime, timedelta
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.calendar_range(entities, start, datetime.now() + timedelta(hours=hours))[:30]

    def calendar_range(self, entities: list[str], start, end) -> list[dict]:
        """Events of Home Assistant calendars between start and end (datetimes). All-day events: end inclusive."""
        from datetime import date, timedelta
        res = self._sync(self.client.call_response("calendar", "get_events", {
            "entity_id": entities, "start_date_time": start.isoformat(), "end_date_time": end.isoformat()}), timeout=15) or {}
        out = []
        for eid, d in res.items():
            for e in (d or {}).get("events", []):
                st, en = str(e.get("start") or ""), str(e.get("end") or "")
                all_day = "T" not in st
                if all_day and en:          # Home Assistant: the end of an all-day event is the day after
                    try:
                        en = (date.fromisoformat(en[:10]) - timedelta(days=1)).isoformat()
                    except ValueError:
                        pass
                out.append({"title": e.get("summary") or "", "start": st, "end": en or st, "all_day": all_day, "calendar": eid,
                            "location": e.get("location") or ""})
        return sorted(out, key=lambda e: e["start"])

    def weather_forecast(self, entity: str) -> tuple[dict | None, list[dict]]:
        """State and forecast (hourly, else daily) of a weather entity."""
        state = self._sync(self.client.get_state(entity))
        forecast: list[dict] = []
        for kind in ("hourly", "daily"):
            try:
                res = self._sync(self.client.call_response("weather", "get_forecasts", {"entity_id": entity, "type": kind}), timeout=15) or {}
                forecast = (res.get(entity) or {}).get("forecast") or []
            except Exception:  # noqa: BLE001 – not every weather integration has every kind
                forecast = []
            if forecast:
                break
        return state, forecast

    # ---------------------------------------------------------------- areas (rooms) for the devices of a child
    def _registries(self) -> dict:
        """Area, device and entity registry (websocket), cached for 5 minutes."""
        import time
        cache = getattr(self, "_reg_cache", None)
        if cache and time.time() - cache[0] < 300:
            return cache[1]
        async def load():
            return {"areas": await self.client.command({"type": "config/area_registry/list"}),
                    "devices": await self.client.command({"type": "config/device_registry/list"}),
                    "entities": await self.client.command({"type": "config/entity_registry/list"})}
        reg = self._sync(load(), timeout=20)
        self._reg_cache = (time.time(), reg)
        return reg

    # ---------------------------------------------------------------- speakers for «Errate den Song»
    def media_players(self) -> list[dict]:
        try:
            states = self._sync(self.client.states())
        except Exception:  # noqa: BLE001
            return []
        return sorted(({"entity_id": s["entity_id"], "name": s.get("attributes", {}).get("friendly_name", s["entity_id"]), "state": s.get("state")}
                       for s in states if s["entity_id"].startswith("media_player.")), key=lambda x: x["name"].lower())

    def media(self, entity_id: str, action: str) -> None:
        """play | pause | next | shuffle – the speaker plays its own playlist, the app only steers it."""
        if action.startswith("volume:"):                 # volume:0.35 – the game leader turns it up or down
            service, data = "volume_set", {"volume_level": max(0.0, min(1.0, float(action.split(":", 1)[1])))}
        else:
            service, data = {"play": ("media_play", {}), "pause": ("media_pause", {}), "next": ("media_next_track", {}),
                             "shuffle": ("shuffle_set", {"shuffle": True})}[action]
        self._sync(self.client.call("media_player", service, {"entity_id": entity_id, **data}))

    def announce(self, entity_id: str, url: str) -> None:
        """A short sound as an announcement: the speaker (e.g. Sonos) lowers / pauses its playlist, plays the sound and
        goes on where it was – the queue stays as it is. Speakers without announcements are left alone."""
        self._sync(self.client.call("media_player", "play_media", {"entity_id": entity_id, "media_content_id": url,
                                                                   "media_content_type": "music", "announce": True}))

    def media_info(self, entity_id: str) -> dict:
        st = self._sync(self.client.get_state(entity_id)) or {}
        a = st.get("attributes", {})
        return {"state": st.get("state"), "title": a.get("media_title") or "", "artist": a.get("media_artist") or a.get("media_album_artist") or "",
                "album": a.get("media_album_name") or "", "picture": a.get("entity_picture") or "", "content_id": a.get("media_content_id") or "",
                "volume": a.get("volume_level")}

    def media_cover(self, picture: str) -> tuple[bytes, str] | None:
        """The cover of the song – through Home Assistant (its address and token stay on the server)."""
        if not picture:
            return None
        async def get():
            if picture.startswith("http"):
                import httpx
                async with httpx.AsyncClient(timeout=10) as c:
                    return await c.get(picture)
            return await self.client.http.get(picture)
        try:
            r = self._sync(get(), timeout=12)
        except Exception:  # noqa: BLE001
            return None
        if r.status_code != 200:
            return None
        return r.content, r.headers.get("content-type", "image/jpeg")

    def users(self) -> list[dict]:
        """Home Assistant users that are persons (person.* with a user) – the parents' logins for the parent area."""
        try:
            states = self._sync(self.client.states())
        except Exception:  # noqa: BLE001
            return []
        out = []
        for st in states:
            a = st.get("attributes", {})
            if st["entity_id"].startswith("person.") and a.get("user_id"):
                out.append({"id": a["user_id"], "name": a.get("friendly_name") or st["entity_id"][7:], "person": st["entity_id"]})
        return sorted(out, key=lambda u: u["name"].lower())

    def todo_lists(self) -> list[dict]:
        """All to-do lists of Home Assistant with the integration they come from (e.g. «bring» for Bring!)."""
        reg = self._registries()
        platform = {e["entity_id"]: e.get("platform") for e in reg["entities"] or []}
        try:
            states = self._sync(self.client.states())
        except Exception:  # noqa: BLE001
            return []
        return [{"entity_id": s["entity_id"], "name": s.get("attributes", {}).get("friendly_name", s["entity_id"]),
                 "platform": platform.get(s["entity_id"]) or "", "count": s.get("state")}
                for s in states if s["entity_id"].startswith("todo.")]

    def areas(self) -> list[dict]:
        reg = self._registries()
        return sorted(({"area_id": a["area_id"], "name": a.get("name") or a["area_id"]} for a in reg["areas"] or []),
                      key=lambda a: a["name"].lower())

    def area_entities(self, area_id: str) -> list[str]:
        """Entities of an area that a child may control (light, switch …) – the entity's own area wins over its device's."""
        from ..devices import DOMAINS
        reg = self._registries()
        dev_area = {d["id"]: d.get("area_id") for d in reg["devices"] or []}
        out = []
        for e in reg["entities"] or []:
            eid = e.get("entity_id", "")
            if eid.split(".", 1)[0] not in DOMAINS or e.get("disabled_by") or e.get("hidden_by") or e.get("entity_category"):
                continue
            if (e.get("area_id") or dev_area.get(e.get("device_id"))) == area_id:
                out.append(eid)
        return sorted(out)

def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False)
