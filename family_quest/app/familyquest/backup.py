"""Backup and restore: everything of Family Quest in one ZIP file.

Contents: manifest.json, family_quest.db (consistent copy via the SQLite backup API – profiles, learning
progress, points, chores, Family Planer data, packs, settings), media/ (pictures and audio of packs) and
family_planer/ (uploaded photos). The signing key (secret.key) is not part of it, so a backup cannot be used
to log in somewhere else; after a restore on the same installation everybody stays logged in.

Only what cannot be made again goes in: the pictures of the packs that come with the app (built-in / share folder)
are left out – the app copies them again after a restore; photos taken from Home Assistant Media are only
referenced (they belong to Home Assistant's own backup); the database copy is compacted (VACUUM).
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
MAX_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024    # everything in the backup, unpacked
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
        dst.execute("VACUUM")                    # without the free pages of deleted rows
        skip = {f"media/{r[0]}" for r in dst.execute("SELECT id FROM pack WHERE source IN ('builtin','share')")}
        dst.close()
        counts = _counts(copy)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copy, "family_quest.db")
            for d in FILE_DIRS:
                base = data_dir / d
                if base.is_dir():
                    for f in base.rglob("*"):
                        name = f"{d}/{f.relative_to(base).as_posix()}"
                        if f.is_file() and not any(name.startswith(s + "/") for s in skip):
                            z.write(f, name)
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
    if sum(i.file_size for i in z.infolist()) > MAX_UNPACKED_BYTES:          # a «zip bomb»: refused before unpacking
        raise BackupError("backup file too large")
    return manifest


SAFETY_FILE = "before-restore.zip"        # the data before the last restore – in the data folder, one copy


def check(raw: bytes, current_version: str = "") -> dict:
    """Everything a restore needs, tried out first on a copy: the file, the database (not damaged, a Family Quest
    database), its version – and for an older backup the update to the current version. Returns the manifest plus
    "compat": {"status": same | older, "schema", "current", "from", "to"}. Raises BackupError if it cannot work."""
    from .db import MIGRATIONS, Database
    manifest = inspect(raw)
    z = zipfile.ZipFile(io.BytesIO(raw))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "check.db"
        path.write_bytes(z.read("family_quest.db"))
        c = sqlite3.connect(path)
        try:
            if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupError("the database in the backup is damaged")
            if not c.execute("SELECT name FROM sqlite_master WHERE name='profile'").fetchone():
                raise BackupError("not a Family Quest backup")
            ver = c.execute("PRAGMA user_version").fetchone()[0]
        finally:
            c.close()
        if ver > len(MIGRATIONS):
            raise BackupError("the backup comes from a newer version of Family Quest – update the app first")
        if ver < len(MIGRATIONS):                # older: try the update to the current version on the copy
            try:
                db = Database(path)
                db.val("SELECT COUNT(*) FROM profile")
                db.val("SELECT COUNT(*) FROM ledger")
                db.conn.close()
            except Exception as e:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).warning("older backup cannot be migrated: %s", e)
                raise BackupError("this older backup cannot be updated to the current version") from None
    manifest["compat"] = {"status": "older" if ver < len(MIGRATIONS) else "same", "schema": ver, "current": len(MIGRATIONS),
                          "from": manifest.get("app_version") or "?", "to": current_version or "?"}
    return manifest


def restore(fq, raw: bytes) -> dict:
    """Replace all data with the backup. The caller stops and restarts the planner around this.
    First the backup is checked (an older one is updated on a copy), then the current data are saved as
    before-restore.zip in the data folder – only then the data are replaced."""
    manifest = check(raw, fq.settings.version)
    try:
        safety, _name = create(fq)
        (fq.settings.data_dir / SAFETY_FILE).write_bytes(safety)
        manifest["safety"] = SAFETY_FILE
    except Exception:  # noqa: BLE001 – no safety copy (e.g. disk full): the restore itself still works
        manifest["safety"] = None
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
    fq.db.migrate_logins()                      # … and the explicit sign-in of each profile
    for d in FILE_DIRS:
        target = data_dir / d
        shutil.rmtree(target, ignore_errors=True)
        for n in z.namelist():
            if n.startswith(d + "/") and not n.endswith("/"):
                out = data_dir / n
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(n))
    fq.packs.invalidate()
    if fq.db.q1("SELECT 1 FROM setting WHERE key='xp_items_from'") is None:   # a backup from before the XP items:
        fq.db.set_setting("xp_items_from", int(fq.db.val("SELECT MAX(id) FROM ledger", default=0) or 0))  # old XP stay old
    from .rewards import avatar as av
    av.set_overrides(fq.db.get_setting("shop_items", {}))      # the shop as in the backup
    try:                                        # the pictures of the built-in packs come from the app again
        fq.packs.sync_folders(fq.settings.packs_dirs)
    except Exception:  # noqa: BLE001
        pass
    return manifest


def sizes(fq) -> dict:
    """What takes how much room (bytes) – shown in the parent area next to «Download backup»."""
    data_dir: Path = fq.settings.data_dir
    builtin = {r["id"] for r in fq.db.q("SELECT id FROM pack WHERE source IN ('builtin','share')")}
    out = {"database": 0, "pack_pictures": 0, "photo_sets": 0, "planner_photos": 0, "app_pictures": 0}
    try:
        out["database"] = int(fq.db.val("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()", default=0) or 0)
        out["database"] -= int(fq.db.val("SELECT freelist_count * page_size FROM pragma_freelist_count(), pragma_page_size()", default=0) or 0)
    except Exception:  # noqa: BLE001
        pass
    def size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0
    media = data_dir / "media"
    if media.is_dir():
        for sub in media.iterdir():
            n = size(sub)
            if sub.name == "_memory":
                out["photo_sets"] += n
            elif sub.name in builtin:
                out["app_pictures"] += n
            else:
                out["pack_pictures"] += n
    out["planner_photos"] = size(data_dir / "family_planer")
    out["backup"] = out["database"] + out["pack_pictures"] + out["photo_sets"] + out["planner_photos"]
    return out
