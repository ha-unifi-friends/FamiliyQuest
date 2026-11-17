"""«Jass» (Schieber) – ranking, following suit, no under-trumping, the Buur, points (157 / Match), Weis and Stöck,
pushing, bots on all levels, the table in the app (coins once, end by the leader, only own cards, running games)."""
import json
import random

import pytest

from familyquest import jass as J
from familyquest.community import CommunityError


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(people=4, bots=0, seed=1, level="normal", **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, people + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "jass", "rules": {**J.DEFAULTS, "bot_ms": 0, **rules}, "players": players, "phase": "lobby"}
    clock = Clock()
    t = J.Table(st, random.Random(seed), now=clock)
    t.setup()
    return t, clock


def hands(t, *hs, mode=None, turn="1", trick=()):
    """Set the four hands (seat order), the trump and whose turn it is."""
    for pid, h in zip(t.order(), hs):
        t.st["hands"][pid] = list(h)
    if mode:
        t.st.update(mode=mode, phase="play", picker=turn, chooser=turn)
    t.st.update(turn=turn, trick=[list(x) for x in trick])


# ---------------------------------------------------------------- ranking and points
def test_card_ranking_and_points():
    assert J.TRUMP_ORDER[-1] == "U" and J.TRUMP_ORDER[-2] == "9" and J.TRUMP_ORDER[-3] == "A"
    tr = "rosen"
    trick = [["1", "rosen:A"], ["2", "rosen:9"], ["3", "rosen:U"], ["4", "rosen:K"]]
    assert J.trick_winner(trick, tr) == 2                                    # the Buur takes it
    assert J.trick_winner([["1", "rosen:A"], ["2", "rosen:9"]], tr) == 1      # Nell over the Ass
    assert J.trick_winner([["1", "eicheln:6"], ["2", "eicheln:A"], ["3", "rosen:6"]], tr) == 2   # the smallest trump
    assert J.trick_winner([["1", "eicheln:6"], ["2", "schellen:A"]], tr) == 0  # another suit never takes it
    assert J.trick_winner([["1", "eicheln:K"], ["2", "eicheln:A"]], "obe") == 1
    assert J.trick_winner([["1", "eicheln:K"], ["2", "eicheln:6"], ["3", "eicheln:A"]], "une") == 1
    assert J.points("rosen:U", tr) == 20 and J.points("rosen:9", tr) == 14 and J.points("eicheln:U", tr) == 2
    assert J.points("eicheln:8", tr) == 0 and J.points("eicheln:8", "obe") == 8 and J.points("eicheln:6", "une") == 11
    assert J.points("eicheln:A", "une") == 0
    for kind in ("swiss", "french"):
        d = J.deck(kind)
        assert len(d) == 36 == len(set(d))
        for mode in J.DECKS[kind] + ["obe", "une"]:
            assert sum(J.points(c, mode) for c in d) + J.LAST_TRICK == 157
    assert J.rank("h:J") == "U" and J.rank("h:Q") == "O" and J.points("h:J", "h") == 20


# ---------------------------------------------------------------- following
def test_follow_suit_and_trump_in():
    t, _ = table()
    hands(t, ["eicheln:A"], ["eicheln:6", "rosen:7", "schellen:K"], [], [], mode="rosen", turn="2",
          trick=[["1", "eicheln:A"]])
    assert sorted(t.legal("2")) == ["eicheln:6", "rosen:7"]                  # follow or trump in – no other suit
    with pytest.raises(CommunityError, match="may not be played"):
        t.play("2", "schellen:K")
    hands(t, [], ["schilten:6", "rosen:7", "schellen:K"], [], [], turn="2", trick=[["1", "eicheln:A"]])
    assert len(t.legal("2")) == 3                                           # no Eicheln: anything
    t.st["mode"] = "obe"
    hands(t, [], ["eicheln:6", "rosen:7"], [], [], turn="2", trick=[["1", "eicheln:A"]])
    assert t.legal("2") == ["eicheln:6"]                                    # Obenabe: no trump to play in


def test_no_under_trumping():
    t, _ = table()
    hands(t, [], [], ["eicheln:7", "rosen:6", "rosen:U"], [], mode="rosen", turn="3",
          trick=[["1", "eicheln:A"], ["2", "rosen:A"]])
    assert sorted(t.legal("3")) == ["eicheln:7", "rosen:U"]                 # rosen:6 would under-trump
    hands(t, [], [], ["schilten:7", "rosen:6"], [], turn="3", trick=[["1", "eicheln:A"], ["2", "rosen:A"]])
    assert t.legal("3") == ["schilten:7"]                                   # no Eicheln: still no under-trumping
    hands(t, [], [], ["rosen:6", "rosen:7"], [], turn="3", trick=[["1", "eicheln:A"], ["2", "rosen:A"]])
    assert sorted(t.legal("3")) == ["rosen:6", "rosen:7"]                   # only trumps left: allowed


def test_buur_may_be_held_back():
    t, _ = table()
    hands(t, ["rosen:A"], ["rosen:U", "eicheln:6", "schellen:K"], [], [], mode="rosen", turn="2", trick=[["1", "rosen:A"]])
    assert len(t.legal("2")) == 3                                           # the Buur is the only trump: free
    hands(t, ["rosen:A"], ["rosen:U", "rosen:6", "eicheln:6"], [], [], turn="2", trick=[["1", "rosen:A"]])
    assert sorted(t.legal("2")) == ["rosen:6", "rosen:U"]                   # another trump: follow trump


def test_only_own_cards_and_turns():
    t, _ = table()
    hands(t, ["eicheln:A", "eicheln:K"], ["eicheln:6"], ["eicheln:7"], ["eicheln:8"], mode="rosen", turn="1")
    with pytest.raises(CommunityError, match="not your turn"):
        t.play("2", "eicheln:6")
    with pytest.raises(CommunityError, match="do not have"):
        t.play("1", "eicheln:6")
    with pytest.raises(CommunityError, match="not at this table"):
        t.play("9", "eicheln:6")
    t.play("1", "eicheln:A")
    assert t.st["turn"] == "2" and t.legal("1") == []


# ---------------------------------------------------------------- trump, pushing
def test_first_chooser_and_pushing():
    t, _ = table(seed=3)
    holder = next(p for p, h in t.st["hands"].items() if "schellen:7" in h)
    assert t.st["phase"] == "trump" and t.st["turn"] == holder == t.st["chooser"]
    with pytest.raises(CommunityError, match="not your turn"):
        t.choose(t.partner(holder), "obe")
    with pytest.raises(CommunityError, match="Choose a trump"):
        t.choose(holder, "xyz")
    t.choose(holder, "push")
    assert t.st["turn"] == t.partner(holder) and t.st["pushed"]
    with pytest.raises(CommunityError, match="Pushed already"):
        t.choose(t.partner(holder), "push")
    t.choose(t.partner(holder), "une")
    assert t.st["mode"] == "une" and t.st["phase"] == "play" and t.st["picker"] == t.partner(holder)
    assert t.st["turn"] == holder                                           # who pushed leads the first trick
    # next round: the next seat to the right chooses
    t.st.update(phase="between", next_at=0)
    t.next_round(holder)
    assert t.st["round"] == 2 and t.st["chooser"] == t.nxt(holder) and t.st["phase"] == "trump"


# ---------------------------------------------------------------- a whole round: 157, Match
def play_round(t, level="normal"):
    while t.st["phase"] in ("trump", "play"):
        p = t.st["turn"]
        if t.st["phase"] == "trump":
            t.choose(p, t.bot_choose(p, level))
        else:
            assert t.st["hands"][p] and t.legal(p)
            t.play(p, t.bot_card(p, level))


def test_points_add_up_to_157_and_match():
    for seed in range(12):
        t, _ = table(seed=seed, weis=False, stoeck=False, goal="rounds", rounds=1)
        play_round(t)
        rr = t.st["round_result"]
        assert sum(rr["cards"]) == 157 and sum(t.st["tricks"]) == 9
        assert sum(rr["points"]) == 157 + (100 if rr["match"] is not None else 0)
        assert t.st["phase"] == "done" and t.st["complete"]
    # a Match: one team takes all 9 tricks – 257
    t, _ = table(weis=False, stoeck=False, goal="rounds", rounds=1)
    strong = [f"rosen:{r}" for r in J.NATURAL]                             # all Rosen to player 1
    rest = [c for c in J.deck("swiss") if not c.startswith("rosen")]
    hands(t, strong, rest[0:9], rest[9:18], rest[18:27], mode="rosen", turn="1")
    for _ in range(9):
        for _ in range(4):
            p = t.st["turn"]
            t.play(p, t.legal(p)[0])
    assert t.st["round_result"]["points"] == [257, 0] and t.st["round_result"]["match"] == 0


def test_multipliers():
    t, _ = table(mult=True, weis=False, stoeck=False, goal="rounds", rounds=1, seed=2)
    hands(t, *[t.st["hands"][p] for p in t.order()], mode="obe", turn=t.st["chooser"])
    assert t.multiplier() == 3
    t.st["phase"] = "play"
    play_round(t)
    assert sum(t.st["round_result"]["points"]) in (157 * 3, 257 * 3)
    t, _ = table(mult=False)
    t.st["mode"] = "obe"
    assert t.multiplier() == 1
    t.st["mode"] = "schellen"
    t.r["mult"] = True
    assert t.multiplier() == 1 and J.MULT["eicheln"] == 2 and J.MULT["s"] == 2 and J.MULT["h"] == 1


# ---------------------------------------------------------------- Weis and Stöck
def test_weis_found():
    ws = J.weis_of(["rosen:6", "rosen:7", "rosen:8", "rosen:9", "eicheln:U", "rosen:U", "schellen:U", "schilten:U", "eicheln:A"])
    assert sorted(w["points"] for w in ws) == [50, 200]                      # Vierblatt + 4 Under
    ws = J.weis_of(["h:10", "h:J", "h:Q", "h:K", "h:A", "s:6", "s:7", "s:8", "c:9"])
    assert sorted(w["points"] for w in ws) == [20, 100]                      # Fünfblatt (French: J, Q) + Dreiblatt
    assert J.weis_of(["h:8", "s:8", "c:8", "d:8", "h:A", "s:10"]) == []                    # four 8s: nothing
    nines = J.weis_of(["h:9", "s:9", "c:9", "d:9"])
    assert [w["points"] for w in nines] == [150]
    # the better Weis: more points, then more cards, then the higher card, then trump
    a = {"kind": "seq", "cards": ["h:6", "h:7", "h:8"], "points": 20, "suit": "h"}
    b = {"kind": "seq", "cards": ["s:7", "s:8", "s:9"], "points": 20, "suit": "s"}
    assert J.weis_key(b, "obe") > J.weis_key(a, "obe") and J.weis_key(a, "une") > J.weis_key(b, "une")
    c = {"kind": "seq", "cards": ["c:7", "c:8", "c:9"], "points": 20, "suit": "c"}
    assert J.weis_key(c, "c") > J.weis_key(b, "c")


def test_best_weis_team_writes_all_its_weis():
    W = lambda *cs: J.weis_of(list(cs))                                      # noqa: E731
    t, _ = table(stoeck=False)
    t.st["mode"] = "schilten"
    t.st["weis"] = {"1": W("eicheln:6", "eicheln:7", "eicheln:8") + W("schellen:6", "schellen:7", "schellen:8"),
                    "3": W("eicheln:10", "eicheln:U", "eicheln:O"), "2": W("rosen:7", "rosen:8", "rosen:9", "rosen:10")}
    t._weis_resolve("1")
    assert t.st["weis_win"]["team"] == 1 and t.st["weis_pts"] == [0, 50]          # 50 beats 20 + 20 + 20
    assert set(t.st["weis_win"]["shown"]) == {"2"}
    t.st.update(weis_pts=[0, 0], weis={"1": W("eicheln:6", "eicheln:7", "eicheln:8", "eicheln:9"), "3": W("rosen:6", "rosen:7", "rosen:8"),
                                       "2": W("rosen:A", "schilten:A", "eicheln:A", "schellen:A")})
    t._weis_resolve("2")
    assert t.st["weis_win"]["team"] == 1 and t.st["weis_pts"] == [0, 100]         # 4 Ass (100) over a Vierblatt (50)
    # equal Weis: the first to play wins
    for first, team in (("2", 1), ("3", 0), ("1", 1)):
        t, _ = table(stoeck=False)
        t.st.update(mode="une", weis={"2": W("eicheln:6", "eicheln:7", "eicheln:8"), "3": W("schellen:6", "schellen:7", "schellen:8")})
        t._weis_resolve(first)
        assert t.st["weis_win"]["team"] == team and t.st["weis_pts"][team] == 20, first
    # declared with the first card, resolved after the first trick
    h1 = ["eicheln:6", "eicheln:7", "eicheln:8", "eicheln:9", "schilten:A", "schilten:K", "schellen:6", "rosen:A", "rosen:10"]
    rest = [c for c in J.deck("swiss") if c not in h1]
    for rule in (True, False):
        t, _ = table(stoeck=False, weis=rule)
        hands(t, h1, rest[0::3][:9], rest[1::3][:9], rest[2::3][:9], mode="schilten", turn="1")
        t.play("1", "schellen:6")
        assert ("1" in t.st["weis"]) == rule and any(e["kind"] == "weis" and e["points"] == 50 for e in t.st["log"]) == rule
        for _ in range(3):
            p = t.st["turn"]
            t.play(p, t.legal(p)[0])
        if rule:
            assert t.st["weis_win"] and t.st["weis_pts"][t.st["weis_win"]["team"]] >= 50
        else:
            assert t.st["weis_pts"] == [0, 0] and t.st["weis_win"] is None


def test_stoeck():
    others = [c for c in J.deck("swiss") if c not in ("rosen:K", "rosen:O")]
    h1 = ["rosen:K", "rosen:O"] + others[0:7]
    for mode, holder, stoeck in (("rosen", "1", [20, 0]), ("eicheln", "4", [0, 20]), ("obe", None, [0, 0])):   # 4: all Eicheln
        t, _ = table(weis=False, goal="rounds", rounds=1)
        hands(t, h1, others[7:16], others[16:25], others[25:34])
        t.st.update(chooser="1", turn="1")
        t.choose("1", mode)
        assert t.st["stoeck"] == holder
        play_round(t)
        rr = t.st["round_result"]
        assert rr["stoeck"] == stoeck
        assert sum(rr["points"]) == 157 + sum(stoeck) + (100 if rr["match"] is not None else 0)
    t, _ = table(weis=False, stoeck=False)
    hands(t, h1, others[7:16], others[16:25], others[25:34])
    t.st.update(chooser="1", turn="1")
    t.choose("1", "rosen")
    assert t.st["stoeck"] is None                                             # rule off


# ---------------------------------------------------------------- bots, whole games
@pytest.mark.parametrize("level", ["easy", "normal", "hard"])
def test_bots_finish_games(level):
    for seed in range(3):
        t, clock = table(0, bots=4, seed=seed, level=level, target=1000)
        t.tick()                                                             # bots only: the whole game at once
        assert t.st["phase"] == "done" and t.st["complete"] and max(t.st["totals"]) >= 1000
        assert sorted(t.st["places"].values()) in ([1, 1, 2, 2], [1, 1, 1, 1])
        assert {t.st["places"][p] for p in t.order()[0::2]} == {1 if t.st["totals"][0] >= t.st["totals"][1] else 2}
        for rr in t.st["rounds_log"]:
            assert sum(rr["cards"]) == 157
    t, _ = table(0, bots=4, seed=9, level=level, goal="rounds", rounds=3, mult=True, deck="french")
    t.tick()
    assert t.st["phase"] == "done" and len(t.st["rounds_log"]) == 3


def test_bot_trump_choice_by_strength():
    t, _ = table()
    strong = ["rosen:U", "rosen:9", "rosen:A", "rosen:K", "rosen:10", "eicheln:A", "schilten:A", "schellen:6", "eicheln:7"]
    weak = ["rosen:7", "rosen:9", "eicheln:8", "eicheln:10", "schilten:7", "schilten:9", "schellen:8", "schellen:O", "eicheln:U"]
    aces = ["rosen:A", "rosen:K", "rosen:O", "eicheln:A", "eicheln:K", "schilten:A", "schilten:K", "schellen:A", "schellen:7"]
    t.st["turn"] = "1"
    t.st["hands"]["1"] = strong
    assert t.bot_choose("1", "hard") == "rosen"
    t.st["hands"]["1"] = weak
    assert t.bot_choose("1", "hard") == "push"
    t.st["pushed"] = True
    assert t.bot_choose("1", "hard") != "push"                              # pushed to: must choose
    t.st["pushed"] = False
    t.st["hands"]["1"] = aces
    assert t.bot_choose("1", "hard") == "obe"


def test_hard_bots_play_partner_aware():
    t, _ = table()
    # the partner (seat 1) takes it with the Ass, I am last: «schmieren» the 10
    hands(t, [], [], ["eicheln:10", "eicheln:6", "rosen:7"], [], mode="schilten", turn="3",
          trick=[["4", "eicheln:8"], ["1", "eicheln:A"], ["2", "eicheln:7"]])
    assert t.bot_card("3", "hard") == "eicheln:10" and t.bot_card("3", "normal") == "eicheln:10"
    # an opponent takes it, I am last and can take it cheaply
    hands(t, [], [], ["eicheln:K", "eicheln:6", "schilten:6"], [], turn="3", trick=[["4", "eicheln:10"], ["1", "eicheln:7"], ["2", "eicheln:O"]])
    assert t.bot_card("3", "hard") == "eicheln:K"
    # nothing to win: the cheapest card, not the trump
    hands(t, [], [], ["eicheln:6", "schilten:U", "rosen:A"], [], turn="3", trick=[["4", "eicheln:9"], ["1", "eicheln:7"], ["2", "eicheln:8"]])
    assert t.bot_card("3", "hard") == "eicheln:6"
    # … but 11 points are worth the Buur
    hands(t, [], [], ["eicheln:6", "schilten:U", "rosen:A"], [], turn="3", trick=[["4", "eicheln:A"], ["1", "eicheln:7"], ["2", "eicheln:8"]])
    assert t.bot_card("3", "hard") == "schilten:U"


def test_hard_beats_easy():
    diff = 0
    for seed in range(40):
        for sw in (0, 1):
            t, _ = table(0, bots=4, seed=seed, goal="rounds", rounds=1)
            for i, p in enumerate(t.st["players"]):
                p["level"] = "hard" if i % 2 == sw else "easy"
            t.tick()
            tot = t.st["totals"]
            diff += tot[sw] - tot[1 - sw]
    assert diff > 0


def test_bots_wait_for_their_reaction_time():
    t, clock = table(1, bots=3, bot_ms=1000, seed=4)
    t.st.update(phase="trump", chooser="bot1", turn="bot1", pushed=False, turn_at=clock.t)
    seq = t.st["seq"]
    assert not t.tick()
    clock.t += 1.1
    assert t.tick() and t.st["seq"] == seq + 1                               # one move per reaction time
    assert not t.tick()


def test_seating():
    assert J.seating(["a", "b"], ["x", "y"], True) == ["a", "x", "b", "y"]
    assert J.seating(["a", "b"], ["x", "y"], False) == ["a", "b", "x", "y"]
    assert J.seating(["a", "b", "c"], ["x"]) == ["a", "b", "c", "x"]
    assert J.seating(["a"], ["x", "y", "z"]) == ["a", "x", "y", "z"]


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _force(fq, gid, fn):
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    s = json.loads(row["state"])
    fn(s)
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), gid)


def drive(client, hd, st, n=4000):
    for _ in range(n):
        if st["phase"] == "done":
            return st
        if st["can_choose"]:
            st = client.post("/api/community/jass/trump", json={"mode": "push" if st["can_push"] else "obe"}, headers=hd).json()
        elif st["my_turn"] and st["legal"]:
            st = client.post("/api/community/jass/play", json={"card": st["legal"][-1]}, headers=hd).json()
        elif st["phase"] == "between":
            st = client.post("/api/community/jass/next", headers=hd).json()
        else:
            st = client.get("/api/community/jass", headers=hd).json()
    raise AssertionError("the game did not end")


def test_solo_with_bots_no_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    st = client.post("/api/community/jass/start", json={"solo": True, "level": "hard", "bot_ms": 0, "goal": "rounds", "rounds": 2},
                     headers=hm).json()
    assert st["solo"] and st["phase"] in ("trump", "play") and len(st["players"]) == 4 and not st["coins_on"]
    assert len(st["hand"]) == 9
    assert st["players"][0]["id"] == str(mia) and all(p["bot"] for p in st["players"][1:])
    assert "hands" not in st and all("hand" not in p for p in st["players"])          # only the own cards
    st = drive(client, hm, st)
    assert st["complete"] and len(st["rounds_log"]) == 2 and all(p["coins"] == 0 for p in st["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'jass:%'")
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "jass" and hist[0]["data"]["complete"] and hist[0]["data"]["rounds"] == 2
    assert client.get("/api/community/jass", headers=login(client, leo)).json() is None


def test_family_table_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert client.get("/api/parent/game-rewards", headers=phd).json()["jass"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"jass": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/jass/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/jass/start", json={"bot_ms": 0, "partners": True, "deck": "french"}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"] and st["bots"] == 3
    assert client.post("/api/community/jass/play", json={"card": "h:A"}, headers=hm).status_code == 400   # not started
    v = client.post("/api/community/jass/join", headers=hl).json()
    assert v["coins_on"] and [s["id"] for s in v["seating"]] == [str(mia), None, str(leo), None]
    assert client.post("/api/community/jass/begin", headers=hl).status_code == 403          # Leo does not lead
    assert client.post("/api/community/jass/mix", headers=hl).status_code == 403
    st = client.post("/api/community/jass/begin", headers=hm).json()
    assert [p["id"] for p in st["players"]][0::2] == [str(mia), str(leo)] and st["my_team"] == 0     # partners
    assert client.get("/api/me", headers=hl).json()["community"]["jass"]["joined"]
    lv = client.get("/api/community/jass", headers=hl).json()
    assert lv["my_seat"] == 2 and len(lv["hand"]) == 9 and set(lv["hand"]).isdisjoint(st["hand"])
    assert all(c.split(":")[0] in ("s", "h", "c", "d") for c in lv["hand"])
    gid = st["game"]
    # somebody else's card / a card not in the hand: refused
    assert client.post("/api/community/jass/play", json={"card": lv["hand"][0]}, headers=hm).status_code == 400
    assert client.post("/api/community/jass/trump", json={"mode": "xx"}, headers=hl).status_code == 400
    # play to the end (target 300 – a short game)
    _force(fq, gid, lambda s: s["rules"].update(target=300))
    for _ in range(3000):
        sm = client.get("/api/community/jass", headers=hm).json()
        if sm["phase"] == "done":
            break
        for hd in (hm, hl):
            s = client.get("/api/community/jass", headers=hd).json()
            if s["phase"] == "between":
                client.post("/api/community/jass/next", headers=hd)
            elif s["can_choose"]:
                client.post("/api/community/jass/trump", json={"mode": "push" if s["can_push"] else "h"}, headers=hd)
            elif s["my_turn"] and s["legal"]:
                assert set(s["legal"]) <= set(s["hand"])
                client.post("/api/community/jass/play", json={"card": s["legal"][0]}, headers=hd)
    assert sm["phase"] == "done" and sm["complete"]
    won = sm["players"][0]["place"] == 1
    coins = {p["id"]: p["coins"] for p in sm["players"] if not p["bot"]}
    assert coins == ({str(mia): 8, str(leo): 8} if won else {str(mia): 0, str(leo): 0})
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.jass._save(row, json.loads(row["state"]))                                          # paid once
    client.get("/api/community/jass", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"jass:{gid}:%") == (2 if won else 0)
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "jass" and hist[0]["data"]["place"] == (1 if won else 2) and hist[0]["data"]["partner"] == "Leo"


def test_coins_rules(fq):
    st = {"solo": False, "phase": "done", "complete": True, "places": {"1": 1, "b1": 2, "2": 1, "b2": 2},
          "players": [{"id": "1"}, {"id": "b1", "bot": True}, {"id": "2"}, {"id": "b2", "bot": True}]}
    assert fq.jass.coins_for(st) == {"1": 10, "2": 10}
    st2 = {**st, "places": {"1": 1, "b1": 2, "2": 2, "b2": 1}}
    assert fq.jass.coins_for(st2) == {"1": 10}                                       # only the winning team
    assert fq.jass.coins_for({**st, "complete": False}) == {}
    assert fq.jass.coins_for({**st, "solo": True}) == {}
    assert fq.jass.coins_for({**st, "players": [{"id": "1"}, {"id": "2", "guest": True}, {"id": "b1", "bot": True}]}) == {}


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/jass/start", json={"bot_ms": 5000, "partners": False}, headers=hm)
    client.post("/api/community/jass/join", headers=hl)
    st = client.post("/api/community/jass/begin", headers=hm).json()
    assert [p["id"] for p in st["players"]][:2] == [str(mia), str(leo)]                 # against each other
    assert client.post("/api/community/jass/end", headers=hl).status_code == 403
    v = client.post("/api/community/jass/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'jass:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='jass'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    r = fq.jass.clean_rules("jass", {"deck": "x", "level": "x", "bot_ms": 99999, "target": 1, "rounds": 99, "goal": "x", "back": "x"})
    assert r == {**J.DEFAULTS, "bot_ms": 5000, "target": 300, "rounds": 24}
    fq.jass.start("jass", kid, {"level": "hard", "deck": "french", "mult": True}, solo=True)
    assert fq.jass.default_rules()["deck"] == "french" and fq.jass.default_rules()["mult"] is True
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='jass'")["state"])
    assert len(st["players"]) == 4 and all(p["level"] == "hard" for p in st["players"][1:])


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/jass/start", json={}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "jass"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Jass"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "mix"):
        assert client.post("/api/community/jass/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.get("/api/community/jass/rules", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/jass/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"] if not p["bot"]] == [False, True] and not st["coins_on"]
    assert client.get("/api/community/jass", headers=hg).json()["hand"]
    client.post("/api/community/jass/end", headers=hm)
    for p in ("", "/join", "/trump", "/play"):
        assert netfilter.is_guest_path("/api/community/jass" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/mix"):
        assert not netfilter.is_guest_path("/api/community/jass" + p), p


def test_switched_off_blocks_it(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "jass" in client.get("/api/me", headers=hm).json()["games_list"]
    assert client.put("/api/parent/games", json={"access": {"jass": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/jass", headers=hm).status_code == 403
    assert client.post("/api/community/jass/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "jass" not in me["games_list"] and me["community"]["jass"] is None


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/jass/start", json={"solo": True, "bot_ms": 5000}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "jass")
    assert g["title"] == "Jass" and g["icon"] == J.EMOJI and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "jass" for x in r["running"])
    v = client.get("/api/community/jass", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]
