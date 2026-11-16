"""The children's own bots: make, share, play against them."""
from test_api import setup_family


def test_own_bots_shared_and_at_the_table(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.post("/api/community/bots", json={"name": ""}, headers=hm).status_code == 400
    b1 = client.post("/api/community/bots", json={"name": "Robo Rita", "emoji": "🤖", "color": "#e03131", "level": "hard", "shared": True}, headers=hm).json()["id"]
    b2 = client.post("/api/community/bots", json={"name": "Geheim", "emoji": "👻", "level": "easy"}, headers=hm).json()["id"]
    leo_sees = client.get("/api/community/bots", headers=hl).json()["bots"]
    assert [b["name"] for b in leo_sees] == ["Robo Rita"] and not leo_sees[0]["mine"] and leo_sees[0]["owner"] == "Mia"
    assert client.put(f"/api/community/bots/{b1}", json={"name": "Hack"}, headers=hl).status_code == 400      # not his bot
    assert client.delete(f"/api/community/bots/{b2}", headers=hl).status_code == 400
    # Leo plays Tschau Sepp alone against Mia's shared bot (and an animal bot)
    st = client.post("/api/community/cards/tschau/start", json={"solo": True, "bots": 2, "bot_ids": [b1, b2]}, headers=hl).json()
    bots = [p for p in st["players"] if p["bot"]]
    assert len(bots) == 2 and bots[0]["name"] == "Robo Rita" and "Geheim" not in [p["name"] for p in bots]   # not shared → not for Leo
    # poker: Mia's own secret bot
    st = client.post("/api/community/poker/start", json={"solo": True, "bots": 1, "bot_ids": [b2]}, headers=hm).json()
    assert [p["name"] for p in st["players"] if p["bot"]] == ["Geheim"]
    assert client.delete(f"/api/community/bots/{b2}", headers=hm).status_code == 200
