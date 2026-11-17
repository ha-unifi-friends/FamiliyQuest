"""«Dorfmarkt» – the board, rolling and doubles, buying, rent, building evenly, mortgages, the town meeting, cards,
debts and bankruptcy, auction, trading, pause, the end by rounds / time, bots, the table in the app (coins once,
permissions, guests, running games)."""
import json
import random

import pytest

from familyquest import dorfmarkt as dm
from familyquest.community import CommunityError


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Dice(random.Random):
    """Dice that roll the given numbers (then at random)."""

    def __init__(self, rolls=(), seed=1):
        super().__init__(seed)
        self.rolls = list(rolls)

    def randint(self, a, b):
        return self.rolls.pop(0) if self.rolls else super().randint(a, b)

    def shuffle(self, x):                      # the card decks stay in their order
        pass


def table(n=2, bots=0, rolls=(), level="normal", **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "dorfmarkt", "rules": {**dm.DEFAULTS, "bot_ms": 0, **rules}, "players": players, "phase": "lobby"}
    clock = Clock()
    t = dm.Table(st, Dice(rolls), now=clock)
    t.setup()
    return t, clock


def own(t, pid, *fields):
    for f in fields:
        t.st["owner"][str(f)] = pid


# ---------------------------------------------------------------- the board
def test_board_has_its_own_layout():
    assert len(dm.FIELDS) == 36 and [dm.FIELDS[i]["t"] for i in (0, 9, 18, 27)] == ["start", "jail", "free", "gojail"]
    assert [len(g) for g in dm.GROUPS] == [2, 2, 3, 2, 3, 2, 3, 3] and len(dm.BUSES) == 4 and len(dm.UTILS) == 2
    assert sum(1 for f in dm.FIELDS if f["t"] in ("chance", "chest")) == 4 and sum(1 for f in dm.FIELDS if f["t"] == "tax") == 2
    for g in dm.GROUPS:                                   # prices grow around the board
        assert all(dm.FIELDS[a]["price"] <= dm.FIELDS[b]["price"] for a, b in zip(g, g[1:]))


def test_setup_money_and_order():
    t, _ = table(3, money=2000)
    assert t.st["money"] == {"1": 2000, "2": 2000, "3": 2000} and t.st["pos"] == {"1": 0, "2": 0, "3": 0}
    assert t.st["turn"] == "1" and t.st["stage"] == "roll" and t.st["round"] == 1


# ---------------------------------------------------------------- rolling, moving, Markttag
def test_roll_move_buy_and_end_turn():
    t, _ = table(2, rolls=[2, 3])
    assert t.roll("1") == [2, 3]
    assert t.st["pos"]["1"] == 5 and t.st["stage"] == "buy"                      # Village bus: School
    t.buy("1")
    assert t.owner(5) == "1" and t.st["money"]["1"] == 1300 and t.st["stage"] == "done"
    with pytest.raises(CommunityError):
        t.roll("1")                                                             # no second roll without a double
    t.end_turn("1")
    assert t.st["turn"] == "2" and t.st["stage"] == "roll"


def test_only_own_turn_and_stage():
    t, _ = table(2, rolls=[2, 3])
    with pytest.raises(CommunityError):
        t.roll("2")
    with pytest.raises(CommunityError):
        t.buy("1")                                                              # nothing to buy before rolling
    with pytest.raises(CommunityError):
        t.roll("9")


def test_passing_markttag_pays():
    t, _ = table(2, rolls=[3, 4])
    t.st["pos"]["1"] = 33                                                        # 33 + 7 = 40 → field 4 (tax)
    t.roll("1")
    assert t.st["pos"]["1"] == 4 and t.st["money"]["1"] == 1500 + 200 - 100
    assert any(e["kind"] == "move" and e["bonus"] == 200 for e in t.st["log"])


def test_double_rolls_again_and_three_doubles_go_to_the_meeting():
    t, _ = table(2, rolls=[1, 1, 2, 2, 3, 3])
    t.roll("1")                                                                  # field 2: Dorfkasse
    assert t.st["stage"] == "roll" and t.st["turn"] == "1" and t.st["doubles"] == 1
    t.roll("1")                                                                  # field 6: ice cream stand
    t.skip("1")
    assert t.st["stage"] == "roll" and t.st["doubles"] == 2
    t.roll("1")
    assert t.st["pos"]["1"] == dm.JAIL and "1" in t.st["meeting"] and t.st["stage"] == "done"
    t.end_turn("1")
    assert t.st["turn"] == "2"


def test_skip_leaves_the_field_free():
    t, _ = table(2, rolls=[3, 3, 1, 2])
    t.roll("1")
    t.skip("1")
    assert t.owner(6) is None and t.st["stage"] == "roll"                       # a double: once more


def test_cannot_afford_skips_by_itself():
    t, _ = table(2, rolls=[2, 3])
    t.st["money"]["1"] = 100
    t.roll("1")
    assert t.owner(5) is None and t.st["stage"] == "done" and t.st["last"]["poor"]


# ---------------------------------------------------------------- rent
def test_rent_doubles_with_the_whole_group_and_grows_with_buildings():
    t, _ = table(2)
    own(t, "2", 10, 12)
    base = dm.FIELDS[10]["rent"][0]
    assert t.rent(10) == base
    own(t, "2", 13)
    assert t.rent(10) == 2 * base
    t.st["build"]["10"] = 2
    assert t.rent(10) == dm.FIELDS[10]["rent"][2]
    t.st["build"]["10"] = 5
    assert t.rent(10) == dm.FIELDS[10]["rent"][5]
    t.st["mortgaged"].append(12)
    assert t.rent(12) == 0


def test_rent_is_paid_to_the_owner():
    t, _ = table(2, rolls=[4, 6])
    own(t, "2", 10, 12, 13)
    t.roll("1")
    rent = 2 * dm.FIELDS[10]["rent"][0]
    assert t.st["money"] == {"1": 1500 - rent, "2": 1500 + rent} and t.st["last"]["kind"] == "rent"


def test_postauto_and_works_rent():
    t, _ = table(2)
    own(t, "2", 5)
    assert t.rent(5) == 25
    own(t, "2", 14, 23, 31)
    assert t.rent(5) == 200
    own(t, "2", 11)
    assert t.rent(11, 7) == 28
    own(t, "2", 26)
    assert t.rent(11, 7) == 70


# ---------------------------------------------------------------- building evenly, selling, mortgages
def test_build_only_with_the_group_and_evenly():
    t, _ = table(2)
    own(t, "1", 1)
    assert not t.can_build("1", 1)
    own(t, "1", 3)
    t.build("1", 1)
    with pytest.raises(CommunityError):
        t.build("1", 1)                                                        # first the other field of the group
    t.build("1", 3)
    t.build("1", 1)
    assert t.builds(1) == 2 and t.builds(3) == 1 and t.st["money"]["1"] == 1500 - 3 * 50
    with pytest.raises(CommunityError):
        t.sell("1", 3)                                                         # sell evenly too: the higher one first
    t.sell("1", 1)
    assert t.builds(1) == 1 and t.st["money"]["1"] == 1500 - 3 * 50 + 25
    for _ in range(4):
        t.build("1", 1)
        t.build("1", 3)
    assert t.builds(1) == 5 and t.builds(3) == 5 and not t.can_build("1", 1)  # the market hall is the end
    with pytest.raises(CommunityError):
        t.build("2", 1)
    with pytest.raises(CommunityError):
        t.build("1", 5)                                                        # no buildings at a Village bus stop


def test_mortgage_rules():
    t, _ = table(2)
    own(t, "1", 1, 3)
    t.build("1", 1)
    with pytest.raises(CommunityError):
        t.mortgage("1", 3)                                                     # buildings in the group
    t.sell("1", 1)
    t.mortgage("1", 3)
    assert t.mortgaged(3) and t.st["money"]["1"] == 1500 - 50 + 25 + 30
    assert not t.can_build("1", 1)                                             # no building with a mortgage in the group
    t.unmortgage("1", 3)
    assert not t.mortgaged(3) and t.st["money"]["1"] == 1500 - 50 + 25 + 30 - 33
    t2, _ = table(2, mortgage=False)
    own(t2, "1", 1)
    with pytest.raises(CommunityError):
        t2.mortgage("1", 1)


# ---------------------------------------------------------------- the town meeting
def test_meeting_pay_or_roll_a_double():
    t, _ = table(2, rolls=[1, 2, 4, 4])
    t._to_meeting("1", "field")
    t.st["stage"] = "roll"
    t.roll("1")                                                                  # no double: stays
    assert "1" in t.st["meeting"] and t.st["meeting"]["1"] == 1 and t.st["pos"]["1"] == dm.JAIL and t.st["stage"] == "done"
    t.end_turn("1")
    t.st.update(turn="1", stage="roll")
    t.roll("1")                                                                  # a double: out, moves, no extra roll
    assert "1" not in t.st["meeting"] and t.st["pos"]["1"] == dm.JAIL + 8
    t2, _ = table(2)
    t2._to_meeting("1", "card")
    t2.st["stage"] = "roll"
    t2.bail("1")
    assert "1" not in t2.st["meeting"] and t2.st["money"]["1"] == 1450 and t2.st["stage"] == "roll"


def test_meeting_after_three_tries_pays_and_goes():
    t, _ = table(2, rolls=[1, 2, 1, 2, 1, 2])
    t._to_meeting("1", "field")
    for _ in range(2):
        t.st.update(turn="1", stage="roll")
        t.roll("1")
    t.st.update(turn="1", stage="roll")
    t.roll("1")
    assert "1" not in t.st["meeting"] and t.st["pos"]["1"] == dm.JAIL + 3 and t.st["money"]["1"] == 1450


def test_going_to_the_meeting_corner_and_free_pass():
    t, _ = table(2, rolls=[3, 4])
    t.st["pos"]["1"] = 20
    t.roll("1")
    assert t.st["pos"]["1"] == dm.JAIL and "1" in t.st["meeting"]
    t.st["free"]["1"] = ["z_free"]
    t.st["decks"]["chance"].remove("z_free")
    t.st.update(turn="1", stage="roll")
    t.use_card("1")
    assert "1" not in t.st["meeting"] and "1" not in t.st["free"] and t.st["decks"]["chance"][-1] == "z_free"


# ---------------------------------------------------------------- cards
def _draw(t, deck, card, pid="1", pos=None):
    t.st["decks"][deck] = [card] + [c for c in t.st["decks"][deck] if c != card]
    field = 7 if deck == "chance" else 2
    t.st["pos"][pid] = field if pos is None else pos
    t.st.update(turn=pid, stage="roll")
    t._land(pid, "done")


def test_cards_money_move_and_each():
    t, _ = table(3)
    _draw(t, "chest", "d_birthday")
    assert t.st["money"] == {"1": 1520, "2": 1490, "3": 1490} and t.st["decks"]["chest"][-1] == "d_birthday"
    _draw(t, "chance", "z_back3")
    assert t.st["pos"]["1"] == 4 and t.st["money"]["1"] == 1520 - 100              # back onto the municipal tax
    _draw(t, "chance", "z_postauto")
    assert t.st["pos"]["1"] == 14 and t.st["stage"] == "buy"
    t.st["stage"] = "done"
    _draw(t, "chance", "z_markttag", pos=20)
    assert t.st["pos"]["1"] == 0 and t.st["money"]["1"] == 1420 + 200
    _draw(t, "chance", "z_icecream")
    assert t.st["money"] == {"1": 1580, "2": 1510, "3": 1510}
    _draw(t, "chance", "z_meeting")
    assert "1" in t.st["meeting"] and t.st["pos"]["1"] == dm.JAIL


def test_repair_card_counts_buildings():
    t, _ = table(2)
    own(t, "1", 1, 3)
    t.st["build"].update({"1": 3, "3": 5})
    _draw(t, "chance", "z_cleaning")
    assert t.st["money"]["1"] == 1500 - 3 * 25 - 100


# ---------------------------------------------------------------- debts, bankruptcy
def test_debt_must_be_raised_then_the_turn_goes_on():
    t, _ = table(2, rolls=[4, 6])
    own(t, "2", 10, 12, 13)
    t.st["build"].update({"10": 1, "12": 1, "13": 1})
    own(t, "1", 1, 3)
    t.st["money"]["1"] = 10
    t.roll("1")                                                                  # rent 50: 40 short, 60 can be raised
    assert t.st["stage"] == "debt" and t.st["money"]["1"] == -40
    with pytest.raises(CommunityError):
        t.end_turn("1")
    t.mortgage("1", 1)
    assert t.st["stage"] == "debt"
    t.mortgage("1", 3)
    assert t.st["stage"] == "done" and t.st["money"]["1"] == 20
    t2, _ = table(2, rolls=[4, 6])
    own(t2, "2", 10, 12, 13)
    t2.st["build"]["10"] = 1
    own(t2, "1", 24, 25)
    t2.st["money"]["1"] = 10
    t2.roll("1")
    assert t2.st["stage"] == "debt"
    t2.liquidate("1")
    assert t2.st["stage"] == "done" and t2.st["money"]["1"] >= 0 and t2.mortgaged(24)


def test_bankrupt_to_a_player_gets_everything():
    t, _ = table(3, rolls=[4, 6])
    own(t, "2", 10, 12, 13)
    t.st["build"].update({"10": 5, "12": 5, "13": 5})
    own(t, "1", 5)
    t.st["mortgaged"].append(5)
    t.st["money"]["1"] = 50
    t.roll("1")
    assert t.st["out"] == ["1"] and t.owner(5) == "2" and t.mortgaged(5)
    assert t.st["money"]["2"] == 1500 + 50 and t.st["turn"] == "2"              # all that was there – not more


def test_bankrupt_to_the_bank_frees_the_fields_and_the_last_one_wins():
    t, _ = table(2, rolls=[2, 2])
    own(t, "1", 1, 3)
    t.st["mortgaged"].append(1)
    t.st["money"]["1"] = 50
    t.st["pos"]["1"] = 0
    t.roll("1")                                                                  # municipal tax 100, nothing to raise
    assert t.st["phase"] == "done" and t.st["complete"] and t.owner(1) is None and not t.mortgaged(1)
    assert t.st["places"] == {"2": 1, "1": 2}


def test_others_pay_by_themselves():
    t, _ = table(3)
    own(t, "2", 24, 25)
    t.st["money"]["2"] = 5
    t.st["money"]["3"] = 5
    _draw(t, "chest", "d_birthday")
    assert t.mortgaged(24) and t.st["money"]["2"] >= 0                         # mortgaged by itself
    assert "3" in t.st["out"] and t.st["money"]["1"] == 1500 + 10 + 5           # bankrupt: the 5 it had go to the creditor


# ---------------------------------------------------------------- auction
def test_open_auction_with_steps_and_five_seconds():
    t, clock = table(3, rolls=[2, 3], auction=True)
    t.roll("1")
    t.skip("1")
    assert t.st["stage"] == "auction" and t.st["auction"]["price"] == 0
    t.bid("2", 50)                                                             # 0 + 50
    with pytest.raises(CommunityError):
        t.bid("3", 30)                                                         # only 10, 25 or 50 more
    clock.t += 4
    t.bid("3", 25)                                                             # 75 – the 5 seconds start again
    clock.t += 4
    assert not t.tick() or t.st["auction"]                                     # still running (4 s after the last bid)
    t.bid("3", 10)                                                             # raise the own bid: 85
    assert t.st["auction"]["leader"] == "3" and t.st["auction"]["price"] == 85
    clock.t += dm.AUCTION_SECONDS + 0.1
    assert t.tick()
    assert t.owner(5) == "3" and t.st["money"]["3"] == 1500 - 85 and t.st["stage"] == "done"


def test_auction_without_bids_and_too_little_money():
    t, clock = table(3, rolls=[2, 3], auction=True)
    t.roll("1")
    t.skip("1")
    t.st["money"]["2"] = 20
    with pytest.raises(CommunityError):
        t.bid("2", 25)                                                         # not enough Taler
    clock.t += dm.AUCTION_SECONDS + 1
    assert t.tick()
    assert t.owner(5) is None and t.st["stage"] == "done" and t.st["auction"] is None


def test_auction_of_the_old_sealed_bid_format_does_not_break():
    """A game saved during an auction of the old format (sealed bids: no price, leader, history) goes on."""
    t, clock = table(3, rolls=[2, 3], auction=True)
    t.roll("1")
    t.skip("1")
    t.st["auction"] = {"field": 5, "player": "1", "after": "done", "bids": {}, "until": clock.t + 5}
    t.bid("2", 25)
    assert t.st["auction"]["price"] == 25 and t.st["auction"]["leader"] == "2"
    clock.t += dm.AUCTION_SECONDS + 1
    assert t.tick() and t.owner(5) == "2" and t.st["stage"] == "done"
    # without bids and without a deadline: it closes at the next tick – also with bots at the table
    t, clock = table(1, bots=2, rolls=[2, 3], auction=True)
    t.roll("1")
    t.skip("1")
    t.st["auction"] = {"field": 5, "player": "1", "bids": {"bot1": 100}}
    t.tick()
    assert t.st["auction"] is None or t.st["auction"].get("price") is not None


# ---------------------------------------------------------------- trading
def test_trade_offer_accept_decline_and_rules():
    t, _ = table(3)
    own(t, "1", 1)
    own(t, "2", 3, 10)
    tr = t.offer("1", "2", [1], 50, [3], 0)
    with pytest.raises(CommunityError):
        t.answer("3", tr["id"], True)                                          # only who gets the offer answers
    t.answer("2", tr["id"], True)
    assert t.owner(1) == "2" and t.owner(3) == "1" and t.st["money"] == {"1": 1450, "2": 1550, "3": 1500}
    tr = t.offer("1", "2", [], 0, [10], 10)
    t.answer("2", tr["id"], False)
    assert t.owner(10) == "2" and not t.st["trades"]
    with pytest.raises(CommunityError):
        t.offer("1", "2", [10], 0, [], 0)                                      # not mine
    own(t, "2", 12, 13)
    t.st["build"]["12"] = 1
    with pytest.raises(CommunityError):
        t.offer("1", "2", [], 0, [10], 0)                                      # buildings in the group
    with pytest.raises(CommunityError):
        t.offer("1", "2", [], 99999, [1], 0)
    with pytest.raises(CommunityError):
        t.offer("1", "1", [3], 0, [], 0)


def test_bots_accept_only_good_trades():
    t, _ = table(1, bots=1)
    own(t, "bot1", 1)
    own(t, "1", 24)
    t.offer("1", "bot1", [], 10, [1], 0)                                       # 10 Taler for a 60 field: no
    assert t.owner(1) == "bot1"
    t.offer("1", "bot1", [24], 0, [1], 0)                                      # a 260 field for a 60 one: yes
    assert t.owner(1) == "1" and t.owner(24) == "bot1"


# ---------------------------------------------------------------- the end
def test_rounds_end_with_the_richest():
    t, _ = table(2, rounds=5)
    t.st["round"] = 5
    own(t, "2", 35)
    t.st["stage"] = "done"
    t.end_turn("1")
    assert t.st["turn"] == "2"
    t.st["stage"] = "done"
    t.end_turn("2")
    assert t.st["phase"] == "done" and t.st["complete"] and t.st["places"] == {"2": 1, "1": 2}
    assert t.st["worths"]["2"] == 1500 + 400


def test_time_limit_and_pause():
    t, clock = table(2, mode="time", minutes=10)
    clock.t += 300
    t.pause(True)
    with pytest.raises(CommunityError):
        t.roll("1")
    clock.t += 3000                                                              # paused time does not count
    assert t.time_left() == 300
    t.pause(False)
    assert t.time_left() == 300
    clock.t += 301
    t.st["stage"] = "done"
    t.end_turn("1")
    assert t.st["phase"] == "done" and t.st["complete"]


def test_leader_ends_as_it_stands():
    t, _ = table(2)
    t.end()
    assert t.st["phase"] == "done" and not t.st["complete"] and t.st["places"] == {"1": 1, "2": 1}


# ---------------------------------------------------------------- bots
@pytest.mark.parametrize("level,auction,mode", [("easy", False, "classic"), ("normal", True, "rounds"), ("hard", False, "classic")])
def test_bots_finish_games(level, auction, mode):
    for seed in range(4):
        players = [{"id": "1", "name": "P"}] + [{"id": f"bot{i}", "name": "B", "bot": True, "level": level} for i in range(1, 4)]
        st = {"kind": "dorfmarkt", "rules": {**dm.DEFAULTS, "bot_ms": 0, "auction": auction, "mode": mode}, "players": players, "phase": "lobby"}
        clock = Clock()
        t = dm.Table(st, random.Random(seed), now=clock)
        t.setup()
        for _ in range(30000):
            if st["phase"] != "play":
                break
            clock.t += 1
            a = st.get("auction")
            if not a and st["turn"] == "1":
                st["players"][0]["bot"] = True                                  # the person plays like a bot
                t.bot_step("1")
                st["players"][0]["bot"] = False
            else:
                t.tick()
        assert st["phase"] == "done" and all(v >= 0 for v in st["money"].values())
        assert all(1 <= n <= 5 for n in st["build"].values())


def test_bots_wait_for_their_reaction_time():
    t, clock = table(1, bots=1, bot_ms=2000)
    t.st.update(turn="bot1", turn_at=clock.t)
    assert not t.tick()
    clock.t += 2.1
    assert t.tick() and t.st["roll_seq"] == 1


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
    assert len(client.get("/api/community/dorfmarkt/board", headers=hm).json()) == 36
    st = client.post("/api/community/dorfmarkt/start", json={"solo": True, "bots": 3, "level": "hard", "bot_ms": 0, "rounds": 5}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 4 and not st["coins_on"] and st["rules"]["rounds"] == 5
    assert st["my_turn"] and st["can_roll"]
    for _ in range(600):
        if st["phase"] == "done":
            break
        if st["can_roll"]:
            st = client.post("/api/community/dorfmarkt/act", json={"action": "roll"}, headers=hm).json()
        elif st["my_turn"] and st["stage"] == "buy":
            st = client.post("/api/community/dorfmarkt/act", json={"action": "buy" if st["can_buy"] else "skip"}, headers=hm).json()
        elif st["my_turn"] and st["stage"] == "done":
            st = client.post("/api/community/dorfmarkt/act", json={"action": "end_turn"}, headers=hm).json()
        elif st["my_turn"] and st["stage"] == "debt":
            st = client.post("/api/community/dorfmarkt/act", json={"action": "liquidate"}, headers=hm).json()
        else:
            st = client.get("/api/community/dorfmarkt", headers=hm).json()
    assert st["phase"] == "done" and st["complete"] and all(p["coins"] == 0 for p in st["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'dorfmarkt:%'")
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "dorfmarkt" and hist[0]["data"]["complete"] and hist[0]["data"]["worth"] > 0
    assert client.get("/api/community/dorfmarkt", headers=login(client, leo)).json() is None


def test_family_table_moves_trade_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert client.get("/api/parent/game-rewards", headers=phd).json()["dorfmarkt"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"dorfmarkt": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/dorfmarkt/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/dorfmarkt/start", json={"bots": 0, "bot_ms": 0, "rounds": 10}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"]
    act = lambda h, **b: client.post("/api/community/dorfmarkt/act", json=b, headers=h)        # noqa: E731
    assert act(hm, action="roll").status_code == 400                                           # not started
    assert client.post("/api/community/dorfmarkt/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/dorfmarkt/begin", headers=hl).status_code == 403        # Leo does not lead
    st = client.post("/api/community/dorfmarkt/begin", headers=hm).json()
    assert st["phase"] == "play" and st["turn"] == str(mia)
    assert client.get("/api/me", headers=hl).json()["community"]["dorfmarkt"]["joined"]
    assert act(hl, action="roll").status_code == 400                                           # not Leo's turn
    assert act(hm, action="nonsense").status_code == 400
    assert act(hm, action="build", field=99).status_code == 422
    gid = st["game"]
    # Mia lands on the bakery: Leo cannot buy it for her
    _force(fq, gid, lambda s: s.update(stage="buy", after_buy="done") or s["pos"].__setitem__(str(mia), 10))
    assert act(hl, action="buy").status_code == 400
    v = act(hm, action="buy").json()
    assert v["owner"]["10"] == str(mia) and v["players"][0]["money"] == 1360 and v["stage"] == "done"
    # pause: only who leads; nothing moves while paused
    assert client.post("/api/community/dorfmarkt/pause", json={"on": True}, headers=hl).status_code == 403
    assert client.post("/api/community/dorfmarkt/pause", json={"on": True}, headers=hm).json()["paused"]
    assert act(hm, action="end_turn").status_code == 400
    assert not client.post("/api/community/dorfmarkt/pause", json={"on": False}, headers=hm).json()["paused"]
    v = act(hm, action="end_turn").json()
    assert v["turn"] == str(leo)
    # Leo offers Taler for the bakery, Mia accepts
    t = act(hl, action="offer", to=str(mia), give_money=200, want=[10]).json()["trades"][0]
    assert client.get("/api/community/dorfmarkt", headers=hm).json()["trades"][0]["id"] == t["id"]
    assert act(hl, action="answer", trade=t["id"], accept=True).status_code == 400             # not his to answer
    v = act(hm, action="answer", trade=t["id"], accept=True).json()
    assert v["owner"]["10"] == str(leo) and v["players"][0]["money"] == 1560 and not v["trades"]
    # the game survives a restart: a new object on the same database goes on
    from familyquest.dorfmarkt import Dorfmarkt
    again = Dorfmarkt(fq.db, fq.community.add_history, fq.rewards)
    assert again.state("dorfmarkt", leo)["turn"] == str(leo)
    # the end: the last round is over – Mia is richer
    _force(fq, gid, lambda s: s.update(round=10, stage="done"))
    v = act(hl, action="end_turn").json()
    assert v["phase"] == "done" and v["complete"]
    coins = {p["id"]: (p["place"], p["coins"]) for p in v["players"]}
    assert coins == {str(mia): (1, 8), str(leo): (2, 4)}
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.dorfmarkt._save(row, json.loads(row["state"]))                                       # paid once
    client.get("/api/community/dorfmarkt", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"dorfmarkt:{gid}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"dorfmarkt:{gid}:{mia}")["reason"] == "Dorfmarkt – Platz 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "dorfmarkt" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["coins"] == 8
    prof = fq.db.q1("SELECT settings FROM profile WHERE id=?", mia)
    assert json.loads(prof["settings"]).get("champion")


def test_coins_rules(fq):
    st = {"solo": False, "phase": "done", "complete": True, "places": {"1": 1, "2": 2, "3": 3, "bot1": 1},
          "players": [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "bot1", "bot": True}]}
    assert fq.dorfmarkt.coins_for(st) == {"1": 10, "2": 5, "3": 2}
    assert fq.dorfmarkt.coins_for({**st, "complete": False}) == {}
    assert fq.dorfmarkt.coins_for({**st, "solo": True}) == {}
    assert fq.dorfmarkt.coins_for({**st, "players": [{"id": "1"}, {"id": "2", "guest": True}, {"id": "bot1", "bot": True}]}) == {}


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/dorfmarkt/start", json={"bots": 1, "bot_ms": 5000, "level": "easy"}, headers=hm)
    client.post("/api/community/dorfmarkt/join", headers=hl)
    st = client.post("/api/community/dorfmarkt/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"]
    assert client.post("/api/community/dorfmarkt/end", headers=hl).status_code == 403
    v = client.post("/api/community/dorfmarkt/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'dorfmarkt:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='dorfmarkt'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.dorfmarkt.clean_rules("dorfmarkt", {"bots": 9, "level": "x", "bot_ms": 99999, "mode": "y", "rounds": 1, "minutes": 1, "money": 7, "auction": 1}) == \
        {"bots": 5, "level": "normal", "bot_ms": 5000, "mode": "rounds", "rounds": 5, "minutes": 10, "auction": True, "mortgage": True, "money": 500}
    assert dm.DEFAULTS["rounds"] == 30 and dm.DEFAULTS["mode"] == "rounds"
    fq.dorfmarkt.start("dorfmarkt", kid, {"bots": 0, "level": "hard", "mode": "classic"}, solo=True)
    assert fq.dorfmarkt.default_rules()["level"] == "hard" and fq.dorfmarkt.default_rules()["mode"] == "classic"
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='dorfmarkt'")["state"])
    assert len(st["players"]) == 2 and st["players"][1]["level"] == "hard"                  # alone: at least one bot


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/dorfmarkt/start", json={"bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "dorfmarkt"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Dorfmarkt"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "pause"):
        assert client.post("/api/community/dorfmarkt/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.get("/api/community/dorfmarkt/rules", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/dorfmarkt/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    client.post("/api/community/dorfmarkt/end", headers=hm)
    for p in ("", "/join", "/act", "/board"):
        assert netfilter.is_guest_path("/api/community/dorfmarkt" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/pause"):
        assert not netfilter.is_guest_path("/api/community/dorfmarkt" + p), p


def test_switched_off_blocks_it(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "dorfmarkt" in client.get("/api/me", headers=hm).json()["games_list"]
    assert client.put("/api/parent/games", json={"access": {"dorfmarkt": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/dorfmarkt", headers=hm).status_code == 403
    assert client.post("/api/community/dorfmarkt/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "dorfmarkt" not in me["games_list"] and me["community"]["dorfmarkt"] is None


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/dorfmarkt/start", json={"solo": True, "bots": 2, "bot_ms": 5000}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "dorfmarkt")
    assert g["title"] == "Village Market" and g["icon"] == "🏘️" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "dorfmarkt" for x in r["running"])
    v = client.get("/api/community/dorfmarkt", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]


def test_bots_bid_in_the_open_auction():
    import random as _r
    players = [{"id": "1", "name": "P1"}] + [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": "hard"} for i in (1, 2)]
    st = {"kind": "dorfmarkt", "rules": {**dm.DEFAULTS, "bot_ms": 0, "auction": True}, "players": players, "phase": "lobby"}
    clock = Clock()
    t = dm.Table(st, _r.Random(3), now=clock)
    t.setup()
    st.update(turn="1", stage="auction", after_buy=None)
    st["auction"] = {"field": 5, "player": "1", "after": "done", "price": 0, "leader": None, "history": [],
                     "until": clock.t + dm.AUCTION_SECONDS, "last_at": clock.t}
    t.tick()                                                                   # the bots raise each other up to their value
    a = st["auction"]
    assert a and a["price"] > 0 and a["leader"].startswith("bot") and len(a["history"]) >= 2
    clock.t += dm.AUCTION_SECONDS + 1
    t.tick()
    assert t.owner(5) and t.owner(5).startswith("bot")


def test_bid_through_the_api_with_a_step(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.post("/api/community/dorfmarkt/start", json={"solo": True, "bots": 1, "bot_ms": 5000, "auction": True}, headers=hm)
    fq = client.app.state.fq
    import json as _j
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='dorfmarkt' AND status!='done'")
    st = _j.loads(row["state"])
    me = str(mia)
    st.update(turn=me, stage="auction")
    st["auction"] = {"field": 5, "player": me, "after": "done", "price": 0, "leader": None, "history": [], "until": 9e12, "last_at": 9e12}
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", _j.dumps(st), row["id"])
    r = client.post("/api/community/dorfmarkt/act", json={"action": "bid", "step": 25}, headers=hm)
    assert r.status_code == 200, r.text
    a = r.json()["auction"]
    assert a["price"] == 25 and a["leader"] == me and a["steps"] == [10, 25, 50]
