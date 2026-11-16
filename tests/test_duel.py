"""Tic-Tac-Toe on two devices."""
from test_api import setup_family


def test_duel_flow(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    opp = client.get("/api/community/duel/opponents", headers=hm).json()
    assert {o["name"] for o in opp} == {"Leo", "Papa"}
    st = client.post("/api/community/duel", json={"opponent": leo}, headers=hm).json()
    assert st["status"] == "invite" and st["me"] == "X"
    assert client.get("/api/me", headers=hl).json()["community"]["duel"]["from"] == "Mia"
    assert client.post("/api/community/duel/move", json={"cell": 0}, headers=hm).status_code == 400   # not accepted yet
    assert client.post("/api/community/duel/accept", headers=hl).json()["status"] == "play"
    assert client.post("/api/community/duel/move", json={"cell": 4}, headers=hl).status_code == 400   # X starts
    for pid_h, cell in [(hm, 0), (hl, 3), (hm, 1), (hl, 4)]:
        assert client.post("/api/community/duel/move", json={"cell": cell}, headers=pid_h).status_code == 200
    assert client.post("/api/community/duel/move", json={"cell": 4}, headers=hm).status_code == 400   # taken
    st = client.post("/api/community/duel/move", json={"cell": 2}, headers=hm).json()
    assert st["status"] == "done" and st["result"] == "X" and st["line"] == [0, 1, 2] and st["score"]["X"] == 1
    st = client.post("/api/community/duel/again", headers=hl).json()
    assert st["status"] == "play" and st["turn"] == "O" and st["board"] == [None] * 9
    client.post("/api/community/duel/leave", headers=hl)
    assert client.get("/api/community/duel", headers=hl).json() is None
    assert client.get("/api/community/duel", headers=hm).json()["status"] == "gone"
    client.post("/api/community/duel/leave", headers=hm)
    assert client.get("/api/community/duel", headers=hm).json() is None
    # declined invitation
    client.post("/api/community/duel", json={"opponent": leo}, headers=hm)
    client.post("/api/community/duel/decline", headers=hl)
    assert client.get("/api/community/duel", headers=hm).json()["status"] == "declined"
    assert client.get("/api/me", headers=hl).json()["community"]["duel"] is None
