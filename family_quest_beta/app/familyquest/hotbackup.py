"""Consistent hot backups by Home Assistant (config.yaml: `backup: hot`, `backup_pre`, `backup_post`).

The Supervisor runs `backup_pre` inside the app's container before it copies /data, and `backup_post` afterwards:

    python3 /app/familyquest/hotbackup.py pre     # pause the writes, checkpoint SQLite: the database file is complete
    python3 /app/familyquest/hotbackup.py post    # writes go on

pre writes the flag file /data/.backup-pause ({"token", "until"}). The app (db.py, Database.start_backup_watch) sees it
within a fraction of a second, lets the running write finish, stops new writes, runs
`PRAGMA wal_checkpoint(TRUNCATE)` (everything is in family_quest.db, the WAL is empty) and answers with
/data/.backup-paused. Reading goes on as usual. pre waits for that answer; when the app does not run, it checkpoints
the database itself. post removes the flag. The pause never lasts longer than PAUSE_MAX (2 minutes) – also when post
never comes – so the app never hangs; a flag older than that (e.g. one that came back with a restore) is ignored.

Standalone on purpose (only the standard library): it runs as a script, without the app's packages.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
import time
from pathlib import Path

FLAG = ".backup-pause"
ACK = ".backup-paused"
PAUSE_MAX = 120.0          # seconds: the longest pause of the writes
WAIT_ACK = 20.0            # seconds pre waits for the app's answer


def data_dir() -> Path:
    return Path(os.environ.get("FQ_DATA_DIR", "/data"))


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def read_flag(path: Path) -> dict | None:
    """The pause asked for: {"token", "until"} – `until` at most PAUSE_MAX after the flag was written. None: no flag."""
    try:
        st = path.stat()
        d = json.loads(path.read_text(encoding="utf-8"))
        until = float(d.get("until") or 0)
        token = str(d.get("token") or "")
    except FileNotFoundError:
        return None
    except (OSError, ValueError, TypeError, AttributeError):
        try:
            st = path.stat()
        except OSError:
            return None
        until, token = 0.0, ""
    return {"token": token or f"m{st.st_mtime}", "until": min(until or st.st_mtime + PAUSE_MAX, st.st_mtime + PAUSE_MAX)}


def _checkpoint(db: Path) -> list:
    c = sqlite3.connect(db, timeout=30)
    try:
        return list(c.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
    finally:
        c.close()


def pre(folder: Path | None = None, wait: float = WAIT_ACK, pause: float = PAUSE_MAX) -> dict:
    folder = folder or data_dir()
    token = secrets.token_hex(8)
    (folder / ACK).unlink(missing_ok=True)
    write_json(folder / FLAG, {"token": token, "until": time.time() + min(pause, PAUSE_MAX)})
    end = time.time() + wait
    while time.time() < end:
        try:
            ack = json.loads((folder / ACK).read_text(encoding="utf-8"))
            if ack.get("token") == token:
                return {"paused": True, "by": "app", "checkpoint": ack.get("checkpoint")}
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    db = folder / "family_quest.db"               # the app does not answer (not running): checkpoint here
    res = _checkpoint(db) if db.exists() else None
    return {"paused": False, "by": "script", "checkpoint": res}


def post(folder: Path | None = None) -> dict:
    folder = folder or data_dir()
    (folder / FLAG).unlink(missing_ok=True)
    end = time.time() + 5                         # the app answers by removing its ACK
    while (folder / ACK).exists() and time.time() < end:
        time.sleep(0.1)
    (folder / ACK).unlink(missing_ok=True)
    return {"resumed": True}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("pre", "post"):
        print("usage: hotbackup.py pre|post", file=sys.stderr)
        return 2
    try:
        res = pre() if argv[1] == "pre" else post()
        print(f"Family Quest backup {argv[1]}: {json.dumps(res)}")
    except Exception as e:  # noqa: BLE001 – never fail Home Assistant's backup because of this
        print(f"Family Quest backup {argv[1]}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
