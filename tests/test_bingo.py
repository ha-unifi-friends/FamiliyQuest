"""Family bingo: balls come by time, players mark themselves, «Bingo!» is checked."""
from familyquest import bingo as B


def family(client):
    r = client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()
    ph = {"X-FQ-Parent": r["parent_token"]}
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=ph).json()["id"]
    leo = client.post("/api/parent/profiles", json={"name": "Leo"}, headers=ph).json()["id"]
    tok = lambda pid: {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid}).json()["token"]}
    return ph, tok(mia), tok(leo), mia


def test_card_layout():
    c = B.new_card()
    assert len(c) == 25 and c[B.FREE] == 0 and len(set(c)) == 25
    for i, n in enumerate(c):
        if i != B.FREE:
            assert (i % 5) * 15 + 1 <= n <= (i % 5) * 15 + 15          # column B 1–15, I 16–30 …
    assert len(B.LINES) == 12 and all(B.FREE in ln for ln in (B.LINES[2], B.LINES[7], B.LINES[10], B.LINES[11]))


def test_bingo_game(client, monkeypatch):
    ph, mia_h, leo_h, mia = family(client)
    st = client.post("/api/community/bingo/start", json={"interval": 8}, headers=mia_h).json()
    assert st["status"] == "lobby" and st["host"] == mia and len(st["card"]) == 25
    assert client.post("/api/community/bingo/start", json={}, headers=ph).status_code == 400        # one at a time
    assert client.get("/api/me", headers=leo_h).json()["community"]["bingo"] == {"status": "lobby", "joined": False}
    client.post("/api/community/bingo/join", headers=leo_h)
    assert client.post("/api/community/bingo/begin", headers=leo_h).status_code == 403              # Mia leads
    st = client.post("/api/community/bingo/begin", headers=mia_h).json()
    assert st["status"] == "running" and st["count"] == 1 and st["current"]
    # time runs: 10 balls later
    fq = client.app.state.fq
    g = fq.bingo._game()
    fq.db.x("UPDATE bingo_game SET started=started-80 WHERE id=?", g["id"])
    st = client.get("/api/community/bingo", headers=mia_h).json()
    assert st["count"] == 11 and len(st["recent"]) == 5
    # a false «Bingo!» blocks the button for a moment
    r = client.post("/api/community/bingo/claim", headers=leo_h).json()
    assert r["bingo"] is False and r["state"]["blocked_ms"] > 0
    assert client.post("/api/community/bingo/claim", headers=leo_h).status_code == 400
    # Mia gets her first row drawn and marks it herself
    card = st["card"]
    drawn = set(g["draw_order"][:11])
    row = [0, 1, 2, 3, 4]
    order = [card[i] for i in row] + [n for n in g["draw_order"] if n not in {card[i] for i in row}]
    fq.db.x("UPDATE bingo_game SET draw_order=? WHERE id=?", __import__("json").dumps(order), g["id"])
    for i in row[:4]:
        client.post("/api/community/bingo/mark", json={"cell": i}, headers=mia_h)
    assert client.post("/api/community/bingo/claim", headers=mia_h).json()["bingo"] is False       # one field not marked yet
    fq.db.x("UPDATE bingo_card SET blocked_until=0")
    assert 4 in client.post("/api/community/bingo/mark", json={"cell": 4}, headers=mia_h).json()["marks"]
    r = client.post("/api/community/bingo/claim", headers=mia_h).json()
    assert r["bingo"] and r["line"] == row and r["state"]["winner"]["name"] == "Mia"
    hist = client.get("/api/community/history", headers=leo_h).json()[0]
    assert hist["kind"] == "bingo" and hist["data"]["winner"] == "Mia" and not hist["data"]["won"]
    assert client.get("/api/me", headers=mia_h).json()["community"]["bingo"] is None


def test_rules_are_remembered(client):
    ph, mia_h, leo_h, mia = family(client)
    assert client.get("/api/community/bingo/rules", headers=mia_h).json() == {"interval": 8, "win": "line"}
    st = client.post("/api/community/bingo/start", json={"interval": 12, "win": "full"}, headers=mia_h).json()
    assert st["rules"] == {"interval": 12, "win": "full"} and st["interval"] == 12
    client.post("/api/community/bingo/end", headers=mia_h)
    # the next game starts with the rules used last
    assert client.get("/api/community/bingo/rules", headers=leo_h).json() == {"interval": 12, "win": "full"}
    st = client.post("/api/community/bingo/start", json={}, headers=leo_h).json()
    assert st["rules"]["win"] == "full"
    # with «full card» one line is not enough
    fq = client.app.state.fq
    client.post("/api/community/bingo/begin", headers=leo_h)
    g = fq.bingo._game()
    card = st["card"]
    order = [card[i] for i in range(5)] + [n for n in g["draw_order"] if n not in card[:5]]
    fq.db.x("UPDATE bingo_game SET draw_order=?, started=started-100 WHERE id=?", __import__("json").dumps(order), g["id"])
    for i in range(5):
        client.post("/api/community/bingo/mark", json={"cell": i}, headers=leo_h)
    assert client.post("/api/community/bingo/claim", headers=leo_h).json()["bingo"] is False
