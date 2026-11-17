"""Parent area › Shop: avatar items can be switched off, get a new price or be paid with new XP."""
from tests.test_api import setup_family


def test_parents_lock_reprice_and_switch_items_to_new_xp(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    items = {i["id"]: i for i in client.get("/api/parent/shop/items", headers=ph).json()["items"]}
    assert items["cap"]["rule"] == {"cost": 40} and items["bg_space"]["rule"] == {"xp": 500}
    fq.rewards.book(mia, "coins", 100, "bonus", "test")
    # off: not in the shop, cannot be bought
    assert client.put("/api/parent/shop/items/cap", json={"off": True}, headers=ph).json()["rule"]["off"]
    assert client.post("/api/me/avatar/buy", json={"item": "cap"}, headers=h).status_code == 400
    # new price in coins
    assert client.put("/api/parent/shop/items/sunglasses", json={"price": 7}, headers=ph).json()["rule"] == {"cost": 7}
    assert client.post("/api/me/avatar/buy", json={"item": "sunglasses"}, headers=h).status_code == 200
    assert fq.rewards.balance(mia, "coins") == 93
    # paid with new XP instead of coins (same price), the XP account is not touched
    assert client.put("/api/parent/shop/items/scarf", json={"currency": "xp"}, headers=ph).json()["rule"] == {"xp": 45}
    assert client.post("/api/me/avatar/buy", json={"item": "scarf"}, headers=h).status_code == 400   # no new XP yet
    fq.rewards.book(mia, "xp", 50, "bonus", "new")
    xp = fq.rewards.balance(mia, "xp")
    assert client.post("/api/me/avatar/buy", json={"item": "scarf"}, headers=h).status_code == 200
    assert fq.rewards.balance(mia, "xp") == xp and client.get("/api/me/avatar", headers=h).json()["new_xp"] == 5
    # a level item with a price: still by level, or bought
    assert client.put("/api/parent/shop/items/crown", json={"price": 3}, headers=ph).json()["rule"] == {"level": 20, "cost": 3}
    # reset
    assert client.put("/api/parent/shop/items/cap", json={}, headers=ph).json()["rule"] == {"cost": 40}
    assert client.put("/api/parent/shop/items/nope", json={}, headers=ph).status_code == 404
    assert client.put("/api/parent/shop/items/cap", json={"currency": "gold"}, headers=ph).status_code == 400


def test_drafts_can_be_assigned_before_publishing(client):
    ph, mia, _ = setup_family(client)
    pack = {"id": "early", "titel": "Early", "fach": "englisch", "sprache": "en", "einheiten": [{"id": "a", "karten": [{"de": "Hund", "en": "dog"}]}]}
    client.post("/api/parent/import/json", json=pack, headers=ph)
    assert client.post("/api/parent/packs/activate", json={"profile_id": mia, "pack_id": "early", "on": True}, headers=ph).status_code == 200
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    has = lambda: "early" in {s["pack"] for s in client.get("/api/me", headers=h).json()["subjects"]}
    assert not has()
    client.post("/api/parent/packs/early/status", json={"status": "active"}, headers=ph)
    assert has()
