"""Parent area: list the running games and end one or all."""
from test_api import setup_family


def kid(client, pid):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, "pin": "1111"}).json()["token"]}


def test_parents_end_one_or_all_running_games(client):
    ph, mia, leo = setup_family(client)
    hm = kid(client, mia)
    assert client.get("/api/parent/games/running", headers=ph).json() == []
    assert client.post("/api/community/domino/start", json={"solo": True}, headers=hm).status_code == 200
    assert client.post("/api/community/paarjagd/start", json={}, headers=hm).status_code == 200
    assert client.post("/api/community/poker/start", json={"solo": True, "bots": 2}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    assert {g["game"] for g in games} == {"domino", "paarjagd", "poker"}
    pj = next(g for g in games if g["game"] == "paarjagd")
    assert pj["solo"] is False and pj["host"] == "Mia"
    r = client.post("/api/parent/games/end", json={"key": pj["key"]}, headers=ph).json()
    assert {g["game"] for g in r["running"]} == {"domino", "poker"}
    assert client.get("/api/community/paarjagd", headers=hm).json() in (None, {}) or client.get("/api/community/paarjagd", headers=hm).json()["status"] == "done"
    r = client.post("/api/parent/games/end", json={"all": True}, headers=ph).json()
    assert r["ended"] == 2 and r["running"] == []
    assert client.post("/api/parent/games/end", json={"key": "nope"}, headers=ph).status_code == 400
    assert client.get("/api/parent/games/running", headers=hm).status_code == 401          # parents only
