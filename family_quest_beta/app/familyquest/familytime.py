"""Games for FamilyTime: wishes, a vote, a game bought with coins.

FamilyTime events of the family calendar (calendar.py, kind «familytime») can get a game on their agenda:
- Wishes: every family member (children and parents, never guests) wishes one game per event – a family game of the
  app (the ones this person may play) or a board game typed in (free text, max. 60 letters). The wish can be changed
  until the vote starts.
- The wish window closes when a parent taps «Start the vote» or automatically `familytime_vote_hours` hours before
  the event starts. One wish (or several of the same game): it is set directly. Several: a vote – one vote per family
  member; it ends when everybody voted, when a parent ends it, or when the event starts. A tie: the parents decide
  (one of the leaders, or 🎲 at random); a tie still open when the event starts is decided at random.
- Parents may set a game directly, skip the vote (no game from wishes this time), clear the wishes, remove the game.
- A child can buy the game for `familytime_game_price` coins (0 = off) while the event has no game yet: it is set
  firmly and ends wishes and vote. A parent who removes a bought game (or deletes the event) gives the coins back.
Setting a game writes a history entry for every family member. Switched off (`familytime_wishes`): children see
nothing of it, nobody can wish, vote or buy.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta

from .community import CommunityError
from .i18n import _t

MAX_TITLE = 60
HORIZON_DAYS = 60            # FamilyTime events this far ahead can get wishes
MAX_EVENTS = 6
# the family games of the app that can be wished (single-player corner games like Sudoku are left out)
GAMES = {"quiz": ("🎯", _t("Family quiz")), "bingo": ("🎱", "Bingo"), "song": ("🎵", _t("Guess the song")),
         "tschau": ("🂡", "Tschau Sepp"), "karussell": ("🎠", _t("Card Carousel")), "domino": ("🁫", "Domino"),
         "paarjagd": ("🧠", _t("Pair Hunt")), "werbinich": ("🎭", _t("Who am I?")), "kartenlauf": ("🏁", _t("Card Race")),
         "stadtland": ("🏙️", _t("City, Country, River")), "zeichnen": ("🎨", _t("Draw & Guess")), "wuerfel": ("🎲", _t("Five Dice")),
         "heimwaerts": ("🏠", _t("Homeward")), "jump": ("🦘", "Jump"), "klatsch": ("👏", _t("Clap the Beat")),
         "verboten": ("🚫", _t("Forbidden Words")), "jass": ("♣️", _t("Jass")), "werwolf": ("🐺", _t("Werewolves")),
         "schach": ("♟️", _t("Chess")), "dorfmarkt": ("🏘️", _t("Village Market")), "poker": ("🃏", "Texas Hold'em"),
         "ttt": ("⭕", _t("Tic-Tac-Toe")), "pingpong": ("🏓", _t("Ping-Pong"))}
BOARD_ICON = "🎲"


def _norm(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def choice_of(game: str | None, title: str | None) -> tuple[str, str, bool]:
    """A wish → (key, title, app game?). Key «g:tschau» or «t:monopoly» – the same game wished twice is one option."""
    if game:
        if game not in GAMES:
            raise CommunityError("Unknown game")
        return "g:" + game, GAMES[game][1], True
    t = " ".join(str(title or "").split())[:MAX_TITLE]
    if not t:
        raise CommunityError("Which game? Choose one or type a board game")
    return "t:" + _norm(t), t, False


def _icon(key: str) -> str:
    return GAMES[key[2:]][0] if key.startswith("g:") and key[2:] in GAMES else BOARD_ICON


class FamilyTimeGames:
    def __init__(self, fq):
        self.fq = fq
        self.db = fq.db

    # ---------------------------------------------------------------- settings
    def settings(self) -> dict:
        g = self.db.get_setting
        try:
            price = max(0, min(10000, int(g("familytime_game_price") if g("familytime_game_price") is not None else 150)))
        except (TypeError, ValueError):
            price = 150
        try:
            hours = max(0, min(24 * 14, int(g("familytime_vote_hours") if g("familytime_vote_hours") is not None else 24)))
        except (TypeError, ValueError):
            hours = 24
        return {"enabled": g("familytime_wishes") is not False, "price": price, "vote_hours": hours}

    # ---------------------------------------------------------------- helpers
    def members(self) -> list[dict]:
        return self.db.q("SELECT id, name, role FROM profile WHERE archived=0 AND role IN ('kid','parent') ORDER BY role DESC, id")

    @staticmethod
    def _member(prof: dict) -> None:
        if prof.get("role") not in ("kid", "parent") or prof.get("archived"):
            raise CommunityError("Only the family can take part")

    @staticmethod
    def _parent(prof: dict) -> None:
        if prof.get("role") != "parent" or prof.get("archived"):
            raise CommunityError("Only parents can do this")

    def allowed_games(self, prof: dict) -> list[str]:
        """The family games this person may wish: parents all, children those switched on for them (parent area ›
        Games) – an OfflineTime just now does not matter, the wish is for later."""
        if prof.get("role") == "parent":
            return list(GAMES)
        acc = self.fq.games_access()
        return [g for g in GAMES if g in acc and (acc[g]["mode"] == "all" or (acc[g]["mode"] == "some" and prof["id"] in acc[g]["profiles"]))]

    @staticmethod
    def _bounds(e: dict) -> tuple[datetime, datetime]:
        if e["all_day"]:
            return datetime.fromisoformat(e["start"][:10]), datetime.fromisoformat(e["end"][:10]) + timedelta(days=1)
        return datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end"])

    def _event(self, eid: int) -> dict:
        e = self.db.q1("SELECT * FROM family_event WHERE id=? AND kind='familytime'", eid)
        if not e:
            raise CommunityError("Unknown FamilyTime")
        return e

    def _row(self, eid: int) -> dict:
        r = self.db.q1("SELECT * FROM ft_game WHERE event_id=?", eid)
        if not r:
            self.db.x("INSERT OR IGNORE INTO ft_game(event_id) VALUES(?)", eid)
            r = self.db.q1("SELECT * FROM ft_game WHERE event_id=?", eid)
        return r

    def upcoming(self, now: datetime | None = None) -> list[dict]:
        """FamilyTime events that are not over and start within HORIZON_DAYS – the next first."""
        now = now or datetime.now()
        rows = self.db.q("""SELECT * FROM family_event WHERE kind='familytime' AND substr(end,1,10) >= ? AND substr(start,1,10) <= ?
                            ORDER BY start, id""", now.date().isoformat(), (now + timedelta(days=HORIZON_DAYS)).date().isoformat())
        out = []
        for e in rows:
            a, b = self._bounds(e)
            if b > now:
                out.append({**e, "_a": a, "_b": b})
        return out[:MAX_EVENTS]

    def _options(self, eid: int) -> list[dict]:
        """The distinct wishes of an event (the options of the vote), the first wish of a game gives its spelling."""
        opts: dict[str, dict] = {}
        for w in self.db.q("""SELECT w.*, p.name FROM ft_wish w LEFT JOIN profile p ON p.id=w.profile_id
                              WHERE w.event_id=? ORDER BY w.id""", eid):
            o = opts.setdefault(w["choice"], {"key": w["choice"], "title": w["title"], "app": w["choice"].startswith("g:"),
                                              "icon": _icon(w["choice"]), "by": []})
            o["by"].append(w["name"] or "?")
        return list(opts.values())

    # ---------------------------------------------------------------- the lazy clock
    def tick(self, now: datetime | None = None) -> None:
        """The wish window closes `vote_hours` before the start; a vote still open at the start is decided."""
        now = now or datetime.now()
        hours = self.settings()["vote_hours"]
        for e in self.upcoming(now):
            r = self.db.q1("SELECT * FROM ft_game WHERE event_id=?", e["id"])
            status = r["status"] if r else "wish"
            if status == "wish" and now >= e["_a"] - timedelta(hours=hours) and not (r and r["auto_done"]):
                if self.db.val("SELECT COUNT(*) FROM ft_wish WHERE event_id=?", e["id"], default=0):
                    self._start_vote(e["id"], None)
                self._row(e["id"])
                self.db.x("UPDATE ft_game SET auto_done=1 WHERE event_id=?", e["id"])
            elif status in ("vote", "tie") and now >= e["_a"]:
                self._finish(e["id"], force_random=True)

    # ---------------------------------------------------------------- state
    def game_of(self, eid: int) -> dict | None:
        r = self.db.q1("""SELECT g.*, p.name AS by_name FROM ft_game g LEFT JOIN profile p ON p.id=g.by_id
                          WHERE g.event_id=? AND g.status='set'""", eid)
        if not r:
            return None
        return {"key": r["choice"], "title": r["title"], "app": (r["choice"] or "").startswith("g:"), "icon": _icon(r["choice"] or ""),
                "how": r["how"], "by": r["by_name"], "by_id": r["by_id"], "price": r["price"]}

    def games_for_events(self, ids: list[int]) -> dict[int, dict]:
        out = {}
        for i in ids:
            g = self.game_of(i)
            if g:
                out[i] = g
        return out

    def _wish_until(self, e: dict) -> datetime:
        return e["_a"] - timedelta(hours=self.settings()["vote_hours"])

    def _view(self, e: dict, prof: dict, now: datetime, members: list[dict]) -> dict:
        r = self.db.q1("SELECT * FROM ft_game WHERE event_id=?", e["id"]) or {"status": "wish", "auto_done": 0, "tie": None}
        status = r["status"]
        wishes = self.db.q("""SELECT w.id, w.profile_id, w.choice, w.title, p.name FROM ft_wish w LEFT JOIN profile p ON p.id=w.profile_id
                              WHERE w.event_id=? ORDER BY w.id""", e["id"])
        votes = self.db.q("""SELECT v.profile_id, v.choice, p.name FROM ft_vote v LEFT JOIN profile p ON p.id=v.profile_id
                             WHERE v.event_id=?""", e["id"])
        mine_w = next((w for w in wishes if w["profile_id"] == prof["id"]), None)
        mine_v = next((v["choice"] for v in votes if v["profile_id"] == prof["id"]), None)
        until = self._wish_until(e)
        wishes_open = status == "wish" and not r["auto_done"] and now < until and now < e["_a"]
        see = prof.get("role") == "parent" or mine_v is not None or status in ("tie", "set")
        opts = []
        if status in ("vote", "tie"):
            tie = set(json.loads(r["tie"] or "[]"))
            for o in self._options(e["id"]):
                o = dict(o)
                if see:
                    o["votes"] = sum(1 for v in votes if v["choice"] == o["key"])
                    o["names"] = sorted(v["name"] or "?" for v in votes if v["choice"] == o["key"])
                o["tie"] = o["key"] in tie
                opts.append(o)
        game = self.game_of(e["id"])
        st = self.settings()
        return {"id": e["id"], "title": e["title"], "icon": e["icon"], "start": e["_a"].isoformat(timespec="minutes"),
                "end": e["_b"].isoformat(timespec="minutes"), "all_day": bool(e["all_day"]), "started": now >= e["_a"],
                "status": status, "wishes_open": wishes_open, "wish_until": until.isoformat(timespec="minutes"),
                "wishes": [{"id": w["id"], "profile_id": w["profile_id"], "name": w["name"], "key": w["choice"], "title": w["title"],
                            "app": w["choice"].startswith("g:"), "icon": _icon(w["choice"])} for w in wishes],
                "my_wish": ({"key": mine_w["choice"], "title": mine_w["title"]} if mine_w else None),
                "options": opts, "my_vote": mine_v, "voters": len(votes), "members": len(members),
                "missing": [m["name"] for m in members if m["id"] not in {v["profile_id"] for v in votes}] if status == "vote" and prof.get("role") == "parent" else [],
                "game": game,
                "can_buy": bool(st["enabled"] and st["price"] > 0 and prof.get("role") == "kid" and not game)}

    def state(self, prof: dict, now: datetime | None = None) -> dict:
        self._member(prof)
        now = now or datetime.now()
        st = self.settings()
        if not st["enabled"] and prof.get("role") != "parent":
            return {**st, "events": [], "games": []}
        self.tick(now)
        members = self.members()
        return {**st, "coins": self.fq.rewards.balance(prof["id"], "coins"),
                "games": [{"key": g, "icon": GAMES[g][0], "title": GAMES[g][1]} for g in self.allowed_games(prof)],
                "events": [self._view(e, prof, now, members) for e in self.upcoming(now)]}

    def summary(self, prof: dict, now: datetime | None = None) -> dict | None:
        """For the start page: the next FamilyTime that waits for this person's wish or vote."""
        if prof.get("role") not in ("kid", "parent") or not self.settings()["enabled"]:
            return None
        now = now or datetime.now()
        self.tick(now)
        hours = self.settings()["vote_hours"]
        for e in self.upcoming(now):
            r = self.db.q1("SELECT status, auto_done FROM ft_game WHERE event_id=?", e["id"]) or {"status": "wish", "auto_done": 0}
            base = {"id": e["id"], "title": e["title"], "start": e["_a"].isoformat(timespec="minutes"), "all_day": bool(e["all_day"])}
            if r["status"] == "wish" and not r["auto_done"] and now < e["_a"] - timedelta(hours=hours):
                if not self.db.q1("SELECT 1 FROM ft_wish WHERE event_id=? AND profile_id=?", e["id"], prof["id"]):
                    return {**base, "state": "wish"}
            elif r["status"] == "vote":
                if not self.db.q1("SELECT 1 FROM ft_vote WHERE event_id=? AND profile_id=?", e["id"], prof["id"]):
                    return {**base, "state": "vote"}
        return None

    # ---------------------------------------------------------------- wishes and the vote
    def _enabled(self) -> None:
        if not self.settings()["enabled"]:
            raise CommunityError("Game wishes for FamilyTime are switched off")

    def wish(self, prof: dict, eid: int, game: str | None = None, title: str | None = None, now: datetime | None = None) -> None:
        self._member(prof)
        self._enabled()
        now = now or datetime.now()
        self.tick(now)
        e = self._event(eid)
        a, _ = self._bounds(e)
        r = self.db.q1("SELECT * FROM ft_game WHERE event_id=?", eid)
        if (r and (r["status"] != "wish" or r["auto_done"])) or now >= a - timedelta(hours=self.settings()["vote_hours"]) or now >= a:
            raise CommunityError("The wishes for this FamilyTime are closed")
        if game and game not in self.allowed_games(prof):
            raise CommunityError("This game is switched off for you")
        key, t, _ = choice_of(game, title)
        self.db.x("""INSERT INTO ft_wish(event_id, profile_id, choice, title) VALUES(?,?,?,?)
                     ON CONFLICT(event_id, profile_id) DO UPDATE SET choice=excluded.choice, title=excluded.title,
                     at=datetime('now','localtime')""", eid, prof["id"], key, t)

    def unwish(self, prof: dict, eid: int) -> None:
        self._member(prof)
        r = self.db.q1("SELECT * FROM ft_game WHERE event_id=?", eid)
        if r and r["status"] != "wish":
            raise CommunityError("The wishes for this FamilyTime are closed")
        self.db.x("DELETE FROM ft_wish WHERE event_id=? AND profile_id=?", eid, prof["id"])

    def _start_vote(self, eid: int, by: int | None) -> str:
        """Close the wishes: one option → set directly, several → the vote. Returns the new status."""
        opts = self._options(eid)
        if not opts:
            raise CommunityError("No wishes yet")
        self._row(eid)
        if len(opts) == 1:
            o = opts[0]
            wisher = self.db.val("SELECT profile_id FROM ft_wish WHERE event_id=? AND choice=? ORDER BY id LIMIT 1", eid, o["key"])
            self._set(eid, o["key"], o["title"], "single", wisher)
            return "set"
        self.db.x("DELETE FROM ft_vote WHERE event_id=?", eid)
        self.db.x("UPDATE ft_game SET status='vote', tie=NULL, vote_at=datetime('now','localtime') WHERE event_id=?", eid)
        return "vote"

    def start_vote(self, prof: dict, eid: int) -> str:
        self._parent(prof)
        self._event(eid)
        r = self._row(eid)
        if r["status"] not in ("wish", "skipped"):
            raise CommunityError("The vote already started")
        return self._start_vote(eid, prof["id"])

    def vote(self, prof: dict, eid: int, choice: str) -> dict:
        self._member(prof)
        self._enabled()
        self.tick()
        self._event(eid)
        r = self.db.q1("SELECT * FROM ft_game WHERE event_id=?", eid)
        if not r or r["status"] != "vote":
            raise CommunityError("There is no vote for this FamilyTime just now")
        if choice not in {o["key"] for o in self._options(eid)}:
            raise CommunityError("Choose one of the wishes")
        self.db.x("""INSERT INTO ft_vote(event_id, profile_id, choice) VALUES(?,?,?)
                     ON CONFLICT(event_id, profile_id) DO UPDATE SET choice=excluded.choice""", eid, prof["id"], choice)
        ids = {m["id"] for m in self.members()}
        voted = {v["profile_id"] for v in self.db.q("SELECT profile_id FROM ft_vote WHERE event_id=?", eid)}
        if ids <= voted:                                    # everybody voted: the result
            return {"status": self._finish(eid)}
        return {"status": "vote"}

    def end_vote(self, prof: dict, eid: int) -> str:
        self._parent(prof)
        r = self.db.q1("SELECT * FROM ft_game WHERE event_id=?", eid)
        if not r or r["status"] != "vote":
            raise CommunityError("There is no vote for this FamilyTime just now")
        return self._finish(eid)

    def _finish(self, eid: int, force_random: bool = False) -> str:
        """Count the votes: one winner → set; a tie → the parents decide (or at the start of the event: at random)."""
        opts = {o["key"]: o for o in self._options(eid)}
        if not opts:
            self.db.x("UPDATE ft_game SET status='wish', tie=NULL WHERE event_id=?", eid)
            return "wish"
        count = {k: 0 for k in opts}
        for v in self.db.q("SELECT choice FROM ft_vote WHERE event_id=?", eid):
            if v["choice"] in count:
                count[v["choice"]] += 1
        top = max(count.values())
        lead = [k for k, n in count.items() if n == top]
        if len(lead) == 1:
            self._set(eid, lead[0], opts[lead[0]]["title"], "vote", None)
            return "set"
        if force_random:
            k = secrets.choice(lead)
            self._set(eid, k, opts[k]["title"], "random", None)
            return "set"
        self.db.x("UPDATE ft_game SET status='tie', tie=? WHERE event_id=?", json.dumps(lead), eid)
        return "tie"

    # ---------------------------------------------------------------- the game on the agenda
    def _set(self, eid: int, key: str, title: str, how: str, by: int | None, price: int = 0) -> None:
        self._row(eid)
        self.db.x("""UPDATE ft_game SET status='set', choice=?, title=?, how=?, by_id=?, price=?, tie=NULL,
                     set_at=datetime('now','localtime') WHERE event_id=?""", key, title, how, by, price, eid)
        self.db.x("DELETE FROM ft_vote WHERE event_id=?", eid)
        e = self.db.q1("SELECT title, start FROM family_event WHERE id=?", eid) or {"title": "FamilyTime", "start": ""}
        by_name = self.db.val("SELECT name FROM profile WHERE id=?", by) if by else None
        for m in self.members():
            self.fq.community.add_history(m["id"], "familytime", {"event": e["title"], "date": e["start"][:10], "game": title,
                                                                  "app": key.startswith("g:"), "how": how, "by": by_name,
                                                                  "mine": by == m["id"]})

    def set_game(self, prof: dict, eid: int, game: str | None = None, title: str | None = None, choice: str | None = None,
                 random: bool = False) -> None:
        """A parent sets the game: a game or a board game, one of the wishes (`choice`), or 🎲 at random among the
        leaders of a tie (or among all wishes)."""
        self._parent(prof)
        self._event(eid)
        r = self._row(eid)
        if r["status"] == "set":
            raise CommunityError("This FamilyTime has a game already – remove it first")
        opts = {o["key"]: o for o in self._options(eid)}
        if random:
            pool = json.loads(r["tie"] or "[]") if r["status"] == "tie" else list(opts)
            pool = [k for k in pool if k in opts]
            if not pool:
                raise CommunityError("No wishes yet")
            k = secrets.choice(pool)
            return self._set(eid, k, opts[k]["title"], "random", prof["id"])
        if choice:
            if choice not in opts:
                raise CommunityError("Choose one of the wishes")
            return self._set(eid, choice, opts[choice]["title"], "parent", prof["id"])
        key, t, _ = choice_of(game, title)
        self._set(eid, key, t, "parent", prof["id"])

    def skip(self, prof: dict, eid: int) -> None:
        """No vote this time: the wishes close without a game (parents can still set one, a child can still buy one)."""
        self._parent(prof)
        self._event(eid)
        r = self._row(eid)
        if r["status"] == "set":
            raise CommunityError("This FamilyTime has a game already – remove it first")
        self.db.x("DELETE FROM ft_vote WHERE event_id=?", eid)
        self.db.x("UPDATE ft_game SET status='skipped', tie=NULL WHERE event_id=?", eid)

    def _refund(self, eid: int) -> None:
        r = self.db.q1("SELECT * FROM ft_game WHERE event_id=? AND status='set' AND how='bought' AND price > 0", eid)
        if r and r["by_id"]:
            self.fq.rewards.book(r["by_id"], "coins", float(r["price"]), "familytime_refund", "FamilyTime: " + (r["title"] or ""),
                                 f"familytime:{eid}:refund")

    def remove_game(self, prof: dict, eid: int) -> None:
        """A parent takes the game off the agenda – a bought game gives the coins back. The wishes stay; they open
        again if the wish window is still open (else the parents start the vote, set a game or clear the wishes)."""
        self._parent(prof)
        e = self._event(eid)
        a, _ = self._bounds(e)
        closed = int(datetime.now() >= a - timedelta(hours=self.settings()["vote_hours"]))
        with self.db.tx():
            self._refund(eid)
            self.db.x("DELETE FROM ft_vote WHERE event_id=?", eid)
            self.db.x("""UPDATE ft_game SET status='wish', choice=NULL, title=NULL, how=NULL, by_id=NULL, price=0, tie=NULL,
                         auto_done=? WHERE event_id=?""", closed, eid)

    def clear(self, prof: dict, eid: int) -> None:
        """A parent starts over: wishes, votes and the game go (a bought game gives the coins back)."""
        self._parent(prof)
        self._event(eid)
        with self.db.tx():
            self._refund(eid)
            self.db.x("DELETE FROM ft_vote WHERE event_id=?", eid)
            self.db.x("DELETE FROM ft_wish WHERE event_id=?", eid)
            self.db.x("DELETE FROM ft_game WHERE event_id=?", eid)

    def buy(self, prof: dict, eid: int, game: str | None = None, title: str | None = None, now: datetime | None = None) -> dict:
        """A child pays the price and sets the game firmly – only while the event has no game yet."""
        self._member(prof)
        self._enabled()
        if prof.get("role") != "kid":
            raise CommunityError("Parents set the game directly")
        st = self.settings()
        if st["price"] <= 0:
            raise CommunityError("Buying a game is switched off")
        now = now or datetime.now()
        e = self._event(eid)
        _, b = self._bounds(e)
        if now >= b:
            raise CommunityError("This FamilyTime is over")
        if game and game not in self.allowed_games(prof):
            raise CommunityError("This game is switched off for you")
        key, t, _ = choice_of(game, title)
        with self.db.tx():
            r = self._row(eid)
            if r["status"] == "set":
                raise CommunityError("This FamilyTime has a game already")
            if self.fq.rewards.balance(prof["id"], "coins") < st["price"]:
                raise CommunityError("Not enough coins")
            self.fq.rewards.book(prof["id"], "coins", -float(st["price"]), "familytime_game", "FamilyTime: " + t, f"familytime:{eid}")
            self._set(eid, key, t, "bought", prof["id"], st["price"])
        return {"price": st["price"], "coins": self.fq.rewards.balance(prof["id"], "coins")}

    def event_gone(self, eid: int) -> None:
        """The event is deleted or no longer a FamilyTime: a bought game gives the coins back, the rest goes."""
        with self.db.tx():
            self._refund(eid)
            for t in ("ft_vote", "ft_wish", "ft_game"):
                self.db.x(f"DELETE FROM {t} WHERE event_id=?", eid)
