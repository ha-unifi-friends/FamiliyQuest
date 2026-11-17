"""Shop prank «Tintenbombe»: bought for 500 coins (one charge each), thrown at family members, wiped clean."""
from test_api import setup_family


def login(client, pid, pin=None):
    body = {"profile_id": pid, **({"pin": pin} if pin else {})}
    return {"X-FQ-Token": client.post("/api/login", json=body).json()["token"]}


def test_buy_throw_and_clean(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    papa = client.app.state.fq.db.val("SELECT id FROM profile WHERE role='parent'")
    assert client.post("/api/me/pranks/buy", headers=hl).status_code == 400              # not enough coins
    client.post("/api/parent/book", json={"profile_id": leo, "account": "coins", "amount": 1100}, headers=ph)
    assert client.post("/api/me/pranks/throw", json={"targets": [mia]}, headers=hl).status_code == 400   # no bomb yet
    st = client.post("/api/me/pranks/buy", headers=hl).json()
    assert st["charges"] == 1 and st["coins"] == 600
    st = client.post("/api/me/pranks/buy", headers=hl).json()
    assert st["charges"] == 2 and st["coins"] == 100
    assert {p["id"] for p in st["family"]} == {mia, papa}                                 # not himself
    # one bomb for several people; himself and unknown ids are ignored
    r = client.post("/api/me/pranks/throw", json={"targets": [mia, papa, leo, 999]}, headers=hl).json()
    assert sorted(r["hit"]) == sorted([mia, papa]) and r["charges"] == 1
    assert all(p["hit_today"] for p in r["family"])
    # once a day per person
    assert client.post("/api/me/pranks/throw", json={"targets": [mia]}, headers=hl).status_code == 400
    assert client.get("/api/me/pranks", headers=hl).json()["charges"] == 1               # the failed throw keeps the bomb
    # Mia sees it – in the dashboard too – and only she can clean it
    p = client.get("/api/me", headers=hm).json()["prank"]
    assert p and p["from"]["name"] == "Leo"
    assert client.get("/api/me", headers=hl).json()["prank"] is None
    client.post(f"/api/me/pranks/{p['id']}/clean", headers=hl)                            # not Leo's ink
    assert client.get("/api/me/pranks/pending", headers=hm).json()["prank"]["id"] == p["id"]
    assert client.post(f"/api/me/pranks/{p['id']}/clean", headers=hm).json()["next"] is None
    assert client.get("/api/me/pranks/pending", headers=hm).json()["prank"] is None


def test_archived_profiles_cannot_be_hit(client):
    ph, mia, leo = setup_family(client)
    hl = login(client, leo)
    fq = client.app.state.fq
    client.post("/api/parent/book", json={"profile_id": leo, "account": "coins", "amount": 500}, headers=ph)
    client.post("/api/me/pranks/buy", headers=hl)
    fq.db.x("UPDATE profile SET archived=1 WHERE id=?", mia)
    assert client.post("/api/me/pranks/throw", json={"targets": [mia]}, headers=hl).status_code == 400
    assert mia not in {p["id"] for p in client.get("/api/me/pranks", headers=hl).json()["family"]}


class FakeHA:
    connected = True

    def __init__(self):
        self.calls = []

    def media_players(self):
        return [{"entity_id": "media_player.kitchen", "state": "idle"}, {"entity_id": "media_player.living", "state": "playing"},
                {"entity_id": "media_player.old", "state": "unavailable"}]

    def announce(self, entity, url, volume=None):
        self.calls.append((entity, url.rsplit("/", 1)[-1], volume))


def test_whoopee_cushion_three_times_on_all_speakers(client):
    import time
    ph, mia, leo = setup_family(client)
    hl = login(client, leo)
    fq = client.app.state.fq
    client.post("/api/parent/book", json={"profile_id": leo, "account": "coins", "amount": 300}, headers=ph)
    assert client.post("/api/me/pranks/fart", headers=hl).status_code == 400            # no speakers (no Home Assistant)
    fake = FakeHA()
    fq.ha, fq.lan_base = fake, "http://192.168.1.5:8099"
    try:
        assert client.post("/api/me/pranks/fart", headers=hl).status_code == 400        # no cushion yet
        st = client.post("/api/me/pranks/buy", json={"kind": "fart"}, headers=hl).json()
        assert st["fart"]["left"] == 3 and st["coins"] == 0 and st["fart"]["speakers"]
        for left in (2, 1, 0):
            r = client.post("/api/me/pranks/fart", headers=hl).json()
            assert r["fart"]["left"] == left and r["speakers"] == 2
        assert client.post("/api/me/pranks/fart", headers=hl).status_code == 400        # used up
        for _ in range(50):
            if len(fake.calls) == 6:
                break
            time.sleep(0.02)
        assert sorted(set(fake.calls)) == [("media_player.kitchen", "fart.mp3", 0.5), ("media_player.living", "fart.mp3", 0.5)]
        assert client.post("/api/me/pranks/buy", json={"kind": "nope"}, headers=hl).status_code == 400
    finally:
        fq.ha, fq.lan_base = None, None
