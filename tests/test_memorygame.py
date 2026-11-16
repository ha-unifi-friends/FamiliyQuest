"""Pairs game: photo sets and family crest from the parent area."""
import io

from test_api import setup_family

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_photo_sets_and_crest(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    names = []
    for i in range(4):
        r = client.post("/api/parent/memory/photo", files={"file": ("a.png", io.BytesIO(PNG + bytes([i])), "image/png")}, headers=ph)
        assert r.status_code == 200, r.text
        names.append(r.json()["name"])
    assert client.post("/api/parent/memory/photo", files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")}, headers=ph).status_code == 400
    assert client.get(f"/media/_memory/{names[0]}").status_code == 200
    assert client.put("/api/parent/memory", json={"sets": [{"name": "", "photos": names}]}, headers=ph).status_code == 400
    r = client.put("/api/parent/memory", json={"sets": [{"name": "Ferien", "photos": names[:3] + ["evil/../x.png"]}, {"name": "Zu wenig", "photos": names[3:]}],
                                              "crest": {"name": "Muster", "icon": "🦁", "colors": ["#ff0000", "nope"], "pattern": "quarter"}}, headers=ph)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["sets"][0]["photos"] == names[:3] and d["crest"]["colors"] == ["#ff0000", "#fcc419"]
    pub = client.get("/api/community/memory", headers=hm).json()
    assert [s["name"] for s in pub["sets"]] == ["Ferien"]                 # a set with fewer than 3 photos gives no game
    assert pub["sets"][0]["photos"][0] == f"media/_memory/{names[0]}" and pub["crest"]["icon"] == "🦁"
    # removing a set deletes photos nobody uses any more
    client.put("/api/parent/memory", json={"sets": [{"name": "Ferien", "photos": names[:2]}]}, headers=ph)
    assert client.get(f"/media/_memory/{names[3]}").status_code == 404
    assert client.get(f"/media/_memory/{names[0]}").status_code == 200
