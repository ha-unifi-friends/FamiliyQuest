"""«Star Runner» – the course (the same for everybody, the same in the app), the server replaying the inputs (anti-cheat),
lives, the end, ranking, coins once, bots, the table in the app, guests, the switches."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from familyquest import sternlauf as sl
from familyquest.community import CommunityError

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(n=2, bots=0, level="normal", solo=False, seed=7, rng_seed=1, lives=3, minutes=3):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "sternlauf", "rules": {**sl.DEFAULTS, "lives": lives, "minutes": minutes}, "players": players, "phase": "lobby", "solo": solo}
    clock = Clock()
    t = sl.Table(st, random.Random(rng_seed), now=clock)
    t.setup(seed)
    return t, clock


def at(t, clock, gt):
    """Move the clock to this game time (the apps of the people stay alive)."""
    clock.t = t.st["t0"] + gt
    for p in t.order():
        if not t.seat_of(p).get("bot"):
            t.st["run"][p]["seen"] = clock.t


def perfect_inputs(seed, upto_t):
    """The inputs of a runner without mistakes – from the bot planner with no timing error and no mistakes."""
    t, clock = table(1, bots=1, level="hard", seed=seed, solo=True)
    old = sl.BOT_SKILL["hard"]
    sl.BOT_SKILL["hard"] = (0.0, 0.0, 0.85)
    try:
        r = t.st["run"]["bot1"]
        t._bot(t.seat_of("bot1"), r, t.obstacles(upto_t + 5), upto_t)
        return [e for e in r["ev"] if e[0] <= upto_t]
    finally:
        sl.BOT_SKILL["hard"] = old


def rows(c):
    out = {}
    for x, lane, kind in c:
        out.setdefault(x, []).append((lane, kind))
    return out


# ---------------------------------------------------------------- the course
def test_course_is_deterministic_and_always_passable():
    c = sl.course(42, 4000)
    assert c == sl.course(42, 4000) and c != sl.course(43, 4000)
    assert c == sorted(c, key=lambda o: o[0])
    assert {k for _, _, k in c} == {sl.LOG, sl.PUDDLE, sl.BRANCH, sl.ROCK, sl.SPARK, sl.SKY}
    obstacle_rows = [(x, r) for x, r in rows(c).items() if any(k in sl.NEED for _, k in r)]
    assert len(obstacle_rows) > 150
    for (x, r), (x2, _) in zip(obstacle_rows, obstacle_rows[1:]):
        blocked = {lane for lane, k in r if k == sl.ROCK}
        assert len(blocked) <= 2                                          # at least one lane open
        assert sl.time_at(x2) - sl.time_at(x) >= 0.75                     # time to swerve, land and jump again
    assert abs(sl.dist(sl.time_at(1234.5)) - 1234.5) < 1e-6 and sl.dist(-1) == 0


def test_the_runner_rules():
    s = {"lane": 1, "lj": -99.0, "ld": -99.0}
    assert sl.meets(s, 5, 1, sl.ROCK) == "hit" and sl.meets(s, 5, 0, sl.ROCK) is None
    assert sl.meets(s, 5, 1, sl.LOG) == "hit" and sl.meets(s, 5, 1, sl.BRANCH) == "hit"
    assert sl.meets(s, 5, 1, sl.SPARK) == "spark" and sl.meets(s, 5, 1, sl.SKY) is None
    jump = sl.state_at(s, [[4.7, "u"]], 5)
    assert sl.meets(jump, 5, 1, sl.LOG) is None and sl.meets(jump, 5, 1, sl.PUDDLE) is None and sl.meets(jump, 5, 1, sl.SKY) == "spark"
    assert sl.meets(jump, 5, 1, sl.BRANCH) == "hit" and sl.meets(jump, 5, 1, sl.ROCK) == "hit"
    assert sl.meets(sl.state_at(s, [[4.0, "u"]], 5), 5, 1, sl.LOG) == "hit"           # landed already
    duck = sl.state_at(s, [[4.7, "d"]], 5)
    assert sl.meets(duck, 5, 1, sl.BRANCH) is None and sl.meets(duck, 5, 1, sl.LOG) == "hit"
    assert sl.meets(sl.state_at(s, [[4.6, "u"], [4.8, "d"]], 5), 5, 1, sl.BRANCH) is None   # a duck ends the jump
    assert sl.state_at(s, [[1, "u"], [1.2, "u"]], 2)["lj"] == 1                          # no jump in the air
    assert sl.state_at(s, [[1, "l"], [1.1, "l"], [1.2, "l"]], 2)["lane"] == 0             # not off the path
    assert sl.state_at(s, [[1, "r"], [3, "r"]], 2)["lane"] == 2                           # later inputs not yet


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_the_app_builds_the_same_course_and_rules():
    src = (WEB / "sternlauf.js").read_text(encoding="utf-8").split("function sternlaufRulesView")[0]
    code = src + """
const out = [1, 77, 2147483646].map(s => srCourse(s, 5000).map(o => [o[0], o[1], o[2], o[3]]));
const s0 = { lane: 1, lj: -99, ld: -99 };
const ev = [[0.5, "l"], [1.0, "u"], [1.2, "u"], [2.0, "r"], [2.05, "r"], [3.0, "d"], [3.3, "u"]];
const probe = [0.4, 0.6, 1.1, 1.5, 2.1, 3.2, 3.5, 3.9].map(t => { const s = srStateAt(s0, ev, t); return [s.lane, s.lj, s.ld,
  [0, 1, 2, 3, 4, 5].map(k => srMeets(s, t, s.lane, k))]; });
console.log(JSON.stringify([out, probe]));"""
    js_course, js_probe = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30, check=True).stdout)
    for s, got in zip((1, 77, 2147483646), js_course):
        assert [[x, lane, k] for x, lane, k, _ in got] == [[x, lane, k] for x, lane, k in sl.course(s, 5000)]
        assert all(abs(tr - sl.time_at(x)) < 1e-12 for x, _, _, tr in got)
    s0 = {"lane": 1, "lj": -99.0, "ld": -99.0}
    ev = [[0.5, "l"], [1.0, "u"], [1.2, "u"], [2.0, "r"], [2.05, "r"], [3.0, "d"], [3.3, "u"]]
    py = []
    for t in (0.4, 0.6, 1.1, 1.5, 2.1, 3.2, 3.5, 3.9):
        s = sl.state_at(s0, ev, t)
        py.append([s["lane"], s["lj"], s["ld"], [sl.meets(s, t, s["lane"], k) for k in range(6)]])
    assert js_probe == py


# ---------------------------------------------------------------- the server replays the inputs
def test_a_perfect_run_has_no_hits_and_the_server_counts_the_sparks():
    t, clock = table(1, seed=11)
    ev = perfect_inputs(11, 60)
    for k in range(0, 61 * 4):                     # the app reports every 0.25 s what happened since
        now = k / 4
        at(t, clock, now)
        t.report("1", [e for e in ev if now - 0.25 < e[0] <= now])
        t.tick()
    r = t.st["run"]["1"]
    assert r["hits"] == [] and r["lives"] == 3 and r["out"] is None and r["sparks"] > 20
    assert r["h"] == pytest.approx(now - sl.SETTLE)
    assert len(r["ev"]) < 30                       # older inputs folded into the base state


def test_doing_nothing_costs_lives_and_the_server_decides():
    t, clock = table(2, seed=5, lives=3)
    at(t, clock, 40)
    t.tick()
    r = t.st["run"]["1"]
    assert r["out"] is not None and r["lives"] == 0 and len(r["hits"]) == 3
    obs = t.obstacles(50)
    assert all(obs[i][2] in sl.NEED for i, _ in r["hits"])
    assert all(b[1] >= a[1] + sl.INVULN for a, b in zip(r["hits"], r["hits"][1:]))


def test_late_future_and_garbage_inputs_are_ignored():
    t, clock = table(2, seed=3)
    at(t, clock, 10)
    t.tick()                                        # settled up to 8.5
    r = t.st["run"]["1"]
    assert r["h"] == pytest.approx(10 - sl.SETTLE)
    assert t.report("1", [[5.0, "l"], [8.0, "u"]]) == 0                  # too late: that part is decided
    assert t.report("1", [[11.0, "l"], [99, "r"]]) == 0                  # ahead of the clock
    assert t.report("1", [["x", "l"], [9.0, "jump"], [float("nan"), "u"], [9.0], None, [9.1, "r"]]) == 1
    assert t.report("1", [[9.1, "l"], [9.12, "l"], [9.3, "l"]]) == 1    # not before / right after the last one
    assert [e[1] for e in r["ev"] if e[0] >= 9] == ["r", "l"]
    assert t.st["run"]["2"]["ev"] == []                                 # only the own runner
    with pytest.raises(CommunityError):
        t.report("bot1", [[9.5, "l"]])


def test_reported_hits_or_distance_do_not_exist():
    """The app cannot claim anything but inputs – a client that sends nothing still gets its hits."""
    t, clock = table(1, seed=9, lives=1)
    for k in range(80):
        at(t, clock, k / 4)
        t.report("1", [])
        t.tick()
        if t.st["phase"] != "play":
            break
    assert t.st["phase"] == "done" and t.st["run"]["1"]["out"] is not None
    assert t.st["scores"]["1"] == int(sl.dist(t.st["run"]["1"]["out"])) + sl.SPARK_PTS * t.st["run"]["1"]["sparks"]


def test_silent_app_is_out():
    t, clock = table(2)
    clock.t = t.st["t0"] + 5
    t.st["run"]["1"]["seen"] = clock.t
    t.st["run"]["2"]["seen"] = clock.t - sl.STALE - 1
    t.st["run"]["1"]["lives"] = t.st["run"]["2"]["lives"] = 99
    t.tick()
    assert t.st["run"]["2"]["out"] is not None and t.st["run"]["1"]["out"] is None


# ---------------------------------------------------------------- the end, the ranking
def test_time_limit_ends_and_ranks_by_points():
    t, clock = table(2, seed=13, minutes=2)
    ev = perfect_inputs(13, 125)
    for k in range(0, 121 * 2):
        now = k / 2
        at(t, clock, now)
        t.report("1", [e for e in ev if now - 0.5 < e[0] <= now])
        t.st["run"]["2"]["lives"] = 99                                   # P2 never goes out but hits a lot
        t.tick()
    assert t.st["phase"] == "play"                                        # 120 s + the settle time
    at(t, clock, 120 + sl.SETTLE)
    t.tick()
    assert t.st["phase"] == "done" and t.st["complete"] and t.st["end_t"] == 120
    sc = t.st["scores"]
    assert sc["1"] == int(sl.dist(120)) + sl.SPARK_PTS * t.st["run"]["1"]["sparks"]
    assert sc["1"] > sc["2"] and t.st["places"] == {"1": 1, "2": 2} and t.st["ranking"] == ["1", "2"]


def test_everybody_out_ends_bots_keep_their_points():
    t, clock = table(1, bots=1, level="hard", seed=4, lives=1)
    for k in range(200):
        at(t, clock, k / 4)
        t.tick()
        if t.st["phase"] != "play":
            break
    assert t.st["phase"] == "done" and t.st["complete"]
    assert t.st["run"]["1"]["out"] is not None
    assert t.st["end_t"] >= t.st["run"]["1"]["out"]


def test_leader_ends_early():
    t, clock = table(2, bots=1, lives=5)
    at(t, clock, 5)
    t.tick()
    t.st["run"]["1"]["lives"] = t.st["run"]["2"]["lives"] = 99
    at(t, clock, 20)
    t.tick()
    t.end()
    assert t.st["phase"] == "done" and not t.st["complete"] and t.st["end_t"] == 20


# ---------------------------------------------------------------- bots
def test_bots_make_mistakes_by_level():
    lost = {}
    for lvl in ("easy", "hard"):
        total = 0
        for seed in range(1, 7):
            t, clock = table(1, bots=1, level=lvl, seed=seed, rng_seed=seed, solo=True)
            for k in range(0, 60 * 4):
                at(t, clock, k / 4)
                t.st["run"]["1"]["lives"] = 99
                t.tick()
            total += len(t.st["run"]["bot1"]["hits"])
        lost[lvl] = total
    assert lost["easy"] > lost["hard"] and lost["easy"] >= 6


def test_bots_plan_ahead_and_ghosts_see_only_the_present():
    t, clock = table(1, bots=1, level="hard", seed=8)
    at(t, clock, 10)
    t.tick()
    r = t.st["run"]["bot1"]
    assert r["ev"] and max(e[0] for e in r["ev"]) <= 10 + sl.LOOKAHEAD
    assert all(b[0] > a[0] for a, b in zip(r["ev"], r["ev"][1:]))


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _clock(fq):
    c = Clock(2_000_000_000.0)
    fq.sternlauf.now = c
    return c


def test_family_table_same_course_only_own_inputs_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    assert client.get("/api/parent/game-rewards", headers=phd).json()["sternlauf"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"sternlauf": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/sternlauf/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/sternlauf/start", json={"bots": 0, "lives": 1, "minutes": 2}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"]
    assert client.post("/api/community/sternlauf/sync", json={"inputs": []}, headers=hm).status_code == 400   # not started
    assert client.post("/api/community/sternlauf/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/sternlauf/begin", headers=hl).status_code == 403              # Leo does not lead
    st = client.post("/api/community/sternlauf/begin", headers=hm).json()
    assert st["phase"] == "play" and st["lives0"] == 1 and st["limit"] == 120 and st["t0"] == clock.t + sl.COUNTDOWN
    lv = client.get("/api/community/sternlauf", headers=hl).json()
    assert lv["seed"] == st["seed"] and lv["t0"] == st["t0"]                                         # the same course
    assert client.get("/api/me", headers=hl).json()["community"]["sternlauf"]["joined"]
    # Mia runs perfectly, Leo does nothing: Leo is out by the server's decision
    ev = perfect_inputs(st["seed"], 130)
    assert client.post("/api/community/sternlauf/sync", json={"inputs": [[1, "l"]] * 41}, headers=hm).status_code == 422
    v = None
    for k in range(0, 123 * 2):
        now = k / 2
        clock.t = st["t0"] + now
        v = client.post("/api/community/sternlauf/sync", json={"inputs": [e for e in ev if now - 0.5 < e[0] <= now]}, headers=hm).json()
        client.post("/api/community/sternlauf/sync", json={"inputs": []}, headers=hl)
        if v["phase"] == "done":
            break
        if k == 40:
            me = next(p for p in v["players"] if p["id"] == str(mia))
            other = next(p for p in v["players"] if p["id"] == str(leo))
            assert "hits" in me and "hits" not in other and "base" in other                        # ghosts: inputs, no secrets
            assert other["out"] is not None and me["out"] is None
    assert v["phase"] == "done" and v["complete"]
    res = {p["id"]: (p["place"], p["coins"]) for p in v["players"]}
    assert res == {str(mia): (1, 8), str(leo): (2, 4)}
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", st["game"])
    fq.sternlauf._save(row, json.loads(row["state"]))                                                # paid once
    client.get("/api/community/sternlauf", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"sternlauf:{st['game']}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"sternlauf:{st['game']}:{mia}")["reason"] == "Star Runner – place 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "sternlauf" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["coins"] == 8
    assert hist[0]["data"]["record"] and hist[0]["data"]["dist"] == int(sl.dist(120)) and hist[0]["data"]["sparks"] > 0
    av = lambda pid: fq.avatar_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid), {"items": {}})["items"].get("hat")
    assert av(mia) == "champion" and av(leo) is None
    v = client.post("/api/community/sternlauf/sync", json={"inputs": []}, headers=hl).json()       # after the end: the result
    assert v["phase"] == "done"


def test_solo_high_score_and_personal_best(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm = login(client, mia, "1111")
    st = client.post("/api/community/sternlauf/start", json={"solo": True, "bots": 0, "lives": 1}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 1 and not st["coins_on"] and st["best"] == 0
    clock.t = st["t0"] + 30
    v = client.post("/api/community/sternlauf/sync", json={"inputs": []}, headers=hm).json()
    assert v["phase"] == "done" and v["players"][0]["record"] and v["best"] == v["players"][0]["score"] > 0
    assert v["players"][0]["coins"] == 0 and not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'sternlauf:%'")
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "sternlauf" and hist[0]["data"]["players"] == 1
    assert client.get("/api/community/sternlauf", headers=login(client, leo)).json() is None


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    _clock(fq)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/sternlauf/start", json={"bots": 1, "level": "easy"}, headers=hm)
    client.post("/api/community/sternlauf/join", headers=hl)
    st = client.post("/api/community/sternlauf/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"]
    assert client.post("/api/community/sternlauf/end", headers=hl).status_code == 403
    v = client.post("/api/community/sternlauf/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'sternlauf:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='sternlauf'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.sternlauf.clean_rules("sternlauf", {"bots": 9, "level": "x", "lives": 4, "minutes": 7}) == {"bots": 7, "level": "normal", "lives": 3, "minutes": 3}
    fq.sternlauf.start("sternlauf", kid, {"bots": 2, "level": "hard", "lives": 5, "minutes": 5}, solo=True)
    assert fq.sternlauf.default_rules() == {"bots": 2, "level": "hard", "lives": 5, "minutes": 5}
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='sternlauf'")["state"])
    assert len(st["players"]) == 3 and st["players"][1]["level"] == "hard" and st["run"]["bot1"]["lives"] == 5


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/sternlauf/start", json={"bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "sternlauf"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Star Runner"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end"):
        assert client.post("/api/community/sternlauf/" + path, json={}, headers=hg).status_code in (401, 403), path
    st = client.post("/api/community/sternlauf/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    assert client.post("/api/community/sternlauf/sync", json={"inputs": []}, headers=hg).status_code == 200
    client.post("/api/community/sternlauf/end", headers=hm)
    for p in ("", "/join", "/sync"):
        assert netfilter.is_guest_path("/api/community/sternlauf" + p), p
    for p in ("/start", "/begin", "/end", "/rules"):
        assert not netfilter.is_guest_path("/api/community/sternlauf" + p), p


def test_switched_off_blocks_it(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "sternlauf" in client.get("/api/me", headers=hm).json()["games_list"]
    assert client.put("/api/parent/games", json={"access": {"sternlauf": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/sternlauf", headers=hm).status_code == 403
    assert client.post("/api/community/sternlauf/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "sternlauf" not in me["games_list"] and me["community"]["sternlauf"] is None


def test_without_bots_switch(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "sternlauf" in client.get("/api/parent/games", headers=phd).json()["bot_games"]
    r = client.put("/api/parent/games", json={"access": {"sternlauf": {"mode": "all", "bots": False}}}, headers=phd)
    assert r.status_code == 200
    r = client.post("/api/community/sternlauf/start", json={"solo": True, "bots": 2}, headers=hm)
    assert r.status_code == 403 and r.json()["detail"] == "Playing with bots is switched off for this game"
    st = client.post("/api/community/sternlauf/start", json={"solo": True}, headers=hm).json()     # alone: still fine
    assert not any(p.get("bot") for p in st["players"])
    # a family table remembered with bots: the bots do not take a seat
    client.post("/api/community/sternlauf/start", json={}, headers=hm)
    fq = client.app.state.fq
    fq.db.set_setting("game_rules.sternlauf", {**sl.DEFAULTS, "bots": 3})
    client.post("/api/community/sternlauf/end", headers=hm)
    client.post("/api/community/sternlauf/start", json={}, headers=hm)
    st = client.post("/api/community/sternlauf/begin", headers=hm).json()
    assert not any(p["bot"] for p in st["players"])
    # a parent at the table: bots allowed
    client.post("/api/community/sternlauf/end", headers=hm)
    st = client.post("/api/community/sternlauf/start", json={"solo": True, "bots": 2}, headers=phd).json()
    assert sum(p["bot"] for p in st["players"]) == 2


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/sternlauf/start", json={"solo": True, "bots": 2}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "sternlauf")
    assert g["title"] == "Star Runner" and g["icon"] == "🌠" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "sternlauf" for x in r["running"])
    v = client.get("/api/community/sternlauf", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]
