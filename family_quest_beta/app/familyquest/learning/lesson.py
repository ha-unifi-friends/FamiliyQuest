"""Learning service: progress per item, unit stars, building and running sessions."""
from __future__ import annotations

import json
import random
import secrets
from datetime import date, datetime

from ..db import Database, profile_settings
from ..i18n import _t
from ..packs.registry import PackInfo, PackStore, UnitInfo
from ..rewards.engine import Rewards, today
from . import exercises as ex
from .leitner import next_state, stars

MODES = ("path", "daily", "quiz", "cards")
QUIZ_TIMER = 15


class LearnError(ValueError):
    pass


class Learning:
    def __init__(self, db: Database, packs: PackStore, rewards: Rewards):
        self.db = db
        self.packs = packs
        self.rewards = rewards
        self.listeners: list = []

    # ---------------------------------------------------------------- state
    def states(self, pid: int, pack_id: str, unit_id: str | None = None) -> dict[str, dict]:
        if unit_id:
            rows = self.db.q("SELECT * FROM item_state WHERE profile_id=? AND pack_id=? AND unit_id=?", pid, pack_id, unit_id)
        else:
            rows = self.db.q("SELECT * FROM item_state WHERE profile_id=? AND pack_id=?", pid, pack_id)
        return {r["item_key"]: r for r in rows}

    def unit_stars(self, pid: int, pack: PackInfo, unit: UnitInfo, st: dict | None = None) -> int:
        st = st if st is not None else self.states(pid, pack.id, unit.id)
        return stars([st.get(k, {}).get("box", 0) for k in unit.keys(pack.id)])

    def pack_progress(self, pid: int, pack: PackInfo) -> dict:
        st = self.states(pid, pack.id)
        units, unlocked = [], True
        path = getattr(pack.model, "pfad", False)
        if path and self.db.val("SELECT role FROM profile WHERE id=?", pid) == "parent":
            path = False                          # parents try out every unit, nothing is locked for them
        for u in pack.units:
            s = self.unit_stars(pid, pack, u, st)
            keys = u.keys(pack.id)
            due = sum(1 for k in keys if k in st and st[k]["box"] > 0 and (st[k]["due"] or "") <= today().isoformat())
            seen = sum(1 for k in keys if k in st)
            boxes = [0] * 6                       # Leitner card box: [new, box 1 … box 5]
            for k in keys:
                boxes[min(5, st[k]["box"]) if k in st else 0] += 1
            units.append({"id": u.id, "title": u.title, "kind": u.kind, "icon": u.icon, "stars": s, "unlocked": unlocked,
                          "due": due, "seen": seen, "count": len(keys), "exercises": u.exercises, "boxes": boxes})
            unlocked = (unlocked and s >= 1) or not path
        total = sum(u["stars"] for u in units)
        nxt = next((u for u in units if u["unlocked"] and u["stars"] < 5), None)
        cards = [u for u in units if u["kind"] == "cards"]
        return {"units": units, "stars": total, "max_stars": 5 * len(units),
                "boxes": [sum(u["boxes"][i] for u in cards) for i in range(6)],
                "percent": round(100 * total / max(1, 5 * len(units))), "next": nxt["id"] if nxt else None,
                "due": sum(u["due"] for u in units)}

    # ---------------------------------------------------------------- selection
    @staticmethod
    def _pick_cards(unit: UnitInfo, st: dict, n: int, n_new: int, rng: random.Random) -> list[dict]:
        t = today().isoformat()
        due, new, rest = [], [], []
        for it in unit.items:
            s = st.get(it["key"])
            if not s or s["box"] == 0:
                new.append(it)
            elif (s["due"] or "") <= t:
                due.append((s["box"], s["due"] or "", it))
            else:
                rest.append((s["box"], s["last_seen"] or "", it))
        due.sort(key=lambda x: (x[0], x[1]))
        rest.sort(key=lambda x: (x[0], x[1]))
        out = [x[2] for x in due[:n]]
        out += new[:max(0, min(n_new, n - len(out)))]
        out += [x[2] for x in rest[:max(0, n - len(out))]]
        if len(out) < n and unit.items:            # small unit: repeat, but never the same twice in a row
            pool = list(unit.items)
            while len(out) < n:
                rng.shuffle(pool)
                out += [p for p in pool if not out or p["key"] != out[-1]["key"]][: n - len(out)]
        return out

    @staticmethod
    def _skill_weights(pack: PackInfo, unit: UnitInfo, st: dict) -> list[float]:
        ws = []
        for s in unit.skills:
            k = f"{pack.id}:{unit.id}:@{s}"
            r = st.get(k)
            if not r:
                ws.append(3.0)
                continue
            tries = r["correct"] + r["wrong"]
            err = r["wrong"] / tries if tries else 0.5
            ws.append(1.0 + 5.0 * err + 0.4 * (5 - r["box"]))
        return ws

    def _steps_for_unit(self, pid: int, pack: PackInfo, unit: UnitInfo, n: int, n_new: int, rng: random.Random,
                        mode: str) -> list[dict]:
        st = self.states(pid, pack.id, unit.id)
        if unit.kind == "generator":
            if not unit.skills:
                return []
            ws = self._skill_weights(pack, unit, st)
            timer = QUIZ_TIMER if mode == "quiz" else 0
            return [ex.generator_step(pack, unit, rng.choices(unit.skills, ws)[0], rng, timer) for _ in range(n)]
        if not unit.items:
            return []
        kinds = unit.exercises
        if mode == "cards":
            return [ex.card_step(pack, unit, it) for it in self._pick_cards(unit, st, n, n, rng)]
        if mode == "quiz":
            learned = [it for it in unit.items if st.get(it["key"], {}).get("box", 0) >= 1] or unit.items
            sel = rng.sample(learned, min(n, len(learned)))
            while len(sel) < n:
                sel.append(rng.choice(learned))
            return [ex.choice_step(pack, unit, it, unit.items, rng, reverse=rng.random() < 0.3, timer=QUIZ_TIMER) for it in sel]
        if kinds == ["zuordnen"] or ("zuordnen" in kinds and len(kinds) == 1):
            per = 6
            sel = self._pick_cards(unit, st, max(per, min(len(unit.items), n // 2 * per)), n_new * 2, rng)
            steps = []
            for i in range(0, len(sel), per):
                chunk = sel[i:i + per]
                uniq = list({c["key"]: c for c in chunk}.values())
                if len(uniq) >= 3:
                    steps.append(ex.sort_step(pack, unit, uniq, rng, unit.items))
            return steps[: max(1, n // 4)]
        sel = self._pick_cards(unit, st, n, n_new, rng)
        steps: list[dict] = []
        group: list[dict] = []
        for it in sel:
            box = st.get(it["key"], {}).get("box", 0)
            v = it["view"]
            options = []
            if box == 0:
                options = [k for k in ("auswahl", "karteikarte") if k in kinds] or kinds
            else:
                if "auswahl" in kinds:
                    options.append("auswahl")
                if "eintippen" in kinds and box >= 1:
                    options += ["eintippen"] * (2 if box >= 2 else 1)
                if "lueckentext" in kinds and v["sentence"]:
                    options += ["lueckentext"] * 2
                if "hoeren" in kinds and pack.lang and v["prompt"]:
                    options.append("hoeren")
                if "paare" in kinds:
                    options.append("paare")
                if "zuordnen" in kinds:
                    options.append("zuordnen")
                if "karteikarte" in kinds and not options:
                    options.append("karteikarte")
            k = rng.choice(options or ["auswahl"])
            if k in ("paare", "zuordnen"):
                group.append(it)
                if len(group) >= 4:
                    steps.append(ex.pairs_step(pack, unit, group, rng) if k == "paare"
                                 else ex.sort_step(pack, unit, group, rng, unit.items))
                    group = []
                continue
            if k == "eintippen":
                steps.append(ex.type_step(pack, unit, it))
            elif k == "lueckentext" and v["sentence"]:
                steps.append(ex.gap_step(pack, unit, it, unit.items, rng))
            elif k == "hoeren":
                steps.append(ex.listen_step(pack, unit, it, unit.items, rng))
            elif k == "karteikarte":
                steps.append(ex.card_step(pack, unit, it))
            else:
                steps.append(ex.choice_step(pack, unit, it, unit.items, rng, reverse=box >= 2 and rng.random() < 0.3))
        for it in group:                       # leftovers that did not fill a pairs round
            steps.append(ex.choice_step(pack, unit, it, unit.items, rng))
        # a pairs round needs enough distinct cards
        if "paare" in kinds and len(unit.items) >= 4 and not any(s["kind"] == "paare" for s in steps) and len(steps) >= 6:
            seen = [it for it in unit.items if st.get(it["key"], {}).get("box", 0) >= 1]
            if len(seen) >= 4:
                steps.append(ex.pairs_step(pack, unit, rng.sample(seen, 4), rng))
        return steps

    def build(self, pid: int, mode: str, pack_id: str | None = None, unit_id: str | None = None,
              seed: int | None = None) -> dict:
        if mode not in MODES:
            raise LearnError("unknown mode")
        prof = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
        if not prof:
            raise LearnError("unknown profile")
        ps = profile_settings(prof)
        self._check_hours(ps)
        n, n_new = int(ps["lesson_length"]), int(ps["new_per_lesson"])
        rng = random.Random(seed)
        steps: list[dict] = []
        allowed = {p.id for p in self.packs.for_profile(pid)}
        if mode == "daily":
            steps = self._daily(pid, n, n_new, rng)
        else:
            pack = self.packs.get(pack_id or "")
            if not pack or pack.id not in allowed:
                raise LearnError("pack not available")
            units = [pack.unit(unit_id)] if unit_id else [pack.unit(u["id"]) for u in self.pack_progress(pid, pack)["units"] if u["unlocked"]]
            units = [u for u in units if u]
            if not units:
                raise LearnError("unit not available")
            if mode == "path" and unit_id:
                prog = {u["id"]: u for u in self.pack_progress(pid, pack)["units"]}
                if not prog.get(unit_id, {}).get("unlocked"):
                    raise LearnError("unit is still locked")
            per = max(1, n // len(units)) if len(units) > 1 else n
            if mode == "cards" and not unit_id:
                steps = self._card_box(pid, pack, [u for u in units if u.kind == "cards"], n, n_new, rng)
                units = []
            for u in units:
                steps += self._steps_for_unit(pid, pack, u, per, n_new, rng, mode)
            if len(units) > 1:
                rng.shuffle(steps)
            steps = steps[: max(n, 1)]
        if not steps:
            raise LearnError("nothing to learn here yet")
        sid = secrets.token_urlsafe(12)
        data = {"steps": steps, "answered": {}, "pack": pack_id, "unit": unit_id, "started": datetime.now().isoformat(),
                "ledger_from": self.db.val("SELECT MAX(id) FROM ledger", default=0),
                "badge_from": self.db.val("SELECT MAX(rowid) FROM badge", default=0)}
        self.db.x("INSERT INTO session(id,profile_id,mode,data) VALUES(?,?,?,?)", sid, pid, mode, json.dumps(data, ensure_ascii=False))
        self.mark_stars_before(sid, pid)
        return self.public(sid, pid)

    def _card_box(self, pid: int, pack: PackInfo, units: list[UnitInfo], n: int, n_new: int,
                  rng: random.Random) -> list[dict]:
        """Card box over a whole pack: due cards of all units first (lowest box first), then new ones."""
        st = self.states(pid, pack.id)
        merged = UnitInfo("all", "", "cards", ["karteikarte"], items=[it for u in units for it in u.items])
        owner = {it["key"]: u for u in units for it in u.items}
        picked = self._pick_cards(merged, st, n, n_new, rng)
        return [ex.card_step(pack, owner[it["key"]], it) for it in picked]

    def _daily(self, pid: int, n: int, n_new: int, rng: random.Random) -> list[dict]:
        """Daily lesson: due repetitions from every active pack, a few new cards, some arithmetic."""
        steps: list[dict] = []
        packs = self.packs.for_profile(pid, try_all=False)      # parents: no drafts in the daily lesson
        rng.shuffle(packs)
        due_steps, new_steps = [], []
        for pack in packs:
            prog = self.pack_progress(pid, pack)
            for u in prog["units"]:
                unit = pack.unit(u["id"])
                if not unit or not u["unlocked"]:
                    continue
                if unit.kind == "generator":
                    if u["id"] == prog["next"]:
                        new_steps += self._steps_for_unit(pid, pack, unit, 3, 0, rng, "path")
                    continue
                if u["due"]:
                    due_steps += self._steps_for_unit(pid, pack, unit, min(u["due"], n), 0, rng, "path")
                if u["id"] == prog["next"]:
                    new_steps += self._steps_for_unit(pid, pack, unit, max(2, n_new), n_new, rng, "path")
        rng.shuffle(due_steps)
        steps = due_steps[: max(n // 2, n - len(new_steps))]
        rng.shuffle(new_steps)
        steps += new_steps[: n - len(steps)]
        rng.shuffle(steps)
        return steps[:n]

    @staticmethod
    def _check_hours(ps: dict) -> None:
        hours = (ps.get("learning_hours") or "").strip()
        if not hours or "-" not in hours:
            return
        a, b = [h.strip() for h in hours.split("-", 1)]
        now = datetime.now().strftime("%H:%M")
        if not (a <= now <= b):
            raise LearnError("learning time is over for today")

    # ---------------------------------------------------------------- running
    def _load(self, sid: str, pid: int) -> tuple[dict, dict]:
        row = self.db.q1("SELECT * FROM session WHERE id=? AND profile_id=?", sid, pid)
        if not row:
            raise LearnError("session not found")
        return row, json.loads(row["data"])

    def public(self, sid: str, pid: int) -> dict:
        row, data = self._load(sid, pid)
        return {"id": sid, "mode": row["mode"], "finished": bool(row["finished"]),
                "steps": [{"kind": s["kind"], **s["public"]} for s in data["steps"]],
                "answered": data["answered"]}

    def pack_rewards(self, pack_id: str | None) -> dict:
        """A pack's own XP / coins per finished lesson (parent area › Packs) – None: the family rule."""
        own = (self.db.get_setting("pack_rewards", {}) or {}).get(pack_id or "") or {}
        return {k: own.get(k) for k in ("xp", "coins") if own.get(k) is not None}

    def _perfect_coins(self, pid: int) -> int:
        """Coins for a perfect lesson – within the parents' daily coin limit of the lesson rule (if it has one)."""
        v = self.db.get_setting("lesson_perfect_coins")
        try:
            coins = max(0, min(1000, int(5 if v is None else v)))
        except (TypeError, ValueError, OverflowError):
            coins = 5
        limit = self.db.val("""SELECT MIN(daily_limit) FROM rule WHERE event='lesson_done' AND account='coins' AND active=1
                               AND daily_limit IS NOT NULL""")
        if limit is not None and coins:
            # one limit for all lesson coins of the day: the finished lessons and the perfect ones together
            used = float(self.db.val("""SELECT SUM(amount) FROM ledger WHERE profile_id=? AND account='coins'
                                        AND event IN ('lesson_done','lesson_perfect') AND date(at)=date('now','localtime')""", pid, default=0) or 0)
            coins = int(max(0.0, min(coins, float(limit) - used)))
        return coins

    def answer(self, sid: str, pid: int, idx: int, answer, ms: int | None = None) -> dict:
        row, data = self._load(sid, pid)
        if row["finished"]:
            raise LearnError("session already finished")
        if not 0 <= idx < len(data["steps"]):
            raise LearnError("no such step")
        if str(idx) in data["answered"]:
            return data["answered"][str(idx)]
        step = data["steps"][idx]
        res = ex.grade(step, answer)
        bookings = []
        pack = self.packs.get(step["pack"])
        subject = pack.subject if pack else ""
        with self.db.tx():
            for key, r in res["results"].items():
                was = self._apply(pid, step, key, r, ms, subject, row["mode"])
                if r == "correct":
                    ev = "answer_fixed" if was and was.get("last_ok") == 0 else "answer_correct"
                    bookings += self.rewards.emit(pid, ev, ref=sid, ctx={"subject": subject, "mode": row["mode"]})
            if row["mode"] == "quiz" and res["correct"] and ms is not None and ms < 5000:
                bookings += self.rewards.emit(pid, "answer_fast", ref=sid, ctx={"subject": subject})
            out = {"correct": res["correct"], "note": res.get("note", ""), "solution": res["solution"],
                   "score": res.get("score"), "xp": sum(b.get("amount", 0) for b in bookings if b.get("account") == "xp")}
            data["answered"][str(idx)] = out
            self.db.x("UPDATE session SET data=? WHERE id=?", json.dumps(data, ensure_ascii=False), sid)
        return out

    def _apply(self, pid: int, step: dict, key: str, result: str, ms, subject: str, mode: str) -> dict | None:
        was = self.db.q1("SELECT * FROM item_state WHERE profile_id=? AND item_key=?", pid, key)
        box = was["box"] if was else 0
        nb, due = next_state(box, result, today())
        ok = 1 if result == "correct" else 0
        self.db.x("""INSERT INTO item_state(profile_id,item_key,pack_id,unit_id,box,due,correct,wrong,last_ok,last_seen)
                     VALUES(?,?,?,?,?,?,?,?,?,datetime('now','localtime'))
                     ON CONFLICT(profile_id,item_key) DO UPDATE SET box=excluded.box, due=excluded.due,
                     correct=correct+excluded.correct, wrong=wrong+excluded.wrong, last_ok=excluded.last_ok,
                     last_seen=excluded.last_seen""",
                  pid, key, step["pack"], step["unit"], nb, due, ok, 1 if result == "wrong" else 0, ok)
        self.db.x("INSERT INTO attempt(profile_id,item_key,pack_id,unit_id,subject,kind,correct,ms) VALUES(?,?,?,?,?,?,?,?)",
                  pid, key, step["pack"], step["unit"], subject, step["kind"], ok, ms)
        return was

    def finish(self, sid: str, pid: int) -> dict:
        row, data = self._load(sid, pid)
        if row["finished"]:
            return data.get("result", {})
        steps, answered = data["steps"], data["answered"]
        total = len(steps)
        done = len(answered)
        right = sum(1 for a in answered.values() if a["correct"])
        touched = {(s["pack"], s["unit"]) for s in steps}
        stars_before = data.get("stars_before") or {}
        start = datetime.fromisoformat(data["started"])
        seconds = int((datetime.now() - start).total_seconds())
        bookings: list[dict] = []
        unit_stars = []
        with self.db.tx():
            if not self.db.x("UPDATE session SET finished=1 WHERE id=? AND finished=0", sid):
                return self._load(sid, pid)[1].get("result", {})        # finished at the same time by a double tap: no second booking
            completed = done >= max(1, total // 2)
            self.rewards.add_time(pid, seconds, lessons=1 if completed else 0)
            if completed and row["mode"] in ("path", "daily", "cards"):
                own = self.pack_rewards(data.get("pack")) if row["mode"] != "daily" else {}
                bookings += self.rewards.emit(pid, "lesson_done", ref=sid, ctx={"mode": row["mode"]}, amounts=own)
                if total and done == total and right == total:          # a perfect lesson: every answer right
                    coins = self._perfect_coins(pid)
                    if coins > 0 and "coins" in {a["key"] for a in self.rewards.accounts()}:
                        bookings.append(self.rewards.book(pid, "coins", coins, "lesson_perfect", _t("Perfect lesson"), sid))
            if row["mode"] == "quiz" and done == total and right == total:
                bookings += self.rewards.emit(pid, "quiz_perfect", ref=sid)
                bookings += self.rewards.award(pid, "quiz_ace")
            for pack_id, unit_id in touched:
                pack = self.packs.get(pack_id)
                unit = pack.unit(unit_id) if pack else None
                if unit:
                    unit_stars.append({"pack": pack_id, "unit": unit_id, "title": unit.title, "subject": pack.subject,
                                       "generator": unit.generator or "", "stars": self.unit_stars(pid, pack, unit),
                                       "before": stars_before.get(f"{pack_id}:{unit_id}")})
            bookings += self.rewards.check_badges(pid, unit_stars=unit_stars)
            # everything booked since the session started (answers, lesson, daily goal, badges)
            gained = {r["account"]: float(r["s"] or 0) for r in self.db.q(
                "SELECT account, SUM(amount) s FROM ledger WHERE profile_id=? AND id>? AND amount>0 GROUP BY account",
                pid, data.get("ledger_from", 0))}
            new_ids = {r["badge"] for r in self.db.q("SELECT badge FROM badge WHERE profile_id=? AND rowid>?",
                                                      pid, data.get("badge_from", 0))}
            new_badges = [b for b in self.rewards.badges(pid) if b["id"] in new_ids]
            result = {"total": total, "answered": done, "right": right, "seconds": seconds, "gained": gained,
                      "badges": new_badges,
                      "units": unit_stars, "goal_met": self.rewards.xp_today(pid) >= self.rewards.daily_goal(pid),
                      "level": self.rewards.level(pid), "streak": self.rewards.streak(pid), "completed": completed}
            data["result"] = result
            self.db.x("UPDATE session SET data=? WHERE id=?", json.dumps(data, ensure_ascii=False), sid)
        for fn in self.listeners:
            fn("lesson", pid, {"mode": row["mode"], "right": right, "total": total, "completed": completed})
        return result

    # ---------------------------------------------------------------- statistics for parents
    def weak_spots(self, pid: int, limit: int = 8) -> list[dict]:
        rows = self.db.q("""SELECT item_key, pack_id, unit_id, correct, wrong, box FROM item_state
                            WHERE profile_id=? AND wrong>0 ORDER BY (wrong*1.0/(correct+wrong)) DESC, wrong DESC LIMIT 60""", pid)
        out = []
        for r in rows:
            pack = self.packs.get(r["pack_id"])
            unit = pack.unit(r["unit_id"]) if pack else None
            if not unit:
                continue
            label = ""
            if "@" in r["item_key"]:
                from .. import generators
                skill = r["item_key"].split("@", 1)[1]
                try:
                    label = generators.get(unit.generator or "").skill_title(skill)
                except KeyError:
                    label = skill
            else:
                it = next((i for i in unit.items if i["key"] == r["item_key"]), None)
                if not it:
                    continue
                label = f'{it["view"]["prompt"]} → {it["view"]["answer"]}'
            tries = r["correct"] + r["wrong"]
            out.append({"pack": pack.title, "unit": unit.title, "label": label, "wrong": r["wrong"], "tries": tries,
                        "rate": round(r["wrong"] / tries, 2) if tries else 0, "subject": pack.subject})
            if len(out) >= limit:
                break
        return out

    def time_per_subject(self, pid: int, days: int = 7) -> list[dict]:
        rows = self.db.q("""SELECT subject, COUNT(*) n, SUM(correct) ok, SUM(COALESCE(ms,0)) ms FROM attempt
                            WHERE profile_id=? AND at>=datetime('now','localtime',?) GROUP BY subject ORDER BY n DESC""",
                         pid, f"-{int(days)} days")
        return [{"subject": r["subject"] or "", "answers": r["n"], "right": r["ok"] or 0,
                 "minutes": round((r["ms"] or 0) / 60000, 1)} for r in rows]

    def mark_stars_before(self, sid: str, pid: int) -> None:
        """Remember unit stars at session start so the result screen can show the change."""
        row, data = self._load(sid, pid)
        before = {}
        for s in data["steps"]:
            k = f'{s["pack"]}:{s["unit"]}'
            if k in before:
                continue
            pack = self.packs.get(s["pack"])
            unit = pack.unit(s["unit"]) if pack else None
            if unit:
                before[k] = self.unit_stars(pid, pack, unit)
        data["stars_before"] = before
        self.db.x("UPDATE session SET data=? WHERE id=?", json.dumps(data, ensure_ascii=False), sid)


def iso(d: date) -> str:
    return d.isoformat()
