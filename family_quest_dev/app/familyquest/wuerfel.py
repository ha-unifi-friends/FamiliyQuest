"""«Fünf Würfel» – the dice game with five dice and a score sheet (after the public-domain «Generala / Yacht» family).

Everybody plays on their own device at the same time (family table, guests via QR code) or a child plays alone
against bots – the tables live in the `card_game` table with kind "wuerfel" (lobby, join, summary, may_lead from
cardgames.CardGames, like Kartenlauf).

A game has 13 rounds. In every round EVERY player rolls their own five dice: up to 3 rolls, between the rolls any dice
may be held (they are not rolled again). Then the player fills one free box of their score sheet (or crosses one out
with 0). When everybody has filled a box, the next round starts. The dice are rolled on the server; the client only
animates them.

Boxes (CATS):
  ones … sixes      the sum of the dice with that number – upper section: 35 bonus with 63 points or more
  three_kind        3 alike: the sum of all dice           four_kind    4 alike: the sum of all dice
  full_house        3 alike + 2 alike (two numbers): 25    small_straight  4 in a row: 30
  large_straight    5 in a row: 40                          fuenfling    5 alike: 50
  chance            the sum of all dice
House rule `extra` (default on): every further «Fünfling» gives +50 when the Fünfling box already holds 50 (the
dice still fill a box as usual).
End: totals → ranking (a tie shares the place). Who leads may end the game early: the sheets count as they stand,
but coins only for a game played to the end.
Coins (setting `game_rewards["wuerfel"]`): places 1–3, only people of the family at a family table with at least two
of them – never alone against bots; paid once (flag `paid`, a unique ledger `ref` per player).
Bots (levels easy / normal / hard) move by themselves with a reaction time (bot_ms) per roll and choice.
"""
from __future__ import annotations

import json
import random
import time
from collections import Counter
from functools import lru_cache
from itertools import combinations_with_replacement
from math import factorial

from .cardgames import BOTS, BOT_DELAY, CardGames, bot_delay
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .running import win_reason

KIND = "wuerfel"
TITLE = "Fünf Würfel"
EMOJI = "🎲"
UPPER = ("ones", "twos", "threes", "fours", "fives", "sixes")
LOWER = ("three_kind", "four_kind", "full_house", "small_straight", "large_straight", "fuenfling", "chance")
CATS = UPPER + LOWER
ROUNDS = len(CATS)                     # 13
DICE, MAX_ROLLS = 5, 3
BONUS_AT, BONUS = 63, 35
FULL_HOUSE, SMALL, LARGE, FUENFLING, EXTRA = 25, 30, 40, 50, 50
MAX_PLAYERS = 6
LEVELS = ("easy", "normal", "hard")
DEFAULTS = {"bots": 2, "level": "normal", "bot_ms": 1400, "extra": True}


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


# ---------------------------------------------------------------- scoring
def score(cat: str, dice) -> int:
    """The points these five dice give in this box."""
    d = list(dice)
    if len(d) != DICE:
        return 0
    c = Counter(d)
    most = max(c.values())
    if cat in UPPER:
        n = UPPER.index(cat) + 1
        return n * c[n]
    if cat == "three_kind":
        return sum(d) if most >= 3 else 0
    if cat == "four_kind":
        return sum(d) if most >= 4 else 0
    if cat == "full_house":
        return FULL_HOUSE if sorted(c.values()) == [2, 3] else 0
    s = set(d)
    if cat == "small_straight":
        return SMALL if any(set(r) <= s for r in ((1, 2, 3, 4), (2, 3, 4, 5), (3, 4, 5, 6))) else 0
    if cat == "large_straight":
        return LARGE if s in ({1, 2, 3, 4, 5}, {2, 3, 4, 5, 6}) else 0
    if cat == "fuenfling":
        return FUENFLING if most == 5 else 0
    if cat == "chance":
        return sum(d)
    raise CommunityError("Unknown box")


def is_fuenfling(dice) -> bool:
    return len(dice) == DICE and len(set(dice)) == 1


def totals(sheet: dict, extra: int = 0) -> dict:
    """Upper sum, bonus, lower sum, extra Fünfling bonus and the total of a sheet ({box: points})."""
    upper = sum(sheet.get(c) or 0 for c in UPPER)
    lower = sum(sheet.get(c) or 0 for c in LOWER)
    bonus = BONUS if upper >= BONUS_AT else 0
    return {"upper": upper, "bonus": bonus, "lower": lower, "extra": extra, "total": upper + bonus + lower + extra}


# ---------------------------------------------------------------- bots: the value of a hand (exact look-ahead over multisets)
# rough average points of a box with good play – a bot scores a box by what it gets above (or below) that
BASE = {"ones": 2.1, "twos": 5.3, "threes": 8.6, "fours": 12.2, "fives": 15.7, "sixes": 19.2, "three_kind": 21.7,
        "four_kind": 13.1, "full_house": 22.6, "small_straight": 29.5, "large_straight": 32.7, "fuenfling": 16.9, "chance": 22.0}
HANDS = [tuple(h) for h in combinations_with_replacement(range(1, 7), DICE)]          # the 252 sorted hands


@lru_cache(maxsize=None)
def _outcomes(k: int) -> tuple[tuple[tuple[int, ...], float], ...]:
    """Rolling k dice: every sorted result with its probability."""
    out = []
    for combo in combinations_with_replacement(range(1, 7), k):
        n = factorial(k)
        for v in Counter(combo).values():
            n //= factorial(v)
        out.append((combo, n / 6 ** k))
    return tuple(out)


def _subs(hand: tuple) -> set[tuple]:
    """The distinct sorted sub-multisets of a hand (what can be held)."""
    out = {()}
    for x in hand:
        out |= {tuple(sorted(s + (x,))) for s in out}
    return {s for s in out if len(s) <= len(hand)} | {tuple(hand)}


@lru_cache(maxsize=None)
def _subs_cached(hand: tuple) -> tuple:
    return tuple(_subs(hand))


class Brain:
    """The best keep for a sheet: value(hand) = the best box for it; E[keep] over the rolls still left."""

    def __init__(self, free: list[str], value_of):
        self.free = free
        self.value_of = value_of                            # (box, hand) → value
        self.final = {h: max(value_of(c, h) for c in free) for h in HANDS}
        self.levels = [self.final]                          # levels[r]: value of a hand with r rolls left
        self.exp: list[dict] = []                           # exp[r]: keep → expected value of rolling the rest with r rolls left after

    def _exp_keep(self, keep: tuple, vals: dict) -> float:
        return sum(p * vals[tuple(sorted(keep + o))] for o, p in _outcomes(DICE - len(keep)))

    def ensure(self, rolls_left: int) -> None:
        while len(self.exp) < rolls_left:
            vals = self.levels[len(self.exp)]
            e = {}
            for h in HANDS:
                for keep in _subs_cached(h):
                    if keep not in e:
                        e[keep] = self._exp_keep(keep, vals) if len(keep) < DICE else vals[keep]
            self.exp.append(e)
            self.levels.append({h: max(e[k] for k in _subs_cached(h)) for h in HANDS})

    def best_keep(self, hand: tuple, rolls_left: int) -> tuple:
        """rolls_left ≥ 1: the dice to hold (a sorted tuple; all five = stop rolling)."""
        self.ensure(rolls_left)
        e = self.exp[rolls_left - 1]
        hand = tuple(sorted(hand))
        best, bv = hand, self.levels[0][hand]              # stop rolling: the best box now
        for k in _subs_cached(hand):
            if len(k) < DICE and e[k] > bv + 1e-9:
                best, bv = k, e[k]
        return best


def value_fn(level: str, chase: bool, fu50: bool):
    """How much a bot likes these dice in a box: the points against the box's average, the upper bonus (hard)."""
    def value(cat: str, hand) -> float:
        pts = score(cat, hand)
        v = pts - BASE[cat] * (0.35 if level == "normal" else 0.5)
        if cat in UPPER:
            n = UPPER.index(cat) + 1
            if chase:
                v += (pts - 3 * n) * 1.2 + (6 if pts >= 3 * n else 0)
        elif cat == "chance" and level == "hard":
            v -= 6                                          # keep the chance for a bad round
        if fu50 and is_fuenfling(hand):
            v += EXTRA
        return v
    return value


@lru_cache(maxsize=512)
def _brain(free: tuple, level: str, chase: bool, fu50: bool) -> Brain:
    return Brain(list(free), value_fn(level, chase, fu50))


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

    # ---------- the game
    def setup(self) -> None:
        ids = self.order()
        self.st.update(phase="play", round=0, sheets={p: {} for p in ids}, extra={p: 0 for p in ids},
                       fuenflinge={p: 0 for p in ids}, last={}, ranking=None, places=None, complete=False)
        self._round()

    def _round(self) -> None:
        ids = self.order()
        now = self.now()
        self.st.update(round=self.st["round"] + 1, dice={p: [] for p in ids}, held={p: [False] * DICE for p in ids},
                       rolls={p: 0 for p in ids}, round_at=now, bot_at={p: now for p in ids})

    def _check(self, pid: str) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")

    def chose(self, pid: str) -> bool:
        """Filled a box in this round already."""
        return len(self.st["sheets"].get(pid) or {}) >= self.st["round"]

    def free(self, pid: str) -> list[str]:
        sh = self.st["sheets"].get(pid) or {}
        return [c for c in CATS if c not in sh]

    def hold(self, pid: str, held) -> None:
        self._check(pid)
        if self.chose(pid):
            raise CommunityError("You have filled a box already – wait for the others")
        if not self.st["rolls"][pid]:
            raise CommunityError("Roll first")
        if not isinstance(held, (list, tuple)) or len(held) != DICE:
            raise CommunityError("Five dice are needed")
        self.st["held"][pid] = [bool(x) for x in held]

    def roll(self, pid: str, held=None) -> list[int]:
        self._check(pid)
        if self.chose(pid):
            raise CommunityError("You have filled a box already – wait for the others")
        n = self.st["rolls"][pid]
        if n >= MAX_ROLLS:
            raise CommunityError("No more rolls – choose a box")
        if held is not None and n:
            self.hold(pid, held)
        keep = self.st["held"][pid] if n else [False] * DICE
        dice = self.st["dice"][pid] if n else [0] * DICE
        self.st["dice"][pid] = [dice[i] if keep[i] else self.rng.randint(1, 6) for i in range(DICE)]
        self.st["held"][pid] = list(keep)
        self.st["rolls"][pid] = n + 1
        return self.st["dice"][pid]

    def options(self, pid: str) -> dict[str, int]:
        """The points of every free box for the current dice (empty before the first roll)."""
        if not self.st.get("rolls", {}).get(pid) or self.chose(pid):
            return {}
        d = self.st["dice"][pid]
        return {c: score(c, d) for c in self.free(pid)}

    def choose(self, pid: str, cat: str) -> int:
        self._check(pid)
        if self.chose(pid):
            raise CommunityError("You have filled a box already – wait for the others")
        if cat not in CATS:
            raise CommunityError("Unknown box")
        if not self.st["rolls"][pid]:
            raise CommunityError("Roll first")
        sheet = self.st["sheets"][pid]
        if cat in sheet:
            raise CommunityError("This box is filled already")
        d = self.st["dice"][pid]
        pts = score(cat, d)
        extra = 0
        if is_fuenfling(d):
            self.st["fuenflinge"][pid] = self.st["fuenflinge"].get(pid, 0) + 1
            if self.r.get("extra") and sheet.get("fuenfling") == FUENFLING:
                extra = EXTRA
                self.st["extra"][pid] = self.st["extra"].get(pid, 0) + EXTRA
        sheet[cat] = pts
        self.st["last"][pid] = {"cat": cat, "pts": pts, "extra": extra, "round": self.st["round"], "dice": list(d)}
        self._maybe_next()
        return pts

    def _maybe_next(self) -> None:
        if self.st.get("phase") == "play" and all(self.chose(p) for p in self.order()):
            if self.st["round"] >= ROUNDS:
                self.st["complete"] = True
                self._finish()
            else:
                self._round()

    def total(self, pid: str) -> int:
        return totals(self.st["sheets"].get(pid) or {}, (self.st.get("extra") or {}).get(pid, 0))["total"]

    def _finish(self) -> None:
        order = self.order()
        tot = {p: self.total(p) for p in order}
        self.st["places"] = places(order, tot)
        self.st["ranking"] = sorted(order, key=lambda p: (-tot[p], order.index(p)))
        self.st["phase"] = "done"
        self.st["finished"] = self.now()

    def end(self) -> None:
        """Who leads ends the game: the sheets count as they stand (no coins – see coins_for)."""
        if self.st.get("phase") == "play":
            self._finish()

    # ---------- bots
    def _value_key(self, pid: str, level: str) -> tuple:
        sheet = self.st["sheets"].get(pid) or {}
        upper = sum(sheet.get(c) or 0 for c in UPPER)
        open_up = [c for c in UPPER if c not in sheet]
        need = BONUS_AT - upper
        par_left = sum(3 * (UPPER.index(c) + 1) for c in open_up)
        chase = level == "hard" and need > 0 and bool(open_up) and need <= par_left + 6
        fu50 = sheet.get("fuenfling") == FUENFLING and bool(self.r.get("extra"))
        return level, chase, fu50

    def _value(self, pid: str, level: str):
        return value_fn(*self._value_key(pid, level))

    def bot_keep(self, pid: str, level: str) -> list[bool] | None:
        """The dice a bot holds before the next roll – None: stop rolling."""
        d = self.st["dice"][pid]
        left = MAX_ROLLS - self.st["rolls"][pid]
        free = self.free(pid)
        if level == "easy":
            c = Counter(d)
            if self.rng.random() < 0.2 or max(score(x, d) for x in free) >= 25:
                return None
            if self.rng.random() < 0.75:
                n = max(c, key=lambda x: (c[x], x))
                return [x == n for x in d]
            return [self.rng.random() < 0.5 for _ in d]
        if level == "normal":
            s = set(d)
            if any(score(x, d) >= 25 for x in free if x in ("full_house", "small_straight", "large_straight", "fuenfling")) \
                    and not ("large_straight" in free and score("small_straight", d) and not score("large_straight", d)):
                return None
            for run in ((2, 3, 4, 5), (1, 2, 3, 4), (3, 4, 5, 6)):
                if set(run) <= s and ("large_straight" in free or "small_straight" in free):
                    held, used = [], set()
                    for x in d:
                        held.append(x in run and x not in used)
                        used.add(x)
                    return held
            c = Counter(d)
            n = max(c, key=lambda x: (c[x], x))
            return [x == n for x in d]
        brain = _brain(tuple(free), *self._value_key(pid, level))
        keep = list(brain.best_keep(tuple(d), left))
        if len(keep) == DICE:
            return None
        held = []
        for x in d:
            if x in keep:
                keep.remove(x)
                held.append(True)
            else:
                held.append(False)
        return held

    def bot_choice(self, pid: str, level: str) -> str:
        d = self.st["dice"][pid]
        free = self.free(pid)
        if level == "easy":
            best = max(score(c, d) for c in free)
            if best == 0:                                   # cross out a box that is worth little anyway
                return min(free, key=lambda c: (BASE[c], self.rng.random()))
            return self.rng.choice([c for c in free if score(c, d) == best])
        value = self._value(pid, level)
        return max(free, key=lambda c: (value(c, d), -CATS.index(c)))

    def bot_step(self, pid: str, level: str) -> None:
        """One action of a bot: roll (holding some dice) or fill a box."""
        n = self.st["rolls"][pid]
        if n == 0:
            self.roll(pid)
            return
        keep = self.bot_keep(pid, level) if n < MAX_ROLLS else None
        if keep is None or all(keep):
            self.choose(pid, self.bot_choice(pid, level))
        else:
            self.roll(pid, keep)

    def tick(self) -> bool:
        """The bots act (one action each after their reaction time; at once with bot_ms 0). True if something changed."""
        changed = False
        delay = bot_delay(self.r, BOT_DELAY)
        for _ in range(ROUNDS * 5 if delay == 0 else 1):
            if self.st.get("phase") != "play":
                break
            moved = False
            now = self.now()
            for p in self.st["players"]:
                pid = p["id"]
                if not p.get("bot") or self.chose(pid) or self.st.get("phase") != "play":
                    continue
                if now - self.st["bot_at"].get(pid, 0) < delay:
                    continue
                rnd = self.st["round"]
                self.bot_step(pid, p.get("level", "normal"))
                if self.st["round"] == rnd:
                    self.st["bot_at"][pid] = now
                moved = changed = True
            if not moved:
                break
        return changed


# ================================================================ the games in the database (table card_game, kind "wuerfel")
class Wuerfel(CardGames):
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
        return {**self.default_rules(), "rewards": rewards_of(self.db), "cats": list(CATS), "bonus_at": BONUS_AT,
                "bonus": BONUS, "max_players": MAX_PLAYERS}

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
        self._payout(KIND, row["id"], coins, lambda pid: win_reason(KIND, st["places"][pid]))
        self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history and st.get("round"):
            t = Table(st)
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]), "points": t.total(p["id"]),
                        "complete": bool(st.get("complete")), "fuenflinge": (st.get("fuenflinge") or {}).get(p["id"], 0),
                        "coins": coins.get(p["id"], 0)})
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

    def _deal(self, st: dict) -> None:
        humans = [p for p in st["players"] if not p.get("bot")]
        n = st["rules"]["bots"]
        if st.get("solo"):
            n = max(1, n)
        n = max(0, min(n, MAX_PLAYERS - len(humans)))
        st["players"] = humans + self._bots(st, n)
        st.pop("bot_pool", None)
        if len(st["players"]) < 2 and not st.get("solo"):
            raise CommunityError("Add a bot or wait for a second player")
        self.table(st).setup()

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
            if solo:                                      # alone against bots: the first round starts right away
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

    def begin(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            self._deal(st)
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

    def roll(self, pid: int, held=None) -> list[int]:
        return self._with(pid, lambda t: t.roll(str(pid), held))

    def hold(self, pid: int, held) -> None:
        self._with(pid, lambda t: t.hold(str(pid), held))

    def choose(self, pid: int, cat: str) -> int:
        return self._with(pid, lambda t: t.choose(str(pid), cat))

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: the sheets count as they stand (coins only for a game played to the end)."""
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
        base = {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph,
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "joined": joined,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2,
                "cats": list(CATS), "rounds": ROUNDS, "max_rolls": MAX_ROLLS, "bonus_at": BONUS_AT, "bonus": BONUS}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            bots = st["rules"]["bots"] if not st.get("solo") else max(1, st["rules"]["bots"])
            return {**base, "players": players, "bots": max(0, min(bots, MAX_PLAYERS - len(players))), "max_players": MAX_PLAYERS}
        t = self.table(st)
        coins, pl = st.get("coins") or {}, st.get("places") or {}
        players = []
        for p in st["players"]:
            pid = p["id"]
            sheet = st["sheets"].get(pid) or {}
            players.append({"id": pid, "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                            "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"),
                            "sheet": sheet, **totals(sheet, (st.get("extra") or {}).get(pid, 0)),
                            "dice": list((st.get("dice") or {}).get(pid) or []), "held": list((st.get("held") or {}).get(pid) or []),
                            "rolls": (st.get("rolls") or {}).get(pid, 0), "done": ph == "play" and t.chose(pid),
                            "last": (st.get("last") or {}).get(pid), "fuenflinge": (st.get("fuenflinge") or {}).get(pid, 0),
                            "place": pl.get(pid), "coins": coins.get(pid, 0)})
        mine = next((p for p in players if p["id"] == me), None) if joined else None
        return {**base, "players": players, "round": st.get("round", 0), "ranking": st.get("ranking"),
                "complete": bool(st.get("complete")),
                "me": me if joined else None,
                "options": t.options(me) if joined and ph == "play" else {},
                "can_roll": bool(mine) and ph == "play" and not mine["done"] and mine["rolls"] < MAX_ROLLS,
                "waiting": [p["id"] for p in players if ph == "play" and not p["done"]]}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
