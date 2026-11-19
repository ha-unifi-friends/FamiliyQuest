"""«Fünf Würfel» – scoring, rolling and holding, simultaneous rounds, bots, the table in the app."""
import json
import random

import pytest

from familyquest import wuerfel as fw
from familyquest.community import CommunityError


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(n=2, bots=0, seed=1, level="normal", **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "wuerfel", "rules": {**fw.DEFAULTS, "bot_ms": 0, **rules}, "players": players, "phase": "lobby"}
    clock = Clock()
    t = fw.Table(st, random.Random(seed), now=clock)
    t.setup()
    return t, clock


def set_dice(t, pid, dice, rolls=1):
    t.st["dice"][pid] = list(dice)
    t.st["rolls"][pid] = rolls


# ---------------------------------------------------------------- scoring
@pytest.mark.parametrize("cat, dice, pts", [
    ("ones", [1, 1, 3, 4, 1], 3), ("twos", [2, 2, 2, 2, 5], 8), ("threes", [1, 2, 4, 5, 6], 0), ("fours", [4, 4, 1, 1, 1], 8),
    ("fives", [5, 5, 5, 5, 5], 25), ("sixes", [6, 6, 6, 1, 2], 18),
    ("three_kind", [3, 3, 3, 1, 6], 16), ("three_kind", [3, 3, 2, 1, 6], 0), ("three_kind", [4, 4, 4, 4, 1], 17),
    ("four_kind", [2, 2, 2, 2, 6], 14), ("four_kind", [2, 2, 2, 5, 6], 0), ("four_kind", [6, 6, 6, 6, 6], 30),
    ("full_house", [2, 2, 3, 3, 3], 25), ("full_house", [2, 2, 3, 3, 4], 0), ("full_house", [5, 5, 5, 5, 5], 0),
    ("small_straight", [1, 2, 3, 4, 6], 30), ("small_straight", [3, 4, 5, 6, 6], 30), ("small_straight", [2, 3, 4, 5, 1], 30),
    ("small_straight", [1, 2, 3, 5, 6], 0),
    ("large_straight", [5, 4, 3, 2, 1], 40), ("large_straight", [2, 3, 4, 5, 6], 40), ("large_straight", [1, 2, 3, 4, 6], 0),
    ("fuenfling", [4, 4, 4, 4, 4], 50), ("fuenfling", [4, 4, 4, 4, 3], 0),
    ("chance", [1, 2, 3, 4, 6], 16),
])
def test_score_every_box(cat, dice, pts):
    assert fw.score(cat, dice) == pts


def test_totals_with_bonus_and_extra():
    sheet = {"ones": 3, "twos": 6, "threes": 9, "fours": 12, "fives": 15, "sixes": 18}          # exactly 63
    assert fw.totals(sheet) == {"upper": 63, "bonus": 35, "lower": 0, "extra": 0, "total": 98}
    sheet["sixes"] = 12
    assert fw.totals(sheet)["bonus"] == 0
    assert fw.totals({**sheet, "chance": 20, "fuenfling": 50}, 100)["total"] == 57 + 70 + 100
    assert fw.CATS == fw.UPPER + fw.LOWER and fw.ROUNDS == 13
    with pytest.raises(CommunityError):
        fw.score("nope", [1, 1, 1, 1, 1])


def test_extra_fuenfling_only_with_50_in_the_box_and_the_rule():
    t, _ = table(1)
    set_dice(t, "1", [6] * 5)
    assert t.choose("1", "fuenfling") == 50 and t.st["extra"]["1"] == 0                # the first one: just the box
    set_dice(t, "1", [3] * 5)
    assert t.choose("1", "threes") == 15 and t.st["extra"]["1"] == 50                  # a further one: +50
    set_dice(t, "1", [2] * 5)
    t.choose("1", "chance")
    assert t.st["extra"]["1"] == 100 and t.st["fuenflinge"]["1"] == 3
    assert t.total("1") == 50 + 15 + 10 + 100
    # without the rule, or with the Fünfling box crossed out: no extra
    t, _ = table(1, extra=False)
    set_dice(t, "1", [6] * 5)
    t.choose("1", "fuenfling")
    set_dice(t, "1", [6] * 5)
    t.choose("1", "sixes")
    assert t.st["extra"]["1"] == 0
    t, _ = table(1)
    set_dice(t, "1", [1, 2, 3, 4, 6])
    t.choose("1", "fuenfling")                                                            # crossed out: 0
    set_dice(t, "1", [5] * 5)
    t.choose("1", "fives")
    assert t.st["sheets"]["1"]["fuenfling"] == 0 and t.st["extra"]["1"] == 0


# ---------------------------------------------------------------- rolling, holding, rounds
def test_holding_and_at_most_three_rolls():
    t, _ = table(1)
    with pytest.raises(CommunityError):
        t.choose("1", "chance")                                                           # roll first
    with pytest.raises(CommunityError):
        t.hold("1", [True] * 5)
    d1 = t.roll("1", [True] * 5)                                                          # held is ignored on the first roll
    assert len(d1) == 5 and all(1 <= x <= 6 for x in d1) and t.st["rolls"]["1"] == 1
    t.hold("1", [True, False, True, False, False])
    for _ in range(2):
        d = t.roll("1")
        assert d[0] == d1[0] and d[2] == d1[2]
    with pytest.raises(CommunityError, match="No more rolls"):
        t.roll("1")
    with pytest.raises(CommunityError):
        t.hold("1", [True, True])                                                         # five dice needed
    assert set(t.options("1")) == set(fw.CATS)
    t.choose("1", "chance")
    assert t.st["round"] == 2 and t.st["rolls"]["1"] == 0 and t.st["dice"]["1"] == []
    # hold with the roll itself
    first = t.roll("1")
    again = t.roll("1", [True, True, True, True, False])
    assert again[:4] == first[:4]


def test_rounds_advance_only_when_everybody_chose():
    t, _ = table(3)
    for p in ("1", "2"):
        t.roll(p)
        t.choose(p, "chance")
    assert t.st["round"] == 1 and t.chose("1") and not t.chose("3")
    with pytest.raises(CommunityError, match="wait for the others"):
        t.roll("1")
    with pytest.raises(CommunityError, match="wait for the others"):
        t.choose("1", "ones")
    t.roll("3")
    t.choose("3", "ones")
    assert t.st["round"] == 2 and not any(t.chose(p) for p in "123")


def test_server_side_validation():
    t, _ = table(2)
    t.roll("1")
    with pytest.raises(CommunityError, match="Unknown box"):
        t.choose("1", "yacht")
    with pytest.raises(CommunityError, match="not at this table"):
        t.roll("9")
    t.choose("1", "sixes")
    t.roll("2")
    t.choose("2", "sixes")
    t.roll("1")
    with pytest.raises(CommunityError, match="filled already"):
        t.choose("1", "sixes")
    assert "sixes" not in t.options("1")
    # every player has their own dice: rolling never touches the others'
    t.roll("2")
    before = list(t.st["dice"]["2"])
    t.roll("1")
    t.roll("1")
    assert t.st["dice"]["2"] == before


def test_full_game_ends_with_places_ties_share():
    t, _ = table(2)
    for r in range(13):
        for p in ("1", "2"):
            t.roll(p)
            set_dice(t, p, [2, 2, 2, 3, 3])
            t.choose(p, fw.CATS[r])
    assert t.st["phase"] == "done" and t.st["complete"]
    assert t.st["places"] == {"1": 1, "2": 1} and t.total("1") == t.total("2")
    with pytest.raises(CommunityError):
        t.roll("1")


@pytest.mark.parametrize("level", ["easy", "normal", "hard"])
def test_bots_finish_full_games(level):
    for seed in range(4):
        t, _ = table(0, bots=3, seed=seed, level=level)
        t.tick()
        assert t.st["phase"] == "done", (level, seed, t.st["round"])
        for p in t.order():
            assert len(t.st["sheets"][p]) == 13
        assert sorted(t.st["places"].values())[0] == 1


def test_hard_bots_beat_easy_bots_on_average():
    def avg(level):
        tot = []
        for seed in range(8):
            t, _ = table(0, bots=2, seed=seed, level=level)
            t.tick()
            tot += [t.total(p) for p in t.order()]
        return sum(tot) / len(tot)
    assert avg("hard") > avg("easy") + 25


def test_bots_wait_for_their_reaction_time_and_humans():
    t, clock = table(1, bots=2, bot_ms=1000)
    assert not t.tick()                                                                   # not yet
    clock.t += 1.1
    assert t.tick() and all(t.st["rolls"][b] == 1 for b in ("bot1", "bot2"))
    for _ in range(10):
        clock.t += 1.1
        t.tick()
    assert t.chose("bot1") and t.chose("bot2") and t.st["round"] == 1                      # the human is still busy
    t.roll("1")
    t.choose("1", "chance")
    assert t.st["round"] == 2


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def test_solo_against_bots_no_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    st = client.post("/api/community/wuerfel/start", json={"solo": True, "bots": 2, "level": "hard", "bot_ms": 0}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 3 and st["round"] == 1 and not st["coins_on"]
    assert st["can_roll"] and st["options"] == {}
    for r in range(13):
        v = client.post("/api/community/wuerfel/roll", json={}, headers=hm).json()
        assert v["options"] and set(v["options"]) == set(v["cats"]) - set(next(p for p in v["players"] if p["id"] == str(mia))["sheet"])
        cat = max(v["options"], key=v["options"].get)
        v = client.post("/api/community/wuerfel/choose", json={"cat": cat}, headers=hm).json()
    assert v["phase"] == "done" and v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'wuerfel:%'")
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "wuerfel" and hist[0]["data"]["complete"]
    # another child does not see Mia's own table
    assert client.get("/api/community/wuerfel", headers=login(client, leo)).json() is None


def _play_round(client, heads, cats):
    v = None
    for hd, cat in zip(heads, cats):
        client.post("/api/community/wuerfel/roll", json={}, headers=hd)
        v = client.post("/api/community/wuerfel/choose", json={"cat": cat}, headers=hd).json()
    return v


def test_family_table_simultaneous_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert client.get("/api/parent/game-rewards", headers=phd).json()["wuerfel"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"wuerfel": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/wuerfel/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/wuerfel/start", json={"bots": 0, "bot_ms": 0}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"]
    assert client.post("/api/community/wuerfel/roll", json={}, headers=hm).status_code == 400          # not started
    assert client.post("/api/community/wuerfel/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/wuerfel/begin", headers=hl).status_code == 403                  # Leo does not lead
    st = client.post("/api/community/wuerfel/begin", headers=hm).json()
    assert st["phase"] == "play" and len(st["players"]) == 2
    assert client.get("/api/me", headers=hl).json()["community"]["wuerfel"]["joined"]
    # Mia rolls and chooses – the round waits for Leo
    client.post("/api/community/wuerfel/roll", json={}, headers=hm)
    v = client.post("/api/community/wuerfel/choose", json={"cat": "chance"}, headers=hm).json()
    assert v["round"] == 1 and v["waiting"] == [str(leo)] and not v["can_roll"]
    assert client.post("/api/community/wuerfel/roll", json={}, headers=hm).status_code == 400
    assert client.post("/api/community/wuerfel/choose", json={"cat": "ones"}, headers=hl).status_code == 400   # Leo: roll first
    lv = client.get("/api/community/wuerfel", headers=hl).json()
    assert lv["options"] == {} and lv["can_roll"]
    v = _play_round(client, [hl], ["chance"])
    assert v["round"] == 2 and v["waiting"] == [str(mia), str(leo)]
    # choosing a filled box is refused; the view never lets a hold change somebody else's dice
    client.post("/api/community/wuerfel/roll", json={}, headers=hm)
    assert client.post("/api/community/wuerfel/choose", json={"cat": "chance"}, headers=hm).status_code == 400
    mine = next(p for p in client.get("/api/community/wuerfel", headers=hm).json()["players"] if p["id"] == str(mia))
    assert client.post("/api/community/wuerfel/hold", json={"held": [True] * 5}, headers=hl).status_code == 400   # Leo has not rolled
    assert next(p for p in client.get("/api/community/wuerfel", headers=hm).json()["players"] if p["id"] == str(mia))["dice"] == mine["dice"]
    client.post("/api/community/wuerfel/roll", json={}, headers=hm)
    client.post("/api/community/wuerfel/roll", json={}, headers=hm)
    assert client.post("/api/community/wuerfel/roll", json={}, headers=hm).status_code == 400          # no 4th roll
    client.post("/api/community/wuerfel/choose", json={"cat": "ones"}, headers=hm)
    _play_round(client, [hl], ["ones"])
    # the remaining rounds: Mia wins (fixed dice), then the coins are paid once
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='wuerfel' AND status!='done'")
    gid = row["id"]
    for cat in fw.CATS[1:]:
        if cat in ("chance",):
            continue
        for pid, hd in ((str(mia), hm), (str(leo), hl)):
            client.post("/api/community/wuerfel/roll", json={}, headers=hd)
            row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
            s = json.loads(row["state"])
            s["dice"][pid] = [6, 6, 6, 6, 6] if pid == str(mia) else [1, 1, 2, 2, 4]
            fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), gid)
            v = client.post("/api/community/wuerfel/choose", json={"cat": cat}, headers=hd).json()
    assert v["phase"] == "done" and v["complete"]
    coins = {p["id"]: (p["place"], p["coins"]) for p in v["players"]}
    assert coins[str(mia)] == (1, 8) and coins[str(leo)] == (2, 4)
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.wuerfel._save(row, json.loads(row["state"]))                                                 # paid once
    client.get("/api/community/wuerfel", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"wuerfel:{gid}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"wuerfel:{gid}:{mia}")["reason"] == "Five Dice – place 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "wuerfel" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["coins"] == 8
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='__family__'") in (0, 1)


def test_coins_rules(fq):
    st = {"solo": False, "phase": "done", "complete": True, "places": {"1": 1, "2": 2, "3": 3, "bot1": 1},
          "players": [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "bot1", "bot": True}]}
    assert fq.wuerfel.coins_for(st) == {"1": 10, "2": 5, "3": 2}
    assert fq.wuerfel.coins_for({**st, "complete": False}) == {}                                    # ended early
    assert fq.wuerfel.coins_for({**st, "solo": True}) == {}
    assert fq.wuerfel.coins_for({**st, "players": [{"id": "1"}, {"id": "2", "guest": True}, {"id": "bot1", "bot": True}]}) == {}


def test_ended_early_counts_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/wuerfel/start", json={"bots": 1, "bot_ms": 0, "level": "easy"}, headers=hm)
    client.post("/api/community/wuerfel/join", headers=hl)
    st = client.post("/api/community/wuerfel/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"]
    _play_round(client, [hm, hl], ["chance", "chance"])
    assert client.post("/api/community/wuerfel/end", headers=hl).status_code == 403
    v = client.post("/api/community/wuerfel/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'wuerfel:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='wuerfel'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.wuerfel.clean_rules("wuerfel", {"bots": 9, "level": "x", "bot_ms": 99999, "extra": 0}) == \
        {"bots": 5, "level": "normal", "bot_ms": 5000, "extra": False}
    fq.wuerfel.start("wuerfel", kid, {"bots": 0, "level": "hard", "extra": False}, solo=True)
    assert fq.wuerfel.default_rules()["level"] == "hard" and fq.wuerfel.default_rules()["extra"] is False
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='wuerfel'")["state"])
    assert len(st["players"]) == 2 and st["players"][1]["level"] == "hard"                          # alone: at least one bot


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    client.post("/api/community/wuerfel/start", json={"bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "wuerfel"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Five Dice"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end"):
        assert client.post("/api/community/wuerfel/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.get("/api/community/wuerfel/rules", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/wuerfel/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    v = client.post("/api/community/wuerfel/roll", json={}, headers=hg).json()
    assert next(p for p in v["players"] if p["guest"])["rolls"] == 1
    for p in ("", "/join", "/roll", "/hold", "/choose"):
        assert netfilter.is_guest_path("/api/community/wuerfel" + p), p
    for p in ("/start", "/begin", "/end", "/rules"):
        assert not netfilter.is_guest_path("/api/community/wuerfel" + p), p
    assert fq.guests


def test_switched_off_blocks_it(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "wuerfel" in client.get("/api/me", headers=hm).json()["games_list"]
    assert client.put("/api/parent/games", json={"access": {"wuerfel": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/wuerfel", headers=hm).status_code == 403
    assert client.post("/api/community/wuerfel/start", json={"solo": True}, headers=hm).status_code == 403
    assert client.get("/api/community/wuerfel", headers=phd).status_code == 200
    me = client.get("/api/me", headers=hm).json()
    assert "wuerfel" not in me["games_list"] and me["community"]["wuerfel"] is None


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/wuerfel/start", json={"solo": True, "bots": 2, "bot_ms": 5000}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "wuerfel")
    assert g["title"] == "Five Dice" and g["icon"] == "🎲" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "wuerfel" for x in r["running"])
    v = client.get("/api/community/wuerfel", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]
