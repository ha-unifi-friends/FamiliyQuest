"""«Somebody opened a table»: the open family tables another person may join (web/kid.js shows a note in the header)."""
from tests.test_api import setup_family


def test_open_tables_for_the_others(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.get("/api/community/tables", headers=hl).json() == []
    assert client.post("/api/community/cards/tschau/start", json={}, headers=hm).status_code == 200          # a family table
    t = client.get("/api/community/tables", headers=hl).json()
    assert len(t) == 1 and t[0]["game"] == "tschau" and t[0]["route"] == "tschau" and t[0]["host"] == "Mia"
    assert client.get("/api/community/tables", headers=hm).json() == []                                       # not for who opened it
    client.post("/api/community/cards/tschau/join", headers=hl)
    assert client.get("/api/community/tables", headers=hl).json() == []                                       # joined: no note
    # alone against bots: nobody is told; the parent area still lists everything (JSON)
    assert client.get("/api/parent/games/running", headers=ph).status_code == 200
