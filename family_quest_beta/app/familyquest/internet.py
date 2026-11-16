"""Internet time managed by the app: budget in the account «internet», start/stop by the child,
one minute deducted per started minute, a UniFi firewall/traffic rule (a switch in Home Assistant)
allows or blocks the internet.

The rule is switched through `switcher(entity_id, on: bool) -> None` (set by the Home Assistant
service). Without Home Assistant the internet time cannot be started.
"""
from __future__ import annotations

import logging
import math
import threading
import re
from datetime import datetime, timedelta
from typing import Callable

from .db import Database, profile_settings
from .i18n import _t
from .rewards.engine import Rewards

log = logging.getLogger("familyquest.internet")
ACCOUNT = "internet"


class InternetError(ValueError):
    pass


# ---------------------------------------------------------------- plan: budget and block times per child
BLOCK_MODES = ("internet", "games", "app")     # what still works in a block time: the app / the app without games / nothing
_HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _hm(v, default: str) -> str:
    v = str(v or "").strip()
    if re.fullmatch(r"\d:[0-5]\d", v):
        v = "0" + v
    return v if _HM.match(v) else default


def clean_plan(p) -> dict | None:
    """{"budget": minutes, "period": "day"|"week", "reset": "HH:MM", "reset_day": 0–6 (Monday = 0),
    "days": {"5": minutes, …} (other budget on these weekdays, period «day»),
    "blocks": [{"days": [0…6], "from": "HH:MM", "to": "HH:MM", "mode": internet|games|app}]} – or None (no plan)."""
    if not isinstance(p, dict):
        return None
    def mins(v, hi):
        try:
            return max(0, min(hi, int(v)))
        except (TypeError, ValueError):
            return 0
    period = "week" if p.get("period") == "week" else "day"
    hi = 7 * 1440 if period == "week" else 1440
    days = {}
    if period == "day":
        for k, v in (p.get("days") or {}).items() if isinstance(p.get("days"), dict) else []:
            if str(k) in {str(i) for i in range(7)} and v not in (None, ""):
                days[str(k)] = mins(v, 1440)
    blocks = []
    for b in (p.get("blocks") or [])[:20] if isinstance(p.get("blocks"), list) else []:
        if not isinstance(b, dict):
            continue
        d = sorted({int(x) for x in b.get("days") or [] if str(x) in {str(i) for i in range(7)}})
        f, t = _hm(b.get("from"), ""), _hm(b.get("to"), "")
        if not d or not f or not t or f == t:
            raise InternetError("Block time: choose days and a time from – to")
        blocks.append({"days": d, "from": f, "to": t, "mode": b.get("mode") if b.get("mode") in BLOCK_MODES else "internet"})
    return {"budget": mins(p.get("budget"), hi), "period": period, "reset": _hm(p.get("reset"), "00:00"),
            "reset_day": mins(p.get("reset_day"), 6), "days": days, "blocks": blocks}


def period_of(plan: dict, now: datetime) -> tuple[datetime, datetime, int]:
    """(start, end, budget) of the budget period around `now`."""
    hh, mm = map(int, plan["reset"].split(":"))
    start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if plan["period"] == "week":
        start -= timedelta(days=(start.weekday() - plan["reset_day"]) % 7)
        if start > now:
            start -= timedelta(days=7)
        return start, start + timedelta(days=7), plan["budget"]
    if start > now:
        start -= timedelta(days=1)
    return start, start + timedelta(days=1), plan["days"].get(str(start.weekday()), plan["budget"])


def block_at(plan: dict | None, now: datetime) -> dict | None:
    """The block time active at `now` (a block over midnight belongs to the day it starts) with its end."""
    if not plan:
        return None
    t = now.strftime("%H:%M")
    for b in plan.get("blocks") or []:
        over = b["to"] <= b["from"]                    # e.g. 20:00 – 07:00
        today, yesterday = now.weekday() in b["days"], (now.weekday() - 1) % 7 in b["days"]
        if (not over and today and b["from"] <= t < b["to"]) or (over and today and t >= b["from"]):
            end_day = now + timedelta(days=1) if over else now
        elif over and yesterday and t < b["to"]:
            end_day = now
        else:
            continue
        hh, mm = map(int, b["to"].split(":"))
        return {**b, "until": end_day.replace(hour=hh, minute=mm, second=0, microsecond=0).isoformat(timespec="minutes")}
    return None


class InternetTime:
    def __init__(self, db: Database, rewards: Rewards):
        self.db = db
        self.rewards = rewards
        self.switcher: Callable[[str, bool], None] | None = None
        self.on_change: list[Callable[[int], None]] = []
        self.offline: Callable[[int], object] = lambda pid: None
        self.lock = threading.RLock()     # tick() runs from requests and from the 20-second loop – one at a time     # an OfflineTime of the calendar switches the internet off

    # ---------------------------------------------------------------- state
    @staticmethod
    def rule_of(profile: dict) -> tuple[str, bool]:
        s = profile_settings(profile)
        return (s.get("internet_rule") or "").strip(), bool(s.get("internet_rule_blocks", True))

    def managed(self, profile: dict) -> bool:
        return bool(self.rule_of(profile)[0])

    def balance(self, pid: int) -> float:
        return self.rewards.balance(pid, ACCOUNT)

    @staticmethod
    def plan_of(profile: dict) -> dict | None:
        try:
            return clean_plan(profile_settings(profile).get("internet_plan"))
        except InternetError:
            return None

    def allowance(self, profile: dict, now: datetime | None = None) -> dict | None:
        """The budget of the current period: {"total", "used", "left", "reset_at"} – None without a plan."""
        plan = self.plan_of(profile)
        if not plan or not plan["budget"] and not plan["days"]:
            return None
        start, end, total = period_of(plan, now or datetime.now())
        key = start.isoformat(timespec="minutes")
        row = self.db.q1("SELECT * FROM internet_allowance WHERE profile_id=?", profile["id"])
        used = row["used"] if row and row["period"] == key else 0
        return {"total": total, "used": used, "left": max(0, total - used), "reset_at": end.isoformat(timespec="minutes"), "period": key}

    def _use_allowance(self, profile: dict, minutes: int) -> None:
        a = self.allowance(profile)
        if not a or minutes <= 0:
            return
        self.db.x("""INSERT INTO internet_allowance(profile_id, period, used) VALUES(?,?,?)
                     ON CONFLICT(profile_id) DO UPDATE SET used=CASE WHEN period=excluded.period THEN used+excluded.used ELSE excluded.used END,
                     period=excluded.period""", profile["id"], a["period"], minutes)

    def available(self, profile: dict) -> float:
        """Budget of the period plus earned / bought minutes (account «internet»)."""
        a = self.allowance(profile)
        return (a["left"] if a else 0) + self.balance(profile["id"])

    def block(self, profile: dict, now: datetime | None = None) -> dict | None:
        """The block time of the child's plan active now (internet off; mode: what the app still allows)."""
        return block_at(self.plan_of(profile), now or datetime.now())

    def _session(self, pid: int) -> dict | None:
        return self.db.q1("SELECT * FROM internet_session WHERE profile_id=? AND running=1", pid)

    def state(self, profile: dict) -> dict | None:
        if not self.managed(profile):
            return None
        pid = profile["id"]
        ses = self._session(pid)
        left = self.available(profile)
        blk = self.block(profile)
        out = {"running": bool(ses), "minutes": max(0, math.floor(left + 1e-9)), "started_at": ses["started_at"] if ses else None,
               "can_start": self.switcher is not None and left >= 1 and not blk and not self.offline(pid),
               "budget": self.allowance(profile), "extra": max(0, math.floor(self.balance(pid) + 1e-9)),
               "block": blk}
        if ses:
            # the running minute is already paid; minutes not booked yet (tick pending) are subtracted
            unbooked = max(0, self._minutes_since(ses["started_at"]) - ses["deducted"])
            out["seconds_left"] = max(0, int((left - unbooked) * 60 + 60 - self._seconds_into_minute(ses["started_at"])))
        return out

    @staticmethod
    def _minutes_since(started: str) -> int:
        """Started minutes since the start (the first minute counts at once)."""
        secs = (datetime.now() - datetime.fromisoformat(started)).total_seconds()
        return int(secs // 60) + 1

    @staticmethod
    def _seconds_into_minute(started: str) -> int:
        return int((datetime.now() - datetime.fromisoformat(started)).total_seconds() % 60)

    def ensure_account(self) -> None:
        self.db.x("UPDATE account SET active=1 WHERE key=?", ACCOUNT)

    # ---------------------------------------------------------------- actions
    def _switch(self, profile: dict, allow: bool) -> None:
        rule, blocks = self.rule_of(profile)
        if not rule:
            raise InternetError("No firewall rule chosen for this profile")
        if self.switcher is None:
            raise InternetError("Home Assistant is not connected")
        self.switcher(rule, (not allow) if blocks else allow)

    def start(self, profile: dict) -> dict:
        pid = profile["id"]
        if self._session(pid):
            return self.state(profile)
        if self.offline(pid) or self.block(profile):
            raise InternetError("It is OfflineTime – the internet stays off")
        if self.available(profile) < 1:
            raise InternetError("No internet minutes left")
        self._switch(profile, True)
        with self.db.tx():
            self.db.x("DELETE FROM internet_session WHERE profile_id=?", pid)
            self.db.x("INSERT INTO internet_session(profile_id, started_at, deducted, running) VALUES(?,?,0,1)",
                      pid, datetime.now().isoformat(timespec="seconds"))
        self.tick(pid)                       # the first minute is booked at once
        self._changed(pid)
        return self.state(profile)

    def stop(self, profile: dict, reason: str = "") -> dict | None:
        pid = profile["id"]
        try:
            self._switch(profile, False)
        except InternetError as e:
            log.warning("cannot block internet for %s: %s", profile.get("name"), e)
        self.db.x("UPDATE internet_session SET running=0 WHERE profile_id=?", pid)
        self._changed(pid)
        return self.state(profile)

    def tick(self, only: int | None = None) -> None:
        """Book the used minutes of every running session; block when the budget is used up."""
        with self.lock:                   # two ticks at once would charge the same minute twice
            self._tick(only)

    def _tick(self, only: int | None = None) -> None:
        rows = self.db.q("SELECT * FROM internet_session WHERE running=1" + (" AND profile_id=?" if only else ""),
                         *([only] if only else []))
        for ses in rows:
            prof = self.db.q1("SELECT * FROM profile WHERE id=?", ses["profile_id"])
            if not prof or not self.managed(prof):
                self.db.x("UPDATE internet_session SET running=0 WHERE profile_id=?", ses["profile_id"])
                continue
            if self.offline(prof["id"]) or self.block(prof):     # OfflineTime / block time begins: the internet goes off
                self.stop(prof, "offline")
                continue
            due = self._minutes_since(ses["started_at"]) - ses["deducted"]
            a = self.allowance(prof)
            from_budget = a["left"] if a else 0
            left = from_budget + self.balance(prof["id"])
            take = min(due, math.floor(left + 1e-9))
            if take > 0:
                budget_part = min(take, from_budget)            # the budget of the period first, then earned minutes
                with self.db.tx():
                    self._use_allowance(prof, budget_part)
                    if take - budget_part > 0:
                        self.rewards.book(prof["id"], ACCOUNT, -float(take - budget_part), "internet_used", _t("Internet time"),
                                          f"internet:{ses['started_at']}")
                    self.db.x("UPDATE internet_session SET deducted=deducted+? WHERE profile_id=?", take, prof["id"])
                self._changed(prof["id"])
            if due > take:                   # the next started minute cannot be paid any more
                self.stop(prof, "empty")

    def block_all_idle(self) -> None:
        """At start: every managed profile without a running session gets the rule set to «blocked»."""
        for prof in self.db.q("SELECT * FROM profile WHERE archived=0"):
            if self.managed(prof) and not self._session(prof["id"]):
                try:
                    self._switch(prof, False)
                except InternetError:
                    pass

    def _changed(self, pid: int) -> None:
        for fn in self.on_change:
            try:
                fn(pid)
            except Exception:  # noqa: BLE001
                log.exception("listener failed")
