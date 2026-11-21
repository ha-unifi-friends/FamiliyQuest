"""«24h Endurance» (24-Stunden-Rennen), the short version – the car (steering across the track, the corners with their
safe speeds, running wide, the slipstream, the gentle bump, the driving assist, rain and tyres, the engine, the same
step in the app), into the pits after every lap, the crew's jobs (checked and timed on the server), the stop time from
what was ready, the engine swap, the electric car's battery (drain, emergency drive mode, the swap at every stop, the
ONE spare charging on the server's clock, the garage, bots), the driver change for 1 / 2 / 3 people, bots, team looks
(colour, country, number), the lap times, the end and the winner, coins once, history, records, guests, the game
battery, settings, the app."""
import json
import math
import random
import re
import subprocess
from pathlib import Path

import pytest

from familyquest import langstrecke as ls
from familyquest.community import CommunityError
from websrc import parent_js

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def car(**kw):
    c = ls.new_car(0.0, 0.0)
    c.update(kw)
    return c


def drive(c, secs, jr=False, rain=False, s0=0.0, others=None):
    """Steps for `secs` seconds; `others(s)` gives the other cars at game time s."""
    evs = []
    for k in range(int(round(secs / ls.DT))):
        s = s0 + k * ls.DT
        evs += ls.step(c, s, jr, rain, others(s) if others else ())
    return evs


def straight(monkeypatch):
    """A track without corners (a long straight)."""
    monkeypatch.setattr(ls, "CORNERS", ())


def table(humans=(("1", 0),), bots=0, level="normal", solo=False, seed=7, rng_seed=1, **rules):
    players = [{"id": pid, "name": f"P{pid}", "team": team} for pid, team in humans]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "langstrecke", "rules": {**ls.DEFAULTS, "weather": 0, **rules}, "players": players, "phase": "lobby", "solo": solo}
    clock = Clock()
    t = ls.Table(st, random.Random(rng_seed), now=clock)
    t.setup(seed)
    return t, clock


def at(t, clock, s, seen=True):
    """The clock to game time s (the server simulates SETTLE behind) – everybody's app alive."""
    clock.t = t.st["t0"] + s + ls.SETTLE
    if seen:
        for pid in t.st["seen"]:
            t.st["seen"][pid] = clock.t
    t.tick()


def mine(t, pid="1"):
    return t.team_of(pid)


def to_line(t, team, metres=1.0):
    """Put the team's car in the pit lane just before the line (it crosses it in a step, then rolls to its box)."""
    car_ = team["car"]
    laps = ls.laps_of(car_["d"])
    car_.update(d=(laps + 1) * ls.L - metres, v=ls.PIT_V, x=ls.PL_X, sf=0, pl=1, ap=0)


def lap(c, s0=0.0, rain=False, limit=200.0):
    """Drives the car until it is in the pits: the events."""
    evs, k = [], 0
    while not c["pit"] and k * ls.DT < limit:
        evs += ls.step(c, s0 + k * ls.DT, False, rain)
        k += 1
    return evs


# ---------------------------------------------------------------- the circuit and the car
def test_the_circuit_has_real_corners_a_racing_line_and_closes():
    assert ls.L == 640.0 and len(ls.CORNERS) == 5
    assert sum(c[2] for c in ls.CORNERS) == 360.0                       # one clockwise loop
    for (a, b, ang, vs), nxt in zip(ls.CORNERS, ls.CORNERS[1:] + ((ls.L + ls.CORNERS[0][0],),)):
        assert ls.PIT_Z < a < b < nxt[0] and 10 <= vs <= 26 and ang
    assert min(c[3] for c in ls.CORNERS) == 13.0                        # the hairpin
    assert ls.corner_at(100.0) == ls.CORNERS[0] and ls.corner_at(180.0) is None
    assert ls.next_corner(100.0) == (ls.CORNERS[0], 0.0) and ls.next_corner(600.0) == (ls.CORNERS[0], 130.0)
    # the line: outside before the corner, the apex inside in its middle, never off the track, no jumps
    a, b, ang, _ = ls.CORNERS[2]                                         # the hairpin turns right: outside = left (−)
    assert ls.race_line(a) == pytest.approx(-ls.LINE_OUT) and ls.race_line((a + b) / 2) == pytest.approx(ls.LINE_APEX)
    ys = [ls.race_line(x / 2) for x in range(int(ls.L * 2))]
    assert all(abs(y) <= ls.LMAX < ls.HW for y in ys) and max(abs(p - q) for p, q in zip(ys, ys[1:])) < 0.5
    # rain and the wrong tyres lower every corner's safe speed
    c = ls.CORNERS[0]
    assert ls.safe_speed(c, "s", False) == 20.0 and ls.safe_speed(c, "r", True) == pytest.approx(20 * ls.RAIN_C)
    assert ls.safe_speed(c, "s", True) == pytest.approx(20 * ls.RAIN_C * ls.WET_SLICK) and ls.safe_speed(c, "r", False) == pytest.approx(18.0)


def _parity_cases():
    rng = random.Random(4)
    cases = []
    for n in range(8):
        ev, t = ([[0.0, "m", 1]] if n >= 5 else []), 0.0     # 5–7: manual gears – every gear, R at speed (grinding), N, junk
        while t < 120:
            t = round(t + rng.uniform(0.1, 1.5), 3)
            c = rng.choice("sssuuua" if n < 5 else "ssuuuggggm")
            ev.append([t, c, rng.randint(-100, 100) if c == "s" else rng.choice((-1, 0, 1, 1)) if c == "u"
                       else rng.choice((-1, 0, 1, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, -2)) if c == "g" else rng.choice((0, 1, 1))])
        # recorded other cars: a column at 26 m/s, and (case 4) a slow car to catch up with
        others = [[[-30 + 8 * k + 26 * s / 10, (k - 1) * 1.5, 26.0] for k in range(3)] + ([[15 + 6 * s / 10, xo, 6.0] for xo in (-3.5, 0.0, 3.5)] if n == 4 else [])
                  for s in range(1300)] if n in (2, 3, 4, 7) else None
        cases.append({"ev": ev, "rain": [[30, 60]] if n % 2 else [], "tyre": "r" if n in (1, 6) else "s", "bat": (100.0, 55.0, 30.0, 70.0, 100.0, 100.0, 80.0, 100.0)[n],
                      "jr": n == 3, "others": others, "keep": n in (0, 5)})    # 0, 5: the driver keeps right and steers into the pit lane
    return cases


def test_the_app_runs_exactly_the_same_step_on_recorded_inputs():
    """Python and the app's leStep() on the same recorded inputs (steering, pedals, the assist on / off, manual gears with
    every gear, N, R at speed and from a standstill, invalid gears) and the same recorded other cars: the same events and
    the same numbers, step by step."""
    src = (WEB / "langstrecke.js").read_text(encoding="utf-8").split("// ---------------------------------------------------------------- the rules, the start")[0]
    cases = _parity_cases()
    keys = list(ls.new_car(0.0, 0.0))
    code = "const T = s => s;\n" + src + "\nconst {cases, keys} = JSON.parse(require('fs').readFileSync(0, 'utf8')), out = [];\n" + """
for (const c of cases) { const car = {...c.car};
  const trace = [], evs = [];
  let i = 0;
  for (let k = 0; k < 1300; k++) { const s = k / 10;
    while (i < c.ev.length && c.ev[i][0] <= s + 1e-9) { leApply(car, c.ev[i][1], c.ev[i][2]); i++; }
    if (c.keep && car.pl === 0 && car.d > 0 && leLapPos(car.d) >= 560) leApply(car, "s", 60);
    for (const e of leStep(car, s, c.jr, leInWin(c.rain, s), c.others ? c.others[k] : [])) evs.push([k, e]);
    if (car.pit) { car.pit = 0; car.eng = 0; car.bat = c.bat; car.pl = 3; car.ap = 0; }
    if (k % 10 === 0) trace.push(keys.map(x => car[x])); }
  out.push([trace, evs]); }
console.log(JSON.stringify(out));"""
    for n, c in enumerate(cases):                                       # the same car to begin with (its box: team n)
        c["car"] = {**ls.new_car(-2.5, -5.0), "tyre": c["tyre"], "bat": c["bat"], "box": ls.box_of(n % 8)}
    js = json.loads(subprocess.run(["node", "-e", code], input=json.dumps({"cases": cases, "keys": keys}), capture_output=True, text=True,
                                   timeout=120, check=True).stdout)
    seen = set()
    for c, (jtrace, jevs) in zip(cases, js):
        cr = dict(c["car"])
        trace, evs, i = [], [], 0
        for k in range(1300):
            s = k / 10
            while i < len(c["ev"]) and c["ev"][i][0] <= s + 1e-9:
                ls.apply_input(cr, c["ev"][i][1], c["ev"][i][2])
                i += 1
            if c["keep"] and cr["pl"] == 0 and cr["d"] > 0 and ls.lap_pos(cr["d"]) >= 560:
                ls.apply_input(cr, "s", 60)
            for e in ls.step(cr, s, c["jr"], ls.in_window(c["rain"], s), c["others"][k] if c["others"] else ()):
                evs.append([k, e])
            if cr["pit"]:
                cr.update(pit=0, eng=0, bat=c["bat"], pl=3, ap=0)
            if k % 10 == 0:
                trace.append([cr[x] for x in keys])
        assert evs == jevs, c["bat"]
        seen |= {e for _, e in evs}
        for a, b in zip(trace, jtrace):
            for x, y, key in zip(a, b, keys):
                if isinstance(x, float) or isinstance(y, float):
                    assert abs(float(x) - float(y)) < 1e-9, (key, x, y)
                else:
                    assert x == y, (key, x, y)
    assert {"lap", "pit", "kerb", "off", "empty", "bump", "grind", "blow", "pitlane", "autopilot"} <= seen


def test_steering_is_smooth_and_moves_the_car_across_the_track(monkeypatch):
    straight(monkeypatch)
    c = car(v=20.0, d=50.0)
    ls.apply_input(c, "s", 100)
    drive(c, 0.1)
    assert 0 < c["sw"] <= ls.WHEEL * ls.DT + 1e-9 < 1 and c["x"] < 0.5      # the wheel turns over a few steps, no jump
    drive(c, 0.5, s0=0.1)
    assert c["sw"] == pytest.approx(1.0) and c["x"] > 1.5
    ls.apply_input(c, "s", 0)
    x = c["x"]
    drive(c, 0.5, s0=0.6)
    assert c["sw"] == pytest.approx(0.0) and x < c["x"] < x + 1.0        # straight on again
    ls.apply_input(c, "s", -999)
    assert c["st"] == -100                                              # bounded
    drive(c, 5, s0=1.1)
    assert c["x"] == -ls.XMAX and c["sf"] == 2 and c["offs"] == 1 and c["v"] <= ls.VGRASS + 1e-9   # the tyre wall: no crash
    slow = car(v=0.0, d=50.0, st=100, sw=1.0)
    drive(slow, 0.1)
    assert abs(slow["x"]) < 0.2                                         # standing: the steering hardly moves the car


def test_full_throttle_heats_the_engine_it_overheats_and_limps(monkeypatch):
    straight(monkeypatch)
    c = car(thr=1, d=10.0)
    drive(c, 12)
    assert not c["eng"] and c["temp"] > ls.YELLOW and abs(c["v"] - ls.VFULL) < 1e-6
    evs = drive(c, 5)
    assert "blow" in evs and c["eng"] and c["blows"] == 1 and 60 <= c["temp"] <= 80
    drive(c, 3)
    assert c["v"] == pytest.approx(ls.VLIMP) and c["temp"] < 80          # limping: slow, the engine cools
    a, j = car(thr=1, d=10.0), car(thr=1, d=10.0)                       # lifting off cools, juniors heat slower
    drive(a, 8)
    drive(j, 8, jr=True)
    assert j["temp"] < a["temp"]
    a["thr"] = 0
    t0 = a["temp"]
    drive(a, 2)
    assert a["temp"] < t0 and a["v"] < ls.VFULL


def test_the_battery_drains_much_faster_at_full_throttle_braking_gives_a_little_back(monkeypatch):
    straight(monkeypatch)
    full, lifted = car(thr=1, d=10.0, v=ls.VFULL), car(thr=0, d=10.0, v=ls.VLIFT)
    drive(full, 4)
    drive(lifted, 4)
    used_full, used_lift = 100 - full["bat"], 100 - lifted["bat"]
    assert used_full == pytest.approx(ls.E_FULL * ls.VFULL * 4, rel=0.01) and used_lift == pytest.approx(ls.E_LIFT * ls.VLIFT * 4, rel=0.01)
    per_m = (used_full / (full["d"] - 10)), (used_lift / (lifted["d"] - 10))
    assert per_m[0] > 2 * per_m[1]                                       # per metre more than twice as much
    assert ls.E_FULL * ls.L > 100 > ls.E_LIFT * ls.L * 1.5               # flat out a full battery does not last a lap, lifted easily
    b = car(thr=-1, d=10.0, v=ls.VFULL, bat=50.0)                       # braking gives a little back
    drive(b, 0.5)
    assert b["bat"] > 50.0 and b["v"] < ls.VFULL
    e = car(thr=-1, d=10.0, v=ls.VFULL, bat=0.0)                        # an empty battery stays empty
    drive(e, 1)
    assert e["bat"] == 0.0


def test_an_empty_battery_means_the_emergency_drive_mode(monkeypatch):
    straight(monkeypatch)
    c = car(thr=1, d=10.0, v=ls.VFULL, bat=2.0)
    evs = drive(c, 1)
    assert evs.count("empty") == 1 and c["bat"] == 0 and c["flat"] == 1
    drive(c, 6)
    assert c["v"] == pytest.approx(ls.VEMERG) and not c["eng"]          # it crawls – full throttle does nothing any more
    t0 = c["temp"]
    drive(c, 2)
    assert c["temp"] <= t0
    evs = drive(c, 120)
    assert "pit" in evs and c["pit"] and "empty" not in evs and c["flat"] == 1    # no retirement: it crawls into the pits


def test_rain_slicks_and_rain_tyres_on_the_straight(monkeypatch):
    straight(monkeypatch)
    speed = {}
    for tyre in ("s", "r"):
        for rain in (False, True):
            c = car(thr=0, tyre=tyre, d=10.0)
            drive(c, 6, rain=rain)
            speed[tyre, rain] = c["v"]
    assert speed["s", False] == pytest.approx(ls.VLIFT) and speed["r", True] == pytest.approx(ls.VLIFT)
    assert speed["s", True] == pytest.approx(ls.VLIFT * ls.WET_SLICK) and speed["r", False] == pytest.approx(ls.VLIFT * ls.DRY_RAIN)


def test_a_corner_too_fast_runs_wide_onto_the_kerb_and_the_grass_and_slows_down_hard():
    a, b, ang, vs = ls.CORNERS[2]                                         # the hairpin (right): safe 13 m/s
    fast = car(d=a - 2, v=24.0, x=-ls.LINE_OUT, thr=1, st=100, sw=1.0)   # flat out, steering into it with full lock
    evs, xs, vs_ = [], [], []
    for k in range(30):
        evs += ls.step(fast, k * ls.DT, False)
        xs.append(fast["x"])
        vs_.append(fast["v"])
    assert evs.index("kerb") < evs.index("off") and min(xs) < -ls.HW - ls.KERB and fast["offs"] == 1
    assert min(vs_) <= ls.VGRASS + 1e-9 and "pit" not in evs              # a heavy slowdown – no crash, no retirement
    back = []
    for k in range(30, 40):                                             # slow on the grass the steering wins: back on the track
        ls.step(fast, k * ls.DT, False)
        back.append((fast["sf"], fast["v"]))
    assert back[-1][0] == 0 and back[-1][1] > ls.VGRASS + 3
    # at the safe speed the same corner with the right steering stays on the track (the assist steers here)
    ok = car(d=a - 40, v=vs * 0.95, x=-ls.LINE_OUT, thr=0, ast=1)
    evs = drive(ok, 7)
    assert "off" not in evs and ok["sf"] == 0 and ls.lap_pos(ok["d"]) > b
    # the push grows with the speed: the same steering, faster → further out
    xs = []
    for v in (8.0, 12.0, 16.0):
        c = car(d=a, v=v, x=0.0, thr=0)
        drive(c, 0.8)
        xs.append(c["x"])
    assert xs[0] > xs[1] > xs[2] and xs[2] < -1.5
    # in the rain the safe speed drops: a speed fine in the dry runs wide in the rain on slicks
    dry, wet = car(d=a - 40, v=vs * 0.95, x=-ls.LINE_OUT, ast=1, ak=1.0), car(d=a - 40, v=vs * 0.95, x=-ls.LINE_OUT, ast=0, st=0)
    assert "off" not in drive(dry, 5)
    wet.update(ast=1, ak=1.0)
    wet_evs = drive(wet, 5, rain=True)
    assert "off" not in wet_evs and wet["v"] < dry["v"] + 1e-9           # the assist brakes harder for the rain


def test_the_slipstream_gives_more_speed_on_a_straight(monkeypatch):
    straight(monkeypatch)
    alone, behind = car(d=100.0, v=ls.VFULL, thr=1), car(d=100.0, v=ls.VFULL, thr=1)
    ahead = lambda s: [[118.0 + ls.VFULL * 1.1 * s, 0.3, ls.VFULL * 1.1]]   # 18 m ahead, a bit faster (it stays ahead)  # noqa: E731
    drive(alone, 3)
    drive(behind, 3, others=ahead)
    assert alone["v"] == pytest.approx(ls.VFULL) and alone["tow"] == 0
    assert behind["v"] > ls.VFULL + 1.0 and behind["tow"] > 0 and behind["d"] > alone["d"] + 3
    side = car(d=100.0, v=ls.VFULL, thr=1, x=3.0)                       # not behind it (to the side): no slipstream
    drive(side, 3, others=ahead)
    assert side["v"] == pytest.approx(ls.VFULL) and side["tow"] == 0
    # not in a corner
    monkeypatch.setattr(ls, "CORNERS", ((90.0, 400.0, 90.0, 40.0),))
    bend = car(d=100.0, v=ls.VFULL, thr=1, ast=1, ak=1.0, x=ls.race_line(100.0))
    drive(bend, 1, others=lambda s: [[110.0 + ls.VFULL * s, bend["x"], ls.VFULL]])
    assert bend["tow"] == 0


def test_running_into_a_car_is_a_gentle_bump_never_through_it(monkeypatch):
    straight(monkeypatch)
    c = car(d=100.0, v=ls.VFULL, thr=1)
    evs = []
    for k in range(40):
        s = k * ls.DT
        other = [120.0 + 15.0 * s, 0.5, 15.0]
        evs += ls.step(c, s, False, False, [other])
        if c["d"] >= other[0] + 15.0 * ls.DT:                           # never through it: only beside it
            assert abs(c["x"] - 0.5) >= ls.CAR_W - 0.2
    assert "bump" in evs and c["bumps"] >= 1 and "off" not in evs
    assert c["x"] < -0.5                                                 # pushed aside a little (it is right of the middle)
    ls.apply_input(c, "s", -60)                                          # steering past it: overtaking works
    drive(c, 4, s0=4.0, others=lambda s: [[120.0 + 15.0 * s, 0.5, 15.0]])
    assert c["d"] > 120.0 + 15.0 * 8
    # no contact in the pit lane (the cars come out of the pits together)
    p = car(d=640.0 + 5.0, v=10.0, thr=1)
    assert "bump" not in drive(p, 0.5, others=lambda s: [[648.0, 0.0, 2.0]])


def test_the_assist_keeps_a_junior_on_the_track_and_brakes_for_every_corner():
    """Full throttle all lap, no steering at all: with the assist the car stays on the track in every corner (dry and
    in the rain, with the right or the wrong tyres); without it the first corner throws it off."""
    for rain, tyre in ((False, "s"), (True, "r"), (True, "s"), (False, "r")):
        c = ls.new_car(0.0, -5.0)
        c.update(ast=1, thr=1, tyre=tyre)
        surfaces = []
        k = 0
        while not c["pit"] and k < 1200:
            ls.step(c, k / 10, True, rain)
            surfaces.append(c["sf"])
            k += 1
        assert c["pit"] and c["offs"] == 0 and max(surfaces) <= 1, (rain, tyre)
        assert 20 < c["best"] < 50
    off = ls.new_car(0.0, -5.0)
    off["thr"] = 1
    evs = lap(off)
    assert "off" in evs and off["offs"] >= 1
    # the driver's own steering still counts: steering left with the assist moves the car left of the line
    c = car(d=20.0, v=20.0, ast=1)
    ls.apply_input(c, "s", -100)
    drive(c, 1)
    assert c["x"] < ls.race_line(ls.lap_pos(c["d"])) - 2


def test_every_lap_ends_in_the_pits_with_its_lap_time(monkeypatch):
    straight(monkeypatch)
    c = ls.new_car(0.0, -5.0)
    c["thr"] = 1
    evs = drive(c, 3)
    assert "pit" not in evs and c["ls"] > 0                               # crossing the line at the start: the first lap begins
    evs = drive(c, 40, s0=3.0)
    assert evs.count("lap") == 1 and "pit" in evs and c["pit"] and c["d"] == ls.L + c["box"] and c["v"] == 0     # stopped at its box
    assert c["pl"] == 2 and abs(c["x"] - ls.PL_X) <= ls.PL_HW and evs.index("pitlane") < evs.index("lap") < evs.index("pit")
    assert 18 < c["best"] < 45 and c["last"] == c["best"]


# ---------------------------------------------------------------- the pit lane: in on the right, the limiter, the box, out again
def to_entry(c, laps=1):
    """Before the pit entry on the main straight (the lap's last metres), a little left of the middle."""
    c.update(d=laps * ls.L + 560.0, x=-2.0, v=22.0, sf=0, pl=0, ap=0, ls=float(laps * 30))


def run_in(c, s0=0.0, each=None, limit=30.0):
    """Steps until the car stands at its box: the events and a trace (pl, ap, d, x, v)."""
    evs, trace, k = [], [], 0
    while not c["pit"] and k * ls.DT < limit:
        if each:
            each(c)
        evs += ls.step(c, s0 + k * ls.DT, False)
        trace.append((c["pl"], c["ap"], c["d"], c["x"], c["v"]))
        k += 1
    return evs, trace


def test_without_steering_in_the_autopilot_takes_the_car_into_the_pits():
    """Nobody can miss the pits: no steering (and no assist) at the entry line – the autopilot steers right into the pit
    lane smoothly, slows to the pit speed and the car stops at its box; the driver's own inputs do not count meanwhile."""
    c = car(thr=1, box=ls.box_of(2))
    to_entry(c)
    evs, tr = run_in(c, each=lambda c_: c_.update(thr=1, st=-100 if c_["pl"] else 0))   # in the lane it even steers left
    assert evs[:2] == ["pitlane", "autopilot"] and evs.count("lap") == 1 and evs[-1] == "pit" and "off" not in evs
    assert c["pit"] and c["d"] == ls.L * 2 + ls.box_of(2) and c["v"] == 0 and c["ap"] == 0     # its own box, the stop begins
    lane = [x for pl, ap, d, x, v in tr if pl and ls.pit_z(d, pl) >= ls.PZ_IN + ls.PIT_ENTRY]
    assert lane and all(ls.PL_X - ls.PL_HW - 1e-9 <= x <= ls.PL_X + ls.PL_HW + 1e-9 for x in lane)   # between the pit wall and the boxes
    xs = [x for *_, x, _ in tr]
    assert max(abs(a - b) for a, b in zip(xs, xs[1:])) < 1.0                               # smooth – no jump into the lane
    assert all(v <= ls.PIT_V + 1e-9 for pl, ap, d, x, v in tr if pl and ls.pit_z(d, pl) >= ls.PZ_IN + ls.PIT_ENTRY)
    assert all(ap == 1 for pl, ap, *_ in tr[:-1] if pl)                                    # the autopilot until the box


def test_the_driver_steers_into_the_pit_lane_by_hand():
    """Keeping right (the hint «Pit lane – keep right») and steering right at the entry: no autopilot – the driver steers
    in, the joystick keeps working in the lane (between the pit wall and the boxes), the car rolls into its box."""
    c = car(thr=1, box=ls.box_of(0))
    to_entry(c)
    c["x"] = 3.0
    evs, tr = run_in(c, each=lambda c_: c_.update(st=70 if c_["pl"] < 2 else -40))
    assert "pitlane" in evs and "autopilot" not in evs and evs[-1] == "pit" and c["d"] == 2 * ls.L + ls.box_of(0)
    assert all(ap == 0 for _, ap, *_ in tr)
    after = [(d, x) for pl, ap, d, x, v in tr if pl == 2]
    assert after and min(x for _, x in after) >= ls.PL_X - ls.PL_HW - 1e-9            # steering left: the pit wall stops it
    # steering in late: the autopilot still takes over before the pit wall
    late = car(thr=1)
    to_entry(late)
    late["x"] = 2.0
    evs, tr = run_in(late, each=lambda c_: c_.update(st=0))
    assert evs[:1] == ["pitlane"] and "autopilot" in evs and late["pit"]


def test_the_pit_limiter_holds_the_speed_automatic_and_manual_without_a_penalty():
    for man, gear in ((0, 1), (1, 4), (1, 6)):
        c = car(thr=1, man=man, gear=gear)
        to_entry(c)
        c["x"] = 3.0
        temps = []
        evs, tr = run_in(c, each=lambda c_: (c_.update(thr=1, st=60 if c_["pl"] < 2 else 0), temps.append(c_["temp"])))
        lane = [v for pl, ap, d, x, v in tr if pl and ls.pit_z(d, pl) >= ls.PZ_IN + 15]
        assert lane and max(lane) <= ls.PIT_V + 1e-9, man                 # braked down to the limit, held there (full throttle)
        assert "off" not in evs and "blow" not in evs and c["pit"]
        assert c["man"] == man and c["gear"] == gear or man == 0            # manual stays manual (no penalty, no shifting)
    # out of the box: limited to the pit exit, then full speed again – and racing (pl 0) after the merge
    c = car(thr=1, pl=3, d=ls.L + ls.box_of(1), x=ls.PL_X, v=0.0)
    vs = []
    for k in range(80):
        ls.step(c, k * ls.DT, False)
        vs.append((ls.lap_pos(c["d"]), c["v"], c["pl"], c["x"]))
    assert all(v <= ls.PIT_V + 1e-9 for xl, v, pl, x in vs if xl < ls.PIT_OUT)
    assert c["pl"] == 0 and c["v"] > ls.PIT_V + 3 and 0 < c["x"] <= ls.HW                   # back on the track, its right side
    assert all(x >= ls.pit_bounds(xl)[0] - 1.0 for xl, v, pl, x in vs if pl)             # merging along the exit lane


def test_no_contact_between_the_pit_lane_and_the_track():
    t, clock = table(humans=(("1", 0),), bots=1)
    at(t, clock, 3)
    me, bot = mine(t), next(x for x in t.st["teams"] if x["bot"])
    # my car leaves the pits slowly on the exit lane, the bot comes along the track behind it at full speed, same line
    me["car"].update(d=ls.L + 66.0, x=5.0, v=4.0, pl=3, thr=0, st=0)
    bot["car"].update(d=ls.L + 50.0, x=5.0, v=ls.VFULL, pl=0, ast=0)
    s = t.sim_t()
    t.report("1", [[t.gt(), "u", 0]])
    at(t, clock, s + 1.2)
    assert me["car"]["bumps"] == 0 and bot["car"]["bumps"] == 0
    # a car on the pit entry is never in the others' view – and it sees nobody
    c = car(d=ls.L + 600.0, x=4.0, v=20.0, pl=1)
    assert "bump" not in drive(c, 0.5, others=lambda s: [[ls.L + 603.0 + 5 * s, 4.0, 5.0]]) and c["tow"] == 0


def test_the_lap_time_and_the_line_are_unchanged_by_the_pit_lane():
    """The line crosses the track and the pit lane: the lap ends where it always did (d = n·L), its time is taken at the
    moment of the crossing (within the step) – the pit lane's metres are the lap's metres beside it, d never jumps."""
    c = ls.new_car(0.0, -5.0)
    c.update(thr=1, ast=1)
    s, prev, crossings = 0.0, None, []
    for k in range(2000):
        d0, v_before = c["d"], c["v"]
        evs = ls.step(c, s, False)
        if c["d"] < d0 - 1e-9:
            raise AssertionError("d jumped back")
        assert c["d"] - d0 <= ls.VFULL * ls.DT + 1e-9                     # no jump forward either (into the pits)
        if math.floor(c["d"] / ls.L) > math.floor(d0 / ls.L) and d0 >= 0:
            assert "lap" in evs and c["pl"] == 2
            tc = s + (math.floor(c["d"] / ls.L) * ls.L - d0) / ((c["d"] - d0) / ls.DT)
            assert c["ls"] == ls._r2(tc)
            if prev is not None:
                assert c["last"] == ls._r2(tc - prev)
            prev = c["ls"]
            crossings.append(c["d"])
        else:
            assert "lap" not in evs
        if c["pit"]:
            c.update(pit=0, pl=3, bat=100.0, temp=60.0)
        s += ls.DT
    assert len(crossings) >= 3 and ls.laps_of(c["d"]) == len(crossings)


def test_the_app_runs_the_same_pit_lane():
    """leStep in node and step() on the pit entry (autopilot and by hand), the limiter, the box and the exit."""
    cases = []
    for k, (x, st, man, gear) in enumerate(((-3.0, 0, 0, 1), (3.0, 60, 0, 1), (2.0, 0, 1, 3), (-6.0, 100, 1, 5))):
        c = car(thr=1, man=man, gear=gear, box=ls.box_of(k), ast=k % 2)
        to_entry(c)
        c.update(x=x, st=st)
        cases.append(c)
    out = _app_js("""const res = data.map(c => { const tr = [], evs = [];
      for (let k = 0; k < 400; k++) { for (const e of leStep(c, k / 10, false, false, [])) evs.push([k, e]);
        if (c.pit) { c.pit = 0; c.pl = 3; } tr.push([c.d, c.x, c.v, c.pl, c.ap, c.sw, c.temp, c.bat]); }
      return [tr, evs]; });
      console.log(JSON.stringify(res));""", cases)
    for c, (jtr, jevs) in zip(cases, out):
        evs, tr = [], []
        for k in range(400):
            evs += [[k, e] for e in ls.step(c, k / 10, False, False, ())]
            if c["pit"]:
                c.update(pit=0, pl=3)
            tr.append([c["d"], c["x"], c["v"], c["pl"], c["ap"], c["sw"], c["temp"], c["bat"]])
        assert evs == jevs and {"pitlane", "lap", "pit"} <= {e for _, e in evs}
        for a, b in zip(tr, jtr):
            assert all(abs(p - q) < 1e-9 for p, q in zip(a, b)), (a, b)


def test_bots_take_the_same_pit_lane_into_their_own_boxes():
    seen = []
    orig = ls.step

    def spy(car_, s, jr, rain=False, others=()):
        evs = orig(car_, s, jr, rain, others)
        if "pit" in evs:
            seen.append((car_["box"], ls.lap_pos(car_["d"]), car_["x"]))
        if "autopilot" in evs:
            seen.append(("ap", car_["box"]))
        return evs
    t, clock = table(humans=(("1", 0),), bots=3, level="hard", minutes=5)
    boxes = [x["car"]["box"] for x in t.st["teams"]]
    assert sorted(boxes) == [ls.box_of(i) for i in range(4)]             # one box per team
    ls.step = spy
    try:
        for s in range(2, 120, 2):
            at(t, clock, s, seen=False)
    finally:
        ls.step = orig
    stops = [x for x in seen if x[0] != "ap"]
    bot_boxes = {x["car"]["box"] for x in t.st["teams"] if x["bot"]}
    assert len(stops) >= 6 and all(abs(xl - box) < 1e-6 and abs(x - ls.PL_X) <= ls.PL_HW for box, xl, x in stops)
    assert not any(x[1] in bot_boxes for x in seen if x[0] == "ap")       # bots keep right and steer in themselves


def test_race_clock_day_and_night_and_frequent_showers():
    assert ls.race_hour(0, 480) == 15 and ls.darkness(0, 480) == 0 and ls.darkness(240, 480) == 1
    plan = ls.rain_plan(random.Random(3), 480)
    assert len(plan) >= 3 and plan[0][0] >= 35 and all(30 <= round(b - a) <= 55 for a, b in plan[:-1]) and plan[-1][1] <= 480
    t, _ = table(weather=1)
    assert t.st["rain"]
    t, _ = table(weather=0)
    assert t.st["rain"] == []


def test_bots_drive_the_racing_line_their_laps_in_a_time_range_by_skill():
    times, offs = {}, {}
    for level in ("easy", "hard"):
        t, clock = table(humans=(("1", 0),), bots=3, level=level, minutes=5, weather=0, rng_seed=5)
        s = 0.0
        while t.st["phase"] == "play":
            s += 2.0
            at(t, clock, s, seen=False)
        bots = [x for x in t.st["teams"] if x["bot"]]
        laps = [lp["time"] for b in bots for lp in b["laps"]]
        assert all(len(b["laps"]) >= 6 for b in bots)
        assert all(24.0 <= x <= 60.0 for x in laps), level                   # every bot lap within a sensible time
        times[level] = sorted(laps)[len(laps) // 2]
        offs[level] = sum(b["car"]["offs"] for b in bots)
    assert 28.0 <= times["hard"] <= 40.0 and times["hard"] < times["easy"]       # the lap includes the pit lane (100 km/h) and the stop
    assert offs["hard"] <= offs["easy"]


def test_bots_overtake_a_slower_car():
    t, clock = table(humans=(("1", 0),), bots=1, level="hard")
    me, bot = mine(t), next(x for x in t.st["teams"] if x["bot"])
    at(t, clock, 5)
    me["car"].update(d=560.0, x=0.0, v=8.0, thr=-1, st=0, ast=0)        # I crawl on the straight
    bot["car"].update(d=520.0, x=0.0, v=ls.VFULL)
    t.report("1", [[t.gt(), "u", -1]])
    at(t, clock, 8.5)                                                   # (the automatic's shift gaps: half a second more)
    assert ls.lap_pos(bot["car"]["d"]) > ls.lap_pos(me["car"]["d"]) or bot["car"]["pit"]
    assert bot["car"]["lo"] != 0.0 or bot["car"]["bumps"] <= 1


# ---------------------------------------------------------------- teams, inputs, the crew's jobs
def test_teams_from_the_lobby_with_their_looks_and_bots():
    t, _ = table(humans=(("1", 0), ("2", 0), ("3", 1)), bots=2)
    ts = t.st["teams"]
    assert len(ts) == 4 and [x["members"] for x in ts[:2]] == [["1", "2"], ["3"]] and all(x["bot"] for x in ts[2:])
    assert [x["num"] for x in ts[:2]] == [7, 24] and ts[0]["color"] == ls.TEAM_STYLES[0][1]
    assert len({x["num"] for x in ts}) == 4 and len({x["color"] for x in ts}) == 4
    assert all(x["country"] in ls.COUNTRIES for x in ts[2:])
    looks = ls.default_looks("CH")
    looks[0].update(color=ls.TEAM_STYLES[5][1], num=99)
    players = [{"id": "1", "name": "A", "team": 0}, {"id": "bot1", "name": "B", "bot": True, "level": "normal"}]
    st = {"kind": "langstrecke", "rules": dict(ls.DEFAULTS), "players": players, "phase": "lobby", "looks": looks}
    ls.Table(st, random.Random(1), now=Clock()).setup(3)
    a, b = st["teams"]
    assert (a["color"], a["country"], a["num"]) == (ls.TEAM_STYLES[5][1], "CH", 99) and b["color"] != a["color"] and b["num"] != 99
    assert ls.default_looks("XX")[0]["country"] is None and ls.default_looks()[0]["country"] is None


def test_only_the_driver_steers_and_late_inputs_never_go_into_the_past():
    t, clock = table(humans=(("1", 0), ("2", 0)), bots=1)
    at(t, clock, 5)
    tm = mine(t)
    assert tm["driver"] == "1"
    assert t.report("2", [[5.0, "u", 1]]) == 0                           # the crew cannot drive
    assert t.report("1", [[1.0, "u", 1], [5.2, "s", -40], [99, "s", 0], [5.3, "b", 1]]) == 2
    assert tm["ev"][0][0] >= t.sim_t() and tm["ev"][0][1:] == ["u", 1] and tm["ev"][1][1:] == ["s", -40]
    with pytest.raises(CommunityError):
        t.report("bot1", [])


# ---------------------------------------------------------------- the gearbox (manual: H shifter, 6 gears, N, R)
def test_gear_bands_too_high_lugs_and_the_limiter_caps_and_heats(monkeypatch):
    straight(monkeypatch)
    assert len(ls.GEAR_TOP) == 6 and list(ls.GEAR_TOP) == sorted(ls.GEAR_TOP) and ls.GEAR_TOP[-1] == ls.VFULL
    for g in range(1, 7):                                               # flat out in a gear: up to its limiter, not beyond
        c = car(thr=1, d=10.0, v=ls.GEAR_LOW[g - 1], man=1, gear=g)
        drive(c, 8)
        assert c["v"] == pytest.approx(ls.GEAR_TOP[g - 1]), g
    lug, good = car(thr=1, d=10.0, v=4.0, man=1, gear=5), car(thr=1, d=10.0, v=4.0, man=1, gear=1)
    drive(lug, 0.5)
    drive(good, 0.5)
    assert lug["v"] - 4 == pytest.approx(ls.ACC * ls.GEAR_ACC[4] * ls.LUG * 0.5) and good["v"] - 4 > 2.5 * (lug["v"] - 4)
    on, off = car(thr=1, d=10.0, v=ls.GEAR_TOP[2], man=1, gear=3), car(thr=1, d=10.0, v=ls.VFULL)   # the limiter heats faster
    drive(on, 2)
    drive(off, 2)
    assert on["temp"] - ls.TMIN == pytest.approx((off["temp"] - ls.TMIN) * ls.LIM_HEAT) and on["v"] == pytest.approx(ls.GEAR_TOP[2])
    hot = car(thr=1, d=10.0, v=ls.GEAR_TOP[1], man=1, gear=2, temp=99.0)
    assert "blow" in drive(hot, 1) and hot["eng"] == 1                  # on the limiter into the red: the engine is gone
    down = car(thr=0, d=10.0, v=27.0, man=1, gear=3)                    # a downshift: engine braking, harder than lifting
    lift = car(thr=0, d=10.0, v=27.0)
    drive(down, 0.5)
    drive(lift, 0.5)
    assert down["v"] == pytest.approx(27.0 - ls.EBRAKE * 0.5) and lift["v"] == pytest.approx(27.0 - ls.COAST * 0.5)
    rain = car(thr=1, d=10.0, v=10.0, man=1, gear=3)                    # slicks in the rain: the limiter × grip
    drive(rain, 6, rain=True)
    assert rain["v"] == pytest.approx(ls.GEAR_TOP[2] * ls.WET_SLICK)


def test_neutral_has_no_drive_and_r_at_speed_grinds_then_drives_backwards(monkeypatch):
    straight(monkeypatch)
    n = car(thr=1, d=10.0, v=20.0, man=1, gear=0, bat=50.0)
    drive(n, 1)
    assert n["v"] == pytest.approx(20.0 - ls.NEUTRAL_DEC) and n["temp"] == ls.TMIN and n["bat"] == pytest.approx(50 - ls.E_LIFT * (19.85 * 1), abs=0.2)
    drive(n, 10)
    assert n["v"] == 0.0                                                # neutral: no gas helps, it rolls out
    # R while rolling at 25 m/s: a much harder stop than the brake, the engine heats fast – from warm it is gone
    r, b = car(thr=0, d=10.0, v=25.0, man=1, gear=-1, temp=70.0), car(thr=-1, d=10.0, v=25.0)
    evs = drive(r, 0.5)
    drive(b, 0.5)
    assert r["v"] == pytest.approx(25.0 - ls.GRIND_DEC * 0.5) and 25.0 - r["v"] > 1.5 * (25.0 - b["v"]) and "grind" in evs
    assert r["temp"] == pytest.approx(70.0 + ls.GRIND_HEAT * 0.5)
    evs = drive(r, 1.0)
    assert "blow" in evs and r["eng"] == 1 and r["blows"] == 1          # counted like an overheat: the spare engine
    assert r["v"] <= 0.0
    # from a standstill R drives slowly backwards (gas faster, lifted creeps, the brake stops) – never over the line
    rv = car(thr=1, d=10.0, v=0.0, man=1, gear=-1)
    assert "grind" not in drive(rv, 2)
    assert rv["v"] == pytest.approx(-ls.VREV) and rv["d"] < 10.0 and rv["temp"] < 61
    rv["thr"] = 0
    drive(rv, 1)
    assert rv["v"] == pytest.approx(-ls.VCREEP)
    rv["thr"] = -1
    drive(rv, 1)
    assert rv["v"] == 0.0
    line = car(thr=1, d=ls.L + 0.5, v=0.0, man=1, gear=-1, ls=10.0)
    drive(line, 3)
    assert line["d"] == ls.L and line["v"] == 0.0                       # no lap twice by backing over the line
    ls.apply_input(line, "g", 1)
    assert "lap" not in drive(line, 2) and line["d"] > ls.L
    auto = car(thr=1, d=10.0, v=20.0, gear=-1)                          # automatic: the gear input does nothing
    drive(auto, 1)
    assert auto["v"] > 20.0


def test_good_manual_shifting_is_a_little_faster_automatic_is_never_bad():
    def run(man, rain=False, wrong=False):
        c = car(ast=1, thr=1, man=man, gear=1)
        laps, s = [], 0.0
        while len(laps) < 2:
            if man:
                gr = ls.grip(c["tyre"], rain)
                c["gear"] = 6 if wrong else next((i + 1 for i, t in enumerate(ls.GEAR_TOP) if c["v"] < t * gr - 0.4), 6)
            evs = ls.step(c, s, False, rain)
            if "lap" in evs:
                laps.append(c["last"])
            if "pit" in evs:                                            # at the box: out again at once (pit lane, exit)
                c.update(pit=0, pl=3, temp=60.0, bat=100.0, eng=0, gear=1)
            s += ls.DT
        return laps[-1], c["blows"]
    for rain in (False, True):
        (auto, b0), (man, b1) = run(0, rain), run(1, rain)
        assert b0 == b1 == 0 and 0.01 <= (auto - man) / auto <= 0.03, (rain, auto, man)
    slow, _ = run(1, wrong=True)
    assert slow > run(0)[0] * 1.15                                      # sixth gear all lap: much slower than automatic
    assert [ls.auto_gear(v) for v in (0.0, 8.0, 12.0, 30.0)] == [1, 1, 2, 6]


def test_the_automatic_shifts_up_at_90_percent_with_a_torque_gap_never_into_the_red(monkeypatch):
    straight(monkeypatch)
    c = car(thr=1, d=10.0, v=0.0)
    gears, trace = [], []
    for k in range(120):
        before = c["gear"]
        ls.step(c, k * ls.DT, False)
        trace.append((before, c["gear"], c["v"]))
    ups = [(i, v) for i, (a, b, v) in enumerate(trace) if b == a + 1]
    assert [b for _, (a, b, _) in [(i, trace[i]) for i, _ in ups]] == [2, 3, 4, 5, 6]
    for i, _ in ups:                                                   # shifted at 90 % of the old gear's top – never in the red
        a, b, v = trace[i]
        v0 = trace[i - 1][2]
        assert ls.GEAR_TOP[a - 1] * ls.AUTO_UP <= v0 < ls.GEAR_TOP[a - 1] * 0.97
        gap = [trace[j][2] for j in range(i, i + round(ls.AUTO_GAP / ls.DT))]
        assert all(abs(x - v0) < 1e-9 for x in gap) and trace[i + round(ls.AUTO_GAP / ls.DT)][2] > v0   # no drive in the gap, then on
    assert c["v"] == pytest.approx(ls.VFULL) and c["gear"] == 6
    m = car(thr=1, d=10.0, v=0.0, man=1, gear=1)                        # a hand: up at the limiter, no gap – sooner at full speed
    t_auto = next(i for i, x in enumerate(trace) if x[2] >= 25.0)
    for k in range(120):
        m["gear"] = next((i + 1 for i, t in enumerate(ls.GEAR_TOP) if m["v"] < t - 0.4), 6)
        ls.step(m, k * ls.DT, False)
        if m["v"] >= 25.0:
            break
    assert k < t_auto - 3
    hunt = car(thr=0, d=10.0, v=ls.GEAR_TOP[2] * ls.AUTO_UP - 0.05, gear=3)   # no hunting: a little slower stays in the gear
    hunt["thr"] = -1
    ls.step(hunt, 0.0, False)
    assert hunt["gear"] == 3


def test_switching_a_m_mid_stint_engages_the_fitting_gear_without_a_jolt_remembered_per_driver():
    t, clock = table(humans=(("1", 0), ("2", 0)), bots=1)
    at(t, clock, 3)
    tm = mine(t)
    t.report("1", [[t.gt(), "u", 1]])
    at(t, clock, 8)
    c = tm["car"]
    v0, x0 = c["v"], c["x"]
    assert c["man"] == 0 and v0 > 5
    t.report("1", [[t.gt(), "m", 1]])                                   # to manual, flat out: the gear that fits the speed
    at(t, clock, 8.1)
    assert c["man"] == 1 and c["gear"] == ls.auto_gear(v0) or c["gear"] == ls.auto_gear(c["v"])
    assert abs(c["v"] - v0) < 2.5 and t.st["manual"] == {"1": True}     # no jolt
    t.report("1", [[t.gt(), "m", 0]])                                   # and back, mid-stint
    at(t, clock, 8.2)
    assert c["man"] == 0 and t.st["manual"] == {"1": False}
    t.report("1", [[t.gt(), "m", 1]])
    at(t, clock, 8.3)
    # the next stint: the next driver (no choice yet) automatic, then driver 1 again with manual from 1st
    for nxt, man in (("2", 0), ("1", 1)):
        tm["stop"] = {"end": 0, "tyre": "s", "bat_in": 90.0, "bat_out": 10.0, "n": 1, "time": 3.0, "change": True, "garage": False,
                      "eng": False, "t": 0, "prev": tm["driver"], "next": nxt}
        tm["car"].update(pit=1, gear=4)
        t._release(tm)
        assert tm["driver"] == nxt and tm["car"]["man"] == man and tm["car"]["gear"] == 1


def test_gear_inputs_are_validated_and_the_choice_is_remembered_bots_never_shift():
    t, clock = table(humans=(("1", 0), ("2", 0)), bots=1)
    at(t, clock, 5)
    tm = mine(t)
    now = t.gt()
    assert tm["car"]["man"] == 0 and tm["car"]["gear"] >= 1            # automatic: it picks the gear itself
    assert t.report("1", [[now, "g", 7], [now, "g", -2], [now, "g", 2.5], [now, "g", "x"], [now, "m", 5], [now, "g", 3], [now, "g", -1], [now, "g", 0]]) == 5
    assert [e[1:] for e in tm["ev"][-5:]] == [["g", 2], ["m", 1], ["g", 3], ["g", -1], ["g", 0]]
    assert t.st["manual"] == {"1": True}
    at(t, clock, 6)
    assert tm["car"]["man"] == 1 and tm["car"]["gear"] == 0
    bot = next(x for x in t.st["teams"] if x["bot"])
    for s in range(7, 40):
        at(t, clock, s)
        assert bot["car"]["man"] == 0 and "grind" not in str(t.st["log"])
    # the next stint of a manual driver starts in 1st; the autopilot drives automatic
    tm["stop"] = {"end": 0, "tyre": "s", "bat_in": 90.0, "bat_out": 10.0, "n": 1, "time": 3.0, "change": True, "garage": False,
                  "eng": False, "t": 0, "prev": "1", "next": "1"}
    tm["car"].update(pit=1, gear=4)
    t._release(tm)
    assert tm["car"]["man"] == 1 and tm["car"]["gear"] == 1


def test_the_drivers_inputs_are_validated_and_bounded():
    t, clock = table(humans=(("1", 0), ("2", 0)), bots=1)
    at(t, clock, 5)
    tm = mine(t)
    now = t.gt()
    bad = [[now, "l", 0], [now, "r", 0], [now, "x", 1], [float("nan"), "s", 10], [float("inf"), "u", 1], [now, "s", float("inf")],
           [now, "s", float("nan")], [now, "u"], ["soon", "u", 1], [now], [], None, [now + 5, "u", 1]]
    assert t.report("1", bad) == 1 and tm["ev"][-1][1:] == ["u", 0]     # only [now, "u"] (value missing = 0) counts
    assert t.report("1", [[now, "s", 999], [now, "s", -5000], [now, "u", 7], [now, "a", 3]]) == 4
    assert [e[1:] for e in tm["ev"][-4:]] == [["s", 100], ["s", -100], ["u", 1], ["a", 1]]
    assert t.report("1", [[now, "s", 1]] * 60) == 40                   # at most 40 per report, 120 kept
    assert len(tm["ev"]) <= 120 and all(e[0] >= t.sim_t() for e in tm["ev"])
    at(t, clock, 6)
    c = tm["car"]
    assert -100 <= c["st"] <= 100 and c["ast"] == 1 and all(isinstance(c[k], (int, float)) and abs(c[k]) < 1e6 for k in ("d", "x", "v", "sw", "bat"))
    # the assist is remembered for the person: the next stint starts with it (the other one keeps the default: off)
    assert t.st["assist"] == {"1": True, "2": False}
    t.report("1", [[t.gt(), "a", 0]])
    assert t.st["assist"]["1"] is False


def test_the_crews_jobs_are_checked_and_timed_on_the_server(monkeypatch):
    straight(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0), ("3", 1)))
    at(t, clock, 2)
    tm = mine(t)
    with pytest.raises(CommunityError):
        t.prep("1", "tyre", 0)                                           # the driver drives
    with pytest.raises(CommunityError):
        t.prep("2", "tyre", 4)
    with pytest.raises(CommunityError):
        t.prep("2", "eng_on")                                            # the engine is fine
    with pytest.raises(CommunityError):
        t.prep("2", "nonsense")
    assert t.prep("2", "tyre", 0)["tyres"] == 1
    assert t.prep("2", "tyre", 0)["again"]
    with pytest.raises(CommunityError):
        t.prep("2", "tyre", 1)                                           # too fast after the last tyre
    for k in (1, 2, 3):
        clock.t += 0.3
        t.prep("2", "tyre", k)
    assert t.ready(tm, t.gt())["tyres"] and t.ready(tm, t.gt())["battery"]          # the first spare is full from the start
    with pytest.raises(CommunityError):
        t.prep("3", "tyre", 0)                                           # alone in the team: the driver – the garage prepares
    assert t.team_of("3")["prep"]["tyres"] == [None] * 4
    for old in ("fuel_on", "fuel_off"):                                  # no fuel any more
        with pytest.raises(CommunityError):
            t.prep("2", old)
    with pytest.raises(CommunityError):
        t.prep("1", "plug")                                              # the driver drives
    # the tyre choice
    assert t.prep("2", "rain")["compound"] == "r" and t.prep("2", "slicks")["compound"] == "s"


def stop_now(t, clock, team, s):
    """The car crosses the line at game time ≈ s and stops at its box a second or two later; answers the stop."""
    at(t, clock, s)
    to_line(t, team)
    k = 0
    while not team["stop"] and k < 60:
        k += 1
        at(t, clock, s + 0.1 * k)
    assert team["car"]["pit"] and team["stop"] and team["stop"]["t"] < s + 3
    return team["stop"]


def test_stop_time_from_what_the_crew_had_ready_and_the_tyres_they_chose(monkeypatch):
    straight(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)), bots=1)
    tm = mine(t)
    stp = stop_now(t, clock, tm, 3)                                       # tyres not ready: 2 + 1 (the battery swap) + 4
    assert stp["time"] == 7.0 and [p[0] for p in stp["parts"]] == ["base", "battery", "tyres"] and not stp["garage"]
    assert stp["parts"][1] == ["battery", ls.BAT_SWAP, True] and stp["bat_in"] == 100.0       # the first spare is full
    with pytest.raises(CommunityError):
        t.prep("2", "tyre", 0)                                           # the car is in: too late
    with pytest.raises(CommunityError):
        t.prep("2", "plug")
    at(t, clock, stp["end"] + 0.3)
    assert not tm["car"]["pit"] and tm["driver"] == "2" and tm["pits"][-1]["time"] == 7.0 and tm["prep"]["tyres"] == [None] * 4
    # everything ready (crew: player 1 now – plugged in first), rain tyres chosen: 3 s, rain tyres on
    at(t, clock, 11)
    t.prep("1", "plug")
    at(t, clock, 20)
    for k in range(4):
        t.prep("1", "tyre", k)
        clock.t += 0.3
    t.prep("1", "rain")
    stp = stop_now(t, clock, tm, 28)
    assert stp["time"] == 3.0 and stp["tyre"] == "r" and all(p[2] for p in stp["parts"])
    at(t, clock, stp["end"] + 0.3)
    assert tm["car"]["tyre"] == "r" and tm["best_pit"] == 3.0 and tm["driver"] == "1"


def test_jobs_done_after_the_car_arrived_do_not_count(monkeypatch):
    straight(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    at(t, clock, 5)
    for k in range(4):
        t.prep("2", "tyre", k)
        clock.t += 0.3
    to_line(t, tm)                                                        # at its box at ≈ 6.2 – the tyres were laid out at ≈ 5.8 … 6.7
    at(t, clock, 8.0, seen=True)
    assert tm["stop"]["parts"][2] == ["tyres", ls.PEN_PREP, False]


def test_an_overheated_engine_is_swapped_prepared_or_not(monkeypatch):
    straight(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    at(t, clock, 2)
    tm["car"]["eng"] = 1
    stp = stop_now(t, clock, tm, 3)
    assert stp["parts"][-1] == ["engine", ls.ENG_SWAP, False] and stp["time"] == 2 + 1 + 4 + 6 and stp["eng"]
    at(t, clock, stp["end"] + 0.3)
    assert not tm["car"]["eng"] and not tm["car"]["pit"]
    tm["car"]["eng"] = 1                                                  # again – now the crew (player 1) prepares the engine
    at(t, clock, 25)
    t.prep("1", "eng_on")
    clock.t += 1.0
    assert not t.prep("1", "eng_off")["ready"]
    t.prep("1", "eng_on")
    clock.t += 1.2
    assert t.prep("1", "eng_off")["ready"]
    stp = stop_now(t, clock, tm, 28)
    assert stp["parts"][-1] == ["engine", ls.ENG_READY, True]


def test_the_swap_puts_the_spare_in_with_its_charge_and_it_charges_only_once_plugged_in(monkeypatch):
    straight(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    at(t, clock, 2)
    tm["car"]["bat"] = 12.0                                               # a hard lap
    stp = stop_now(t, clock, tm, 3)
    assert stp["bat_in"] == 100.0 and 9 < stp["bat_out"] < 12.0
    end = stp["end"]
    at(t, clock, end + 0.3)
    assert tm["car"]["bat"] > 99.5                                         # the spare is in the car now …
    sp = tm["spare"]
    assert sp["c0"] == stp["bat_out"] and sp["t"] == end and sp["plug"] is None    # … and the used one is the ONE spare
    out = sp["c0"]
    # not plugged in: it does not charge at all
    at(t, clock, end + 6)
    assert ls.spare_charge(sp, t.gt()) == out and not t.ready(tm, t.gt())["battery"]
    # plugged in late (6 s after the stop): charging by the server's clock, the app's number is ignored
    pin = t.gt()
    r = t.prep("1", "plug", 100)
    assert r["charge"] == pytest.approx(out, abs=0.1) and sp["plug"] == pytest.approx(pin, abs=0.01)
    assert t.prep("1", "plug")["again"] and sp["plug"] == pytest.approx(pin, abs=0.01)   # plugging in again changes nothing
    at(t, clock, end + 11)
    assert ls.spare_charge(sp, t.gt()) == pytest.approx(out + ls.CHARGE_RATE * 5, abs=0.1)
    # the car comes in 16 s after the stop: only 10 s on the charger – it goes in partly charged
    stp2 = stop_now(t, clock, tm, end + 15.5)
    want = out + ls.CHARGE_RATE * (stp2["t"] - sp["plug"])
    assert stp2["bat_in"] == pytest.approx(want, abs=0.01) and stp2["bat_in"] < 100
    assert ["battery", ls.BAT_SWAP, False] in stp2["parts"] and stp2["time"] == ls.STOP_BASE + ls.BAT_SWAP + ls.PEN_PREP
    at(t, clock, stp2["end"] + 0.3)
    assert tm["car"]["bat"] == pytest.approx(want, abs=0.2)               # the next driver has to save energy
    # plugged in right away: full after 100 / CHARGE_RATE seconds at the latest
    sp = tm["spare"]
    t.prep("2", "plug")
    at(t, clock, stp2["end"] + 0.3 + 100 / ls.CHARGE_RATE + 0.5)
    assert ls.spare_charge(sp, t.gt()) == 100.0 and t.ready(tm, t.gt())["battery"]
    # two batteries per team, never more: one in the car, one spare
    assert isinstance(tm["spare"], dict) and all(isinstance(x["spare"], dict) for x in t.st["teams"])


def test_the_charge_comes_only_from_the_servers_timestamps():
    sp = ls.new_spare(40.0, 50.0)
    assert ls.spare_charge(sp, 99.0) == 40.0                             # never plugged in: never charged
    sp["plug"] = 52.0
    assert ls.spare_charge(sp, 51.0) == 40.0 and ls.spare_charge(sp, 52.0) == 40.0
    assert ls.spare_charge(sp, 57.0) == pytest.approx(40.0 + 5 * ls.CHARGE_RATE)
    assert ls.spare_charge(sp, 52.0 + 100 / ls.CHARGE_RATE) == 100.0 and ls.spare_charge(sp, 999.0) == 100.0
    assert 100 / ls.CHARGE_RATE == 25.0                                  # empty → full in about a lap
    # the plug-in time is the server's: a stopped clock, then the job – the app sends nothing but the action
    t, clock = table(humans=(("1", 0), ("2", 0)))
    at(t, clock, 3)
    tm = mine(t)
    tm["spare"] = ls.new_spare(20.0, 0.0)
    now_t = t.gt()
    assert t.prep("2", "plug", 99)["charge"] == 20.0 and tm["spare"]["plug"] == pytest.approx(now_t, abs=0.002)


def test_the_garage_plugs_in_late_for_a_team_alone_and_an_offline_crew(monkeypatch):
    straight(monkeypatch)
    t, clock = table(humans=(("1", 0),), bots=1)
    tm = mine(t)
    at(t, clock, 2)
    tm["car"]["bat"] = 10.0
    stp = stop_now(t, clock, tm, 3)
    assert stp["garage"] and stp["time"] == ls.GARAGE + ls.BAT_SWAP
    end = stp["end"]
    at(t, clock, end + ls.GARAGE_PLUG - 1)
    assert tm["spare"]["plug"] is None
    at(t, clock, end + ls.GARAGE_PLUG + 1)
    assert tm["spare"]["plug"] == pytest.approx(end + ls.GARAGE_PLUG)    # exactly GARAGE_PLUG s after the stop
    with pytest.raises(CommunityError):
        t.prep("1", "plug")                                              # alone: the driver drives
    # 25 s later: 10 % + 17 s × 4 %/s – fair, not perfect
    assert ls.spare_charge(tm["spare"], end + 25) == pytest.approx(stp["bat_out"] + (25 - ls.GARAGE_PLUG) * ls.CHARGE_RATE, abs=0.01)
    # a crew that is online plugs in itself – the garage keeps out; offline: the garage plugs in
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    stp = stop_now(t, clock, tm, 3)
    at(t, clock, stp["end"] + ls.GARAGE_PLUG + 2)
    assert tm["spare"]["plug"] is None                                    # player 1 is in the crew now, online: their job
    t.st["seen"]["1"] = clock.t - 60
    clock.t += 1.0
    t.st["seen"]["2"] = clock.t
    t.tick()
    assert tm["spare"]["plug"] is not None and tm["spare"]["plug"] >= stp["end"] + ls.GARAGE_PLUG + 2    # not into the past


def test_bots_plug_in_first_and_save_energy_when_low(monkeypatch):
    straight(monkeypatch)
    t, clock = table(humans=(("1", 0),), bots=1, level="hard")
    bot = t.st["teams"][1] if t.st["teams"][1]["bot"] else t.st["teams"][0]
    at(t, clock, 2, seen=False)
    stp = stop_now(t, clock, bot, 3)
    at(t, clock, stp["end"] + 1.0, seen=False)
    assert bot["spare"]["plug"] == pytest.approx(stp["end"] + ls.BOT_PLUG)
    # low on battery: the bot lifts off instead of flat out – and reaches the pits without the emergency mode
    car_ = bot["car"]
    car_.update(bat=50.0, d=ls.laps_of(car_["d"]) * ls.L + 20, x=0.0, sf=0)
    t._drive(bot, t.sim_t())
    assert car_["thr"] == 0
    car_.update(bat=50.0, d=ls.laps_of(car_["d"]) * ls.L + 500, temp=ls.TMIN, v=ls.VLIFT)
    bot["hot"] = 0
    t._drive(bot, t.sim_t())
    assert car_["thr"] == 1                                               # enough for the last 140 m flat out
    car_.update(bat=50.0, d=ls.laps_of(car_["d"]) * ls.L + 20)
    car_["bat"] = 50.0
    s = t.sim_t()
    while not car_["pit"] and s < 400:
        s += 2.0
        at(t, clock, s, seen=False)
    assert car_["pit"] or bot["pits"][-1]["n"] >= 2
    assert car_["flat"] == 0


def test_driver_rotation_for_one_two_and_three_people(monkeypatch):
    straight(monkeypatch)
    # three: 1 → 2 → 3 → 1, a silent person is skipped
    t, clock = table(humans=(("1", 0), ("2", 0), ("3", 0)))
    tm = mine(t)
    order = []
    s = 2.0
    for _ in range(4):
        stp = stop_now(t, clock, tm, s)
        s = stp["end"] + 0.5
        at(t, clock, s)
        order.append(tm["driver"])
    assert order == ["2", "3", "1", "2"] and tm["drives"] == {"1": 2, "2": 2, "3": 1}
    stp = stop_now(t, clock, tm, s + 1)
    clock.t += 30
    assert stp["next"] == "3"
    t.st["seen"] = {"1": clock.t, "2": clock.t, "3": clock.t - 100}
    assert t.next_driver(tm) == "1"                                       # 2 drives, 3 is offline: 1 is next
    # two: they take turns
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    seen = []
    s = 2.0
    for _ in range(3):
        stp = stop_now(t, clock, tm, s)
        assert stp["change"]
        s = stp["end"] + 0.5
        at(t, clock, s)
        seen.append(tm["driver"])
    assert seen == ["2", "1", "2"]
    # one: always the same driver, the garage – a fixed time, the tyres by the forecast
    t, clock = table(humans=(("1", 0),), bots=1, weather=1)
    tm = mine(t)
    t.st["rain"] = [[10.0, 60.0]]
    stp = stop_now(t, clock, tm, 3)
    assert stp["garage"] and stp["time"] == ls.GARAGE + ls.BAT_SWAP == 5.0 and not stp["change"] and stp["tyre"] == "r"
    with pytest.raises(CommunityError):
        t.prep("1", "tyre", 0)
    at(t, clock, stp["end"] + 0.5)
    assert tm["driver"] == "1" and tm["best_pit"] is None                  # garage stops are no record


def test_a_crew_that_is_offline_gets_the_garage(monkeypatch):
    straight(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    at(t, clock, 3)
    to_line(t, tm)
    clock.t += 2.0
    t.st["seen"]["2"] = clock.t - 60
    t.tick()
    assert tm["stop"]["garage"] and not tm["stop"]["change"]


def test_a_silent_driver_gets_the_autopilot():
    t, clock = table(humans=(("1", 0),), bots=1)
    at(t, clock, 3)
    assert not mine(t)["auto"]
    at(t, clock, 30, seen=False)
    assert mine(t)["auto"] and mine(t)["car"]["d"] > 200


def test_bots_race_and_prepare_sensibly_and_the_most_laps_wins():
    t, clock = table(humans=(("1", 0),), bots=3, level="hard", minutes=5, weather=1)
    s = 0.0
    while t.st["phase"] == "play":
        s += 2.0
        at(t, clock, s, seen=False)
    assert t.st["complete"] and s >= 300
    bots = [x for x in t.st["teams"] if x["bot"]]
    assert all(ls.laps_of(b["car"]["d"]) >= 6 for b in bots) and all(b["car"]["blows"] == 0 for b in bots)
    assert all(len(b["laps"]) == ls.laps_of(b["car"]["d"]) and all(lp["time"] > 20 for lp in b["laps"]) for b in bots)
    assert all(min(p["time"] for p in b["pits"]) == ls.STOP_BASE + ls.BAT_SWAP for b in bots)
    assert all(b["car"]["flat"] == 0 for b in bots)                        # they save energy in time
    places = {i: x["place"] for i, x in enumerate(t.st["teams"])}
    best = max(ls.laps_of(x["car"]["d"]) for x in t.st["teams"])
    assert all(places[i] == 1 for i, x in enumerate(t.st["teams"]) if ls.laps_of(x["car"]["d"]) == best and x["car"]["d"] == max(y["car"]["d"] for y in t.st["teams"]))


# ---------------------------------------------------------------- in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _clock(fq):
    c = Clock(2_000_000_000.0)
    fq.langstrecke.now = c
    return c


def test_family_table_teams_race_coins_once_history_and_records(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    assert client.get("/api/parent/game-rewards", headers=phd).json()["langstrecke"] == [10, 5, 2]
    hm, hl = login(client, mia, "1111"), login(client, leo)
    rules = client.get("/api/community/langstrecke/rules", headers=hm).json()
    assert rules["minutes"] == 8 and rules["weather"] == 1 and rules["circuit"] == "Circuit des Tannes" and rules["rewards"] == [10, 5, 2]
    st = client.post("/api/community/langstrecke/start", json={"bots": 1, "minutes": 5, "teams": 2, "country": "CH"}, headers=hm).json()
    assert st["phase"] == "lobby" and st["nteams"] == 2 and not st["coins_on"] and st["players"][0]["team"] == 0
    assert st["looks"][0]["country"] == "CH" and len(st["countries"]) == 66 and len(st["palette"]) == 8
    assert client.post("/api/community/langstrecke/sync", json={"inputs": []}, headers=hm).status_code == 400   # not started
    st = client.post("/api/community/langstrecke/join", headers=hl).json()
    assert st["coins_on"] and [p["team"] for p in st["players"]] == [0, 1]                 # into the smaller team
    assert client.post("/api/community/langstrecke/team", json={"team": 5}, headers=hl).status_code == 400
    assert client.post("/api/community/langstrecke/mix", headers=hl).status_code == 403
    assert client.post("/api/community/langstrecke/begin", headers=hl).status_code == 403
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    assert st["phase"] == "play" and len(st["teams"]) == 3 and st["t0"] == clock.t + ls.COUNTDOWN and st["my_team"] == 0
    me = st["teams"][0]
    assert me["driver"] == str(mia) and "car" in me and "prep" in me and "car" not in st["teams"][1]      # only my team's details
    assert me["country"] == "CH" and me["num"] == 7 and st["rain"]
    assert client.get("/api/me", headers=hl).json()["community"]["langstrecke"]["joined"]
    clock.t = st["t0"] + 2.0
    v = client.post("/api/community/langstrecke/sync", json={"inputs": [[1.9, "u", 1], [1.95, "s", 50]]}, headers=hm).json()
    assert v["taken"] == 2
    assert client.post("/api/community/langstrecke/sync", json={"inputs": [[1, "u", 1]] * 50}, headers=hm).status_code == 422
    r = client.post("/api/community/langstrecke/prep", json={"action": "tyre", "spot": 0}, headers=hm)
    assert r.status_code == 400                                                              # the driver drives
    # the race runs to the end (both apps silent: the autopilot drives, the garage does the stops)
    clock.t = st["t0"] + 300 + 5
    v = client.get("/api/community/langstrecke", headers=hm).json()
    assert v["phase"] == "done" and v["complete"]
    places = {p["id"]: (p["place"], p["coins"]) for p in v["players"]}
    assert places[str(mia)][0] != places[str(leo)][0]
    amounts = {1: 10, 2: 5, 3: 2}
    assert places[str(mia)][1] == amounts[places[str(mia)][0]] and places[str(leo)][1] == amounts[places[str(leo)][0]]
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", st["game"])
    fq.langstrecke._save(row, json.loads(row["state"]))                                        # paid once
    client.get("/api/community/langstrecke", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"langstrecke:{st['game']}:%") == 2
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "langstrecke" and hist[0]["data"]["laps"] >= 6 and hist[0]["data"]["team"] == "Comet Racing"
    assert hist[0]["data"]["players"] == 3 and hist[0]["data"]["record"] and hist[0]["data"]["drives"] >= 1 and hist[0]["data"]["stops"] >= 5
    best = fq.db.get_setting("langstrecke_best")
    assert best[str(mia)] == hist[0]["data"]["laps"] and str(leo) in best
    winner = mia if places[str(mia)][0] == 1 else leo if places[str(leo)][0] == 1 else None
    if winner:
        av = fq.avatar_public(fq.db.q1("SELECT * FROM profile WHERE id=?", winner), {"items": {}})["items"].get("hat")
        assert av == "champion"
    from familyquest import facts
    gens = {c["gen"]: c for c in facts.Facts(fq).candidates()}
    assert gens["record_langstrecke"]["right"] == str(max(best.values()))


def test_pit_records_from_a_real_crew(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/langstrecke/start", json={"bots": 1, "minutes": 5, "teams": 1, "weather": 0, "difficulty": "junior"}, headers=hm)
    client.post("/api/community/langstrecke/join", headers=hl)
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    assert st["teams"][st["my_team"]]["members"] == [str(mia), str(leo)]
    # Leo is the crew: everything ready before the first stop
    clock.t = st["t0"] + 1
    for k in range(4):
        assert client.post("/api/community/langstrecke/prep", json={"action": "tyre", "spot": k}, headers=hl).status_code == 200
        clock.t += 0.3
    r = client.post("/api/community/langstrecke/prep", json={"action": "plug", "charge": 100}, headers=hl).json()
    assert r["charge"] == 100.0 and r["state"]["teams"][0]["prep"]["ready"] == {"tyres": True, "battery": True, "engine": False}
    assert r["state"]["teams"][0]["spare"]["charge"] == 100.0 and r["state"]["teams"][0]["car"]["bat"] < 100
    t = 6.0
    while True:                                                            # both apps stay in touch until the first stop is done
        clock.t = st["t0"] + t
        client.post("/api/community/langstrecke/sync", json={"inputs": []}, headers=hm)
        v = client.post("/api/community/langstrecke/sync", json={"inputs": []}, headers=hl).json()
        if v["teams"][0]["pits"]:
            break
        t += 1.0
    assert v["teams"][0]["pits"][0]["time"] == 3.0 and v["teams"][0]["driver"] == str(leo)
    clock.t = st["t0"] + 320
    client.get("/api/community/langstrecke", headers=hm)
    assert fq.db.get_setting("langstrecke_pit")[str(mia)] == 30
    from familyquest import facts
    gens = {c["gen"]: c for c in facts.Facts(fq).candidates()}
    assert gens["record_pit"]["right"] == "3.0 s"


def _app_js(code: str, data) -> object:
    """Runs the app's pure part (the car, the clock, the screen) in node with `data` on stdin – answers its JSON."""
    src = (WEB / "langstrecke.js").read_text(encoding="utf-8").split("// ---------------------------------------------------------------- the rules, the start")[0]
    prog = "const T = s => s;\n" + src + "\nconst data = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n" + code
    return json.loads(subprocess.run(["node", "-e", prog], input=json.dumps(data), capture_output=True, text=True, timeout=120, check=True).stdout)


def test_the_joystick_maps_the_thumb_to_steering_and_pedals():
    """leJoy (pure, in node): a dead zone in the middle, full lock before the edge, gas / brake beyond 30 % up / down,
    lifted in between, the knob clamped to the ring."""
    pts = [[0, 0], [5, 0], [-5, 3], [8, 0], [-50, 0], [50, 0], [42.5, 0], [100, 0], [0, -14], [0, -16], [0, 14], [0, 16],
           [-35, -35], [0, 200], [300, 400], [20, -10], ["x", None]]
    out = _app_js("console.log(JSON.stringify(data.map(([x, y]) => leJoy(x, y, 50))));", pts)
    s = [o["s"] for o in out]
    u = [o["u"] for o in out]
    assert s[:3] == [0, 0, 0] and s[3] > 0 and s[4] == -100 and s[5] == 100 and s[6] == 100 and s[7] == 100
    assert all(v % 5 == 0 and -100 <= v <= 100 for v in s)
    assert u[:8] == [0] * 8 and u[8] == 0 and u[9] == 1 and u[10] == 0 and u[11] == -1
    assert s[12] < -70 and u[12] == 1                                   # pushed up-left: gas and a lot of steering
    assert out[13] == {"kx": 0, "ky": 50, "s": 0, "u": -1}               # clamped to the ring
    assert abs(out[14]["kx"] - 30) < 1e-9 and abs(out[14]["ky"] - 40) < 1e-9 and out[14]["u"] == -1
    assert 0 < s[15] < 100 and u[15] == 0                               # a little up: lifted off
    assert out[16] == {"kx": 0, "ky": 0, "s": 0, "u": 0}                # junk: at rest


def test_the_h_shifter_gate_maps_drag_positions_to_gears():
    """leGate (pure, in node): R | 1 2 | 3 4 | 5 6 over the neutral rail – the lever stays in the gate, a gear only deep
    in its slot, else N; leGatePos the other way round; leRev the shift light."""
    pts = [[-0.75, -1], [-0.25, -1], [-0.25, 1], [0.25, -1], [0.25, 1], [0.75, -1], [0.75, 1], [-0.8, 0.4], [0, 0], [0.25, -0.4],
           [0.3, -0.9], [-2, -3], [2, 3], [0.5, 0.05], [0.1, 0.9], [None, "y"]]
    out = _app_js("console.log(JSON.stringify({g: data.map(([x, y]) => leGate(x, y)), p: [-1, 0, 1, 2, 3, 4, 5, 6, 9].map(leGatePos),"
                  " r: [leRev({man: 1, gear: 3, v: 18, tyre: 's'}, false), leRev({man: 1, gear: 3, v: 9, tyre: 's'}, false),"
                  " leRev({man: 0, v: 20, tyre: 's'}, false), leRev({man: 1, gear: -1, v: 0, tyre: 's'}, false), leRev({man: 1, gear: 6, v: 25.2, tyre: 's'}, true)]}));", pts)
    gears = [o["gear"] for o in out["g"]]
    assert gears == [-1, 1, 2, 3, 4, 5, 6, 0, 0, 0, 3, -1, 6, 0, 4, 0]
    assert out["g"][7]["x"] == -0.75 and out["g"][7]["y"] == 0           # below R there is no slot: the lever stays on the rail
    assert out["g"][13] == {"x": 0.5, "y": 0, "gear": 0} and out["g"][14]["x"] == 0.25                  # near a slot: into it
    for o in out["g"]:                                                  # always on the gate
        assert o["y"] == 0 or o["x"] in (-0.75, -0.25, 0.25, 0.75)
        assert -1 <= o["y"] <= 1 and -0.75 <= o["x"] <= 0.75
    assert out["p"] == [[-0.75, -1], [0, 0], [-0.25, -1], [-0.25, 1], [0.25, -1], [0.25, 1], [0.75, -1], [0.75, 1], [0, 0]]
    r = out["r"]
    assert r[0]["lim"] and not r[1]["lim"] and r[2]["g"] == 4 and not r[2]["lim"] and r[3] == {"g": -1, "r": 0, "lim": False}
    assert r[4]["lim"]                                                  # in the rain the limiter comes earlier (× grip)


def test_two_players_of_a_team_see_the_right_screen_in_every_phase(client):
    """The bug from a 2-player race: the crew got stuck on the start screen (the intro with the lights) with the jobs
    below it, also in later laps. Every phase from the server's view of BOTH apps through the app's own leScreen():
    the start lights for both (the crew without jobs), then exactly one driver and one crew, both in the pits at a
    stop, the roles swapped after it – and never the intro again after the start."""
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/langstrecke/start", json={"bots": 2, "minutes": 5, "teams": 1, "team_size": 2, "weather": 1, "difficulty": "junior"}, headers=hm)
    client.post("/api/community/langstrecke/join", headers=hl)
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    ids = (str(mia), str(leo))
    slim = lambda v: {"phase": v["phase"], "status": v["status"], "joined": v["joined"], "my_team": v["my_team"],
                      "teams": [{k: tm.get(k) for k in ("driver", "car", "stop", "members", "next")} for tm in v["teams"]]}
    steps = []
    g = -ls.COUNTDOWN + 0.5
    while g < 110:
        clock.t = st["t0"] + g
        views = [client.post("/api/community/langstrecke/sync", json={"inputs": []}, headers=h).json() for h in (hm, hl)]
        assert all(v["now"] - v["t0"] == pytest.approx(g) for v in views)
        steps.append([g, [[slim(v), pid, v["now"] - v["t0"]] for v, pid in zip(views, ids)], len(views[0]["teams"][0]["pits"])])
        g += 0.5
    screens = _app_js("console.log(JSON.stringify(data.map(([g, vs]) => vs.map(([v, me, t]) => leScreen(v, me, t)))));", steps)
    roles = []
    for (g, _, pits), (sm, sl) in zip(steps, screens):
        if g < 0:                                                          # the start: the lights for both
            assert sm == {"mode": "drive", "intro": True} and sl == {"mode": "crew", "intro": True}, g
            continue
        assert not sm["intro"] and not sl["intro"], g                       # never the start screen again
        pair = (sm["mode"], sl["mode"])
        assert pair in {("drive", "crew"), ("crew", "drive"), ("pit", "pit")}, (g, pair)
        if not roles or roles[-1][0] != pair:
            roles.append((pair, pits))
    assert [r for r, _ in roles][:5] == [("drive", "crew"), ("pit", "pit"), ("crew", "drive"), ("pit", "pit"), ("drive", "crew")]
    assert [p for _, p in roles][:5] == [0, 0, 1, 1, 2]
    # a reload mid-race: a fresh app (no state yet) lands straight in its role, no intro
    v = client.get("/api/community/langstrecke", headers=hl).json()
    assert _app_js("console.log(JSON.stringify(leScreen(data[0], data[1], data[2])));", [v, str(leo), v["now"] - v["t0"]])["intro"] is False


def test_the_apps_clock_recovers_when_the_phone_slept():
    """The app's clock (leClockSample): the best (shortest) round trip wins – but a phone that slept comes back with a
    performance.now() that stood still, and its requests are slower than the best one from the lobby. A sample that
    proves the offset wrong replaces it at once (before: the old offset stayed – the start screen for the whole race)."""
    out = _app_js("""
const ck0 = leClockSample({ offset: null, rtt: 1e9 }, 1000.010, 5.000, 5.020);              // the lobby: 20 ms
const same = leClockSample(ck0, 1001.050, 6.000, 6.100);                                   // slower, agrees: kept
const better = leClockSample(ck0, 1002.008, 7.000, 7.015);                                 // faster: taken
// the phone slept 40 s: performance.now() stood still, the server's clock did not – slower requests from now on
const woke = leClockSample(better, 1050.0, 8.000, 8.090);
const game = ck => 8.09 + ck.offset;                                                       // the server time now as the app sees it
console.log(JSON.stringify({ ck0, same, better, woke, gameBefore: game(better), gameAfter: game(woke) }));""", None)
    assert out["ck0"]["offset"] == pytest.approx(995.0) and out["ck0"]["rtt"] == pytest.approx(0.02)
    assert out["same"]["offset"] == out["ck0"]["offset"] and out["same"]["rtt"] > out["ck0"]["rtt"]       # the best ages a little
    assert out["better"]["rtt"] == pytest.approx(0.015) and out["better"]["offset"] == pytest.approx(995.0005)
    assert out["woke"]["offset"] == pytest.approx(1050.0 - 8.045) and out["woke"]["rtt"] == pytest.approx(0.09)
    assert out["gameBefore"] < 1004 and out["gameAfter"] == pytest.approx(1050.045)


def test_lobby_looks_colour_country_and_number_are_validated(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/langstrecke/start", json={"bots": 0, "teams": 2}, headers=hm)
    client.post("/api/community/langstrecke/join", headers=hl)
    look = lambda body, h: client.post("/api/community/langstrecke/look", json=body, headers=h)      # noqa: E731
    blue = ls.TEAM_STYLES[1][1]
    assert look({"color": blue}, hm).status_code == 400                               # Leo's team has it
    assert look({"color": "#123456"}, hm).status_code == 400
    assert look({"color": ls.TEAM_STYLES[6][1], "country": "DK", "num": 42}, hm).status_code == 200
    assert look({"country": "XX"}, hm).status_code == 400 and look({"country": "ZZ"}, hl).status_code == 400
    assert look({"num": 0}, hm).status_code == 400 and look({"num": 100}, hm).status_code == 400
    assert look({"num": 42}, hl).status_code == 400                                   # taken by Mia's team
    assert "manual" not in look({"assist": True}, hm).json()            # the gears are no lobby choice: A / M in the picture
    st = look({"num": 5, "country": ""}, hl).json()
    assert st["looks"][0] == {"color": ls.TEAM_STYLES[6][1], "country": "DK", "num": 42} and st["looks"][1]["country"] is None
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    a, b = st["teams"]
    assert (a["color"], a["country"], a["num"]) == (ls.TEAM_STYLES[6][1], "DK", 42) and (b["num"], b["country"]) == (5, None)
    assert a["car"]["man"] == 0 and a["car"]["gear"] == 1                # nobody chose yet: automatic
    assert look({"num": 9}, hm).status_code == 400                                    # started: no more changes


def test_solo_against_bot_teams_no_coins_and_the_battery(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm = login(client, mia, "1111")
    st = client.post("/api/community/langstrecke/start", json={"solo": True, "bots": 3, "minutes": 5, "difficulty": "junior"}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["teams"]) == 4 and not st["coins_on"] and st["rules"]["difficulty"] == "junior"
    clock.t = st["t0"] + 400
    v = client.get("/api/community/langstrecke", headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'langstrecke:%'")
    assert client.get("/api/community/langstrecke", headers=login(client, leo)).json() is None


@pytest.mark.battery
def test_starting_costs_a_battery_segment_joining_is_free(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    bat = lambda h: client.get("/api/me", headers=h).json()["battery"]["charge"]        # noqa: E731
    assert bat(hm) == 5
    assert client.post("/api/community/langstrecke/start", json={"bots": 1}, headers=hm).status_code == 200
    assert bat(hm) == 4
    assert client.post("/api/community/langstrecke/join", headers=hl).status_code == 200
    assert bat(hl) == 5


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    _clock(fq)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/langstrecke/start", json={"bots": 0, "teams": 2}, headers=hm)
    client.post("/api/community/langstrecke/join", headers=hl)
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    assert len(st["teams"]) == 2 and not any(x["bot"] for x in st["teams"])
    assert client.post("/api/community/langstrecke/end", headers=hl).status_code == 403
    v = client.post("/api/community/langstrecke/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'langstrecke:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='langstrecke'") == 2


def test_one_team_without_bots_is_no_race(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.put("/api/parent/games", json={"access": {"langstrecke": {"mode": "all", "bots": False}}}, headers=phd).status_code == 200
    client.post("/api/community/langstrecke/start", json={"teams": 1}, headers=hm)
    client.post("/api/community/langstrecke/join", headers=hl)
    r = client.post("/api/community/langstrecke/begin", headers=hm)
    assert r.status_code == 400 and "two cars" in r.json()["detail"]
    r = client.post("/api/community/langstrecke/start", json={"solo": True, "bots": 2}, headers=hm)
    assert r.status_code == 403


def test_rules_cleaned_remembered_and_parent_defaults(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert fq.langstrecke.clean_rules("langstrecke", {"bots": 9, "level": "x", "minutes": 7, "weather": 0, "difficulty": "pro", "team_size": 9, "teams": 0}) == \
        {"bots": 5, "level": "normal", "minutes": 8, "weather": 0, "difficulty": "normal", "team_size": 5, "teams": 1}
    hm = login(client, mia, "1111")
    assert client.put("/api/community/langstrecke/rules", json={"minutes": 12}, headers=hm).status_code == 403
    r = client.put("/api/community/langstrecke/rules", json={"minutes": 12, "weather": 0, "difficulty": "junior", "team_size": 2}, headers=phd).json()
    assert (r["minutes"], r["weather"], r["difficulty"], r["team_size"]) == (12, 0, "junior", 2)
    st = client.post("/api/community/langstrecke/start", json={"solo": True, "bots": 1}, headers=hm).json()
    assert st["rules"]["minutes"] == 12 and st["limit"] == 720 and st["rain"] == []


def test_guests_join_a_team_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm = login(client, mia, "1111")
    client.post("/api/community/langstrecke/start", json={"bots": 0, "teams": 2}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "langstrecke"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "24h Endurance"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "mix"):
        assert client.post("/api/community/langstrecke/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.post("/api/community/langstrecke/team", json={"team": 0}, headers=hg).status_code == 200
    assert client.post("/api/community/langstrecke/look", json={"num": 12}, headers=hg).status_code == 200
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]][:2] == [False, True] and not st["coins_on"]
    assert len(st["teams"]) == 2 and st["teams"][0]["members"] == [str(mia), str(g["profile"]["id"])]         # a bot team for a race of two
    clock.t = st["t0"] + 1
    v = client.post("/api/community/langstrecke/sync", json={"inputs": []}, headers=hg).json()
    assert v["my_team"] == 0 and v["teams"][0]["driver"] == str(mia)
    assert client.post("/api/community/langstrecke/prep", json={"action": "tyre", "spot": 2}, headers=hg).json()["tyres"] == 1
    client.post("/api/community/langstrecke/end", headers=hm)
    for p in ("", "/join", "/sync", "/team", "/look", "/prep"):
        assert netfilter.is_guest_path("/api/community/langstrecke" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/mix"):
        assert not netfilter.is_guest_path("/api/community/langstrecke" + p), p


def test_switched_off_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "langstrecke" in client.get("/api/me", headers=hm).json()["games_list"]
    assert "langstrecke" in client.get("/api/parent/games", headers=ph).json()["bot_games"]
    assert client.post("/api/community/langstrecke/start", json={"solo": True, "bots": 2}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "langstrecke")
    assert g["title"] == "24h Endurance" and g["icon"] == "🏎️" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "langstrecke" for x in r["running"])
    assert client.get("/api/community/langstrecke", headers=hm).json()["phase"] == "done"
    assert client.put("/api/parent/games", json={"access": {"langstrecke": {"mode": "off"}}}, headers=ph).status_code == 200
    assert client.get("/api/community/langstrecke", headers=hm).status_code == 403
    assert client.post("/api/community/langstrecke/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "langstrecke" not in me["games_list"] and me["community"]["langstrecke"] is None


def test_the_app_knows_the_game():
    for f in ("index.html", "eltern.html", "gast.html"):
        assert 'src="langstrecke.js' in (WEB / f).read_text(encoding="utf-8"), f
    kid = (WEB / "kid.js").read_text(encoding="utf-8")
    assert 'view === "langstrecke"' in kid and 'canPlay("langstrecke"), langstreckeFamilyCard' in kid
    parent = parent_js()
    assert '["langstrecke", "🏎️", T("24h Endurance")]' in parent and 'gameRewardsRow("langstrecke")' in parent
    assert 'e.kind === "langstrecke"' in (WEB / "community.js").read_text(encoding="utf-8")
    assert 'game === "langstrecke"' in (WEB / "gast.js").read_text(encoding="utf-8")
    from familyquest import familytime, channel
    assert "langstrecke" in familytime.GAMES and "langstrecke" not in channel.DEV_GAMES
    js = (WEB / "langstrecke.js").read_text(encoding="utf-8")
    codes = re.findall(r"\b([A-Z]{2}): T\(", js.split("const LE_COUNTRIES = {")[1].split("};")[0])
    assert sorted(codes) == sorted(ls.COUNTRIES) and len(codes) == 66
    for lang in ("de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"):
        d = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert d.get("24h Endurance") and d.get("Lay out 4 tyres") and d.get("Switzerland") and d.get("Saint Kitts and Nevis"), lang
    assert json.loads((WEB / "i18n" / "de-DE.json").read_text(encoding="utf-8"))["24h Endurance"] == "24-Stunden-Rennen"
    assert json.loads((WEB / "i18n" / "de-CH.json").read_text(encoding="utf-8"))["24h Endurance"] == "24-Stunde-Rännä"
    src = js + Path(ls.__file__).read_text(encoding="utf-8")
    for lang in ("de-DE", "de-CH", "fr-FR"):           # no trademark names: own circuit, own cars and teams
        src += (WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8")
    for word in ("Le Mans", "Ferrari", "Porsche", "Audi", "Toyota", "Peugeot", "Michelin"):
        assert not re.search(r"\b" + word + r"\b", src), word
