"""Ping-Pong doubles on up to four devices – two teams of two (familyquest/duel.py is the duel for two).

Seats: A1 (back) and A2 (front, short paddle near the net) against B1 (back) and B2 (front). The one who sets up the
table sits on A1 and chooses who sits on the other three seats: a family member (gets an invitation on their device)
or a bot (easy, normal, hard). When every invited person has said yes the host starts the match; a seat whose person
says «no thanks» stays open until the host gives it to somebody else or to a bot.

Same model as the duel: the host's device moves the ball and the bots; every device sends only its own paddle (0…1,
left to right as team A sees the table) about 15 times a second and gets the whole table back. The ball, the points
and the end of a match come from the host only. Somebody who leaves a running match is replaced by a normal bot; when
the host leaves, the match is over. The state lives in memory only (like the duel – no coins, no history).
"""
from __future__ import annotations

import itertools
import threading
import time

SEATS = ("A1", "A2", "B1", "B2")
LEVELS = ("easy", "normal", "hard")
TARGETS = (5, 7, 11)
FRONT = 0.55                        # the front paddle is 55 % as long as the back one
IDLE = 30 * 60                      # a table nobody touched for 30 minutes is gone
INVITE = 5 * 60                     # a table still waiting for answers (or left by its host) for 5 minutes is gone


class DoublesError(ValueError):
    pass


def busy_text(name: str) -> str:
    return str(DoublesError("{0} is playing a match right now")).replace("{0}", name)


def team(seat: str) -> str:
    return seat[0]


class Doubles:
    def __init__(self, names):
        self.names = names            # pid → display name
        self.games: dict[int, dict] = {}
        self.ids = itertools.count(1)
        self.invites = itertools.count(1)       # every invitation has its own number: the popup shows each once
        self.lock = threading.RLock()

    # ------------------------------------------------------------ helpers
    def _clean(self) -> None:
        now = time.time()
        for gid, g in list(self.games.items()):
            if now - g["touched"] > IDLE or (g["status"] in ("lobby", "gone") and now - g["touched"] > INVITE):
                del self.games[gid]

    @staticmethod
    def _seat_of(g: dict, pid: int) -> str | None:
        return next((s for s in SEATS if g["seats"][s]["pid"] == pid), None)

    def _of(self, pid: int) -> dict | None:
        """The table of this player (newest first): a seat with this person who did not leave or decline."""
        self._clean()
        for g in sorted(self.games.values(), key=lambda g: -g["id"]):
            s = self._seat_of(g, pid)
            if s and g["seats"][s]["state"] in ("host", "invite", "in"):
                return g
        return None

    def _mine(self, pid: int) -> tuple[dict, str]:
        g = self._of(pid)
        if not g:
            raise DoublesError("This match is over")
        g["touched"] = time.time()
        return g, self._seat_of(g, pid)

    def busy(self, pid: int) -> bool:
        with self.lock:
            return self._of(pid) is not None

    @staticmethod
    def _pong_new(to: int) -> dict:
        return {"pads": {s: 0.5 for s in SEATS}, "ball": None, "points": {"A": 0, "B": 0}, "to": to}

    def _fill(self, g: dict, seat: str, spec: dict, host: int) -> None:
        """Give a seat to a person (invitation) or to a bot."""
        if seat not in SEATS[1:]:
            raise DoublesError("Unknown seat")
        bot = spec.get("bot")
        pid = spec.get("pid")
        if bot is not None:
            if bot not in LEVELS:
                raise DoublesError("Unknown bot")
            g["seats"][seat] = {"pid": None, "bot": bot, "state": "bot"}
            return
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            raise DoublesError("Choose a player or a bot") from None
        if pid == host or any(x["pid"] == pid for s, x in g["seats"].items() if s != seat):
            raise DoublesError("Everybody can only sit on one seat")
        if any(o is not g and self._seat_of(o, pid) and o["seats"][self._seat_of(o, pid)]["state"] in ("host", "invite", "in")
               for o in self.games.values()):
            raise DoublesError(busy_text(self.names(pid)))
        g["seats"][seat] = {"pid": pid, "bot": None, "state": "invite", "inv": next(self.invites)}

    # ------------------------------------------------------------ setting up the table
    def create(self, pid: int, seats: dict, to: int = 7) -> dict:
        """The host sits on A1 and fills A2, B1, B2 – each with {"pid": id} or {"bot": "easy|normal|hard"}."""
        if to not in TARGETS:
            raise DoublesError("Unknown target")
        if not isinstance(seats, dict) or set(seats) != set(SEATS[1:]):
            raise DoublesError("Fill all three seats")
        with self.lock:
            for g in list(self.games.values()):        # one table at a time: a new one ends my old one
                s = self._seat_of(g, pid)
                if s:
                    self._leave(g, s)
            gid = next(self.ids)
            g = {"id": gid, "host": pid, "status": "lobby", "seats": {"A1": {"pid": pid, "bot": None, "state": "host"}},
                 "to": to, "score": {"A": 0, "B": 0}, "result": None, "touched": time.time()}
            for seat in SEATS[1:]:
                self._fill(g, seat, seats[seat] or {}, pid)
            g["pong"] = self._pong_new(to)
            self.games[gid] = g
            return self._state(pid)

    def seat(self, pid: int, seat: str, spec: dict) -> dict:
        """In the lobby the host changes a seat (e.g. a bot for somebody who said no)."""
        with self.lock:
            g, me = self._mine(pid)
            if me != "A1" or g["status"] != "lobby":
                raise DoublesError("Only the host can change the seats before the start")
            self._fill(g, seat, spec or {}, pid)
            return self._state(pid)

    def answer(self, pid: int, accept: bool) -> dict | None:
        with self.lock:
            g, me = self._mine(pid)
            if g["seats"][me]["state"] != "invite" or g["status"] != "lobby":
                raise DoublesError("This match is over")
            g["seats"][me]["state"] = "in" if accept else "declined"
            return self._state(pid) if accept else None

    def start(self, pid: int) -> dict:
        with self.lock:
            g, me = self._mine(pid)
            if me != "A1" or g["status"] != "lobby":
                raise DoublesError("Only the host can start")
            if any(g["seats"][s]["state"] not in ("host", "in", "bot") for s in SEATS):
                raise DoublesError("Not everybody is ready yet")
            g["status"] = "play"
            return self._state(pid)

    # ------------------------------------------------------------ the match
    def sync(self, pid: int, pad, bots=None, ball=None, points=None, over=None) -> dict:
        """My paddle in (0…1 as team A sees the table); the host also sends the bots' paddles, ball, points, end."""
        with self.lock:
            g, me = self._mine(pid)
            p = g["pong"]
            try:
                p["pads"][me] = max(0.0, min(1.0, float(pad)))
            except (TypeError, ValueError):
                pass
            if me == "A1" and g["status"] == "play":
                if isinstance(bots, dict):
                    for s, v in bots.items():
                        if s in SEATS and g["seats"][s]["state"] == "bot":
                            try:
                                p["pads"][s] = max(0.0, min(1.0, float(v)))
                            except (TypeError, ValueError):
                                pass
                if isinstance(ball, dict):
                    try:
                        p["ball"] = {k: round(float(ball[k]), 4) for k in ("x", "y", "vx", "vy")}
                    except (KeyError, TypeError, ValueError):
                        pass
                if isinstance(points, dict):
                    p["points"] = {k: max(0, min(99, int(points.get(k, 0) or 0))) for k in ("A", "B")}
                if over in ("A", "B"):
                    g.update(status="done", result=over)
                    g["score"][over] += 1
            return self._state(pid)

    def again(self, pid: int) -> dict:
        with self.lock:
            g, me = self._mine(pid)
            if g["status"] != "done":
                raise DoublesError("The round is still running")
            g.update(status="play", result=None)
            g["pong"] = self._pong_new(g["to"])
            return self._state(pid)

    def _leave(self, g: dict, seat: str) -> None:
        if seat == "A1":
            if g["status"] == "lobby":
                del self.games[g["id"]]
            else:
                g["seats"]["A1"]["state"] = "left"
                g.update(status="gone", touched=time.time())
            return
        if g["status"] == "lobby":
            g["seats"][seat]["state"] = "declined"
        else:                                           # a normal bot plays on for whoever left
            g["seats"][seat] = {"pid": None, "bot": "normal", "state": "bot", "left": g["seats"][seat]["pid"]}
        g["touched"] = time.time()

    def leave(self, pid: int) -> None:
        with self.lock:
            g = self._of(pid)
            if g:
                self._leave(g, self._seat_of(g, pid))

    # ------------------------------------------------------------ what the devices see
    def state(self, pid: int) -> dict | None:
        with self.lock:
            return self._state(pid)

    def _state(self, pid: int) -> dict | None:
        g = self._of(pid)
        if not g:
            return None
        me = self._seat_of(g, pid)
        seats = {}
        for s in SEATS:
            x = g["seats"][s]
            seats[s] = {"name": self.names(x["pid"]) if x["pid"] else None, "bot": x["bot"], "state": x["state"],
                        "pid": x["pid"], "left": self.names(x["left"]) if x.get("left") else None, "inv": x.get("inv")}
        return {"id": g["id"], "kind": "pong4", "status": g["status"], "me": me, "team": team(me), "host": me == "A1",
                "seats": seats, "to": g["to"], "score": g["score"], "result": g["result"], "pong": g["pong"],
                "front": FRONT}

    def summary(self, pid: int) -> dict | None:
        """For the start page: an invitation waiting for me."""
        with self.lock:
            g = self._of(pid)
            if not g:
                return None
            me = self._seat_of(g, pid)
            if g["status"] == "lobby" and g["seats"][me]["state"] == "invite":
                return {"id": g["id"], "from": self.names(g["host"]), "seat": me, "team": team(me)}
        return None
