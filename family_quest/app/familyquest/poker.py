"""Texas Hold'em for the family table: everybody plays on their own phone (guests via QR code), only with play chips –
never with coins or points of the app.

Rules (no-limit Texas Hold'em): two hole cards each, five community cards (flop 3, turn 1, river 1), four betting
rounds. Blinds move with the dealer button; heads-up the dealer posts the small blind and acts first before the flop.
A raise must be at least the last raise; an all-in for less does not reopen the betting. Side pots are built from
what everybody put in; a split pot gives the odd chip to the first winner left of the dealer.

Settings (the one who starts sets them, the last ones are the default):
  start_chips, small_blind / big_blind, ante, blind increase every N minutes (0 = never, the blinds double),
  turn time in seconds (when it runs out: check if possible, else fold), pause between hands,
  mode «equal» (everybody starts with the same chips; who has none is out – the last one wins) or
  «bank» (a game leader manages buy-ins: players ask for chips, the leader gives them; with a limit of re-buys).

Alone against bots: animals (or the children's own bots) sit at the table and decide by the strength of their
cards, the pot odds and their level (easy bluffs and calls a lot, hard plays tight).
No background task: every request of the state moves the game on (time-outs, the next hand, the bots).
The state is one JSON document per game; the deck and the hole cards of the others never leave the server.
"""
from __future__ import annotations

import itertools
import json
import random
import threading
import time
from collections import Counter

from .community import CommunityError

RANKS = "23456789TJQKA"
SUITS = "shdc"
RULES_KEY = "game_rules.poker"
DEFAULT_RULES = {"start_chips": 1000, "small_blind": 10, "big_blind": 20, "ante": 0, "blind_minutes": 10,
                 "turn_seconds": 30, "pause_seconds": 6, "mode": "equal", "rebuys": 3, "max_players": 9}
BOT_DELAY = 1.3                       # seconds before a bot moves (so people can follow)
BOT_LEVELS = {"easy": {"noise": .25, "bluff": .22, "aggr": .25}, "normal": {"noise": .12, "bluff": .1, "aggr": .4},
              "hard": {"noise": .05, "bluff": .05, "aggr": .55}}
CATEGORIES = ["high_card", "pair", "two_pair", "three", "straight", "flush", "full_house", "four", "straight_flush"]


# ================================================================ cards and hands
def new_deck(rng: random.Random | None = None) -> list[str]:
    d = [r + s for r in RANKS for s in SUITS]
    (rng or random).shuffle(d)
    return d


def _rank5(cards: list[str]) -> tuple:
    vals = sorted((RANKS.index(c[0]) + 2 for c in cards), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    uniq = sorted(set(vals), reverse=True)
    straight_high = 0
    if len(uniq) == 5 and uniq[0] - uniq[4] == 4:
        straight_high = uniq[0]
    elif uniq == [14, 5, 4, 3, 2]:                      # wheel: A-2-3-4-5
        straight_high = 5
    cnt = Counter(vals)
    groups = sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape = [n for _, n in groups]
    order = [v for v, _ in groups]
    if straight_high and flush:
        return (8, straight_high)
    if shape == [4, 1]:
        return (7, *order)
    if shape == [3, 2]:
        return (6, *order)
    if flush:
        return (5, *vals)
    if straight_high:
        return (4, straight_high)
    if shape == [3, 1, 1]:
        return (3, *order)
    if shape == [2, 2, 1]:
        return (2, *order)
    if shape == [2, 1, 1, 1]:
        return (1, *order)
    return (0, *vals)


def best_hand(cards: list[str]) -> tuple[tuple, list[str]]:
    """Best five of five to seven cards → (rank tuple, the five cards)."""
    best = None
    for combo in itertools.combinations(cards, 5):
        r = _rank5(list(combo))
        if best is None or r > best[0]:
            best = (r, list(combo))
    return best


def strength(hole: list[str], board: list[str]) -> float:
    """Rough strength of a hand, 0 … 1 – for the bots."""
    v = sorted((RANKS.index(c[0]) + 2 for c in hole), reverse=True)
    if len(board) < 3:                                   # before the flop: pairs, high cards, suited, connected
        s = (v[0] + v[1]) / 28 * .55
        if v[0] == v[1]:
            s = .55 + v[0] / 14 * .4
        if hole[0][1] == hole[1][1]:
            s += .05
        if abs(v[0] - v[1]) == 1:
            s += .03
        return min(1.0, s)
    rank = best_hand(hole + board)[0]
    base = [0, .3, .5, .62, .72, .78, .86, .95, 1][rank[0]]
    # does the hand use my cards? a pair on the board helps everybody
    board_rank = best_hand(board)[0][0] if len(board) >= 5 else (-1 if len(board) < 5 else 0)
    if len(board) >= 5 and board_rank >= rank[0]:
        base *= .6
    return min(1.0, base + (rank[1] if len(rank) > 1 else 0) / 14 * .08)


def side_pots(contrib: dict[str, int], folded: set[str]) -> list[dict]:
    """Pots from what everybody put in: [{"amount", "eligible": [players still in the hand]}] – main pot first."""
    levels = sorted({v for p, v in contrib.items() if v > 0 and p not in folded})
    pots, prev = [], 0
    for lv in levels:
        amount = sum(min(v, lv) - min(v, prev) for v in contrib.values())
        eligible = [p for p, v in contrib.items() if v >= lv and p not in folded]
        if amount:
            pots.append({"amount": amount, "eligible": eligible})
        prev = lv
    rest = sum(v - min(v, prev) for v in contrib.values())     # chips of folded players above the last level
    if rest and pots:
        pots[-1]["amount"] += rest
    return pots


# ================================================================ one table
class Table:
    """The game state as a plain dict (stored as JSON). Player ids are strings (profile ids)."""

    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now

    # ---------- helpers
    @property
    def r(self) -> dict:
        return self.st["rules"]

    @property
    def hand(self) -> dict | None:
        return self.st.get("hand")

    def seat(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def in_game(self) -> list[dict]:
        return [p for p in self.st["players"] if p["chips"] > 0 and not p.get("out") and not p.get("away")]

    def blinds(self) -> tuple[int, int]:
        sb, bb = self.r["small_blind"], self.r["big_blind"]
        mins = self.r.get("blind_minutes") or 0
        if mins and self.st.get("started"):
            level = int((self.now() - self.st["started"]) // (mins * 60))
            sb, bb = sb * 2 ** level, bb * 2 ** level
        return sb, bb

    def _next_from(self, order: list[str], pid: str, cond) -> str | None:
        if not order:
            return None
        i = order.index(pid) if pid in order else -1
        for k in range(1, len(order) + 1):
            q = order[(i + k) % len(order)]
            if cond(q):
                return q
        return None

    def _put(self, pid: str, amount: int) -> int:
        p, h = self.seat(pid), self.hand
        amount = max(0, min(amount, p["chips"]))
        p["chips"] -= amount
        h["bets"][pid] = h["bets"].get(pid, 0) + amount
        h["contrib"][pid] = h["contrib"].get(pid, 0) + amount
        if p["chips"] == 0 and pid not in h["allin"]:
            h["allin"].append(pid)
        return amount

    def _log(self, text: str, **kw) -> None:
        self.st.setdefault("log", []).append({"t": round(self.now(), 1), "text": text, **kw})
        self.st["log"] = self.st["log"][-40:]

    # ---------- a new hand
    def deal(self) -> None:
        players = self.in_game()
        if len(players) < 2:
            if self.r["mode"] == "bank" and len([p for p in self.st["players"] if not p.get("away")]) >= 2:
                self.st["phase"] = "waiting"                 # the bank: wait until the game leader gives chips
                return
            self.finish()
            return
        order = [p["id"] for p in self.st["players"] if p in players]
        prev = self.st.get("dealer")
        dealer = self._next_from(order, prev, lambda q: True) if prev else order[0]
        self.st["dealer"] = dealer
        deck = new_deck(self.rng)
        sb_amt, bb_amt = self.blinds()
        h = {"no": self.st.get("hand_no", 0) + 1, "deck": deck, "board": [], "hole": {}, "bets": {}, "contrib": {},
             "folded": [], "allin": [], "street": "preflop", "order": order, "acted": [], "result": None,
             "sb": sb_amt, "bb": bb_amt}
        self.st["hand"] = h
        self.st["hand_no"] = h["no"]
        for pid in order:
            h["hole"][pid] = [deck.pop(), deck.pop()]
        if self.r.get("ante"):
            for pid in order:
                self._put(pid, self.r["ante"])
            h["bets"] = {}                                   # antes are dead money, not part of the first bet
        heads_up = len(order) == 2
        sb = dealer if heads_up else self._next_from(order, dealer, lambda q: True)
        bb = self._next_from(order, sb, lambda q: True)
        self._put(sb, sb_amt)
        self._put(bb, bb_amt)
        h["sb_player"], h["bb_player"] = sb, bb
        h["current_bet"] = max(h["bets"].values() or [0])
        h["min_raise"] = bb_amt
        self._log("hand", no=h["no"], dealer=dealer)
        h["to_act"] = self._next_actor(bb)
        h["deadline"] = self.now() + (self.r.get("turn_seconds") or 0) if self.r.get("turn_seconds") else None
        self.st["phase"] = "hand"
        self._settle_if_needed()

    def _can_act(self, pid: str) -> bool:
        h = self.hand
        return pid not in h["folded"] and pid not in h["allin"]

    def _next_actor(self, after: str) -> str | None:
        return self._next_from(self.hand["order"], after, self._can_act)

    def _active(self) -> list[str]:
        h = self.hand
        return [p for p in h["order"] if p not in h["folded"]]

    # ---------- actions
    def legal(self, pid: str) -> dict:
        h = self.hand
        if not h or h.get("result") or h.get("to_act") != pid:
            return {}
        p = self.seat(pid)
        owe = h["current_bet"] - h["bets"].get(pid, 0)
        out = {"fold": owe > 0, "check": owe <= 0, "call": min(owe, p["chips"]) if owe > 0 else 0}
        max_to = h["bets"].get(pid, 0) + p["chips"]
        min_to = h["current_bet"] + h["min_raise"] if h["current_bet"] else max(h["bb"], h["min_raise"])
        if max_to > h["current_bet"] and not h.get("no_reopen", {}).get(pid):
            out["raise"] = {"min": min(min_to, max_to), "max": max_to}
        return out

    def act(self, pid: str, kind: str, amount: int | None = None) -> None:
        h = self.hand
        if not h or h.get("result"):
            raise CommunityError("No hand is being played right now")
        if h.get("to_act") != pid:
            raise CommunityError("It is not your turn")
        legal = self.legal(pid)
        owe = h["current_bet"] - h["bets"].get(pid, 0)
        if kind == "fold":
            h["folded"].append(pid)
        elif kind == "check":
            if owe > 0:
                raise CommunityError("You cannot check – call or fold")
        elif kind == "call":
            if owe <= 0:
                raise CommunityError("There is nothing to call")
            self._put(pid, owe)
        elif kind in ("raise", "bet", "allin"):
            if "raise" not in legal:
                raise CommunityError("You cannot raise now")
            to = legal["raise"]["max"] if kind == "allin" else int(amount or 0)
            if to < legal["raise"]["min"] and to != legal["raise"]["max"]:
                raise CommunityError("The raise is too small")
            to = min(to, legal["raise"]["max"])
            raise_by = to - h["current_bet"]
            self._put(pid, to - h["bets"].get(pid, 0))
            if raise_by >= h["min_raise"]:                  # a full raise reopens the betting for everybody
                h["min_raise"] = raise_by
                h["acted"] = []
                h["no_reopen"] = {}
            else:                                           # a short all-in: those who acted already may only call
                h["no_reopen"] = {q: True for q in h["acted"]}
            h["current_bet"] = max(h["current_bet"], to)
        else:
            raise CommunityError("Unknown action")
        h["acted"].append(pid)
        h.setdefault("last_action", {})[pid] = kind
        self._log(kind, player=pid, amount=h["bets"].get(pid, 0))
        self._advance(pid)

    # ---------- bots
    def bot_act(self, pid: str) -> None:
        h, seat = self.hand, self.seat(pid)
        lv = BOT_LEVELS.get(seat.get("level"), BOT_LEVELS["normal"])
        legal = self.legal(pid)
        s = strength(h["hole"][pid], h["board"]) + self.rng.uniform(-lv["noise"], lv["noise"])
        owe = legal.get("call", 0)
        pot = sum(h["contrib"].values())
        rais = legal.get("raise")
        want_raise = rais and s > .7 and self.rng.random() < lv["aggr"] + (s - .7)
        if rais and (want_raise or (owe == 0 and s > .55 and self.rng.random() < lv["aggr"] / 2)):
            to = h["current_bet"] + max(h["min_raise"], int(pot * (.5 if s < .85 else 1)))
            to = max(rais["min"], min(rais["max"], to))
            self.act(pid, "allin" if to >= rais["max"] else "raise", to)
        elif owe == 0:
            self.act(pid, "check")
        elif s > owe / (pot + owe) + .12 or self.rng.random() < lv["bluff"] or owe <= h["bb"] // 2 and s > .25:
            self.act(pid, "call")
        else:
            self.act(pid, "fold")

    def _bots(self) -> None:
        """Let the bots whose turn it is move – one after the other, each after a short pause."""
        for _ in range(12):
            h = self.hand
            if self.st.get("phase") != "hand" or not h or not h.get("to_act"):
                return
            seat = self.seat(h["to_act"])
            if not seat or not seat.get("bot"):
                return
            key = f'{h["no"]}:{h["street"]}:{h["to_act"]}:{len(h["acted"])}:{h["current_bet"]}'
            if h.get("bot_key") != key:
                h["bot_key"], h["bot_at"] = key, self.now()
                return
            if self.now() - h["bot_at"] < BOT_DELAY:
                return
            self.bot_act(h["to_act"])
            h = self.hand
            if h:
                h["bot_key"], h["bot_at"] = None, self.now()

    def _round_done(self) -> bool:
        h = self.hand
        open_ = [p for p in self._active() if p not in h["allin"]]
        return all(p in h["acted"] and h["bets"].get(p, 0) == h["current_bet"] for p in open_)

    def _advance(self, last: str) -> None:
        h = self.hand
        if len(self._active()) == 1:
            self._showdown()
            return
        if not self._round_done():
            h["to_act"] = self._next_actor(last)
            h["deadline"] = self.now() + self.r["turn_seconds"] if self.r.get("turn_seconds") else None
            return
        self._next_street()

    def _next_street(self) -> None:
        h = self.hand
        while True:
            h["bets"], h["acted"], h["no_reopen"], h["last_action"] = {}, [], {}, {}
            h["current_bet"], h["min_raise"] = 0, h["bb"]
            if h["street"] == "river":
                self._showdown()
                return
            nxt = {"preflop": "flop", "flop": "turn", "turn": "river"}[h["street"]]
            h["deck"].pop()                                  # burn
            h["board"] += [h["deck"].pop() for _ in range(3 if nxt == "flop" else 1)]
            h["street"] = nxt
            # nobody (or only one) can bet any more → deal the rest without betting
            if len([p for p in self._active() if p not in h["allin"]]) >= 2:
                h["to_act"] = self._next_actor(self.st["dealer"])
                h["deadline"] = self.now() + self.r["turn_seconds"] if self.r.get("turn_seconds") else None
                return

    def _settle_if_needed(self) -> None:
        """After the blinds: if nobody can act any more (everybody all-in), run the board out."""
        h = self.hand
        if h["to_act"] is None or (len([p for p in self._active() if p not in h["allin"]]) < 2 and self._round_done()):
            self._next_street()

    def _showdown(self) -> None:
        h = self.hand
        active = self._active()
        folded = set(h["folded"])
        while len(h["board"]) < 5 and len(active) > 1:         # all-in before the river: deal the rest
            h["deck"].pop()
            h["board"] += [h["deck"].pop() for _ in range(3 if not h["board"] else 1)]
        ranks = {p: best_hand(h["hole"][p] + h["board"]) for p in active} if len(active) > 1 else {}
        wins: dict[str, int] = {}
        pots = side_pots(h["contrib"], folded)
        order = h["order"]
        left_of_dealer = order[(order.index(self.st["dealer"]) + 1) % len(order):] + order[:(order.index(self.st["dealer"]) + 1) % len(order)]
        for pot in pots:
            el = [p for p in pot["eligible"] if p in active] or active
            if len(el) == 1:
                win = el
            else:
                top = max(ranks[p][0] for p in el)
                win = [p for p in el if ranks[p][0] == top]
            share, odd = divmod(pot["amount"], len(win))
            for p in win:
                wins[p] = wins.get(p, 0) + share
            for p in left_of_dealer:
                if odd and p in win:
                    wins[p] += odd
                    odd = 0
        for p, amount in wins.items():
            self.seat(p)["chips"] += amount
        h["result"] = {"winners": wins, "pots": pots, "shown": {p: h["hole"][p] for p in ranks},
                       "hands": {p: {"category": CATEGORIES[ranks[p][0][0]], "cards": ranks[p][1]} for p in ranks}}
        h["to_act"] = None
        h["deadline"] = None
        h["street"] = "showdown"
        self.st["phase"] = "between"
        self.st["next_at"] = self.now() + (self.r.get("pause_seconds") or 6)
        self._log("won", winners=wins)
        for p in self.st["players"]:
            if p["chips"] == 0 and not p.get("out") and p["id"] in order:
                if self.r["mode"] == "equal":
                    p["out"] = True
                    p["place"] = len([q for q in self.st["players"] if not q.get("out")]) + 1
        if self.r["mode"] == "equal" and len(self.in_game()) < 2:
            self.finish()

    def finish(self) -> None:
        self.st["phase"] = "done"
        alive = sorted(self.st["players"], key=lambda p: (-p["chips"], p.get("place") or 0))
        for i, p in enumerate(alive):
            if not p.get("place") or p["chips"] > 0:
                p["place"] = i + 1
        self.st["finished"] = self.now()

    # ---------- time moves the game on
    def tick(self) -> None:
        if self.st.get("paused"):
            return
        h = self.hand
        if self.st.get("phase") == "hand" and h and h.get("deadline") and self.now() > h["deadline"] and h.get("to_act"):
            pid = h["to_act"]
            self.act(pid, "check" if self.legal(pid).get("check") else "fold")
            self._log("timeout", player=pid)
        if self.st.get("phase") == "between" and self.now() >= self.st.get("next_at", 0):
            self.deal()
        elif self.st.get("phase") == "waiting" and len(self.in_game()) >= 2:
            self.deal()
        # alone against bots: out of chips after a hand is settled (not while all-in – the hand still runs) → over
        if self.st.get("solo") and self.st.get("phase") == "between" and not any(
                not p.get("bot") and p["chips"] > 0 for p in self.st["players"]):
            self.finish()                                  # alone against bots: out of chips – the game is over
            return
        self._bots()


# ================================================================ the family game (stored in the database)
class Poker:
    def __init__(self, db, add_history=None):
        self.db = db
        self.add_history = add_history
        self.lock = threading.Lock()

    def default_rules(self) -> dict:
        return {**DEFAULT_RULES, **(self.db.get_setting(RULES_KEY) or {})}

    @staticmethod
    def clean_rules(r: dict) -> dict:
        def num(k, lo, hi):
            try:
                return max(lo, min(hi, int(r.get(k, DEFAULT_RULES[k]))))
            except (TypeError, ValueError):
                return DEFAULT_RULES[k]
        out = {"start_chips": num("start_chips", 100, 1_000_000), "small_blind": num("small_blind", 1, 100_000),
               "ante": num("ante", 0, 100_000), "blind_minutes": num("blind_minutes", 0, 120),
               "turn_seconds": num("turn_seconds", 0, 300), "pause_seconds": num("pause_seconds", 2, 30),
               "rebuys": num("rebuys", 0, 99), "max_players": num("max_players", 2, 10),
               "mode": r.get("mode") if r.get("mode") in ("equal", "bank") else "equal"}
        out["big_blind"] = max(out["small_blind"] * 2, num("big_blind", 2, 200_000))
        if out["big_blind"] * 5 > out["start_chips"]:
            raise CommunityError("The start chips must be at least five big blinds")
        return out

    def _row(self, pid: int | None = None):
        """The family table – or, for `pid`, the own table against bots when one is running."""
        if pid is not None:
            row = self.db.q1("""SELECT * FROM poker_game WHERE status!='done' AND host_id=? AND json_extract(state,'$.solo')=1
                                ORDER BY id DESC LIMIT 1""", pid)
            if row:
                return row
        return self.db.q1("SELECT * FROM poker_game WHERE status!='done' AND IFNULL(json_extract(state,'$.solo'),0)=0 ORDER BY id DESC LIMIT 1")

    def _load(self, row) -> tuple[dict, Table]:
        st = json.loads(row["state"])
        return st, Table(st)

    def _save(self, row, st: dict) -> None:
        status = "done" if st.get("phase") == "done" else ("running" if st.get("phase") in ("hand", "between", "waiting") else "lobby")
        self.db.x("UPDATE poker_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status == "done" and self.add_history and not st.get("history_written"):
            st["history_written"] = True
            self.db.x("UPDATE poker_game SET state=? WHERE id=?", json.dumps(st), row["id"])
            for p in st["players"]:
                try:
                    self.add_history(int(p["id"]), "poker", {"place": p.get("place"), "players": len(st["players"]),
                                                             "chips": p["chips"]})
                except Exception:  # noqa: BLE001
                    pass

    def _game(self) -> dict | None:            # the shape the guests module expects
        row = self._row()
        return {"id": row["id"], "status": row["status"]} if row else None

    def may_lead(self, prof: dict, family: bool = False) -> bool:
        """Lead the own table (solo first) – or, with `family`, the family table (the bank: giving chips)."""
        row = self._row() if family else self._row(prof["id"])
        return bool(row) and (prof["role"] == "parent" or row["host_id"] == prof["id"])

    def start(self, host: int, rules: dict | None = None, solo: bool = False, bots: list[dict] | None = None) -> int:
        """Open the family table – or, with `solo`, a table of your own against bots (dealt right away)."""
        if solo:
            return self._start_solo(host, rules, bots or [])
        with self.lock:
            if self._row():
                raise CommunityError("A poker game is already running")
            r = self.clean_rules({**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
            self.db.set_setting(RULES_KEY, r)
            st = {"rules": r, "players": [], "phase": "lobby", "requests": {}}
            gid = self.db.x("INSERT INTO poker_game(host_id, state) VALUES(?,?)", host, json.dumps(st))
        self.join(host)
        return gid

    def _start_solo(self, host: int, rules: dict | None, bots: list[dict]) -> int:
        with self.lock:
            r = self.clean_rules({**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None},
                                  "mode": "equal", "turn_seconds": 0})
            if not 1 <= len(bots) <= 8:
                raise CommunityError("Choose one to eight bots")
            self.db.x("""UPDATE poker_game SET status='done', finished_at=datetime('now','localtime')
                         WHERE status!='done' AND host_id=? AND json_extract(state,'$.solo')=1""", host)
            p = self.db.q1("SELECT name, avatar FROM profile WHERE id=?", host)
            players = [{"id": str(host), "name": p["name"] if p else "?", "avatar": json.loads(p["avatar"] or "{}") if p else {},
                        "chips": r["start_chips"], "buyins": 1}]
            for i, b in enumerate(bots):
                players.append({"id": f"bot{i + 1}", "name": str(b.get("name") or "Bot")[:30], "emoji": b.get("emoji") or "🤖", "color": b.get("color"),
                                "avatar": b.get("avatar") or None, "bot": True,
                                "level": b.get("level") if b.get("level") in BOT_LEVELS else "normal",
                                "chips": r["start_chips"], "buyins": 1})
            st = {"rules": r, "players": players, "phase": "lobby", "requests": {}, "solo": True, "started": time.time()}
            Table(st).deal()
            return self.db.x("INSERT INTO poker_game(host_id, state, status) VALUES(?,?,'running')", host, json.dumps(st))

    def join(self, pid: int) -> None:
        with self.lock:
            row = self._row()
            if not row:
                raise CommunityError("No poker game is running")
            st, t = self._load(row)
            if t.seat(str(pid)):
                return
            if len(st["players"]) >= st["rules"]["max_players"]:
                raise CommunityError("The table is full")
            p = self.db.q1("SELECT name, avatar FROM profile WHERE id=?", pid)
            # who comes later during a running game sits down with the start chips and plays from the next hand
            st["players"].append({"id": str(pid), "name": p["name"] if p else "?", "avatar": json.loads(p["avatar"] or "{}") if p else {},
                                  "chips": st["rules"]["start_chips"], "buyins": 1})
            self._save(row, st)

    def begin(self, pid: int | None = None) -> None:
        with self.lock:
            row = self._row(pid)
            if not row:
                raise CommunityError("No poker game is running")
            st, t = self._load(row)
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) < 2:
                raise CommunityError("Poker needs at least two players")
            st["started"] = time.time()
            t.deal()
            self._save(row, st)

    def act(self, pid: int, kind: str, amount: int | None = None) -> None:
        with self.lock:
            row = self._row(pid)
            if not row:
                raise CommunityError("No poker game is running")
            st, t = self._load(row)
            t.tick()
            t.act(str(pid), kind, amount)
            self._save(row, st)

    def pause(self, on: bool, pid: int | None = None) -> None:
        with self.lock:
            row = self._row(pid)
            if not row:
                raise CommunityError("No poker game is running")
            st, t = self._load(row)
            h = st.get("hand")
            if on and not st.get("paused"):
                st["paused"] = time.time()
            elif not on and st.get("paused"):
                gap = time.time() - st.pop("paused")
                st["started"] = (st.get("started") or time.time()) + gap      # the blinds do not rise while paused
                if h and h.get("deadline"):
                    h["deadline"] += gap
                if st.get("next_at"):
                    st["next_at"] += gap
            self._save(row, st)

    def end(self, pid: int | None = None) -> None:
        with self.lock:
            row = self._row(pid)
            if not row:
                return
            st, t = self._load(row)
            if st["phase"] == "lobby":
                self.db.x("UPDATE poker_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])
                return
            t.finish()
            self._save(row, st)

    # ---------- the bank: buy-ins managed by the game leader
    def ask_chips(self, pid: int) -> None:
        with self.lock:
            row = self._row()
            if not row:
                raise CommunityError("No poker game is running")
            st, t = self._load(row)
            p = t.seat(str(pid))
            if st["rules"]["mode"] != "bank" or not p:
                raise CommunityError("Chips are not given out in this game")
            if p["buyins"] > st["rules"]["rebuys"]:
                raise CommunityError("No more buy-ins in this game")
            st["requests"][str(pid)] = time.time()
            self._save(row, st)

    def give_chips(self, pid: int, ok: bool = True, amount: int | None = None) -> None:
        with self.lock:
            row = self._row()
            if not row:
                raise CommunityError("No poker game is running")
            st, t = self._load(row)
            st["requests"].pop(str(pid), None)
            p = t.seat(str(pid))
            if ok and p:
                in_hand = st.get("hand") and st["phase"] == "hand" and str(pid) in st["hand"]["order"]
                if in_hand and str(pid) not in st["hand"]["folded"]:
                    raise CommunityError("Chips only between hands")
                p["chips"] += int(amount or st["rules"]["start_chips"])
                p["buyins"] = p.get("buyins", 1) + 1
                p.pop("out", None)
            self._save(row, st)

    # ---------- what a device sees
    def state(self, viewer: int) -> dict | None:
        with self.lock:
            row = self._row(viewer)
            if row:
                st, t = self._load(row)
                before = json.dumps(st)
                t.tick()
                if json.dumps(st) != before:
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM poker_game WHERE id=?", row["id"])
            else:
                row = self.db.q1("""SELECT * FROM poker_game WHERE status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                    ORDER BY id DESC LIMIT 1""")
                if not row:
                    return None
                st, t = self._load(row)
            if not t.seat(str(viewer)) and row["status"] == "done":
                return None
        return self._view(row, st, t, str(viewer))

    def _view(self, row, st: dict, t: Table, me: str) -> dict:
        h = st.get("hand") or {}
        res = h.get("result") or {}
        sb, bb = t.blinds()
        players = []
        for p in st["players"]:
            pid = p["id"]
            players.append({"id": int(pid) if pid.isdigit() else pid, "name": p["name"], "avatar": p.get("avatar"), "chips": p["chips"],
                            "bot": bool(p.get("bot")), "emoji": p.get("emoji"), "color": p.get("color"),
                            "bet": (h.get("bets") or {}).get(pid, 0), "in_hand": pid in (h.get("order") or []),
                            "folded": pid in (h.get("folded") or []), "allin": pid in (h.get("allin") or []),
                            "dealer": st.get("dealer") == pid, "sb": h.get("sb_player") == pid, "bb": h.get("bb_player") == pid,
                            "out": bool(p.get("out")), "place": p.get("place"), "buyins": p.get("buyins", 1),
                            "asks": pid in st.get("requests", {}), "last": (h.get("last_action") or {}).get(pid),
                            "cards": res.get("shown", {}).get(pid), "hand": (res.get("hands") or {}).get(pid, {}).get("category"),
                            "won": (res.get("winners") or {}).get(pid, 0)})
        pot = sum((h.get("contrib") or {}).values())
        return {"game": row["id"], "status": row["status"], "phase": st["phase"], "host": row["host_id"], "rules": st["rules"],
                "paused": bool(st.get("paused")), "hand_no": h.get("no", 0), "street": h.get("street"),
                "board": h.get("board", []), "pot": pot, "current_bet": h.get("current_bet", 0),
                "to_act": (int(h["to_act"]) if h["to_act"].isdigit() else h["to_act"]) if h.get("to_act") else None, "solo": bool(st.get("solo")),
                "turn_ms": max(0, int((h["deadline"] - time.time()) * 1000)) if h.get("deadline") and not st.get("paused") else None,
                "next_ms": max(0, int((st.get("next_at", 0) - time.time()) * 1000)) if st["phase"] == "between" else None,
                "blinds": [sb, bb], "players": players, "joined": bool(t.seat(me)),
                "my_cards": (h.get("hole") or {}).get(me), "legal": t.legal(me) if st["phase"] == "hand" else {},
                "best": CATEGORIES[best_hand((h.get("hole") or {}).get(me, []) + h.get("board", []))[0][0]]
                if (h.get("hole") or {}).get(me) and len(h.get("board", [])) >= 3 else None,
                "requests": list(st.get("requests", {}).keys())}

    def summary(self, pid: int) -> dict | None:
        row = self._row(pid)
        if not row:
            return None
        st = json.loads(row["state"])
        return {"status": row["status"], "joined": any(p["id"] == str(pid) for p in st["players"])}
