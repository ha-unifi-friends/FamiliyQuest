"""«Jump» – a live jumping race: every player has their own lane, obstacles come from the left, jump over them.

Everybody plays on their own device (family table, guests via QR code) or alone (high score, optionally with practice
bots) – the tables live in the `card_game` table with kind "jump" (lobby, join, summary, may_lead from
cardgames.CardGames, like «Heimwärts»).

Fair for everybody: all lanes get the SAME obstacles – a course made from a seed of the server (`course()`, the same
generator runs in web/jump.js) – and run on the same game clock (game time 0 = `t0`, a short countdown after the start).
The speed grows with the distance (V0 → VMAX); from speed 7 also double obstacles, from speed 10 long ones.

The jump physics run in the app (no waiting for the network): it reports its jumps (game times) and the obstacles it hit
(index + game time). The server is tolerant – it keeps lives and the state per player, checks only sane values (a time
near the game clock, an obstacle that really passes then, one life per obstacle, a short invulnerability) and shows the
others' lanes from the reported jump times (the app draws them a moment late, so they look smooth).
Everybody has 3 lives (rule `lives`: 1 / 3 / 5); without lives you are out. A player whose app stays silent for
STALE seconds is out too (left the game).
End: at a family table the last one alive wins (the game ends when one is left, or no person is left); alone (also with
practice bots) you play until you are out – the distance (m) is your score, your personal best is kept (setting
`jump_best`). Places: who stays longest; the same moment shares the place. Who leads may end the game early: ranked as
it stands (the ones still running by lives), no coins. Safety: after MAX_T seconds everybody still running is first.
Coins (setting `game_rewards["jump"]`): places 1–3, only people of the family at a family table with at least two of
them – never alone; paid once (flag `paid`, a unique ledger `ref` per player).
Bots (easy / normal / hard): they jump for every obstacle with a timing error (and sometimes forget it) – the faster the
game, the narrower the window; planned LOOKAHEAD seconds ahead so the others see their jumps in time.
"""
from __future__ import annotations

import json
import math
import random
import time

from .cardgames import BOTS, CardGames
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of

KIND = "jump"
TITLE = "Jump"
EMOJI = "🦘"
MAX_PLAYERS = 6
LEVELS = ("easy", "normal", "hard")
DEFAULTS = {"bots": 0, "level": "normal", "lives": 3}
LIVES = (1, 3, 5)

# ---------------------------------------------------------------- the course (the same numbers in web/jump.js)
V0 = 5.0                     # units per second at the start (the lane shows 12 units)
VMAX = 12.0
ACC = 0.05                   # units per second² (VMAX after 140 s)
T1 = (VMAX - V0) / ACC
D1 = V0 * T1 + ACC * T1 * T1 / 2
JT = 0.6                     # a jump lasts 0.6 s …
JH = 1.5                     # … and goes 1.5 units high
OH = 0.7                     # every obstacle is 0.7 units high
AW = 0.25                    # half the width of the avatar (forgiving)
WIDTH = (0.6, 1.6, 2.6)      # single, double, long
FIRST = 2.5                  # the first obstacle after about 2.5 s
COUNTDOWN = 3.0              # seconds from the start to game time 0
INVULN = 1.2                 # after a hit: invulnerable (blinking)
STALE = 12.0                 # a silent app for this long: out
MAX_T = 900.0                # safety: after 15 minutes everybody still running wins
GRACE = 1.0                  # one left: the game ends this much later (a hit at the same moment may be on its way)
LOOKAHEAD = 0.9              # bots plan their jump this early
BOT_SKILL = {"easy": (0.06, 0.03), "normal": (0.035, 0.012), "hard": (0.02, 0.004)}   # timing error σ (s), forgetting


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


def course(seed: int, upto: float) -> list[tuple[float, int]]:
    """The obstacles (distance of the front edge, kind 0 single / 1 double / 2 long) up to this distance."""
    rnd = mulberry32(seed)
    out = []
    x = V0 * FIRST
    while x <= upto:
        v = speed_at(x)
        r1 = rnd()
        r2 = rnd()
        prog = (v - V0) / (VMAX - V0)
        kind = 0
        if v >= 10 and r1 < 0.2:
            kind = 2
        elif v >= 7 and r1 < 0.5:
            kind = 1
        out.append((x, kind))
        x = x + WIDTH[kind] + v * (0.95 + r2 * (1.3 - 0.4 * prog))
    return out


def window(x: float, kind: int) -> tuple[float, float]:
    """The game times while the obstacle is under the avatar."""
    return time_at(x - AW), time_at(x + WIDTH[kind] + AW)


def clears(jump: float, x: float, kind: int) -> bool:
    """A jump started at this game time carries the avatar over the obstacle."""
    s = math.sqrt(1 - OH / JH)
    a, b = window(x, kind)
    return jump + JT * (1 - s) / 2 <= a and b <= jump + JT * (1 + s) / 2


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

    def obstacles(self, t: float) -> list[tuple[float, int]]:
        upto = dist(t) + 40
        if self._course is None or self._course[0] < upto:
            self._course = (upto + 200, course(self.st["seed"], upto + 200))
        return self._course[1]

    def setup(self, seed: int | None = None) -> None:
        ids = self.order()
        if not 1 <= len(ids) <= MAX_PLAYERS:
            raise CommunityError("The table is full")
        lives = int(self.st["rules"].get("lives", 3))
        self.st.update(phase="play", seed=seed if seed is not None else self.rng.randrange(1, 2 ** 31), t0=self.now() + COUNTDOWN,
                       lives=lives, ranking=None, places=None, complete=False, end_t=None,
                       run={pid: {"lives": lives, "jumps": [], "hits": [], "out": None, "t": -COUNTDOWN, "next": 0, "seen": self.now()}
                            for pid in ids})

    def alive(self, t: float | None = None) -> list[str]:
        run = self.st["run"]
        return [p for p in self.order() if run[p]["out"] is None or (t is not None and run[p]["out"] > t)]

    # ---------- what an app reports
    def report(self, pid: str, t=None, jumps=(), hits=()) -> None:
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        r = self.st["run"].get(pid)
        p = self.seat_of(pid)
        if r is None or not p or p.get("bot"):
            raise CommunityError("You are not at this table")
        now_t = self.gt()
        r["seen"] = self.now()
        if r["out"] is not None:
            return

        def ok(x) -> float | None:
            try:
                x = float(x)
            except (TypeError, ValueError):
                return None
            return x if math.isfinite(x) and -COUNTDOWN - 1 <= x <= now_t + 1.0 else None
        tt = ok(t)
        if tt is not None:
            r["t"] = max(r["t"], tt)
        for j in sorted(x for x in (ok(j) for j in list(jumps)[:20]) if x is not None):
            if not r["jumps"] or j >= r["jumps"][-1] + JT * 0.8:
                r["jumps"].append(round(j, 3))
        del r["jumps"][:-8]
        obs = self.obstacles(now_t + 2)
        for h in list(hits)[:10]:
            if r["out"] is not None:
                break
            try:
                i, th = int(h[0]), ok(h[1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if th is None or not 0 <= i < len(obs) or any(k == i for k, _ in r["hits"]):
                continue
            a, b = window(*obs[i])
            if not a - 1.5 <= th <= b + 1.5:
                continue
            if r["hits"] and th < r["hits"][-1][1] + INVULN * 0.8:
                continue
            self._hit(r, i, th)
        self._maybe_end()

    def _hit(self, r: dict, i: int, th: float) -> None:
        r["hits"].append([i, round(th, 3)])
        r["lives"] -= 1
        if r["lives"] <= 0:
            r["lives"] = 0
            r["out"] = round(th, 3)

    # ---------- the clock: bots, silent apps, the end
    def tick(self) -> bool:
        if self.st.get("phase") != "play":
            return False
        before = json.dumps(self.st["run"], sort_keys=True)
        now_t = self.gt()
        obs = self.obstacles(now_t + LOOKAHEAD + 2)
        for p in self.st["players"]:
            r = self.st["run"][p["id"]]
            if r["out"] is not None:
                continue
            if p.get("bot"):
                self._bot(p, r, obs, now_t)
            elif now_t > 0 and self.now() - r.get("seen", 0) > STALE:        # the app is gone: out
                r["out"] = round(max(0.0, min(now_t, r["t"])), 3)
        self._maybe_end()
        return self.st.get("phase") != "play" or json.dumps(self.st["run"], sort_keys=True) != before

    def _bot(self, p: dict, r: dict, obs: list, now_t: float) -> None:
        sigma, forget = BOT_SKILL.get(p.get("level"), BOT_SKILL["normal"])
        while r["out"] is None and r["next"] < len(obs):
            i = r["next"]
            x, kind = obs[i]
            a, b = window(x, kind)
            if a - JT > now_t + LOOKAHEAD:
                break
            r["next"] += 1
            v = speed_at(x)
            lost = self.rng.random() < forget * (1 + (v - V0) / V0)        # forgot to jump
            last = r["jumps"][-1] if r["jumps"] else -99.0
            if not lost:
                j = (a + b) / 2 - JT / 2 + self.rng.gauss(0, sigma)
                j = max(j, last + JT)
                r["jumps"].append(round(j, 3))
                del r["jumps"][:-8]
                ok = clears(j, x, kind)
            else:
                ok = clears(last, x, kind)
            if not ok and not (r["hits"] and a < r["hits"][-1][1] + INVULN):
                self._hit(r, i, round(a, 3))

    def _maybe_end(self) -> None:
        if self.st.get("phase") != "play":
            return
        now_t = self.gt()
        run, people = self.st["run"], [p["id"] for p in self.st["players"] if not p.get("bot")]
        alive = self.alive(now_t)
        alive_people = [p for p in people if p in alive]
        end = not alive_people or now_t >= MAX_T
        if not self.st.get("solo") and len(self.order()) >= 2 and len(alive) <= 1:
            # one left: a moment of grace – a hit at the same moment may still be on its way
            last = max((run[p]["out"] for p in self.order() if run[p]["out"] is not None), default=0.0)
            end = end or now_t >= last + GRACE
        if end:
            self.st["complete"] = True
            outs = [run[p]["out"] for p in self.order() if run[p]["out"] is not None and run[p]["out"] <= now_t]
            self._finish(now_t if alive else max(outs, default=now_t))

    def score(self, pid: str, t: float | None = None) -> int:
        """The distance run (m) – up to the moment out, else up to now / the end."""
        r = self.st["run"][pid]
        if r["out"] is not None:
            return int(dist(r["out"]))
        end = self.st.get("end_t")
        return int(dist(end if end is not None else (t if t is not None else self.gt())))

    def _finish(self, end_t: float) -> None:
        order, run = self.order(), self.st["run"]
        for p in order:                                   # a bot's planned miss after the end does not count
            if run[p]["out"] is not None and run[p]["out"] > end_t:
                run[p]["out"] = None
                run[p]["lives"] = max(1, run[p]["lives"])
        self.st["end_t"] = round(max(0.0, end_t), 3)
        rank = {p: (10 ** 9 + run[p]["lives"] * 10 ** 6 if run[p]["out"] is None else int(run[p]["out"] * 1000)) for p in order}
        self.st["places"] = places(order, rank)
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st["scores"] = {p: self.score(p) for p in order}
        self.st.update(phase="done", finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: ranked as it stands (no coins – see coins_for)."""
        if self.st.get("phase") == "play":
            self._finish(max(0.0, self.gt()))


# ================================================================ the games in the database (table card_game, kind "jump")
class Jump(CardGames):
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
        return out

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    def best(self, pid) -> int:
        return int((self.db.get_setting("jump_best") or {}).get(str(pid), 0) or 0)

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status != "done" or st.get("paid") or st.get("places") is None:
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        # the personal best (people of the family, alone or at a table)
        best = dict(self.db.get_setting("jump_best") or {})
        records = {}
        for p in st["players"]:
            if p.get("bot") or p.get("guest"):
                continue
            sc = int((st.get("scores") or {}).get(p["id"], 0))
            if sc > int(best.get(p["id"], 0) or 0):
                best[p["id"]] = sc
                records[p["id"]] = True
        if records:
            self.db.set_setting("jump_best", best)
        st["records"] = records
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", f"{TITLE} – Platz {st['places'][pid]}", ref=ref)
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

    def report(self, pid: int, t=None, jumps=(), hits=()) -> dict | None:
        """The app of this player reports its jumps and hits (only its own player) – answers with the state."""
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
                    t_.tick()
                    if st["phase"] == "play":
                        t_.report(str(pid), t, jumps, hits)
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
                "best": self.best(me) if joined else 0, "now": self.now()}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            return {**base, "players": players, "bots": max(0, min(st["rules"]["bots"], MAX_PLAYERS - len(players)))}
        t = self.table(st)
        run, coins, pl = st["run"], st.get("coins") or {}, st.get("places") or {}
        scores = st.get("scores") or {}
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                    "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"), "level": p.get("level"),
                    "lives": run[p["id"]]["lives"], "jumps": run[p["id"]]["jumps"], "hits": run[p["id"]]["hits"],
                    "out": run[p["id"]]["out"], "score": scores.get(p["id"]) if ph == "done" else None,
                    "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0), "record": bool((st.get("records") or {}).get(p["id"]))}
                   for p in st["players"]]
        return {**base, "players": players, "me": me if joined else None, "seed": st["seed"], "t0": st["t0"], "lives0": st.get("lives", 3),
                "end_t": st.get("end_t"), "ranking": st.get("ranking"), "complete": bool(st.get("complete")),
                "now_t": t.gt() if ph == "play" else st.get("end_t")}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
