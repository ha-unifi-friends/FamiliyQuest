"""Backup and restore: three kinds of backup, one restore.

A backup is a ZIP file: manifest.json, family_quest.db (consistent copy via the SQLite backup API, compacted) and the
file folders that belong to its kind. The kind is in the manifest (`kind`: full | data | customizing); older backups
without it are full backups.

- full: everything, as before.
- data: what the family *did* – ledger, XP, learning progress, games played, chores done, deals, redemptions,
  weather, logs, the planner's lists … No settings, no profiles (their ids and names are in the manifest, so a restore
  can match them), no own content.
- customizing: everything that is *set up* – settings, profiles (PIN hashes, avatars, login modes, HA user links) and
  the family's own content (packs, quizzes, books and adventure games, photo sets, shop, rewards, chores, designs,
  texts, the crest …). No usage data. Made to set up a dev/beta installation like the real one, without the data.

Which table and which setting belongs to which kind is decided in ONE place: TABLES and SETTINGS below
(tests/test_backup_kinds.py fails when a table, a migration or a setting key is not classified).

Restore: a full backup replaces the whole database. A data or customizing backup replaces only the tables (and setting
keys) of its kind and leaves the others as they are. Values that belong to *this* installation (ENVIRONMENT – the
Home Assistant panel path, links, tokens …) are never taken from a backup, whatever its kind. Before every restore the
current state is saved as before-restore.zip (a full backup) in the data folder.

The signing key (secret.key) is not part of any backup, so a backup cannot be used to log in somewhere else; after a
restore on the same installation everybody stays logged in. The pictures of the packs that come with the app
(built-in / share folder) are left out – the app copies them again after a restore; photos taken from Home Assistant
Media are only referenced (they belong to Home Assistant's own backup).
"""
from __future__ import annotations

import functools
import io
import json
import shutil
import sqlite3
import tempfile
import time
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

FORMAT = "family-quest-backup"
MAX_RESTORE_BYTES = 500 * 1024 * 1024
MAX_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024    # everything in the backup, unpacked
SAFETY_FILE = "before-restore.zip"             # the data before the last restore – in the data folder, one copy

FULL, DATA, CUSTOM = "full", "data", "customizing"
KINDS = (FULL, DATA, CUSTOM)
ENV = "environment"                            # belongs to this installation: never taken from a backup


class BackupError(ValueError):
    pass


# ================================================================ the classification (one place)
# Every table of the database: (kind, owner columns, parent).
#   kind    DATA or CUSTOM.
#   owners  (data tables) columns holding the profile the row belongs to – on a data restore rows of a profile that
#           does not exist here are skipped (and reported). NULL is fine (e.g. a guest, «the family»).
#   parent  (data tables) (column, table): the row belongs to a row of that table and is skipped with it.
TABLES: dict[str, tuple[str, tuple[str, ...], tuple[str, str] | None]] = {
    # ---- customizing: profiles, configuration and the family's own content
    "profile": (CUSTOM, (), None),             # user accounts: PIN hashes, avatars, login modes, HA user links
    "setting": (CUSTOM, (), None),             # split per key: SETTINGS below
    "account": (CUSTOM, (), None),             # the currencies (coins, XP …)
    "rule": (CUSTOM, (), None),                # how many points an activity gives
    "reward": (CUSTOM, (), None),              # the shop's rewards
    "chore": (CUSTOM, (), None),               # chore definitions (the done chores are chore_task)
    "goal": (CUSTOM, (), None),                # weekly goals and the family goal set by the parents
    "pack": (CUSTOM, (), None),                # learning packs (own, imported, AI, built-in)
    "pack_profile": (CUSTOM, (), None),        # which child has which pack
    "quiz": (CUSTOM, (), None),                # own family quizzes
    "story": (CUSTOM, (), None),               # books and adventure games (own games)
    "codelab_project": (CUSTOM, (), None),     # games made in the code workshop (own games)
    "bot": (CUSTOM, (), None),                 # own game bots (name, look, level)
    # ---- data: what the family did
    "ledger": (DATA, ("profile_id",), None),   # points, coins, XP – balances are summed from it
    "daily": (DATA, ("profile_id",), None),    # XP / learning time per day (written with the ledger)
    "xp_spent": (DATA, ("profile_id",), None),
    "item_state": (DATA, ("profile_id",), None),     # learning progress per card
    "attempt": (DATA, ("profile_id",), None),
    "session": (DATA, ("profile_id",), None),
    "badge": (DATA, ("profile_id",), None),
    "unlock": (DATA, ("profile_id",), None),          # bought / unlocked avatar items
    "redemption": (DATA, ("profile_id",), None),      # reward redemptions
    "chore_task": (DATA, ("profile_id",), None),      # chores done
    "chore_seen": (DATA, ("profile_id",), None),
    "deal": (DATA, ("a_id", "b_id"), None),           # deals between family members
    "deal_msg": (DATA, (), ("deal_id", "deal")),
    "deal_seen": (DATA, ("profile_id",), ("deal_id", "deal")),
    "deal_hold": (DATA, ("profile_id",), ("deal_id", "deal")),
    "deal_pay": (DATA, (), None),
    "weather_log": (DATA, ("profile_id",), None),     # behaviour weather history
    "login_log": (DATA, (), None),
    "history": (DATA, ("profile_id",), None),
    "internet_session": (DATA, ("profile_id",), None),
    "internet_allowance": (DATA, ("profile_id",), None),
    "play_minute": (DATA, ("profile_id",), None),
    "game_pass": (DATA, ("profile_id",), None),
    "battery": (DATA, ("profile_id",), None),
    "battery_log": (DATA, ("profile_id",), None),
    "pet": (DATA, ("profile_id",), None),
    "pet_item": (DATA, (), ("pet_id", "pet")),
    "prank": (DATA, ("to_id",), None),
    "prank_stock": (DATA, ("profile_id",), None),
    "prank_charge": (DATA, ("profile_id",), None),
    "deck": (DATA, ("profile_id",), None),            # a child's own flash cards – with its learning state
    "deck_card": (DATA, (), ("deck_id", "deck")),
    "story_read": (DATA, ("profile_id",), ("story_id", "story")),   # reading progress of the books (of books here)
    "codelab_progress": (DATA, ("profile_id",), None),
    "kv": (DATA, (), None),                           # the Family Planer (lists, week, its points)
    "family_event": (DATA, (), None),                 # the family calendar
    "ft_game": (DATA, (), None),
    "ft_wish": (DATA, ("profile_id",), None),
    "ft_vote": (DATA, ("profile_id",), None),
    "quiz_game": (DATA, (), None),                    # games played (results and history)
    "quiz_answer": (DATA, ("profile_id",), ("game_id", "quiz_game")),
    "bingo_game": (DATA, (), None),
    "bingo_card": (DATA, ("profile_id",), ("game_id", "bingo_game")),
    "poker_game": (DATA, (), None),
    "card_game": (DATA, (), None),
    "song_game": (DATA, (), None),
    "council_topic": (DATA, (), None),
    "council_proposal": (DATA, (), ("topic_id", "council_topic")),
    "council_vote": (DATA, ("profile_id",), ("topic_id", "council_topic")),
    "poll": (DATA, (), None),
    "poll_option": (DATA, (), ("poll_id", "poll")),
    "poll_vote": (DATA, ("profile_id",), ("poll_id", "poll")),
    "board": (DATA, (), None),                        # bulletin boards and their notes
    "board_item": (DATA, (), ("board_id", "board")),
    "board_seen": (DATA, ("profile_id",), ("board_id", "board")),
    "wichtel": (DATA, (), None),                      # secret gift giving rounds
    "privacy_run": (DATA, (), None),                  # log of the privacy clean-up runs
    "ledger_folded": (DATA, ("profile_id",), None),   # bookings folded by a clean-up – goes with the ledger
}
INTERNAL_TABLES = ("sqlite_sequence", "sqlite_stat1", "sqlite_stat4")    # SQLite's own

# Every setting key: DATA, CUSTOM or ENV. Keys ending with «.» are prefixes (game_rules.<game>).
SETTINGS: dict[str, str] = {
    # ---- customizing
    "levels": CUSTOM, "family_visibility": CUSTOM, "sound": CUSTOM, "reminder_time": CUSTOM,
    "notify_service": CUSTOM, "chore_reminder_time": CUSTOM, "family_lang": CUSTOM,
    "planer_points": CUSTOM, "planer_points_factor": CUSTOM, "planer_points_account": CUSTOM,
    "games": CUSTOM, "games_guests": CUSTOM, "quiz_facts": CUSTOM, "game_starter": CUSTOM, "games_profiles": CUSTOM,
    "games_access": CUSTOM, "game_rewards": CUSTOM, "game_rules.": CUSTOM, "lesson_perfect_coins": CUSTOM,
    "parent_ha_only": CUSTOM, "ha_app_login": CUSTOM, "kid_ha_login": CUSTOM,
    "allowed_networks": CUSTOM, "guest_networks": CUSTOM, "parent_networks": CUSTOM,
    "guest_wifi_qr": CUSTOM,                           # the image entity of the guest Wi-Fi QR code (Invite guests)
    "calendar": CUSTOM, "dashboard": CUSTOM,           # dashboard.key: ENVIRONMENT_PARTS
    "translations": CUSTOM, "weather": CUSTOM, "themes": CUSTOM, "battery": CUSTOM,
    "pet_food_cost": CUSTOM, "pet_hotel_cost": CUSTOM, "hamster_coins_per_day": CUSTOM, "pet_shop_currency": CUSTOM,
    "memory": CUSTOM,                                  # photo sets and the family crest
    "familytime_wishes": CUSTOM, "familytime_game_price": CUSTOM, "familytime_vote_hours": CUSTOM,
    "deals": CUSTOM, "stories": CUSTOM, "codelab": CUSTOM, "shop_items": CUSTOM, "pack_rewards": CUSTOM,
    "packs_optional_v1": CUSTOM, "packs_optional_unassign_v1": CUSTOM,
    "analytics_reports": CUSTOM, "analytics_dashboards": CUSTOM,   # analytics: «My reports», dashboards (layout, tiles, period)
    "season_live": CUSTOM,                             # live weather of the season designs (planer seasons.weather: kv)
    "privacy": CUSTOM,                                 # retention periods, master switch, automatic run
    # ---- data
    "jump_best": DATA, "sternlauf_best": DATA, "snack_best": DATA, "verkehr_best": DATA, "klatsch_best": DATA,
    "langstrecke_best": DATA, "langstrecke_pit": DATA, "escape_played": DATA,
    "xp_items_from": DATA,                             # ledger id from which XP count as «new» – goes with the ledger
    "guest_invites": DATA,                             # open guest invitations of running games
    "party": DATA,                                     # the party mode switched on just now (ends by itself)
    # ---- environment: this installation's own values, never taken from a backup
    "ha_panel_path": ENV,                              # /app/<slug> or /hassio/ingress/<slug> of this HA
    "ha_app_login_url": ENV,                           # Home Assistant address for «Sign in with Home Assistant»
    "ha_integration": ENV,                             # token hash and instance of the HA integration
    "ha_integration_poll": ENV,
    "last_backup": ENV,                                # «Last backup» of this installation
}
# parts of a setting that belong to the installation (the rest of the setting follows its kind)
ENVIRONMENT_PARTS: dict[str, tuple[str, ...]] = {"dashboard": ("key",)}       # the kiosk link's key (its password)

# Number of migrations (db.MIGRATIONS) whose tables and settings are classified above – a new migration fails the
# sync guard until somebody checked it and raised this number.
CLASSIFIED_MIGRATIONS = 45

# The file folders in the data folder that go into a backup: folder → kind; media/ with all sub-folders (pack pictures,
# _memory = photo sets, _stories = pictures of the books) – all own content. Nothing else of the data folder is packed:
# not secret.key, options.json, before-restore.zip, restore_upload/ or the privacy snapshots (privacy_backups/).
FILE_DIRS: dict[str, str] = {"media": CUSTOM, "family_planer": DATA}

def table_kind(name: str) -> str | None:
    t = TABLES.get(name)
    return t[0] if t else None


def setting_kind(key: str, default: str | None = CUSTOM) -> str | None:
    """DATA, CUSTOM or ENV of a setting key (`default` for a key that is not classified)."""
    if key in SETTINGS:
        return SETTINGS[key]
    for k, v in SETTINGS.items():
        if k.endswith(".") and key.startswith(k):
            return v
    return default


def kind_of(manifest: dict) -> str:
    k = manifest.get("kind")
    return k if k in KINDS else FULL                 # backups from before the kinds: full


def _ex(c: sqlite3.Connection, sql: str, args: tuple = ()) -> sqlite3.Cursor:
    """Run on a cursor that gives plain tuples (the live connection gives dicts)."""
    cur = c.cursor()
    cur.row_factory = None
    return cur.execute(sql, args)


def _user_tables(c: sqlite3.Connection, schema: str = "main") -> list[str]:
    return [r[0] for r in _ex(c, f"SELECT name FROM {schema}.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


# ================================================================ create
def create(fq, kind: str = FULL, files: bool = True) -> tuple[bytes, str]:
    """Returns (zip bytes, file name). Call after the planner has saved its state. files=False: the database only (the
    privacy snapshots – a clean-up deletes only database rows); a restore of it leaves the file folders as they are."""
    if kind not in KINDS:
        raise BackupError("unknown kind of backup")
    data_dir: Path = fq.settings.data_dir
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "family_quest.db"
        dst = sqlite3.connect(copy)
        with fq.db.lock:
            fq.db.conn.backup(dst)
        profiles = [{"id": r[0], "name": r[1], "role": r[2], "archived": bool(r[3])}
                    for r in dst.execute("SELECT id, name, role, archived FROM profile ORDER BY id")]
        if kind != FULL:
            _strip(dst, kind)
        dst.execute("VACUUM")                    # without the free pages of deleted rows
        skip = {f"media/{r[0]}" for r in dst.execute("SELECT id FROM pack WHERE source IN ('builtin','share')")}
        dst.close()
        counts = _counts(copy)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copy, "family_quest.db")
            for d, dkind in FILE_DIRS.items():
                if kind not in (FULL, dkind) or not files:
                    continue
                base = data_dir / d
                if base.is_dir():
                    for f in base.rglob("*"):
                        name = f"{d}/{f.relative_to(base).as_posix()}"
                        if f.is_file() and not any(name.startswith(s + "/") for s in skip):
                            z.write(f, name)
            z.writestr("manifest.json", json.dumps({
                "format": FORMAT, "version": 2, "kind": kind, "app_version": fq.settings.version,
                "created": datetime.now().isoformat(timespec="seconds"), "counts": counts,
                "profiles": profiles, **({} if files else {"files": False})}, ensure_ascii=False, indent=1))
    middle = "" if kind == FULL else f"{kind}-"
    name = f"family-quest-backup-{middle}{datetime.now():%Y-%m-%d-%H%M}.zip"
    return buf.getvalue(), name


def _strip(c: sqlite3.Connection, kind: str) -> None:
    """Leave only what belongs to `kind` in a copy of the database (the schema stays complete)."""
    for t in _user_tables(c):
        if t == "setting":
            for (key,) in c.execute("SELECT key FROM setting").fetchall():
                if setting_kind(key) != kind:
                    c.execute("DELETE FROM setting WHERE key=?", (key,))
            _strip_env_parts(c)
        elif table_kind(t) != kind:
            c.execute(f'DELETE FROM "{t}"')
    c.commit()


def _strip_env_parts(c: sqlite3.Connection) -> None:
    for key, parts in ENVIRONMENT_PARTS.items():
        row = c.execute("SELECT value FROM setting WHERE key=?", (key,)).fetchone()
        if row:
            v = json.loads(row[0])
            if isinstance(v, dict):
                for p in parts:
                    v.pop(p, None)
                c.execute("UPDATE setting SET value=? WHERE key=?", (json.dumps(v, ensure_ascii=False), key))


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


# ================================================================ check
def inspect(raw: bytes, deep: bool = True) -> dict:
    """Check a backup file and return its manifest (raises BackupError). deep: also read every entry (CRC check)."""
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
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise BackupError("not a Family Quest backup")
    if "kind" in manifest and manifest["kind"] not in KINDS:
        raise BackupError("unknown kind of backup")
    for n in names:
        if n.startswith("/") or ".." in Path(n).parts:
            raise BackupError("invalid path in backup")
    if sum(i.file_size for i in z.infolist()) > MAX_UNPACKED_BYTES:          # a «zip bomb»: refused before unpacking
        raise BackupError("backup file too large")
    if deep:                                     # every entry readable (CRC): a broken one is found before anything changes
        try:
            bad = z.testzip()
        except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, ValueError):
            bad = "?"
        if bad:
            raise BackupError("the backup file is damaged")
    manifest["kind"] = kind_of(manifest)
    return manifest


def check(raw: bytes, current_version: str = "", fq=None) -> dict:
    """Everything a restore needs, tried out first on a copy: the file, the database (not damaged, a Family Quest
    database), its version – and for an older backup the update to the current version. Returns the manifest plus
    "kind", "compat": {"status": same | older, "schema", "current", "from", "to"} and – with `fq` – "plan": what a restore
    replaces and keeps, and how the profiles match. Raises BackupError if it cannot work."""
    from .db import MIGRATIONS, Database
    manifest = inspect(raw)
    z = zipfile.ZipFile(io.BytesIO(raw))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "check.db"
        path.write_bytes(z.read("family_quest.db"))
        c = sqlite3.connect(path)
        try:
            try:
                ok = c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            except sqlite3.DatabaseError:
                ok = False
            if not ok:
                raise BackupError("the database in the backup is damaged")
            if not c.execute("SELECT name FROM sqlite_master WHERE name='profile'").fetchone():
                raise BackupError("not a Family Quest backup")
            # database code (triggers, views) is never part of Family Quest's schema: such a backup was made by hand
            # (a trigger could later rewrite settings or PINs – past the protection of the environment values)
            if c.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
                raise BackupError("the backup contains database code that is not part of Family Quest")
            ver = c.execute("PRAGMA user_version").fetchone()[0]
            if not manifest.get("profiles"):
                manifest["profiles"] = [{"id": r[0], "name": r[1], "role": r[2], "archived": bool(r[3])}
                                        for r in c.execute("SELECT id, name, role, archived FROM profile ORDER BY id")]
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
    if fq is not None:
        manifest["plan"] = plan(fq, manifest)
    return manifest


def plan(fq, manifest: dict) -> dict:
    """What a restore of this backup does here (the parent area names what is replaced and kept per kind): the
    environment values kept, and the profiles:
    matched by id – `missing` (in a data backup, not here: their rows are skipped), `renamed` (same id, other name:
    the rows go to the profile here), `kept` (here, not in a customizing backup: they stay)."""
    kind = kind_of(manifest)
    here = {r["id"]: r for r in fq.db.q("SELECT id, name, role, archived FROM profile")}
    theirs = {int(p["id"]): p for p in manifest.get("profiles") or [] if str(p.get("id", "")).isdecimal()}
    out = {"kind": kind, "environment": environment_keys(),
           "missing": [], "renamed": [], "kept": []}
    if kind in (DATA, CUSTOM):
        for pid, p in sorted(theirs.items()):
            if pid not in here:
                if kind == DATA:
                    out["missing"].append({"id": pid, "name": p.get("name") or "?"})
            elif (here[pid]["name"] or "").strip().casefold() != str(p.get("name") or "").strip().casefold():
                out["renamed"].append({"id": pid, "backup": p.get("name") or "?", "here": here[pid]["name"]})
    if kind == CUSTOM:
        out["kept"] = [{"id": pid, "name": r["name"]} for pid, r in sorted(here.items()) if pid not in theirs]
    return out


def environment_keys() -> list[str]:
    return [k for k, v in SETTINGS.items() if v == ENV] + [f"{k}.{p}" for k, ps in ENVIRONMENT_PARTS.items() for p in ps]


# ================================================================ restore
def _env_snapshot(fq) -> dict:
    out = {"keys": {}, "parts": {}}
    for r in fq.db.q("SELECT key, value FROM setting"):
        if setting_kind(r["key"]) == ENV:
            out["keys"][r["key"]] = r["value"]
    for key, parts in ENVIRONMENT_PARTS.items():
        v = fq.db.get_setting(key)
        out["parts"][key] = {p: (v or {}).get(p) for p in parts} if isinstance(v, dict) else {}
    return out


def _env_apply(conn: sqlite3.Connection, snap: dict) -> None:
    """Put this installation's own values back (after the database was replaced or merged)."""
    for (k,) in _ex(conn, "SELECT key FROM main.setting").fetchall():
        if setting_kind(k) == ENV and k not in snap["keys"]:
            _ex(conn, "DELETE FROM main.setting WHERE key=?", (k,))
    for k, v in snap["keys"].items():
        _ex(conn, "INSERT INTO main.setting(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
    for key, parts in snap["parts"].items():
        row = _ex(conn, "SELECT value FROM main.setting WHERE key=?", (key,)).fetchone()
        if not row:
            continue
        v = json.loads(row[0])
        if not isinstance(v, dict):
            continue
        for p in ENVIRONMENT_PARTS[key]:
            if parts.get(p) is None:
                v.pop(p, None)
            else:
                v[p] = parts[p]
        _ex(conn, "UPDATE main.setting SET value=? WHERE key=?", (json.dumps(v, ensure_ascii=False), key))


def restore(fq, raw: bytes) -> dict:
    """Restore a backup of any kind. The caller stops and restarts the planner around this.
    First the backup is checked (an older one is updated on a copy), then the current data are saved as
    before-restore.zip in the data folder – only then the data are replaced. Returns the manifest with "report":
    {"kind", "skipped": [{"id", "name", "rows"}], "kept": [profiles kept], "renamed": [...], "environment": [keys],
    "orphans": {table: rows deleted that pointed nowhere (data / customizing)}, "removed": [foreign schema objects (full)]}.
    Refused while Home Assistant makes a backup (the writes are paused)."""
    from . import memo
    from .db import Database
    if fq.db.paused():
        raise BackupError("Home Assistant is making a backup right now – try again in a minute")
    manifest = check(raw, fq.settings.version, fq)
    kind = manifest["kind"]
    report = {"kind": kind, "skipped": [], "kept": manifest["plan"]["kept"], "renamed": manifest["plan"]["renamed"],
              "environment": environment_keys(), "orphans": {}, "removed": []}
    try:
        safety, _name = create(fq)
        (fq.settings.data_dir / SAFETY_FILE).write_bytes(safety)
        manifest["safety"] = SAFETY_FILE
    except Exception:  # noqa: BLE001 – no safety copy (e.g. disk full): the restore itself still works
        manifest["safety"] = None
    snap = _env_snapshot(fq)
    z = zipfile.ZipFile(io.BytesIO(raw))
    data_dir: Path = fq.settings.data_dir
    dirs = [d for d, dkind in FILE_DIRS.items() if kind in (FULL, dkind) and manifest.get("files", True) is not False]
    staging = Path(tempfile.mkdtemp(prefix=".restore-", dir=data_dir))     # the same disk: moved into place later
    try:
        try:                                     # the files first – a broken entry stops the restore before the DB changes
            for n in z.namelist():
                if any(n.startswith(d + "/") for d in dirs) and not n.endswith("/"):
                    out = staging / n
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(z.read(n))
        except (zipfile.BadZipFile, zlib.error, EOFError):
            raise BackupError("the backup file is damaged") from None
        with tempfile.TemporaryDirectory() as tmp:
            src_path = Path(tmp) / "restore.db"
            src_path.write_bytes(z.read("family_quest.db"))
            try:
                src_db = Database(src_path)          # an older backup is updated here, on the copy
                src_db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                src_db.conn.execute("PRAGMA journal_mode=DELETE")
                src_db.conn.close()
            except Exception:  # noqa: BLE001
                raise BackupError("this older backup cannot be updated to the current version") from None
            conn = fq.db.conn
            with fq.db.lock:
                if kind == FULL:
                    src = sqlite3.connect(src_path)
                    try:
                        src.backup(conn)             # replaces the whole live database in one step
                    finally:
                        src.close()
                    fq.db.migrate()
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        report["removed"] = _drop_foreign(conn)
                        _env_apply(conn, snap)
                        conn.execute("COMMIT")
                    except BaseException:
                        conn.execute("ROLLBACK")
                        raise
                else:
                    report["skipped"], report["orphans"] = _merge(conn, src_path, kind, snap, manifest)
            memo.clear()
        for d in dirs:                           # the file folders: swapped in (renamed on the same disk)
            target = data_dir / d
            shutil.rmtree(target, ignore_errors=True)
            if (staging / d).exists():
                (staging / d).rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    fq.db.migrate_logins()                      # profiles from before the explicit sign-in get it
    fq.packs.invalidate()
    if kind in (FULL, DATA) and fq.db.q1("SELECT 1 FROM setting WHERE key='xp_items_from'") is None:
        # a backup from before the XP items: old XP stay old
        fq.db.set_setting("xp_items_from", int(fq.db.val("SELECT MAX(id) FROM ledger", default=0) or 0))
    from .rewards import avatar as av
    av.set_overrides(fq.db.get_setting("shop_items", {}))      # the shop as it is now
    if kind in (FULL, CUSTOM):
        try:                                    # the pictures of the built-in packs come from the app again
            fq.packs.sync_folders(fq.settings.packs_dirs)
        except Exception:  # noqa: BLE001
            pass
    manifest["report"] = report
    return manifest


@functools.lru_cache(maxsize=1)
def _app_schema() -> frozenset:
    """(type, name) of everything Family Quest's migrations create."""
    from .db import Database
    db = Database(":memory:")
    try:
        return frozenset((r["type"], r["name"]) for r in db.q("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
    finally:
        db.conn.close()


def _drop_foreign(conn: sqlite3.Connection) -> list[str]:
    """After a full restore: triggers, views, indexes and tables that are not Family Quest's own go (inside the
    transaction of the caller). Returns «type name» of what was removed."""
    app = _app_schema()
    out = []
    rows = _ex(conn, "SELECT type, name FROM main.sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    for typ in ("trigger", "view", "index", "table"):             # dependants first
        for t, name in rows:
            if t == typ and (t, name) not in app:
                conn.execute(f'DROP {typ.upper()} IF EXISTS main."{name.replace(chr(34), chr(34) * 2)}"')
                out.append(f"{t} {name}")
    return out


def _drop_orphans(conn: sqlite3.Connection) -> dict[str, int]:
    """Rows whose foreign key points nowhere after a partial restore (reading progress of a book that is not here, a
    redemption of another reward …) are deleted. Returns {table: rows}."""
    out: dict[str, int] = {}
    for _ in range(10):                                           # a deletion can leave further orphans (cascades are off)
        found: dict[str, set] = {}
        for table, rowid, _parent, _fk in _ex(conn, "PRAGMA main.foreign_key_check").fetchall():
            if rowid is not None:
                found.setdefault(table, set()).add(rowid)
        if not found:
            break
        for table, ids in found.items():
            ids = sorted(ids)
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                conn.execute(f'DELETE FROM main."{table}" WHERE rowid IN ({",".join("?" * len(chunk))})', chunk)
            out[table] = out.get(table, 0) + len(ids)
    return out


def _ordered(tables: list[str]) -> list[str]:
    """Parents before the tables that hang on them."""
    done: list[str] = []
    pending = list(tables)
    while pending:
        for t in list(pending):
            parent = (TABLES.get(t) or (None, (), None))[2]
            if not parent or parent[1] not in pending:
                done.append(t)
                pending.remove(t)
    return done


def _merge(conn: sqlite3.Connection, src_path: Path, kind: str, snap: dict, manifest: dict) -> tuple[list[dict], dict]:
    """Replace the tables and settings of `kind` with those of the backup, in one transaction. Data rows of profiles
    that do not exist here are skipped (returned per profile); profiles here that are not in a customizing backup stay."""
    names = {int(p["id"]): p.get("name") for p in manifest.get("profiles") or [] if str(p.get("id", "")).isdecimal()}
    skipped: dict[int, int] = {}
    conn.execute("PRAGMA foreign_keys=OFF")     # profiles are replaced: no cascade into the data (outside a transaction)
    conn.execute("ATTACH DATABASE ? AS src", (str(src_path),))
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            live = _user_tables(conn)
            theirs = set(_user_tables(conn, "src"))
            if kind == CUSTOM:                   # profiles here that the backup does not know stay – with their data
                conn.execute("CREATE TEMP TABLE fq_keep AS SELECT * FROM main.profile WHERE id NOT IN (SELECT id FROM src.profile)")
                conn.execute("CREATE TEMP TABLE fq_keep_pp AS SELECT * FROM main.pack_profile WHERE profile_id IN (SELECT id FROM temp.fq_keep)")
            for t in _ordered([t for t in live if t in theirs]):
                cols = [r[1] for r in _ex(conn, f'PRAGMA main.table_info("{t}")')]
                src_cols = {r[1] for r in _ex(conn, f'PRAGMA src.table_info("{t}")')}
                cl = ", ".join(f'"{c}"' for c in cols if c in src_cols)
                if t == "setting":
                    for (key,) in _ex(conn, "SELECT key FROM main.setting").fetchall():
                        if setting_kind(key) == kind:
                            conn.execute("DELETE FROM main.setting WHERE key=?", (key,))
                    for k, v in _ex(conn, "SELECT key, value FROM src.setting").fetchall():
                        if setting_kind(k) == kind:
                            conn.execute("INSERT INTO main.setting(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
                    continue
                if table_kind(t) != kind:
                    continue
                if kind == CUSTOM:
                    conn.execute(f'DELETE FROM main."{t}"')
                    conn.execute(f'INSERT INTO main."{t}"({cl}) SELECT {cl} FROM src."{t}"')
                    continue
                # a data table: rows of profiles that are not here are skipped
                _k, owners, parent = TABLES[t]
                cond = []
                for o in owners:
                    if o in src_cols:
                        cond.append(f'("{o}" IS NULL OR "{o}" IN (SELECT id FROM main.profile))')
                        for pid, n in _ex(conn, f'SELECT "{o}", COUNT(*) FROM src."{t}" WHERE "{o}" IS NOT NULL AND "{o}" NOT IN (SELECT id FROM main.profile) GROUP BY "{o}"').fetchall():
                            skipped[pid] = skipped.get(pid, 0) + n
                if parent and parent[0] in src_cols:
                    cond.append(f'"{parent[0]}" IN (SELECT id FROM main."{parent[1]}")')
                where = (" WHERE " + " AND ".join(cond)) if cond else ""
                conn.execute(f'DELETE FROM main."{t}"')
                conn.execute(f'INSERT INTO main."{t}"({cl}) SELECT {cl} FROM src."{t}"{where}')
            if kind == CUSTOM:
                conn.execute("INSERT INTO main.profile SELECT * FROM temp.fq_keep")
                conn.execute("INSERT OR IGNORE INTO main.pack_profile SELECT * FROM temp.fq_keep_pp WHERE pack_id IN (SELECT id FROM main.pack)")
            orphans = _drop_orphans(conn)       # the foreign keys were off: nothing may point nowhere now
            _env_apply(conn, snap)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        for sql in ("DROP TABLE IF EXISTS temp.fq_keep", "DROP TABLE IF EXISTS temp.fq_keep_pp", "DETACH DATABASE src",
                    "PRAGMA foreign_keys=ON"):
            try:                                 # never hide the error of the restore itself
                conn.execute(sql)
            except sqlite3.Error:
                pass
    return [{"id": pid, "name": names.get(pid) or "?", "rows": n} for pid, n in sorted(skipped.items())], orphans


# ================================================================ sizes
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
