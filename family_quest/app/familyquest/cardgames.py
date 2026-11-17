"""Card games where you shed your cards – the base for «Tschau Sepp» and «Kartenkarussell».

Everybody plays on their own device; the family plays together (guests via QR code) or a child plays alone against
bots. Bots are animals with their own name and look; they move by themselves (lazy: every state request moves the
bots whose turn it is, after a short delay so people can follow).

A move: play a card that fits the top card (same suit / colour or same value; wild cards fit always), or draw.
Special cards (the one who starts sets which are on; the last rules are the default):
  draw2  – the next player draws 2 (stacks: the next can answer with the same card, the sum grows)
  draw4  – wild, choose a suit/colour, the next player draws 4 (Kartenkarussell)
  skip   – the next player is skipped
  reverse – the direction changes (with two players: like skip)
  wish   – wild: play it on any card and choose the suit/colour (not on another wish card)
  again  – play one more card
Calls: going down to one card you must say «Tschau» (Kartenkarussell: «Letzte!»), with the last card «Sepp»
(«Fertig!»). Forgotten → 2 penalty cards (setting).
Rounds: who has no cards first wins the round; the others get the points of their cards. After the set number of
rounds (or when somebody passes the point limit) the lowest points win.
"""
from __future__ import annotations

import json
import secrets
import random
import threading
import time

from .community import CommunityError

BOTS = [("Fuchs Fridolin", "🦊"), ("Bär Bruno", "🐻"), ("Eule Olga", "🦉"), ("Frosch Fritz", "🐸"), ("Katze Kiki", "🐱"),
        ("Hase Hoppel", "🐰"), ("Pinguin Pino", "🐧"), ("Igel Ida", "🦔")]
BOT_DELAY = 1.4                      # seconds before a bot moves (default – the reaction time is set at the start: bot_ms)

# ---------------------------------------------------------------- the two games
SWISS = {"suits": ["schellen", "schilten", "rosen", "eicheln"], "ranks": ["6", "7", "8", "9", "10", "U", "O", "K", "A"]}
FRENCH = {"suits": ["s", "h", "d", "c"], "ranks": ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]}
KARUSSELL_COLORS = ["violet", "pink", "orange", "petrol"]

GAMES = {
    "tschau": {
        "title": "Tschau Sepp",
        "defaults": {"deck": "swiss", "hand": 7, "rounds": 1, "draw2": True, "skip": True, "wish": True, "again": True,
                     "reverse": False, "stack": True, "penalty": 2, "bots": 2, "level": "normal", "back": "classic", "bot_ms": 1400},
        "calls": ("Tschau", "Sepp"),
    },
    "karussell": {
        "title": "Kartenkarussell",
        "defaults": {"hand": 7, "rounds": 1, "stack": True, "penalty": 2, "bots": 2, "level": "normal", "back": "classic", "bot_ms": 1400},
        "calls": ("Letzte!", "Fertig!"),
    },
}


def tschau_deck(rules: dict) -> list[str]:
    d = FRENCH if rules.get("deck") == "french" else SWISS
    return [f"{s}:{r}" for s in d["suits"] for r in d["ranks"]]


def karussell_deck() -> list[str]:
    cards = []
    for c in KARUSSELL_COLORS:
        cards.append(f"{c}:0")
        for n in range(1, 10):
            cards += [f"{c}:{n}"] * 2
        for sp in ("draw2", "skip", "reverse"):
            cards += [f"{c}:{sp}"] * 2
    cards += ["wild:wish"] * 4 + ["wild:draw4"] * 4
    return cards


def effect(kind: str, card: str, rules: dict) -> str | None:
    """What a card does in this game with these rules (None = a plain card)."""
    suit, rank = card.split(":")
    if kind == "karussell":
        return rank if rank in ("draw2", "skip", "reverse", "wish", "draw4") else None
    if rank == "7" and rules.get("draw2"):
        return "draw2"
    if rank == "8" and rules.get("skip"):
        return "skip"
    if rank in ("U", "J") and rules.get("wish"):
        return "wish"
    if rank == "A" and rules.get("again"):
        return "again"
    if rank == "10" and rules.get("reverse"):
        return "reverse"
    return None


def points(kind: str, card: str, rules: dict) -> int:
    suit, rank = card.split(":")
    if kind == "karussell":
        return 50 if suit == "wild" else (20 if not rank.isdigit() else int(rank))
    if effect(kind, card, rules) == "wish":
        return 20
    if rank.isdigit():
        return int(rank)
    return {"U": 2, "J": 2, "O": 3, "Q": 3, "K": 4, "A": 11}.get(rank, 0)


# ================================================================ one table (pure logic on a dict)
class Shed:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now

    @property
    def kind(self) -> str:
        return self.st["kind"]

    @property
    def r(self) -> dict:
        return self.st["rules"]

    def seat(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    # ---------- a round
    def deal(self) -> None:
        deck = karussell_deck() if self.kind == "karussell" else tschau_deck(self.r)
        self.rng.shuffle(deck)
        # many players, few cards (36 Swiss cards): fewer cards each, so that a pile to draw from is left
        n = max(1, len(self.st["players"]))
        size = max(1, min(int(self.r.get("hand") or 7), (len(deck) - 8) // n))
        hands = {p["id"]: [deck.pop() for _ in range(size)] for p in self.st["players"]}
        top = deck.pop()
        for _ in range(len(deck)):                                     # no wild card to start with (if there is another)
            if effect(self.kind, top, self.r) not in ("wish", "draw4"):
                break
            deck.insert(0, top)
            top = deck.pop()
        rnd = self.st.get("round", 0) + 1
        starter = self.order()[(rnd - 1) % len(self.order())]
        self.st.update(round=rnd, deck=deck, discard=[top], hands=hands, turn=starter, direction=1, wish=None,
                       pending=0, drawn=False, again=False, phase="play", said={}, round_result=None, last=None)
        self.st["turn_at"] = self.now()

    def top(self) -> str:
        return self.st["discard"][-1]

    def fits(self, card: str) -> bool:
        top = self.top()
        eff, top_eff = effect(self.kind, card, self.r), effect(self.kind, top, self.r)
        if self.st["pending"]:                      # a draw-2 / draw-4 is open: only answer with the same, if stacking is on
            return bool(self.r.get("stack")) and eff == top_eff and eff in ("draw2", "draw4")
        if eff in ("wish", "draw4"):
            return not (self.kind == "tschau" and top_eff == "wish")    # no wish on wish (Tschau Sepp)
        s, r = card.split(":")
        ts, tr = top.split(":")
        want = self.st.get("wish") or ts
        return s == want or (r == tr and not self.st.get("wish"))

    def playable(self, pid: str) -> list[str]:
        if self.st.get("phase") != "play" or self.st["turn"] != pid:
            return []
        return [c for c in dict.fromkeys(self.st["hands"][pid]) if self.fits(c)]

    def _next(self, steps: int = 1) -> str:
        order = self.order()
        i = order.index(self.st["turn"])
        return order[(i + steps * self.st["direction"]) % len(order)]

    def _draw(self, pid: str, n: int) -> list[str]:
        got = []
        for _ in range(n):
            if not self.st["deck"]:
                if len(self.st["discard"]) <= 1:
                    break
                top = self.st["discard"].pop()
                self.st["deck"] = self.st["discard"]
                self.rng.shuffle(self.st["deck"])
                self.st["discard"] = [top]
            got.append(self.st["deck"].pop())
        self.st["hands"][pid] += got
        return got

    def play(self, pid: str, card: str, wish: str | None = None, say: bool = False) -> None:
        if self.st.get("phase") != "play" or self.st["turn"] != pid:
            raise CommunityError("It is not your turn")
        hand = self.st["hands"][pid]
        if card not in hand:
            raise CommunityError("You do not have this card")
        if not self.fits(card):
            raise CommunityError("This card does not fit")
        if self.st["drawn"] and card != hand[-1]:
            raise CommunityError("After drawing you may only play the card you drew")
        eff = effect(self.kind, card, self.r)
        suits = KARUSSELL_COLORS if self.kind == "karussell" else (FRENCH if self.r.get("deck") == "french" else SWISS)["suits"]
        if eff in ("wish", "draw4") and wish not in suits:
            raise CommunityError("Choose a suit")
        hand.remove(card)
        self.st["discard"].append(card)
        self.st["wish"] = wish if eff in ("wish", "draw4") else None
        self.st["drawn"] = False
        self.st["last"] = {"player": pid, "card": card, "wish": self.st["wish"], "t": self.now()}
        # calls: «Tschau» going down to one card, «Sepp» with the last one – forgotten: penalty cards
        left = len(hand)
        if left in (0, 1):
            if not say:
                pen = int(self.r.get("penalty") or 0)
                if pen:
                    self._draw(pid, pen)
                    self.st["last"]["penalty"] = pen
                    left = len(hand)
            else:
                self.st["said"][pid] = left
        if left == 0:
            self._round_end(pid)
            return
        steps = 1
        if eff == "draw2":
            self.st["pending"] += 2
        elif eff == "draw4":
            self.st["pending"] += 4
        elif eff == "skip":
            steps = 2
        elif eff == "reverse":
            self.st["direction"] *= -1
            if len(self.order()) == 2:
                steps = 2
        elif eff == "again":
            self.st["turn_at"] = self.now()
            return                                   # same player once more
        self.st["turn"] = self._next(steps)
        self.st["turn_at"] = self.now()

    def draw(self, pid: str) -> list[str]:
        if self.st.get("phase") != "play" or self.st["turn"] != pid:
            raise CommunityError("It is not your turn")
        if self.st["pending"]:                       # take the open draw-2 / draw-4 – then the turn passes
            got = self._draw(pid, self.st["pending"])
            self.st["pending"] = 0
            self.st["last"] = {"player": pid, "drew": len(got), "t": self.now()}
            self.st["turn"] = self._next()
            self.st["turn_at"] = self.now()
            return got
        if self.st["drawn"]:
            raise CommunityError("You have drawn already – play the card or pass")
        got = self._draw(pid, 1)
        self.st["drawn"] = True
        self.st["last"] = {"player": pid, "drew": len(got), "t": self.now()}
        if not got or not self.fits(got[0]):
            self.pass_turn(pid)
        return got

    def pass_turn(self, pid: str) -> None:
        if self.st["turn"] != pid or not self.st["drawn"]:
            raise CommunityError("Draw a card first")
        self.st["drawn"] = False
        self.st["turn"] = self._next()
        self.st["turn_at"] = self.now()

    def _round_end(self, winner: str) -> None:
        scores = self.st.setdefault("scores", {p: 0 for p in self.order()})
        for p, hand in self.st["hands"].items():
            scores[p] = scores.get(p, 0) + sum(points(self.kind, c, self.r) for c in hand)
        wins = self.st.setdefault("wins", {})
        wins[winner] = wins.get(winner, 0) + 1
        self.st["round_result"] = {"winner": winner, "points": {p: sum(points(self.kind, c, self.r) for c in h) for p, h in self.st["hands"].items()}}
        if self.st["round"] >= int(self.r.get("rounds") or 1):
            self.st["phase"] = "done"
            ranking = sorted(self.order(), key=lambda p: (scores.get(p, 0), -wins.get(p, 0)))
            self.st["ranking"] = ranking
            self.st["finished"] = self.now()
        else:
            self.st["phase"] = "between"
            self.st["next_at"] = self.now() + 6

    # ---------- bots
    def bot_move(self, pid: str, level: str = "normal") -> None:
        hand = self.st["hands"][pid]
        cards = self.playable(pid)
        if self.st["drawn"]:
            cards = [c for c in cards if c == hand[-1]]
        if not cards:
            if self.st["drawn"]:
                self.pass_turn(pid)
            else:
                self.draw(pid)
            return
        if level == "easy":
            card = self.rng.choice(cards)
        else:                                       # keep wild cards for later, attack when the next one is almost out
            nxt = self._next()
            danger = len(self.st["hands"].get(nxt, [])) <= 2
            def score(c):
                e = effect(self.kind, c, self.r)
                if e in ("draw2", "draw4", "skip"):
                    return 3 if danger else 1
                if e == "wish":
                    return -2
                return 0
            card = max(cards, key=lambda c: (score(c), points(self.kind, c, self.r), self.rng.random()))
        wish = None
        if effect(self.kind, card, self.r) in ("wish", "draw4"):
            rest = [c.split(":")[0] for c in hand if c != card and c.split(":")[0] != "wild"]
            pool = KARUSSELL_COLORS if self.kind == "karussell" else (FRENCH if self.r.get("deck") == "french" else SWISS)["suits"]
            wish = max(pool, key=lambda s: (rest.count(s), self.rng.random()))
        say = self.rng.random() > (0.25 if level == "easy" else 0.0)       # easy bots sometimes forget to call
        self.play(pid, card, wish, say)

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
            p = self.seat(self.st["turn"])
            if not p or not p.get("bot") or self.now() - self.st.get("turn_at", 0) < bot_delay(self.st["rules"], BOT_DELAY):
                break
            self.bot_move(p["id"], p.get("level", "normal"))
            changed = True
            self.st["turn_at"] = self.now()
        return changed


def bot_delay(rules: dict, default: float) -> float:
    """Seconds before a bot moves – set when starting a game (bot_ms, 0 = at once)."""
    try:
        return max(0, min(5000, int(rules.get("bot_ms", default * 1000)))) / 1000
    except (TypeError, ValueError):
        return default


# ================================================================ the games in the database
# ---------------------------------------------------------------- who begins (parent area › Settings › Games)
STARTER_MODES = ("dice", "leader", "choose")


def starter_mode(db) -> str:
    m = db.get_setting("game_starter")
    return m if m in STARTER_MODES else "dice"


def apply_starter(st: dict, mode: str, chosen=None, leader=None) -> str:
    """Who begins a turn-based game: the player list is turned round so that this player comes first – seat order,
    teams and partners stay as they are. dice = drawn at random, leader = whoever leads the table, choose = the
    player the leader picked (`chosen`; without a valid choice: the leader). Stores st["starter"] for the banner."""
    players = st.get("players") or []
    if not players:
        return ""
    ids = [str(p["id"]) for p in players]
    how = mode if mode in STARTER_MODES else "dice"
    first = None
    if how == "choose" and chosen is not None and str(chosen) in ids:
        first = str(chosen)
    elif how in ("leader", "choose"):
        first = str(leader) if leader is not None and str(leader) in ids else ids[0]
        how = "leader" if how == "leader" or chosen is None else how
    else:
        first = secrets.choice(ids)
        how = "dice"
    i = ids.index(first)
    st["players"] = players[i:] + players[:i]
    p = st["players"][0]
    st["starter"] = {"id": first, "how": how, "name": p.get("name") or "?", "at": time.time()}
    return first


class CardGames:
    no_bots = None     # hook (services.table_without_bots): (kind, ids of the people) → True when no bot may sit at the table

    def __init__(self, db, add_history=None):
        self.db = db
        self.add_history = add_history
        self.lock = threading.Lock()

    def bots_off(self, kind: str, players: list) -> bool:
        """The parents switched the bots off for this game (parent area › Games) – not when a parent plays along."""
        if not self.no_bots:
            return False
        ids = [p["id"] if isinstance(p, dict) else p for p in players if not (isinstance(p, dict) and (p.get("bot") or p.get("guest")))]
        return bool(self.no_bots(kind, ids))

    def default_rules(self, kind: str) -> dict:
        return {**GAMES[kind]["defaults"], **(self.db.get_setting(f"game_rules.{kind}") or {})}

    def clean_rules(self, kind: str, r: dict) -> dict:
        d = GAMES[kind]["defaults"]
        out = {}
        for k, v in d.items():
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
        out["hand"] = max(3, min(10, out["hand"]))
        out["rounds"] = max(1, min(10, out["rounds"]))
        out["penalty"] = max(0, min(4, out["penalty"]))
        out["bots"] = max(0, min(5, out["bots"]))
        out["bot_ms"] = max(0, min(5000, out["bot_ms"]))
        out["level"] = out["level"] if out["level"] in ("easy", "normal") else "normal"
        out["back"] = out["back"] if out["back"] in ("classic", "stars", "waves", "checks") else "classic"
        if kind == "tschau":
            out["deck"] = out["deck"] if out["deck"] in ("swiss", "french") else "swiss"
        return out

    # ---------- which table
    def _row(self, kind: str, viewer: int | None = None):
        """The family table of this game, or the viewer's own table against bots."""
        if viewer is not None:
            mine = self.db.q1("""SELECT * FROM card_game WHERE kind=? AND status!='done' AND solo=1 AND host_id=? ORDER BY id DESC LIMIT 1""",
                              kind, viewer)
            if mine:
                return mine
        return self.db.q1("SELECT * FROM card_game WHERE kind=? AND status!='done' AND solo=0 ORDER BY id DESC LIMIT 1", kind)

    def _game(self, kind: str):
        row = self._row(kind)
        return {"id": row["id"], "status": row["status"]} if row else None

    def may_lead(self, kind: str, prof: dict) -> bool:
        row = self._row(kind, prof["id"])
        return bool(row) and (prof["role"] == "parent" or row["host_id"] == prof["id"])

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status == "done" and self.add_history and not st.get("history_written"):
            st["history_written"] = True
            self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
            self._champion(st, (st.get("ranking") or [])[:1])
            for i, pid in enumerate(st.get("ranking", [])):
                p = next(x for x in st["players"] if x["id"] == pid)
                if not p.get("bot"):
                    try:
                        self.add_history(int(pid), "cards", {"game": GAMES[st["kind"]]["title"], "place": i + 1, "players": len(st["players"])})
                    except Exception:  # noqa: BLE001
                        pass

    def _champion(self, st: dict, winners: list) -> None:
        """A family game is over: the «No. 1» hat goes to the winners (community.family_result) – not alone against
        bots, not without a winner; guests and bots do not count."""
        if st.get("solo") or not self.add_history or not winners:
            return
        people = [p["id"] for p in st["players"] if not p.get("bot") and not p.get("guest")]
        try:
            self.add_history(0, "__family__", {"people": people, "winners": [w for w in winners if w in people]})
        except Exception:  # noqa: BLE001
            pass

    def _person(self, pid: int) -> dict:
        p = self.db.q1("SELECT name, avatar FROM profile WHERE id=?", pid)
        return {"id": str(pid), "name": p["name"] if p else "?", "avatar": json.loads(p["avatar"] or "{}") if p else {}}

    def start(self, kind: str, host: int, rules: dict | None = None, solo: bool = False, bots: list[dict] | None = None) -> int:
        if kind not in GAMES:
            raise CommunityError("Unknown game")
        with self.lock:
            if not solo and self._row(kind):
                raise CommunityError("This game is already running")
            if solo:
                old = self._row(kind, host)
                if old and old["solo"]:
                    self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", old["id"])
            r = self.clean_rules(kind, {**self.default_rules(kind), **{k: v for k, v in (rules or {}).items() if v is not None}})
            self.db.set_setting(f"game_rules.{kind}", r)
            players = [self._person(host)]
            n_bots = r["bots"] if not solo else max(1, r["bots"])
            if n_bots and self.bots_off(kind, [host]):
                raise CommunityError("Playing with bots is switched off for this game")
            if bots is None:
                bots = [{"name": n, "emoji": e, "level": r["level"]} for n, e in random.sample(BOTS, len(BOTS))[:n_bots]]
            for i, b in enumerate(bots[:n_bots]):
                players.append({"id": f"bot{i + 1}", "name": b["name"], "emoji": b.get("emoji") or "🤖", "color": b.get("color"),
                                "owner": b.get("owner"), "bot": True,
                                "level": "easy" if b.get("level") == "easy" else "normal"})
            st = {"kind": kind, "rules": r, "players": players, "phase": "lobby", "solo": solo}
            gid = self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", kind, host, int(solo), json.dumps(st))
            if solo:                                  # alone against bots: deal right away
                row = self.db.q1("SELECT * FROM card_game WHERE id=?", gid)
                apply_starter(st, starter_mode(self.db), None, leader=host)     # «choose» without a choice: you begin
                Shed(st).deal()
                self._save(row, st)
            return gid

    def join(self, kind: str, pid: int) -> None:
        with self.lock:
            row = self._row(kind)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if any(p["id"] == str(pid) for p in st["players"]):
                return
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) >= 8:
                raise CommunityError("The table is full")
            humans = [p for p in st["players"] if not p.get("bot")]
            st["players"].insert(len(humans), self._person(pid))
            self._save(row, st)

    def begin(self, kind: str, viewer: int, starter=None) -> None:
        with self.lock:
            row = self._row(kind, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) < 2:
                raise CommunityError("Add a bot or wait for a second player")
            apply_starter(st, starter_mode(self.db), starter, leader=row["host_id"])
            Shed(st).deal()
            self._save(row, st)

    def _with(self, kind: str, viewer: int, fn) -> None:
        with self.lock:
            row = self._row(kind, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            t = Shed(st)
            t.tick()
            fn(t)
            self._save(row, st)

    def play(self, kind: str, pid: int, card: str, wish: str | None, say: bool) -> None:
        self._with(kind, pid, lambda t: t.play(str(pid), card, wish, say))

    def draw(self, kind: str, pid: int) -> None:
        self._with(kind, pid, lambda t: t.draw(str(pid)))

    def pass_turn(self, kind: str, pid: int) -> None:
        self._with(kind, pid, lambda t: t.pass_turn(str(pid)))

    def end(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(kind, viewer)
            if row:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int) -> dict | None:
        with self.lock:
            row = self._row(kind, viewer)
            if row:
                st = json.loads(row["state"])
                if Shed(st).tick():
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
            else:
                row = self.db.q1("""SELECT * FROM card_game WHERE kind=? AND status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                    AND (solo=0 OR host_id=?) ORDER BY id DESC LIMIT 1""", kind, viewer)
                if not row:
                    return None
                st = json.loads(row["state"])
                if not any(p["id"] == str(viewer) for p in st["players"]):
                    return None
        return self._view(row, st, str(viewer))

    def _view(self, row, st: dict, me: str) -> dict:
        t = Shed(st)
        hands = st.get("hands") or {}
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")), "color": p.get("color"), "owner": p.get("owner"),
                    "cards": len(hands.get(p["id"], [])), "said": (st.get("said") or {}).get(p["id"]),
                    "score": (st.get("scores") or {}).get(p["id"], 0), "wins": (st.get("wins") or {}).get(p["id"], 0)}
                   for p in st["players"]]
        mine = hands.get(me)
        return {"game": row["id"], "kind": st["kind"], "title": GAMES[st["kind"]]["title"], "calls": GAMES[st["kind"]]["calls"],
                "status": row["status"], "phase": st["phase"], "starter": st.get("starter"), "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"],
                "players": players, "joined": any(p["id"] == me for p in st["players"]),
                "round": st.get("round", 0), "top": st["discard"][-1] if st.get("discard") else None,
                "deck_left": len(st.get("deck") or []), "turn": st.get("turn"), "direction": st.get("direction", 1),
                "wish": st.get("wish"), "pending": st.get("pending", 0), "drawn": st.get("drawn", False),
                "last": st.get("last"), "hand": mine, "playable": t.playable(me) if mine is not None else [],
                "round_result": st.get("round_result"), "ranking": st.get("ranking"),
                "next_ms": max(0, int((st.get("next_at", 0) - time.time()) * 1000)) if st["phase"] == "between" else None}

    def summary(self, kind: str, pid: int) -> dict | None:
        row = self._row(kind, pid)
        if not row:
            return None
        st = json.loads(row["state"])
        return {"status": row["status"], "joined": any(p["id"] == str(pid) for p in st["players"])}
