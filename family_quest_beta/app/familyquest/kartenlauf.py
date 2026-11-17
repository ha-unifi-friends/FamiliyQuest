"""«Kartenlauf» – a live race board game with cards for the family (traditional Canadian/Swiss game mechanics).

Everybody plays on their own device (family table, guests via QR code) or a child plays alone against bots – like
Domino (domino.py); the tables live in the `card_game` table with kind "kartenlauf".

Board: always the 4-seat board – a ring of 64 fields (16 per seat). Seat s has its start field 16·s on the ring, a
kennel with 4 marbles and 4 home fields that branch off the ring just before the start field (after field 16·s − 1).
2 players sit opposite (seats 0, 2), 3 players on seats 0, 1, 2. 4 players: teams of two (partners opposite) or alone.

Cards: two French decks with 3 jokers each (110 cards, only the rank counts). Rounds deal 6, 5, 4, 3, 2 cards, then
again 6 … (a fresh shuffled deck with every 6). The dealer rotates; the player after the dealer starts. With teams
every player first passes one card face-down to the partner.
  A    1 or 11 forward, or bring a marble out onto its start field
  K    13 forward, or bring a marble out
  Q    12 forward
  J    swap one of your marbles on the ring with another player's marble on the ring (not protected ones)
  4    4 forward or 4 backward
  7    7 steps split among your marbles (all 7 must be used) – every marble passed over is sent back to its kennel
  2 3 5 6 8 9 10   that many forward
  Joker  stands for any card
A marble that just came out sits «protected» on its start field: nobody may pass or land on it until it moves on.
Landing on another marble sends it back to its kennel (partner's and own marbles too). A marble may enter its home
only after it left its start field, only forward, exactly, without jumping over marbles in the home.
Who cannot play any card throws their cards away for this round.
Win: alone – the first with all 4 marbles home (the others by marbles home and progress). Teams – with your 4 home
you play with your partner's marbles; the team wins with all 8 home.
House rules: «7 may move the partner's marbles» (else only when your own are all home), «the joker may be the card
that wins» (else a joker may not bring the last marble home).
Coins (setting `game_rewards["kartenlauf"]`): places 1–3, only people of the family at a family table with at least
two of them; teams: both of the winning team place 1, the others place 2. Paid once (unique ledger ref).
The view never shows the other players' hand cards.
"""
from __future__ import annotations

import json
import random
import time
from itertools import product

from .cardgames import BOTS, BOT_DELAY, CardGames, bot_delay, apply_starter, starter_mode
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of

KIND = "kartenlauf"
TITLE = "Kartenlauf"
DEFAULTS = {"seats": 4, "teams": True, "seven_partner": False, "joker_last": True, "level": "normal", "bot_ms": 1400}
LEVELS = ("easy", "normal", "hard")
RING = 64
PER_SEAT = 16
HOME = 64                    # positions 64..67: the home fields 0..3 of the marble's owner; -1: in the kennel
SIZES = (6, 5, 4, 3, 2)      # cards per round
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
JOKER = "X"
JOKER_AS = tuple(r for r in RANKS if r != "7") + ("7",)    # the 7 last: its splits are the most work
SUITS = ("s", "h", "d", "c")
SEATS = {1: [0], 2: [0, 2], 3: [0, 1, 2], 4: [0, 1, 2, 3]}
BETWEEN = 2.5                # seconds between two rounds
MAX_ROUNDS = 150             # safety: a game that never ends is decided by progress
CAP7 = 240                   # at most this many 7-splits are listed per card (bots, the view)


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def new_deck() -> list[str]:
    cards = [f"{s}:{r}" for _ in range(2) for s in SUITS for r in RANKS]
    return cards + ["x:X"] * 6


def rank(card: str) -> str:
    return card.split(":", 1)[1] if ":" in card else card


def mid(owner: str, idx: int) -> str:
    return f"{owner}:{idx}"


def parse_mid(m) -> tuple[str, int]:
    try:
        owner, i = str(m).rsplit(":", 1)
        i = int(i)
    except (TypeError, ValueError):
        raise CommunityError("Unknown marble") from None
    if not 0 <= i < 4:
        raise CommunityError("Unknown marble")
    return owner, i


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now

    @property
    def r(self) -> dict:
        return self.st["rules"]

    def seat_of(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def order(self) -> list[str]:
        seats = self.st.get("seats") or {}
        return sorted((p["id"] for p in self.st["players"]), key=lambda p: seats.get(p, 0))

    def teams(self) -> bool:
        return bool(self.st.get("teams"))

    def start_of(self, pid: str) -> int:
        return self.st["seats"][pid] * PER_SEAT

    def entry_of(self, pid: str) -> int:
        return (self.start_of(pid) - 1) % RING

    def partner(self, pid: str) -> str | None:
        if not self.teams():
            return None
        s = (self.st["seats"][pid] + 2) % 4
        return next((p for p, x in self.st["seats"].items() if x == s), None)

    def side(self, pid: str) -> str:
        return str(self.st["seats"][pid] % 2) if self.teams() else pid

    def members(self, side: str) -> list[str]:
        return [p for p in self.order() if self.side(p) == side]

    def sides(self) -> list[str]:
        return ["0", "1"] if self.teams() else self.order()

    @staticmethod
    def home_count(M: dict, pid: str) -> int:
        return sum(1 for pos, _ in M[pid] if pos >= HOME)

    def all_home(self, M: dict, pid: str) -> bool:
        return self.home_count(M, pid) == 4

    def side_done(self, M: dict, pid: str) -> bool:
        return all(self.all_home(M, p) for p in self.members(self.side(pid)))

    def controlled(self, M: dict, pid: str) -> list[str]:
        """Whose marbles this player moves: their own – with teams and all own marbles home: the partner's."""
        if self.teams() and self.all_home(M, pid):
            pa = self.partner(pid)
            return [pa] if pa else []
        return [pid]

    def seven_owners(self, M: dict, pid: str) -> list[str]:
        own = self.controlled(M, pid)
        pa = self.partner(pid)
        if self.teams() and self.r.get("seven_partner") and pa and pa not in own:
            own = own + [pa]
        return own

    def seven_marbles(self, pid: str) -> list[str]:
        """The marbles a 7 may move: the own (or controlled) ones – and the partner's when the rule allows it, or when
        all own marbles left could get home during this 7 (the rest of the steps then go to the partner)."""
        M = self.st["marbles"]
        owners = self.seven_owners(M, pid)
        pa = self.partner(pid)
        if pa and pa not in owners and pid in owners:
            left = [M[pid][i] for i in range(4) if M[pid][i][0] < HOME]
            if all(0 <= pos and not fresh for pos, fresh in left) and \
                    sum((self.entry_of(pid) - pos) % RING + 1 for pos, _ in left) < 7:
                owners = owners + [pa]
        return [mid(o, i) for o in owners for i in range(4) if 0 <= M[o][i][0] < HOME + 3]

    # ---------- a game, a round
    def setup(self) -> None:
        """The seats and the marbles (all in the kennels) – then the first round."""
        ids = [p["id"] for p in self.st["players"]]
        n = len(ids)
        if not 2 <= n <= 4:
            raise CommunityError("Kartenlauf needs 2 to 4 players")
        self.st["seats"] = {pid: s for pid, s in zip(ids, SEATS[n])}
        self.st["teams"] = bool(self.r.get("teams")) and n == 4
        self.st["marbles"] = {pid: [[-1, 0] for _ in range(4)] for pid in ids}
        self.st.update(round=0, deck=[], discard=[], log=[], finished_order=[], ranking=None, places=None, winner=None)
        self.new_round()

    def new_round(self) -> None:
        rnd = self.st.get("round", 0) + 1
        size = SIZES[(rnd - 1) % len(SIZES)]
        order = self.order()
        if size == SIZES[0] or len(self.st.get("deck") or []) < size * len(order):
            deck = new_deck()
            self.rng.shuffle(deck)
            self.st["deck"] = deck
            self.st["discard"] = []
        dealer = order[(rnd - 1) % len(order)]
        self.st["hands"] = {p: [self.st["deck"].pop() for _ in range(size)] for p in order}
        self.st.update(round=rnd, dealer=dealer, turn=None, give={}, got={}, last=None, round_size=size)
        self.st["turn_at"] = self.now()
        if self.teams():
            self.st["phase"] = "exchange"
            self.st["give"] = {p: None for p in order}
        else:
            self.st["phase"] = "play"
            self._advance(dealer)

    def _log(self, ev: dict) -> None:
        ev["t"] = self.now()
        self.st["last"] = ev
        log = self.st.setdefault("log", [])
        log.append(ev)
        del log[:-8]

    def _advance(self, cur: str) -> None:
        """The next player with cards who can play; who cannot throws the cards away. No cards left: the round ends."""
        order = self.order()
        i = order.index(cur)
        for k in range(1, len(order) + 1):
            p = order[(i + k) % len(order)]
            hand = self.st["hands"].get(p) or []
            if not hand:
                continue
            if self.has_move(p):
                self.st["turn"] = p
                self.st["turn_at"] = self.now()
                return
            self.st["discard"] += hand
            self._log({"player": p, "fold": len(hand), "cards": list(hand)})
            self.st["hands"][p] = []
        self._round_end()

    def _round_end(self) -> None:
        self.st["turn"] = None
        if self.st["round"] >= MAX_ROUNDS:
            self._finish(None)
            return
        self.st["phase"] = "between"
        self.st["next_at"] = self.now() + BETWEEN

    # ---------- the card exchange (teams)
    def give(self, pid: str, card: str) -> None:
        if self.st.get("phase") != "exchange":
            raise CommunityError("No card exchange right now")
        if pid not in self.st["give"]:
            raise CommunityError("You do not play at this table")
        if self.st["give"][pid]:
            raise CommunityError("You gave a card already")
        if card not in self.st["hands"][pid]:
            raise CommunityError("You do not have this card")
        self.st["give"][pid] = card
        if all(self.st["give"].values()):
            hands = self.st["hands"]
            for p, c in self.st["give"].items():
                hands[p].remove(c)
            got = {}
            for p, c in self.st["give"].items():
                pa = self.partner(p)
                hands[pa].append(c)
                got[pa] = c
            self.st["got"] = got
            self.st["phase"] = "play"
            self._log({"exchange": True})
            self._advance(self.st["dealer"])

    # ---------- moves: simulate on a copy, check, apply
    @staticmethod
    def _copy(M: dict) -> dict:
        return {p: [[a, b] for a, b in ms] for p, ms in M.items()}

    @staticmethod
    def _occ(M: dict) -> dict[int, tuple[str, int]]:
        return {pos: (p, i) for p, ms in M.items() for i, (pos, _) in enumerate(ms) if 0 <= pos < RING}

    def _can_reach_home(self, M: dict, owner: str, i: int, n: int) -> bool:
        pos, fresh = M[owner][i]
        if not 0 <= pos < RING or fresh:
            return False
        d = (self.entry_of(owner) - pos) % RING
        return d < n <= d + 4

    def _step(self, M: dict, owner: str, i: int, n: int, home, kick_all: bool, ev: dict) -> None:
        """Move marble (owner, i) n fields forward (home: True = into the home, False = on along the ring,
        None = into the home if it can). kick_all: the 7 – every marble passed over goes back to its kennel."""
        pos, fresh = M[owner][i]
        if pos < 0:
            raise CommunityError("This marble is in the kennel")
        if pos >= HOME:                                         # inside the home: forward, exactly, no jumping
            h = pos - HOME
            if h + n > 3:
                raise CommunityError("Too far for the home")
            taken = {q - HOME for q, _ in M[owner] if q >= HOME}
            if any(j in taken for j in range(h + 1, h + n + 1)):
                raise CommunityError("No jumping over marbles in the home")
            M[owner][i] = [HOME + h + n, 0]
            ev["moved"].append([mid(owner, i), pos, HOME + h + n])
            return
        d = (self.entry_of(owner) - pos) % RING
        reach = not fresh and d < n <= d + 4
        if home is None:
            home = reach and self._home_free(M, owner, n - d - 1)
        if home and not reach:
            raise CommunityError("This marble cannot go into its home with this card")
        ring_steps = d if home else n
        occ = self._occ(M)
        path = [(pos + k) % RING for k in range(1, ring_steps + 1)]
        for f in path:
            o = occ.get(f)
            if o and M[o[0]][o[1]][1]:
                raise CommunityError("A protected marble blocks the way")
        hits = path if kick_all else (path[-1:] if not home else [])
        for f in hits:
            o = occ.get(f)
            if o and o != (owner, i):
                M[o[0]][o[1]] = [-1, 0]
                ev["kicked"].append(mid(*o))
        if home:
            hi = n - d - 1
            if not self._home_free(M, owner, hi):
                raise CommunityError("No jumping over marbles in the home")
            M[owner][i] = [HOME + hi, 0]
            ev["home"].append(mid(owner, i))
        else:
            M[owner][i] = [path[-1], 0]
        ev["moved"].append([mid(owner, i), pos, M[owner][i][0]])

    @staticmethod
    def _home_free(M: dict, owner: str, hi: int) -> bool:
        if hi > 3:
            return False
        taken = {q - HOME for q, _ in M[owner] if q >= HOME}
        return not any(j in taken for j in range(0, hi + 1))

    def _back(self, M: dict, owner: str, i: int, n: int, ev: dict) -> None:
        pos, _ = M[owner][i]
        if not 0 <= pos < RING:
            raise CommunityError("Only a marble on the ring can go backwards")
        occ = self._occ(M)
        path = [(pos - k) % RING for k in range(1, n + 1)]
        for f in path:
            o = occ.get(f)
            if o and M[o[0]][o[1]][1]:
                raise CommunityError("A protected marble blocks the way")
        o = occ.get(path[-1])
        if o:
            M[o[0]][o[1]] = [-1, 0]
            ev["kicked"].append(mid(*o))
        M[owner][i] = [path[-1], 0]
        ev["moved"].append([mid(owner, i), pos, path[-1]])

    def _out(self, M: dict, owner: str, i: int, ev: dict) -> None:
        if M[owner][i][0] != -1:
            raise CommunityError("This marble is not in the kennel")
        start = self.start_of(owner)
        o = self._occ(M).get(start)
        if o:
            if M[o[0]][o[1]][1]:
                raise CommunityError("Your start field is blocked")
            M[o[0]][o[1]] = [-1, 0]
            ev["kicked"].append(mid(*o))
        M[owner][i] = [start, 1]
        ev["moved"].append([mid(owner, i), -1, start])

    def simulate(self, pid: str, mv: dict) -> tuple[dict, dict]:
        """The marbles after this move (a copy) and what happened – raises CommunityError if it is not allowed."""
        card = mv.get("card")
        hand = self.st["hands"].get(pid) or []
        if card not in hand:
            raise CommunityError("You do not have this card")
        rk = rank(card)
        if rk == JOKER:
            rk = mv.get("as")
            if rk not in RANKS:
                raise CommunityError("Choose the card the joker stands for")
        M = self._copy(self.st["marbles"])
        ev = {"moved": [], "kicked": [], "home": [], "rank": rk}
        kind = mv.get("kind")
        mine = self.controlled(M, pid)

        def marble(key="marble"):
            owner, i = parse_mid(mv.get(key))
            if owner not in M:
                raise CommunityError("Unknown marble")
            return owner, i

        if rk == "7":
            split = mv.get("split") or []
            if not isinstance(split, list) or not split:
                raise CommunityError("Split the 7 among your marbles")
            total, used = 0, set()
            for part in split:
                if not isinstance(part, (list, tuple)) or len(part) < 2:
                    raise CommunityError("Split the 7 among your marbles")
                owner, i = parse_mid(part[0])
                try:
                    n = int(part[1])
                except (TypeError, ValueError):
                    raise CommunityError("Split the 7 among your marbles") from None
                home = part[2] if len(part) > 2 else None
                if owner not in M or n < 1 or (owner, i) in used:
                    raise CommunityError("Split the 7 among your marbles")
                if owner not in self.seven_owners(M, pid):
                    raise CommunityError("This is not your marble")
                used.add((owner, i))
                total += n
                self._step(M, owner, i, n, home if home in (True, False) else None, True, ev)
            if total != 7:
                raise CommunityError("Use exactly 7 steps")
            kind = "seven"
        elif rk == "J":
            if kind not in (None, "swap"):
                raise CommunityError("A jack swaps two marbles")
            owner, i = marble()
            other, j = marble("target")
            if owner not in mine:
                raise CommunityError("This is not your marble")
            if other == owner:
                raise CommunityError("Swap with another player's marble")
            a, b = M[owner][i], M[other][j]
            for pos, fresh in (a, b):
                if not 0 <= pos < RING:
                    raise CommunityError("Only marbles on the ring can be swapped")
                if fresh:
                    raise CommunityError("A protected marble cannot be swapped")
            M[owner][i], M[other][j] = [b[0], 0], [a[0], 0]
            ev["moved"] += [[mid(owner, i), a[0], b[0]], [mid(other, j), b[0], a[0]]]
            ev["swap"] = [mid(owner, i), mid(other, j)]
            kind = "swap"
        else:
            if kind == "out":
                if rk not in ("A", "K"):
                    raise CommunityError("Only an ace or a king brings a marble out")
                owner, i = marble()
                if owner not in mine:
                    raise CommunityError("This is not your marble")
                self._out(M, owner, i, ev)
            elif kind == "back":
                if rk != "4":
                    raise CommunityError("Only a 4 goes backwards")
                owner, i = marble()
                if owner not in mine:
                    raise CommunityError("This is not your marble")
                self._back(M, owner, i, 4, ev)
            elif kind in (None, "move"):
                allowed = {"A": (1, 11), "K": (13,), "Q": (12,)}.get(rk) or (int(rk),)
                n = mv.get("steps") or allowed[0]
                try:
                    n = int(n)
                except (TypeError, ValueError):
                    raise CommunityError("Not possible with this card") from None
                if n not in allowed:
                    raise CommunityError("Not possible with this card")
                owner, i = marble()
                if owner not in mine:
                    raise CommunityError("This is not your marble")
                home = mv.get("home")
                self._step(M, owner, i, n, home if home in (True, False) else None, False, ev)
                kind = "move"
            else:
                raise CommunityError("Not possible with this card")
        ev["kind"] = kind
        if rank(card) == JOKER and not self.r.get("joker_last", True) and self.side_done(M, pid):
            raise CommunityError("The joker may not be the card that wins")
        return M, ev

    def _simulate_any_order(self, pid: str, mv: dict) -> tuple[dict, dict]:
        """Like simulate – a 7-split that does not work in the given order is tried in the other orders too."""
        try:
            return self.simulate(pid, mv)
        except CommunityError:
            split = mv.get("split")
            if not isinstance(split, list) or not 1 < len(split) <= 5:
                raise
            from itertools import permutations
            for other in permutations(split):
                try:
                    return self.simulate(pid, {**mv, "split": list(other)})
                except CommunityError:
                    continue
            raise

    def legal(self, pid: str, mv: dict) -> bool:
        try:
            self.simulate(pid, mv)
            return True
        except CommunityError:
            return False

    # ---------- the legal moves (for bots, the view and «cannot play»)
    def _candidates(self, pid: str, rk: str, cap7: int = CAP7):
        M = self.st["marbles"]
        mine = self.controlled(M, pid)
        mbl = [(o, i) for o in mine for i in range(4)]
        if rk == "7":
            yield from self._splits(pid, cap7)
            return
        if rk == "J":
            others = [(o, j) for o in M for j in range(4) if 0 <= M[o][j][0] < RING and not M[o][j][1]]
            for o, i in mbl:
                if 0 <= M[o][i][0] < RING and not M[o][i][1]:
                    for o2, j in others:
                        if o2 != o:
                            yield {"kind": "swap", "marble": mid(o, i), "target": mid(o2, j)}
            return
        if rk in ("A", "K"):
            for o in mine:                                    # one marble of the kennel is enough (they are all alike)
                k = next((i for i in range(4) if M[o][i][0] == -1), None)
                if k is not None:
                    yield {"kind": "out", "marble": mid(o, k)}
        steps = {"A": (1, 11), "K": (13,), "Q": (12,)}.get(rk) or (int(rk),)
        for o, i in mbl:
            if M[o][i][0] < 0:
                continue
            for n in steps:
                if self._can_reach_home(M, o, i, n):
                    yield {"kind": "move", "marble": mid(o, i), "steps": n, "home": True}
                yield {"kind": "move", "marble": mid(o, i), "steps": n, "home": False}
            if rk == "4" and M[o][i][0] < RING:
                yield {"kind": "back", "marble": mid(o, i)}

    def _splits(self, pid: str, cap: int):
        """Legal 7-splits: a depth-first search over the movable marbles in any order (each marble once), every step
        checked on a copy – illegal beginnings are cut off, equal results come only once."""
        cand = [parse_mid(m) for m in self.seven_marbles(pid)]
        seen, results = set(), set()
        count = 0

        def sig(M):
            return tuple(tuple(x for pr in M[p] for x in pr) for p in sorted(M))

        def rec(M, left, used, parts):
            nonlocal count
            key = (sig(M), left, used)
            if key in seen:
                return
            seen.add(key)
            if left == 0:
                s = key[0]
                if s not in results:
                    results.add(s)
                    count += 1
                    yield [list(x) for x in parts]
                return
            owners = self.seven_owners(M, pid)
            for k, (o, i) in enumerate(cand):
                if used >> k & 1 or o not in owners or M[o][i][0] < 0:
                    continue
                for n in range(left, 0, -1):
                    for hm in ((True, False) if self._can_reach_home(M, o, i, n) else (False,)):
                        M2 = self._copy(M)
                        try:
                            self._step(M2, o, i, n, hm, True, {"moved": [], "kicked": [], "home": []})
                        except CommunityError:
                            continue
                        parts.append((mid(o, i), n, hm))
                        yield from rec(M2, left - n, used | 1 << k, parts)
                        parts.pop()
                        if count >= cap:
                            return

        for split in rec(self._copy(self.st["marbles"]), 7, 0, []):
            yield {"kind": "seven", "split": split}
            if count >= cap:
                return

    def moves(self, pid: str, cap7: int = CAP7, first: bool = False) -> list[dict]:
        """The legal moves of this player (first=True: stop at the first one)."""
        out = []
        hand = sorted(self.st["hands"].get(pid) or [], key=lambda c: rank(c) in ("7", JOKER))
        seen = set()
        for card in hand:
            rk = rank(card)
            if rk in seen:
                continue
            seen.add(rk)
            for r in (JOKER_AS if rk == JOKER else (rk,)):
                for mv in self._candidates(pid, r, cap7):
                    mv = {**mv, "card": card}
                    if rk == JOKER:
                        mv["as"] = r
                    if self.legal(pid, mv):
                        out.append(mv)
                        if first:
                            return out
        return out

    def has_move(self, pid: str) -> bool:
        return bool(self.moves(pid, cap7=10 ** 6, first=True))

    def my_turn(self, pid: str) -> bool:
        return self.st.get("phase") == "play" and self.st.get("turn") == pid

    def play(self, pid: str, mv: dict) -> dict:
        if not self.my_turn(pid):
            raise CommunityError("It is not your turn")
        M, ev = self._simulate_any_order(pid, mv)
        self.st["marbles"] = M
        card = mv["card"]
        self.st["hands"][pid].remove(card)
        self.st["discard"].append(card)
        self._log({"player": pid, "card": card, "as": ev["rank"] if rank(card) == JOKER else None, "kind": ev["kind"],
                   "moved": ev["moved"], "kicked": ev["kicked"], "home": ev["home"], "swap": ev.get("swap")})
        for p in self.order():                               # who has all 4 home (finishing order)
            if self.all_home(M, p) and p not in self.st["finished_order"]:
                self.st["finished_order"].append(p)
        if self.side_done(M, pid):
            self._finish(self.side(pid))
            return ev
        self._advance(pid)
        return ev

    def progress(self, pid: str) -> int:
        out = 0
        for pos, _ in self.st["marbles"][pid]:
            if pos >= HOME:
                out += 100 + pos - HOME
            elif pos >= 0:
                out += 1 + (pos - self.start_of(pid)) % RING
        return out

    def _finish(self, winner: str | None) -> None:
        self.st["phase"] = "done"
        self.st["turn"] = None
        self.st["winner"] = winner
        order = self.order()
        if self.teams():
            def key(s):
                return (s != winner, -sum(self.progress(p) for p in self.members(s)))
            ranked = sorted(self.sides(), key=key)
            self.st["places"] = {p: n + 1 for n, s in enumerate(ranked) for p in self.members(s)}
            self.st["ranking"] = [p for s in ranked for p in self.members(s)]
        else:
            fin = self.st.get("finished_order") or []
            score = {p: (1000 - fin.index(p) if p in fin else 0) * 1000 + self.progress(p) for p in order}
            self.st["places"] = places(order, score)
            self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st["finished"] = self.now()

    # ---------- bots
    def _value(self, M: dict, pid: str, level: str) -> float:
        """How good the marbles are for this player's side (the bigger the better)."""
        me = set(self.members(self.side(pid)))
        occ_opp = [(p, pos) for p, ms in M.items() if p not in me for pos, _ in ms if 0 <= pos < RING]
        total = 0.0
        for p, ms in M.items():
            sign = 1.0 if p in me else -0.8
            start = self.start_of(p)
            for pos, fresh in ms:
                if pos < 0:
                    v = 0.0
                elif pos >= HOME:
                    v = 120 + (pos - HOME) * 3
                else:
                    v = 30 + (pos - start) % RING
                    if p in me and not fresh:
                        # danger: opponents up to 12 fields behind could land here
                        danger = sum(1 for _, q in occ_opp if 1 <= (pos - q) % RING <= 12)
                        v -= (3 if level == "normal" else 6) * danger
                    if fresh and p in me:
                        v += 4
                total += sign * v
        return total

    def _card_cost(self, pid: str, mv: dict, level: str) -> float:
        if level != "hard":
            return 0
        rk = rank(mv["card"])
        kennel = sum(1 for pos, _ in self.st["marbles"][pid] if pos < 0)
        outs = sum(1 for c in self.st["hands"][pid] if rank(c) in ("A", "K", JOKER))
        cost = {JOKER: 14, "7": 6, "J": 3, "4": 2}.get(rk, 0)
        if rk in ("A", "K") and mv.get("kind") != "out" and kennel and outs <= 1:
            cost += 18                                       # keep the last ace / king to come out
        return cost

    def bot_choice(self, pid: str, level: str = "normal") -> dict | None:
        moves = self.moves(pid, cap7=CAP7 if level == "hard" else 60)
        if not moves:
            return None
        if level == "easy":
            cards = sorted({m["card"] for m in moves})
            card = self.rng.choice(cards)
            return self.rng.choice([m for m in moves if m["card"] == card])
        best, best_v = None, None
        for mv in moves:
            M, ev = self.simulate(pid, mv)
            v = self._value(M, pid, level) - self._card_cost(pid, mv, level) + self.rng.random() * 0.5
            if ev["kind"] == "out":
                v += 8
            if self.side_done(M, pid):
                v += 10000
            if best_v is None or v > best_v:
                best, best_v = mv, v
        return best

    def bot_give(self, pid: str) -> str:
        """The card for the partner: an ace / king if the partner has marbles in the kennel and we have one to spare,
        else the card we need the least."""
        hand = self.st["hands"][pid]
        pa = self.partner(pid)
        M = self.st["marbles"]
        outs = [c for c in hand if rank(c) in ("A", "K")]
        mine_k = sum(1 for pos, _ in M[pid] if pos < 0)
        if pa and any(pos < 0 for pos, _ in M[pa]) and outs and (len(outs) > 1 or not mine_k):
            return outs[0]
        worth = {JOKER: 50, "7": 20, "A": 15 if mine_k else 8, "K": 14 if mine_k else 9, "4": 10, "J": 9}
        return min(hand, key=lambda c: (worth.get(rank(c), 5), self.rng.random()))

    def tick(self) -> bool:
        """Bots give and move, the next round starts. True if something changed."""
        changed = False
        for _ in range(4):
            ph = self.st.get("phase")
            if ph == "between" and self.now() >= self.st.get("next_at", 0):
                self.new_round()
                changed = True
                continue
            if ph == "exchange":
                bots = [p for p in self.order() if (self.seat_of(p) or {}).get("bot") and not self.st["give"].get(p)]
                if not bots:
                    break
                for p in bots:
                    self.give(p, self.bot_give(p))
                changed = True
                continue
            if ph != "play":
                break
            p = self.seat_of(self.st.get("turn") or "")
            if not p or not p.get("bot") or self.now() - self.st.get("turn_at", 0) < bot_delay(self.r, BOT_DELAY):
                break
            mv = self.bot_choice(p["id"], p.get("level", "normal"))
            if mv is None:                                   # cannot happen (_advance checks) – be safe
                self._advance(p["id"])
            else:
                self.play(p["id"], mv)
            changed = True
        return changed


# ================================================================ the games in the database (table card_game, kind "kartenlauf")
class Kartenlauf(CardGames):
    """The family table / own tables against bots – the same rows and lobby as the card games (end, summary)."""

    def __init__(self, db, add_history=None, rewards=None):
        super().__init__(db, add_history)
        self.rewards = rewards

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, {**DEFAULTS, **(self.db.get_setting(f"game_rules.{KIND}") or {})})

    def rules_info(self) -> dict:
        return {**self.default_rules(), "rewards": rewards_of(self.db)}

    def clean_rules(self, kind: str, r: dict) -> dict:
        out = {}
        for k, v in DEFAULTS.items():
            x = r.get(k, v)
            if isinstance(v, bool):
                out[k] = bool(x)
            elif isinstance(v, int):
                try:
                    out[k] = int(x)
                except (TypeError, ValueError):
                    out[k] = v
            else:
                out[k] = str(x)
        out["seats"] = out["seats"] if out["seats"] in (2, 3, 4) else 4
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
        if status != "done" or st.get("paid") or not st.get("places"):
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
                if p.get("bot"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {"place": st["places"].get(p["id"]), "players": len(st["players"]),
                                                         "teams": bool(st.get("teams")), "home": t.home_count(st["marbles"], p["id"]),
                                                         "coins": coins.get(p["id"], 0)})
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

    def _bots(self, st: dict, need: int) -> list[dict]:
        pool = st.pop("bot_pool", None) or []
        taken = {b["name"] for b in pool}
        for n, e in random.sample(BOTS, len(BOTS)):
            if len(pool) >= need:
                break
            if n not in taken:
                pool.append({"name": n, "emoji": e, "level": st["rules"]["level"]})
        out = []
        for i, b in enumerate(pool[:need]):
            lvl = b.get("level") if b.get("level") in LEVELS else st["rules"]["level"]
            out.append({"id": f"bot{i + 1}", "name": b["name"], "emoji": b.get("emoji") or "🤖", "color": b.get("color"),
                        "owner": b.get("owner"), "bot": True, "level": lvl})
        return out

    def _deal(self, st: dict) -> None:
        humans = [p for p in st["players"] if not p.get("bot")]
        seats = max(st["rules"]["seats"], len(humans))
        st["players"] = humans + self._bots(st, seats - len(humans))
        if len(st["players"]) < 2:
            raise CommunityError("Add a bot or wait for a second player")
        Table(st).setup()

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
            if solo:                                      # alone against bots: deal right away
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
            if len(st["players"]) >= 4:
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

    def _with(self, viewer: int, fn) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            t = Table(st)
            t.tick()
            fn(t)
            self._save(row, st)

    def play(self, kind: str, pid: int, move: dict) -> None:
        self._with(pid, lambda t: t.play(str(pid), move))

    def give(self, kind: str, pid: int, card: str) -> None:
        self._with(pid, lambda t: t.give(str(pid), card))

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
        joined = any(p["id"] == me for p in st["players"])
        coins = st.get("coins") or {}
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        base = {"game": row["id"], "starter": st.get("starter"), "kind": KIND, "title": TITLE, "status": row["status"], "phase": st["phase"],
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "joined": joined,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            return {**base, "players": players, "free": max(0, st["rules"]["seats"] - len(players))}
        t = Table(st)
        hands = st.get("hands") or {}
        pl = st.get("places") or {}
        M = st["marbles"]
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                    "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"), "seat": st["seats"][p["id"]],
                    "side": t.side(p["id"]), "partner": t.partner(p["id"]), "cards": len(hands.get(p["id"], [])),
                    "home": t.home_count(M, p["id"]), "gave": bool((st.get("give") or {}).get(p["id"])),
                    "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0)}
                   for p in sorted(st["players"], key=lambda x: st["seats"][x["id"]])]
        marbles = [{"id": mid(p, i), "owner": p, "pos": pos, "fresh": bool(fresh)} for p, ms in M.items() for i, (pos, fresh) in enumerate(ms)]
        hand = hands.get(me) if joined else None
        my_turn = t.my_turn(me)
        moves, seven, seven_marbles = [], {}, []
        if my_turn:
            moves = [mv for mv in t.moves(me, cap7=1) if mv["kind"] != "seven"]   # 7-splits: the player builds them
            for card in dict.fromkeys(hand or []):
                if rank(card) in ("7", JOKER):
                    seven[card] = self._seven_ok(t, me, card)
            seven_marbles = t.seven_marbles(me)
        last_cards = (st.get("discard") or [])[-1:]
        return {**base, "players": players, "teams": t.teams(), "my_side": t.side(me) if joined else None,
                "my_seat": st["seats"].get(me) if joined else None, "control": t.controlled(M, me) if joined else [],
                "round": st.get("round", 0), "round_size": st.get("round_size"), "dealer": st.get("dealer"),
                "marbles": marbles, "turn": st.get("turn"), "my_turn": my_turn, "last": st.get("last"), "log": st.get("log") or [],
                "top": last_cards[0] if last_cards else None, "discarded": len(st.get("discard") or []), "deck_left": len(st.get("deck") or []),
                "hand": hand, "moves": moves, "seven": seven, "seven_marbles": seven_marbles,
                "exchange": st["phase"] == "exchange", "gave": (st.get("give") or {}).get(me) if joined else None,
                "got": (st.get("got") or {}).get(me) if joined else None,
                "winner": st.get("winner"), "ranking": st.get("ranking"), "finished_order": st.get("finished_order") or [],
                "next_ms": max(0, int((st.get("next_at", 0) - time.time()) * 1000)) if st["phase"] == "between" else None}

    @staticmethod
    def _seven_ok(t: Table, me: str, card: str) -> bool:
        """Whether this card can be played as a 7 (stops at the first legal split)."""
        for mv in t._splits(me, 10 ** 6):
            mv = {**mv, "card": card}
            if rank(card) == JOKER:
                mv["as"] = "7"
            if t.legal(me, mv):
                return True
        return False
