"""«24h Endurance» (24-Stunden-Rennen), the short version – the car (engine, things on the track, chicanes, rain and
tyres, the same step in the app), into the pits after every lap, the crew's jobs (checked and timed on the server), the
stop time from what was ready, the engine swap, the electric car's battery (drain, emergency drive mode, the swap at
every stop, the ONE spare charging on the server's clock, the garage, bots), the driver change for 1 / 2 / 3 people,
bots, team looks (colour, country, number), the end and the winner, coins once, history, records, guests, the game
battery, settings, the app."""
import json
import random
import re
import subprocess
from pathlib import Path

import pytest

from familyquest import langstrecke as ls
from familyquest.community import CommunityError

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def car(**kw):
    c = ls.new_car(1, 0.0)
    c.update(kw)
    return c


def drive(c, secs, seed=1, jr=False, rain=False, dark=False, s0=0.0):
    evs = []
    for k in range(int(round(secs / ls.DT))):
        evs += ls.step(c, s0 + k * ls.DT, seed, jr, rain, dark)
    return evs


def no_things(monkeypatch):
    monkeypatch.setattr(ls, "lap_things", lambda seed, lap, jr: [])


def no_kerbs(monkeypatch):
    """A track without chicanes (no kerbs, no braking zones)."""
    monkeypatch.setattr(ls, "kerbs", lambda tricky: [])
    monkeypatch.setattr(ls, "CHICANES", ())


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


def to_line(t, team, metres=3.0):
    """Put the team's car just before the line (it arrives within a step or two)."""
    car = team["car"]
    laps = ls.laps_of(car["d"])
    car.update(d=(laps + 1) * ls.L - metres, v=ls.VLIFT, olap=laps + 1, ob=0)


# ---------------------------------------------------------------- the track and the car
def test_things_on_the_track_are_the_same_for_everybody_and_not_in_the_chicanes():
    a = ls.lap_things(42, 3, False)
    assert a == ls.lap_things(42, 3, False) and a != ls.lap_things(42, 4, False) and a != ls.lap_things(43, 3, False)
    assert [x[0] for x in a] == sorted(x[0] for x in a)
    for lap in range(40):
        for x, lane, kind in ls.lap_things(5, lap, False):
            assert any(lo <= x <= hi for lo, hi in ls.FREE) and 0 <= lane <= 2 and kind in (0, 1, 2)
    n = sum(len(ls.lap_things(5, k, False)) for k in range(40))
    assert 3 * 40 <= n <= 4 * 40 and all(len(ls.lap_things(5, k, True)) == 2 for k in range(40))
    assert ls.kerbs(False) == [[210.0, [2]], [245.0, [0]], [450.0, [0]], [485.0, [2]]]
    assert ls.kerbs(True)[0] == [210.0, [2, 1]]                         # in the rain / at night the kerb is wider


def test_the_app_runs_exactly_the_same_step():
    src = (WEB / "langstrecke.js").read_text(encoding="utf-8").split("// ---------------------------------------------------------------- the rules, the start")[0]
    rng = random.Random(4)
    cases = []
    for n in range(4):
        ev, t = [], 0.0
        while t < 120:
            t = round(t + rng.uniform(0.2, 3.0), 3)
            c = rng.choice("lruuu")
            ev.append([t, c, rng.choice((-1, 0, 1, 1)) if c == "u" else 0])
        cases.append({"seed": 100 + n, "jr": n == 3, "ev": ev, "rain": [[30, 60]] if n % 2 else [], "dark": [[50, 90]] if n >= 2 else [],
                      "tyre": "r" if n == 1 else "s", "bat": (100.0, 55.0, 30.0, 70.0)[n]})
    keys = ["d", "v", "lane", "thr", "temp", "eng", "slow", "olap", "ob", "best", "pit", "hits", "blows", "kerb", "off", "offs", "bat", "flat"]
    code = "const T = s => s;\n" + src + "\nconst cases = %s, keys = %s, out = [];\n" % (json.dumps(cases), json.dumps(keys)) + """
for (const c of cases) { const car = {d: -5, v: 0, lane: 1, thr: 0, temp: 60, eng: 0, slow: 0, olap: 0, ob: 0, ls: 0, best: 0, pit: 0, hits: 0, blows: 0, tyre: c.tyre, kerb: 0, off: 0, offs: 0,
    bat: c.bat, flat: 0};
  const trace = [], evs = [];
  let i = 0;
  for (let k = 0; k < 1300; k++) { const s = k / 10;
    while (i < c.ev.length && c.ev[i][0] <= s + 1e-9) { leApply(car, c.ev[i][1], c.ev[i][2]); i++; }
    for (const e of leStep(car, s, c.seed, c.jr, leInWin(c.rain, s), leInWin(c.dark, s))) evs.push([k, e]);
    if (car.pit) { car.pit = 0; car.eng = 0; car.bat = c.bat; }
    if (k % 50 === 0) trace.push(keys.map(x => car[x])); }
  out.push([trace, evs]); }
console.log(JSON.stringify(out));"""
    js = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=120, check=True).stdout)
    seen = set()
    for c, (jtrace, jevs) in zip(cases, js):
        cr = ls.new_car(1, -5.0)
        cr["tyre"] = c["tyre"]
        cr["bat"] = c["bat"]
        trace, evs, i = [], [], 0
        for k in range(1300):
            s = k / 10
            while i < len(c["ev"]) and c["ev"][i][0] <= s + 1e-9:
                ls.apply_input(cr, c["ev"][i][1], c["ev"][i][2])
                i += 1
            for e in ls.step(cr, s, c["seed"], c["jr"], ls.in_window(c["rain"], s), ls.in_window(c["dark"], s)):
                evs.append([k, e])
            if cr["pit"]:
                cr.update(pit=0, eng=0, bat=c["bat"])
            if k % 50 == 0:
                trace.append([cr[x] for x in keys])
        assert evs == jevs, c["seed"]
        seen |= {e for _, e in evs}
        for a, b in zip(trace, jtrace):
            for x, y, key in zip(a, b, keys):
                if isinstance(x, float) or isinstance(y, float):
                    assert abs(float(x) - float(y)) < 1e-6, (key, x, y)
                else:
                    assert x == y, (key, x, y)
    assert {"lap", "pit", "hit", "kerb", "off", "empty"} <= seen


def test_full_throttle_heats_the_engine_it_overheats_and_limps(monkeypatch):
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    c = car(thr=1, d=10.0)
    evs = drive(c, 12)
    assert not c["eng"] and c["temp"] > ls.YELLOW and abs(c["v"] - ls.VFULL) < 1e-6
    evs = drive(c, 5)
    assert "blow" in evs and c["eng"] and c["blows"] == 1 and 60 <= c["temp"] <= 80
    drive(c, 3)
    assert c["v"] == pytest.approx(ls.VLIMP) and c["temp"] < 80          # limping: slow, the engine cools
    # lifting off cools, juniors heat slower
    a, j = car(thr=1, d=10.0), car(thr=1, d=10.0)
    drive(a, 8)
    drive(j, 8, jr=True)
    assert j["temp"] < a["temp"]
    a["thr"] = 0
    t0 = a["temp"]
    drive(a, 2)
    assert a["temp"] < t0 and a["v"] < ls.VFULL


def test_the_battery_drains_much_faster_at_full_throttle_braking_gives_a_little_back(monkeypatch):
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    full, lifted = car(thr=1, d=10.0, v=ls.VFULL), car(thr=0, d=10.0, v=ls.VLIFT)
    drive(full, 4)
    drive(lifted, 4)
    used_full, used_lift = 100 - full["bat"], 100 - lifted["bat"]
    assert used_full == pytest.approx(ls.E_FULL * ls.VFULL * 4, rel=0.01) and used_lift == pytest.approx(ls.E_LIFT * ls.VLIFT * 4, rel=0.01)
    per_m = (used_full / (full["d"] - 10)), (used_lift / (lifted["d"] - 10))
    assert per_m[0] > 2 * per_m[1]                                       # per metre more than twice as much
    assert ls.E_FULL * ls.L > 100 > ls.E_LIFT * ls.L * 1.5               # flat out a full battery does not last a lap, lifted easily
    # braking gives a little back
    b = car(thr=-1, d=10.0, v=ls.VFULL, bat=50.0)
    drive(b, 0.5)
    assert b["bat"] > 50.0 and b["v"] < ls.VFULL
    # an empty battery stays empty (no regeneration in the emergency mode)
    e = car(thr=-1, d=10.0, v=ls.VFULL, bat=0.0)
    drive(e, 1)
    assert e["bat"] == 0.0


def test_an_empty_battery_means_the_emergency_drive_mode(monkeypatch):
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    c = car(thr=1, d=10.0, v=ls.VFULL, bat=2.0)
    evs = drive(c, 1)
    assert evs.count("empty") == 1 and c["bat"] == 0 and c["flat"] == 1
    drive(c, 6)
    assert c["v"] == pytest.approx(ls.VEMERG) and not c["eng"]          # it crawls – full throttle does nothing any more
    t0 = c["temp"]
    drive(c, 2)
    assert c["temp"] <= t0                                               # and the engine cools
    evs = drive(c, 120)
    assert "pit" in evs and c["pit"]                                     # no retirement: it crawls into the pits
    assert "empty" not in evs and c["flat"] == 1


def test_rain_slicks_slide_and_rain_tyres_are_slower_in_the_dry(monkeypatch):
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    speed = {}
    for tyre in ("s", "r"):
        for rain in (False, True):
            c = car(thr=0, tyre=tyre, d=10.0)
            drive(c, 6, rain=rain)
            speed[tyre, rain] = c["v"]
    assert speed["s", False] == pytest.approx(ls.VLIFT) and speed["r", True] == pytest.approx(ls.VLIFT)
    assert speed["s", True] == pytest.approx(ls.VLIFT * ls.WET_SLICK) and speed["r", False] == pytest.approx(ls.VLIFT * ls.DRY_RAIN)


def test_chicane_kerbs_slow_the_car_wider_in_the_rain_and_at_night(monkeypatch):
    no_things(monkeypatch)
    c = car(lane=2, d=190.0, v=ls.VLIFT)                                 # the kerb of the first gate is in lane 2
    evs = drive(c, 1.5)
    assert "kerb" in evs and c["kerb"] == 1 and c["slow"] > 0
    c = car(lane=1, d=190.0, v=ls.VLIFT)
    assert "kerb" not in drive(c, 1.5)                                   # dry by day: the middle lane is free
    c = car(lane=1, d=190.0, v=ls.VLIFT)
    assert "kerb" in drive(c, 1.5, dark=True)
    c = car(lane=0, d=190.0, v=ls.VLIFT)
    assert "kerb" not in drive(c, 1.5, rain=True)


def test_too_fast_into_a_chicane_goes_off_braking_passes_clean(monkeypatch):
    no_things(monkeypatch)
    fast = car(thr=1, d=150.0, v=ls.VFULL)                              # flat out into the first chicane (gate at 210 m)
    evs = drive(fast, 6)
    assert "off" in evs and fast["offs"] == 1 and fast["slow"] == 0
    braked = car(thr=1, d=150.0, v=ls.VFULL)
    drive(braked, 1.0)                                                   # 30 m at full speed, then brake to 21 m/s
    braked["thr"] = -1
    while braked["v"] > 21:
        drive(braked, 0.1, s0=1.0)
    braked["thr"] = 0                                                    # through the chicane lifted off, then flat out again
    evs = drive(braked, 2, s0=2.0)
    braked["thr"] = 1
    evs += drive(braked, 3, s0=4.0)
    assert "off" not in evs and braked["offs"] == 0 and braked["d"] > fast["d"] + 30
    # lifting off is enough by day in the dry (20 m/s), not in the rain or at night (safe: 18 m/s)
    lifted = car(thr=0, d=100.0, v=ls.VLIFT)
    assert "off" not in drive(lifted, 6)
    lifted = car(thr=0, d=100.0, v=ls.VLIFT)
    assert "off" in drive(lifted, 6, dark=True)
    braking = car(thr=-1, d=150.0, v=ls.VLIFT)
    drive(braking, 1)
    assert braking["v"] < 10                                              # the brake bites hard (lifting off only coasts)


def test_bots_brake_before_the_chicanes_also_in_the_rain_and_at_night():
    t, clock = table(humans=(("1", 0),), bots=3, level="easy", minutes=5, weather=1)
    s = 0.0
    while t.st["phase"] == "play":
        s += 2.0
        at(t, clock, s, seen=False)
    assert all(x["car"]["offs"] == 0 for x in t.st["teams"] if x["bot"])


def test_every_lap_ends_in_the_pits_not_the_start(monkeypatch):
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    c = ls.new_car(0, -5.0)
    c["thr"] = 1
    evs = drive(c, 3)
    assert "pit" not in evs and c["ls"] > 0                               # crossing the line at the start: the first lap begins
    evs = drive(c, 40, s0=3.0)
    assert evs.count("lap") == 1 and "pit" in evs and c["pit"] and c["d"] == ls.L and c["v"] == 0
    assert 18 < c["best"] < 45                                          # full throttle all lap: it overheats on the way


def test_race_clock_day_and_night_and_frequent_showers():
    assert ls.race_hour(0, 480) == 15 and ls.darkness(0, 480) == 0 and ls.darkness(240, 480) == 1
    plan = ls.rain_plan(random.Random(3), 480)
    assert len(plan) >= 3 and plan[0][0] >= 35 and all(30 <= round(b - a) <= 55 for a, b in plan[:-1]) and plan[-1][1] <= 480
    t, _ = table(weather=1)
    assert t.st["rain"]
    t, _ = table(weather=0)
    assert t.st["rain"] == []


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
    assert t.report("1", [[1.0, "u", 1], [5.2, "l", 0], [99, "r", 0], [5.3, "b", 1]]) == 2
    assert tm["ev"][0][0] >= t.sim_t() and tm["ev"][0][1:] == ["u", 1]
    with pytest.raises(CommunityError):
        t.report("bot1", [])


def test_the_crews_jobs_are_checked_and_timed_on_the_server(monkeypatch):
    no_things(monkeypatch)
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
    """The car arrives at game time ≈ s + 0.2; answers the stop."""
    at(t, clock, s)
    to_line(t, team)
    at(t, clock, s + 0.5)
    assert team["car"]["pit"] and team["stop"]
    return team["stop"]


def test_stop_time_from_what_the_crew_had_ready_and_the_tyres_they_chose(monkeypatch):
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)), bots=1)
    tm = mine(t)
    stp = stop_now(t, clock, tm, 3)                                       # tyres not ready: 2 + 1 (the battery swap) + 4
    assert stp["time"] == 7.0 and [p[0] for p in stp["parts"]] == ["base", "battery", "tyres"] and not stp["garage"]
    assert stp["parts"][1] == ["battery", ls.BAT_SWAP, True] and stp["bat_in"] == 100.0       # the first spare is full
    with pytest.raises(CommunityError):
        t.prep("2", "tyre", 0)                                           # the car is in: too late
    with pytest.raises(CommunityError):
        t.prep("2", "plug")
    at(t, clock, 3.2 + 7 + 0.3)
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
    at(t, clock, 32)
    assert tm["car"]["tyre"] == "r" and tm["best_pit"] == 3.0 and tm["driver"] == "1"


def test_jobs_done_after_the_car_arrived_do_not_count(monkeypatch):
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    at(t, clock, 5)
    for k in range(4):
        t.prep("2", "tyre", k)
        clock.t += 0.3
    to_line(t, tm)                                                        # arrives at ≈ 5.2 – the tyres were laid out at ≈ 5.8 … 6.7
    at(t, clock, 7.5, seen=True)
    assert tm["stop"]["parts"][2] == ["tyres", ls.PEN_PREP, False]


def test_an_overheated_engine_is_swapped_prepared_or_not(monkeypatch):
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    at(t, clock, 2)
    tm["car"]["eng"] = 1
    stp = stop_now(t, clock, tm, 3)
    assert stp["parts"][-1] == ["engine", ls.ENG_SWAP, False] and stp["time"] == 2 + 1 + 4 + 6 and stp["eng"]
    at(t, clock, 3.2 + 13 + 0.3)
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
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
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
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
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
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
    t, clock = table(humans=(("1", 0),), bots=1, level="hard")
    bot = t.st["teams"][1] if t.st["teams"][1]["bot"] else t.st["teams"][0]
    at(t, clock, 2, seen=False)
    stp = stop_now(t, clock, bot, 3)
    at(t, clock, stp["end"] + 1.0, seen=False)
    assert bot["spare"]["plug"] == pytest.approx(stp["end"] + ls.BOT_PLUG)
    # low on battery: the bot lifts off instead of flat out – and reaches the pits without the emergency mode
    car_ = bot["car"]
    car_.update(bat=50.0, d=ls.laps_of(car_["d"]) * ls.L + 20, olap=ls.laps_of(car_["d"]), ob=0)
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
    no_things(monkeypatch)
    no_kerbs(monkeypatch)
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
    no_things(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)))
    tm = mine(t)
    at(t, clock, 3)
    to_line(t, tm)
    clock.t += 0.5
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
    assert all(ls.laps_of(b["car"]["d"]) >= 8 for b in bots) and all(b["car"]["blows"] == 0 for b in bots)
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
    v = client.post("/api/community/langstrecke/sync", json={"inputs": [[1.9, "u", 1], [1.95, "r", 0]]}, headers=hm).json()
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
    client.post("/api/community/langstrecke/start", json={"bots": 1, "minutes": 5, "teams": 1, "weather": 0}, headers=hm)
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
    st = look({"num": 5, "country": ""}, hl).json()
    assert st["looks"][0] == {"color": ls.TEAM_STYLES[6][1], "country": "DK", "num": 42} and st["looks"][1]["country"] is None
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    a, b = st["teams"]
    assert (a["color"], a["country"], a["num"]) == (ls.TEAM_STYLES[6][1], "DK", 42) and (b["num"], b["country"]) == (5, None)
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
    parent = (WEB / "parent.js").read_text(encoding="utf-8")
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
