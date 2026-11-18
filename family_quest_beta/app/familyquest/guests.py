"""Guests in the family games: friends or grandparents play along without a profile.

Whoever leads a quiz or a bingo game opens an invitation (a short code, shown as a QR code). A guest scans it with
their own phone in the home network, types a name and plays – nothing else of the app is open to them.
Guests are profiles with archived = 2: every list of the app (archived = 0) leaves them out, the play endpoints
accept their token (kind "guest"). They and everything they did are deleted after GUEST_HOURS.
Parents can switch guests off for all games (setting `games_guests`).
"""
from __future__ import annotations

import json
import random
import secrets
import time

from .rewards import avatar as av

GUEST = 2
GUEST_HOURS = 12
GAMES = ("quiz", "bingo", "poker", "tschau", "karussell", "song", "domino", "paarjagd", "werbinich", "kartenlauf", "stadtland", "zeichnen", "wuerfel", "heimwaerts", "jump", "sternlauf", "snack", "verkehr", "langstrecke", "klatsch", "verboten", "jass", "werwolf", "schach", "dorfmarkt", "escape", "stempeljagd")
KEY = "guest_invites"
COLORS = ["#ff6b6b", "#4f8cff", "#51cf66", "#fcc419", "#845ef7", "#20c997", "#ff922b"]


class GuestError(ValueError):
    pass


class Guests:
    def __init__(self, fq):
        self.fq = fq
        self.db = fq.db

    def enabled(self) -> bool:
        return self.db.get_setting("games_guests") is not False

    def _invites(self) -> dict:
        return dict(self.db.get_setting(KEY) or {})

    def invite(self, game: str, on: bool = True, gid: int | None = None) -> dict | None:
        """Open (or close) the invitation for the running game of this kind (chess: this open game)."""
        if game not in GAMES:
            raise GuestError("Unknown game")
        if on and not self.enabled():
            raise GuestError("Guests are switched off in the parent area")
        inv = self._invites()
        if not on:
            inv.pop(game, None)
            self.db.set_setting(KEY, inv)
            return None
        gid = self._game_id(game, gid)
        if not gid:
            raise GuestError("No game is running")
        cur = inv.get(game)
        if not cur or cur.get("game_id") != gid:
            cur = {"code": secrets.token_urlsafe(6), "game_id": gid, "at": time.time()}
            inv[game] = cur
            self.db.set_setting(KEY, inv)
        return {"game": game, **cur}

    def _game_id(self, game: str, gid: int | None = None) -> int | None:
        if game == "schach":                      # several chess games at a time: an open seat of this game (or the newest)
            g = self.fq.schach._game(game, gid=gid)
        elif game in ("domino", "paarjagd", "werbinich", "kartenlauf", "stadtland", "zeichnen", "wuerfel", "heimwaerts", "jump", "sternlauf", "snack", "verkehr", "langstrecke", "klatsch", "verboten", "jass", "werwolf", "dorfmarkt", "escape", "stempeljagd"):
            g = getattr(self.fq, game)._game(game)
        elif game in ("tschau", "karussell"):
            g = self.fq.cards._game(game)
        else:
            g = {"quiz": self.fq.community, "bingo": self.fq.bingo, "poker": self.fq.poker, "song": self.fq.songs}[game]._game()
        return g["id"] if g and g.get("status") != "done" else None

    def find(self, code: str) -> tuple[str, dict] | None:
        for game, inv in self._invites().items():
            if code and secrets.compare_digest(str(code), inv.get("code", "")) and self._game_id(game, inv.get("game_id")) == inv.get("game_id"):
                return game, inv
        return None

    def info(self, code: str) -> dict:
        f = self.find(code)
        if not f or not self.enabled():
            raise GuestError("This invitation is not valid (any more)")
        game, _ = f
        from .running import TITLES          # English source – the guest page translates it
        title = {"bingo": "Bingo", "poker": "Texas Hold'em", "song": "Guess the song", **TITLES}.get(game, "")
        if game == "quiz":
            st = self.fq.community.state(0) or {}
            title = st.get("title") or "Quiz"
        return {"game": game, "title": title}

    def join(self, code: str, name: str) -> dict:
        self.cleanup()
        info = self.info(code)
        name = " ".join(str(name or "").split())[:20]
        if not name:
            raise GuestError("Please type your name")
        taken = {r["name"].lower() for r in self.db.q("SELECT name FROM profile WHERE archived IN (0, 2)")}
        base, n = name, 2
        while name.lower() in taken:
            name = f"{base} {n}"
            n += 1
        avatar = {**av.DEFAULT_AVATAR, "hair": random.choice(["short", "long", "curly", "bun", "ponytail"]),
                  "outfitColor": random.choice(COLORS), "skin": random.choice(["#ffe0bd", "#f1c27d", "#e0ac69", "#c68642"])}
        pid = self.db.x("INSERT INTO profile(name, role, color, avatar, settings, archived) VALUES(?,?,?,?,?,?)",
                        name, "guest", random.choice(COLORS), json.dumps(avatar), json.dumps({"guest": True}), GUEST)
        if info["game"] == "schach":
            self.fq.schach.join("schach", pid, gid=self.find(code)[1].get("game_id"))
        elif info["game"] in ("domino", "paarjagd", "werbinich", "kartenlauf", "stadtland", "zeichnen", "wuerfel", "heimwaerts", "jump", "sternlauf", "snack", "verkehr", "langstrecke", "klatsch", "verboten", "jass", "werwolf", "dorfmarkt", "escape", "stempeljagd"):
            getattr(self.fq, info["game"]).join(info["game"], pid)
        elif info["game"] in ("tschau", "karussell"):
            self.fq.cards.join(info["game"], pid)
        else:
            {"quiz": self.fq.community, "bingo": self.fq.bingo, "poker": self.fq.poker, "song": self.fq.songs}[info["game"]].join(pid)
        p = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
        return {"token": self.fq.tokens.make(pid, "guest"), "profile": {**self.fq.profile_public(p), "guest": True}, **info}

    def cleanup(self) -> int:
        """Delete guests older than GUEST_HOURS with everything they left behind."""
        old = [r["id"] for r in self.db.q("SELECT id FROM profile WHERE archived=? AND created_at < datetime('now', ?)",
                                          GUEST, f"-{GUEST_HOURS} hours")]
        if not old:
            return 0
        marks = ",".join("?" * len(old))
        for t in self.db.q("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            cols = {c["name"] for c in self.db.q(f"PRAGMA table_info({t['name']})")}
            if "profile_id" in cols and t["name"] != "profile":
                self.db.x(f"DELETE FROM {t['name']} WHERE profile_id IN ({marks})", *old)
        self.db.x(f"DELETE FROM profile WHERE id IN ({marks})", *old)
        return len(old)
