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


def test_api_solo_and_family(client):
    from test_api import setup_family
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
    other = hm if me is hl else hl
    assert client.post("/api/community/cards/karussell/play", json={"card": "violet:1"}, headers=other).status_code == 400


@pytest.mark.parametrize("n", [5, 6, 8])
def test_many_players_still_get_a_pile(n):
    """Review: 36 Swiss cards, up to 8 players × 7 cards – fewer cards each, never a crash or an endless loop."""
    for seed in range(12):
        r = {**cg.GAMES["tschau"]["defaults"], "hand": 7}
        st = {"kind": "tschau", "rules": r, "players": [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)], "phase": "lobby"}
        t = cg.Shed(st, random.Random(seed), now=Clock())
        t.deal()
        assert len(t.st["deck"]) >= 7 and total(t) == 36
