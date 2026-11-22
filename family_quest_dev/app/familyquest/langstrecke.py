"""«24h Endurance» (24-Stunden-Rennen) – a short, fast live team race on the fictional «Circuit des Tannes».

Teams are racing stables (a colour, a name, a start number), each with ONE car. The family splits into 1–4 teams at
the table (guests via QR code join a team too); bots bring extra cars – alone against bot teams works too. The tables
live in the `card_game` table with kind "langstrecke" (lobby, join, summary, may_lead from cardgames.CardGames).

24 race hours are compressed into 5 / 8 / 12 real minutes (rule `minutes`, default 8): the race clock starts at 15:00
and runs through the night into the next afternoon. Winner: the most laps (then the longer distance). In the lobby each
team chooses its colour (from the palette, unique), its country (a flag on the car) and its car number (1–99, unique).

The driving – real racing on a circuit (the general mechanics of the classic racing simulations, own track and look):
- the car has a position along the lap (d) and ACROSS the track (x, metres from the middle, + = right). The driver
  steers smoothly (an analog steering value −100…100: the virtual joystick, the arrow keys; the wheel follows it at
  WHEEL per second) and uses gas / lifted / brake (the joystick up / middle / down).
- gears: automatic (default; bots and the autopilot always – shifts up at AUTO_UP with a torque gap AUTO_GAP) or manual
  per driver («A / M» on the picture, any time, remembered per person) – an H shifter with
  R | 1 2 | 3 4 | 5 6: every gear a speed band (its top the rev limiter, heating faster; too high a gear pulls weakly;
  a downshift brakes with the engine), N no drive, R slowly backwards from a standstill only – R while rolling grinds
  the gearbox (a very hard stop that heats the engine fast, an overheat counts as usual).
- the lap has CORNERS (start, end, angle, safe speed). In a corner the car is pushed outward, growing with the square
  of the speed: at the corner's safe speed it takes PUSH of full lock to hold the line – a bit faster and the steering
  is not enough: the car runs wide onto the kerb (a little slower) and then the grass (heavy slowdown, VGRASS), never a
  crash (a tyre wall at XMAX). Braking boards (150 / 100 / 50 m) and a corner sign with the suggested speed come first.
- rain: less grip – the safe speeds drop (RAIN_C), slicks in the rain / rain tyres in the dry even more (and are
  slower on the straights, WET_SLICK / DRY_RAIN); the next driver picks the tyres at the stop. Night: a shorter view and
  headlights (the app), at night in the rain only 40 m – the bots slow down with the view (view_dist, bot_caution).
- other cars: following closely on a straight gives a SLIPSTREAM (a higher top speed); running into one from behind
  is a gentle bump: the car behind slows to the speed of the one ahead and slides aside – no crashes.
- the driving ASSIST (junior: on for everybody by default; every driver can switch it for themselves): the car brakes
  by itself before a corner and the steering helps towards the racing line (the driver's own steering wins). Bots and
  the autopilot drive with the same assist – their skill is how close to the safe speed they dare (BOT_SKILL).

The loop – one short lap (about 30 s), then the car drives into the pits, every time:
- the pit lane branches off the main straight to the RIGHT (PIT_IN): the driver keeps right and steers in, else a smooth
  autopilot takes the car in (nobody misses the pits); the pit limiter (PIT_V) holds the speed from the entry line to
  the pit exit (no penalty); the car crosses the line in the pit lane (the lap, timed at the crossing as always – the
  lane's metres are the lap's metres beside it), rolls into its team's box and stops there (the stop begins); after the
  stop it drives out to the pit exit and merges onto the track's right side. No contact between the pit lane and the
  track; bots take the same entry.
- full throttle heats the engine; at RED it overheats: the car limps on to the pits and the engine has to be swapped.
- the car is electric: its battery (0–100 %) drains by the metre, much faster at full throttle (E_FULL) than lifted
  (E_LIFT); braking gives a little back (REGEN). Empty: the emergency drive mode – the car crawls (VEMERG) to the pits.
- there are only drivers (no pit crew): the people of a team take turns – at EVERY stop the next person of the team (in
  turn, who is online; alone: the same person) takes over. The stop is theirs: on their phone they tap everything at
  once, in any order – the battery (STOP_BAT seconds – the new battery is always full), the 4 tyres (STOP_TYRE seconds
  each; slicks or rain tyres with one toggle, the current weather by default) and after an overheat also the engine
  (STOP_ENG) – every job runs from its own tap, all at the same time. About 4.2 s done well (with the engine about
  7.2 s); nothing tapped: done by itself after STOP_MAX seconds (+ ENG_EXTRA after an overheat) – never longer. The
  driver who came in has a break and watches the stop live. Bot teams stop in a fair fixed time (BOT_STOP, + ENG_EXTRA
  after an overheat). The server keeps the time of every tap.
- the handbrake: a short tap at the entry of a corner at speed starts a drift – full gas and steering into the corner
  hold it and the car comes through a little faster than the corner's safe speed (DRIFT_K); lifting or steering
  against it ends it and costs speed; held too long it brakes hard; a tap too late in the corner (or far too fast)
  spins the car wide off the track; on a straight just a small brake. In the rain easier to start, harder to hold.
  The assist and the bots never drift.

The server decides everything (the same step function runs in web/langstrecke.js for a smooth picture of the own
car): the driver's app only reports its inputs (steering, pedals, assist) with their game time; the server simulates
all cars in fixed steps of DT seconds SETTLE seconds behind the clock – a late input is applied at the next step (never
in the past). Every step sees the other cars as they were at the start of the step (the order of the teams does not
matter). The taps at a stop are actions on the server timed with the server's clock (in any order, a tap twice
ignored). A driver whose app is silent for AUTO_AFTER seconds gets the autopilot until the app is back. Bots drive by
the same rules (they lift off when the battery runs low and overtake on the straights) and pick their tyres by the
forecast (easier bots get it wrong more often).

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
# (an old stored `crew` rule – the pit crew of earlier versions – is ignored: clean_rules keeps only these keys)
DEFAULTS = {"bots": 2, "level": "normal", "minutes": 8, "weather": 1, "difficulty": "normal", "team_size": 3, "teams": 2}
# the countries a team can race for (ISO codes; names and groups in web/langstrecke.js) – or none
COUNTRIES = ("BE", "BG", "DK", "DE", "FI", "FR", "GR", "GB", "IE", "IT", "LV", "LI", "LU", "MC", "NL", "NO", "AT", "PL", "PT", "RO",
             "RU", "SM", "SE", "CH", "SK", "SI", "ES", "CZ", "TR", "HU", "BY",
             "AR", "BO", "BR", "CL", "DO", "EC", "GT", "CA", "CO", "CU", "MX", "PA", "PR", "KN", "US", "VE",
             "CN", "HK", "IN", "ID", "JP", "QA", "MY", "OM", "SA", "SG", "KR", "SY", "TW", "TH", "AE",
             "AU", "MA", "NZ", "ZA")

# ---------------------------------------------------------------- the circuit and the car (the same numbers in web/langstrecke.js)
L = 640.0                    # metres per lap: about 30 s
DT = 0.1                     # one step of the simulation (seconds)
VLIFT, VFULL = 20.0, 30.0    # m/s lifted / full throttle (shown as km/h × 7)
ACC, BRAKE, COAST = 8.5, 14.0, 5.0   # m/s²: speeding up, braking (the brake), slowing down by lifting off
VBRAKE = 8.0                 # holding the brake slows down towards this
VLIMP = 13.0                 # with an overheated engine
HEAT, HEAT_JR = 2.6, 1.7     # °/s at full throttle
COOL = 4.0                   # °/s lifted
TMIN, YELLOW, RED = 60.0, 85.0, 100.0
# grip: slicks in the rain / rain tyres in the dry are slower (the right tyres: 1.0); rain lowers every corner's safe speed
WET_SLICK, DRY_RAIN = 0.8, 0.9
RAIN_C = 0.85
# the corners: start, end (metres in the lap), angle (degrees, + = right), safe speed (m/s, dry, the right tyres)
CORNERS = ((90.0, 130.0, 90.0, 20.0), (210.0, 240.0, -45.0, 25.0), (300.0, 350.0, 150.0, 13.0),
           (420.0, 450.0, 75.0, 21.0), (500.0, 550.0, 90.0, 17.0))
HW, KERB, XMAX = 5.5, 1.5, 11.0   # half the track's width, the kerb beyond its edge, the tyre wall (metres from the middle)
STEER_V = 7.0                # m/s sideways at full lock (at speed)
VSTEER = 10.0                # below this speed the steering bites less
WHEEL = 6.0                  # the wheel follows the steering this much per second (smooth steering)
PUSH = 0.75                  # a corner at its safe speed pushes outward with this much of full lock (∝ speed²)
VGRASS, GRASS_DEC = 9.0, 16.0    # on the grass: this slow, braked this hard
KERB_F = 0.9                 # on the kerb: the top speed × this
SLIP_D, SLIP_W, SLIP_V = 30.0, 2.2, 3.5   # the slipstream: behind a car within this far, this much to the side → up to +this m/s
BUMP_D, CAR_W, NUDGE = 4.5, 1.9, 1.5      # a car this close ahead and overlapping: bump (slow to its speed, slide aside m/s)
PIT_Z = 25.0                 # no contact on the track this close to the line (the pit entry / exit)
# the pit lane – beside the main straight on its RIGHT. Its metres are the lap's metres of the straight beside it (d
# keeps counting along the lap; the line crosses the track and the pit lane, a lap still ends at d = n·L). Phases `pl`:
# 0 racing, 1 the entry and the lane up to the line, 2 after the line to the box, 3 out of the box to the pit exit and
# back onto the track (the end of the merge: racing again). `pz`: metres from the line of this stop (− before it).
PIT_IN = 580.0               # lap metres: the pit entry line – from here every car is on its way into the pits (every lap)
PIT_ENTRY = 30.0             # the entry bends off to the right over this many metres, then the pit wall
PIT_OUT = 60.0               # metres after the line: the pit exit (the end of the speed limit) …
PIT_MERGE = 15.0             # … and the exit lane joins the track on its right side over this many metres
PL_X, PL_HW = 9.5, 2.0       # the pit lane: its middle (metres right of the track's middle) and half its width
SIDE_X = 3.5                 # where the entry leaves / the exit joins the track (its right side)
PIT_V = 100.0 / 7.0          # the pit speed limit (100 km/h on the display): the limiter holds it by itself, no penalty
KEEP_R, KEEP_ST = 1.5, 20    # at the entry line right of this, or steering right: the driver steers in himself …
AP_LATE = 12.0               # … still on the track (left of SIDE_X) this many metres before the pit wall: the autopilot
AP_K = 0.7                   # the autopilot's steering: full lock per 1.4 m off the lane
FUNNEL = 0.45                # the entry's inner white line closes in this much per metre (nobody misses the pits)
BOX0, BOX_GAP = 10.0, 6.0    # the boxes along the pit lane: the first this far after the line, then one per team
BOX_DEC = 6.0                # m/s²: rolling into the box
PZ_IN = PIT_IN - L           # the entry line, from the line (−60 m)
LINE_D, LINE_OUT, LINE_APEX, LMAX = 40.0, 3.5, 3.5, 4.0  # the racing line: outside before the corner, the apex inside
ASSIST_K = 0.5               # the steering assist: full lock per 2 m off the line
AK_ASSIST = 0.92             # the assist brakes down to this share of the safe speed
E_FULL, E_LIFT, REGEN = 0.16, 0.07, 0.3   # the battery: % per metre at full throttle / lifted, % back per m/s braked off
VEMERG = 7.0                 # m/s with an empty battery: the emergency drive mode
# the gearbox («Manual» per driver; «Automatic» = the plain VFULL / VLIFT car above, bots and the autopilot always):
# gears 1–6 each with a speed band – its top is the rev limiter (× the tyres' grip), below its low end the gear is too
# high for the speed (weak pull, LUG) – and a pull factor; N (0) no drive; R (−1) slowly backwards, but only from a
# standstill: R while rolling forward grinds the gearbox – a very hard stop (GRIND_DEC) that heats the engine fast
GEAR_TOP = (9.0, 13.5, 18.0, 22.5, 27.0, 30.0)   # m/s: the limiter of gears 1–6
GEAR_LOW = (0.0, 5.0, 8.5, 12.5, 16.5, 21.0)     # m/s: below this the gear lugs
GEAR_ACC = (1.15, 1.1, 1.05, 1.0, 0.95, 0.9)     # × ACC in the right band
LUG = 0.35                   # the pull of a gear too high for the speed
EBRAKE = 7.0                 # m/s²: engine braking above the gear's limiter (after a downshift)
LIM_HEAT = 1.5               # on the limiter the engine heats this much faster
NEUTRAL_DEC = 3.0            # m/s²: rolling in neutral
VREV_ON = 0.75               # m/s (about 5 km/h): R engages only below this
VREV, VCREEP, REV_ACC = 2.5, 1.0, 3.0      # backwards: with gas / lifted (m/s), speeding up (m/s²)
GRIND_DEC, GRIND_HEAT = 22.0, 30.0         # R while rolling: m/s² (much harder than the brake), °/s
AUTO_UP = 0.9                # the automatic gearbox shifts up at this share of a gear's top (never into the red) …
AUTO_DOWN = 0.75             # … down below this share of the next lower gear's top (no hunting between two gears) …
AUTO_GAP = 0.2               # … and slower than a hand: no drive for this many seconds per upshift (the torque gap)
# the handbrake and the drift: a short tap at the corner's entry at speed swings the car sideways – full gas and steering
# into the corner hold it and the car comes through a little faster than the grip allows (DRIFT_K × the safe speed);
# lifting or steering against it ends it (DRIFT_LOSS); held too long the handbrake brakes hard; a tap too late in the
# corner or far too fast spins the car wide (off the track as usual); on a straight or too slow: just a small brake
HB_LONG = 0.6                # s: the handbrake held longer than this brakes hard
HB_DEC_SOFT, HB_DEC = 6.0, 15.0   # m/s²: a tap (no drift) / held too long
DRIFT_PRE, DRIFT_PRE_RAIN = 12.0, 18.0   # m before the corner: the entry window opens (in the rain: earlier – easier)
DRIFT_LATE = 0.35            # share of the corner: a tap later than this spins the car
DRIFT_VMIN, DRIFT_VMIN_RAIN = 0.85, 0.75   # × the safe speed: slower – no drift (in the rain: easier)
DRIFT_SPIN = 1.35            # × the safe speed: faster – the car spins
DRIFT_K, DRIFT_K_RAIN = 1.06, 1.03   # a held drift takes the corner at this × the safe speed
DRIFT_ST, DRIFT_ST_RAIN = 25, 60     # steering into the corner at least this much holds it (in the rain: harder)
DRIFT_GRACE = 0.3            # s after the tap before gas and steering count
DRIFT_DEC = 9.0              # m/s²: scrubbing down to the drift speed
DRIFT_LOSS = 3.0             # m/s lost when the drift is broken (lifted, steered against it)
DRIFT_HEAT = 1.0             # °/s extra heat while drifting
DRIFT_YAW, YAW_RATE, SPIN_RATE = 28.0, 140.0, 540.0   # degrees: the drift angle, how fast it builds / goes, a spin
SPIN_X, SPIN_T = 6.0, 2.0    # a spin: m/s outward, at most this long
COUNTDOWN = 6.0              # seconds from the start to game time 0 (the intro: run to the cars, engines, lights)
SETTLE = 0.8                 # the server simulates this far behind the clock
AHEAD = 0.5                  # inputs may be this much ahead of the server's clock
AUTO_AFTER = 6.0             # a silent driver: the autopilot drives
STALE = 10.0                 # a silent person is not counted as the next driver
# ---------------------------------------------------------------- the pit stop
# the stop – done by the driver who drives next, on their phone (a driver alone: the same person): every job runs from
# its own tap, all at the same time, in any order – the battery (STOP_BAT seconds – the new battery is always full), the
# 4 tyres (STOP_TYRE seconds each); after an overheat also the engine (STOP_ENG). Done when the last job is done –
# STOP_MAX seconds (+ ENG_EXTRA after an overheat) at the latest; no taps: that long. Bots: a fair fixed time
# (BOT_STOP, + ENG_EXTRA after an overheat) – a little slower than a stop tapped at once (about 4.2 s).
STOP_BAT, STOP_TYRE, STOP_MAX, STOP_ENG, ENG_EXTRA = 4.0, 1.0, 10.0, 7.0, 3.0
BOT_STOP = {"easy": 5.2, "normal": 4.9, "hard": 4.6}
TEAM_STYLES = (("Comet Racing", "#e03131"), ("Blue Falcon Works", "#1c7ed6"), ("Pine Cone Motors", "#2f9e44"),
               ("Sunrise Speedsters", "#f08c00"), ("Silver Owl Garage", "#7048e8"), ("Night Fox Racing", "#0c8599"),
               ("Thunder Bee Team", "#e8590c"), ("Snow Hare Racing", "#495057"))
NUMBERS = (3, 7, 8, 11, 12, 17, 21, 24, 27, 33, 36, 42, 44, 51, 58, 63, 77, 88, 91, 99)
# a corner too fast now and then, temperature to lift off / to push again, the chance of the wrong tyres at a stop,
# how close to the safe speed they dare (the assist's share)
BOT_SKILL = {"easy": (0.2, 92.0, 78.0, 0.35, 0.84), "normal": (0.1, 93.0, 84.0, 0.15, 0.93), "hard": (0.03, 96.0, 90.0, 0.05, 0.99)}
BOT_GREEDY = 1.3             # a missed corner: the bot dares this share of the safe speed


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def lap_pos(d: float) -> float:
    """The position in the lap (0 … L) – the same arithmetic as in the app."""
    return d - L * math.floor(d / L)


def corner_at(xl: float):
    for c in CORNERS:
        if c[0] <= xl < c[1]:
            return c
    return None


def next_corner(xl: float):
    """The corner the car is in or the next one ahead: (corner, metres to its start – 0 inside it)."""
    best, dz = None, 0.0
    for c in CORNERS:
        if c[0] <= xl < c[1]:
            return c, 0.0
        z = c[0] - xl if c[0] > xl else c[0] + L - xl
        if best is None or z < dz:
            best, dz = c, z
    return best, dz


def grip(tyre: str, rain: bool) -> float:
    return (WET_SLICK if tyre != "r" else 1.0) if rain else (DRY_RAIN if tyre == "r" else 1.0)


def safe_speed(c, tyre: str, rain: bool) -> float:
    """The corner's safe speed with these tyres in this weather."""
    return c[3] * grip(tyre, rain) * (RAIN_C if rain else 1.0)


def _r2(x: float) -> float:
    """Rounded to 1/100 – exactly the same arithmetic in the app."""
    return math.floor(x * 100 + 0.5) / 100


def _ease(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def race_line(xl: float) -> float:
    """The ideal line across the track at this point of the lap: outside before a corner, the apex inside in its
    middle, outside again at the exit (only + − × ÷ – exactly the same numbers in the app)."""
    y = 0.0
    for a, b, ang, _ in CORNERS:
        dr = 1.0 if ang > 0 else -1.0
        if a - LINE_D <= xl < a:
            y -= dr * LINE_OUT * _ease((xl - (a - LINE_D)) / LINE_D)
        elif a <= xl < b:
            u = (xl - a) / (b - a)
            y += -dr * LINE_OUT + dr * (LINE_OUT + LINE_APEX) * 4.0 * u * (1.0 - u)
        elif b <= xl < b + LINE_D:
            y -= dr * LINE_OUT * (1.0 - _ease((xl - b) / LINE_D))
    return clamp(y, -LMAX, LMAX)


def pit_z(d: float, pl: int) -> float:
    """Metres from the line of this pit stop: − on the entry before it, + after it (the boxes, the exit)."""
    xl = lap_pos(d)
    return xl - L if pl == 1 else xl


def pit_x(pz: float) -> float:
    """The middle of the pit lane at pz: the entry bends off the track's right side, the lane, the exit bends back."""
    if pz < PZ_IN + PIT_ENTRY:
        return SIDE_X + (PL_X - SIDE_X) * _ease((pz - PZ_IN) / PIT_ENTRY)
    if pz < PIT_OUT:
        return PL_X
    return PL_X + (SIDE_X - PL_X) * _ease((pz - PIT_OUT) / PIT_MERGE)


def pit_bounds(pz: float) -> tuple[float, float]:
    """Where a car in the pit lane can be across: on the entry still open to the track (its white line closes in),
    then between the pit wall and the boxes, on the exit bending back onto the track's right side."""
    if pz < PZ_IN + PIT_ENTRY:
        return max(-XMAX, PL_X - PL_HW - (PZ_IN + PIT_ENTRY - pz) * FUNNEL), PL_X + PL_HW
    c = pit_x(pz)
    return c - PL_HW, c + PL_HW


def box_of(i: int) -> float:
    """The box of the team with this index: metres after the line."""
    return BOX0 + BOX_GAP * i


def default_looks(country: str | None = None) -> list[dict]:
    """The lobby: colour, country (the family's own if the app knows it, else none) and car number of the teams of
    people – they can change them."""
    c = country if country in COUNTRIES else None
    return [{"color": TEAM_STYLES[i][1], "country": c, "num": (7, 24, 44, 88)[i]} for i in range(4)]


def new_car(x: float, d: float) -> dict:
    return {"d": d, "x": x, "v": 0.0, "thr": 0, "st": 0, "sw": 0.0, "ast": 0, "ak": AK_ASSIST, "lo": 0.0, "temp": TMIN,
            "eng": 0, "ls": 0.0, "best": 0.0, "last": 0.0, "pit": 0, "bumps": 0, "bc": 0.0, "blows": 0, "tyre": "s",
            "kerb": 0, "sf": 0, "offs": 0, "tow": 0.0, "bat": 100.0, "flat": 0, "man": 0, "gear": 1, "sg": 0.0,
            "pl": 0, "ap": 0, "box": BOX0,
            "hb": 0, "hbt": 0.0, "dr": 0, "drt": 0.0, "dc": 0, "yaw": 0.0}


def auto_gear(v: float) -> int:
    """The gear the automatic gearbox would be in at speed v (the same in the app)."""
    for i, top in enumerate(GEAR_TOP):
        if v < top * AUTO_UP:
            return i + 1
    return len(GEAR_TOP)


def apply_input(car: dict, c: str, v) -> None:
    """One input of the driver – the same rules as in the app: "s" steering −100 … 100, "u" 1 gas / 0 lifted / −1
    brake, "a" the assist on / off, "m" manual gears on / off (on: the gear that fits the speed), "g" the gear
    −1 R / 0 N / 1–6 (anything else is ignored), "h" the handbrake held 1 / released 0."""
    if c == "s":
        car["st"] = max(-100, min(100, int(v)))
    elif c == "u":
        car["thr"] = 1 if int(v) > 0 else -1 if int(v) < 0 else 0
    elif c == "a":
        car["ast"] = 1 if int(v) else 0
        car["ak"] = AK_ASSIST
    elif c == "m":
        car["man"] = 1 if int(v) else 0
        car["gear"] = auto_gear(car["v"])
    elif c == "g" and -1 <= int(v) <= len(GEAR_TOP):
        car["gear"] = int(v)
    elif c == "h":
        car["hb"] = 1 if int(v) else 0


def step(car: dict, s: float, jr: bool, rain: bool = False, others=()) -> list[str]:
    """One step of DT seconds from game time s – the same in web/langstrecke.js. `others`: the other cars on the
    track as they were at the start of the step, [[d, x, v], …]. Answers what happened."""
    ev: list[str] = []
    if car["pit"]:
        car["temp"] = max(TMIN, car["temp"] - COOL * DT)
        return ev
    d0, x0, v0 = car["d"], car["x"], car["v"]
    xl = lap_pos(d0)
    # the pit lane: from the entry line on every car is on its way into the pits – the driver steers in (keeping right
    # or steering right at the line), else the autopilot takes over; out of the pit exit it races again
    pl = car.get("pl", 0)
    if pl == 0 and d0 >= 0 and xl >= PIT_IN:
        pl = car["pl"] = 1
        car["ap"] = 0 if x0 >= KEEP_R or car["st"] >= KEEP_ST else 1
        ev.append("pitlane")
        if car["ap"]:
            ev.append("autopilot")
    elif pl == 3 and PIT_OUT + PIT_MERGE <= xl < PIT_IN:
        pl = car["pl"] = 0
    pz = pit_z(d0, pl) if pl else 0.0
    if pl == 1 and not car.get("ap", 0) and pz >= PZ_IN + PIT_ENTRY - AP_LATE and x0 < SIDE_X:
        car["ap"] = 1                                  # not steering in: the autopilot (nobody misses the pits)
        ev.append("autopilot")
    ap = pl > 0 and car.get("ap", 0) == 1
    cn = corner_at(xl)
    th = 0 if ap else car["thr"]                       # the autopilot: lifted off – the limiter brings it to the pit speed
    stc = 0.0 if ap else car["st"] / 100.0
    emg = car["bat"] <= 0                              # the battery is empty: the emergency drive mode
    bite = min(1.0, 0.2 + abs(v0) / VSTEER)            # how much the steering bites at this speed
    # the handbrake and the drift (not in the pit lane, not by the autopilot)
    hb = 1 if car.get("hb", 0) and not pl and not ap else 0
    hbt0 = car.get("hbt", 0.0)
    car["hbt"] = hbt0 + DT if hb else 0.0
    dr, lose, spinx = car.get("dr", 0), False, 0.0
    if hb and hbt0 == 0.0 and dr == 0 and car["sf"] != 2 and v0 > 0:     # the tap: a drift, a spin – or just a small brake
        nc, dz = next_corner(xl)
        if nc is not None:
            sv = safe_speed(nc, car["tyre"], rain)
            u = (xl - nc[0]) / (nc[1] - nc[0]) if cn is not None else -1.0
            if v0 >= sv * (DRIFT_VMIN_RAIN if rain else DRIFT_VMIN):
                entry = (cn is None and dz <= (DRIFT_PRE_RAIN if rain else DRIFT_PRE)) or (cn is not None and u <= DRIFT_LATE)
                late = cn is not None and u > DRIFT_LATE
                if late or (entry and v0 >= sv * DRIFT_SPIN):
                    dr = 2
                    ev.append("spin")
                elif entry:
                    dr = 1
                    ev.append("drift")
                if dr:
                    car["dc"] = CORNERS.index(nc)
                    car["drt"] = 0.0
    dc = CORNERS[car.get("dc", 0)] if dr else (0.0, 0.0, 0.0, 0.0)   # the drift's corner
    ddir = 1.0 if dc[2] > 0 else -1.0
    dsafe = safe_speed(dc, car["tyre"], rain) * (DRIFT_K_RAIN if rain else DRIFT_K)
    if dr == 1:                                        # the drift: gas and steering into the corner hold it
        car["drt"] = car.get("drt", 0.0) + DT
        if hbt0 + DT > HB_LONG or car["sf"] == 2 or pl:
            dr = 0                                     # held too long (brakes hard) / on the grass / the pit lane
        elif cn is None and xl >= dc[1]:
            dr = 0                                     # through the corner: a clean exit
        elif car["drt"] > DRIFT_GRACE + 1e-9 and not (car["thr"] > 0 and car["st"] * ddir >= (DRIFT_ST_RAIN if rain else DRIFT_ST)):
            dr = 0                                     # lifted or steered against it: the drift breaks
            lose = True
    elif dr == 2:                                      # the spin: wide off the track, then the grass slows it down
        car["drt"] = car.get("drt", 0.0) + DT
        if car["sf"] == 2 or v0 <= VGRASS or car["drt"] > SPIN_T:
            dr = 0
        else:
            spinx = -ddir * SPIN_X
    car["dr"] = dr
    push = 0.0                                         # a corner pushes outward, ∝ speed² (drifting: against the drift speed)
    if cn is not None:
        q = v0 / (dsafe if dr == 1 else safe_speed(cn, car["tyre"], rain))
        push = (-1.0 if cn[2] > 0 else 1.0) * STEER_V * PUSH * q * q
    if ap:                                             # the autopilot steers smoothly along the pit lane
        stc = clamp((pit_x(pz) - x0) * AP_K, -1.0, 1.0)
    elif car["ast"] and dr == 0:                       # the assist (never while drifting): towards the racing line (the pit lane), brake before a corner
        aim = pit_x(pz) if pl else clamp(race_line(xl) + car["lo"], -LMAX, LMAX)
        help_ = clamp((aim - x0) * ASSIST_K - push / (STEER_V * bite), -1.0, 1.0)
        stc = clamp(stc + (1.0 - abs(stc)) * help_, -1.0, 1.0)
        nc, dz = next_corner(xl)
        if nc is not None:
            tv = safe_speed(nc, car["tyre"], rain) * car["ak"]
            if v0 > tv and dz <= (v0 * v0 - tv * tv) / (2.0 * BRAKE) + v0 * 0.3 + 2.0:
                th = -1
    car["sw"] += clamp(stc - car["sw"], -WHEEL * DT, WHEEL * DT)
    full = th > 0 and not car["eng"] and not emg
    pitlim = pl > 0 and pz < PIT_OUT                   # the pit limiter: on by itself from the entry line to the exit
    if pitlim and v0 >= PIT_V - 0.3:
        full = False                                   # holding the limit: no full throttle (no heat, lifted drain)
    gr = grip(car["tyre"], rain)
    man, g = (0 if ap else car.get("man", 0)), car.get("gear", 1)   # the autopilot: automatic gears
    acc, dec, lim, grind, rev, top = ACC, COAST, False, False, False, 0.0
    gap = False
    if not man:                                        # automatic: the plain car – with a torque gap at every shift
        vt = VLIMP if car["eng"] else (VFULL if full else VLIFT) * gr
        if not 1 <= g <= len(GEAR_TOP):                # from N / R: the gear that fits, no gap
            g = car["gear"] = auto_gear(v0)
        if g < len(GEAR_TOP) and v0 >= GEAR_TOP[g - 1] * AUTO_UP:
            car["gear"] = max(g + 1, auto_gear(v0))     # one shift (one gap), however far up it goes
            car["sg"] = AUTO_GAP
        elif g > 1 and v0 < GEAR_TOP[g - 2] * AUTO_DOWN:
            car["gear"] = g - 1
        gap = car.get("sg", 0.0) > 1e-9
        car["sg"] = max(0.0, car.get("sg", 0.0) - DT)
    elif g >= 1:                                       # a gear: its band, its limiter, too high = weak pull
        top = GEAR_TOP[g - 1] * gr
        vt = min(VLIMP, top) if car["eng"] else top if full else min(VLIFT * gr, top)
        acc = ACC * GEAR_ACC[g - 1] * (LUG if v0 < GEAR_LOW[g - 1] else 1.0)
        lim = v0 >= top - 0.3 and (full or v0 > top + 0.3)
        if v0 > top + 0.3:                             # over the limiter after a downshift: engine braking
            dec = EBRAKE
    else:                                              # N: no drive – R: grinding while rolling, else backwards
        full = False
        vt = 0.0
        grind = g < 0 and v0 > VREV_ON
        rev = g < 0 and not grind
        dec = GRIND_DEC if grind else NEUTRAL_DEC
    if emg:
        vt = min(vt, VEMERG)
    if th < 0:
        vt = min(vt, VBRAKE)
        dec = max(dec, BRAKE)
    if pitlim:                                         # the limiter (manual gears too) – braking down to it
        vt = min(vt, PIT_V)
        if v0 > PIT_V:
            dec = max(dec, BRAKE)
    if dr == 1:                                        # drifting: the car settles at the drift speed
        vt = min(vt, dsafe)
        dec = max(dec, DRIFT_DEC)
    elif dr == 2:
        vt = min(vt, VGRASS)
        dec = max(dec, GRASS_DEC)
    elif hb:                                           # the handbrake: a tap brakes a little, held too long hard
        vt = min(vt, VBRAKE)
        dec = max(dec, HB_DEC if car["hbt"] > HB_LONG + 1e-9 else HB_DEC_SOFT)
    if pl == 2:                                        # rolling into the box and stopping there
        vt = min(vt, max(2.0, math.sqrt(2.0 * BOX_DEC * max(0.0, car.get("box", BOX0) - pz))))
        dec = max(dec, BOX_DEC)
    # the other cars: the slipstream behind one on a straight, a gentle bump when too close (never with the pit lane)
    tow, bump, nudge = 0.0, None, 0.0
    if not pl and PIT_Z <= xl <= L - PIT_Z:
        for od, ox, ov in others:
            ol = lap_pos(od)
            if ol < PIT_Z or ol > L - PIT_Z:
                continue
            rel = lap_pos(od - d0)
            dx = ox - x0
            if rel <= 0.0 or rel > SLIP_D:
                continue
            if cn is None and abs(dx) < SLIP_W:
                tow = max(tow, 1.0 - rel / (SLIP_D * 1.5))
            if rel < BUMP_D and abs(dx) < CAR_W and (bump is None or ov < bump):
                bump = ov
                nudge = -NUDGE if dx > 0 else NUDGE
    car["tow"] = tow
    if tow > 0 and th >= 0 and (not man or g >= 1):
        vt += SLIP_V * tow
    if car["sf"] == 2:                                 # on the grass: heavy slowdown
        vt = min(vt, VGRASS)
        dec = max(dec, GRASS_DEC)
    elif car["sf"] == 1:
        vt *= KERB_F
    v = (v0 if gap else min(vt, v0 + acc * DT)) if v0 < vt else max(vt, v0 - dec * DT)
    if rev:                                            # backwards, slowly: gas / lifted creeps / the brake stops
        tg = 0.0 if th < 0 else -VREV if th > 0 else -VCREEP
        v = max(tg, v0 - REV_ACC * DT) if v0 > tg else min(tg, v0 + (BRAKE if th < 0 else REV_ACC) * DT)
    if lose:
        v = max(0.0, v - DRIFT_LOSS)
    car["bc"] = max(0.0, car["bc"] - DT)
    if bump is not None and v > bump:
        v = max(0.0, bump)
        if car["bc"] <= 0:
            car["bc"] = 1.0
            car["bumps"] += 1
            ev.append("bump")
    else:
        nudge = 0.0
    # across the track: the wheel, the corner's push, a nudge; then the surface under the car
    lo, hi = pit_bounds(pz) if pl else (-XMAX, XMAX)   # in the pit lane: its white line, the pit wall, the boxes
    x = clamp(x0 + (car["sw"] * STEER_V * bite + push + nudge + spinx) * DT, lo, hi)
    ax = abs(x)
    sf = 0 if ax <= HW or (pl and x > 0) else 1 if ax <= HW + KERB else 2
    if sf == 2 and car["sf"] != 2:
        car["offs"] += 1
        ev.append("off")
    elif sf == 1 and car["sf"] == 0:
        car["kerb"] += 1
        ev.append("kerb")
    car["sf"] = sf
    # the battery: by the metre – full throttle much more than lifted; braking gives a little back
    if not emg:
        use = (E_FULL if full else E_LIFT) * abs(v) * DT
        if th < 0 and v < v0:
            use -= REGEN * (v0 - v)
        car["bat"] = max(0.0, min(100.0, car["bat"] - use))
        if car["bat"] <= 0:
            car["flat"] += 1
            ev.append("empty")
    d1 = d0 + v * DT
    if v < 0 and d1 < math.floor(d0 / L) * L:          # backwards never over the line (no lap twice)
        d1 = math.floor(d0 / L) * L
        v = 0.0
    # the engine: full throttle heats it (on the limiter faster, a grinding gearbox much faster), lifting cools it;
    # at RED it overheats (limp to the pits, swap it there)
    if grind:
        car["temp"] = min(RED, car["temp"] + GRIND_HEAT * DT)
        ev.append("grind")
    elif lim:
        car["temp"] = min(RED, car["temp"] + (HEAT_JR if jr else HEAT) * LIM_HEAT * DT)
    elif full:
        car["temp"] = min(RED, car["temp"] + (HEAT_JR if jr else HEAT) * DT)
    else:
        car["temp"] = max(TMIN, car["temp"] - COOL * DT)
    if dr == 1:                                        # drifting heats the engine a little more
        car["temp"] = min(RED, car["temp"] + DRIFT_HEAT * DT)
    if (full or lim or grind) and car["temp"] >= RED - 1e-9:
        car["eng"] = 1
        car["blows"] += 1
        car["temp"] = 80.0
        ev.append("blow")
    # the line (across the track and the pit lane): a lap – on in the pit lane to the box (not at the start)
    # the drift angle (the picture): towards the drift's angle, round and round in a spin, back to straight
    yaw = car.get("yaw", 0.0)
    if dr == 1:
        yaw += clamp(ddir * DRIFT_YAW - yaw, -YAW_RATE * DT, YAW_RATE * DT)
    elif dr == 2:
        yaw += ddir * SPIN_RATE * DT
        if yaw > 180.0:
            yaw -= 360.0
        elif yaw < -180.0:
            yaw += 360.0
    else:
        yaw += clamp(-yaw, -2.0 * YAW_RATE * DT, 2.0 * YAW_RATE * DT)
    car["yaw"] = yaw
    n0, n1 = math.floor(d0 / L), math.floor(d1 / L)
    tc = s + (n1 * L - d0) / v if n1 > n0 else 0.0     # the moment the car crossed the line (within the step)
    if n1 > n0 and n0 >= 0:
        lt = _r2(tc - car["ls"])
        car["last"] = lt
        car["best"] = lt if not car["best"] or lt < car["best"] else car["best"]
        car["ls"] = _r2(tc)
        pl = car["pl"] = 2
        ev.append("lap")
    elif n1 > n0:
        car["ls"] = _r2(tc)                             # the start: the first lap begins
    if pl == 2 and d1 >= n1 * L + car.get("box", BOX0):          # at the box: the car stops – the pit stop begins
        d1 = n1 * L + car.get("box", BOX0)
        v = 0.0
        car.update(pit=1, sw=0.0, sf=0, tow=0.0, ap=0, dr=0, yaw=0.0, hbt=0.0)
        ev.append("pit")
    car["d"] = d1
    car["x"] = x
    car["v"] = v
    return ev


def laps_of(d: float) -> int:
    return max(0, math.floor(d / L))


def race_hour(s: float, limit: float) -> float:
    """The race clock (hour of the day, 0–24): 16:00 at the start."""
    return (16 + 24 * max(0.0, s) / limit) % 24


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


def view_dist(dk: float, rain: bool) -> float:
    """How far a driver sees (metres; leView() in the app): 150 by day, 70 at night, 125 in the rain by day, 40 at night
    in the rain – the app shows the track, the corner sign and the boards only that far ahead."""
    return 125.0 - 85.0 * dk if rain else 150.0 - 80.0 * dk


def bot_caution(dk: float, rain: bool) -> tuple[float, bool]:
    """Bots drive by what they can see: the share of their usual corner speed (about proportional to the view) and
    whether they lift off on the straights (night in the rain)."""
    vis = view_dist(dk, rain) / 150.0
    return 0.72 + 0.28 * vis, vis < 0.35


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
        for pos, ti in enumerate(order):                 # the grid: two by two (left, right), 8 m apart
            t = teams[ti]
            t.update(car=new_car(-2.5 if pos % 2 == 0 else 2.5, -5.0 - 8.0 * pos), driver=t["members"][0], drives={t["members"][0]: 1},
                     stop=None, pits=[], best_pit=None, ev=[], auto=False, bk="", hot=0, grid=pos + 1, laps=[])
        for i, t in enumerate(teams):                    # the boxes along the pit lane: one per team
            t["car"]["box"] = box_of(i)
        for p in players:
            p["team"] = next(i for i, t in enumerate(teams) if p["id"] in t["members"])
        junior = self.jr()
        assist = self.st.setdefault("assist", {})
        for p in humans:                                 # the driving assist per person: junior → on unless switched off
            assist.setdefault(p["id"], junior)
        manual = self.st.setdefault("manual", {})
        for t in teams:
            if not t["bot"]:
                t["car"]["ast"] = 1 if assist.get(t["driver"]) else 0
                t["car"]["man"] = 1 if manual.get(t["driver"]) else 0
        self.st.update(phase="play", seed=seed if seed is not None else self.rng.randrange(1, 2 ** 31), t0=self.now() + COUNTDOWN,
                       k=0, teams=teams, rain=rain_plan(self.rng, self.limit()) if self.st["rules"].get("weather", 1) else [], seen={p["id"]: self.now() for p in humans}, ranking=None, places=None, complete=False,
                       end_t=None, log=[])

    # ---------- what the apps send
    def report(self, pid: str, inputs=()) -> int:
        """The driver's inputs ([game time, "s"|"u"|"a"|"m"|"g"|"h", value]: steering −100 … 100, the pedals, the assist,
        manual gears on / off, the gear −1 R / 0 N / 1–6 – another gear is dropped –, the handbrake 1 / 0) – only
        the current driver's count; a late one is applied at the next step (never in the past). Answers how many were
        taken."""
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
            except (TypeError, ValueError, OverflowError, IndexError, KeyError):     # int(inf): OverflowError
                continue
            if c not in ("s", "u", "a", "m", "g", "h") or not math.isfinite(te) or te > now_t + AHEAD:
                continue
            if c == "g" and not -1 <= v <= len(GEAR_TOP):
                continue
            if c == "s":
                v = max(-100, min(100, v))
            elif c != "g":
                v = 1 if v > 0 else -1 if v < 0 else 0
            if c == "h":
                v = 1 if v > 0 else 0
            if c == "a":
                v = 1 if v else 0
                self.st.setdefault("assist", {})[pid] = bool(v)     # remembered for this person's next stints
            elif c == "m":
                v = 1 if v else 0
                self.st.setdefault("manual", {})[pid] = bool(v)     # manual gears: remembered like the assist
            last = t["ev"][-1][0] if t["ev"] else -COUNTDOWN
            te = max(te, sim, last)
            t["ev"].append([round(te, 3), c, v])
            taken += 1
        del t["ev"][:-120]
        return taken

    def tap(self, pid: str, action: str, spot=None) -> dict:
        """A tap of the driver who drives next at the team's stop – timed by the server's clock: the battery, the tyres
        (and after an overheat the engine) in any order, every job from its own tap, all at the same time; a tap twice
        is ignored, a tap of anybody else or after the stop is refused. All done: the stop ends when the last job is
        done (STOP_MAX, + ENG_EXTRA after an overheat, at the latest). "slicks" / "rain": the tyres to fit."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        t = self.team_of(pid)
        if not t or t["bot"]:
            raise CommunityError("You are not at this table")
        self.st["seen"][pid] = self.now()
        stp = t["stop"]
        if not stp or not stp.get("jobs") or stp["next"] != pid:
            raise CommunityError("Not your stop")
        now_t = math.floor(self.gt() * 1000) / 1000       # stored to the millisecond, never later than now
        jobs = stp["jobs"]
        if now_t >= stp["end"] - 1e-9 or now_t < stp["t"]:
            return {"ok": False, "over": True}
        if action in ("slicks", "rain"):
            stp["tyre"] = "r" if action == "rain" else "s"
            return {"ok": True, "tyre": stp["tyre"]}
        if action == "battery":
            if jobs["bat"] is not None:
                return {"ok": True, "again": True}
            jobs["bat"] = now_t                          # the battery: the time of the tap (done STOP_BAT later)
            done = round(now_t + STOP_BAT, 3)
            self._stop_done(stp)
            return {"ok": True, "done": done}
        if action == "tyre":
            try:
                k = int(spot)
            except (TypeError, ValueError):
                raise CommunityError("Unknown spot") from None
            if not 0 <= k <= 3:
                raise CommunityError("Unknown spot")
        elif action == "engine":
            if not stp["eng"]:
                raise CommunityError("The engine is fine")
        else:
            raise CommunityError("Unknown job")
        cur = jobs["tyres"][k] if action == "tyre" else jobs["eng"]
        if cur is not None:
            return {"ok": True, "again": True}
        done = round(now_t + (STOP_TYRE if action == "tyre" else STOP_ENG), 3)   # from its own tap, beside the others
        if action == "tyre":
            jobs["tyres"][k] = done
        else:
            jobs["eng"] = done
        self._stop_done(stp)
        return {"ok": True, "done": done}

    @staticmethod
    def _stop_done(stp: dict) -> None:
        """Every job tapped: the stop ends when the last one is done (its cap at the latest)."""
        jobs = stp["jobs"]
        if jobs["bat"] is None or any(x is None for x in jobs["tyres"]) or (stp["eng"] and jobs["eng"] is None):
            return
        end = round(min(stp["t"] + stp["cap"], max([jobs["bat"] + STOP_BAT] + jobs["tyres"] + [jobs["eng"] or 0.0])), 2)
        stp.update(end=end, time=round(end - stp["t"], 1), done=True)

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
        """The car stopped at its box: a bot team's stop takes its fixed time; a team of people waits for the taps of the
        driver who drives next (STOP_MAX at the latest, + ENG_EXTRA after an overheat). The new battery is always full;
        the tyres: the current weather (bots: the forecast, now and then wrong) – the next driver can switch them."""
        car = t["car"]
        at = round(s + DT, 2)
        eng = bool(car["eng"])
        nxt = self.next_driver(t)
        rain_now = in_window(self.st.get("rain"), at)
        if t["bot"]:
            level = self.person(t["driver"]).get("level", "normal")
            miss = BOT_SKILL.get(level, BOT_SKILL["normal"])[3]
            took = round(BOT_STOP.get(level, BOT_STOP["normal"]) + (ENG_EXTRA if eng else 0.0), 1)
            wet_soon = self.wet_soon(at + took)
            tyre = ("r" if wet_soon else "s") if self.rng.random() >= miss else ("s" if wet_soon else "r")
            jobs = None
        else:
            took = STOP_MAX + (ENG_EXTRA if eng else 0.0)
            tyre = "r" if rain_now else "s"
            jobs = {"bat": None, "tyres": [None, None, None, None], "eng": None}
        t["stop"] = {"t": at, "end": round(at + took, 2), "time": took, "cap": took, "n": len(t["pits"]) + 1, "prev": t["driver"],
                     "next": nxt, "change": nxt != t["driver"], "eng": eng, "tyre": tyre, "bat_in": 100.0,
                     "bat_out": round(car["bat"], 2), "jobs": jobs, "done": False}

    def wet_soon(self, s: float) -> bool:
        """The forecast for the next lap: rain at about the middle of it."""
        return in_window(self.st.get("rain"), s + 12.0)

    def _release(self, t: dict) -> None:
        car, stop = t["car"], t["stop"]
        car.update(pit=0, v=0.0, eng=0, slow=0.0, temp=min(car["temp"], 70.0), tyre=stop["tyre"], bat=stop["bat_in"], pl=3, ap=0, sw=0.0,
                   hb=0, hbt=0.0, dr=0, yaw=0.0)
        if not t["bot"]:
            car.update(thr=0, st=0)                      # the new driver presses the pedal again
        t["pits"].append({"n": stop["n"], "time": stop["time"], "change": stop["change"], "eng": stop["eng"], "at": stop["t"],
                          "driver": stop["prev"], "by": stop["next"]})
        if not t["bot"] and stop.get("done") and (t["best_pit"] is None or stop["time"] < t["best_pit"]):   # records: stops tapped to the end
            t["best_pit"] = stop["time"]
        t["driver"] = stop["next"]
        t["drives"][t["driver"]] = t["drives"].get(t["driver"], 0) + 1
        if not t["bot"]:                                 # the new driver's own choice of the assist and the gears (from 1st)
            car.update(ast=1 if (self.st.get("assist") or {}).get(t["driver"]) else 0, ak=AK_ASSIST, lo=0.0,
                       man=1 if (self.st.get("manual") or {}).get(t["driver"]) else 0, gear=1)
        t["ev"] = []
        t["stop"] = None

    # ---------- the clock: everything up to SETTLE seconds ago
    def tick(self) -> None:
        if self.st.get("phase") != "play":
            return
        now_t = self.gt()
        lim = self.limit()
        horizon = min(now_t - SETTLE, lim)
        jr = self.jr()
        for t in self.st["teams"]:                       # who drives: the app, or the autopilot when it is silent
            was = t["auto"]
            t["auto"] = not t["bot"] and not self.seen_ok(t["driver"], AUTO_AFTER) and now_t > 0
            if was and not t["auto"]:                    # back in the app: the pedal released, the driver's own assist
                t["car"].update(thr=0, st=0, hb=0, lo=0.0, ak=AK_ASSIST, ast=1 if (self.st.get("assist") or {}).get(t["driver"]) else 0,
                                man=1 if (self.st.get("manual") or {}).get(t["driver"]) else 0, gear=auto_gear(t["car"]["v"]))
        steps = 0
        teams = self.st["teams"]
        while (self.st["k"] + 1) / 10 <= horizon + 1e-9 and steps < 30000:
            s = self.st["k"] / 10
            rain = in_window(self.st.get("rain"), s)
            # every car sees the others as they were at the start of the step (the order of the teams does not matter)
            # (the pit lane apart: no contact between the track and the pit lane)
            snap = [None if t["car"]["pit"] or t["car"].get("pl") else [t["car"]["d"], t["car"]["x"], t["car"]["v"]] for t in teams]
            for i, t in enumerate(teams):
                car = t["car"]
                if car["pit"] and t["stop"] and s + 1e-9 >= t["stop"]["end"]:
                    self._release(t)
                others = [o for j, o in enumerate(snap) if j != i and o is not None]
                if t["bot"] or t["auto"]:
                    self._drive(t, s, others)
                else:
                    while t["ev"] and t["ev"][0][0] <= s + 1e-9:
                        _, c, v = t["ev"].pop(0)
                        apply_input(car, c, v)
                for e in step(car, s, jr, rain, others):
                    if e == "lap":
                        t.setdefault("laps", []).append({"n": len(t["laps"]) + 1, "driver": t["driver"], "time": car["last"],
                                                         "offs": car["offs"] - sum(x.get("offs", 0) for x in t["laps"]), "rain": rain})
                    elif e == "pit":
                        self._open_stop(t, s)
                    elif e == "blow":
                        self.st["log"].append([round(s + DT, 1), e, t["num"]])
                        del self.st["log"][:-30]
            self.st["k"] += 1
            steps += 1
        self._maybe_end(horizon)

    def _drive(self, t: dict, s: float, others=()) -> None:
        """The bot driver (also the autopilot of a silent app): the assist on the racing line – as close to the safe
        speed as its skill dares (now and then a corner too fast), overtaking on the side, lifting off when hot or when
        the battery would not last the lap flat out."""
        car = t["car"]
        if car["pit"]:
            return
        level = self.person(t["driver"]).get("level", "normal") if t["bot"] else "normal"
        miss, hot_hi, hot_lo, _, dare = BOT_SKILL.get(level, BOT_SKILL["normal"])
        xl = lap_pos(car["d"])
        nc, _ = next_corner(xl)
        key = f"{math.floor(car['d'] / L)}:{CORNERS.index(nc) if nc in CORNERS else -1}"
        caution, lift = bot_caution(darkness(s, self.limit()), in_window(self.st.get("rain"), s))
        if key != t.get("bk"):                           # a new corner ahead: this time carefully – or too greedy
            t["bk"] = key
            car["ak"] = (BOT_GREEDY if self.rng.random() < miss else dare) * caution    # (in the dark and the rain: slower)
        car.update(ast=1, st=0, man=0, hb=0)             # bots and the autopilot: automatic gears, never R, no handbrake
        # overtaking: a car close ahead – drive alongside it (the slipstream helps on the straight)
        line = race_line(xl)
        ahead = None
        for od, ox, ov in others:
            rel = lap_pos(od - car["d"])
            if rel > L / 2:
                rel -= L
            if -6.0 < rel < 35.0 and abs(ox - car["x"]) < 3.0 and (ahead is None or abs(rel) < abs(ahead[0])):
                ahead = (rel, ox)
        if ahead is None:
            car["lo"] = 0.0
        elif not car["lo"]:
            ox = ahead[1]
            car["lo"] = clamp(ox + (3.2 if ox <= line else -3.2), -LMAX, LMAX) - line
        if not car.get("pl") and car["d"] >= 0 and PIT_IN - 40.0 <= xl < PIT_IN:
            car["lo"] = LMAX - line                      # the pit lane ahead: keep right, steer in at the entry
        if car["temp"] >= hot_hi:
            t["hot"] = 1
        elif car["temp"] <= hot_lo:
            t["hot"] = 0
        car["thr"] = 0 if t["hot"] or lift else 1         # night and rain: hardly any view – lifted on the straights too
        # the battery: flat out only while it lasts to the pits, else lift off (economical)
        left = (math.floor(car["d"] / L) + 1) * L - car["d"]
        if car["bat"] < left * E_FULL + 2.0:
            car["thr"] = 0

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
        self._payout(KIND, row["id"], coins, lambda pid: win_reason(KIND, st["places"][pid]))
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

    def choose_look(self, pid: int, color: str | None = None, country: str | None = None, num: int | None = None,
                    assist: bool | None = None) -> None:
        """In the lobby: the colour (from the palette, not taken by another team), the country and the car number (1–99,
        not taken by another team) of my team – and my own driving assist (on / off)."""
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
            if assist is not None:
                st.setdefault("assist", {})[str(pid)] = bool(assist)
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

    def tap(self, pid: int, action: str, spot=None) -> dict:
        """A tap of the next driver at the team's stop (battery, tyre, engine, slicks / rain) – checked and timed by the server."""
        return self._with_play(pid, lambda t, st: t.tap(str(pid), action, spot)) or {"ok": False}

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
                "best": self.best(me) if joined else None, "now": self.now(),
                "assist": bool((st.get("assist") or {}).get(me, st["rules"].get("difficulty") == "junior")) if joined else None}
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
                  "driver": t["driver"], "laps": laps_of(car["d"]), "d": round(car["d"], 2), "v": round(car["v"], 2), "x": round(car["x"], 2),
                  "pit": car["pit"], "eng": car["eng"], "emg": car["bat"] <= 0, "stops": len(t["pits"]), "best_pit": t["best_pit"], "best_lap": car["best"],
                  "gap": round(lead - car["d"], 1), "auto": t["auto"], "place": t.get("place"), "grid": t["grid"], "sf": car["sf"],
                  "last_lap": car.get("last", 0.0), "pl": car.get("pl", 0), "ap": car.get("ap", 0), "box": car.get("box", BOX0),
                  "dr": car.get("dr", 0), "yaw": round(car.get("yaw", 0.0), 1)}
            if t is mine or ph == "done":
                tv.update(car=car, drives=t["drives"], pits=t["pits"], ev=t["ev"] if t is mine else [], stop=t["stop"], laptimes=(t.get("laps") or [])[-12:],
                          next=t_.next_driver(t) if ph == "play" else None)
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
