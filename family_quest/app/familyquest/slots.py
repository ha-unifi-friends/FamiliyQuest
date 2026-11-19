"""Game corner: the one-armed bandit (slot machine).

A child gets the machine like every game with a price (gamepasses.py: DEFAULT_PRICE 250 coins to buy it once – the
parents can change the price, set 0 or change the rent – default 20 coins a day), then plays for 1 coin, at most
PLAYS_PER_DAY times a day. Before that a free try (gamepasses.py `preview`, default 1) is one spin.
Whoever bought it before (unlock `slot_machine`, 150 coins) keeps it (db migration 35).

The reels are drawn here on the server (secrets) – the app only shows them. Three reels with weighted symbols and a
fixed pay table. The parents set the luck 1–10 (parent area › Games › One-armed bandit, default 5): the outcome
(which line wins, or nothing) is drawn first, with the win chances of the plain reels scaled so the machine pays back
target_return(luck) of the bets on average – 5: 92 % like a typical casino machine, 10: 120 %, 1: 60 %. The reels are
then drawn to show that outcome.
"""
from __future__ import annotations

import functools
import itertools
import secrets

from .i18n import _t

ITEM = "slot_machine"           # the old unlock (bought before migration 35)
BET = 1
PLAYS_PER_DAY = 3
DEFAULT_LUCK = 5
# symbol: weight per reel (all three reels alike)
WEIGHTS = {"cherry": 4, "lemon": 7, "orange": 7, "bell": 5, "star": 2, "seven": 1}
EMOJI = {"cherry": "🍒", "lemon": "🍋", "orange": "🍊", "bell": "🔔", "star": "⭐", "seven": "7️⃣"}
THREE = {"seven": 100, "star": 40, "bell": 20, "orange": 10, "lemon": 8, "cherry": 5}      # three alike
CHERRIES = {2: 2, 1: 1}                                                                     # cherries anywhere (not three)
_RNG = secrets.SystemRandom()


def payout(reels: list[str]) -> int:
    if reels[0] == reels[1] == reels[2]:
        return THREE[reels[0]]
    return CHERRIES.get(reels.count("cherry"), 0)


def _outcome(reels) -> str:
    if reels[0] == reels[1] == reels[2]:
        return "three:" + reels[0]
    n = reels.count("cherry")
    return f"cherry:{n}" if n else "none"


@functools.lru_cache(maxsize=1)
def _plain() -> dict[str, float]:
    """Probability of each outcome with the plain weighted reels."""
    total = sum(WEIGHTS.values()) ** 3
    out: dict[str, float] = {}
    for r in itertools.product(WEIGHTS, repeat=3):
        k = _outcome(r)
        out[k] = out.get(k, 0) + WEIGHTS[r[0]] * WEIGHTS[r[1]] * WEIGHTS[r[2]] / total
    return out


def _pay(kind: str) -> int:
    if kind.startswith("three:"):
        return THREE[kind[6:]]
    if kind.startswith("cherry:"):
        return CHERRIES[int(kind[7:])]
    return 0


def expected_return() -> float:
    """Average coins back per coin bet with the plain reels (about 98.6 %) – the base the luck scales."""
    return sum(p * _pay(k) for k, p in _plain().items())


def clean_luck(v) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError(_t("Luck: 1 to 10")) from None
    if not 1 <= n <= 10:
        raise ValueError(_t("Luck: 1 to 10"))
    return n


def target_return(luck: int = DEFAULT_LUCK) -> float:
    """Coins back per coin bet: 1 → 60 %, 5 → 92 % (a typical casino machine), 10 → 120 %; straight lines between."""
    luck = clean_luck(luck)
    return (60 + (luck - 1) * 8) / 100 if luck <= 5 else (92 + (luck - 5) * 5.6) / 100


@functools.lru_cache(maxsize=16)
def _outcomes(luck: int) -> tuple:
    plain = _plain()
    f = target_return(luck) / expected_return()
    out = {k: p * f for k, p in plain.items() if k != "none"}
    out["none"] = 1 - sum(out.values())
    return tuple(out), tuple(out.values())


def outcomes(luck: int = DEFAULT_LUCK) -> dict[str, float]:
    """Probability of each outcome at this luck: every win scaled by the same factor, the rest is «nothing»."""
    return dict(zip(*_outcomes(clean_luck(luck))))


def reels_for(kind: str, rng=_RNG) -> list[str]:
    """Three reels that show this outcome (the other symbols drawn with the reel weights)."""
    others = [s for s in WEIGHTS if s != "cherry"]
    pick = lambda: rng.choices(others, weights=[WEIGHTS[s] for s in others])[0]   # noqa: E731
    if kind.startswith("three:"):
        return [kind[6:]] * 3
    if kind.startswith("cherry:"):
        n = int(kind[7:])
        while True:
            r = ["cherry" if rng.random() < 0.5 else pick() for _ in range(3)]
            if r.count("cherry") == n:
                return r
    while True:
        r = [pick() for _ in range(3)]
        if not r[0] == r[1] == r[2]:
            return r


def spin_reels(luck: int = DEFAULT_LUCK, rng=_RNG) -> list[str]:
    kinds, weights = _outcomes(clean_luck(luck))
    kind = rng.choices(kinds, weights=weights)[0]
    return reels_for(kind, rng)


class SlotError(ValueError):
    pass


def payout(reels: list[str]) -> int:
    if reels[0] == reels[1] == reels[2]:
        return THREE[reels[0]]
    return CHERRIES.get(reels.count("cherry"), 0)


def expected_return() -> float:
    """Average coins back per coin bet (for the tests and the info text)."""
    import itertools
    total = sum(WEIGHTS.values()) ** 3
    return sum(WEIGHTS[a] * WEIGHTS[b] * WEIGHTS[c] * payout([a, b, c])
               for a, b, c in itertools.product(WEIGHTS, repeat=3)) / total


def _draw(rng=secrets.SystemRandom()) -> str:
    return rng.choices(list(WEIGHTS), weights=list(WEIGHTS.values()))[0]


class Slots:
    def __init__(self, db, rewards):
        self.db = db
        self.rewards = rewards
        self.spin_reels = spin_reels                   # the tests set fixed reels
        self.settings = lambda: {"price": 250, "rent": 0, "period": "week", "luck": DEFAULT_LUCK}   # services: games_access()["slots"]
        self.unlocked = lambda pid: False              # services: bought / rented (gamepasses.py), parents always
        self.tries = lambda pid: 0                     # services: free tries left before buying / renting
        self.try_play = lambda pid: False              # services: use one free try (True: there was one)

    def owned(self, pid: int) -> bool:
        return bool(self.unlocked(pid))

    def plays_today(self, pid: int) -> int:
        return int(self.db.val("""SELECT COUNT(*) FROM ledger WHERE profile_id=? AND event='slots_bet'
                                  AND date(at)=date('now','localtime')""", pid, default=0))

    def state(self, pid: int) -> dict:
        a = self.settings()
        owned = self.owned(pid)
        return {"owned": owned, "tries_left": 0 if owned else self.tries(pid),
                "price": int(a.get("price") or 0), "rent": int(a.get("rent") or 0),
                "period": a.get("period") or "week", "bet": BET, "max": PLAYS_PER_DAY,
                "left": max(0, PLAYS_PER_DAY - self.plays_today(pid)),
                "coins": self.rewards.available(pid),
                "symbols": EMOJI, "three": THREE, "cherries": CHERRIES}

    def spin(self, pid: int) -> dict:
        with self.db.tx():                      # check and book in one step – a double tap cannot play twice
            owned = self.owned(pid)
            if not owned and not self.tries(pid):
                raise SlotError("Buy the slot machine first")
            if self.plays_today(pid) >= PLAYS_PER_DAY:
                raise SlotError("That was all for today – come back tomorrow")
            if self.rewards.available(pid) < BET:
                raise SlotError("Not enough coins")
            if not owned and not self.try_play(pid):       # a free try: one spin (counted in this transaction)
                raise SlotError("Buy the slot machine first")
            reels = list(self.spin_reels(int(self.settings().get("luck") or DEFAULT_LUCK)))
            win = payout(reels)
            self.rewards.book(pid, "coins", -float(BET), "slots_bet", _t("One-armed bandit"), "slots")
            if win:
                self.rewards.book(pid, "coins", float(win), "slots_win", _t("One-armed bandit {0}").replace("{0}", "".join(EMOJI[r] for r in reels)), "slots")
        return {**self.state(pid), "reels": reels, "win": win, "jackpot": win >= THREE["star"]}
