"""Behaviour weather: parents give each child a weather of the day – ☀️ with a bonus, 🌧️ or ⛈️ with a malus.

The levels (icon, name, points) and the daily reset time are set in the parent area. Setting a level books its points
once. At the reset time (default 12:00) every child is back at the default level – nothing is booked for that.
A child only ever sees its own weather.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .db import Database
from .rewards.engine import Rewards


def _t(s: str) -> str:
    return s


DEFAULT = {
    "enabled": True,
    "levels": [
        {"key": "sun", "icon": "☀️", "name": _t("Sunny"), "points": 5},
        {"key": "cloudy", "icon": "⛅", "name": _t("Cloudy"), "points": 0},
        {"key": "rain", "icon": "🌧️", "name": _t("Rain"), "points": -5},
        {"key": "storm", "icon": "⛈️", "name": _t("Thunderstorm"), "points": -10},
    ],
    "default": "sun",
    "reset": "12:00",
    "account": "coins",
}
DAYS = 30


class WeatherError(ValueError):
    pass


class Weather:
    def __init__(self, db: Database, rewards: Rewards):
        self.db = db
        self.rewards = rewards

    # ---------------------------------------------------------------- configuration
    def config(self) -> dict:
        c = self.db.get_setting("weather") or {}
        return {**DEFAULT, **c}

    def save_config(self, c: dict) -> dict:
        levels = []
        for i, lv in enumerate(c.get("levels") or []):
            icon = str(lv.get("icon") or "").strip()[:8]
            name = str(lv.get("name") or "").strip()[:40]
            if not icon:
                raise WeatherError("Every weather needs a symbol")
            key = str(lv.get("key") or "").strip()[:20] or f"w{i}"
            if any(x["key"] == key for x in levels):
                key = f"{key}{i}"
            try:
                pts = float(lv.get("points") or 0)
            except (TypeError, ValueError):
                raise WeatherError("Points must be a number") from None
            levels.append({"key": key, "icon": icon, "name": name, "points": max(-1000, min(1000, pts))})
        if not 2 <= len(levels) <= 8:
            raise WeatherError("Choose between 2 and 8 weathers")
        reset = str(c.get("reset") or "12:00")
        try:
            datetime.strptime(reset, "%H:%M")
        except ValueError:
            raise WeatherError("Reset time must look like 12:00") from None
        default = c.get("default") if any(x["key"] == c.get("default") for x in levels) else levels[0]["key"]
        account = str(c.get("account") or "coins")
        if not self.db.q1("SELECT 1 FROM account WHERE key=?", account):
            raise WeatherError("Unknown account")
        out = {"enabled": bool(c.get("enabled", True)), "levels": levels, "default": default, "reset": reset, "account": account}
        self.db.set_setting("weather", out)
        return out

    # ---------------------------------------------------------------- state
    def last_reset(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now()
        hh, mm = map(int, self.config()["reset"].split(":"))
        r = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return r if r <= now else r - timedelta(days=1)

    def _level(self, key: str) -> dict | None:
        c = self.config()
        for i, lv in enumerate(c["levels"]):
            if lv["key"] == key:
                return {**lv, "rank": i}
        return None

    def current(self, pid: int, now: datetime | None = None) -> dict | None:
        c = self.config()
        if not c["enabled"]:
            return None
        since = self.last_reset(now).strftime("%Y-%m-%d %H:%M:%S")
        r = self.db.q1("SELECT * FROM weather_log WHERE profile_id=? AND at>=? ORDER BY id DESC LIMIT 1", pid, since)
        lv = self._level(r["level"]) if r else None
        if r and not lv:   # level was removed later – show what was set
            lv = {"key": r["level"], "icon": r["icon"], "name": "", "points": r["points"], "rank": r["rank"]}
        lv = lv or self._level(c["default"]) or {**c["levels"][0], "rank": 0}
        return {**lv, "set_at": r["at"] if r else None, "until": (self.last_reset(now) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")}

    def set(self, pid: int, key: str, by_id: int | None = None) -> dict:
        c = self.config()
        if not c["enabled"]:
            raise WeatherError("The weather is switched off")
        lv = self._level(key)
        if not lv:
            raise WeatherError("Unknown weather")
        self.db.x("INSERT INTO weather_log(profile_id,level,icon,rank,points,by_id) VALUES(?,?,?,?,?,?)",
                  pid, lv["key"], lv["icon"], lv["rank"], lv["points"], by_id)
        if lv["points"]:
            self.rewards.book(pid, c["account"], lv["points"], "weather", f"{lv['icon']} {lv['name']}".strip(), "weather")
        return self.current(pid)

    def history(self, pid: int, days: int = DAYS, today: date | None = None) -> list[dict]:
        """One entry per day (oldest first): the worst weather set that day, or None when nobody set one."""
        today = today or date.today()
        start = today - timedelta(days=days - 1)
        rows = self.db.q("SELECT date(at) d, MAX(rank) rk, COUNT(*) n FROM weather_log WHERE profile_id=? AND date(at)>=? "
                         "GROUP BY date(at)", pid, start.isoformat())
        by = {r["d"]: r for r in rows}
        out = []
        for i in range(days):
            d = (start + timedelta(days=i)).isoformat()
            r = by.get(d)
            icon = None
            if r:
                x = self.db.q1("SELECT icon FROM weather_log WHERE profile_id=? AND date(at)=? AND rank=? ORDER BY id DESC LIMIT 1",
                               pid, d, r["rk"])
                icon = x["icon"]
            out.append({"date": d, "rank": r["rk"] if r else None, "icon": icon, "count": r["n"] if r else 0})
        return out
