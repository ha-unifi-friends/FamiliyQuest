"""Family Quest ⇄ Family Planer: one family, one point balance.

* Persons: every Family Quest profile is a Planer person (kids → "kid", parents → "adult"). Name, colour and role
  come from the profile. A person created in the Planer becomes a Family Quest profile (a parent profile without a
  PIN cannot log in until a PIN is set). Persons are managed in Family Quest: a Planer person whose profile still
  exists is created again.
* Points: the Planer points and the Family Quest account set in `planer_points_account` (default: coins) are kept
  equal. Every Planer booking (chores, bonuses, level-ups, rewards, corrections) is booked in Family Quest
  (ref fp:<entry id>), every booking of that account in Family Quest becomes a Planer correction (ref fq:<ledger id>).
  When a person is linked the first time, both balances are added up.
* Removed Planer bookings (a chore un-checked again, fair re-booking) are reversed in Family Quest. Bookings
  that disappear because the Planer folds entries older than a year into one carry entry are not.

State in the kv document `fq.planer_bridge`: {"links": {profile id: person id}, "seen": {entry id: [profile id, pts, ts]},
"fq_last": last Family Quest ledger id looked at, "held": {profile id: coins reserved in deals mirrored as held}}.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from . import rewards as prew
from .hacompat import StoreBackend, dt_util

log = logging.getLogger("familyquest.planer.bridge")
KEY = "fq.planer_bridge"          # document in the kv table
TRIM_DAYS = 399          # the Planer folds ledger entries older than 400 days (rewards.trim)
RESYNC_SECONDS = 60


class Bridge:
    def __init__(self, host) -> None:
        self.host = host
        self.fq = host.fq
        self.loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._again = False
        self._timer: asyncio.Task | None = None
        self.kv = StoreBackend(self.fq.db)
        self._lock = asyncio.Lock()

    # ---------------------------------------------------------------- scheduling
    def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.attach()
        self.fq.rewards.book_listeners.append(self._on_book)
        self._timer = asyncio.create_task(self._tick())
        self.request()

    def attach(self) -> None:
        """Listen to the (possibly new) planner object."""
        self.host.planner._listeners.add(self.request)

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
        try:
            self.fq.rewards.book_listeners.remove(self._on_book)
        except ValueError:
            pass

    def _on_book(self, account: str, ref: str) -> None:
        if account == self.account() and not str(ref or "").startswith("fp"):
            self.request()

    def request(self) -> None:
        """Ask for a sync – from any thread."""
        loop = self.loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._schedule()
        else:
            loop.call_soon_threadsafe(self._schedule)

    def _schedule(self) -> None:
        if self._task and not self._task.done():
            self._again = True
            return
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            self._again = False
            await asyncio.sleep(0.3)          # several changes in a row → one sync
            try:
                await self.sync()
            except Exception:  # noqa: BLE001 – never break the planner or learning
                log.exception("planer bridge sync failed")
            if not self._again:
                return

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(RESYNC_SECONDS)
            self.request()

    # ---------------------------------------------------------------- state
    def account(self) -> str:
        acc = self.fq.db.get_setting("planer_points_account", "coins")
        if not acc:
            return ""
        return acc if self.fq.db.q1("SELECT 1 FROM account WHERE key=?", acc) else ""

    def state(self) -> dict:
        st = self.kv.load(KEY) or {}
        st.setdefault("links", {})
        st.setdefault("seen", {})
        if "fq_last" not in st:
            st["fq_last"] = int(self.fq.db.val("SELECT MAX(id) FROM ledger", default=0) or 0)
        return st

    def person_of(self, profile_id: int) -> str | None:
        return self.state()["links"].get(str(profile_id))

    # ---------------------------------------------------------------- sync
    async def sync(self) -> bool:
        async with self._lock:
            return await self._sync()

    async def _sync(self) -> bool:
        planner = self.host.planner
        if not planner.data or getattr(planner, "closing", False):
            return False
        st = self.state()
        changed, new_links = await self._persons(planner, st)
        acc = self.account()
        if "account" in st and st["account"] != acc:
            # shared points switched on/off or to another account: continue from now on, nothing is booked twice
            st["seen"] = {e["id"]: [0, 0, e["ts"]] for e in planner.data["ledger"]}
            st["fq_last"] = int(self.fq.db.val("SELECT MAX(id) FROM ledger", default=0) or 0)
            new_links = []
        st["account"] = acc
        if acc:
            changed |= self._points(planner, st, acc, new_links)
        self.kv.save(KEY, st)
        if changed:
            planner._changed()
        return changed

    async def _persons(self, planner, st: dict) -> tuple[bool, list[str]]:
        persons: dict = planner.data["persons"]
        links: dict = st["links"]
        profiles = {str(p["id"]): p for p in self.fq.db.q("SELECT id, name, role, color FROM profile WHERE archived=0")}
        changed, new_links = False, []
        # profile removed in Family Quest → person removed in the Planer
        for prof_id, person in list(links.items()):
            if prof_id not in profiles:
                del links[prof_id]
                if person in persons:
                    await planner.async_remove_person(person)
                    changed = True
        linked = set(links.values())
        # every profile has a person: existing link, same name, or a new person
        for prof_id, p in profiles.items():
            person = links.get(prof_id)
            if person and person in persons:
                continue
            match = next((k for k, v in persons.items()
                          if k not in linked and v.get("name", "").strip().casefold() == p["name"].strip().casefold()), None)
            if match is None:
                match = planner._add_person(p["name"], color=p["color"])
            links[prof_id] = match
            linked.add(match)
            new_links.append(prof_id)
            changed = True
        # persons created in the Planer → Family Quest profiles
        for person, v in persons.items():
            if person in linked:
                continue
            role = "parent" if v.get("role") == "adult" else "kid"
            prof_id = self.fq.db.x("INSERT INTO profile(name, role, color) VALUES(?,?,?)",
                                   (v.get("name") or person)[:40], role, v.get("color") or "#4f8cff")
            if role == "kid":
                self.fq.packs.activate_defaults(prof_id)
            links[str(prof_id)] = person
            linked.add(person)
            new_links.append(str(prof_id))
            profiles[str(prof_id)] = {"id": prof_id, "name": v.get("name") or person, "role": role, "color": v.get("color")}
            log.info("profile %s created for planner person %s", prof_id, person)
        # name, colour, role from the profile
        for prof_id, person in links.items():
            p, v = profiles.get(prof_id), persons.get(person)
            if not p or v is None:
                continue
            want = {"name": p["name"], "color": p["color"] or v.get("color"), "role": "adult" if p["role"] == "parent" else "kid"}
            for k, val in want.items():
                if val and v.get(k) != val:
                    v[k] = val
                    changed = True
        return changed, new_links

    def _points(self, planner, st: dict, acc: str, new_links: list[str]) -> bool:
        ledger: list = planner.data["ledger"]
        links: dict = st["links"]
        owner = {person: int(prof) for prof, person in links.items()}
        seen: dict = st["seen"]
        now = dt_util.now()
        ts = now.isoformat()
        changed = False
        # first link of a person: add both balances up, older Planer entries count as booked
        for prof_id in new_links:
            person = links.get(prof_id)
            if not person:
                continue
            pid = int(prof_id)
            fq_before = self.fq.rewards.balance(pid, acc)
            fp_before = prew.balance(ledger, person)
            for e in ledger:
                if e["pid"] == person:
                    seen[e["id"]] = [pid, int(e["pts"]), e["ts"]]
            if fp_before:
                self.fq.rewards.book(pid, acc, fp_before, "planer", "Family Planer", f"fp:init:{person}")
            if round(fq_before):
                prew._add(ledger, person, round(fq_before), "adjust", f"fq:init:{pid}", "Family Quest", ts)
                changed = True
        # Planer → Family Quest
        present = set()
        for e in ledger:
            present.add(e["id"])
            ref = str(e.get("ref") or "")
            if e["id"] in seen or e.get("kind") == "carry" or ref.startswith("fq:") or e["pid"] not in owner:
                continue
            pid = owner[e["pid"]]
            pts = int(e["pts"])
            if pts:
                # chores count like chores of the own plan (badge «Helping hand»)
                event = "chore_done" if e.get("kind") == "chore" else "planer"
                self.fq.rewards.book(pid, acc, pts, event, _reason(e), f"fp:{e['id']}")
                if event == "chore_done":
                    self.fq.rewards.check_badges(pid)
            seen[e["id"]] = [pid, pts, e["ts"]]
        limit = (now - timedelta(days=TRIM_DAYS)).isoformat()
        for eid, (pid, pts, ets) in list(seen.items()):
            if eid in present:
                continue
            del seen[eid]
            if pts and ets >= limit and str(pid) in links:
                self.fq.rewards.book(pid, acc, -pts, "planer", "Family Planer ↩", f"fp-undo:{eid}")
        # Family Quest → Planer
        rows = self.fq.db.q("SELECT id, profile_id, amount, reason, event, ref FROM ledger WHERE id>? AND account=? ORDER BY id",
                            st["fq_last"], acc)
        for r in rows:
            st["fq_last"] = r["id"]
            if str(r["ref"] or "").startswith("fp"):
                continue
            person = links.get(str(r["profile_id"]))
            pts = round(r["amount"] or 0)
            if not person or not pts:
                continue
            prew._add(ledger, person, pts, "adjust", f"fq:{r['id']}", (r["reason"] or r["event"] or "Family Quest")[:60], ts)
            changed = True
        if rows:
            st["fq_last"] = max(st["fq_last"], rows[-1]["id"])
        # coins reserved in a deal (deals.py) cannot be spent in the Planer either: a correction mirrors the
        # reservation (balance minus reserved) and gives it back when the deal pays or ends
        held: dict = st.setdefault("held", {})
        for prof_id, person in links.items():
            want = round(self.fq.rewards.reserved(int(prof_id), acc))
            have = int(held.get(prof_id, 0))
            if want != have:
                st["held_n"] = int(st.get("held_n", 0)) + 1
                prew._add(ledger, person, have - want, "adjust", f"fq:held:{st['held_n']}", "Family Quest: deal 🔒", ts)
                held[prof_id] = want
                changed = True
        return changed


def _reason(e: dict) -> str:
    kind = e.get("kind", "")
    text = str(e.get("text") or "")
    label = {"chore": "Ämtli", "bonus": "Tagesbonus", "streak": "Serie", "reward": "Belohnung", "level": "Level"}.get(kind, "Planer")
    return f"{label}: {text}"[:80] if text else label
