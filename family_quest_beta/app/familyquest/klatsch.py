"""«Klatsch den Beat» – a live rhythm game: listen to a beat, then clap it back in time on the big clap button.

Everybody plays at the same time on their own device (family table, guests via QR code) or alone for a personal best,
optionally with practice bots – the tables live in the `card_game` table with kind "klatsch" (lobby, join, summary,
may_lead from cardgames.CardGames, like «Jump»).

A round («call and response», fixed on the shared game clock – game time 0 = `t0`, a short countdown after the start):
  1. count-in – one bar of four hi-hat clicks at the round's tempo,
  2. listen   – the app plays the pattern (claps over a kick / hi-hat groove); the dots appear on the bar as they sound,
     then a «ready» bar of four clicks (a run-up to the clap bar),
  3. clap     – the next bar: the same dots stay on the bar, a playhead sweeps over them – clap when it reaches a dot,
  4. results  – a short pause with the points of the round and the live ranking, then the next round.
The server makes the patterns (random with `secrets`): a bar of 4/4 on a 16th grid (positions 0–15), at least an
eighth apart. They get harder per round: the tempo goes from 80 to 140 BPM, first quarters and eighths, then syncopes
(off-beat eighths, a missing «one»), at the end sixteenth syncopes and longer pauses. 5–8 rounds (rule `rounds`).

Timing: the app knows the server clock (it estimates the offset from the `now` of its answers, the one with the
shortest round trip counts), subtracts its own audio/tap delay (a calibration per device: tap along to 8 clicks) and
reports its taps as game times; the server judges them against the pattern – every note takes the nearest free tap:
within ±PERFECT «perfect» (100 points), within ±GOOD «good» (50), else «miss»; a tap that hits no note costs EXTRA
points (no drumming through), never below 0 per round. Reports for a round are taken until GRACE seconds after its
clap bar, then the round is scored for everybody at once – so everybody is ranked by the same rules.
End: after the last round – places by the total points (the same total shares the place). Who leads may end early:
ranked as it stands, no coins. Alone (and at a table) the accuracy (perfect = 1, good = ½ of a note) of a game
played to the end is the personal best (setting `klatsch_best`, %).
Coins (setting `game_rewards["klatsch"]`): places 1–3, only people of the family at a family table with at least two
of them – never alone; paid once (flag `paid`, a unique ledger `ref` per player). The «No. 1» hat for the winners.
Bots (easy / normal / hard): they clap every note with a timing error and now and then miss one or clap too much.
"""
from __future__ import annotations

import json
import math
import random
import secrets
import time

from .cardgames import BOTS, CardGames
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .running import win_reason

KIND = "klatsch"
TITLE = "Klatsch den Beat"
EMOJI = "👏"
MAX_PLAYERS = 8
LEVELS = ("easy", "normal", "hard")
DEFAULTS = {"bots": 0, "level": "normal", "rounds": 6}
ROUNDS = (5, 6, 7, 8)

BPM0, BPM1 = 80, 140         # the tempo of the first and the last round
COUNTDOWN = 3.0              # seconds from the start to game time 0 (the first count-in)
PAUSE = 4.5                  # the results between two rounds (from the end of a clap bar to the next count-in)
GRACE = 1.0                  # taps of a round are taken this long after its clap bar, then it is scored
PERFECT = 0.06               # ± seconds
GOOD = 0.13
PTS_PERFECT, PTS_GOOD, EXTRA = 100, 50, 25
MAX_TAPS = 48                # taps per round and player
BOT_SKILL = {"easy": (0.085, 0.14, 0.12), "normal": (0.05, 0.06, 0.05), "hard": (0.028, 0.02, 0.02)}   # σ (s), miss, extra tap


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def tempo(i: int, n: int) -> int:
    """The BPM of round i (0-based) of n – from BPM0 to BPM1, even numbers."""
    if n <= 1:
        return BPM0
    return int(round((BPM0 + (BPM1 - BPM0) * i / (n - 1)) / 2) * 2)


def pattern(i: int, n: int, rng) -> list[int]:
    """The notes of round i of n: 16th positions 0–15, at least two apart (an eighth); harder per round."""
    p = i / (n - 1) if n > 1 else 0.0
    for _ in range(300):
        if p < 0.3:                                   # quarters and eighths, always on the «one»
            k = rng.choice((3, 4) if p < 0.15 else (4, 4, 5))
            grid = [0, 4, 8, 12] if p < 0.15 and rng.random() < 0.6 else list(range(0, 16, 2))
            notes = sorted({0, *rng.sample(grid[1:], k - 1)})
        elif p < 0.65:                                # eighths with syncopes, sometimes a missing «one»
            k = rng.choice((4, 5, 5))
            notes = sorted(rng.sample(range(0, 16, 2), k))
            if not any(x % 4 == 2 for x in notes):
                continue
        else:                                         # sixteenth syncopes and pauses
            k = rng.choice((5, 5, 6))
            notes = sorted(rng.sample(range(16), k))
            if not any(x % 2 == 1 for x in notes):
                continue
            gaps = [b - a for a, b in zip(notes, notes[1:])] + [16 - notes[-1] + notes[0]]
            if max(gaps) < 4:                         # a real pause somewhere
                continue
        if all(b - a >= 2 for a, b in zip(notes, notes[1:])) and len(notes) >= 3:
            return notes
    return [0, 4, 8, 12]


def judge(notes: list[float], taps: list[float]) -> tuple[list[float | None], int]:
    """Every note takes the nearest free tap (the closest pairs first): the time difference per note (None = missed)
    and the number of taps that hit no note."""
    pairs = sorted((abs(t - n), a, b) for a, n in enumerate(notes) for b, t in enumerate(taps) if abs(t - n) <= GOOD)
    got: list[float | None] = [None] * len(notes)
    used = set()
    for _, a, b in pairs:
        if got[a] is None and b not in used:
            got[a] = taps[b] - notes[a]
            used.add(b)
    return got, len(taps) - len(used)


def score_of(got: list[float | None], extras: int) -> dict:
    pf = sum(1 for d in got if d is not None and abs(d) <= PERFECT)
    gd = sum(1 for d in got if d is not None and abs(d) > PERFECT)
    pts = max(0, pf * PTS_PERFECT + gd * PTS_GOOD - extras * EXTRA)
    return {"p": pf, "g": gd, "m": len(got) - pf - gd, "x": extras, "pts": pts}


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng=None, now=time.time):
        self.st = st
        self.rng = rng or secrets.SystemRandom()
        self.now = now

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    def seat_of(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def gt(self) -> float:
        """The game time now."""
        return self.now() - self.st["t0"]

    @staticmethod
    def times(rd: dict) -> tuple[float, float, float, float]:
        """count-in, listen, clap, end of the clap bar (game times). Between the listen and the clap bar a second
        count-in bar («ready»: four clicks) – a run-up, so the first note of the clap bar can be hit."""
        bar = 4 * 60.0 / rd["bpm"]
        s = rd["start"]
        return s, s + bar, s + 3 * bar, s + 4 * bar

    @staticmethod
    def note_times(rd: dict) -> list[float]:
        _, _, clap, _ = Table.times(rd)
        step = 60.0 / rd["bpm"] / 4
        return [clap + x * step for x in rd["notes"]]

    def setup(self) -> None:
        ids = self.order()
        if not 1 <= len(ids) <= MAX_PLAYERS:
            raise CommunityError("The table is full")
        n = int(self.st["rules"].get("rounds", 6))
        rounds, s = [], 0.0
        for i in range(n):
            rd = {"bpm": tempo(i, n), "start": round(s, 3), "notes": pattern(i, n, self.rng)}
            rounds.append(rd)
            s = self.times(rd)[3] + PAUSE
        self.st.update(phase="play", t0=self.now() + COUNTDOWN, rounds=rounds, scored=0, ranking=None, places=None,
                       complete=False, run={pid: {"taps": {}, "res": [], "total": 0} for pid in ids})

    def current(self, t: float | None = None) -> int:
        """The round being played or shown now (the first one not yet over)."""
        t = self.gt() if t is None else t
        for i, rd in enumerate(self.st["rounds"]):
            if t < self.times(rd)[3] + PAUSE:
                return i
        return len(self.st["rounds"]) - 1

    # ---------- what an app reports
    def report(self, pid: str, rnd, taps=()) -> None:
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        r = self.st["run"].get(pid)
        p = self.seat_of(pid)
        if r is None or not p or p.get("bot"):
            raise CommunityError("You are not at this table")
        try:
            i = int(rnd)
        except (TypeError, ValueError):
            return
        if not self.st["scored"] <= i < len(self.st["rounds"]):
            return                                        # already scored (too late) or no such round
        now_t = self.gt()
        _, _, clap, end = self.times(self.st["rounds"][i])
        if now_t > end + GRACE:
            return
        mine = list(r["taps"].get(str(i), []))
        for x in list(taps)[:MAX_TAPS]:
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(x) or not clap - 0.3 <= x <= end + 0.3 or x > now_t + 0.3:
                continue
            if any(abs(x - y) < 0.03 for y in mine):     # sent again
                continue
            mine.append(round(x, 4))
        r["taps"][str(i)] = sorted(mine)[:MAX_TAPS]

    # ---------- the clock: scoring the rounds, the end
    def tick(self) -> bool:
        if self.st.get("phase") != "play":
            return False
        before = self.st["scored"]
        now_t = self.gt()
        rounds = self.st["rounds"]
        while self.st["scored"] < len(rounds) and now_t >= self.times(rounds[self.st["scored"]])[3] + GRACE:
            self._score(self.st["scored"])
        if self.st["scored"] >= len(rounds):
            self.st["complete"] = True
            self._finish()
        return self.st.get("phase") != "play" or self.st["scored"] != before

    def _bot_taps(self, p: dict, rd: dict) -> list[float]:
        sigma, miss, extra = BOT_SKILL.get(p.get("level"), BOT_SKILL["normal"])
        hard = 1 + (rd["bpm"] - BPM0) / (BPM1 - BPM0)          # faster: a bit worse
        out = []
        for n in self.note_times(rd):
            if self.rng.random() < miss * hard:
                continue
            out.append(round(n + self.rng.gauss(0, sigma * (0.8 + 0.2 * hard)), 4))
        if self.rng.random() < extra * hard:
            _, _, clap, end = self.times(rd)
            out.append(round(clap + self.rng.random() * (end - clap), 4))
        return sorted(out)

    def _score(self, i: int) -> None:
        rd = self.st["rounds"][i]
        notes = self.note_times(rd)
        for p in self.st["players"]:
            r = self.st["run"][p["id"]]
            if p.get("bot"):
                r["taps"][str(i)] = self._bot_taps(p, rd)
            got, extras = judge(notes, r["taps"].get(str(i), []))
            res = score_of(got, extras)
            res["d"] = [None if d is None else round(d * 1000) for d in got]     # ms per note (for the app)
            r["res"].append(res)
            r["total"] += res["pts"]
            r["taps"].pop(str(i - 1), None)                # keep the state small
        self.st["scored"] = i + 1

    def accuracy(self, pid: str) -> int:
        """Perfect = 1, good = ½ of a note, in % of all notes of the scored rounds."""
        res = self.st["run"][pid]["res"]
        notes = sum(x["p"] + x["g"] + x["m"] for x in res)
        return int(round(100 * sum(x["p"] + x["g"] / 2 for x in res) / notes)) if notes else 0

    def _finish(self) -> None:
        order, run = self.order(), self.st["run"]
        self.st["places"] = places(order, {p: run[p]["total"] for p in order})
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st["scores"] = {p: run[p]["total"] for p in order}
        self.st["acc"] = {p: self.accuracy(p) for p in order}
        self.st.update(phase="done", finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: the rounds already played are scored, ranked as it stands (no coins)."""
        if self.st.get("phase") != "play":
            return
        now_t = self.gt()
        rounds = self.st["rounds"]
        while self.st["scored"] < len(rounds) and now_t >= self.times(rounds[self.st["scored"]])[3]:
            self._score(self.st["scored"])
        self._finish()


# ================================================================ the games in the database (table card_game, kind "klatsch")
class Klatsch(CardGames):
    """The family table / own tables – the same rows and lobby as the card games (summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng=None):
        super().__init__(db, add_history)
        self.rewards = rewards
        self.now = now
        self.rng = rng

    def table(self, st: dict) -> Table:
        return Table(st, self.rng, now=lambda: self.now())

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, {**DEFAULTS, **(self.db.get_setting(f"game_rules.{KIND}") or {})})

    def rules_info(self) -> dict:
        return {**self.default_rules(), "rewards": rewards_of(self.db), "max_players": MAX_PLAYERS}

    def clean_rules(self, kind: str, r: dict) -> dict:
        out = {}
        for k, v in DEFAULTS.items():
            x = (r or {}).get(k, v)
            if isinstance(v, int):
                try:
                    out[k] = int(x)
                except (TypeError, ValueError):
                    out[k] = v
            else:
                out[k] = str(x)
        out["bots"] = max(0, min(MAX_PLAYERS - 1, out["bots"]))
        out["level"] = out["level"] if out["level"] in LEVELS else "normal"
        out["rounds"] = out["rounds"] if out["rounds"] in ROUNDS else 6
        return out

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    def best(self, pid) -> int:
        return int((self.db.get_setting("klatsch_best") or {}).get(str(pid), 0) or 0)

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status != "done" or st.get("paid") or st.get("places") is None:
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        best = dict(self.db.get_setting("klatsch_best") or {})          # the personal best: accuracy of a full game
        records = {}
        if st.get("complete"):
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                acc = int((st.get("acc") or {}).get(p["id"], 0))
                if acc > int(best.get(p["id"], 0) or 0):
                    best[p["id"]] = acc
                    records[p["id"]] = True
        if records:
            self.db.set_setting("klatsch_best", best)
        st["records"] = records
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", win_reason(KIND, st['places'][pid]), ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        if len(st["players"]) >= 2:
            self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history:
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]), "score": (st.get("scores") or {}).get(p["id"], 0),
                        "acc": (st.get("acc") or {}).get(p["id"], 0), "rounds": st.get("scored", 0),
                        "record": bool(records.get(p["id"])), "complete": bool(st.get("complete")), "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins per player: places 1–3, only people of the family, only with at least two of them at a family table,
        only for a game played to the end."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if st.get("solo") or len(people) < 2 or st.get("phase") != "done" or not st.get("complete"):
            return {}
        amounts = rewards_of(self.db)
        pl = st.get("places") or {}
        out = {}
        for p in people:
            n = pl.get(p["id"])
            if n and 1 <= n <= 3 and amounts[n - 1] > 0:
                out[p["id"]] = amounts[n - 1]
        return out

    def _bots(self, st: dict, need: int) -> list[dict]:
        if need > 0 and self.bots_off(KIND, st["players"]):          # parent area › Games: without bots
            st.pop("bot_pool", None)
            return []
        pool = st.pop("bot_pool", None) or []
        taken = {b["name"] for b in pool}
        for n, e in random.sample(BOTS, len(BOTS)):
            if len(pool) >= need:
                break
            if n not in taken:
                pool.append({"name": n, "emoji": e, "level": st["rules"]["level"]})
                taken.add(n)
        out = []
        for i, b in enumerate(pool[:need]):
            lvl = b.get("level") if b.get("level") in LEVELS else st["rules"]["level"]
            out.append({"id": f"bot{i + 1}", "name": b["name"], "emoji": b.get("emoji") or "🤖", "color": b.get("color"),
                        "owner": b.get("owner"), "bot": True, "level": lvl})
        return out

    def _deal(self, st: dict) -> None:
        humans = [p for p in st["players"] if not p.get("bot")]
        n = max(0, min(st["rules"]["bots"], MAX_PLAYERS - len(humans)))
        st["players"] = humans + self._bots(st, n)
        st.pop("bot_pool", None)
        self.table(st).setup()

    def start(self, kind: str, host: int, rules: dict | None = None, solo: bool = False, bots: list[dict] | None = None) -> int:
        if kind != KIND:
            raise CommunityError("Unknown game")
        with self.lock:
            if not solo and self._row(KIND):
                raise CommunityError("This game is already running")
            if solo:
                old = self._row(KIND, host)
                if old and old["solo"]:
                    self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", old["id"])
            r = self.clean_rules(KIND, {**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
            self.db.set_setting(f"game_rules.{KIND}", r)
            st = {"kind": KIND, "rules": r, "players": [self._person(host)], "phase": "lobby", "solo": solo, "bot_pool": list(bots or [])}
            gid = self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, int(solo), json.dumps(st))
            if solo:                                      # alone: the countdown starts right away
                row = self.db.q1("SELECT * FROM card_game WHERE id=?", gid)
                self._deal(st)
                self._save(row, st)
            return gid

    def join(self, kind: str, pid: int) -> None:
        with self.lock:
            row = self._row(KIND)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if any(p["id"] == str(pid) for p in st["players"]):
                return
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) >= MAX_PLAYERS:
                raise CommunityError("The table is full")
            st["players"].append(self._person(pid))
            self._save(row, st)

    def begin(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            self._deal(st)
            self._save(row, st)

    def report(self, pid: int, rnd=None, taps=()) -> dict | None:
        """The app of this player reports its taps of a round (only its own player) – answers with the state."""
        with self.lock:
            row = self._row(KIND, pid)
            if row:
                st = json.loads(row["state"])
                if st["phase"] == "lobby":
                    raise CommunityError("The game has not started yet")
                if st["phase"] == "play":
                    t_ = self.table(st)
                    if rnd is not None:
                        t_.report(str(pid), rnd, taps)
                    t_.tick()
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
        if not row:                                       # over in the meantime: the result
            return self.state(KIND, pid)
        return self._view(row, st, str(pid))

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: ranked as it stands (coins only for a game played to the end)."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] == "play":
                self.table(st).end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int) -> dict | None:
        with self.lock:
            row = self._row(KIND, viewer)
            if row:
                st = json.loads(row["state"])
                if st["phase"] == "play" and self.table(st).tick():
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
            else:
                row = self.db.q1("""SELECT * FROM card_game WHERE kind=? AND status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                    AND (solo=0 OR host_id=?) ORDER BY id DESC LIMIT 1""", KIND, viewer)
                if not row:
                    return None
                st = json.loads(row["state"])
                if not any(p["id"] == str(viewer) for p in st["players"]):
                    return None
        return self._view(row, st, str(viewer))

    def _view(self, row, st: dict, me: str) -> dict:
        joined = any(p["id"] == me for p in st["players"])
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        ph = st["phase"]
        if row["status"] == "done" and ph != "lobby":
            ph = "done"
        base = {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph,
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "joined": joined,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2, "max_players": MAX_PLAYERS,
                "best": self.best(me) if joined else 0, "now": self.now(),
                "windows": {"perfect": round(PERFECT * 1000), "good": round(GOOD * 1000)}}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            return {**base, "players": players, "bots": max(0, min(st["rules"]["bots"], MAX_PLAYERS - len(players)))}
        t = self.table(st)
        run, coins = st["run"], st.get("coins") or {}
        done = ph == "done"
        pl = st.get("places") if done and st.get("places") else places(t.order(), {p: run[p]["total"] for p in t.order()})
        now_t = t.gt()
        # the rounds that started or start soon (the patterns stay a surprise until shortly before)
        rounds = [{"i": i, **rd} for i, rd in enumerate(st["rounds"]) if done or i < st["scored"] or rd["start"] <= now_t + PAUSE + 2]
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                    "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"), "level": p.get("level"),
                    "total": run[p["id"]]["total"], "pts": [x["pts"] for x in run[p["id"]]["res"]],
                    "last": run[p["id"]]["res"][-1] if run[p["id"]]["res"] else None,
                    "acc": t.accuracy(p["id"]), "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0),
                    "record": bool((st.get("records") or {}).get(p["id"]))}
                   for p in st["players"]]
        return {**base, "players": players, "me": me if joined else None, "t0": st["t0"], "rounds": rounds,
                "n_rounds": len(st["rounds"]), "scored": st["scored"], "grace": GRACE, "pause": PAUSE,
                "current": t.current(now_t), "ranking": st.get("ranking"), "complete": bool(st.get("complete")),
                "now_t": now_t if ph == "play" else None}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
