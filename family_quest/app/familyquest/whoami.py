"""«Wer bin ich?» – a live guessing game for the family: everybody on their own device, like Paarjagd (pairhunt.py).

The tables live in the `card_game` table with kind "werbinich" (no own table); lobby, join, end and summary come from
cardgames.CardGames. Only people play (family and guests via QR code) – no bots: they cannot ask or answer questions.

Rules:
  Who opens the table chooses a category (whoami_data.py). At the start every player gets a different character of it
  at random. Everybody sees the characters of all the others – but not their own (the server never sends it while it
  is hidden). It goes round in seat order (players who are finished are skipped). Whose turn it is can
  - ask a yes/no question (typed or said aloud): the others answer yes / no / don't know. When all of them answered
    (finished players answer too – they know), the question closes; the asker or who leads may close it earlier once
    there is an answer. A majority of «yes»: the asker asks again; otherwise the turn passes.
  - guess: «I am …» – checked against the name and its aliases (no case, accents, articles, punctuation; a small typo
    is fine). Right: the player is finished and gets the next place. Wrong: the turn passes.
  - give up (any time): the own character is shown; finished without a place.
  The game ends when everybody is finished, or when who leads ends it (then everything is shown; who has not found
  their character gets no place).
Coins (setting `game_rewards["werbinich"]`): places 1–3 – only at a table with at least two people of the family,
never for guests. Paid once (flag `paid` in the state, a unique `ref` per player in the ledger).
"""
from __future__ import annotations

import json
import random
import re
import time
import unicodedata

from .cardgames import CardGames
from .community import CommunityError
from .pairhunt import rewards_of as _rewards_of
from .whoami_data import CATEGORIES, DEFAULT

KIND = "werbinich"
TITLE = "Wer bin ich?"
EMOJI = "🎭"
VOTES = ("yes", "no", "unknown")
MAX_TEXT = 140
FILLERS = {"ich", "bin", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einen", "eines",
           "the", "a", "an", "le", "la", "les", "l", "un", "une"}


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


# ---------------------------------------------------------------- checking a guess
def norm(s: str) -> str:
    """Lower case, no accents (ä → a), no punctuation, no articles / «ich bin», no spaces."""
    s = str(s or "").lower().replace("ß", "ss")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    words = re.sub(r"[^a-z0-9]+", " ", s).split()
    return "".join(w for w in words if w not in FILLERS)


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


def matches(guess: str, char: dict) -> bool:
    g = norm(guess)
    if not g:
        return False
    for name in [char["name"], *char.get("aliases", [])]:
        n = norm(name)
        if not n:
            continue
        tol = 2 if len(n) >= 9 else 1 if len(n) >= 5 else 0
        if g == n or (tol and abs(len(g) - len(n)) <= tol and distance(g, n) <= tol):
            return True
    return False


def category(key: str) -> dict:
    return CATEGORIES.get(key) or CATEGORIES[DEFAULT]


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    def chars(self) -> list[dict]:
        return category(self.st["rules"].get("category"))["chars"]

    def char_of(self, pid: str) -> dict | None:
        i = (self.st.get("chars") or {}).get(pid)
        return self.chars()[i] if i is not None else None

    def deal(self) -> None:
        order = self.order()
        if len(order) > len(self.chars()):
            raise CommunityError("Too many players for this category")
        picks = self.rng.sample(range(len(self.chars())), len(order))
        self.st.update(chars=dict(zip(order, picks)), turn=order[0], question=None, log=[], done={}, found=[],
                       phase="play", ranking=None, places=None, last=None, qn=0)
        self.st["turn_at"] = self.now()

    # ---------- helpers
    def finished(self, pid: str) -> bool:
        return pid in self.st["done"]

    def _check_player(self, pid: str) -> None:
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        if pid not in self.order():
            raise CommunityError("You are not at this table")

    def _check_turn(self, pid: str) -> None:
        self._check_player(pid)
        if self.st.get("turn") != pid:
            raise CommunityError("It is not your turn")

    def voters(self) -> list[str]:
        """Who answers the open question: everybody except the asker (finished players too – they know)."""
        q = self.st.get("question")
        return [p for p in self.order() if q and p != q["asker"]]

    def _next(self, pid: str) -> str | None:
        order = self.order()
        i = order.index(pid)
        for k in range(1, len(order) + 1):
            p = order[(i + k) % len(order)]
            if not self.finished(p):
                return p
        return None

    def _pass(self, pid: str) -> None:
        """The turn goes to the next player who is still guessing (or the game ends)."""
        nxt = self._next(pid)
        if nxt is None:
            self._finish()
            return
        self.st["turn"] = nxt
        self.st["turn_at"] = self.now()

    # ---------- questions
    def ask(self, pid: str, text: str = "") -> None:
        self._check_turn(pid)
        if self.st.get("question"):
            raise CommunityError("A question is already open")
        self.st["qn"] = self.st.get("qn", 0) + 1
        self.st["question"] = {"n": self.st["qn"], "asker": pid, "text": " ".join(str(text or "").split())[:MAX_TEXT],
                               "votes": {}, "t": self.now()}

    def answer(self, pid: str, vote: str) -> None:
        self._check_player(pid)
        q = self.st.get("question")
        if not q:
            raise CommunityError("There is no open question")
        if pid == q["asker"]:
            raise CommunityError("You cannot answer your own question")
        if vote not in VOTES:
            raise CommunityError("Answer yes, no or don't know")
        q["votes"][pid] = vote
        if all(p in q["votes"] for p in self.voters()):
            self._close()

    def close(self, pid: str, lead: bool = False) -> None:
        if lead:                                              # who leads may close it without playing
            if self.st.get("phase") != "play":
                raise CommunityError("The game is not running")
        else:
            self._check_player(pid)
        q = self.st.get("question")
        if not q:
            raise CommunityError("There is no open question")
        if pid != q["asker"] and not lead:
            raise CommunityError("Only who asked can close the question")
        if not q["votes"]:
            raise CommunityError("Wait for at least one answer")
        self._close()

    def _close(self) -> None:
        q = self.st["question"]
        n = {v: sum(1 for x in q["votes"].values() if x == v) for v in VOTES}
        total = sum(n.values())
        result = "yes" if n["yes"] * 2 > total else "no" if n["no"] * 2 > total else "unknown"
        entry = {"n": q["n"], "asker": q["asker"], "text": q["text"], **n, "result": result, "t": self.now()}
        self.st["log"].append(entry)
        self.st["question"] = None
        self.st["last"] = {"type": "answer", "player": q["asker"], "result": result, "t": self.now()}
        if result == "yes":                                   # a majority of yes: the same player asks again
            self.st["turn_at"] = self.now()
        else:
            self._pass(q["asker"])

    # ---------- guessing, giving up
    def guess(self, pid: str, text: str) -> bool:
        self._check_turn(pid)
        if self.st.get("question"):
            raise CommunityError("Close the question first")
        text = " ".join(str(text or "").split())[:MAX_TEXT]
        if not norm(text):
            raise CommunityError("Type who you are")
        ok = matches(text, self.char_of(pid))
        self.st["last"] = {"type": "guess", "player": pid, "text": text, "ok": ok, "t": self.now()}
        if ok:
            self.st["found"].append(pid)
            self.st["done"][pid] = {"how": "found", "place": len(self.st["found"]), "t": self.now()}
            self.st["last"]["char"] = self.char_of(pid)["name"]
        self._pass(pid)
        return ok

    def give_up(self, pid: str) -> None:
        self._check_player(pid)
        if self.finished(pid):
            raise CommunityError("You are finished already")
        self.st["done"][pid] = {"how": "gave_up", "t": self.now()}
        self.st["last"] = {"type": "give_up", "player": pid, "char": self.char_of(pid)["name"], "t": self.now()}
        q = self.st.get("question")
        if q and q["asker"] == pid:
            self.st["question"] = None
        if self.st.get("turn") == pid:
            self._pass(pid)
        elif all(self.finished(p) for p in self.order()):
            self._finish()

    def skip(self) -> None:
        """Who leads passes the turn on (e.g. somebody left): an open question is dropped."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        self.st["question"] = None
        self.st["last"] = {"type": "skip", "player": self.st["turn"], "t": self.now()}
        self._pass(self.st["turn"])

    def _finish(self) -> None:
        """The end: places for who found their character (in finishing order); the others none."""
        order, done = self.order(), self.st["done"]
        self.st["phase"] = "done"
        self.st["question"] = None
        self.st["places"] = {p: done[p]["place"] for p in order if (done.get(p) or {}).get("how") == "found"}
        rest = [p for p in order if p not in self.st["places"]]
        gave_up = [p for p in rest if p in done]
        self.st["ranking"] = sorted(self.st["places"], key=self.st["places"].get) + gave_up + [p for p in rest if p not in done]
        self.st["finished"] = self.now()

    def end(self) -> None:
        if self.st.get("phase") == "play":
            self._finish()

    def tick(self) -> bool:
        return False


# ================================================================ the games in the database (table card_game, kind "werbinich")
class Whoami(CardGames):
    """The family table – the same rows and lobby as the card games (join, summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None):
        super().__init__(db, add_history)
        self.rewards = rewards

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, self.db.get_setting(f"game_rules.{KIND}") or {})

    def clean_rules(self, kind: str, r: dict) -> dict:
        c = str((r or {}).get("category") or DEFAULT)
        return {"category": c if c in CATEGORIES else DEFAULT}

    def rules_info(self) -> dict:
        """The remembered category, all categories and the coins for places 1–3 (for the start dialog)."""
        return {**self.default_rules(), "rewards": rewards_of(self.db),
                "categories": [{"key": k, "title": c["title"], "emoji": c["emoji"], "count": len(c["chars"])} for k, c in CATEGORIES.items()]}

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
        if status != "done" or st.get("paid") or not st.get("chars"):
            return
        # the end: coins for places 1–3 (once), the history
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", f"{TITLE} – Platz {st['places'][pid]}", ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history:
            t = Table(st)
            cat = category(st["rules"].get("category"))
            asked = {}
            for e in st.get("log") or []:
                asked[e["asker"]] = asked.get(e["asker"], 0) + 1
            for p in st["players"]:
                if p.get("bot"):
                    continue
                how = (st["done"].get(p["id"]) or {}).get("how")
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": (st.get("places") or {}).get(p["id"]), "players": len(st["players"]),
                        "char": t.char_of(p["id"])["name"], "category": cat["title"], "found": how == "found",
                        "found_count": len(st.get("found") or []), "questions": asked.get(p["id"], 0), "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins per player: places 1–3, only people of the family, only with at least two of them at the table."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if st.get("solo") or len(people) < 2 or st.get("phase") != "done":
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
        with self.lock:
            if self._row(KIND):
                raise CommunityError("This game is already running")
            r = self.clean_rules(KIND, {**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
            self.db.set_setting(f"game_rules.{KIND}", r)
            st = {"kind": KIND, "rules": r, "players": [self._person(host)], "phase": "lobby", "solo": False}
            return self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, 0, json.dumps(st))

    def begin(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) < 2:
                raise CommunityError("Wait for a second player")
            Table(st).deal()
            self._save(row, st)

    def _act(self, pid: int, fn):
        with self.lock:
            row = self._row(KIND, pid)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            out = fn(Table(st))
            self._save(row, st)
            return out

    def ask(self, pid: int, text: str = "") -> None:
        self._act(pid, lambda t: t.ask(str(pid), text))

    def answer(self, pid: int, vote: str) -> None:
        self._act(pid, lambda t: t.answer(str(pid), vote))

    def close(self, pid: int, lead: bool = False) -> None:
        self._act(pid, lambda t: t.close(str(pid), lead))

    def guess(self, pid: int, text: str) -> bool:
        return self._act(pid, lambda t: t.guess(str(pid), text))

    def give_up(self, pid: int) -> None:
        self._act(pid, lambda t: t.give_up(str(pid)))

    def skip(self, pid: int) -> None:
        self._act(pid, lambda t: t.skip())

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: everything is shown, places only for who found their character (coins for them)."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] == "play":
                Table(st).end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int) -> dict | None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                row = self.db.q1("""SELECT * FROM card_game WHERE kind=? AND status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                    AND solo=0 ORDER BY id DESC LIMIT 1""", KIND)
            if not row:
                return None
            st = json.loads(row["state"])
            if row["status"] == "done" and not any(p["id"] == str(viewer) for p in st["players"]):
                return None
        return self._view(row, st, str(viewer))

    def _view(self, row, st: dict, me: str) -> dict:
        """What one player sees: every character except their own while it is hidden."""
        t = Table(st)
        cat = category(st["rules"].get("category"))
        done, coins = st.get("done") or {}, st.get("coins") or {}
        over = st["phase"] == "done" or row["status"] == "done"
        asked: dict[str, int] = {}
        for e in st.get("log") or []:
            asked[e["asker"]] = asked.get(e["asker"], 0) + 1
        players = []
        for p in st["players"]:
            c = t.char_of(p["id"]) if st.get("chars") else None
            shown = c is not None and (p["id"] != me or over or p["id"] in done)
            d = done.get(p["id"]) or {}
            players.append({"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "guest": bool(p.get("guest")),
                            "char": c["name"] if shown else None, "hidden": c is not None and not shown,
                            "status": d.get("how") or "playing", "place": (st.get("places") or {}).get(p["id"]) or d.get("place"),
                            "questions": asked.get(p["id"], 0), "coins": coins.get(p["id"], 0)})
        q = st.get("question")
        question = None
        if q:
            votes = q["votes"]
            question = {"n": q["n"], "asker": q["asker"], "text": q["text"], "votes": dict(votes),
                        **{v: sum(1 for x in votes.values() if x == v) for v in VOTES},
                        "need": len(t.voters()), "mine": votes.get(me)}
        log = st.get("log") or []
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        playing = st["phase"] == "play" and row["status"] != "done"
        return {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": "done" if over and st["phase"] != "lobby" else st["phase"],
                "solo": False, "host": row["host_id"], "rules": st["rules"],
                "category": {"key": st["rules"].get("category"), "title": cat["title"], "emoji": cat["emoji"]},
                "players": players, "joined": any(p["id"] == me for p in st["players"]),
                "turn": st.get("turn") if playing else None, "my_turn": playing and st.get("turn") == me and not q,
                "question": question, "last_q": log[-1] if log else None,
                "my_log": [e for e in log if e["asker"] == me][-30:],
                "last": st.get("last"), "ranking": st.get("ranking"), "finished_me": me in done,
                "rewards": rewards_of(self.db), "coins_on": people >= 2}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
