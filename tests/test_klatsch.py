"""«Klatsch den Beat» – patterns, judging, rounds on the game clock, ranking, bots, the table in the app."""
import json
import random

import pytest

from familyquest import klatsch as kb
from familyquest.community import CommunityError


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(n=2, bots=0, level="normal", solo=False, rounds=6, rng_seed=1):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "klatsch", "rules": {**kb.DEFAULTS, "rounds": rounds}, "players": players, "phase": "lobby", "solo": solo}
    clock = Clock()
    t = kb.Table(st, random.Random(rng_seed), now=clock)
    t.setup()
    return t, clock


def at(t, clock, gt):
    clock.t = t.st["t0"] + gt


def clap_end(t, i):
    return kb.Table.times(t.st["rounds"][i])[3]


# ---------------------------------------------------------------- patterns and judging
def test_patterns_get_harder_and_stay_playable():
    rng = random.Random(3)
    for n in kb.ROUNDS:
        bpms = [kb.tempo(i, n) for i in range(n)]
        assert bpms[0] == 80 and bpms[-1] == 140 and bpms == sorted(bpms)
        for _ in range(40):
            pats = [kb.pattern(i, n, rng) for i in range(n)]
            for p in pats:
                assert 3 <= len(p) <= 6 and all(0 <= x < 16 for x in p)
                assert all(b - a >= 2 for a, b in zip(p, p[1:]))           # at least an eighth apart
            assert pats[0][0] == 0 and all(x % 2 == 0 for x in pats[0])     # easy start: on the one, no 16ths
            assert any(x % 2 == 1 for x in pats[-1])                        # the last one: 16th syncopes


def test_judge_takes_the_nearest_tap_and_counts_extras():
    notes = [1.0, 1.25, 1.5]
    got, extras = kb.judge(notes, [1.03, 1.14, 1.27, 2.0])
    assert got[0] == pytest.approx(0.03) and got[1] == pytest.approx(0.02) and got[2] is None and extras == 2
    res = kb.score_of(got, extras)
    assert res == {"p": 2, "g": 0, "m": 1, "x": 2, "pts": 200 - 2 * kb.EXTRA}
    got, extras = kb.judge(notes, [1.1, 1.62])                               # 100 ms and 120 ms off: good
    assert kb.score_of(got, extras) == {"p": 0, "g": 2, "m": 1, "x": 0, "pts": 100}
    assert kb.score_of(*kb.judge(notes, [0.5] * 20))["pts"] == 0            # drumming: never below 0


# ---------------------------------------------------------------- rounds on the clock
def test_schedule_and_scoring_per_round():
    t, clock = table(2)
    rs = t.st["rounds"]
    assert len(rs) == 6 and rs[0]["start"] == 0 and t.st["t0"] == clock.t + kb.COUNTDOWN
    for a, b in zip(rs, rs[1:]):
        assert b["start"] == pytest.approx(kb.Table.times(a)[3] + kb.PAUSE, abs=1e-3)
    notes = kb.Table.note_times(rs[0])
    at(t, clock, notes[-1] + 0.05)
    t.report("1", 0, [x + 0.01 for x in notes])                    # perfect
    t.report("1", 0, [notes[0] + 0.012])                            # sent again: no extra tap
    t.report("2", 0, [x + 0.1 for x in notes[:-1]])                 # good, one missed
    t.report("2", 0, [notes[-1] + 50, float("nan"), "x"])           # garbage, the future
    t.tick()
    assert t.st["scored"] == 0                                      # the grace is not over yet
    at(t, clock, clap_end(t, 0) + kb.GRACE + 0.001)
    t.tick()
    n = len(notes)
    assert t.st["scored"] == 1
    assert t.st["run"]["1"]["res"][0]["pts"] == n * 100 and t.st["run"]["1"]["res"][0]["x"] == 0
    assert t.st["run"]["2"]["res"][0] == {"p": 0, "g": n - 1, "m": 1, "x": 0, "pts": (n - 1) * 50, "d": [100] * (n - 1) + [None]}
    t.report("2", 0, notes)                                         # too late: the round is scored
    assert t.st["run"]["2"]["total"] == (n - 1) * 50


def test_taps_only_for_the_own_player():
    t, clock = table(2, bots=1)
    at(t, clock, 2)
    with pytest.raises(CommunityError):
        t.report("9", 0, [1.0])
    with pytest.raises(CommunityError):
        t.report("bot1", 0, [1.0])
    t.report("1", 0, [kb.Table.times(t.st["rounds"][0])[2] + 0.1])
    assert t.st["run"]["2"]["taps"] == {}


def test_game_ends_after_the_last_round_with_places():
    t, clock = table(3, rounds=5)
    for i in range(5):
        notes = kb.Table.note_times(t.st["rounds"][i])
        at(t, clock, notes[-1] + 0.01)
        t.report("1", i, notes)
        t.report("2", i, notes)
        t.report("3", i, notes[:1])
        at(t, clock, clap_end(t, i) + kb.GRACE + 0.001)
        t.tick()
    assert t.st["phase"] == "done" and t.st["complete"]
    assert t.st["places"] == {"1": 1, "2": 1, "3": 3} and t.st["ranking"] == ["1", "2", "3"]
    assert t.st["acc"]["1"] == 100 and t.st["acc"]["3"] < 40
    with pytest.raises(CommunityError):
        t.report("1", 4, [])


def test_silent_players_get_nothing_and_a_late_tick_scores_everything():
    t, clock = table(2, rounds=5)
    at(t, clock, 999)
    t.tick()
    assert t.st["phase"] == "done" and t.st["scored"] == 5 and t.st["places"] == {"1": 1, "2": 1}
    assert t.st["scores"] == {"1": 0, "2": 0}


def test_leader_ends_as_it_stands():
    t, clock = table(2)
    notes = kb.Table.note_times(t.st["rounds"][0])
    at(t, clock, clap_end(t, 0) + 0.2)                              # round 0 over (grace still running)
    t.report("2", 0, notes)
    t.end()
    assert t.st["phase"] == "done" and not t.st["complete"] and t.st["scored"] == 1 and t.st["ranking"][0] == "2"


# ---------------------------------------------------------------- bots
def _bot_total(level, seed):
    t, clock = table(1, bots=1, level=level, solo=True, rng_seed=seed)
    at(t, clock, 999)
    t.tick()
    return t.st["acc"]["bot1"]


def test_bots_clap_and_hard_bots_are_better():
    easy = sum(_bot_total("easy", s) for s in range(8))
    hard = sum(_bot_total("hard", s) for s in range(8))
    assert 0 < easy < hard and hard / 8 > 70


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _clock(fq):
    c = Clock(2_000_000_000.0)
    fq.klatsch.now = c
    return c


def test_family_table_coins_once_history_and_hat(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    assert client.get("/api/parent/game-rewards", headers=phd).json()["klatsch"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"klatsch": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/klatsch/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/klatsch/start", json={"bots": 0, "rounds": 5}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"]
    assert client.post("/api/community/klatsch/sync", json={"round": 0, "taps": []}, headers=hm).status_code == 400
    assert client.post("/api/community/klatsch/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/klatsch/begin", headers=hl).status_code == 403          # Leo does not lead
    st = client.post("/api/community/klatsch/begin", headers=hm).json()
    assert st["phase"] == "play" and st["n_rounds"] == 5 and st["t0"] == clock.t + kb.COUNTDOWN
    assert [r["i"] for r in st["rounds"]] == [0] and st["now"] == clock.t                    # only the first pattern yet
    assert client.get("/api/me", headers=hl).json()["community"]["klatsch"]["joined"]
    assert client.post("/api/community/klatsch/sync", json={"round": 0, "taps": [0.1] * 70}, headers=hm).status_code == 422
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", st["game"])
    rounds = json.loads(row["state"])["rounds"]
    for i, rd in enumerate(rounds):
        notes = kb.Table.note_times(rd)
        clock.t = st["t0"] + notes[-1] + 0.05
        v = client.post("/api/community/klatsch/sync", json={"round": i, "taps": notes}, headers=hm).json()
        client.post("/api/community/klatsch/sync", json={"round": i, "taps": [x + 0.1 for x in notes]}, headers=hl)
        clock.t = st["t0"] + kb.Table.times(rd)[3] + kb.GRACE + 0.001
        v = client.get("/api/community/klatsch", headers=hl).json()
        if i < 4:
            assert v["scored"] == i + 1 and v["phase"] == "play"
            me = next(p for p in v["players"] if p["id"] == str(mia))
            assert me["last"]["p"] == len(notes) and me["place"] == 1
    assert v["phase"] == "done" and v["complete"]
    res = {p["id"]: (p["place"], p["coins"], p["acc"]) for p in v["players"]}
    assert res == {str(mia): (1, 8, 100), str(leo): (2, 4, 50)}
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", st["game"])
    fq.klatsch._save(row, json.loads(row["state"]))                                            # paid once
    client.get("/api/community/klatsch", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"klatsch:{st['game']}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"klatsch:{st['game']}:{mia}")["reason"] == "Klatsch den Beat – Platz 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "klatsch" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["coins"] == 8
    assert hist[0]["data"]["acc"] == 100 and hist[0]["data"]["record"]
    av = lambda pid: fq.avatar_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid), {"items": {}})["items"].get("hat")
    assert av(mia) == "champion" and av(leo) is None
    v = client.post("/api/community/klatsch/sync", json={"round": 1, "taps": [1]}, headers=hl).json()
    assert v["phase"] == "done"


def test_solo_personal_best(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm = login(client, mia, "1111")
    st = client.post("/api/community/klatsch/start", json={"solo": True, "bots": 0, "rounds": 5}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 1 and not st["coins_on"] and st["best"] == 0
    rd = st["rounds"][0]
    notes = kb.Table.note_times(rd)
    clock.t = st["t0"] + notes[-1] + 0.05
    client.post("/api/community/klatsch/sync", json={"round": 0, "taps": notes}, headers=hm)
    clock.t = st["t0"] + 999
    v = client.get("/api/community/klatsch", headers=hm).json()
    acc = v["players"][0]["acc"]
    assert v["phase"] == "done" and v["players"][0]["record"] and 0 < acc < 100 and v["best"] == acc
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'klatsch:%'")
    # a worse game: the best stays; a game ended early never counts
    st = client.post("/api/community/klatsch/start", json={"solo": True}, headers=hm).json()
    clock.t = st["t0"] + 999
    v = client.get("/api/community/klatsch", headers=hm).json()
    assert v["phase"] == "done" and not v["players"][0]["record"] and v["best"] == acc
    assert fq.community.history(mia)[0]["data"]["players"] == 1
    assert client.get("/api/community/klatsch", headers=login(client, leo)).json() is None


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    _clock(fq)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/klatsch/start", json={"bots": 1, "level": "easy"}, headers=hm)
    client.post("/api/community/klatsch/join", headers=hl)
    st = client.post("/api/community/klatsch/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"]
    assert client.post("/api/community/klatsch/end", headers=hl).status_code == 403
    v = client.post("/api/community/klatsch/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'klatsch:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='klatsch'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.klatsch.clean_rules("klatsch", {"bots": 99, "level": "x", "rounds": 12}) == {"bots": 7, "level": "normal", "rounds": 6}
    fq.klatsch.start("klatsch", kid, {"bots": 2, "level": "hard", "rounds": 8}, solo=True)
    assert fq.klatsch.default_rules() == {"bots": 2, "level": "hard", "rounds": 8}
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='klatsch'")["state"])
    assert len(st["players"]) == 3 and st["players"][1]["level"] == "hard" and len(st["rounds"]) == 8


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/klatsch/start", json={"bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "klatsch"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Klatsch den Beat"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end"):
        assert client.post("/api/community/klatsch/" + path, json={}, headers=hg).status_code in (401, 403), path
    st = client.post("/api/community/klatsch/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    assert client.post("/api/community/klatsch/sync", json={"round": 0, "taps": []}, headers=hg).status_code == 200
    client.post("/api/community/klatsch/end", headers=hm)
    for p in ("", "/join", "/sync"):
        assert netfilter.is_guest_path("/api/community/klatsch" + p), p
    for p in ("/start", "/begin", "/end", "/rules"):
        assert not netfilter.is_guest_path("/api/community/klatsch" + p), p


def test_switched_off_blocks_it(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "klatsch" in client.get("/api/me", headers=hm).json()["games_list"]
    assert client.put("/api/parent/games", json={"access": {"klatsch": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/klatsch", headers=hm).status_code == 403
    assert client.post("/api/community/klatsch/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "klatsch" not in me["games_list"] and me["community"]["klatsch"] is None


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/klatsch/start", json={"solo": True, "bots": 2}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "klatsch")
    assert g["title"] == "Clap the Beat" and g["icon"] == "👏" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "klatsch" for x in r["running"])
    v = client.get("/api/community/klatsch", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]
