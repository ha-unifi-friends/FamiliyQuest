"""Privacy (parent area › Privacy): how long each kind of stored data is kept, and the clean-up runs that delete what
is older.

Retention periods – every kind of personal / usage data has a lifetime (days, months, years or «keep forever») with a
sensible default the parents can change (setting `privacy`). What the family made itself (books, quizzes, decks,
programs, photo sets, boards, pets, profiles, balances, settings) is not time-based: it is listed as «keep».

Clean-up runs – the list of entries past their retention period IS the preview (a dry run: nothing is deleted while
looking). Parents select kinds (or single entries where that makes sense) and run the deletion with a confirm step.
Every run:
  * first writes a backup snapshot with the backup module (data folder `privacy_backups/`, the last 3 are kept) – a run
    whose snapshot fails deletes nothing;
  * deletes each kind in one transaction;
  * is logged in `privacy_run` (date, kinds, counts, who) – the «Past runs».

Balances never change: old ledger rows are folded into «Balance brought forward» rows (one per profile, account and
class: earned / spent in the pet shop, plus / minus, before / after the XP items started) dated at the cut-off, in the
same transaction. The carry-forward row takes the id of the newest row it replaces, so everything that counts by ledger
id (new XP for the XP items, the Family Planer sync, lessons in progress) sees the same numbers. The number of chores
folded per profile goes to `ledger_folded` (badge «50 chores», the facts quiz). Old learning days are folded the same
way into one row per profile (day 0001-01-01): total XP, time and lessons stay; the days of the current streak are kept.

Never deleted, because something still refers to it: anything of the current week (week stats, daily limits, weekly
shop limits), running games, open / pending chores and chores of deals still going, deals not ended, shop orders
waiting for approval, open council topics and polls, a Wichteln whose date is still to come, the newest row of each
table (its id is never given out again – game coins, battery charges and chore points are booked once per id), the last
game of every quiz (it stays «played»), ledger rows since the active family goal started, the days of a running streak.

Master switch (`enabled`, on by default): off = no counts, no runs (manual or automatic: PrivacyOff), no badge.
The menu badge (`badge`): the total of the preview, cached BADGE_TTL seconds, reset by a run or a settings change.

Optional automatic clean-up (off by default): at night (02:00–05:00) the kinds that are past due are cleaned once a day,
with the same snapshot and log (by «automatic»).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable

from .i18n import _t
from .rewards.engine import SPEND_EVENTS, today

log = logging.getLogger(__name__)

SETTING = "privacy"
UNITS = ("days", "months", "years", "forever")
LIMITS = {"days": 3650, "months": 120, "years": 20}
BACKUP_DIR = "privacy_backups"
KEEP_BACKUPS = 3
AUTO_HOURS = (2, 5)                      # the automatic clean-up runs at night between 02:00 and 05:00
CARRY_DAY = "0001-01-01"                 # learning days folded into one row per profile
CARRY_REF = "carry:"                     # ledger rows «Balance brought forward»
CARRY_REASON = _t("Balance brought forward")
DEAL_ENDED = ("done", "rejected", "withdrawn", "declined", "failed", "cancelled")
ENTRY_LIMIT = 300
BADGE_TTL = 300                          # seconds the menu badge count is cached
_badge_cache: dict = {}                  # db path → (time, count)


class PrivacyOff(Exception):
    """The privacy module is switched off (master switch): no counts, no clean-up runs."""


@dataclass
class Part:
    """One table of a kind: its date, which rows may go, how an entry is shown, what goes with it."""
    table: str
    date: str                                       # SQL: the date of a row (text 'YYYY-MM-DD …')
    where: str = "1"
    label: str = "''"
    keep_newest: bool = True                        # never the row with the highest id (ids are not given out again)
    children: tuple = ()                            # (table, column) deleted with a row
    counted: bool = True                            # shown in the counts (False: small tracking rows that go along)
    after: Callable | None = None                   # after(db, ids) – extra work in the same transaction


@dataclass
class Kind:
    key: str
    icon: str
    title: str
    info: str
    default: tuple                                  # (n, unit) – unit "keep" = not time-based
    parts: list = field(default_factory=list)
    drill: bool = False                             # single entries can be chosen
    special: str = ""                               # "ledger" | "daily": folded, not just deleted


def _pname(col: str = "t.profile_id") -> str:
    return f"COALESCE((SELECT name FROM profile WHERE id={col}), '?')"


def _boards_floor(db, ids: list) -> None:
    """Removed board items that are gone for good: clients that knew them load the board anew (boards.py `floor`)."""
    for r in db.q(f"SELECT board_id, MAX(version) v FROM board_item WHERE id IN ({','.join('?' * len(ids))}) GROUP BY board_id", *ids):
        db.x("UPDATE board SET floor=MAX(floor, ?) WHERE id=?", r["v"], r["board_id"])


def _deal_pay(db, ids: list) -> None:
    for i in ids:
        db.x("DELETE FROM deal_pay WHERE ref LIKE ?", f"deal:{int(i)}:%")


_ENDED = ",".join(f"'{s}'" for s in DEAL_ENDED)

KINDS: list[Kind] = [
    Kind("security", "🔐", _t("Login log"),
         _t("Every login and failed login with time, address and device – to notice somebody guessing a PIN. A few months are enough."),
         (90, "days"), [Part("login_log", "t.at", label="CASE WHEN t.ok THEN '✓ ' ELSE '✗ ' END || COALESCE(t.ip, '') || COALESCE(' · ' || t.device, '')",
                             keep_newest=False)], drill=True),
    Kind("weather", "🌦️", _t("Behaviour weather"),
         _t("The weather you gave each child every day, with its bonus or malus. The points themselves stay in the balance."),
         (3, "months"), [Part("weather_log", "t.at", label=_pname() + " || ' ' || t.icon", keep_newest=False)], drill=True),
    Kind("usage", "🔋", _t("Game battery log"),
         _t("Every start, recharge and charge of the game battery. Only needed for the last weeks; the charge itself stays."),
         (3, "months"), [Part("battery_log", "t.at", label=_pname() + " || ' · ' || t.kind || COALESCE(' · ' || t.game, '')")]),
    Kind("pranks", "💣", _t("Pranks received"),
         _t("Ink bombs and other pranks a child received and has seen. What is still unseen stays."),
         (3, "months"), [Part("prank", "t.at", "t.seen_at IS NOT NULL", _pname("t.to_id") + " || ' · ' || t.kind")]),
    Kind("boards", "📌", _t("Removed board items"),
         _t("Notes and drawings removed from a bulletin board are kept a while for «undo». After that they can go."),
         (1, "months"), [Part("board_item", "t.updated_at", "t.deleted=1", "t.kind", after=_boards_floor)]),
    Kind("history", "📜", _t("Personal history"),
         _t("The history of every person: game results, quizzes, council votes. Records, highscores and badges are kept separately and stay."),
         (1, "years"), [Part("history", "t.at", label=_pname() + " || ' · ' || t.kind")], drill=True),
    Kind("games", "🎲", _t("Finished games"),
         _t("Tables of finished games with the moves and answers of everybody. Running games and the last game of every quiz stay."),
         (1, "years"), [
             Part("card_game", "COALESCE(t.finished_at, t.created_at)", "t.status='done'", "t.kind"),
             Part("poker_game", "COALESCE(t.finished_at, t.created_at)", "t.status='done'", "'poker'"),
             Part("song_game", "COALESCE(t.finished_at, t.created_at)", "t.status='done'", "'song'"),
             Part("bingo_game", "COALESCE(t.finished_at, t.created_at)", "t.status='done'", "'bingo'", children=(("bingo_card", "game_id"),)),
             Part("quiz_game", "COALESCE(t.finished_at, t.created_at)",
                  "t.status='done' AND t.id NOT IN (SELECT MAX(id) FROM quiz_game WHERE status='done' GROUP BY quiz_id)",
                  "COALESCE((SELECT title FROM quiz WHERE id=t.quiz_id), 'quiz')", children=(("quiz_answer", "game_id"),))], drill=True),
    Kind("learning", "📝", _t("Learning answers"),
         _t("Every single answer in the lessons and the finished lessons. What a child knows (the card boxes) and the learning progress stay."),
         (1, "years"), [Part("attempt", "t.at", label=_pname() + " || ' · ' || COALESCE(t.subject, '')", keep_newest=False),
                        Part("session", "t.created_at", label="''", keep_newest=False, counted=False)]),
    Kind("learning_days", "📅", _t("Learning days"),
         _t("XP, learning time and lessons per child and day. Old days are added up into one row, so totals, levels and badges stay; the days of a running streak are kept."),
         (2, "years"), special="daily"),
    Kind("ledger", "🪙", _t("Point bookings"),
         _t("Every booking of coins, XP and other points. Old bookings are added up into one «Balance brought forward» per child and account – balances, levels and XP never change."),
         (2, "years"), [Part("ledger", "t.at", f"COALESCE(t.ref, '') NOT LIKE '{CARRY_REF}%'", keep_newest=False)], special="ledger"),
    Kind("chores", "🧹", _t("Chores done"),
         _t("Which chore was done by whom on which day. Open and pending chores and chores of running deals stay."),
         (1, "years"), [Part("chore_task", "t.period",
                             f"t.status!='pending' AND (t.deal_id IS NULL OR t.deal_id NOT IN (SELECT id FROM deal WHERE status NOT IN ({_ENDED})))"),
                        Part("chore_seen", "t.day", keep_newest=False, counted=False)]),
    Kind("deals", "🤝", _t("Deals"),
         _t("Ended deals between family members with their messages. Deals that are still open or running stay."),
         (1, "years"), [Part("deal", "COALESCE(t.ended_at, t.updated_at)",
                             f"t.status IN ({_ENDED}) AND NOT EXISTS (SELECT 1 FROM deal_hold h WHERE h.deal_id=t.id AND h.active=1)",
                             _pname("t.a_id") + " || ' ↔ ' || " + _pname("t.b_id") + " || ' · ' || t.status",
                             children=(("deal_msg", "deal_id"), ("deal_seen", "deal_id"), ("deal_hold", "deal_id")), after=_deal_pay)], drill=True),
    Kind("redemptions", "🛍️", _t("Shop orders"),
         _t("What the children bought in the shop and your decisions. Orders waiting for your approval stay; the coins are not touched."),
         (1, "years"), [Part("redemption", "t.created_at", "t.status!='pending'",
                             _pname() + " || ' · ' || COALESCE((SELECT name FROM reward WHERE id=t.reward_id), '?')")], drill=True),
    Kind("community", "🗳️", _t("Council topics and polls"),
         _t("Closed family council topics and polls with their proposals and votes. Open ones stay."),
         (1, "years"), [Part("council_topic", "COALESCE(t.closed_at, t.created_at)", "t.status='closed'", "t.title",
                             children=(("council_proposal", "topic_id"), ("council_vote", "topic_id"))),
                        Part("poll", "COALESCE(t.closed_at, t.created_at)", "t.status='closed'", "t.question",
                             children=(("poll_vote", "poll_id"), ("poll_option", "poll_id")))], drill=True),
    Kind("wichteln", "🎁", _t("Secret gift giving"),
         _t("Past secret gift giving draws: who gave to whom. A draw whose date is still to come stays."),
         (1, "years"), [Part("wichtel", "COALESCE(t.due, t.created_at)", label="t.title")], drill=True),
    Kind("calendar", "📆", _t("Past calendar events"),
         _t("Calendar events that are over, with the FamilyTime game wishes and votes. Birthdays stay."),
         (2, "years"), [Part("family_event", "t.end", "t.kind!='birthday'", "t.title",
                             children=(("ft_vote", "event_id"), ("ft_wish", "event_id"), ("ft_game", "event_id")))], drill=True),
]

# not time-based: what the family made or needs to work – kept until you delete it yourself
KEEP: list[Kind] = [
    Kind("profiles", "👤", _t("Profiles, balances and settings"),
         _t("The profiles with avatar, PIN and settings, the current balances, badges, records and highscores. Delete a profile to remove them."), (0, "keep")),
    Kind("progress", "🧠", _t("Learning progress and card decks"),
         _t("What each child knows (the card boxes of the packs) and the own flash card decks – deleting it would start learning from zero."), (0, "keep")),
    Kind("creations", "📚", _t("Books, quizzes and programs"),
         _t("Books, interactive books, adventure games, own quizzes and Code Workshop programs the family wrote. Delete them where they are made."), (0, "keep")),
    Kind("photos", "🖼️", _t("Photo sets and uploads"),
         _t("Photo sets of the pairs game, pictures of packs and photos in the Family Planer. Delete them in their own place."), (0, "keep")),
    Kind("family", "📌", _t("Boards, pets and the calendar ahead"),
         _t("Bulletin boards, pets with their things, upcoming events and the chore plan – they are in use."), (0, "keep")),
]

BY_KEY = {k.key: k for k in KINDS}


# ---------------------------------------------------------------- settings
def defaults() -> dict:
    return {"enabled": True, "retention": {k.key: {"n": k.default[0], "unit": k.default[1]} for k in KINDS}, "auto": False,
            "last_auto": ""}


def clean_period(v, fallback: dict) -> dict:
    if not isinstance(v, dict) or v.get("unit") not in UNITS:
        return dict(fallback)
    if v["unit"] == "forever":
        return {"n": 0, "unit": "forever"}
    try:
        n = int(v.get("n"))
    except (TypeError, ValueError):
        return dict(fallback)
    return {"n": max(1, min(LIMITS[v["unit"]], n)), "unit": v["unit"]}


def settings(db) -> dict:
    d = defaults()
    raw = db.get_setting(SETTING) or {}
    if isinstance(raw, dict):
        ret = raw.get("retention") if isinstance(raw.get("retention"), dict) else {}
        d["retention"] = {k: clean_period(ret.get(k), v) for k, v in d["retention"].items()}
        d["auto"] = bool(raw.get("auto", False))
        d["enabled"] = bool(raw.get("enabled", True))
        d["last_auto"] = str(raw.get("last_auto") or "")
    return d


def save_settings(db, body: dict) -> dict:
    cur = settings(db)
    if isinstance(body.get("retention"), dict):
        for k, v in body["retention"].items():
            if k in cur["retention"]:
                cur["retention"][k] = clean_period(v, cur["retention"][k])
    if "auto" in body:
        cur["auto"] = bool(body["auto"])
    if "enabled" in body:
        cur["enabled"] = bool(body["enabled"])
    db.set_setting(SETTING, cur)
    badge_reset(db)
    return cur


def login_cap_days(db, base: int) -> int | None:
    """How long the login log keeps rows at most (loginlog.py): its own limit, longer when the parents keep the login
    log longer, None when they keep it forever."""
    p = settings(db)["retention"]["security"]
    if p["unit"] == "forever":
        return None
    c = cutoff_of(p, today())
    return max(base, (today() - date.fromisoformat(c)).days) if c else base


# ---------------------------------------------------------------- cut-off
def _minus_months(d: date, n: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    m += 1
    import calendar as _cal
    return date(y, m, min(d.day, _cal.monthrange(y, m)[1]))


def cutoff_of(p: dict, now: date) -> str | None:
    """The first day that is kept (rows dated before it are past due) – never later than the Monday of this week."""
    if p["unit"] == "forever":
        return None
    n = int(p["n"])
    c = now - timedelta(days=n) if p["unit"] == "days" else _minus_months(now, n * (12 if p["unit"] == "years" else 1))
    monday = now - timedelta(days=now.weekday())
    return min(c, monday).isoformat()


def _ledger_cutoff(db, c: str) -> str:
    """Rows since the active family goal started count for it: they stay."""
    g = db.val("SELECT MIN(created_at) FROM goal WHERE profile_id IS NULL AND kind='family' AND active=1")
    return min(c, str(g)[:10]) if g else c


def _streak_start(fq, pid: int) -> str:
    s = fq.rewards.streak(pid)
    return (today() - timedelta(days=s + 1)).isoformat()


# ---------------------------------------------------------------- what is due (the preview)
def _part_sql(p: Part, select: str) -> str:
    sql = f"SELECT {select} FROM {p.table} t WHERE {p.date} < ? AND ({p.where})"
    if p.keep_newest:
        sql += f" AND t.id < (SELECT MAX(id) FROM {p.table})"
    return sql


def _daily_rows(fq, c: str) -> list[dict]:
    out = []
    for r in fq.db.q("SELECT DISTINCT profile_id FROM daily WHERE day < ? AND day != ?", c, CARRY_DAY):
        pc = min(c, _streak_start(fq, r["profile_id"]))
        out += fq.db.q("SELECT profile_id, day FROM daily WHERE profile_id=? AND day < ? AND day != ?", r["profile_id"], pc, CARRY_DAY)
    return out


def due(fq, kind: Kind, c: str | None) -> dict:
    """Counts of what is past due for one kind (nothing is changed)."""
    out = {"count": 0, "oldest": None, "newest": None}
    if c is None:
        return out
    if kind.special == "daily":
        rows = _daily_rows(fq, c)
        if rows:
            days = sorted(r["day"] for r in rows)
            out.update(count=len(rows), oldest=days[0], newest=days[-1])
        return out
    if kind.special == "ledger":
        c = _ledger_cutoff(fq.db, c)
    for p in kind.parts:
        if not p.counted:
            continue
        r = fq.db.q1(_part_sql(p, f"COUNT(*) n, MIN({p.date}) a, MAX({p.date}) b"), c)
        if r and r["n"]:
            out["count"] += r["n"]
            out["oldest"] = min(filter(None, [out["oldest"], str(r["a"])[:10]]))
            out["newest"] = max(filter(None, [out["newest"], str(r["b"])[:10]]))
    return out


def preview(fq) -> dict:
    st = settings(fq.db)
    now = today()
    kinds = []
    for k in KINDS:
        c = cutoff_of(st["retention"][k.key], now)
        # switched off: no counts at all (nothing is looked at)
        cnt = due(fq, k, c) if st["enabled"] else {"count": 0, "oldest": None, "newest": None}
        kinds.append({"key": k.key, "icon": k.icon, "title": k.title, "info": k.info, "default": {"n": k.default[0], "unit": k.default[1]},
                      "retention": st["retention"][k.key], "cutoff": c, "drill": k.drill, **cnt})
    if st["enabled"]:
        _badge_cache[fq.db.path] = (time.monotonic(), sum(k["count"] for k in kinds))
    keep = [{"key": k.key, "icon": k.icon, "title": k.title, "info": k.info} for k in KEEP]
    return {"enabled": st["enabled"], "kinds": kinds, "keep": keep, "auto": st["auto"], "last_auto": st["last_auto"], "runs": runs(fq.db),
            "backup_dir": BACKUP_DIR, "keep_backups": KEEP_BACKUPS, "auto_hours": list(AUTO_HOURS)}


def entries(fq, key: str, limit: int = ENTRY_LIMIT) -> list[dict]:
    """The single entries of a kind that are past due – newest first (ids «table:id»)."""
    kind = BY_KEY.get(key)
    if not kind or not kind.drill or not settings(fq.db)["enabled"]:
        return []
    c = cutoff_of(settings(fq.db)["retention"][key], today())
    if c is None:
        return []
    out = []
    for p in kind.parts:
        if p.counted:
            for r in fq.db.q(_part_sql(p, f"t.id AS id, {p.date} AS at, {p.label} AS label") + f" ORDER BY {p.date} DESC LIMIT ?", c, limit):
                out.append({"id": f"{p.table}:{r['id']}", "at": str(r["at"] or "")[:16], "label": r["label"] or ""})
    out.sort(key=lambda r: r["at"], reverse=True)
    return out[:limit]


# ---------------------------------------------------------------- deleting
def _purge_parts(fq, kind: Kind, c: str, only: set | None) -> int:
    db = fq.db
    n = 0
    for p in kind.parts:
        ids = [r["id"] for r in db.q(_part_sql(p, "t.rowid AS id" if p.table in ("chore_seen", "session") else "t.id AS id"), c)]
        if only is not None:
            ids = [i for i in ids if f"{p.table}:{i}" in only]
        if not ids:
            continue
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join("?" * len(chunk))
            for table, col in p.children:
                db.x(f"DELETE FROM {table} WHERE {col} IN ({marks})", *chunk)
            if p.after:
                p.after(db, chunk)
            key = "rowid" if p.table in ("chore_seen", "session") else "id"
            db.x(f"DELETE FROM {p.table} WHERE {key} IN ({marks})", *chunk)
        if p.counted:
            n += len(ids)
    return n


def _fold_ledger(fq, c: str) -> int:
    """Old ledger rows → «Balance brought forward» rows. Sums per profile, account and class stay exactly the same."""
    db = fq.db
    c = _ledger_cutoff(db, c)
    start = int(db.get_setting("xp_items_from", 0) or 0)
    rows = db.q("SELECT id, profile_id, account, amount, event, ref FROM ledger WHERE at < ?", c)
    groups: dict[tuple, list] = {}
    for r in rows:
        spent = (r["event"] or "") in SPEND_EVENTS
        key = (r["profile_id"], r["account"], r["event"] if spent else "", r["amount"] > 0, r["id"] > start)
        groups.setdefault(key, []).append(r)
    at = (date.fromisoformat(c) - timedelta(days=1)).isoformat() + " 23:59:59"
    folded = 0
    counts: dict[tuple, set] = {}
    for (pid, account, spent_event, _pos, _new), rs in groups.items():
        real = [r for r in rs if not str(r["ref"] or "").startswith(CARRY_REF)]
        if not real:
            continue                                         # only an earlier carry-forward row: nothing to do
        total = round(sum(float(r["amount"]) for r in rs), 6)
        keep_id = max(r["id"] for r in rs)
        ids = [r["id"] for r in rs]
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            db.x(f"DELETE FROM ledger WHERE id IN ({','.join('?' * len(chunk))})", *chunk)
        if total:
            db.x("INSERT INTO ledger(id, profile_id, account, amount, event, reason, ref, at) VALUES(?,?,?,?,?,?,?,?)",
                 keep_id, pid, account, total, spent_event or "carry_forward", CARRY_REASON, f"{CARRY_REF}{c}", at)
        folded += len(real)
        for r in real:
            if r["amount"] > 0 and r["event"]:
                counts.setdefault((pid, r["event"]), set()).add(r["ref"] or f"#{r['id']}")
    for (pid, event), refs in counts.items():
        db.x("""INSERT INTO ledger_folded(profile_id, event, n) VALUES(?,?,?)
                ON CONFLICT(profile_id, event) DO UPDATE SET n=n+excluded.n""", pid, event, len(refs))
    return folded


def _fold_daily(fq, c: str) -> int:
    db = fq.db
    rows = _daily_rows(fq, c)
    by: dict[int, list] = {}
    for r in rows:
        by.setdefault(r["profile_id"], []).append(r["day"])
    for pid, days in by.items():
        marks = ",".join("?" * len(days))
        s = db.q1(f"SELECT SUM(xp) xp, SUM(seconds) s, SUM(lessons) l FROM daily WHERE profile_id=? AND day IN ({marks})", pid, *days)
        db.x(f"DELETE FROM daily WHERE profile_id=? AND day IN ({marks})", pid, *days)
        db.x("""INSERT INTO daily(profile_id, day, xp, seconds, lessons, goal_met) VALUES(?,?,?,?,?,0)
                ON CONFLICT(profile_id, day) DO UPDATE SET xp=xp+excluded.xp, seconds=seconds+excluded.seconds,
                lessons=lessons+excluded.lessons""", pid, CARRY_DAY, s["xp"] or 0, s["s"] or 0, s["l"] or 0)
    return len(rows)


def purge(fq, key: str, only: set | None = None, now: date | None = None) -> int:
    """Delete what is past due of one kind, in one transaction. `only`: just these entries («table:id»)."""
    kind = BY_KEY[key]
    c = cutoff_of(settings(fq.db)["retention"][key], now or today())
    if c is None:
        return 0
    with fq.db.tx():
        if kind.special == "ledger":
            return _fold_ledger(fq, c)
        if kind.special == "daily":
            return _fold_daily(fq, c)
        return _purge_parts(fq, kind, c, only if kind.drill else None)


def snapshot(fq) -> str:
    """A backup before the run (backup.py) in the data folder; only the newest KEEP_BACKUPS stay."""
    from . import backup
    raw, name = backup.create(fq)
    folder = fq.settings.data_dir / BACKUP_DIR
    folder.mkdir(parents=True, exist_ok=True)
    name = name.replace("family-quest-backup-", "before-cleanup-")
    path = folder / name
    k = 1
    while path.exists():
        k += 1
        path = folder / name.replace(".zip", f"-{k}.zip")
    path.write_bytes(raw)
    for old in sorted(folder.glob("before-cleanup-*.zip"), key=lambda p: p.stat().st_mtime)[:-KEEP_BACKUPS]:
        old.unlink(missing_ok=True)
    return path.name


def run(fq, keys: list[str], picks: dict | None = None, by: dict | None = None, auto: bool = False) -> dict:
    """A clean-up run: snapshot, then every chosen kind in its own transaction, then the log entry.
    `picks` {kind: ["table:id", …]}: only these entries of that kind (kinds with single entries)."""
    picks = picks or {}
    st = settings(fq.db)
    if not st["enabled"]:
        raise PrivacyOff()
    now = today()
    todo = []
    for k in keys:
        kind = BY_KEY.get(k)
        if not kind or k in todo:
            continue
        c = cutoff_of(st["retention"][k], now)
        if c is None or not due(fq, kind, c)["count"]:
            continue
        todo.append(k)
    if not todo:
        return {"counts": {}, "backup": None, "id": None}
    name = snapshot(fq)                                      # no snapshot – nothing is deleted (it raises)
    counts = {}
    for k in todo:
        only = set(picks[k]) if isinstance(picks.get(k), list) and picks[k] else None
        try:
            counts[k] = purge(fq, k, only, now)
        except Exception:  # noqa: BLE001 – this kind is rolled back, the others go on
            log.exception("clean-up of %s failed", k)
            counts[k] = -1
    rid = fq.db.x("INSERT INTO privacy_run(by_id, by_name, auto, counts, backup) VALUES(?,?,?,?,?)",
                  (by or {}).get("id"), (by or {}).get("name") or "", int(auto), json.dumps(counts), name)
    badge_reset(fq.db)
    return {"counts": counts, "backup": name, "id": rid}


def runs(db, limit: int = 20) -> list[dict]:
    out = []
    for r in db.q("SELECT * FROM privacy_run ORDER BY id DESC LIMIT ?", limit):
        r["counts"] = json.loads(r["counts"] or "{}")
        r["auto"] = bool(r["auto"])
        out.append(r)
    return out


# ---------------------------------------------------------------- the badge on the menu item
def badge_reset(db) -> None:
    _badge_cache.pop(db.path, None)


def badge(fq) -> dict:
    """{"on", "count"}: entries past their retention period (the total of the preview) – cached BADGE_TTL seconds."""
    st = settings(fq.db)
    if not st["enabled"]:
        return {"on": False, "count": 0}
    hit = _badge_cache.get(fq.db.path)
    if hit and time.monotonic() - hit[0] < BADGE_TTL:
        return {"on": True, "count": hit[1]}
    now = today()
    n = sum(due(fq, k, cutoff_of(st["retention"][k.key], now))["count"] for k in KINDS)
    _badge_cache[fq.db.path] = (time.monotonic(), n)
    return {"on": True, "count": n}


# ---------------------------------------------------------------- automatic clean-up at night
def maybe_auto(fq, now: datetime | None = None) -> dict | None:
    """The nightly run when the switch is on: once a day between 02:00 and 05:00, all kinds past due."""
    now = now or datetime.now()
    st = settings(fq.db)
    if not st["enabled"] or not st["auto"] or not (AUTO_HOURS[0] <= now.hour < AUTO_HOURS[1]) or st["last_auto"] == now.date().isoformat():
        return None
    fq.db.set_setting(SETTING, {**st, "last_auto": now.date().isoformat()})
    return run(fq, [k.key for k in KINDS], by={"id": None, "name": ""}, auto=True)


async def auto_loop(fq, every: float = 600) -> None:
    while True:
        await asyncio.sleep(every)
        try:
            await asyncio.to_thread(maybe_auto, fq)
        except Exception:  # noqa: BLE001
            log.exception("automatic clean-up failed")
