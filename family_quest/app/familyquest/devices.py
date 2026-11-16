"""Home Assistant devices for a profile: e.g. a child switches and dims the light in its own room.

Parents choose the entities per profile (profile setting `devices`). The learning app shows only those and may only
control those – the server checks every call. Supported:
  light (on/off, brightness if the light can dim), switch / input_boolean / fan (on/off),
  cover (open / stop / close), scene and script (run).
"""
from __future__ import annotations

DOMAINS = ("light", "switch", "input_boolean", "fan", "cover", "scene", "script")
ACTIONS = {
    "light": {"on", "off", "brightness"},
    "switch": {"on", "off"}, "input_boolean": {"on", "off"}, "fan": {"on", "off"},
    "cover": {"open", "close", "stop"},
    "scene": {"run"}, "script": {"run"},
}


class DeviceError(ValueError):
    pass


def view(state: dict) -> dict:
    """What the app shows for one entity."""
    eid = state["entity_id"]
    domain = eid.split(".", 1)[0]
    a = state.get("attributes") or {}
    modes = a.get("supported_color_modes") or []
    dimmable = domain == "light" and (any(m != "onoff" for m in modes) or "brightness" in a)
    bri = a.get("brightness")
    return {"entity_id": eid, "domain": domain, "name": a.get("friendly_name") or eid, "state": state.get("state"),
            "on": state.get("state") in ("on", "open", "opening"), "dimmable": dimmable,
            "brightness": round(int(bri) * 100 / 255) if isinstance(bri, (int, float)) else None,
            "available": state.get("state") not in ("unavailable", "unknown", None)}


def service_call(entity_id: str, action: str, value: int | None = None) -> tuple[str, str, dict]:
    """(domain, service, data) for an action – raises DeviceError for what the entity cannot do."""
    domain = entity_id.split(".", 1)[0]
    if domain not in DOMAINS or action not in ACTIONS[domain]:
        raise DeviceError("This device cannot do that")
    data = {"entity_id": entity_id}
    if domain == "light":
        if action == "brightness":
            pct = max(1, min(100, int(value or 0)))
            return "light", "turn_on", {**data, "brightness_pct": pct}
        return "light", "turn_on" if action == "on" else "turn_off", data
    if domain == "cover":
        return "cover", {"open": "open_cover", "close": "close_cover", "stop": "stop_cover"}[action], data
    if domain in ("scene", "script"):
        return domain, "turn_on", data
    return domain, "turn_on" if action == "on" else "turn_off", data
