"""«24h Endurance» (24-Stunden-Rennen) – a short, fast live team race on the fictional «Circuit des Tannes».

Teams are racing stables (a colour, a name, a start number), each with ONE car. The family splits into 1–4 teams at
the table (guests via QR code join a team too); bots bring extra cars – alone against bot teams works too. The tables
live in the `card_game` table with kind "langstrecke" (lobby, join, summary, may_lead from cardgames.CardGames).

24 race hours are compressed into 5 / 8 / 12 real minutes (rule `minutes`, default 8): the race clock starts at 15:00
and runs through the night into the next afternoon. Winner: the most laps (then the longer distance). In the lobby each
team chooses its colour (from the palette, unique), its country (a flag on the car) and its car number (1–99, unique).

Weather (rule `weather`, on by default): sudden showers (30–55 s, every 1–2 minutes, planned at the start, everybody
sees the forecast). Slicks in the rain and rain tyres in the dry are slower (grip WET_SLICK / DRY_RAIN); the crew picks
the tyres for the next lap. The lap has two chicanes: at each gate a kerb covers a lane (in the rain or at night also
the middle lane) – touching it slows the car down for a moment. Other cars are not obstacles (no collisions between
cars); the app draws a car close to mine in my lane moving over to a free lane while it overtakes.

The loop – one short lap (about 20–30 s), then the car drives into the pits by itself, every time:
- the driver (one person of the team) steers on three lanes (swipe / arrow keys) round a few things on the track and
  holds the throttle for full speed. Full throttle heats the engine; at RED it overheats: the car limps on to the pits
  and the engine has to be swapped there.
- the car is electric: its battery (0–100 %) drains by the metre, much faster at full throttle (E_FULL) than lifted
  (E_LIFT); braking gives a little back (REGEN). Empty: the emergency drive mode – the car crawls (VEMERG) to the pits.
- every team has exactly TWO batteries: the one in the car and ONE spare. At every stop they are swapped (BAT_SWAP
  seconds): the spare goes into the car with WHATEVER charge it has, the used one comes out and waits in the pits. It
  charges only while it is plugged in: CHARGE_RATE % per second from the moment the crew plugged it in (the server's
  time – never the app's number). Plugged in late (other jobs first): not full at the next stop, the next driver has
  to save energy.
- everybody else of the team is the pit crew: during the lap they prepare the stop on their phones – plug the spare
  battery in, lay out the 4 tyres (slicks or rain tyres, tap the 4 spots) and, only after an overheat, prepare the
  spare engine (hold). The server keeps the times of all of it.
- the stop: STOP_BASE seconds + the battery swap BAT_SWAP + a penalty for tyres not ready when the car arrived
  (PEN_PREP), the engine swap ENG_READY prepared or ENG_SWAP not. Shown as a stopwatch to the whole team.
- at EVERY stop the driver changes: the next person of the team (in turn) drives, the driver joins the crew. A team of
  two takes turns; a team of one (or a team whose crew is all offline) gets the garage: a fixed GARAGE seconds (+ the
  swap), and the garage plugs the spare in only GARAGE_PLUG seconds after the stop (fair, not perfect).

The server decides everything (the same step function runs in web/langstrecke.js for a smooth picture of the own
car): the driver's app only reports its inputs (lane, throttle) with their game time; the server simulates all cars
in fixed steps of DT seconds SETTLE seconds behind the clock – a late input is applied at the next step (never in the
past). Pit jobs are actions on the server (plug in, a tyre on a spot, start / stop holding) timed with the server's
clock: a job counts only if it was finished before the car arrived. A driver whose app is silent for AUTO_AFTER seconds
gets the autopilot until the app is back. Bots drive by the same rules (they lift off when the battery runs low), plug
their spare in first and prepare their stops (easier bots miss more).

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
from .running import win_reason
from .pairhunt import rewards_of as _rewards_of

KIND = "langstrecke"
TITLE = "24h Endurance"
EMOJI = "🏎️"
CIRCUIT = "Circuit des Tannes"
MAX_PLAYERS = 12
LEVELS = ("easy", "normal", "hard")
DIFFS = ("junior", "normal")
MINUTES = (5, 8, 12)
DEFAULTS = {"bots": 2, "level": "normal", "minutes": 8, "weather": 1, "difficulty": "normal", "team_size": 3, "teams": 2}
# the countries a team can race for (ISO codes; names and groups in web/langstrecke.js) – or none
COUNTRIES = ("BE", "BG", "DK", "DE", "FI", "FR", "GR", "GB", "IE", "IT", "LV", "LI", "LU", "MC", "NL", "NO", "AT", "PL", "PT", "RO",
             "RU", "SM", "SE", "CH", "SK", "SI", "ES", "CZ", "TR", "HU", "BY",
             "AR", "BO", "BR", "CL", "DO", "EC", "GT", "CA", "CO", "CU", "MX", "PA", "PR", "KN", "US", "VE",
             "CN", "HK", "IN", "ID", "JP", "QA", "MY", "OM", "SA", "SG", "KR", "SY", "TW", "TH", "AE",
             "AU", "MA", "NZ", "ZA")

# ---------------------------------------------------------------- the car (the same numbers in web/langstrecke.js)
L = 640.0                    # metres per lap: about 22 s at full throttle, 32 s lifted
DT = 0.1                     # one step of the simulation (seconds)
VLIFT, VFULL = 20.0, 30.0    # m/s lifted / full throttle (shown as km/h × 7)
ACC, BRAKE, COAST = 7.0, 14.0, 5.0   # m/s²: speeding up, braking (the brake), slowing down by lifting off
VBRAKE = 8.0                 # holding the brake slows down towards this
VLIMP, VSLOW = 13.0, 10.0    # with an overheated engine / after a hit
SLOW_T = 1.2                 # seconds slow after a hit
HEAT, HEAT_JR = 2.6, 1.7     # °/s at full throttle
COOL = 4.0                   # °/s lifted
TMIN, YELLOW, RED = 60.0, 85.0, 100.0
OIL, CONES, SLOWCAR = 0, 1, 2
# grip: slicks in the rain / rain tyres in the dry are slower (the right tyres: 1.0)
WET_SLICK, DRY_RAIN = 0.8, 0.9
# two chicanes (S-bends): at each gate a kerb covers a lane (in the rain or at night two) – touching it slows the car
CHICANES = ((210.0, 245.0, 2, 0), (450.0, 485.0, 0, 2))      # gate a, gate b, kerb lane at a, at b
KERB_T, KERB_T_WET = 0.6, 1.0                               # seconds slow after touching a kerb
SAFE, SAFE_TRICKY = 23.0, 18.0                              # m/s at most into a chicane (by day and dry / in the rain or at night)
VOFF, OFF_T = 6.0, 3.0                                      # too fast: off into the gravel – this slow for this long
# the battery (an electric car): % per metre at full throttle / lifted (also limping), % back per m/s braked off
E_FULL, E_LIFT, REGEN = 0.16, 0.07, 0.3
VEMERG = 7.0                 # m/s with an empty battery: the emergency drive mode
COUNTDOWN = 6.0              # seconds from the start to game time 0 (the intro: run to the cars, engines, lights)
SETTLE = 0.8                 # the server simulates this far behind the clock
AHEAD = 0.5                  # inputs may be this much ahead of the server's clock
AUTO_AFTER = 6.0             # a silent driver: the autopilot drives
STALE = 10.0                 # a silent person is not counted as crew / next driver
# ---------------------------------------------------------------- the pit stop
STOP_BASE = 2.0              # every stop (the driver change included)
BAT_SWAP = 1.0               # the battery swap at every stop (a fixed time)
PEN_PREP = 4.0               # tyres not ready
ENG_READY, ENG_SWAP = 2.0, 6.0   # the engine swap: prepared / not prepared
GARAGE = 4.0                 # a team without crew: the garage prepares, a fixed time (+ the swap, + GARAGE_ENG after an overheat)
GARAGE_ENG = 4.0
TYRE_GAP = 0.25              # seconds at least between two tyres of a team
CHARGE_RATE = 4.0            # % per second while the spare battery is plugged in (empty → full in 25 s, about a lap)
GARAGE_PLUG = 8.0            # no crew: the garage plugs the spare in this many seconds after the stop
BOT_PLUG, BOT_PLUG_LATE = 0.5, 8.0   # bots plug in right away – or late (the chance of a missed job)
ENGINE_HOLD = 2.0            # seconds of holding to prepare the spare engine
TEAM_STYLES = (("Comet Racing", "#e03131"), ("Blue Falcon Works", "#1c7ed6"), ("Pine Cone Motors", "#2f9e44"),
               ("Sunrise Speedsters", "#f08c00"), ("Silver Owl Garage", "#7048e8"), ("Night Fox Racing", "#0c8599"),
               ("Thunder Bee Team", "#e8590c"), ("Snow Hare Racing", "#495057"))
NUMBERS = (3, 7, 8, 11, 12, 17, 21, 24, 27, 33, 36, 42, 44, 51, 58, 63, 77, 88, 91, 99)
# missed things, temperature to lift off / to push again, the chance that a job of the crew is not ready
BOT_SKILL = {"easy": (0.25, 92.0, 78.0, 0.35), "normal": (0.12, 93.0, 84.0, 0.15), "hard": (0.04, 96.0, 90.0, 0.05)}


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
        n = 2 if junior else (3 + int(rnd() * 2))
        got = []
        for i in range(n):
            x = free_x((i + 0.15 + 0.7 * rnd()) / n)
            lane = int(rnd() * 3)
            r = rnd()
            kind = OIL if r < 0.35 else CONES if r < 0.7 else SLOWCAR
            got.append([math.floor(x * 10 + 0.5) / 10, lane, kind])
        if len(_THINGS) > 4000:
            _THINGS.clear()
        _THINGS[key] = got
    return got


FREE = ((100.0, 180.0), (285.0, 420.0), (525.0, 600.0))   # the parts of the lap without a chicane: things lie only there


def free_x(u: float) -> float:
    """u in 0…1 along the free parts of the lap → the position in the lap."""
    x = u * sum(b - a for a, b in FREE)
    for a, b in FREE:
        if x <= b - a:
            return a + x
        x -= b - a
    return FREE[-1][1]


def kerbs(tricky: bool) -> list[list]:
    """The chicane gates: [[x in the lap, [kerb lanes]], …] – in the rain or at night the kerb reaches the middle lane."""
    out = []
    for xa, xb, la, lb in CHICANES:
        out.append([xa, [la, 1] if tricky else [la]])
        out.append([xb, [lb, 1] if tricky else [lb]])
    return out


def default_looks(country: str | None = None) -> list[dict]:
    """The lobby: colour, country (the family's own if the app knows it, else none) and car number of the teams of
    people – they can change them."""
    c = country if country in COUNTRIES else None
    return [{"color": TEAM_STYLES[i][1], "country": c, "num": (7, 24, 44, 88)[i]} for i in range(4)]


def new_car(lane: int, d: float) -> dict:
    return {"d": d, "v": 0.0, "lane": lane, "thr": 0, "temp": TMIN, "eng": 0, "slow": 0.0, "olap": 0, "ob": 0,
            "ls": 0.0, "best": 0.0, "pit": 0, "hits": 0, "blows": 0, "tyre": "s", "kerb": 0, "off": 0.0, "offs": 0,
            "bat": 100.0, "flat": 0}


def new_spare(charge: float, t: float, auto: float | None = None) -> dict:
    """The team's ONE spare battery in the pits: its charge when it came out of the car (c0) at game time t, when it was
    plugged in (None: not yet) and when the garage / the bot plugs it in by itself (auto)."""
    return {"c0": charge, "t": t, "plug": None, "auto": auto}


def spare_charge(sp: dict, at: float) -> float:
    """The spare's charge at game time `at` – from the server's timestamps only."""
    if sp["plug"] is None or at <= sp["plug"]:
        return sp["c0"]
    return min(100.0, sp["c0"] + CHARGE_RATE * (at - sp["plug"]))


def apply_input(car: dict, c: str, v) -> None:
    """One input of the driver – the same rules as in the app."""
    if c == "l":
        if not car["pit"]:
            car["lane"] = max(0, car["lane"] - 1)
    elif c == "r":
        if not car["pit"]:
            car["lane"] = min(2, car["lane"] + 1)
    elif c == "u":                                       # 1 full throttle, 0 lifted, -1 braking
        car["thr"] = 1 if int(v) > 0 else -1 if int(v) < 0 else 0


def grip(tyre: str, rain: bool) -> float:
    return (WET_SLICK if tyre != "r" else 1.0) if rain else (DRY_RAIN if tyre == "r" else 1.0)


def step(car: dict, s: float, seed: int, jr: bool, rain: bool = False, dark: bool = False) -> list[str]:
    """One step of DT seconds from game time s – the same in web/langstrecke.js. Answers what happened."""
    ev: list[str] = []
    if car["pit"]:
        car["temp"] = max(TMIN, car["temp"] - COOL * DT)
        return ev
    emg = car["bat"] <= 0                              # the battery is empty: the emergency drive mode
    full = car["thr"] > 0 and not car["eng"] and not emg
    vt = VLIMP if car["eng"] else (VFULL if full else VLIFT) * grip(car["tyre"], rain)
    if emg:
        vt = min(vt, VEMERG)
    dec = COAST
    if car["thr"] < 0:
        vt = min(vt, VBRAKE)
        dec = BRAKE
    if car["slow"] > 0:
        vt = min(vt, VOFF if car.get("off", 0) > 0 else VSLOW)
        dec = BRAKE
        car["slow"] = max(0.0, car["slow"] - DT)
    car["off"] = max(0.0, car.get("off", 0.0) - DT)
    v0 = car["v"]
    v = min(vt, v0 + ACC * DT) if v0 < vt else max(vt, v0 - dec * DT)
    # the battery: by the metre – full throttle much more than lifted; braking gives a little back
    if not emg:
        use = (E_FULL if full else E_LIFT) * v * DT
        if car["thr"] < 0 and v < v0:
            use -= REGEN * (v0 - v)
        car["bat"] = max(0.0, min(100.0, car["bat"] - use))
        if car["bat"] <= 0:
            car["flat"] += 1
            ev.append("empty")
    d0 = car["d"]
    d1 = d0 + v * DT
    # the engine: full throttle heats it, lifting cools it; at RED it overheats (limp to the pits, swap it there)
    if full:
        car["temp"] = min(RED, car["temp"] + (HEAT_JR if jr else HEAT) * DT)
    else:
        car["temp"] = max(TMIN, car["temp"] - COOL * DT)
    if full and car["temp"] >= RED - 1e-9:
        car["eng"] = 1
        car["blows"] += 1
        car["temp"] = 80.0
        ev.append("blow")
    # what lies on the track
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
        if xa <= d0 or lane != car["lane"]:
            continue
        car["slow"] = SLOW_T
        car["hits"] += 1
        v = min(v, VSLOW + 4)
        ev.append("hit")
    # the chicanes: too fast into one – off into the gravel; a kerb at the gate in my lane
    lap0 = math.floor(d0 / L)
    if lap0 >= 0:
        for xa_, _, _, _ in CHICANES:
            xa = lap0 * L + xa_
            if d0 < xa <= d1 and v > (SAFE_TRICKY if rain or dark else SAFE) + 1e-9:
                car["slow"] = max(car["slow"], OFF_T)
                car["off"] = OFF_T
                car["offs"] = car.get("offs", 0) + 1
                v = min(v, VOFF)
                ev.append("off")
        for x, lanes in kerbs(rain or dark):
            xa = lap0 * L + x
            if d0 < xa <= d1 and car["lane"] in lanes:
                car["slow"] = max(car["slow"], KERB_T_WET if rain else KERB_T)
                car["kerb"] += 1
                v = min(v, VSLOW + 6)
                ev.append("kerb")
    # the line: a lap – and into the pits, every time (not at the start)
    n0, n1 = math.floor(d0 / L), math.floor(d1 / L)
    if n1 > n0 and n0 >= 0:
        lt = s + DT - car["ls"]
        car["best"] = round(lt, 2) if not car["best"] or lt < car["best"] else car["best"]
        car["ls"] = round(s + DT, 2)
        d1 = n1 * L
        v = 0.0
        car["pit"] = 1
        ev += ["lap", "pit"]
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


def in_window(wins, s: float) -> bool:
    return any(a <= s < b for a, b in wins or ())


def rain_plan(rng, limit: float) -> list[list[float]]:
    """Frequent, sudden showers: 30–55 s of rain, then 45–90 s dry."""
    out = []
    t = rng.uniform(35, 70)
    while t < limit - 20:
        dur = rng.uniform(30, 55)
        out.append([round(t, 1), round(min(limit, t + dur), 1)])
        t += dur + rng.uniform(45, 90)
    return out


def new_prep() -> dict:
    """The pit crew's jobs for the next stop: tyres on the 4 spots (the server's time of each), the spare engine (held
    seconds, who holds since when, when ready). The spare battery is the team's `spare` (it stays from stop to stop)."""
    return {"tyres": [None, None, None, None], "tyre_t": -99.0, "compound": None, "eng": 0.0, "eng_on": None, "eng_at": None}


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
        return 60.0 * int(self.st["rules"].get("minutes", 8))

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
        looks = self.st.get("looks") or default_looks()
        taken: set[int] = set()
        for i, k in enumerate(sorted(groups)):           # a team keeps the name, colour, country and number of the lobby
            look = looks[k] if k < len(looks) else {}
            num = int(look.get("num") or 0)
            if not 1 <= num <= 99 or num in taken:
                num = next(n for n in NUMBERS if n not in taken)
            taken.add(num)
            teams.append({"name": styles[k % len(styles)][0], "color": look.get("color") or styles[k % len(styles)][1],
                          "country": look.get("country"), "num": num, "members": groups[k], "bot": False})
        nums = self.rng.sample([n for n in NUMBERS if n not in taken], len(bots))
        used = {t["color"] for t in teams}
        free = [st_ for i, st_ in enumerate(styles) if i not in groups and st_[1] not in used] or styles
        for j, b in enumerate(bots):
            name, color = free[j % len(free)]
            teams.append({"name": name, "color": color, "country": self.rng.choice(COUNTRIES), "num": nums[j],
                          "members": [b["id"]], "bot": True})
        if not teams:
            raise CommunityError("Nobody is at the table")
        order = list(range(len(teams)))
        self.rng.shuffle(order)
        for pos, ti in enumerate(order):                 # the grid: two by two, 10 m apart
            t = teams[ti]
            t.update(car=new_car(pos % 3, -5.0 - 10.0 * pos), driver=t["members"][0], drives={t["members"][0]: 1},
                     stop=None, pits=[], best_pit=None, ev=[], auto=False, bm=[], blc=-9.0, hot=0, grid=pos + 1, prep=new_prep(),
                     spare=new_spare(100.0, 0.0))
        for p in players:
            p["team"] = next(i for i, t in enumerate(teams) if p["id"] in t["members"])
        self.st.update(phase="play", seed=seed if seed is not None else self.rng.randrange(1, 2 ** 31), t0=self.now() + COUNTDOWN,
                       k=0, teams=teams, rain=rain_plan(self.rng, self.limit()) if self.st["rules"].get("weather", 1) else [], seen={p["id"]: self.now() for p in humans}, ranking=None, places=None, complete=False,
                       end_t=None, log=[])

    # ---------- what the apps send
    def report(self, pid: str, inputs=()) -> int:
        """The driver's inputs ([game time, "l"|"r"|"u", value]) – only the current driver's count; a late one is
        applied at the next step (never in the past). Answers how many were taken."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        p = self.person(pid)
        if not p or p.get("bot"):
            raise CommunityError("You are not at this table")
        self.st["seen"][pid] = self.now()
        t = self.team_of(pid)
        if not t or t["driver"] != pid:
            return 0
        now_t, sim = self.gt(), self.sim_t()
        taken = 0
        for item in list(inputs)[:40]:
            try:
                te, c = float(item[0]), str(item[1])
                v = int(item[2]) if len(item) > 2 and item[2] is not None else 0
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if c not in ("l", "r", "u") or not math.isfinite(te) or te > now_t + AHEAD:
                continue
            last = t["ev"][-1][0] if t["ev"] else -COUNTDOWN
            te = max(te, sim, last)
            t["ev"].append([round(te, 3), c, v])
            taken += 1
        del t["ev"][:-120]
        return taken

    def crew(self, t: dict) -> list[str]:
        return [m for m in t["members"] if m != t["driver"]]

    def active_crew(self, t: dict) -> list[str]:
        """The crew whose apps are alive (bots have none: their team prepares by itself)."""
        return [p for p in self.crew(t) if self.seen_ok(p, STALE)] if not t["bot"] else []

    def prep(self, pid: str, action: str, spot=None) -> dict:
        """A job of the pit crew during the lap – the server's clock decides (plug the spare battery in, a tyre on a
        spot, start / stop holding the spare engine)."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        t = self.team_of(pid)
        if not t or t["bot"]:
            raise CommunityError("You are not at this table")
        self.st["seen"][pid] = self.now()
        if t["driver"] == pid:
            raise CommunityError("The driver keeps the hands on the wheel")
        if t["car"]["pit"]:
            raise CommunityError("The car is in the pits")
        now_t = math.floor(self.gt() * 1000) / 1000       # stored to the millisecond, never later than now
        pr = t["prep"]
        self._settle(t, now_t)
        if action == "tyre":
            try:
                k = int(spot)
            except (TypeError, ValueError):
                raise CommunityError("Unknown spot") from None
            if not 0 <= k <= 3:
                raise CommunityError("Unknown spot")
            if pr["tyres"][k] is not None:
                return {"ok": True, "again": True}
            if now_t - pr["tyre_t"] < TYRE_GAP:
                raise CommunityError("Too fast")
            pr["tyres"][k] = now_t
            pr["tyre_t"] = now_t
            return {"ok": True, "tyres": sum(1 for x in pr["tyres"] if x is not None)}
        if action in ("slicks", "rain"):
            pr["compound"] = "r" if action == "rain" else "s"
            return {"ok": True, "compound": pr["compound"]}
        if action == "plug":                             # the spare battery onto the charger – from now on it charges
            sp = t["spare"]
            if sp["plug"] is not None:
                return {"ok": True, "again": True, "charge": round(spare_charge(sp, now_t), 1)}
            sp["plug"] = max(now_t, sp["t"])
            return {"ok": True, "charge": round(sp["c0"], 1)}
        if action == "eng_on":
            if not t["car"]["eng"]:
                raise CommunityError("The engine is fine")
            if pr["eng_at"] is not None:
                return {"ok": True, "again": True}
            if pr["eng_on"]:
                if pr["eng_on"][0] != pid:
                    raise CommunityError("Somebody else is on it")
                return {"ok": True, "again": True}
            pr["eng_on"] = [pid, now_t]
            return {"ok": True}
        if action == "eng_off":
            on = pr["eng_on"]
            if not on or on[0] != pid:
                return {"ok": True, "again": True, "held": pr["eng"], "ready": pr["eng_at"] is not None}
            pr["eng_on"] = None
            pr["eng"] = round(min(ENGINE_HOLD, pr["eng"] + max(0.0, now_t - on[1])), 2)
            if pr["eng"] >= ENGINE_HOLD - 1e-9:
                pr["eng_at"] = now_t
            return {"ok": True, "held": pr["eng"], "ready": pr["eng_at"] is not None}
        raise CommunityError("Unknown job")

    def _settle(self, t: dict, now_t: float) -> None:
        """Holding on long enough: the spare engine is ready."""
        pr = t["prep"]
        on = pr["eng_on"]
        if on and pr["eng"] + now_t - on[1] >= ENGINE_HOLD:
            at = round(on[1] + ENGINE_HOLD - pr["eng"], 3)
            pr.update(eng=ENGINE_HOLD, eng_on=None, eng_at=at)

    def ready(self, t: dict, at: float) -> dict:
        """Which jobs were finished by game time `at`."""
        pr = t["prep"]
        ty = pr["tyres"]
        eng_at = pr["eng_at"]
        if eng_at is None and pr["eng_on"]:
            eng_at = pr["eng_on"][1] + ENGINE_HOLD - pr["eng"]
        return {"tyres": all(x is not None and x <= at + 1e-9 for x in ty),
                "battery": spare_charge(t["spare"], at) >= 100.0 - 1e-9,
                "engine": eng_at is not None and eng_at <= at + 1e-9}

    # ---------- the pit stop
    def next_driver(self, t: dict) -> str:
        """The next person of the team in turn (who is online); alone: the same."""
        m = t["members"]
        i = m.index(t["driver"]) if t["driver"] in m else 0
        for k in range(1, len(m)):
            pid = m[(i + k) % len(m)]
            if self.seen_ok(pid, STALE):
                return pid
        return t["driver"]

    def _open_stop(self, t: dict, s: float) -> None:
        car = t["car"]
        at = round(s + DT, 2)
        eng = bool(car["eng"])
        crew = self.active_crew(t)
        parts: list[list] = []
        garage = False
        # the battery swap (every stop, a fixed time): the spare goes in with the charge it has right now
        bat_in = round(spare_charge(t["spare"], at), 2)
        swap = ["battery", BAT_SWAP, bat_in >= 100.0 - 1e-9]
        if t["bot"]:
            miss = BOT_SKILL.get(self.person(t["driver"]).get("level", "normal"), BOT_SKILL["normal"])[3]
            parts += [["base", STOP_BASE, True], swap]
            ok = self.rng.random() >= miss
            parts.append(["tyres", 0.0 if ok else PEN_PREP, ok])
            if eng:
                ok = self.rng.random() >= miss
                parts.append(["engine", ENG_READY if ok else ENG_SWAP, ok])
        elif not crew:                                   # alone (or the crew is offline): the garage, a fixed time
            garage = True
            parts += [["garage", GARAGE, True], swap]
            if eng:
                parts.append(["engine", GARAGE_ENG, False])
        else:
            self._settle(t, at)
            rd = self.ready(t, at)
            parts += [["base", STOP_BASE, True], swap]
            parts.append(["tyres", 0.0 if rd["tyres"] else PEN_PREP, rd["tyres"]])
            if eng:
                parts.append(["engine", ENG_READY if rd["engine"] else ENG_SWAP, rd["engine"]])
        took = round(sum(p[1] for p in parts), 1)
        # the tyres for the next lap: the crew's choice (the garage and the bots look at the forecast)
        wet_soon = self.wet_soon(at + took)
        if t["bot"]:
            tyre = ("r" if wet_soon else "s") if self.rng.random() >= miss else ("s" if wet_soon else "r")
        elif garage:
            tyre = "r" if wet_soon else "s"
        else:
            tyre = t["prep"]["compound"] or car["tyre"]
        nxt = self.next_driver(t)
        t["stop"] = {"t": at, "end": round(at + took, 2), "time": took, "n": len(t["pits"]) + 1, "parts": parts,
                     "prev": t["driver"], "next": nxt, "change": nxt != t["driver"], "garage": garage, "eng": eng, "tyre": tyre,
                     "bat_in": bat_in, "bat_out": round(car["bat"], 2)}

    def wet_soon(self, s: float) -> bool:
        """The forecast for the next lap: rain at about the middle of it."""
        return in_window(self.st.get("rain"), s + 12.0)

    def _release(self, t: dict) -> None:
        car, stop = t["car"], t["stop"]
        car.update(pit=0, v=0.0, eng=0, slow=0.0, temp=min(car["temp"], 70.0), tyre=stop["tyre"], bat=stop["bat_in"])
        # the used battery comes out and waits in the pits for the charger: a bot plugs it in right away (or late, like
        # a missed job), the garage after GARAGE_PLUG seconds when nobody of the crew is there
        if t["bot"]:
            miss = BOT_SKILL.get(self.person(t["driver"]).get("level", "normal"), BOT_SKILL["normal"])[3]
            auto = stop["end"] + (BOT_PLUG if self.rng.random() >= miss else BOT_PLUG_LATE)
        else:
            auto = stop["end"] + GARAGE_PLUG
        t["spare"] = new_spare(stop["bat_out"], stop["end"], round(auto, 2))
        if not t["bot"]:
            car["thr"] = 0                               # the new driver presses the pedal again
        t["pits"].append({"n": stop["n"], "time": stop["time"], "change": stop["change"], "garage": stop["garage"],
                          "eng": stop["eng"], "at": stop["t"], "driver": stop["prev"]})
        if not stop["garage"] and (t["best_pit"] is None or stop["time"] < t["best_pit"]):
            t["best_pit"] = stop["time"]
        t["driver"] = stop["next"]
        t["drives"][t["driver"]] = t["drives"].get(t["driver"], 0) + 1
        t["ev"] = []
        t["stop"] = None
        t["prep"] = new_prep()

    # ---------- the clock: everything up to SETTLE seconds ago
    def tick(self) -> None:
        if self.st.get("phase") != "play":
            return
        now_t = self.gt()
        lim = self.limit()
        horizon = min(now_t - SETTLE, lim)
        seed, jr = self.st["seed"], self.jr()
        for t in self.st["teams"]:                       # who drives: the app, or the autopilot when it is silent
            was = t["auto"]
            t["auto"] = not t["bot"] and not self.seen_ok(t["driver"], AUTO_AFTER) and now_t > 0
            if was and not t["auto"]:
                t["car"]["thr"] = 0                      # back in the app: the pedal is released until pressed again
        steps = 0
        while (self.st["k"] + 1) / 10 <= horizon + 1e-9 and steps < 30000:
            s = self.st["k"] / 10
            rain, dark = in_window(self.st.get("rain"), s), darkness(s, lim) > 0.5
            for t in self.st["teams"]:
                car = t["car"]
                if car["pit"] and t["stop"] and s + 1e-9 >= t["stop"]["end"]:
                    self._release(t)
                sp = t["spare"]
                if sp["plug"] is None and sp["auto"] is not None and s + 1e-9 >= sp["auto"] and not car["pit"] and not self.active_crew(t):
                    sp["plug"] = round(max(sp["auto"], s), 2)  # the garage / the bot plugs the spare in
                if t["bot"] or t["auto"]:
                    self._drive(t, s)
                else:
                    while t["ev"] and t["ev"][0][0] <= s + 1e-9:
                        _, c, v = t["ev"].pop(0)
                        apply_input(car, c, v)
                for e in step(car, s, seed, jr, rain, dark):
                    if e == "pit":
                        self._open_stop(t, s)
                    elif e == "blow":
                        self.st["log"].append([round(s + DT, 1), e, t["num"]])
                        del self.st["log"][:-30]
            self.st["k"] += 1
            steps += 1
        for t in self.st["teams"]:
            if not t["car"]["pit"]:
                self._settle(t, now_t)
        self._maybe_end(horizon)

    def _drive(self, t: dict, s: float) -> None:
        """The bot driver (also the autopilot of a silent app): dodge, push, lift off when hot."""
        car = t["car"]
        if car["pit"]:
            return
        level = self.person(t["driver"]).get("level", "normal") if t["bot"] else "normal"
        miss, hot_hi, hot_lo, _ = BOT_SKILL.get(level, BOT_SKILL["normal"])
        jr = self.jr()
        look = car["v"] * 1.4 + 14
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
        lap0 = math.floor(car["d"] / L)
        tricky = in_window(self.st.get("rain"), s) or in_window(self.st.get("rain"), s + 3.0) or darkness(s + 3.0, self.limit()) > 0.5 or darkness(s, self.limit()) > 0.5
        for k in range(2):
            for x, lanes in kerbs(tricky):
                dz = (lap0 + k) * L + x - car["d"]
                if 0 < dz <= look:
                    ahead += [(dz, ln) for ln in lanes]
        if s - t["blc"] >= 0.3 and ahead:
            near = min(ahead)[0]
            blocked = {lane for dz, lane in ahead if dz <= near + 20}
            if car["lane"] in blocked:
                free = [ln for ln in (car["lane"] - 1, car["lane"] + 1) if 0 <= ln <= 2 and ln not in blocked]
                far = [ln for ln in range(3) if ln not in blocked]
                goal = free[0] if free else (far[0] if far else car["lane"])
                if goal != car["lane"]:
                    car["lane"] += 1 if goal > car["lane"] else -1
                    t["blc"] = s
        if car["temp"] >= hot_hi:
            t["hot"] = 1
        elif car["temp"] <= hot_lo:
            t["hot"] = 0
        car["thr"] = 0 if t["hot"] else 1
        # the battery: flat out only while it lasts to the pits, else lift off (economical)
        left = (math.floor(car["d"] / L) + 1) * L - car["d"]
        if car["bat"] < left * E_FULL + 2.0:
            car["thr"] = 0
        # brake in time before a chicane (down to a little below the safe speed)
        safe = (SAFE_TRICKY if tricky else SAFE) - {"easy": 2.5, "normal": 1.5, "hard": 0.8}.get(level, 1.5)
        for k in range(2):
            for xa_, _, _, _ in CHICANES:
                dz = (lap0 + k) * L + xa_ - car["d"]
                if 0 < dz <= 160 and car["v"] > safe and dz <= (car["v"] ** 2 - safe ** 2) / (2 * BRAKE) + car["v"] * 0.4 + 4:
                    car["thr"] = -1

    # ---------- the end
    def _maybe_end(self, horizon: float) -> None:
        if self.st.get("phase") != "play":
            return
        if horizon >= self.limit() and self.st["k"] / 10 >= self.limit() - 1e-9:
            self.st["complete"] = True
            self._finish()

    def standings(self) -> list[int]:
        """Team indexes by laps, then distance, then who crossed the line first (two cars in the pits)."""
        ts = self.st["teams"]
        return sorted(range(len(ts)), key=lambda i: (-laps_of(ts[i]["car"]["d"]), -ts[i]["car"]["d"], ts[i]["car"]["ls"], ts[i]["grid"]))

    def _finish(self) -> None:
        order = self.standings()
        ts = self.st["teams"]
        pl, n = {}, 0
        prev = None
        for k, i in enumerate(order):
            key = (laps_of(ts[i]["car"]["d"]), round(ts[i]["car"]["d"], 1), ts[i]["car"]["ls"])
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
        out["minutes"] = out["minutes"] if out["minutes"] in MINUTES else DEFAULTS["minutes"]
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
                    self.rewards.book(int(pid), "coins", amount, "game_win", win_reason(KIND, st['places'][pid]), ref=ref)
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
                        "team": t["name"], "num": t["num"], "best_pit": t.get("best_pit"), "drives": t["drives"].get(p["id"], 0),
                        "stops": len(t["pits"]), "record": bool(records.get(p["id"])), "complete": bool(st.get("complete")),
                        "flat": t["car"].get("flat", 0),
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

    def start(self, kind: str, host: int, rules: dict | None = None, solo: bool = False, bots: list[dict] | None = None,
              country: str | None = None) -> int:
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
            st = {"kind": KIND, "rules": r, "players": [], "phase": "lobby", "solo": solo, "bot_pool": list(bots or []), "looks": default_looks(country)}
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

    def choose_look(self, pid: int, color: str | None = None, country: str | None = None, num: int | None = None) -> None:
        """In the lobby: the colour (from the palette, not taken by another team), the country and the car number (1–99,
        not taken by another team) of my team."""
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
            looks = st.setdefault("looks", default_looks())
            k = int(p.get("team", 0))
            if color is not None:
                if color not in [c for _, c in TEAM_STYLES]:
                    raise CommunityError("Unknown colour")
                if any(i != k and lk["color"] == color for i, lk in enumerate(looks)):
                    raise CommunityError("Another team has this colour")
                looks[k]["color"] = color
            if country is not None:
                if country and country not in COUNTRIES:
                    raise CommunityError("Unknown country")
                looks[k]["country"] = country or None
            if num is not None:
                try:
                    num = int(num)
                except (TypeError, ValueError):
                    raise CommunityError("Car numbers go from 1 to 99") from None
                if not 1 <= num <= 99:
                    raise CommunityError("Car numbers go from 1 to 99")
                n = 1 if st.get("solo") else st["rules"]["teams"]
                if any(i != k and i < n and lk.get("num") == num for i, lk in enumerate(looks)):
                    raise CommunityError("Another team has this number")
                looks[k]["num"] = num
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

    def prep(self, pid: int, action: str, spot=None) -> dict:
        """A job of the pit crew (plug the spare battery in, tyre, spare engine) – checked and timed by the server."""
        return self._with_play(pid, lambda t, st: t.prep(str(pid), action, spot)) or {"ok": False}

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
            return {**base, "bots": nb, "nteams": 1 if st.get("solo") else st["rules"]["teams"], "looks": st.get("looks") or default_looks(),
                    "palette": [{"name": n, "color": c} for n, c in TEAM_STYLES], "countries": list(COUNTRIES)}
        t_ = self.table(st)
        mine = t_.team_of(me) if joined else None
        coins, recs = st.get("coins") or {}, st.get("records") or {}
        teams = []
        lead = max((t["car"]["d"] for t in st["teams"]), default=0)
        now_t = t_.gt()
        for i, t in enumerate(st["teams"]):
            car = t["car"]
            tv = {"i": i, "name": t["name"], "color": t["color"], "country": t.get("country"), "tyre": car["tyre"], "num": t["num"], "members": t["members"], "bot": t["bot"],
                  "driver": t["driver"], "laps": laps_of(car["d"]), "d": round(car["d"], 2), "v": round(car["v"], 2), "lane": car["lane"],
                  "pit": car["pit"], "eng": car["eng"], "emg": car["bat"] <= 0, "stops": len(t["pits"]), "best_pit": t["best_pit"], "best_lap": car["best"],
                  "gap": round(lead - car["d"], 1), "auto": t["auto"], "place": t.get("place"), "grid": t["grid"]}
            if t is mine or ph == "done":
                pr, sp = t["prep"], t["spare"]
                tv.update(car=car, drives=t["drives"], pits=t["pits"], ev=t["ev"] if t is mine else [], stop=t["stop"],
                          next=t_.next_driver(t) if ph == "play" else None,
                          spare={"c0": sp["c0"], "t": sp["t"], "plug": sp["plug"], "rate": CHARGE_RATE, "garage": not t_.active_crew(t),
                                 "charge": round(spare_charge(sp, now_t if ph == "play" else sp["t"]), 1)},
                          prep={"tyres": [x is not None for x in pr["tyres"]], "compound": pr["compound"] or car["tyre"], "eng": pr["eng"],
                                "eng_on": pr["eng_on"], "need_eng": bool(car["eng"]), "ready": t_.ready(t, now_t if ph == "play" else 1e9)})
            teams.append(tv)
        players_out = []
        for p in players:
            p = dict(p)
            p["place"] = (st.get("places") or {}).get(p["id"])
            p["coins"] = coins.get(p["id"], 0)
            p["record"] = recs.get(p["id"]) or None
            players_out.append(p)
        return {**base, "players": players_out, "me": me if joined else None, "seed": st["seed"], "t0": st["t0"], "limit": t_.limit(),
                "k": st["k"], "rain": st.get("rain") or [], "teams": teams, "my_team": mine and st["teams"].index(mine),
                "standings": t_.standings(), "log": st.get("log", [])[-6:], "end_t": st.get("end_t"), "ranking": st.get("ranking"),
                "complete": bool(st.get("complete")), "now_t": t_.gt() if ph == "play" else st.get("end_t")}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
