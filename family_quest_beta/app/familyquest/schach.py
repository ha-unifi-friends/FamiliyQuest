"""«Schach» – chess with the full standard rules (rules and bots: schach_engine.py).

Three ways to play:
  duel  – two people on two devices: who starts invites one person of the family (or leaves the seat open for
          anybody of the family, guests via QR code); the game starts when the second one joins.
  bot   – alone against a bot (easy / normal / hard).
  local – two people on ONE device (pass and play): the host's device plays both colours, the board turns.
Every game is its own row of the `card_game` table (kind "schach") – unlike the other live games a person can have
several games at the same time (MAX_OPEN unfinished games each). Status: lobby (waiting for the second player),
running, paused, done.

Pausing: either player (in a bot or pass-and-play game: the host) pauses; the clock stops, nobody can move, the game
waits in the database (it survives restarts) until a player continues. Who started the game or a parent deletes a
paused game (or an open invitation); the invited person may decline an invitation.
Clock (optional): 5, 10 or 15 minutes per side, no increment; it runs for the side to move from the start of the game
(a duel: from the moment the second player joins). Who runs out of time loses – a draw if the other side has no
material left to mate (a lone king or a single minor piece).
The end: checkmate, stalemate, threefold repetition (automatic), the 50-move rule (automatic), insufficient material,
resignation, a draw offer accepted (the bot accepts when its position is clearly worse), the flag – or ended by a
parent (running games in the parent area) without a result.
Coins (setting `game_rewards["schach"]`, three numbers): [0] the winner of a game between two people of the family,
[1] a win against the hard bot, [2] a win against the normal bot. Never against the easy bot, in pass and play or
against guests; only when the winner made at least MIN_MOVES moves (no quick resign deals); paid once (flag `paid`,
a unique ledger ref). The «No. 1» hat goes to the winner of a game between two people of the family.
"""
from __future__ import annotations

import json
import random
import secrets
import threading
import time

from .community import CommunityError
from .pairhunt import rewards_of as _rewards_of
from .schach_engine import START_FEN, Position, Searcher, bot_move, name, parse_sq
from .running import win_reason

KIND = "schach"
TITLE = "Schach"
MODES = ("duel", "bot", "local")
LEVELS = ("easy", "normal", "hard")
CLOCKS = (0, 5, 10, 15)
COLORS = ("white", "black", "random")
MAX_OPEN = 12                    # unfinished games per person
MIN_MOVES = 10                   # the winner's moves for coins
BOT_DELAY = 0.5                  # seconds before the bot moves (so the own move can be seen)
BOT_LIMIT = 1.6                  # thinking time of the hard bot
BOTS = {"easy": ("Hase Hoppel", "🐰"), "normal": ("Fuchs Fridolin", "🦊"), "hard": ("Eule Olga", "🦉")}
DEFAULTS = {"mode": "bot", "level": "normal", "clock": 0, "color": "white"}
FULL = {"P": 8, "N": 2, "B": 2, "R": 2, "Q": 1}


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def other(side: str) -> str:
    return "b" if side == "w" else "w"


class Schach:
    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng: random.Random | None = None, bot_limit: float = BOT_LIMIT):
        self.db = db
        self.add_history = add_history
        self.rewards = rewards
        self.now = now
        self.rng = rng or random.SystemRandom()
        self.bot_limit = bot_limit
        self.bot_delay = BOT_DELAY
        self.lock = threading.Lock()
        self.thinking: set[int] = set()

    # ---------------------------------------------------------------- rules (remembered for the next game)
    def default_rules(self) -> dict:
        return self.clean_rules({**DEFAULTS, **(self.db.get_setting(f"game_rules.{KIND}") or {})})

    def clean_rules(self, r: dict) -> dict:
        r = r or {}
        try:
            clock = int(r.get("clock") or 0)
        except (TypeError, ValueError):
            clock = 0
        return {"mode": r.get("mode") if r.get("mode") in MODES else "bot",
                "level": r.get("level") if r.get("level") in LEVELS else "normal",
                "clock": clock if clock in CLOCKS else 0,
                "color": r.get("color") if r.get("color") in COLORS else "white"}

    def rules_info(self) -> dict:
        return {**self.default_rules(), "rewards": rewards_of(self.db), "clocks": list(CLOCKS), "max_open": MAX_OPEN, "min_moves": MIN_MOVES}

    # ---------------------------------------------------------------- rows
    def _row(self, gid):
        try:
            gid = int(gid)
        except (TypeError, ValueError):
            return None
        return self.db.q1("SELECT * FROM card_game WHERE id=? AND kind=?", gid, KIND)

    def _person(self, pid: int) -> dict:
        p = self.db.q1("SELECT name, avatar, role FROM profile WHERE id=?", pid)
        out = {"id": str(pid), "name": p["name"] if p else "?", "avatar": json.loads(p["avatar"] or "{}") if p else {}}
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    @staticmethod
    def _ids(st: dict) -> set[str]:
        return {p["id"] for p in (st.get("players") or {}).values() if p and not p.get("bot")}

    def _save(self, row, st: dict, status: str | None = None) -> None:
        status = status or ("done" if st.get("result") else row["status"])
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status == "done" and st.get("result") and not st.get("paid"):
            self._finish(row, st)

    def _open_count(self, pid: int) -> int:
        n = 0
        for r in self.db.q("SELECT state FROM card_game WHERE kind=? AND status!='done'", KIND):
            if str(pid) in self._ids(json.loads(r["state"])):
                n += 1
        return n

    # ---------------------------------------------------------------- starting and joining
    def start(self, host: int, rules: dict | None = None, opponent: int | None = None) -> int:
        r = self.clean_rules({**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
        with self.lock:
            if self._open_count(host) >= MAX_OPEN:
                raise CommunityError("You have too many unfinished chess games – finish or delete one first")
            self.db.set_setting(f"game_rules.{KIND}", r)
            color = r["color"] if r["color"] != "random" else secrets.choice(["white", "black"])
            me, them = ("w", "b") if color == "white" else ("b", "w")
            players = {me: self._person(host), them: None}
            mode = r["mode"]
            if mode == "bot":
                n, e = BOTS[r["level"]]
                players[them] = {"id": "bot", "name": n, "emoji": e, "bot": True, "level": r["level"]}
            elif mode == "local":
                players = {"w": self._person(host), "b": self._person(host)}
            elif opponent is not None:
                if int(opponent) == int(host):
                    raise CommunityError("Choose somebody else")
                if not self.db.q1("SELECT id FROM profile WHERE id=? AND archived=0 AND role IN ('kid','parent')", int(opponent)):
                    raise CommunityError("Unknown person")
            pos = Position.from_fen(START_FEN)
            st = {"kind": KIND, "mode": mode, "rules": r, "players": players, "invite": str(opponent) if mode == "duel" and opponent is not None else None,
                  "fen": START_FEN, "moves": [], "keys": [pos.key()], "result": None, "draw_offer": None,
                  "clock": {"w": r["clock"] * 60000, "b": r["clock"] * 60000} if r["clock"] else None, "since": None,
                  "created": self.now()}
            status = "lobby" if mode == "duel" else "running"
            if status == "running":
                st["since"] = self.now()
                st["turn_at"] = self.now()
            return self.db.x("INSERT INTO card_game(kind, host_id, solo, status, state) VALUES(?,?,?,?,?)",
                             KIND, host, int(mode != "duel"), status, json.dumps(st))

    def _open_lobbies(self):
        return [r for r in self.db.q("SELECT * FROM card_game WHERE kind=? AND status='lobby' ORDER BY id DESC", KIND)]

    def _game(self, kind: str = KIND, host: int | None = None, gid: int | None = None):
        """An open seat (a duel waiting for anybody – the guest invitation): this game, the newest of this host, or the newest."""
        for r in self._open_lobbies():
            st = json.loads(r["state"])
            if st.get("invite") is not None:
                continue
            if gid is not None and r["id"] != gid:
                continue
            if host is not None and r["host_id"] != host:
                continue
            return {"id": r["id"], "status": r["status"]}
        return None

    def may_lead(self, kind: str, prof: dict, gid: int | None = None) -> bool:
        if gid is None:
            g = self._game(kind, prof["id"])
            return bool(g) or prof["role"] == "parent"
        row = self._row(gid)
        return bool(row) and (prof["role"] == "parent" or row["host_id"] == prof["id"])

    def join(self, kind: str, pid: int, gid: int | None = None) -> int:
        with self.lock:
            if gid is None:
                g = self._game(kind)
                gid = g["id"] if g else None
            row = self._row(gid)
            if not row or row["status"] == "done":
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if str(pid) in self._ids(st):
                return row["id"]
            if row["status"] != "lobby":
                raise CommunityError("The game has already started")
            if st.get("invite") is not None and st["invite"] != str(pid):
                raise CommunityError("This game is for somebody else")
            if self._open_count(pid) >= MAX_OPEN:
                raise CommunityError("You have too many unfinished chess games – finish or delete one first")
            side = "w" if st["players"].get("w") is None else "b"
            st["players"][side] = self._person(pid)
            st["since"] = st["turn_at"] = self.now()
            self._save(row, st, "running")
            return row["id"]

    # ---------------------------------------------------------------- who may do what
    def _side_of(self, st: dict, pid) -> str | None:
        """The colour this person plays (pass and play: the side to move)."""
        pid = str(pid)
        if st["mode"] == "local":
            return st["fen"].split()[1] if pid in self._ids(st) else None
        for side in ("w", "b"):
            p = st["players"].get(side)
            if p and p["id"] == pid and not p.get("bot"):
                return side
        return None

    def _load(self, gid, pid=None, parent: bool = False):
        row = self._row(gid)
        if not row:
            raise CommunityError("No game is running")
        st = json.loads(row["state"])
        if pid is not None and not parent and str(pid) not in self._ids(st):
            raise CommunityError("You do not play in this game")
        return row, st

    # ---------------------------------------------------------------- the clock and the end
    def _left(self, st: dict, side: str, now: float | None = None) -> int | None:
        if not st.get("clock"):
            return None
        ms = st["clock"][side]
        turn = "w" if st["fen"].split()[1] == "w" else "b"
        if st.get("since") and side == turn:
            ms -= int(((now or self.now()) - st["since"]) * 1000)
        return max(0, ms)

    def _flag(self, row, st: dict) -> bool:
        """Time is up for the side to move? Then the game ends (saved)."""
        if row["status"] != "running" or not st.get("clock") or st.get("result"):
            return False
        turn = st["fen"].split()[1]
        if self._left(st, turn) > 0:
            return False
        st["clock"][turn] = 0
        st["since"] = None
        pos = Position.from_fen(st["fen"])
        win = other(turn)
        self._end(st, win if pos.has_mating_material(win == "w") else None, "timeout")
        self._save(row, st, "done")
        return True

    def _end(self, st: dict, winner: str | None, reason: str) -> None:
        st["result"] = {"winner": winner, "reason": reason}
        st["draw_offer"] = None
        st["finished"] = self.now()

    def _apply(self, st: dict, m: tuple) -> None:
        pos = Position.from_fen(st["fen"])
        legal = pos.legal()
        if m not in legal:
            raise CommunityError("This move is not allowed")
        san = pos.san(m, legal)
        side = "w" if pos.white else "b"
        now = self.now()
        if st.get("clock") and st.get("since"):
            st["clock"][side] = self._left(st, side, now)
        st["since"] = now
        st["turn_at"] = now
        n = pos.make(m)
        st["fen"] = n.fen()
        st["moves"].append({"uci": pos.uci(m), "san": san, "by": side})
        key = n.key()
        st["keys"].append(key)
        if st.get("draw_offer") and st["draw_offer"] != side:      # a move answers a draw offer with «no»
            st["draw_offer"] = None
        replies = n.legal()
        if not replies:
            self._end(st, side if n.in_check() else None, "checkmate" if n.in_check() else "stalemate")
        elif st["keys"].count(key) >= 3:
            self._end(st, None, "repetition")
        elif n.half >= 100:
            self._end(st, None, "fifty")
        elif n.insufficient():
            self._end(st, None, "material")

    # ---------------------------------------------------------------- playing
    def move(self, gid, pid: int, frm: str, to: str, promo: str | None = None) -> None:
        with self.lock:
            row, st = self._load(gid, pid)
            if self._flag(row, st):
                raise CommunityError("Time is up")
            if row["status"] == "paused":
                raise CommunityError("The game is paused")
            if row["status"] != "running" or st.get("result"):
                raise CommunityError("The game is not running")
            pos = Position.from_fen(st["fen"])
            side = "w" if pos.white else "b"
            if self._side_of(st, pid) != side:
                raise CommunityError("It is not your turn")
            try:
                m = pos.parse_move(frm, to, promo)
            except ValueError:
                raise CommunityError("This move is not allowed") from None
            if pos.b[m[0]] in "Pp" and m[1] // 10 in (2, 9) and not m[2]:
                raise CommunityError("Choose a piece for the promotion")
            if m[2] and m[2] not in "qrbn":
                raise CommunityError("This move is not allowed")
            self._apply(st, m)
            self._save(row, st)

    def bot_step(self, gid) -> bool:
        """The bot's turn: think outside the lock, then play the move if nothing changed meanwhile."""
        with self.lock:
            row = self._row(gid)
            if not row or row["status"] != "running" or row["id"] in self.thinking:
                return False
            st = json.loads(row["state"])
            if st["mode"] != "bot" or st.get("result") or self._flag(row, st):
                return False
            turn = st["fen"].split()[1]
            bot = st["players"].get(turn)
            if not bot or not bot.get("bot") or self.now() - st.get("turn_at", 0) < self.bot_delay:
                return False
            self.thinking.add(row["id"])
            fen, keys, ply, level = st["fen"], list(st["keys"]), len(st["moves"]), bot.get("level", "normal")
        try:
            m = bot_move(Position.from_fen(fen), level, self.rng, keys, self.bot_limit)
            with self.lock:
                row = self._row(gid)
                if not row or row["status"] != "running":
                    return False
                st = json.loads(row["state"])
                if len(st["moves"]) != ply or st.get("result") or self._flag(row, st):
                    return False
                self._apply(st, m)
                self._save(row, st)
                return True
        finally:
            self.thinking.discard(int(gid))

    def pause(self, gid, pid: int, parent: bool = False) -> None:
        with self.lock:
            row, st = self._load(gid, pid, parent)
            if self._flag(row, st):
                return
            if row["status"] != "running":
                raise CommunityError("The game is not running")
            turn = st["fen"].split()[1]
            if st.get("clock"):
                st["clock"][turn] = self._left(st, turn)
            st["since"] = None
            st["paused_by"] = self._person(pid)["name"] if pid is not None else ""
            st["paused_at"] = self.now()
            self._save(row, st, "paused")

    def resume(self, gid, pid: int) -> None:
        with self.lock:
            row, st = self._load(gid, pid)
            if row["status"] != "paused":
                raise CommunityError("The game is not paused")
            st["since"] = st["turn_at"] = self.now()
            st.pop("paused_by", None)
            st.pop("paused_at", None)
            self._save(row, st, "running")

    def resign(self, gid, pid: int) -> None:
        with self.lock:
            row, st = self._load(gid, pid)
            if self._flag(row, st):
                return
            if row["status"] not in ("running", "paused") or st.get("result"):
                raise CommunityError("The game is not running")
            side = self._side_of(st, pid)
            self._freeze(st, row["status"])
            self._end(st, other(side), "resign")
            self._save(row, st, "done")

    def _freeze(self, st: dict, status: str) -> None:
        if status == "running" and st.get("clock") and st.get("since"):
            turn = st["fen"].split()[1]
            st["clock"][turn] = self._left(st, turn)
        st["since"] = None

    def draw(self, gid, pid: int, action: str) -> None:
        """offer / accept / decline – pass and play: «offer» is a draw by agreement at once; against the bot it
        answers at once (yes when its position is clearly worse)."""
        with self.lock:
            row, st = self._load(gid, pid)
            if self._flag(row, st):
                return
            if row["status"] != "running" or st.get("result"):
                raise CommunityError("The game is not running")
            side = self._side_of(st, pid)
            if action == "offer":
                if st["mode"] == "local":
                    self._freeze(st, "running")
                    self._end(st, None, "agreement")
                elif st["mode"] == "bot":
                    pos = Position.from_fen(st["fen"])
                    v = Searcher(limit=0.5).evaluate(pos, 2)
                    bot_view = v if st["players"].get("w" if pos.white else "b", {}).get("bot") else -v
                    if bot_view <= -200:
                        self._freeze(st, "running")
                        self._end(st, None, "agreement")
                    else:
                        st["draw_declined"] = len(st["moves"])
                        self._save(row, st)
                        raise CommunityError("The bot wants to play on")
                elif st.get("draw_offer") == other(side):           # both want a draw
                    self._freeze(st, "running")
                    self._end(st, None, "agreement")
                elif st.get("draw_offer") != side:
                    st["draw_offer"] = side
            elif action in ("accept", "decline"):
                if not st.get("draw_offer") or st["draw_offer"] == side:
                    raise CommunityError("There is no draw offer")
                if action == "accept":
                    self._freeze(st, "running")
                    self._end(st, None, "agreement")
                else:
                    st["draw_offer"] = None
            else:
                raise CommunityError("Unknown action")
            self._save(row, st)

    def delete(self, gid, prof: dict) -> None:
        """Who started it or a parent: delete a paused game or an open invitation (the invited person may decline)."""
        with self.lock:
            row = self._row(gid)
            if not row or row["status"] == "done":
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            lead = prof["role"] == "parent" or row["host_id"] == prof["id"]
            invited = row["status"] == "lobby" and st.get("invite") == str(prof["id"])
            if not (lead or invited):
                raise CommunityError("Only who started the game (or a parent) can delete it")
            if row["status"] not in ("paused", "lobby"):
                raise CommunityError("Pause the game first")
            self.db.x("DELETE FROM card_game WHERE id=?", row["id"])

    def abort(self, gid) -> None:
        """The parent area ends a game (running games): no result, no coins."""
        with self.lock:
            row = self._row(gid)
            if not row or row["status"] == "done":
                return
            st = json.loads(row["state"])
            self._freeze(st, row["status"])
            if not st.get("result"):
                self._end(st, None, "ended")
            st["paid"] = True                       # nothing to pay for an ended game
            self._save(row, st, "done")

    def end(self, kind: str, viewer: int) -> None:          # running.py compatibility: the newest game of this host
        row = self.db.q1("SELECT id FROM card_game WHERE kind=? AND status!='done' AND host_id=? ORDER BY id DESC LIMIT 1", KIND, viewer)
        if row:
            self.abort(row["id"])

    # ---------------------------------------------------------------- the result: coins, hat, history
    def coins_for(self, st: dict) -> dict[str, int]:
        res = st.get("result") or {}
        w = res.get("winner")
        if not w or res.get("reason") == "ended" or st["mode"] == "local":
            return {}
        winner, loser = st["players"].get(w), st["players"].get(other(w))
        if not winner or winner.get("bot") or winner.get("guest") or not loser:
            return {}
        if sum(1 for m in st["moves"] if m["by"] == w) < MIN_MOVES:
            return {}
        amounts = rewards_of(self.db)
        if st["mode"] == "duel":
            if loser.get("guest") or loser.get("bot"):
                return {}
            n = amounts[0]
        else:
            n = {"hard": amounts[1], "normal": amounts[2]}.get(loser.get("level"), 0)
        return {winner["id"]: n} if n > 0 else {}

    def _finish(self, row, st: dict) -> None:
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", win_reason(KIND), ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        res = st["result"]
        if not self.add_history or res.get("reason") == "ended":
            return
        w = res.get("winner")
        if st["mode"] == "duel" and w:
            people = [p["id"] for p in st["players"].values() if p and not p.get("bot") and not p.get("guest")]
            try:
                self.add_history(0, "__family__", {"people": people, "winners": [st["players"][w]["id"]]})
            except Exception:  # noqa: BLE001
                pass
        done = set()
        for side in ("w", "b"):
            p = st["players"].get(side)
            if not p or p.get("bot") or p.get("guest") or p["id"] in done:
                continue
            done.add(p["id"])
            opp = st["players"].get(other(side)) or {}
            if st["mode"] == "local":
                out = "white" if w == "w" else "black" if w == "b" else "draw"
            else:
                out = "win" if w == side else "draw" if not w else "loss"
            try:
                self.add_history(int(p["id"]), KIND, {"mode": st["mode"], "result": out, "reason": res.get("reason"),
                                                       "opp": opp.get("name") if st["mode"] != "local" else None,
                                                       "level": opp.get("level") if opp.get("bot") else None,
                                                       "moves": (len(st["moves"]) + 1) // 2, "coins": coins.get(p["id"], 0)})
            except Exception:  # noqa: BLE001
                pass

    # ---------------------------------------------------------------- reading
    def state(self, gid, viewer: int, parent: bool = False) -> dict:
        if self.bot_step(gid):
            pass
        with self.lock:
            row = self._row(gid)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            me = str(viewer)
            if me not in self._ids(st) and not parent:
                open_seat = row["status"] == "lobby" and st.get("invite") in (None, me)
                if not open_seat:
                    raise CommunityError("You do not play in this game")
            if self._flag(row, st):
                row = self._row(gid)
        return self._view(row, st, me)

    def _captured(self, pos: Position) -> dict:
        have = {}
        for c in pos.b:
            if c not in " .":
                have[c] = have.get(c, 0) + 1
        out = {}
        for side, upper in (("w", False), ("b", True)):          # what white took: the missing black pieces
            s = ""
            for p, n in FULL.items():
                c = p if upper else p.lower()
                s += c * max(0, n - have.get(c, 0))
            out[side] = s
        return out

    def _view(self, row, st: dict, me: str) -> dict:
        pos = Position.from_fen(st["fen"])
        turn = "w" if pos.white else "b"
        status = row["status"]
        my_side = self._side_of(st, me) if st["mode"] != "local" else (turn if me in self._ids(st) else None)
        running = status == "running" and not st.get("result")
        my_turn = running and my_side == turn
        legal = {}
        if my_turn:
            for m in pos.legal():
                legal.setdefault(name(m[0]), [])
                t = name(m[1])
                if t not in legal[name(m[0])]:
                    legal[name(m[0])].append(t)
        board = "".join(pos.b[21 + f + 10 * r] for r in range(8) for f in range(8))
        check = name(pos.king(pos.white)) if pos.in_check() else None
        last = st["moves"][-1]["uci"] if st["moves"] else None
        players = {}
        for side in ("w", "b"):
            p = st["players"].get(side)
            players[side] = None if not p else {"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"),
                                                 "bot": bool(p.get("bot")), "guest": bool(p.get("guest")), "level": p.get("level")}
        invite = None
        if st.get("invite"):
            q = self.db.q1("SELECT name FROM profile WHERE id=?", int(st["invite"]))
            invite = {"id": st["invite"], "name": q["name"] if q else "?"}
        res = st.get("result")
        rw = rewards_of(self.db)
        if st["mode"] == "duel":
            coins_on = rw[0] if not any(p and p.get("guest") for p in st["players"].values()) else 0
        elif st["mode"] == "bot":
            coins_on = {"hard": rw[1], "normal": rw[2]}.get(st["rules"]["level"], 0)
        else:
            coins_on = 0
        return {"game": row["id"], "kind": KIND, "title": TITLE, "mode": st["mode"], "status": "done" if res else status,
                "host": row["host_id"], "rules": st["rules"], "players": players, "invite": invite,
                "joined": me in self._ids(st), "me": me, "my_side": my_side, "turn": turn, "my_turn": my_turn,
                "board": board, "fen": st["fen"], "check": check, "last": [last[:2], last[2:4]] if last else None,
                "legal": legal, "moves": [m["san"] for m in st["moves"]], "captured": self._captured(pos),
                "material": sum((1 if c.isupper() else -1) * {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9}.get(c.lower(), 0) for c in pos.b if c not in " .Kk"),
                "clock": {s: self._left(st, s) for s in ("w", "b")} if st.get("clock") else None,
                "ticking": turn if st.get("clock") and st.get("since") and running else None,
                "draw_offer": st.get("draw_offer"), "draw_declined": st.get("draw_declined") == len(st["moves"]),
                "result": res, "paused_by": st.get("paused_by") if status == "paused" else None,
                "coins": st.get("coins") or {}, "coins_on": coins_on, "min_moves": MIN_MOVES, "rewards": rw,
                "thinking": running and bool((st["players"].get(turn) or {}).get("bot"))}

    def _brief(self, row, st: dict, me: str) -> dict:
        pos_turn = st["fen"].split()[1]
        my_side = None
        for side in ("w", "b"):
            p = st["players"].get(side)
            if p and p["id"] == me and not p.get("bot"):
                my_side = side if st["mode"] != "local" else None
        opp = None
        if st["mode"] != "local" and my_side:
            o = st["players"].get(other(my_side))
            opp = {"name": o["name"], "avatar": o.get("avatar"), "emoji": o.get("emoji"), "bot": bool(o.get("bot")), "level": o.get("level")} if o else None
        host = st["players"].get("w") if st["mode"] == "local" else None
        inv = None
        if st.get("invite"):
            q = self.db.q1("SELECT name FROM profile WHERE id=?", int(st["invite"]))
            inv = q["name"] if q else "?"
        return {"id": row["id"], "mode": st["mode"], "status": row["status"], "my_side": my_side, "opp": opp, "invite": inv,
                "host": row["host_id"], "host_name": (host or {}).get("name") or self.db.val("SELECT name FROM profile WHERE id=?", row["host_id"], default="?"),
                "my_turn": row["status"] == "running" and (st["mode"] == "local" or pos_turn == my_side),
                "moves": (len(st["moves"]) + 1) // 2, "clock": st["rules"]["clock"], "paused_by": st.get("paused_by")}

    def overview(self, viewer: int, parent: bool = False) -> dict:
        """The viewer's unfinished games, the invitations and open seats to join – and for a parent all games."""
        me = str(viewer)
        mine, open_, others = [], [], []
        for row in self.db.q("SELECT * FROM card_game WHERE kind=? AND status!='done' ORDER BY id DESC", KIND):
            st = json.loads(row["state"])
            if me in self._ids(st):
                mine.append(self._brief(row, st, me))
            elif row["status"] == "lobby" and st.get("invite") in (None, me):
                open_.append(self._brief(row, st, me))
            elif parent:
                others.append(self._brief(row, st, me))
        return {"games": mine, "open": open_, "others": others, "rules": self.rules_info()}

    def summary(self, kind: str, pid: int) -> dict | None:
        """For the start page banner: an invitation, an open seat or a duel where it is the viewer's move."""
        o = self.overview(pid)
        inv = [g for g in o["open"] if g["host"] != pid]
        turn = [g for g in o["games"] if g["mode"] == "duel" and g["status"] == "running" and g["my_turn"]]
        if not inv and not turn:
            return None
        return {"status": "running" if turn else "lobby", "joined": bool(turn), "invites": len(inv), "my_turn": len(turn),
                "game": (turn or inv)[0]["id"], "from": None if turn else inv[0]["host_name"]}
