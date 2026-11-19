"""«Heimwärts» – legal moves, hitting, safe fields and benches, the home, three tries, bots, the table in the app."""
import json
import random

import pytest

from familyquest import heimwaerts as hw
from familyquest.community import CommunityError


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Dice(random.Random):
    """A die that rolls the given numbers (then at random)."""

    def __init__(self, rolls=(), seed=1):
        super().__init__(seed)
        self.rolls = list(rolls)

    def randint(self, a, b):
        return self.rolls.pop(0) if self.rolls else super().randint(a, b)


def table(n=2, bots=0, rolls=(), seed=1, level="normal", **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "heimwaerts", "rules": {**hw.DEFAULTS, "bot_ms": 0, **rules}, "players": players, "phase": "lobby"}
    clock = Clock()
    t = hw.Table(st, Dice(rolls, seed), now=clock)
    t.setup()
    return t, clock


def place(t, pid, *rels):
    t.st["pieces"][pid] = list(rels) + [hw.YARD] * (4 - len(rels))


def rolled(t, pid, die):
    """It is pid's turn and the die shows this number (to move)."""
    t.st.update(turn=pid, stage="move", die=die)


# ---------------------------------------------------------------- setup, seats
def test_seats_and_start():
    t, _ = table(2)
    assert t.st["seats"] == {"1": 0, "2": 2} and t.st["turn"] == "1" and t.st["stage"] == "roll"
    assert all(p == [hw.YARD] * 4 for p in t.st["pieces"].values())
    t, _ = table(3)
    assert list(t.st["seats"].values()) == [0, 1, 2]
    assert t.field("2", 0) == 10 and t.field("3", 35) == 15 and t.field("1", 39) == 39


# ---------------------------------------------------------------- rolling: 6 brings out and rolls again, three tries
def test_six_brings_a_piece_out_and_rolls_again():
    t, _ = table(2, rolls=[6, 3])
    assert t.roll("1") == 6 and t.st["stage"] == "move"
    assert {m["piece"] for m in t.moves("1")} == {0, 1, 2, 3} and all(m["to"] == 0 for m in t.moves("1"))
    t.move("1", 2)
    assert t.st["pieces"]["1"] == [-1, -1, 0, -1]
    assert t.st["turn"] == "1" and t.st["stage"] == "roll"                     # the 6: roll again
    t.roll("1")
    assert [m["piece"] for m in t.moves("1")] == [2]                          # a 3: only the piece out moves
    t.move("1", 2)
    assert t.st["pieces"]["1"][2] == 3 and t.st["turn"] == "2"


def test_three_tries_without_a_piece_out():
    t, _ = table(2, rolls=[2, 3, 5])
    for k in range(2):
        t.roll("1")
        assert t.st["turn"] == "1" and t.st["tries"] == k + 1 and t.st["last"]["kind"] == "try"
    t.roll("1")
    assert t.st["turn"] == "2" and t.st["tries"] == 0 and t.st["last"]["kind"] == "pass"
    # with a 6 in the tries: out
    t, _ = table(2, rolls=[1, 6])
    t.roll("1")
    t.roll("1")
    assert t.st["stage"] == "move"
    # a piece on the track: only one roll – no move, the turn passes
    t, _ = table(2, rolls=[4])
    place(t, "1", 38, 42)                                                    # 38 + 4 = 42: taken, 42 + 4: too far – no move
    t.roll("1")
    assert t.st["turn"] == "2" and t.st["last"]["kind"] == "pass"


def test_a_six_without_a_move_still_rolls_again():
    t, _ = table(2, rolls=[6])
    place(t, "1", 0, 40, 41, 42)                                             # start taken by the own piece, 0 + 6 = 6 …
    t.st["pieces"]["2"] = [-1] * 4
    t.st["pieces"]["1"][0] = 39                                              # 39 + 6: beyond the home (exact) – no move
    t.roll("1")
    assert t.st["turn"] == "1" and t.st["stage"] == "roll" and t.st["last"]["kind"] == "again"


def test_turn_and_stage_are_checked():
    t, _ = table(2, rolls=[3])
    with pytest.raises(CommunityError, match="not your turn"):
        t.roll("2")
    with pytest.raises(CommunityError, match="Roll first"):
        t.move("1", 0)
    with pytest.raises(CommunityError, match="not at this table"):
        t.roll("9")
    place(t, "1", 5)
    t.roll("1")
    with pytest.raises(CommunityError, match="Move a piece first"):
        t.roll("1")
    with pytest.raises(CommunityError, match="cannot move"):
        t.move("1", 1)                                                       # in the yard, no 6
    with pytest.raises(CommunityError, match="cannot move"):
        t.move("1", "x")


# ---------------------------------------------------------------- moving: own pieces, hitting, safe start fields
def test_only_own_pieces_and_no_two_own_on_a_field():
    t, _ = table(2)
    place(t, "1", 5, 8)
    place(t, "2", 3)
    rolled(t, "1", 3)
    assert [m["piece"] for m in t.moves("1")] == [1]                         # 5 + 3 = 8: own piece there
    rolled(t, "1", 6)
    assert [(m["piece"], m["to"]) for m in t.moves("1")] == [(0, 11), (1, 14), (2, 0), (3, 0)]
    with pytest.raises(CommunityError, match="not your turn"):
        t.move("2", 0)                                                       # the other player cannot move now


def test_landing_on_an_opponent_sends_it_home():
    t, _ = table(2)
    place(t, "1", 5)
    place(t, "2", 27)                                                        # seat 2: field 20 + 27 = 47 → 7
    rolled(t, "1", 2)
    mv = t.moves("1")[0]
    assert mv["to"] == 7 and mv["hit"] == [("2", 0)]
    t.move("1", 0)
    assert t.st["pieces"]["2"][0] == hw.YARD and t.st["last"]["hit"] == [["2", 0]]
    assert t.st["turn"] == "2"


def test_start_fields_are_safe_and_shared_by_default():
    t, _ = table(2)
    place(t, "1", 17)                                                        # 17 + 3 = 20: the start field of seat 2
    place(t, "2", 0)
    rolled(t, "1", 3)
    mv = t.moves("1")[0]
    assert mv["to"] == 20 and mv["hit"] == []
    t.move("1", 0)
    assert t.st["pieces"]["2"][0] == 0 and t.on_field(20) == [("1", 0), ("2", 0)]
    # passing safe fields is fine without benches; coming out does not hit a piece on the own start field
    t.st["pieces"]["1"] = [20, -1, -1, -1]
    t.st["pieces"]["2"] = [-1, -1, -1, 20]                                   # seat 2, rel 20 → field 0: seat 0's start
    rolled(t, "1", 6)
    out = [m for m in t.moves("1") if m["from"] == hw.YARD][0]
    assert out["hit"] == []


def test_benches_cannot_be_hit_or_passed():
    t, _ = table(2, bench=True)
    assert t.safe() == {0, 10, 20, 30, 5, 15, 25, 35}
    place(t, "2", 25)                                                        # field 45 → 5: a bench
    place(t, "1", 3)
    rolled(t, "1", 2)
    assert t.moves("1") == []                                                # cannot land on it
    rolled(t, "1", 4)
    assert t.moves("1") == []                                                # cannot pass it
    t.st["pieces"]["2"][0] = 24                                              # off the bench: field 4 – hit / pass are fine
    rolled(t, "1", 1)
    assert t.moves("1")[0]["hit"] == [("2", 0)]
    rolled(t, "1", 4)
    assert t.moves("1")[0]["to"] == 7
    # an own piece on a bench blocks the own pieces too
    place(t, "1", 3, 5)
    place(t, "2")
    rolled(t, "1", 4)
    assert [m["piece"] for m in t.moves("1")] == [1]
    # coming out sends a piece on the own start bench home – the owner's right
    place(t, "1", 12)
    place(t, "2", 20)                                                        # seat 2, rel 20 → field 0: seat 0's start
    rolled(t, "1", 6)
    out = next(m for m in t.moves("1") if m["from"] == hw.YARD)
    assert out["hit"] == [("2", 0)]
    t.move("1", out["piece"])
    assert t.st["pieces"]["2"][0] == hw.YARD


def test_bench_option_off_means_passing_is_free():
    t, _ = table(2)
    place(t, "2", 25)
    place(t, "1", 3)
    rolled(t, "1", 4)
    assert t.moves("1")[0]["to"] == 7
    rolled(t, "1", 2)
    assert t.moves("1")[0]["hit"] == [("2", 0)]                             # field 5 is no safe field without benches


# ---------------------------------------------------------------- the home: exact roll, no jumping
def test_exact_roll_needed_into_the_home():
    t, _ = table(2)
    place(t, "1", 37)
    rolled(t, "1", 6)                                                        # 37 + 6 = 43: the last home field
    assert t.moves("1")[0]["to"] == 43
    place(t, "1", 38)
    rolled(t, "1", 6)                                                        # 44: too far
    assert [m for m in t.moves("1") if m["piece"] == 0] == []
    place(t, "1", 36, 41)
    rolled(t, "1", 6)                                                        # 42: would jump over the piece on 41
    assert [m for m in t.moves("1") if m["piece"] == 0] == []
    rolled(t, "1", 1)
    assert {m["piece"]: m["to"] for m in t.moves("1")} == {0: 37, 1: 42}
    place(t, "1", 40, 42)
    rolled(t, "1", 2)
    assert [m for m in t.moves("1") if m["piece"] == 0] == []                # 40 → 42 taken
    rolled(t, "1", 1)
    assert {m["piece"]: m["to"] for m in t.moves("1")} == {0: 41, 1: 43}


def test_without_exact_a_piece_goes_as_deep_as_it_can():
    t, _ = table(2, exact=False)
    place(t, "1", 38)
    rolled(t, "1", 6)
    assert t.moves("1")[0]["to"] == 43
    place(t, "1", 38, 42)
    rolled(t, "1", 6)
    assert {m["piece"]: m["to"] for m in t.moves("1")}[0] == 41
    place(t, "1", 38, 40)
    rolled(t, "1", 5)
    assert [m for m in t.moves("1") if m["piece"] == 0] == []                # the first home field is taken


def test_first_home_wins_and_the_others_play_on():
    t, _ = table(3)
    place(t, "1", 37, 41, 42, 43)
    rolled(t, "1", 3)
    t.move("1", 0)
    assert t.st["finished_order"] == ["1"] and t.st["phase"] == "play" and t.st["turn"] == "2"
    assert t.finished("1")
    place(t, "2", 36, 41, 42, 43)
    rolled(t, "2", 4)
    t.move("2", 0)
    assert t.st["phase"] == "done" and t.st["complete"]                      # one left: over
    assert t.st["places"] == {"1": 1, "2": 2, "3": 3}
    # a finished player is skipped; a 6 that finishes does not roll again
    t, _ = table(3)
    place(t, "1", 34, 41, 42, 43)
    rolled(t, "1", 6)
    t.move("1", 0)
    assert t.finished("1") and t.st["turn"] == "2"
    t.st["turn"] = "3"
    t.st["stage"] = "roll"
    t.st["pieces"]["3"] = [5, -1, -1, -1]
    t.rng = Dice([2])
    t.roll("3")
    t.move("3", 0)
    assert t.st["turn"] == "2"


def test_end_when_the_winner_is_in():
    t, _ = table(3, play_on=False)
    place(t, "2", 20, 3)
    place(t, "3", 10)
    place(t, "1", 37, 41, 42, 43)
    rolled(t, "1", 3)
    t.move("1", 0)
    assert t.st["phase"] == "done" and t.st["complete"]
    assert t.st["places"] == {"1": 1, "2": 2, "3": 3}                        # the others by how far they are


def test_game_ends_when_only_bots_are_left():
    t, _ = table(1, bots=2)
    place(t, "1", 36, 41, 42, 43)
    rolled(t, "1", 4)
    t.move("1", 0)
    assert t.st["phase"] == "done" and t.st["complete"] and t.st["places"]["1"] == 1


def test_leader_ends_the_game_as_it_stands():
    t, _ = table(2)
    place(t, "2", 10, 40)
    t.end()
    assert t.st["phase"] == "done" and not t.st["complete"] and t.st["places"] == {"1": 2, "2": 1}


# ---------------------------------------------------------------- bots
def play_out(t, level):
    """Everybody plays like a bot of this level until the game is over."""
    for _ in range(20000):
        if t.st["phase"] != "play":
            return
        p = t.st["turn"]
        if t.st["stage"] == "roll":
            t.roll(p)
        else:
            t.move(p, t.bot_move(p, level))
    raise AssertionError("the game did not end")


@pytest.mark.parametrize("level", ["easy", "normal", "hard"])
@pytest.mark.parametrize("bench", [False, True])
def test_bots_finish_full_games(level, bench):
    for seed in range(3):
        for n in (2, 4):
            t, _ = table(n, seed=seed, bench=bench, exact=seed != 1)
            play_out(t, level)
            assert t.st["complete"] and len(t.st["finished_order"]) == n - 1
            assert sorted(t.st["places"].values()) == list(range(1, n + 1))
    # bots alone through tick(): the game ends with the first one home (only bots left)
    t, _ = table(0, bots=4, seed=3, level=level, bench=bench)
    t.tick()
    assert t.st["phase"] == "done" and t.st["finished_order"]


def test_hard_bots_prefer_hitting_safety_and_finishing():
    t, _ = table(2)
    place(t, "1", 5, 20)
    place(t, "2", 29)                                                        # field 9: 4 ahead of piece 0
    rolled(t, "1", 4)
    assert t.bot_move("1", "hard") == 0                                      # hit
    place(t, "1", 36, 12)
    place(t, "2")
    rolled(t, "1", 5)
    assert t.bot_move("1", "hard") == 0                                      # into the home
    place(t, "1", 15, 25)
    place(t, "2", 31)                                                        # field 11: 4 behind piece 0 (field 15)
    rolled(t, "1", 5)
    assert t.bot_move("1", "hard") == 0                                      # run away onto the start field 20


def test_hard_beats_easy_on_average():
    wins = 0
    for seed in range(60):
        t, _ = table(0, bots=2, seed=seed)
        t.st["players"][seed % 2]["level"] = "hard"
        t.st["players"][1 - seed % 2]["level"] = "easy"
        t.tick()
        hard = t.st["players"][seed % 2]["id"]
        wins += t.st["places"][hard] == 1
    assert wins >= 36


def test_bots_wait_for_their_reaction_time():
    t, clock = table(1, bots=1, bot_ms=1000, rolls=[2, 3, 1])
    t.roll("1")                                                              # no 6: try 2 …
    t.roll("1")
    t.roll("1")
    assert t.st["turn"] == "bot1"
    assert not t.tick()
    clock.t += 1.1
    assert t.tick() and t.st["turn"] == "bot1"                               # one roll per reaction time


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _force(fq, gid, fn):
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    s = json.loads(row["state"])
    fn(s)
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), gid)


def test_solo_against_bots_plays_and_no_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    st = client.post("/api/community/heimwaerts/start", json={"solo": True, "bots": 3, "level": "hard", "bot_ms": 0}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 4 and not st["coins_on"]
    assert st["my_turn"] and st["can_roll"] and st["three_tries"] and st["moves"] == [] and st["my_seat"] == 0
    for _ in range(3000):
        if st["phase"] == "done":
            break
        if st["can_roll"]:
            st = client.post("/api/community/heimwaerts/roll", headers=hm).json()
        elif st["my_turn"] and st["moves"]:
            st = client.post("/api/community/heimwaerts/move", json={"piece": st["moves"][-1]["piece"]}, headers=hm).json()
        else:
            st = client.get("/api/community/heimwaerts", headers=hm).json()
    assert st["phase"] == "done" and st["complete"] and all(p["coins"] == 0 for p in st["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'heimwaerts:%'")
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "heimwaerts" and hist[0]["data"]["complete"]
    assert client.get("/api/community/heimwaerts", headers=login(client, leo)).json() is None


def test_the_starter_rolls_first_but_the_seats_stay(client):
    """The chosen starter rolls first – the seats (colours) stay in the order of the lobby, the turn goes on clockwise."""
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    ben = client.post("/api/parent/profiles", json={"name": "Ben"}, headers=phd).json()["id"]
    client.put("/api/parent/settings", json={"game_starter": "choose"}, headers=phd)
    hm, hl, hb = login(client, mia, "1111"), login(client, leo), login(client, ben)
    client.post("/api/community/heimwaerts/start", json={"bots": 0, "bot_ms": 0}, headers=hm)
    client.post("/api/community/heimwaerts/join", headers=hl)
    client.post("/api/community/heimwaerts/join", headers=hb)
    st = client.post("/api/community/heimwaerts/begin", json={"starter": str(leo)}, headers=hm).json()
    assert [(p["id"], p["seat"]) for p in st["players"]] == [(str(mia), 0), (str(leo), 1), (str(ben), 2)]
    assert st["turn"] == str(leo) and st["starter"]["id"] == str(leo)
    t = hw.Table(json.loads(client.app.state.fq.db.val("SELECT state FROM card_game WHERE id=?", st["game"])))
    t._next()
    assert t.st["turn"] == str(ben)


def test_family_table_turns_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert client.get("/api/parent/game-rewards", headers=phd).json()["heimwaerts"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"heimwaerts": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/heimwaerts/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/heimwaerts/start", json={"bots": 0, "bot_ms": 0}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"]
    assert client.post("/api/community/heimwaerts/roll", headers=hm).status_code == 400          # not started
    assert client.post("/api/community/heimwaerts/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/heimwaerts/begin", headers=hl).status_code == 403          # Leo does not lead
    st = client.post("/api/community/heimwaerts/begin", headers=hm).json()
    assert st["phase"] == "play" and [p["seat"] for p in st["players"]] == [0, 2] and st["turn"] == str(mia)
    assert client.get("/api/me", headers=hl).json()["community"]["heimwaerts"]["joined"]
    assert client.post("/api/community/heimwaerts/roll", headers=hl).status_code == 400          # not Leo's turn
    lv = client.get("/api/community/heimwaerts", headers=hl).json()
    assert not lv["my_turn"] and lv["my_seat"] == 2 and lv["moves"] == []
    gid = st["game"]
    # Mia: a piece on the track, the die shows 3 – she moves; Leo cannot move her pieces
    _force(fq, gid, lambda s: s.update(stage="move", die=3) or s["pieces"][str(mia)].__setitem__(0, 5))
    assert client.post("/api/community/heimwaerts/move", json={"piece": 0}, headers=hl).status_code == 400
    assert client.post("/api/community/heimwaerts/move", json={"piece": 1}, headers=hm).status_code == 400   # yard, no 6
    assert client.post("/api/community/heimwaerts/move", json={"piece": 9}, headers=hm).status_code == 422
    v = client.post("/api/community/heimwaerts/move", json={"piece": 0}, headers=hm).json()
    assert v["players"][0]["pieces"][0] == 8 and v["turn"] == str(leo) and v["last"]["kind"] == "move"
    # the end: Mia gets her last piece home, then Leo – coins once
    _force(fq, gid, lambda s: s.update(turn=str(mia), stage="move", die=2) or s["pieces"].update({str(mia): [38, 41, 42, 43]}))
    v = client.post("/api/community/heimwaerts/move", json={"piece": 0}, headers=hm).json()
    assert v["phase"] == "done" and v["complete"]                                               # one left: over
    coins = {p["id"]: (p["place"], p["coins"]) for p in v["players"]}
    assert coins == {str(mia): (1, 8), str(leo): (2, 4)}
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.heimwaerts._save(row, json.loads(row["state"]))                                          # paid once
    client.get("/api/community/heimwaerts", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"heimwaerts:{gid}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"heimwaerts:{gid}:{mia}")["reason"] == "Homeward – place 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "heimwaerts" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["home"] == 4
    assert hist[0]["data"]["coins"] == 8


def test_coins_rules(fq):
    st = {"solo": False, "phase": "done", "complete": True, "places": {"1": 1, "2": 2, "3": 3, "bot1": 1},
          "players": [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "bot1", "bot": True}]}
    assert fq.heimwaerts.coins_for(st) == {"1": 10, "2": 5, "3": 2}
    assert fq.heimwaerts.coins_for({**st, "complete": False}) == {}
    assert fq.heimwaerts.coins_for({**st, "solo": True}) == {}
    assert fq.heimwaerts.coins_for({**st, "players": [{"id": "1"}, {"id": "2", "guest": True}, {"id": "bot1", "bot": True}]}) == {}


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/heimwaerts/start", json={"bots": 1, "bot_ms": 5000, "level": "easy"}, headers=hm)
    client.post("/api/community/heimwaerts/join", headers=hl)
    st = client.post("/api/community/heimwaerts/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"] and [p["seat"] for p in st["players"]] == [0, 1, 2]
    assert client.post("/api/community/heimwaerts/end", headers=hl).status_code == 403
    v = client.post("/api/community/heimwaerts/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'heimwaerts:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='heimwaerts'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.heimwaerts.clean_rules("heimwaerts", {"bots": 9, "level": "x", "bot_ms": 99999, "bench": 1, "exact": 0}) == \
        {"bots": 3, "level": "normal", "bot_ms": 5000, "bench": True, "exact": False, "play_on": True}
    fq.heimwaerts.start("heimwaerts", kid, {"bots": 0, "level": "hard", "bench": True}, solo=True)
    assert fq.heimwaerts.default_rules()["level"] == "hard" and fq.heimwaerts.default_rules()["bench"] is True
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='heimwaerts'")["state"])
    assert len(st["players"]) == 2 and st["players"][1]["level"] == "hard"                    # alone: at least one bot


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/heimwaerts/start", json={"bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "heimwaerts"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Homeward"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end"):
        assert client.post("/api/community/heimwaerts/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.get("/api/community/heimwaerts/rules", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/heimwaerts/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    client.post("/api/community/heimwaerts/end", headers=hm)
    for p in ("", "/join", "/roll", "/move"):
        assert netfilter.is_guest_path("/api/community/heimwaerts" + p), p
    for p in ("/start", "/begin", "/end", "/rules"):
        assert not netfilter.is_guest_path("/api/community/heimwaerts" + p), p


def test_switched_off_blocks_it(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "heimwaerts" in client.get("/api/me", headers=hm).json()["games_list"]
    assert client.put("/api/parent/games", json={"access": {"heimwaerts": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/heimwaerts", headers=hm).status_code == 403
    assert client.post("/api/community/heimwaerts/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "heimwaerts" not in me["games_list"] and me["community"]["heimwaerts"] is None


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/heimwaerts/start", json={"solo": True, "bots": 2, "bot_ms": 5000}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "heimwaerts")
    assert g["title"] == "Homeward" and g["icon"] == "🏠" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "heimwaerts" for x in r["running"])
    v = client.get("/api/community/heimwaerts", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]
