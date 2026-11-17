"""«Jump» – the course (the same for everybody, the same in the app), lives, elimination, ranking, bots, the table in the app."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from familyquest import jump as ju
from familyquest.community import CommunityError

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(n=2, bots=0, level="normal", solo=False, seed=7, rng_seed=1, lives=3):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "jump", "rules": {**ju.DEFAULTS, "lives": lives}, "players": players, "phase": "lobby", "solo": solo}
    clock = Clock()
    t = ju.Table(st, random.Random(rng_seed), now=clock)
    t.setup(seed)
    return t, clock


def at(t, clock, gt):
    """Move the clock to this game time."""
    clock.t = t.st["t0"] + gt


def hit(t, clock, pid, i):
    """pid reports a hit on obstacle i (at the moment it passes) – the clock a bit later (after the grace)."""
    a, b = ju.window(*t.obstacles(200)[i])
    at(t, clock, max(b + 0.1, a + ju.GRACE + 0.1))
    for p in t.order():                                    # the others' apps stay alive
        if p != pid and not t.seat_of(p).get("bot"):
            t.st["run"][p]["seen"] = clock.t
    t.report(pid, b + 0.05, [], [[i, a + 0.01]])


# ---------------------------------------------------------------- the course
def test_course_is_deterministic_and_playable():
    c = ju.course(42, 5000)
    assert c == ju.course(42, 5000) and c != ju.course(43, 5000)
    assert c[0] == (ju.V0 * ju.FIRST, 0)
    for (x, k), (x2, _) in zip(c, c[1:]):
        v = ju.speed_at(x)
        assert k == 0 or (k == 1 and v >= 7) or (k == 2 and v >= 10)
        gap = ju.time_at(x2) - ju.time_at(x + ju.WIDTH[k])
        assert gap >= ju.JT + 0.3                           # time to land and jump again
        a, b = ju.window(x, k)
        assert ju.clears((a + b) / 2 - ju.JT / 2, x, k)      # every obstacle can be jumped
    assert {k for _, k in c} == {0, 1, 2}
    assert abs(ju.dist(ju.time_at(1234.5)) - 1234.5) < 1e-6 and ju.dist(-1) == 0


def test_jump_physics():
    x, k = ju.course(1, 100)[0]
    a, b = ju.window(x, k)
    good = (a + b) / 2 - ju.JT / 2
    assert ju.clears(good, x, k)
    assert not ju.clears(good - 0.3, x, k) and not ju.clears(good + 0.3, x, k)


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_the_app_builds_the_same_course():
    src = (WEB / "jump.js").read_text(encoding="utf-8").split("function jumpRulesView")[0]
    code = src + "\nconsole.log(JSON.stringify([1, 77, 2147483646].map(s => juCourse(s, 6000).map(o => [o[0], o[1]]))));"
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30, check=True).stdout
    js = json.loads(out)
    py = [[[x, k] for x, k in ju.course(s, 6000)] for s in (1, 77, 2147483646)]
    assert js == py


# ---------------------------------------------------------------- lives, elimination, ranking
def test_setup_one_seed_and_lives_for_everybody():
    t, clock = table(3, lives=5)
    assert t.st["phase"] == "play" and t.st["seed"] == 7 and t.st["t0"] == clock.t + ju.COUNTDOWN
    assert all(r["lives"] == 5 and r["out"] is None for r in t.st["run"].values())


def test_hits_cost_lives_once_with_invulnerability():
    t, clock = table(2)
    obs = t.obstacles(200)
    hit(t, clock, "1", 0)
    r = t.st["run"]["1"]
    assert r["lives"] == 2 and [i for i, _ in r["hits"]] == [0]
    hit(t, clock, "1", 0)                                     # the same obstacle again: nothing
    assert r["lives"] == 2
    a1, _ = ju.window(*obs[1])
    at(t, clock, a1 + 0.5)
    t.report("1", a1 + 0.4, [], [[1, r["hits"][0][1] + 0.3]])  # within the invulnerability: nothing
    assert r["lives"] == 2
    # insane values: an obstacle far away, a time in the future, garbage
    t.report("1", None, ["x", 1e9, float("nan")], [[50, 1.0], [1, 9999], ["a", "b"], [2]])
    assert r["lives"] == 2 and r["jumps"] == []
    assert t.st["run"]["2"]["lives"] == 3                    # only the own player


def test_jumps_are_kept_and_checked():
    t, clock = table(2)
    at(t, clock, 5)
    t.report("1", 5, [1.0, 1.1, 2.0, 7.5], [])
    assert t.st["run"]["1"]["jumps"] == [1.0, 2.0]           # one in the air ignored, one in the future ignored
    t.report("1", 5, [1.0, 2.0], [])                         # sent again: nothing new
    assert t.st["run"]["1"]["jumps"] == [1.0, 2.0]
    with pytest.raises(CommunityError):
        t.report("9", 5, [3.0], [])


def test_elimination_and_last_one_alive_wins():
    t, clock = table(3)
    for i in range(3):
        hit(t, clock, "2", i)
    assert t.st["run"]["2"]["out"] is not None and t.st["phase"] == "play"
    for i in range(3, 6):
        hit(t, clock, "3", i)
    assert t.st["phase"] == "done" and t.st["complete"]
    assert t.st["places"] == {"1": 1, "3": 2, "2": 3} and t.st["ranking"] == ["1", "3", "2"]
    sc = t.st["scores"]
    assert sc["1"] >= sc["3"] > sc["2"] > 0
    with pytest.raises(CommunityError):
        t.report("1", 1, [], [])


def test_the_same_moment_shares_the_place():
    t, clock = table(2)
    a, b = ju.window(*t.obstacles(200)[2])
    at(t, clock, b + 0.2)
    for p in ("1", "2"):
        t.st["run"][p].update(lives=1)
    t.report("1", b, [], [[2, a]])
    assert t.st["phase"] == "play"                              # 2 is still alive – a moment of grace
    t.report("2", b, [], [[2, a]])
    assert t.st["phase"] == "done" and t.st["places"] == {"1": 1, "2": 1}


def test_solo_runs_until_out_even_when_the_bots_are_gone():
    t, clock = table(1, bots=1, solo=True)
    t.st["run"]["bot1"].update(lives=0, out=1.0)
    at(t, clock, 30)
    t.report("1", 30, [], [])
    assert t.st["phase"] == "play"                              # alone in front: run on for the high score
    for i in range(3):
        hit(t, clock, "1", i + 5)
    assert t.st["phase"] == "done" and t.st["places"] == {"1": 1, "bot1": 2}


def test_family_table_ends_when_no_person_is_left():
    t, clock = table(1, bots=2, level="hard")
    for i in range(3):
        hit(t, clock, "1", i)
    assert t.st["phase"] == "done" and t.st["places"]["1"] == 3


def test_a_silent_app_is_out():
    t, clock = table(2)
    at(t, clock, 4)
    t.report("1", 4, [], [])
    at(t, clock, 4 + ju.STALE + 1)
    t.st["run"]["2"]["seen"] = clock.t
    t.tick()
    assert t.st["run"]["1"]["out"] == 4 and t.st["phase"] == "done" and t.st["ranking"][0] == "2"


def test_leader_ends_the_game_as_it_stands():
    t, clock = table(3)
    hit(t, clock, "2", 0)
    for i in range(1, 4):
        hit(t, clock, "3", i)
    t.end()
    assert t.st["phase"] == "done" and t.st["places"] == {"1": 1, "2": 2, "3": 3}


def test_max_time_ends_everybody_on_place_one():
    t, clock = table(2)
    at(t, clock, ju.MAX_T + 1)
    for p in ("1", "2"):
        t.st["run"][p]["seen"] = clock.t
    t.tick()
    assert t.st["phase"] == "done" and t.st["places"] == {"1": 1, "2": 1}


# ---------------------------------------------------------------- bots
def _bot_run(level, rng_seed):
    t, clock = table(1, bots=1, level=level, solo=True, rng_seed=rng_seed)
    for s in range(0, 600):
        at(t, clock, s)
        t.st["run"]["1"]["seen"] = clock.t
        t.tick()
        if t.st["run"]["bot1"]["out"] is not None:
            break
    return t


def test_bots_jump_and_lose_lives():
    t = _bot_run("easy", 3)
    r = t.st["run"]["bot1"]
    assert r["out"] is not None and len(r["hits"]) == 3 and len(r["jumps"]) == 8
    assert all(b >= a + ju.JT for a, b in zip(r["jumps"], r["jumps"][1:]))
    hs = [h[1] for h in r["hits"]]
    assert all(b >= a + ju.INVULN for a, b in zip(hs, hs[1:]))


def test_hard_bots_last_longer_than_easy():
    easy = sorted(_bot_run("easy", s).st["run"]["bot1"]["out"] or 600 for s in range(6))
    hard = sorted(_bot_run("hard", s).st["run"]["bot1"]["out"] or 600 for s in range(6))
    assert sum(hard) > sum(easy) * 1.5


def test_bots_plan_ahead_but_a_late_miss_does_not_count_after_the_end():
    t, clock = table(1, bots=1, level="easy", rng_seed=5)
    at(t, clock, 10)
    t.st["run"]["1"]["seen"] = clock.t
    t.tick()
    assert t.st["run"]["bot1"]["jumps"] and max(t.st["run"]["bot1"]["jumps"]) <= 10 + ju.LOOKAHEAD
    t.st["run"]["bot1"].update(out=10.5, lives=0)
    t.end()
    assert t.st["run"]["bot1"]["out"] is None and t.st["run"]["bot1"]["lives"] == 1


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _clock(fq):
    c = Clock(2_000_000_000.0)
    fq.jump.now = c
    return c


def test_family_table_same_course_lives_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    assert client.get("/api/parent/game-rewards", headers=phd).json()["jump"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"jump": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/jump/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/jump/start", json={"bots": 0, "lives": 3}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"]
    assert client.post("/api/community/jump/sync", json={"t": 0}, headers=hm).status_code == 400   # not started
    assert client.post("/api/community/jump/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/jump/begin", headers=hl).status_code == 403                # Leo does not lead
    st = client.post("/api/community/jump/begin", headers=hm).json()
    assert st["phase"] == "play" and st["lives0"] == 3 and st["t0"] == clock.t + ju.COUNTDOWN
    lv = client.get("/api/community/jump", headers=hl).json()
    assert lv["seed"] == st["seed"] and lv["t0"] == st["t0"]                                       # the same course
    assert client.get("/api/me", headers=hl).json()["community"]["jump"]["joined"]
    obs = ju.course(st["seed"], 300)
    # Mia jumps and hits obstacle 0 – only her own player changes
    a, b = ju.window(*obs[0])
    clock.t = st["t0"] + b + 0.2
    v = client.post("/api/community/jump/sync", json={"t": b + 0.1, "jumps": [0.5], "hits": [[0, a]]}, headers=hm).json()
    me = next(p for p in v["players"] if p["id"] == str(mia))
    other = next(p for p in v["players"] if p["id"] == str(leo))
    assert me["lives"] == 2 and me["jumps"] == [0.5] and other["lives"] == 3 and other["jumps"] == []
    assert client.post("/api/community/jump/sync", json={"t": 1, "hits": [[0, 1, 2]] * 30}, headers=hm).status_code == 422
    # Leo hits three obstacles: out – Mia wins
    for i in (1, 2, 3):
        a, b = ju.window(*obs[i])
        clock.t = st["t0"] + b + 0.2
        client.post("/api/community/jump/sync", json={"t": b}, headers=hm)
        v = client.post("/api/community/jump/sync", json={"t": b, "hits": [[i, a]]}, headers=hl).json()
    assert v["phase"] == "play"                                                                    # a moment of grace
    clock.t += ju.GRACE
    v = client.post("/api/community/jump/sync", json={"t": b + ju.GRACE}, headers=hm).json()
    assert v["phase"] == "done" and v["complete"]
    res = {p["id"]: (p["place"], p["coins"]) for p in v["players"]}
    assert res == {str(mia): (1, 8), str(leo): (2, 4)}
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", st["game"])
    fq.jump._save(row, json.loads(row["state"]))                                                   # paid once
    client.get("/api/community/jump", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"jump:{st['game']}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"jump:{st['game']}:{mia}")["reason"] == "Jump – Platz 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "jump" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["coins"] == 8
    assert hist[0]["data"]["record"] and hist[0]["data"]["score"] > 0
    # the «No. 1» hat for the winner
    av = lambda pid: fq.avatar_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid), {"items": {}})["items"].get("hat")
    assert av(mia) == "champion" and av(leo) is None
    # a sync after the end answers with the result
    v = client.post("/api/community/jump/sync", json={"t": 1}, headers=hl).json()
    assert v["phase"] == "done"


def test_solo_high_score_and_personal_best(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm = login(client, mia, "1111")
    st = client.post("/api/community/jump/start", json={"solo": True, "bots": 0, "lives": 1}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 1 and not st["coins_on"] and st["best"] == 0
    obs = ju.course(st["seed"], 2000)
    a, b = ju.window(*obs[20])
    clock.t = st["t0"] + b + 0.2
    v = client.post("/api/community/jump/sync", json={"t": b, "hits": [[20, a]]}, headers=hm).json()
    assert v["phase"] == "done" and v["players"][0]["record"] and v["players"][0]["score"] == int(ju.dist(round(a, 3)))
    assert v["best"] == v["players"][0]["score"] and v["players"][0]["coins"] == 0
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'jump:%'")
    best = v["best"]
    # a worse run: the best stays
    st = client.post("/api/community/jump/start", json={"solo": True}, headers=hm).json()
    a, b = ju.window(*ju.course(st["seed"], 300)[1])
    clock.t = st["t0"] + b + 0.2
    v = client.post("/api/community/jump/sync", json={"t": b, "hits": [[1, a]]}, headers=hm).json()
    assert v["phase"] == "done" and not v["players"][0]["record"] and v["best"] == best
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "jump" and hist[0]["data"]["players"] == 1 and not hist[0]["data"]["record"]
    assert client.get("/api/community/jump", headers=login(client, leo)).json() is None


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    _clock(fq)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/jump/start", json={"bots": 1, "level": "easy"}, headers=hm)
    client.post("/api/community/jump/join", headers=hl)
    st = client.post("/api/community/jump/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"]
    assert client.post("/api/community/jump/end", headers=hl).status_code == 403
    v = client.post("/api/community/jump/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'jump:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='jump'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.jump.clean_rules("jump", {"bots": 9, "level": "x", "lives": 4}) == {"bots": 5, "level": "normal", "lives": 3}
    fq.jump.start("jump", kid, {"bots": 2, "level": "hard", "lives": 5}, solo=True)
    assert fq.jump.default_rules() == {"bots": 2, "level": "hard", "lives": 5}
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='jump'")["state"])
    assert len(st["players"]) == 3 and st["players"][1]["level"] == "hard" and st["run"]["bot1"]["lives"] == 5


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/jump/start", json={"bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "jump"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Jump"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end"):
        assert client.post("/api/community/jump/" + path, json={}, headers=hg).status_code in (401, 403), path
    st = client.post("/api/community/jump/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    assert client.post("/api/community/jump/sync", json={"t": 0, "jumps": [0]}, headers=hg).status_code == 200
    client.post("/api/community/jump/end", headers=hm)
    for p in ("", "/join", "/sync"):
        assert netfilter.is_guest_path("/api/community/jump" + p), p
    for p in ("/start", "/begin", "/end", "/rules"):
        assert not netfilter.is_guest_path("/api/community/jump" + p), p


def test_switched_off_blocks_it(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "jump" in client.get("/api/me", headers=hm).json()["games_list"]
    assert client.put("/api/parent/games", json={"access": {"jump": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/jump", headers=hm).status_code == 403
    assert client.post("/api/community/jump/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "jump" not in me["games_list"] and me["community"]["jump"] is None


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/jump/start", json={"solo": True, "bots": 2}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "jump")
    assert g["title"] == "Jump" and g["icon"] == "🦘" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "jump" for x in r["running"])
    v = client.get("/api/community/jump", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]
