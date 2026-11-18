"""Shop: redeem rewards with an account balance; parents approve where required.

Reward kinds:
  voucher           parents fulfil it themselves (ice cream, movie night …)
  internet_minutes  minutes go to the profile's internet budget entity in Home Assistant
  planer_points     points are booked in the Family Planer (family_planer.add_points)
  ha_script         runs a Home Assistant script
  avatar_item       unlocks an avatar item (config: {"item": "cap"})
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Callable

from ..db import Database, profile_settings
from ..i18n import _t
from .engine import Rewards

log = logging.getLogger("familyquest.shop")

KINDS = ["voucher", "internet_minutes", "planer_points", "ha_script", "avatar_item"]

# executor(kind, profile_row, reward_row, redemption_id) -> (ok, note)
Executor = Callable[[str, dict, dict, int], tuple[bool, str]]


class ShopError(ValueError):
    pass


class Shop:
    def __init__(self, db: Database, rewards: Rewards):
        self.db = db
        self.rewards = rewards
        self.executor: Executor | None = None
        self.internet = None              # InternetTime – minutes booked in the app when a firewall rule is chosen
        self.on_pending: list[Callable[[dict], None]] = []     # notify parents
        self.lock = threading.Lock()      # two taps at once must not buy twice (balance and weekly limit are checked inside)
        self.on_change: list[Callable[[int], None]] = []

    def offers(self, pid: int) -> list[dict]:
        bal = self.rewards.balances(pid)
        if "coins" in bal:
            bal["coins"] -= self.rewards.reserved(pid)        # coins promised in a deal (deals.py) cannot be spent
        prof = self.db.q1("SELECT * FROM profile WHERE id=?", pid) or {}
        ps = profile_settings(prof)
        active_accounts = {a["key"] for a in self.rewards.accounts()}
        out = []
        for r in self.rewards.rewards():
            if r["account"] not in active_accounts:
                continue
            if r["kind"] == "internet_minutes" and not ps.get("internet_entity") and not ps.get("internet_rule"):
                continue                       # no budget entity chosen for this child
            used = self.rewards.redeemed_this_week(pid, r["id"]) if r["weekly_limit"] else 0
            reason = ""
            if r["weekly_limit"] and used >= r["weekly_limit"]:
                reason = _t("Already redeemed this week")
            elif bal.get(r["account"], 0) < r["cost"]:
                reason = _t("Not enough yet")
            elif r["kind"] == "internet_minutes":
                mins = float(r["config"].get("minutes", 0))
                if self.rewards.internet_today(pid) + mins > float(ps.get("internet_daily_limit") or 0):
                    reason = _t("Daily limit reached")
            out.append({**r, "can": not reason, "reason": reason, "missing": max(0, r["cost"] - bal.get(r["account"], 0)),
                        "week_used": used})
        return out

    def redeem(self, pid: int, reward_id: int) -> dict:
        with self.lock:                   # check and book in one step – a double tap cannot buy twice
            offer = next((o for o in self.offers(pid) if o["id"] == reward_id), None)
            if not offer:
                raise ShopError("reward not available")
            if not offer["can"]:
                raise ShopError(offer["reason"])
            with self.db.tx():
                rid = self.db.x("INSERT INTO redemption(profile_id,reward_id,cost,account,status) VALUES(?,?,?,?, 'pending')",
                                pid, reward_id, offer["cost"], offer["account"])
                # the amount is reserved right away; a rejection books it back
                self.rewards.book(pid, offer["account"], -float(offer["cost"]), "redeem", offer["name"], f"redemption:{rid}")
        red = self.get(rid)
        if offer["approval"]:
            for fn in self.on_pending:
                try:
                    fn(red)
                except Exception:  # noqa: BLE001
                    log.exception("notify failed")
        else:
            red = self.decide(rid, True, by_parent=False)
        self._changed(pid)
        return red

    def get(self, rid: int) -> dict | None:
        r = self.db.q1("""SELECT d.*, r.name, r.kind, r.icon, r.config, p.name AS profile_name FROM redemption d
                          JOIN reward r ON r.id=d.reward_id JOIN profile p ON p.id=d.profile_id WHERE d.id=?""", rid)
        if r:
            r["config"] = json.loads(r["config"] or "{}")
        return r

    def list(self, status: str | None = None, pid: int | None = None, limit: int = 50) -> list[dict]:
        sql = """SELECT d.*, r.name, r.kind, r.icon, p.name AS profile_name FROM redemption d
                 JOIN reward r ON r.id=d.reward_id JOIN profile p ON p.id=d.profile_id WHERE 1=1"""
        args: list = []
        if status:
            sql += " AND d.status=?"
            args.append(status)
        if pid:
            sql += " AND d.profile_id=?"
            args.append(pid)
        sql += " ORDER BY d.id DESC LIMIT ?"
        args.append(limit)
        return self.db.q(sql, *args)

    def decide(self, rid: int, approve: bool, by_parent: bool = True, note: str = "") -> dict:
        red = self.get(rid)
        if not red:
            raise ShopError("unknown redemption")
        if red["status"] != "pending":
            return red
        # claim it: of two decisions at the same time (app and push message) only one goes on
        if not self.db.x("UPDATE redemption SET status='processing' WHERE id=? AND status='pending'", rid):
            return self.get(rid)
        reward = self.db.q1("SELECT * FROM reward WHERE id=?", red["reward_id"])
        reward["config"] = json.loads(reward["config"] or "{}")
        profile = self.db.q1("SELECT * FROM profile WHERE id=?", red["profile_id"])
        status, msg = ("rejected", note)
        if approve:
            ok, msg = self.execute(reward, profile, rid)
            status = "approved" if ok else "failed"
        with self.db.tx():
            self.db.x("UPDATE redemption SET status=?, note=?, decided_at=datetime('now','localtime') WHERE id=?",
                      status, msg or note, rid)
            if status in ("rejected", "failed"):
                self.rewards.book(red["profile_id"], red["account"], float(red["cost"]), "refund", red["name"], f"redemption:{rid}")
        self._changed(red["profile_id"])
        return self.get(rid)

    def execute(self, reward: dict, profile: dict, rid: int) -> tuple[bool, str]:
        kind = reward["kind"]
        if kind == "voucher":
            return True, ""
        if kind == "avatar_item":
            item = reward["config"].get("item")
            if item:
                self.db.x("INSERT OR IGNORE INTO unlock(profile_id,item) VALUES(?,?)", profile["id"], item)
            return True, ""
        if kind == "internet_minutes" and self.internet and self.internet.managed(profile):
            minutes = float(reward["config"].get("minutes", reward["cost"]))
            self.internet.ensure_account()
            self.rewards.book(profile["id"], "internet", minutes, "redeem", reward["name"], f"redemption:{rid}")
            return True, f"+{minutes:g} min"
        if self.executor is None:
            return False, _t("Home Assistant is not connected")
        try:
            return self.executor(kind, profile, reward, rid)
        except Exception as e:  # noqa: BLE001
            log.exception("reward action failed")
            return False, str(e)

    def _changed(self, pid: int) -> None:
        for fn in self.on_change:
            try:
                fn(pid)
            except Exception:  # noqa: BLE001
                log.exception("listener failed")
