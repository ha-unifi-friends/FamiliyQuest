import random

import pytest

from familyquest import cardgames as cg
from familyquest.community import CommunityError


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def table(kind="tschau", n=3, bots=0, **rules):
    r = {**cg.GAMES[kind]["defaults"], **rules}
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": "normal"} for i in range(1, bots + 1)]
    st = {"kind": kind, "rules": r, "players": players, "phase": "lobby"}
    clock = Clock()
    t = cg.Shed(st, random.Random(3), now=clock)
    t.deal()
    return t, clock


def total(t):
    return len(t.st["deck"]) + len(t.st["discard"]) + sum(len(h) for h in t.st["hands"].values())


def test_decks_and_effects():
    assert len(cg.tschau_deck({"deck": "swiss"})) == 36 and len(cg.tschau_deck({"deck": "french"})) == 36
    assert len(cg.karussell_deck()) == 4 * (1 + 18 + 6) + 8
    r = cg.GAMES["tschau"]["defaults"]
    assert cg.effect("tschau", "rosen:7", r) == "draw2" and cg.effect("tschau", "rosen:U", r) == "wish"
    assert cg.effect("tschau", "rosen:10", r) is None and cg.effect("tschau", "rosen:10", {**r, "reverse": True}) == "reverse"
    assert cg.points("tschau", "rosen:U", r) == 20 and cg.points("tschau", "rosen:9", r) == 9 and cg.points("karussell", "wild:draw4", {}) == 50


def test_fit_wish_and_draw2_stack():
    t, _ = table(n=2)
    st = t.st
    st["discard"] = ["rosen:9"]
    st["hands"]["1"] = ["rosen:6", "eicheln:9", "schellen:K", "eicheln:U", "rosen:7"]
    st["turn"] = "1"
    assert sorted(t.playable("1")) == sorted(["rosen:6", "eicheln:9", "eicheln:U", "rosen:7"])
    with pytest.raises(CommunityError):
        t.play("1", "eicheln:U")                                   # a wish needs a suit
    t.play("1", "eicheln:U", wish="schellen")
    assert st["wish"] == "schellen" and st["turn"] == "2"
    st["hands"]["2"] = ["schellen:7", "rosen:U", "eicheln:6"]
    assert sorted(t.playable("2")) == ["schellen:7"]               # no wish on wish
    t.play("2", "schellen:7")
    assert st["pending"] == 2 and st["turn"] == "1"
    assert t.playable("1") == ["rosen:7"]                          # stacking: only another 7
    t.play("1", "rosen:7")
    assert st["pending"] == 4
    st["hands"]["2"] = ["eicheln:6", "rosen:K"]
    before = len(st["hands"]["2"])
    t.draw("2")
    assert len(st["hands"]["2"]) == before + 4 and st["pending"] == 0 and st["turn"] == "1"


def test_calls_and_penalty_and_round_end():
    t, _ = table(n=2, rounds=1)
    st = t.st
    st["discard"] = ["rosen:9"]
    st["hands"]["1"] = ["rosen:6", "rosen:8"]
    st["turn"] = "1"
    t.play("1", "rosen:6")                                         # forgot «Tschau» → 2 penalty cards
    assert len(st["hands"]["1"]) == 3 and st["last"]["penalty"] == 2
    st["hands"]["1"] = ["rosen:6"]
    st["turn"], st["discard"] = "1", ["rosen:9"]
    t.play("1", "rosen:6", say=True)                               # «Sepp»: done
    assert st["phase"] == "done" and st["ranking"][0] == "1"


def test_bots_play_a_whole_game():
    for kind in ("tschau", "karussell"):
        t, clock = table(kind, n=0, bots=3, rounds=2)
        n = total(t)
        for _ in range(3000):
            if t.st["phase"] == "done":
                break
            clock.t += 2
            t.tick()
            assert total(t) == n or t.st["phase"] in ("between", "done")
        assert t.st["phase"] == "done" and len(t.st["ranking"]) == 3, kind


def test_api_solo_and_family(client, monkeypatch):
    from test_api import setup_family
    monkeypatch.setattr(cg, "bot_delay", lambda rules, default: 3600)   # the bots wait: the turn cannot move on by itself during the test
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    # alone against two bots: dealt at once, private
    st = client.post("/api/community/cards/tschau/start", json={"solo": True, "bots": 2, "deck": "french"}, headers=hm).json()
    assert st["phase"] == "play" and st["solo"] and len(st["hand"]) == 7 and [p["bot"] for p in st["players"]] == [False, True, True]
    assert client.get("/api/community/cards/tschau", headers=hl).json() is None             # Leo does not see Mia's private table
    # the family table: Leo opens, Mia joins (her own solo game stays apart)
    st = client.post("/api/community/cards/karussell/start", json={"bots": 1}, headers=hl).json()
    assert st["phase"] == "lobby"
    client.post("/api/community/cards/karussell/join", headers=hm)
    st = client.post("/api/community/cards/karussell/begin", headers=hl).json()
    assert st["phase"] == "play" and len(st["players"]) == 3
    me = hl if st["turn"] == str(leo) else hm
    view = client.get("/api/community/cards/karussell", headers=me).json()
    if view["playable"]:
        c = view["playable"][0]
        body = {"card": c, "wish": "violet" if c.startswith("wild") else None}
        assert client.post("/api/community/cards/karussell/play", json=body, headers=me).status_code == 200
    else:
        assert client.post("/api/community/cards/karussell/draw", headers=me).status_code == 200
    # a person who is not on turn cannot play – not even a card of their own hand that fits. (Before: Mia tried
    # «violet:1» – but after Leo's card it is usually Mia's turn, and with violet:1 in her hand on a violet card the
    # play was valid: a rare random failure.)
    turn = client.get("/api/community/cards/karussell", headers=hl).json()["turn"]
    other = hm if turn == str(leo) else hl
    hand = client.get("/api/community/cards/karussell", headers=other).json()["hand"]
    r = client.post("/api/community/cards/karussell/play", json={"card": hand[0]}, headers=other)
    assert r.status_code == 400 and r.json()["detail"] == "It is not your turn"


@pytest.mark.parametrize("n", [5, 6, 8])
def test_many_players_still_get_a_pile(n):
    """Review: 36 Swiss cards, up to 8 players × 7 cards – fewer cards each, never a crash or an endless loop."""
    for seed in range(12):
        r = {**cg.GAMES["tschau"]["defaults"], "hand": 7}
        st = {"kind": "tschau", "rules": r, "players": [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)], "phase": "lobby"}
        t = cg.Shed(st, random.Random(seed), now=Clock())
        t.deal()
        assert len(t.st["deck"]) >= 7 and total(t) == 36


def test_bot_reaction_time():
    assert cg.bot_delay({}, 1.4) == 1.4 and cg.bot_delay({"bot_ms": 0}, 1.4) == 0 and cg.bot_delay({"bot_ms": 99999}, 1.4) == 5
    assert cg.CardGames.clean_rules(None, "tschau", {"bot_ms": -5})["bot_ms"] == 0
    for ms, moves_at_once in ((0, True), (3000, False)):
        t, clock = table("tschau", n=0, bots=3, bot_ms=ms)
        before = total(t) and t.st["turn"]
        moved = t.tick()                                          # no time passed since the deal
        assert moved is moves_at_once, ms
        clock.t += 3
        assert t.tick()


def test_number_one_hat_for_the_winner_of_a_family_game(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    def hat(pid):
        return (client.get("/api/parent/profiles", headers=ph).json() and
                next(p for p in fq.db.q("SELECT * FROM profile WHERE id=?", pid)) and
                fq.avatar_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid), {"items": {}})["items"].get("hat"))
    fq.community.add_history(0, "__family__", {"people": [mia, leo], "winners": [mia]})
    assert hat(mia) == "champion" and hat(leo) is None
    fq.community.add_history(0, "__family__", {"people": [mia, leo], "winners": []})          # no winner: no change
    assert hat(mia) == "champion"
    fq.community.add_history(0, "__family__", {"people": [mia, leo], "winners": [leo]})       # 2nd place or worse: gone
    assert hat(mia) is None and hat(leo) == "champion"
    fq.community.add_history(0, "__family__", {"people": [leo], "winners": [leo]})            # alone: not a family game
    assert hat(leo) == "champion"
    # a card game at a family table gives the hat, alone against bots does not
    st = {"kind": "tschau", "solo": True, "players": [{"id": str(mia)}, {"id": "bot1", "bot": True}], "ranking": [str(mia)]}
    fq.cards._champion(st, [str(mia)])
    assert hat(mia) is None
    st = {"kind": "tschau", "players": [{"id": str(mia)}, {"id": str(leo)}], "ranking": [str(mia), str(leo)]}
    fq.cards._champion(st, [str(mia)])
    assert hat(mia) == "champion" and hat(leo) is None
