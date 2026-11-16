"""Family bingo: 75 balls, a 5 × 5 card per player (columns B 1–15, I 16–30, N 31–45 with a free field, G 46–60,
O 61–75). One game at a time.

The balls come by themselves: the order is shuffled at the start and the number of balls drawn follows from the
time (`interval` seconds per ball: the carousel spins, stops and shows the ball). No background task is needed –
every state request computes it; a pause moves the clock.
Players mark the numbers themselves. «Bingo!» is checked: a row, column or diagonal of marked cells whose numbers have
all been drawn (the free field counts) – or two lines or the full card, as the one who starts sets the rules (the
rules used last are the default). A false «Bingo!» blocks the button for a few seconds.
"""
from __future__ import annotations

import json
import random
import time

from .community import CommunityError
from .db import Database
from .rewards.engine import Rewards

COLUMNS = "BINGO"
FREE = 12
FALSE_CLAIM_BLOCK = 10.0        # seconds
INTERVALS = (8, 12)             # normal, slow
WINS = ("line", "two_lines", "full")    # one line / two lines / the full card
RULES_KEY = "game_rules.bingo"          # the rules used last are the default of the next game
LINES = [[r * 5 + c for c in range(5)] for r in range(5)] + [[r * 5 + c for r in range(5)] for c in range(5)] \
    + [[i * 6 for i in range(5)], [(i + 1) * 4 for i in range(5)]]


def new_card(rng: random.Random | None = None) -> list[int]:
    rng = rng or random
    cols = [rng.sample(range(c * 15 + 1, c * 15 + 16), 5) for c in range(5)]
    card = [cols[c][r] for r in range(5) for c in range(5)]
    card[FREE] = 0
    return card


def letter(n: int) -> str:
    return COLUMNS[(n - 1) // 15] if 1 <= n <= 75 else ""


class Bingo:
    def __init__(self, db: Database, rewards: Rewards, history):
        self.db = db
        self.rewards = rewards
        self.add_history = history          # Community.add_history

    # ---------------------------------------------------------------- game
    def _game(self) -> dict | None:
        g = self.db.q1("SELECT * FROM bingo_game WHERE status!='done' ORDER BY id DESC LIMIT 1")
        if g:
            g["draw_order"] = json.loads(g["draw_order"])
        return g

    def default_rules(self) -> dict:
        r = self.db.get_setting(RULES_KEY) or {}
        return {"interval": r.get("interval", 8) if r.get("interval") in INTERVALS else 8,
                "win": r.get("win") if r.get("win") in WINS else "line"}

    def start(self, host: int, rules: dict | None = None) -> int:
        if self._game():
            raise CommunityError("A bingo game is already running")
        r = {**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}}
        r["interval"] = min(INTERVALS, key=lambda x: abs(x - float(r.get("interval") or 8)))
        if r.get("win") not in WINS:
            r["win"] = "line"
        self.db.set_setting(RULES_KEY, r)
        order = list(range(1, 76))
        random.shuffle(order)
        gid = self.db.x("INSERT INTO bingo_game(host_id, draw_order, interval, rules) VALUES(?,?,?,?)",
                        host, json.dumps(order), r["interval"], json.dumps(r))
        self.join(host)
        return gid

    def join(self, pid: int) -> None:
        g = self._game()
        if not g:
            raise CommunityError("No bingo game is running")
        self.db.x("INSERT OR IGNORE INTO bingo_card(game_id, profile_id, numbers) VALUES(?,?,?)", g["id"], pid, json.dumps(new_card()))

    def may_lead(self, prof: dict) -> bool:
        g = self._game()
        return bool(g) and (prof["role"] == "parent" or g["host_id"] == prof["id"])

    def begin(self) -> None:
        g = self._game()
        if not g or g["status"] != "lobby":
            raise CommunityError("No bingo game is waiting to start")
        self.db.x("UPDATE bingo_game SET status='running', started=? WHERE id=?", time.time(), g["id"])

    def pause(self, on: bool) -> None:
        g = self._game()
        if not g or g["status"] != "running":
            raise CommunityError("No bingo game is running")
        now = time.time()
        if on and not g["paused_at"]:
            self.db.x("UPDATE bingo_game SET paused_at=? WHERE id=?", now, g["id"])
        elif not on and g["paused_at"]:
            self.db.x("UPDATE bingo_game SET paused_at=NULL, paused_total=paused_total+? WHERE id=?", now - g["paused_at"], g["id"])

    def end(self) -> None:
        g = self._game()
        if g:
            self.db.x("UPDATE bingo_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", g["id"])

    @staticmethod
    def _clock(g: dict, now: float | None = None) -> tuple[int, float]:
        """(balls drawn, seconds into the current ball's cycle)."""
        if g["status"] == "lobby" or not g["started"]:
            return 0, 0.0
        now = g["paused_at"] or (now or time.time())
        elapsed = max(0.0, now - g["started"] - (g["paused_total"] or 0))
        n = int(elapsed // g["interval"]) + 1
        if n > 75:
            return 75, g["interval"]
        return n, elapsed % g["interval"]

    def drawn(self, g: dict) -> list[int]:
        n, _ = self._clock(g)
        return g["draw_order"][:n]

    # ---------------------------------------------------------------- player
    def _card(self, g: dict, pid: int) -> dict | None:
        c = self.db.q1("SELECT * FROM bingo_card WHERE game_id=? AND profile_id=?", g["id"], pid)
        if c:
            c["numbers"], c["marks"] = json.loads(c["numbers"]), json.loads(c["marks"])
        return c

    def mark(self, pid: int, cell: int) -> list[int]:
        g = self._game()
        if not g or g["status"] != "running":
            raise CommunityError("No bingo game is running")
        c = self._card(g, pid)
        if not c:
            raise CommunityError("Join the game first")
        if not 0 <= cell < 25 or cell == FREE:
            raise CommunityError("Unknown field")
        marks = set(c["marks"]) ^ {cell}
        marks.add(FREE)
        self.db.x("UPDATE bingo_card SET marks=? WHERE game_id=? AND profile_id=?", json.dumps(sorted(marks)), g["id"], pid)
        return sorted(marks)

    def claim(self, pid: int) -> dict:
        """«Bingo!» – right: the game ends with this winner; wrong: the button is blocked for a moment."""
        g = self._game()
        if not g or g["status"] != "running":
            raise CommunityError("No bingo game is running")
        c = self._card(g, pid)
        if not c:
            raise CommunityError("Join the game first")
        now = time.time()
        if c["blocked_until"] > now:
            raise CommunityError("Wait a moment before the next «Bingo!»")
        drawn = set(self.drawn(g))
        marks = set(c["marks"]) | {FREE}
        ok = lambda i: i == FREE or (i in marks and c["numbers"][i] in drawn)      # noqa: E731
        win = json.loads(g["rules"] or "{}").get("win", "line")
        full_lines = [ln for ln in LINES if all(ok(i) for i in ln)]
        need = {"line": 1, "two_lines": 2, "full": 12}[win]
        line = full_lines[0] if len(full_lines) >= need else None
        if not line:
            self.db.x("UPDATE bingo_card SET blocked_until=? WHERE game_id=? AND profile_id=?", now + FALSE_CLAIM_BLOCK, g["id"], pid)
            return {"bingo": False, "blocked_s": FALSE_CLAIM_BLOCK}
        if not self.db.x("""UPDATE bingo_game SET status='done', winner_id=?, finished_at=datetime('now','localtime')
                             WHERE id=? AND status='running'""", pid, g["id"]):
            return {"bingo": False, "late": True}
        players = [r["profile_id"] for r in self.db.q("SELECT profile_id FROM bingo_card WHERE game_id=?", g["id"])]
        winner = self.db.q1("SELECT name FROM profile WHERE id=?", pid)
        for p in players:
            self.add_history(p, "bingo", {"winner": winner["name"] if winner else "?", "won": p == pid,
                                          "balls": len(drawn), "players": len(players), "game": g["id"]})
            self.rewards.emit(p, "bingo_played", ref=f"bingo:{g['id']}")
        self.rewards.emit(pid, "bingo_won", ref=f"bingo:{g['id']}")
        return {"bingo": True, "line": line}

    # ---------------------------------------------------------------- state
    def state(self, viewer: int) -> dict | None:
        g = self._game()
        if not g:
            last = self.db.q1("""SELECT * FROM bingo_game WHERE status='done' AND winner_id IS NOT NULL
                                 AND finished_at >= datetime('now','localtime','-10 minutes') ORDER BY id DESC LIMIT 1""")
            if not last or not self.db.q1("SELECT 1 FROM bingo_card WHERE game_id=? AND profile_id=?", last["id"], viewer):
                return None
            last["draw_order"] = json.loads(last["draw_order"])
            g = last
        n, phase = self._clock(g) if g["status"] != "done" else (0, 0.0)
        drawn = g["draw_order"][:n] if g["status"] != "done" else []
        cards = self.db.q("""SELECT c.profile_id, p.name, p.avatar FROM bingo_card c JOIN profile p ON p.id=c.profile_id
                              WHERE c.game_id=? ORDER BY c.rowid""", g["id"])
        out = {"game": g["id"], "status": g["status"], "host": g["host_id"], "interval": g["interval"],
               "rules": json.loads(g["rules"] or "{}"),
               "paused": bool(g["paused_at"]), "count": len(drawn), "current": drawn[-1] if drawn else None,
               "phase_ms": int(phase * 1000), "recent": drawn[-6:-1][::-1],
               "players": [{"id": c["profile_id"], "name": c["name"], "avatar": json.loads(c["avatar"] or "{}")} for c in cards]}
        if g["status"] == "done" and g["winner_id"]:
            w = self.db.q1("SELECT id, name, avatar FROM profile WHERE id=?", g["winner_id"])
            out["winner"] = {"id": w["id"], "name": w["name"], "avatar": json.loads(w["avatar"] or "{}")} if w else None
        mine = self._card(g, viewer)
        if mine:
            out["card"] = mine["numbers"]
            out["marks"] = mine["marks"]
            out["blocked_ms"] = max(0, int((mine["blocked_until"] - time.time()) * 1000))
        return out

    def summary(self, pid: int) -> dict | None:
        g = self._game()
        if not g:
            return None
        return {"status": g["status"], "joined": bool(self.db.q1("SELECT 1 FROM bingo_card WHERE game_id=? AND profile_id=?", g["id"], pid))}
