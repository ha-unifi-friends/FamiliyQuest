import random

import pytest

from familyquest import poker as pk
from familyquest.community import CommunityError


def rank(cards):
    return pk.CATEGORIES[pk.best_hand(cards.split())[0][0]]


def test_hand_ranks():
    assert rank("As Ks Qs Js Ts 2d 3c") == "straight_flush"
    assert rank("Ah 2d 3c 4s 5h 9d Kc") == "straight"                 # wheel
    assert rank("Ah Ad Ac Kd Ks 2c 3d") == "full_house"
    assert rank("2h 7h 9h Jh Kh Ad Ac") == "flush"
    assert rank("Ah Ad Kc Kd 2s 3s 9c") == "two_pair"
    assert pk.best_hand("Ah Ad Kc Kd Qs 2s 3c".split())[0] > pk.best_hand("Ah Ad Kc Kd Js 2s 3c".split())[0]   # kicker
    assert pk.best_hand("5h 4d 3c 2s Ah Kd Qc".split())[0] < pk.best_hand("6h 5d 4c 3s 2h Kd Qc".split())[0]   # wheel < six-high


def test_side_pots():
    pots = pk.side_pots({"a": 50, "b": 200, "c": 200, "d": 30}, folded={"d"})
    assert pots == [{"amount": 180, "eligible": ["a", "b", "c"]}, {"amount": 300, "eligible": ["b", "c"]}]


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def table(n=3, chips=1000, **rules):
    st = {"rules": {**pk.DEFAULT_RULES, "blind_minutes": 0, **rules},
          "players": [{"id": str(i), "name": f"P{i}", "avatar": {}, "chips": chips, "buyins": 1} for i in range(1, n + 1)],
          "phase": "lobby", "requests": {}}
    clock = Clock()
    t = pk.Table(st, random.Random(7), now=clock)
    t.deal()
    return t, clock


def total(t):
    return sum(p["chips"] for p in t.st["players"]) + sum(t.hand["contrib"].values()) * (t.hand.get("result") is None)


def test_betting_round_and_fold_win():
    t, _ = table(3)
    h = t.hand
    assert t.st["dealer"] == "1" and h["sb_player"] == "2" and h["bb_player"] == "3" and h["to_act"] == "1"
    with pytest.raises(CommunityError):
        t.act("2", "call")                                           # not your turn
    t.act("1", "raise", 60)
    t.act("2", "fold")
    assert t.legal("3")["call"] == 40
    t.act("3", "fold")
    assert h["result"]["winners"] == {"1": 90} and t.seat("1")["chips"] == 1030
    assert sum(p["chips"] for p in t.st["players"]) == 3000


def test_check_down_to_showdown_keeps_the_chips():
    t, clock = table(3)
    t.act("1", "call"); t.act("2", "call"); t.act("3", "check")       # big blind's option
    assert t.hand["street"] == "flop" and len(t.hand["board"]) == 3 and t.hand["to_act"] == "2"
    for _ in range(3):
        for p in ("2", "3", "1"):
            t.act(p, "check")
    assert t.hand["street"] == "showdown" and sum(p["chips"] for p in t.st["players"]) == 3000
    assert t.st["phase"] == "between"
    clock.t += 10
    t.tick()                                                         # the next hand comes by itself
    assert t.hand["no"] == 2 and t.st["dealer"] == "2"


def test_all_in_runs_the_board_out_and_side_pot():
    t, _ = table(3)
    t.seat("1")["chips"] = 100                                       # short stack (dealer, acts first)
    t.act("1", "allin")
    t.act("2", "call"); t.act("3", "call")
    assert t.hand["street"] == "flop"
    t.act("2", "raise", 300); t.act("3", "call")
    t.act("2", "check") if t.hand["to_act"] == "2" else None
    while t.hand.get("to_act"):
        t.act(t.hand["to_act"], "check")
    assert t.hand["result"] and len(t.hand["board"]) == 5
    assert sum(p["chips"] for p in t.st["players"]) == 2100
    assert len(t.hand["result"]["pots"]) == 2


def test_timeout_checks_or_folds_and_equal_mode_ends():
    t, clock = table(2, chips=100, turn_seconds=20)
    first = t.hand["to_act"]                                         # heads-up: the dealer (small blind) acts first
    assert first == t.st["dealer"]
    clock.t += 30
    t.tick()                                                         # owes the rest of the big blind → folds
    assert first in t.hand["folded"]
    for _ in range(200):                                             # all in until one has everything
        if t.st["phase"] == "done":
            break
        clock.t += 31
        if t.st["phase"] == "hand" and t.hand.get("to_act"):
            p = t.hand["to_act"]
            t.act(p, "allin" if "raise" in t.legal(p) else ("call" if t.legal(p).get("call") else "check"))
        t.tick()
    assert t.st["phase"] == "done" and sorted(p["place"] for p in t.st["players"]) == [1, 2]


def test_family_game_api(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.post("/api/community/poker/start", json={"start_chips": 100, "big_blind": 50}, headers=hm).status_code == 400
    st = client.post("/api/community/poker/start", json={"start_chips": 500, "small_blind": 5, "big_blind": 10, "mode": "bank"}, headers=hm).json()
    assert st["phase"] == "lobby" and st["rules"]["mode"] == "bank"
    client.post("/api/community/poker/join", headers=hl)
    assert client.post("/api/community/poker/begin", headers=hl).status_code == 403            # only the leader starts
    st = client.post("/api/community/poker/begin", headers=hm).json()
    assert st["phase"] == "hand" and len(st["my_cards"]) == 2
    other = client.get("/api/community/poker", headers=hl).json()
    assert other["my_cards"] != st["my_cards"] and all(p["cards"] is None for p in other["players"])   # no peeking
    who = st["to_act"]
    h = hm if who == mia else hl
    client.post("/api/community/poker/act", json={"kind": "allin"}, headers=h)
    h2 = hl if who == mia else hm
    client.post("/api/community/poker/act", json={"kind": "call"}, headers=h2)
    st = client.get("/api/community/poker", headers=hm).json()
    assert st["phase"] in ("between", "waiting") and sum(p["chips"] for p in st["players"]) == 1000
    loser = next((p for p in st["players"] if p["chips"] == 0), None)
    if loser:                                                                               # the bank: ask, the leader gives
        hx = hm if loser["id"] == mia else hl
        client.post("/api/community/poker/ask", headers=hx)
        assert client.get("/api/community/poker", headers=hm).json()["requests"] == [str(loser["id"])]
        client.post("/api/community/poker/give", json={"profile_id": loser["id"], "ok": True}, headers=hm)
        p = next(p for p in client.get("/api/community/poker", headers=hm).json()["players"] if p["id"] == loser["id"])
        assert p["chips"] == 500 and p["buyins"] == 2
    client.post("/api/community/poker/end", headers=hm)
    assert client.get("/api/community/poker", headers=hm).json()["phase"] == "done"


def test_alone_against_bots(client, monkeypatch):
    from test_api import setup_family
    from familyquest import poker as pk
    monkeypatch.setattr(pk, "BOT_DELAY", 0)
    assert pk.strength(["As", "Ah"], []) > pk.strength(["7c", "2d"], []) and pk.strength(["As", "Ah"], ["Ad", "Ac", "5s"]) > .9
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    st = client.post("/api/community/poker/start", json={"solo": True, "bots": 3, "level": "hard"}, headers=hm).json()
    assert st["solo"] and st["phase"] == "hand" and len(st["players"]) == 4 and sum(p["bot"] for p in st["players"]) == 3
    # the family table is still free: Leo can open one at the same time
    assert client.post("/api/community/poker/start", json={}, headers=hl).status_code == 200
    assert not client.get("/api/community/poker", headers=hl).json()["solo"]
    seen_bot_move, hands = False, set()
    for _ in range(400):
        st = client.get("/api/community/poker", headers=hm).json()
        hands.add(st["hand_no"])
        if any(p["bot"] and p["last"] for p in st["players"]):
            seen_bot_move = True
        if st["phase"] == "done":
            break
        if st["to_act"] == mia:
            L = st["legal"]
            client.post("/api/community/poker/act", json={"kind": "check" if L.get("check") else "call"}, headers=hm)
        elif st["phase"] == "between":
            row = client.app.state.fq.poker._row(mia)
            import json as _j
            s = _j.loads(row["state"]); s["next_at"] = 0
            client.app.state.fq.db.x("UPDATE poker_game SET state=? WHERE id=?", _j.dumps(s), row["id"])
        if len(hands) >= 3 and seen_bot_move:
            break
    assert seen_bot_move and len(hands) >= 2
    client.post("/api/community/poker/end", headers=hm)
    st = client.get("/api/community/poker", headers=hm).json()
    assert not st["solo"] and st["phase"] == "lobby"            # her own table is over – Leo's family table is open


def test_solo_all_in_does_not_end_the_hand():
    """Review: a human all-in (0 chips, hand still open) must not end the solo game before the showdown."""
    st = {"rules": {**pk.DEFAULT_RULES, "blind_minutes": 0, "turn_seconds": 0}, "solo": True, "phase": "lobby", "requests": {},
          "players": [{"id": "1", "name": "Mia", "avatar": {}, "chips": 1000, "buyins": 1},
                      {"id": "bot1", "name": "Fuchs", "bot": True, "level": "normal", "chips": 1000, "buyins": 1},
                      {"id": "bot2", "name": "Bär", "bot": True, "level": "normal", "chips": 1000, "buyins": 1}]}
    clock = Clock()
    t = pk.Table(st, random.Random(5), now=clock)
    t.deal()
    for _ in range(10):                                   # bots before Mia move first
        if t.hand["to_act"] == "1":
            break
        t.act(t.hand["to_act"], "call" if t.legal(t.hand["to_act"]).get("call") else "check")
    t.act("1", "allin")
    t.tick()
    assert st["phase"] != "done"                            # the bots still play the hand out
    for _ in range(200):
        if st["phase"] != "hand":
            break
        clock.t += 5
        t.tick()
    assert st["phase"] in ("between", "done") and st["hand"]["result"] is not None
    assert sum(p["chips"] for p in st["players"]) == 3000   # the pot was paid out
