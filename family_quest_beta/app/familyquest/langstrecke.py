"""«24h Endurance» (24-Stunden-Rennen) – a live team endurance race on the fictional «Circuit des Tannes».

Teams are racing stables (a colour, a name, a start number), each with ONE car. The family splits into 1–4 teams at
the table (guests via QR code join a team too); bots bring extra cars (traffic) – alone against bot teams works too. The
tables live in the `card_game` table with kind "langstrecke" (lobby, join, summary, may_lead from cardgames.CardGames).

24 race hours are compressed into 10 / 15 / 20 real minutes (rule `minutes`): the race clock starts at 15:00 and runs
through the night (dusk, headlights, a shorter view, fog banks) into the next afternoon. Optional rain (rule `weather`):
showers drawn at the start, the race engineer sees them coming on the radar. Winner: the most laps at the end (then
the longer distance).

Roles in a team, each on their own phone – they rotate at every pit stop (driver change; a driver may drive at most
STINT_MAX stints in a row, so everybody gets to drive):
- alone: you drive and do the pit-stop jobs yourself one after the other;
- 2–3 people: a driver and the pit crew; 4–5: also a race engineer (telemetry, radar, gaps, radio calls).
The driver steers the car on three lanes (swipe / arrow keys) with a throttle lever (0–10). Pushing is faster but
heats the engine (yellow: hot, red: lift off within GRACE seconds of pushing – else engine damage: limp to the pits; ignoring the
red twice: the team retires and keeps its laps) and costs tyres and fuel. On the track: gravel, oil, debris, slow
cars (backmarkers); collisions wear the tyres or break the wing. Rain on slicks: less grip; rain tyres in the dry wear
twice as fast. A crash (engine failure, a fast hit into a backmarker) brings the safety car: SC_LEN seconds at a
limited speed for everybody, no overtaking, the track is cleared – a cheap moment for a pit stop. The last two race
hours are the finale.

Pit stop (the driver boxes: «Box this lap» – the car stops at the line): the crew plays mini-games on their phones at
the same time while a stopwatch runs – tyres (choose the compound, tap the 4 wheel nuts in the shown order and hold
each until tight: a loose one costs a wheel on the next lap), refuelling (hold the nozzle, let go in the green zone:
too little may run dry, an overflow costs SPILL_PEN seconds), and after damage a repair (connect the cables by colour
or turn the screws straight; a wrong answer costs WRONG_PEN seconds). Each job ends at the moment the server gets it
(server time); claimed hold times must fit into that time. A job nobody does is done by the garage after
PIT_TASK_MAX seconds.

The server decides everything (the same step function runs in web/langstrecke.js for a smooth picture of the own
car): the driver's app only reports its inputs (lane, throttle, box) with their game time; the server simulates all
cars in fixed steps of DT seconds SETTLE seconds behind the clock – a late input is applied at the next step (never
in the past), so laps, hits, damage and pit results cannot be cheated. A driver whose app is silent for AUTO_AFTER
seconds gets the autopilot (the bot driver) until the app is back. Bots drive by the same rules: they dodge what
they see (easier bots miss more), manage the temperature and pit sensibly (fuel, tyres, damage, rain, safety car).

Coins (setting `game_rewards["langstrecke"]`): places 1–3, for every person of the family in that team, only at a
family table with at least two people of the family, only for a race run to the end – paid once (flag `paid`, a
unique ledger `ref` per player). Records: most laps (`langstrecke_best`) and the fastest pit stop in tenths of a
second (`langstrecke_pit`) per person; the «No. 1» hat for the winning team.
"""
from __future__ import annotations

import json
import math
import random
import time

from .cardgames import BOTS, CardGames
from .community import CommunityError
from .pairhunt import rewards_of as _rewards_of

KIND = "langstrecke"
TITLE = "24h Endurance"
EMOJI = "🏎️"
CIRCUIT = "Circuit des Tannes"
MAX_PLAYERS = 12
LEVELS = ("easy", "normal", "hard")
DIFFS = ("junior", "normal")
MINUTES = (10, 15, 20)
DEFAULTS = {"bots": 2, "level": "normal", "minutes": 15, "weather": 1, "difficulty": "normal", "team_size": 4, "teams": 2}

# ---------------------------------------------------------------- the car (the same numbers in web/langstrecke.js)
L = 1500.0                   # metres per lap
DT = 0.1                     # one step of the simulation (seconds)
VMIN, VMAX = 10.0, 62.0      # m/s at throttle 0 / 10 (shown as km/h × 5)
ACC, BRAKE = 9.0, 22.0       # m/s²
VLIMP, VDRY, VSC, VSLOW, VBACK = 18.0, 8.0, 26.0, 16.0, 24.0   # limping / no fuel / safety car / after gravel or oil / backmarkers
HEAT, HEAT_JR = 1.5, 0.8     # °/s per throttle step above COOL_AT
COOL_AT = 7.4
YELLOW, RED = 75.0, 90.0
GRACE, GRACE_JR = 3.0, 6.0   # seconds in the red before the engine is damaged
FUEL_M = 100.0 / (7 * L)     # % fuel per metre at full throttle (×(0.55 + 0.045·throttle))
WEAR_M = 100.0 / (12 * L)    # % tyre wear per metre at full throttle (×(0.5 + 0.05·throttle))
GRAVEL, OIL, SLOW, DEBRIS = 0, 1, 2, 3
COUNTDOWN = 8.0              # seconds from the start to game time 0 (the intro: run to the cars, engines, lights)
SETTLE = 0.8                 # the server simulates this far behind the clock
AHEAD = 0.5                  # inputs may be this much ahead of the server's clock
AUTO_AFTER = 6.0             # a silent driver: the autopilot drives
STALE = 10.0                 # a silent member gets no pit job
STINT_MAX = 2                # stints in a row per driver
CHANGE_T = 2.0               # a driver change takes at least this long
PIT_TASK_MAX = 30.0          # a job nobody does: the garage does it after this long
FILL_RATE = 30.0             # % per second at the fuel nozzle
GREEN = (88.0, 100.0)        # the green zone of the fuel gauge
SPILL_PEN, WRONG_PEN = 3.0, 2.0
HOLD_MIN = 0.5               # a wheel nut held at least this long is tight
SC_LEN, SC_GAP = 20.0, 60.0  # safety car: duration, at least this long between two
REF_V = 45.0                 # m/s for the gaps in seconds
RADIO = ("box", "save", "push", "rain", "dry")
TEAM_STYLES = (("Comet Racing", "#e03131"), ("Blue Falcon Works", "#1c7ed6"), ("Pine Cone Motors", "#2f9e44"),
               ("Sunrise Speedsters", "#f08c00"), ("Silver Owl Garage", "#7048e8"), ("Night Fox Racing", "#0c8599"),
               ("Thunder Bee Team", "#e8590c"), ("Snow Hare Racing", "#495057"))
NUMBERS = (3, 7, 8, 11, 12, 17, 21, 24, 27, 33, 36, 42, 44, 51, 58, 63, 77, 88, 91, 99)
BOT_SKILL = {"easy": (0.22, 7.0, (7, 10), (4, 6), (7, 10)), "normal": (0.1, 9.0, (5, 8), (3.5, 5), (5, 8)),
             "hard": (0.04, 10.0, (4, 6), (3, 4), (4, 6))}       # missed things, push, tyres / fuel / repair seconds


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


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


_THINGS: dict = {}


def lap_things(seed: int, lap: int, junior: bool) -> list[list]:
    """What lies on the track in this lap (the same for every car on its own lap): [[x in the lap, lane, kind], …]."""
    key = (seed, lap, junior)
    got = _THINGS.get(key)
    if got is None:
        rnd = mulberry32((seed + lap * 7919) & 0xFFFFFFFF)
        n = (2 + int(rnd() * 2)) if junior else (4 + int(rnd() * 3))
        got = []
        for i in range(n):
            x = 160 + (L - 320) * (i + 0.15 + 0.7 * rnd()) / n
            lane = int(rnd() * 3)
            r = rnd()
            kind = GRAVEL if r < 0.28 else OIL if r < 0.48 else SLOW if r < 0.76 else DEBRIS
            got.append([math.floor(x * 10 + 0.5) / 10, lane, kind])
        if len(_THINGS) > 4000:
            _THINGS.clear()
        _THINGS[key] = got
    return got


def fog_at(seed: int, lap: int) -> float:
    """A fog bank in this lap (only at night, only for the eyes): its position in the lap."""
    rnd = mulberry32((seed * 3 + lap * 104729 + 17) & 0xFFFFFFFF)
    return math.floor((300 + (L - 600) * rnd()) * 10 + 0.5) / 10


def new_car(lane: int, d: float) -> dict:
    return {"d": d, "v": 0.0, "lane": lane, "thr": 6, "temp": 60.0, "red": 0.0, "blow": 0, "eng": 0, "wing": 0, "wheel": 0,
            "loose": -1.0, "wear": 0.0, "fuel": 100.0, "tyre": "s", "box": 0, "boxed": 0, "slow": 0.0, "olap": 0, "ob": 0,
            "ls": 0.0, "best": 0.0, "out": None, "pit": 0, "hits": 0}


def in_window(wins, s: float) -> bool:
    return any(a <= s < b for a, b in wins or ())


def apply_input(car: dict, c: str, v) -> None:
    """One input of the driver – the same rules as in the app."""
    if c == "l":
        if not car["pit"]:
            car["lane"] = max(0, car["lane"] - 1)
    elif c == "r":
        if not car["pit"]:
            car["lane"] = min(2, car["lane"] + 1)
    elif c == "u":
        car["thr"] = max(0, min(10, int(v)))
    elif c == "b":
        car["box"] = max(0, min(2, int(v))) if not (car["eng"] or car["wheel"] or car["fuel"] <= 0) else max(1, int(v))


def step(car: dict, s: float, seed: int, jr: bool, rain: bool, sc: bool) -> list[str]:
    """One step of DT seconds from game time s – the same in web/langstrecke.js. Answers what happened."""
    ev: list[str] = []
    if car["out"] is not None:
        return ev
    if car["pit"]:
        car["temp"] = max(55.0, car["temp"] - 8 * DT)
        return ev
    thr = car["thr"]
    w = car["wear"]
    g = 1 - 0.3 * (w / 100) * (w / 100) if w < 100 else 0.55
    if rain:
        g *= 0.97 if car["tyre"] == "r" else 0.75
    elif car["tyre"] == "r":
        g *= 0.93
    vt = (VMIN + (VMAX - VMIN) * thr / 10) * g
    if car["wing"]:
        vt *= 0.88
    if car["eng"] or car["wheel"]:
        vt = min(vt, VLIMP)
    if car["fuel"] <= 0:
        vt = min(vt, VDRY)
    if car["slow"] > 0:
        vt = min(vt, VSLOW)
        car["slow"] = max(0.0, car["slow"] - DT)
    if sc:
        vt = min(vt, VSC)
    v = car["v"]
    v = min(vt, v + ACC * DT) if v < vt else max(vt, v - BRAKE * DT)
    d0 = car["d"]
    d1 = d0 + v * DT
    # the engine
    heat = (HEAT_JR if jr else HEAT) * (0.5 if car["eng"] else 1)          # a damaged engine (limping) heats slower
    car["temp"] = min(110.0, max(50.0, car["temp"] + ((thr - COOL_AT) * heat - (0.4 if rain else 0)) * DT))
    if car["temp"] >= RED and thr > COOL_AT:            # in the red and still pushing: the clock runs (lifting off stops it)
        car["red"] += DT
        if car["red"] > (GRACE_JR if jr else GRACE) + 1e-9:
            car["blow"] += 1
            car["red"] = 0.0
            car["temp"] = 70.0
            if car["blow"] >= 2:
                car["out"] = round(s + DT, 2)
                car["v"] = 0.0
                ev.append("retired")
                return ev
            car["eng"] = 1
            car["box"] = max(car["box"], 1)
            ev.append("blow")
    elif car["temp"] < RED:
        car["red"] = 0.0
    # fuel and tyres
    dist = d1 - d0
    had = car["fuel"] > 0
    car["fuel"] = max(0.0, car["fuel"] - dist * FUEL_M * (0.55 + 0.045 * thr))
    if had and car["fuel"] <= 0:
        car["box"] = max(car["box"], 1)
        ev.append("dry")
    car["wear"] = min(100.0, car["wear"] + dist * WEAR_M * (0.5 + 0.05 * thr) * (2 if car["tyre"] == "r" and not rain else 1))
    # what lies on the track (cleared under the safety car)
    while True:
        things = lap_things(seed, car["olap"], jr)
        if car["ob"] >= len(things):
            car["olap"] += 1
            car["ob"] = 0
            if car["olap"] * L > d1:
                break
            continue
        x, lane, kind = things[car["ob"]]
        xa = car["olap"] * L + x
        if xa > d1:
            break
        car["ob"] += 1
        if xa <= d0 or sc or lane != car["lane"]:
            continue
        if kind == GRAVEL:
            car["slow"] = 1.5
            car["wear"] = min(100.0, car["wear"] + 6)
            ev.append("gravel")
        elif kind == OIL:
            car["slow"] = 3.0 if rain and car["tyre"] != "r" else 2.0
            car["wear"] = min(100.0, car["wear"] + 3)
            ev.append("oil")
        elif kind == DEBRIS:
            car["wear"] = min(100.0, car["wear"] + 12)
            if v > 40:
                car["wing"] = 1
            ev.append("debris")
        elif v > VBACK + 4:                              # into a slow car
            car["wing"] = 1
            car["wear"] = min(100.0, car["wear"] + 8)
            car["slow"] = 1.0
            ev.append("bigcrash" if v > 45 else "crash")
            v = min(v, 20.0)
        else:
            continue
        car["hits"] += 1
    if car["loose"] >= 0 and d1 >= car["loose"]:          # the loose wheel comes off
        car["wheel"] = 1
        car["loose"] = -1.0
        car["box"] = max(car["box"], 1)
        ev.append("wheel")
    # the line: a lap, maybe into the pits
    n0, n1 = math.floor(d0 / L), math.floor(d1 / L)
    if n1 > n0 and n0 >= 0:
        lt = s + DT - car["ls"]
        if car["ls"] > 0 or n0 >= 1:
            car["best"] = round(lt, 2) if not car["best"] or lt < car["best"] else car["best"]
        car["ls"] = round(s + DT, 2)
        ev.append("lap")
        if car["box"]:
            d1 = n1 * L
            v = 0.0
            car["pit"] = 1
            car["boxed"] = car["box"]
            car["box"] = 0
            ev.append("pit")
    elif n1 > n0:
        car["ls"] = round(s + DT, 2)                    # the start: the first lap begins
    car["d"] = d1
    car["v"] = v
    return ev


def laps_of(d: float) -> int:
    return max(0, math.floor(d / L))


def race_hour(s: float, limit: float) -> float:
    """The race clock (hour of the day, 0–24): 15:00 at the start."""
    return (15 + 24 * max(0.0, s) / limit) % 24


def darkness(s: float, limit: float) -> float:
    """0 = day … 1 = night (dusk 20:30–21:30, dawn 05:30–06:30)."""
    hr = race_hour(s, limit)
    if 21.5 <= hr or hr < 5.5:
        return 1.0
    if 20.5 <= hr < 21.5:
        return hr - 20.5
    if 5.5 <= hr < 6.5:
        return 6.5 - hr
    return 0.0


def rain_plan(rng, limit: float) -> list[list[float]]:
    """1–2 showers somewhere in the race (not right at the start)."""
    out = []
    n = rng.choice((1, 2, 2))
    for k in range(n):
        a = limit * (0.12 + 0.8 * (k + rng.random() * 0.7) / n)
        out.append([round(a, 1), round(min(limit, a + limit * (0.06 + 0.06 * rng.random())), 1)])
    return out


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now

    # ---------- basics
    def gt(self) -> float:
        return self.now() - self.st["t0"]

    def limit(self) -> float:
        return 60.0 * int(self.st["rules"].get("minutes", 15))

    def jr(self) -> bool:
        return self.st["rules"].get("difficulty") == "junior"

    def sim_t(self) -> float:
        return self.st["k"] / 10

    def person(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def team_of(self, pid: str) -> dict | None:
        return next((t for t in self.st["teams"] if pid in t["members"]), None)

    def seen_ok(self, pid: str, within: float) -> bool:
        return self.now() - (self.st["seen"].get(pid) or 0) <= within

    def setup(self, seed: int | None = None) -> None:
        """The grid: human teams by the lobby's choice, one bot team per bot; the order on the grid by lot."""
        players = self.st["players"]
        humans = [p for p in players if not p.get("bot")]
        bots = [p for p in players if p.get("bot")]
        groups: dict[int, list[str]] = {}
        for p in humans:
            groups.setdefault(int(p.get("team", 0)), []).append(p["id"])
        teams = []
        styles = list(TEAM_STYLES)
        nums = self.rng.sample(NUMBERS, len(groups) + len(bots))
        for i, k in enumerate(sorted(groups)):           # a team keeps the look it had in the lobby
            name, color = styles[k % len(styles)]
            teams.append({"name": name, "color": color, "num": nums[i], "members": groups[k], "bot": False})
        free = [st_ for i, st_ in enumerate(styles) if i not in groups] or styles
        for j, b in enumerate(bots):
            name, color = free[j % len(free)]
            teams.append({"name": name, "color": color, "num": nums[len(groups) + j], "members": [b["id"]], "bot": True})
        if not teams:
            raise CommunityError("Nobody is at the table")
        order = list(range(len(teams)))
        self.rng.shuffle(order)
        for pos, ti in enumerate(order):                 # the grid: two by two, 10 m apart
            t = teams[ti]
            t.update(car=new_car(pos % 3, -5.0 - 10.0 * pos), driver=t["members"][0], streak=1, stints={t["members"][0]: 1},
                     stop=None, pits=[], radio=None, best_pit=None, ev=[], auto=False, bm=[], blc=-9.0, hot=0, grid=pos + 1)
        for p in players:
            p["team"] = next(i for i, t in enumerate(teams) if p["id"] in t["members"])
        rules = self.st["rules"]
        self.st.update(phase="play", seed=seed if seed is not None else self.rng.randrange(1, 2 ** 31), t0=self.now() + COUNTDOWN,
                       k=0, teams=teams, sc=[], rain=rain_plan(self.rng, self.limit()) if rules.get("weather") else [],
                       seen={p["id"]: self.now() for p in humans}, ranking=None, places=None, complete=False, end_t=None, log=[])

    # ---------- what the apps send
    def report(self, pid: str, inputs=()) -> int:
        """The driver's inputs ([game time, "l"|"r"|"u"|"b", value]) – only the current driver's count; a late one is
        applied at the next step (never in the past). Answers how many were taken."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        p = self.person(pid)
        if not p or p.get("bot"):
            raise CommunityError("You are not at this table")
        self.st["seen"][pid] = self.now()
        t = self.team_of(pid)
        if not t or t["driver"] != pid or t["car"]["out"] is not None:
            return 0
        now_t, sim = self.gt(), self.sim_t()
        taken = 0
        for item in list(inputs)[:40]:
            try:
                te, c = float(item[0]), str(item[1])
                v = int(item[2]) if len(item) > 2 and item[2] is not None else 0
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if c not in ("l", "r", "u", "b") or not math.isfinite(te) or te > now_t + AHEAD:
                continue
            last = t["ev"][-1][0] if t["ev"] else -COUNTDOWN
            te = max(te, sim, last)
            t["ev"].append([round(te, 3), c, v])
            taken += 1
        del t["ev"][:-120]
        return taken

    def radio(self, pid: str, msg: str) -> None:
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        if msg not in RADIO:
            raise CommunityError("Unknown radio call")
        t = self.team_of(pid)
        if not t or t["bot"]:
            raise CommunityError("You are not at this table")
        if t["driver"] == pid and len(t["members"]) > 1:
            raise CommunityError("The driver keeps the hands on the wheel")
        now_t = self.gt()
        if t["radio"] and now_t - t["radio"]["t"] < 1.5:
            return
        self.st["seen"][pid] = self.now()
        t["radio"] = {"m": msg, "t": round(now_t, 2), "from": pid}

    def pit_job(self, pid: str, task: str, data: dict) -> dict:
        """A pit-stop job done on a phone – checked here; the job counts at the server's time of now."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        t = self.team_of(pid)
        if not t or t["bot"]:
            raise CommunityError("You are not at this table")
        self.st["seen"][pid] = self.now()
        stop = t.get("stop")
        if not stop or task not in stop["tasks"]:
            raise CommunityError("No pit stop right now")
        if stop["who"].get(task) != pid:
            raise CommunityError("This is not your job")
        if task in stop["done"]:
            return {"ok": True, "again": True}
        now_t = self.gt()
        el = now_t - stop["t"]
        if el < 0:
            raise CommunityError("No pit stop right now")
        busy = stop["busy"].get(pid, 0.0)
        data = data if isinstance(data, dict) else {}
        out: dict = {"ok": True}
        if task == "tyres":
            nuts = data.get("nuts")
            if not isinstance(nuts, list) or len(nuts) != 4:
                raise CommunityError("Four wheel nuts are needed")
            try:
                order = [int(n[0]) for n in nuts]
                holds = [max(0.0, min(10.0, float(n[1]))) for n in nuts]
            except (TypeError, ValueError, IndexError):
                raise CommunityError("Four wheel nuts are needed") from None
            if order != stop["tasks"]["tyres"]["order"] or not all(math.isfinite(x) for x in holds):
                raise CommunityError("Wrong order")
            if busy + sum(holds) > el + 0.3:
                raise CommunityError("Too fast")
            tyre = "r" if data.get("tyre") == "r" else "s"
            loose = [order[i] for i, x in enumerate(holds) if x < HOLD_MIN]
            stop["busy"][pid] = busy + sum(holds)
            stop["done"]["tyres"] = {"at": round(now_t, 2), "tyre": tyre, "loose": loose}
            out["loose"] = loose
        elif task == "fuel":
            try:
                hold = max(0.0, min(20.0, float(data.get("hold"))))
            except (TypeError, ValueError):
                raise CommunityError("How long was the nozzle held?") from None
            if not math.isfinite(hold) or busy + hold > el + 0.3:
                raise CommunityError("Too fast")
            level = stop["tasks"]["fuel"]["from"] + FILL_RATE * hold
            spill = level > 100.0
            stop["busy"][pid] = busy + hold
            stop["done"]["fuel"] = {"at": round(now_t, 2), "level": round(min(100.0, level), 1), "spill": spill}
            if spill:
                stop["pen"] = round(stop["pen"] + SPILL_PEN, 2)
            out.update(level=round(min(100.0, level), 1), spill=spill, green=GREEN[0] <= level <= GREEN[1])
        elif task == "repair":
            rep = stop["tasks"]["repair"]
            ans = data.get("answer")
            try:
                ans = [int(x) for x in ans]
            except (TypeError, ValueError):
                raise CommunityError("Wrong answer") from None
            ok = (ans == rep["perm"]) if rep["kind"] == "cables" else (len(ans) == len(rep["rot"]) and all((r + a) % 4 == 0 for r, a in zip(rep["rot"], ans)))
            if not ok:
                stop["pen"] = round(stop["pen"] + WRONG_PEN, 2)
                return {"ok": False, "pen": WRONG_PEN}
            stop["done"]["repair"] = {"at": round(now_t, 2)}
        self._stop_end(t)
        return out

    # ---------- the pit stop
    def _rotation(self, t: dict) -> list[str]:
        """The members from the driver on (the order of the roles)."""
        m = t["members"]
        i = m.index(t["driver"]) if t["driver"] in m else 0
        return m[i:] + m[:i]

    def roles(self, t: dict) -> dict[str, str]:
        rot = self._rotation(t)
        out = {rot[0]: "driver"}
        for k, pid in enumerate(rot[1:]):
            out[pid] = "engineer" if k == 0 and len(rot) >= 4 else "crew"
        return out

    def _open_stop(self, t: dict, s: float) -> None:
        car = t["car"]
        dmg = bool(car["eng"] or car["wing"] or car["wheel"])
        tasks: dict = {"tyres": {"order": self.rng.sample(range(4), 4), "from": car["tyre"]},
                       "fuel": {"from": round(car["fuel"], 1), "rate": FILL_RATE, "green": list(GREEN)}}
        if dmg:
            if self.rng.random() < 0.5:
                tasks["repair"] = {"kind": "cables", "perm": self.rng.sample(range(4), 4)}
            else:
                tasks["repair"] = {"kind": "screws", "rot": [self.rng.choice((1, 2, 3, 5, 6, 7)) for _ in range(3)]}   # 45° steps; straight: 0° or 180°
        stop = {"t": round(s + DT, 2), "n": len(t["pits"]) + 1, "tasks": tasks, "who": {}, "done": {}, "pen": 0.0, "busy": {},
                "end": None, "dmg": dmg}
        # the driver: change (default) or stay for a second stint in a row
        rot = self._rotation(t)
        nxt = t["driver"]
        if len(rot) > 1 and not t["bot"] and not (car.get("boxed") == 2 and t["streak"] < STINT_MAX):
            for pid in rot[1:]:
                if self.seen_ok(pid, STALE):
                    nxt = pid
                    break
        stop["next"], stop["change"] = nxt, nxt != t["driver"]
        if t["bot"]:
            self._bot_jobs(t, stop, self.person(t["driver"]).get("level", "normal"), s)
        else:
            roles = self.roles(t)
            crew = [p for p in rot[1:] if roles[p] == "crew" and self.seen_ok(p, STALE)]
            if not crew:
                crew = [p for p in rot[1:] if self.seen_ok(p, STALE)]
            if not crew and self.seen_ok(t["driver"], STALE) and not t["auto"]:
                crew = [t["driver"]]
            jobs = list(tasks)
            if not crew:                                 # nobody there: the garage does it (a bit slower)
                self._bot_jobs(t, stop, "easy", s, extra=3.0)
            else:
                for i, job in enumerate(jobs):
                    stop["who"][job] = crew[min(i, len(crew) - 1)] if len(crew) >= 3 else crew[0] if len(crew) == 1 else crew[0 if job == "tyres" else 1]
        t["stop"] = stop
        self._stop_end(t)

    def _bot_jobs(self, t: dict, stop: dict, level: str, s: float, extra: float = 0.0) -> None:
        _, _, ty, fu, rp = BOT_SKILL.get(level, BOT_SKILL["normal"])
        rain_soon = any(a - 45 <= s < b for a, b in self.st["rain"])
        base = stop["t"] + 1.0 + extra
        stop["done"]["tyres"] = {"at": round(base + self.rng.uniform(*ty), 2), "tyre": "r" if rain_soon else "s", "loose": []}
        stop["done"]["fuel"] = {"at": round(base + self.rng.uniform(*fu), 2), "level": round(self.rng.uniform(95, 100), 1), "spill": False}
        if "repair" in stop["tasks"]:
            stop["done"]["repair"] = {"at": round(base + self.rng.uniform(*rp), 2)}
        for job in stop["tasks"]:
            stop["who"][job] = "bot"

    def _stop_end(self, t: dict) -> None:
        stop = t["stop"]
        if not stop or stop["end"] is not None or any(job not in stop["done"] for job in stop["tasks"]):
            return
        end = max(d["at"] for d in stop["done"].values()) + stop["pen"]
        if stop["change"]:
            end = max(end, stop["t"] + CHANGE_T)
        stop["end"] = round(end, 2)

    def _garage(self, t: dict, s: float) -> None:
        """Jobs nobody did in time: the garage does them."""
        stop = t["stop"]
        if not stop or stop["end"] is not None or s < stop["t"] + PIT_TASK_MAX:
            return
        at = round(stop["t"] + PIT_TASK_MAX, 2)
        for job in stop["tasks"]:
            if job not in stop["done"]:
                stop["done"][job] = {"at": at, "tyre": stop["tasks"]["tyres"]["from"], "loose": []} if job == "tyres" else \
                    {"at": at, "level": 80.0, "spill": False} if job == "fuel" else {"at": at}
                stop["done"][job]["garage"] = True
        self._stop_end(t)

    def _release(self, t: dict) -> None:
        car, stop = t["car"], t["stop"]
        ty, fu = stop["done"]["tyres"], stop["done"]["fuel"]
        car.update(pit=0, v=0.0, wear=0.0, tyre=ty["tyre"], fuel=max(car["fuel"], fu["level"]), slow=0.0, box=0, boxed=0,
                   loose=(car["d"] + L * 0.5) if ty["loose"] else -1.0)
        if "repair" in stop["done"]:
            car.update(eng=0, wing=0, wheel=0)
        car["temp"] = min(car["temp"], 70.0)
        took = round(stop["end"] - stop["t"], 1)
        t["pits"].append({"n": stop["n"], "time": took, "change": stop["change"], "who": dict(stop["who"]), "loose": bool(ty["loose"]),
                          "spill": bool(fu.get("spill")), "at": stop["t"]})
        if t["best_pit"] is None or took < t["best_pit"]:
            t["best_pit"] = took
        if stop["change"]:
            t["driver"], t["streak"] = stop["next"], 1
        else:
            t["streak"] += 1
        t["stints"][t["driver"]] = t["stints"].get(t["driver"], 0) + 1
        t["ev"] = []
        t["stop"] = None

    # ---------- the clock: everything up to SETTLE seconds ago
    def tick(self) -> None:
        if self.st.get("phase") != "play":
            return
        now_t = self.gt()
        lim = self.limit()
        horizon = min(now_t - SETTLE, lim)
        seed, jr = self.st["seed"], self.jr()
        for t in self.st["teams"]:                       # who drives: the app, or the autopilot when it is silent
            t["auto"] = not t["bot"] and not self.seen_ok(t["driver"], AUTO_AFTER) and now_t > 0
        steps = 0
        while (self.st["k"] + 1) / 10 <= horizon + 1e-9 and steps < 30000:
            s = self.st["k"] / 10
            rain, sc = in_window(self.st["rain"], s), in_window(self.st["sc"], s)
            for t in self.st["teams"]:
                car = t["car"]
                if car["out"] is not None:
                    continue
                if car["pit"]:
                    self._garage(t, s)
                    if t["stop"] and t["stop"]["end"] is not None and s + 1e-9 >= t["stop"]["end"]:
                        self._release(t)
                if t["bot"] or t["auto"]:
                    self._drive(t, s, rain, sc)
                else:
                    while t["ev"] and t["ev"][0][0] <= s + 1e-9:
                        _, c, v = t["ev"].pop(0)
                        apply_input(car, c, v)
                for e in step(car, s, seed, jr, rain, sc):
                    if e == "pit":
                        self._open_stop(t, s)
                    elif e in ("blow", "retired", "bigcrash"):
                        self._safety_car(s + DT)
                        self.st["log"].append([round(s + DT, 1), e, t["num"]])
                    del self.st["log"][:-30]
            self.st["k"] += 1
            steps += 1
        self._maybe_end(horizon)

    def _safety_car(self, s: float) -> None:
        sc = self.st["sc"]
        lim = self.limit()
        if len(sc) >= (2 if lim <= 600 else 3) or s > lim - 60 or in_window(sc, s) or (sc and s - sc[-1][1] < SC_GAP):
            return
        sc.append([round(s, 1), round(s + SC_LEN, 1)])

    def _drive(self, t: dict, s: float, rain: bool, sc: bool) -> None:
        """The bot driver (also the autopilot of a silent app): dodge, manage the engine, box sensibly."""
        car = t["car"]
        if car["pit"]:
            return
        level = self.person(t["driver"]).get("level", "normal") if t["bot"] else "normal"
        miss, push, *_ = BOT_SKILL.get(level, BOT_SKILL["normal"])
        jr = self.jr()
        # dodge: what is ahead in my lane
        look = car["v"] * 1.4 + 18
        ahead = []
        lap, ob = car["olap"], car["ob"]
        for k in range(2):
            things = lap_things(self.st["seed"], lap + k, jr)
            for i in range(ob if k == 0 else 0, len(things)):
                x, lane, kind = things[i]
                dz = (lap + k) * L + x - car["d"]
                if 0 < dz <= look:
                    key = f"{lap + k}:{i}"
                    if key not in t["bm"]:
                        t["bm"].append(key)
                        del t["bm"][:-20]
                        if self.rng.random() < miss:
                            t["bm"].append("x" + key)
                    if "x" + key not in t["bm"]:
                        ahead.append((dz, lane))
        if not sc and s - t["blc"] >= 0.3:
            blocked = {lane for _, lane in ahead}
            if car["lane"] in blocked:
                free = [ln for ln in (car["lane"] - 1, car["lane"] + 1) if 0 <= ln <= 2 and ln not in blocked]
                far = [ln for ln in range(3) if ln not in blocked]
                goal = free[0] if free else (far[0] if far else car["lane"])
                if goal != car["lane"]:
                    car["lane"] += 1 if goal > car["lane"] else -1
                    t["blc"] = s
        # the engine: push, lift when hot
        hot_at = {"easy": (89.0, 74.0, 5), "normal": (84.0, 74.0, 6), "hard": (87.0, 81.0, 7)}.get(level, (84.0, 74.0, 6))
        if car["temp"] >= hot_at[0]:
            t["hot"] = 1
        elif car["temp"] <= hot_at[1]:
            t["hot"] = 0
        car["thr"] = 6 if sc else (hot_at[2] if t["hot"] else int(push))
        # box: fuel, tyres, damage, the weather, a cheap stop under the safety car
        per_lap = L * FUEL_M * (0.55 + 0.045 * 10)
        rain_soon = any(a - 30 <= s < b for a, b in self.st["rain"])
        if car["fuel"] < per_lap * 1.25 or car["wear"] > 82 or car["wing"] or (rain and car["tyre"] == "s" and t["bot"]) \
                or (not rain_soon and car["tyre"] == "r") or (sc and car["fuel"] < 55) or car["eng"] or car["wheel"]:
            car["box"] = 1

    # ---------- the end
    def _maybe_end(self, horizon: float) -> None:
        if self.st.get("phase") != "play":
            return
        humans = [t for t in self.st["teams"] if not t["bot"]]
        if horizon >= self.limit() and self.st["k"] / 10 >= self.limit() - 1e-9:
            self.st["complete"] = True
            self._finish()
        elif humans and all(t["car"]["out"] is not None for t in humans):     # every team of people retired
            self.st["complete"] = True
            self._finish()

    def standings(self) -> list[int]:
        """Team indexes by laps, then distance (a retired car keeps its laps)."""
        ts = self.st["teams"]
        return sorted(range(len(ts)), key=lambda i: (-laps_of(ts[i]["car"]["d"]), -ts[i]["car"]["d"], ts[i]["grid"]))

    def _finish(self) -> None:
        order = self.standings()
        ts = self.st["teams"]
        pl, n = {}, 0
        prev = None
        for k, i in enumerate(order):
            key = (laps_of(ts[i]["car"]["d"]), round(ts[i]["car"]["d"], 1))
            if key != prev:
                n = k + 1
                prev = key
            pl[i] = n
        for i, t in enumerate(ts):
            t["place"] = pl[i]
        self.st["places"] = {p["id"]: pl[p["team"]] for p in self.st["players"]}
        self.st["ranking"] = order
        self.st["end_t"] = round(self.st["k"] / 10, 2)
        self.st.update(phase="done", finished=self.now())

    def end(self) -> None:
        if self.st.get("phase") == "play":
            self._finish()


# ================================================================ the games in the database (table card_game, kind "langstrecke")
class Langstrecke(CardGames):
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
        return {**self.default_rules(), "rewards": rewards_of(self.db), "max_players": MAX_PLAYERS, "circuit": CIRCUIT}

    def set_defaults(self, rules: dict) -> dict:
        """Parent area: the defaults (duration, weather, difficulty, team size)."""
        r = self.clean_rules(KIND, {**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
        self.db.set_setting(f"game_rules.{KIND}", r)
        return r

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
        out["bots"] = max(0, min(5, out["bots"]))
        out["level"] = out["level"] if out["level"] in LEVELS else "normal"
        out["minutes"] = out["minutes"] if out["minutes"] in MINUTES else 15
        out["weather"] = 1 if out["weather"] else 0
        out["difficulty"] = out["difficulty"] if out["difficulty"] in DIFFS else "normal"
        out["team_size"] = max(1, min(5, out["team_size"]))
        out["teams"] = max(1, min(4, out["teams"]))
        return out

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role, color FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        if p and p["color"]:
            out["color"] = p["color"]
        return out

    def best(self, pid) -> dict:
        return {"laps": int((self.db.get_setting("langstrecke_best") or {}).get(str(pid), 0) or 0),
                "pit": int((self.db.get_setting("langstrecke_pit") or {}).get(str(pid), 0) or 0)}

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status != "done" or st.get("paid") or st.get("places") is None:
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        best = dict(self.db.get_setting("langstrecke_best") or {})
        pits = dict(self.db.get_setting("langstrecke_pit") or {})
        records: dict = {}
        family = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        for p in family:
            t = st["teams"][p["team"]]
            laps = laps_of(t["car"]["d"])
            rec = {}
            if laps > int(best.get(p["id"], 0) or 0):
                best[p["id"]] = laps
                rec["laps"] = True
            if t.get("best_pit") and st.get("complete"):
                tenths = int(round(t["best_pit"] * 10))
                if tenths > 0 and (not pits.get(p["id"]) or tenths < int(pits[p["id"]])):
                    pits[p["id"]] = tenths
                    rec["pit"] = True
            if rec:
                records[p["id"]] = rec
        self.db.set_setting("langstrecke_best", best)
        self.db.set_setting("langstrecke_pit", pits)
        st["records"] = records
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", f"{TITLE} – Platz {st['places'][pid]}", ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        if len(st["teams"]) >= 2 and st.get("complete"):
            self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history:
            for p in family:
                t = st["teams"][p["team"]]
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["teams"]), "laps": laps_of(t["car"]["d"]),
                        "team": t["name"], "num": t["num"], "best_pit": t.get("best_pit"), "stints": t["stints"].get(p["id"], 0),
                        "retired": t["car"]["out"] is not None, "record": bool(records.get(p["id"])), "complete": bool(st.get("complete")),
                        "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins per person: by the team's place 1–3, only people of the family, only with at least two of them at a family
        table, only for a race run to the end."""
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
        if need > 0 and self.bots_off(KIND, st["players"]):
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
        nteams = len({int(p.get("team", 0)) for p in humans})
        n = max(0, min(st["rules"]["bots"], 8 - nteams))
        if not st.get("solo") and nteams + n < 2:
            n = 2 - nteams                                # a race needs two cars at least
        bots = self._bots(st, n)
        if not st.get("solo") and nteams + len(bots) < 2:
            raise CommunityError("At least two cars are needed – split up into two teams or add bot teams")
        st["players"] = humans + bots
        st.pop("bot_pool", None)
        self.table(st).setup()

    def _seat(self, st: dict, p: dict) -> None:
        """A new player: into the team with the fewest people (that still has room)."""
        r = st["rules"]
        n = 1 if st.get("solo") else r["teams"]
        counts = [sum(1 for q in st["players"] if not q.get("bot") and q.get("team") == i) for i in range(n)]
        free = [i for i in range(n) if counts[i] < r["team_size"]]
        if not free:
            raise CommunityError("The table is full")
        p["team"] = min(free, key=lambda i: (counts[i], i))

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
            st = {"kind": KIND, "rules": r, "players": [], "phase": "lobby", "solo": solo, "bot_pool": list(bots or [])}
            me = self._person(host)
            self._seat(st, me)
            st["players"].append(me)
            gid = self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, int(solo), json.dumps(st))
            if solo:                                      # alone: the intro starts right away
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
            if len([p for p in st["players"] if not p.get("bot")]) >= MAX_PLAYERS:
                raise CommunityError("The table is full")
            p = self._person(pid)
            self._seat(st, p)
            st["players"].append(p)
            self._save(row, st)

    def choose_team(self, pid: int, team: int) -> None:
        """In the lobby: sit down in another team (if it has room)."""
        with self.lock:
            row = self._row(KIND, pid)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            p = next((x for x in st["players"] if x["id"] == str(pid)), None)
            if not p:
                raise CommunityError("You are not at this table")
            r = st["rules"]
            n = 1 if st.get("solo") else r["teams"]
            if not 0 <= int(team) < n:
                raise CommunityError("Unknown team")
            if p.get("team") != int(team) and sum(1 for q in st["players"] if q.get("team") == int(team)) >= r["team_size"]:
                raise CommunityError("This team is full")
            p["team"] = int(team)
            self._save(row, st)

    def shuffle(self, viewer: int) -> None:
        """Who leads mixes the teams (as even as possible)."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            people = [p for p in st["players"] if not p.get("bot")]
            random.shuffle(people)
            n = 1 if st.get("solo") else st["rules"]["teams"]
            for i, p in enumerate(people):
                p["team"] = i % n
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

    def _with_play(self, pid: int, fn):
        with self.lock:
            row = self._row(KIND, pid)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            out = None
            if st["phase"] == "play":
                t_ = self.table(st)
                t_.tick()
                if st["phase"] == "play":
                    out = fn(t_, st)
                self._save(row, st)
            return out

    def report(self, pid: int, inputs=()) -> dict | None:
        """The app of a player: its inputs (only the driver's count) – answers with the state."""
        taken = 0
        with self.lock:
            row = self._row(KIND, pid)
            if row:
                st = json.loads(row["state"])
                if st["phase"] == "lobby":
                    raise CommunityError("The game has not started yet")
                if st["phase"] == "play":
                    t_ = self.table(st)
                    if any(p["id"] == str(pid) for p in st["players"]):
                        st["seen"][str(pid)] = self.now()
                        taken = t_.report(str(pid), inputs)
                    t_.tick()
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
        if not row:
            return self.state(KIND, pid)
        return {**self._view(row, st, str(pid)), "taken": taken}

    def radio(self, pid: int, msg: str) -> None:
        self._with_play(pid, lambda t, st: t.radio(str(pid), msg))

    def pit_job(self, pid: int, task: str, data: dict) -> dict:
        return self._with_play(pid, lambda t, st: t.pit_job(str(pid), task, data)) or {"ok": False}

    def end(self, kind: str, viewer: int) -> None:
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
                    k = st["k"]
                    self.table(st).tick()
                    if st["k"] != k or st["phase"] != "play":
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
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                    "guest": bool(p.get("guest")), "color": p.get("color"), "level": p.get("level"), "team": p.get("team", 0)}
                   for p in st["players"]]
        base = {"game": row["id"], "kind": KIND, "title": TITLE, "circuit": CIRCUIT, "status": row["status"], "phase": ph,
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "joined": joined, "players": players,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2, "max_players": MAX_PLAYERS,
                "best": self.best(me) if joined else None, "now": self.now()}
        if st["phase"] == "lobby":
            nb = max(0, min(st["rules"]["bots"], 8))
            return {**base, "bots": nb, "nteams": 1 if st.get("solo") else st["rules"]["teams"]}
        t_ = self.table(st)
        mine = t_.team_of(me) if joined else None
        coins, recs = st.get("coins") or {}, st.get("records") or {}
        teams = []
        lead = max((t["car"]["d"] for t in st["teams"]), default=0)
        for i, t in enumerate(st["teams"]):
            car = t["car"]
            tv = {"i": i, "name": t["name"], "color": t["color"], "num": t["num"], "members": t["members"], "bot": t["bot"],
                  "driver": t["driver"], "laps": laps_of(car["d"]), "d": round(car["d"], 2), "v": round(car["v"], 2), "lane": car["lane"],
                  "pit": car["pit"], "out": car["out"], "stops": len(t["pits"]), "best_pit": t["best_pit"], "best_lap": car["best"],
                  "gap": round(lead - car["d"], 1), "auto": t["auto"], "place": t.get("place"), "grid": t["grid"],
                  "dmg": [k for k in ("eng", "wing", "wheel") if car[k]]}
            if t is mine or ph == "done":
                tv.update(car=car, roles=t_.roles(t), stints=t["stints"], streak=t["streak"], pits=t["pits"],
                          radio=t["radio"], ev=t["ev"] if t is mine else [])
                if t["stop"]:
                    stop = t["stop"]
                    tv["stop"] = {k: stop[k] for k in ("t", "n", "tasks", "who", "done", "pen", "end", "next", "change", "dmg")}
            teams.append(tv)
        players_out = []
        for p in players:
            p = dict(p)
            p["place"] = (st.get("places") or {}).get(p["id"])
            p["coins"] = coins.get(p["id"], 0)
            p["record"] = recs.get(p["id"]) or None
            players_out.append(p)
        return {**base, "players": players_out, "me": me if joined else None, "seed": st["seed"], "t0": st["t0"], "limit": t_.limit(),
                "k": st["k"], "rain": st["rain"], "sc": st["sc"], "teams": teams, "my_team": mine and st["teams"].index(mine),
                "standings": t_.standings(), "log": st.get("log", [])[-6:], "end_t": st.get("end_t"), "ranking": st.get("ranking"),
                "complete": bool(st.get("complete")), "now_t": t_.gt() if ph == "play" else st.get("end_t")}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
