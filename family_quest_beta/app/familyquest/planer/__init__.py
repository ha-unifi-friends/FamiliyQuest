"""Family Planer module of Family Quest.

The pure logic in this package (engine, schedule, rewards, awards, levels, sonder, seasons,
vacation, lists, msgqueue, persontodos, speech, validate, settings_spec, const) is taken over
from Family Planer by magibuilds (https://github.com/magi1982/family-planer, MIT License, see
LICENSE.family-planer) and kept as close to the original as possible so fixes can flow both ways.
"""


def get_planner(hass, entry_id=None):
    """The planner of this Family Quest installation (websocket.py looks it up like in Home Assistant)."""
    host = getattr(hass, "planer_host", None)
    return host.planner if host else None
