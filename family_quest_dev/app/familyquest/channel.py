"""Release channel of this app: stable / beta (normal) or «Family Quest Dev» (tools/publish_dev.py).

The dev app carries a marker file `app/CHANNEL` (in the container /app/CHANNEL) with the word `dev`; without it the
channel is normal. The environment variable FQ_CHANNEL overrides the file (local test servers).

Games still in development (DEV_GAMES) exist only in the dev channel: elsewhere they are not in the games lists, the
access settings, FamilyTime, the Facts quiz or the running tables, and their API answers 404. Their code and tests stay
in the repository; history entries of families that played them keep showing.
"""
from __future__ import annotations

import os
from pathlib import Path

CHANNEL_FILE = Path(__file__).resolve().parent.parent / "CHANNEL"
# too complex to play yet – reworked before they go to the beta (docs/BACKLOG.md)
DEV_GAMES = frozenset({"stempeljagd"})

_channel: str | None = None         # read once; tests set it with monkeypatch (tests/test_channel.py)


def channel() -> str:
    """«dev» or «» (stable and beta)."""
    global _channel
    if _channel is None:
        value = os.environ.get("FQ_CHANNEL")
        if value is None:
            try:
                value = CHANNEL_FILE.read_text(encoding="utf-8")
            except OSError:
                value = ""
        _channel = value.strip().lower()
    return _channel


def is_dev() -> bool:
    return channel() == "dev"


def hidden_games() -> frozenset:
    """The games that do not exist in this channel."""
    return frozenset() if is_dev() else DEV_GAMES


def visible(games) -> tuple:
    hide = hidden_games()
    return tuple(g for g in games if g not in hide)


class ChannelGames:
    """A class attribute with the games of this channel (works on the class and on instances, read at call time)."""

    def __init__(self, games: tuple):
        self.games = tuple(games)

    def __get__(self, obj, owner=None) -> tuple:
        return visible(self.games)
