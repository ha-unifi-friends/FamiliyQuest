"""«Stadt-Land-Fluss» – the classic word game, live for the family: everybody writes on their own device.

The tables live in the `card_game` table with kind "stadtland" (no own table); lobby, join, end and summary come from
cardgames.CardGames, like «Wer bin ich?» (whoami.py). Only people play (family and guests via QR code) – no bots.

Rules (chosen by who opens the table, remembered):
  categories   3 to 8: built-in ones (CATS, the default: Stadt, Land, Fluss, Tier, Name, Beruf) plus up to 2 own ones
  rounds       3, 5, 8 or 10
  time         60, 90, 120 or 180 seconds per round – or 0: until somebody calls «Stopp!»
  stopp        the first who has filled every field (each answer starting with the letter) may call «Stopp!» –
               the others get GRACE more seconds (always on with time 0)
  hard         also the difficult letters C, Q, X, Y (umlauts never; no letter twice in a game)
A round: a random letter (a short spin), everybody fills one field per category; the answers are saved while typing
(the server accepts them until LATE seconds after the end, so the last keystrokes arrive). Then the writing closes.
Review: answers must start with the letter (no matter capitals, accents, a leading article: «die Aare» → A,
«Écosse» → E, «Ägypten» → A); empty and wrong-letter answers score 0. Everybody sees all answers and may reject
(👎) the answers of the others; an answer is out when a strict majority of the OTHER players rejected it. Who leads
may decide an answer (valid / invalid) and that wins over the votes. The review closes when everybody pressed
«Done» or who leads goes on.
Points per category: the only valid answer 20, a valid answer nobody else gave 10, the same valid answer as somebody
else 5 (same normalised text), invalid / empty 0. Totals over all rounds → ranking (a tie shares the place).
Who leads may end the game any time: the rounds so far count (a round in its review is scored as it stands, a round
still being written is dropped).
Coins (setting `game_rewards["stadtland"]`): places 1–3 – only people of the family, only with at least two of them,
only when at least one round was played; paid once (flag `paid`, a unique ledger `ref` per player).
The view never shows the other players' answers while a round is being written.
"""
from __future__ import annotations

import json
import random
import re
import time
import unicodedata

from .cardgames import CardGames
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .running import win_reason

KIND = "stadtland"
TITLE = "Stadt-Land-Fluss"
EMOJI = "🏙️"
# built-in categories: key → (German title – content of the history –, emoji); the app shows them translated
CATS = {
    "stadt": ("Stadt", "🏙️"), "land": ("Land", "🗺️"), "fluss": ("Fluss", "🌊"), "tier": ("Tier", "🐾"),
    "name": ("Name", "🙂"), "beruf": ("Beruf", "🧑‍🔧"), "pflanze": ("Pflanze", "🌱"), "essen": ("Essen", "🍝"),
    "gegenstand": ("Gegenstand", "🧸"), "sport": ("Sportart", "⚽"), "ort": ("Schweizer Ort", "🇨🇭"),
    "farbe": ("Farbe", "🎨"), "instrument": ("Musikinstrument", "🎸"), "koerper": ("Körperteil", "🦵"),
    "spielzeug": ("Spielzeug", "🪀"), "getraenk": ("Getränk", "🥤"),
}
DEFAULT_CATS = ["stadt", "land", "fluss", "tier", "name", "beruf"]
ROUNDS = (3, 5, 8, 10)
TIMES = (60, 90, 120, 180, 0)              # 0: until somebody calls «Stopp!»
DEFAULTS = {"cats": DEFAULT_CATS, "own": [], "rounds": 5, "time": 90, "stopp": True, "hard": False}
EASY = "ABDEFGHIJKLMNOPRSTUVWZ"            # A–Z without C, Q, X, Y
HARD = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MIN_CATS, MAX_CATS, MAX_OWN = 3, 8, 2
MAX_ANSWER = 40
MAX_OWN_LEN = 24
SPIN = 2.5                                  # seconds of the letter spin at the start of a round (part of the time)
GRACE = 10                                  # seconds for the others after «Stopp!»
LATE = 2                                    # answers saved this long after the end still count (network)
ARTICLES = {"der", "die", "das", "den", "dem", "des", "le", "la", "les", "l", "il", "lo", "the", "el"}
POINTS_ONLY, POINTS_UNIQUE, POINTS_SAME = 20, 10, 5


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


# ---------------------------------------------------------------- checking an answer
def _plain(s: str) -> str:
    """Lower case, no accents (ä → a, é → e), ß → ss."""
    s = str(s or "").lower().replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def words(s: str) -> list[str]:
    """The words of an answer without a leading article («die Aare» → ["aare"], «l'Écosse» → ["ecosse"])."""
    w = re.sub(r"[^a-z0-9]+", " ", _plain(s)).split()
    while len(w) > 1 and w[0] in ARTICLES:
        w = w[1:]
    return w


def norm(s: str) -> str:
    """The text two answers are compared by: no case, accents, article, spaces or punctuation."""
    return "".join(words(s))


def fits(text: str, letter: str) -> bool:
    """Does the answer start with the letter (Ä counts as A, É as E, a leading article is skipped)?"""
    n = norm(text)
    return bool(n) and n[0] == str(letter or "").lower()[:1]


def clean_text(s, n: int = MAX_ANSWER) -> str:
    return " ".join(str(s or "").split())[:n]


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

    def cat_keys(self) -> list[str]:
        return [c["key"] for c in self.st["cats"]]

    # ---------- the game
    def begin(self) -> None:
        own = [{"key": f"own{i + 1}", "title": t, "own": True} for i, t in enumerate(self.r.get("own") or [])]
        self.st.update(cats=[{"key": k, "title": CATS[k][0]} for k in self.r["cats"]] + own,
                       round=0, letters=[], totals={p: 0 for p in self.order()}, log=[], ranking=None, places=None)
        self._round()

    def letter_pool(self) -> list[str]:
        used = set(self.st.get("letters") or [])
        return [c for c in (HARD if self.r.get("hard") else EASY) if c not in used]

    def _round(self) -> None:
        pool = self.letter_pool()
        if not pool:                                          # cannot happen with ≤ 10 rounds – but never loop
            self._finish()
            return
        letter = self.rng.choice(pool)
        self.st["letters"].append(letter)
        now = self.now()
        t = int(self.r.get("time") or 0)
        self.st.update(round=self.st["round"] + 1, letter=letter, phase="write", started=now,
                       deadline=now + SPIN + t if t else None, stopp=None,
                       answers={p: {} for p in self.order()}, votes={}, override={}, ready=[])

    def _check_player(self, pid: str) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")

    def writing_open(self) -> bool:
        d = self.st.get("deadline")
        return self.st.get("phase") == "write" and (d is None or self.now() <= d + LATE)

    def save(self, pid: str, answers: dict) -> None:
        """Autosave while typing: the fields sent replace the saved ones (unknown categories are ignored)."""
        self._check_player(pid)
        if self.st.get("phase") != "write" or not self.writing_open():
            raise CommunityError("Time is up")
        mine = self.st["answers"].setdefault(pid, {})
        keys = self.cat_keys()
        for k, v in (answers or {}).items():
            if k in keys:
                mine[k] = clean_text(v)

    def complete(self, pid: str) -> bool:
        """Every field filled with an answer that starts with the letter."""
        a = self.st.get("answers", {}).get(pid) or {}
        return all(fits(a.get(k, ""), self.st["letter"]) for k in self.cat_keys())

    def filled(self, pid: str) -> int:
        a = self.st.get("answers", {}).get(pid) or {}
        return sum(1 for k in self.cat_keys() if (a.get(k) or "").strip())

    def stopp(self, pid: str) -> None:
        self._check_player(pid)
        if self.st.get("phase") != "write" or not self.writing_open():
            raise CommunityError("Time is up")
        if not self.r.get("stopp"):
            raise CommunityError("«Stopp» is switched off in this game")
        if self.st.get("stopp"):
            raise CommunityError("Somebody called «Stopp» already")
        if not self.complete(pid):
            raise CommunityError("Fill every field first")
        now = self.now()
        end = now + GRACE
        d = self.st.get("deadline")
        self.st["deadline"] = min(d, end) if d is not None else end
        self.st["stopp"] = {"by": pid, "t": now}

    def lead_next(self) -> None:
        """Who leads goes on: closes the writing (the clients still send their last letters), the review, or starts
        the next round after the scores."""
        ph = self.st.get("phase")
        if ph == "write":
            now = self.now()
            d = self.st.get("deadline")
            self.st["deadline"] = min(d, now) if d is not None else now
            self.st["closed_by_lead"] = True
        elif ph == "review":
            self._close_review()
        elif ph == "scores":
            self._round()
        else:
            raise CommunityError("The game is not running")

    def tick(self) -> bool:
        """The time is over (plus LATE for the last saves): the writing closes, the review opens."""
        d = self.st.get("deadline")
        if self.st.get("phase") == "write" and d is not None and self.now() > d + LATE:
            self.st.update(phase="review", votes={}, override={}, ready=[], review_at=self.now())
            return True
        return False

    # ---------- the review
    def _check_review(self) -> None:
        if self.st.get("phase") != "review":
            raise CommunityError("The answers are not being checked now")

    def _check_target(self, target: str, cat: str) -> None:
        if target not in self.order():
            raise CommunityError("Unknown player")
        if cat not in self.cat_keys():
            raise CommunityError("Unknown category")

    def vote(self, pid: str, target: str, cat: str, reject: bool = True) -> None:
        self._check_review()
        self._check_player(pid)
        self._check_target(target, cat)
        if pid == target:
            raise CommunityError("You cannot vote on your own answer")
        voters = self.st["votes"].setdefault(cat, {}).setdefault(target, [])
        if reject and pid not in voters:
            voters.append(pid)
        elif not reject and pid in voters:
            voters.remove(pid)

    def override(self, target: str, cat: str, valid: bool | None) -> None:
        """Who leads decides an answer (True / False) – None gives it back to the votes."""
        self._check_review()
        self._check_target(target, cat)
        ov = self.st["override"].setdefault(cat, {})
        if valid is None:
            ov.pop(target, None)
        else:
            ov[target] = bool(valid)

    def ready(self, pid: str, on: bool = True) -> None:
        self._check_review()
        self._check_player(pid)
        rd = self.st["ready"]
        if on and pid not in rd:
            rd.append(pid)
        elif not on and pid in rd:
            rd.remove(pid)
        if all(p in rd for p in self.order()):
            self._close_review()

    def judge(self) -> dict:
        """Per category and player: the answer, the automatic check, the votes, the decision and the points."""
        order, letter = self.order(), self.st.get("letter")
        others = len(order) - 1
        out: dict[str, dict] = {}
        for cat in self.cat_keys():
            row = {}
            for p in order:
                text = (self.st["answers"].get(p) or {}).get(cat, "") or ""
                auto = fits(text, letter)
                rej = [v for v in (self.st.get("votes") or {}).get(cat, {}).get(p, []) if v != p]
                ov = (self.st.get("override") or {}).get(cat, {}).get(p)
                if not text.strip():
                    valid = False
                elif ov is not None:
                    valid = ov
                else:
                    valid = auto and not (others > 0 and len(rej) * 2 > others)
                row[p] = {"text": text, "auto": auto, "rejects": rej, "override": ov, "valid": valid, "pts": 0}
            ok = [p for p in order if row[p]["valid"]]
            for p in ok:
                if len(ok) == 1:
                    row[p]["pts"] = POINTS_ONLY
                else:
                    same = sum(1 for q in ok if q != p and norm(row[q]["text"]) == norm(row[p]["text"]))
                    row[p]["pts"] = POINTS_SAME if same else POINTS_UNIQUE
            out[cat] = row
        return out

    def round_points(self, j: dict | None = None) -> dict[str, int]:
        j = j or self.judge()
        return {p: sum(j[c][p]["pts"] for c in j) for p in self.order()}

    def _close_review(self) -> None:
        j = self.judge()
        pts = self.round_points(j)
        for p, n in pts.items():
            self.st["totals"][p] = self.st["totals"].get(p, 0) + n
        self.st["log"].append({"n": self.st["round"], "letter": self.st["letter"], "points": pts,
                               "answers": {c: {p: {"text": x["text"], "valid": x["valid"], "pts": x["pts"]} for p, x in row.items()}
                                           for c, row in j.items()},
                               "stopp": (self.st.get("stopp") or {}).get("by")})
        self.st.update(answers={}, votes={}, override={}, ready=[])
        if self.st["round"] >= int(self.r.get("rounds") or 5):
            self._finish()
        else:
            self.st["phase"] = "scores"

    # ---------- the end
    def _finish(self) -> None:
        order, tot = self.order(), self.st.get("totals") or {}
        self.st["places"] = places(order, tot) if self.st.get("log") else {}
        self.st["ranking"] = sorted(order, key=lambda p: (-tot.get(p, 0), order.index(p)))
        self.st["phase"] = "done"
        self.st["finished"] = self.now()

    def end(self) -> None:
        """Who leads ends the game: a round in its review is scored as it stands, a round being written is dropped."""
        ph = self.st.get("phase")
        if ph == "review":
            self._close_review()
            if self.st["phase"] == "done":
                return
        if ph in ("write", "review", "scores"):
            self._finish()


# ================================================================ the games in the database (table card_game, kind "stadtland")
class Stadtland(CardGames):
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
        cats = r.get("cats") if isinstance(r.get("cats"), list) else DEFAULT_CATS
        cats = [k for k in dict.fromkeys(str(x) for x in cats) if k in CATS]
        own_in = r.get("own") if isinstance(r.get("own"), list) else []
        own: list[str] = []
        for x in own_in:
            t = clean_text(x, MAX_OWN_LEN)
            if t and t.lower() not in {o.lower() for o in own} and len(own) < MAX_OWN:
                own.append(t)
        try:
            rounds = int(r.get("rounds"))
        except (TypeError, ValueError):
            rounds = DEFAULTS["rounds"]
        try:
            t = int(r.get("time"))
        except (TypeError, ValueError):
            t = DEFAULTS["time"]
        t = t if t in TIMES else DEFAULTS["time"]
        return {"cats": cats, "own": own, "rounds": rounds if rounds in ROUNDS else DEFAULTS["rounds"], "time": t,
                "stopp": True if t == 0 else bool(r.get("stopp")), "hard": bool(r.get("hard"))}

    def rules_info(self) -> dict:
        """The remembered rules, all categories, the choices and the coins for places 1–3 (for the start dialog)."""
        return {**self.default_rules(), "rewards": rewards_of(self.db), "defaults": DEFAULT_CATS,
                "categories": [{"key": k, "title": t, "emoji": e} for k, (t, e) in CATS.items()],
                "rounds_choice": list(ROUNDS), "times": list(TIMES), "min": MIN_CATS, "max": MAX_CATS, "max_own": MAX_OWN,
                "grace": GRACE}

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
        if status != "done" or st.get("paid"):
            return
        # the end: coins for places 1–3 (once), the history – only when at least one round was played
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        self._payout(KIND, row["id"], coins, lambda pid: win_reason(KIND, st["places"][pid]))
        self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history and st.get("log"):
            letters = "".join(e["letter"] for e in st["log"])
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": (st.get("places") or {}).get(p["id"]), "players": len(st["players"]),
                        "points": (st.get("totals") or {}).get(p["id"], 0), "rounds": len(st["log"]), "letters": letters,
                        "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins per player: places 1–3, only people of the family, only with at least two of them at the table and
        at least one round played."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if st.get("solo") or len(people) < 2 or st.get("phase") != "done" or not st.get("log"):
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
        rules = {k: v for k, v in (rules or {}).items() if v is not None}
        r = self.clean_rules(KIND, {**self.default_rules(), **rules})
        n = len(r["cats"]) + len(r["own"])
        if not MIN_CATS <= n <= MAX_CATS:
            raise CommunityError("Choose 3 to 8 categories")
        with self.lock:
            if self._row(KIND):
                raise CommunityError("This game is already running")
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

    def save(self, pid: int, answers: dict) -> None:
        self._act(pid, lambda t: t.save(str(pid), answers))

    def stopp(self, pid: int) -> None:
        self._act(pid, lambda t: t.stopp(str(pid)))

    def vote(self, pid: int, target: str, cat: str, reject: bool = True) -> None:
        self._act(pid, lambda t: t.vote(str(pid), str(target), cat, reject))

    def override(self, pid: int, target: str, cat: str, valid: bool | None) -> None:
        self._act(pid, lambda t: t.override(str(target), cat, valid))

    def ready(self, pid: int, on: bool = True) -> None:
        self._act(pid, lambda t: t.ready(str(pid), on))

    def next(self, pid: int) -> None:
        self._act(pid, lambda t: t.lead_next())

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: the rounds so far count (coins only when at least one round was played)."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] in ("write", "review", "scores"):
                t = self.table(st)
                t.tick()
                t.end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int) -> dict | None:
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
        return self._view(row, st, str(viewer))

    def _view(self, row, st: dict, me: str) -> dict:
        """What one player sees – while a round is being written only their own answers (of the others: how many
        fields they filled)."""
        t = self.table(st)
        ph = st["phase"]
        over = ph == "done" or row["status"] == "done"
        if over and ph != "lobby":
            ph = "done"
        now = self.now()
        coins, totals = st.get("coins") or {}, st.get("totals") or {}
        cats = st.get("cats") or []
        writing = ph == "write"
        players = []
        for p in st["players"]:
            pid = p["id"]
            players.append({"id": pid, "name": p["name"], "avatar": p.get("avatar"), "guest": bool(p.get("guest")),
                            "total": totals.get(pid, 0), "place": (st.get("places") or {}).get(pid), "coins": coins.get(pid, 0),
                            "filled": t.filled(pid) if writing else None, "complete": t.complete(pid) if writing else None,
                            "ready": pid in (st.get("ready") or []) if ph == "review" else None})
        out = {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph, "solo": False,
               "host": row["host_id"], "rules": st["rules"], "cats": cats, "players": players,
               "joined": any(p["id"] == me for p in st["players"]), "round": st.get("round", 0),
               "rounds": st["rules"].get("rounds"), "letter": st.get("letter") if ph != "lobby" else None,
               "letters": st.get("letters") or [], "ranking": st.get("ranking"),
               "rewards": rewards_of(self.db), "coins_on": sum(1 for p in st["players"] if not p.get("guest")) >= 2,
               "grace": GRACE, "spin_ms": 0, "left_ms": None, "stopp": None, "mine": None, "review": None,
               "last": st["log"][-1] if st.get("log") and ph in ("scores", "done") else None,
               "log": [{"n": e["n"], "letter": e["letter"], "points": e["points"]} for e in st.get("log") or []]}
        if writing:
            d = st.get("deadline")
            out["left_ms"] = max(0, int((d - now) * 1000)) if d is not None else None
            out["spin_ms"] = max(0, int((st.get("started", now) + SPIN - now) * 1000))
            out["time_ms"] = int((d - st.get("started", now)) * 1000) if d is not None else None
            out["stopp"] = {"by": st["stopp"]["by"]} if st.get("stopp") else None
            out["mine"] = dict((st.get("answers") or {}).get(me) or {}) if out["joined"] else None
            out["finished"] = sum(1 for p in st["players"] if t.complete(p["id"]))
        elif ph == "review":
            j = t.judge()
            out["review"] = {c: {p: {**x, "mine_reject": me in x["rejects"]} for p, x in row_.items()} for c, row_ in j.items()}
            out["round_points"] = t.round_points(j)
            out["stopp"] = {"by": st["stopp"]["by"]} if st.get("stopp") else None
        return out

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
