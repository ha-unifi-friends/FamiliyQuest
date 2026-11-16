"""Move the chores of the own Family Quest chore plan into the built-in Family Planer (one chore plan).

Mapping (own plan → Planer):
* daily → every weekday; weekdays → those weekdays; weekly → Monday with 7 days to do it
* fixed → every chosen child; rotate weekly → child i every n-th week (same order as before);
  rotate daily → the weekdays are shared out in turn (Mon child 1, Tue child 2, …) – the Planer has no daily rotation
* points stay; icon goes in front of the title; a Planer without chores counts points per chore
  (its default «fair» shares a fixed number of points per day out over the day's chores)
* «once» chores stay in the own plan (they are special chores in the Planer – please create them there)
* duty/bonus and the parent confirmation do not exist in the Planer
Moved chores are switched off in the own plan (their history stays).
"""
from __future__ import annotations

from datetime import date

from . import engine

FQ_EPOCH = date(2024, 1, 1)        # chores.EPOCH – rotation of the own plan counts weeks from here


def _days(ch: dict) -> list[int]:
    if ch["frequency"] == "daily":
        return list(range(1, 8))
    if ch["frequency"] == "weekdays":
        return [d + 1 for d in ch["weekdays"]]          # own plan: 0 = Monday, Planer: "1" = Monday
    return [1]                                          # weekly: Monday, 7 days to do it


def to_planer(ch: dict, person_of: dict[int, str]) -> dict | None:
    if ch["frequency"] == "once":
        return None
    people = [person_of[p] for p in ch["profiles"] if p in person_of]
    if not people:
        return None
    window = 7 if ch["frequency"] == "weekly" else 1
    days = _days(ch)
    assign: dict[str, dict] = {}
    if ch["assign"] != "rotate" or len(people) == 1:
        for pid in people:
            assign[pid] = {str(d): {"every": 1, "offset": 0, "window": window} for d in days}
    elif ch["rotate_every"] == "week" or ch["frequency"] == "weekly":
        n = len(people)
        k0 = engine.week_index(FQ_EPOCH)
        for i, pid in enumerate(people):
            assign[pid] = {str(d): {"every": n, "offset": (i + k0) % n, "window": window} for d in days}
    else:
        for j, d in enumerate(days):
            assign.setdefault(people[j % len(people)], {})[str(d)] = {"every": 1, "offset": 0, "window": window}
    icon = (ch.get("icon") or "").strip()
    return {"title": f"{icon} {ch['name']}".strip(), "assign": assign, "points": int(round(ch.get("points") or 0))}


async def migrate(fq) -> dict:
    host = fq.planer_host
    bridge = host.bridge
    await bridge.sync()                                  # every profile has its person
    person_of = {int(k): v for k, v in bridge.state()["links"].items()}
    moved, kept = [], []
    planner = host.planner
    if not planner.data.get("chores"):
        # a fresh Planer: count the points per chore like the own plan did (instead of «fair»: points per day shared out)
        game = planner.settings.setdefault("gamification", {})
        game.setdefault("mode", "per_chore")
    for ch in fq.chores.list(active_only=True):
        spec = to_planer(ch, person_of)
        if spec is None:
            kept.append(ch["name"])
            continue
        await host.planner.async_save_chore(None, spec)
        fq.chores.delete(ch["id"])                        # switched off, history stays
        moved.append(ch["name"])
    return {"moved": moved, "kept": kept}
