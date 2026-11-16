import random

import pytest

from familyquest import domino as dm
from familyquest.community import CommunityError


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def table(n=4, bots=0, seed=3, **rules):
    r = {**dm.DEFAULTS, **rules}
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": "normal"} for i in range(1, bots + 1)]
    st = {"kind": "domino", "rules": r, "players": players, "phase": "lobby"}
    clock = Clock()
    t = dm.Table(st, random.Random(seed), now=clock)
    t.deal()
    return t, clock


def all_tiles(t):
    return [x for h in t.st["hands"].values() for x in h] + t.st["boneyard"] + [f"{min(a, b)}-{max(a, b)}" for a, b in t.st["line"]]


def test_deal_sets_and_hand_sizes():
    assert len(dm.tiles(6)) == 28 and len(dm.tiles(9)) == 55
    t, _ = table(4, mode="cuban", set=9)
    assert all(len(h) == 10 for h in t.st["hands"].values()) and len(t.st["boneyard"]) == 15
    tl = all_tiles(t)
    assert len(tl) == 55 and len(set(tl)) == 55 and t.st["teams"]
    t, _ = table(2, mode="simple", set=6, teams=False, draw=True)
    assert all(len(h) == 7 for h in t.st["hands"].values()) and len(set(all_tiles(t))) == 28 and not t.st["teams"]
    t, _ = table(3, mode="simple", set=9, teams=True)               # teams need an even number (≥ 4)
    assert all(len(h) == 10 for h in t.st["hands"].values()) and not t.teams()
    t, _ = table(8, mode="cuban", set=6)                             # few tiles, many players: fewer each
    assert all(len(h) == 3 for h in t.st["hands"].values())
    # the highest double leads
    t, _ = table(4, mode="cuban", set=9)
    best = next(f"{d}-{d}" for d in range(9, -1, -1) if any(f"{d}-{d}" in h for h in t.st["hands"].values()))
    assert best in t.st["hands"][t.st["turn"]]


def test_play_on_ends_choose_end_and_wrong_tile():
    t, _ = table(2, mode="simple", set=6, teams=False, draw=True)
    st = t.st
    st["hands"]["1"] = ["3-5", "1-2", "4-6"]
    st["hands"]["2"] = ["5-6", "2-3", "0-0"]
    st["turn"], st["line"] = "1", []
    t.play("1", "3-5")                                               # first tile: anything
    assert st["line"] == [[3, 5]] and st["turn"] == "2"
    assert t.playable("2") == {"5-6": ["right"], "2-3": ["left"]}
    with pytest.raises(CommunityError):
        t.play("2", "0-0")                                           # does not fit
    with pytest.raises(CommunityError):
        t.play("1", "1-2")                                           # not your turn
    t.play("2", "2-3")                                               # only the left end fits: placed by itself
    assert st["line"] == [[2, 3], [3, 5]] and t.ends() == (2, 5)
    st["hands"]["1"] = ["2-5", "6-6"]
    with pytest.raises(CommunityError):
        t.play("1", "2-5")                                           # fits on both ends: choose
    with pytest.raises(CommunityError):
        t.play("1", "6-6", "left")
    t.play("1", "2-5", "left")
    assert st["line"][0] == [5, 2] and t.ends() == (5, 5)


def test_pass_only_when_nothing_fits_and_draw_first():
    t, _ = table(2, mode="simple", set=6, teams=False, draw=True)
    st = t.st
    st["line"], st["turn"] = [[1, 1]], "1"
    st["hands"]["1"] = ["1-4", "2-3"]
    st["hands"]["2"] = ["5-6", "2-2"]
    st["boneyard"] = ["0-5", "1-6"]
    with pytest.raises(CommunityError):
        t.pass_turn("1")                                             # 1-4 fits
    t.play("1", "1-4", "right")
    assert t.can_draw("2") and not t.must_pass("2")
    with pytest.raises(CommunityError):
        t.pass_turn("2")                                             # draw first
    assert t.draw("2") == "1-6"
    assert t.playable("2") == {"1-6": ["left"]}
    with pytest.raises(CommunityError):
        t.draw("2")                                                  # a tile fits now
    # Cuban: no drawing, pass at once
    t, _ = table(4, mode="cuban", set=9)
    st = t.st
    st["line"], st["turn"] = [[9, 9]], "1"
    st["hands"] = {"1": ["0-1", "2-3"], "2": ["4-9", "0-0"], "3": ["5-9"], "4": ["6-9"]}
    assert t.must_pass("1") and not t.can_draw("1")
    with pytest.raises(CommunityError):
        t.draw("1")
    t.pass_turn("1")
    assert st["passes"] == ["1"] and st["turn"] == "2"
    t.play("2", "4-9", "right")
    assert st["passes"] == []


def test_blocked_round_simple_scoring_and_tie():
    t, _ = table(3, mode="simple", set=6, teams=False, draw=False)
    st = t.st
    st["line"], st["turn"] = [[6, 6], [6, 1]], "1"
    st["hands"] = {"1": ["0-1", "5-5"], "2": ["2-3", "4-4"], "3": ["0-2"]}
    st["boneyard"] = []
    t.play("1", "0-1", "right")                                      # ends 6 / 0 – 2: 2-3, 4-4 no; 3: 0-2 fits
    assert st["phase"] == "play"
    t.pass_turn("2")
    assert st["passes"] == ["2"] and st["last"]["passed"]
    t.play("3", "0-2", "right")                                      # player 3 dominoes: scores the others' pips (10 + 13)
    assert st["phase"] == "between" and st["scores"]["3"] == 23 and st["sheet"][-1]["reason"] == "domino"
    # blocked: the lowest pip total wins and scores the opponents' pips
    t, _ = table(3, mode="simple", set=6, teams=False, draw=False)
    st = t.st
    st["line"], st["turn"], st["boneyard"] = [[5, 5]], "1", []
    st["hands"] = {"1": ["0-5", "1-1"], "2": ["2-3", "4-4"], "3": ["0-2", "6-6"]}
    t.play("1", "0-5", "right")                                      # ends 5 / 0 – 2: no; 3: 0-2 → fits
    t.pass_turn("2")
    t.play("3", "0-2", "right")                                      # ends 5 / 2: 2 has 2-3
    t.pass_turn("1")
    t.play("2", "2-3", "right")                                      # ends 5 / 3: nobody (1-1, 4-4, 6-6) → blocked
    assert st["phase"] == "between"
    res = st["sheet"][-1]
    assert res["reason"] == "blocked" and res["side"] == "1" and res["points"] == 8 + 12 and st["scores"]["1"] == 20
    assert st["next_starter"] == "1"
    # a tie: no points, the same starters
    t, _ = table(2, mode="simple", set=6, teams=False, draw=False)
    st = t.st
    st["starter"] = "2"
    st["line"], st["turn"], st["boneyard"] = [[5, 5]], "1", []
    st["hands"] = {"1": ["1-5", "2-2"], "2": ["1-3"]}
    t.play("1", "1-5", "right")
    t.play("2", "1-3", "right")                                      # 2 dominoes
    assert st["scores"] == {"1": 0, "2": 4}
    t.deal()
    st["line"], st["turn"], st["boneyard"] = [[6, 6]], "1", []
    st["hands"] = {"1": ["0-6", "2-2"], "2": ["1-3"]}
    t.play("1", "0-6", "right")                                      # ends 6 / 0: 4 against 4 → tie
    res = st["sheet"][-1]
    assert res["tie"] and res["points"] == 0 and st["scores"] == {"1": 0, "2": 4} and st["next_starter"] == "2"


def test_cuban_scoring_all_hands_and_winning_team_starts():
    t, clock = table(4, mode="cuban", set=9)
    st = t.st
    st["line"], st["turn"] = [[9, 9]], "1"
    st["hands"] = {"1": ["0-9"], "2": ["1-1"], "3": ["2-3"], "4": ["4-4"]}
    t.play("1", "0-9", "right")
    res = st["sheet"][-1]
    assert res["side"] == "0" and res["points"] == 2 + 5 + 8               # the partner's pips (seat 3) count too
    assert st["scores"] == {"0": 15, "1": 0}
    clock.t += 7
    assert t.tick()                                                      # next round: team 0 leads
    assert st["round"] == 2 and st["turn"] == "team:0"
    assert t.my_turn("1") and t.my_turn("3") and not t.my_turn("2")
    with pytest.raises(CommunityError):
        t.play("2", st["hands"]["2"][0])
    tile = st["hands"]["3"][0]
    t.play("3", tile)                                                    # any member may lead – then the rotation goes on
    assert st["turn"] == "4" and len(st["line"]) == 1


def test_target_and_pollona():
    t, _ = table(4, mode="cuban", set=9, target=100)
    st = t.st
    st["scores"] = {"0": 90, "1": 0}
    st["line"], st["turn"] = [[9, 9]], "2"
    st["hands"] = {"1": ["1-1"], "2": ["8-9"], "3": ["2-3"], "4": ["4-4"]}
    t.play("2", "8-9", "right")
    assert st["phase"] == "between" and st["scores"]["1"] == 15
    t.deal()
    st["scores"] = {"0": 95, "1": 0}
    st["line"], st["turn"] = [[9, 9]], "1"
    st["hands"] = {"1": ["0-9"], "2": ["1-1"], "3": ["2-3"], "4": ["4-4"]}
    t.play("1", "0-9", "right")
    assert st["phase"] == "done" and st["winner"] == "0" and st["pollona"]
    assert st["ranking"][:2] == ["1", "3"]
    t, _ = table(4, mode="cuban", set=9, target=100)
    st = t.st
    st["scores"] = {"0": 95, "1": 5}
    st["line"], st["turn"] = [[9, 9]], "1"
    st["hands"] = {"1": ["0-9"], "2": ["1-1"], "3": ["2-3"], "4": ["4-4"]}
    t.play("1", "0-9", "right")
    assert st["phase"] == "done" and not st["pollona"]


@pytest.mark.parametrize("rules", [{"mode": "cuban", "set": 9}, {"mode": "simple", "set": 6, "teams": False, "draw": True},
                                   {"mode": "simple", "set": 9, "teams": True, "draw": True, "target": 150}])
def test_bots_play_a_whole_match(rules):
    for seed in range(3):
        t, clock = table(0, bots=4, seed=seed, **rules)
        for _ in range(20000):
            if t.st["phase"] == "done":
                break
            clock.t += 2
            t.tick()
        assert t.st["phase"] == "done", (rules, seed)
        assert max(t.st["scores"].values()) >= t.st["rules"]["target"] and len(t.st["ranking"]) == 4


def test_api_solo_and_family(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    rules = client.get("/api/community/domino/rules", headers=hm).json()
    assert rules["mode"] == "cuban" and rules["set"] == 9 and rules["teams"] and not rules["draw"] and rules["target"] == 100
    # alone against three bots: dealt at once, private, teams
    st = client.post("/api/community/domino/start", json={"solo": True, "bots": 3}, headers=hm).json()
    assert st["phase"] == "play" and st["solo"] and st["teams"] and len(st["hand"]) == 10 and len(st["players"]) == 4
    assert client.get("/api/community/domino", headers=hl).json() is None             # Leo does not see Mia's table
    # the family table: Leo opens (simple rules, one bot), Mia joins
    st = client.post("/api/community/domino/start", json={"mode": "simple", "set": 6, "teams": False, "draw": True, "bots": 1},
                     headers=hl).json()
    assert st["phase"] == "lobby"
    assert client.post("/api/community/domino/end", headers=hm).status_code == 200      # Mia ends her own table
    assert client.post("/api/community/domino/begin", headers=hm).status_code == 403    # Mia does not lead Leo's
    client.post("/api/community/domino/join", headers=hm)
    st = client.post("/api/community/domino/begin", headers=hl).json()
    assert st["phase"] == "play" and len(st["players"]) == 3 and len(st["hand"]) == 7 and st["boneyard"] == 28 - 21
    fq = client.app.state.fq
    import json as _json
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='domino' AND solo=0 AND status!='done'")
    s = _json.loads(row["state"])
    s["turn"], s["turn_at"] = str(leo), 1e12
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", _json.dumps(s), row["id"])
    view = client.get("/api/community/domino", headers=hl).json()
    assert view["my_turn"] and view["playable"]
    tile = next(iter(view["playable"]))
    assert client.post("/api/community/domino/play", json={"tile": tile}, headers=hm).status_code == 400   # not Mia's turn
    r = client.post("/api/community/domino/play", json={"tile": tile}, headers=hl)
    assert r.status_code == 200 and r.json()["line"] and tile not in r.json()["hand"]
    assert client.post("/api/community/domino/pass", headers=hl).status_code == 400
    # summary for the start page, the end
    assert client.get("/api/me", headers=hm).json()["community"]["domino"]["joined"]
    assert client.post("/api/community/domino/end", headers=hl).status_code == 200


def test_domino_switched_off(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    assert client.put("/api/parent/games", json={"access": {"domino": {"mode": "off"}}}, headers=ph).status_code == 200
    assert client.get("/api/community/domino", headers=hm).status_code == 403
    assert client.post("/api/community/domino/start", json={"solo": True}, headers=hm).status_code == 403
    assert client.get("/api/community/domino", headers=ph).status_code == 200            # parents always
    me = client.get("/api/me", headers=hm).json()
    assert "domino" not in me["games_list"] and me["community"]["domino"] is None


def test_guest_paths():
    from familyquest import netfilter
    assert netfilter.is_guest_path("/api/community/domino") and netfilter.is_guest_path("/api/community/domino/play")
    assert not netfilter.is_guest_path("/api/community/domino/start") and not netfilter.is_guest_path("/api/community/domino/rules")
