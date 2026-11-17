"""«Dorfmarkt» – a property-trading board game in a Swiss village (generic mechanics of the genre, own board and names).

Everybody plays on their own device (family table, guests via QR code) or a child plays alone against bots – the
tables live in the `card_game` table with kind "dorfmarkt" (lobby, join, summary, may_lead from cardgames.CardGames,
like «Heimwärts»). The whole game is in the state of the row, so a game survives a restart; who leads may pause it.

Board: a square ring of 36 fields (4 corners + 8 per side), clockwise from the «Markttag» corner:
  0 Markttag (passing or landing: +Markttag money) · 9 Gemeindehaus (just visiting, or sitting in the
  «Gemeindeversammlung») · 18 Dorfplatz (free) · 27 «Ab in die Gemeindeversammlung».
  20 village shops / places in 8 colour groups (2–3 each), 4 «Village bus» stops, 2 works (water, electricity),
  2 «Zufall» and 2 «Dorfkasse» card fields, 2 fees («Gemeindesteuer», «Vereinsbeitrag»).
A turn: roll 2 dice (on the server). Doubles roll again; the third double in a row goes straight into the
Gemeindeversammlung. Landing on a free field: buy it at its price or leave it (rule `auction`: then an open auction –
everybody raises the current price by 10, 25 or 50; 5 seconds after the last bid the highest bidder gets the field). Landing on a field of another player: pay the rent – double for an
unbuilt field when the owner has the whole colour group; with «Marktstände» (1–4, built evenly, only with the whole
group) and a «Markthalle» (the 5th step) much more. Village bus: 25 / 50 / 100 / 200 for 1–4 stops of the owner. Works:
4× the dice (10× with both). Rule `mortgage`: a field without buildings can be mortgaged for half its price (no rent
while mortgaged), paid back with 10 % more.
Gemeindeversammlung: pay 50 Taler, use a «free» card or try to roll a double (3 tries; after the third: pay and go).
Trading: any player may offer fields (without buildings in their group) and Taler for fields and Taler of another
player – accept or decline (bots decide by the value).
Debts: who cannot pay sells (half the building price) and mortgages – or is bankrupt: all goes to the creditor
(to the bank: the fields are free again).
End (rule `mode`): "rounds" (default 30 rounds) or "time" (minutes) – then the richest (Taler + fields + buildings)
wins; "classic": until one is left. Always over when only one player (or no person) is left.
Coins (setting `game_rewards["dorfmarkt"]`): places 1–3, only people of the family at a family table with at least two
of them – never alone against bots; paid once (flag `paid`, a unique ledger `ref` per player), only for a game played
to the end (not ended early by who leads).
Bots (easy / normal / hard) buy, build, pay out of the meeting, bid and accept fair trades, with a reaction time (bot_ms).
"""
from __future__ import annotations

import json
import random
import secrets
import time

from .cardgames import BOTS, BOT_DELAY, CardGames, bot_delay, apply_starter, starter_mode
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of

KIND = "dorfmarkt"
TITLE = "Dorfmarkt"
EMOJI = "🏘️"
MAX_PLAYERS = 6
LEVELS = ("easy", "normal", "hard")
MODES = ("rounds", "time", "classic")
DEFAULTS = {"bots": 2, "level": "normal", "bot_ms": 1400, "mode": "rounds", "rounds": 30, "minutes": 60,
            "auction": False, "mortgage": True, "money": 1500}
N = 36
START, JAIL, FREE, GOJAIL = 0, 9, 18, 27
BAIL = 50
MARKTTAG_MONEY = 200
MAX_DOUBLES = 3
MEETING_TRIES = 3
AUCTION_SECONDS = 5                    # the auction ends 5 seconds after the last bid
BID_STEPS = (10, 25, 50)               # a bid raises the current price by one of these
MAX_TURNS = 3000              # safety: a game that never ends is decided by the riches
RENT_STEPS = (1, 5, 15, 40, 50, 60)          # rent × base for 0, 1–4 stands, the Markthalle
GROUP_HOUSE = (50, 50, 100, 100, 150, 150, 200, 200)


def _p(key, g, price):
    return {"t": "prop", "key": key, "g": g, "price": price}


FIELDS = [
    {"t": "start", "key": "markttag"},
    _p("farmshop", 0, 60), {"t": "chest", "key": "dorfkasse"}, _p("beehouse", 0, 60),
    {"t": "tax", "key": "tax", "amount": 100}, {"t": "bus", "key": "bus_school", "price": 200},
    _p("icecream", 1, 100), {"t": "chance", "key": "zufall"}, _p("kiosk", 1, 120),
    {"t": "jail", "key": "townhall"},
    _p("bakery", 2, 140), {"t": "util", "key": "power", "price": 150}, _p("pastry", 2, 140), _p("cheese", 2, 160),
    {"t": "bus", "key": "bus_church", "price": 200}, _p("bikeshop", 3, 180), {"t": "chest", "key": "dorfkasse"}, _p("carpenter", 3, 200),
    {"t": "free", "key": "square"},
    _p("pool", 4, 220), {"t": "chance", "key": "zufall"}, _p("minigolf", 4, 220), _p("climbing", 4, 240),
    {"t": "bus", "key": "bus_station", "price": 200}, _p("villageshop", 5, 260), _p("flowers", 5, 260), {"t": "util", "key": "water", "price": 150},
    {"t": "gojail", "key": "gomeeting"},
    _p("hairdresser", 6, 300), _p("bookshop", 6, 300), _p("toyshop", 6, 320), {"t": "bus", "key": "bus_alp", "price": 200},
    _p("inn", 7, 350), {"t": "tax", "key": "club", "amount": 75}, _p("chocolate", 7, 380), _p("watchmaker", 7, 400),
]
assert len(FIELDS) == N
for _i, _f in enumerate(FIELDS):
    if _f["t"] == "prop":
        base = max(2, round(_f["price"] / 14))
        _f["rent"] = [base * m for m in RENT_STEPS]
        _f["house"] = GROUP_HOUSE[_f["g"]]
GROUPS = [[i for i, f in enumerate(FIELDS) if f["t"] == "prop" and f["g"] == g] for g in range(8)]
BUSES = [i for i, f in enumerate(FIELDS) if f["t"] == "bus"]
UTILS = [i for i, f in enumerate(FIELDS) if f["t"] == "util"]
OWNABLE = [i for i, f in enumerate(FIELDS) if f["t"] in ("prop", "bus", "util")]

# the cards: (id, effect) – the texts are in the app (dorfmarkt.js)
CHANCE = [("z_markttag", ("goto", START)), ("z_postauto", ("bus",)), ("z_pool", ("goto", 19)), ("z_back3", ("back", 3)),
          ("z_snow", ("money", 50)), ("z_tyre", ("money", -15)), ("z_meeting", ("jail",)), ("z_free", ("free",)),
          ("z_sackrace", ("money", 100)), ("z_cleaning", ("repair", 25, 100)), ("z_watch", ("goto", 35)),
          ("z_icecream", ("each", -20))]
CHEST = [("d_counted", ("money", 150)), ("d_birthday", ("each", 10)), ("d_library", ("money", -20)), ("d_flea", ("money", 60)),
         ("d_markttag", ("goto", START)), ("d_free", ("free",)), ("d_meeting", ("jail",)), ("d_garden", ("money", 50)),
         ("d_music", ("money", -50)), ("d_grandma", ("money", 100)), ("d_trip", ("money", -40)), ("d_road", ("repair", 20, 60))]
CARDS = {cid: eff for cid, eff in CHANCE + CHEST}


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or secrets.SystemRandom()
        self.now = now

    @property
    def r(self) -> dict:
        return self.st["rules"]

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    def active(self) -> list[str]:
        out = self.st.get("out") or []
        return [p for p in self.order() if p not in out]

    def seat_of(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def is_bot(self, pid: str | None) -> bool:
        return bool((self.seat_of(pid or "") or {}).get("bot"))

    # ---------- the board
    def owner(self, f: int) -> str | None:
        return self.st["owner"].get(str(f))

    def builds(self, f: int) -> int:
        return int(self.st["build"].get(str(f), 0))

    def mortgaged(self, f: int) -> bool:
        return f in self.st["mortgaged"]

    def fields_of(self, pid: str) -> list[int]:
        return [f for f in OWNABLE if self.owner(f) == pid]

    def full_group(self, pid: str, g: int) -> bool:
        return all(self.owner(f) == pid for f in GROUPS[g])

    def group_built(self, f: int) -> bool:
        fd = FIELDS[f]
        return fd["t"] == "prop" and any(self.builds(x) for x in GROUPS[fd["g"]])

    def rent(self, f: int, dice_sum: int | None = None) -> int:
        fd, own = FIELDS[f], self.owner(f)
        if own is None or self.mortgaged(f):
            return 0
        if fd["t"] == "prop":
            b = self.builds(f)
            if b:
                return fd["rent"][b]
            return fd["rent"][0] * (2 if self.full_group(own, fd["g"]) else 1)
        if fd["t"] == "bus":
            n = sum(1 for x in BUSES if self.owner(x) == own)
            return 25 * 2 ** (n - 1)
        n = sum(1 for x in UTILS if self.owner(x) == own)
        if dice_sum is None:
            dice_sum = sum(self.st.get("dice") or [0])
        return dice_sum * (10 if n == 2 else 4)

    def worth(self, pid: str) -> int:
        w = self.st["money"].get(pid, 0)
        for f in self.fields_of(pid):
            fd = FIELDS[f]
            w += fd["price"] // 2 if self.mortgaged(f) else fd["price"]
            if fd["t"] == "prop":
                w += self.builds(f) * fd["house"]
        return w

    def raisable(self, pid: str) -> int:
        """Taler a player could still raise: sell all buildings (half), mortgage all fields (half, if the rule is on)."""
        n = 0
        for f in self.fields_of(pid):
            fd = FIELDS[f]
            if fd["t"] == "prop":
                n += self.builds(f) * fd["house"] // 2
            if self.r.get("mortgage") and not self.mortgaged(f):
                n += fd["price"] // 2
        return n

    # ---------- the game
    def setup(self) -> None:
        ids = self.order()
        if not 2 <= len(ids) <= MAX_PLAYERS:
            raise CommunityError("Add a bot or wait for a second player")
        chance, chest = [c for c, _ in CHANCE], [c for c, _ in CHEST]
        self.rng.shuffle(chance)
        self.rng.shuffle(chest)
        m = int(self.r.get("money") or 1500)
        self.st.update(phase="play", turn=ids[0], stage="roll", dice=None, roll_seq=0, doubles=0, round=1, turns=0,
                       money={p: m for p in ids}, pos={p: 0 for p in ids}, owner={}, build={}, mortgaged=[],
                       meeting={}, free={}, decks={"chance": chance, "chest": chest}, out=[], log=[], last=None,
                       trades=[], auction=None, debt_to=None, after_debt=None, ranking=None, places=None, complete=False,
                       started=self.now(), paused=False, paused_at=None, paused_total=0.0, turn_at=self.now(), seq=0)

    def _check(self, pid: str, stages: tuple | None = None, own_turn: bool = True) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        if self.st.get("paused"):
            raise CommunityError("The game is paused")
        if pid in (self.st.get("out") or []):
            raise CommunityError("You are out of the game")
        if own_turn and self.st.get("turn") != pid:
            raise CommunityError("It is not your turn")
        if stages and self.st.get("stage") not in stages:
            raise CommunityError("Not now")

    def _log(self, ev: dict) -> None:
        self.st["seq"] = self.st.get("seq", 0) + 1
        ev.update(t=self.now(), seq=self.st["seq"])
        self.st["last"] = ev
        log = self.st.setdefault("log", [])
        log.append(ev)
        del log[:-30]

    def elapsed(self) -> float:
        now = self.st.get("paused_at") or self.now()
        return max(0.0, now - self.st.get("started", now) - self.st.get("paused_total", 0.0))

    def time_left(self) -> int | None:
        if self.r.get("mode") != "time":
            return None
        return max(0, int(int(self.r.get("minutes") or 60) * 60 - self.elapsed()))

    # ---------- money
    def _pay(self, pid: str, amount: int, to: str | None = None) -> None:
        """pid pays amount to `to` (None: the bank). The money may go below 0 – then the debt is settled."""
        self.st["money"][pid] -= amount
        if to is not None:
            self.st["money"][to] += amount
        if self.st["money"][pid] < 0:
            self.st["debt_to"] = to

    def _settle_others(self) -> None:
        """Players (not on turn) below 0: sell and mortgage by themselves – or are bankrupt."""
        for p in list(self.active()):
            if p != self.st["turn"] and self.st["money"][p] < 0:
                self._liquidate(p)
                if self.st["money"][p] < 0:
                    self._bankrupt(p, self.st.get("debt_to"))

    def _settle(self, after: str) -> None:
        """After something was paid: the player on turn below 0 must raise money (stage «debt») or is bankrupt."""
        self._settle_others()
        if self.st.get("phase") != "play":
            return
        pid = self.st["turn"]
        if pid in (self.st.get("out") or []):
            return
        if self.st["money"][pid] < 0:
            if self.st["money"][pid] + self.raisable(pid) < 0:
                self._bankrupt(pid, self.st.get("debt_to"))
                return
            self.st.update(stage="debt", after_debt=after, turn_at=self.now())
            return
        self.st.update(stage=after, turn_at=self.now())

    def _debt_paid(self) -> None:
        if self.st.get("stage") == "debt" and self.st["money"][self.st["turn"]] >= 0:
            self.st.update(stage=self.st.get("after_debt") or "done", after_debt=None, turn_at=self.now())

    def _liquidate(self, pid: str) -> None:
        """Raise money by itself: sell the buildings (expensive groups last), then mortgage (cheapest first)."""
        while self.st["money"][pid] < 0:
            built = [f for f in self.fields_of(pid) if FIELDS[f]["t"] == "prop" and self.builds(f)]
            if not built:
                break
            f = max(built, key=lambda x: (self.builds(x), -FIELDS[x]["price"]))
            self._sell(pid, f)
        if self.r.get("mortgage"):
            for f in sorted(self.fields_of(pid), key=lambda x: FIELDS[x]["price"]):
                if self.st["money"][pid] >= 0:
                    break
                if not self.mortgaged(f) and not self.group_built(f):
                    self._mortgage(pid, f)

    def _bankrupt(self, pid: str, to: str | None) -> None:
        if to is not None and (to == pid or to in (self.st.get("out") or [])):
            to = None
        for f in self.fields_of(pid):                      # the buildings go back to the bank for half
            if FIELDS[f]["t"] == "prop" and self.builds(f):
                self.st["money"][pid] += self.builds(f) * FIELDS[f]["house"] // 2
                self.st["build"].pop(str(f), None)
        left = self.st["money"][pid]
        if to is not None:
            self.st["money"][to] += left                   # the creditor got the whole payment – the part that was not there goes back
            for f in self.fields_of(pid):
                self.st["owner"][str(f)] = to
        else:
            for f in self.fields_of(pid):
                self.st["owner"].pop(str(f), None)
                if f in self.st["mortgaged"]:
                    self.st["mortgaged"].remove(f)
        self.st["money"][pid] = 0
        self.st["meeting"].pop(pid, None)
        for c in self.st["free"].pop(pid, []):
            self.st["decks"]["chance" if c.startswith("z_") else "chest"].append(c)
        self.st["out"].append(pid)
        self.st["trades"] = [t for t in self.st["trades"] if pid not in (t["from"], t["to"])]
        self._log({"kind": "bankrupt", "player": pid, "to": to})
        if self.st.get("auction") and self.st["auction"].get("player") == pid:
            self.st["auction"] = None
        if self._maybe_end():
            return
        if self.st["turn"] == pid:
            self._next_turn()

    def _maybe_end(self) -> bool:
        act = self.active()
        if len(act) <= 1 or all(self.is_bot(p) for p in act):
            self.st["complete"] = True
            self._finish()
            return True
        return False

    # ---------- rolling and moving
    def roll(self, pid: str) -> list[int]:
        self._check(pid, ("roll",))
        d = [self.rng.randint(1, 6), self.rng.randint(1, 6)]
        self.st["dice"] = d
        self.st["roll_seq"] = self.st.get("roll_seq", 0) + 1
        self.st["turn_at"] = self.now()
        double = d[0] == d[1]
        if pid in self.st["meeting"]:                       # in the Gemeindeversammlung: a double lets you out
            self._log({"kind": "roll", "player": pid, "dice": d, "meeting": True})
            if double:
                self.st["meeting"].pop(pid)
                self._log({"kind": "leave", "player": pid, "how": "double"})
                self.st["doubles"] = 0
                self._move(pid, sum(d), after="done")
                return d
            self.st["meeting"][pid] += 1
            if self.st["meeting"][pid] >= MEETING_TRIES:
                self.st["meeting"].pop(pid)
                self._pay(pid, BAIL)
                self._log({"kind": "leave", "player": pid, "how": "forced", "amount": BAIL})
                self._move(pid, sum(d), after="done")
                return d
            self.st["stage"] = "done"
            return d
        self._log({"kind": "roll", "player": pid, "dice": d, "double": double})
        if double:
            self.st["doubles"] = self.st.get("doubles", 0) + 1
            if self.st["doubles"] >= MAX_DOUBLES:
                self._to_meeting(pid, "doubles")
                return d
        else:
            self.st["doubles"] = 0
        self._move(pid, sum(d), after="roll" if double else "done")
        return d

    def _to_meeting(self, pid: str, why: str) -> None:
        self.st["pos"][pid] = JAIL
        self.st["meeting"][pid] = 0
        self.st["doubles"] = 0
        self._log({"kind": "meeting", "player": pid, "why": why})
        self.st.update(stage="done", turn_at=self.now())

    def _move(self, pid: str, steps: int, after: str) -> None:
        old = self.st["pos"][pid]
        new = (old + steps) % N
        passed = old + steps >= N
        self.st["pos"][pid] = new
        bonus = 0
        if passed:
            bonus = MARKTTAG_MONEY
            self.st["money"][pid] += bonus
        self._log({"kind": "move", "player": pid, "from": old, "to": new, "steps": steps, "bonus": bonus})
        self._land(pid, after)

    def _goto(self, pid: str, target: int, after: str, collect: bool = True) -> None:
        """Move forward to a field (collecting the Markttag money on the way), or – collect=False – jump back to it."""
        old = self.st["pos"][pid]
        if collect:
            self._move(pid, (target - old) % N, after)
            return
        self.st["pos"][pid] = target
        self._log({"kind": "move", "player": pid, "from": old, "to": target, "steps": -((old - target) % N), "bonus": 0})
        self._land(pid, after)

    def _land(self, pid: str, after: str) -> None:
        f = self.st["pos"][pid]
        fd = FIELDS[f]
        t = fd["t"]
        if t in ("prop", "bus", "util"):
            own = self.owner(f)
            if own is None:
                if self.st["money"][pid] < fd["price"] and not self.r.get("auction"):
                    self._log({"kind": "skip", "player": pid, "field": f, "poor": True})
                    self._settle(after)
                    return
                self.st.update(stage="buy", after_buy=after, turn_at=self.now())
                return
            if own != pid:
                amount = self.rent(f)
                if amount:
                    self._pay(pid, amount, own)
                    self._log({"kind": "rent", "player": pid, "to": own, "field": f, "amount": amount})
                elif self.mortgaged(f):
                    self._log({"kind": "free_rent", "player": pid, "to": own, "field": f})
            self._settle(after)
            return
        if t == "tax":
            self._pay(pid, fd["amount"])
            self._log({"kind": "tax", "player": pid, "field": f, "amount": fd["amount"]})
            self._settle(after)
            return
        if t in ("chance", "chest"):
            self._card(pid, t, after)
            return
        if t == "gojail":
            self._to_meeting(pid, "field")
            return
        self._settle(after)

    def _card(self, pid: str, deck: str, after: str) -> None:
        cards = self.st["decks"][deck]
        if not cards:                                     # all «free» cards are held: nothing to draw
            self._settle(after)
            return
        cid = cards.pop(0)
        eff = CARDS[cid]
        self._log({"kind": "card", "player": pid, "deck": deck, "card": cid})
        if eff[0] != "free":
            cards.append(cid)
        kind = eff[0]
        if kind == "money":
            if eff[1] >= 0:
                self.st["money"][pid] += eff[1]
            else:
                self._pay(pid, -eff[1])
            self._settle(after)
        elif kind == "each":
            others = [p for p in self.active() if p != pid]
            for o in others:
                if eff[1] > 0:
                    self._pay(o, eff[1], pid)
                else:
                    self._pay(pid, -eff[1], o)
            self._settle(after)
        elif kind == "repair":
            stands = halls = 0
            for f in self.fields_of(pid):
                b = self.builds(f)
                if b == 5:
                    halls += 1
                else:
                    stands += b
            amount = stands * eff[1] + halls * eff[2]
            if amount:
                self._pay(pid, amount)
            self.st["last"]["amount"] = amount
            self._settle(after)
        elif kind == "free":
            self.st["free"].setdefault(pid, []).append(cid)
            self._settle(after)
        elif kind == "jail":
            self._to_meeting(pid, "card")
        elif kind == "goto":
            self._goto(pid, eff[1], after)
        elif kind == "back":
            self._goto(pid, (self.st["pos"][pid] - eff[1]) % N, after, collect=False)
        elif kind == "bus":
            pos = self.st["pos"][pid]
            target = min(BUSES, key=lambda b: (b - pos) % N or N)
            self._goto(pid, target, after)

    # ---------- buying, auction
    def buy(self, pid: str) -> None:
        self._check(pid, ("buy",))
        f = self.st["pos"][pid]
        price = FIELDS[f]["price"]
        if self.st["money"][pid] < price:
            raise CommunityError("Not enough Taler")
        self.st["money"][pid] -= price
        self.st["owner"][str(f)] = pid
        self._log({"kind": "buy", "player": pid, "field": f, "price": price})
        self._settle(self.st.pop("after_buy", "done"))

    def skip(self, pid: str) -> None:
        self._check(pid, ("buy",))
        f = self.st["pos"][pid]
        after = self.st.pop("after_buy", "done")
        if self.r.get("auction"):
            self.st["auction"] = {"field": f, "player": pid, "after": after, "price": 0, "leader": None, "history": [],
                                  "until": self.now() + AUCTION_SECONDS, "last_at": self.now()}
            self.st.update(stage="auction", turn_at=self.now())
            self._log({"kind": "auction_start", "player": pid, "field": f})
            return
        self._log({"kind": "skip", "player": pid, "field": f})
        self._settle(after)

    def bid(self, pid: str, step) -> None:
        """An open bid: the current price + 10, 25 or 50 (also to raise the own bid). Every bid starts the 5 seconds again."""
        self._check(pid, ("auction",), own_turn=False)
        a = self.st["auction"]
        if self.now() >= a["until"]:
            raise CommunityError("The auction is over")
        try:
            step = int(step)
        except (TypeError, ValueError):
            raise CommunityError("Not a number") from None
        if step not in BID_STEPS:
            raise CommunityError("Bid 10, 25 or 50 more")
        amount = a["price"] + step
        if amount > self.st["money"][pid]:
            raise CommunityError("Not enough Taler")
        a.update(price=amount, leader=pid, until=self.now() + AUCTION_SECONDS, last_at=self.now())
        a["history"] = (a.get("history") or [])[-19:] + [[pid, amount]]

    def _auction_check(self, force: bool = False) -> None:
        """5 seconds after the last bid (or the start): the highest bidder pays and gets the field."""
        a = self.st.get("auction")
        if not a or (not force and self.now() < a["until"]):
            return
        best, amount = a.get("leader"), a.get("price", 0)
        self.st["auction"] = None
        if best and amount > 0 and self.st["money"][best] >= amount:
            self.st["money"][best] -= amount
            self.st["owner"][str(a["field"])] = best
            self._log({"kind": "auction", "player": best, "field": a["field"], "amount": amount})
        else:
            self._log({"kind": "auction", "player": None, "field": a["field"], "amount": 0})
        self._settle(a["after"])

    # ---------- the turn ends
    def end_turn(self, pid: str) -> None:
        self._check(pid, ("done",))
        self._next_turn()

    def _next_turn(self) -> None:
        order = self.order()
        cur = self.st["turn"]
        i = order.index(cur)
        self.st["turns"] = self.st.get("turns", 0) + 1
        act = self.active()
        if not act:
            self._finish()
            return
        nxt = None
        for k in range(1, len(order) + 1):
            p = order[(i + k) % len(order)]
            if p in act:
                nxt = p
                break
        if order.index(nxt) <= i:                         # round over
            self.st["round"] = self.st.get("round", 1) + 1
        mode = self.r.get("mode")
        if (mode == "rounds" and self.st["round"] > int(self.r.get("rounds") or 30)) \
                or (mode == "time" and self.time_left() == 0) or self.st["turns"] >= MAX_TURNS:
            self.st["complete"] = True
            self._finish()
            return
        self.st.update(turn=nxt, stage="roll", doubles=0, dice=None, turn_at=self.now(), after_debt=None, debt_to=None)

    def _finish(self) -> None:
        order = self.order()
        out = self.st.get("out") or []
        score = {p: (10_000_000 + self.worth(p)) if p not in out else out.index(p) for p in order}
        self.st["places"] = places(order, score)
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st["worths"] = {p: self.worth(p) for p in order}
        self.st.update(phase="done", turn=None, stage=None, auction=None, trades=[], finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: ranked as it stands (no coins)."""
        if self.st.get("phase") == "play":
            self._finish()

    def pause(self, on: bool) -> None:
        if self.st.get("phase") != "play" or bool(self.st.get("paused")) == bool(on):
            return
        if on:
            self.st.update(paused=True, paused_at=self.now())
        else:
            gap = self.now() - (self.st.get("paused_at") or self.now())
            self.st["paused_total"] = self.st.get("paused_total", 0.0) + gap
            if self.st.get("auction"):
                self.st["auction"]["until"] += gap
            self.st.update(paused=False, paused_at=None, turn_at=self.now())

    # ---------- the Gemeindeversammlung
    def bail(self, pid: str) -> None:
        self._check(pid, ("roll",))
        if pid not in self.st["meeting"]:
            raise CommunityError("You are not in the town meeting")
        if self.st["money"][pid] < BAIL:
            raise CommunityError("Not enough Taler")
        self.st["meeting"].pop(pid)
        self._pay(pid, BAIL)
        self._log({"kind": "leave", "player": pid, "how": "pay", "amount": BAIL})

    def use_card(self, pid: str) -> None:
        self._check(pid, ("roll",))
        if pid not in self.st["meeting"]:
            raise CommunityError("You are not in the town meeting")
        held = self.st["free"].get(pid) or []
        if not held:
            raise CommunityError("You have no such card")
        c = held.pop(0)
        if not held:
            self.st["free"].pop(pid, None)
        self.st["decks"]["chance" if c.startswith("z_") else "chest"].append(c)
        self.st["meeting"].pop(pid)
        self._log({"kind": "leave", "player": pid, "how": "card"})

    # ---------- building, mortgages
    def can_build(self, pid: str, f: int) -> bool:
        fd = FIELDS[f]
        if fd["t"] != "prop" or self.owner(f) != pid or self.builds(f) >= 5:
            return False
        g = GROUPS[fd["g"]]
        if not self.full_group(pid, fd["g"]) or any(self.mortgaged(x) for x in g):
            return False
        return self.builds(f) == min(self.builds(x) for x in g)

    def can_sell(self, pid: str, f: int) -> bool:
        fd = FIELDS[f]
        if fd["t"] != "prop" or self.owner(f) != pid or not self.builds(f):
            return False
        return self.builds(f) == max(self.builds(x) for x in GROUPS[fd["g"]])

    def can_mortgage(self, pid: str, f: int) -> bool:
        return bool(self.r.get("mortgage")) and self.owner(f) == pid and not self.mortgaged(f) and not self.group_built(f)

    def unmortgage_cost(self, f: int) -> int:
        half = FIELDS[f]["price"] // 2
        return half + (half + 9) // 10

    def build(self, pid: str, f) -> None:
        self._check(pid, ("roll", "done"))
        f = self._field(f)
        if not self.can_build(pid, f):
            raise CommunityError("You cannot build here now")
        cost = FIELDS[f]["house"]
        if self.st["money"][pid] < cost:
            raise CommunityError("Not enough Taler")
        self.st["money"][pid] -= cost
        self.st["build"][str(f)] = self.builds(f) + 1
        self._log({"kind": "build", "player": pid, "field": f, "n": self.builds(f), "amount": cost})

    def sell(self, pid: str, f) -> None:
        self._check(pid, ("roll", "done", "debt"))
        f = self._field(f)
        if not self.can_sell(pid, f):
            raise CommunityError("You cannot sell here now")
        self._sell(pid, f)
        self._debt_paid()

    def _sell(self, pid: str, f: int) -> None:
        back = FIELDS[f]["house"] // 2
        self.st["build"][str(f)] = self.builds(f) - 1
        if not self.st["build"][str(f)]:
            self.st["build"].pop(str(f))
        self.st["money"][pid] += back
        self._log({"kind": "sell", "player": pid, "field": f, "n": self.builds(f), "amount": back})

    def mortgage(self, pid: str, f) -> None:
        self._check(pid, ("roll", "done", "debt"))
        f = self._field(f)
        if not self.can_mortgage(pid, f):
            raise CommunityError("You cannot mortgage this field now")
        self._mortgage(pid, f)
        self._debt_paid()

    def _mortgage(self, pid: str, f: int) -> None:
        self.st["mortgaged"].append(f)
        self.st["money"][pid] += FIELDS[f]["price"] // 2
        self._log({"kind": "mortgage", "player": pid, "field": f, "amount": FIELDS[f]["price"] // 2})

    def unmortgage(self, pid: str, f) -> None:
        self._check(pid, ("roll", "done"))
        f = self._field(f)
        if self.owner(f) != pid or not self.mortgaged(f):
            raise CommunityError("This field is not mortgaged")
        cost = self.unmortgage_cost(f)
        if self.st["money"][pid] < cost:
            raise CommunityError("Not enough Taler")
        self.st["money"][pid] -= cost
        self.st["mortgaged"].remove(f)
        self._log({"kind": "unmortgage", "player": pid, "field": f, "amount": cost})

    def liquidate(self, pid: str) -> None:
        """In debt: sell and mortgage by itself until the debt is paid."""
        self._check(pid, ("debt",))
        self._liquidate(pid)
        if self.st["money"][pid] < 0:
            self._bankrupt(pid, self.st.get("debt_to"))
        else:
            self._debt_paid()

    def give_up(self, pid: str) -> None:
        self._check(pid, ("debt",))
        self._bankrupt(pid, self.st.get("debt_to"))

    @staticmethod
    def _field(f) -> int:
        try:
            f = int(f)
        except (TypeError, ValueError):
            raise CommunityError("Unknown field") from None
        if not 0 <= f < N:
            raise CommunityError("Unknown field")
        return f

    # ---------- trading
    def tradable(self, pid: str, f: int) -> bool:
        return self.owner(f) == pid and not self.group_built(f)

    def offer(self, pid: str, to: str, give: list, give_money, want: list, want_money) -> dict:
        self._check(pid, own_turn=False)
        if to == pid or to not in self.active():
            raise CommunityError("Choose another player")
        try:
            give = sorted({self._field(f) for f in give or []})
            want = sorted({self._field(f) for f in want or []})
            gm, wm = max(0, int(give_money or 0)), max(0, int(want_money or 0))
        except (TypeError, ValueError):
            raise CommunityError("Not a number") from None
        if not (give or want or gm or wm):
            raise CommunityError("Offer something and ask for something")
        if any(not self.tradable(pid, f) for f in give) or any(not self.tradable(to, f) for f in want):
            raise CommunityError("These fields cannot be traded (sell the buildings of the group first)")
        if gm > self.st["money"][pid] or wm > self.st["money"][to]:
            raise CommunityError("Not enough Taler")
        self.st["trades"] = [t for t in self.st["trades"] if t["from"] != pid]
        t = {"id": secrets.token_hex(4), "from": pid, "to": to, "give": give, "give_money": gm, "want": want, "want_money": wm, "t": self.now()}
        self.st["trades"].append(t)
        self._log({"kind": "offer", "player": pid, "to": to})
        if self.is_bot(to):                                # bots answer at once
            self._answer(t, self.bot_accepts(to, t))
        return t

    def answer(self, pid: str, tid: str, accept: bool) -> None:
        self._check(pid, own_turn=False)
        t = next((x for x in self.st["trades"] if x["id"] == tid), None)
        if not t or t["to"] != pid:
            raise CommunityError("This offer is not there any more")
        self._answer(t, accept)

    def cancel(self, pid: str, tid: str) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")
        self.st["trades"] = [t for t in self.st.get("trades") or [] if not (t["id"] == tid and t["from"] == pid)]

    def _answer(self, t: dict, accept: bool) -> None:
        self.st["trades"] = [x for x in self.st["trades"] if x["id"] != t["id"]]
        a, b = t["from"], t["to"]
        ok = accept and all(self.tradable(a, f) for f in t["give"]) and all(self.tradable(b, f) for f in t["want"]) \
            and self.st["money"][a] >= t["give_money"] and self.st["money"][b] >= t["want_money"]
        if accept and not ok:
            self._log({"kind": "trade_failed", "player": a, "to": b})
            return
        if not ok:
            self._log({"kind": "trade_no", "player": a, "to": b})
            return
        for f in t["give"]:
            self.st["owner"][str(f)] = b
        for f in t["want"]:
            self.st["owner"][str(f)] = a
        self.st["money"][a] += t["want_money"] - t["give_money"]
        self.st["money"][b] += t["give_money"] - t["want_money"]
        self._log({"kind": "trade", "player": a, "to": b, "give": t["give"], "want": t["want"],
                   "give_money": t["give_money"], "want_money": t["want_money"]})
        self._debt_paid()

    # ---------- bots
    def _value(self, pid: str, f: int, gaining: bool) -> float:
        """What a field is worth to a player: its price, more when it completes (or is part of) a group."""
        fd = FIELDS[f]
        v = fd["price"] * (0.5 if self.mortgaged(f) else 1.0)
        if fd["t"] == "prop":
            g = GROUPS[fd["g"]]
            mine = sum(1 for x in g if self.owner(x) == pid and x != f)
            if mine == len(g) - 1:
                v *= 2.5                                    # completes (or would break) a whole group
            elif mine:
                v *= 1.4
        elif fd["t"] in ("bus", "util"):
            mine = sum(1 for x in (BUSES if fd["t"] == "bus" else UTILS) if self.owner(x) == pid and x != f)
            v *= 1 + 0.3 * mine
        return v

    def bot_accepts(self, bot: str, t: dict) -> bool:
        lvl = (self.seat_of(bot) or {}).get("level", "normal")
        get = sum(self._value(bot, f, True) for f in t["give"]) + t["give_money"]
        lose = sum(self._value(bot, f, False) for f in t["want"]) + t["want_money"]
        # what the other side wins: giving away a field that completes their group is costly
        for f in t["want"]:
            fd = FIELDS[f]
            if fd["t"] == "prop" and all(self.owner(x) == t["from"] or x == f for x in GROUPS[fd["g"]]):
                lose += fd["price"] * (0.5 if lvl == "easy" else 1.5)
        if t["want_money"] > self.st["money"][bot]:
            return False
        factor = {"easy": 0.9, "normal": 1.1, "hard": 1.3}.get(lvl, 1.1)
        return get >= lose * factor and get > 0

    def _reserve(self, lvl: str) -> int:
        return {"easy": 50, "normal": 150, "hard": 250}.get(lvl, 150)

    def bot_buys(self, pid: str, lvl: str) -> bool:
        f = self.st["pos"][pid]
        price, money = FIELDS[f]["price"], self.st["money"][pid]
        if money < price:
            return False
        if lvl == "easy":
            return self.rng.random() < 0.75
        left = money - price
        fd = FIELDS[f]
        wanted = fd["t"] == "prop" and any(self.owner(x) is not None for x in GROUPS[fd["g"]] if x != f)
        return left >= self._reserve(lvl) or (lvl == "hard" and wanted and left >= 0)

    def bot_bid(self, pid: str, f: int, lvl: str) -> int:
        money, price = self.st["money"][pid], FIELDS[f]["price"]
        if lvl == "easy":
            return min(money, int(price * self.rng.uniform(0.2, 0.8)))
        v = self._value(pid, f, True) * (0.8 if lvl == "normal" else 0.95)
        return max(0, min(money - self._reserve(lvl) // 2, int(v)))

    def bot_build(self, pid: str, lvl: str) -> bool:
        """One building step (or paying back a mortgage). True if something was done."""
        money = self.st["money"][pid]
        reserve = {"easy": 300, "normal": 250, "hard": 150}.get(lvl, 250)
        if lvl == "easy" and self.rng.random() < 0.5:
            return False
        if self.r.get("mortgage"):
            for f in self.fields_of(pid):
                if self.mortgaged(f) and money - self.unmortgage_cost(f) >= reserve * 2:
                    self.unmortgage(pid, f)
                    return True
        opts = [f for f in self.fields_of(pid) if self.can_build(pid, f) and money - FIELDS[f]["house"] >= reserve]
        if not opts:
            return False
        self.build(pid, max(opts, key=lambda f: (FIELDS[f]["price"], -f)))
        return True

    def bot_step(self, pid: str) -> None:
        lvl = (self.seat_of(pid) or {}).get("level", "normal")
        stage = self.st["stage"]
        if stage == "debt":
            self.liquidate(pid)
        elif stage == "buy":
            if self.bot_buys(pid, lvl):
                self.buy(pid)
            else:
                self.skip(pid)
        elif stage == "roll":
            if pid in self.st["meeting"]:
                if self.st["free"].get(pid):
                    self.use_card(pid)
                    return
                early = len(self.st["owner"]) < len(OWNABLE) * 0.7
                pay = {"easy": self.rng.random() < 0.3, "normal": early, "hard": early}.get(lvl, early)
                if pay and self.st["money"][pid] >= BAIL + self._reserve(lvl):
                    self.bail(pid)
                    return
            elif lvl != "easy" and self.bot_build(pid, lvl):
                return
            self.roll(pid)
        elif stage == "done":
            if self.bot_build(pid, lvl):
                return
            self.end_turn(pid)

    def tick(self) -> bool:
        """The bots act (after their reaction time; at once with bot_ms 0), auctions close. True if something changed."""
        changed = False
        delay = bot_delay(self.r, BOT_DELAY)
        for _ in range(MAX_TURNS * 8 if delay == 0 else 2):
            if self.st.get("phase") != "play" or self.st.get("paused"):
                break
            a = self.st.get("auction")
            if a:
                if self.now() >= a["until"]:
                    self._auction_check()
                    changed = True
                    continue
                # a bot that is not leading and still wants the field raises – after a short reaction time (< 5 s)
                limits = a.setdefault("limits", {})
                wait = min(AUCTION_SECONDS * 0.6, max(0.0, delay * 0.8))
                bidders = []
                for b in self.active():
                    if not self.is_bot(b) or b == a.get("leader"):
                        continue
                    if b not in limits:
                        limits[b] = self.bot_bid(b, a["field"], (self.seat_of(b) or {}).get("level", "normal"))
                    step = next((x for x in BID_STEPS if a["price"] + x <= min(limits[b], self.st["money"][b])), None)
                    if step:
                        bidders.append((b, step))
                if bidders and self.now() - a.get("last_at", 0) >= wait:
                    b, step = self.rng.choice(bidders)
                    self.bid(b, step)
                    changed = True
                    if delay == 0:
                        continue
                break
            p = self.st.get("turn")
            if not self.is_bot(p):
                if self.r.get("mode") == "time" and self.time_left() == 0 and self.elapsed() > int(self.r.get("minutes") or 60) * 60 + 600:
                    self.st["complete"] = True                # a person who does not end the turn: over 10 minutes later
                    self._finish()
                    changed = True
                break
            wait = delay if self.st["stage"] in ("roll", "done") else delay * 0.7
            if self.now() - self.st.get("turn_at", 0) < wait:
                break
            self.bot_step(p)
            self.st["turn_at"] = self.now()
            changed = True
        return changed


# ================================================================ the games in the database (table card_game, kind "dorfmarkt")
class Dorfmarkt(CardGames):
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
        return {**self.default_rules(), "rewards": rewards_of(self.db), "max_players": MAX_PLAYERS}

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
        out["mode"] = out["mode"] if out["mode"] in MODES else "rounds"
        out["rounds"] = max(5, min(100, out["rounds"]))
        out["minutes"] = max(10, min(240, out["minutes"]))
        out["money"] = max(500, min(5000, out["money"]))
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
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]),
                        "worth": (st.get("worths") or {}).get(p["id"], 0), "fields": len(t.fields_of(p["id"])),
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
        n = st["rules"]["bots"]
        if st.get("solo"):
            n = max(1, n)
        n = max(0, min(n, MAX_PLAYERS - len(humans)))
        st["players"] = humans + self._bots(st, n)
        st.pop("bot_pool", None)
        if len(st["players"]) < 2:
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
            if solo:                                      # alone against bots: the game starts right away
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

    def begin(self, kind: str, viewer: int, starter=None) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            apply_starter(st, starter_mode(self.db), starter, leader=row["host_id"])     # who begins (Settings › Games)
            self._deal(st)
            self._save(row, st)

    ACTIONS = ("roll", "buy", "skip", "bid", "end_turn", "build", "sell", "mortgage", "unmortgage", "bail", "use_card",
               "liquidate", "give_up", "offer", "answer", "cancel")

    def act(self, pid: int, action: str, data: dict | None = None):
        if action not in self.ACTIONS:
            raise CommunityError("Unknown action")
        d = data or {}
        me = str(pid)

        def run(t: Table):
            if action == "bid":
                return t.bid(me, d.get("step") if d.get("step") is not None else d.get("amount"))
            if action in ("build", "sell", "mortgage", "unmortgage"):
                return getattr(t, action)(me, d.get("field"))
            if action == "offer":
                return t.offer(me, str(d.get("to") or ""), d.get("give") or [], d.get("give_money"), d.get("want") or [], d.get("want_money"))
            if action == "answer":
                return t.answer(me, str(d.get("trade") or ""), bool(d.get("accept")))
            if action == "cancel":
                return t.cancel(me, str(d.get("trade") or ""))
            return getattr(t, action)(me)
        return self._with(pid, run)

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

    def pause(self, viewer: int, on: bool) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "play":
                raise CommunityError("The game is not running")
            self.table(st).pause(on)
            self._save(row, st)

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
        base = {"game": row["id"], "starter": st.get("starter"), "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph,
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "joined": joined,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2, "max_players": MAX_PLAYERS}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            bots = st["rules"]["bots"] if not st.get("solo") else max(1, st["rules"]["bots"])
            return {**base, "players": players, "bots": max(0, min(bots, MAX_PLAYERS - len(players)))}
        t = self.table(st)
        coins, pl = st.get("coins") or {}, st.get("places") or {}
        out = st.get("out") or []
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                    "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"), "seat": i,
                    "money": st["money"][p["id"]], "pos": st["pos"][p["id"]], "worth": t.worth(p["id"]),
                    "fields": len(t.fields_of(p["id"])), "meeting": st["meeting"].get(p["id"]),
                    "free": len(st["free"].get(p["id"]) or []), "out": p["id"] in out,
                    "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0)} for i, p in enumerate(st["players"])]
        live = ph == "play"
        my_turn = joined and live and st.get("turn") == me and not st.get("paused")
        stage = st.get("stage") if live else None
        mine = t.fields_of(me) if joined else []
        a = st.get("auction")
        auction = None
        if a and live:
            auction = {"field": a["field"], "player": a["player"], "price": a.get("price", 0), "leader": a.get("leader"),
                       "history": (a.get("history") or [])[-5:], "steps": list(BID_STEPS), "seconds": AUCTION_SECONDS,
                       "ms": max(0, int((a["until"] - self.now()) * 1000))}
        trades = [x for x in st.get("trades") or [] if me in (x["from"], x["to"])] if joined else []
        in_meeting = joined and me in st["meeting"]
        return {**base, "players": players, "turn": st.get("turn") if live else None, "stage": stage,
                "dice": st.get("dice"), "roll_seq": st.get("roll_seq", 0), "doubles": st.get("doubles", 0),
                "round": st.get("round", 1), "time_left": t.time_left() if live else None, "paused": bool(st.get("paused")),
                "owner": st.get("owner") or {}, "build": st.get("build") or {}, "mortgaged": st.get("mortgaged") or [],
                "me": me if joined else None, "my_turn": my_turn, "in_meeting": in_meeting, "bail": BAIL,
                "can_roll": my_turn and stage == "roll",
                "can_buy": my_turn and stage == "buy" and st["money"][me] >= FIELDS[st["pos"][me]]["price"],
                "may_build": [f for f in mine if t.can_build(me, f)] if my_turn and stage in ("roll", "done") else [],
                "may_sell": [f for f in mine if t.can_sell(me, f)] if my_turn and stage in ("roll", "done", "debt") else [],
                "may_mortgage": [f for f in mine if t.can_mortgage(me, f)] if my_turn and stage in ("roll", "done", "debt") else [],
                "may_unmortgage": [f for f in mine if t.mortgaged(f)] if my_turn and stage in ("roll", "done") else [],
                "unmortgage_cost": {str(f): t.unmortgage_cost(f) for f in OWNABLE},
                "tradable": [f for f in OWNABLE if t.owner(f) and not t.group_built(f)] if live else [],
                "auction": auction, "trades": trades, "rent_now": {str(f): t.rent(f, 7) for f in OWNABLE if t.owner(f)},
                "last": st.get("last"), "log": (st.get("log") or [])[-12:], "out": out,
                "ranking": st.get("ranking"), "complete": bool(st.get("complete")), "worths": st.get("worths")}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)


def board() -> list[dict]:
    """The fields for the app (prices, rents, groups) – the names are in dorfmarkt.js."""
    return [{k: v for k, v in f.items()} for f in FIELDS]
