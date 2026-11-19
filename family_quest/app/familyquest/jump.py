"""«Jump» – a live jumping race: every player has their own lane, obstacles come from the left, jump over them.

Everybody plays on their own device (family table, guests via QR code) or alone (high score, optionally with practice
bots) – the tables live in the `card_game` table with kind "jump" (lobby, join, summary, may_lead from
cardgames.CardGames, like «Heimwärts»).

Fair for everybody: all lanes get the SAME obstacles – a course made from a seed of the server (`course()`, the same
generator runs in web/jump.js) – and run on the same game clock (game time 0 = `t0`, a short countdown after the start).
The speed grows with the distance (V0 → VMAX); from speed 7 also double crates, from speed 10 long hedges.
Crates carry you: landing on top is safe (you run along and may jump on from there), only running into their side costs
a life. Cacti (and hedges) cost a life when touched. At about CLOUD_T seconds (then again CLOUD_EVERY s after the end of
the last one) comes a cloud parcours: after a free stretch with a signpost (the app shows a warning) 4–6 crates on
clouds at heights 1.0–1.4, a short jump apart, over a dense cactus field – falling down costs a life (one per field piece).
After any hit you hop up a little and are invulnerable for INVULN s.

The jump physics run in the app (no waiting for the network) step by step (`Runner`, the same in web/jump.js as
JuRunner, so every app draws the others' lanes from their jump times exactly): it reports its jumps (game times) and the
elements it hit (index + game time). The server is tolerant – it keeps lives and the state per player, checks only sane values (a time
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
Bots (easy / normal / hard) run the same Runner: when a hit is coming they look for the jump times that get them past
(over it, onto a crate, onto the next cloud box) and aim at the middle with a timing error (and sometimes forget it) –
the faster the game, the narrower the window; planned LOOKAHEAD seconds ahead so the others see their jumps in time.
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
JT = 0.6                     # a jump from the ground back to the ground lasts 0.6 s …
JH = 1.5                     # … and goes 1.5 units high
OH = 0.7                     # a crate / a hedge is 0.7 units high
AW = 0.25                    # half the width of the avatar (forgiving)
# the kinds: 0 crate, 1 double crate (both solid: stand on them, only their side costs a life), 2 long hedge,
# 3 cactus (both: touching costs a life), 4 a crate on a cloud (a platform: only landed on from above, never a hit),
# 5 the dense cactus field under the cloud boxes (costs a life)
WIDTH = (0.6, 1.6, 2.6, 0.5)
TALL = (0.7, 0.7, 0.7, 0.8)
FIELD_H = 0.5                # the cactus field
FIRST = 2.5                  # the first obstacle after about 2.5 s
CLOUD_T = 45.0               # the first cloud parcours at about this game time …
CLOUD_EVERY = 60.0           # … then again this long after the end of the last one
CLOUD_LEAD = 1.6             # free ground before the first cloud box (the warning shows ~3 s before)
COUNTDOWN = 3.0              # seconds from the start to game time 0
INVULN = 1.2                 # after a hit: invulnerable (blinking)
STALE = 12.0                 # a silent app for this long: out
MAX_T = 900.0                # safety: after 15 minutes everybody still running wins
GRACE = 1.0                  # one left: the game ends this much later (a hit at the same moment may be on its way)
LOOKAHEAD = 0.9              # bots plan their jump this early
BOT_SKILL = {"easy": (0.06, 0.03), "normal": (0.035, 0.012), "hard": (0.02, 0.004)}   # timing error σ (s), forgetting
# the physics, step by step (the same in web/jump.js – JuRunner)
HZ = 120                     # steps per second
G = 8 * JH / (JT * JT)       # gravity, units/s²
VJ = 4 * JH / JT             # the jump's start speed
VB = 0.6 * VJ                # the little hop after a hit
LG = 0.2                     # landing grace: feet up to this much below a top still land on it (and do not hit its side)
COYOTE = 0.1                 # a jump just after walking off an edge still counts
MINJ = 0.2                   # two reported jumps at least this far apart
KEEP = 40                    # the last jumps kept per player (the others' apps draw the lanes from them)


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


def _clouds(out: list, x: float, rnd) -> float:
    """A cloud parcours from x on: 4–6 crates on clouds (heights 1.0–1.4, gaps a short jump wide), under them a dense
    cactus field (one piece per box). Answers where the normal course goes on."""
    v = speed_at(x)
    n = 4 + int(rnd() * 3)
    x = x + v * CLOUD_LEAD
    top = 1.1
    plats = []
    for k in range(n):
        w = v * ((0.85 if k == 0 else 0.6) + 0.25 * rnd())
        plats.append((x, w, top))
        x = x + w + v * (0.24 + 0.1 * rnd())
        top = min(1.4, max(1.0, top + (rnd() - 0.5) * 0.8))
    for k in range(n):
        px, w, top = plats[k]
        out.append((px, 4, w, top))
        fs = px + 0.4 if k == 0 else px
        fe = plats[k + 1][0] if k + 1 < n else px + w - 0.4
        out.append((fs, 5, fe - fs, FIELD_H))
    return plats[-1][0] + plats[-1][1] + v * 1.4


def course(seed: int, upto: float) -> list[tuple[float, int, float, float]]:
    """The course up to this distance: (x of the front edge, kind, width, height of the top) – see WIDTH for the kinds.
    A longer course starts with the same elements (the indexes stay)."""
    rnd = mulberry32(seed)
    out = []
    x = V0 * FIRST
    nc = dist(CLOUD_T)
    while x <= upto:
        if x >= nc:
            x = _clouds(out, x, rnd)
            nc = dist(time_at(x) + CLOUD_EVERY)
            continue
        v = speed_at(x)
        r1 = rnd()
        r2 = rnd()
        r3 = rnd()
        prog = (v - V0) / (VMAX - V0)
        kind = 3 if r3 < 0.4 else 0
        if v >= 10 and r1 < 0.2:
            kind = 2
        elif v >= 7 and r1 < 0.5:
            kind = 1
        out.append((x, kind, WIDTH[kind], TALL[kind]))
        x = x + WIDTH[kind] + v * (0.95 + r2 * (1.3 - 0.4 * prog))
    return out


def clouds(obs) -> list[int]:
    """The indexes where a cloud parcours starts (its first cloud box)."""
    return [i for i, o in enumerate(obs) if o[1] == 4 and (i == 0 or obs[i - 1][1] < 4)]


def window(x: float, kind: int, w: float | None = None, h: float | None = None) -> tuple[float, float]:
    """The game times while the element is under the avatar."""
    return time_at(x - AW), time_at(x + (WIDTH[kind] if w is None else w) + AW)


def clears(jump: float, x: float, kind: int, w: float | None = None, h: float | None = None) -> bool:
    """A jump from the ground started at this game time carries the avatar over the element (without landing on it)."""
    s = math.sqrt(1 - (TALL[kind] if h is None else h) / JH)
    a, b = window(x, kind, w)
    return jump + JT * (1 - s) / 2 <= a and b <= jump + JT * (1 + s) / 2


class Runner:
    """The jump physics of one runner, step by step (1/HZ s) – the same in web/jump.js (JuRunner), so every app draws
    the others' lanes from their jump times exactly as they ran. Crates and cloud boxes carry you (landing grace LG),
    the side of a crate, a cactus, a hedge or the cactus field costs a life (one per element, then INVULN s
    invulnerable, with a little hop). A jump counts only from the ground / a box (or just after walking off: COYOTE)."""
    FIELDS = ("k", "y", "vy", "ground", "walk", "left", "jt", "last", "lo", "hits")

    def __init__(self, d: dict | None = None):
        self.k, self.y, self.vy, self.ground, self.walk = 0, 0.0, 0.0, True, False
        self.left, self.jt, self.last, self.lo, self.hits = -99.0, -99.0, -99.0, 0, []
        for f in self.FIELDS:
            if d and f in d:
                setattr(self, f, d[f])
        self.hits = [list(h) for h in self.hits]
        self.ids = {h[0] for h in self.hits} | set((d or {}).get("ids") or ())
        self.jumped = False

    def dump(self) -> dict:
        return {f: getattr(self, f) for f in self.FIELDS}

    def copy(self) -> "Runner":
        c = Runner(self.dump())
        c.hits, c.ids = [], set(self.ids)
        return c

    def t(self) -> float:
        return self.k / HZ

    def can_jump(self) -> bool:
        return self.ground or (self.walk and (self.k + 1) / HZ - self.left <= COYOTE)

    def ji(self, jumps) -> int:
        """The first jump not used yet."""
        i = len(jumps)
        while i > 0 and jumps[i - 1] > self.jt:
            i -= 1
        return i

    def near(self, obs, d: float) -> list[int]:
        while self.lo < len(obs) and obs[self.lo][0] + obs[self.lo][2] < d - AW:
            self.lo += 1
        out, i = [], self.lo
        while i < len(obs) and obs[i][0] <= d + AW:
            if obs[i][0] + obs[i][2] >= d - AW:
                out.append(i)
            i += 1
        return out

    def step(self, obs, jumps, ji: int) -> tuple[int, list | None]:
        k1 = self.k + 1
        t1 = k1 / HZ
        want = False
        while ji < len(jumps) and jumps[ji] < t1:
            want = True
            self.jt = jumps[ji]
            ji += 1
        self.jumped = False
        if want and self.can_jump():
            self.vy, self.ground, self.walk, self.jumped = VJ, False, False, True
        near = self.near(obs, dist(t1))
        y0 = self.y
        if self.ground:
            s = 0.0
            for i in near:
                o = obs[i]
                if (o[1] <= 1 or o[1] == 4) and s < o[3] <= y0 + 1e-6:
                    s = o[3]
            if s < y0 - 1e-6:                              # walked off an edge: falling
                self.ground, self.walk, self.left, self.vy = False, True, t1, 0.0
            else:
                self.y = s
        if not self.ground:
            y1 = y0 + self.vy / HZ - G / (2 * HZ * HZ)
            self.vy = self.vy - G / HZ
            land = None
            if self.vy <= 0:
                if y1 <= 0:
                    land = 0.0
                for i in near:
                    o = obs[i]
                    if (o[1] <= 1 or o[1] == 4) and y1 <= o[3] <= y0 + LG and (land is None or o[3] > land):
                        land = o[3]
            if land is not None:
                self.y, self.vy, self.ground, self.walk = land, 0.0, True, False
            else:
                self.y = y1
        self.k = k1
        if t1 >= self.last + INVULN:
            for i in near:
                o = obs[i]
                if o[1] == 4 or i in self.ids:
                    continue
                if self.y < (o[3] - LG if o[1] <= 1 else o[3]):
                    hit = [i, t1]
                    self.ids.add(i)
                    self.hits.append(hit)
                    self.last = t1
                    self.vy, self.ground, self.walk = VB, False, False
                    return ji, hit
        return ji, None

    def run(self, obs, jumps, t: float) -> list[list]:
        """On to game time t: the new hits."""
        ji, out = self.ji(jumps), []
        while (self.k + 1) / HZ <= t:
            ji, hit = self.step(obs, jumps, ji)
            if hit:
                out.append(hit)
        return out


def _danger(run: Runner, obs, steps: int) -> tuple[int, int] | None:
    """Without a jump: (the step of the first hit, the element) within this many steps – or None."""
    c = run.copy()
    c.last = -99.0
    for _ in range(steps):
        _, hit = c.step(obs, (), 0)
        if hit:
            return c.k, hit[0]
    return None


def _safe(run: Runner, obs, j: float, i0: int, steps: int) -> bool:
    """A jump at j gets past element i0 (or onto a box) without a hit."""
    c = run.copy()
    c.last = -99.0
    js, ji, jumped = [j], 0, False
    end = obs[i0][0] + obs[i0][2]
    for _ in range(steps):
        before = ji
        ji, hit = c.step(obs, js, ji)
        if hit:
            return False
        if ji > before and not c.jumped:
            return False
        jumped = jumped or c.jumped
        if jumped and c.ground and (c.y > 0.3 or dist(c.t()) - AW > end):
            return True
    return True


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
                       run={pid: {"lives": lives, "jumps": [], "hits": [], "out": None, "t": -COUNTDOWN, "seen": self.now()}
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
            if not r["jumps"] or j >= r["jumps"][-1] + MINJ:
                r["jumps"].append(round(j, 3))
        del r["jumps"][:-KEEP]
        obs = self.obstacles(now_t + 2)
        for h in list(hits)[:10]:
            if r["out"] is not None:
                break
            try:
                i, th = int(h[0]), ok(h[1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if th is None or not 0 <= i < len(obs) or obs[i][1] == 4 or any(k == i for k, _ in r["hits"]):
                continue                                  # a cloud box never hits
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
        """A bot runs the same physics as the apps, planned LOOKAHEAD s ahead: when a hit is coming without a jump
        (a crate, a cactus, the gap between two cloud boxes), it looks for the jump times that get it past (over it
        or onto a box), aims at the middle with a timing error – and sometimes forgets it."""
        sigma, forget = BOT_SKILL.get(p.get("level"), BOT_SKILL["normal"])
        run = Runner(r.get("sim"))
        jumps = r["jumps"]
        ji = run.ji(jumps)
        until = int((now_t + LOOKAHEAD) * HZ)
        while run.k < until and r["out"] is None:
            if run.k >= r.get("wait", 0) and run.can_jump() and not (jumps and jumps[-1] >= run.t()):
                self._bot_plan(r, run, obs, sigma, forget)
                ji = run.ji(jumps)
            ji, hit = run.step(obs, jumps, ji)
            if hit and r["out"] is None:
                self._hit(r, hit[0], round(hit[1], 3))
        run.hits = []                                      # the hits are kept in r["hits"]
        r["sim"] = run.dump()
        r["sim"]["ids"] = sorted(run.ids)

    def _bot_plan(self, r: dict, run: Runner, obs: list, sigma: float, forget: float) -> None:
        d = dist(run.t())
        v = speed_at(d)
        nxt = next((o for o in obs[run.lo:] if o[0] + o[2] >= d - AW), None)
        if run.y <= 0 and (nxt is None or nxt[0] > d + v * 1.3 + 1):   # nothing near: look again a bit later
            r["wait"] = run.k + 12
            return
        dg = _danger(run, obs, int(1.3 * HZ))
        if dg is None:
            r["wait"] = run.k + 12
            return
        kh, i0 = dg
        if self.rng.random() < forget * (1 + (v - V0) / V0):           # forgot to jump
            r["wait"] = kh + 1
            return
        cands = list(range(max(run.k, kh - int(0.9 * HZ)), kh, 4))
        ok = [_safe(run, obs, kj / HZ, i0, int(1.6 * HZ)) for kj in cands]
        best, cur = (0, 0), None                                       # the longest stretch of good jump times
        for n, good in enumerate(ok + [False]):
            if good and cur is None:
                cur = n
            elif not good and cur is not None:
                if n - cur > best[1] - best[0]:
                    best = (cur, n)
                cur = None
        if best[1] > best[0]:
            mid = (cands[best[0]] + cands[best[1] - 1]) / 2 / HZ
        else:
            mid = max(run.k, kh - int(0.3 * HZ)) / HZ
        j = round(max(run.t(), mid + self.rng.gauss(0, sigma)), 3)
        r["jumps"].append(j)
        del r["jumps"][:-KEEP]
        r["wait"] = run.k + 1

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
        self._payout(KIND, row["id"], coins, lambda pid: win_reason(KIND, st["places"][pid]))
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
