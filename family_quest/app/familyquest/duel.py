"""Duels of the game corner on two devices – Tic-Tac-Toe between two family members.

One invites another; the invitation shows on the other's start page. The state lives in memory only (a round lasts a
minute; after a restart you simply invite again). Both devices poll the state.
"""
from __future__ import annotations

import itertools
import threading
import time

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
IDLE = 30 * 60                     # a duel nobody touched for 30 minutes is gone
INVITE = 5 * 60                    # an invitation is open for 5 minutes


class DuelError(ValueError):
    pass


def winner(board: list) -> tuple[str | None, list[int]]:
    for line in LINES:
        a, b, c = (board[i] for i in line)
        if a and a == b == c:
            return a, list(line)
    return ("draw", []) if all(board) else (None, [])


class Duels:
    def __init__(self, names):
        self.names = names            # pid → display name
        self.games: dict[int, dict] = {}
        self.ids = itertools.count(1)
        self.lock = threading.RLock()      # every read cleans up old duels – reads take the lock too

    def _clean(self) -> None:
        now = time.time()
        for gid, g in list(self.games.items()):
            if now - g["touched"] > IDLE or (g["status"] == "invite" and now - g["touched"] > INVITE):
                del self.games[gid]

    def _of(self, pid: int) -> dict | None:
        """The duel of this player – a running one or a new invitation before an old, declined or left one."""
        self._clean()
        mine = [g for g in sorted(self.games.values(), key=lambda g: -g["id"])
                if pid in (g["host"], g["guest"]) and g.get("left_by") != pid]
        return next((g for g in mine if g["status"] in ("invite", "play", "done")), mine[0] if mine else None)

    def invite(self, pid: int, opponent: int, kind: str = "ttt") -> dict:
        if kind != "ttt":
            raise DuelError("Unknown game")
        if opponent == pid:
            raise DuelError("Choose somebody else")
        with self.lock:
            for g in [g for g in self.games.values() if pid in (g["host"], g["guest"])]:
                del self.games[g["id"]]                # one duel at a time: a new invitation ends the old one
            if any(opponent in (g["host"], g["guest"]) and g["status"] in ("invite", "play", "done") for g in self.games.values()):
                raise DuelError("{0} is playing a duel right now")
            gid = next(self.ids)
            self.games[gid] = {"id": gid, "kind": kind, "host": pid, "guest": opponent, "status": "invite", "board": [None] * 9,
                               "turn": "X", "starter": "X", "result": None, "line": [], "score": {"X": 0, "O": 0, "draw": 0},
                               "touched": time.time()}
            return self.state(pid)

    def _mine(self, pid: int) -> dict:
        g = self._of(pid)
        if not g:
            raise DuelError("This duel is over")
        g["touched"] = time.time()
        return g

    def answer(self, pid: int, accept: bool) -> dict | None:
        with self.lock:
            g = self._mine(pid)
            if g["guest"] != pid or g["status"] != "invite":
                raise DuelError("This duel is over")
            if not accept:
                g.update(status="declined", left_by=pid)     # the inviter still sees «no thanks», the guest is free
                return None
            g["status"] = "play"
            return self.state(pid)

    def move(self, pid: int, cell: int) -> dict:
        with self.lock:
            g = self._mine(pid)
            me = "X" if pid == g["host"] else "O"
            if g["status"] != "play" or g["turn"] != me:
                raise DuelError("It is not your turn")
            if not 0 <= cell < 9 or g["board"][cell]:
                raise DuelError("This field is taken")
            g["board"][cell] = me
            res, line = winner(g["board"])
            if res:
                g.update(status="done", result=res, line=line)
                g["score"][res] += 1
            else:
                g["turn"] = "O" if me == "X" else "X"
            return self.state(pid)

    def again(self, pid: int) -> dict:
        with self.lock:
            g = self._mine(pid)
            if g["status"] != "done":
                raise DuelError("The round is still running")
            g["starter"] = "O" if g["starter"] == "X" else "X"
            g.update(status="play", board=[None] * 9, turn=g["starter"], result=None, line=[])
            return self.state(pid)

    def leave(self, pid: int) -> None:
        """Leave the duel (or take back / ignore the invitation). The other sees that you left."""
        with self.lock:
            g = self._of(pid)
            if not g:
                return
            if g["status"] in ("invite", "declined", "gone"):
                del self.games[g["id"]]
            else:
                g.update(status="gone", left_by=pid, touched=time.time())

    def state(self, pid: int) -> dict | None:
        with self.lock:
            return self._state(pid)

    def _state(self, pid: int) -> dict | None:
        g = self._of(pid)
        if not g:
            return None
        if g["status"] == "gone" and g.get("left_by") == pid:
            return None
        if g["status"] == "declined" and pid == g["guest"]:
            return None
        me = "X" if pid == g["host"] else "O"
        return {"id": g["id"], "kind": g["kind"], "status": g["status"], "me": me, "board": g["board"], "turn": g["turn"],
                "result": g["result"], "line": g["line"], "score": g["score"],
                "names": {"X": self.names(g["host"]), "O": self.names(g["guest"])},
                "host": g["host"] == pid}

    def summary(self, pid: int) -> dict | None:
        """For the start page: an invitation waiting for me."""
        with self.lock:
            g = self._of(pid)
        if g and g["guest"] == pid and g["status"] == "invite":
            return {"id": g["id"], "kind": g["kind"], "from": self.names(g["host"])}
        return None
