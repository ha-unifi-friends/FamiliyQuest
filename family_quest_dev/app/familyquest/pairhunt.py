"""«Paarjagd» – a live pairs game for the family: everybody on their own device, like Domino (domino.py).

The tables live in the `card_game` table with kind "paarjagd" (no own table). Cards come from an emoji set of the app
(web/cards.js PAIR_SETS) or from a photo set of the parents (memorygame.py); the back is a card back or the family crest.

Rules:
  On your turn you turn two cards. A pair scores a point and you go again; no pair: both stay open for HIDE seconds,
  then they turn back and the next player goes. When all pairs are found the most pairs win (a tie shares the place).
Bots remember a card they saw with a chance by level (easy / normal / hard).
Coins (setting `game_rewards`, set by the parents): places 1–3 get coins – only at a family table with at least two
people of the family (not guests); never for bots, guests or alone against bots. Paid once (flag `paid` in the state,
a unique `ref` per player in the ledger).
The view never shows which picture lies under a face-down card.
"""
from __future__ import annotations

import json
import random
import time

from .cardgames import BOTS, BOT_DELAY, CardGames, bot_delay, apply_starter, starter_mode
from .community import CommunityError
from .running import win_reason

KIND = "paarjagd"
TITLE = "Paarjagd"
EMOJI_SETS = {"animals": 20, "fruit": 20, "vehicles": 20, "sea": 20}     # web/cards.js PAIR_SETS: number of pictures
PAIRS = (6, 8, 12, 18)
LEVELS = {"easy": 0.3, "normal": 0.6, "hard": 0.9}                       # how likely a bot remembers a card it saw
BACKS = ("classic", "stars", "waves", "checks", "crest")
DEFAULTS = {"set": "animals", "pairs": 8, "bots": 2, "level": "normal", "back": "classic", "bot_ms": 1400}
HIDE = 1.6                 # seconds two cards that are no pair stay open
REWARDS = [10, 5, 2]       # coins for places 1, 2, 3 (setting game_rewards["paarjagd"])
MEMORY_FOLDER = "_memory"  # memorygame.FOLDER


def photo_sets(db) -> dict[str, list[str]]:
    """The parents' photo sets with at least 3 photos: {"photo:<id>": [addresses]}."""
    d = db.get_setting("memory") or {}
    from .memorygame import photo_url
    return {f"photo:{s['id']}": [photo_url(p) for p in s.get("photos") or []]
            for s in d.get("sets") or [] if len(s.get("photos") or []) >= 3}


def rewards_of(db, kind: str = KIND) -> list[int]:
    """Coins for places 1, 2, 3 of a live game (setting game_rewards[kind]; Paarjagd and «Wer bin ich?» use it)."""
    v = (db.get_setting("game_rewards") or {}).get(kind)
    if isinstance(v, list) and len(v) == 3 and all(isinstance(x, int) and 0 <= x <= 1000 for x in v):
        return list(v)
    return list(REWARDS)


def places(order: list[str], scores: dict) -> dict[str, int]:
    """Place per player: a tie shares the place (5, 5, 3 pairs → 1, 1, 3)."""
    return {p: 1 + sum(1 for q in order if scores.get(q, 0) > scores.get(p, 0)) for p in order}


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

    def deal(self, items: list | None = None) -> None:
        """items: one face per pair (from the set, already chosen); without: pair numbers only (tests)."""
        n = len(items) if items else int(self.r.get("pairs") or 8)
        cards = [k for k in range(n) for _ in range(2)]
        self.rng.shuffle(cards)
        order = self.order()
        self.st.update(cards=cards, items=items or [{"n": k} for k in range(n)], found={}, open=[], hide_at=None,
                       turn=order[0], scores={p: 0 for p in order}, last=None, phase="play", ranking=None, places=None,
                       memory={p["id"]: {} for p in self.st["players"] if p.get("bot")}, moves=0)
        self.st["turn_at"] = self.now()

    def _next(self, pid: str) -> str:
        order = self.order()
        return order[(order.index(pid) + 1) % len(order)]

    def _hidden(self) -> list[int]:
        """Face-down cards (not found, not open)."""
        found, opened = self.st["found"], set(self.st["open"])
        return [i for i in range(len(self.st["cards"])) if str(i) not in found and i not in opened]

    def _see(self, idx: int) -> None:
        """Every bot sees the card – and remembers it with the chance of its level."""
        k = self.st["cards"][idx]
        for p in self.st["players"]:
            if p.get("bot") and self.rng.random() < LEVELS.get(p.get("level"), LEVELS["normal"]):
                self.st["memory"].setdefault(p["id"], {})[str(idx)] = k

    def flip(self, pid: str, idx) -> None:
        if self.st.get("phase") != "play" or self.st.get("turn") != pid:
            raise CommunityError("It is not your turn")
        if len(self.st["open"]) >= 2:
            raise CommunityError("Wait until the cards turn back")
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            raise CommunityError("This card does not exist") from None
        if not 0 <= idx < len(self.st["cards"]):
            raise CommunityError("This card does not exist")
        if str(idx) in self.st["found"] or idx in self.st["open"]:
            raise CommunityError("This card is already open")
        self.st["open"].append(idx)
        self._see(idx)
        now = self.now()
        self.st["turn_at"] = now
        if len(self.st["open"]) < 2:
            self.st["last"] = {"player": pid, "flip": idx, "t": now}
            return
        a, b = self.st["open"]
        self.st["moves"] = self.st.get("moves", 0) + 1
        if self.st["cards"][a] == self.st["cards"][b]:          # a pair: a point, the same player goes again
            self.st["found"][str(a)] = self.st["found"][str(b)] = pid
            self.st["scores"][pid] = self.st["scores"].get(pid, 0) + 1
            self.st["open"] = []
            for mem in self.st["memory"].values():
                mem.pop(str(a), None)
                mem.pop(str(b), None)
            self.st["last"] = {"player": pid, "pair": [a, b], "match": True, "t": now}
            if len(self.st["found"]) >= len(self.st["cards"]):
                self._finish()
        else:                                                   # no pair: open for a moment, then the next player
            self.st["hide_at"] = now + HIDE
            self.st["last"] = {"player": pid, "pair": [a, b], "match": False, "t": now}

    def _finish(self) -> None:
        order, scores = self.order(), self.st["scores"]
        self.st["phase"] = "done"
        self.st["ranking"] = sorted(order, key=lambda p: (-scores.get(p, 0), order.index(p)))
        self.st["places"] = places(order, scores)
        self.st["finished"] = self.now()

    # ---------- bots
    def bot_move(self, pid: str) -> None:
        mem = {int(i): k for i, k in (self.st["memory"].get(pid) or {}).items()}
        hidden = self._hidden()
        known = {i: k for i, k in mem.items() if i in hidden}
        unknown = [i for i in hidden if i not in known]
        opened = self.st["open"]
        if not opened:
            seen: dict[int, int] = {}
            pair = None
            for i, k in sorted(known.items()):
                if k in seen:
                    pair = seen[k]
                    break
                seen[k] = i
            idx = pair if pair is not None else self.rng.choice(unknown or hidden)
        else:
            k = self.st["cards"][opened[0]]
            mate = next((i for i, x in known.items() if x == k and i != opened[0]), None)
            rest = [i for i in unknown if i != opened[0]] or [i for i in hidden if i != opened[0]]
            idx = mate if mate is not None else self.rng.choice(rest)
        self.flip(pid, idx)

    def tick(self) -> bool:
        """Cards that are no pair turn back, bots move. True if something changed."""
        changed = False
        for _ in range(3):
            if self.st.get("phase") != "play":
                break
            now = self.now()
            if len(self.st["open"]) >= 2:
                if now < (self.st.get("hide_at") or 0):
                    break
                self.st["open"], self.st["hide_at"] = [], None
                self.st["turn"] = self._next(self.st["turn"])
                self.st["turn_at"] = now
                changed = True
                continue
            p = self.seat(self.st["turn"])
            if not p or not p.get("bot") or now - self.st.get("turn_at", 0) < bot_delay(self.st["rules"], BOT_DELAY):
                break
            self.bot_move(p["id"])
            changed = True
        return changed


# ================================================================ the games in the database (table card_game, kind "paarjagd")
class Pairhunt(CardGames):
    """The family table / own tables against bots – the same rows and lobby as the card games (join, end, summary)."""

    def __init__(self, db, add_history=None, rewards=None):
        super().__init__(db, add_history)
        self.rewards = rewards

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, {**DEFAULTS, **(self.db.get_setting(f"game_rules.{KIND}") or {})})

    def rules_info(self) -> dict:
        """The remembered rules and the coins for places 1–3 (for the start dialog)."""
        mem = self.db.get_setting("memory") or {}
        names = {f"photo:{s['id']}": s["name"] for s in mem.get("sets") or []}
        return {**self.default_rules(), "rewards": rewards_of(self.db), "crest": mem.get("crest"),
                "photo_sets": [{"key": k, "name": names.get(k, ""), "count": len(v)} for k, v in photo_sets(self.db).items()]}

    def clean_rules(self, kind: str, r: dict) -> dict:
        out = {}
        for k, v in DEFAULTS.items():
            x = r.get(k, v)
            if isinstance(v, int):
                try:
                    out[k] = int(x)
                except (TypeError, ValueError):
                    out[k] = v
            else:
                out[k] = str(x)
        if out["set"] not in EMOJI_SETS and out["set"] not in photo_sets(self.db):
            out["set"] = DEFAULTS["set"]
        out["pairs"] = out["pairs"] if out["pairs"] in PAIRS else DEFAULTS["pairs"]
        out["bots"] = max(0, min(5, out["bots"]))
        out["bot_ms"] = max(0, min(5000, out["bot_ms"]))
        out["level"] = out["level"] if out["level"] in LEVELS else "normal"
        out["back"] = out["back"] if out["back"] in BACKS else "classic"
        if out["back"] == "crest" and not (self.db.get_setting("memory") or {}).get("crest"):
            out["back"] = "classic"
        return out

    def _items(self, r: dict) -> list[dict]:
        """One face per pair, chosen at random from the set: {"e": index in PAIR_SETS} or {"img": address}."""
        photos = photo_sets(self.db).get(r["set"])
        pool = [{"img": u} for u in photos] if photos else [{"e": i} for i in range(EMOJI_SETS.get(r["set"], 20))]
        return random.sample(pool, min(r["pairs"], len(pool)))

    def _deal(self, st: dict) -> None:
        Table(st).deal(self._items(st["rules"]))

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
        # the end: coins for places 1–3 (once), the history
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
            scores = st.get("scores") or {}
            for p in st["players"]:
                if p.get("bot"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {"place": (st.get("places") or {}).get(p["id"]), "pairs": scores.get(p["id"], 0),
                                                         "players": len(st["players"]), "coins": coins.get(p["id"], 0)})
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
            if n_bots and self.bots_off(KIND, [host]):
                raise CommunityError("Playing with bots is switched off for this game")
            if bots is None:
                bots = [{"name": n, "emoji": e} for n, e in random.sample(BOTS, len(BOTS))[:n_bots]]
            for i, b in enumerate(bots[:n_bots]):
                players.append({"id": f"bot{i + 1}", "name": b["name"], "emoji": b.get("emoji") or "🤖", "color": b.get("color"),
                                "owner": b.get("owner"), "bot": True, "level": r["level"]})
            st = {"kind": KIND, "rules": r, "players": players, "phase": "lobby", "solo": solo}
            if r["back"] == "crest":
                st["crest"] = (self.db.get_setting("memory") or {}).get("crest")
            gid = self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, int(solo), json.dumps(st))
            if solo:                                      # alone against bots: deal right away
                row = self.db.q1("SELECT * FROM card_game WHERE id=?", gid)
                self._deal(st)
                self._save(row, st)
            return gid

    def begin(self, kind: str, viewer: int, starter=None) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) < 2:
                raise CommunityError("Add a bot or wait for a second player")
            apply_starter(st, starter_mode(self.db), starter, leader=row["host_id"])     # who begins (parent area › Games)
            self._deal(st)
            self._save(row, st)

    def flip(self, kind: str, pid: int, idx) -> None:
        with self.lock:
            row = self._row(KIND, pid)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            t = Table(st)
            t.tick()
            t.flip(str(pid), idx)
            self._save(row, st)

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
        cards, found, opened = st.get("cards") or [], st.get("found") or {}, st.get("open") or []
        items = st.get("items") or []
        # only what lies open: the pair number of a face-down card never leaves the server
        faces = {str(i): cards[i] for i in range(len(cards)) if str(i) in found or i in opened}
        scores = st.get("scores") or {}
        coins = st.get("coins") or {}
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                    "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"), "pairs": scores.get(p["id"], 0),
                    "place": (st.get("places") or {}).get(p["id"]), "coins": coins.get(p["id"], 0)}
                   for p in st["players"]]
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        return {"game": row["id"], "starter": st.get("starter"), "kind": KIND, "title": TITLE, "status": row["status"], "phase": st["phase"],
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "players": players,
                "joined": any(p["id"] == me for p in st["players"]), "crest": st.get("crest"),
                "count": len(cards), "faces": faces, "items": items, "found": found, "open": opened,
                "turn": st.get("turn"), "my_turn": st.get("phase") == "play" and st.get("turn") == me and len(opened) < 2,
                "last": st.get("last"), "moves": st.get("moves", 0), "ranking": st.get("ranking"),
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2}
