"""Backup and restore of everything in one file."""
import io
import json
import zipfile


def ph(client):
    return {"X-FQ-Parent": client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()["parent_token"]}


def test_backup_and_restore_roundtrip(client):
    h = ph(client)
    fq = client.app.state.fq
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=h).json()["id"]
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 100}, headers=h)
    (fq.settings.media_dir / "x").mkdir(parents=True, exist_ok=True)
    (fq.settings.media_dir / "x" / "bild.png").write_bytes(b"PNG")
    planner = fq.planer_host.planner
    planner.data["persons"]["lea"] = {"name": "Lea", "color": "#ff0000"}

    r = client.get("/api/parent/backup", headers=h)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    manifest = json.loads(z.read("manifest.json"))
    assert manifest["format"] == "family-quest-backup" and manifest["counts"]["profile"] == 2
    assert "media/x/bild.png" in z.namelist()
    backup = r.content

    # change things after the backup
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 500}, headers=h)
    leo = client.post("/api/parent/profiles", json={"name": "Leo"}, headers=h).json()["id"]
    (fq.settings.media_dir / "x" / "bild.png").unlink()
    fq.planer_host.planner.data["persons"].pop("lea")

    r = client.post("/api/parent/restore", files={"file": ("b.zip", backup)}, headers=h)
    assert r.status_code == 200, r.text
    assert fq.rewards.balance(mia, "coins") == 100
    assert not fq.db.q1("SELECT 1 FROM profile WHERE id=? AND archived=0", leo)
    assert (fq.settings.media_dir / "x" / "bild.png").read_bytes() == b"PNG"
    assert "lea" in fq.planer_host.planner.data["persons"]               # planner reloaded from the backup
    # parent login still works after the restore
    assert client.get("/api/parent/overview", headers=h).status_code == 200


def test_restore_rejects_bad_files(client):
    h = ph(client)
    assert client.post("/api/parent/restore", files={"file": ("x.zip", b"nope")}, headers=h).status_code == 400
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": "other"}))
        z.writestr("family_quest.db", b"x")
    assert client.post("/api/parent/restore", files={"file": ("x.zip", buf.getvalue())}, headers=h).status_code == 400
    # a backup from a newer app version is refused
    good = client.get("/api/parent/backup", headers=h).content
    z = zipfile.ZipFile(io.BytesIO(good))
    import sqlite3, tempfile, pathlib
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp) / "db"
        p.write_bytes(z.read("family_quest.db"))
        c = sqlite3.connect(p); c.execute("PRAGMA user_version=999"); c.commit(); c.close()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z2:
            z2.writestr("manifest.json", z.read("manifest.json"))
            z2.writestr("family_quest.db", p.read_bytes())
    r = client.post("/api/parent/restore", files={"file": ("x.zip", buf.getvalue())}, headers=h)
    assert r.status_code == 400 and "newer" in r.json()["detail"]
    assert client.get("/api/parent/backup").status_code == 401                 # parent PIN needed


def test_restore_in_pieces_for_big_backups(client):
    """Home Assistant refuses uploads above ~16 MB: the parent area sends the backup in pieces."""
    h = ph(client)
    fq = client.app.state.fq
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=h).json()["id"]
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 70}, headers=h)
    backup = client.get("/api/parent/backup", headers=h).content
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 500}, headers=h)
    up, step = "abc123def456", 1000
    pieces = [backup[i:i + step] for i in range(0, len(backup), step)]
    assert len(pieces) > 2
    assert client.post("/api/parent/backup/chunk?upload=abc123def456&index=1", content=b"x", headers=h).status_code == 400   # not started
    for i, piece in enumerate(pieces):
        r = client.post(f"/api/parent/backup/chunk?upload={up}&index={i}", content=piece, headers={**h, "content-type": "application/octet-stream"})
        assert r.status_code == 200, r.text
    assert r.json()["size"] == len(backup)
    m = client.post("/api/parent/backup/inspect-upload", json={"upload": up}, headers=h).json()["manifest"]
    assert m["format"] == "family-quest-backup"
    r = client.post("/api/parent/restore-upload", json={"upload": up}, headers=h)
    assert r.status_code == 200, r.text
    assert fq.rewards.balance(mia, "coins") == 70
    assert client.post("/api/parent/restore-upload", json={"upload": up}, headers=h).status_code == 400    # used up
    assert client.post("/api/parent/backup/chunk?upload=../x&index=0", content=b"x", headers=h).status_code == 400
    assert client.post(f"/api/parent/backup/chunk?upload={up}&index=0", content=b"x").status_code == 401    # parents only
