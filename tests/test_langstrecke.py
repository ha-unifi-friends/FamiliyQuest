"""«24h Endurance» (24-Stunden-Rennen) – the car (engine, fuel, tyres, things on the track, the same step in the app),
teams and roles, inputs only from the driver, pit stops with their jobs (checked on the server), stint limit, safety
car, rain, autopilot, bots, the end and the winner, coins once, history, records, guests, battery, settings, the app."""
import json
import random
import subprocess
from pathlib import Path

import pytest

from familyquest import langstrecke as ls
from familyquest.community import CommunityError

pytestmark = pytest.mark.dev_channel        # a dev game (channel.py DEV_GAMES): only in «Family Quest Dev»

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


def drive(c, secs, seed=1, jr=False, rain=False, sc=False, s0=0.0):
    evs = []
    for k in range(int(round(secs / ls.DT))):
        evs += ls.step(c, s0 + k * ls.DT, seed, jr, rain, sc)
    return evs


def no_things(monkeypatch):
    monkeypatch.setattr(ls, "lap_things", lambda seed, lap, jr: [])


def table(humans=(("1", 0),), bots=0, level="normal", solo=False, seed=7, rng_seed=1, **rules):
    players = [{"id": pid, "name": f"P{pid}", "team": team} for pid, team in humans]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "langstrecke", "rules": {**ls.DEFAULTS, **rules}, "players": players, "phase": "lobby", "solo": solo}
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


# ---------------------------------------------------------------- the track and the car
def test_things_on_the_track_are_the_same_for_everybody_and_fewer_for_juniors():
    a = ls.lap_things(42, 3, False)
    assert a == ls.lap_things(42, 3, False) and a != ls.lap_things(42, 4, False) and a != ls.lap_things(43, 3, False)
    assert all(160 <= x <= ls.L - 160 and 0 <= lane <= 2 and kind in (0, 1, 2, 3) for x, lane, kind in a)
    assert [x[0] for x in a] == sorted(x[0] for x in a)
    n = sum(len(ls.lap_things(5, k, False)) for k in range(40))
    j = sum(len(ls.lap_things(5, k, True)) for k in range(40))
    assert 4 * 40 <= n <= 6 * 40 and 2 * 40 <= j <= 3 * 40
    assert {k for lap in range(30) for _, _, k in ls.lap_things(9, lap, False)} == {0, 1, 2, 3}


def test_the_app_runs_exactly_the_same_step():
    src = (WEB / "langstrecke.js").read_text(encoding="utf-8").split("// ---------------------------------------------------------------- the rules, the start")[0]
    rng = random.Random(4)
    cases = []
    for n in range(4):
        ev, t = [], 0.0
        while t < 120:
            t = round(t + rng.uniform(0.2, 3.0), 3)
            c = rng.choice("lruuub")
            ev.append([t, c, rng.randint(0, 10) if c == "u" else rng.choice((0, 1, 1, 2)) if c == "b" else 0])
        cases.append({"seed": 100 + n, "jr": n == 3, "ev": ev, "rain": [[30, 60]] if n % 2 else [], "sc": [[70, 80]] if n == 2 else []})
    keys = ["d", "v", "lane", "thr", "temp", "red", "blow", "eng", "wing", "wheel", "wear", "fuel", "tyre", "box", "slow", "olap", "ob", "best", "out", "pit", "hits"]
    code = "const T = s => s;\n" + src + "\nconst cases = %s, keys = %s, out = [];\n" % (json.dumps(cases), json.dumps(keys)) + """
for (const c of cases) { const car = {d: -5, v: 0, lane: 1, thr: 6, temp: 60, red: 0, blow: 0, eng: 0, wing: 0, wheel: 0, loose: -1, wear: 0, fuel: 100, tyre: "s", box: 0, boxed: 0, slow: 0, olap: 0, ob: 0, ls: 0, best: 0, out: null, pit: 0, hits: 0};
  const trace = [], evs = [];
  let i = 0;
  for (let k = 0; k < 1300; k++) { const s = k / 10;
    while (i < c.ev.length && c.ev[i][0] <= s + 1e-9) { leApply(car, c.ev[i][1], c.ev[i][2]); i++; }
    for (const e of leStep(car, s, c.seed, c.jr, leInWin(c.rain, s), leInWin(c.sc, s))) evs.push([k, e]);
    if (car.pit) { car.pit = 0; car.fuel = 100; car.wear = 0; car.eng = 0; car.wing = 0; car.wheel = 0; }
    if (k % 50 === 0) trace.push(keys.map(x => car[x])); }
  out.push([trace, evs]); }
console.log(JSON.stringify(out));"""
    js = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=120, check=True).stdout)
    seen = set()
    for c, (jtrace, jevs) in zip(cases, js):
        cr = ls.new_car(1, -5.0)
        trace, evs, i = [], [], 0
        for k in range(1300):
            s = k / 10
            while i < len(c["ev"]) and c["ev"][i][0] <= s + 1e-9:
                ls.apply_input(cr, c["ev"][i][1], c["ev"][i][2])
                i += 1
            for e in ls.step(cr, s, c["seed"], c["jr"], ls.in_window(c["rain"], s), ls.in_window(c["sc"], s)):
                evs.append([k, e])
            if cr["pit"]:
                cr.update(pit=0, fuel=100.0, wear=0.0, eng=0, wing=0, wheel=0)
            if k % 50 == 0:
                trace.append([cr[x] for x in keys])
        assert evs == jevs, c["seed"]
        for a, b in zip(trace, jtrace):
            for x, y, key in zip(a, b, keys):
                if isinstance(x, float) or isinstance(y, float):
                    assert abs(float(x) - float(y)) < 1e-6, (key, x, y)
                else:
                    assert x == y, (key, x, y)
        seen |= {e for _, e in evs}
    assert {"lap", "pit"} <= seen and seen & {"gravel", "oil", "debris", "crash", "bigcrash"}


def test_full_throttle_heats_the_engine_damage_limps_and_a_second_time_retires(monkeypatch):
    no_things(monkeypatch)
    c = car(thr=10)
    evs = drive(c, 6)
    assert c["temp"] > ls.YELLOW and not c["eng"]
    evs = drive(c, 14, s0=6)
    assert "blow" in evs and c["eng"] == 1 and c["box"] >= 1 and c["blow"] == 1
    drive(c, 3, s0=20)
    assert c["v"] <= ls.VLIMP + 1e-9                              # limping to the pits
    c["box"] = 0
    ls.apply_input(c, "b", 0)
    assert c["box"] == 1                                         # a damaged car must box
    evs = drive(c, 40, s0=23)
    assert "retired" in evs and c["out"] is not None and c["v"] == 0
    d = c["d"]
    drive(c, 5, s0=63)
    assert c["d"] == d                                           # retired: the laps so far stay


def test_lifting_off_in_the_red_saves_the_engine_and_juniors_heat_slower(monkeypatch):
    no_things(monkeypatch)
    c = car(thr=10)
    t = 0.0
    while c["temp"] < ls.RED:
        drive(c, 0.1, s0=t)
        t += 0.1
    normal = t
    drive(c, 2.0, s0=t)                                          # 2 s in the red …
    c["thr"] = 4                                                 # … then lift off
    drive(c, 10, s0=t + 2)
    assert not c["eng"] and c["blow"] == 0 and c["temp"] < ls.RED
    j = car(thr=10)
    t = 0.0
    while j["temp"] < ls.RED:
        drive(j, 0.1, jr=True, s0=t)
        t += 0.1
    assert t > normal * 1.6
    drive(j, ls.GRACE + 1, jr=True, s0=t)                         # juniors have more time to lift off
    assert not j["eng"]


def test_pushing_costs_fuel_and_tyres_and_an_empty_tank_crawls_to_the_pits(monkeypatch):
    no_things(monkeypatch)
    a, b = car(thr=10), car(thr=6)
    drive(a, 12)
    drive(b, 12)
    assert a["d"] > b["d"]
    assert (100 - a["fuel"]) / a["d"] > (100 - b["fuel"]) / b["d"] and a["wear"] / a["d"] > b["wear"] / b["d"]
    c = car(thr=7, fuel=0.5, v=40.0)
    evs = drive(c, 5)
    assert "dry" in evs and c["fuel"] == 0 and c["box"] >= 1 and c["v"] <= ls.VDRY + 1e-9


def test_rain_slicks_slide_rain_tyres_wear_in_the_dry(monkeypatch):
    no_things(monkeypatch)
    dry, wet, rt = car(thr=8), car(thr=8), car(thr=8, tyre="r")
    drive(dry, 30)
    drive(wet, 30, rain=True)
    drive(rt, 30, rain=True)
    assert dry["d"] > rt["d"] > wet["d"]
    rd = car(thr=8, tyre="r")
    drive(rd, 30)
    sd = car(thr=8)
    drive(sd, 30)
    assert rd["wear"] / rd["d"] > 1.8 * sd["wear"] / sd["d"]


def test_collisions_wear_tyres_break_the_wing_and_nothing_under_the_safety_car(monkeypatch):
    things = {0: [[200.0, 1, ls.SLOW], [500.0, 1, ls.GRAVEL], [800.0, 1, ls.DEBRIS], [1100.0, 0, ls.OIL]]}
    monkeypatch.setattr(ls, "lap_things", lambda seed, lap, jr: things.get(lap, []))
    c = car(thr=8, v=50.0, d=100.0)
    evs = drive(c, 4)
    assert "bigcrash" in evs and c["wing"] == 1 and c["wear"] >= 8 and c["hits"] == 1
    evs = drive(c, 30, s0=4)
    assert "gravel" in evs and "debris" in evs and "oil" not in evs           # the oil was in another lane
    s = car(thr=10, v=50.0, d=100.0)
    evs = drive(s, 30, sc=True)
    assert not set(evs) & {"crash", "bigcrash", "gravel", "debris"} and s["hits"] == 0 and s["v"] <= ls.VSC + 1e-9


def test_a_loose_wheel_comes_off_half_a_lap_later(monkeypatch):
    no_things(monkeypatch)
    c = car(thr=8, v=40.0, d=1000.0, loose=1000.0 + ls.L * 0.5)
    evs = drive(c, 30)
    assert "wheel" in evs and c["wheel"] == 1 and c["loose"] == -1 and c["box"] >= 1


def test_the_box_stops_the_car_at_the_line_and_counts_laps(monkeypatch):
    no_things(monkeypatch)
    c = car(thr=10, v=55.0, d=ls.L * 2 - 30)
    ls.apply_input(c, "b", 2)
    evs = drive(c, 2)
    assert "lap" in evs and "pit" in evs and c["pit"] == 1 and c["d"] == ls.L * 2 and c["boxed"] == 2 and c["box"] == 0
    assert ls.laps_of(c["d"]) == 2 and ls.laps_of(-5) == 0


def test_race_clock_day_and_night():
    lim = 900.0
    assert ls.race_hour(0, lim) == 15 and ls.darkness(0, lim) == 0
    assert ls.darkness(lim * 9 / 24, lim) == 1                                  # midnight
    assert 0 < ls.darkness(lim * 6 / 24, lim) < 1                               # dusk at 21:00
    assert ls.darkness(lim * 20 / 24, lim) == 0                                 # 11:00 the next day


# ---------------------------------------------------------------- the table: teams, roles, inputs
def test_teams_from_the_lobby_bots_bring_cars_and_roles_by_team_size():
    t, _ = table(humans=(("1", 0), ("2", 0), ("3", 0), ("4", 0), ("5", 1)), bots=2)
    teams = t.st["teams"]
    assert len(teams) == 4 and [len(x["members"]) for x in teams] == [4, 1, 1, 1] and [x["bot"] for x in teams] == [False, False, True, True]
    assert len({x["num"] for x in teams}) == 4 and len({x["color"] for x in teams}) == 4 and sorted(x["grid"] for x in teams) == [1, 2, 3, 4]
    assert teams[0]["name"] == ls.TEAM_STYLES[0][0] and teams[1]["name"] == ls.TEAM_STYLES[1][0]
    assert t.roles(teams[0]) == {"1": "driver", "2": "engineer", "3": "crew", "4": "crew"} and t.roles(teams[1]) == {"5": "driver"}
    t2, _ = table(humans=(("1", 0), ("2", 0), ("3", 0)))
    assert t2.roles(t2.st["teams"][0]) == {"1": "driver", "2": "crew", "3": "crew"}
    assert all(x["car"]["d"] < 0 and x["car"]["thr"] == 6 for x in teams)
    assert t.st["t0"] == 1000.0 + ls.COUNTDOWN and t.st["rain"] and t.st["k"] == 0


def test_only_the_driver_steers_and_late_inputs_never_go_into_the_past():
    t, clock = table(humans=(("1", 0), ("2", 0)), bots=1)
    at(t, clock, 2.0)
    sim = t.sim_t()
    assert t.report("2", [[2.0, "l", 0]]) == 0                       # the crew does not steer
    assert t.report("1", [[sim - 1.0, "r", 0], [sim + 0.2, "u", 10], [clock.t - t.st["t0"] + 5, "l", 0], ["x", "r", 0], [1, "q", 0]]) == 2
    ev = t.st["teams"][0]["ev"]
    assert ev[0][0] >= sim and ev[0][1] == "r" and [e[1] for e in ev] == ["r", "u"]       # the late one: applied now, not back then
    with pytest.raises(CommunityError):
        t.report("bot1", [[1, "l", 0]])
    lane = t.st["teams"][0]["car"]["lane"]
    at(t, clock, 3.5)
    assert t.st["teams"][0]["car"]["thr"] == 10 and t.st["teams"][0]["car"]["lane"] == min(2, lane + 1)
    with pytest.raises(CommunityError):
        t.radio("1", "box")                                          # the driver keeps the hands on the wheel
    t.radio("2", "push")
    assert t.st["teams"][0]["radio"]["m"] == "push"
    with pytest.raises(CommunityError):
        t.radio("2", "dance")


def pit_now(t, clock, team=0, boxed=1, s=None):
    """Put the team's car just before the line with the box set, run until it stops."""
    tm = t.st["teams"][team]
    c = tm["car"]
    c.update(d=ls.L * (ls.laps_of(max(c["d"], 0)) + 1) - 5, v=50.0, box=boxed, thr=8)
    s = s if s is not None else t.sim_t() + 0.5
    at(t, clock, s)
    assert c["pit"] == 1 and tm["stop"], tm["stop"]
    return tm["stop"]


def test_pit_stop_jobs_are_checked_on_the_server_and_the_stopwatch_runs(monkeypatch):
    no_things(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0), ("3", 0)), bots=1)
    at(t, clock, 3.0)
    t.st["teams"][0]["car"].update(wing=1, fuel=20.0, wear=70.0)
    stop = pit_now(t, clock)
    assert set(stop["tasks"]) == {"tyres", "fuel", "repair"} and stop["change"] and stop["next"] == "2"
    assert stop["who"] == {"tyres": "2", "fuel": "3", "repair": "3"}            # 3 people: two in the crew
    t0 = stop["t"]
    clock.t = t.st["t0"] + t0 + 1.0
    with pytest.raises(CommunityError, match="not your job"):
        t.pit_job("3", "tyres", {})
    order = stop["tasks"]["tyres"]["order"]
    with pytest.raises(CommunityError, match="Wrong order"):
        t.pit_job("2", "tyres", {"nuts": [[n, 0.6] for n in reversed(order)]})
    with pytest.raises(CommunityError, match="Too fast"):
        t.pit_job("2", "tyres", {"nuts": [[n, 0.6] for n in order]})         # 2.4 s of holding in 1 s
    clock.t = t.st["t0"] + t0 + 3.5
    out = t.pit_job("2", "tyres", {"tyre": "r", "nuts": [[n, 0.6 if i != 2 else 0.2] for i, n in enumerate(order)]})
    assert out["loose"] == [order[2]] and stop["done"]["tyres"]["at"] == round(t0 + 3.5, 2)
    assert t.pit_job("2", "tyres", {"nuts": []})["again"]                    # once is enough
    clock.t = t.st["t0"] + t0 + 4.0
    out = t.pit_job("3", "fuel", {"hold": 3.0})                             # 20 % + 90 % → spills
    assert out["spill"] and stop["pen"] == ls.SPILL_PEN and stop["done"]["fuel"]["level"] == 100.0
    rep = stop["tasks"]["repair"]
    wrong = [0, 0, 0] if rep["kind"] == "screws" else list(reversed(rep["perm"]))
    if rep["kind"] == "cables" and wrong == rep["perm"]:
        wrong = rep["perm"][1:] + rep["perm"][:1]
    clock.t = t.st["t0"] + t0 + 5.0
    assert t.pit_job("3", "repair", {"answer": wrong}) == {"ok": False, "pen": ls.WRONG_PEN}
    right = rep["perm"] if rep["kind"] == "cables" else [(8 - r) % 8 for r in rep["rot"]]
    clock.t = t.st["t0"] + t0 + 6.0
    assert t.pit_job("3", "repair", {"answer": right})["ok"]
    assert stop["end"] == round(t0 + 6.0 + ls.SPILL_PEN + ls.WRONG_PEN, 2)
    at(t, clock, stop["end"] + 0.2)
    tm = t.st["teams"][0]
    c = tm["car"]
    assert not c["pit"] and tm["stop"] is None and c["wear"] < 0.1 and c["tyre"] == "r" and c["fuel"] > 99.9 and not c["wing"]
    assert c["loose"] == ls.L * ls.laps_of(c["d"]) + ls.L * 0.5 or c["loose"] > c["d"]
    assert tm["driver"] == "2" and tm["streak"] == 1 and tm["stints"] == {"1": 1, "2": 1}
    assert tm["pits"][0]["time"] == round(stop["end"] - t0, 1) and tm["best_pit"] == tm["pits"][0]["time"]
    assert t.roles(tm) == {"2": "driver", "3": "crew", "1": "crew"}           # the roles rotate


def test_stint_limit_one_double_stint_then_a_change(monkeypatch):
    no_things(monkeypatch)
    t, clock = table(humans=(("1", 0), ("2", 0)), bots=1)
    at(t, clock, 3.0)
    stop = pit_now(t, clock, boxed=2)                                      # «stay in» – allowed once
    assert not stop["change"] and stop["next"] == "1" and set(stop["who"].values()) == {"2"}
    clock.t = t.st["t0"] + stop["t"] + ls.PIT_TASK_MAX + 1
    at(t, clock, stop["t"] + ls.PIT_TASK_MAX + 0.5)                         # nobody did the jobs: the garage
    tm = t.st["teams"][0]
    assert tm["stop"] is None and tm["driver"] == "1" and tm["streak"] == 2 and tm["pits"][0]["time"] == ls.PIT_TASK_MAX
    stop = pit_now(t, clock, boxed=2)                                      # a third stint in a row: no
    assert stop["change"] and stop["next"] == "2"


def test_alone_you_drive_and_do_the_jobs_yourself_and_the_change_waits(monkeypatch):
    no_things(monkeypatch)
    t, clock = table(humans=(("1", 0),), bots=1, solo=True)
    at(t, clock, 3.0)
    t.st["teams"][0]["car"]["fuel"] = 30.0
    stop = pit_now(t, clock)
    assert not stop["change"] and set(stop["who"].values()) == {"1"} and set(stop["tasks"]) == {"tyres", "fuel"}
    clock.t = t.st["t0"] + stop["t"] + 2.6
    t.pit_job("1", "tyres", {"nuts": [[n, 0.6] for n in stop["tasks"]["tyres"]["order"]]})
    with pytest.raises(CommunityError, match="Too fast"):                 # one person: the jobs one after the other
        t.pit_job("1", "fuel", {"hold": 1.0})
    clock.t = t.st["t0"] + stop["t"] + 4.0
    t.pit_job("1", "fuel", {"hold": 1.2})
    assert stop["end"] == round(stop["t"] + 4.0, 2) and not stop["pen"]


def test_safety_car_after_an_engine_failure_slows_everybody(monkeypatch):
    no_things(monkeypatch)
    t, clock = table(humans=(("1", 0),), bots=2)
    at(t, clock, 5.0)
    t.st["teams"][0]["car"].update(temp=ls.RED + 1, thr=10)
    at(t, clock, 10.0)
    assert t.st["teams"][0]["car"]["eng"] == 1 and len(t.st["sc"]) == 1
    a, b = t.st["sc"][0]
    assert b - a == ls.SC_LEN and any(e[1] == "blow" for e in t.st["log"])
    at(t, clock, a + 4)
    assert all(x["car"]["v"] <= ls.VSC + 1e-9 for x in t.st["teams"])
    t._safety_car(a + 10)                                                  # not twice at once, not right after
    t._safety_car(b + 10)
    assert len(t.st["sc"]) == 1
    t._safety_car(b + ls.SC_GAP + 1)
    assert len(t.st["sc"]) == 2


def test_rain_only_with_weather_on():
    assert table(weather=0)[0].st["rain"] == []
    plan = table(weather=1)[0].st["rain"]
    assert 1 <= len(plan) <= 2 and all(0 < a < b <= 900 for a, b in plan)


def test_a_silent_driver_gets_the_autopilot_and_takes_over_again(monkeypatch):
    no_things(monkeypatch)
    t, clock = table(humans=(("1", 0),), bots=1)
    at(t, clock, 3.0)
    clock.t = t.st["t0"] + 20
    t.tick()
    assert t.st["teams"][0]["auto"] and t.st["teams"][0]["car"]["thr"] >= 6 and t.st["teams"][0]["car"]["d"] > 300
    at(t, clock, 21)
    assert not t.st["teams"][0]["auto"]


def test_bots_race_sensibly_and_the_most_laps_wins():
    t, clock = table(humans=(), bots=4, minutes=10, weather=1) if False else table(humans=(("1", 0),), bots=4, minutes=10)
    t.st["seen"]["1"] = 0                                                   # my car on autopilot too
    clock.t = t.st["t0"] + 600 + ls.SETTLE + 1
    t.tick()
    assert t.st["phase"] == "done" and t.st["complete"]
    teams = t.st["teams"]
    assert all(ls.laps_of(x["car"]["d"]) >= 12 for x in teams)
    assert all(x["pits"] for x in teams if x["bot"]) and all(x["car"]["out"] is None for x in teams)
    order = t.st["ranking"]
    laps = [(ls.laps_of(teams[i]["car"]["d"]), teams[i]["car"]["d"]) for i in order]
    assert laps == sorted(laps, reverse=True) and teams[order[0]]["place"] == 1
    assert t.st["places"]["1"] == teams[0]["place"]


def test_retired_team_keeps_its_laps_and_all_people_retired_ends_the_race(monkeypatch):
    no_things(monkeypatch)
    t, clock = table(humans=(("1", 0),), bots=1)
    at(t, clock, 3)
    t.st["teams"][0]["car"].update(d=ls.L * 5 + 10, blow=1, temp=ls.RED + 1, thr=10, eng=0)
    at(t, clock, 8)
    assert t.st["teams"][0]["car"]["out"] is not None
    assert t.st["phase"] == "done" and t.st["complete"] and ls.laps_of(t.st["teams"][0]["car"]["d"]) == 5
    assert t.st["teams"][0]["place"] == 1                                   # 5 laps beat the bot's first lap


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
    assert rules["minutes"] == 15 and rules["circuit"] == "Circuit des Tannes" and rules["rewards"] == [10, 5, 2]
    st = client.post("/api/community/langstrecke/start", json={"bots": 1, "minutes": 10, "teams": 2}, headers=hm).json()
    assert st["phase"] == "lobby" and st["nteams"] == 2 and not st["coins_on"] and st["players"][0]["team"] == 0
    assert client.post("/api/community/langstrecke/sync", json={"inputs": []}, headers=hm).status_code == 400   # not started
    st = client.post("/api/community/langstrecke/join", headers=hl).json()
    assert st["coins_on"] and [p["team"] for p in st["players"]] == [0, 1]                 # into the smaller team
    assert client.post("/api/community/langstrecke/team", json={"team": 5}, headers=hl).status_code == 400
    assert client.post("/api/community/langstrecke/mix", headers=hl).status_code == 403
    assert client.post("/api/community/langstrecke/begin", headers=hl).status_code == 403
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    assert st["phase"] == "play" and len(st["teams"]) == 3 and st["t0"] == clock.t + ls.COUNTDOWN and st["my_team"] == 0
    me = st["teams"][0]
    assert me["roles"] == {str(mia): "driver"} and "car" in me and "car" not in st["teams"][1]        # only my team's telemetry
    assert client.get("/api/me", headers=hl).json()["community"]["langstrecke"]["joined"]
    # Mia drives: her inputs count, Leo's (another team's driver) for his own car only
    clock.t = st["t0"] + 2.0
    v = client.post("/api/community/langstrecke/sync", json={"inputs": [[1.9, "u", 9], [1.95, "r", 0]]}, headers=hm).json()
    assert v["taken"] == 2
    assert client.post("/api/community/langstrecke/sync", json={"inputs": [[1, "u", 1]] * 50}, headers=hm).status_code == 422
    assert client.post("/api/community/langstrecke/radio", json={"msg": "box"}, headers=hm).status_code == 200     # alone in the team: may
    assert client.post("/api/community/langstrecke/pit", json={"task": "fuel", "data": {"hold": 1}}, headers=hm).status_code == 400
    # the race runs to the end (both apps silent: the autopilot drives, the garage does the stops)
    clock.t = st["t0"] + 600 + 5
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
    assert hist[0]["kind"] == "langstrecke" and hist[0]["data"]["laps"] >= 12 and hist[0]["data"]["team"] == "Comet Racing"
    assert hist[0]["data"]["players"] == 3 and hist[0]["data"]["record"] and hist[0]["data"]["stints"] >= 1
    best = fq.db.get_setting("langstrecke_best")
    assert best[str(mia)] == hist[0]["data"]["laps"] and str(leo) in best
    assert fq.db.get_setting("langstrecke_pit")[str(mia)] == int(round(hist[0]["data"]["best_pit"] * 10))
    winner = mia if places[str(mia)][0] == 1 else leo if places[str(leo)][0] == 1 else None
    if winner:
        av = fq.avatar_public(fq.db.q1("SELECT * FROM profile WHERE id=?", winner), {"items": {}})["items"].get("hat")
        assert av == "champion"
    # «Family Quest Facts»: most laps and the fastest pit stop
    from familyquest import facts
    gens = {c["gen"]: c for c in facts.Facts(fq).candidates()}
    assert gens["record_langstrecke"]["right"] == str(max(best.values()))
    assert gens["record_pit"]["right"].endswith(" s") and gens["record_pit"]["q"][0] == "How long did the family's fastest pit stop in {0} take?"


def test_solo_against_bot_teams_no_coins_and_the_battery(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm = login(client, mia, "1111")
    st = client.post("/api/community/langstrecke/start", json={"solo": True, "bots": 3, "minutes": 10, "difficulty": "junior"}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["teams"]) == 4 and not st["coins_on"] and st["rules"]["difficulty"] == "junior"
    clock.t = st["t0"] + 700
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
    assert fq.langstrecke.clean_rules("langstrecke", {"bots": 9, "level": "x", "minutes": 7, "weather": "yes", "difficulty": "pro", "team_size": 9, "teams": 0}) == \
        {"bots": 5, "level": "normal", "minutes": 15, "weather": 1, "difficulty": "normal", "team_size": 5, "teams": 1}
    hm = login(client, mia, "1111")
    assert client.put("/api/community/langstrecke/rules", json={"minutes": 20}, headers=hm).status_code == 403
    r = client.put("/api/community/langstrecke/rules", json={"minutes": 20, "weather": 0, "difficulty": "junior", "team_size": 3}, headers=phd).json()
    assert (r["minutes"], r["weather"], r["difficulty"], r["team_size"]) == (20, 0, "junior", 3)
    st = client.post("/api/community/langstrecke/start", json={"solo": True, "bots": 1}, headers=hm).json()
    assert st["rules"]["minutes"] == 20 and st["limit"] == 1200 and st["rain"] == []


def test_guests_join_a_team_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/langstrecke/start", json={"bots": 0, "teams": 2}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "langstrecke"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "24h Endurance"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "mix"):
        assert client.post("/api/community/langstrecke/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.post("/api/community/langstrecke/team", json={"team": 0}, headers=hg).status_code == 200
    st = client.post("/api/community/langstrecke/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]][:2] == [False, True] and not st["coins_on"]
    assert len(st["teams"]) == 2 and st["teams"][0]["members"] == [str(mia), str(g["profile"]["id"])]         # a bot team for a race of two
    v = client.post("/api/community/langstrecke/sync", json={"inputs": []}, headers=hg).json()
    assert v["my_team"] == 0 and v["teams"][0]["roles"][str(g["profile"]["id"])] == "crew"
    assert client.post("/api/community/langstrecke/radio", json={"msg": "rain"}, headers=hg).status_code == 200
    client.post("/api/community/langstrecke/end", headers=hm)
    for p in ("", "/join", "/sync", "/team", "/radio", "/pit"):
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
    from familyquest import familytime
    assert "langstrecke" in familytime.GAMES
    for lang in ("de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"):
        d = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert d.get("24h Endurance") and d.get("Box this lap!"), lang
    assert json.loads((WEB / "i18n" / "de-DE.json").read_text(encoding="utf-8"))["24h Endurance"] == "24-Stunden-Rennen"
    assert json.loads((WEB / "i18n" / "de-CH.json").read_text(encoding="utf-8"))["24h Endurance"] == "24-Stunde-Rännä"
    src = (WEB / "langstrecke.js").read_text(encoding="utf-8") + (Path(ls.__file__)).read_text(encoding="utf-8")
    import re
    for lang in ("en",) + tuple(("de-DE", "de-CH", "fr-FR")):           # no trademark names: own circuit, own cars and teams
        if lang != "en":
            src += (WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8")
    for word in ("Le Mans", "Mans", "Ferrari", "Porsche", "Audi", "Toyota", "Peugeot", "Michelin"):
        assert not re.search(r"\b" + word + r"\b", src), word
