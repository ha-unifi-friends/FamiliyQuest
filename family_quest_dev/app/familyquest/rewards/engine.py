"""Reward module: accounts, rules (event → amount → account), streak, levels, badges.

`Rewards.emit(profile_id, event)` is the single entry point: it books every matching
active rule into the ledger (respecting the daily limit), keeps the daily XP, checks the
daily goal, streak milestones and badges, and notifies listeners (Home Assistant).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Callable

from ..db import Database, profile_settings
from ..i18n import _t

log = logging.getLogger("familyquest.rewards")

# Badges: id → (English name, icon, description)
BADGES: dict[str, tuple[str, str, str]] = {
    # id: (name, icon, how to get it – written as a tip for the child)
    "first_lesson": (_t("First lesson"), "🎒", _t("Finish your first lesson")),
    "ten_lessons": (_t("Busy bee"), "🐝", _t("Finish 10 lessons")),
    "quiz_ace": (_t("Quiz ace"), "⚡", _t("Answer every question of a quiz round correctly")),
    "streak_7": (_t("7 day streak"), "🔥", _t("Reach your daily goal 7 days in a row")),
    "streak_30": (_t("30 day streak"), "🏆", _t("Reach your daily goal 30 days in a row")),
    "xp_1000": (_t("1000 XP"), "💎", _t("Collect 1000 XP")),
    "unit_master": (_t("Unit master"), "🌟", _t("Get 5 stars in any unit")),
    "times_tables_pro": (_t("Times tables pro"), "✖️", _t("Get 5 stars in the times tables")),
    "french_star": (_t("French star"), "🥖", _t("Get 5 stars in a French unit")),
    "geo_thurgau": (_t("Thurgau explorer"), "🗺️", _t("Get 5 stars in a Thurgau geography station")),
    "chores_50": (_t("Helping hand"), "🧹", _t("Do 50 chores")),
}

EVENTS = {
    "answer_correct": _t("Correct answer"),
    "answer_fixed": _t("Card that was wrong before"),
    "answer_fast": _t("Fast answer in the quiz"),
    "lesson_done": _t("Lesson finished"),
    "daily_goal": _t("Daily goal reached"),
    "quiz_perfect": _t("Quiz round without mistakes"),
    "badge": _t("New badge"),
    "chore_done": _t("Chore done"),
    "streak_7": _t("7 day streak"),
    "streak_30": _t("30 day streak"),
    "weekly_winner": _t("Winner of the week"),
    "chores_week_all": _t("All chores of the week done"),
    "quiz_played": _t("Played the family quiz"),
    "quiz_won": _t("Won the family quiz"),
    "bingo_played": _t("Played bingo"),
    "bingo_won": _t("Won bingo"),
}


# XP spent in a shop (pet shop) is booked with one of these events: it lowers the XP balance, but not the level, the
# daily goal or the weekly XP – those count the XP earned
SPEND_EVENTS = ("pet_shop",)
_NOT_SPENT = "COALESCE(event, '') NOT IN (" + ",".join("?" * len(SPEND_EVENTS)) + ")"


def today() -> date:
    return datetime.now().date()


class Rewards:
    def __init__(self, db: Database):
        self.db = db
        self.listeners: list[Callable[[str, int, dict], None]] = []   # (kind, profile_id, data)
        self.book_listeners: list[Callable[[str, str], None]] = []      # (account, ref) after every booking

    def _notify(self, kind: str, pid: int, data: dict | None = None) -> None:
        for fn in self.listeners:
            try:
                fn(kind, pid, data or {})
            except Exception:  # noqa: BLE001 – a broken listener must not break learning
                log.exception("listener failed")

    # ---------------------------------------------------------------- accounts
    def accounts(self, active_only: bool = True) -> list[dict]:
        sql = "SELECT * FROM account" + (" WHERE active=1" if active_only else "") + " ORDER BY sort, key"
        return self.db.q(sql)

    def balance(self, pid: int, account: str) -> float:
        return float(self.db.val("SELECT SUM(amount) FROM ledger WHERE profile_id=? AND account=?", pid, account, default=0))

    def reserved(self, pid: int, account: str = "coins") -> float:
        """Coins promised in a deal that stands (deals.py) and not paid yet – they cannot be spent meanwhile."""
        if account != "coins":
            return 0.0
        return float(self.db.val("SELECT SUM(amount-paid) FROM deal_hold WHERE profile_id=? AND kind='coins' AND active=1",
                                 pid, default=0) or 0)

    def available(self, pid: int, account: str = "coins") -> float:
        """The balance that can be spent: coins reserved in deals (deals.py) are not – every shop, game price, battery
        recharge, pet cost … checks this one."""
        return self.balance(pid, account) - self.reserved(pid, account)

    def balances(self, pid: int) -> dict[str, float]:
        out = {a["key"]: 0.0 for a in self.accounts()}
        for r in self.db.q("SELECT account, SUM(amount) s FROM ledger WHERE profile_id=? GROUP BY account", pid):
            if r["account"] in out:
                out[r["account"]] = float(r["s"] or 0)
        return out

    def book(self, pid: int, account: str, amount: float, event: str = "", reason: str = "", ref: str = "") -> dict:
        lid = self.db.x("INSERT INTO ledger(profile_id,account,amount,event,reason,ref) VALUES(?,?,?,?,?,?)",
                        pid, account, amount, event, reason, ref)
        if account == "xp" and event not in SPEND_EVENTS:
            self._add_daily(pid, xp=amount)
        for fn in self.book_listeners:
            try:
                fn(account, ref)
            except Exception:  # noqa: BLE001
                log.exception("book listener failed")
        return {"id": lid, "account": account, "amount": amount, "event": event, "reason": reason}

    def _add_daily(self, pid: int, xp: float = 0, seconds: int = 0, lessons: int = 0) -> None:
        d = today().isoformat()
        self.db.x("""INSERT INTO daily(profile_id,day,xp,seconds,lessons) VALUES(?,?,?,?,?)
                     ON CONFLICT(profile_id,day) DO UPDATE SET xp=xp+excluded.xp, seconds=seconds+excluded.seconds,
                     lessons=lessons+excluded.lessons""", pid, d, xp, seconds, lessons)

    def add_time(self, pid: int, seconds: int, lessons: int = 0) -> None:
        self._add_daily(pid, seconds=max(0, min(int(seconds), 3600)), lessons=lessons)

    # ---------------------------------------------------------------- rules
    def emit(self, pid: int, event: str, ref: str = "", ctx: dict | None = None, _depth: int = 0,
             amounts: dict | None = None) -> list[dict]:
        """Apply all rules for an event. Returns the bookings (incl. follow-up events).
        `amounts` {account: amount} replaces the rules of that account (e.g. a pack's own XP / coins): the amount is
        booked once per account – limited by the smallest daily limit of the matching rules; without any rule for
        that event and account it is booked as it is (a rule the parents switched off: nothing)."""
        ctx = ctx or {}
        out: list[dict] = []
        active = {a["key"] for a in self.accounts()}
        own = {k: float(v) for k, v in (amounts or {}).items() if v is not None}
        with self.db.tx():
            def used_today(account: str) -> float:
                return float(self.db.val(
                    """SELECT SUM(amount) FROM ledger WHERE profile_id=? AND account=? AND event=?
                       AND date(at)=date('now','localtime')""", pid, account, event, default=0) or 0)

            rows = self.db.q("SELECT * FROM rule WHERE event=?", event)
            matching: dict[str, list] = {}
            for r in rows:
                if not r["active"] or r["account"] not in active:
                    continue
                cond = json.loads(r["condition"] or "{}")
                if any(str(ctx.get(k)) != str(v) for k, v in cond.items() if v not in (None, "")):
                    continue
                matching.setdefault(r["account"], []).append(r)
            for r in (r for rs in matching.values() for r in rs):
                if r["account"] in own:
                    continue                            # booked once below
                amount = float(r["amount"])
                if r["daily_limit"] is not None:
                    amount = max(0.0, min(amount, float(r["daily_limit"]) - used_today(r["account"])))
                if amount <= 0:
                    continue
                out.append(self.book(pid, r["account"], amount, event, r["label"] or EVENTS.get(event, event), ref))
            for account, amount in own.items():
                rs = matching.get(account) or []
                if account not in active or (not rs and any(r["account"] == account for r in rows)):
                    continue                            # the account is off, or its rule is switched off / does not match
                limits = [float(r["daily_limit"]) for r in rs if r["daily_limit"] is not None]
                if limits:
                    amount = max(0.0, min(amount, min(limits) - used_today(account)))
                if amount <= 0:
                    continue
                label = next((r["label"] for r in rs if r["label"]), None) or EVENTS.get(event, event)
                out.append(self.book(pid, account, amount, event, label, ref))
        if out:
            self._notify("ledger", pid, {"event": event, "bookings": out})
        if _depth < 3 and any(b["account"] == "xp" for b in out):
            out += self._check_goal(pid, _depth)
        if _depth < 3:
            out += self.check_badges(pid, _depth)
        return out

    # ---------------------------------------------------------------- daily goal, streak, level
    def daily_goal(self, pid: int) -> int:
        p = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
        return int(profile_settings(p or {})["daily_goal"]) if p else 50

    def xp_today(self, pid: int) -> float:
        return float(self.db.val("SELECT xp FROM daily WHERE profile_id=? AND day=?", pid, today().isoformat(), default=0))

    def _check_goal(self, pid: int, depth: int) -> list[dict]:
        d = today().isoformat()
        row = self.db.q1("SELECT * FROM daily WHERE profile_id=? AND day=?", pid, d)
        if not row or row["goal_met"] or row["xp"] < self.daily_goal(pid):
            return []
        self.db.x("UPDATE daily SET goal_met=1 WHERE profile_id=? AND day=?", pid, d)
        out = self.emit(pid, "daily_goal", ref=d, _depth=depth + 1)
        s = self.streak(pid)
        if s and s % 30 == 0:
            out += self.emit(pid, "streak_30", ref=d, _depth=depth + 1)
        if s and s % 7 == 0:
            out += self.emit(pid, "streak_7", ref=d, _depth=depth + 1)
        self._notify("goal", pid, {"streak": s})
        return out

    def streak(self, pid: int) -> int:
        """Days in a row with the daily goal met, ending today (or yesterday while today is still open)."""
        days = {r["day"] for r in self.db.q(
            "SELECT day FROM daily WHERE profile_id=? AND goal_met=1 AND day>=?", pid,
            (today() - timedelta(days=400)).isoformat())}
        d = today()
        if d.isoformat() not in days:
            d -= timedelta(days=1)
        n = 0
        while d.isoformat() in days:
            n += 1
            d -= timedelta(days=1)
        return n

    def new_xp(self, pid: int) -> float:
        """XP earned since the XP backgrounds exist (setting xp_items_from) – what they are «bought» with."""
        start = int(self.db.get_setting("xp_items_from", 0) or 0)
        return float(self.db.val(f"""SELECT SUM(amount) FROM ledger WHERE profile_id=? AND account='xp' AND amount>0
                                     AND id>? AND {_NOT_SPENT}""", pid, start, *SPEND_EVENTS, default=0))

    def total_xp(self, pid: int) -> float:
        """XP earned (the level counts these) – XP spent in the pet shop does not lower it; `balance(pid, "xp")` does."""
        return float(self.db.val(f"SELECT SUM(amount) FROM ledger WHERE profile_id=? AND account='xp' AND {_NOT_SPENT}",
                                 pid, *SPEND_EVENTS, default=0))

    def level(self, pid: int) -> dict:
        thresholds = self.db.get_setting("levels")
        xp = self.total_xp(pid)
        lvl = 1
        for i, t in enumerate(thresholds):
            if xp >= t:
                lvl = i + 1
        nxt = thresholds[lvl] if lvl < len(thresholds) else None
        cur = thresholds[lvl - 1] if thresholds else 0
        return {"level": lvl, "xp": xp, "from": cur, "next": nxt,
                "progress": 1.0 if nxt is None else round((xp - cur) / max(1, nxt - cur), 3)}

    # ---------------------------------------------------------------- badges
    def badges(self, pid: int) -> list[dict]:
        rows = self.db.q("SELECT badge, at FROM badge WHERE profile_id=? ORDER BY at", pid)
        return [{"id": r["badge"], "at": r["at"], "name": BADGES.get(r["badge"], (r["badge"], "🏅", ""))[0],
                 "icon": BADGES.get(r["badge"], ("", "🏅", ""))[1], "description": BADGES.get(r["badge"], ("", "", ""))[2]}
                for r in rows]

    def award(self, pid: int, badge: str, depth: int = 0) -> list[dict]:
        n = self.db.x("INSERT OR IGNORE INTO badge(profile_id,badge) VALUES(?,?)", pid, badge)
        if not n:
            return []
        self._notify("badge", pid, {"badge": badge, "name": BADGES.get(badge, (badge,))[0]})
        return [{"badge": badge, "name": BADGES.get(badge, (badge,))[0], "icon": BADGES.get(badge, ("", "🏅"))[1]}] + \
            self.emit(pid, "badge", ref=badge, _depth=depth + 1)

    def check_badges(self, pid: int, depth: int = 0, unit_stars: list[dict] | None = None) -> list[dict]:
        have = {r["badge"] for r in self.db.q("SELECT badge FROM badge WHERE profile_id=?", pid)}
        out: list[dict] = []

        def want(b: str, cond: bool) -> None:
            if b not in have and cond:
                out.extend(self.award(pid, b, depth))

        lessons = int(self.db.val("SELECT SUM(lessons) FROM daily WHERE profile_id=?", pid, default=0))
        want("first_lesson", lessons >= 1)
        want("ten_lessons", lessons >= 10)
        if "streak_7" not in have or "streak_30" not in have:
            s = self.streak(pid)
            want("streak_7", s >= 7)
            want("streak_30", s >= 30)
        want("xp_1000", self.total_xp(pid) >= 1000)
        want("chores_50", int(self.db.val("SELECT COUNT(DISTINCT ref) FROM ledger WHERE profile_id=? AND event='chore_done'", pid, default=0)) >= 50)
        for u in unit_stars or []:
            if u["stars"] >= 5:
                want("unit_master", True)
                want("times_tables_pro", u.get("generator") == "einmaleins")
                want("french_star", u.get("subject") == "franzoesisch")
                want("geo_thurgau", u.get("subject") in ("nmg", "geografie") and "tg" in u.get("pack", "").split("-"))
        return out

    # ---------------------------------------------------------------- shop
    def rewards(self, active_only: bool = True) -> list[dict]:
        rows = self.db.q("SELECT * FROM reward" + (" WHERE active=1" if active_only else "") + " ORDER BY sort, cost")
        for r in rows:
            r["config"] = json.loads(r["config"] or "{}")
        return rows

    def redeemed_this_week(self, pid: int, reward_id: int) -> int:
        monday = today() - timedelta(days=today().weekday())
        return int(self.db.val("""SELECT COUNT(*) FROM redemption WHERE profile_id=? AND reward_id=? AND status!='rejected'
                                  AND date(created_at)>=?""", pid, reward_id, monday.isoformat(), default=0))

    def internet_today(self, pid: int) -> float:
        rows = self.db.q("""SELECT r.config FROM redemption d JOIN reward r ON r.id=d.reward_id
                            WHERE d.profile_id=? AND r.kind='internet_minutes' AND d.status IN ('pending','approved')
                            AND date(d.created_at)=date('now','localtime')""", pid)
        return sum(float(json.loads(r["config"] or "{}").get("minutes", 0)) for r in rows)


def week_key(d: date | None = None) -> str:
    y, w, _ = (d or today()).isocalendar()
    return f"{y}-W{w:02d}"
