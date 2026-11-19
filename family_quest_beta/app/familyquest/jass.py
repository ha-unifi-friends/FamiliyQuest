"""«Jass» – the Swiss card game Schieber (traditional public-domain rules), live for the family.

Everybody plays on their own device (family table, guests via QR code) or a child plays with 3 bots – the tables live in
the `card_game` table with kind "jass" (lobby, join, summary, may_lead from cardgames.CardGames, like «Heimwärts»).

4 players in 2 teams, partners sit opposite (seats 0 + 2 against 1 + 3); free seats are taken by bots. Rule `partners`
(default on): two people with two bots play together as partners (off: against each other). Who leads can mix the
seats in the lobby. Play passes to the right (seat order 0 → 1 → 2 → 3).
Cards (rule `deck`): Swiss (Schellen, Schilten, Rosen, Eicheln; 6–9, Banner, Under, Ober, König, Ass) or French
(♠ ♥ ♦ ♣; 6–10, J, Q, K, A) – the J counts as Under, the Q as Ober. 36 cards, 9 each, shuffled with `secrets`.

A round: the player whose turn it is chooses («ansagen») Trumpf (one of the 4 suits), Obenabe (no trump, the Ass is
highest) or Undeufe (no trump, the 6 is highest) – or «schiebt» to the partner, who then must choose. In the first
round the holder of the Schellen 7 (♦ 7) chooses, then the next seat to the right; the player who chose (or pushed)
leads the first trick, the winner of a trick leads the next one.
Following: you must follow suit if you can; you may always trump in instead (Trumpf game), but never under-trump
(play a trump lower than a trump already in the trick) – unless you only hold trumps. Trump led: you must follow with
a trump – except when the Buur (Under of trump) is your only trump (he may always be held back).
Ranking: trump Buur > Nell (9) > A > K > O > 10 > 8 > 7 > 6; other suits and Obenabe A > K > O > U > 10 > 9 > 8 > 7 > 6;
Undeufe the other way round. Card points: trump Buur 20, Nell 14, A 11, K 4, O 3, 10 10; other suits A 11, K 4, O 3,
U 2, 10 10; Obenabe / Undeufe: no trump, the 8 counts 8 (Undeufe: the 6 counts 11, the Ass 0). The last trick +5:
always 157 per round; all 9 tricks to one team («Match») +100.
Weis (rule `weis`, default on): declared with the first card (automatically): Dreiblatt 20, Vierblatt 50, Fünfblatt 100,
Sechsblatt 150, Siebenblatt 200, Achtblatt 250, Neunblatt 300 (in a suit, natural order 6 7 8 9 10 U O K A); four of a
kind: 4 Under 200, 4 Nell 150, 4 Ass / König / Ober / Banner 100. Only the team with the best single Weis (points, then
more cards, then the higher card – Undeufe the lower –, then trump, then who played first) writes all of its Weis.
Stöck (rule `stoeck`, default on): König and Ober of trump in one hand, 20 points – announced with the second of them,
they always count.
Multipliers (rule `mult`, default off): Rosen / Schellen (♥ ♦) ×1, Schilten / Eicheln (♠ ♣) ×2, Obenabe / Undeufe ×3 –
the whole round (cards, Match, Weis, Stöck) counts that many times.
End (rule `goal`): «points» – the first team at the target (`target`, default 1000, checked at the end of a round; both
over it: more points wins) – or «rounds» – after `rounds` rounds. Who leads may end the game early: ranked as it
stands, but coins only for a game played to the end.
Coins (setting `game_rewards["jass"]`): the members of the winning team get the coins for place 1 – only people of the
family at a family table with at least two of them, never alone against bots; paid once (flag `paid`, a unique ledger
`ref` per player). Winners get the «No. 1» hat (_champion; not on a tie), everybody of the family a history entry.
Bots (easy / normal / hard: hard counts the cards, plays partner-aware, chooses the trump by the strength of the hand and
pushes a weak hand) play with a reaction time (bot_ms).
"""
from __future__ import annotations

import json
import random
import secrets
import time

from .cardgames import BOTS, BOT_DELAY, CardGames, bot_delay
from .community import CommunityError
from .pairhunt import rewards_of as _rewards_of
from .running import win_reason

KIND = "jass"
TITLE = "Jass"
EMOJI = "♣️"
SEATS = 4
HAND = 9
LEVELS = ("easy", "normal", "hard")
DECKS = {"swiss": ["schellen", "schilten", "rosen", "eicheln"], "french": ["s", "h", "c", "d"]}
RANKS = {"swiss": ["6", "7", "8", "9", "10", "U", "O", "K", "A"], "french": ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]}
NATURAL = ["6", "7", "8", "9", "10", "U", "O", "K", "A"]                 # low → high (canonical ranks)
TRUMP_ORDER = ["6", "7", "8", "10", "O", "K", "A", "9", "U"]             # low → high
FIRST = {"swiss": "schellen:7", "french": "d:7"}                         # who holds it chooses in the first round
MULT = {"rosen": 1, "schellen": 1, "schilten": 2, "eicheln": 2, "h": 1, "d": 1, "s": 2, "c": 2, "obe": 3, "une": 3}
SEQ_POINTS = {3: 20, 4: 50, 5: 100, 6: 150, 7: 200, 8: 250, 9: 300}
FOUR_POINTS = {"U": 200, "9": 150, "A": 100, "K": 100, "O": 100, "10": 100}
LAST_TRICK = 5
MATCH = 100
TARGETS = (500, 1000, 1500, 2500)
BETWEEN = 12                   # seconds the round result stays before the next round is dealt (or tap «Next round»)
DEFAULTS = {"deck": "swiss", "level": "normal", "bot_ms": 1400, "weis": True, "stoeck": True, "mult": False,
            "goal": "points", "target": 1000, "rounds": 4, "partners": True, "back": "classic"}


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def suit(card: str) -> str:
    return card.split(":")[0]


def rank(card: str) -> str:
    """The canonical rank: the J is the Under, the Q the Ober."""
    r = card.split(":")[1]
    return {"J": "U", "Q": "O"}.get(r, r)


def deck(kind: str) -> list[str]:
    return [f"{s}:{r}" for s in DECKS[kind] for r in RANKS[kind]]


def points(card: str, mode: str) -> int:
    s, r = suit(card), rank(card)
    if s == mode:
        return {"U": 20, "9": 14, "A": 11, "K": 4, "O": 3, "10": 10}.get(r, 0)
    if mode == "obe":
        return {"A": 11, "K": 4, "O": 3, "U": 2, "10": 10, "8": 8}.get(r, 0)
    if mode == "une":
        return {"6": 11, "K": 4, "O": 3, "U": 2, "10": 10, "8": 8}.get(r, 0)
    return {"A": 11, "K": 4, "O": 3, "U": 2, "10": 10}.get(r, 0)


def order_in_suit(card: str, mode: str) -> int:
    """The height of a card within its own suit in this game (higher wins)."""
    r = rank(card)
    if suit(card) == mode:
        return TRUMP_ORDER.index(r)
    if mode == "une":
        return 8 - NATURAL.index(r)
    return NATURAL.index(r)


def strength(card: str, mode: str, lead: str) -> int:
    """How strong a card is in a trick with this led suit (trump > led suit > the rest)."""
    if suit(card) == mode:
        return 200 + order_in_suit(card, mode)
    if suit(card) == lead:
        return 100 + order_in_suit(card, mode)
    return order_in_suit(card, mode) - 100


def trick_winner(trick: list, mode: str) -> int:
    """The index (in the trick) of the card that takes it."""
    lead = suit(trick[0][1])
    return max(range(len(trick)), key=lambda i: strength(trick[i][1], mode, lead))


def weis_of(hand: list[str]) -> list[dict]:
    """All Weis in a hand: the longest runs in a suit (3 or more) and four of a kind."""
    out = []
    for s in dict.fromkeys(suit(c) for c in hand):
        cards = sorted((c for c in hand if suit(c) == s), key=lambda c: NATURAL.index(rank(c)))
        run = []
        for c in cards + [None]:
            if c is not None and run and NATURAL.index(rank(c)) == NATURAL.index(rank(run[-1])) + 1:
                run.append(c)
                continue
            if len(run) >= 3:
                out.append({"kind": "seq", "cards": list(run), "points": SEQ_POINTS[len(run)], "suit": s})
            run = [c] if c is not None else []
    for r, pts in FOUR_POINTS.items():
        four = [c for c in hand if rank(c) == r]
        if len(four) == 4:
            out.append({"kind": "four", "cards": four, "points": pts, "suit": None})
    return out


def weis_key(w: dict, mode: str) -> tuple:
    """Which single Weis is better: points, more cards, the higher (Undeufe: the lower) card, trump."""
    nat = [NATURAL.index(rank(c)) for c in w["cards"]]
    height = -min(nat) if mode == "une" and w["kind"] == "seq" else max(nat)
    return (w["points"], len(w["cards"]), height, w.get("suit") == mode)


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

    def seat_of(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def idx(self, pid: str) -> int:
        return self.order().index(pid)

    def team(self, pid: str) -> int:
        return self.idx(pid) % 2

    def partner(self, pid: str) -> str:
        return self.order()[(self.idx(pid) + 2) % SEATS]

    def nxt(self, pid: str, k: int = 1) -> str:
        return self.order()[(self.idx(pid) + k) % SEATS]

    def suits(self) -> list[str]:
        return DECKS[self.r.get("deck", "swiss")]

    def modes(self) -> list[str]:
        return self.suits() + ["obe", "une"]

    def _log(self, ev: dict) -> None:
        ev["t"] = self.now()
        ev["seq"] = self.st.get("seq", 0) + 1
        self.st["seq"] = ev["seq"]
        log = self.st.setdefault("log", [])
        log.append(ev)
        del log[:-14]

    # ---------- the game
    def setup(self) -> None:
        if len(self.order()) != SEATS:
            raise CommunityError("Jass needs 4 players")
        self.st.update(totals=[0, 0], round=0, rounds_log=[], log=[], seq=0, ranking=None, places=None, complete=False)
        self.deal()

    def deal(self) -> None:
        d = deck(self.r.get("deck", "swiss"))
        self.rng.shuffle(d)
        ids = self.order()
        hands = {p: d[i * HAND:(i + 1) * HAND] for i, p in enumerate(ids)}
        rnd = self.st.get("round", 0) + 1
        if rnd == 1:
            first = FIRST[self.r.get("deck", "swiss")]
            chooser = next(p for p in ids if first in hands[p])
        else:
            chooser = self.nxt(self.st["chooser"])
        self.st.update(round=rnd, hands=hands, mode=None, chooser=chooser, picker=None, pushed=False, phase="trump",
                       turn=chooser, leader=chooser, trick=[], tricks=[0, 0], pts=[0, 0], played=[], last_trick=None,
                       weis={}, weis_win=None, weis_pts=[0, 0], stoeck=None, stoeck_n=0, stoeck_pts=[0, 0],
                       round_result=None, next_at=None, turn_at=self.now())

    def _check(self, pid: str, phase: str) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")
        if self.st.get("phase") != phase:
            raise CommunityError("Not now" if self.st.get("phase") in ("trump", "play", "between") else "The game is not running")
        if self.st.get("turn") != pid:
            raise CommunityError("It is not your turn")

    def choose(self, pid: str, mode: str) -> None:
        """Announce the trump (a suit, «obe», «une») – or «push» it to the partner (only once)."""
        self._check(pid, "trump")
        if mode == "push":
            if self.st["pushed"]:
                raise CommunityError("Pushed already – now you must choose")
            self.st.update(pushed=True, turn=self.partner(pid), turn_at=self.now())
            self._log({"kind": "push", "player": pid})
            return
        if mode not in self.modes():
            raise CommunityError("Choose a trump")
        self.st.update(mode=mode, picker=pid, phase="play", turn=self.st["chooser"], leader=self.st["chooser"], turn_at=self.now())
        if self.r.get("stoeck", True) and mode in self.suits():
            ko = {f"{mode}:{r}" for r in self._ranks_of("K", "O")}
            self.st["stoeck"] = next((p for p, h in self.st["hands"].items() if ko <= set(h)), None)
        self._log({"kind": "trump", "player": pid, "mode": mode, "pushed": self.st["pushed"]})

    def _ranks_of(self, *canon: str) -> list[str]:
        kind = self.r.get("deck", "swiss")
        return [RANKS[kind][NATURAL.index(c)] for c in canon]

    def trump(self) -> str | None:
        m = self.st.get("mode")
        return m if m in self.suits() else None

    def legal(self, pid: str) -> list[str]:
        """The cards this player may play now."""
        if self.st.get("phase") != "play" or self.st.get("turn") != pid:
            return []
        hand = self.st["hands"][pid]
        trick = self.st["trick"]
        if not trick:
            return list(hand)
        lead = suit(trick[0][1])
        tr = self.trump()
        same = [c for c in hand if suit(c) == lead]
        if tr and lead == tr:
            if any(rank(c) != "U" for c in same):          # must follow trump – unless the Buur is the only trump
                return same
            return list(hand)
        if not tr:
            return same or list(hand)
        cand = same + [c for c in hand if suit(c) == tr] if same else list(hand)
        in_trick = [c for _, c in trick if suit(c) == tr]
        if in_trick and not all(suit(c) == tr for c in hand):   # no under-trumping (unless only trumps are left)
            best = max(order_in_suit(c, tr) for c in in_trick)
            cand = [c for c in cand if suit(c) != tr or order_in_suit(c, tr) > best]
        return cand

    def play(self, pid: str, card: str) -> None:
        self._check(pid, "play")
        hand = self.st["hands"][pid]
        if card not in hand:
            raise CommunityError("You do not have this card")
        if card not in self.legal(pid):
            raise CommunityError("This card may not be played now")
        mode = self.st["mode"]
        if len(hand) == HAND and self.r.get("weis", True):          # Weis: declared with the first card
            ws = weis_of(hand)
            if ws:
                self.st["weis"][pid] = ws
                self._log({"kind": "weis", "player": pid, "points": sum(w["points"] for w in ws),
                           "best": max(ws, key=lambda w: weis_key(w, mode))["points"]})
        hand.remove(card)
        self.st["trick"].append([pid, card])
        if self.st.get("stoeck") == pid and suit(card) == mode and rank(card) in ("K", "O"):
            self.st["stoeck_n"] = self.st.get("stoeck_n", 0) + 1
            if self.st["stoeck_n"] == 2:
                self.st["stoeck_pts"][self.team(pid)] += 20
                self._log({"kind": "stoeck", "player": pid})
        self._log({"kind": "card", "player": pid, "card": card})
        if len(self.st["trick"]) < SEATS:
            self.st.update(turn=self.nxt(pid), turn_at=self.now())
            return
        self._take_trick()

    def _take_trick(self) -> None:
        trick, mode = self.st["trick"], self.st["mode"]
        w = trick[trick_winner(trick, mode)][0]
        t = self.team(w)
        n = sum(self.st["tricks"]) + 1
        pts = sum(points(c, mode) for _, c in trick) + (LAST_TRICK if n == HAND else 0)
        self.st["tricks"][t] += 1
        self.st["pts"][t] += pts
        self.st["played"] += [c for _, c in trick]
        self.st["last_trick"] = {"cards": [list(x) for x in trick], "winner": w, "points": pts, "no": n}
        self._log({"kind": "trick", "player": w, "points": pts, "no": n})
        if n == 1:
            self._weis_resolve(trick[0][0])
        self.st.update(trick=[], leader=w, turn=w, turn_at=self.now())
        if n == HAND:
            self._round_end()

    def _weis_resolve(self, first: str) -> None:
        weis, mode = self.st.get("weis") or {}, self.st["mode"]
        if not weis:
            return
        play_order = [self.nxt(first, k) for k in range(SEATS)]
        best = max(weis, key=lambda p: (max(weis_key(w, mode) for w in weis[p]), -play_order.index(p)))
        t = self.team(best)
        team_weis = {p: ws for p, ws in weis.items() if self.team(p) == t}
        total = sum(w["points"] for ws in team_weis.values() for w in ws)
        self.st["weis_pts"][t] += total
        self.st["weis_win"] = {"team": t, "points": total, "shown": team_weis}
        self._log({"kind": "weis_win", "team": t, "player": best, "points": total})

    def multiplier(self) -> int:
        return MULT.get(self.st.get("mode"), 1) if self.r.get("mult") else 1

    def _round_end(self) -> None:
        match = [MATCH if self.st["tricks"][t] == HAND else 0 for t in (0, 1)]
        mult = self.multiplier()
        res = [(self.st["pts"][t] + match[t] + self.st["weis_pts"][t] + self.st["stoeck_pts"][t]) * mult for t in (0, 1)]
        for t in (0, 1):
            self.st["totals"][t] += res[t]
        rr = {"round": self.st["round"], "mode": self.st["mode"], "picker": self.st["picker"], "points": res,
              "cards": list(self.st["pts"]), "match": next((t for t in (0, 1) if match[t]), None),
              "weis": list(self.st["weis_pts"]), "stoeck": list(self.st["stoeck_pts"]), "mult": mult, "totals": list(self.st["totals"])}
        self.st["round_result"] = rr
        self.st["rounds_log"].append(rr)
        self._log({"kind": "round", "points": res, "match": rr["match"]})
        tot = self.st["totals"]
        if self.r.get("goal") == "rounds":
            over = self.st["round"] >= int(self.r.get("rounds") or 1)
        else:
            over = max(tot) >= int(self.r.get("target") or 1000)
        if over:
            self.st["complete"] = True
            self._finish()
            return
        people = any(not p.get("bot") for p in self.st["players"])
        self.st.update(phase="between", turn=None, next_at=self.now() + (BETWEEN if people else 0))

    def next_round(self, pid: str | None = None) -> None:
        if pid is not None and pid not in self.order():
            raise CommunityError("You are not at this table")
        if self.st.get("phase") == "between":
            self.deal()

    def _finish(self) -> None:
        order = self.order()
        tot = self.st.get("totals") or [0, 0]
        self.st["places"] = {p: 1 if tot[self.team(p)] >= max(tot) else 2 for p in order}     # a tie: both teams first
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st.update(phase="done", turn=None, finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: ranked as it stands (no coins – see coins_for)."""
        if self.st.get("phase") in ("trump", "play", "between"):
            self._finish()

    # ---------- bots
    def _mode_score(self, hand: list[str], mode: str) -> float:
        """How good this hand is for this game (bigger: more points to expect)."""
        if mode in ("obe", "une"):
            top = ["A", "K", "O", "U", "10", "9", "8", "7", "6"] if mode == "obe" else NATURAL
            s = 0.0
            for su in self.suits():
                rs = {rank(c) for c in hand if suit(c) == su}
                k = 0
                while k < len(top) and top[k] in rs:
                    k += 1
                s += [0, 11, 20, 27, 32, 36, 39, 41, 42, 43][k]
                if k == 0 and top[1] in rs and len(rs) >= 2:
                    s += 4                                    # a protected second card
                if k >= 2:
                    s += 3 * (len(rs) - k)                    # the rest of a strong suit comes home too
            return s
        tr = {rank(c) for c in hand if suit(c) == mode}
        s = 7.0 * len(tr)
        s += 15 if "U" in tr else 0
        s += 10 if "9" in tr else 0
        s += 5 if "A" in tr else 0
        s += 2 * len(tr & {"K", "O", "10"})
        for su in self.suits():
            if su == mode:
                continue
            rs = {rank(c) for c in hand if suit(c) == su}
            s += 6 if "A" in rs else 0
            s += 2 if {"A", "K"} <= rs else 0
            if not rs and len(tr) >= 3:
                s += 3                                        # void: trump in
        return s

    def bot_choose(self, pid: str, level: str = "normal") -> str:
        hand = self.st["hands"][pid]
        can_push = not self.st["pushed"]
        sc = {m: self._mode_score(hand, m) for m in self.modes()}
        if level == "easy":
            if can_push and self.rng.random() < 0.15:
                return "push"
            return max(sc, key=lambda m: sc[m] + self.rng.random() * 25)
        best = max(sc, key=lambda m: (sc[m], self.rng.random()))
        limit = 40 if level == "hard" else 34
        if can_push and sc[best] < limit:
            return "push"
        return best

    def _unseen(self, pid: str) -> list[str]:
        """Cards nobody has played yet that are not in this hand (hard bots count the cards)."""
        seen = set(self.st.get("played") or []) | {c for _, c in self.st["trick"]} | set(self.st["hands"][pid])
        return [c for c in deck(self.r.get("deck", "swiss")) if c not in seen]

    def _master(self, card: str, unseen: list[str]) -> bool:
        """No card that is still out could beat it in its suit."""
        mode = self.st["mode"]
        return not any(suit(c) == suit(card) and order_in_suit(c, mode) > order_in_suit(card, mode) for c in unseen)

    def bot_card(self, pid: str, level: str = "normal") -> str:
        legal = self.legal(pid)
        if len(legal) == 1 or level == "easy" and self.rng.random() < 0.7:
            return self.rng.choice(legal)
        mode, trick, tr = self.st["mode"], self.st["trick"], self.trump()
        hard = level == "hard"
        unseen = self._unseen(pid) if hard else [c for c in deck(self.r.get("deck", "swiss")) if c not in self.st["hands"][pid]]
        is_tr = lambda c: suit(c) == tr                                  # noqa: E731
        low = lambda c: (is_tr(c), points(c, mode), order_in_suit(c, mode) + (20 if hard and self._master(c, unseen) else 0))  # noqa: E731
        if not trick:                                                    # lead
            hand = self.st["hands"][pid]
            if tr and hard:
                mine = [c for c in hand if is_tr(c)]
                out = [c for c in unseen if is_tr(c)]
                ours = self.st["picker"] in (pid, self.partner(pid))
                if mine and out and (ours or len(mine) >= 3):
                    top = max(mine, key=lambda c: order_in_suit(c, mode))
                    if self._master(top, unseen):
                        return top                                       # pull the trumps
            masters = [c for c in legal if not is_tr(c) and self._master(c, unseen)]
            if tr and hard:
                trumps_out = any(is_tr(c) for c in unseen)
                masters = [c for c in masters if not trumps_out or points(c, mode) >= 10]
            if masters:
                return max(masters, key=lambda c: (points(c, mode), order_in_suit(c, mode)))
            plain = [c for c in legal if not is_tr(c)] or legal
            longest = max(self.suits(), key=lambda s: sum(1 for c in plain if suit(c) == s))
            return min([c for c in plain if suit(c) == longest] or plain, key=low)
        lead = suit(trick[0][1])
        wi = trick_winner(trick, mode)
        wpid, wcard = trick[wi]
        best = strength(wcard, mode, lead)
        last = len(trick) == SEATS - 1
        tpts = sum(points(c, mode) for _, c in trick)
        beats = [c for c in legal if strength(c, mode, lead) > best]
        if self.team(wpid) == self.team(pid):                           # the partner takes it so far
            safe = last or (self._master(wcard, unseen) and not (tr and suit(wcard) != tr and hard
                                                                   and any(is_tr(c) for c in unseen)))
            if not hard:
                safe = last or rank(wcard) in ("A", "U") or (mode == "une" and rank(wcard) == "6")
            if safe:
                plain = [c for c in legal if not is_tr(c)]
                if plain:                                                # «schmieren»: give points to the partner
                    return max(plain, key=lambda c: (points(c, mode) if not (hard and self._master(c, unseen) and not last) else -1,
                                                     -order_in_suit(c, mode)))
            return min(legal, key=low)
        if beats:
            plain = [c for c in beats if not is_tr(c)]
            if last:
                if plain:
                    return min(plain, key=lambda c: (order_in_suit(c, mode), points(c, mode)))
                if tpts >= 10 or not hard:
                    return min(beats, key=lambda c: (points(c, mode), order_in_suit(c, mode)))
            else:
                sure = [c for c in beats if self._master(c, unseen)] if hard else [c for c in plain if rank(c) in ("A",)]
                if sure and (not tr or not hard or lead == tr or not any(is_tr(c) for c in unseen) or tpts >= 10):
                    return min(sure, key=lambda c: (is_tr(c), points(c, mode)))
                if not plain and (tpts >= 10 or (hard and tpts >= 4)):
                    return min(beats, key=lambda c: (points(c, mode), order_in_suit(c, mode)))
        return min(legal, key=low)

    def tick(self) -> bool:
        """The bots choose and play (after their reaction time; at once with bot_ms 0), the next round starts. True if
        something changed."""
        changed = False
        delay = bot_delay(self.r, BOT_DELAY)
        for _ in range(SEATS * HAND * 60 if delay == 0 else 6):
            ph = self.st.get("phase")
            if ph == "between":
                if self.now() < (self.st.get("next_at") or 0):
                    break
                self.deal()
                changed = True
                continue
            if ph not in ("trump", "play"):
                break
            p = self.seat_of(self.st.get("turn") or "")
            if not p or not p.get("bot"):
                break
            wait = delay
            if ph == "play" and not self.st["trick"] and self.st.get("last_trick"):
                wait = delay + min(1.2, delay)                          # the full trick stays a moment
            if self.now() - self.st.get("turn_at", 0) < wait:
                break
            if ph == "trump":
                self.choose(p["id"], self.bot_choose(p["id"], p.get("level", "normal")))
            else:
                self.play(p["id"], self.bot_card(p["id"], p.get("level", "normal")))
            changed = True
        return changed


def seating(humans: list, bots: list, partners: bool = True) -> list:
    """The seats 0..3 (partners opposite): two people with two bots play together when `partners` is on."""
    h, b = list(humans), list(bots)
    if len(h) == 2:
        return [h[0], b[0], h[1], b[1]] if partners else [h[0], h[1], b[0], b[1]]
    return (h + b)[:SEATS]


# ================================================================ the games in the database (table card_game, kind "jass")
class Jass(CardGames):
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
        return {**self.default_rules(), "rewards": rewards_of(self.db), "targets": list(TARGETS)}

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
        out["deck"] = out["deck"] if out["deck"] in DECKS else "swiss"
        out["level"] = out["level"] if out["level"] in LEVELS else "normal"
        out["bot_ms"] = max(0, min(5000, out["bot_ms"]))
        out["goal"] = out["goal"] if out["goal"] in ("points", "rounds") else "points"
        out["target"] = max(300, min(5000, out["target"]))
        out["rounds"] = max(1, min(24, out["rounds"]))
        out["back"] = out["back"] if out["back"] in ("classic", "stars", "waves", "checks") else "classic"
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
        self._payout(KIND, row["id"], coins, lambda pid: win_reason(KIND, 1))
        tot = st.get("totals") or [0, 0]
        if tot[0] != tot[1]:                                            # a tie: nobody gets the «No. 1» hat
            self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history:
            t = Table(st)
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                me = t.team(p["id"])
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]), "points": tot[me], "other": tot[1 - me],
                        "partner": (t.seat_of(t.partner(p["id"])) or {}).get("name"), "rounds": len(st.get("rounds_log") or []),
                        "complete": bool(st.get("complete")), "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins for the winning team: the coins of place 1 for each person of the family in it – only with at least two
        people of the family at a family table, only for a game played to the end."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if st.get("solo") or len(people) < 2 or st.get("phase") != "done" or not st.get("complete"):
            return {}
        amount = rewards_of(self.db)[0]
        pl = st.get("places") or {}
        return {p["id"]: amount for p in people if pl.get(p["id"]) == 1 and amount > 0}

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
        humans = [p for p in st["players"] if not p.get("bot")][:SEATS]
        bots = self._bots(st, SEATS - len(humans))
        if len(humans) + len(bots) < SEATS:                            # bots switched off (parent area › Games)
            raise CommunityError("Jass needs 4 people when playing with bots is switched off")
        st["players"] = seating(humans, bots, st["rules"].get("partners", True))
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
            if solo:                                      # alone with bots: the game starts right away
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
            if len(st["players"]) >= SEATS:
                raise CommunityError("The table is full")
            st["players"].append(self._person(pid))
            self._save(row, st)

    def _lobby(self, viewer: int, fn) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            fn(st)
            self._save(row, st)

    def begin(self, kind: str, viewer: int) -> None:
        self._lobby(viewer, self._deal)

    def mix(self, viewer: int) -> None:
        """Who leads mixes the seats in the lobby (the teams: seats 1 + 3 against 2 + 4)."""
        self._lobby(viewer, lambda st: (self.rng or secrets.SystemRandom()).shuffle(st["players"]))

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

    def choose(self, pid: int, mode: str) -> None:
        return self._with(pid, lambda t: t.choose(str(pid), mode))

    def play_card(self, pid: int, card: str) -> None:
        return self._with(pid, lambda t: t.play(str(pid), card))

    def next_round(self, pid: int) -> None:
        return self._with(pid, lambda t: t.next_round(str(pid)))

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: ranked as it stands (coins only for a game played to the end)."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] in ("trump", "play", "between"):
                self.table(st).end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int) -> dict | None:
        with self.lock:
            row = self._row(KIND, viewer)
            if row:
                st = json.loads(row["state"])
                if st["phase"] in ("trump", "play", "between") and self.table(st).tick():
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

    @staticmethod
    def _pub(p: dict) -> dict:
        return {"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner")}

    def _view(self, row, st: dict, me: str) -> dict:
        joined = any(p["id"] == me for p in st["players"])
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        ph = st["phase"]
        if row["status"] == "done" and ph != "lobby":
            ph = "done"
        base = {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph,
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": st["rules"], "joined": joined,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2, "max_players": SEATS}
        if st["phase"] == "lobby":
            humans = [self._pub(p) for p in st["players"]]
            plan = seating(humans, [None] * (SEATS - len(humans)), st["rules"].get("partners", True))
            return {**base, "players": humans, "bots": SEATS - len(humans),
                    "seating": [{"id": p["id"] if p else None, "team": i % 2} for i, p in enumerate(plan)]}
        t = self.table(st)
        coins, pl = st.get("coins") or {}, st.get("places") or {}
        hands = st.get("hands") or {}
        players = [{**self._pub(p), "seat": i, "team": i % 2, "cards": len(hands.get(p["id"], [])),
                    "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0)} for i, p in enumerate(st["players"])]
        mode = st.get("mode")
        hand = None
        if joined:
            suits = t.suits()
            hand = sorted(hands.get(me, []), key=lambda c: (suits.index(suit(c)), -order_in_suit(c, mode or "obe")))
        playing = ph in ("trump", "play")
        my_turn = joined and playing and st.get("turn") == me
        weis = st.get("weis") or {}
        win = st.get("weis_win")
        return {**base, "players": players, "round": st.get("round", 0), "mode": mode, "chooser": st.get("chooser"),
                "picker": st.get("picker"), "pushed": bool(st.get("pushed")), "turn": st.get("turn") if playing else None,
                "leader": st.get("leader"), "trick": st.get("trick") or [], "last_trick": st.get("last_trick"),
                "tricks": st.get("tricks") or [0, 0], "pts": st.get("pts") or [0, 0], "totals": st.get("totals") or [0, 0],
                "weis": {p: sum(w["points"] for w in ws) for p, ws in weis.items()},
                "weis_win": win, "weis_pts": st.get("weis_pts") or [0, 0], "stoeck_pts": st.get("stoeck_pts") or [0, 0],
                "mult": t.multiplier() if mode else 1, "round_result": st.get("round_result"), "rounds_log": st.get("rounds_log") or [],
                "next_ms": max(0, int(((st.get("next_at") or 0) - self.now()) * 1000)) if ph == "between" else None,
                "me": me if joined else None, "my_seat": t.idx(me) if joined else None, "my_team": t.team(me) if joined else None,
                "hand": hand, "my_turn": my_turn, "legal": t.legal(me) if my_turn and st.get("phase") == "play" else [],
                "can_choose": my_turn and st.get("phase") == "trump", "can_push": my_turn and st.get("phase") == "trump" and not st.get("pushed"),
                "log": st.get("log") or [], "ranking": st.get("ranking"), "complete": bool(st.get("complete"))}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
