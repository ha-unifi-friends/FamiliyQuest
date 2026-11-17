"""«Traffic Cadet» (Verkehrskadett) – the worlds, the deterministic map (the same in the app), crashes, moods, out,
ranking, the table on the server (switches, worlds, the end), bots, coins, guests, the app touchpoints."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from familyquest import verkehr as vk
from familyquest.community import CommunityError

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def run_map(n, events, ticks=vk.WT, seed=5, diff="normal", la=99, lg=99):
    w = vk.world(n, seed, diff)
    p = vk.Prep(w)
    S = vk.new_state(w, la, lg)
    for _ in range(ticks):
        vk.step(p, S, events, vk.thresholds(diff))
    return p, S


def table(n=2, bots=0, level="normal", solo=False, seed=7, rng_seed=1, worlds=2, diff="normal"):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "verkehr", "rules": {**vk.DEFAULTS, "worlds": worlds, "difficulty": diff}, "players": players, "phase": "lobby", "solo": solo}
    clock = Clock()
    t = vk.Table(st, random.Random(rng_seed), now=clock)
    t.setup(seed)
    return t, clock


def at(t, clock, gk):
    """The clock to this global tick (the server simulates the apps LAG ticks behind)."""
    clock.t = t.st["t0"] + gk / vk.HZ + 1e-6
    for p in t.order():
        t.st["run"][p]["seen"] = clock.t


# ---------------------------------------------------------------- the worlds
def test_worlds_grow_in_complexity_and_have_no_conflict_inside_a_group():
    sizes = []
    for n in range(5):
        lay = vk.layout(n)
        assert lay["name"] == vk.LAYOUTS[n][0] and lay["conf"] and lay["phases"]
        assert all(a != b for a, b in vk.group_conflicts(lay)), n           # one group never crashes with itself
        assert all(g["heads"] and g["label"] for g in lay["groups"])
        for i, a, b, j, c, d in lay["conf"]:                                 # a car waiting at its line is outside
            for p, x in ((i, a), (j, c)):
                assert all(x >= sp + 2 or sp > x + 40 for sp, g, y in lay["paths"][p]["stops"]), (n, p, x)
        sizes.append((len(lay["paths"]), len(lay["groups"])))
    assert sizes[0] == (4, 2) and all(sizes[k][0] >= sizes[0][0] for k in range(5))
    assert [m for m in "SLR" if m in {p["mv"] for p in vk.layout(0)["paths"]}] == ["S"]           # world 1: straight on only
    assert {p["mv"] for p in vk.layout(2)["paths"]} == {"S", "L", "R"} and len(vk.layout(2)["groups"]) == 4
    assert vk.layout(4)["ring"] and vk.layout(4)["yields"] and vk.layout(4)["phases"] == [[0, 1, 2, 3]]
    two = vk.layout(3)
    assert any(len(p["stops"]) == 2 for p in two["paths"])                     # through both crossings
    assert [0, 2] in two["phases"] and [1, 3] in two["phases"]


def test_cars_come_from_the_seed_the_same_for_everybody():
    a = vk.arrivals(2, 42, "normal")
    assert a == vk.arrivals(2, 42, "normal") and a != vk.arrivals(2, 43, "normal") and a != vk.arrivals(3, 42, "normal")
    assert a[0][0] >= vk.INTRO * vk.HZ and a[-1][0] < vk.WT
    assert all(x[0] <= y[0] for x, y in zip(a, a[1:]))
    assert all(0 <= p < len(vk.layout(2)["paths"]) and k in (0, 1, 2, 3) for _, p, k in a)
    assert len(vk.arrivals(2, 42, "hard")) > len(a) > len(vk.arrivals(2, 42, "easy"))
    kinds = {k for n in range(5) for _, _, k in vk.arrivals(n, 9, "hard")}
    assert kinds == {0, 1, 2, 3}
    w = vk.world(1, 42, "normal")
    assert w["arrivals"] == vk.arrivals(1, 42, "normal") and w["n"] == 1
    w["arrivals"].clear()
    assert vk.world(1, 42, "normal")["arrivals"]                               # a fresh copy every time


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_the_app_runs_exactly_the_same_map():
    src = (WEB / "verkehr.js").read_text(encoding="utf-8").split("// ---------------------------------------------------------------- the rules, the start")[0]
    worlds = [vk.world(n, 1234, "hard") for n in range(5)]
    cases = []
    for n in range(5):
        rng = random.Random(n)
        ev, k = [], 0
        while True:
            k += rng.randint(5, 120)
            if k >= vk.WT:
                break
            ev.append([k, rng.randrange(len(worlds[n]["groups"])), rng.randint(0, 1)])
        cases.append((n, ev))
    code = "const T = s => s;\n" + src + "\nconst cases = %s, worlds = %s, out = [];\n" % (json.dumps(cases), json.dumps(worlds)) + """
for (const [n, ev] of cases) { const p = vkPrep(worlds[n]), S = vkNewState(worlds[n], 99, 99), trace = [];
  for (let k = 0; k < VK.WT; k++) { vkStep(p, S, ev, [70, 140]); if (k % 25 === 0) trace.push(JSON.stringify([S.cars, S.pend, S.lights])); }
  out.push([S.acc, S.ann, S.ang, S.pas, S.pts, S.crash, trace]); }
console.log(JSON.stringify(out));"""
    js = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=120, check=True).stdout)
    total = [0, 0, 0]
    for (n, ev), j in zip(cases, js):
        p, S = vk.Prep(worlds[n]), vk.new_state(worlds[n], 99, 99)
        trace = []
        for k in range(vk.WT):
            vk.step(p, S, ev, (70, 140))
            if k % 25 == 0:
                trace.append(json.dumps([S["cars"], S["pend"], S["lights"]], separators=(",", ":")))
        assert [S["acc"], S["ann"], S["ang"], S["pas"], S["pts"], S["crash"]] == j[:6], n
        assert trace == j[6], n
        total = [total[0] + S["acc"], total[1] + S["ang"], total[2] + S["pas"]]
    assert all(x > 5 for x in total)                                              # the random switching did crash and anger


# ---------------------------------------------------------------- the rules of the road
def test_red_stops_green_goes_and_both_green_crash():
    _, S = run_map(0, [], ticks=300)
    assert S["pas"] == 0 and S["acc"] == 0 and S["cars"] and all(c[2] <= 400 for c in S["cars"])
    stops = {p["stops"][0][0] for p in vk.layout(0)["paths"]}
    assert all(c[2] <= max(stops) for c in S["cars"])                            # nobody passes a red light
    _, S = run_map(0, [[1, 0, 1]])                                               # only north–south green: safe
    assert S["acc"] == 0 and S["pas"] > 10
    _, S = run_map(0, [[1, 0, 1], [1, 1, 1]])                                     # both green: crashes
    assert S["acc"] >= 2 and S["crash"]


def test_a_crash_blocks_for_a_while_then_the_wrecks_are_towed():
    p, S = vk.Prep(vk.world(0, 5, "normal")), None
    S = vk.new_state(p.w, 99, 99)
    ev = [[1, 0, 1], [1, 1, 1]]
    while not S["acc"]:
        vk.step(p, S, ev, (100, 200))
    k0 = S["k"]
    ids = set(S["crash"][-1][1:])
    wrecks = [c for c in S["cars"] if c[0] in ids]
    assert len(wrecks) == 2 and all(c[6] == vk.BLOCK for c in wrecks)
    pos = {c[0]: c[2] for c in wrecks}
    for _ in range(vk.BLOCK - 1):
        vk.step(p, S, ev, (100, 200))
        assert {c[0]: c[2] for c in S["cars"] if c[0] in ids} == pos              # they stay where they crashed
    vk.step(p, S, ev, (100, 200))
    assert S["k"] == k0 + vk.BLOCK and not any(c[0] in ids for c in S["cars"])   # towed away


def test_amber_then_red_and_cars_keep_their_gap():
    p = vk.Prep(vk.world(0, 5, "normal"))
    S = vk.new_state(p.w, 99, 99)
    ev = [[1, 0, 1], [200, 0, 0]]
    for _ in range(200):
        vk.step(p, S, ev, (100, 200))
    assert S["lights"][0] == [2, vk.AMBER]
    for _ in range(vk.AMBER):
        vk.step(p, S, ev, (100, 200))
    assert S["lights"][0] == [0, 0]
    for _ in range(100):
        vk.step(p, S, ev, (100, 200))
        for c in S["cars"]:                                                        # same lane: never closer than the gap
            for d in S["cars"]:
                if c is not d and c[1] == d[1] and c[2] < d[2]:
                    assert c[2] <= d[2] - vk.KLEN[d[3]] - vk.GAP + vk.KV[c[3]]
    ev2 = [[1, 0, 1], [5, 0, 1], [6, 0, 0], [7, 0, 1]]                             # amber back to green
    S = vk.new_state(p.w, 99, 99)
    for _ in range(7):
        vk.step(p, S, ev2, (100, 200))
    assert S["lights"][0] == [1, 0]


def test_waiting_makes_drivers_annoyed_then_angry_the_ambulance_sooner():
    S = {"ann": 0, "ang": 0}
    thr = vk.thresholds("normal")
    assert vk._mood(S, 0, thr[0] // 2, 0, thr) == 1 and S == {"ann": 0, "ang": 0}
    assert vk._mood(S, 0, thr[0], 1, thr) == 2 and S == {"ann": 1, "ang": 0}
    assert vk._mood(S, 0, thr[1], 2, thr) == 3 and S == {"ann": 1, "ang": 1}
    assert vk._mood(S, 0, thr[1] + 50, 3, thr) == 3 and S == {"ann": 1, "ang": 1}       # counted once
    assert vk._mood(S, 3, vk.AMB_MOOD[1], 0, thr) == 3 and S == {"ann": 2, "ang": 2}   # the ambulance: both at once
    assert vk.AMB_MOOD[1] < thr[0]
    _, S = run_map(0, [], ticks=vk.WT)                                               # all red the whole world
    assert S["ang"] >= 10 and S["ann"] >= S["ang"] and S["pend"] and any(q for q in S["pend"])


def test_out_after_too_many_accidents_or_angry_drivers():
    _, S = run_map(0, [], la=3, lg=4)
    assert S["out"] is not None and S["ang"] == 4
    k = S["k"]
    p = vk.Prep(vk.world(0, 5, "normal"))
    vk.step(p, S, [], (100, 200))
    assert S["k"] == k                                                               # out: the map stands still
    _, S = run_map(0, [[1, 0, 1], [1, 1, 1]], la=2, lg=99)
    assert S["out"] is not None and S["acc"] == 2


# ---------------------------------------------------------------- the table on the server
def test_setup_same_seed_all_red_and_limits_from_the_difficulty():
    t, clock = table(3, diff="hard", worlds=4)
    assert t.st["phase"] == "play" and t.st["seed"] == 7 and t.st["t0"] == clock.t + vk.COUNTDOWN
    for r in t.st["run"].values():
        assert r["w"] == 0 and r["sim"]["la"] == vk.DIFF["hard"]["acc"] and r["sim"]["lg"] == vk.DIFF["hard"]["ang"]
        assert all(L == [0, 0] for L in r["sim"]["lights"])
    assert t.total() == 4 * vk.WT


def test_switches_only_own_checked_and_late_ones_rejected():
    t, clock = table(2)
    at(t, clock, 100)
    rej = t.report("1", 10.0, [[105, 0, 1], [106, 1, 1], [104, 0, 0]])
    assert t.st["run"]["1"]["evs"]["0"] == [[105, 0, 1], [106, 1, 1]] and rej == [[104, 0, 0]]   # out of order
    assert t.st["run"]["2"]["evs"] == {}
    assert t.report("1", 10.0, [[50, 0, 1]]) == [[50, 0, 1]]                     # the server is past it already
    assert t.report("1", 10.0, [[500, 0, 1]]) == [[500, 0, 1]]                   # far in the future
    assert t.report("1", 10.0, [[107, 9, 1], ["x", 0, 1], [107, 0]]) == [[107, 9, 1]]   # garbage: dropped / rejected
    with pytest.raises(CommunityError):
        t.report("bot1", 1, [])
    t2, c2 = table(1, bots=1)
    with pytest.raises(CommunityError):
        t2.report("bot1", 1, [])
    with pytest.raises(CommunityError):
        t2.report("9", 1, [])


def schedule(period=80, clear=40, start=21):
    """A sensible player at the simple crossing: north–south and east–west in turn, with a clearance pause."""
    ev = [[start, 0, 1]]
    for k in range(start + period, vk.WT, 2 * period):
        ev += [[k, 0, 0], [k + clear, 1, 1], [k + period, 1, 0], [k + period + clear, 0, 1]]
    return [e for e in ev if e[0] < vk.WT]


def cycle(n, green=60, clear=40):
    """Every phase of world n in turn."""
    ph = vk.layout(n)["phases"]
    ev, k, i = [], 21, 0
    while k < vk.WT:
        ev += [[k, g, 1] for g in ph[i % len(ph)]]
        k += green
        ev += [[k, g, 0] for g in ph[i % len(ph)]]
        k += clear
        i += 1
    return [e for e in ev if e[0] < vk.WT]


def test_a_sensible_schedule_keeps_the_crossing_safe():
    for seed in (5, 7, 9):
        _, S = run_map(0, schedule(), seed=seed)
        assert S["acc"] == 0 and S["ang"] == 0 and S["pas"] > 30 and S["out"] is None


def test_the_server_map_follows_the_reported_switches_and_moves_on_through_the_worlds():
    t, clock = table(2, worlds=2)
    at(t, clock, 30)
    assert t.report("1", 3, [[31, 0, 1]]) == []
    t.st["run"]["1"]["evs"]["0"] = schedule(start=31)                        # (as the app would report them in time)
    t.report("2", 3, [])
    at(t, clock, vk.WT + vk.LAG + 5)
    t.tick()
    r1, r2 = t.st["run"]["1"], t.st["run"]["2"]
    _, ref = run_map(0, schedule(start=31), seed=7)
    assert r1["w"] == 1 and r1["tot"]["pas"] == ref["pas"] > 10 and r1["tot"]["ang"] == ref["ang"] and r1["out"] is None
    assert r2["tot"]["pas"] == 0 and r2["out"] is not None and r2["out"] < vk.WT       # nobody switched: all red – out
    assert r1["sim"]["k"] == 5 and r1["sim"]["lights"] == [[0, 0]] * len(vk.layout(1)["groups"])   # world 2, fresh
    assert r1["sim"]["la"] == 3 - ref["acc"] and r1["sim"]["lg"] == vk.DIFF["normal"]["ang"] - ref["ang"]
    assert "0" not in r1["evs"]
    st = t.stats("1")
    assert st["pas"] == ref["pas"] + r1["sim"]["pas"] and st["score"] == st["pts"] - 5 * st["acc"] - 2 * st["ang"]
    assert t.st["phase"] == "done"                                           # player 2 out: the last one standing


def test_out_stays_out_spectators_and_the_ranking():
    t, clock = table(3, worlds=2)
    t.st["run"]["1"]["evs"]["0"] = schedule()
    t.st["run"]["2"]["evs"]["0"] = schedule()
    t.st["run"]["3"]["evs"]["0"] = [[21, 0, 1]]                               # only north–south: east–west gets angry
    at(t, clock, vk.WT - 50)
    t.tick()
    r3 = t.st["run"]["3"]
    assert r3["out"] is not None and r3["out"] < vk.WT - 100 and t.st["phase"] == "play"
    o = r3["out"]
    at(t, clock, vk.WT + 100)
    t.tick()
    assert t.st["run"]["3"]["out"] == o and t.st["run"]["3"]["w"] == 0          # out stays out (in world 1)
    assert t.st["run"]["1"]["w"] == t.st["run"]["2"]["w"] == 1                   # the others moved on together
    # world 2: player 2 does nothing – angry drivers put them out; player 1 is the last one standing
    t.st["run"]["1"]["evs"]["1"] = cycle(1)
    at(t, clock, 2 * vk.WT)
    t.tick()
    assert t.st["run"]["2"]["out"] is not None
    assert t.st["phase"] == "done" and t.st["complete"]
    assert t.st["ranking"][0] == "1" and t.st["places"] == {"1": 1, "2": 2, "3": 3}   # out later: the better place
    with pytest.raises(CommunityError):
        t.report("1", 1, [])


def test_ranking_by_points_among_those_still_in_after_the_last_world():
    t, clock = table(2, worlds=1)
    t.st["run"]["1"]["evs"]["0"] = schedule(80)
    t.st["run"]["2"]["evs"]["0"] = schedule(120)
    at(t, clock, vk.WT + vk.LAG + 1)
    t.tick()
    assert t.st["phase"] == "done" and t.st["complete"]
    s = t.st["scores"]
    assert t.st["run"]["1"]["out"] is None and t.st["run"]["2"]["out"] is None
    order = sorted(("1", "2"), key=lambda p: -s[p]["score"])
    assert t.st["ranking"] == order or s["1"]["score"] == s["2"]["score"]
    assert all(k in s["1"] for k in ("acc", "ann", "ang", "pas", "pts", "score"))
    assert t.st["run"]["1"]["evs"] == {} and t.st["run"]["1"]["sim"]["cars"] == []   # the maps are not kept
    t2, c2 = table(2, worlds=1)                                                 # the same: the same place
    t2.st["run"]["1"]["evs"]["0"] = t2.st["run"]["2"]["evs"]["0"] = schedule()
    at(t2, c2, vk.WT + vk.LAG + 1)
    t2.tick()
    assert t2.st["places"] == {"1": 1, "2": 1}


def test_solo_plays_on_alone_and_a_silent_app_is_out():
    t, clock = table(1, bots=1, solo=True, worlds=2)
    t.st["run"]["bot1"]["out"] = 5
    t.st["run"]["1"]["evs"]["0"] = schedule()
    at(t, clock, 300)
    t.report("1", 30, [])
    assert t.st["phase"] == "play"                                                # alone in front: plays on
    t2, c2 = table(2)
    t2.st["run"]["2"]["evs"]["0"] = schedule()
    at(t2, c2, 50)
    t2.report("1", 5, [])
    c2.t += vk.STALE + 1
    t2.st["run"]["2"]["seen"] = c2.t
    t2.tick()
    assert t2.st["run"]["1"]["out"] is not None and t2.st["run"]["1"]["left"] and t2.st["phase"] == "done"
    assert t2.st["ranking"][0] == "2"


def test_leader_ends_the_game_as_it_stands():
    t, clock = table(2)
    at(t, clock, 300)
    t.report("1", 30, [[301, 0, 1]])
    t.end()
    assert t.st["phase"] == "done" and set(t.st["places"]) == {"1", "2"} and t.st["scores"]["1"]["pas"] >= 0


# ---------------------------------------------------------------- bots
def _bot_world(level, n, seed=3, rng=0, diff="normal"):
    st = {"kind": "verkehr", "rules": {**vk.DEFAULTS, "worlds": 5, "difficulty": diff},
          "players": [{"id": "bot1", "name": "B", "bot": True, "level": level}], "phase": "lobby", "solo": True}
    t = vk.Table(st, random.Random(rng), now=lambda: 1000.0)
    t.setup(seed)
    r = st["run"]["bot1"]
    r["w"] = n
    r["sim"] = vk.new_state(t.prep(n).w, 99, 99)
    t.advance("bot1", (n + 1) * vk.WT - 1)
    return r


def test_bots_switch_phases_by_demand_and_keep_the_traffic_flowing():
    for n in range(5):
        r = _bot_world("hard", n)
        S = r["sim"]
        ev = r["evs"][str(n)]
        assert ev and S["pas"] > 20, n
        assert S["acc"] <= 1, n
        assert all(a[0] <= b[0] for a, b in zip(ev, ev[1:]))
    r = _bot_world("normal", 0)
    assert r["sim"]["ang"] <= 3 and r["sim"]["acc"] == 0


def test_easy_bots_slip_more_than_hard_ones():
    easy = sum(_bot_world("easy", n, seed=s, rng=s)["sim"]["acc"] for n in range(4) for s in range(6))
    hard = sum(_bot_world("hard", n, seed=s, rng=s)["sim"]["acc"] for n in range(4) for s in range(6))
    assert easy >= 2 * hard and easy > 0


def test_bots_are_simulated_live_without_lag():
    t, clock = table(1, bots=2, level="normal", worlds=1)
    t.st["run"]["1"]["evs"]["0"] = schedule()
    at(t, clock, 300)
    t.tick()
    assert t.st["run"]["bot1"]["sim"]["k"] == 300 and t.st["run"]["1"]["sim"]["k"] == 300 - vk.LAG
    assert t.st["run"]["bot1"]["evs"]["0"]


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _clock(fq):
    c = Clock(2_000_000_000.0)
    fq.verkehr.now = c
    return c


def play_api(client, clock, st, plans, step=1):
    """Every second: each app reports the switches of its plan that are due (as the app does) – until the end."""
    sent = {k: 0 for k in plans}
    v = None
    for sec in range(1, vk.WT // vk.HZ + 5, step):
        clock.t = st["t0"] + sec
        now = sec * vk.HZ
        for who, (head, ev) in plans.items():
            due = [e for e in ev if sent[who] < e[0] <= now + 5]
            sent[who] = max([sent[who]] + [e[0] for e in due])
            v = client.post("/api/community/verkehr/sync", json={"t": sec, "events": due}, headers=head).json()
            assert not v.get("rej"), (who, v.get("rej"))
        if v["phase"] == "done":
            break
    return v


def test_family_table_same_worlds_switches_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    assert client.get("/api/parent/game-rewards", headers=phd).json()["verkehr"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"verkehr": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    rules = client.get("/api/community/verkehr/rules", headers=hm).json()
    assert rules["rewards"] == [8, 4, 1] and rules["worlds"] == 3 and len(rules["worlds_names"]) == 5
    st = client.post("/api/community/verkehr/start", json={"bots": 0, "worlds": 1, "difficulty": "normal"}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"] and st["worlds_names"] == ["Simple crossing"]
    assert client.get("/api/community/verkehr/worlds", headers=hm).json() is None
    assert client.post("/api/community/verkehr/sync", json={"t": 0}, headers=hm).status_code == 400   # not started
    assert client.post("/api/community/verkehr/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/verkehr/begin", headers=hl).status_code == 403                # Leo does not lead
    st = client.post("/api/community/verkehr/begin", headers=hm).json()
    assert st["phase"] == "play" and st["t0"] == clock.t + vk.COUNTDOWN and st["my"]["w"] == 0 and st["my"]["sim"]["k"] == 0
    wm = client.get("/api/community/verkehr/worlds", headers=hm).json()
    wl = client.get("/api/community/verkehr/worlds", headers=hl).json()
    assert wm == wl and len(wm["worlds"]) == 1 and wm["worlds"][0]["arrivals"] == vk.arrivals(0, st["seed"], "normal")
    assert client.get("/api/me", headers=hl).json()["community"]["verkehr"]["joined"]
    # Mia sets north–south green – only her own map changes
    clock.t = st["t0"] + 2.0
    v = client.post("/api/community/verkehr/sync", json={"t": 2.0, "events": [[21, 0, 1]]}, headers=hm).json()
    assert v["rej"] == [] and "my" not in v
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", st["game"])
    run = json.loads(row["state"])["run"]
    assert run[str(mia)]["evs"]["0"] == [[21, 0, 1]] and not run[str(leo)]["evs"].get("0")
    # a switch for a moment the server simulated already: rejected, my map comes back
    clock.t = st["t0"] + 10.0
    v = client.post("/api/community/verkehr/sync?mine=1", json={"t": 10.0, "events": [[30, 1, 1]]}, headers=hm).json()
    assert v["rej"] == [[30, 1, 1]] and v["my"]["sim"]["k"] == 100 - vk.LAG and v["my"]["evs"]["0"] == [[21, 0, 1]]
    assert client.post("/api/community/verkehr/sync", json={"t": 1, "events": [[1, 0, 1]] * 50}, headers=hm).status_code == 422
    # Mia switches in turn, Leo never: his drivers get angry – out, Mia is the last one standing
    v = play_api(client, clock, st, {"mia": (hm, [e for e in schedule() if e[0] > 100]), "leo": (hl, [])})
    assert v["phase"] == "done" and v["complete"]
    res = {p["id"]: (p["place"], p["coins"]) for p in v["players"]}
    me = next(p for p in v["players"] if p["id"] == str(mia))
    assert me["pas"] > 10 and me["score"] > 0
    assert res[str(mia)] == (1, 8) and res[str(leo)] == (2, 4)
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", st["game"])
    fq.verkehr._save(row, json.loads(row["state"]))                                                     # paid once
    client.get("/api/community/verkehr", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"verkehr:{st['game']}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"verkehr:{st['game']}:{mia}")["reason"] == "Traffic Cadet – Platz 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "verkehr" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["coins"] == 8
    assert hist[0]["data"]["passed"] == me["pas"] and hist[0]["data"]["worlds"] == 1 and hist[0]["data"]["record"]
    av = lambda pid: fq.avatar_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid), {"items": {}})["items"].get("hat")
    assert av(mia) == "champion" and av(leo) is None
    v = client.post("/api/community/verkehr/sync", json={"t": 1}, headers=hl).json()
    assert v["phase"] == "done"


def test_solo_with_practice_bots_no_coins_and_personal_best(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm = login(client, mia, "1111")
    st = client.post("/api/community/verkehr/start", json={"solo": True, "bots": 1, "worlds": 1, "level": "hard"}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 2 and not st["coins_on"] and st["players"][1]["bot"]
    v = play_api(client, clock, st, {"mia": (hm, schedule())})
    assert v["phase"] == "done"
    me = next(p for p in v["players"] if p["id"] == str(mia))
    assert me["coins"] == 0 and v["best"] == me["score"] and me["record"]
    bot = next(p for p in v["players"] if p["bot"])
    assert bot["pas"] > 10
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'verkehr:%'")
    assert client.get("/api/community/verkehr", headers=login(client, leo)).json() is None


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    _clock(fq)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/verkehr/start", json={"bots": 1, "level": "easy"}, headers=hm)
    client.post("/api/community/verkehr/join", headers=hl)
    st = client.post("/api/community/verkehr/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"]
    assert client.post("/api/community/verkehr/end", headers=hl).status_code == 403
    v = client.post("/api/community/verkehr/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'verkehr:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='verkehr'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.verkehr.clean_rules("verkehr", {"bots": 9, "level": "x", "difficulty": "y", "worlds": 9}) == \
        {"bots": 5, "level": "normal", "difficulty": "normal", "worlds": 5}
    assert fq.verkehr.clean_rules("verkehr", {"worlds": 0})["worlds"] == 1
    fq.verkehr.start("verkehr", kid, {"bots": 2, "level": "hard", "difficulty": "easy", "worlds": 4}, solo=True)
    assert fq.verkehr.default_rules() == {"bots": 2, "level": "hard", "difficulty": "easy", "worlds": 4}
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='verkehr'")["state"])
    assert len(st["players"]) == 3 and st["players"][1]["level"] == "hard" and st["run"]["bot1"]["sim"]["la"] == vk.DIFF["easy"]["acc"]


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/verkehr/start", json={"bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "verkehr"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Traffic Cadet"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end"):
        assert client.post("/api/community/verkehr/" + path, json={}, headers=hg).status_code in (401, 403), path
    st = client.post("/api/community/verkehr/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    assert client.post("/api/community/verkehr/sync", json={"t": 0, "events": []}, headers=hg).status_code == 200
    assert client.get("/api/community/verkehr/worlds", headers=hg).json()["worlds"]
    client.post("/api/community/verkehr/end", headers=hm)
    for p in ("", "/join", "/sync", "/worlds"):
        assert netfilter.is_guest_path("/api/community/verkehr" + p), p
    for p in ("/start", "/begin", "/end", "/rules"):
        assert not netfilter.is_guest_path("/api/community/verkehr" + p), p


def test_switched_off_and_without_bots(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "verkehr" in client.get("/api/me", headers=hm).json()["games_list"]
    d = client.get("/api/parent/games", headers=phd).json()
    assert "verkehr" in d["bot_games"]
    # «active without bots»: alone with practice bots refused, alone without bots fine, the remembered bots stay
    client.app.state.fq.db.set_setting("game_rules.verkehr", {"bots": 3})
    assert client.put("/api/parent/games", json={"access": {"verkehr": {"mode": "all", "bots": False}}}, headers=phd).status_code == 200
    r = client.post("/api/community/verkehr/start", json={"solo": True, "bots": 2}, headers=hm)
    assert r.status_code == 403 and r.json()["detail"] == "Playing with bots is switched off for this game"
    st = client.post("/api/community/verkehr/start", json={"solo": True}, headers=hm).json()
    assert not any(p["bot"] for p in st["players"])
    assert client.app.state.fq.db.get_setting("game_rules.verkehr")["bots"] == 3
    # inactive
    assert client.put("/api/parent/games", json={"access": {"verkehr": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/verkehr", headers=hm).status_code == 403
    assert client.post("/api/community/verkehr/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "verkehr" not in me["games_list"] and me["community"]["verkehr"] is None


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/verkehr/start", json={"solo": True, "bots": 2}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "verkehr")
    assert g["title"] == "Traffic Cadet" and g["icon"] == "🚦" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "verkehr" for x in r["running"])
    v = client.get("/api/community/verkehr", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]


def test_the_app_knows_the_game():
    for f in ("index.html", "eltern.html", "gast.html"):
        assert 'src="verkehr.js' in (WEB / f).read_text(encoding="utf-8"), f
    kid = (WEB / "kid.js").read_text(encoding="utf-8")
    assert 'view === "verkehr"' in kid and 'canPlay("verkehr")' in kid
    parent = (WEB / "parent.js").read_text(encoding="utf-8")
    assert '["verkehr", "🚦", T("Traffic Cadet")]' in parent and 'gameRewardsRow("verkehr")' in parent
    assert 'e.kind === "verkehr"' in (WEB / "community.js").read_text(encoding="utf-8")
    assert 'game === "verkehr"' in (WEB / "gast.js").read_text(encoding="utf-8")
    for lang in ("de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"):
        d = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert d.get("Traffic Cadet"), lang
    assert json.loads((WEB / "i18n" / "de-DE.json").read_text(encoding="utf-8"))["Traffic Cadet"] == "Verkehrskadett"
