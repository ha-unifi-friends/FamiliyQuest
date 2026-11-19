"""«Snack Rush» – a live snack-stand race: every player runs their own snack stand, all serve the same customers.

Everybody plays on their own device (family table, guests via QR code) or alone (high score, optionally with practice
bots) – the tables live in the `card_game` table with kind "snack" (lobby, join, summary, may_lead from
cardgames.CardGames, like «Jump»).

Fair for everybody: all stands get the SAME customers – a stream made on the server from a seed of `secrets`
(`customers()`: arrival, patience and order of every customer; the app gets the next ones with every answer) – on the
same game clock (game time 0 = `t0`, a short countdown after the start). It gets harder: customers come more often,
order more and lose their patience faster (level easy / normal / hard).

Every food is made in steps one after the other, every step takes its time on a station with a few places (FOODS,
STATIONS – the same numbers in web/snack.js): burger = grill (4 s) → assemble (2 s), hot dog = pot (3 s) → into the
bun (1.5 s), fries = fryer (5 s) → salt (1 s), drink = fill (3 s), pizza = oven (6 s), ice cream = machine (2 s).
Grill, fryer and oven burn what is left on them too long, the ice cream melts – into the bin, the money is lost.

The till (the game's own pretend money 💰 – not the coins of the app): every step costs its ingredients when it starts
(COST, half on «easy»); a served customer pays the prices of the order (PRICE) plus a tip for fast service – 1–3
stars, the more patience was left the more (TIP). An angry customer walks away without paying: what was already made
for them goes back onto the shelf and can be given to the next customer who wants the same – a food on the shelf gets
cold after SHELF_COLD seconds and goes into the bin. The till = earnings − ingredients.

The game runs for a set time (rule `mode`: t3 / t5 / t8 – 3, 5 or 8 minutes, default 5); who has the most money in
the till at the end wins (then more served customers, more stars, fewer angry ones; the same shares the place).
Optional (rule `limit`: 0 = off, the default, or 3 / 5 / 8): with that many angry customers you are out – your till
stays as it is; the game ends early when no person is left in. A player whose app stays silent for STALE seconds is out
then too. The score is the till; the personal best is kept (setting `snack_best`). Who leads may end the game early:
ranked as it stands, no coins.

The kitchen runs in the app (no waiting for the network): it reports the customers it served (index + game time), the
ones it saw leave angry and the money it spent on ingredients. The server keeps per player who was served and who left
angry and checks the serves (`Table.report`): a customer only once, not before they came, not after their patience
ran out, not in the future – and the stand must have been able to make it: every serve books its foods step by step on
the earliest free place of each station (a food made ahead may wait at most HOLD seconds), the last step must be done
by the serve. A customer whose patience ran out without a valid serve is angry – the server decides that itself FINAL
seconds later (the app may say so earlier; that only counts against itself). The money spent counts at least the
ingredients of every served food (the app may report more – burnt and cold food – never less).
Coins (setting `game_rewards["snack"]`): places 1–3, only people of the family at a family table with at least two of
them – never alone; paid once (flag `paid`, a unique ledger `ref` per player). The winners get the «No. 1» hat.
Bots (easy / normal / hard) work through the customers in order with a time per food, a reaction time and sometimes
forget a part (that costs them time and ingredients); hopeless customers they let go – so they fail when it gets busy.
"""
from __future__ import annotations

import json
import math
import random
import secrets
import time

from .cardgames import BOTS, CardGames
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .running import win_reason

KIND = "snack"
TITLE = "Snack Rush"
EMOJI = "🍔"
MAX_PLAYERS = 6
LEVELS = ("easy", "normal", "hard")
MODES = ("t3", "t5", "t8")
LIMITS = (0, 3, 5, 8)
FOOD_KEYS = ("burger", "hotdog", "fries", "drink", "pizza", "icecream")
DEFAULTS = {"bots": 0, "level": "normal", "mode": "t5", "limit": 0, "foods": ",".join(FOOD_KEYS)}

# ---------------------------------------------------------------- the kitchen (the same numbers in web/snack.js)
# the steps of every food: (station, seconds)
FOODS = {
    "burger": (("grill", 4.0), ("prep", 2.0)),
    "hotdog": (("pot", 3.0), ("prep", 1.5)),
    "fries": (("fryer", 5.0), ("prep", 1.0)),
    "drink": (("drinks", 3.0),),
    "pizza": (("oven", 6.0),),
    "icecream": (("ice", 2.0),),
}
PRICE = {"burger": 8, "hotdog": 6, "fries": 4, "drink": 3, "pizza": 7, "icecream": 4}     # 💰 a customer pays per food
COST = {"burger": (2, 1), "hotdog": (2, 1), "fries": (1, 0), "drink": (1,), "pizza": (3,), "icecream": (1,)}   # 💰 per step
TIP = {3: 3, 2: 1, 1: 0}     # 💰 tip by stars
STATIONS = {"grill": 2, "pot": 2, "fryer": 2, "drinks": 2, "oven": 2, "ice": 2, "prep": 3}     # places per station
SPOIL = {"grill": 4.0, "fryer": 4.0, "oven": 5.0, "ice": 6.0}     # done and left there this long: burnt / melted
SHELF = 8                    # ready foods waiting on the shelf
SHELF_COLD = 25.0            # a food on the shelf longer than this is cold – into the bin
HOLD = 90.0                  # the server: a food may have been made at most this long before it was served
TOL = 0.6                    # seconds of tolerance (clocks, rounding)
COUNTDOWN = 3.0              # seconds from the start to game time 0
FIRST = 1.5                  # the first customer
FINAL = 4.0                  # the server decides «angry» this long after the patience ran out
LATE = 8.0                   # a serve reported this long after it happened is too late
STALE = 20.0                 # a silent app for this long: out (when `limit` is on)
GRACE = 1.0                  # nobody left in: the game ends this much later
MAX_T = 1200.0               # safety: 20 minutes
COUNTER = 4                  # customers at the counter (the others wait in the line)
RAMP = 240.0                 # seconds until the full rush (and after it a little more)
LEVEL = {"easy": (8.5, 40.0), "normal": (7.0, 32.0), "hard": (5.5, 26.0)}     # gap between customers, patience (s)
DURATION = {"t3": 180.0, "t5": 300.0, "t8": 480.0}
# bots: seconds of work per food, reaction time, chance to forget a part, timing noise σ
BOT_SKILL = {"easy": (3.6, 2.8, 0.18, 1.6), "normal": (2.6, 1.8, 0.1, 1.1), "hard": (1.8, 1.0, 0.05, 0.7)}
VIEW_AHEAD = 25.0            # the app gets the customers coming in the next seconds


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def chain(food: str) -> float:
    """The shortest time a food needs (its steps one after the other)."""
    return sum(d for _, d in FOODS[food])


def cost(food: str, level: str) -> int:
    """The ingredients of a whole food – half (rounded down per step) on «easy»."""
    return sum(c // 2 if level == "easy" else c for c in COST[food])


def pay(order: list[str], st: int) -> int:
    """What a served customer pays: the prices of the order and the tip."""
    return sum(PRICE[f] for f in order) + TIP.get(st, 0)


def foods_of(rules: dict) -> list[str]:
    want = [f.strip() for f in str((rules or {}).get("foods") or "").split(",")]
    out = [f for f in FOOD_KEYS if f in want]
    return out or list(FOOD_KEYS)


def customers(seed: int, level: str, foods: list[str], upto: float) -> list[tuple[float, float, list[str]]]:
    """The customers up to this game time: (arrival, patience, order). The same seed gives the same customers – a longer
    stream keeps the indexes (every customer takes the same random numbers)."""
    rnd = random.Random(seed)
    g0, p0 = LEVEL.get(level, LEVEL["normal"])
    t, out = FIRST, []
    while t <= upto:
        x = min(1.0, t / RAMP)
        late = max(0.0, (t - RAMP) / 120)
        r1, r2, r3 = rnd.random(), rnd.random(), rnd.random()
        n = 1 + (r1 < 0.2 + 0.5 * x) + (r2 < 0.04 + 0.36 * x)
        picks = [foods[int(rnd.random() * len(foods)) % len(foods)] for _ in range(3)][:n]
        order = sorted(picks, key=FOOD_KEYS.index)
        p = p0 * (1 - 0.35 * x) / (1 + 0.15 * late) + 4 * n + max(chain(f) for f in order)
        out.append((round(t, 2), round(p, 2), order))
        gap = g0 * (1 - 0.45 * x) / (1 + 0.25 * late) * (0.7 + 0.6 * r3) * (0.8 + 0.2 * n)
        t += max(1.2, gap)
    return out


def stars(a: float, p: float, ts: float) -> int:
    """1–3 stars: the more patience left, the more."""
    left = 1 - (ts - a) / p
    return 3 if left > 0.6 else 2 if left > 0.3 else 1


def book(free: dict, order: list[str], ts: float) -> bool:
    """Could the stand have made this order by ts? Every food takes the earliest free place of each of its stations,
    step after step (made at most HOLD s before). Changes `free` (lists of free-from times per station) only on success."""
    trial = {k: list(v) for k, v in free.items()}
    for f in sorted(order, key=chain, reverse=True):
        ready = max(0.0, ts - HOLD)
        for station, d in FOODS[f]:
            slots = trial.setdefault(station, [0.0] * STATIONS[station])
            k = min(range(len(slots)), key=lambda j: slots[j])
            start = max(slots[k], ready)
            slots[k] = ready = start + d
        if ready > ts + TOL:
            return False
    free.clear()
    free.update(trial)
    return True


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now
        self._cust = None

    @property
    def r(self) -> dict:
        return self.st["rules"]

    @property
    def level(self) -> str:
        return self.r.get("level", "normal")

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    def seat_of(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def gt(self) -> float:
        return self.now() - self.st["t0"]

    def custs(self, upto: float) -> list:
        if self._cust is None or self._cust[0] < upto:
            u = upto + 120
            self._cust = (u, customers(self.st["seed"], self.level, foods_of(self.r), u))
        return self._cust[1]

    def timed(self) -> float:
        return DURATION.get(self.r.get("mode"), DURATION["t5"])

    def setup(self, seed: int | None = None) -> None:
        ids = self.order()
        if not 1 <= len(ids) <= MAX_PLAYERS:
            raise CommunityError("The table is full")
        self.st.update(phase="play", seed=seed if seed is not None else secrets.randbelow(2 ** 31 - 1) + 1, t0=self.now() + COUNTDOWN,
                       ranking=None, places=None, complete=False, end_t=None,
                       run={pid: {"served": {}, "angry": {}, "out": None, "t": -COUNTDOWN, "seen": self.now(), "free": {},
                                  "spent": 0, "waste": [], "next": 0, "busy": 0.0} for pid in ids})

    # ---------- counting (at a game time)
    def served(self, pid: str, t: float | None = None) -> list:
        """[(index, time, stars, paid, ingredients)] served up to t."""
        s = self.st["run"][pid]["served"]
        return [(int(i), *v) for i, v in s.items() if t is None or v[0] <= t]

    def angry(self, pid: str, t: float | None = None) -> int:
        return sum(1 for v in self.st["run"][pid]["angry"].values() if t is None or v <= t)

    def money(self, pid: str, t: float | None = None) -> tuple[int, int]:
        """(earned, spent) up to t: a person's spent money is what the app reported, at least the ingredients of the
        served food; a bot's is the ingredients of its served food and its waste."""
        sv, r, p = self.served(pid, t), self.st["run"][pid], self.seat_of(pid) or {}
        earned, need = sum(x[3] for x in sv), sum(x[4] for x in sv)
        if p.get("bot"):
            return earned, need + sum(a for tw, a in r["waste"] if t is None or tw <= t)
        return earned, max(int(r.get("spent", 0)), need)

    def till(self, pid: str, t: float | None = None) -> int:
        e, s = self.money(pid, t)
        return e - s

    def alive(self, t: float | None = None) -> list[str]:
        run = self.st["run"]
        return [p for p in self.order() if run[p]["out"] is None or (t is not None and run[p]["out"] > t)]

    def _check_out(self, r: dict) -> None:
        """Rule `limit` on: the `limit`-th angry customer sends you out (at the moment that customer left)."""
        lim = int(self.r.get("limit", 0) or 0)
        if not lim or r["out"] is not None:
            return
        times = sorted(r["angry"].values())
        if len(times) >= lim:
            r["out"] = round(times[lim - 1], 3)

    # ---------- what an app reports
    def report(self, pid: str, t=None, serves=(), angry=(), spent=None) -> list[int]:
        """The app of this player: its game time, customers served [[index, time]], customers that left angry [index],
        the money spent on ingredients so far. Answers with the indexes of the serves that were refused."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        r = self.st["run"].get(pid)
        p = self.seat_of(pid)
        if r is None or not p or p.get("bot"):
            raise CommunityError("You are not at this table")
        now_t = self.gt()
        r["seen"] = self.now()
        refused = []
        if r["out"] is not None and r["out"] <= now_t:
            return refused

        def num(x) -> float | None:
            try:
                x = float(x)
            except (TypeError, ValueError):
                return None
            return x if math.isfinite(x) else None
        tt = num(t)
        if tt is not None and -COUNTDOWN - 1 <= tt <= now_t + 1.0:
            r["t"] = max(r["t"], tt)
        sp = num(spent)
        if sp is not None and 0 <= sp <= 100000:                  # only ever more (it only counts against the app)
            r["spent"] = max(int(r.get("spent", 0)), int(sp))
        cs = self.custs(now_t + 2)
        items = []
        for s in list(serves)[:30]:
            try:
                i, ts = int(s[0]), num(s[1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            if ts is not None:
                items.append((ts, i))
        for ts, i in sorted(items):
            ok = (0 <= i < len(cs) and str(i) not in r["served"] and str(i) not in r["angry"]
                  and now_t - LATE <= ts <= now_t + 1.0 and ts >= 0)
            if ok:
                a, pat, order = cs[i]
                ok = a - TOL <= ts <= a + pat + TOL and (r["out"] is None or ts < r["out"]) and book(r["free"], order, ts)
            if ok:
                sr = stars(a, pat, ts)
                r["served"][str(i)] = [round(ts, 3), sr, pay(order, sr), sum(cost(f, self.level) for f in order)]
            else:
                refused.append(i)
        for i in list(angry)[:30]:
            try:
                i = int(i)
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(cs) and str(i) not in r["served"] and str(i) not in r["angry"]:
                a, pat, _ = cs[i]
                if now_t >= a + pat - TOL:
                    r["angry"][str(i)] = round(a + pat, 3)
        self._check_out(r)
        self._maybe_end()
        return refused

    # ---------- the clock: angry customers, bots, silent apps, the end
    def tick(self) -> bool:
        if self.st.get("phase") != "play":
            return False
        before = json.dumps(self.st["run"], sort_keys=True)
        now_t = self.gt()
        cs = self.custs(now_t + 2)
        for p in self.st["players"]:
            r = self.st["run"][p["id"]]
            if p.get("bot"):
                self._bot(p, r, cs, now_t)
                continue
            for i, (a, pat, _) in enumerate(cs):                 # patience gone and no serve came: angry
                if a + pat + FINAL >= now_t:
                    break
                if str(i) not in r["served"] and str(i) not in r["angry"]:
                    r["angry"][str(i)] = round(a + pat, 3)
            self._check_out(r)
            if self.r.get("limit") and r["out"] is None and now_t > 0 and self.now() - r.get("seen", 0) > STALE:
                r["out"] = round(max(0.0, min(now_t, r["t"])), 3)          # the app is gone: out
        self._maybe_end()
        return self.st.get("phase") != "play" or json.dumps(self.st["run"], sort_keys=True) != before

    def _bot(self, p: dict, r: dict, cs: list, now_t: float) -> None:
        """A bot plans every customer when they come: in order, with its working time – so the others see it serve."""
        work, react, forget, noise = BOT_SKILL.get(p.get("level"), BOT_SKILL["normal"])
        while r["next"] < len(cs) and cs[r["next"]][0] <= now_t:
            i = r["next"]
            r["next"] += 1
            if r["out"] is not None:
                continue
            a, pat, order = cs[i]
            start = max(a + react * (0.6 + 0.8 * self.rng.random()), r["busy"])
            w = work * len(order)
            longest = max(order, key=chain)
            if self.rng.random() < forget:                       # forgot a part (or burnt it) – made again
                w += chain(longest)
                r["waste"].append([round(start + w, 3), cost(longest, self.level)])
            ts = start + max(w, chain(longest) + 0.8) + abs(self.rng.gauss(0, noise))
            if ts > a + pat:                                       # too late: the customer leaves angry
                r["angry"][str(i)] = round(a + pat, 3)
                r["busy"] = max(r["busy"], min(ts, a + pat) - w * 0.5)   # a part of the work was in vain
                if r["busy"] > start:
                    r["waste"].append([round(a + pat, 3), cost(order[0], self.level)])
                self._check_out(r)
            else:
                sr = stars(a, pat, ts)
                r["served"][str(i)] = [round(ts, 3), sr, pay(order, sr), sum(cost(f, self.level) for f in order)]
                r["busy"] = start + w

    def _maybe_end(self) -> None:
        if self.st.get("phase") != "play":
            return
        now_t = self.gt()
        run, people = self.st["run"], [p["id"] for p in self.st["players"] if not p.get("bot")]
        if now_t >= min(self.timed(), MAX_T):                         # time is up
            self.st["complete"] = True
            self._finish(min(self.timed(), MAX_T))
            return
        alive = self.alive(now_t)
        if not [p for p in people if p in alive]:                     # rule `limit`: no person is left in
            outs = [run[p]["out"] for p in people if run[p]["out"] is not None]
            if now_t >= max(outs, default=0.0) + GRACE:
                self.st["complete"] = True
                self._finish(now_t)

    def rank_key(self, pid: str, t: float):
        sv = self.served(pid, t)
        return (self.till(pid, t), len(sv), sum(x[2] for x in sv), -self.angry(pid, t))

    def _finish(self, end_t: float) -> None:
        order, run = self.order(), self.st["run"]
        end_t = round(max(0.0, end_t), 3)
        for p in order:                                   # what a bot planned after the end does not count
            r = run[p]
            r["served"] = {i: v for i, v in r["served"].items() if v[0] <= end_t}
            r["angry"] = {i: v for i, v in r["angry"].items() if v <= end_t}
            r["waste"] = [w for w in r["waste"] if w[0] <= end_t]
            if r["out"] is not None and r["out"] > end_t:
                r["out"] = None
        self.st["end_t"] = end_t
        keys = {p: self.rank_key(p, end_t) for p in order}
        self.st["places"] = places(order, keys)
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st["scores"] = {p: self.till(p, end_t) for p in order}
        self.st["served"] = {p: len(run[p]["served"]) for p in order}
        self.st["stars"] = {p: sum(v[1] for v in run[p]["served"].values()) for p in order}
        self.st.update(phase="done", finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: ranked as it stands (no coins – see coins_for)."""
        if self.st.get("phase") == "play":
            self._finish(max(0.0, self.gt()))


# ================================================================ the games in the database (table card_game, kind "snack")
class Snack(CardGames):
    """The family table / own tables – the same rows and lobby as the card games (summary, may_lead)."""

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
            if isinstance(v, int):
                try:
                    out[k] = int(x)
                except (TypeError, ValueError):
                    out[k] = v
            else:
                out[k] = ",".join(x) if k == "foods" and isinstance(x, (list, tuple)) else str(x)
        out["bots"] = max(0, min(MAX_PLAYERS - 1, out["bots"]))
        out["level"] = out["level"] if out["level"] in LEVELS else "normal"
        out["mode"] = out["mode"] if out["mode"] in MODES else "t5"
        out["limit"] = out["limit"] if out["limit"] in LIMITS else 0
        out["foods"] = ",".join(foods_of(out))
        return out

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    def best(self, pid) -> int:
        return int((self.db.get_setting("snack_best") or {}).get(str(pid), 0) or 0)

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status != "done" or st.get("paid") or st.get("places") is None:
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        best = dict(self.db.get_setting("snack_best") or {})       # the personal best (the till)
        records = {}
        for p in st["players"]:
            if p.get("bot") or p.get("guest"):
                continue
            sc = int((st.get("scores") or {}).get(p["id"], 0))
            if sc > int(best.get(p["id"], 0) or 0):
                best[p["id"]] = sc
                records[p["id"]] = True
        if records:
            self.db.set_setting("snack_best", best)
        st["records"] = records
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        self._payout(KIND, row["id"], coins, lambda pid: win_reason(KIND, st["places"][pid]))
        if len(st["players"]) >= 2:
            self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history:
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]), "score": (st.get("scores") or {}).get(p["id"], 0),
                        "served": (st.get("served") or {}).get(p["id"], 0), "stars": (st.get("stars") or {}).get(p["id"], 0), "record": bool(records.get(p["id"])),
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

    def _deal(self, st: dict) -> None:
        humans = [p for p in st["players"] if not p.get("bot")]
        n = max(0, min(st["rules"]["bots"], MAX_PLAYERS - len(humans)))
        st["players"] = humans + self._bots(st, n)
        st.pop("bot_pool", None)
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
            if solo:                                      # alone: the countdown starts right away
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

    def report(self, pid: int, t=None, serves=(), angry=(), spent=None) -> dict | None:
        """The app of this player reports its serves and angry customers (only its own stand) – answers with the state."""
        refused = []
        with self.lock:
            row = self._row(KIND, pid)
            if row:
                st = json.loads(row["state"])
                if st["phase"] == "lobby":
                    raise CommunityError("The game has not started yet")
                if st["phase"] == "play":
                    t_ = self.table(st)
                    if str(pid) in st["run"]:
                        st["run"][str(pid)]["seen"] = self.now()      # alive before the clock looks for silent apps
                    if st["phase"] == "play":
                        refused = t_.report(str(pid), t, serves, angry, spent)
                    t_.tick()
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
        if not row:                                       # over in the meantime: the result
            return self.state(KIND, pid)
        return {**self._view(row, st, str(pid)), "refused": refused}

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
        base = {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph,
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "joined": joined,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2, "max_players": MAX_PLAYERS,
                "best": self.best(me) if joined else 0, "now": self.now()}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            return {**base, "players": players, "bots": max(0, min(st["rules"]["bots"], MAX_PLAYERS - len(players)))}
        t = self.table(st)
        done = ph == "done"
        now_t = st.get("end_t") if done and st.get("end_t") is not None else t.gt()
        run, coins, pl = st["run"], st.get("coins") or {}, st.get("places") or {}
        players = []
        for p in st["players"]:
            r = run[p["id"]]
            sv = t.served(p["id"], now_t)
            out = r["out"] if r["out"] is not None and r["out"] <= now_t else None
            players.append({"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                            "guest": bool(p.get("guest")), "color": p.get("color"), "level": p.get("level"),
                            "served": len(sv), "stars": sum(x[2] for x in sv), "till": t.till(p["id"], now_t), "angry": t.angry(p["id"], now_t), "out": out,
                            "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0), "record": bool((st.get("records") or {}).get(p["id"]))})
        out = {**base, "players": players, "me": me if joined else None, "t0": st["t0"], "end_t": st.get("end_t"),
               "ranking": st.get("ranking"), "complete": bool(st.get("complete")), "now_t": now_t,
               "duration": t.timed(), "limit": int(st["rules"].get("limit", 0) or 0), "foods": foods_of(st["rules"])}
        if joined and not done:
            r = run[me]
            cs = t.custs(max(0.0, now_t) + VIEW_AHEAD)
            lo = max(0.0, now_t) - 120
            out["customers"] = [[i, a, pat, order] for i, (a, pat, order) in enumerate(cs) if a <= now_t + VIEW_AHEAD and a + pat >= lo]
            out["mine"] = {"served": dict(r["served"]), "angry": sorted(int(i) for i in r["angry"]), "spent": int(r.get("spent", 0))}
        return out

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
