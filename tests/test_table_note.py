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


def test_only_tables_that_can_still_be_joined(client):
    """A card-game table that already started is not announced any more (its join refuses) – poker only while a seat
    is free (later players sit down for the next hand)."""
    import json
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    ben = client.post("/api/parent/profiles", json={"name": "Ben"}, headers=ph).json()["id"]
    hb = {"X-FQ-Token": client.post("/api/login", json={"profile_id": ben}).json()["token"]}
    client.post("/api/community/cards/tschau/start", json={"bots": 0}, headers=hm)
    client.post("/api/community/cards/tschau/join", headers=hl)
    assert [t["game"] for t in client.get("/api/community/tables", headers=hb).json()] == ["tschau"]
    client.post("/api/community/cards/tschau/begin", headers=hm)
    assert client.post("/api/community/cards/tschau/join", headers=hb).status_code == 400                    # too late
    assert client.get("/api/community/tables", headers=hb).json() == []
    assert client.post("/api/community/poker/start", json={"max_players": 2}, headers=hm).status_code == 200
    assert [t["game"] for t in client.get("/api/community/tables", headers=hb).json()] == ["poker"]
    client.post("/api/community/poker/join", headers=hl)                                                     # full now
    st = json.loads(fq.db.val("SELECT state FROM poker_game WHERE status!='done'"))
    assert len(st["players"]) == 2 and client.get("/api/community/tables", headers=hb).json() == []


def test_join_path_of_the_note(client):
    """«Join» in the note seats the child at once through the path the note carries – one exists for every game."""
    from familyquest import running
    ph, mia, leo = setup_family(client)
    hb = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    for game in running.ROUTES:                     # no table open: the endpoint exists and refuses (not 404/405)
        assert client.post("/api/" + running.join_path(game), headers=hb).status_code not in (404, 405), game
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    client.post("/api/community/werwolf/start", json={}, headers=hm)
    t = client.get("/api/community/tables", headers=hl).json()
    assert t and t[0]["join"] == "community/werwolf/join"
    assert client.post("/api/" + t[0]["join"], headers=hl).status_code == 200
    assert client.get("/api/community/tables", headers=hl).json() == []
