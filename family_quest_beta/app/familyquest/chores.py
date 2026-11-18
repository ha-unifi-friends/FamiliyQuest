"""Own chore plan (Ämtliplan): chores, who does what on which day, ticking off, parent confirmation, points.

Tasks are created lazily: asking for a day's chores creates the rows for that day (or week) if they
do not exist yet. Rotation is computed from the date, so it continues by itself without a scheduler.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Callable

from .db import Database
from .i18n import _t
from .rewards.engine import Rewards, today

log = logging.getLogger("familyquest.chores")

FREQUENCIES = ["daily", "weekdays", "weekly", "once"]
EPOCH = date(2024, 1, 1)            # a Monday – rotation counts days/weeks from here


class ChoreError(ValueError):
    pass


def _energy(v) -> int:
    """Energy bonus of a chore: battery segments (battery.py) charged when it is done – 0 to 20."""
    try:
        n = int(v or 0)
    except (TypeError, ValueError):
        raise ChoreError("Energy bonus: 0 to 20 segments") from None
    if not 0 <= n <= 20:
        raise ChoreError("Energy bonus: 0 to 20 segments")
    return n


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


class Chores:
    def __init__(self, db: Database, rewards: Rewards):
        self.db = db
        self.rewards = rewards
        self.on_pending: list[Callable[[dict], None]] = []     # push to parents
        self.on_change: list[Callable[[int], None]] = []       # sensors
        self.deals = None        # deals.Deals: a chore taken over in a deal (its coins, the transfer when it is approved)

    # ---------------------------------------------------------------- definitions
    def list(self, active_only: bool = False) -> list[dict]:
        rows = self.db.q("SELECT * FROM chore" + (" WHERE active=1" if active_only else "") + " ORDER BY sort, id")
        for r in rows:
            r["weekdays"] = json.loads(r["weekdays"] or "[]")
            r["profiles"] = json.loads(r["profiles"] or "[]")
        return rows

    def save(self, data: dict, chore_id: int | None = None) -> int:
        name = str(data.get("name", "")).strip()
        if not name:
            raise ChoreError("Name is required")
        freq = data.get("frequency", "daily")
        if freq not in FREQUENCIES:
            raise ChoreError("Unknown frequency")
        days = sorted({int(x) for x in data.get("weekdays") or [] if 0 <= int(x) <= 6})
        if freq == "weekdays" and not days:
            raise ChoreError("Choose at least one weekday")
        if freq == "once" and not data.get("date"):
            raise ChoreError("Choose a date")
        profiles = [int(x) for x in data.get("profiles") or []]
        if not profiles:
            raise ChoreError("Choose at least one child")
        vals = (name[:60], data.get("icon") or "🧹", float(data.get("points", 10)), data.get("account") or "coins", freq,
                json.dumps(days), data.get("date") or None, data.get("assign") if data.get("assign") in ("fixed", "rotate") else "fixed",
                data.get("rotate_every") if data.get("rotate_every") in ("day", "week") else "week", json.dumps(profiles),
                data.get("kind") if data.get("kind") in ("duty", "bonus") else "bonus", int(bool(data.get("confirm", True))),
                int(bool(data.get("active", True))), int(data.get("sort", 0)), _energy(data.get("energy")))
        if chore_id:
            self.db.x("""UPDATE chore SET name=?,icon=?,points=?,account=?,frequency=?,weekdays=?,date=?,assign=?,rotate_every=?,
                         profiles=?,kind=?,confirm=?,active=?,sort=?,energy=? WHERE id=?""", *vals, chore_id)
            # open tasks of today and later follow the new plan
            self.db.x("DELETE FROM chore_task WHERE chore_id=? AND status='open' AND period>=? AND deal_id IS NULL", chore_id,
                      monday(today()).isoformat() if freq == "weekly" else today().isoformat())
            return chore_id
        return self.db.x("""INSERT INTO chore(name,icon,points,account,frequency,weekdays,date,assign,rotate_every,profiles,kind,
                            confirm,active,sort,energy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", *vals)

    def delete(self, chore_id: int) -> None:
        with self.db.tx():
            self.db.x("UPDATE chore SET active=0 WHERE id=?", chore_id)
            self.db.x("DELETE FROM chore_task WHERE chore_id=? AND status='open'", chore_id)

    # ---------------------------------------------------------------- plan
    @staticmethod
    def due_on(ch: dict, d: date) -> str | None:
        """Period key if the chore is due on day d, else None."""
        f = ch["frequency"]
        if f == "daily":
            return d.isoformat()
        if f == "weekdays":
            return d.isoformat() if d.weekday() in ch["weekdays"] else None
        if f == "weekly":
            return monday(d).isoformat()
        if f == "once":
            return d.isoformat() if ch["date"] == d.isoformat() else None
        return None

    @staticmethod
    def assignees(ch: dict, d: date, kids: list[int]) -> list[int]:
        people = [p for p in ch["profiles"] if p in kids]
        if not people:
            return []
        if ch["assign"] != "rotate":
            return people
        n = (d - EPOCH).days if ch["rotate_every"] == "day" else (monday(d) - EPOCH).days // 7
        return [people[n % len(people)]]

    def _kids(self) -> list[int]:
        return [r["id"] for r in self.db.q("SELECT id FROM profile WHERE archived=0")]

    def ensure(self, d: date) -> None:
        kids = self._kids()
        for ch in self.list(active_only=True):
            period = self.due_on(ch, d)
            if not period:
                continue
            for pid in self.assignees(ch, d, kids):
                # not when somebody took this one over in a deal (deals.py: the row moved to the doer, from_id = pid)
                self.db.x("""INSERT OR IGNORE INTO chore_task(chore_id, profile_id, period) SELECT ?,?,? WHERE NOT EXISTS(
                             SELECT 1 FROM chore_task WHERE chore_id=? AND period=? AND from_id=?)""",
                          ch["id"], pid, period, ch["id"], period, pid)

    def tasks(self, d: date | None = None, pid: int | None = None) -> list[dict]:
        d = d or today()
        self.ensure(d)
        periods = [d.isoformat(), monday(d).isoformat()]
        sql = """SELECT t.*, c.name, c.icon, c.points, c.account, c.kind, c.confirm, c.frequency, c.energy, p.name AS profile_name,
                 f.name AS from_name FROM chore_task t JOIN chore c ON c.id=t.chore_id JOIN profile p ON p.id=t.profile_id
                 LEFT JOIN profile f ON f.id=t.from_id
                 WHERE c.active=1 AND ((c.frequency='weekly' AND t.period=?) OR (c.frequency!='weekly' AND t.period=?))"""
        args: list = [periods[1], periods[0]]
        if pid:
            sql += " AND t.profile_id=?"
            args.append(pid)
        return self.db.q(sql + " ORDER BY c.kind='bonus', c.sort, c.id", *args)

    def for_kid(self, pid: int) -> list[dict]:
        """Today's chores of a child in the shape the dashboard uses (same as Family Planer chores)."""
        return [{"uid": f"fq:{t['id']}", "summary": t["name"], "icon": t["icon"], "done": t["status"] == "done",
                 "pending": t["status"] == "pending", "redo": bool(t["redo"]), "points": t["points"], "account": t["account"],
                 "kind": t["kind"], "weekly": t["frequency"] == "weekly", "source": "fq", "energy": t["energy"] or 0,
                 "from": t["from_name"] if t["deal_id"] else None, "deal": t["deal_id"]} for t in self.tasks(pid=pid)]

    def week(self, start: date | None = None) -> dict:
        """Who does what on each day of a week (for the parent plan view)."""
        start = monday(start or today())
        kids = self._kids()
        days = []
        for i in range(7):
            d = start + timedelta(days=i)
            entries = []
            for ch in self.list(active_only=True):
                if ch["frequency"] == "weekly" and i > 0:
                    continue
                if self.due_on(ch, d):
                    entries.append({"chore": ch["id"], "name": ch["name"], "icon": ch["icon"], "weekly": ch["frequency"] == "weekly",
                                    "profiles": self.assignees(ch, d, kids)})
            days.append({"day": d.isoformat(), "entries": entries})
        return {"start": start.isoformat(), "days": days}

    # ---------------------------------------------------------------- ticking off
    def _task(self, task_id: int) -> dict | None:
        return self.db.q1("""SELECT t.*, c.name, c.icon, c.points, c.account, c.kind, c.confirm, c.frequency, p.name AS profile_name
                             FROM chore_task t JOIN chore c ON c.id=t.chore_id JOIN profile p ON p.id=t.profile_id WHERE t.id=?""", task_id)

    def mark_done(self, pid: int, task_id: int) -> dict:
        t = self._task(task_id)
        if not t or t["profile_id"] != pid:
            raise ChoreError("This chore is not yours")
        cur = today()
        if t["period"] not in (cur.isoformat(), monday(cur).isoformat()):
            raise ChoreError("This chore is not due today")
        if t["status"] != "open":
            return t
        if t["confirm"]:
            self.db.x("UPDATE chore_task SET status='pending', done_at=datetime('now','localtime') WHERE id=?", task_id)
            t = self._task(task_id)
            for fn in self.on_pending:
                try:
                    fn(t)
                except Exception:  # noqa: BLE001
                    log.exception("notify failed")
        else:
            self._complete(t)
            t = self._task(task_id)
        self._changed(pid)
        return t

    def decide(self, task_id: int, ok: bool) -> dict:
        t = self._task(task_id)
        if not t:
            raise ChoreError("Unknown chore")
        if t["status"] != "pending":
            return t
        if ok:
            self._complete(t)
        else:   # «Nochmals»: back to open
            self.db.x("UPDATE chore_task SET status='open', redo=1, done_at=NULL WHERE id=?", task_id)
            if t.get("deal_id") and self.deals:          # a chore taken over in a deal: the deal fails (deals.py)
                self.deals.chore_rejected(t)
        self._changed(t["profile_id"])
        return self._task(task_id)

    def _complete(self, t: dict) -> None:
        with self.db.tx():
            n = self.db.x("UPDATE chore_task SET status='done', confirmed_at=datetime('now','localtime') WHERE id=? AND status!='done'", t["id"])
            if not n:
                return
            # a chore taken over in a deal: its coins go to whom the deal says (XP always to who did it – deals.py)
            to = self.deals.reward_to(t) if t.get("deal_id") and self.deals and t["account"] != "xp" else t["profile_id"]
            if t["points"] and self.db.q1("SELECT 1 FROM account WHERE key=? AND active=1", t["account"]):
                self.rewards.book(to, t["account"], float(t["points"]), "chore_done", t["name"], f"chore:{t['id']}")
            self._week_bonus(t["profile_id"])
            if t.get("deal_id") and self.deals:
                self.deals.chore_done(t)                  # the share of the deal for this chore (same transaction)
        self.rewards.check_badges(t["profile_id"])
        self.rewards._notify("chore", t["profile_id"], {"chore": t["name"], "task": t["id"]})

    def _week_bonus(self, pid: int) -> None:
        """All chores of this week (so far planned for the whole week) done → bonus rule, once per week."""
        start = monday(today())
        for i in range(7):
            self.ensure(start + timedelta(days=i))
        end = (start + timedelta(days=6)).isoformat()
        rows = self.db.q("""SELECT t.status FROM chore_task t JOIN chore c ON c.id=t.chore_id
                            WHERE c.active=1 AND t.profile_id=? AND t.period>=? AND t.period<=?
                            AND t.deal_id IS NULL""", pid, start.isoformat(), end)       # chores taken over in a deal do not count
        if rows and all(r["status"] == "done" for r in rows):
            ref = f"chores-week:{start.isoformat()}"
            if not self.db.q1("SELECT 1 FROM ledger WHERE profile_id=? AND ref=?", pid, ref):
                self.rewards.emit(pid, "chores_week_all", ref=ref)

    def pending(self) -> list[dict]:
        return self.db.q("""SELECT t.*, c.name, c.icon, c.points, c.account, p.name AS profile_name FROM chore_task t
                            JOIN chore c ON c.id=t.chore_id JOIN profile p ON p.id=t.profile_id
                            WHERE t.status='pending' ORDER BY t.done_at""")

    def stats(self, pid: int) -> dict | None:
        """Reliability of the own chores: share done in this week so far (past and today)."""
        start = monday(today())
        for i in range(today().weekday() + 1):
            self.ensure(start + timedelta(days=i))
        rows = self.db.q("""SELECT t.status FROM chore_task t JOIN chore c ON c.id=t.chore_id
                            WHERE t.profile_id=? AND t.period>=? AND t.period<=?""", pid, start.isoformat(), today().isoformat())
        if not rows:
            return None
        done = sum(1 for r in rows if r["status"] == "done")
        open_today = sum(1 for t in self.tasks(pid=pid) if t["status"] != "done")
        return {"reliability": round(100 * done / len(rows)), "week_percent": round(100 * done / len(rows)),
                "open_today": open_today, "done_week": done, "total_week": len(rows)}

    def _changed(self, pid: int) -> None:
        for fn in self.on_change:
            try:
                fn(pid)
            except Exception:  # noqa: BLE001
                log.exception("listener failed")


TEXTS = [_t("This chore is not yours"), _t("This chore is not due today"), _t("Unknown chore"), _t("Name is required"),
         _t("Unknown frequency"), _t("Choose at least one weekday"), _t("Choose a date"), _t("Choose at least one child")]
