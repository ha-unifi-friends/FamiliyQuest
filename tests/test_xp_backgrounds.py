"""Backgrounds for new XP: every 500 XP earned after the feature exists unlock one; the XP account is not touched."""
from tests.test_api import setup_family


def test_xp_backgrounds_use_new_xp_only(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    old_marker = fq.db.get_setting("xp_items_from")
    fq.rewards.book(mia, "xp", 400, "bonus", "old xp")
    fq.db.set_setting("xp_items_from", int(fq.db.val("SELECT MAX(id) FROM ledger")))    # those 400 XP are «old»
    assert old_marker is not None
    d = client.get("/api/me/avatar", headers=h).json()
    xp_items = [i for i in d["items"] if i["rule"].get("xp")]
    assert len(xp_items) == 15 and d["new_xp"] == 0
    assert client.post("/api/me/avatar/buy", json={"item": "bg_space"}, headers=h).status_code == 400
    fq.rewards.book(mia, "xp", 520, "bonus", "new xp")
    before = (fq.rewards.balance(mia, "xp"), fq.rewards.total_xp(mia))
    assert client.post("/api/me/avatar/buy", json={"item": "bg_space"}, headers=h).status_code == 200
    assert (fq.rewards.balance(mia, "xp"), fq.rewards.total_xp(mia)) == before        # XP account unchanged
    d = client.get("/api/me/avatar", headers=h).json()
    assert d["new_xp"] == 20 and next(i for i in d["items"] if i["id"] == "bg_space")["unlocked"]
    assert client.post("/api/me/avatar/buy", json={"item": "bg_forest"}, headers=h).status_code == 400
    a = client.post("/api/me/avatar", json={"avatar": {**d["avatar"], "items": {"background": "bg_space"}}}, headers=h).json()
    assert a["avatar"]["items"]["background"] == "bg_space"
