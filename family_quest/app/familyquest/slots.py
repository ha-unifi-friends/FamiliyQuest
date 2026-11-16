"""Game corner: the one-armed bandit (slot machine).

A child buys the machine once (PRICE coins, unlock `slot_machine`), then plays for 1 coin, at most PLAYS_PER_DAY times
a day. The reels are drawn here on the server (secrets) – the app only shows them. Three reels with weighted symbols;
the pay table returns about 98.6 % of the bets on average (real machines: about 88–95 %) and a bit less than half of
the spins win something.
"""
from __future__ import annotations

import secrets

from .i18n import _t

ITEM = "slot_machine"
PRICE = 150
BET = 1
PLAYS_PER_DAY = 3
# symbol: weight per reel (all three reels alike)
WEIGHTS = {"cherry": 4, "lemon": 7, "orange": 7, "bell": 5, "star": 2, "seven": 1}
EMOJI = {"cherry": "🍒", "lemon": "🍋", "orange": "🍊", "bell": "🔔", "star": "⭐", "seven": "7️⃣"}
THREE = {"seven": 100, "star": 40, "bell": 20, "orange": 10, "lemon": 8, "cherry": 5}      # three alike
CHERRIES = {2: 2, 1: 1}                                                                     # cherries anywhere (not three)


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
        self.draw = _draw

    def owned(self, pid: int) -> bool:
        return bool(self.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item=?", pid, ITEM))

    def plays_today(self, pid: int) -> int:
        return int(self.db.val("""SELECT COUNT(*) FROM ledger WHERE profile_id=? AND event='slots_bet'
                                  AND date(at)=date('now','localtime')""", pid, default=0))

    def state(self, pid: int) -> dict:
        return {"owned": self.owned(pid), "price": PRICE, "bet": BET, "max": PLAYS_PER_DAY,
                "left": max(0, PLAYS_PER_DAY - self.plays_today(pid)),
                "coins": self.rewards.balance(pid, "coins"),
                "symbols": EMOJI, "three": THREE, "cherries": CHERRIES}

    def buy(self, pid: int) -> dict:
        with self.db.tx():
            if self.owned(pid):
                raise SlotError("You have the slot machine already")
            if self.rewards.balance(pid, "coins") < PRICE:
                raise SlotError("Not enough coins")
            self.rewards.book(pid, "coins", -float(PRICE), "slots_buy", _t("One-armed bandit"), f"slots:buy:{pid}")
            self.db.x("INSERT INTO unlock(profile_id, item) VALUES(?,?)", pid, ITEM)
        return self.state(pid)

    def spin(self, pid: int) -> dict:
        with self.db.tx():                      # check and book in one step – a double tap cannot play twice
            if not self.owned(pid):
                raise SlotError("Buy the slot machine first")
            if self.plays_today(pid) >= PLAYS_PER_DAY:
                raise SlotError("That was all for today – come back tomorrow")
            if self.rewards.balance(pid, "coins") < BET:
                raise SlotError("Not enough coins")
            reels = [self.draw() for _ in range(3)]
            win = payout(reels)
            self.rewards.book(pid, "coins", -float(BET), "slots_bet", _t("One-armed bandit"), "slots")
            if win:
                self.rewards.book(pid, "coins", float(win), "slots_win", _t("One-armed bandit") + f" {''.join(EMOJI[r] for r in reels)}", "slots")
        return {**self.state(pid), "reels": reels, "win": win, "jackpot": win >= THREE["star"]}
