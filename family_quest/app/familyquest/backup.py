"""Backup and restore: everything of Family Quest in one ZIP file.

Contents: manifest.json, family_quest.db (consistent copy via the SQLite backup API – profiles, learning
progress, points, chores, Family Planer data, packs, settings), media/ (pictures and audio of packs) and
family_planer/ (uploaded photos). The signing key (secret.key) is not part of it, so a backup cannot be used
to log in somewhere else; after a restore on the same installation everybody stays logged in.
"""
from __future__ import annotations

import io
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

FORMAT = "family-quest-backup"
MAX_RESTORE_BYTES = 500 * 1024 * 1024
FILE_DIRS = ("media", "family_planer")


class BackupError(ValueError):
    pass


def create(fq) -> tuple[bytes, str]:
    """Returns (zip bytes, file name). Call after the planner has saved its state."""
    data_dir: Path = fq.settings.data_dir
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "family_quest.db"
        dst = sqlite3.connect(copy)
        with fq.db.lock:
            fq.db.conn.backup(dst)
        dst.close()
        counts = _counts(copy)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copy, "family_quest.db")
            for d in FILE_DIRS:
                base = data_dir / d
                if base.is_dir():
                    for f in base.rglob("*"):
                        if f.is_file():
                            z.write(f, f"{d}/{f.relative_to(base).as_posix()}")
            z.writestr("manifest.json", json.dumps({
                "format": FORMAT, "version": 1, "app_version": fq.settings.version,
                "created": datetime.now().isoformat(timespec="seconds"), "counts": counts}, ensure_ascii=False, indent=1))
    name = f"family-quest-backup-{datetime.now():%Y-%m-%d-%H%M}.zip"
    return buf.getvalue(), name


def _counts(db_path: Path) -> dict:
    c = sqlite3.connect(db_path)
    out = {}
    for t in ("profile", "pack", "ledger", "item_state", "chore", "kv"):
        try:
            out[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.Error:
            pass
    c.close()
    return out


def inspect(raw: bytes) -> dict:
    """Check a backup file and return its manifest (raises BackupError)."""
    if len(raw) > MAX_RESTORE_BYTES:
        raise BackupError("backup file too large")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise BackupError("not a Family Quest backup") from None
    names = set(z.namelist())
    if "manifest.json" not in names or "family_quest.db" not in names:
        raise BackupError("not a Family Quest backup")
    try:
        manifest = json.loads(z.read("manifest.json"))
    except ValueError:
        raise BackupError("not a Family Quest backup") from None
    if manifest.get("format") != FORMAT:
        raise BackupError("not a Family Quest backup")
    for n in names:
        if n.startswith("/") or ".." in Path(n).parts:
            raise BackupError("invalid path in backup")
    return manifest


def restore(fq, raw: bytes) -> dict:
    """Replace all data with the backup. The caller stops and restarts the planner around this."""
    manifest = inspect(raw)
    z = zipfile.ZipFile(io.BytesIO(raw))
    data_dir: Path = fq.settings.data_dir
    with tempfile.TemporaryDirectory() as tmp:
        src_path = Path(tmp) / "restore.db"
        src_path.write_bytes(z.read("family_quest.db"))
        src = sqlite3.connect(src_path)
        try:
            if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupError("the database in the backup is damaged")
            if not src.execute("SELECT name FROM sqlite_master WHERE name='profile'").fetchone():
                raise BackupError("not a Family Quest backup")
            ver = src.execute("PRAGMA user_version").fetchone()[0]
            from .db import MIGRATIONS
            if ver > len(MIGRATIONS):
                raise BackupError("the backup comes from a newer version of Family Quest – update the app first")
            with fq.db.lock:
                src.backup(fq.db.conn)          # replaces the whole live database in one step
        finally:
            src.close()
    fq.db.migrate()                             # older backups get the newer tables
    for d in FILE_DIRS:
        target = data_dir / d
        shutil.rmtree(target, ignore_errors=True)
        for n in z.namelist():
            if n.startswith(d + "/") and not n.endswith("/"):
                out = data_dir / n
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(n))
    fq.packs.invalidate()
    return manifest
