"""Deals: children trade with each other and with their parents.

A deal has two sides – what each person gives. A side combines any of these building blocks:

* `coins` – only coins (XP can never be traded),
* `chore` – «I do your chore X» (one time, or the next N times of a recurring chore of the own chore plan): the chore
  tasks move to the giver (`chore_task.profile_id`, with `from_id` = whose chore it was, `deal_id`),
* `newchore` – a new task a parent hands over to a child («mow the lawn today»): a one-off chore of the chore plan,
* `pet`, `avatar`, `game` – an owned pet (not in the pet hotel, at a sitter or while pet care is paused), an avatar
  item bought with coins, a game bought for good (rented games cannot be traded – they run out),
* `text` – a free deal without automation («I help you with homework»): both confirm «Done ✓».

Flow: A offers to B (version 1). B accepts, rejects or makes a counter-offer (version 2, the same building blocks) –
and so on; the thread keeps every version. The deal stands when both accepted the same version. If the parents want
to approve big deals (settings: coins from a threshold, always for pets), it waits for a parent first (deals with a
parent never do). When it stands, what will be given later is reserved (`deal_hold`: coins cannot be spent – see
`Rewards.available` – items are locked) and taken-over chores move to the doer.

Execution: coins and items of a side are the payment for the services (chores, free text) of the other side. Without
services on the other side they are transferred at once when the deal stands. Otherwise each service done pays its
share of the coins (pro rata, the remainder with the last one) and the items come with the last one. A taken-over chore
counts when the parents approved it (or at once for chores without confirmation): its own coins go to the doer – or to
the original owner when the deal says so – and its XP always to the doer (chores.py asks `reward_to`). A chore not done
by the end of its day (week for weekly chores), rejected by a parent or removed makes the deal fail: the reservations
are released and the open taken-over chores go back to their owner (the missed one stays with who missed it).
Free text: both confirm «Done ✓»; if one says «not done», a parent settles it – or the family council votes.

Parents: settings (trading on/off per child, which building blocks, max coins per deal, approval of big deals), an
overview of every deal, cancel any deal (releases the reservations), approve, settle. Parents trade too: coins of a
parent are «paid by the parents» (booked to the child like a manual booking, not taken from a parent account), coins a
child gives to a parent go to the parents (taken from the child only). Guests cannot trade.

Every transfer has a unique ref in `deal_pay` and is booked in the same transaction as its state – never twice.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, timedelta

from .chores import monday
from .i18n import _t
from .rewards import avatar as av
from .rewards.engine import today

log = logging.getLogger("familyquest.deals")

KEY = "deals"
BLOCKS = ("coins", "chores", "pets", "avatar", "games", "text")
DEFAULT = {"on": True, "off": [], "kinds": {k: True for k in BLOCKS}, "max_coins": 500,
           "approval": False, "threshold": 100, "approval_pets": False}
ITEM_KINDS = {"coins": "coins", "chore": "chores", "newchore": "chores", "pet": "pets", "avatar": "avatar", "game": "games",
              "text": "text"}
OPEN = ("open", "approval", "running")          # active deals (a chore / an item can be in one of them only)
ENDED = ("done", "rejected", "withdrawn", "declined", "failed", "cancelled")
MAX_ITEMS = 8           # per side
MAX_TIMES = 10          # «the next N times» of a chore
LOOKAHEAD = 42          # days searched for the next times of a chore
NEW_CHORE_DAYS = 14     # a new task a parent hands over: today … in 14 days
MAX_TEXT = 140
GAME_TITLES = {"ttt": "Tic-Tac-Toe", "sudoku": "Sudoku", "patience": "Patience", "pingpong": "Ping-Pong",
               "slots": "One-armed bandit", "cube": "Cube solver", "quiz": "Family quiz", "song": "Guess the song"}
REASONS = {
    "missed": _t("A taken-over chore was not done in time"),
    "rejected": _t("A parent rejected a taken-over chore"),
    "removed": _t("A chore of the deal was removed"),
    "gone": _t("Something of the deal is no longer there"),
    "text": _t("The free deal was not fulfilled"),
    "cancelled": _t("A parent cancelled the deal"),
    "council": _t("The family council decided: not done"),
}


class DealError(ValueError):
    pass


def _j(s, default):
    try:
        return json.loads(s) if s else default
    except ValueError:
        return default


def _int(v, lo: int, hi: int, msg: str) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise DealError(msg) from None
    if not lo <= n <= hi:
        raise DealError(msg)
    return n


def other(side: str) -> str:
    return "b" if side == "a" else "a"


class Deals:
    def __init__(self, fq):
        self.fq = fq
        self.db = fq.db
        self.rewards = fq.rewards
        self.lock = threading.RLock()            # one change at a time – the checks and the bookings belong together

    # ================================================================ settings
    def settings(self) -> dict:
        return self.clean(self.db.get_setting(KEY) or {})

    @staticmethod
    def clean(data: dict | None) -> dict:
        d = data if isinstance(data, dict) else {}
        out = json.loads(json.dumps(DEFAULT))
        if "on" in d:
            out["on"] = bool(d["on"])
        out["off"] = sorted({int(x) for x in d.get("off") or [] if str(x).lstrip("-").isdigit()})
        kinds = d.get("kinds") if isinstance(d.get("kinds"), dict) else {}
        out["kinds"] = {k: bool(kinds.get(k, True)) for k in BLOCKS}
        for k, lo, hi in (("max_coins", 1, 100000), ("threshold", 1, 100000)):
            if d.get(k) is not None:
                try:
                    out[k] = max(lo, min(hi, int(d[k])))
                except (TypeError, ValueError):
                    pass
        out["approval"] = bool(d.get("approval", False))
        out["approval_pets"] = bool(d.get("approval_pets", False))
        return out

    def save_settings(self, data: dict) -> dict:
        s = self.clean({**self.settings(), **(data or {})})
        self.db.set_setting(KEY, s)
        return s

    def can_trade(self, prof: dict | None, st: dict | None = None) -> bool:
        if not prof or prof.get("archived") or prof.get("role") not in ("kid", "parent"):
            return False
        st = st or self.settings()
        if not st["on"]:
            return False
        return prof["role"] == "parent" or prof["id"] not in st["off"]

    def _prof(self, pid: int) -> dict:
        p = self.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", pid)
        if not p:
            raise DealError("Unknown profile")
        return p

    def partners(self, prof: dict) -> list[dict]:
        st = self.settings()
        out = []
        for p in self.db.q("SELECT * FROM profile WHERE archived=0 AND id!=? ORDER BY role DESC, name", prof["id"]):
            if prof["role"] == "parent" and p["role"] == "parent":
                continue                                         # parents do not trade with each other
            if self.can_trade(p, st):
                out.append(self._person(p))
        return out

    @staticmethod
    def _person(p: dict) -> dict:
        return {"id": p["id"], "name": p["name"], "role": p["role"], "avatar": _j(p.get("avatar"), {})}

    # ================================================================ what can be traded
    def _chore(self, chore_id: int) -> dict:
        ch = next((c for c in self.fq.chores.list(active_only=True) if c["id"] == chore_id), None)
        if not ch:
            raise DealError("Unknown chore")
        return ch

    @staticmethod
    def _due_end(period: str, weekly: bool) -> date:
        d = date.fromisoformat(period)
        return d + timedelta(days=6) if weekly else d

    def _occurrences(self, ch: dict, owner: int, doer: int, times: int, create: bool = False) -> list[dict]:
        """The next `times` times the chore is the owner's (from today on) that the doer can take over: still open, not
        in a deal, not a time the doer has the same chore himself. create=True makes the task rows (to move them)."""
        kids = self.fq.chores._kids()
        out, seen, d0 = [], set(), today()
        for i in range(LOOKAHEAD):
            d = d0 + timedelta(days=i)
            period = self.fq.chores.due_on(ch, d)
            if not period or period in seen:
                continue
            seen.add(period)
            who = self.fq.chores.assignees(ch, d, kids)
            if owner not in who or doer in who:
                continue
            if ch["frequency"] == "weekly" and self._due_end(period, True) < d0:
                continue
            row = self.db.q1("SELECT * FROM chore_task WHERE chore_id=? AND period=? AND (profile_id=? OR from_id=?)",
                             ch["id"], period, owner, owner)
            if row and (row["status"] != "open" or row["deal_id"] or row["profile_id"] != owner):
                continue
            if self.db.q1("SELECT 1 FROM chore_task WHERE chore_id=? AND period=? AND profile_id=?", ch["id"], period, doer):
                continue
            if create and not row:
                self.db.x("INSERT OR IGNORE INTO chore_task(chore_id, profile_id, period) VALUES(?,?,?)", ch["id"], owner, period)
                row = self.db.q1("SELECT * FROM chore_task WHERE chore_id=? AND period=? AND profile_id=?", ch["id"], period, owner)
            out.append({"period": period, "task": row["id"] if row else None})
            if len(out) >= times:
                break
        return out

    def chores_of(self, owner: int, doer: int) -> list[dict]:
        """Chores of `owner` the `doer` could take over – with the next dates (offer builder)."""
        out = []
        for ch in self.fq.chores.list(active_only=True):
            occ = self._occurrences(ch, owner, doer, MAX_TIMES)
            if occ:
                out.append({"chore": ch["id"], "name": ch["name"], "icon": ch["icon"], "points": ch["points"],
                            "account": ch["account"], "frequency": ch["frequency"], "max": len(occ),
                            "dates": [o["period"] for o in occ]})
        return out

    def _pet_problem(self, pet: dict | None, giver: int) -> str | None:
        from .pets import now as pets_now, _ts
        if not pet or pet["profile_id"] != giver or pet["dead_at"]:
            return _t("That is not your pet")
        if _ts(pet["hotel_until"]) and _ts(pet["hotel_until"]) > pets_now():
            return _t("A pet in the pet hotel cannot be traded")
        if pet["sitter_id"] and (pet["sit_until"] or "") >= today().isoformat():
            return _t("A pet at a pet sitter cannot be traded")
        if self.fq.pets.paused_by_parents(giver):
            return _t("Pet care is paused – pets cannot be traded now")
        rule = av.ITEMS.get(pet["kind"], ("", "", {}))[2]
        spent = self.db.val("SELECT new_xp FROM unlock WHERE profile_id=? AND item=?", giver, pet["kind"], default=0)
        if "badge" in rule or "xp" in rule or spent:
            return _t("Pets earned with a badge or XP cannot be traded")
        return None

    def items_of(self, pid: int) -> dict:
        """What a profile owns that can be traded: pets, avatar items bought with coins, games bought for good."""
        from .pets import KINDS as PET_KINDS
        pets = []
        for p in self.db.q("SELECT * FROM pet WHERE profile_id=? AND dead_at IS NULL ORDER BY id", pid):
            why = self._pet_problem(p, pid)
            pets.append({"id": p["id"], "kind": p["kind"], "name": p["name"], "emoji": PET_KINDS.get(p["kind"], ("🐾",))[0],
                         "ok": not why, "why": why})
        avatar = []
        for r in self.db.q("SELECT item, new_xp FROM unlock WHERE profile_id=? ORDER BY item", pid):
            it = av.ITEMS.get(r["item"])
            if not it or it[1] == "pet" or r["new_xp"] or "cost" not in it[2]:
                continue
            avatar.append({"item": r["item"], "slot": it[1], "name": it[0]})
        games = [{"game": r["game"], "name": self._game_title(r["game"]), "icon": self._game_icon(r["game"])}
                 for r in self.db.q("SELECT game FROM game_pass WHERE profile_id=? AND bought=1 ORDER BY game", pid)]
        return {"pets": pets, "avatar": avatar, "games": games}

    @staticmethod
    def _game_title(g: str) -> str:
        from .running import TITLES
        return TITLES.get(g) or GAME_TITLES.get(g) or g

    @staticmethod
    def _game_icon(g: str) -> str:
        from .running import ICONS
        return ICONS.get(g) or {"ttt": "⭕", "sudoku": "🔢", "patience": "🃏", "pingpong": "🏓", "slots": "🎰", "cube": "🧊"}.get(g, "🎮")

    def assets(self, prof: dict, other_id: int) -> dict:
        """Everything the offer builder needs for a deal between `prof` and `other_id`."""
        self._check_pair(prof, self._prof(other_id))
        o = self._prof(other_id)
        st = self.settings()
        mine, theirs = self.items_of(prof["id"]), self.items_of(other_id)
        return {"settings": {"kinds": st["kinds"], "max_coins": st["max_coins"]},
                "me": {**self._person(prof), "coins": None if prof["role"] == "parent" else self.rewards.available(prof["id"]),
                       "chores": self.chores_of(prof["id"], other_id), **mine},
                "other": {**self._person(o), "chores": self.chores_of(other_id, prof["id"]),
                          **(theirs if o["role"] == "kid" else {"pets": [], "avatar": [], "games": []})},
                "new_task": prof["role"] == "parent" or o["role"] == "parent"}

    # ================================================================ terms
    def _check_pair(self, a: dict, b: dict) -> None:
        if a["id"] == b["id"]:
            raise DealError("You cannot make a deal with yourself")
        if a["role"] == "parent" and b["role"] == "parent":
            raise DealError("Parents do not trade with each other")
        st = self.settings()
        if not self.can_trade(a, st):
            raise DealError("Trading is switched off for you")
        if not self.can_trade(b, st):
            raise DealError("Trading is switched off for this person")

    def _item(self, raw: dict, giver: dict, receiver: dict, st: dict) -> dict:
        if not isinstance(raw, dict):
            raise DealError("Unknown building block")
        t = raw.get("t")
        if t not in ITEM_KINDS:
            raise DealError("Unknown building block")
        if not st["kinds"].get(ITEM_KINDS[t], True):
            raise DealError("This building block is switched off by the parents")
        if t == "coins":
            return {"t": "coins", "n": _int(raw.get("n"), 1, 100000, "Coins: a whole number from 1")}
        if t == "text":
            text = " ".join(str(raw.get("text") or "").split())[:MAX_TEXT]
            if not text:
                raise DealError("Write what the free deal is")
            return {"t": "text", "text": text}
        if t == "chore":
            ch = self._chore(_int(raw.get("chore"), 1, 10 ** 9, "Unknown chore"))
            times = 1 if ch["frequency"] == "once" else _int(raw.get("times", 1), 1, MAX_TIMES, "Times: 1 to 10")
            occ = self._occurrences(ch, receiver["id"], giver["id"], times)
            if len(occ) < times:
                raise DealError(_t("This chore is not coming up that often") if occ else _t("This chore cannot be taken over"))
            to = raw.get("to") if raw.get("to") in ("doer", "owner") else "doer"
            return {"t": "chore", "chore": ch["id"], "name": ch["name"], "icon": ch["icon"], "points": ch["points"],
                    "account": ch["account"], "times": times, "to": to, "dates": [o["period"] for o in occ]}
        if t == "newchore":
            if not (receiver["role"] == "parent" and giver["role"] == "kid"):
                raise DealError("New tasks are only for deals between a parent and a child")
            name = " ".join(str(raw.get("name") or "").split())[:60]
            if not name:
                raise DealError("Name is required")
            try:
                d = date.fromisoformat(str(raw.get("date") or today().isoformat()))
            except ValueError:
                raise DealError("Choose a date") from None
            if not today() <= d <= today() + timedelta(days=NEW_CHORE_DAYS):
                raise DealError("Choose a date in the next two weeks")
            icon = str(raw.get("icon") or "🧹").strip()[:8] or "🧹"
            return {"t": "newchore", "name": name, "icon": icon, "date": d.isoformat()}
        if receiver["role"] != "kid":
            raise DealError("Pets, avatar items and games can only go to a child")
        if t == "pet":
            from .pets import KINDS as PET_KINDS, MAX_PER_KIND
            pet = self.db.q1("SELECT * FROM pet WHERE id=?", _int(raw.get("id"), 1, 10 ** 9, "That is not your pet"))
            why = self._pet_problem(pet, giver["id"])
            if why:
                raise DealError(why)
            n = self.db.val("SELECT COUNT(*) FROM pet WHERE profile_id=? AND kind=? AND dead_at IS NULL", receiver["id"], pet["kind"], default=0)
            if n >= MAX_PER_KIND:
                raise DealError("The other one has the most pets of this kind already")
            return {"t": "pet", "id": pet["id"], "kind": pet["kind"], "name": pet["name"],
                    "emoji": PET_KINDS.get(pet["kind"], ("🐾",))[0]}
        if t == "avatar":
            item = str(raw.get("item") or "")
            row = self.db.q1("SELECT * FROM unlock WHERE profile_id=? AND item=?", giver["id"], item)
            it = av.ITEMS.get(item)
            if not row or not it or it[1] == "pet" or row["new_xp"] or "cost" not in it[2]:
                raise DealError("Only avatar items bought with coins can be traded")
            if self.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item=?", receiver["id"], item):
                raise DealError("The other one has this item already")
            return {"t": "avatar", "item": item, "slot": it[1], "name": it[0]}
        game = str(raw.get("game") or "")                     # t == "game"
        if not self.db.q1("SELECT 1 FROM game_pass WHERE profile_id=? AND game=? AND bought=1", giver["id"], game):
            raise DealError("Only games bought for good can be traded (not rented ones)")
        if self.db.q1("SELECT 1 FROM game_pass WHERE profile_id=? AND game=? AND bought=1", receiver["id"], game):
            raise DealError("The other one has this game already")
        return {"t": "game", "game": game, "name": self._game_title(game), "icon": self._game_icon(game)}

    @staticmethod
    def _key(it: dict, giver: int, receiver: int) -> str | None:
        """What can be in one active deal only."""
        if it["t"] == "chore":
            return f"chore:{it['chore']}:{receiver}"
        if it["t"] in ("pet", "avatar", "game"):
            return f"{it['t']}:{giver}:{it.get('id') or it.get('item') or it.get('game')}"
        return None

    def _busy(self, deal_id: int | None) -> set[str]:
        out = set()
        for d in self.db.q(f"SELECT * FROM deal WHERE status IN ({','.join('?' * len(OPEN))}) AND id!=?", *OPEN, deal_id or 0):
            terms = _j(d["terms"], {})
            for side, giver, receiver in (("a", d["a_id"], d["b_id"]), ("b", d["b_id"], d["a_id"])):
                for it in terms.get(side) or []:
                    k = self._key(it, giver, receiver)
                    if k:
                        out.add(k)
        return out

    def _side_items(self, raw, giver: dict, receiver: dict, st: dict) -> list[dict]:
        if not isinstance(raw, list):
            raise DealError("Unknown building block")
        items, coins, keys = [], 0, set()
        for r in raw[:MAX_ITEMS * 2]:
            it = self._item(r, giver, receiver, st)
            if it["t"] == "coins":
                coins += it["n"]
                continue
            k = self._key(it, giver["id"], receiver["id"]) or json.dumps(it, sort_keys=True)
            if k in keys:
                raise DealError("The same thing is in the deal twice")
            keys.add(k)
            items.append(it)
        if coins:
            items.insert(0, {"t": "coins", "n": coins})
        if len(items) > MAX_ITEMS:
            raise DealError("At most 8 things per side")
        return items

    def _terms(self, give, get, me: dict, other_p: dict, me_side: str, deal_id: int | None = None) -> dict:
        """The terms {"a": …, "b": …} from what `me` gives and gets – checked against the parents' settings, what each
        one owns and the other active deals."""
        st = self.settings()
        mine = self._side_items(give, me, other_p, st)
        theirs = self._side_items(get, other_p, me, st)
        if not mine or not theirs:
            raise DealError("Both sides need something – what do you give, what do you get?")
        kid_coins = sum(it["n"] for side, p in ((mine, me), (theirs, other_p)) if p["role"] == "kid" for it in side if it["t"] == "coins")
        if kid_coins > st["max_coins"]:
            raise DealError(_t("At most {0} coins per deal").replace("{0}", str(st["max_coins"])))
        my_coins = sum(it["n"] for it in mine if it["t"] == "coins")
        if my_coins and me["role"] == "kid" and self.rewards.available(me["id"]) < my_coins:
            raise DealError("You do not have that many coins")
        busy = self._busy(deal_id)
        for side, g, r in ((mine, me, other_p), (theirs, other_p, me)):
            for it in side:
                k = self._key(it, g["id"], r["id"])
                if k and k in busy:
                    raise DealError("This is already in another deal")
        return {me_side: mine, other(me_side): theirs}

    # ================================================================ records and views
    def _deal(self, deal_id: int) -> dict:
        d = self.db.q1("SELECT * FROM deal WHERE id=?", deal_id)
        if not d:
            raise DealError("Unknown deal")
        return d

    @staticmethod
    def side_of(d: dict, pid: int) -> str | None:
        return "a" if d["a_id"] == pid else "b" if d["b_id"] == pid else None

    def _mine(self, deal_id: int, prof: dict) -> tuple[dict, str]:
        d = self._deal(deal_id)
        side = self.side_of(d, prof["id"])
        if not side:
            raise DealError("This is not your deal")
        return d, side

    def _msg(self, deal_id: int, pid: int | None, kind: str, **data) -> int:
        return self.db.x("INSERT INTO deal_msg(deal_id, profile_id, kind, data) VALUES(?,?,?,?)",
                         deal_id, pid, kind, json.dumps(data, ensure_ascii=False))

    def _touch(self, deal_id: int, **cols) -> None:
        sets = ", ".join(f"{k}=?" for k in cols)
        self.db.x(f"UPDATE deal SET {sets}{', ' if sets else ''}updated_at=datetime('now','localtime') WHERE id=?", *cols.values(), deal_id)

    def _names(self) -> dict[int, dict]:
        return {p["id"]: p for p in self.db.q("SELECT id, name, role, avatar FROM profile")}

    def view(self, d: dict, viewer: int | None, names: dict | None = None, thread: bool = False) -> dict:
        """A deal as the viewer sees it: «give» = what the viewer gives (parents in the overview: side a)."""
        names = names or self._names()
        side = self.side_of(d, viewer) if viewer else None
        me = side or "a"
        terms, prog = _j(d["terms"], {}), _j(d["progress"], {})
        accepted = _j(d["accepted"], [])
        oid = d["b_id"] if me == "a" else d["a_id"]
        mid = d["a_id"] if me == "a" else d["b_id"]
        person = lambda pid: self._person({**names.get(pid, {"name": "?", "role": "kid", "avatar": "{}"}), "id": pid})
        turn = d["status"] == "open" and side is not None and d["by_id"] != viewer
        units = self._units(terms, prog)
        out = {"id": d["id"], "status": d["status"], "version": d["version"], "me": person(mid), "with": person(oid),
               "give": terms.get(me) or [], "get": terms.get(other(me)) or [], "by": d["by_id"],
               "accepted": accepted, "turn": turn, "reason": d["reason"], "created_at": d["created_at"],
               "updated_at": d["updated_at"], "stood_at": d["stood_at"], "ended_at": d["ended_at"],
               "progress": {"give": units.get(me), "get": units.get(other(me)),
                            "text": {"me": bool((prog.get("text") or {}).get(me)), "other": bool((prog.get("text") or {}).get(other(me)))},
                            "dispute": prog.get("dispute"), "council": prog.get("council")},
               "can": {}}
        if side:
            has_text = any(it["t"] == "text" for s in ("a", "b") for it in terms.get(s) or [])
            out["can"] = {"accept": turn, "counter": turn, "reject": turn,
                          "withdraw": d["status"] == "open" and d["by_id"] == viewer,
                          "confirm": d["status"] == "running" and has_text and not prog.get("text_done") and not prog.get("dispute"),
                          "council": d["status"] == "running" and bool(prog.get("dispute")) and not prog.get("council")}
        if thread:
            out["messages"] = []
            for m in self.db.q("SELECT * FROM deal_msg WHERE deal_id=? ORDER BY id", d["id"]):
                data = _j(m["data"], {})
                if "terms" in data:
                    data["give"], data["get"] = data["terms"].get(me) or [], data["terms"].get(other(me)) or []
                    del data["terms"]
                out["messages"].append({"id": m["id"], "kind": m["kind"], "by": m["profile_id"],
                                        "name": names.get(m["profile_id"], {}).get("name") if m["profile_id"] else None,
                                        "mine": m["profile_id"] == viewer and viewer is not None, "at": m["at"], "data": data})
        return out

    def _units(self, terms: dict, prog: dict) -> dict:
        """Per side: the services (taken-over chores, free text) and how many are done."""
        out = {}
        for s in ("a", "b"):
            tasks = (prog.get("tasks") or {}).get(s) or []
            done = (prog.get("done") or {}).get(s) or []
            has_text = any(it["t"] == "text" for it in terms.get(s) or [])
            rows = []
            for tid in tasks:
                t = self.db.q1("""SELECT t.id, t.period, t.status, c.name, c.icon, c.frequency FROM chore_task t
                                  JOIN chore c ON c.id=t.chore_id WHERE t.id=?""", tid)
                rows.append({"task": tid, "name": t["name"] if t else "?", "icon": t["icon"] if t else "🧹",
                             "period": t["period"] if t else None, "weekly": bool(t and t["frequency"] == "weekly"),
                             "status": "done" if tid in done else (t["status"] if t else "gone")})
            out[s] = {"chores": rows, "text": has_text, "text_done": bool(prog.get("text_done")),
                      "units": len(tasks) + (1 if has_text else 0),
                      "done": len(done) + (1 if has_text and prog.get("text_done") else 0)}
        return out

    def list(self, prof: dict, ended: bool = False) -> list[dict]:
        self.sweep()
        names = self._names()
        st = ENDED if ended else OPEN
        rows = self.db.q(f"""SELECT * FROM deal WHERE (a_id=? OR b_id=?) AND status IN ({','.join('?' * len(st))})
                             ORDER BY updated_at DESC, id DESC LIMIT 60""", prof["id"], prof["id"], *st)
        seen = {r["deal_id"]: r["msg_id"] for r in self.db.q("SELECT deal_id, msg_id FROM deal_seen WHERE profile_id=?", prof["id"])}
        out = []
        for d in rows:
            v = self.view(d, prof["id"], names)
            last = self.db.val("SELECT MAX(id) FROM deal_msg WHERE deal_id=? AND (profile_id IS NULL OR profile_id!=?)", d["id"], prof["id"], default=0)
            v["new"] = bool(last and last > seen.get(d["id"], 0))
            out.append(v)
        return out

    def get(self, prof: dict, deal_id: int) -> dict:
        self.sweep()
        d, _ = self._mine(deal_id, prof)
        last = self.db.val("SELECT MAX(id) FROM deal_msg WHERE deal_id=?", deal_id, default=0)
        self.db.x("""INSERT INTO deal_seen(deal_id, profile_id, msg_id) VALUES(?,?,?)
                     ON CONFLICT(deal_id, profile_id) DO UPDATE SET msg_id=excluded.msg_id""", deal_id, prof["id"], last)
        return self.view(self._deal(deal_id), prof["id"], thread=True)

    def summary(self, prof: dict) -> dict | None:
        """For the start page and the menu badge: deals waiting for this person, news since the last look."""
        if not self.can_trade(prof) and not self.db.q1("SELECT 1 FROM deal WHERE a_id=? OR b_id=? LIMIT 1", prof["id"], prof["id"]):
            return None
        try:
            self.sweep()
        except Exception:  # noqa: BLE001 – the start page must open anyway
            log.exception("deal sweep failed")
        pid = prof["id"]
        turn = int(self.db.val("SELECT COUNT(*) FROM deal WHERE status='open' AND (a_id=? OR b_id=?) AND by_id!=?", pid, pid, pid, default=0))
        rows = self.db.q("""SELECT m.*, d.a_id, d.b_id FROM deal_msg m JOIN deal d ON d.id=m.deal_id
                            LEFT JOIN deal_seen s ON s.deal_id=m.deal_id AND s.profile_id=?
                            WHERE (d.a_id=? OR d.b_id=?) AND (m.profile_id IS NULL OR m.profile_id!=?) AND m.id>COALESCE(s.msg_id, 0)
                            AND m.at>=datetime('now','localtime','-14 days') ORDER BY m.id DESC LIMIT 40""", pid, pid, pid, pid)
        names = self._names()
        notes, done = [], set()
        for m in rows:
            if m["deal_id"] in done:
                continue
            done.add(m["deal_id"])
            oid = m["b_id"] if m["a_id"] == pid else m["a_id"]
            notes.append({"deal": m["deal_id"], "msg": m["id"], "kind": m["kind"], "with": names.get(oid, {}).get("name", "?")})
        approval = int(self.db.val("SELECT COUNT(*) FROM deal WHERE status='approval'", default=0)) if prof["role"] == "parent" else 0
        return {"on": self.can_trade(prof), "turn": turn, "notes": notes[:5], "approval": approval}

    def seen(self, prof: dict, deal_id: int, msg_id: int) -> None:
        d, _ = self._mine(deal_id, prof)
        self.db.x("""INSERT INTO deal_seen(deal_id, profile_id, msg_id) VALUES(?,?,?)
                     ON CONFLICT(deal_id, profile_id) DO UPDATE SET msg_id=MAX(msg_id, excluded.msg_id)""", deal_id, prof["id"], int(msg_id))

    # ================================================================ offer, counter-offer, answer
    def offer(self, prof: dict, to_id: int, give, get, text: str = "") -> dict:
        with self.lock, self.db.tx():
            o = self._prof(int(to_id))
            self._check_pair(prof, o)
            terms = self._terms(give, get, prof, o, "a")
            did = self.db.x("INSERT INTO deal(a_id, b_id, terms, by_id, accepted) VALUES(?,?,?,?,?)",
                            prof["id"], o["id"], json.dumps(terms, ensure_ascii=False), prof["id"], json.dumps([prof["id"]]))
            self._msg(did, prof["id"], "offer", version=1, terms=terms, text=self._text(text))
            self.db.x("INSERT OR REPLACE INTO deal_seen(deal_id, profile_id, msg_id) VALUES(?,?,?)", did, prof["id"],
                      self.db.val("SELECT MAX(id) FROM deal_msg WHERE deal_id=?", did, default=0))
        return self.get(prof, did)

    @staticmethod
    def _text(text) -> str:
        return " ".join(str(text or "").split())[:MAX_TEXT]

    def _my_turn(self, d: dict, prof: dict) -> None:
        if d["status"] != "open":
            raise DealError("This deal is no longer open")
        if d["by_id"] == prof["id"]:
            raise DealError("Wait for the answer of the other one")

    def counter(self, prof: dict, deal_id: int, give, get, text: str = "", version: int | None = None) -> dict:
        with self.lock, self.db.tx():
            d, side = self._mine(deal_id, prof)
            self._my_turn(d, prof)
            if version is not None and int(version) != d["version"]:
                raise DealError("The offer changed meanwhile – look again")
            o = self._prof(d["b_id"] if side == "a" else d["a_id"])
            self._check_pair(prof, o)
            terms = self._terms(give, get, prof, o, side, deal_id)
            v = d["version"] + 1
            self._touch(deal_id, version=v, terms=json.dumps(terms, ensure_ascii=False), by_id=prof["id"],
                        accepted=json.dumps([prof["id"]]))
            self._msg(deal_id, prof["id"], "counter", version=v, terms=terms, text=self._text(text))
        return self.get(prof, deal_id)

    def reject(self, prof: dict, deal_id: int, text: str = "") -> dict:
        with self.lock, self.db.tx():
            d, _ = self._mine(deal_id, prof)
            self._my_turn(d, prof)
            self._touch(deal_id, status="rejected", ended_at=self._now())
            self._msg(deal_id, prof["id"], "reject", text=self._text(text))
        return self.get(prof, deal_id)

    def withdraw(self, prof: dict, deal_id: int) -> dict:
        with self.lock, self.db.tx():
            d, _ = self._mine(deal_id, prof)
            if d["status"] != "open" or d["by_id"] != prof["id"]:
                raise DealError("This offer cannot be withdrawn now")
            self._touch(deal_id, status="withdrawn", ended_at=self._now())
            self._msg(deal_id, prof["id"], "withdraw")
        return self.get(prof, deal_id)

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def accept(self, prof: dict, deal_id: int, version: int) -> dict:
        """Accept exactly this version – the deal stands when both accepted the same one."""
        with self.lock, self.db.tx():
            d, side = self._mine(deal_id, prof)
            self._my_turn(d, prof)
            if int(version) != d["version"]:
                raise DealError("The offer changed meanwhile – look again")
            accepted = sorted(set(_j(d["accepted"], [])) | {prof["id"]})
            self._touch(deal_id, accepted=json.dumps(accepted))
            self._msg(deal_id, prof["id"], "accept", version=d["version"])
            if {d["a_id"], d["b_id"]} <= set(accepted):
                self._stand(self._deal(deal_id))
        return self.get(prof, deal_id)

    # ================================================================ the deal stands
    def _revalidate(self, d: dict) -> dict:
        """Everything still owned and free – the stored terms checked again (coins of both children too)."""
        a, b = self._prof(d["a_id"]), self._prof(d["b_id"])
        terms = _j(d["terms"], {})
        st = self.settings()
        busy = self._busy(d["id"])
        for side, g, r in (("a", a, b), ("b", b, a)):
            fresh = []
            for it in terms.get(side) or []:
                if it["t"] == "chore":
                    ch = self._chore(it["chore"])
                    occ = self._occurrences(ch, r["id"], g["id"], it["times"])
                    if len(occ) < it["times"]:
                        raise DealError("This chore cannot be taken over")
                    it = {**it, "dates": [o["period"] for o in occ]}
                elif it["t"] not in ("coins", "text", "newchore"):
                    it = self._item(it, g, r, st)
                k = self._key(it, g["id"], r["id"])
                if k and k in busy:
                    raise DealError("This is already in another deal")
                fresh.append(it)
            coins = sum(it["n"] for it in fresh if it["t"] == "coins")
            if coins and g["role"] == "kid" and self.rewards.available(g["id"]) < coins:
                raise DealError(_t("{0} does not have that many coins").replace("{0}", g["name"]))
            terms[side] = fresh
        return terms

    def needs_approval(self, d: dict, terms: dict) -> bool:
        roles = {self.db.val("SELECT role FROM profile WHERE id=?", d["a_id"]), self.db.val("SELECT role FROM profile WHERE id=?", d["b_id"])}
        if "parent" in roles:
            return False                                       # a deal with a parent never needs a parent's approval
        st = self.settings()
        coins = sum(it["n"] for s in ("a", "b") for it in terms.get(s) or [] if it["t"] == "coins")
        pets = any(it["t"] == "pet" for s in ("a", "b") for it in terms.get(s) or [])
        return (st["approval"] and coins >= st["threshold"]) or (st["approval_pets"] and pets)

    def _stand(self, d: dict) -> None:
        terms = self._revalidate(d)
        self._touch(d["id"], terms=json.dumps(terms, ensure_ascii=False))
        if self.needs_approval(d, terms):
            self._touch(d["id"], status="approval")
            self._hold_all(d["id"], d, terms)
            self._msg(d["id"], None, "approval")
            return
        self._start(self._deal(d["id"]))

    def _hold_all(self, deal_id: int, d: dict, terms: dict) -> None:
        for side, gid in (("a", d["a_id"]), ("b", d["b_id"])):
            self._hold(deal_id, gid, terms.get(side) or [])

    def _hold(self, deal_id: int, gid: int, items: list[dict]) -> None:
        role = self.db.val("SELECT role FROM profile WHERE id=?", gid)
        for it in items:
            if it["t"] == "coins" and role == "kid":
                self.db.x("INSERT INTO deal_hold(deal_id, profile_id, kind, amount) VALUES(?,?, 'coins', ?)", deal_id, gid, it["n"])
            elif it["t"] in ("pet", "avatar", "game"):
                self.db.x("INSERT INTO deal_hold(deal_id, profile_id, kind, ref) VALUES(?,?,?,?)", deal_id, gid, it["t"],
                          str(it.get("id") or it.get("item") or it.get("game")))

    def _release(self, deal_id: int) -> None:
        self.db.x("UPDATE deal_hold SET active=0 WHERE deal_id=? AND active=1", deal_id)

    def locked(self, kind: str, ref, pid: int | None = None) -> bool:
        """An item promised in a deal that stands (pets: no pet hotel / sitter meanwhile)."""
        sql = "SELECT 1 FROM deal_hold WHERE kind=? AND ref=? AND active=1" + (" AND profile_id=?" if pid else "")
        return bool(self.db.q1(sql, kind, str(ref), *([pid] if pid else [])))

    def approve(self, parent: dict, deal_id: int, ok: bool) -> dict:
        with self.lock, self.db.tx():
            d = self._deal(deal_id)
            if d["status"] != "approval":
                raise DealError("This deal does not wait for approval")
            self._release(deal_id)
            if not ok:
                self._touch(deal_id, status="declined", ended_at=self._now())
                self._msg(deal_id, parent["id"], "declined")
            else:
                self._msg(deal_id, parent["id"], "approved")
                self._revalidate(d)
                self._start(self._deal(deal_id))
        return self.view(self._deal(deal_id), None, thread=True)

    def _start(self, d: dict) -> None:
        """The deal stands: chores move, new tasks are made, payments without services are transferred, the rest reserved."""
        terms = _j(d["terms"], {})
        pid = {"a": d["a_id"], "b": d["b_id"]}
        prog = {"tasks": {"a": [], "b": []}, "done": {"a": [], "b": []}, "owner_pay": [], "new_chores": [],
                "text": {"a": False, "b": False}, "text_done": False, "paid_units": {"a": 0, "b": 0}, "items_done": {"a": False, "b": False}}
        for s in ("a", "b"):
            doer, owner = pid[s], pid[other(s)]
            for it in terms.get(s) or []:
                if it["t"] == "chore":
                    ch = self._chore(it["chore"])
                    occ = self._occurrences(ch, owner, doer, it["times"], create=True)
                    if len(occ) < it["times"]:
                        raise DealError("This chore cannot be taken over")
                    for o in occ:
                        n = self.db.x("""UPDATE chore_task SET profile_id=?, from_id=?, deal_id=? WHERE id=? AND status='open'
                                         AND deal_id IS NULL""", doer, owner, d["id"], o["task"])
                        if not n:
                            raise DealError("This chore cannot be taken over")
                        prog["tasks"][s].append(o["task"])
                        if it["to"] == "owner":
                            prog["owner_pay"].append(o["task"])
                elif it["t"] == "newchore":
                    cid = self.fq.chores.save({"name": it["name"], "icon": it["icon"], "points": 0, "frequency": "once",
                                               "date": it["date"], "profiles": [doer], "confirm": True, "kind": "bonus"})
                    prog["new_chores"].append(cid)
                    tid = self.db.x("INSERT INTO chore_task(chore_id, profile_id, period, from_id, deal_id) VALUES(?,?,?,?,?)",
                                    cid, doer, it["date"], owner, d["id"])
                    prog["tasks"][s].append(tid)
        self._touch(d["id"], status="running", stood_at=self._now(), progress=json.dumps(prog))
        self._msg(d["id"], None, "stand")
        units = self._units(terms, prog)
        for s in ("a", "b"):
            o = other(s)                     # side s pays for the services of side o
            if units[o]["units"] == 0:
                self._safe(d["id"], lambda s=s: self._pay_all(self._deal(d["id"]), s))
            else:
                self._hold(d["id"], pid[s], terms.get(s) or [])
        self._check_done(d["id"])
        for p in (d["a_id"], d["b_id"]):
            self.fq.chores._changed(p)

    # ================================================================ transfers
    def _book_once(self, ref: str) -> bool:
        return bool(self.db.x("INSERT OR IGNORE INTO deal_pay(ref) VALUES(?)", ref))

    def _coins(self, d: dict, giver: int, receiver: int, amount: int, ref: str) -> None:
        if amount <= 0 or not self._book_once(ref):
            return
        names = self._names()
        g, r = names.get(giver, {}), names.get(receiver, {})
        if g.get("role") == "kid":
            self.rewards.book(giver, "coins", -float(amount), "deal", _t("Deal with") + f" {r.get('name', '?')}", ref)
            self.db.x("UPDATE deal_hold SET paid=paid+? WHERE deal_id=? AND profile_id=? AND kind='coins' AND active=1",
                      amount, d["id"], giver)
        if r.get("role") == "kid":           # coins to a parent go to the parents (no parent account)
            self.rewards.book(receiver, "coins", float(amount), "deal", _t("Deal with") + f" {g.get('name', '?')}", ref)
        self._msg(d["id"], None, "coins", n=amount, giver=giver, receiver=receiver)

    def _item_move(self, d: dict, it: dict, giver: int, receiver: int) -> None:
        ref = f"deal:{d['id']}:{it['t']}:{it.get('id') or it.get('item') or it.get('game')}"
        if not self._book_once(ref):
            return
        if it["t"] == "pet":
            pet = self.db.q1("SELECT * FROM pet WHERE id=?", it["id"])
            if not pet or pet["profile_id"] != giver or pet["dead_at"]:
                raise _Gone()
            kind = pet["kind"]
            self.db.x("UPDATE pet SET profile_id=?, sitter_id=NULL, sit_until=NULL WHERE id=?", receiver, pet["id"])
            self.db.x("INSERT OR IGNORE INTO unlock(profile_id, item) VALUES(?,?)", receiver, kind)
            if not self.db.val("SELECT COUNT(*) FROM pet WHERE profile_id=? AND kind=? AND dead_at IS NULL", giver, kind, default=0):
                self.db.x("DELETE FROM unlock WHERE profile_id=? AND item=?", giver, kind)
                self._unwear(giver, "pet", kind)
        elif it["t"] == "avatar":
            if not self.db.x("DELETE FROM unlock WHERE profile_id=? AND item=? AND new_xp=0", giver, it["item"]):
                raise _Gone()
            self.db.x("INSERT OR IGNORE INTO unlock(profile_id, item) VALUES(?,?)", receiver, it["item"])
            self._unwear(giver, it["slot"], it["item"])
        elif it["t"] == "game":
            if not self.db.x("UPDATE game_pass SET bought=0, bought_at=NULL WHERE profile_id=? AND game=? AND bought=1", giver, it["game"]):
                raise _Gone()
            self.db.x("""INSERT INTO game_pass(profile_id, game, bought, bought_at) VALUES(?,?,1,?)
                         ON CONFLICT(profile_id, game) DO UPDATE SET bought=1, bought_at=excluded.bought_at""",
                      receiver, it["game"], self._now())
        self.db.x("UPDATE deal_hold SET active=0 WHERE deal_id=? AND profile_id=? AND kind=? AND ref=?", d["id"], giver, it["t"],
                  str(it.get("id") or it.get("item") or it.get("game")))
        self._msg(d["id"], None, "item", item=it, giver=giver, receiver=receiver)

    def _unwear(self, pid: int, slot: str, item: str) -> None:
        p = self.db.q1("SELECT avatar FROM profile WHERE id=?", pid)
        a = _j((p or {}).get("avatar"), {})
        if (a.get("items") or {}).get(slot) == item:
            a["items"].pop(slot, None)
            self.db.x("UPDATE profile SET avatar=? WHERE id=?", json.dumps(a), pid)

    def _pay_all(self, d: dict, s: str) -> None:
        """Side s pays everything at once (no services on the other side)."""
        terms = _j(d["terms"], {})
        giver, receiver = (d["a_id"], d["b_id"]) if s == "a" else (d["b_id"], d["a_id"])
        for it in terms.get(s) or []:
            if it["t"] == "coins":
                self._coins(d, giver, receiver, it["n"], f"deal:{d['id']}:coins:{s}:all")
            elif it["t"] in ("pet", "avatar", "game"):
                self._item_move(d, it, giver, receiver)
        prog = _j(self._deal(d["id"])["progress"], {})
        prog.setdefault("items_done", {})[s] = True
        self._touch(d["id"], progress=json.dumps(prog))

    def _unit_done(self, d: dict, s: str) -> None:
        """One service of side s is done: the other side pays its share (items with the last one)."""
        prog = _j(d["progress"], {})
        terms = _j(d["terms"], {})
        o = other(s)
        n = self._units(terms, prog)[s]["units"]
        k = int((prog.get("paid_units") or {}).get(s, 0)) + 1
        if k > n:
            return
        prog.setdefault("paid_units", {})[s] = k
        self._touch(d["id"], progress=json.dumps(prog))
        giver, receiver = (d["a_id"], d["b_id"]) if o == "a" else (d["b_id"], d["a_id"])
        total = sum(it["n"] for it in terms.get(o) or [] if it["t"] == "coins")
        share = total * k // n - total * (k - 1) // n
        self._coins(d, giver, receiver, share, f"deal:{d['id']}:coins:{o}:{k}")
        if k == n:
            for it in terms.get(o) or []:
                if it["t"] in ("pet", "avatar", "game"):
                    self._item_move(self._deal(d["id"]), it, giver, receiver)
            prog = _j(self._deal(d["id"])["progress"], {})
            prog.setdefault("items_done", {})[o] = True
            self._touch(d["id"], progress=json.dumps(prog))
            self.db.x("UPDATE deal_hold SET active=0 WHERE deal_id=? AND profile_id=? AND active=1", d["id"], giver)

    def _check_done(self, deal_id: int) -> None:
        d = self._deal(deal_id)
        if d["status"] != "running":
            return
        terms, prog = _j(d["terms"], {}), _j(d["progress"], {})
        units = self._units(terms, prog)
        if all(units[s]["done"] >= units[s]["units"] for s in ("a", "b")) and all((prog.get("items_done") or {}).get(s) for s in ("a", "b")):
            self._release(deal_id)
            self._touch(deal_id, status="done", ended_at=self._now())
            self._msg(deal_id, None, "done")

    def _safe(self, deal_id: int, fn) -> None:
        """Run a transfer step; an item that is gone meanwhile makes the deal fail (inside the same transaction)."""
        try:
            fn()
        except _Gone:
            self._fail(self._deal(deal_id), "gone")

    # ================================================================ chores of a deal (called by chores.py)
    def reward_to(self, t: dict) -> int:
        d = self.db.q1("SELECT * FROM deal WHERE id=?", t["deal_id"])
        if d and t["id"] in (_j(d["progress"], {}).get("owner_pay") or []) and t.get("from_id"):
            return t["from_id"]
        return t["profile_id"]

    def chore_done(self, t: dict) -> None:
        with self.lock:
            d = self.db.q1("SELECT * FROM deal WHERE id=?", t["deal_id"])
            if not d or d["status"] != "running":
                return
            prog = _j(d["progress"], {})
            for s in ("a", "b"):
                if t["id"] in ((prog.get("tasks") or {}).get(s) or []) and t["id"] not in ((prog.get("done") or {}).get(s) or []):
                    prog.setdefault("done", {}).setdefault(s, []).append(t["id"])
                    self._touch(d["id"], progress=json.dumps(prog))
                    self._msg(d["id"], None, "chore", name=t["name"], icon=t.get("icon"), doer=t["profile_id"])
                    self._safe(d["id"], lambda: self._unit_done(self._deal(d["id"]), s))
                    self._check_done(d["id"])
                    return

    def chore_rejected(self, t: dict) -> None:
        with self.lock, self.db.tx():
            d = self.db.q1("SELECT * FROM deal WHERE id=?", t["deal_id"])
            if d and d["status"] == "running":
                self._fail(d, "rejected", keep=None, chore=t["name"])

    # ================================================================ failure, cancel
    def _fail(self, d: dict, reason: str, keep: int | None = None, chore: str | None = None, status: str = "failed",
              by: int | None = None) -> None:
        """Release every reservation; open taken-over chores go back to their owner (`keep`: the missed one stays)."""
        if d["status"] in ENDED:
            return
        prog = _j(d["progress"], {})
        self._release(d["id"])
        new = set(prog.get("new_chores") or [])
        for tid in [x for s in ("a", "b") for x in ((prog.get("tasks") or {}).get(s) or [])]:
            t = self.db.q1("SELECT * FROM chore_task WHERE id=?", tid)
            if not t or t["status"] != "open" or tid == keep:
                continue
            if t["chore_id"] in new:
                self.db.x("DELETE FROM chore_task WHERE id=?", tid)
            elif t["from_id"]:
                self.db.x("UPDATE chore_task SET profile_id=?, from_id=NULL, deal_id=NULL, redo=0 WHERE id=?", t["from_id"], tid)
        for cid in new:
            if not self.db.q1("SELECT 1 FROM chore_task WHERE chore_id=? AND status!='open'", cid):
                self.db.x("UPDATE chore SET active=0 WHERE id=?", cid)
        self._touch(d["id"], status=status, reason=reason, ended_at=self._now())
        self._msg(d["id"], by, "cancelled" if status == "cancelled" else "failed", reason=reason, chore=chore)
        for p in (d["a_id"], d["b_id"]):
            self.fq.chores._changed(p)

    def cancel(self, parent: dict, deal_id: int) -> dict:
        with self.lock, self.db.tx():
            d = self._deal(deal_id)
            if d["status"] not in OPEN:
                raise DealError("This deal is over already")
            self._fail(d, "cancelled", status="cancelled", by=parent["id"])
        return self.view(self._deal(deal_id), None, thread=True)

    def sweep(self) -> None:
        """Missed and removed chores, council results – called on every look and by the periodic tick."""
        with self.lock:
            for d in self.db.q("SELECT * FROM deal WHERE status='running'"):
                with self.db.tx():
                    d = self._deal(d["id"])
                    if d["status"] != "running":
                        continue
                    prog = _j(d["progress"], {})
                    for s in ("a", "b"):
                        done = set((prog.get("done") or {}).get(s) or [])
                        for tid in (prog.get("tasks") or {}).get(s) or []:
                            if tid in done:
                                continue
                            t = self.db.q1("""SELECT t.*, c.name, c.frequency, c.active FROM chore_task t JOIN chore c ON c.id=t.chore_id
                                              WHERE t.id=?""", tid)
                            if not t or t["deal_id"] != d["id"] or not t["active"]:
                                self._fail(d, "removed", chore=t["name"] if t else None)
                                break
                            if t["status"] == "open" and self._due_end(t["period"], t["frequency"] == "weekly") < today():
                                self._fail(d, "missed", keep=tid, chore=t["name"])
                                break
                        if self._deal(d["id"])["status"] != "running":
                            break
                    if self._deal(d["id"])["status"] == "running" and prog.get("council"):
                        self._council_result(self._deal(d["id"]))

    def tick(self) -> None:
        try:
            self.sweep()
        except Exception:  # noqa: BLE001
            log.exception("deal sweep failed")

    # ================================================================ free text
    def confirm(self, prof: dict, deal_id: int, ok: bool) -> dict:
        """«Done ✓» for the free text of the deal – or «not done» (a parent settles it, or the family council)."""
        with self.lock, self.db.tx():
            d, side = self._mine(deal_id, prof)
            terms, prog = _j(d["terms"], {}), _j(d["progress"], {})
            if d["status"] != "running" or not any(it["t"] == "text" for s in ("a", "b") for it in terms.get(s) or []):
                raise DealError("There is nothing to confirm")
            if prog.get("text_done") or prog.get("dispute"):
                raise DealError("This is decided already")
            if not ok:
                prog["dispute"] = {"by": prof["id"]}
                self._touch(deal_id, progress=json.dumps(prog))
                self._msg(deal_id, prof["id"], "dispute")
            else:
                prog.setdefault("text", {})[side] = True
                self._touch(deal_id, progress=json.dumps(prog))
                self._msg(deal_id, prof["id"], "confirm")
                if all(prog["text"].get(s) for s in ("a", "b")):
                    self._text_done(self._deal(deal_id))
        return self.get(prof, deal_id)

    def _text_done(self, d: dict) -> None:
        prog = _j(d["progress"], {})
        prog["text_done"], prog["dispute"] = True, None
        self._touch(d["id"], progress=json.dumps(prog))
        terms = _j(d["terms"], {})
        for s in ("a", "b"):
            if any(it["t"] == "text" for it in terms.get(s) or []):
                self._safe(d["id"], lambda s=s: self._unit_done(self._deal(d["id"]), s))
        self._check_done(d["id"])

    def settle(self, parent: dict, deal_id: int, done: bool) -> dict:
        """A parent decides a free deal the two do not agree on."""
        with self.lock, self.db.tx():
            d = self._deal(deal_id)
            prog = _j(d["progress"], {})
            if d["status"] != "running" or prog.get("text_done"):
                raise DealError("There is nothing to settle")
            self._msg(deal_id, parent["id"], "settled", done=bool(done))
            if done:
                self._text_done(d)
            else:
                self._fail(d, "text")
        return self.view(self._deal(deal_id), None, thread=True)

    def to_council(self, prof: dict, deal_id: int, lang: str = "") -> dict:
        """The two do not agree: the family council votes «done» or «not done» (community.py)."""
        from .translations import BUILTIN, builtin_dict
        with self.lock, self.db.tx():
            d, _ = self._mine(deal_id, prof)
            prog = _j(d["progress"], {})
            if d["status"] != "running" or not prog.get("dispute") or prog.get("council"):
                raise DealError("There is nothing to send to the family council")
            tr = builtin_dict(lang) if lang in BUILTIN else {}
            t = lambda s: tr.get(s) or s
            names = self._names()
            texts = [it["text"] for s in ("a", "b") for it in _j(d["terms"], {}).get(s) or [] if it["t"] == "text"]
            title = f"🤝 {names[d['a_id']]['name']} ↔ {names[d['b_id']]['name']}: " + " / ".join(texts)
            tid = self.fq.community.open_topic(prof, title[:100], t("Was the deal fulfilled?"),
                                               ["✓ " + t("Done – the deal is fulfilled"), "✗ " + t("Not done – the deal fails")],
                                               vote_now=True)
            prog["council"] = tid
            self._touch(deal_id, progress=json.dumps(prog))
            self._msg(deal_id, prof["id"], "council", topic=tid)
        return self.get(prof, deal_id)

    def _council_result(self, d: dict) -> None:
        prog = _j(d["progress"], {})
        topic = self.db.q1("SELECT * FROM council_topic WHERE id=?", prog["council"])
        if not topic:
            prog["council"] = None                              # the topic was deleted: a parent settles it
            self._touch(d["id"], progress=json.dumps(prog))
            return
        if topic["status"] != "closed":
            return
        res = _j(topic["result"], {})
        win = res.get("winners") or []
        if res.get("decided") and len(win) == 1:
            if win[0].startswith("✓"):
                self._msg(d["id"], None, "settled", done=True, council=True)
                self._text_done(d)
            else:
                self._fail(d, "council")
        else:
            prog["council_open"] = True                         # no decision: a parent settles it
            self._touch(d["id"], progress=json.dumps(prog))

    # ================================================================ parents
    def overview(self) -> dict:
        self.sweep()
        names = self._names()
        rows = self.db.q("SELECT * FROM deal ORDER BY CASE status WHEN 'approval' THEN 0 WHEN 'running' THEN 1 WHEN 'open' THEN 2 ELSE 3 END, updated_at DESC, id DESC LIMIT 200")
        out = []
        for d in rows:
            v = self.view(d, None, names)
            v["a"], v["b"] = v["me"], v["with"]
            out.append(v)
        return {"deals": out, "settings": self.settings(),
                "kids": [self._person(p) for p in self.db.q("SELECT * FROM profile WHERE archived=0 AND role='kid' ORDER BY name")]}

    def thread(self, deal_id: int) -> dict:
        v = self.view(self._deal(deal_id), None, thread=True)
        v["a"], v["b"] = v["me"], v["with"]
        return v


class _Gone(Exception):
    """An item of the deal is no longer there when it should be transferred."""


TEXTS = [_t("You cannot make a deal with yourself"), _t("Parents do not trade with each other"), _t("Trading is switched off for you"),
         _t("Trading is switched off for this person"), _t("Unknown building block"), _t("This building block is switched off by the parents"),
         _t("Coins: a whole number from 1"), _t("Write what the free deal is"), _t("Unknown chore"), _t("Times: 1 to 10"),
         _t("New tasks are only for deals between a parent and a child"), _t("Choose a date in the next two weeks"),
         _t("Pets, avatar items and games can only go to a child"), _t("The other one has the most pets of this kind already"),
         _t("Only avatar items bought with coins can be traded"), _t("The other one has this item already"),
         _t("Only games bought for good can be traded (not rented ones)"), _t("The other one has this game already"),
         _t("The same thing is in the deal twice"), _t("At most 8 things per side"),
         _t("Both sides need something – what do you give, what do you get?"), _t("You do not have that many coins"),
         _t("This is already in another deal"), _t("Unknown deal"), _t("This is not your deal"), _t("This deal is no longer open"),
         _t("Wait for the answer of the other one"), _t("The offer changed meanwhile – look again"),
         _t("This offer cannot be withdrawn now"), _t("This deal does not wait for approval"), _t("This deal is over already"),
         _t("There is nothing to confirm"), _t("This is decided already"), _t("There is nothing to settle"),
         _t("There is nothing to send to the family council"), _t("Unknown profile"), _t("Name is required"), _t("Choose a date"),
         _t("That is not your pet"), _t("This pet is part of a deal"),
         _t("Was the deal fulfilled?"), _t("Done – the deal is fulfilled"), _t("Not done – the deal fails")]
