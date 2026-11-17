"""«Zeichnen & Raten» – a live drawing and guessing game for the family: everybody on their own device.

The tables live in the `card_game` table with kind "zeichnen" (no own table); lobby, join, end and summary come from
cardgames.CardGames, like «Stadt-Land-Fluss» (stadtland.py). Only people play (family and guests via QR code) – no
bots, 2 to 8 players.

Rules (chosen by who opens the table, remembered):
  category   a word list of zeichnen_data.py (animals, jobs, food, things at home, sports, mixed)
  rounds     1, 2 or 3 – everybody draws that many times (in seat order)
  time       60, 80 or 120 seconds per drawing
  hints      on: letters of the word are shown at 50 % and 75 % of the time (at most a third of the letters)
A turn: the drawer gets 3 words to choose from (CHOOSE seconds, then one is taken at random). The drawer draws on
their device; the strokes come to the server in small batches and the others poll them with a cursor (only what is
new). The others see the word only as a mask («_ _ _ _», plus the hint letters) and type guesses:
  - normalised: no case, accents, ä = ae = a, ß = ss, articles (der / die / das / ein …), spaces, hyphens;
  - right: the same text (or an alias) – for words of 5 letters or more one typo is fine (Levenshtein ≤ 1);
  - close: one or two letters off – only the guesser sees «close!»;
  - wrong guesses go to the shared chat – unless they contain the word (or are close): those only the guesser sees.
    A right guess is never shown – the chat says «… guessed it!».
Points: a right guess gets 50 + 50 × the time left (fraction), less 10 % for each who found it before (at least 10);
the drawer 10 per player who found the word. The turn ends when everybody found it or the time is up; the word is
shown to all for REVEAL seconds, then the next drawer. Who leads may skip a turn (the points so far stay) and end the
game (a drawing in progress counts as it stands).
Coins (setting `game_rewards["zeichnen"]`): places 1–3 (a tie shares the place) – only people of the family, only with
at least two of them, only when at least one turn was played and somebody scored; paid once (flag `paid`, a unique ledger `ref`).
The view never shows the word to a guesser who has not found it (only the mask) and never the text of a right guess.
"""
from __future__ import annotations

import json
import random
import re
import time
import unicodedata

from .cardgames import CardGames, apply_starter, starter_mode
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .zeichnen_data import CATEGORIES, DEFAULT

KIND = "zeichnen"
TITLE = "Zeichnen & Raten"
EMOJI = "🎨"
ROUNDS = (1, 2, 3)
TIMES = (60, 80, 120)
DEFAULTS = {"category": DEFAULT, "rounds": 2, "time": 80, "hints": True}
CHOICES = 3                  # words to choose from
CHOOSE = 10                  # seconds to choose, then one is taken at random
REVEAL = 3                   # seconds the word is shown to everybody after a turn
MIN_PLAYERS, MAX_PLAYERS = 2, 8
MAX_GUESS = 40
MAX_CHAT = 120               # chat lines kept per turn
MAX_POINTS = 30000           # points of the drawing per turn (protects the server)
MAX_BATCH_POINTS = 2000      # points per request
MAX_BATCH_OPS = 60
PALETTE = ("#000000", "#7a7a7a", "#e03131", "#f76707", "#fcc419", "#2f9e44", "#1c7ed6", "#7048e8", "#8b5a2b", "#f06595")
SIZES = (1, 2, 3)
POINTS_DRAWER = 10
ARTICLES = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "eines",
            "the", "a", "an", "le", "la", "les", "l", "un", "une"}


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def category(key: str | None) -> dict:
    return CATEGORIES.get(key or "") or CATEGORIES[DEFAULT]


def word_entry(cat: str, name: str) -> dict:
    return next((w for w in category(cat)["words"] if w["name"] == name), {"name": name, "aliases": []})


# ---------------------------------------------------------------- checking a guess
def variants(s: str) -> set[str]:
    """The ways a text is compared: no case, accents, articles, spaces, hyphens – umlauts both as «ae» and as «a»."""
    s = str(s or "").lower().replace("ß", "ss")
    out = set()
    for v in (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue"), s):
        v = "".join(c for c in unicodedata.normalize("NFKD", v) if not unicodedata.combining(c))
        w = re.sub(r"[^a-z0-9]+", " ", v).split()
        while len(w) > 1 and w[0] in ARTICLES:
            w = w[1:]
        out.add("".join(w))
    out.discard("")
    return out


def distance(a: str, b: str) -> int:
    """Levenshtein distance."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def check(guess: str, word: dict) -> str:
    """"right", "close" (one or two letters off – only the guesser hears it), "hidden" (contains the word – not shown
    to the others) or "wrong"."""
    g = variants(guess)
    if not g:
        return "wrong"
    best = None
    contains = False
    for name in [word["name"], *word.get("aliases", [])]:
        for a in variants(name):
            for x in g:
                d = distance(x, a) if abs(len(x) - len(a)) <= 2 else 3
                if d == 0 or (d <= 1 and len(a) >= 5):
                    return "right"
                close = d <= (2 if len(a) >= 4 else 1)
                if close and (best is None or d < best):
                    best = d
                if len(a) >= 3 and a in x:
                    contains = True
    if best is not None:
        return "close"
    return "hidden" if contains else "wrong"


def letters_of(word: str) -> list[int]:
    """The positions of the letters (no spaces / hyphens)."""
    return [i for i, c in enumerate(word) if c.isalnum()]


def clean_points(p) -> list[float]:
    """A flat list x, y, x, y … in 0–1, three decimals; anything else is dropped."""
    if not isinstance(p, list):
        return []
    out: list[float] = []
    for v in p[: MAX_BATCH_POINTS * 2]:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            return out[: len(out) - len(out) % 2]
        out.append(round(min(1.0, max(0.0, float(v))), 3))
    return out[: len(out) - len(out) % 2]


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

    def guessers(self) -> list[str]:
        return [p for p in self.order() if p != self.st.get("drawer")]

    def n_turns(self) -> int:
        return int(self.r.get("rounds") or 1) * len(self.order())

    def word(self) -> dict | None:
        w = self.st.get("word")
        return word_entry(self.r.get("category"), w) if w else None

    # ---------- the game
    def begin(self) -> None:
        self.st.update(turn=-1, totals={p: 0 for p in self.order()}, log=[], used=[], ranking=None, places=None, seq=0)
        self._next_turn()

    def _choices(self) -> list[str]:
        words = [w["name"] for w in category(self.r.get("category"))["words"]]
        used = set(self.st.get("used") or [])
        pool = [w for w in words if w not in used]
        if len(pool) < CHOICES:                                 # all used: start again
            self.st["used"] = []
            pool = words
        return self.rng.sample(pool, min(CHOICES, len(pool)))

    def _next_turn(self, at: float | None = None) -> None:
        t = self.st["turn"] + 1
        if t >= self.n_turns():
            self._finish()
            return
        order = self.order()
        now = self.now() if at is None else at
        self.st.update(turn=t, drawer=order[t % len(order)], phase="choose", choices=self._choices(), word=None,
                       choose_until=now + CHOOSE, started=None, deadline=None, reveal_until=None,
                       strokes=[], npts=0, found=[], turn_pts={}, hint_order=[], chat=[], skipped=False)

    def round(self) -> int:
        return max(0, self.st.get("turn", 0)) // max(1, len(self.order())) + 1

    def choose(self, pid: str, idx: int) -> None:
        if self.st.get("phase") != "choose":
            raise CommunityError("The word is chosen already")
        if pid != self.st.get("drawer"):
            raise CommunityError("It is not your turn to draw")
        try:
            word = self.st["choices"][int(idx)]
        except (TypeError, ValueError, IndexError):
            raise CommunityError("Unknown word") from None
        self._start_draw(word)

    def _start_draw(self, word: str, at: float | None = None) -> None:
        now = self.now() if at is None else at
        pos = letters_of(word)
        self.st["used"].append(word)
        self.st.update(word=word, phase="draw", started=now, deadline=now + int(self.r.get("time") or 80),
                       choices=[], hint_order=self.rng.sample(pos, len(pos)))

    # ---------- the hints and the mask
    def revealed(self) -> list[int]:
        """The letter positions shown to the guessers now: at 50 % and 75 % of the time, at most a third of the letters."""
        if not self.r.get("hints") or self.st.get("phase") != "draw" or not self.st.get("word"):
            return []
        total = len(letters_of(self.st["word"])) // 3
        span = max(1, self.st["deadline"] - self.st["started"])
        frac = (self.now() - self.st["started"]) / span
        k = total if frac >= 0.75 else (total + 1) // 2 if frac >= 0.5 else 0
        return sorted(self.st["hint_order"][:k])

    def mask(self) -> list[str]:
        """The word for the guessers: "_" per hidden letter, the hint letters, spaces and hyphens as they are."""
        w = self.st.get("word") or ""
        shown = set(self.revealed())
        return [c if (not c.isalnum() or i in shown) else "_" for i, c in enumerate(w)]

    # ---------- guessing
    def _check_player(self, pid: str) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")

    def _chat(self, entry: dict) -> None:
        self.st["seq"] = self.st.get("seq", 0) + 1
        chat = self.st.setdefault("chat", [])
        chat.append({"id": self.st["seq"], "t": self.now(), **entry})
        if len(chat) > MAX_CHAT:
            del chat[: len(chat) - MAX_CHAT]

    def guess(self, pid: str, text: str) -> str:
        self._check_player(pid)
        if self.st.get("phase") != "draw":
            raise CommunityError("Nothing to guess right now")
        if pid == self.st.get("drawer"):
            raise CommunityError("You are drawing")
        if pid in self.st["found"]:
            raise CommunityError("You found it already")
        text = " ".join(str(text or "").split())[:MAX_GUESS]
        if not variants(text):
            raise CommunityError("Type a guess")
        res = check(text, self.word())
        if res == "right":
            k = len(self.st["found"])
            span = max(1, self.st["deadline"] - self.st["started"])
            frac = max(0.0, min(1.0, (self.st["deadline"] - self.now()) / span))
            pts = max(10, round((50 + 50 * frac) * max(0.5, 1 - 0.1 * k)))
            drawer = self.st["drawer"]
            self.st["found"].append(pid)
            tp = self.st["turn_pts"]
            tp[pid] = pts
            tp[drawer] = tp.get(drawer, 0) + POINTS_DRAWER
            self.st["totals"][pid] = self.st["totals"].get(pid, 0) + pts
            self.st["totals"][drawer] = self.st["totals"].get(drawer, 0) + POINTS_DRAWER
            self._chat({"k": "found", "p": pid, "pts": pts})
            if all(p in self.st["found"] for p in self.guessers()):
                self._close_turn()
        elif res in ("close", "hidden"):
            self._chat({"k": "close" if res == "close" else "mine", "p": pid, "to": pid, "text": text})
        else:
            self._chat({"k": "guess", "p": pid, "text": text})
        return res

    # ---------- drawing
    def draw(self, pid: str, ops: list, turn: int | None = None) -> dict:
        """A batch of the drawer: {"c": colour, "w": size, "p": [x, y, …], "e": eraser} starts a stroke, {"p": […]}
        continues the last one, {"u": 1} undoes the last stroke, {"x": 1} clears the picture."""
        self._check_player(pid)
        if self.st.get("phase") != "draw" or pid != self.st.get("drawer") or (turn is not None and int(turn) != self.st["turn"]):
            raise CommunityError("It is not your turn to draw")
        ev = self.st["strokes"]
        full = False
        for op in (ops or [])[:MAX_BATCH_OPS]:
            if not isinstance(op, dict):
                continue
            if op.get("u"):
                ev.append({"u": 1})
                continue
            if op.get("x"):
                ev.append({"x": 1})
                continue
            pts = clean_points(op.get("p"))
            room = (MAX_POINTS - self.st["npts"]) * 2
            if len(pts) > room:
                pts, full = pts[:max(0, room)], True
            if "c" in op or "w" in op or "e" in op:
                c = op.get("c") if op.get("c") in PALETTE else PALETTE[0]
                w = op.get("w") if op.get("w") in SIZES else 2
                if not pts:
                    continue
                s = {"c": c, "w": w, "p": pts}
                if op.get("e"):
                    s["e"] = 1
                ev.append(s)
            elif pts and ev and "p" in ev[-1]:
                ev[-1]["p"].extend(pts)
            else:
                continue
            self.st["npts"] += len(pts) // 2
        return {"n": len(ev), "npts": self.st["npts"], "full": full or self.st["npts"] >= MAX_POINTS}

    def strokes_since(self, n: int, pl: int = 0, turn: int | None = None) -> dict:
        """What a guesser does not have yet: the cursor is the number of events they have (n) and the length of the
        point list of their last event (pl). "cont": the first event continues their last one."""
        ev = self.st.get("strokes") or []
        out = {"turn": self.st.get("turn"), "n": len(ev)}
        if (turn is not None and turn != self.st.get("turn")) or n <= 0 or n > len(ev):
            return {**out, "from": 0, "cont": False, "ev": ev}
        last = ev[n - 1]
        if "p" in last:
            if pl > len(last["p"]) or pl < 0:
                return {**out, "from": 0, "cont": False, "ev": ev}
            return {**out, "from": n - 1, "cont": True, "ev": [{"p": last["p"][pl:]}] + ev[n:]}
        return {**out, "from": n, "cont": False, "ev": ev[n:]}

    # ---------- the turn ends, the clock
    def _close_turn(self, skipped: bool = False, at: float | None = None) -> None:
        self.st["log"].append({"n": self.st["turn"], "drawer": self.st["drawer"], "word": self.st["word"],
                               "found": list(self.st["found"]), "points": dict(self.st["turn_pts"]), "skipped": skipped})
        self.st.update(phase="reveal", reveal_until=(self.now() if at is None else at) + REVEAL, skipped=skipped)

    def tick(self) -> bool:
        """The choice times out (a random word), the time is up (the word is shown), the next drawer comes – each step
        at the time it was due, so one call catches up a long pause."""
        changed = False
        for _ in range(3 * 64):
            ph, now = self.st.get("phase"), self.now()
            if ph == "choose" and now >= self.st.get("choose_until", 0):
                self._start_draw(self.rng.choice(self.st["choices"]), self.st["choose_until"])
            elif ph == "draw" and now >= self.st.get("deadline", 0):
                self._close_turn(at=self.st["deadline"])
            elif ph == "reveal" and now >= self.st.get("reveal_until", 0):
                self._next_turn(self.st["reveal_until"])
            else:
                break
            changed = True
        return changed

    def skip(self) -> None:
        """Who leads skips the turn: the word is shown (the points so far stay), or – while choosing – the next drawer."""
        ph = self.st.get("phase")
        if ph == "choose" or ph == "reveal":
            self._next_turn()
        elif ph == "draw":
            self._close_turn(skipped=True)
        else:
            raise CommunityError("The game is not running")

    # ---------- the end
    def _finish(self) -> None:
        order, tot = self.order(), self.st.get("totals") or {}
        self.st["places"] = places(order, tot) if self.st.get("log") else {}
        self.st["ranking"] = sorted(order, key=lambda p: (-tot.get(p, 0), order.index(p)))
        self.st.update(phase="done", finished=self.now(), choices=[])

    def end(self) -> None:
        """Who leads ends the game: a drawing in progress counts as it stands."""
        ph = self.st.get("phase")
        if ph == "draw":
            self._close_turn()
        if ph in ("choose", "draw", "reveal"):
            self._finish()


# ================================================================ the games in the database (table card_game, kind "zeichnen")
class Zeichnen(CardGames):
    """The family table – the same rows and lobby as the card games (join, summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng: random.Random | None = None):
        super().__init__(db, add_history)
        self.rewards = rewards
        self.now = now
        self.rng = rng

    def table(self, st: dict) -> Table:
        return Table(st, self.rng, now=lambda: self.now())

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, self.db.get_setting(f"game_rules.{KIND}") or {})

    def clean_rules(self, kind: str, r: dict) -> dict:
        r = {**DEFAULTS, **(r or {})}
        c = str(r.get("category") or DEFAULT)
        try:
            rounds = int(r.get("rounds"))
        except (TypeError, ValueError):
            rounds = DEFAULTS["rounds"]
        try:
            t = int(r.get("time"))
        except (TypeError, ValueError):
            t = DEFAULTS["time"]
        return {"category": c if c in CATEGORIES else DEFAULT, "rounds": rounds if rounds in ROUNDS else DEFAULTS["rounds"],
                "time": t if t in TIMES else DEFAULTS["time"], "hints": bool(r.get("hints"))}

    def rules_info(self) -> dict:
        """The remembered rules, the categories, the choices and the coins for places 1–3 (for the start dialog)."""
        return {**self.default_rules(), "rewards": rewards_of(self.db),
                "categories": [{"key": k, "title": c["title"], "emoji": c["emoji"], "count": len(c["words"])} for k, c in CATEGORIES.items()],
                "rounds_choice": list(ROUNDS), "times": list(TIMES), "palette": list(PALETTE)}

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st, separators=(",", ":")), status, status, row["id"])
        if status != "done" or st.get("paid"):
            return
        # the end: coins for places 1–3 (once), the history – only when at least one turn was played
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st, separators=(",", ":")), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", f"{TITLE} – Platz {st['places'][pid]}", ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history and st.get("log"):
            cat = category(st["rules"].get("category"))
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                found = sum(1 for e in st["log"] if p["id"] in e["found"])
                drawn = [e["word"] for e in st["log"] if e["drawer"] == p["id"]]
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": (st.get("places") or {}).get(p["id"]), "players": len(st["players"]),
                        "points": (st.get("totals") or {}).get(p["id"], 0), "turns": len(st["log"]), "found": found,
                        "drawn": drawn, "category": cat["title"], "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins per player: places 1–3, only people of the family, only with at least two of them at the table,
        at least one turn played and at least one point scored."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if st.get("solo") or len(people) < 2 or st.get("phase") != "done" or not st.get("log"):
            return {}
        if not any((st.get("totals") or {}).values()):           # nobody scored (started and ended at once): nothing to win
            return {}
        amounts = rewards_of(self.db)
        pl = st.get("places") or {}
        out = {}
        for p in people:
            n = pl.get(p["id"])
            if n and 1 <= n <= 3 and amounts[n - 1] > 0:
                out[p["id"]] = amounts[n - 1]
        return out

    # ---------- the table
    def start(self, kind: str, host: int, rules: dict | None = None, solo: bool = False, bots: list[dict] | None = None) -> int:
        if kind != KIND:
            raise CommunityError("Unknown game")
        if solo:
            raise CommunityError("This game needs at least two people")
        r = self.clean_rules(KIND, {**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
        with self.lock:
            if self._row(KIND):
                raise CommunityError("This game is already running")
            self.db.set_setting(f"game_rules.{KIND}", r)
            st = {"kind": KIND, "rules": r, "players": [self._person(host)], "phase": "lobby", "solo": False}
            return self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, 0, json.dumps(st))

    def begin(self, kind: str, viewer: int, starter=None) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) < MIN_PLAYERS:
                raise CommunityError("Wait for a second player")
            apply_starter(st, starter_mode(self.db), starter, leader=row["host_id"])     # who begins (Settings › Games)
            self.table(st).begin()
            self._save(row, st)

    def _act(self, pid: int, fn):
        with self.lock:
            row = self._row(KIND, pid)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            t = self.table(st)
            t.tick()
            try:
                out = fn(t)
            finally:
                self._save(row, st)
            return out

    def choose(self, pid: int, idx: int) -> None:
        self._act(pid, lambda t: t.choose(str(pid), idx))

    def draw(self, pid: int, ops: list, turn: int | None = None) -> dict:
        return self._act(pid, lambda t: t.draw(str(pid), ops, turn))

    def guess(self, pid: int, text: str) -> str:
        return self._act(pid, lambda t: t.guess(str(pid), text))

    def skip(self, pid: int) -> None:
        self._act(pid, lambda t: t.skip())

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: the turns so far count (coins only when at least one turn was played)."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] in ("choose", "draw", "reveal"):
                t = self.table(st)
                t.tick()
                t.end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int, n: int | None = None, pl: int = 0, turn: int | None = None) -> dict | None:
        """The view of one player; with a cursor (n, pl, turn) the strokes they do not have yet."""
        with self.lock:
            row = self._row(KIND, viewer)
            if row:
                st = json.loads(row["state"])
                if st["phase"] != "lobby" and self.table(st).tick():
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
            else:
                row = self.db.q1("""SELECT * FROM card_game WHERE kind=? AND status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                    AND solo=0 ORDER BY id DESC LIMIT 1""", KIND)
                if not row:
                    return None
                st = json.loads(row["state"])
                if not any(p["id"] == str(viewer) for p in st["players"]):
                    return None
        return self._view(row, st, str(viewer), n, pl, turn)

    def _view(self, row, st: dict, me: str, n: int | None = None, pl: int = 0, turn: int | None = None) -> dict:
        """What one player sees – the word only when they draw, found it, or the turn is over."""
        t = self.table(st)
        ph = st["phase"]
        if (ph == "done" or row["status"] == "done") and ph != "lobby":
            ph = "done"
        now = self.now()
        cat = category(st["rules"].get("category"))
        coins, totals = st.get("coins") or {}, st.get("totals") or {}
        found = (st.get("found") or []) if ph in ("draw", "reveal") else []
        playing = ph in ("choose", "draw", "reveal")
        drawer = st.get("drawer") if playing else None
        tp = st.get("turn_pts") or {}
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "guest": bool(p.get("guest")),
                    "total": totals.get(p["id"], 0), "place": (st.get("places") or {}).get(p["id"]), "coins": coins.get(p["id"], 0),
                    "drawer": p["id"] == drawer, "found": p["id"] in found, "turn_pts": tp.get(p["id"], 0) if playing else 0}
                   for p in st["players"]]
        joined = any(p["id"] == me for p in st["players"])
        sees = ph in ("reveal", "done") or (ph == "draw" and (me == drawer or me in found))
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        out = {"game": row["id"], "starter": st.get("starter"), "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph, "solo": False,
               "host": row["host_id"], "rules": st["rules"],
               "category": {"key": st["rules"].get("category"), "title": cat["title"], "emoji": cat["emoji"]},
               "players": players, "joined": joined, "turn": st.get("turn", -1) if ph != "lobby" else None,
               "turns": t.n_turns(), "round": t.round() if ph != "lobby" else 0, "rounds": st["rules"].get("rounds"),
               "drawer": drawer, "me_drawer": bool(drawer) and drawer == me, "found_me": me in found,
               "choices": list(st.get("choices") or []) if ph == "choose" and me == drawer else None,
               "word": st.get("word") if sees else None,
               "mask": t.mask() if ph == "draw" else None, "left_ms": None, "time_ms": None,
               "chat": [], "ranking": st.get("ranking"), "rewards": rewards_of(self.db), "coins_on": people >= 2,
               "palette": list(PALETTE), "max_points": MAX_POINTS, "npts": st.get("npts", 0) if ph == "draw" else 0,
               "last": (st.get("log") or [None])[-1] if ph in ("reveal", "done") else None,
               "log": [{"n": e["n"], "drawer": e["drawer"], "word": e["word"], "found": len(e["found"])} for e in st.get("log") or []]
               if ph == "done" else None}
        if ph == "choose":
            out["left_ms"] = max(0, int((st.get("choose_until", now) - now) * 1000))
            out["time_ms"] = CHOOSE * 1000
        elif ph == "draw":
            out["left_ms"] = max(0, int((st["deadline"] - now) * 1000))
            out["time_ms"] = int((st["deadline"] - st["started"]) * 1000)
        elif ph == "reveal":
            out["left_ms"] = max(0, int((st.get("reveal_until", now) - now) * 1000))
            out["skipped"] = bool(st.get("skipped"))
        if ph in ("draw", "reveal"):
            out["chat"] = [{k: v for k, v in c.items() if k not in ("to", "t")} for c in st.get("chat") or []
                           if c.get("to") in (None, me)][-40:]
            if n is not None and n >= 0:
                out["strokes"] = t.strokes_since(n, pl, turn)
        return out

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
