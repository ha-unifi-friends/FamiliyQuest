"""Own flash card decks: own cards, cards from packs with one click, Leitner repeating, only one's own decks."""
from datetime import date, timedelta

from test_api import setup_family

FR = "franz-5kl-la-maison"


def _login(client, pid, pin=None):
    body = {"profile_id": pid} | ({"pin": pin} if pin else {})
    return {"X-FQ-Token": client.post("/api/login", json=body).json()["token"]}


def test_own_deck_and_repeating(client):
    ph, mia, leo = setup_family(client)
    hm, hl = _login(client, mia, "1111"), _login(client, leo)
    assert client.post("/api/me/decks", json={"name": " "}, headers=hm).status_code == 400
    did = client.post("/api/me/decks", json={"name": "Französisch Wörtli", "icon": "🇫🇷"}, headers=hm).json()["id"]
    assert client.post(f"/api/me/decks/{did}/cards", json={"front": "Haus", "back": ""}, headers=hm).status_code == 400
    c1 = client.post(f"/api/me/decks/{did}/cards", json={"front": "Haus", "back": "la maison"}, headers=hm).json()["id"]
    c2 = client.post(f"/api/me/decks/{did}/cards", json={"front": "Tisch", "back": "la table"}, headers=hm).json()["id"]
    d = client.get("/api/me/decks", headers=hm).json()
    assert d["decks"][0]["count"] == 2 and d["decks"][0]["new"] == 2 and d["due"] == 0
    # Leo neither sees nor touches Mia's deck
    assert client.get("/api/me/decks", headers=hl).json()["decks"] == []
    assert client.get(f"/api/me/decks/{did}", headers=hl).status_code == 400
    assert client.post(f"/api/me/decks/cards/{c1}/grade", json={"result": "correct"}, headers=hl).status_code == 400
    study = client.get(f"/api/me/decks/{did}/study", headers=hm).json()["cards"]
    assert {c["id"] for c in study} == {c1, c2}
    r = client.post(f"/api/me/decks/cards/{c1}/grade", json={"result": "correct"}, headers=hm).json()
    assert r["box"] == 1 and r["status"] == "learning"
    client.post(f"/api/me/decks/cards/{c2}/grade", json={"result": "wrong"}, headers=hm)
    cards = {c["id"]: c for c in client.get(f"/api/me/decks/{did}", headers=hm).json()["cards"]}
    assert cards[c2]["status"] == "due" and cards[c1]["status"] == "learning"
    # only the due one comes again today
    assert [c["id"] for c in client.get(f"/api/me/decks/{did}/study", headers=hm).json()["cards"]] == [c2]
    assert len(client.get(f"/api/me/decks/{did}/study?mode=all", headers=hm).json()["cards"]) == 2
    # a card in box 3 that is not due counts as known
    fq = client.app.state.fq
    fq.db.x("UPDATE deck_card SET box=3, due=? WHERE id=?", (date.today() + timedelta(days=3)).isoformat(), c1)
    deck = client.get("/api/me/decks", headers=hm).json()["decks"][0]
    assert (deck["known"], deck["due"]) == (1, 1)
    client.put(f"/api/me/decks/cards/{c1}", json={"front": "das Haus", "back": "la maison"}, headers=hm)
    client.delete(f"/api/me/decks/cards/{c2}", headers=hm)
    assert [c["front"] for c in client.get(f"/api/me/decks/{did}", headers=hm).json()["cards"]] == ["das Haus"]
    client.delete(f"/api/me/decks/{did}", headers=hm)
    assert client.get("/api/me/decks", headers=hm).json()["decks"] == []


def test_cards_from_packs(client):
    ph, mia, leo = setup_family(client)
    hm = _login(client, mia, "1111")
    client.post(f"/api/me/courses/{FR}", json={"on": True}, headers=hm)
    s = client.post("/api/me/session", json={"mode": "path", "pack": FR, "unit": "zimmer"}, headers=hm).json()
    assert client.post("/api/me/decks/from-session", json={"session": s["id"], "step": 0}, headers=hm).status_code == 400  # answer first
    client.post(f"/api/me/session/{s['id']}/answer", json={"step": 0, "answer": "x"}, headers=hm)
    r = client.post("/api/me/decks/from-session", json={"session": s["id"], "step": 0}, headers=hm).json()
    assert r["added"] >= 1 and r["deck"]["name"] == "French"
    again = client.post("/api/me/decks/from-session", json={"session": s["id"], "step": 0}, headers=hm).json()
    assert again["added"] == 0 and again["deck"]["id"] == r["deck"]["id"]            # no doubles, same deck
    u = client.post("/api/me/decks/from-unit", json={"pack": FR, "unit": "moebel"}, headers=hm).json()
    assert u["added"] > 3 and u["deck"]["id"] == r["deck"]["id"]
    cards = client.get(f"/api/me/decks/{r['deck']['id']}", headers=hm).json()["cards"]
    assert all(c["front"] or c["image"] or c["emoji"] for c in cards) and all(c["back"] for c in cards) and cards[0]["from_pack"]
    # another person's session cannot be used
    hl = _login(client, leo)
    assert client.post("/api/me/decks/from-session", json={"session": s["id"], "step": 0}, headers=hl).status_code == 400
