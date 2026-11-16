"""Weather alarm for the family: from a weather entity of Home Assistant (any weather integration) the dashboard
and the children's start page show what to take along today – «rain jacket or umbrella», «thunderstorm possible» …

The current state and the hourly forecast of the next hours are looked at (daily forecast as fallback). A hint comes
when the condition says so, or when the chance of rain reaches the threshold. Nothing is stored.
"""
from __future__ import annotations

from datetime import datetime, timedelta

ICONS = {"sunny": "☀️", "clear-night": "🌙", "partlycloudy": "⛅", "cloudy": "☁️", "fog": "🌫️", "rainy": "🌧️",
         "pouring": "🌧️", "lightning": "🌩️", "lightning-rainy": "⛈️", "snowy": "🌨️", "snowy-rainy": "🌨️",
         "hail": "🌨️", "windy": "💨", "windy-variant": "💨", "exceptional": "⚠️"}
RAIN = {"rainy", "pouring", "lightning-rainy", "snowy-rainy", "hail"}
STORM = {"lightning", "lightning-rainy"}
SNOW = {"snowy", "snowy-rainy", "hail"}
WIND = {"windy", "windy-variant"}

# the hints, most important first (English source – translated in the app)
HINTS = {
    "storm": ("⛈️", "Thunderstorm possible – better stay inside when it starts."),
    "rain": ("🌂", "Rain today – take your rain jacket or umbrella!"),
    "snow": ("🧤", "Snow – warm shoes, gloves and a cap!"),
    "wind": ("💨", "Strong wind – hold on to your cap!"),
    "cold": ("🧣", "Cold today – put on a warm jacket!"),
    "hot": ("🧢", "Hot today – drink a lot, sun cream and a cap!"),
}
DEFAULTS = {"weather_entity": "", "weather_hours": 12, "rain_chance": 50, "cold_below": 3, "hot_above": 28, "wind_above": 50}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def alerts(state: dict | None, forecast: list[dict], cfg: dict, now: datetime | None = None) -> dict:
    """{"now": {"icon", "condition", "temperature", "unit"}, "hints": [{"key", "icon", "text"}]}"""
    cfg = {**DEFAULTS, **(cfg or {})}
    now = now or datetime.now()
    until = now + timedelta(hours=int(cfg["weather_hours"] or 12))
    attrs = (state or {}).get("attributes") or {}
    cond_now = (state or {}).get("state")
    upcoming = []
    for f in forecast or []:
        try:
            t = datetime.fromisoformat(str(f.get("datetime", "")).replace("Z", "+00:00"))
            if t.tzinfo:
                t = t.astimezone().replace(tzinfo=None)
        except ValueError:
            continue
        if t <= until:
            upcoming.append(f)
    conds = {cond_now} | {f.get("condition") for f in upcoming}
    chance = max([_num(f.get("precipitation_probability")) or 0 for f in upcoming] or [0])
    temps = [x for x in [_num(attrs.get("temperature"))] + [_num(f.get("temperature")) for f in upcoming] + [_num(f.get("templow")) for f in upcoming] if x is not None]
    winds = [x for x in [_num(attrs.get("wind_speed"))] + [_num(f.get("wind_speed")) for f in upcoming] if x is not None]
    hints = []
    if conds & STORM:
        hints.append("storm")
    if conds & RAIN or chance >= float(cfg["rain_chance"]):
        hints.append("rain")
    if conds & SNOW:
        hints.append("snow")
    if conds & WIND or (winds and max(winds) >= float(cfg["wind_above"])):
        hints.append("wind")
    if temps and min(temps) <= float(cfg["cold_below"]) and "snow" not in hints:
        hints.append("cold")
    if temps and max(temps) >= float(cfg["hot_above"]):
        hints.append("hot")
    return {"now": {"icon": ICONS.get(cond_now, "🌡️"), "condition": cond_now, "temperature": _num(attrs.get("temperature")),
                    "unit": attrs.get("temperature_unit") or "°C", "chance": int(chance)} if state else None,
            "hints": [{"key": k, "icon": HINTS[k][0], "text": HINTS[k][1]} for k in hints]}
