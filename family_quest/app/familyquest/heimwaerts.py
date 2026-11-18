"""«Heimwärts» – a classic cross-and-circle race board game (public-domain mechanics of the Pachisi / Ludo family).

Everybody plays on their own device (family table, guests via QR code) or a child plays alone against bots – the
tables live in the `card_game` table with kind "heimwaerts" (lobby, join, summary, may_lead from cardgames.CardGames,
like Kartenlauf and «Fünf Würfel»).

Board: a cross of 11 × 11 cells with a shared track of 40 fields (10 per seat) running clockwise. Seat s has its start
field 10·s on the track, a yard with 4 pieces and 4 home fields that branch off the track just before the start field.
2 players sit opposite (seats 0, 2), 3 players on seats 0, 1, 2. A piece's position is counted from its own start
field: -1 yard, 0..39 the track (0 = own start field), 40..43 the home fields.

A turn: roll the die (on the server – the app only animates it), then move one piece by the number:
  - a 6 brings a piece out of the yard onto the own start field (if no own piece stands there) – and rolls again
    (every 6 rolls again, also when no piece can move);
  - landing on an opponent sends it back to its yard; two own pieces never share a field;
  - who has no piece that can move (all in the yard / home) gets three tries to roll a 6;
  - into the home only the own pieces, never jumping over pieces in the home. Rule `exact` (default on): the exact
    number is needed; off: a piece goes as deep as the number (and the free fields) allow.
Safe fields: the 4 start fields – a piece there cannot be hit, pieces of different colours may share it.
Rule `bench` («Eile-mit-Weile-Bänkli», default off): 4 more benches halfway along the arms; a piece on a start field
or a bench cannot be hit AND no other piece may pass or land there – only the owner of a start field, coming out of
the yard, sends a piece sitting on it back home.
End: the first with all 4 pieces home wins. Rule `play_on` (default on): the others play on for the next places (the
game ends when one is left, or only bots are left); off: the game ends when the winner is in (the others ranked by
how far they are). Who leads may end the game early: ranked as it stands, but coins only for a game played to the end.
Coins (setting `game_rewards["heimwaerts"]`): places 1–3, only people of the family at a family table with at least
two of them – never alone against bots; paid once (flag `paid`, a unique ledger `ref` per player).
Bots (easy / normal / hard: hard prefers hitting, safe fields and finishing) move with a reaction time (bot_ms).
"""
from __future__ import annotations

import json
import random
import time

from .cardgames import BOTS, BOT_DELAY, CardGames, bot_delay, apply_starter, starter_mode
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .running import win_reason

KIND = "heimwaerts"
TITLE = "Heimwärts"
EMOJI = "🏠"
RING = 40
PER_SEAT = 10
HOME = 40                      # positions 40..43: the home fields 0..3 of the piece's owner
LAST = HOME + 3
YARD = -1
PIECES = 4
TRIES = 3
MAX_PLAYERS = 4
SEATS = {1: [0], 2: [0, 2], 3: [0, 1, 2], 4: [0, 1, 2, 3]}
STARTS = tuple(PER_SEAT * s for s in range(4))
BENCHES = tuple(PER_SEAT * s + 5 for s in range(4))
LEVELS = ("easy", "normal", "hard")
DEFAULTS = {"bots": 3, "level": "normal", "bot_ms": 1400, "bench": False, "exact": True, "play_on": True}
MAX_TURNS = 4000               # safety: a game that never ends is decided by progress


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now

    @property
    def r(self) -> dict:
        return self.st["rules"]

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    def seat_of(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def seat(self, pid: str) -> int:
        return self.st["seats"][pid]

    def field(self, pid: str, rel: int) -> int:
        """The track field (0..39) of a piece at this position (0..39) of this player."""
        return (PER_SEAT * self.seat(pid) + rel) % RING

    def safe(self) -> set[int]:
        return set(STARTS) | (set(BENCHES) if self.r.get("bench") else set())

    def on_field(self, f: int) -> list[tuple[str, int]]:
        """The pieces (owner, index) on a track field."""
        P = self.st["pieces"]
        return [(p, i) for p in self.order() for i, rel in enumerate(P[p]) if 0 <= rel < RING and self.field(p, rel) == f]

    # ---------- the game
    def setup(self, first: str | None = None) -> None:
        """The seats (colours) in the order of the lobby – `first` (the starter) rolls first, then clockwise."""
        ids = self.order()
        if not 2 <= len(ids) <= MAX_PLAYERS:
            raise CommunityError("Add a bot or wait for a second player")
        self.st["seats"] = {pid: s for pid, s in zip(ids, SEATS[len(ids)])}
        self.st["pieces"] = {pid: [YARD] * PIECES for pid in ids}
        self.st.update(phase="play", turn=first if first in ids else ids[0], stage="roll", die=None, roll_seq=0, tries=0, turns=0, last=None, log=[],
                       finished_order=[], ranking=None, places=None, complete=False, turn_at=self.now())

    def _check(self, pid: str) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        if self.st.get("turn") != pid:
            raise CommunityError("It is not your turn")

    def target(self, pid: str, i: int, die: int) -> dict | None:
        """Where piece i of this player goes with this number (None: it cannot move)."""
        P = self.st["pieces"]
        mine = P[pid]
        rel = mine[i]
        bench = bool(self.r.get("bench"))
        safe = self.safe()
        if rel == YARD:
            if die != 6 or 0 in mine:
                return None
            start = self.field(pid, 0)
            others = [x for x in self.on_field(start) if x[0] != pid]
            return {"piece": i, "from": YARD, "to": 0, "hit": others if bench else []}     # the owner's right on its bench
        if rel >= HOME:                                                   # deeper into the home
            to = rel + die
            if to > LAST:
                if self.r.get("exact", True):
                    return None
                to = LAST
            for h in range(rel + 1, to + 1):
                if h in mine:                                             # never jump over a piece in the home
                    if self.r.get("exact", True):
                        return None
                    to = h - 1
                    break
            return {"piece": i, "from": rel, "to": to, "hit": []} if to > rel else None
        to = rel + die
        if to >= HOME:
            if to > LAST:
                if self.r.get("exact", True):
                    return None
                to = LAST
            for h in range(HOME, to + 1):
                if h in mine:
                    if self.r.get("exact", True):
                        return None
                    to = h - 1
                    break
            if to < HOME:
                return None
        # the track fields passed (and the one landed on)
        if bench:
            last_ring = min(to, RING - 1)
            for k in range(rel + 1, last_ring + 1):
                f = self.field(pid, k)
                if f in safe and self.on_field(f):                        # nobody passes or lands on an occupied bench
                    return None
        if to >= HOME:
            return {"piece": i, "from": rel, "to": to, "hit": []}
        f = self.field(pid, to)
        here = self.on_field(f)
        if any(o == pid for o, _ in here):
            return None
        hit = []
        if here and f not in safe:
            hit = here
        return {"piece": i, "from": rel, "to": to, "hit": hit}

    def moves(self, pid: str, die: int | None = None) -> list[dict]:
        die = die if die is not None else self.st.get("die")
        if not die:
            return []
        out = []
        for i in range(PIECES):
            t = self.target(pid, i, die)
            if t:
                out.append(t)
        return out

    def active(self, pid: str) -> bool:
        """Has a piece that could move without a 6 (on the track, or in the home with a free field ahead)."""
        mine = self.st["pieces"][pid]
        for rel in mine:
            if 0 <= rel < RING:
                return True
            if HOME <= rel < LAST and rel + 1 not in mine:
                return True
        return False

    def finished(self, pid: str) -> bool:
        return all(rel >= HOME for rel in self.st["pieces"][pid])

    def _log(self, ev: dict) -> None:
        ev["t"] = self.now()
        ev["seq"] = self.st.get("seq", 0) + 1
        self.st["seq"] = ev["seq"]
        self.st["last"] = ev
        log = self.st.setdefault("log", [])
        log.append(ev)
        del log[:-10]

    def roll(self, pid: str) -> int:
        self._check(pid)
        if self.st["stage"] != "roll":
            raise CommunityError("Move a piece first")
        v = self.rng.randint(1, 6)
        self.st["die"] = v
        self.st["roll_seq"] = self.st.get("roll_seq", 0) + 1
        self.st["turn_at"] = self.now()
        if self.moves(pid, v):
            self.st["stage"] = "move"
            self._log({"player": pid, "die": v, "kind": "roll"})
            return v
        if v == 6:                                                        # a 6 rolls again, even without a move
            self._log({"player": pid, "die": v, "kind": "again"})
        elif not self.active(pid) and self.st.get("tries", 0) + 1 < TRIES:
            self.st["tries"] = self.st.get("tries", 0) + 1
            self._log({"player": pid, "die": v, "kind": "try", "try": self.st["tries"]})
        else:
            self._log({"player": pid, "die": v, "kind": "pass"})
            self._next()
        return v

    def move(self, pid: str, piece) -> dict:
        self._check(pid)
        if self.st["stage"] != "move":
            raise CommunityError("Roll first")
        try:
            piece = int(piece)
        except (TypeError, ValueError):
            raise CommunityError("This piece cannot move") from None
        die = self.st["die"]
        mv = next((m for m in self.moves(pid, die) if m["piece"] == piece), None)
        if not mv:
            raise CommunityError("This piece cannot move")
        P = self.st["pieces"]
        for o, j in mv["hit"]:
            P[o][j] = YARD
        P[pid][piece] = mv["to"]
        self._log({"player": pid, "die": die, "kind": "move", "piece": piece, "from": mv["from"], "to": mv["to"],
                   "hit": [[o, j] for o, j in mv["hit"]], "out": mv["from"] == YARD, "home": mv["to"] >= HOME > mv["from"]})
        self.st["tries"] = 0
        if self.finished(pid) and pid not in self.st["finished_order"]:
            self.st["finished_order"].append(pid)
            if self._maybe_end():
                return mv
        if die == 6 and not self.finished(pid):
            self.st["stage"] = "roll"
            self.st["turn_at"] = self.now()
        else:
            self._next()
        return mv

    def _maybe_end(self) -> bool:
        fin = self.st["finished_order"]
        left = [p for p in self.order() if p not in fin]
        if not fin:
            return False
        if not self.r.get("play_on", True) or len(left) <= 1 or all((self.seat_of(p) or {}).get("bot") for p in left):
            self.st["complete"] = True
            self._finish()
            return True
        return False

    def _next(self) -> None:
        order = self.order()
        i = order.index(self.st["turn"])
        self.st["turns"] = self.st.get("turns", 0) + 1
        if self.st["turns"] >= MAX_TURNS:
            self.st["complete"] = True
            self._finish()
            return
        for k in range(1, len(order) + 1):
            p = order[(i + k) % len(order)]
            if p not in self.st["finished_order"]:
                self.st.update(turn=p, stage="roll", tries=0, turn_at=self.now())
                return
        self._finish()

    def progress(self, pid: str) -> int:
        return sum(rel + 1 for rel in self.st["pieces"][pid] if rel >= 0)

    def home_count(self, pid: str) -> int:
        return sum(1 for rel in self.st["pieces"][pid] if rel >= HOME)

    def _finish(self) -> None:
        order = self.order()
        fin = self.st.get("finished_order") or []
        score = {p: (100 - fin.index(p)) * 1000 if p in fin else self.progress(p) for p in order}
        self.st["places"] = places(order, score)
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st.update(phase="done", turn=None, stage=None, finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: ranked as it stands (no coins – see coins_for)."""
        if self.st.get("phase") == "play":
            self._finish()

    # ---------- bots
    def _danger(self, pid: str, f: int, P: dict) -> int:
        """How many opponent pieces could land on track field f with one roll (1..6 behind it, or out of the yard
        onto their start field when that is f and the benches are on)."""
        n = 0
        for o in self.order():
            if o == pid:
                continue
            for rel in P[o]:
                if 0 <= rel < RING:
                    d = (f - self.field(o, rel)) % RING
                    if 1 <= d <= 6 and rel + d < RING:
                        n += 1
            if self.r.get("bench") and f == self.field(o, 0) and YARD in P[o]:
                n += 2
        return n

    def bot_move(self, pid: str, level: str = "normal") -> int:
        ms = self.moves(pid)
        if level == "easy":
            if self.rng.random() < 0.5:                                   # half of the time: just a piece that can move
                return self.rng.choice(ms)["piece"]
            return max(ms, key=lambda m: (bool(m["hit"]), m["from"] == YARD, self.rng.random()))["piece"]
        if level == "normal":
            def key(m):
                return (bool(m["hit"]) * 50 + (m["to"] >= HOME > m["from"]) * 40 + (m["from"] == YARD) * 30
                        + m["to"] * 0.5 + self.rng.random() * 3)
            return max(ms, key=key)["piece"]
        P = self.st["pieces"]
        safe = self.safe()

        def value(m):                                                     # hard: hit, finish, come out, stay safe
            after = {o: list(rs) for o, rs in P.items()}
            for o, j in m["hit"]:
                after[o][j] = YARD
            after[pid][m["piece"]] = m["to"]
            v = bool(m["hit"]) * 60 + (m["to"] >= HOME > m["from"]) * 40 + (m["from"] == YARD) * 30 + m["to"] * 0.5
            if 0 <= m["to"] < RING:
                f = self.field(pid, m["to"])
                v += 6 if f in safe else -12 * self._danger(pid, f, after)
            if 0 <= m["from"] < RING and self.field(pid, m["from"]) not in safe:
                v += 10 * self._danger(pid, self.field(pid, m["from"]), P)     # get away from a piece behind
            return v + self.rng.random() * 0.1
        return max(ms, key=value)["piece"]

    def tick(self) -> bool:
        """The bots roll and move (after their reaction time; at once with bot_ms 0). True if something changed."""
        changed = False
        delay = bot_delay(self.r, BOT_DELAY)
        for _ in range(MAX_TURNS * 3 if delay == 0 else 1):
            if self.st.get("phase") != "play":
                break
            p = self.seat_of(self.st.get("turn") or "")
            if not p or not p.get("bot"):
                break
            wait = delay if self.st["stage"] == "roll" else delay * 0.6
            if self.now() - self.st.get("turn_at", 0) < wait:
                break
            if self.st["stage"] == "roll":
                self.roll(p["id"])
            else:
                self.move(p["id"], self.bot_move(p["id"], p.get("level", "normal")))
            changed = True
        return changed


# ================================================================ the games in the database (table card_game, kind "heimwaerts")
class Heimwaerts(CardGames):
    """The family table / own tables against bots – the same rows and lobby as the card games (summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng: random.Random | None = None):
        super().__init__(db, add_history)
        self.rewards = rewards
        self.now = now
        self.rng = rng

    def table(self, st: dict) -> Table:
        return Table(st, self.rng, now=lambda: self.now())

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, {**DEFAULTS, **(self.db.get_setting(f"game_rules.{KIND}") or {})})

    def rules_info(self) -> dict:
        return {**self.default_rules(), "rewards": rewards_of(self.db), "max_players": MAX_PLAYERS}

    def clean_rules(self, kind: str, r: dict) -> dict:
        out = {}
        for k, v in DEFAULTS.items():
            x = (r or {}).get(k, v)
            if isinstance(v, bool):
                out[k] = bool(x)
            elif isinstance(v, int):
                try:
                    out[k] = int(x)
                except (TypeError, ValueError):
                    out[k] = v
            else:
                out[k] = str(x)
        out["bots"] = max(0, min(MAX_PLAYERS - 1, out["bots"]))
        out["bot_ms"] = max(0, min(5000, out["bot_ms"]))
        out["level"] = out["level"] if out["level"] in LEVELS else "normal"
        return out

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status != "done" or st.get("paid") or st.get("places") is None:
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", win_reason(KIND, st['places'][pid]), ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history:
            t = Table(st)
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]), "home": t.home_count(p["id"]),
                        "complete": bool(st.get("complete")), "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins per player: places 1–3, only people of the family, only with at least two of them at a family table,
        only for a game played to the end."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if st.get("solo") or len(people) < 2 or st.get("phase") != "done" or not st.get("complete"):
            return {}
        amounts = rewards_of(self.db)
        pl = st.get("places") or {}
        out = {}
        for p in people:
            n = pl.get(p["id"])
            if n and 1 <= n <= 3 and amounts[n - 1] > 0:
                out[p["id"]] = amounts[n - 1]
        return out

    def _bots(self, st: dict, need: int) -> list[dict]:
        if need > 0 and self.bots_off(KIND, st["players"]):          # parent area › Games: without bots
            st.pop("bot_pool", None)
            return []
        pool = st.pop("bot_pool", None) or []
        taken = {b["name"] for b in pool}
        for n, e in random.sample(BOTS, len(BOTS)):
            if len(pool) >= need:
                break
            if n not in taken:
                pool.append({"name": n, "emoji": e, "level": st["rules"]["level"]})
                taken.add(n)
        out = []
        for i, b in enumerate(pool[:need]):
            lvl = b.get("level") if b.get("level") in LEVELS else st["rules"]["level"]
            out.append({"id": f"bot{i + 1}", "name": b["name"], "emoji": b.get("emoji") or "🤖", "color": b.get("color"),
                        "owner": b.get("owner"), "bot": True, "level": lvl})
        return out

    def _deal(self, st: dict, first: str | None = None) -> None:
        humans = [p for p in st["players"] if not p.get("bot")]
        n = st["rules"]["bots"]
        if st.get("solo"):
            n = max(1, n)
        n = max(0, min(n, MAX_PLAYERS - len(humans)))
        st["players"] = humans + self._bots(st, n)
        st.pop("bot_pool", None)
        if len(st["players"]) < 2:
            raise CommunityError("Add a bot or wait for a second player")
        self.table(st).setup(first)

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
            st = {"kind": KIND, "rules": r, "players": [self._person(host)], "phase": "lobby", "solo": solo, "bot_pool": list(bots or [])}
            gid = self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, int(solo), json.dumps(st))
            if solo:                                      # alone against bots: the game starts right away
                row = self.db.q1("SELECT * FROM card_game WHERE id=?", gid)
                self._deal(st)
                self._save(row, st)
            return gid

    def join(self, kind: str, pid: int) -> None:
        with self.lock:
            row = self._row(KIND)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if any(p["id"] == str(pid) for p in st["players"]):
                return
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) >= MAX_PLAYERS:
                raise CommunityError("The table is full")
            st["players"].append(self._person(pid))
            self._save(row, st)

    def begin(self, kind: str, viewer: int, starter=None) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            seats = list(st["players"])          # the seats and colours stay as in the lobby – the starter only rolls first
            first = apply_starter(st, starter_mode(self.db), starter, leader=row["host_id"])     # who begins (parent area › Games)
            st["players"] = seats
            self._deal(st, first)
            self._save(row, st)

    def _with(self, viewer: int, fn):
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            t = self.table(st)
            t.tick()
            try:
                return fn(t)
            finally:
                self._save(row, st)

    def roll(self, pid: int) -> int:
        return self._with(pid, lambda t: t.roll(str(pid)))

    def move(self, pid: int, piece) -> dict:
        return self._with(pid, lambda t: t.move(str(pid), piece))

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: ranked as it stands (coins only for a game played to the end)."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] == "play":
                self.table(st).end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int) -> dict | None:
        with self.lock:
            row = self._row(KIND, viewer)
            if row:
                st = json.loads(row["state"])
                if st["phase"] == "play" and self.table(st).tick():
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
        joined = any(p["id"] == me for p in st["players"])
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        ph = st["phase"]
        if row["status"] == "done" and ph != "lobby":
            ph = "done"
        base = {"game": row["id"], "starter": st.get("starter"), "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph,
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "joined": joined,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2, "max_players": MAX_PLAYERS}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            bots = st["rules"]["bots"] if not st.get("solo") else max(1, st["rules"]["bots"])
            return {**base, "players": players, "bots": max(0, min(bots, MAX_PLAYERS - len(players)))}
        t = self.table(st)
        coins, pl = st.get("coins") or {}, st.get("places") or {}
        fin = st.get("finished_order") or []
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                    "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"), "seat": st["seats"][p["id"]],
                    "pieces": list(st["pieces"][p["id"]]), "home": t.home_count(p["id"]),
                    "finished": fin.index(p["id"]) + 1 if p["id"] in fin else None,
                    "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0)} for p in st["players"]]
        my_turn = joined and ph == "play" and st.get("turn") == me
        return {**base, "players": players, "turn": st.get("turn") if ph == "play" else None, "stage": st.get("stage") if ph == "play" else None,
                "die": st.get("die"), "roll_seq": st.get("roll_seq", 0), "tries": st.get("tries", 0), "max_tries": TRIES,
                "me": me if joined else None, "my_seat": st["seats"].get(me) if joined else None, "my_turn": my_turn,
                "can_roll": my_turn and st.get("stage") == "roll",
                "three_tries": my_turn and st.get("stage") == "roll" and not t.active(me),
                "moves": t.moves(me) if my_turn and st.get("stage") == "move" else [],
                "last": st.get("last"), "log": st.get("log") or [], "safe": sorted(t.safe()), "starts": list(STARTS),
                "benches": list(BENCHES) if st["rules"].get("bench") else [],
                "finished_order": fin, "ranking": st.get("ranking"), "complete": bool(st.get("complete"))}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
