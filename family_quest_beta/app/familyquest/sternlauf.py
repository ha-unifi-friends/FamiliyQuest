"""«Star Runner» (Sternschnuppen-Lauf) – a live endless runner on a forest path with three lanes.

The story: at night the big lantern of the village went out. The children run as forest messengers along the forest
path, catch the falling star sparks (✨) and bring them home to light it again. On the way: fallen logs and puddles
(jump), low branches with hanging vines (duck), rocks and tree stumps that block a lane (change the lane).

Everybody plays on their own device at the same time (family table, guests via QR code) or alone (high score,
optionally with practice bots) – the tables live in the `card_game` table with kind "sternlauf" (lobby, join, summary,
may_lead from cardgames.CardGames, like «Jump»).

Fair for everybody: all players run the SAME course – made from a seed of the server (`course()`, the same generator
runs in web/sternlauf.js) – on the same game clock (game time 0 = `t0`, after a short countdown). The speed grows with
the distance (V0 → VMAX), the rows of obstacles come closer together.

The server decides what counts: the app only reports its INPUTS (swipes with their game time: `l`/`r` lane, `u` jump,
`d` duck). The server replays them on the course (`Runner`, the same rules as in the app) and decides itself which
obstacle hit and which spark was caught – an app cannot report a distance, sparks or "no hit". An input is only taken
when it comes in time: not before the last one, not in the future (now + AHEAD) and not for a part of the course the
server already settled (`h` = game time minus SETTLE). So nobody can dodge afterwards; a very slow connection only
costs the late swipes. The app simulates the same thing for smooth 60 fps and adopts the server's result.

Lives (rule `lives`: 1 / 3 / 5, default 3): every hit costs one (then INVULN seconds of blinking), without lives you
are out. A player whose app stays silent for STALE seconds is out too. The run ends when nobody of the people is running
any more or the time is up (rule `minutes`: 2 / 3 / 5). Points: the distance (m) + SPARK_PTS per spark. Places by
points (the same points share the place). Who leads may end the game early: ranked as it stands, no coins.
Coins (setting `game_rewards["sternlauf"]`): places 1–3, only people of the family at a family table with at least two
of them, only for a game played to the end – paid once (flag `paid`, a unique ledger `ref` per player). Personal best
(points) in the setting `sternlauf_best`; the «No. 1» hat via `_champion`.
Bots (easy / normal / hard) run the same rules: they plan their swipes LOOKAHEAD seconds ahead with a timing error and
now and then a mistake (forget to jump / duck, swerve too late) – the faster, the more mistakes.
The others are shown in the app as translucent ghosts: the server relays everybody's recent inputs (`base` + `ev`).
"""
from __future__ import annotations

import json
import math
import random
import time

from .cardgames import BOTS, CardGames
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .running import win_reason

KIND = "sternlauf"
TITLE = "Sternschnuppen-Lauf"
EMOJI = "🌠"
MAX_PLAYERS = 8
LEVELS = ("easy", "normal", "hard")
DEFAULTS = {"bots": 0, "level": "normal", "lives": 3, "minutes": 3}
LIVES = (1, 3, 5)
MINUTES = (2, 3, 5)

# ---------------------------------------------------------------- the course (the same numbers in web/sternlauf.js)
V0 = 9.0                     # metres per second at the start
VMAX = 18.0
ACC = 0.07                   # m/s² (VMAX after about 130 s)
T1 = (VMAX - V0) / ACC
D1 = V0 * T1 + ACC * T1 * T1 / 2
FIRST = 3.0                  # the first row after about 3 s
JT = 0.65                    # a jump lasts 0.65 s …
AIR0 = 0.07                  # … and is high enough from 0.07 s after the take-off to 0.07 s before the landing
DT = 0.75                    # ducking lasts 0.75 s
INVULN = 1.0                 # after a hit: invulnerable (blinking)
SPARK_PTS = 10               # points per spark
COUNTDOWN = 3.0              # seconds from the start to game time 0
SETTLE = 1.5                 # the server settles the course this far behind the game clock
AHEAD = 0.5                  # inputs may be this much ahead of the server's clock (clocks are never exact)
MIN_STEP = 0.04              # two inputs at least this far apart
STALE = 10.0                 # a silent app for this long: out
LOOKAHEAD = 1.3              # bots plan their swipes this early
# kinds of things on the course
LOG, PUDDLE, BRANCH, ROCK, SPARK, SKY = 0, 1, 2, 3, 4, 5
NEED = {LOG: "u", PUDDLE: "u", BRANCH: "d", ROCK: "x"}
BOT_SKILL = {"easy": (0.07, 0.07, 0.35), "normal": (0.045, 0.035, 0.6), "hard": (0.03, 0.015, 0.85)}   # σ (s), mistake, sparks


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def dist(t: float) -> float:
    """The distance run at game time t."""
    if t <= 0:
        return 0.0
    if t < T1:
        return V0 * t + ACC * t * t / 2
    return D1 + VMAX * (t - T1)


def time_at(x: float) -> float:
    """The game time when the distance x is reached."""
    if x <= 0:
        return 0.0
    if x < D1:
        return (-V0 + math.sqrt(V0 * V0 + 2 * ACC * x)) / ACC
    return T1 + (x - D1) / VMAX


def speed_at(x: float) -> float:
    return min(VMAX, math.sqrt(V0 * V0 + 2 * ACC * x))


def mulberry32(seed: int):
    """A small random generator that gives the same numbers in Python and JavaScript."""
    a = seed & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((a ^ (a >> 15)) * (a | 1)) & 0xFFFFFFFF
        t = (((t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return nxt


def course(seed: int, upto: float) -> list[tuple[float, int, int]]:
    """Everything on the path up to this distance, sorted: (x, lane 0–2, kind). Every row of obstacles leaves at least
    one lane that can be passed (free, or with a jump or a duck); between the rows trails of sparks."""
    rnd = mulberry32(seed)
    out = []
    x = V0 * FIRST
    while x <= upto:
        v = speed_at(x)
        prog = (v - V0) / (VMAX - V0)
        r, a, b, c = rnd(), rnd(), rnd(), rnd()
        lane = int(a * 3)
        if r < 0.34:                                   # one obstacle in one lane
            out.append((x, lane, int(b * 4)))
        elif r < 0.58:                                 # rocks / stumps in two lanes, one lane open
            for k in range(3):
                if k != lane:
                    out.append((x, k, ROCK))
            if c < 0.5 * prog:                         # later: in the open lane something to jump or duck
                out.append((x, lane, LOG if b < 0.5 else BRANCH))
        elif r < 0.8:                                  # across the whole path: a log (jump) or a branch (duck)
            k = LOG if b < 0.55 else BRANCH
            for j in range(3):
                out.append((x, j, k))
            if k == LOG and c < 0.6:                   # a spark high above the log
                out.append((x, lane, SKY))
        else:                                          # mixed: rock, log and branch in the three lanes
            kinds = [ROCK, LOG, BRANCH] if b < 0.33 else [LOG, BRANCH, ROCK] if b < 0.66 else [BRANCH, ROCK, LOG]
            for j in range(3):
                out.append((x, (lane + j) % 3, kinds[j]))
        gap = v * (1.05 - 0.25 * prog + rnd() * (0.9 - 0.4 * prog))
        if c > 0.35:                                   # a trail of sparks in the gap
            sl, n = int(rnd() * 3), 3 + int(rnd() * 3)
            step = gap / (n + 2)
            for k in range(1, n + 1):
                out.append((x + step * (k + 0.5), sl, SPARK))
        x = x + gap
    return out


# ---------------------------------------------------------------- one runner: the inputs on the course
def apply_input(s: dict, t: float, c: str) -> None:
    """One input on the state {lane, lj (last jump), ld (last duck)} – the same rules as in the app."""
    if c == "l":
        s["lane"] = max(0, s["lane"] - 1)
    elif c == "r":
        s["lane"] = min(2, s["lane"] + 1)
    elif c == "u":
        if not (s["lj"] > s["ld"] and t - s["lj"] < JT):    # not while in the air (a duck ends the jump)
            s["lj"] = t
    elif c == "d":
        s["ld"] = t


def state_at(base: dict, ev: list, t: float) -> dict:
    s = dict(base)
    for te, c in ev:
        if te > t:
            break
        apply_input(s, te, c)
    return s


def in_air(s: dict, t: float) -> bool:
    return s["lj"] > s["ld"] and AIR0 <= t - s["lj"] <= JT - AIR0


def ducking(s: dict, t: float) -> bool:
    return s["ld"] > s["lj"] and 0 <= t - s["ld"] <= DT


def meets(s: dict, t: float, lane: int, kind: int) -> str | None:
    """What a thing on the path does to this runner at the moment it passes: "hit", "spark" or None."""
    if s["lane"] != lane:
        return None
    if kind == SPARK:
        return "spark"
    if kind == SKY:
        return "spark" if in_air(s, t) else None
    if kind == ROCK:
        return "hit"
    if kind in (LOG, PUDDLE):
        return None if in_air(s, t) else "hit"
    if kind == BRANCH:
        return None if ducking(s, t) else "hit"
    return None


def new_run(lives: int) -> dict:
    return {"lives": lives, "hits": [], "sparks": 0, "got": [], "out": None, "next": 0, "h": 0.0,
            "base": {"lane": 1, "lj": -99.0, "ld": -99.0}, "ev": [], "seen": None, "plan": 0}


def settle(r: dict, obs: list, upto: float) -> None:
    """Decide everything on the course that passed until game time `upto` from the inputs so far."""
    while r["out"] is None and r["next"] < len(obs):
        x, lane, kind = obs[r["next"]]
        tr = time_at(x)
        if tr > upto:
            break
        s = state_at(r["base"], r["ev"], tr)
        what = meets(s, tr, lane, kind)
        i = r["next"]
        r["next"] += 1
        if what == "spark":
            r["sparks"] += 1
            r["got"].append(i)
            del r["got"][:-30]
        elif what == "hit" and not (r["hits"] and tr < r["hits"][-1][1] + INVULN):
            r["hits"].append([i, round(tr, 3)])
            r["lives"] = max(0, r["lives"] - 1)
            if r["lives"] == 0:
                r["out"] = round(tr, 3)
    r["h"] = max(r["h"], upto)
    keep = []                                          # older inputs folded into the base state
    for te, c in r["ev"]:
        if te < r["h"] - 0.5:
            apply_input(r["base"], te, c)
        else:
            keep.append([te, c])
    r["ev"] = keep


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now
        self._course = None

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    def seat_of(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def gt(self) -> float:
        """The game time now."""
        return self.now() - self.st["t0"]

    def limit(self) -> float:
        return 60.0 * int(self.st["rules"].get("minutes", 3))

    def obstacles(self, t: float) -> list:
        upto = dist(t) + 60
        if self._course is None or self._course[0] < upto:
            self._course = (upto + 300, course(self.st["seed"], upto + 300))
        return self._course[1]

    def setup(self, seed: int | None = None) -> None:
        ids = self.order()
        if not 1 <= len(ids) <= MAX_PLAYERS:
            raise CommunityError("The table is full")
        lives = int(self.st["rules"].get("lives", 3))
        self.st.update(phase="play", seed=seed if seed is not None else self.rng.randrange(1, 2 ** 31), t0=self.now() + COUNTDOWN,
                       lives=lives, ranking=None, places=None, complete=False, end_t=None,
                       run={pid: {**new_run(lives), "seen": self.now()} for pid in ids})

    def alive(self) -> list[str]:
        return [p for p in self.order() if self.st["run"][p]["out"] is None]

    # ---------- what an app reports
    def report(self, pid: str, inputs=()) -> int:
        """The inputs of this player's app ([game time, "l"|"r"|"u"|"d"], sorted) – only the ones in time count.
        Answers how many were taken."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        r = self.st["run"].get(pid)
        p = self.seat_of(pid)
        if r is None or not p or p.get("bot"):
            raise CommunityError("You are not at this table")
        r["seen"] = self.now()
        if r["out"] is not None:
            return 0
        now_t = self.gt()
        taken = 0
        for item in list(inputs)[:40]:
            try:
                te, c = float(item[0]), str(item[1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if c not in ("l", "r", "u", "d") or not math.isfinite(te):
                continue
            last = r["ev"][-1][0] if r["ev"] else -COUNTDOWN
            if te < max(r["h"], -1.0) or te > now_t + AHEAD or te < last + MIN_STEP:
                continue
            r["ev"].append([round(te, 3), c])
            taken += 1
        if len(r["ev"]) > 120:                          # far too many inputs: the oldest are folded in
            for te, c in r["ev"][:-120]:
                apply_input(r["base"], te, c)
            del r["ev"][:-120]
        return taken

    # ---------- the clock: settle the course, bots, silent apps, the end
    def tick(self) -> None:
        if self.st.get("phase") != "play":
            return
        now_t = self.gt()
        end_at = self.limit()
        horizon = min(now_t - SETTLE, end_at)          # everybody is settled up to the same moment
        obs = self.obstacles(max(now_t, 0) + LOOKAHEAD + 3)
        for p in self.st["players"]:
            r = self.st["run"][p["id"]]
            if r["out"] is not None:
                continue
            if p.get("bot"):
                self._bot(p, r, obs, min(now_t + LOOKAHEAD, end_at))
            settle(r, obs, horizon)
            if not p.get("bot") and r["out"] is None and now_t > 0 and self.now() - (r.get("seen") or 0) > STALE:
                r["out"] = round(max(0.0, r["h"]), 3)                          # the app is gone: out
        self._maybe_end(horizon)

    def _bot(self, p: dict, r: dict, obs: list, upto: float) -> None:
        """Plan the bot's swipes up to game time `upto`: row by row a passable lane, the swipe a bit early – with a
        timing error and sometimes a mistake."""
        sigma, mistake, greed = BOT_SKILL.get(p.get("level"), BOT_SKILL["normal"])
        plan = state_at(r["base"], r["ev"], 1e9)
        i = r["plan"]
        while i < len(obs):
            x = obs[i][0]
            tr = time_at(x)
            if tr - 0.6 > upto:
                break
            row = []
            while i < len(obs) and obs[i][0] == x:
                row.append(obs[i])
                i += 1
            things = {}
            for _, lane, kind in row:
                things.setdefault(lane, []).append(kind)
            last = r["ev"][-1][0] if r["ev"] else -COUNTDOWN

            def add(te, c):
                nonlocal last
                te = round(max(te, last + MIN_STEP + 0.01, -0.5), 3)
                r["ev"].append([te, c])
                apply_input(plan, te, c)
                last = te
            need_of = {lane: next((NEED[k] for k in ks if k in NEED), None) for lane, ks in things.items()}
            obstacle = any(need_of.values())
            v = speed_at(x)
            wrong = self.rng.random() < mistake * (1 + (v - V0) / V0)
            if obstacle:
                cost = {}
                for lane in range(3):
                    n = need_of.get(lane)
                    if n == "x":
                        continue
                    cost[lane] = abs(lane - plan["lane"]) * 2 + (1 if n else 0) - (1 if SKY in things.get(lane, ()) else 0)
                target = min(cost, key=lambda ln: (cost[ln], abs(ln - 1)))
                steps = target - plan["lane"]
                t_sw = max(tr - 0.55 + self.rng.gauss(0, sigma), r.get("prow", -9) + 0.06)
                if wrong and steps:
                    t_sw = tr + 0.05                     # swerves too late
                for k in range(abs(steps)):
                    add(t_sw + 0.1 * k, "r" if steps > 0 else "l")
                need = need_of.get(target)
                if need and not (wrong and not steps):
                    add(tr - (JT / 2 if need == "u" else 0.3) + self.rng.gauss(0, sigma), need)
                r["prow"] = tr
            else:                                        # a trail of sparks: go there (or not)
                lane = row[0][1]
                if self.rng.random() < greed and lane != plan["lane"]:
                    steps = lane - plan["lane"]
                    for k in range(abs(steps)):
                        add(max(tr - 0.5, r.get("prow", -9) + 0.06) + 0.1 * k + abs(self.rng.gauss(0, sigma)), "r" if steps > 0 else "l")
                while i < len(obs) and obs[i][2] == SPARK and obs[i][1] == lane:      # the rest of the trail
                    i += 1
        r["plan"] = i

    def _maybe_end(self, horizon: float) -> None:
        if self.st.get("phase") != "play":
            return
        run = self.st["run"]
        people = [p["id"] for p in self.st["players"] if not p.get("bot")]
        if horizon >= self.limit():                                         # the time is up (inputs had time to come)
            self.st["complete"] = True
            self._finish(self.limit())
        elif people and all(run[p]["out"] is not None for p in people):    # nobody of the people runs any more
            self.st["complete"] = True
            self._finish(max(horizon, max(run[p]["out"] for p in people)))

    def points(self, pid: str, end_t: float) -> int:
        r = self.st["run"][pid]
        stop = r["out"] if r["out"] is not None else end_t
        return int(dist(min(stop, end_t))) + SPARK_PTS * int(r["sparks"])

    def _finish(self, end_t: float) -> None:
        order, run = self.order(), self.st["run"]
        end_t = max(0.0, end_t)
        obs = self.obstacles(end_t + 1)
        for p in order:                                   # the course up to the end
            if run[p]["out"] is None:
                settle(run[p], obs, end_t)
        self.st["end_t"] = round(end_t, 3)
        scores = {p: self.points(p, end_t) for p in order}
        self.st["scores"] = scores
        self.st["dist"] = {p: int(dist(min(run[p]["out"] if run[p]["out"] is not None else end_t, end_t))) for p in order}
        self.st["places"] = places(order, scores)
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st.update(phase="done", finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: ranked as it stands (no coins – see coins_for)."""
        if self.st.get("phase") == "play":
            self._finish(min(max(0.0, self.gt()), self.limit()))


# ================================================================ the games in the database (table card_game, kind "sternlauf")
class Sternlauf(CardGames):
    """The family table / own tables – the same rows and lobby as the card games (summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng: random.Random | None = None):
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
        out["lives"] = out["lives"] if out["lives"] in LIVES else 3
        out["minutes"] = out["minutes"] if out["minutes"] in MINUTES else 3
        return out

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role, color FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        if p and p["color"]:
            out["color"] = p["color"]
        return out

    def best(self, pid) -> int:
        return int((self.db.get_setting("sternlauf_best") or {}).get(str(pid), 0) or 0)

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status != "done" or st.get("paid") or st.get("places") is None:
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        best = dict(self.db.get_setting("sternlauf_best") or {})
        records = {}
        for p in st["players"]:
            if p.get("bot") or p.get("guest"):
                continue
            sc = int((st.get("scores") or {}).get(p["id"], 0))
            if sc > int(best.get(p["id"], 0) or 0):
                best[p["id"]] = sc
                records[p["id"]] = True
        if records:
            self.db.set_setting("sternlauf_best", best)
        st["records"] = records
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", win_reason(KIND, st['places'][pid]), ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        if len(st["players"]) >= 2 and st.get("complete"):
            self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history:
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]), "score": (st.get("scores") or {}).get(p["id"], 0),
                        "dist": (st.get("dist") or {}).get(p["id"], 0), "sparks": st["run"][p["id"]]["sparks"],
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

    def report(self, pid: int, inputs=()) -> dict | None:
        """The app of this player reports its inputs (only its own player) – answers with the state."""
        taken = 0
        with self.lock:
            row = self._row(KIND, pid)
            if row:
                st = json.loads(row["state"])
                if st["phase"] == "lobby":
                    raise CommunityError("The game has not started yet")
                if st["phase"] == "play":
                    t_ = self.table(st)
                    if str(pid) in st["run"]:
                        st["run"][str(pid)]["seen"] = self.now()      # alive before the clock looks for silent apps
                        if st["run"][str(pid)]["out"] is None:
                            taken = t_.report(str(pid), inputs)
                    t_.tick()
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
        if not row:                                       # over in the meantime: the result
            return self.state(KIND, pid)
        return {**self._view(row, st, str(pid)), "taken": taken}

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
                if st["phase"] == "play":
                    before = json.dumps(st, sort_keys=True)
                    self.table(st).tick()
                    if json.dumps(st, sort_keys=True) != before:
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
                "best": self.best(me) if joined else 0, "now": self.now()}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            return {**base, "players": players, "bots": max(0, min(st["rules"]["bots"], MAX_PLAYERS - len(players)))}
        t = self.table(st)
        run, coins, pl = st["run"], st.get("coins") or {}, st.get("places") or {}
        scores, dists = st.get("scores") or {}, st.get("dist") or {}
        now_t = t.gt() if ph == "play" else st.get("end_t")
        players = []
        for p in st["players"]:
            r = run[p["id"]]
            out = {"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                   "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"), "level": p.get("level"),
                   "lives": r["lives"], "sparks": r["sparks"], "out": r["out"], "next": r["next"], "h": round(r["h"], 3),
                   "score": scores.get(p["id"]) if ph == "done" else None, "dist": dists.get(p["id"]) if ph == "done" else None,
                   "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0), "record": bool((st.get("records") or {}).get(p["id"]))}
            if ph == "play":                              # for the ghosts: the recent inputs (bots: not the planned future)
                out["base"] = r["base"]
                out["ev"] = [e for e in r["ev"] if e[0] <= (now_t or 0) + AHEAD]
            if p["id"] == me:
                out["hits"] = r["hits"]
                out["got"] = r["got"]
            players.append(out)
        return {**base, "players": players, "me": me if joined else None, "seed": st["seed"], "t0": st["t0"], "lives0": st.get("lives", 3),
                "limit": t.limit(), "end_t": st.get("end_t"), "ranking": st.get("ranking"), "complete": bool(st.get("complete")),
                "now_t": now_t}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
