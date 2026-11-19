"""«Verbotene Wörter» – the live explaining game for the family: one explains a word without saying the forbidden
words, the others guess aloud. Everybody has their own device; the talking happens at the table.

The tables live in the `card_game` table with kind "verboten" (no own table); lobby, join, summary and may_lead come
from cardgames.CardGames, like «Zeichnen & Raten» (zeichnen.py). Only people play (family and guests via QR code) – no
bots, 2 to 8 players.

Rules (chosen by who opens the table, remembered):
  level         the cards (verboten_cards.json): easy (younger children), normal or mixed
  time          seconds per turn: 30, 45, 60, 90 or 120
  rounds        1–4 – how often everybody explains (teams: how often each team member explains, see below)
  teams         on: with 4 or more players two teams (seats alternate; who leads can mix the seats in the lobby);
                with 2 or 3 players – or off – everybody plays for themselves
  skip_penalty  0 or 1 point for «Skip»
A turn: the explainer taps «Go!» (phase "ready" → "explain"), the clock runs (the deadline is kept on the server).
The explainer sees the card (the word and 5 forbidden words) and taps
  «Got it»          +1 for the team – alone: +1 for who guessed it (the explainer picks them) and +1 for the explainer
  «Forbidden word»  −1 for the explainer's team (alone: the explainer)
  «Skip»            −skip_penalty
and the next card comes. With teams the players of the other team see the card too (they watch for forbidden words,
the classic rule) and can «Buzz» – the same as «Forbidden word». The explainer's own team never gets the card in its
view. Every action names the number of the card it means, so a late tap (or a buzz and a tap at once) counts once.
When the time is up the card on the table does not count; the turn's cards are shown to everybody and the next
explainer gets ready. Teams take turns, the members of a team explain in turn (a smaller team's members explain more
often so that both teams have the same number of turns). Who leads may skip a turn and end the game (a turn in
progress counts as it stands).
Coins (setting `game_rewards["verboten"]`): places 1–3 (a team shares its place, a tie shares the place) – only
people of the family, only with at least two of them, only when at least one turn was played and somebody scored;
paid once (flag `paid`, a unique ledger `ref`).
Languages (gamewords.py): the cards are English keys – the word, and its five forbidden words as one text – so every
language has its own obvious forbidden words. The state keeps the number of the card; every view shows it in the
viewer's language (the explainer reads it in theirs; the other team checks in theirs).
"""
from __future__ import annotations

import json
import random
import time
from functools import lru_cache
from pathlib import Path

from .cardgames import CardGames, apply_starter, starter_mode
from .gamewords import Words
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .running import win_reason

KIND = "verboten"
TITLE = "Verbotene Wörter"
EMOJI = "🚫"
LEVELS = ("easy", "normal", "mixed")
TIMES = (30, 45, 60, 90, 120)
ROUNDS = (1, 2, 3, 4)
DEFAULTS = {"level": "mixed", "time": 60, "rounds": 2, "teams": True, "skip_penalty": 0}
MIN_PLAYERS, MAX_PLAYERS = 2, 8
MIN_TEAMS = 4                     # players needed for two teams
RESULTS = ("got", "taboo", "pass", "buzz")
CARDS_FILE = Path(__file__).with_name("verboten_cards.json")


@lru_cache(maxsize=1)
def cards() -> dict[str, list[dict]]:
    """The built-in cards per level: [{"word": …, "taboo": [5 words]}]."""
    return json.loads(CARDS_FILE.read_text(encoding="utf-8"))["levels"]


def card(key: str) -> dict | None:
    """A card by its key "e12" / "n7" (level letter + index)."""
    lv = {"e": "easy", "n": "normal"}.get(str(key)[:1])
    try:
        return cards()[lv][int(str(key)[1:])] if lv else None
    except (ValueError, IndexError):
        return None


def deck_keys(level: str) -> list[str]:
    out = []
    for lv in (("easy", "normal") if level == "mixed" else (level,)):
        out += [f"{lv[0]}{i}" for i in range(len(cards()[lv]))]
    return out


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

    def teams(self) -> bool:
        return bool(self.st.get("teams"))

    def side(self, pid: str | None) -> str | None:
        """The key of the scores: the team ("0" / "1") – alone: the player."""
        if pid is None:
            return None
        return (self.st.get("team_of") or {}).get(pid) if self.teams() else pid

    def sees_card(self, pid: str) -> bool:
        """The explainer – and with teams the players of the other team (they watch for forbidden words)."""
        if self.st.get("phase") != "explain" or pid not in self.order():
            return False
        ex = self.st.get("explainer")
        return pid == ex or (self.teams() and self.side(pid) != self.side(ex))

    def n_turns(self) -> int:
        return len(self.st.get("schedule") or [])

    def round(self) -> int:
        """Round 1 … rounds (a round: everybody – or every team member – explained once)."""
        per = max(1, self.n_turns() // max(1, int(self.r.get("rounds") or 1)))
        return min(int(self.r.get("rounds") or 1), max(0, self.st.get("turn", 0)) // per + 1)

    # ---------- the game
    def begin(self, seats: list[str] | None = None) -> None:
        """seats: the seat order of the lobby (the teams: every second seat) – the player list itself may be turned
        round by the starter (cardgames.apply_starter); the starter's team then explains first, the teams stay."""
        order = self.order()
        teams = bool(self.r.get("teams")) and len(order) >= MIN_TEAMS
        rounds = int(self.r.get("rounds") or 1)
        if teams:
            seats = [p for p in (seats or []) if p in order] + [p for p in order if p not in (seats or [])]
            team_of = {p: str(seats.index(p) % 2) for p in order}
            first = team_of[order[0]]                                   # the starter's team explains first
            a, b = [p for p in order if team_of[p] == first], [p for p in order if team_of[p] != first]
            schedule = []
            for i in range(rounds * max(len(a), len(b))):          # the teams take turns, members in turn
                schedule += [a[i % len(a)], b[i % len(b)]]
            scores = {"0": 0, "1": 0}
        else:
            team_of, schedule, scores = {}, order * rounds, {p: 0 for p in order}
        deck = deck_keys(self.r.get("level") or DEFAULTS["level"])
        self.rng.shuffle(deck)
        self.st.update(teams=teams, team_of=team_of, schedule=schedule, scores=scores, deck=deck, pos=0, n=0,
                       turn=-1, log=[], stats={p: {"explained": 0, "guessed": 0, "taboo": 0} for p in order},
                       ranking=None, places=None, cards=[], card=None)
        self._next_turn()

    def _next_turn(self) -> None:
        t = self.st["turn"] + 1
        if t >= self.n_turns():
            self._finish()
            return
        self.st.update(turn=t, explainer=self.st["schedule"][t], phase="ready", card=None, cards=[],
                       started=None, deadline=None)

    def _draw(self) -> None:
        deck = self.st["deck"]
        if self.st["pos"] >= len(deck):                           # all cards used: shuffle again
            self.rng.shuffle(deck)
            self.st["pos"] = 0
        self.st["card"] = deck[self.st["pos"]]
        self.st["pos"] += 1
        self.st["n"] = self.st.get("n", 0) + 1

    def go(self, pid: str) -> None:
        """The explainer is ready: the clock runs, the first card comes."""
        self._check_player(pid)
        if self.st.get("phase") != "ready":
            raise CommunityError("The turn is already running")
        if pid != self.st.get("explainer"):
            raise CommunityError("It is not your turn to explain")
        now = self.now()
        self.st.update(phase="explain", started=now, deadline=now + int(self.r.get("time") or 60), cards=[])
        self._draw()

    def _check_player(self, pid: str) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")

    def _add(self, side: str, pts: int) -> None:
        self.st["scores"][side] = self.st["scores"].get(side, 0) + pts

    def mark(self, pid: str, n: int, result: str, guesser: str | None = None) -> None:
        """«Got it», «Forbidden word», «Skip» (the explainer) or «Buzz» (the other team) for card number n."""
        self._check_player(pid)
        if result not in RESULTS:
            raise CommunityError("Unknown action")
        if self.st.get("phase") != "explain":
            raise CommunityError("The time is up")
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = -1
        if n != self.st.get("n"):
            raise CommunityError("Too late – this card is gone")
        ex = self.st["explainer"]
        if result == "buzz":
            if pid == ex or not self.sees_card(pid):
                raise CommunityError("Only the other team can buzz")
        elif pid != ex:
            raise CommunityError("Only who explains can do that")
        entry = {"key": self.st["card"], "res": result, "pts": 0}
        stats = self.st["stats"]
        if result == "got":
            others = [p for p in self.order() if p != ex]
            if self.teams():
                self._add(self.side(ex), 1)
                entry["pts"] = 1
            else:
                if guesser is None and len(others) == 1:
                    guesser = others[0]
                guesser = None if guesser is None else str(guesser)
                if guesser not in others:
                    raise CommunityError("Who guessed it?")
                self._add(guesser, 1)
                self._add(ex, 1)
                stats[guesser]["guessed"] += 1
                entry.update(by=guesser, pts=1)
            stats[ex]["explained"] += 1
        elif result in ("taboo", "buzz"):
            self._add(self.side(ex), -1)
            stats[ex]["taboo"] += 1
            entry["pts"] = -1
            if result == "buzz":
                entry["by"] = pid
        else:
            pen = int(self.r.get("skip_penalty") or 0)
            if pen:
                self._add(self.side(ex), -pen)
            entry["pts"] = -pen
        self.st["cards"].append(entry)
        self._draw()

    # ---------- the turn ends, the clock
    def _log_turn(self, skipped: bool = False) -> None:
        cs = self.st.get("cards") or []
        open_card = self.st.get("card") if self.st.get("phase") == "explain" else None
        self.st["log"].append({"n": self.st["turn"], "explainer": self.st["explainer"], "side": self.side(self.st["explainer"]),
                               "cards": list(cs), "open": open_card, "points": sum(c["pts"] for c in cs), "skipped": skipped})
        self.st.update(card=None, deadline=None)

    def _close_turn(self, skipped: bool = False) -> None:
        self._log_turn(skipped)
        self._next_turn()

    def tick(self) -> bool:
        """The time is up: the card on the table does not count, the next explainer gets ready."""
        if self.st.get("phase") == "explain" and self.now() >= (self.st.get("deadline") or 0):
            self._close_turn()
            return True
        return False

    def skip(self) -> None:
        """Who leads skips the turn: before «Go!» the next explainer comes, during the turn it ends as it stands."""
        ph = self.st.get("phase")
        if ph == "ready":
            self._next_turn()
        elif ph == "explain":
            self._close_turn(skipped=True)
        else:
            raise CommunityError("The game is not running")

    # ---------- the end
    def points_of(self, pid: str) -> int:
        return (self.st.get("scores") or {}).get(self.side(pid), 0)

    def _finish(self) -> None:
        order = self.order()
        pts = {p: self.points_of(p) for p in order}
        self.st["places"] = places(order, pts) if self.st.get("log") else {}
        self.st["ranking"] = sorted(order, key=lambda p: (-pts[p], order.index(p)))
        self.st.update(phase="done", finished=self.now(), card=None, deadline=None)

    def end(self) -> None:
        """Who leads ends the game: a turn in progress counts as it stands."""
        ph = self.st.get("phase")
        if ph == "explain":
            self._log_turn()
        if ph in ("ready", "explain"):
            self._finish()


def card_view(key: str | None, lang: str = "en", words: Words | None = None) -> dict | None:
    """A card in `lang`: the word and its five forbidden words."""
    c = card(key) if key else None
    return (words or Words()).card(c["word"], c["taboo"], lang) if c else None


# ================================================================ the games in the database (table card_game, kind "verboten")
class Verboten(CardGames):
    """The family table – the same rows and lobby as the card games (join, summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng: random.Random | None = None):
        super().__init__(db, add_history)
        self.rewards = rewards
        self.now = now
        self.rng = rng
        self.words = Words(db)

    def table(self, st: dict) -> Table:
        return Table(st, self.rng, now=lambda: self.now())

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, self.db.get_setting(f"game_rules.{KIND}") or {})

    def clean_rules(self, kind: str, r: dict) -> dict:
        r = {**DEFAULTS, **(r or {})}

        def num(k, allowed):
            try:
                v = int(r.get(k))
            except (TypeError, ValueError):
                return DEFAULTS[k]
            return v if v in allowed else DEFAULTS[k]
        lv = str(r.get("level") or "")
        return {"level": lv if lv in LEVELS else DEFAULTS["level"], "time": num("time", TIMES), "rounds": num("rounds", ROUNDS),
                "teams": bool(r.get("teams")), "skip_penalty": num("skip_penalty", (0, 1))}

    def rules_info(self) -> dict:
        """The remembered rules, the choices, the number of cards and the coins for places 1–3 (for the start dialog)."""
        return {**self.default_rules(), "rewards": rewards_of(self.db), "levels": list(LEVELS), "times": list(TIMES),
                "rounds_choice": list(ROUNDS), "counts": {lv: len(v) for lv, v in cards().items()}, "min_teams": MIN_TEAMS}

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
        # the end: coins for places 1–3 (once), the «No. 1» hat, the history – only when at least one turn was played
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st, separators=(",", ":")), row["id"])
        self._payout(KIND, row["id"], coins, lambda pid: win_reason(KIND, st["places"][pid]))
        if any(p > 0 for p in (st.get("scores") or {}).values()):
            self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history and st.get("log"):
            t = self.table(st)
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                s = (st.get("stats") or {}).get(p["id"]) or {}
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": (st.get("places") or {}).get(p["id"]), "players": len(st["players"]),
                        "points": t.points_of(p["id"]), "teams": bool(st.get("teams")), "turns": len(st["log"]),
                        "explained": s.get("explained", 0), "guessed": s.get("guessed", 0), "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins per player: places 1–3, only people of the family, only with at least two of them at the table,
        at least one turn played and at least one point scored."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if st.get("solo") or len(people) < 2 or st.get("phase") != "done" or not st.get("log"):
            return {}
        if not any(v > 0 for v in (st.get("scores") or {}).values()):
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

    def _lobby(self, viewer: int, fn) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            fn(st, row)
            self._save(row, st)

    def begin(self, kind: str, viewer: int, starter=None) -> None:
        def go(st, row):
            if len(st["players"]) < MIN_PLAYERS:
                raise CommunityError("Wait for a second player")
            seats = [p["id"] for p in st["players"]]          # the teams as shown in the lobby
            apply_starter(st, starter_mode(self.db), starter, leader=row["host_id"])   # only who explains first
            self.table(st).begin(seats)
        self._lobby(viewer, go)

    def mix(self, viewer: int) -> None:
        """Who leads mixes the seats in the lobby (the teams: every second seat)."""
        self._lobby(viewer, lambda st, row: (self.rng or random).shuffle(st["players"]))

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

    def go(self, pid: int) -> None:
        self._act(pid, lambda t: t.go(str(pid)))

    def mark(self, pid: int, n: int, result: str, guesser: str | None = None) -> None:
        self._act(pid, lambda t: t.mark(str(pid), n, result, guesser))

    def skip(self, pid: int) -> None:
        self._act(pid, lambda t: t.skip())

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: the turns so far count (coins only when at least one turn was played)."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] in ("ready", "explain"):
                t = self.table(st)
                t.tick()
                t.end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int, lang: str | None = None) -> dict | None:
        """The view of one player in their language."""
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
        return self._view(row, st, str(viewer), lang or "en")

    def _view(self, row, st: dict, me: str, lang: str = "en") -> dict:
        """What one player sees, in their language – the card only when they explain or (teams) belong to the other team."""
        t = self.table(st)
        tr = self.words.translator(lang)

        def word(key):
            c = card(key)
            return tr(c["word"]) if c else "?"

        ph = st["phase"]
        if (ph == "done" or row["status"] == "done") and ph != "lobby":
            ph = "done"
        now = self.now()
        playing = ph in ("ready", "explain")
        ex = st.get("explainer") if playing else None
        coins = st.get("coins") or {}
        joined = any(p["id"] == me for p in st["players"])
        lobby_teams = ph == "lobby" and bool(st["rules"].get("teams")) and len(st["players"]) >= MIN_TEAMS
        team_of = ({p["id"]: str(i % 2) for i, p in enumerate(st["players"])} if lobby_teams
                   else (st.get("team_of") or {}) if t.teams() else {})
        stats = st.get("stats") or {}
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "guest": bool(p.get("guest")),
                    "team": team_of.get(p["id"]), "total": t.points_of(p["id"]) if ph != "lobby" else 0,
                    "place": (st.get("places") or {}).get(p["id"]), "coins": coins.get(p["id"], 0), "explainer": p["id"] == ex,
                    "explained": (stats.get(p["id"]) or {}).get("explained", 0), "guessed": (stats.get(p["id"]) or {}).get("guessed", 0)}
                   for p in st["players"]]
        sees = ph == "explain" and joined and t.sees_card(me)
        cs = st.get("cards") or []
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))

        def log_entry(e):
            return {"n": e["n"], "explainer": e["explainer"], "side": e.get("side"), "points": e["points"], "skipped": e.get("skipped", False),
                    "cards": [{"word": word(c["key"]), "res": c["res"], "pts": c["pts"], "by": c.get("by")} for c in e["cards"]],
                    "open": word(e["open"]) if e.get("open") else None}
        out = {"game": row["id"], "starter": st.get("starter"), "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph, "solo": False,
               "host": row["host_id"], "rules": st["rules"], "players": players, "joined": joined,
               "teams": bool(team_of), "scores": dict(st.get("scores") or {}) if ph != "lobby" else {},
               "my_team": team_of.get(me), "turn": st.get("turn", -1) if ph != "lobby" else None,
               "turns": t.n_turns(), "round": t.round() if ph != "lobby" else 0, "rounds": st["rules"].get("rounds"),
               "explainer": ex, "me_explainer": bool(ex) and ex == me,
               "next": st["schedule"][st["turn"] + 1] if playing and st["turn"] + 1 < t.n_turns() else None,
               "n": st.get("n") if ph == "explain" else None,
               "card": card_view(st.get("card"), lang, self.words) if sees else None, "can_buzz": sees and me != ex,
               "turn_cards": None, "count": None, "left_ms": None, "time_ms": None,
               "last": log_entry(st["log"][-1]) if ph in ("ready", "done") and st.get("log") else None,
               "log": [log_entry(e) for e in st.get("log") or []] if ph == "done" else None,
               "ranking": st.get("ranking"), "rewards": rewards_of(self.db), "coins_on": people >= 2}
        if ph == "explain":
            out["left_ms"] = max(0, int((st["deadline"] - now) * 1000))
            out["time_ms"] = int((st["deadline"] - st["started"]) * 1000)
            out["count"] = {r: sum(1 for c in cs if c["res"] == r) for r in RESULTS}
            if sees:          # who sees the card also sees the cards of this turn (the others only count them)
                out["turn_cards"] = [{"word": word(c["key"]), "res": c["res"], "pts": c["pts"], "by": c.get("by")} for c in cs]
        return out

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
