import json
import random

import pytest

from familyquest import kartenlauf as kl
from familyquest.community import CommunityError

K = -1          # in the kennel
H = kl.HOME     # home field 0 (H + 1 … H + 3)


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def table(n=4, teams=False, bots=False, seed=1, level="normal", **rules):
    players = [{"id": str(i), "name": f"P{i}", **({"bot": True, "level": level} if bots else {})} for i in range(1, n + 1)]
    st = {"kind": "kartenlauf", "rules": {**kl.DEFAULTS, "teams": teams, "bot_ms": 0, **rules}, "players": players, "phase": "lobby"}
    clock = Clock()
    t = kl.Table(st, random.Random(seed), now=clock)
    t.setup()
    return t, clock


def place(t, pid, *marbles, turn=True, hand=None):
    """Set the marbles of a player ([pos, fresh] or pos) and give them the hand; it is their turn."""
    ms = [[m, 0] if isinstance(m, int) else list(m) for m in marbles]
    t.st["marbles"][pid] = ms + [[K, 0]] * (4 - len(ms))
    if turn:
        t.st["phase"] = "play"
        t.st["turn"] = pid
    if hand is not None:
        t.st["hands"][pid] = list(hand)


def clear(t):
    for p in t.st["marbles"]:
        t.st["marbles"][p] = [[K, 0] for _ in range(4)]
    t.st["phase"] = "play"


def pos(t, pid):
    return [m[0] for m in t.st["marbles"][pid]]


# ---------------------------------------------------------------- board, cards, movement
def test_seats_and_board():
    for n, seats in ((2, [0, 2]), (3, [0, 1, 2]), (4, [0, 1, 2, 3])):
        t, _ = table(n)
        assert [t.st["seats"][p] for p in t.order()] == seats
        assert all(pos(t, p) == [K] * 4 for p in t.order())
    t, _ = table(4)
    assert t.start_of("2") == 16 and t.entry_of("1") == 63 and t.entry_of("3") == 31
    assert not t.teams() and table(4, teams=True)[0].teams() and not table(3, teams=True)[0].teams()


def test_deck_and_deal_6_5_4_3_2(monkeypatch):
    assert len(kl.new_deck()) == 110 and sum(1 for c in kl.new_deck() if kl.rank(c) == "X") == 6
    monkeypatch.setattr(kl.Table, "has_move", lambda self, p: True)       # nobody throws the cards away
    t, clock = table(4)
    sizes, dealers = [], []
    for _ in range(7):
        sizes.append(t.st["round_size"])
        dealers.append(t.st["dealer"])
        assert all(len(h) == t.st["round_size"] for h in t.st["hands"].values())
        assert t.st["turn"] == t.order()[(t.order().index(t.st["dealer"]) + 1) % 4]      # left of the dealer starts
        t.st["hands"] = {p: [] for p in t.order()}
        t._round_end()
        clock.t += kl.BETWEEN + 1
        t.tick()
    assert sizes == [6, 5, 4, 3, 2, 6, 5]
    assert dealers == ["4", "1", "2", "3", "4", "1", "2"]                 # the seat before the starter deals round 1
    # a fresh deck with every 6: 110 − 24 cards
    assert t.st["round"] == 8 and len(t.st["deck"]) == 110 - 6 * 4 - 5 * 4 - 4 * 4      # a fresh deck with every 6


def test_move_forward_and_wrap_around():
    t, _ = table(4)
    clear(t)
    place(t, "2", 60, hand=["h:8", "s:5"])
    t.play("2", {"card": "h:8", "marble": "2:0"})
    assert pos(t, "2")[0] == 4                                      # 60 + 8 wraps to 4
    assert t.st["hands"]["2"] == ["s:5"] and t.st["discard"][-1] == "h:8"


def test_out_with_ace_and_king_only():
    t, _ = table(4)
    clear(t)
    place(t, "1", hand=["h:A", "s:K", "d:Q", "c:5"])
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "d:Q", "kind": "out", "marble": "1:0"})
    t.play("1", {"card": "h:A", "kind": "out", "marble": "1:0"})
    assert t.st["marbles"]["1"][0] == [0, 1]                         # on the start field, protected
    t.st["turn"] = "1"
    with pytest.raises(CommunityError, match="blocked"):             # own protected marble on the start field
        t.simulate("1", {"card": "s:K", "kind": "out", "marble": "1:1"})
    # an opponent on my start field is sent home when I come out
    clear(t)
    place(t, "3", 0, turn=False)
    place(t, "1", hand=["s:K"])
    t.play("1", {"card": "s:K", "kind": "out", "marble": "1:0"})
    assert pos(t, "1")[0] == 0 and pos(t, "3")[0] == K
    assert t.st["last"]["kicked"] == ["3:0"]


def test_ace_one_or_eleven_and_king_13():
    t, _ = table(4)
    clear(t)
    place(t, "1", 5, hand=["h:A", "s:K"])
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "h:A", "marble": "1:0", "steps": 5})
    assert t.simulate("1", {"card": "h:A", "marble": "1:0", "steps": 11})[0]["1"][0][0] == 16
    assert t.simulate("1", {"card": "h:A", "marble": "1:0", "steps": 1})[0]["1"][0][0] == 6
    assert t.simulate("1", {"card": "s:K", "marble": "1:0"})[0]["1"][0][0] == 18


def test_protected_start_field_blocks():
    t, _ = table(4)
    clear(t)
    place(t, "2", [16, 1], turn=False)                              # just came out: protected
    place(t, "1", 12, hand=["h:6", "s:4", "c:J"])
    with pytest.raises(CommunityError, match="protected"):
        t.simulate("1", {"card": "h:6", "marble": "1:0"})            # passing
    with pytest.raises(CommunityError, match="protected"):
        t.simulate("1", {"card": "s:4", "marble": "1:0"})            # landing on it
    assert not [m for m in t.moves("1") if m["card"] == "h:6"]
    # backwards past it is blocked too
    place(t, "1", 18, hand=["s:4"])
    with pytest.raises(CommunityError, match="protected"):
        t.simulate("1", {"card": "s:4", "kind": "back", "marble": "1:0"})
    # once it moved on (or came around) it is not protected any more
    t.st["marbles"]["2"][0] = [16, 0]
    place(t, "1", 12, hand=["s:4"])
    t.play("1", {"card": "s:4", "marble": "1:0"})
    assert pos(t, "1")[0] == 16 and pos(t, "2")[0] == K


def test_kicking_others_partner_and_own():
    t, _ = table(4, teams=True)
    clear(t)
    place(t, "3", 25, turn=False)                                    # partner of "1"
    place(t, "2", 30, turn=False)
    place(t, "1", 20, 22, hand=["h:5", "s:8", "c:2"])
    t.play("1", {"card": "h:5", "marble": "1:0"})
    assert pos(t, "3")[0] == K and pos(t, "1")[0] == 25              # also the partner's marble
    t.st["turn"] = "1"
    t.play("1", {"card": "s:8", "marble": "1:1"})
    assert pos(t, "2")[0] == K and pos(t, "1")[1] == 30
    t.st["turn"] = "1"
    t.play("1", {"card": "c:2", "marble": "1:0", "home": False})     # 25 → 27: nobody there
    # passing a marble (not with a 7) does not kick it
    place(t, "2", 29, turn=False)
    t.st["turn"] = "1"
    t.st["hands"]["1"] = ["h:5"]
    t.play("1", {"card": "h:5", "marble": "1:0"})
    assert pos(t, "2")[0] == 29 and pos(t, "1")[:2] == [32, 30]


def test_home_entry_rules():
    t, _ = table(4)
    clear(t)
    # entry of player 1 is field 63; home fields H..H+3
    place(t, "1", 60, hand=["h:5", "s:8", "c:3", "d:6"])
    assert t.simulate("1", {"card": "h:5", "marble": "1:0", "home": True})[0]["1"][0][0] == H + 1
    assert t.simulate("1", {"card": "h:5", "marble": "1:0", "home": False})[0]["1"][0][0] == 1
    assert t.simulate("1", {"card": "h:5", "marble": "1:0"})[0]["1"][0][0] == H + 1     # auto: into the home
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "s:8", "marble": "1:0", "home": True})                  # too far (exact)
    assert t.simulate("1", {"card": "s:8", "marble": "1:0"})[0]["1"][0][0] == 4          # so on along the ring
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "c:3", "marble": "1:0", "home": True})                  # 3 does not reach it
    # no jumping over a marble in the home
    place(t, "1", 60, H + 1, hand=["h:5", "d:6", "c:3"])
    with pytest.raises(CommunityError, match="jumping"):
        t.simulate("1", {"card": "d:6", "marble": "1:0", "home": True})
    assert t.simulate("1", {"card": "c:3", "marble": "1:0"})[0]["1"][0][0] == 63
    assert t.simulate("1", {"card": "c:3", "marble": "1:0", "home": False})[0]["1"][0][0] == 63
    t.st["hands"]["1"] = ["h:2"]
    assert t.simulate("1", {"card": "h:2", "marble": "1:1"})[0]["1"][1][0] == H + 3     # inside the home: forward
    t.st["hands"]["1"] = ["h:3"]
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "h:3", "marble": "1:1"})                                # beyond the last field
    # a marble that has not left its start field cannot enter (it would need to go around first)
    place(t, "1", [0, 1], hand=["h:A"])
    assert t.simulate("1", {"card": "h:A", "marble": "1:0", "steps": 1})[0]["1"][0][0] == 1
    # the home never with a 4 backwards
    place(t, "1", 2, hand=["s:4"])
    assert t.simulate("1", {"card": "s:4", "kind": "back", "marble": "1:0"})[0]["1"][0][0] == 62


def test_four_backwards_from_start_then_home():
    t, _ = table(4)
    clear(t)
    place(t, "1", [0, 1], hand=["s:4", "h:5"])
    t.play("1", {"card": "s:4", "kind": "back", "marble": "1:0"})
    assert t.st["marbles"]["1"][0] == [60, 0]
    t.st["turn"] = "1"
    t.play("1", {"card": "h:5", "marble": "1:0", "home": True})
    assert pos(t, "1")[0] == H + 1
    # a 4 backwards kicks who sits there
    place(t, "2", 6, turn=False)
    place(t, "1", 10, hand=["s:4"])
    t.play("1", {"card": "s:4", "kind": "back", "marble": "1:0"})
    assert pos(t, "1")[0] == 6 and pos(t, "2")[0] == K


def test_seven_split_kicks_passed_marbles():
    t, _ = table(4)
    clear(t)
    place(t, "2", 22, 24, turn=False)
    place(t, "3", 5, turn=False)
    place(t, "1", 20, 3, hand=["h:7"])
    with pytest.raises(CommunityError, match="exactly 7"):
        t.simulate("1", {"card": "h:7", "split": [["1:0", 3], ["1:1", 3]]})
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "h:7", "split": [["1:0", 3], ["1:0", 4]]})               # each marble once
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "h:7", "split": [["2:0", 7]]})                           # not my marble
    t.play("1", {"card": "h:7", "split": [["1:0", 5], ["1:1", 2]]})
    assert pos(t, "1")[:2] == [25, 5]
    assert pos(t, "2")[:2] == [K, K] and pos(t, "3")[0] == K                            # passed (22, 24) and landed on (5)
    assert sorted(t.st["last"]["kicked"]) == ["2:0", "2:1", "3:0"]


def test_seven_own_marble_kicked_and_any_order():
    t, _ = table(4)
    clear(t)
    place(t, "1", 10, 12, hand=["h:7"])
    t.play("1", {"card": "h:7", "split": [["1:0", 7]]})                                 # passes its own marble
    assert pos(t, "1")[:2] == [17, K]
    # home lane: the front marble must move first – the server tries the other order
    clear(t)
    place(t, "1", H, H + 1, 30, hand=["h:7"])
    t.play("1", {"card": "h:7", "split": [["1:0", 2], ["1:1", 2], ["1:2", 3]]})
    assert sorted(pos(t, "1")[:3]) == [33, H + 2, H + 3]
    # the 7 must be used fully – else it cannot be played
    clear(t)
    place(t, "1", H + 1, hand=["h:7", "s:2"])
    assert all(m["card"] != "h:7" for m in t.moves("1"))


def test_jack_swap_restrictions():
    t, _ = table(4)
    clear(t)
    place(t, "2", [16, 1], 40, H, turn=False)                       # protected / ring / home
    place(t, "1", 10, 20, hand=["c:J"])
    with pytest.raises(CommunityError, match="protected"):
        t.simulate("1", {"card": "c:J", "marble": "1:0", "target": "2:0"})
    with pytest.raises(CommunityError, match="ring"):
        t.simulate("1", {"card": "c:J", "marble": "1:0", "target": "2:2"})
    with pytest.raises(CommunityError, match="ring"):
        t.simulate("1", {"card": "c:J", "marble": "1:0", "target": "2:3"})               # kennel
    with pytest.raises(CommunityError, match="another"):
        t.simulate("1", {"card": "c:J", "marble": "1:0", "target": "1:1"})               # own with own
    with pytest.raises(CommunityError, match="not your"):
        t.simulate("1", {"card": "c:J", "marble": "2:1", "target": "1:0"})
    swaps = {(m["marble"], m["target"]) for m in t.moves("1")}
    assert swaps == {("1:0", "2:1"), ("1:1", "2:1")}
    t.play("1", {"card": "c:J", "marble": "1:0", "target": "2:1"})
    assert pos(t, "1")[0] == 40 and pos(t, "2")[1] == 10
    # own protected marble cannot be swapped either
    place(t, "1", [0, 1], hand=["c:J"])
    with pytest.raises(CommunityError, match="protected"):
        t.simulate("1", {"card": "c:J", "marble": "1:0", "target": "2:1"})


def test_joker_any_card_and_house_rule():
    t, _ = table(4)
    clear(t)
    place(t, "1", hand=["x:X"])
    with pytest.raises(CommunityError, match="joker"):
        t.simulate("1", {"card": "x:X", "kind": "out", "marble": "1:0"})
    t.play("1", {"card": "x:X", "as": "K", "kind": "out", "marble": "1:0"})
    assert pos(t, "1")[0] == 0 and t.st["last"]["as"] == "K"
    clear(t)
    place(t, "1", H + 1, H + 2, H + 3, 61, hand=["x:X"])
    assert {m.get("as") for m in t.moves("1")} >= {"2", "4", "7"}
    assert t.simulate("1", {"card": "x:X", "as": "3", "marble": "1:3", "home": True})[0]["1"][3][0] == H
    t.r["joker_last"] = False
    with pytest.raises(CommunityError, match="joker"):
        t.simulate("1", {"card": "x:X", "as": "3", "marble": "1:3", "home": True})


def test_no_legal_move_throws_cards_away():
    t, _ = table(3)
    clear(t)
    for p in t.order():
        t.st["hands"][p] = ["h:5", "s:Q"]                           # nobody has a marble out: nobody can play
    t.st["hands"]["2"] = ["h:A", "s:5"]
    t._advance("1")
    assert t.st["turn"] == "2"
    t.play("2", {"card": "h:A", "kind": "out", "marble": "2:0"})
    # 3 and 1 cannot play: they throw their cards away, 2 goes again
    assert t.st["hands"]["3"] == [] and t.st["hands"]["1"] == [] and t.st["turn"] == "2"
    assert any(e.get("fold") for e in t.st["log"])
    t.play("2", {"card": "s:5", "marble": "2:0"})
    assert t.st["phase"] == "between"                                # all cards played: the round is over


@pytest.mark.parametrize("teams", [False, True])
def test_the_starter_plays_first(monkeypatch, teams):
    """apply_starter puts the starter first – they must also get the first turn (not the player after them)."""
    from familyquest.cardgames import apply_starter
    monkeypatch.setattr(kl.Table, "has_move", lambda self, p: True)
    for chosen in ("1", "3"):
        players = [{"id": str(i), "name": f"P{i}"} for i in range(1, 5)]
        st = {"kind": "kartenlauf", "rules": {**kl.DEFAULTS, "teams": teams, "bot_ms": 0}, "players": players, "phase": "lobby"}
        apply_starter(st, "choose", chosen, leader="1")
        t = kl.Table(st, random.Random(1), now=Clock())
        t.setup()
        if teams:
            for p in t.order():
                t.give(p, t.st["hands"][p][0])
        assert t.st["turn"] == chosen and st["starter"]["id"] == chosen


def test_card_exchange_in_teams(monkeypatch):
    monkeypatch.setattr(kl.Table, "has_move", lambda self, p: True)
    t, clock = table(4, teams=True)
    assert t.st["phase"] == "exchange" and t.st["turn"] is None
    hands = {p: list(h) for p, h in t.st["hands"].items()}
    with pytest.raises(CommunityError):
        t.play("2", {"card": hands["2"][0], "kind": "out", "marble": "2:0"})
    with pytest.raises(CommunityError):
        t.give("1", "nope")
    gave = {}
    for p in ("1", "2", "3"):
        gave[p] = hands[p][0]
        t.give(p, gave[p])
        with pytest.raises(CommunityError):
            t.give(p, hands[p][1])                                  # only once
    assert t.st["phase"] == "exchange"
    gave["4"] = hands["4"][-1]
    t.give("4", gave["4"])
    assert t.st["phase"] == "play"
    for p in t.order():
        pa = t.partner(p)
        assert gave[pa] in t.st["hands"][p] and t.st["got"][p] == gave[pa] and len(t.st["hands"][p]) == 6
    # bots give by themselves
    monkeypatch.undo()
    t2, _ = table(4, teams=True, bots=True)
    t2.tick()
    assert t2.st["phase"] in ("play", "between", "done") and t2.st["round"] >= 1


def test_team_plays_partner_marbles_and_wins():
    t, _ = table(4, teams=True)
    clear(t)
    place(t, "3", 40, turn=False)                                   # partner of 1 (seat 2)
    place(t, "1", H + 1, H + 2, H + 3, 62, hand=["h:2", "s:3", "c:5"])
    assert t.controlled(t.st["marbles"], "1") == ["1"]
    t.play("1", {"card": "h:2", "marble": "1:3", "home": True})
    assert t.home_count(t.st["marbles"], "1") == 4 and t.st["finished_order"] == ["1"]
    assert t.st["phase"] == "play"                                  # the team is not done yet
    assert t.controlled(t.st["marbles"], "1") == ["3"]
    t.st["turn"] = "1"
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "s:3", "marble": "1:0"})
    t.play("1", {"card": "s:3", "marble": "3:0"})                   # moves the partner's marble
    assert pos(t, "3")[0] == 43
    # the team wins with all 8 home
    place(t, "3", H + 1, H + 2, H + 3, 27, turn=False)
    t.st["turn"] = "1"
    t.play("1", {"card": "c:5", "marble": "3:3", "home": True})
    assert t.st["phase"] == "done" and t.st["winner"] == "0"
    assert t.st["places"] == {"1": 1, "3": 1, "2": 2, "4": 2}


def test_seven_with_partner_marbles():
    t, _ = table(4, teams=True)
    clear(t)
    place(t, "3", 40, turn=False)
    place(t, "1", H + 1, H + 2, H + 3, 60, hand=["h:7"])
    # 4 steps bring the last own marble home, the other 3 go to the partner
    assert "3:0" in t.seven_marbles("1")
    t.play("1", {"card": "h:7", "split": [["1:3", 4, True], ["3:0", 3]]})
    assert pos(t, "1")[3] == H and pos(t, "3")[0] == 43
    # without that: the partner's marbles only with the house rule
    clear(t)
    place(t, "3", 40, turn=False)
    place(t, "1", 10, hand=["h:7"])
    with pytest.raises(CommunityError):
        t.simulate("1", {"card": "h:7", "split": [["1:0", 4], ["3:0", 3]]})
    t.r["seven_partner"] = True
    assert t.simulate("1", {"card": "h:7", "split": [["1:0", 4], ["3:0", 3]]})[0]["3"][0][0] == 43


def test_win_alone_and_ranking():
    t, _ = table(3)
    clear(t)
    place(t, "2", H, 30, turn=False)
    place(t, "3", 5, turn=False)
    place(t, "1", H + 1, H + 2, H + 3, 62, hand=["h:2"])
    t.play("1", {"card": "h:2", "marble": "1:3", "home": True})
    assert t.st["phase"] == "done" and t.st["winner"] == "1"
    assert t.st["ranking"] == ["1", "2", "3"] and t.st["places"] == {"1": 1, "2": 2, "3": 3}


@pytest.mark.parametrize("n,teams", [(2, False), (3, False), (4, False), (4, True)])
def test_bots_play_full_games(n, teams):
    for seed in range(8):
        for level in ("easy", "normal", "hard"):
            t, clock = table(n, teams=teams, bots=True, seed=seed, level=level, seven_partner=bool(seed % 2), joker_last=bool(seed % 3))
            steps = 0
            while t.st["phase"] != "done":
                clock.t += 3
                t.tick()
                steps += 1
                assert steps < 5000, (n, teams, seed, level)
                # the board stays consistent: one marble per ring field, 4 marbles each, cards from the 110
                ring = [m[0] for ms in t.st["marbles"].values() for m in ms if 0 <= m[0] < kl.RING]
                assert len(ring) == len(set(ring))
            assert t.st["round"] < kl.MAX_ROUNDS
            if teams:
                w = t.st["winner"]
                assert all(t.home_count(t.st["marbles"], p) == 4 for p in t.members(w))
            else:
                assert t.home_count(t.st["marbles"], t.st["winner"]) == 4
            assert sorted(t.st["places"].values())[0] == 1


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def test_solo_view_hides_other_hands(fq, kid):
    fq.kartenlauf.start("kartenlauf", kid, {"seats": 4, "teams": True, "level": "easy", "bot_ms": 5000}, solo=True)
    v = fq.kartenlauf.state("kartenlauf", kid)
    assert v["solo"] and v["phase"] == "exchange" and len(v["players"]) == 4 and v["teams"]
    assert len(v["hand"]) == 6 and all(p["cards"] == 6 for p in v["players"])
    row = fq.db.q1("SELECT state FROM card_game WHERE kind='kartenlauf'")
    st = json.loads(row["state"])
    others = [c for p, h in st["hands"].items() if p != str(kid) for c in h]
    assert "hands" not in v and "deck" not in v
    text = json.dumps({k: x for k, x in v.items() if k not in ("hand", "moves", "seven", "top", "log", "last", "rules")})
    assert not any(c in text for c in others)
    # partner of the child: a bot opposite
    me = next(p for p in v["players"] if p["id"] == str(kid))
    assert me["seat"] == 0 and next(p for p in v["players"] if p["id"] == me["partner"])["seat"] == 2
    fq.kartenlauf.give("kartenlauf", kid, v["hand"][0])
    v = fq.kartenlauf.state("kartenlauf", kid)
    assert v["phase"] in ("play", "between") and v["got"]                   # the bots gave at once, the partner's card came


def test_rules_remembered_and_cleaned(fq, kid):
    assert fq.kartenlauf.clean_rules("kartenlauf", {"seats": 7, "level": "x", "bot_ms": 99999}) == {**kl.DEFAULTS, "bot_ms": 5000}
    fq.kartenlauf.start("kartenlauf", kid, {"seats": 3, "teams": False, "level": "hard"}, solo=True)
    assert fq.kartenlauf.default_rules()["seats"] == 3 and fq.kartenlauf.default_rules()["level"] == "hard"
    v = fq.kartenlauf.state("kartenlauf", kid)
    assert len(v["players"]) == 3 and not v["teams"] and all(p["level"] == "hard" for p in json.loads(
        fq.db.q1("SELECT state FROM card_game WHERE kind='kartenlauf'")["state"])["players"] if p.get("bot"))


def _finish_family(fq, winner_ids):
    """Let the side of the given players win the running family table."""
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='kartenlauf' AND solo=0 AND status!='done'")
    st = json.loads(row["state"])
    t = kl.Table(st)
    pid = winner_ids[0]
    st["marbles"][pid] = [[H + 1, 0], [H + 2, 0], [H + 3, 0], [(t.entry_of(pid) - 1) % kl.RING, 0]]
    st["phase"], st["turn"] = "play", pid
    st["hands"][pid] = ["h:2"]
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
    return row["id"]


def test_family_table_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert client.get("/api/parent/game-rewards", headers=phd).json()["kartenlauf"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"kartenlauf": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/kartenlauf/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/kartenlauf/start", json={"seats": 3, "teams": False, "level": "easy", "bot_ms": 5000}, headers=hm).json()
    assert st["phase"] == "lobby" and st["free"] == 2 and not st["coins_on"]
    assert client.post("/api/community/kartenlauf/play", json={"card": "h:5"}, headers=hm).status_code == 400   # not started
    assert client.post("/api/community/kartenlauf/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/kartenlauf/begin", headers=hl).status_code == 403                       # Leo does not lead
    st = client.post("/api/community/kartenlauf/begin", headers=hm).json()
    assert st["phase"] in ("play", "between") and len(st["players"]) == 3 and st["coins_on"]
    assert client.get("/api/me", headers=hl).json()["community"]["kartenlauf"]["joined"]
    gid = _finish_family(fq, [str(mia)])
    before = fq.rewards.balance(mia, "coins"), fq.rewards.balance(leo, "coins")
    v = client.post("/api/community/kartenlauf/play", json={"card": "h:2", "marble": f"{mia}:3", "home": True}, headers=hm).json()
    assert v["phase"] == "done" and v["winner"] == str(mia)
    coins = {p["id"]: (p["place"], p["coins"]) for p in v["players"] if not p["bot"]}
    assert coins[str(mia)] == (1, 8) and coins[str(leo)][1] in (4, 1)
    assert fq.rewards.balance(mia, "coins") == before[0] + 8
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.kartenlauf._save(row, json.loads(row["state"]))                                                         # paid once
    client.get("/api/community/kartenlauf", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before[0] + 8
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"kartenlauf:{gid}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"kartenlauf:{gid}:{mia}")["reason"] == "Card Race – place 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "kartenlauf" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["coins"] == 8


def test_team_coins_both_winners_place_1(fq):
    st = {"solo": False, "phase": "done", "players": [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "bot1", "bot": True}],
          "places": {"1": 1, "bot1": 1, "2": 2, "3": 2}}
    assert fq.kartenlauf.coins_for(st) == {"1": 10, "2": 5, "3": 5}
    assert fq.kartenlauf.coins_for({**st, "players": [{"id": "1"}, {"id": "2", "guest": True}, {"id": "bot1", "bot": True}]}) == {}
    assert fq.kartenlauf.coins_for({**st, "solo": True}) == {}


def test_no_coins_alone_against_bots(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    st = client.post("/api/community/kartenlauf/start", json={"solo": True, "seats": 2, "bot_ms": 5000}, headers=hm).json()
    assert st["solo"] and st["phase"] in ("play", "between") and not st["coins_on"] and len(st["players"]) == 2
    assert client.get("/api/community/kartenlauf", headers=login(client, leo)).json() is None                  # private
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='kartenlauf' AND solo=1")
    s = json.loads(row["state"])
    s["marbles"][str(mia)] = [[H + 1, 0], [H + 2, 0], [H + 3, 0], [62, 0]]
    s["phase"], s["turn"], s["hands"][str(mia)] = "play", str(mia), ["h:2"]
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), row["id"])
    v = client.post("/api/community/kartenlauf/play", json={"card": "h:2", "marble": f"{mia}:3"}, headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'kartenlauf:%'")


def test_guests_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/kartenlauf/start", json={"seats": 2}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "kartenlauf"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Card Race"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    v = client.get("/api/community/kartenlauf", headers=hg).json()
    assert v["joined"] and [p["guest"] for p in v["players"]] == [False, True] and not v["coins_on"]
    assert client.post("/api/community/kartenlauf/begin", headers=hg).status_code in (401, 403)
    assert client.post("/api/community/kartenlauf/start", json={"solo": True}, headers=hg).status_code in (401, 403)
    assert client.post("/api/community/kartenlauf/end", headers=hg).status_code in (401, 403)
    assert netfilter.is_guest_path("/api/community/kartenlauf") and netfilter.is_guest_path("/api/community/kartenlauf/play")
    assert netfilter.is_guest_path("/api/community/kartenlauf/give")
    for p in ("start", "begin", "end", "rules"):
        assert not netfilter.is_guest_path(f"/api/community/kartenlauf/{p}")
    st = client.post("/api/community/kartenlauf/begin", headers=hm).json()
    assert st["phase"] in ("play", "between") and len(st["players"]) == 2


def test_switched_off(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.put("/api/parent/games", json={"access": {"kartenlauf": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/kartenlauf", headers=hm).status_code == 403
    assert client.post("/api/community/kartenlauf/start", json={"solo": True}, headers=hm).status_code == 403
    assert client.get("/api/community/kartenlauf", headers=phd).status_code == 200
    me = client.get("/api/me", headers=hm).json()
    assert "kartenlauf" not in me["games_list"] and me["community"]["kartenlauf"] is None
