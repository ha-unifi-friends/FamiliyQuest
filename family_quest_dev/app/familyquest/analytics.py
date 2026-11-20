"""📈 Analytics in the parent area: a small reporting module (web/parent-analytics.js).

A report is a *spec* – a dataset, up to 3 dimensions (columns, rows, group), 1–4 measures, a date range and a child
filter. Everything a spec names is looked up in the whitelist below (DATASETS, COMMON_DIMS): every SQL fragment is a
constant of this file, user values (dates, profile ids) only ever go in as query parameters. Unknown keys raise
AnalyticsError (→ 400). The query runs on a read-only connection (`mode=ro`, `query_only`), with a time limit and a
row cap.

Privacy: no titles of books (private «Only me» books are left out completely), no quiz titles, no free texts; the
datasets only count what the parent area shows anyway (ledger, learning, games, chores, rewards, battery, weather).

Saved reports («My reports») live in the setting `analytics_reports` – so they are part of every backup (backup.py
copies the whole database).
"""
from __future__ import annotations

import re
import secrets
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

from .i18n import _t
from .packs.registry import SUBJECTS
from .running import TITLES

MAX_DIMS = 3
MAX_MEASURES = 4
MAX_ROWS = 2000
MAX_REPORTS = 50
TIME_LIMIT = 3.0                          # seconds a query may run
SETTING = "analytics_reports"
DASH_SETTING = "analytics_dashboards"
MAX_DASHBOARDS = 20
MAX_TILES = 24
PERIODS = ("day", "week", "month", "year", "r12", "custom")
HEIGHTS = ("s", "m", "l")
# the standard dashboard: the most important templates (tile size w = columns of 4, h = small / medium / tall)
STANDARD_TILES = [("coins_week", 2, "m"), ("xp_week", 2, "m"), ("games_game", 2, "m"), ("chores_status", 2, "s"),
                  ("weather_mix", 2, "s"), ("gametime_day", 2, "m")]
RANGES = ("7d", "30d", "year", "all")
CHARTS = ("table", "pivot", "bar", "stacked", "stacked100", "line", "area", "pie", "bubble")


class AnalyticsError(ValueError):
    pass


# ---------------------------------------------------------------- the whitelist
# {d} = the date column of the dataset (local time text «YYYY-MM-DD[ HH:MM:SS]»), {p} = its profile column
_DAY = "substr({d},1,10)"
_WD = "((CAST(strftime('%w', substr({d},1,10)) AS INTEGER) + 6) % 7)"      # 0 = Monday
COMMON_DIMS = {
    "child": ("{p}", "profile"),
    "day": (_DAY, "day"),
    "week": ("date(substr({d},1,10), '-' || " + _WD + " || ' days')", "week"),     # the Monday of the week
    "month": ("substr({d},1,7)", "month"),
    "year": ("substr({d},1,4)", "year"),
    "weekday": (_WD, "weekday"),
}

# per dataset: FROM (with joins), the date and profile column, an extra WHERE (constant), own dimensions
# {key: (sql, kind)} and measures {key: (sql aggregate, unit)}
DATASETS: dict[str, dict] = {
    "ledger": {
        "from": "ledger l", "date": "l.at", "profile": "l.profile_id", "where": "",
        "dims": {"account": ("l.account", "account"), "event": ("COALESCE(NULLIF(l.event,''),'other')", "event")},
        "measures": {
            "count": ("COUNT(*)", ""),
            "coins": ("SUM(CASE WHEN l.account='coins' THEN l.amount ELSE 0 END)", "coins"),
            "coins_earned": ("SUM(CASE WHEN l.account='coins' AND l.amount>0 THEN l.amount ELSE 0 END)", "coins"),
            "coins_spent": ("SUM(CASE WHEN l.account='coins' AND l.amount<0 THEN -l.amount ELSE 0 END)", "coins"),
            "xp": ("SUM(CASE WHEN l.account='xp' THEN l.amount ELSE 0 END)", "XP"),
            "internet_used": ("SUM(CASE WHEN l.account='internet' AND l.amount<0 THEN -l.amount ELSE 0 END)", "min"),
            "amount": ("SUM(l.amount)", ""),
        },
    },
    "learning": {
        "from": "attempt a", "date": "a.at", "profile": "a.profile_id", "where": "",
        "dims": {"subject": ("COALESCE(NULLIF(a.subject,''),'allgemein')", "subject"),
                 "exercise": ("COALESCE(NULLIF(a.kind,''),'other')", "exercise")},
        "measures": {
            "answers": ("COUNT(*)", ""),
            "correct": ("SUM(CASE WHEN a.correct THEN 1 ELSE 0 END)", ""),
            "wrong": ("SUM(CASE WHEN a.correct THEN 0 ELSE 1 END)", ""),
            "accuracy": ("ROUND(AVG(CASE WHEN a.correct THEN 100.0 ELSE 0 END), 1)", "%"),
            "minutes": ("ROUND(SUM(COALESCE(a.ms,0)) / 60000.0, 1)", "min"),
        },
    },
    "daily": {
        "from": "daily y", "date": "y.day", "profile": "y.profile_id", "where": "",
        "dims": {},
        "measures": {
            "xp": ("SUM(y.xp)", "XP"),
            "minutes": ("ROUND(SUM(y.seconds) / 60.0, 1)", "min"),
            "lessons": ("SUM(y.lessons)", ""),
            "goal_days": ("SUM(CASE WHEN y.goal_met THEN 1 ELSE 0 END)", ""),
            "days": ("COUNT(*)", ""),
        },
    },
    "games": {
        "from": "history h", "date": "h.at", "profile": "h.profile_id",
        "where": "h.kind NOT IN ('council','familytime') AND json_valid(h.data)",
        "dims": {"game": ("CASE WHEN h.kind='cards' THEN COALESCE(json_extract(h.data,'$.game'),'cards') ELSE h.kind END", "game")},
        "measures": {
            "count": ("COUNT(*)", ""),
            "wins": ("SUM(CASE WHEN json_extract(h.data,'$.place')=1 THEN 1 ELSE 0 END)", ""),
            "coins": ("SUM(COALESCE(json_extract(h.data,'$.coins'),0))", "coins"),
            "avg_place": ("ROUND(AVG(json_extract(h.data,'$.place')), 2)", ""),
        },
    },
    "chores": {
        "from": "chore_task t JOIN chore c ON c.id=t.chore_id", "date": "t.period", "profile": "t.profile_id", "where": "",
        "dims": {"chore": ("c.icon || ' ' || c.name", "text"), "status": ("t.status", "status"),
                 "chore_kind": ("c.kind", "chore_kind")},
        "measures": {
            "count": ("COUNT(*)", ""),
            "done": ("SUM(CASE WHEN t.status='done' THEN 1 ELSE 0 END)", ""),
            "open": ("SUM(CASE WHEN t.status<>'done' THEN 1 ELSE 0 END)", ""),
            "rate": ("ROUND(AVG(CASE WHEN t.status='done' THEN 100.0 ELSE 0 END), 1)", "%"),
            "points": ("SUM(CASE WHEN t.status='done' THEN c.points ELSE 0 END)", ""),
        },
    },
    "rewards": {
        "from": "redemption r JOIN reward w ON w.id=r.reward_id", "date": "r.created_at", "profile": "r.profile_id", "where": "",
        "dims": {"reward": ("w.icon || ' ' || w.name", "text"), "status": ("r.status", "status"),
                 "reward_kind": ("w.kind", "reward_kind")},
        "measures": {
            "count": ("COUNT(*)", ""),
            "approved": ("SUM(CASE WHEN r.status='approved' THEN 1 ELSE 0 END)", ""),
            "cost": ("SUM(CASE WHEN r.status IN ('approved','pending') THEN r.cost ELSE 0 END)", ""),
        },
    },
    "gametime": {
        "from": "play_minute m", "date": "m.day", "profile": "m.profile_id", "where": "",
        "dims": {},
        "measures": {
            "minutes": ("COUNT(*)", "min"),
            "hours": ("ROUND(COUNT(*) / 60.0, 1)", "h"),
            "days": ("COUNT(DISTINCT m.day)", ""),
        },
    },
    "battery": {
        "from": "battery_log b", "date": "b.at", "profile": "b.profile_id", "where": "",
        "dims": {"battery_kind": ("b.kind", "battery_kind"), "game": ("COALESCE(NULLIF(b.game,''),'-')", "game")},
        "measures": {
            "starts": ("SUM(CASE WHEN b.kind='start' THEN 1 ELSE 0 END)", ""),
            "used": ("SUM(CASE WHEN b.delta<0 THEN -b.delta ELSE 0 END)", ""),
            "charged": ("SUM(CASE WHEN b.delta>0 THEN b.delta ELSE 0 END)", ""),
            "count": ("COUNT(*)", ""),
        },
    },
    "weather": {
        "from": "weather_log w", "date": "w.at", "profile": "w.profile_id", "where": "",
        "dims": {"weather": ("w.level", "weather")},
        "measures": {
            "count": ("COUNT(*)", ""),
            "points": ("SUM(w.points)", ""),
            "bonus": ("SUM(CASE WHEN w.points>0 THEN w.points ELSE 0 END)", ""),
            "malus": ("SUM(CASE WHEN w.points<0 THEN -w.points ELSE 0 END)", ""),
        },
    },
    # books: never a title – and the private books («Only me») are not counted at all
    "reading": {
        "from": "story_read r JOIN story s ON s.id=r.story_id", "date": "r.updated_at", "profile": "r.profile_id",
        "where": "s.visibility<>'me'",
        "dims": {"book_type": ("s.type", "book_type")},
        "measures": {
            "books": ("COUNT(*)", ""),
            "finished": ("SUM(CASE WHEN r.finished>0 THEN 1 ELSE 0 END)", ""),
            "rating": ("ROUND(AVG(r.rating), 1)", "⭐"),
        },
    },
}

# built-in templates (English source texts, translated in the UI)
TEMPLATES = [
    {"key": "coins_week", "icon": "🪙", "title": _t("Coins per child and week"),
     "spec": {"dataset": "ledger", "rows": ["week"], "columns": ["child"], "group": [], "data": ["coins"], "range": "30d", "chart": "bar"}},
    {"key": "coins_flow", "icon": "💰", "title": _t("Coins earned and spent"),
     "spec": {"dataset": "ledger", "rows": ["child"], "columns": [], "group": [], "data": ["coins_earned", "coins_spent"], "range": "30d", "chart": "pivot"}},
    {"key": "xp_week", "icon": "⭐", "title": _t("XP per child and week"),
     "spec": {"dataset": "daily", "rows": ["week"], "columns": ["child"], "group": [], "data": ["xp"], "range": "year", "chart": "line"}},
    {"key": "learn_subject", "icon": "📚", "title": _t("Correct answers per subject"),
     "spec": {"dataset": "learning", "rows": ["subject"], "columns": ["child"], "group": [], "data": ["correct"], "range": "30d", "chart": "stacked"}},
    {"key": "accuracy_subject", "icon": "🎯", "title": _t("Accuracy per subject"),
     "spec": {"dataset": "learning", "rows": ["subject"], "columns": ["child"], "group": [], "data": ["accuracy"], "range": "30d", "chart": "bar"}},
    {"key": "learn_minutes", "icon": "⏱️", "title": _t("Learning minutes per day"),
     "spec": {"dataset": "daily", "rows": ["day"], "columns": ["child"], "group": [], "data": ["minutes"], "range": "30d", "chart": "area"}},
    {"key": "games_game", "icon": "🎲", "title": _t("Games played per game"),
     "spec": {"dataset": "games", "rows": ["game"], "columns": ["child"], "group": [], "data": ["count"], "range": "year", "chart": "stacked"}},
    {"key": "games_child", "icon": "🏆", "title": _t("Games, wins and coins per child"),
     "spec": {"dataset": "games", "rows": ["child"], "columns": [], "group": [], "data": ["count", "wins", "coins"], "range": "year", "chart": "pivot"}},
    {"key": "chores_week", "icon": "🧹", "title": _t("Chores done per week"),
     "spec": {"dataset": "chores", "rows": ["week"], "columns": ["child"], "group": [], "data": ["done"], "range": "30d", "chart": "stacked"}},
    {"key": "chores_status", "icon": "✅", "title": _t("Chores done or open"),
     "spec": {"dataset": "chores", "rows": ["child"], "columns": ["status"], "group": [], "data": ["count"], "range": "30d", "chart": "stacked100"}},
    {"key": "rewards", "icon": "🎁", "title": _t("Rewards redeemed"),
     "spec": {"dataset": "rewards", "rows": ["reward"], "columns": [], "group": [], "data": ["count"], "range": "year", "chart": "pie"}},
    {"key": "gametime_day", "icon": "🎮", "title": _t("Game time per day"),
     "spec": {"dataset": "gametime", "rows": ["day"], "columns": ["child"], "group": [], "data": ["minutes"], "range": "7d", "chart": "bar"}},
    {"key": "gametime_matrix", "icon": "🫧", "title": _t("Game time by weekday and child"),
     "spec": {"dataset": "gametime", "rows": ["weekday"], "columns": ["child"], "group": [], "data": ["minutes"], "range": "30d", "chart": "bubble"}},
    {"key": "internet_week", "icon": "🌐", "title": _t("Internet minutes used per week"),
     "spec": {"dataset": "ledger", "rows": ["week"], "columns": ["child"], "group": [], "data": ["internet_used"], "range": "30d", "chart": "bar"}},
    {"key": "battery_game", "icon": "🔋", "title": _t("Battery used per game"),
     "spec": {"dataset": "battery", "rows": ["game"], "columns": ["child"], "group": [], "data": ["used"], "range": "30d", "chart": "stacked"}},
    {"key": "weather_mix", "icon": "☀️", "title": _t("Weather of the day per child"),
     "spec": {"dataset": "weather", "rows": ["child"], "columns": ["weather"], "group": [], "data": ["count"], "range": "30d", "chart": "stacked100"}},
    {"key": "weather_points", "icon": "⛈️", "title": _t("Bonus/malus points per week"),
     "spec": {"dataset": "weather", "rows": ["week"], "columns": ["child"], "group": [], "data": ["points"], "range": "30d", "chart": "bar"}},
    {"key": "reading", "icon": "📖", "title": _t("Books read per child"),
     "spec": {"dataset": "reading", "rows": ["child"], "columns": ["book_type"], "group": [], "data": ["books"], "range": "all", "chart": "stacked"}},
]

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_date(v) -> bool:
    if not isinstance(v, str) or not _DATE.match(v):
        return False
    try:
        date.fromisoformat(v)
    except ValueError:
        return False
    return True


def dims_of(ds: str) -> dict:
    return {**COMMON_DIMS, **DATASETS[ds]["dims"]}


def meta() -> dict:
    """What the UI may offer: datasets with their dimensions (key, kind) and measures (key, unit), the templates."""
    return {"datasets": {k: {"dims": [[d, kind] for d, (_, kind) in dims_of(k).items()],
                             "measures": [[m, unit] for m, (_, unit) in v["measures"].items()]} for k, v in DATASETS.items()},
            "ranges": list(RANGES), "charts": list(CHARTS), "limits": {"dims": MAX_DIMS, "measures": MAX_MEASURES, "rows": MAX_ROWS},
            "templates": TEMPLATES}


def _keys(v, allowed, what: str) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise AnalyticsError(_t("Invalid report"))
    bad = [x for x in v if x not in allowed]
    if bad:
        raise AnalyticsError(f"Unknown {what}: {bad[0][:40]}")
    return list(v)


def clean_spec(spec) -> dict:
    """The spec checked against the whitelist – AnalyticsError for anything unknown."""
    if not isinstance(spec, dict):
        raise AnalyticsError(_t("Invalid report"))
    ds = spec.get("dataset")
    if ds not in DATASETS:
        raise AnalyticsError(f"Unknown dataset: {str(ds)[:40]}")
    dims = dims_of(ds)
    out = {"dataset": ds}
    for zone in ("columns", "rows", "group"):
        out[zone] = _keys(spec.get(zone), dims, "dimension")
    used = out["columns"] + out["rows"] + out["group"]
    if len(used) != len(set(used)):
        raise AnalyticsError(_t("A dimension can only be used once"))
    if len(used) > MAX_DIMS:
        raise AnalyticsError(_t("At most 3 dimensions"))
    out["data"] = _keys(spec.get("data"), DATASETS[ds]["measures"], "measure")
    if len(out["data"]) != len(set(out["data"])) or len(out["data"]) > MAX_MEASURES:
        raise AnalyticsError(_t("At most 4 different measures"))
    rng = spec.get("range", "30d")
    if rng not in RANGES:
        raise AnalyticsError(f"Unknown range: {str(rng)[:20]}")
    out["range"] = rng
    # a fixed period (the timeline filter of a dashboard) – overrides the range
    if spec.get("from") is not None or spec.get("to") is not None:
        a, b = spec.get("from"), spec.get("to")
        if not (_is_date(a) and _is_date(b)) or a > b:
            raise AnalyticsError(_t("Invalid period"))
        out["from"], out["to"] = a, b
    prof = spec.get("profiles") or []
    if not isinstance(prof, list) or len(prof) > 50 or not all(isinstance(p, int) and not isinstance(p, bool) for p in prof):
        raise AnalyticsError(_t("Invalid report"))
    out["profiles"] = sorted(set(prof))
    chart = spec.get("chart", "table")
    if chart not in CHARTS:
        raise AnalyticsError(f"Unknown chart: {str(chart)[:20]}")
    out["chart"] = chart
    return out


def date_from(rng: str, today: date) -> str | None:
    if rng == "7d":
        return (today - timedelta(days=6)).isoformat()
    if rng == "30d":
        return (today - timedelta(days=29)).isoformat()
    if rng == "year":
        return f"{today.year}-01-01"
    return None


def period_of(spec: dict, today: date) -> tuple[str | None, str]:
    """The first and last day of a report: the fixed period of a dashboard, else the range up to today."""
    if spec.get("from"):
        return spec["from"], spec["to"]
    return date_from(spec["range"], today), today.isoformat()


def build_sql(spec: dict, today: date) -> tuple[str, list]:
    """SELECT for a clean spec: only constants of the whitelist in the text, values as parameters."""
    ds = DATASETS[spec["dataset"]]
    dims = dims_of(spec["dataset"])
    fill = lambda s: s.replace("{d}", ds["date"]).replace("{p}", ds["profile"])      # noqa: E731
    used = spec["group"] + spec["rows"] + spec["columns"]
    sel = [fill(dims[d][0]) + f" AS d{i}" for i, d in enumerate(used)]
    sel += [ds["measures"][m][0] + f" AS m{i}" for i, m in enumerate(spec["data"])]
    where = [f"{ds['profile']} IN (SELECT id FROM profile WHERE role IN ('kid','parent'))"]
    args: list = []
    if ds["where"]:
        where.append(ds["where"])
    start, end = period_of(spec, today)
    if start:
        where.append(f"substr({ds['date']},1,10) >= ?")
        args.append(start)
    where.append(f"substr({ds['date']},1,10) <= ?")
    args.append(end)
    if spec["profiles"]:
        where.append(f"{ds['profile']} IN ({','.join('?' * len(spec['profiles']))})")
        args += spec["profiles"]
    sql = f"SELECT {', '.join(sel)} FROM {ds['from']} WHERE {' AND '.join(where)}"
    if used:
        n = ", ".join(str(i + 1) for i in range(len(used)))
        sql += f" GROUP BY {n} ORDER BY {n}"
    sql += f" LIMIT {MAX_ROWS + 1}"
    return sql, args


class Analytics:
    def __init__(self, db, weather=None):
        self.db = db
        self.weather = weather

    # ---------------------------------------------------------------- read-only query
    def _run(self, sql: str, args: list) -> list[tuple]:
        deadline = time.monotonic() + TIME_LIMIT
        stop = lambda: 1 if time.monotonic() > deadline else 0     # noqa: E731
        try:
            if self.db.path != ":memory:":
                conn = sqlite3.connect(Path(self.db.path).resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False)
                try:
                    conn.execute("PRAGMA query_only=ON")
                    conn.set_progress_handler(stop, 10000)
                    return conn.execute(sql, args).fetchall()
                finally:
                    conn.close()
            with self.db.lock:                                  # a database in memory (tests): the shared connection
                c = self.db.conn
                c.execute("PRAGMA query_only=ON")
                c.set_progress_handler(stop, 10000)
                try:
                    return [tuple(r.values()) for r in c.execute(sql, args).fetchall()]
                finally:
                    c.set_progress_handler(None, 0)
                    c.execute("PRAGMA query_only=OFF")
        except sqlite3.OperationalError as e:
            if "interrupt" in str(e):
                raise AnalyticsError(_t("The report took too long – choose fewer days or dimensions")) from e
            raise

    def labels(self, kind: str, values: set) -> dict:
        """Names for the values of a dimension (English source texts – translated in the UI; people's names as they are)."""
        if kind == "profile":
            return {r["id"]: r["name"] for r in self.db.q("SELECT id, name FROM profile")}
        if kind == "account":
            return {r["key"]: f"{r['icon']} {r['name']}".strip() for r in self.db.q("SELECT key, name, icon FROM account")}
        if kind == "event":
            from .rewards.engine import EVENTS
            return {v: EVENTS.get(v) or str(v).replace("_", " ").capitalize() for v in values}
        if kind == "game":
            extra = {"quiz": _t("Family quiz"), "bingo": "Bingo", "song": _t("Guess the song"), "poker": "Texas Hold'em", "cards": _t("Card games"), "-": _t("Other")}
            return {v: TITLES.get(v) or extra.get(v) or v for v in values}
        if kind == "subject":
            return {v: SUBJECTS[v][0] if v in SUBJECTS else str(v).replace("-", " ").capitalize() for v in values}
        if kind == "weather":
            cfg = self.weather.config() if self.weather else {"levels": []}
            lv = {x.get("key"): f"{x.get('icon', '')} {x.get('name', '')}".strip() for x in cfg.get("levels") or []}
            icons = {r["level"]: r["icon"] for r in self.db.q("SELECT level, MAX(icon) AS icon FROM weather_log GROUP BY level")}
            return {v: lv.get(v) or f"{icons.get(v, '')} {v}".strip() for v in values}
        return {}

    def order(self, kind: str) -> list | None:
        """A natural order for some dimensions (people as in the family list, weather from the best to the worst)."""
        if kind == "profile":
            return [r["id"] for r in self.db.q("SELECT id FROM profile ORDER BY role='parent', id")]
        if kind == "weather" and self.weather:
            return [x.get("key") for x in self.weather.config().get("levels") or []]
        return None

    def query(self, spec, today: date | None = None) -> dict:
        spec = clean_spec(spec)
        if not spec["data"]:
            raise AnalyticsError(_t("Choose at least one measure"))
        today = today or date.today()
        sql, args = build_sql(spec, today)
        rows = self._run(sql, args)
        truncated = len(rows) > MAX_ROWS
        rows = [list(r) for r in rows[:MAX_ROWS]]
        used = spec["group"] + spec["rows"] + spec["columns"]
        dims = dims_of(spec["dataset"])
        info = []
        for i, d in enumerate(used):
            kind = dims[d][1]
            vals = {r[i] for r in rows}
            lab = self.labels(kind, vals)
            info.append({"key": d, "kind": kind, "labels": {str(v): lab[v] for v in vals if v in lab},
                         "order": [str(x) for x in (self.order(kind) or []) if x in vals] or None})
        units = DATASETS[spec["dataset"]]["measures"]
        for r in rows:                                    # numbers as numbers (no -0, ints where whole)
            for j in range(len(used), len(r)):
                v = r[j] or 0
                r[j] = int(v) if float(v).is_integer() else round(float(v), 2)
        return {"spec": spec, "dims": info, "measures": [{"key": m, "unit": units[m][1]} for m in spec["data"]],
                "rows": rows, "truncated": truncated, "from": period_of(spec, today)[0], "to": period_of(spec, today)[1]}

    # ---------------------------------------------------------------- saved reports («My reports»)
    def reports(self) -> list[dict]:
        out = self.db.get_setting(SETTING, []) or []
        return [r for r in out if isinstance(r, dict) and r.get("id")]

    @staticmethod
    def _name(name) -> str:
        n = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
        if not n:
            raise AnalyticsError(_t("Please enter a name"))
        return n

    def save(self, name, spec) -> dict:
        items = self.reports()
        if len(items) >= MAX_REPORTS:
            raise AnalyticsError(_t("At most 50 saved reports"))
        r = {"id": "r" + secrets.token_hex(4), "name": self._name(name), "spec": clean_spec(spec)}
        self.db.set_setting(SETTING, items + [r])
        return r

    def update(self, rid: str, name=None, spec=None) -> dict:
        items = self.reports()
        r = next((x for x in items if x["id"] == rid), None)
        if not r:
            raise KeyError(rid)
        if name is not None:
            r["name"] = self._name(name)
        if spec is not None:
            r["spec"] = clean_spec(spec)
        self.db.set_setting(SETTING, items)
        return r

    def delete(self, rid: str) -> None:
        items = self.reports()
        if not any(x["id"] == rid for x in items):
            raise KeyError(rid)
        self.db.set_setting(SETTING, [x for x in items if x["id"] != rid])


# ---------------------------------------------------------------- dashboards
def _tile_id() -> str:
    return "t" + secrets.token_hex(4)


def standard_dashboard() -> dict:
    return {"id": "std", "name": _t("Standard dashboard"), "standard": True, "period": {"type": "month"},
            "tiles": [{"id": f"s{i}", "ref": "t:" + k, "w": w, "h": h, "title": ""} for i, (k, w, h) in enumerate(STANDARD_TILES)]}


def clean_period(p) -> dict:
    if p is None:
        return {"type": "month"}
    if not isinstance(p, dict) or p.get("type") not in PERIODS:
        raise AnalyticsError(_t("Invalid period"))
    out = {"type": p["type"]}
    if p.get("from") is not None or p.get("to") is not None:
        if not (_is_date(p.get("from")) and _is_date(p.get("to"))) or p["from"] > p["to"]:
            raise AnalyticsError(_t("Invalid period"))
        out["from"], out["to"] = p["from"], p["to"]
    elif p["type"] == "custom":
        raise AnalyticsError(_t("Invalid period"))
    return out


class Dashboards:
    """Own dashboards of the parents (setting `analytics_dashboards`, part of every backup): a name, the period of the
    timeline filter (remembered per dashboard) and tiles – each a template («t:<key>») or a saved report («r:<id>»)
    with its size and an optional title. The standard dashboard («std») is there from the start and cannot be removed."""

    def __init__(self, db, reports: Analytics):
        self.db = db
        self.an = reports

    def list(self) -> list[dict]:
        items = self.db.get_setting(DASH_SETTING, None)
        if not isinstance(items, list):
            items = [standard_dashboard()]
        items = [d for d in items if isinstance(d, dict) and d.get("id")]
        if not any(d["id"] == "std" for d in items):
            items.insert(0, standard_dashboard())
        return items

    def _clean_tiles(self, tiles) -> list[dict]:
        if not isinstance(tiles, list) or len(tiles) > MAX_TILES:
            raise AnalyticsError(_t("At most 24 tiles"))
        refs = {"t:" + t["key"] for t in TEMPLATES} | {"r:" + r["id"] for r in self.an.reports()}
        out, seen = [], set()
        for t in tiles:
            if not isinstance(t, dict) or t.get("ref") not in refs:
                raise AnalyticsError(_t("Unknown report"))
            w, hh = t.get("w", 2), t.get("h", "m")
            if not isinstance(w, int) or isinstance(w, bool) or not 1 <= w <= 4 or hh not in HEIGHTS:
                raise AnalyticsError(_t("Invalid tile size"))
            tid = t.get("id") if isinstance(t.get("id"), str) and re.fullmatch(r"[a-z0-9]{1,12}", t["id"]) and t["id"] not in seen else _tile_id()
            seen.add(tid)
            tile = {"id": tid, "ref": t["ref"], "w": w, "h": hh, "title": re.sub(r"\s+", " ", str(t.get("title") or "")).strip()[:60]}
            if t.get("chart") is not None:
                if t["chart"] not in CHARTS:
                    raise AnalyticsError(f"Unknown chart: {str(t['chart'])[:20]}")
                tile["chart"] = t["chart"]
            out.append(tile)
        return out

    def create(self, name) -> dict:
        items = self.list()
        if len(items) >= MAX_DASHBOARDS:
            raise AnalyticsError(_t("At most 20 dashboards"))
        d = {"id": "d" + secrets.token_hex(4), "name": Analytics._name(name), "period": {"type": "month"}, "tiles": []}
        self.db.set_setting(DASH_SETTING, items + [d])
        return d

    def update(self, did: str, name=None, tiles=None, period=None) -> dict:
        items = self.list()
        d = next((x for x in items if x["id"] == did), None)
        if not d:
            raise KeyError(did)
        if name is not None:
            d["name"] = Analytics._name(name)
        if tiles is not None:
            d["tiles"] = self._clean_tiles(tiles)
        if period is not None:
            d["period"] = clean_period(period)
        self.db.set_setting(DASH_SETTING, items)
        return d

    def delete(self, did: str) -> None:
        items = self.list()
        if did == "std":
            raise AnalyticsError(_t("The standard dashboard cannot be removed"))
        if not any(x["id"] == did for x in items):
            raise KeyError(did)
        self.db.set_setting(DASH_SETTING, [x for x in items if x["id"] != did])
