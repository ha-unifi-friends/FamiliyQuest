"""Who begins a turn-based game: 🎲 dice, the game leader or a chosen player (cardgames.apply_starter)."""
from collections import Counter

from familyquest.cardgames import apply_starter
from test_api import setup_family


def players(n):
    return [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]


def test_apply_starter_keeps_the_seat_order():
    st = {"players": players(4)}
    assert apply_starter(st, "choose", "3", leader="1") == "3"
    assert [p["id"] for p in st["players"]] == ["3", "4", "1", "2"] and st["starter"]["how"] == "choose"
    st = {"players": players(4)}
    assert apply_starter(st, "choose", "99", leader="2") == "2" and st["starter"]["how"] == "choose"   # no valid choice
    st = {"players": players(4)}
    assert apply_starter(st, "leader", None, leader=2) == "2" and st["starter"]["how"] == "leader"
    seen = Counter()
    for _ in range(400):
        st = {"players": players(4)}
        first = apply_starter(st, "dice", leader="1")
        assert st["players"][0]["id"] == first and st["starter"]["how"] == "dice"
        seen[first] += 1
    assert set(seen) == {"1", "2", "3", "4"} and min(seen.values()) > 50


def test_setting_and_choice_through_the_api(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.put("/api/parent/settings", json={"game_starter": "nope"}, headers=ph).status_code == 400
    client.put("/api/parent/settings", json={"game_starter": "choose"}, headers=ph)
    assert client.get("/api/community/starter", headers=hm).json()["mode"] == "choose"
    client.post("/api/community/cards/tschau/start", json={"bots": 0}, headers=hm)
    client.post("/api/community/cards/tschau/join", headers=hl)
    st = client.post("/api/community/cards/tschau/begin", json={"starter": str(leo)}, headers=hm).json()
    assert st["starter"]["id"] == str(leo) and st["starter"]["name"] == "Leo"
