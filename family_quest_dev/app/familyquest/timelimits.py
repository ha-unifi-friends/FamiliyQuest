"""Daily time limits per child: family games and Family Quest learning.

A limit is stored in the profile settings (`game_limit`, `learn_limit`) as
{"all": minutes | None, "days": {"0".."6": minutes | None}} – None = unlimited (the default), Monday = "0".
`days` holds only the weekdays with their own limit (in the parent area: the «undocked» weekday sliders).

Learning: the minutes of today are `daily.seconds` (booked per finished lesson, rewards.add_time).
Games: every minute in which a child used a family game (any game request, a heartbeat of the game corner) is one row
in `play_minute` – parallel requests in the same minute count once.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .db import Database, profile_settings

KINDS = {"game": "game_limit", "learn": "learn_limit"}
MAX_MINUTES = 1440


class LimitError(ValueError):
    pass


def _minutes(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        m = int(v)
    except (TypeError, ValueError):
        raise LimitError("Time limit: minutes per day (0–1440) or unlimited") from None
    if not 0 <= m <= MAX_MINUTES:
        raise LimitError("Time limit: minutes per day (0–1440) or unlimited")
    return m


def clean_limit(v) -> dict:
    """{"all": minutes|None, "days": {weekday: minutes|None}} – weekdays equal to «all» are dropped (docked)."""
    if v is None:
        return {"all": None, "days": {}}
    if not isinstance(v, dict):
        raise LimitError("Time limit: minutes per day (0–1440) or unlimited")
    every = _minutes(v.get("all"))
    days = {}
    raw = v.get("days") or {}
    if not isinstance(raw, dict):
        raise LimitError("Time limit: minutes per day (0–1440) or unlimited")
    for k, x in raw.items():
        if str(k) not in {str(i) for i in range(7)}:
            raise LimitError("Time limit: minutes per day (0–1440) or unlimited")
        m = _minutes(x)
        if m != every:
            days[str(k)] = m
    return {"all": every, "days": dict(sorted(days.items()))}


def limit_today(setting, weekday: int) -> int | None:
    """The limit (minutes) on this weekday (Monday = 0) – None = unlimited."""
    try:
        s = clean_limit(setting)
    except LimitError:
        return None
    return s["days"][str(weekday)] if str(weekday) in s["days"] else s["all"]


# ---------------------------------------------------------------- minutes used
def touch(db: Database, pid: int, now: datetime | None = None) -> None:
    """A child used a family game in this minute (counted once per minute)."""
    now = now or datetime.now()
    db.x("INSERT OR IGNORE INTO play_minute(profile_id, day, minute) VALUES(?,?,?)",
         pid, now.date().isoformat(), now.hour * 60 + now.minute)
    if now.minute == 0:                                      # once an hour: forget the minutes of last week
        db.x("DELETE FROM play_minute WHERE day < ?", (now.date() - timedelta(days=8)).isoformat())


def used(db: Database, pid: int, kind: str, now: datetime | None = None) -> int:
    day = (now or datetime.now()).date().isoformat()
    if kind == "game":
        return int(db.val("SELECT COUNT(*) FROM play_minute WHERE profile_id=? AND day=?", pid, day, default=0))
    return int(db.val("SELECT seconds FROM daily WHERE profile_id=? AND day=?", pid, day, default=0) or 0) // 60


def left(db: Database, prof: dict, kind: str, now: datetime | None = None) -> int | None:
    """Minutes left today for games («game») or learning («learn») – None = unlimited (parents always)."""
    if not prof or prof.get("role") != "kid":
        return None
    now = now or datetime.now()
    limit = limit_today(profile_settings(prof).get(KINDS[kind]), now.weekday())
    if limit is None:
        return None
    return max(0, limit - used(db, prof["id"], kind, now))


def used_up(db: Database, prof: dict, kind: str, now: datetime | None = None) -> bool:
    return left(db, prof, kind, now) == 0
