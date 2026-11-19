from test_api import setup_family


def test_guests_join_a_game(client, fq=None):
    ph, mia, _ = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    assert client.post("/api/community/guests", json={"game": "bingo"}, headers=ph).status_code == 400   # no game running
    client.post("/api/community/bingo/start", json={}, headers=h)
    inv = client.post("/api/community/guests", json={"game": "bingo"}, headers=h).json()["invite"]
    assert client.get(f"/api/community/guest/info?code={inv['code']}").json()["game"] == "bingo"
    assert client.get("/api/community/guest/info?code=nope").status_code == 404
    r = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    g = {"X-FQ-Token": r["token"]}
    st = client.get("/api/community/bingo", headers=g).json()
    assert st["card"] and "Oma" in [p["name"] for p in st["players"]]
    assert client.post("/api/community/guest/join", json={"code": inv["code"], "name": "oma"}).json()["profile"]["name"] == "oma 2"
    # a guest is no family member: not on the login screen, no app, cannot start or lead
    assert "Oma" not in [p["name"] for p in client.get("/api/profiles").json()]
    assert client.get("/api/me", headers=g).status_code == 401
    assert client.post("/api/community/bingo/begin", headers=g).status_code in (401, 403)
    assert client.get("/api/community/quizzes", headers=g).status_code == 401
    # parents can switch guests off
    client.put("/api/parent/settings", json={"games_guests": False}, headers=ph)
    assert client.get(f"/api/community/guest/info?code={inv['code']}").status_code == 404


def test_guests_are_cleaned_up(fq):
    import json
    pid = fq.db.x("INSERT INTO profile(name, settings, archived, created_at) VALUES('Gast', ?, 2, datetime('now','-13 hours'))", json.dumps({"guest": True}))
    fq.db.x("INSERT INTO history(profile_id, kind) VALUES(?, 'quiz')", pid)
    assert fq.guests.cleanup() == 1
    assert not fq.db.q1("SELECT 1 FROM history WHERE profile_id=?", pid)


def test_guest_network(client):
    from fastapi.testclient import TestClient
    ph, mia, _ = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    # «testclient» is the address of the test client – make a guest network that contains a real address instead
    guest = TestClient(client.app, client=("192.168.50.20", 4000))
    # saving a guest network that contains my own device is refused (I would be a guest then)
    me = TestClient(client.app, client=("192.168.50.5", 4000))
    assert me.put("/api/parent/settings", json={"guest_networks": ["192.168.50.0/24"]}, headers=ph).status_code == 400
    assert client.put("/api/parent/settings", json={"guest_networks": ["192.168.50.0-192.168.50.255"]}, headers=ph).status_code == 200
    client.post("/api/community/bingo/start", json={}, headers=h)
    code = client.post("/api/community/guests", json={"game": "bingo"}, headers=h).json()["invite"]["code"]
    # from the guest network: guest page, scripts, join and play – nothing else
    assert guest.get("/guest").status_code == 200 and guest.get("/shared/ui.js").status_code == 200
    assert guest.get("/").status_code == 403 and guest.get("/parents").status_code == 403
    assert guest.get("/gast?c=" + code).status_code == 200                          # the old address of printed QR codes
    assert guest.get("/api/profiles").status_code == 403
    assert guest.post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 403
    g = {"X-FQ-Token": guest.post("/api/community/guest/join", json={"code": code, "name": "Gotti"}).json()["token"]}
    assert guest.get("/api/community/bingo", headers=g).json()["card"]
    assert guest.get("/api/community/bingo", headers=h).status_code == 403          # a family token does not work there
    assert guest.post("/api/community/bingo/begin", headers=g).status_code == 403


def test_every_family_player_may_invite(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.post("/api/community/guests", json={"game": "bingo", "on": True}, headers=hl).status_code == 400   # nothing running
    client.post("/api/community/bingo/start", json={}, headers=hm)
    r = client.post("/api/community/guests", json={"game": "bingo", "on": True}, headers=hl)       # Leo does not lead – may invite
    assert r.status_code == 200 and r.json()["invite"]["code"]
    assert client.post("/api/community/guests", json={"game": "bingo", "on": False}, headers=hl).status_code == 403   # closing: the leader
