"""Pairs game: photo sets and family crest from the parent area."""
import io
import os
import time

from test_api import setup_family


def age_photos(client):
    """Make the uploaded photos older than an hour – fresh ones are kept while an upload may still be running."""
    folder = client.app.state.fq.settings.media_dir / "_memory"
    for f in folder.iterdir():
        os.utime(f, (time.time() - 7200, time.time() - 7200))

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
    # removing a set deletes photos nobody uses any more (once they are not fresh any more)
    client.put("/api/parent/memory", json={"sets": [{"name": "Ferien", "photos": names[:2]}]}, headers=ph)
    assert client.get(f"/media/_memory/{names[3]}").status_code == 200
    age_photos(client)
    client.put("/api/parent/memory", json={"sets": [{"name": "Ferien", "photos": names[:2]}]}, headers=ph)
    assert client.get(f"/media/_memory/{names[3]}").status_code == 404
    assert client.get(f"/media/_memory/{names[0]}").status_code == 200


JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def test_pictures_from_ha_media_and_crest_picture(client, settings, tmp_path):
    ph, mia, leo = setup_family(client)
    root = tmp_path / "ha_media"
    settings.ha_media_dir = root
    assert client.get("/api/parent/ha-media", headers=ph).json()["available"] is False      # no media folder mapped
    (root / "Ferien" / ".hidden").mkdir(parents=True)
    (root / "Ferien" / "a.jpg").write_bytes(JPG + b"1")
    (root / "Ferien" / "b.JPG").write_bytes(JPG + b"2")
    (root / "Ferien" / "notes.txt").write_text("x")
    (root / "Ferien" / "fake.png").write_bytes(b"hello")
    (tmp_path / "secret.jpg").write_bytes(JPG)
    top = client.get("/api/parent/ha-media", headers=ph).json()
    assert top == {"available": True, "path": "", "folders": ["Ferien"], "images": []}
    d = client.get("/api/parent/ha-media", params={"path": "Ferien"}, headers=ph).json()
    assert d["folders"] == [] and [x["name"] for x in d["images"]] == ["a.jpg", "b.JPG", "fake.png"]
    assert client.get("/api/parent/ha-media", params={"path": "../"}, headers=ph).status_code == 404
    assert client.get("/api/parent/ha-media", params={"path": "Ferien/.hidden"}, headers=ph).status_code == 404
    assert client.get("/api/parent/ha-media/file", params={"path": "Ferien/a.jpg"}, headers=ph).status_code == 200
    assert client.get("/api/parent/ha-media/file", params={"path": "../secret.jpg"}, headers=ph).status_code == 404
    assert client.get("/api/parent/ha-media/file", params={"path": "Ferien/a.jpg"}).status_code == 401  # parents only
    # copy into the photo folder
    assert client.post("/api/parent/memory/ha-media", json={"paths": ["Ferien/fake.png"]}, headers=ph).status_code == 400
    assert client.post("/api/parent/memory/ha-media", json={"paths": ["../secret.jpg"]}, headers=ph).status_code == 400
    r = client.post("/api/parent/memory/ha-media", json={"paths": ["Ferien/a.jpg", "Ferien/b.JPG"]}, headers=ph)
    assert r.status_code == 200, r.text
    a, b = r.json()["names"]
    assert (a, b) == ("ha:Ferien/a.jpg", "ha:Ferien/b.JPG")          # references – no copies (not in the backup)
    assert not (settings.media_dir / "_memory").exists() or not any((settings.media_dir / "_memory").iterdir())
    assert client.get("/hamedia/Ferien/a.jpg").status_code == 404                   # not used by a set yet
    d = client.put("/api/parent/memory", json={"sets": [{"name": "Ferien", "photos": [a, b, "ha:../secret.jpg", "ha:Ferien/nope.jpg"]}]}, headers=ph).json()
    assert d["sets"][0]["photos"] == [a, b]
    assert client.get("/hamedia/Ferien/a.jpg").status_code == 200 and client.get("/hamedia/Ferien/fake.png").status_code == 404
    assert client.get("/hamedia/../secret.jpg").status_code == 404
    # the crest as a picture from Home Assistant Media
    d = client.put("/api/parent/memory", json={"crest": {"name": "Muster", "image": b}}, headers=ph).json()
    assert d["crest"]["image"] == b and client.get("/hamedia/Ferien/b.JPG").status_code == 200
    d = client.put("/api/parent/memory", json={"sets": [], "crest": {"name": "Muster", "image": "nope.jpg"}}, headers=ph).json()
    assert d["crest"]["image"] is None


def test_crest_and_sets_are_saved_separately(client):
    ph, _, _ = setup_family(client)
    names = [client.post("/api/parent/memory/photo", files={"file": ("a.png", io.BytesIO(PNG + bytes([i])), "image/png")}, headers=ph).json()["name"]
             for i in range(3)]
    client.put("/api/parent/memory", json={"sets": [{"name": "Ferien", "photos": names}]}, headers=ph)
    d = client.put("/api/parent/memory", json={"crest": {"name": "Muster", "icon": "🦁"}}, headers=ph).json()   # crest section
    assert d["sets"][0]["photos"] == names and d["crest"]["icon"] == "🦁"
    d = client.put("/api/parent/memory", json={"sets": []}, headers=ph).json()                                    # photo sets section
    assert d["crest"]["icon"] == "🦁" and d["sets"] == []


def test_old_copies_of_ha_media_become_references(client, settings, tmp_path):
    """Until beta.19 photos of Home Assistant Media were copied – now they are found there and only referenced."""
    import hashlib
    from familyquest import memorygame
    fq = client.app.state.fq
    root = tmp_path / "hamedia"
    (root / "Ferien").mkdir(parents=True)
    jpg = b"\xff\xd8\xff\xe0" + b"ferien" * 100
    (root / "Ferien" / "a.jpg").write_bytes(jpg)
    settings.ha_media_dir = root
    folder = settings.media_dir / memorygame.FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    copy = "foto-" + hashlib.sha1(jpg).hexdigest()[:12] + ".jpg"
    (folder / copy).write_bytes(jpg)
    own = "foto-own.png"
    (folder / own).write_bytes(b"\x89PNG\r\n\x1a\n" + b"own" * 50)          # uploaded, not in HA Media: stays
    fq.db.set_setting("memory", {"sets": [{"id": "s1", "name": "Ferien", "photos": [copy, own]}], "crest": {"image": copy}})
    assert memorygame.relink_ha_copies(fq) == 1
    d = memorygame.get(fq)
    assert d["sets"][0]["photos"] == ["ha:Ferien/a.jpg", own] and d["crest"]["image"] == "ha:Ferien/a.jpg"
    assert not (folder / copy).exists() and (folder / own).exists()
    assert memorygame.relink_ha_copies(fq) == 0                                  # nothing left to do
