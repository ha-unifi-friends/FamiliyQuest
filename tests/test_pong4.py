"""Ping-Pong doubles on four devices (familyquest/pong4.py) – 2 against 2, bots fill empty seats."""
import pytest

from test_api import setup_family

from familyquest.pong4 import Doubles, DoublesError


def _family(client):
    ph, mia, leo = setup_family(client)
    ben = client.post("/api/parent/profiles", json={"name": "Ben"}, headers=ph).json()["id"]
    tok = lambda pid, pin=None: {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}
    return ph, (mia, tok(mia, "1111")), (leo, tok(leo)), (ben, tok(ben))


def test_doubles_with_four_people(client):
    ph, (mia, hm), (leo, hl), (ben, hb) = _family(client)
    papa = next(p["id"] for p in client.get("/api/profiles").json() if p["name"] == "Papa")
    players = client.get("/api/community/pong4/players", headers=hm).json()
    assert {p["name"] for p in players} == {"Leo", "Ben", "Papa"}
    st = client.post("/api/community/pong4", json={"seats": {"A2": {"pid": leo}, "B1": {"pid": ben}, "B2": {"pid": papa}}, "to": 5},
                     headers=hm).json()
    assert st["status"] == "lobby" and st["me"] == "A1" and st["host"] and st["to"] == 5
    assert st["pong"]["pads"] == {"A1": 0.5, "A2": 0.5, "B1": 0.5, "B2": 0.5} and st["front"] == 0.55
    inv = client.get("/api/me", headers=hb).json()["community"]["pong4"]
    assert inv["from"] == "Mia" and inv["seat"] == "B1" and inv["team"] == "B"
    assert client.get("/api/community/duel/opponents?kind=pong", headers=hb).json()[0]["busy"]  # nobody free for a duel
    assert client.post("/api/community/pong4/start", headers=hm).status_code == 400           # nobody has answered yet
    assert client.post("/api/community/pong4/accept", headers=hl).json()["team"] == "A"
    assert client.post("/api/community/pong4/accept", headers=hb).json()["me"] == "B1"
    hp = {"X-FQ-Parent": ph["X-FQ-Parent"]}
    client.post("/api/community/pong4/decline", headers=hp)
    st = client.get("/api/community/pong4", headers=hm).json()
    assert st["seats"]["B2"]["state"] == "declined"
    assert client.get("/api/community/pong4", headers=hp).json() is None
    assert client.post("/api/community/pong4/start", headers=hb).status_code == 400            # only the host starts
    assert client.post("/api/community/pong4/seat", json={"seat": "B2", "bot": "hard"}, headers=hb).status_code == 400
    st = client.post("/api/community/pong4/seat", json={"seat": "B2", "bot": "hard"}, headers=hm).json()
    assert st["seats"]["B2"] == {"name": None, "bot": "hard", "state": "bot", "pid": None, "left": None, "inv": None}
    st = client.post("/api/community/pong4/start", headers=hm).json()
    assert st["status"] == "play"

    # only the own paddle: Leo moves A2, Ben B1 – ball, points, bot paddles only from the host
    st = client.post("/api/community/pong4/sync", json={"pad": 0.2, "bots": {"B2": 0.9, "A2": 0.0}, "ball": {"x": 0.5, "y": 0.8, "vx": 0, "vy": -0.4},
                                                        "points": {"A": 1, "B": 0}}, headers=hm).json()
    assert st["pong"]["pads"]["A1"] == 0.2 and st["pong"]["pads"]["B2"] == 0.9 and st["pong"]["pads"]["A2"] == 0.5
    assert st["pong"]["ball"]["vy"] == -0.4 and st["pong"]["points"] == {"A": 1, "B": 0}
    st = client.post("/api/community/pong4/sync", json={"pad": 0.7}, headers=hl).json()
    assert st["pong"]["pads"]["A2"] == 0.7 and st["pong"]["pads"]["A1"] == 0.2
    st = client.post("/api/community/pong4/sync", json={"pad": 3, "bots": {"B2": 0.1}, "ball": {"x": 0, "y": 0, "vx": 0, "vy": 0},
                                                        "points": {"A": 0, "B": 9}, "over": "B"}, headers=hb).json()
    assert st["pong"]["pads"]["B1"] == 1.0 and st["pong"]["pads"]["B2"] == 0.9
    assert st["pong"]["ball"]["y"] == 0.8 and st["pong"]["points"] == {"A": 1, "B": 0} and st["status"] == "play"
    # team scoring: the host ends the match for a team
    st = client.post("/api/community/pong4/sync", json={"pad": 0.5, "points": {"A": 5, "B": 3}, "over": "A"}, headers=hm).json()
    assert st["status"] == "done" and st["result"] == "A" and st["score"] == {"A": 1, "B": 0}
    assert client.get("/api/community/pong4", headers=hl).json()["result"] == "A"
    st = client.post("/api/community/pong4/again", headers=hb).json()
    assert st["status"] == "play" and st["pong"]["points"] == {"A": 0, "B": 0} and st["score"] == {"A": 1, "B": 0}

    # Ben leaves the running match: a normal bot plays on for him
    client.post("/api/community/pong4/leave", headers=hb)
    assert client.get("/api/community/pong4", headers=hb).json() is None
    st = client.get("/api/community/pong4", headers=hm).json()
    assert st["seats"]["B1"]["bot"] == "normal" and st["seats"]["B1"]["left"] == "Ben" and st["status"] == "play"
    # the host leaves: the match is over for everybody
    client.post("/api/community/pong4/leave", headers=hm)
    assert client.get("/api/community/pong4", headers=hm).json() is None
    assert client.get("/api/community/pong4", headers=hl).json()["status"] == "gone"
    client.post("/api/community/pong4/leave", headers=hl)
    assert client.get("/api/community/pong4", headers=hl).json() is None


def test_doubles_against_bots_and_permissions(client):
    ph, (mia, hm), (leo, hl), (ben, hb) = _family(client)
    st = client.post("/api/community/pong4", json={"seats": {"A2": {"bot": "easy"}, "B1": {"bot": "normal"}, "B2": {"bot": "hard"}}},
                     headers=hm).json()
    assert [st["seats"][s]["state"] for s in ("A1", "A2", "B1", "B2")] == ["host", "bot", "bot", "bot"] and st["to"] == 7
    assert client.post("/api/community/pong4/start", headers=hm).json()["status"] == "play"
    st = client.post("/api/community/pong4/sync", json={"pad": 0.4, "bots": {"A2": 0.1, "B1": 0.2, "B2": 0.3}}, headers=hm).json()
    assert st["pong"]["pads"] == {"A1": 0.4, "A2": 0.1, "B1": 0.2, "B2": 0.3}
    assert client.post("/api/community/pong4/sync", json={"pad": 0.4}, headers=hl).status_code == 400   # Leo has no seat
    # wrong set-ups
    bad = [{"seats": {"A2": {"bot": "easy"}, "B1": {"bot": "normal"}}},                     # a seat missing
           {"seats": {"A2": {"bot": "pro"}, "B1": {"bot": "normal"}, "B2": {"bot": "hard"}}},  # unknown bot
           {"seats": {"A2": {"pid": leo}, "B1": {"pid": leo}, "B2": {"bot": "hard"}}},         # twice the same person
           {"seats": {"A2": {"pid": leo}, "B1": {"bot": "easy"}, "B2": {"bot": "hard"}}, "to": 8}]
    for b in bad:
        assert client.post("/api/community/pong4", json=b, headers=hl).status_code == 400
    # Mia is at a table: Leo cannot invite her, nor to a duel
    r = client.post("/api/community/pong4", json={"seats": {"A2": {"pid": mia}, "B1": {"bot": "easy"}, "B2": {"bot": "hard"}}}, headers=hl)
    assert r.status_code == 400 and "Mia" in r.json()["detail"]
    assert client.post("/api/community/duel", json={"opponent": mia, "kind": "pong"}, headers=hl).status_code == 400
    # switched off: no doubles, not even as a guest player at the table
    client.post("/api/community/pong4/leave", headers=hm)
    client.put("/api/parent/settings", json={"games_access": {"pingpong": {"mode": "off", "profiles": []}}}, headers=ph)
    assert client.get("/api/community/pong4", headers=hm).status_code == 403
    assert client.get("/api/me", headers=hm).json()["community"]["pong4"] is None


def test_doubles_unit_rules():
    d = Doubles(lambda pid: {1: "A", 2: "B", 3: "C", 4: "D"}[pid])
    st = d.create(1, {"A2": {"pid": 2}, "B1": {"pid": 3}, "B2": {"bot": "easy"}}, 11)
    assert st["pong"]["to"] == 11
    with pytest.raises(DoublesError):
        d.seat(1, "A1", {"bot": "easy"})                  # the host's seat is fixed
    with pytest.raises(DoublesError):
        d.create(4, {"A2": {"pid": 2}, "B1": {"bot": "easy"}, "B2": {"bot": "easy"}})   # 2 sits at another table
    d.answer(2, True)
    d.leave(3)                                            # leaving in the lobby = no thanks
    assert d.state(1)["seats"]["B1"]["state"] == "declined" and d.state(3) is None
    d.seat(1, "B1", {"pid": 4})
    assert d.summary(4)["seat"] == "B1" and d.summary(2) is None
    d.answer(4, True)
    assert d.start(1)["status"] == "play"
    # a new table of the host ends the old one
    d.create(1, {"A2": {"bot": "easy"}, "B1": {"bot": "easy"}, "B2": {"bot": "easy"}})
    assert d.state(2)["status"] == "gone" and d.state(1)["status"] == "lobby"
    old = next(g for g in d.games.values() if g["status"] == "gone")
    old["touched"] -= 301                                 # a table left by its host is cleared after 5 minutes
    assert d.state(2) is None and not d.busy(2)
    d.leave(1)
    assert d.state(1) is None
