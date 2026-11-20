"""Live weather and daylight for the season scenes of the app header (kid app, like the Family Planer card).

The weather entity is the one of the Family Planer (setting `seasons.weather` of the planner, «Seasons & weather»):
one choice for the planner cards and the app. «Day and night follow the sun» (setting `season_live.sun`, on by
default) reads `sun.sun`; without it the app decides by the clock (night 20–6), as the planner card does.

The states come from the planner's mirror of Home Assistant (planer.host: every state, kept live by the state events);
only when that has nothing yet, Home Assistant is asked directly. The answer is cached for a few minutes and holds
only what the scene needs (no entity ids, no token). The weather shape is that of FPSEASON.weather (web/planer):
{state, kind, icon, temp, unit, wind} – the same tables as there.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import date

from . import themes

log = logging.getLogger(__name__)
TTL = 180                     # seconds the answer is reused
DEFAULT = {"sun": True}

# Home Assistant weather state → icon (FPSEASON COND) and one of the 10 scene states (FPSEASON KIND)
ICON = {"sunny": "☀️", "clear-night": "🌙", "partlycloudy": "⛅", "cloudy": "☁️", "rainy": "🌧️", "pouring": "🌧️",
        "lightning": "🌩️", "lightning-rainy": "⛈️", "snowy": "🌨️", "snowy-rainy": "🌨️", "hail": "🌨️", "fog": "🌫️",
        "windy": "💨", "windy-variant": "💨", "exceptional": "⚠️"}
KIND = {"sunny": "sunny", "clear-night": "clear-night", "partlycloudy": "partlycloudy", "cloudy": "cloudy", "rainy": "rainy",
        "pouring": "pouring", "lightning": "lightning", "lightning-rainy": "lightning", "snowy": "snowy", "snowy-rainy": "snowy",
        "hail": "pouring", "fog": "fog", "windy": "windy", "windy-variant": "windy", "exceptional": "lightning"}
_WIND = {"m/s": 3.6, "mph": 1.609, "kn": 1.852}


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def weather_of(state: str | None, attrs: dict | None) -> dict | None:
    """A weather entity's state → the FPSEASON.weather shape; unavailable / unknown → None."""
    if not state or state in ("unavailable", "unknown"):
        return None
    a = attrs or {}
    t = _num(a.get("temperature"))
    w = _num(a.get("wind_speed"))
    wind = round(w * _WIND.get(str(a.get("wind_speed_unit") or "km/h"), 1), 1) if w is not None else 0
    return {"state": state, "kind": KIND.get(state, "cloudy"), "icon": ICON.get(state, ICON["cloudy"]),
            "temp": round(t) if t is not None else None, "unit": str(a.get("temperature_unit") or "°")[:4], "wind": wind}


def light_of(state: str | None, attrs: dict | None) -> dict | None:
    """sun.sun → {night, dusk ('dawn' | 'dusk' | None), elevation} – the rules of the planner card (_light)."""
    if not state or state in ("unavailable", "unknown"):
        return None
    a = attrs or {}
    el = _num(a.get("elevation"))
    night = state == "below_horizon" and not (el is not None and el > -2)
    dusk = ("dawn" if a.get("rising") else "dusk") if el is not None and -4 < el < 6 else None
    return {"night": night, "dusk": dusk, "elevation": round(el) if el is not None else None}


def config(fq) -> dict:
    c = fq.db.get_setting("season_live") or {}
    return {"weather": weather_entity(fq) or None, "sun": c.get("sun", DEFAULT["sun"]) is not False}


def _planner(fq):
    """The running planner with its settings loaded, else None."""
    host = getattr(fq, "planer_host", None)
    p = getattr(host, "planner", None) if host else None
    data = getattr(p, "data", None) if p is not None else None
    return p if isinstance(data, dict) and isinstance(data.get("settings"), dict) else None


def weather_entity(fq) -> str | None:
    """The weather entity of the season designs – the planner's (one setting for the planner cards and the app)."""
    p = _planner(fq)
    if p is not None:
        try:
            return p.season_settings().get("weather")
        except Exception:  # noqa: BLE001 – planner not loaded yet
            pass
    return (fq.db.get_setting("season_live") or {}).get("weather")


def save(fq, body: dict) -> dict:
    """{"weather": "weather.x" | None, "sun": bool} – the weather entity goes to the planner (and a copy here)."""
    from .planer import validate
    cur = fq.db.get_setting("season_live") or {}
    new = dict(cur)
    if "sun" in body:
        new["sun"] = body.get("sun") is not False
    if "weather" in body:
        ent = validate.entity(body.get("weather"), ("weather",))
        if body.get("weather") and not ent:
            raise ValueError("Weather: a weather entity, e.g. weather.home")
        new["weather"] = ent
        host = getattr(fq, "planer_host", None)
        p = _planner(fq)
        if p is not None and getattr(host, "loop", None):
            fut = asyncio.run_coroutine_threadsafe(p.async_save_section("seasons", {"weather": ent}), host.loop)
            fut.result(15)
    fq.db.set_setting("season_live", new)
    clear(fq)
    return config(fq)


def clear(fq) -> None:
    fq.__dict__.pop("_season_live", None)


def _state(fq, eid: str) -> tuple[str | None, dict]:
    host = getattr(fq, "planer_host", None)
    hass = getattr(host, "hass", None) if host else None
    st = hass.states.get(eid) if hass is not None else None
    if st is not None:
        return st.state, dict(st.attributes or {})
    ha = getattr(fq, "ha", None)
    client = getattr(ha, "client", None) if ha else None
    if ha is not None and client is not None and getattr(ha, "connected", False):
        try:
            d = ha._sync(client.get_state(eid)) or {}
            return d.get("state"), d.get("attributes") or {}
        except Exception:  # noqa: BLE001 – Home Assistant busy: no live data this time
            log.debug("cannot read %s", eid, exc_info=True)
    return None, {}


def live(fq, today: date | None = None) -> dict | None:
    """What the scene needs now: {wx, night, dusk, elevation, jz, storm} or None (nothing live → the clock decides)."""
    cfg = config(fq)
    key = (cfg["weather"], cfg["sun"])
    hit = fq.__dict__.get("_season_live")
    if hit and hit[0] == key and time.monotonic() - hit[1] < TTL:
        return hit[2]
    wx = weather_of(*_state(fq, cfg["weather"])) if cfg["weather"] else None
    lt = light_of(*_state(fq, "sun.sun")) if cfg["sun"] else None
    out = None
    if wx or lt:
        storm = 50
        p = _planner(fq)
        if p is not None:
            try:
                storm = int(p.season_settings().get("storm_kmh") or 50)
            except Exception:  # noqa: BLE001
                pass
        out = {"wx": wx, "night": lt["night"] if lt else None, "dusk": lt["dusk"] if lt else None,
               "elevation": lt["elevation"] if lt else None, "jz": themes.jz(today), "storm": storm}
    fq.__dict__["_season_live"] = (key, time.monotonic(), out)
    return out
