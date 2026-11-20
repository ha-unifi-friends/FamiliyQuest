"""Review 2: restores that cannot plant database code or leave dangling rows, a broken ZIP that changes nothing, privacy
snapshots (database only, few and short-lived), the ledger fold per event (facts stay the same), writes refused during
a hot-backup pause, and no database write on the event loop."""
import asyncio
import io
import json
import os
import sqlite3
import tempfile
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from familyquest import backup, db as dbmod, privacy
from test_backup_kinds import _download, _family, _restore


def _with_db(raw: bytes, change) -> bytes:
    """The backup with its database changed by `change(conn)`."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.db"
        p.write_bytes(z.read("family_quest.db"))
        c = sqlite3.connect(p)
        change(c)
        c.commit()
        c.close()
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as o:
            for n in z.namelist():
                o.writestr(n, p.read_bytes() if n == "family_quest.db" else z.read(n))
    return out.getvalue()


def _plant(c):
    c.execute("CREATE TRIGGER evil AFTER INSERT ON login_log BEGIN "
              "INSERT OR REPLACE INTO setting(key, value) VALUES('ha_integration', '\"EVIL\"'); END")


def test_a_backup_with_a_trigger_is_refused(client):
    """H3: database code in a backup (a trigger that rewrites settings later) – refused before anything changes."""
    h, mia, leo = _family(client)
    fq = client.app.state.fq
    raw = _with_db(_download(client, h, "full"), _plant)
    r = client.post("/api/parent/backup/inspect", files={"file": ("b.zip", raw, "application/zip")}, headers=h)
    assert r.status_code == 400 and "database code" in r.json()["detail"]
    r = client.post("/api/parent/restore", files={"file": ("b.zip", raw, "application/zip")}, headers=h)
    assert r.status_code == 400
    assert not fq.db.q1("SELECT 1 FROM sqlite_master WHERE type='trigger'")
    raw = _with_db(_download(client, h, "full"), lambda c: c.execute("CREATE VIEW v AS SELECT * FROM profile"))
    with pytest.raises(backup.BackupError):
        backup.check(raw)


def test_a_full_restore_drops_what_is_not_family_quests(client, monkeypatch):
    """H3: should a trigger get past the check, a full restore still removes every trigger, view, index and table that
    is not part of the app's schema."""
    h, mia, leo = _family(client)
    fq = client.app.state.fq

    def plant_more(c):
        _plant(c)
        c.execute("CREATE VIEW spy AS SELECT pin_hash FROM profile")
        c.execute("CREATE TABLE extra(x)")
        c.execute("CREATE INDEX extra_x ON extra(x)")
    raw = _with_db(_download(client, h, "full"), plant_more)
    real = backup.check
    monkeypatch.setattr(backup, "check", lambda raw_, *a, **k: real(_with_db(raw_, lambda c: [c.execute(f"DROP {t} {n}") for t, n in (("TRIGGER", "evil"), ("VIEW", "spy"))]), *a, **k))
    out = _restore(client, h, raw)
    assert set(out["report"]["removed"]) == {"trigger evil", "view spy", "index extra_x", "table extra"}
    assert not fq.db.q1("SELECT 1 FROM sqlite_master WHERE name IN ('evil','spy','extra','extra_x')")
    assert client.post("/api/parent/login", json={"pin": "0000"}).status_code == 403     # a failed login (login_log)
    assert fq.db.get_setting("ha_integration") == {"enabled": True, "token_hash": "aa", "instance": "x"}


def test_partial_restores_leave_no_dangling_rows(client):
    """M3 (security) / M4 (architecture): reading progress of a book that is not here is not restored (data), a
    customizing restore that replaces the books deletes the progress of books that are gone – reported."""
    h, mia, leo = _family(client)
    fq = client.app.state.fq
    s1 = fq.db.x("INSERT INTO story(id, title, author_id, data) VALUES(501, 'Buch A', ?, '{}')", mia)
    fq.db.x("INSERT INTO story_read(story_id, profile_id) VALUES(?, ?)", s1, mia)
    data = _download(client, h, "data")
    custom = _download(client, h, "customizing")
    # here the book is gone: a data restore skips its reading progress
    fq.db.x("DELETE FROM story_read")
    fq.db.x("DELETE FROM story WHERE id=501")
    out = _restore(client, h, data)
    assert fq.db.val("SELECT COUNT(*) FROM story_read") == 0
    assert out["report"]["orphans"] == {}
    # the book is back with progress; a customizing backup without it replaces the books → its progress goes too
    fq.db.x("INSERT INTO story(id, title, author_id, data) VALUES(502, 'Buch B', ?, '{}')", mia)
    fq.db.x("INSERT INTO story_read(story_id, profile_id) VALUES(502, ?)", mia)
    out = _restore(client, h, custom)
    assert fq.db.val("SELECT COUNT(*) FROM story_read WHERE story_id=502") == 0
    assert out["report"]["orphans"].get("story_read") == 1
    assert fq.db.q("PRAGMA foreign_key_check") == []


def test_a_broken_zip_entry_changes_nothing(client):
    """L1: a damaged file in the backup is found before the database or a folder is touched."""
    h, mia, leo = _family(client)
    fq = client.app.state.fq
    raw = bytearray(_download(client, h, "full"))
    z = zipfile.ZipFile(io.BytesIO(bytes(raw)))
    info = z.getinfo("media/own/bild.png")
    off = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    raw[off] ^= 0xFF                                         # one byte of the stored picture: CRC error
    fq.db.x("UPDATE profile SET name='Mia neu' WHERE id=?", mia)
    (fq.settings.media_dir / "_memory").mkdir(parents=True, exist_ok=True)
    (fq.settings.media_dir / "_memory" / "keep.txt").write_text("x")
    with pytest.raises(backup.BackupError):
        backup.inspect(bytes(raw))
    r = client.post("/api/parent/restore", files={"file": ("b.zip", bytes(raw), "application/zip")}, headers=h)
    assert r.status_code == 400 and r.json()["detail"] == "the backup file is damaged"
    assert fq.db.val("SELECT name FROM profile WHERE id=?", mia) == "Mia neu"
    assert (fq.settings.media_dir / "_memory" / "keep.txt").exists()
    assert not any(p.name.startswith(".restore-") for p in fq.settings.data_dir.iterdir())


def test_restore_and_privacy_run_wait_for_a_hot_backup(client):
    """M1 (architecture): while Home Assistant's backup pauses the writes, no restore and no clean-up starts."""
    h, mia, leo = _family(client)
    fq = client.app.state.fq
    raw = _download(client, h, "full")
    fq.db._pause_until = time.time() + 30
    try:
        with pytest.raises(backup.BackupError):
            backup.restore(fq, raw)
        fq.db._pause_until = 0                                     # (the settings write must not wait)
        privacy.save_settings(fq.db, {"enabled": True})
        fq.db._pause_until = time.time() + 30
        with pytest.raises(privacy.Busy):
            privacy.run(fq, ["login_log"])
    finally:
        fq.db._release_pause()


def test_privacy_snapshots_are_small_few_and_short_lived(fq, tmp_path):
    """M4: a snapshot holds the database only (no photos), at most 3 stay, none older than 30 days – and restoring
    such a snapshot leaves the photo folders alone."""
    (fq.settings.media_dir / "_memory").mkdir(parents=True, exist_ok=True)
    (fq.settings.media_dir / "_memory" / "foto.jpg").write_bytes(b"JPG" * 1000)
    names = [privacy.snapshot(fq) for _ in range(5)]
    folder = fq.settings.data_dir / privacy.BACKUP_DIR
    left = sorted(p.name for p in folder.iterdir())
    assert len(left) == privacy.KEEP_BACKUPS and names[-1] in left
    z = zipfile.ZipFile(folder / names[-1])
    assert not [n for n in z.namelist() if n.startswith("media/")]
    assert json.loads(z.read("manifest.json"))["files"] is False
    old = folder / left[0]
    t = time.time() - (privacy.SNAPSHOT_DAYS + 1) * 86400
    os.utime(old, (t, t))
    assert privacy.prune_snapshots(fq) == [old.name] and not old.exists()
    backup.restore(fq, (folder / names[-1]).read_bytes())
    assert (fq.settings.media_dir / "_memory" / "foto.jpg").exists()


def test_ledger_fold_keeps_the_family_facts(fq, kid):
    """M3 (architecture): the fold keeps every event – the facts counted from the ledger (slot machine spins and the
    biggest win, shop purchases and coins spent, chores) are the same before and after a clean-up."""
    from familyquest.facts import Facts
    db = fq.db
    leo = db.x("INSERT INTO profile(name) VALUES('Leo')")
    old = (date.today() - timedelta(days=500)).isoformat() + " 10:00:00"
    rows = [(kid, "coins", -2, "slots_bet"), (kid, "coins", -2, "slots_bet"), (kid, "coins", -2, "slots_bet"),
            (kid, "coins", 30, "slots_win"), (kid, "coins", 5, "slots_win"), (leo, "coins", -2, "slots_bet"),
            (leo, "coins", 12, "slots_win"), (kid, "coins", -40, "redeem"), (kid, "coins", -15, "avatar"),
            (leo, "coins", -20, "redeem"), (kid, "coins", 40, "refund"), (leo, "coins", -7, "prank_buy"),
            (kid, "coins", 10, "chore_done"), (kid, "coins", 10, "chore_done"), (leo, "coins", 10, "chore_done"),
            (kid, "xp", 25, "lesson_done"), (kid, "coins", 50, "parent")]
    for i, (pid, acc, amt, ev) in enumerate(rows):
        db.x("INSERT INTO ledger(profile_id, account, amount, event, reason, ref, at) VALUES(?,?,?,?,?,?,?)",
             pid, acc, amt, ev, ev, f"r{i}", old)
    db.x("INSERT INTO ledger(profile_id, account, amount, event, ref) VALUES(?, 'coins', -2, 'slots_bet', 'new')", kid)
    db.set_setting("family_visibility", "all")

    def facts():
        f = Facts(fq)
        gens = {}
        for q in f.records() + f.shop() + f.chores():
            gens[q["gen"]] = q.get("right", q.get("answer"))
        return gens, {p: fq.rewards.balance(p, "coins") for p in (kid, leo)}

    before = facts()
    privacy.save_settings(db, {"enabled": True, "retention": {"ledger": {"n": 1, "unit": "years"}}})
    assert privacy.purge(fq, "ledger") == len(rows)
    assert db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE 'carry:%'") < len(rows)
    after = facts()
    assert after == before
    assert {"slots_spins", "slots_jackpot", "shop_items", "shop_coins", "chores_champion"} <= set(before[0]), before[0]


def test_a_database_write_on_the_event_loop_is_caught(fq):
    """H1 (architecture): the debug guard (on in the tests) – a write on the event loop thread fails, the same write
    through asyncio.to_thread passes."""
    assert dbmod.LOOP_GUARD == "raise"

    async def on_loop():
        fq.db.x("INSERT INTO login_log(kind, ok) VALUES('profile', 1)")

    async def in_thread():
        await asyncio.to_thread(fq.db.x, "INSERT INTO login_log(kind, ok) VALUES('profile', 1)")
    with pytest.raises(RuntimeError, match="event loop"):
        asyncio.run(on_loop())
    asyncio.run(in_thread())
    assert fq.db.q1("SELECT 1 FROM login_log")                      # reading on the loop is fine


def test_indexes_for_running_tables_and_the_ledger(fq):
    """H2 (architecture): the running-table lookups of every game and the ledger by time use an index."""
    plan = lambda sql, *a: " ".join(r["detail"] for r in fq.db.q("EXPLAIN QUERY PLAN " + sql, *a))   # noqa: E731
    assert "card_game_open" in plan("SELECT id FROM card_game WHERE kind=? AND status!='done' AND solo=0", "jump")
    assert "card_game_open" in plan("SELECT id FROM card_game WHERE kind=? AND status!='done' AND solo=1 AND host_id=?", "jump", 2)
    assert "card_game_done" in plan("SELECT id FROM card_game WHERE kind=? AND status='done' ORDER BY finished_at DESC", "jump")
    assert "ledger_at" in plan("SELECT COUNT(*) FROM ledger WHERE at < ?", "2026-01-01")


def test_analytics_date_filter_uses_the_column_itself(fq, kid):
    """M6 (architecture): the period compares the date column itself (an index can be used) – same rows as before,
    the last day included."""
    from familyquest import analytics
    spec = analytics.clean_spec({"dataset": "ledger", "data": [], "from": "2026-03-01", "to": "2026-03-31"})
    sql, args = analytics.build_sql(spec, date(2026, 4, 2))
    assert "substr(" not in sql and args[:2] == ["2026-03-01", "2026-04-01"]
    for at in ("2026-02-28 23:59:59", "2026-03-01 00:00:00", "2026-03-31 23:59:59", "2026-04-01 00:00:00"):
        fq.db.x("INSERT INTO ledger(profile_id, account, amount, event, at) VALUES(?, 'coins', 1, 'parent', ?)", kid, at)
    n = fq.db.val(f"SELECT COUNT(*) FROM ledger l WHERE l.at >= ? AND l.at < ?", *args[:2])
    assert n == 2
