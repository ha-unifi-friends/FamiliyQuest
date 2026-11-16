"""Domino – a live family game: double-6 (28 tiles) or double-9 (55 tiles), «simple» or «Cuban» rules.

Everybody plays on their own device (family table, guests via QR code) or a child plays alone against bots – like
the card games (cardgames.py); the tables live in the same `card_game` table with kind "domino".

Rules:
  simple – double-6, 7 tiles each (10 with double-9), each for themselves (teams optional), draw from the boneyard
           when nothing fits (option); the round winner scores the pips left in the opponents' hands.
  cuban  – double-9, 10 tiles each, teams of two (partners sit opposite), no drawing: pass when nothing fits; the
           round winner scores the pips left in ALL other hands (the partner's too).
First round: the holder of the highest double leads (with any tile). Later rounds: the winning side leads – with teams
any player of that team may lay the first tile (turn = "team:<n>" until one of them plays).
A round ends when a player dominoes (empties the hand) or when it is blocked (nobody can play any more): then the side
with the fewest pips wins (tie: no points, the round is repeated with the same starters).
The match ends when a side reaches the target (100, 150 or 200). Won while the other side has 0 points: «Pollona».
"""
from __future__ import annotations

import json
import random
import time

from .cardgames import BOTS, BOT_DELAY, CardGames, bot_delay
from .community import CommunityError

KIND = "domino"
TITLE = "Domino"
DEFAULTS = {"mode": "cuban", "set": 9, "teams": True, "draw": False, "target": 100, "bots": 3, "level": "normal", "bot_ms": 1400}
TEAM_WAIT = 12.0          # seconds a bot waits before it leads for a team that has people in it too


def tiles(top: int) -> list[str]:
    return [f"{a}-{b}" for a in range(top + 1) for b in range(a, top + 1)]


def nums(tile: str) -> tuple[int, int]:
    a, b = tile.split("-")
    return int(a), int(b)


def pips(tile: str) -> int:
    return sum(nums(tile))


def hand_size(rules: dict, players: int) -> int:
    top = 9 if rules.get("set") == 9 else 6
    base = 7 if top == 6 else 10
    return max(1, min(base, len(tiles(top)) // max(1, players)))


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now

    @property
    def r(self) -> dict:
        return self.st["rules"]

    def seat(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    # ---------- sides: teams (seat 1+3 against 2+4 …) or everybody for themselves
    def teams(self) -> bool:
        if "teams" in self.st:
            return self.st["teams"]
        n = len(self.st["players"])
        return bool(self.r.get("teams")) and n >= 4 and n % 2 == 0

    def side(self, pid: str) -> str:
        return str(self.order().index(pid) % 2) if self.teams() else pid

    def sides(self) -> list[str]:
        return ["0", "1"] if self.teams() else self.order()

    def members(self, side: str) -> list[str]:
        return [p for p in self.order() if self.side(p) == side]

    def cuban(self) -> bool:
        return self.r.get("mode") == "cuban"

    def may_draw(self) -> bool:
        return bool(self.r.get("draw")) and not self.cuban()

    # ---------- a round
    def deal(self) -> None:
        top = 9 if self.r.get("set") == 9 else 6
        pool = tiles(top)
        self.rng.shuffle(pool)
        self.st["teams"] = self.teams()
        size = hand_size(self.r, len(self.st["players"]))
        hands = {pid: sorted((pool.pop() for _ in range(size)), key=nums) for pid in self.order()}
        self.st.setdefault("scores", {s: 0 for s in self.sides()})
        self.st.setdefault("sheet", [])
        starter = self.st.get("next_starter")
        if not starter:                                  # first round: the highest double (else the heaviest tile)
            best = max(((t for h in hands.values() for t in h)), key=lambda t: (nums(t)[0] == nums(t)[1], pips(t), nums(t)[1]))
            starter = next(p for p, h in hands.items() if best in h)
        self.st.update(round=self.st.get("round", 0) + 1, hands=hands, boneyard=pool, line=[], turn=starter,
                       starter=self.st.get("next_starter"), passes=[], phase="play", round_result=None, last=None)
        self.st["turn_at"] = self.now()

    def ends(self) -> tuple[int, int] | None:
        line = self.st.get("line") or []
        return (line[0][0], line[-1][1]) if line else None

    def fits(self, tile: str) -> list[str]:
        """The ends this tile may be laid on: [], ["left"], ["right"] or both."""
        e = self.ends()
        if e is None:
            return ["right"]
        a, b = nums(tile)
        out = [end for end, v in (("left", e[0]), ("right", e[1])) if v in (a, b)]
        if len(out) == 2 and e[0] == e[1]:
            return ["right"]                              # the same either way
        return out

    def my_turn(self, pid: str) -> bool:
        turn = self.st.get("turn") or ""
        if self.st.get("phase") != "play" or pid not in self.order():
            return False
        return turn == pid or (turn.startswith("team:") and self.side(pid) == turn[5:])

    def playable(self, pid: str) -> dict[str, list[str]]:
        if not self.my_turn(pid):
            return {}
        out = {}
        for t in self.st["hands"].get(pid, []):
            f = self.fits(t)
            if f:
                out[t] = f
        return out

    def can_draw(self, pid: str) -> bool:
        return self.my_turn(pid) and self.may_draw() and bool(self.st.get("boneyard")) and not self.playable(pid)

    def must_pass(self, pid: str) -> bool:
        return self.my_turn(pid) and not self.playable(pid) and not self.can_draw(pid)

    def _next(self, pid: str) -> str:
        order = self.order()
        return order[(order.index(pid) + 1) % len(order)]

    def play(self, pid: str, tile: str, end: str | None = None) -> None:
        if not self.my_turn(pid):
            raise CommunityError("It is not your turn")
        hand = self.st["hands"][pid]
        if tile not in hand:
            raise CommunityError("You do not have this tile")
        ok = self.fits(tile)
        if not ok:
            raise CommunityError("This tile does not fit")
        if end is None:
            if len(ok) > 1:
                raise CommunityError("Choose an end: left or right")
            end = ok[0]
        if end not in ok:
            raise CommunityError("This tile does not fit on this end")
        a, b = nums(tile)
        line = self.st["line"]
        if not line:
            line.append([a, b])
        elif end == "left":
            line.insert(0, [a, b] if b == line[0][0] else [b, a])
        else:
            line.append([a, b] if a == line[-1][1] else [b, a])
        hand.remove(tile)
        self.st["passes"] = []
        self.st["last"] = {"player": pid, "tile": tile, "end": end, "t": self.now()}
        if not hand:
            self._round_end(pid, "domino")
            return
        self.st["turn"] = self._next(pid)
        self.st["turn_at"] = self.now()
        self._check_blocked()

    def draw(self, pid: str) -> str:
        if not self.my_turn(pid) or self.st["turn"] != pid:
            raise CommunityError("It is not your turn")
        if not self.may_draw():
            raise CommunityError("No drawing in this game – pass")
        if self.playable(pid):
            raise CommunityError("A tile fits – play it")
        if not self.st["boneyard"]:
            raise CommunityError("The boneyard is empty – pass")
        tile = self.st["boneyard"].pop()
        self.st["hands"][pid].append(tile)
        self.st["last"] = {"player": pid, "drew": 1, "t": self.now()}
        self.st["turn_at"] = self.now()
        return tile

    def pass_turn(self, pid: str) -> None:
        if not self.my_turn(pid) or self.st["turn"] != pid:
            raise CommunityError("It is not your turn")
        if self.playable(pid):
            raise CommunityError("A tile fits – you cannot pass")
        if self.can_draw(pid):
            raise CommunityError("Draw a tile first")
        self.st["passes"].append(pid)
        self.st["last"] = {"player": pid, "passed": True, "t": self.now()}
        self.st["turn"] = self._next(pid)
        self.st["turn_at"] = self.now()
        if len(self.st["passes"]) >= len(self.order()):
            self._round_end(None, "blocked")
        else:
            self._check_blocked()

    def _check_blocked(self) -> None:
        """Nobody can lay a tile any more (and nobody can draw): the round is blocked (tranque)."""
        if self.st.get("phase") != "play" or not self.st["line"] or (self.may_draw() and self.st["boneyard"]):
            return
        if any(self.fits(t) for h in self.st["hands"].values() for t in h):
            return
        self._round_end(None, "blocked")

    def _round_end(self, winner: str | None, reason: str) -> None:
        hands = self.st["hands"]
        totals = {s: sum(pips(t) for p in self.members(s) for t in hands[p]) for s in self.sides()}
        side = self.side(winner) if winner else None
        if reason == "blocked":
            low = min(totals.values())
            best = [s for s in self.sides() if totals[s] == low]
            side = best[0] if len(best) == 1 else None
        scores = self.st["scores"]
        points = 0
        if side is not None:
            points = sum(totals.values()) if self.cuban() else sum(v for s, v in totals.items() if s != side)
            scores[side] = scores.get(side, 0) + points
            self.st["next_starter"] = f"team:{side}" if self.teams() else side
        else:                                             # a tie: no points, the same starters once more
            self.st["next_starter"] = self.st.get("starter")
        res = {"round": self.st["round"], "side": side, "player": winner, "points": points, "reason": reason,
               "tie": side is None, "totals": dict(scores), "pips": totals}
        self.st["sheet"].append(res)
        self.st["round_result"] = {**res, "hands": {p: list(h) for p, h in hands.items()}}
        target = int(self.r.get("target") or 100)
        if side is not None and scores[side] >= target:
            self.st["phase"] = "done"
            self.st["winner"] = side
            self.st["pollona"] = all(v == 0 for s, v in scores.items() if s != side)
            ranked = sorted(self.sides(), key=lambda s: -scores.get(s, 0))
            self.st["ranking"] = [p for s in ranked for p in self.members(s)]
            self.st["finished"] = self.now()
        else:
            self.st["phase"] = "between"
            self.st["next_at"] = self.now() + 6

    # ---------- bots
    def bot_move(self, pid: str, level: str = "normal") -> None:
        opts = self.playable(pid)
        if not opts:
            if self.can_draw(pid):
                self.draw(pid)
            else:
                self.pass_turn(pid)
            return
        if level == "easy":
            tile = self.rng.choice(sorted(opts))
            end = self.rng.choice(opts[tile])
        else:                                             # get rid of doubles and heavy tiles; keep numbers you hold
            tile = max(opts, key=lambda t: (nums(t)[0] == nums(t)[1], pips(t), self.rng.random()))
            rest = [x for x in self.st["hands"][pid] if x != tile]
            e = self.ends()

            def keeps(end):
                if e is None:
                    return 0
                a, b = nums(tile)
                open_ = b if (e[0] if end == "left" else e[1]) == a else a
                return sum(open_ in nums(x) for x in rest)
            end = max(opts[tile], key=lambda x: (keeps(x), self.rng.random()))
        self.play(pid, tile, end)

    def _team_bot(self, side: str) -> tuple[str | None, float]:
        """Who of a team leads: a bot (the one with the heaviest tile) – after a longer wait when people are in it."""
        bots = [p for p in self.members(side) if (self.seat(p) or {}).get("bot")]
        if not bots:
            return None, 0
        wait = TEAM_WAIT if len(bots) < len(self.members(side)) else bot_delay(self.st["rules"], BOT_DELAY)
        best = max(bots, key=lambda p: max((nums(t)[0] == nums(t)[1], pips(t)) for t in self.st["hands"][p]))
        return best, wait

    def tick(self) -> bool:
        """Bots move, the next round starts. True if something changed."""
        changed = False
        for _ in range(3):
            if self.st.get("phase") == "between" and self.now() >= self.st.get("next_at", 0):
                self.deal()
                changed = True
                continue
            if self.st.get("phase") != "play":
                break
            turn = self.st["turn"]
            if turn.startswith("team:"):
                pid, wait = self._team_bot(turn[5:])
            else:
                p = self.seat(turn)
                pid, wait = (turn, bot_delay(self.st["rules"], BOT_DELAY)) if p and p.get("bot") else (None, 0)
            if not pid or self.now() - self.st.get("turn_at", 0) < wait:
                break
            self.bot_move(pid, (self.seat(pid) or {}).get("level", "normal"))
            changed = True
            self.st["turn_at"] = self.now()
        return changed


# ================================================================ the games in the database (table card_game, kind "domino")
class Domino(CardGames):
    """The family table / own tables against bots – the same rows and lobby as the card games (join, end, summary)."""

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, {**DEFAULTS, **(self.db.get_setting(f"game_rules.{KIND}") or {})})

    def clean_rules(self, kind: str, r: dict) -> dict:
        out = {}
        for k, v in DEFAULTS.items():
            x = r.get(k, v)
            if isinstance(v, bool):
                out[k] = bool(x)
            elif isinstance(v, int):
                try:
                    out[k] = int(x)
                except (TypeError, ValueError):
                    out[k] = v
            else:
                out[k] = str(x)
        out["mode"] = out["mode"] if out["mode"] in ("cuban", "simple") else "cuban"
        out["set"] = 9 if out["set"] == 9 else 6
        out["target"] = out["target"] if out["target"] in (100, 150, 200) else 100
        out["bots"] = max(0, min(5, out["bots"]))
        out["bot_ms"] = max(0, min(5000, out["bot_ms"]))
        out["level"] = out["level"] if out["level"] in ("easy", "normal") else "normal"
        if out["mode"] == "cuban":
            out["draw"] = False                          # Cuban: no boneyard – pass instead
        return out

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status == "done" and self.add_history and not st.get("history_written"):
            st["history_written"] = True
            self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
            t = Table(st)
            scores = st.get("scores") or {}
            self._champion(st, [p["id"] for p in st["players"] if st.get("winner") is not None and t.side(p["id"]) == st.get("winner")])
            for p in st["players"]:
                if p.get("bot"):
                    continue
                side = t.side(p["id"])
                try:
                    self.add_history(int(p["id"]), "domino", {"won": side == st.get("winner"), "pollona": bool(st.get("pollona")),
                                                              "points": scores.get(side, 0), "best": scores.get(st.get("winner"), 0),
                                                              "players": len(st["players"])})
                except Exception:  # noqa: BLE001
                    pass

    def start(self, kind: str, host: int, rules: dict | None = None, solo: bool = False, bots: list[dict] | None = None) -> int:
        if kind != KIND:
            raise CommunityError("Unknown game")
        with self.lock:
            if not solo and self._row(KIND):
                raise CommunityError("This game is already running")
            if solo:
                old = self._row(KIND, host)
                if old and old["solo"]:
                    self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", old["id"])
            r = self.clean_rules(KIND, {**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
            self.db.set_setting(f"game_rules.{KIND}", r)
            players = [self._person(host)]
            n_bots = r["bots"] if not solo else max(1, r["bots"])
            if bots is None:
                bots = [{"name": n, "emoji": e, "level": r["level"]} for n, e in random.sample(BOTS, len(BOTS))[:n_bots]]
            for i, b in enumerate(bots[:n_bots]):
                players.append({"id": f"bot{i + 1}", "name": b["name"], "emoji": b.get("emoji") or "🤖", "color": b.get("color"),
                                "owner": b.get("owner"), "bot": True, "level": "easy" if b.get("level") == "easy" else "normal"})
            st = {"kind": KIND, "rules": r, "players": players, "phase": "lobby", "solo": solo}
            gid = self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, int(solo), json.dumps(st))
            if solo:                                      # alone against bots: deal right away
                row = self.db.q1("SELECT * FROM card_game WHERE id=?", gid)
                Table(st).deal()
                self._save(row, st)
            return gid

    def begin(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) < 2:
                raise CommunityError("Add a bot or wait for a second player")
            Table(st).deal()
            self._save(row, st)

    def _with(self, kind: str, viewer: int, fn) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            t = Table(st)
            t.tick()
            fn(t)
            self._save(row, st)

    def play(self, kind: str, pid: int, tile: str, end: str | None = None) -> None:
        self._with(KIND, pid, lambda t: t.play(str(pid), tile, end))

    def draw(self, kind: str, pid: int) -> None:
        self._with(KIND, pid, lambda t: t.draw(str(pid)))

    def pass_turn(self, kind: str, pid: int) -> None:
        self._with(KIND, pid, lambda t: t.pass_turn(str(pid)))

    def state(self, kind: str, viewer: int) -> dict | None:
        with self.lock:
            row = self._row(KIND, viewer)
            if row:
                st = json.loads(row["state"])
                if st["phase"] != "lobby" and Table(st).tick():
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
            else:
                row = self.db.q1("""SELECT * FROM card_game WHERE kind=? AND status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                    AND (solo=0 OR host_id=?) ORDER BY id DESC LIMIT 1""", KIND, viewer)
                if not row:
                    return None
                st = json.loads(row["state"])
                if not any(p["id"] == str(viewer) for p in st["players"]):
                    return None
        return self._view(row, st, str(viewer))

    def _view(self, row, st: dict, me: str) -> dict:
        t = Table(st)
        hands = st.get("hands") or {}
        passes = st.get("passes") or []
        scores = st.get("scores") or {}
        joined = any(p["id"] == me for p in st["players"])
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                    "color": p.get("color"), "owner": p.get("owner"), "tiles": len(hands.get(p["id"], [])),
                    "side": t.side(p["id"]), "passed": p["id"] in passes}
                   for p in st["players"]]
        sides = [{"id": s, "members": t.members(s), "score": scores.get(s, 0)} for s in t.sides()] if st["phase"] != "lobby" else []
        mine = hands.get(me)
        e = t.ends()
        return {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": st["phase"],
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "players": players, "joined": joined,
                "teams": t.teams(), "sides": sides, "my_side": t.side(me) if joined else None,
                "round": st.get("round", 0), "line": st.get("line") or [], "ends": list(e) if e else None,
                "boneyard": len(st.get("boneyard") or []) if t.may_draw() else None,
                "turn": st.get("turn"), "my_turn": t.my_turn(me), "last": st.get("last"),
                "hand": mine, "playable": t.playable(me) if mine is not None else {},
                "can_draw": t.can_draw(me) if mine is not None else False, "must_pass": t.must_pass(me) if mine is not None else False,
                "round_result": st.get("round_result"), "sheet": st.get("sheet") or [], "winner": st.get("winner"),
                "pollona": bool(st.get("pollona")), "ranking": st.get("ranking"),
                "next_ms": max(0, int((st.get("next_at", 0) - time.time()) * 1000)) if st["phase"] == "between" else None}
