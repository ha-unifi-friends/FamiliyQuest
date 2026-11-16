"""The children's own bots: they make them in the avatar area (name, emoji, colour, how well it plays) and can share
them with the family. Bots sit at the card tables and the poker table; the animal bots fill the free seats.
"""
from __future__ import annotations

import random
import re

from .community import CommunityError

LEVELS = ("easy", "normal", "hard")
EMOJIS = ["🤖", "👾", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐵", "🐔", "🐧", "🦉", "🦄", "🐝", "🐙", "🦖", "🐲",
          "🦈", "🐳", "🦜", "🐢", "👻", "🧙", "🧚", "🦸", "🥷", "🧛", "🎃", "⭐", "🌈", "🍕", "⚽", "🚀"]
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_BOTS = 12


class Bots:
    def __init__(self, db):
        self.db = db
        self.pets = None          # pets.Pets – the own living pets play along as bots ("pet:<id>")

    def visible(self, pid: int) -> list[dict]:
        """My bots and the ones others share – with the owner's name."""
        return self.db.q("""SELECT b.*, p.name AS owner FROM bot b LEFT JOIN profile p ON p.id=b.owner_id
                            WHERE b.owner_id=? OR b.shared=1 ORDER BY b.owner_id!=?, b.name""", pid, pid)

    def _clean(self, data: dict) -> dict:
        name = str(data.get("name") or "").strip()[:24]
        if not name:
            raise CommunityError("Give your bot a name")
        emoji = data.get("emoji") if data.get("emoji") in EMOJIS else "🤖"
        color = data.get("color") if isinstance(data.get("color"), str) and COLOR.match(data["color"]) else "#5b5bd6"
        level = data.get("level") if data.get("level") in LEVELS else "normal"
        return {"name": name, "emoji": emoji, "color": color, "level": level, "shared": int(bool(data.get("shared")))}

    def save(self, prof: dict, data: dict, bot_id: int | None = None) -> int:
        d = self._clean(data)
        if bot_id is None:
            if int(self.db.val("SELECT COUNT(*) FROM bot WHERE owner_id=?", prof["id"], default=0)) >= MAX_BOTS:
                raise CommunityError("You have enough bots – delete one first")
            return self.db.x("INSERT INTO bot(owner_id, name, emoji, color, level, shared) VALUES(?,?,?,?,?,?)",
                             prof["id"], d["name"], d["emoji"], d["color"], d["level"], d["shared"])
        self._mine(prof, bot_id)
        self.db.x("UPDATE bot SET name=?, emoji=?, color=?, level=?, shared=? WHERE id=?",
                  d["name"], d["emoji"], d["color"], d["level"], d["shared"], bot_id)
        return bot_id

    def _mine(self, prof: dict, bot_id: int) -> dict:
        b = self.db.q1("SELECT * FROM bot WHERE id=?", bot_id)
        if not b:
            raise CommunityError("Unknown bot")
        if b["owner_id"] != prof["id"] and prof["role"] != "parent":
            raise CommunityError("Only your own bots")
        return b

    def delete(self, prof: dict, bot_id: int) -> None:
        self._mine(prof, bot_id)
        self.db.x("DELETE FROM bot WHERE id=?", bot_id)

    def pick(self, pid: int, ids: list[int | str] | None, count: int, level: str, builtin: list[tuple[str, str]]) -> list[dict]:
        """The bots for a table: the chosen own / shared ones (and own pets) first, then animal bots up to `count`."""
        mine: dict = {b["id"]: b for b in self.visible(pid)}
        if self.pets:
            mine.update({b["id"]: dict(b, owner=None) for b in self.pets.bots(pid)})
        out = []
        for i in ids or []:
            key = i if isinstance(i, str) and i.startswith("pet:") else None
            if key is None:
                try:
                    key = int(i)
                except (TypeError, ValueError):
                    continue
            b = mine.get(key)
            if b and len(out) < count:
                out.append({"name": b["name"], "emoji": b["emoji"], "color": b["color"], "level": b["level"],
                            "owner": b["owner"] if b["owner_id"] != pid else None})
        taken = {b["name"] for b in out}
        for n, e in random.sample(builtin, len(builtin)):
            if len(out) >= count:
                break
            if n not in taken:
                out.append({"name": n, "emoji": e, "level": level})
        return out
