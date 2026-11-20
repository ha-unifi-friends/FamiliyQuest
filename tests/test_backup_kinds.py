"""The three kinds of backup (full / data / customizing), one restore that detects the kind, the classification of
every table and setting (sync guard), the values of the installation that no restore takes over, and the pause of the
writes for Home Assistant's hot backups (hotbackup.py)."""
import io
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from familyquest import backup, hotbackup
from familyquest.db import DEFAULT_SETTINGS, MIGRATIONS, Database

APP = Path(__file__).resolve().parent.parent / "family_quest" / "app"


def _ph(client):
    return {"X-FQ-Parent": client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()["parent_token"]}


@contextmanager
def _other_install():
    """A second installation (own data folder)."""
    from fastapi.testclient import TestClient
    from familyquest.main import create_app
    from familyquest.settings import BUILTIN_PACKS, Settings
    with tempfile.TemporaryDirectory() as tmp:
        s = Settings(data_dir=Path(tmp), packs_dirs=[BUILTIN_PACKS], ha_enabled=False, ha_url="", ha_token=None,
                     secret=b"y" * 32, version="test")
        with TestClient(create_app(s)) as c:
            yield c


def _family(client):
    """Papa (1), Mia (2), Leo (3) with coins, a chore done, a best score, own settings and files."""
    h = _ph(client)
    fq = client.app.state.fq
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=h).json()["id"]
    leo = client.post("/api/parent/profiles", json={"name": "Leo"}, headers=h).json()["id"]
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 100}, headers=h)
    client.post("/api/parent/book", json={"profile_id": leo, "account": "coins", "amount": 40}, headers=h)
    cid = fq.db.x("INSERT INTO chore(name, profiles) VALUES('Tisch decken', ?)", json.dumps([mia]))
    fq.db.x("INSERT INTO chore_task(chore_id, profile_id, period, status) VALUES(?,?,?, 'done')", cid, leo, "2026-11-01")
    fq.db.x("UPDATE reward SET name='Kinoabend' WHERE id=(SELECT MIN(id) FROM reward)")
    fq.db.set_setting("jump_best", {str(mia): 12, str(leo): 30})
    fq.db.set_setting("themes", {"season": "winter"})
    fq.db.set_setting("ha_panel_path", "/app/abc_family_quest")
    fq.db.set_setting("ha_app_login_url", "http://192.168.1.10:8123")
    fq.db.set_setting("ha_integration", {"enabled": True, "token_hash": "aa", "instance": "x"})
    fq.db.set_setting("dashboard", {"enabled": True, "key": "real-key", "title": "Wand"})
    (fq.settings.media_dir / "own").mkdir(parents=True, exist_ok=True)
    (fq.settings.media_dir / "own" / "bild.png").write_bytes(b"PNG")
    (fq.settings.data_dir / "family_planer").mkdir(parents=True, exist_ok=True)
    (fq.settings.data_dir / "family_planer" / "foto.jpg").write_bytes(b"JPG")
    return h, mia, leo


def _download(client, h, kind):
    r = client.get(f"/api/parent/backup?kind={kind}", headers=h)
    assert r.status_code == 200, r.text
    return r.content


def _db_of(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.write(z.read("family_quest.db"))
    tmp.close()
    c = sqlite3.connect(tmp.name)
    return c, json.loads(z.read("manifest.json")), set(z.namelist())


def _restore(client, h, raw):
    r = client.post("/api/parent/restore", files={"file": ("b.zip", raw, "application/zip")}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["manifest"]


def _coins(fq, pid):
    return fq.rewards.balance(pid, "coins")


# ---------------------------------------------------------------- sync guard
def test_every_table_and_migration_is_classified(tmp_path):
    db = Database(tmp_path / "x.db")
    tables = [r["name"] for r in db.q("SELECT name FROM sqlite_master WHERE type='table'")]
    missing = [t for t in tables if t not in backup.TABLES and t not in backup.INTERNAL_TABLES]
    assert not missing, f"classify these tables in backup.TABLES (data or customizing): {missing}"
    assert len(MIGRATIONS) == backup.CLASSIFIED_MIGRATIONS, (
        "a new migration: classify its tables and settings in backup.py (TABLES / SETTINGS), then raise CLASSIFIED_MIGRATIONS")
    for t, (kind, owners, parent) in backup.TABLES.items():
        assert kind in (backup.DATA, backup.CUSTOM), t
        if t in tables:
            cols = {r["name"] for r in db.q(f'PRAGMA table_info("{t}")')}
            assert set(owners) <= cols, (t, owners)
            if parent:
                assert parent[0] in cols and parent[1] in backup.TABLES, (t, parent)


def test_every_setting_key_is_classified():
    keys = set(DEFAULT_SETTINGS)
    src = APP / "familyquest"
    pat = re.compile(r"""(?:get_setting|set_setting)\(\s*f?["']([A-Za-z0-9_.]+)""")
    const = re.compile(r"""^(?:KEY|RULES_KEY|POLL_KEY)\s*=\s*["']([A-Za-z0-9_.]+)["']""", re.M)
    for f in src.rglob("*.py"):
        if "planer" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        keys |= set(pat.findall(text)) | set(const.findall(text))
    from familyquest.facts import BESTS
    keys |= {b[0] for b in BESTS}
    missing = sorted(k for k in keys if backup.setting_kind(k, None) is None)
    assert not missing, f"classify these settings in backup.SETTINGS (data, customizing or environment): {missing}"


# ---------------------------------------------------------------- contents of each kind
def test_each_kind_holds_its_part(client):
    h, mia, leo = _family(client)
    full, data, custom = (_download(client, h, k) for k in ("full", "data", "customizing"))
    c, m, names = _db_of(full)
    assert m["kind"] == "full" and c.execute("SELECT COUNT(*) FROM profile").fetchone()[0] == 3
    assert c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] >= 2
    assert {"media/own/bild.png", "family_planer/foto.jpg"} <= names

    c, m, names = _db_of(data)
    assert m["kind"] == "data"
    assert [p["name"] for p in m["profiles"]] == ["Papa", "Mia", "Leo"]          # for matching on a restore
    for t in ("profile", "chore", "reward", "account", "rule", "pack", "pack_profile"):
        assert c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0, t
    assert c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] >= 2
    assert c.execute("SELECT COUNT(*) FROM chore_task").fetchone()[0] == 1
    keys = {r[0] for r in c.execute("SELECT key FROM setting")}
    assert "jump_best" in keys and not keys & {"themes", "ha_panel_path", "game_starter", "dashboard"}
    assert "family_planer/foto.jpg" in names and not any(n.startswith("media/") for n in names)

    c, m, names = _db_of(custom)
    assert m["kind"] == "customizing"
    for t in ("ledger", "chore_task", "item_state", "daily", "kv", "history"):
        assert c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0, t
    assert c.execute("SELECT COUNT(*) FROM profile").fetchone()[0] == 3
    assert c.execute("SELECT pin_hash FROM profile WHERE name='Papa'").fetchone()[0]
    assert c.execute("SELECT name FROM chore").fetchone()[0] == "Tisch decken"
    keys = {r[0] for r in c.execute("SELECT key FROM setting")}
    assert {"themes", "game_starter", "dashboard"} <= keys and not keys & {"jump_best", "ha_panel_path", "ha_integration"}
    dash = json.loads(c.execute("SELECT value FROM setting WHERE key='dashboard'").fetchone()[0])
    assert "key" not in dash and dash["title"] == "Wand"                         # the kiosk link stays at home
    assert "media/own/bild.png" in names and not any(n.startswith("family_planer/") for n in names)
    assert client.get("/api/parent/backup?kind=other", headers=h).status_code == 400


def test_the_kind_is_detected_and_old_backups_are_full(client):
    h, mia, leo = _family(client)
    for kind in ("full", "data", "customizing"):
        raw = _download(client, h, kind)
        r = client.post("/api/parent/backup/inspect", files={"file": ("b.zip", raw, "application/zip")}, headers=h)
        assert r.status_code == 200 and r.json()["manifest"]["kind"] == kind
        assert r.json()["manifest"]["plan"]["kind"] == kind
    # a backup from before the kinds (no «kind» in the manifest) is a full backup
    raw = _download(client, h, "full")
    z = zipfile.ZipFile(io.BytesIO(raw))
    m = json.loads(z.read("manifest.json"))
    m.pop("kind"); m.pop("profiles"); m["version"] = 1
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z2:
        for n in z.namelist():
            z2.writestr(n, json.dumps(m) if n == "manifest.json" else z.read(n))
    old = buf.getvalue()
    assert backup.check(old)["kind"] == "full"
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 5}, headers=h)
    client.app.state.fq.db.x("DELETE FROM chore")
    out = _restore(client, h, old)
    assert out["kind"] == "full" and out["report"]["kind"] == "full"
    fq = client.app.state.fq
    assert _coins(fq, mia) == 100 and fq.db.val("SELECT COUNT(*) FROM chore") == 1
    # an unknown kind is refused
    m["kind"] = "everything"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z2:
        for n in z.namelist():
            z2.writestr(n, json.dumps(m) if n == "manifest.json" else z.read(n))
    r = client.post("/api/parent/restore", files={"file": ("b.zip", buf.getvalue(), "application/zip")}, headers=h)
    assert r.status_code == 400


# ---------------------------------------------------------------- restores
def test_data_restore_onto_a_customizing_only_install(client):
    h, mia, leo = _family(client)
    custom, data = _download(client, h, "customizing"), _download(client, h, "data")
    fq_a = client.app.state.fq
    a_mia, a_leo = _coins(fq_a, mia), _coins(fq_a, leo)
    with _other_install() as b:
        hb = _ph(b)                                  # Papa (1)
        fq = b.app.state.fq
        _restore(b, hb, custom)                      # the set-up of A: Papa, Mia, Leo – no data
        assert sorted(r["name"] for r in fq.db.q("SELECT name FROM profile")) == ["Leo", "Mia", "Papa"]
        assert fq.db.val("SELECT COUNT(*) FROM ledger") == 0 and _coins(fq, mia) == 0
        assert fq.db.get_setting("themes") == {"season": "winter"}
        assert (fq.settings.media_dir / "own" / "bild.png").read_bytes() == b"PNG"
        # Papa is now the Papa of A (his PIN hash): sign in again
        hb = {"X-FQ-Parent": b.post("/api/parent/login", json={"pin": "1234"}).json()["parent_token"]}
        fq.db.x("DELETE FROM profile WHERE id=?", leo)       # Leo does not exist here
        fq.db.x("UPDATE profile SET name='Mila' WHERE id=?", mia)
        r = b.post("/api/parent/backup/inspect", files={"file": ("d.zip", data, "application/zip")}, headers=hb)
        assert r.status_code == 200, r.text
        r = r.json()["manifest"]
        assert r["plan"]["missing"] == [{"id": leo, "name": "Leo"}]
        assert r["plan"]["renamed"] == [{"id": mia, "backup": "Mia", "here": "Mila"}]
        out = _restore(b, hb, data)
        assert out["kind"] == "data"
        skipped = out["report"]["skipped"]
        assert [s["id"] for s in skipped] == [leo] and skipped[0]["name"] == "Leo" and skipped[0]["rows"] >= 2
        assert _coins(fq, mia) == a_mia == 100                  # matched by id
        assert not fq.db.q1("SELECT 1 FROM ledger WHERE profile_id=?", leo)
        assert not fq.db.q1("SELECT 1 FROM chore_task WHERE profile_id=?", leo)
        assert fq.db.get_setting("jump_best") == {str(mia): 12, str(leo): 30}
        assert fq.db.get_setting("themes") == {"season": "winter"}             # settings stay
        assert (fq.settings.data_dir / "family_planer" / "foto.jpg").read_bytes() == b"JPG"
        assert (fq.settings.media_dir / "own" / "bild.png").is_file()           # own pictures stay
        assert (fq.settings.data_dir / "before-restore.zip").is_file()
        assert b.get("/api/parent/overview", headers=hb).status_code == 200
    assert a_leo == 40


def test_customizing_restore_keeps_the_data(client):
    h, mia, leo = _family(client)
    fq = client.app.state.fq
    custom = _download(client, h, "customizing")
    # after the backup: more coins, a new child with data, other settings and an own reward renamed
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 7}, headers=h)
    zoe = client.post("/api/parent/profiles", json={"name": "Zoe"}, headers=h).json()["id"]
    client.post("/api/parent/book", json={"profile_id": zoe, "account": "coins", "amount": 9}, headers=h)
    fq.db.x("UPDATE reward SET name='Zoo' WHERE name='Kinoabend'")
    fq.db.x("UPDATE chore SET name='Abwaschen'")
    fq.db.set_setting("themes", {"season": "summer"})
    fq.db.set_setting("jump_best", {str(mia): 99})
    tasks = fq.db.val("SELECT COUNT(*) FROM chore_task")
    out = _restore(client, h, custom)
    assert out["kind"] == "customizing"
    assert [p["name"] for p in out["report"]["kept"]] == ["Zoe"]
    assert fq.db.get_setting("themes") == {"season": "winter"}                 # customizing back
    assert fq.db.val("SELECT name FROM chore") == "Tisch decken"
    assert fq.db.q1("SELECT 1 FROM reward WHERE name='Kinoabend'")
    assert _coins(fq, mia) == 107 and _coins(fq, leo) == 40                    # data stay – balances as before
    assert _coins(fq, zoe) == 9 and fq.db.q1("SELECT 1 FROM profile WHERE id=? AND name='Zoe'", zoe)   # no orphans
    assert fq.db.get_setting("jump_best") == {str(mia): 99}
    assert fq.db.val("SELECT COUNT(*) FROM chore_task") == tasks
    assert (fq.settings.data_dir / "family_planer" / "foto.jpg").is_file()
    assert client.get("/api/parent/overview", headers=h).status_code == 200


@pytest.mark.parametrize("kind", ["full", "customizing"])
def test_environment_values_are_never_taken_over(client, kind):
    h, mia, leo = _family(client)
    fq = client.app.state.fq
    raw = _download(client, h, kind)
    # this installation's own values change after the backup (e.g. the backup goes to another installation)
    fq.db.set_setting("ha_panel_path", "/hassio/ingress/dev_family_quest")
    fq.db.set_setting("ha_integration", {"enabled": True, "token_hash": "dev", "instance": "dev"})
    fq.db.set_setting("dashboard", {"enabled": True, "key": "dev-key", "title": "Dev"})
    fq.db.x("DELETE FROM setting WHERE key='ha_app_login_url'")
    fq.db.set_setting("last_backup", "2026-11-19T10:00:00")
    out = _restore(client, h, raw)
    assert set(out["report"]["environment"]) >= {"ha_panel_path", "ha_app_login_url", "ha_integration", "dashboard.key"}
    assert fq.db.get_setting("ha_panel_path") == "/hassio/ingress/dev_family_quest"
    assert fq.db.get_setting("ha_integration")["token_hash"] == "dev"
    assert not fq.db.q1("SELECT 1 FROM setting WHERE key='ha_app_login_url'")    # not set here: not taken over
    assert fq.db.get_setting("last_backup") == "2026-11-19T10:00:00"
    dash = fq.db.get_setting("dashboard")
    assert dash["key"] == "dev-key" and dash["title"] == "Wand"                   # the rest of the setting follows the backup


def test_full_restore_takes_everything_back(client):
    h, mia, leo = _family(client)
    fq = client.app.state.fq
    raw = _download(client, h, "full")
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 7}, headers=h)
    fq.db.set_setting("themes", {"season": "summer"})
    out = _restore(client, h, raw)
    assert out["kind"] == "full" and out["safety"] == "before-restore.zip"
    assert _coins(fq, mia) == 100 and fq.db.get_setting("themes") == {"season": "winter"}
    assert backup.check((fq.settings.data_dir / "before-restore.zip").read_bytes())["kind"] == "full"


# ---------------------------------------------------------------- hot backups by Home Assistant
def _writer(db, stop, count):
    while not stop.is_set():
        db.x("INSERT INTO login_log(kind, ok) VALUES('profile', 1)")
        count[0] += 1
        time.sleep(0.005)


def test_hot_backup_pauses_writes_and_checkpoints(tmp_path):
    db = Database(tmp_path / "family_quest.db")
    db.start_backup_watch(tmp_path, every=0.05)
    stop, count = threading.Event(), [0]
    t = threading.Thread(target=_writer, args=(db, stop, count), daemon=True)
    t.start()
    try:
        time.sleep(0.3)
        assert count[0] > 5
        res = hotbackup.pre(tmp_path, wait=5)
        assert res["by"] == "app" and res["paused"]
        wal = tmp_path / "family_quest.db-wal"
        assert not wal.exists() or wal.stat().st_size == 0                      # everything is in the database file
        rows = sqlite3.connect(tmp_path / "family_quest.db").execute("SELECT COUNT(*) FROM login_log").fetchone()[0]
        n = count[0]
        time.sleep(0.5)
        assert count[0] == n                                                     # no write while paused
        assert db.val("SELECT COUNT(*) FROM login_log") == rows                  # reading goes on
        hotbackup.post(tmp_path)
        time.sleep(0.4)
        assert count[0] > n                                                      # writes go on
        assert not (tmp_path / hotbackup.FLAG).exists() and not (tmp_path / hotbackup.ACK).exists()
    finally:
        stop.set()
        t.join(5)
        db.stop_backup_watch()


def test_hot_backup_pause_ends_by_itself(tmp_path):
    db = Database(tmp_path / "family_quest.db")
    db.start_backup_watch(tmp_path, every=0.05)
    stop, count = threading.Event(), [0]
    t = threading.Thread(target=_writer, args=(db, stop, count), daemon=True)
    t.start()
    try:
        hotbackup.pre(tmp_path, wait=5, pause=0.6)                               # no «post» comes
        n = count[0]
        time.sleep(0.3)
        assert count[0] == n
        time.sleep(1.0)
        assert count[0] > n
    finally:
        stop.set()
        t.join(5)
        db.stop_backup_watch()
    # a flag never pauses longer than PAUSE_MAX, whatever it says
    (tmp_path / hotbackup.FLAG).write_text(json.dumps({"token": "x", "until": time.time() + 99999}))
    assert hotbackup.read_flag(tmp_path / hotbackup.FLAG)["until"] <= time.time() + hotbackup.PAUSE_MAX + 1


def test_hot_backup_script_without_the_app(tmp_path):
    db = Database(tmp_path / "family_quest.db")
    db.x("INSERT INTO login_log(kind, ok) VALUES('profile', 1)")
    db.conn.close()
    script = APP / "familyquest" / "hotbackup.py"
    env = {"FQ_DATA_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, str(script), "pre"], env=env, capture_output=True, text=True, timeout=60,
                       cwd=tmp_path, input="")
    assert r.returncode == 0 and '"by": "script"' in r.stdout, r.stdout + r.stderr
    r = subprocess.run([sys.executable, str(script), "post"], env=env, capture_output=True, text=True, timeout=30, cwd=tmp_path)
    assert r.returncode == 0 and not (tmp_path / hotbackup.FLAG).exists()


def test_the_app_configs_ask_for_hot_backups_with_pre_and_post(tmp_path, monkeypatch):
    root = APP.parent.parent
    cfg = (root / "family_quest" / "config.yaml").read_text(encoding="utf-8")
    assert re.search(r"^backup: hot$", cfg, re.M)
    assert re.search(r"^backup_pre: python3 /app/familyquest/hotbackup.py pre$", cfg, re.M)
    assert re.search(r"^backup_post: python3 /app/familyquest/hotbackup.py post$", cfg, re.M)
    # tools/publish_beta.py (and publish_dev.py) copy config.yaml and only change name, slug, version, port …
    sys.path.insert(0, str(root / "tools"))
    import publish_beta
    monkeypatch.setattr(publish_beta, "ROOT", tmp_path)
    (tmp_path / "family_quest").mkdir()
    (tmp_path / "family_quest" / "config.yaml").write_text(cfg, encoding="utf-8")
    (tmp_path / "family_quest" / "CHANGELOG.md").write_text("# Changelog\n\n", encoding="utf-8")
    icons = tmp_path / "icons"
    icons.mkdir()
    for i in ("icon.png", "logo.png"):
        (icons / i).write_bytes(b"x")

    def fake_run(cmd, **kw):
        out = b"family_quest/config.yaml\0family_quest/CHANGELOG.md\0" if "ls-files" in cmd else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out if kw.get("text") is not True else "", stderr="")
    monkeypatch.setattr(publish_beta.subprocess, "run", fake_run)
    for slug in ("family_quest_beta", "family_quest_dev"):
        publish_beta.publish(slug, "X", "BETA", 8098, icons, "9.9.9-beta.1", ["x"])
        out = (tmp_path / slug / "config.yaml").read_text(encoding="utf-8")
        for line in ("backup: hot", "backup_pre: python3 /app/familyquest/hotbackup.py pre",
                     "backup_post: python3 /app/familyquest/hotbackup.py post"):
            assert re.search("^" + re.escape(line) + "$", out, re.M), (slug, line)
