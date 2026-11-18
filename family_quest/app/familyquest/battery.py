"""Game battery of the children – and the party mode of the parents.

Every child has a game battery with charge segments (default 5, starts full). Starting a game costs one segment: an
own table of a family game (also alone against bots, a new round), opening a game of the game corner. Joining a table
somebody else opened is free, and a started game can always be played to the end. An empty battery: no own starts –
recharging it costs coins (default 50, the battery is full again; ledger event `energy_recharge`).

Settings: the family default `battery` (setting) and per child `battery` in the profile settings – a value missing
there is «as the family». {"on", "cap" 1–20, "cost" 0–10000 coins (0 = free), "unlimited": None | "forever" |
"YYYY-MM-DD HH:MM:SS" (until then)}; the family also has `goal` (off | full | plus) and `goal_plus` (segments): what
reaching the daily goal does. A chore can carry an energy bonus (`chore.energy`, segments) – charged when the chore is
done / approved, like its coins. Charges never go above the capacity; each goal day and each chore task charges once
(unique refs in `battery_log`). Parents have no battery.

Party mode (setting `party`): the parents switch it on for all or chosen children and a time (until switched off,
1 h, 3 h, until midnight, 1 day – it ends by itself). What it does: `unlock` every game (price, rent and «switched off»
do not count), `battery` (starting costs nothing), `limits` (the daily game time, game block times of the internet
plan and the game lock of OfflineTime do not count for games). Nothing is bought or charged – ending it restores all.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .db import Database, profile_settings
from .gamepasses import add_period
from .i18n import _t

FMT = "%Y-%m-%d %H:%M:%S"
DEFAULT = {"on": True, "cap": 5, "cost": 50, "unlimited": None, "goal": "plus", "goal_plus": 1}
MAX_CAP = 20
MAX_COST = 10000
GOALS = ("off", "full", "plus")
UNLIMITED = ("off", "forever", "day", "week", "month", "keep")        # what the parent area sends
SAME_S = 10                     # a second start of the same game within this time: the same start (double tap, two devices)
PARTY_FOR = ("forever", "1h", "3h", "midnight", "day")
CAP_MSG = _t("Capacity: 1 to 20 segments")
COST_MSG = _t("Recharging: 0 to 10000 coins")


class BatteryError(ValueError):
    pass


def _ts(v) -> datetime | None:
    try:
        return datetime.strptime(str(v), FMT)
    except (TypeError, ValueError):
        return None


def _int(v, lo: int, hi: int, msg: str) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise BatteryError(msg) from None
    if not lo <= n <= hi:
        raise BatteryError(msg)
    return n


def _unl(v):
    """A stored unlimited value: None, "", "forever" or a time – anything else is None."""
    if v in (None, "", "forever"):
        return v
    return v if _ts(v) else None


def unlimited_from(choice: str, cur, now: datetime):
    """The value to store for the choice of the parent area (off → None, a period → until now + period)."""
    if choice not in UNLIMITED:
        raise BatteryError("Unlimited: off, permanent, 1 day, 1 week or 1 month")
    if choice == "keep":
        return cur
    if choice == "off":
        return None
    if choice == "forever":
        return "forever"
    return add_period(now.replace(microsecond=0), choice).strftime(FMT)


def clean_family(v) -> dict:
    v = v if isinstance(v, dict) else {}
    out = dict(DEFAULT)
    if "on" in v:
        out["on"] = v["on"] is not False
    for k, hi in (("cap", MAX_CAP), ("cost", MAX_COST)):
        try:
            out[k] = min(hi, max(1 if k == "cap" else 0, int(v.get(k, out[k]))))
        except (TypeError, ValueError):
            pass
    out["unlimited"] = _unl(v.get("unlimited")) or None
    out["goal"] = v.get("goal") if v.get("goal") in GOALS else DEFAULT["goal"]
    try:
        out["goal_plus"] = min(MAX_CAP, max(1, int(v.get("goal_plus", DEFAULT["goal_plus"]))))
    except (TypeError, ValueError):
        pass
    return out


def clean_own(v) -> dict:
    """The child's own values – only those set (a missing key is «as the family»)."""
    v = v if isinstance(v, dict) else {}
    out = {}
    if v.get("on") is not None:
        out["on"] = v["on"] is not False
    for k, lo, hi in (("cap", 1, MAX_CAP), ("cost", 0, MAX_COST)):
        if v.get(k) is not None:
            try:
                out[k] = min(hi, max(lo, int(v[k])))
            except (TypeError, ValueError):
                pass
    if "unlimited" in v and _unl(v["unlimited"]) is not None:
        out["unlimited"] = _unl(v["unlimited"])
    return out


class Battery:
    def __init__(self, db: Database, rewards):
        self.db = db
        self.rewards = rewards
        self.now = datetime.now                  # the tests move time
        self.party = Party(db, lambda: self.now())

    # ------------------------------------------------------------ settings
    def family(self) -> dict:
        return clean_family(self.db.get_setting("battery"))

    def own(self, prof: dict) -> dict:
        return clean_own(profile_settings(prof).get("battery"))

    def _active_unl(self, v, now: datetime):
        """"forever", an until time still ahead – else None."""
        if v == "forever":
            return v
        t = _ts(v)
        return v if t and t > now else None

    def config(self, prof: dict) -> dict:
        """The values for this child: own values before the family default. `unlimited`: "forever", an until time
        (still ahead) or None – the child's own unlimited value wins while it lasts («» = not unlimited)."""
        fam, own, now = self.family(), self.own(prof), self.now()
        c = {k: own.get(k, fam[k]) for k in ("on", "cap", "cost")}
        unl = None
        if "unlimited" in own and (own["unlimited"] == "" or self._active_unl(own["unlimited"], now)):
            unl = self._active_unl(own["unlimited"], now)
        else:
            unl = self._active_unl(fam["unlimited"], now)
        c["unlimited"] = unl
        return c

    def save_family(self, body: dict) -> dict:
        cur = self.family()
        out = dict(cur)
        if "on" in body and body["on"] is not None:
            out["on"] = bool(body["on"])
        if body.get("cap") is not None:
            out["cap"] = _int(body["cap"], 1, MAX_CAP, CAP_MSG)
        if body.get("cost") is not None:
            out["cost"] = _int(body["cost"], 0, MAX_COST, COST_MSG)
        if body.get("unlimited") is not None:
            out["unlimited"] = unlimited_from(body["unlimited"], cur["unlimited"], self.now())
        if body.get("goal") is not None:
            if body["goal"] not in GOALS:
                raise BatteryError("Daily goal: off, full battery or extra segments")
            out["goal"] = body["goal"]
        if body.get("goal_plus") is not None:
            out["goal_plus"] = _int(body["goal_plus"], 1, MAX_CAP, CAP_MSG)
        self.db.set_setting("battery", out)
        return out

    def save_own(self, prof: dict, body: dict) -> dict:
        """body: {"on": bool | None, "cap": n | None, "cost": n | None, "unlimited": "family" | UNLIMITED} – None and
        «family»: as the family."""
        import json
        s = profile_settings(prof)
        own = clean_own(s.get("battery"))
        if "on" in body:
            if body["on"] is None:
                own.pop("on", None)
            else:
                own["on"] = bool(body["on"])
        for k, lo, hi, msg in (("cap", 1, MAX_CAP, CAP_MSG), ("cost", 0, MAX_COST, COST_MSG)):
            if k in body:
                if body[k] is None or body[k] == "":
                    own.pop(k, None)
                else:
                    own[k] = _int(body[k], lo, hi, msg)
        if body.get("unlimited") is not None:
            if body["unlimited"] == "family":
                own.pop("unlimited", None)
            elif body["unlimited"] != "keep":
                v = unlimited_from(body["unlimited"], own.get("unlimited"), self.now())
                own["unlimited"] = "" if v is None else v
        s["battery"] = own
        self.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(s), prof["id"])
        return own

    # ------------------------------------------------------------ charge
    def _charge(self, pid: int, cap: int, row: dict | None = None) -> int:
        r = row if row is not None else self.db.q1("SELECT * FROM battery WHERE profile_id=?", pid)
        if not r or r["charge"] is None:
            return cap
        return max(0, min(cap, int(r["charge"])))

    def _store(self, pid: int, charge: int, cap: int, **more) -> None:
        val = None if charge >= cap else max(0, charge)
        cols = {"charge": val, **more}
        names = ",".join(cols)
        self.db.x(f"""INSERT INTO battery(profile_id,{names}) VALUES(?{",?" * len(cols)})
                      ON CONFLICT(profile_id) DO UPDATE SET {",".join(f"{k}=excluded.{k}" for k in cols)}""",
                  pid, *cols.values())

    def state(self, prof: dict) -> dict | None:
        """For the kid app: {"on", "charge", "cap", "cost", "unlimited" (bool), "forever", "until", "party", "free"}
        – None for parents."""
        if not prof or prof.get("role") != "kid":
            return None
        c = self.config(prof)
        party = self.party.for_kid(prof)
        party_free = bool(party and party["battery"])
        unl = c["unlimited"]
        return {"on": c["on"], "charge": self._charge(prof["id"], c["cap"]), "cap": c["cap"], "cost": c["cost"],
                "unlimited": bool(unl), "forever": unl == "forever", "until": unl if unl not in (None, "forever") else None,
                "party": party_free, "party_until": party["until"] if party_free else None,
                "free": not c["on"] or bool(unl) or party_free}

    def use(self, prof: dict, game: str) -> tuple[str | None, int | None]:
        """Starting a game: ("free", None) – no battery just now (parents, off, unlimited, party); ("same", None) – this
        game was started less than SAME_S seconds ago (a double tap, a second device); ("new", log id) – one segment
        used; (None, None) – empty. Checked and used in one transaction."""
        if not prof or prof.get("role") != "kid":
            return "free", None
        with self.db.tx():
            st = self.state(prof)
            if st["free"]:
                return "free", None
            now = self.now()
            row = self.db.q1("SELECT * FROM battery WHERE profile_id=?", prof["id"])
            at = _ts(row and row["last_at"])
            if row and row["last_game"] == game and at and 0 <= (now - at).total_seconds() < SAME_S:
                return "same", None
            charge = self._charge(prof["id"], st["cap"], row)
            if charge <= 0:
                return None, None
            self._store(prof["id"], charge - 1, st["cap"], last_game=game, last_at=now.strftime(FMT))
            lid = self.db.x("INSERT INTO battery_log(profile_id, delta, kind, game) VALUES(?,?,?,?)", prof["id"], -1, "start", game)
        return "new", lid

    def give_back(self, pid: int, lid: int) -> None:
        """The start that used a segment failed (no table opened): the segment is back."""
        with self.db.tx():
            if not self.db.x("DELETE FROM battery_log WHERE id=? AND profile_id=? AND kind='start'", lid, pid):
                return
            prof = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
            cap = self.config(prof)["cap"]
            self._store(pid, self._charge(pid, cap) + 1, cap, last_at=None)

    def add(self, pid: int, n: int | None, kind: str, ref: str) -> int:
        """Charge n segments (None: full) – capped at the capacity, once per ref. Returns the segments added."""
        prof = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
        if not prof or prof["role"] != "kid":
            return 0
        with self.db.tx():
            if self.db.q1("SELECT 1 FROM battery_log WHERE profile_id=? AND ref=?", pid, ref):
                return 0
            cap = self.config(prof)["cap"]
            cur = self._charge(pid, cap)
            new = cap if n is None else min(cap, cur + max(0, int(n)))
            self.db.x("INSERT INTO battery_log(profile_id, delta, kind, ref) VALUES(?,?,?,?)", pid, new - cur, kind, ref)
            self._store(pid, new, cap)
        return new - cur

    def recharge(self, prof: dict) -> dict:
        """The child recharges its battery to full for coins (cost 0: free). One transaction – a double tap finds the
        battery full and books nothing."""
        if not prof or prof.get("role") != "kid":
            raise BatteryError("Parents play without a battery")
        with self.db.tx():
            st = self.state(prof)
            if st["free"]:
                raise BatteryError("Your game battery needs no recharge just now")
            if st["charge"] >= st["cap"]:
                raise BatteryError("Your game battery is full")
            cost = st["cost"]
            if cost and self.rewards.balance(prof["id"], "coins") < cost:
                raise BatteryError("Not enough coins")
            now = self.now().strftime(FMT)
            lid = self.db.x("INSERT INTO battery_log(profile_id, delta, kind, ref) VALUES(?,?,?,?)",
                            prof["id"], st["cap"] - st["charge"], "recharge", f"recharge:{now}:{st['charge']}")
            if cost:
                self.rewards.book(prof["id"], "coins", -float(cost), "energy_recharge", _t("Game battery recharged"),
                                  f"battery:recharge:{prof['id']}:{lid}")
            self._store(prof["id"], st["cap"], st["cap"])
        return self.state(prof)

    # ------------------------------------------------------------ goals and chores (rewards listener)
    def on_reward(self, kind: str, pid: int, data: dict) -> None:
        if kind == "goal":
            fam = self.family()
            if fam["goal"] == "off":
                return
            self.add(pid, None if fam["goal"] == "full" else fam["goal_plus"], "goal", f"goal:{self.now().date().isoformat()}")
        elif kind == "chore" and data.get("task"):
            n = self.db.val("SELECT c.energy FROM chore_task t JOIN chore c ON c.id=t.chore_id WHERE t.id=?", data["task"], default=0)
            if n and int(n) > 0:
                self.add(pid, int(n), "chore", f"chore:{data['task']}")

    # ------------------------------------------------------------ parent area
    def overview(self, kids: list[dict]) -> dict:
        return {"family": self.family(), "party": self.party.config(),
                "kids": [{"id": k["id"], "name": k["name"], "own": self.own(k), "state": self.state(k)} for k in kids]}


class Party:
    def __init__(self, db: Database, now):
        self.db = db
        self.now = now

    def config(self) -> dict | None:
        """The party mode now – None when off or over (it ends by itself)."""
        p = self.db.get_setting("party")
        if not isinstance(p, dict):
            return None
        until = p.get("until")
        if until != "forever":
            t = _ts(until)
            if not t or t <= self.now():
                return None
        return {"until": None if until == "forever" else until, "kids": p.get("kids") if p.get("kids") == "all" else
                [int(x) for x in p.get("kids") or []], "unlock": bool(p.get("unlock")), "battery": bool(p.get("battery")),
                "limits": bool(p.get("limits")), "since": p.get("since")}

    def for_kid(self, prof: dict) -> dict | None:
        if not prof or prof.get("role") != "kid":
            return None
        p = self.config()
        if not p or (p["kids"] != "all" and prof["id"] not in p["kids"]):
            return None
        return p

    def start(self, body: dict, kid_ids: list[int]) -> dict:
        kids = body.get("kids", "all")
        if kids != "all":
            if not isinstance(kids, list):
                raise BatteryError("Choose the children")
            kids = sorted({int(x) for x in kids if int(x) in kid_ids})
            if not kids:
                raise BatteryError("Choose the children")
        unlock, battery, limits = bool(body.get("unlock")), bool(body.get("battery")), bool(body.get("limits"))
        if not (unlock or battery or limits):
            raise BatteryError("Choose what the party mode opens")
        dur = body.get("for", "forever")
        if dur not in PARTY_FOR:
            raise BatteryError("Choose how long")
        now = self.now().replace(microsecond=0)
        until = {"forever": "forever", "1h": (now + timedelta(hours=1)).strftime(FMT), "3h": (now + timedelta(hours=3)).strftime(FMT),
                 "midnight": (now.replace(hour=0, minute=0, second=0) + timedelta(days=1)).strftime(FMT),
                 "day": (now + timedelta(days=1)).strftime(FMT)}[dur]
        self.db.set_setting("party", {"kids": kids, "unlock": unlock, "battery": battery, "limits": limits, "until": until,
                                      "since": now.strftime(FMT)})
        return self.config()

    def stop(self) -> None:
        self.db.set_setting("party", None)
