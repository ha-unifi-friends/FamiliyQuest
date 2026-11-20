"""The sources of the web app for the static checks of the tests.

The parent area is parent.js (core, login, menu, routing, the shared helpers) and its parts parent-photos.js …
parent-settings.js, which eltern.html loads right after it. `parent_js()` returns all of them as one text, in the
order of eltern.html – the tests that check «the parent area» read that. parent-info.js, parent-analytics.js and
parent-privacy.js have their own checks and are read on their own."""
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
PARENT_JS = ("parent.js", "parent-photos.js", "parent-overview.js", "parent-family.js", "parent-packs.js", "parent-games.js",
             "parent-chores.js", "parent-rewards.js", "parent-shop.js", "parent-calendar.js", "parent-history.js",
             "parent-settings.js")


def parent_js() -> str:
    """The whole parent area (parent.js and its parts) as one text."""
    return "\n".join((WEB / f).read_text(encoding="utf-8") for f in PARENT_JS)


def web_src(name: str) -> str:
    """A file of web/ – "parent.js" stands for the whole parent area (parent_js)."""
    return parent_js() if name == "parent.js" else (WEB / name).read_text(encoding="utf-8")
