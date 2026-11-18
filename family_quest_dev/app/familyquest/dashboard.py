"""Family Quest Dashboard: a read-only page for a kiosk browser (wall tablet, TV, old phone).

The page /dashboard?key=… needs no login – the key (setting `dashboard.key`, new on demand) is its password, so any
kiosk browser can show it. Parents choose in the parent area what it shows: per child avatar (with crown),
weather, learning progress, streak, coins, open chores; for the family the family goal, open to-dos of the
Planer, today's calendar events and a clock. Nothing private (moods, PINs, ledger) is ever sent.
"""
from __future__ import annotations

import hmac
import secrets
import time

from .db import profile_settings

WIDGETS = ["clock", "weather_alarm", "crown", "weather", "learning", "streak", "coins", "chores", "family_goal", "todos", "events"]
DEFAULT = {
    "enabled": False,
    "key": "",
    "title": "Family Quest",
    "kids": [],                 # empty = all children
    "widgets": ["clock", "crown", "learning", "streak", "coins", "chores", "family_goal", "todos"],
    "calendars": [],            # Home Assistant calendar entities for «events»
    "weather_entity": "",       # weather alarm: a weather entity of Home Assistant
    "weather_hours": 12,        # … looking this many hours ahead
    "rain_chance": 50,          # … rain hint from this chance of rain (%)
    "kids_alarm": True,         # … also on the children's start page
    "theme": "auto",            # auto | light | dark
    "refresh": 60,              # seconds
}
KEY = "dashboard"


class DashboardError(ValueError):
    pass


class Dashboard:
    def __init__(self, fq):
        self.fq = fq
        self._events: tuple[float, list] = (0.0, [])

    def config(self) -> dict:
        return {**DEFAULT, **(self.fq.db.get_setting(KEY) or {})}

    def save(self, c: dict) -> dict:
        cur = self.config()
        out = dict(cur)
        if "enabled" in c:
            out["enabled"] = bool(c["enabled"])
        if "title" in c:
            out["title"] = str(c["title"] or "").strip()[:60] or "Family Quest"
        if "kids" in c:
            out["kids"] = [int(x) for x in c["kids"] or [] if str(x).isdigit()]
        if "widgets" in c:
            out["widgets"] = [w for w in WIDGETS if w in (c["widgets"] or [])]
        if "calendars" in c:
            cals = [str(x) for x in c["calendars"] or []]
            if any(not x.startswith("calendar.") for x in cals):
                raise DashboardError("Calendars: calendar entities, e.g. calendar.family")
            out["calendars"] = cals[:10]
        if "weather_entity" in c:
            w = str(c["weather_entity"] or "")
            if w and not w.startswith("weather."):
                raise DashboardError("Weather: a weather entity, e.g. weather.home")
            out["weather_entity"] = w
        for k, lo, hi in (("weather_hours", 1, 48), ("rain_chance", 10, 100)):
            if k in c:
                out[k] = max(lo, min(hi, int(c[k] or DEFAULT[k])))
        if "kids_alarm" in c:
            out["kids_alarm"] = bool(c["kids_alarm"])
        if "theme" in c:
            if c["theme"] not in ("auto", "light", "dark"):
                raise DashboardError("Unknown setting")
            out["theme"] = c["theme"]
        if "refresh" in c:
            out["refresh"] = max(15, min(3600, int(c["refresh"] or 60)))
        if out["enabled"] and not out["key"]:
            out["key"] = secrets.token_urlsafe(18)
        self.fq.db.set_setting(KEY, out)
        return out

    def new_key(self) -> dict:
        c = self.config()
        c["key"] = secrets.token_urlsafe(18)
        self.fq.db.set_setting(KEY, c)
        return c

    def check(self, key: str) -> dict:
        c = self.config()
        if not c["enabled"] or not c["key"] or not hmac.compare_digest(str(key or ""), c["key"]):
            raise DashboardError("Dashboard key not valid")
        return c

    # ---------------------------------------------------------------- data
    def data(self, key: str) -> dict:
        c = self.check(key)
        w = set(c["widgets"])
        fq = self.fq
        kids = [k for k in fq.kids() if not c["kids"] or k["id"] in c["kids"]]
        accounts = [a for a in fq.rewards.accounts() if a["active"] and a["spendable"] and a["key"] != "xp"]
        out_kids = []
        for k in kids:
            pub = fq.profile_public(k)
            d = {"id": k["id"], "name": k["name"], "color": k["color"], "avatar": pub["avatar"] if "crown" in w else _no_crown(fq, k),
                 "crown": bool(pub.get("crown")) and "crown" in w}
            if "weather" in w:
                cur = fq.weather.current(k["id"])
                d["weather"] = {"icon": cur["icon"], "name": cur.get("name", "")} if cur else None
            if "learning" in w:
                d["learning"] = {"xp_today": fq.rewards.xp_today(k["id"]), "goal": int(profile_settings(k)["daily_goal"]),
                                 "level": fq.rewards.level(k["id"])["level"]}
            if "streak" in w:
                d["streak"] = fq.rewards.streak(k["id"])
            if "coins" in w:
                bal = fq.rewards.balances(k["id"])
                d["balances"] = [{"icon": a["icon"], "name": a["name"], "value": bal.get(a["key"], 0)} for a in accounts]
            if "chores" in w:
                try:
                    ch = fq.all_chores(k) or []
                except Exception:  # noqa: BLE001 – a Planer hiccup must not break the wall display
                    ch = []
                d["chores"] = [{"icon": x.get("icon") or "🧹", "title": x.get("summary") or x.get("title") or "", "done": bool(x.get("done"))}
                               for x in ch]
            out_kids.append(d)
        out = {"title": c["title"], "theme": c["theme"], "refresh": c["refresh"], "widgets": c["widgets"], "kids": out_kids,
               "now": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "crest": (fq.db.get_setting("memory") or {}).get("crest"),
               "special_times": fq.calendar.special(None)}
        if "family_goal" in w:
            out["family_goal"] = fq.family_goal()
        if "todos" in w:
            out["todos"] = self._todos(kids)
        if "weather_alarm" in w:
            out["weather_alarm"] = self.weather_alarm()
        if "events" in w:
            out["events"] = self._own_events() + self._calendar(c["calendars"])
            out["events"].sort(key=lambda e: e["start"])
        return out

    def weather_alarm(self) -> dict | None:
        """What to take along today (weatheralarm.py) – cached for 10 minutes."""
        from .weatheralarm import alerts
        c = self.config()
        ent, ha = c.get("weather_entity"), self.fq.ha
        if not ent or not ha or not ha.connected:
            return None
        at, key, cached = getattr(self, "_wx", (0.0, None, None))
        if key == ent and time.time() - at < 600:
            return cached
        try:
            state, forecast = ha.weather_forecast(ent)
            res = alerts(state, forecast, c)
        except Exception:  # noqa: BLE001
            res = cached
        self._wx = (time.time(), ent, res)
        return res

    def _own_events(self) -> list[dict]:
        """Events of the family calendar today and tomorrow."""
        from datetime import date, timedelta
        today = date.today()
        try:
            rows = self.fq.calendar.own(today.isoformat(), (today + timedelta(days=1)).isoformat())
        except Exception:  # noqa: BLE001
            return []
        return [{"title": (r["icon"] + " " if r["icon"] else "") + r["title"], "start": r["start"], "end": r["end"],
                 "all_day": r["all_day"], "calendar": "family"} for r in rows]

    def _todos(self, kids: list[dict]) -> list[dict]:
        host = self.fq.planer_host
        if not host or not getattr(host, "planner", None) or not host.planner.data:
            return []
        bridge = getattr(host, "bridge", None)
        names = {}
        for k in kids:
            pid = bridge.person_of(k["id"]) if bridge else None
            if pid:
                names[pid] = k["name"]
        persons = host.planner.data.get("persons", {})
        out = []
        for tid, t in host.planner.data.get("todos", {}).items():
            if t.get("done"):
                continue
            pid = t.get("person_id")
            out.append({"title": t.get("title", ""), "who": names.get(pid) or (persons.get(pid) or {}).get("name", ""),
                        "created": t.get("created") or ""})
        return sorted(out, key=lambda t: t["created"])[:20]

    def _calendar(self, calendars: list[str]) -> list[dict]:
        """Today's and tomorrow's events (cached for 5 minutes)."""
        ha = self.fq.ha
        if not calendars or not ha or not ha.connected:
            return []
        at, cached = self._events
        if time.time() - at < 300:
            return cached
        try:
            ev = ha.calendar_events(calendars, hours=36)
        except Exception:  # noqa: BLE001
            ev = cached
        self._events = (time.time(), ev)
        return ev


def _no_crown(fq, k: dict) -> dict:
    import json
    try:
        return json.loads(k["avatar"] or "{}")
    except ValueError:
        return {}
