"""Family Quest version of the Family Planer repair issues.

In Home Assistant these were entries in the repair dashboard. Here they are kept on the planner
(`planner.issues`) and shown in the parent area: missing entities and the still active start PIN.
Logic adapted from Family Planer (MIT, magibuilds).
"""
from __future__ import annotations


def _issues(planner) -> dict:
    if not hasattr(planner, "issues"):
        planner.issues = {"missing": [], "default_pin": False}
    return planner.issues


def async_check_entities(hass, planner) -> None:
    """Remember every configured entity (calendar, list, sensor, speaker, AI) that Home Assistant does not know."""
    st = planner.settings
    ann = st.get("announce") or {}
    wanted: dict[str, str] = {}
    for p in planner.data["persons"].values():
        if p.get("calendar"):
            wanted[p["calendar"]] = p["name"]
    for lst in planner.data["lists"].values():
        wanted[lst["entity"]] = lst["name"]
    if ann.get("enabled"):
        for ent in [*(ann.get("motion") or []), *(ann.get("notify") or []), *(ann.get("media_players") or [])]:
            wanted[ent] = ent
        if ann.get("tts"):
            wanted[ann["tts"]] = ann["tts"]
    if st.get("ai_task"):
        wanted[st["ai_task"]] = "AI"
    if not hass.started or hass.service_caller is None:      # without Home Assistant nothing can be checked
        _issues(planner)["missing"] = []
        return
    _issues(planner)["missing"] = [{"entity": e, "used_by": u} for e, u in wanted.items() if hass.states.get(e) is None]


def async_check_pin(hass, planner) -> None:
    """Warn while the well-known start PIN 123456 is still active."""
    _issues(planner)["default_pin"] = bool(planner.pin_default)
