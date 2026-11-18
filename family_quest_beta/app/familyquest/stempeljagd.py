"""«Beat the Bureaucracy» (internal key "stempeljagd") – a light-hearted family party game about a wonderfully
complicated town hall in the invented town of «Little Red-Tapington» (every language has its own funny name).
No real country, authority, law, person or brand – an own parody with own texts.

Everybody plays on their own device (family, guests via QR code) or a child plays alone against bots. A seat is a
team (one device – one or more people). The tables live in the `card_game` table with kind "stempeljagd" (lobby,
join, summary, may_lead from cardgames.CardGames, like «Dorfmarkt»); the whole game is in the state of the row, so it
survives a restart and reconnects.

Goal: every team wants its building project approved (tree house, garage with a water slide, pizza oven …): the permit
needs `target` stamps (rule `length`: short 5 / normal 7 / long 9). The first team with all stamps wins, the others
are ranked by their stamps.

The town hall: Counter 1 «General information» (knows nothing, kindly refers on), 2 «Office for Building Matters»
(open only on Tuesdays and at new moon – one round is one day of a Monday–Friday week, the moon goes round in 8
rounds), 3 «Office for Green Spaces» (asks whether the tree agrees), 4 «Commission for Slowness» (meets every 3
rounds; between the meetings an application goes on the pile and is decided at the next meeting), the archive in
the basement (the document you are missing – sometimes first the form you need for the form) and the coffee kitchen
(a trick card, a rumour and better relations).

A turn: optionally play a trick card (💌 small gift, 📣 the mayor, ⚖️ an objection), then go to a counter. At the
counters 1–4 the entry scene comes first (decided per counter and round – the same for everybody):
  appointment  «Do you have an appointment?» – Yes (with a 📅 appointment card) or No: «fully booked for the next 9
               months» (in an empty waiting room). Then one argument (polite insisting, «it's urgent», «only a tiny
               question», 🥐 croissants, 🤝 connections) – the chance depends on the clerk's mood. It works: the clerk
               phones a colleague with a sigh and you get an audience. It does not: come back another day.
  queue        a huge queue (the display does not move while the clerks chat). Wait (50 %: the chat ends and it is
               your turn – else your place is kept for your next turn) or try a trick to jump the queue, each with a
               chance and its own funny consequence when caught (back to the end, the queue complains: −1 relation,
               the clerk closes the counter for the day).
  free         nobody there – the clerk looks up with a sigh.
The first contact of a team with a counter is always the appointment question. The audience: a ticket number (the
display goes «ding-dong»), then an authority card of that counter: a stamp, two stamps, a referral to another counter
(the next turn must go there – ping-pong between counters is counted), a document is needed (with it in the folder:
a stamp; without: it is missing until fetched from the archive – handing it in at any counter 1–4 is a stamp), lunch
break (miss the next turn), holiday, a grumpy clerk, a trick card, the tree, or a mini-game: an absurd form (tick the
boxes before they slide away), stamping yourself at the right moment, bureaucratic speak («article 7, paragraph 3,
item pancake» – which item was it?). Mini-games are server-authoritative (rule `minigames`; bots and the rule off:
a chance by the bot level).
Trick cards (at most 4 in the hand, two at the start; the mayor once per game for everybody): 📅 appointment,
🥐 croissants (the entry works almost always, the clerk's good mood draws two cards – the better one counts),
🤝 connections (a sure entry, or cancel a referral), 💌 small gift (+2 stamps – but the 🕵️ order inspector catches
it with 35 %: a fine stamp −1 and back to counter 1 – a wink, not life advice), 📎 complete folder (protects once
against «something is missing»), 🗣️ stay friendly (the next grumpy clerk melts: a stamp), 📣 talk to the mayor
(+1 stamp, all referrals and waiting cleared – once per game), ⚖️ objection (another team defends: 📋 expert report with a
document from the folder – sure; ✍️ neighbours' signatures – 45 % + 15 % per relation; 🤝 compromise – 75 %, the
project gets a funny change. A successful objection costs a stamp).
Events at the start of a round (from round 2, 30 %): 📜 new regulation (all documents in the folders are invalid),
💻 system migration (this round the counters give no stamps: «computer says no»), 🎉 open day (all counters open,
no queues, no appointments).
Mode `admin`: one seat plays «the Administration» (a person or a bot) against the builder teams: on its turn (once
per round, last in the order) it plays an authority card on a builder team (referral, lunch break, new regulation,
an absurd form to fill first, a stamp revoked) or opens / closes a counter (at most 2 closed). The builders defend
automatically with 🤝 / 🗣️ / 📎. The administration wins if nobody has the permit after `admin_rounds` rounds.
End: the permit certificate with all stamps and the funniest moments («Leo was sent to counter 4 six times»).
Coins (setting `game_rewards["stempeljagd"]`): places 1–3, only people of the family at a family table with at
least two of them, never alone against bots; paid once (flag `paid`, ledger ref per player), only for a game played
to the end. History for everybody of the family (referrals, time to the permit: records for the facts quiz).
"""
from __future__ import annotations

import json
import random
import secrets
import time

from .cardgames import BOTS, BOT_DELAY, CardGames, bot_delay, apply_starter, starter_mode
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of

KIND = "stempeljagd"
TITLE = "Beat the Bureaucracy"
EMOJI = "🏛️"
MAX_PLAYERS = 4
LEVELS = ("easy", "normal", "hard")
LENGTHS = {"short": 5, "normal": 7, "long": 9}
ADMIN_ROUNDS = {"short": 10, "normal": 15, "long": 22}
MODES = ("teams", "admin")
DEFAULTS = {"bots": 2, "level": "normal", "bot_ms": 1400, "length": "normal", "mode": "teams", "admin": "bot",
            "minigames": True, "projects": "pick"}
MAX_ROUNDS = 40                       # safety: a game without a permit ends by the stamps
HAND = 4
COUNTERS = ("info", "building", "green", "slow", "archive", "coffee")
DESKS = ("info", "building", "green", "slow")          # counters with clerks, scenes and authority cards
NUMBER = {"info": 1, "building": 2, "green": 3, "slow": 4}
PROJECTS = ("treehouse", "slide", "pizza", "hamster", "duck", "lemonade", "igloo", "rocket")
DOCS = ("b12", "copy", "original", "goldfish", "map", "sleep", "confirm", "greeting")
TRICKS = ("appointment", "croissant", "connections", "gift", "folder", "friendly", "objection")
TRICK_WEIGHTS = {"appointment": 3, "croissant": 3, "connections": 2, "gift": 2, "folder": 2, "friendly": 2, "objection": 2}
ACTIVE = ("gift", "mayor", "objection")                 # played before going to a counter
MOODS = ("grumpy", "sleepy", "chatty", "cheerful")
ARGS = {  # argument: (base chance, {mood: bonus}, trick card it needs)
    "polite": (0.55, {"cheerful": 0.25, "grumpy": -0.15, "chatty": 0.1}, None),
    "urgent": (0.45, {"sleepy": 0.3, "grumpy": -0.25, "chatty": -0.1}, None),
    "tiny": (0.5, {"cheerful": 0.2, "chatty": -0.25, "grumpy": 0.1}, None),
    "croissant": (0.95, {"grumpy": -0.05}, "croissant"),
    "connections": (0.9, {}, "connections"),
}
CHEATS = {  # queue trick: (chance, consequence when caught)
    "toilet": (0.5, "end"), "signature": (0.45, "complain"), "delivery": (0.4, "close"),
    "folder": (0.7, "end"), "stroller": (0.5, "complain"), "croissant": (0.9, "end"),
}
EVENTS = ("regulation", "migration", "openday")
EVENT_CHANCE = 0.3
GIFT_CAUGHT = 0.35
WAIT_SERVED = 0.5
COMMISSION_YES = 0.7
TREE_YES, TREE_FRIDAY = 0.6, 0.8
SIG_BASE, SIG_REL, COMPROMISE = 0.45, 0.15, 0.75
BOT_SKILL = {"easy": 0.5, "normal": 0.65, "hard": 0.8}
MINI_SECONDS = {"form": 12, "stamp": 10, "speak": 20}
MINI_GRACE = 2.0
LATENCY = 0.12                        # stamp timing: the tap left the phone about this much earlier
STAMP_PERIOD = 1.6                    # the marker runs 0 → 1 → 0 in this time
STAMP_WINDOW = 0.13
SPEAK_ITEMS = ("pancake", "waffle", "pretzel", "muffin", "noodle", "jellyfish", "bagel", "dumpling")
FORM_BOXES = ("confirmed", "read", "robot", "agree", "hamster", "pen", "today", "copies")

# authority cards per counter: (key, effect, extra) – effects: stamp, stamp2, refer:<counter>, need:<doc>, lunch,
# grumpy, holiday, nothing, trick, tree, mini:<form|stamp|speak>
CARDS = {
    "info": [("i_refer4", "refer:slow", 2), ("i_refer3", "refer:green", 2), ("i_refer2", "refer:building", 2),
             ("i_know", "refer:green", 1), ("i_self", "refer:info", 1), ("i_map", "trick", 2), ("i_yes", "stamp", 2),
             ("i_brochure", "nothing", 1), ("i_expired", "grumpy", 1), ("i_speak", "mini:speak", 1)],
    "building": [("b_received", "stamp", 3), ("b_double", "stamp2", 2), ("b_b12", "need:b12", 2), ("b_copy", "need:copy", 1),
                 ("b_original", "need:original", 1), ("b_holiday", "holiday", 1), ("b_lunch", "lunch", 1),
                 ("b_selfstamp", "mini:stamp", 2), ("b_article", "mini:speak", 1), ("b_refer1", "refer:info", 1), ("b_ink", "grumpy", 1)],
    "green": [("g_tree", "tree", 3), ("g_birds", "stamp", 2), ("g_leaves", "mini:form", 1), ("g_refer2", "refer:building", 1),
              ("g_refer4", "refer:slow", 1), ("g_shadow", "nothing", 1), ("g_map", "need:map", 2), ("g_worm", "stamp", 1),
              ("g_grumpy", "grumpy", 1), ("g_lunch", "lunch", 1), ("g_goldfish", "need:goldfish", 1)],
    "slow": [("s_approved", "stamp", 3), ("s_postponed", "pile", 2), ("s_vote", "stamp", 2), ("s_refer1", "refer:info", 1),
             ("s_confirm", "mini:form", 2), ("s_break", "lunch", 1), ("s_slowstamp", "stamp", 1), ("s_sleep", "need:sleep", 1)],
}
CARD_EFFECT = {k: (eff, c) for c, lst in CARDS.items() for k, eff, _ in lst}
GRUMPY = ("lunch", "grumpy")
ADMIN_CARDS = {"a_refer": 3, "a_lunch": 2, "a_regulation": 2, "a_form": 3, "a_revoke": 1}
RUMOURS = ("r_building", "r_commission", "r_cat", "r_croissant", "r_tree", "r_stamp", "r_plant", "r_counter4")
# how good a card is for the drawing team (croissants: the better of two)
CARD_RANK = {"stamp2": 9, "stamp": 8, "tree": 6, "mini": 6, "need": 4, "trick": 4, "pile": 3, "holiday": 2,
             "nothing": 2, "grumpy": 1, "refer": 1, "lunch": 0}


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def _weighted(rng, items: dict):
    total = sum(items.values())
    x = rng.random() * total
    for k, w in items.items():
        x -= w
        if x < 0:
            return k
    return list(items)[-1]


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

    def seat_of(self, pid: str | None) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def is_bot(self, pid: str | None) -> bool:
        return bool((self.seat_of(pid) or {}).get("bot"))

    def admin(self) -> str | None:
        return self.st.get("admin_id")

    def builders(self) -> list[str]:
        return [p for p in self.order() if p != self.admin()]

    def team(self, pid: str) -> dict:
        return self.st["teams"][pid]

    def stamps(self, pid: str) -> int:
        return len(self.team(pid)["stamps"])

    @property
    def target(self) -> int:
        return LENGTHS.get(self.r.get("length"), 7)

    def level(self, pid: str) -> str:
        return (self.seat_of(pid) or {}).get("level") or self.r.get("level") or "normal"

    # ---------- the calendar
    def weekday(self, rnd: int | None = None) -> int:
        return ((rnd or self.st.get("round", 1)) - 1) % 5               # 0 Monday … 4 Friday

    def moon(self, rnd: int | None = None) -> int:
        return ((rnd or self.st.get("round", 1)) - 1 + self.st.get("moon0", 0)) % 8   # 0 = new moon

    def event(self) -> str | None:
        e = self.st.get("event")
        return e["key"] if e and e.get("round") == self.st.get("round") else None

    def building_open(self, rnd: int | None = None) -> bool:
        return self.weekday(rnd) == 1 or self.moon(rnd) == 0

    def meets(self, rnd: int | None = None) -> bool:
        return (rnd or self.st.get("round", 1)) % 3 == 0

    def closed(self, c: str) -> str | None:
        """Why a counter is closed now (None: open)."""
        if self.event() == "openday":
            return None
        if c in (self.st.get("closed") or []):
            return "admin"
        if (self.st.get("shut") or {}).get(c) == self.st.get("round"):
            return "lunch"
        if c == "building" and not self.building_open():
            return "hours"
        return None

    # ---------- the game
    def setup(self) -> None:
        ids = self.order()
        if not 2 <= len(ids) <= MAX_PLAYERS + 1:
            raise CommunityError("Add a bot or wait for a second player")
        if self.r.get("mode") == "admin" and len(ids) < 2:
            raise CommunityError("Add a bot or wait for a second player")
        teams = {}
        for p in ids:
            teams[p] = {"stamps": [], "fines": 0, "folder": [], "todo": None, "tricks": [self._trick(), self._trick()],
                        "mayor": True, "relations": 0, "skip": 0, "sent_to": None, "sent_from": None, "held": None,
                        "pending": 0, "form_due": False, "visited": [], "project": None, "compromise": None,
                        "turns": 0, "stats": {}}
        self.st.update(phase="projects" if self.r.get("projects") == "pick" else "play", teams=teams, round=1, turns=0,
                       turn=None, stage=None, ticket=self.rng.randint(40, 90), display=None, moon0=self.rng.randint(0, 7),
                       event=None, last_event=None, closed=[], shut={}, scenes={}, cur=None, obj=None, log=[], last=None,
                       seq=0, ranking=None, places=None, complete=False, winner=None, started=self.now(), turn_at=self.now(),
                       admin_hand=[], admin_won=False)
        adm = self.admin()
        if adm:
            teams.pop(adm)
            self.st["admin_hand"] = [self._admin_card() for _ in range(3)]
        if self.st["phase"] == "projects":
            for p in self.builders():
                if self.is_bot(p):
                    self._bot_project(p)
            if all(self.team(p)["project"] for p in self.builders()):
                self._start_play()
            else:
                self.st["stage"] = "project"
        else:
            free = list(PROJECTS)
            self.rng.shuffle(free)
            for p in self.builders():
                self.team(p)["project"] = free.pop()
            self._start_play()

    def _bot_project(self, p: str) -> None:
        free = [k for k in PROJECTS if k not in {self.team(q)["project"] for q in self.builders()}]
        self.team(p)["project"] = self.rng.choice(free)

    def _start_play(self) -> None:
        self.st.update(phase="play", started=self.now())
        self._new_round(first=True)
        self._begin_turn(self.order()[0])

    def pick_project(self, pid: str, key: str) -> None:
        if pid not in self.order() or pid == self.admin():
            raise CommunityError("You are not at this table")
        if self.st.get("phase") != "projects":
            raise CommunityError("Not now")
        if key not in PROJECTS:
            raise CommunityError("Unknown project")
        if any(self.team(q)["project"] == key for q in self.builders() if q != pid):
            raise CommunityError("Another team already builds this project")
        self.team(pid)["project"] = key
        if all(self.team(p)["project"] for p in self.builders()):
            self._start_play()

    def projects_done(self) -> None:
        """Who leads goes on: the teams without a project get one at random."""
        if self.st.get("phase") != "projects":
            return
        for p in self.builders():
            if not self.team(p)["project"]:
                self._bot_project(p)
        self._start_play()

    def _trick(self) -> str:
        return _weighted(self.rng, TRICK_WEIGHTS)

    def _admin_card(self) -> str:
        return _weighted(self.rng, ADMIN_CARDS)

    def _log(self, ev: dict) -> None:
        self.st["seq"] = self.st.get("seq", 0) + 1
        ev.update(t=self.now(), seq=self.st["seq"], round=self.st.get("round"))
        self.st["last"] = ev
        log = self.st.setdefault("log", [])
        log.append(ev)
        del log[:-40]

    def _stat(self, pid: str, key: str, n: int = 1) -> None:
        if pid in self.st["teams"]:
            s = self.team(pid)["stats"]
            s[key] = s.get(key, 0) + n

    def _new_round(self, first: bool = False) -> None:
        rnd = self.st["round"]
        self.st["shut"] = {}
        ev = None
        if not first and self.rng.random() < EVENT_CHANCE:
            ev = self.rng.choice([e for e in EVENTS if e != self.st.get("last_event")])
        self.st["event"] = {"key": ev, "round": rnd} if ev else None
        if ev:
            self.st["last_event"] = ev
            self._log({"kind": "event", "event": ev})
            if ev == "regulation":
                for p in self.builders():
                    self.team(p)["folder"] = []
        scenes = {}
        for c in DESKS:
            kind = "free" if ev == "openday" else _weighted(self.rng, {"queue": 45, "appt": 35, "free": 20})
            scenes[c] = {"kind": kind, "mood": self.rng.choice(MOODS), "queue": self.rng.randint(6, 24), "shown": self.rng.randint(1, 30)}
        self.st["scenes"] = scenes
        if self.meets(rnd) and not first:
            res = {}
            for p in self.builders():
                t = self.team(p)
                yes = 0
                for _ in range(t["pending"]):
                    if self.rng.random() < COMMISSION_YES:
                        yes += 1
                if t["pending"]:
                    no = t["pending"] - yes
                    t["pending"] = no
                    if no:
                        self._stat(p, "postponed", no)
                    res[p] = [yes, no]
                    for _ in range(yes):
                        if self._gain(p, 1, "slow", source="meeting"):
                            break
                if self.st.get("phase") == "done":
                    break
            self._log({"kind": "meeting", "res": res})

    # ---------- turns
    def _begin_turn(self, pid: str) -> None:
        """Start the turn of pid; lunch breaks are skipped here (a loop guard keeps it finite)."""
        order = self.order()
        for _ in range(len(order) * 3 + 2):
            if self.st.get("phase") != "play":
                return
            self.st.update(turn=pid, cur=None, obj=None, turn_at=self.now())
            if pid == self.admin():
                self.st["stage"] = "admin"
                return
            t = self.team(pid)
            if t["skip"] > 0:
                t["skip"] -= 1
                self._log({"kind": "skipped", "player": pid})
                pid = self._advance(pid)
                if pid is None:
                    return
                continue
            t["turns"] += 1
            if t["form_due"]:
                t["form_due"] = False
                self._mini(pid, "form", why="admin")
                return
            self.st["stage"] = "go"
            return

    def _advance(self, cur: str) -> str | None:
        """The next seat (a new round when the order wraps). None: the game ended."""
        order = self.order()
        i = order.index(cur)
        nxt = order[(i + 1) % len(order)]
        self.st["turns"] = self.st.get("turns", 0) + 1
        if order.index(nxt) <= i:
            self.st["round"] += 1
            if self.admin() and self.st["round"] > ADMIN_ROUNDS.get(self.r.get("length"), 16):
                self.st.update(admin_won=True, complete=True)
                self._finish()
                return None
            if self.st["round"] > MAX_ROUNDS:
                self.st["complete"] = True
                self._finish()
                return None
            self._new_round()
            if self.st.get("phase") != "play":
                return None
        return nxt

    def _next_turn(self) -> None:
        nxt = self._advance(self.st["turn"])
        if nxt is not None:
            self._begin_turn(nxt)

    def actor(self) -> str | None:
        if self.st.get("phase") == "projects":
            return None
        if self.st.get("stage") == "objection":
            return (self.st.get("obj") or {}).get("to")
        return self.st.get("turn")

    def _check(self, pid: str, stages: tuple) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        if self.actor() != pid:
            raise CommunityError("It is not your turn")
        if self.st.get("stage") not in stages:
            raise CommunityError("Not now")

    # ---------- stamps
    def _gain(self, pid: str, n: int, office: str, source: str = "counter") -> bool:
        """+n stamps; True when the permit is complete (the game ends)."""
        if source == "counter" and self.event() == "migration":
            self._stat(pid, "computer_no")
            self._log({"kind": "computer_no", "player": pid})
            return False
        t = self.team(pid)
        for _ in range(n):
            if len(t["stamps"]) < self.target:
                t["stamps"].append({"o": office, "r": self.st["round"]})
        if len(t["stamps"]) >= self.target and self.st.get("phase") == "play":
            self.st["winner"] = pid
            self.st["complete"] = True
            t["seconds"] = int(self.now() - self.st.get("started", self.now()))
            self._finish()
            return True
        return False

    def _lose(self, pid: str) -> bool:
        t = self.team(pid)
        if t["stamps"]:
            t["stamps"].pop()
            return True
        return False

    def _consume(self, pid: str, trick: str) -> bool:
        tr = self.team(pid)["tricks"]
        if trick in tr:
            tr.remove(trick)
            return True
        return False

    def _draw_trick(self, pid: str) -> str | None:
        tr = self.team(pid)["tricks"]
        if len(tr) >= HAND:
            return None
        k = self._trick()
        tr.append(k)
        return k

    # ---------- a turn: tricks
    def play(self, pid: str, trick: str, target: str | None = None) -> None:
        self._check(pid, ("go",))
        t = self.team(pid)
        if trick == "mayor":
            if not t["mayor"]:
                raise CommunityError("The mayor helps only once per game")
            t["mayor"] = False
            t.update(sent_to=None, held=None, todo=None, skip=0)
            self._stat(pid, "mayor")
            self._log({"kind": "mayor", "player": pid})
            self._gain(pid, 1, "mayor", source="mayor")
            return
        if trick not in ("gift", "objection"):
            raise CommunityError("This trick card is played elsewhere")
        if trick not in t["tricks"]:
            raise CommunityError("You do not have this trick card")
        if trick == "objection":
            target = str(target or "")
            if target not in self.builders() or target == pid:
                raise CommunityError("Choose a team to object to")
            if not self.stamps(target):
                raise CommunityError("This team has no stamp yet")
            self._consume(pid, "objection")
            self._stat(pid, "objections")
            self.st["obj"] = {"from": pid, "to": target, "at": self.now()}
            self.st.update(stage="objection", turn_at=self.now())
            self._log({"kind": "objection", "player": pid, "to": target})
            return
        self._consume(pid, "gift")
        self._stat(pid, "gifts")
        if self.rng.random() < GIFT_CAUGHT:
            self._stat(pid, "caught")
            lost = self._lose(pid)
            t["fines"] += 1
            t.update(sent_to="info", sent_from=None, held=None)
            self._log({"kind": "inspector", "player": pid, "lost": lost})
            self.st.update(stage="done", cur={"result": "inspector"})
            return
        self._log({"kind": "gift", "player": pid})
        self.st.update(stage="done", cur={"result": "gift"})
        self._gain(pid, 2, "gift", source="gift")

    def defend(self, pid: str, how: str) -> None:
        self._check(pid, ("objection",))
        o = self.st["obj"]
        t = self.team(pid)
        if how == "report":
            if not t["folder"]:
                raise CommunityError("An expert report needs a document from your folder")
            t["folder"].pop(0)
            ok = True
        elif how == "signatures":
            ok = self.rng.random() < SIG_BASE + SIG_REL * t["relations"]
        elif how == "compromise":
            ok = self.rng.random() < COMPROMISE
            if ok:
                t["compromise"] = t["project"]
        else:
            raise CommunityError("Unknown action")
        lost = False
        if not ok:
            lost = self._lose(pid)
            self._stat(o["from"], "objections_won")
            self._stat(pid, "objections_lost")
        self._log({"kind": "defence", "player": pid, "from": o["from"], "how": how, "ok": ok, "lost": lost})
        self.st.update(stage="done", obj=None, cur={"result": "objection", "ok": ok, "how": how, "to": pid}, turn_at=self.now())

    # ---------- going to a counter
    def allowed(self, pid: str) -> list[str]:
        t = self.team(pid)
        open_ = [c for c in COUNTERS if not self.closed(c)]
        if t["sent_to"] and t["sent_to"] in open_:
            return [t["sent_to"]]
        return open_

    def go(self, pid: str, counter: str) -> None:
        self._check(pid, ("go",))
        if counter not in COUNTERS:
            raise CommunityError("Unknown counter")
        t = self.team(pid)
        why = self.closed(counter)
        if why:
            self._stat(pid, "closed")
            raise CommunityError("This counter is closed")
        if counter not in self.allowed(pid):
            raise CommunityError("You were sent to another counter")
        forced = t["sent_to"] == counter
        held = t["held"] == counter
        t.update(sent_to=None, held=None)
        if not forced:
            t["sent_from"] = None
        self.st["cur"] = {"counter": counter, "croissant": False}
        self._log({"kind": "go", "player": pid, "counter": counter})
        if counter == "coffee":
            return self._coffee(pid)
        if counter == "archive":
            return self._archive(pid)
        first = counter not in t["visited"]
        if first:
            t["visited"].append(counter)
        sc = (self.st.get("scenes") or {}).get(counter) or {"kind": "free", "mood": "chatty", "queue": 0}
        kind = "free" if held or self.event() == "openday" else ("appt" if first else sc["kind"])
        self.st["cur"].update(scene=kind, mood=sc["mood"], queue=sc.get("queue", 0))
        if kind == "appt":
            self.st["stage"] = "appt"
        elif kind == "queue":
            self.st["cur"]["cheats"] = self.rng.sample(sorted(CHEATS), 3)
            self.st["stage"] = "queue"
        else:
            self._audience(pid)

    def appt(self, pid: str, yes: bool) -> None:
        self._check(pid, ("appt",))
        if yes:
            if not self._consume(pid, "appointment"):
                raise CommunityError("You do not have an appointment card")
            self._log({"kind": "appt", "player": pid, "yes": True})
            return self._audience(pid)
        self._stat(pid, "booked")
        self._log({"kind": "booked", "player": pid})
        self.st["stage"] = "argue"

    def argue_chance(self, pid: str, arg: str) -> float:
        base, bonus, _ = ARGS[arg]
        mood = (self.st.get("cur") or {}).get("mood")
        return max(0.1, min(0.95, base + bonus.get(mood, 0)))

    def argue(self, pid: str, arg: str) -> None:
        self._check(pid, ("argue",))
        if arg not in ARGS:
            raise CommunityError("Unknown action")
        need = ARGS[arg][2]
        if need and not self._consume(pid, need):
            raise CommunityError("You do not have this trick card")
        ok = self.rng.random() < self.argue_chance(pid, arg)
        self._log({"kind": "argue", "player": pid, "arg": arg, "ok": ok, "counter": self.st["cur"]["counter"]})
        if not ok:
            self._stat(pid, "sent_home")
            self.st.update(stage="done")
            self.st["cur"]["result"] = "no_audience"
            self.st["cur"]["arg"] = arg
            return
        self._stat(pid, "calls")
        if arg == "croissant":
            self.st["cur"]["croissant"] = True
            self._stat(pid, "croissants")
        self._log({"kind": "call", "player": pid, "counter": self.st["cur"]["counter"]})
        self._audience(pid)

    def queue(self, pid: str, how: str) -> None:
        self._check(pid, ("queue",))
        cur = self.st["cur"]
        c = cur["counter"]
        if how == "wait":
            if self.rng.random() < WAIT_SERVED:
                self._log({"kind": "waited", "player": pid, "counter": c, "ok": True})
                return self._audience(pid)
            self.team(pid)["held"] = c
            self.team(pid)["sent_to"] = c
            self._log({"kind": "waited", "player": pid, "counter": c, "ok": False})
            cur["result"] = "held"
            self.st["stage"] = "done"
            return
        if how not in CHEATS or how not in (cur.get("cheats") or []):
            raise CommunityError("Unknown action")
        t = self.team(pid)
        if how == "folder" and not t["folder"]:
            raise CommunityError("Your folder is empty")
        if how == "croissant" and not self._consume(pid, "croissant"):
            raise CommunityError("You do not have this trick card")
        chance, conseq = CHEATS[how]
        self._stat(pid, "cheats")
        if self.rng.random() < chance:
            self._log({"kind": "cheat", "player": pid, "how": how, "ok": True, "counter": c})
            if how == "croissant":
                cur["croissant"] = True
            return self._audience(pid)
        self._stat(pid, "cheats_caught")
        if conseq == "complain":
            t["relations"] = max(0, t["relations"] - 1)
        elif conseq == "close":
            self.st.setdefault("shut", {})[c] = self.st["round"]
        self._log({"kind": "cheat", "player": pid, "how": how, "ok": False, "conseq": conseq, "counter": c})
        cur.update(result="caught", how=how, conseq=conseq)
        self.st["stage"] = "done"

    def _audience(self, pid: str) -> None:
        """At the counter: a ticket (ding-dong), a missing document handed in – or an authority card."""
        cur = self.st["cur"]
        c = cur["counter"]
        self.st["ticket"] = self.st.get("ticket", 50) + 1
        self.st["display"] = {"n": self.st["ticket"], "c": c, "player": pid}
        t = self.team(pid)
        if t["todo"] and t["todo"] in t["folder"]:
            t["folder"].remove(t["todo"])
            doc, t["todo"] = t["todo"], None
            self._log({"kind": "handed", "player": pid, "doc": doc, "counter": c})
            cur.update(result="handed", doc=doc)
            self.st["stage"] = "done"
            self._gain(pid, 1, c)
            return
        if c == "slow" and not self.meets():
            t["pending"] += 1
            self._log({"kind": "pile", "player": pid})
            cur.update(result="pile")
            self.st["stage"] = "done"
            return
        keys = self._deck(c)
        card = self.rng.choice(keys)
        if cur.get("croissant"):
            other = self.rng.choice(keys)
            if CARD_RANK[CARD_EFFECT[other][0].split(":")[0]] > CARD_RANK[CARD_EFFECT[card][0].split(":")[0]]:
                card = other
        cur["card"] = card
        self._log({"kind": "card", "player": pid, "card": card, "counter": c})
        eff = CARD_EFFECT[card][0]
        if eff.startswith("refer:") and "connections" in t["tricks"]:
            self.st["stage"] = "card"                      # use 🤝 connections – or accept the referral
            return
        self._apply(pid, card)

    def _deck(self, c: str) -> list[str]:
        out = []
        for k, _, w in CARDS[c]:
            out += [k] * w
        return out

    def react(self, pid: str, use: bool) -> None:
        self._check(pid, ("card",))
        cur = self.st["cur"]
        if use:
            if not self._consume(pid, "connections"):
                raise CommunityError("You do not have this trick card")
            self._stat(pid, "connections")
            self._log({"kind": "connections", "player": pid})
            keys = [k for k in self._deck(cur["counter"]) if not CARD_EFFECT[k][0].startswith("refer:")]
            cur["card"] = self.rng.choice(keys)
            self._log({"kind": "card", "player": pid, "card": cur["card"], "counter": cur["counter"]})
        self._apply(pid, cur["card"])

    def _apply(self, pid: str, card: str) -> None:
        cur = self.st["cur"]
        t = self.team(pid)
        eff, office = CARD_EFFECT[card]
        kind, _, arg = eff.partition(":")
        self.st["stage"] = "done"
        res = None
        if kind in GRUMPY and "friendly" in t["tricks"]:
            self._consume(pid, "friendly")
            self._stat(pid, "friendly")
            cur["result"] = "friendly"
            self._gain(pid, 1, office)
            return
        if kind == "stamp":
            res = "stamp"
            self._gain(pid, 1, office)
        elif kind == "stamp2":
            res = "stamp2"
            self._gain(pid, 2, office)
        elif kind == "refer":
            res = "refer"
            self._refer(pid, office, arg)
        elif kind == "need":
            if arg in t["folder"]:
                t["folder"].remove(arg)
                res = "doc_ok"
                self._gain(pid, 1, office)
            elif self._consume(pid, "folder"):
                self._stat(pid, "folder")
                res = "folder"
                self._gain(pid, 1, office)
            else:
                t["todo"] = arg
                self._stat(pid, "missing")
                res = "missing"
        elif kind == "lunch":
            t["skip"] += 1
            self._stat(pid, "lunch")
            res = "lunch"
        elif kind in ("grumpy", "holiday", "nothing"):
            self._stat(pid, kind)
            res = kind
        elif kind == "pile":
            t["pending"] += 1
            self._stat(pid, "postponed")
            res = "pile"
        elif kind == "trick":
            cur["trick"] = self._draw_trick(pid)
            res = "trick"
        elif kind == "tree":
            yes = self.rng.random() < (TREE_FRIDAY if self.weekday() == 4 else TREE_YES)
            res = "tree_yes" if yes else "tree_no"
            if yes:
                self._gain(pid, 1, office)
            else:
                self._stat(pid, "tree_no")
        elif kind == "mini":
            self._mini(pid, arg, why="card", office=office)
            return
        cur["result"] = res

    def _refer(self, pid: str, office: str, to: str) -> None:
        t = self.team(pid)
        self._stat(pid, "referrals")
        rs = t["stats"].setdefault("ref_to", {})
        rs[to] = rs.get(to, 0) + 1
        if t.get("sent_from") == to or to == office:
            self._stat(pid, "pingpong")
        t.update(sent_to=to, sent_from=office)

    # ---------- the archive and the coffee kitchen
    def _archive(self, pid: str) -> None:
        t = self.team(pid)
        cur = self.st["cur"]
        if t["todo"] and t["todo"] not in t["folder"]:
            if self.rng.random() < 0.3:
                self._log({"kind": "preform", "player": pid})
                return self._mini(pid, "form", why="preform")
            doc = t["todo"]
        else:
            doc = self.rng.choice(DOCS)
        cur.update(result="doc", doc=doc)
        if len(t["folder"]) >= 3:
            t["folder"].pop(0)
        t["folder"].append(doc)
        self._log({"kind": "doc", "player": pid, "doc": doc})
        self.st["stage"] = "done"

    def _coffee(self, pid: str) -> None:
        t = self.team(pid)
        t["relations"] = min(3, t["relations"] + 1)
        k = self._draw_trick(pid)
        rumour = self.rng.choice(RUMOURS)
        info = None
        if rumour == "r_building":
            info = next((n for n in range(1, 9) if self.building_open(self.st["round"] + n)), 1)
        elif rumour == "r_commission":
            info = next(n for n in range(1, 4) if self.meets(self.st["round"] + n))
        self.st["cur"].update(result="coffee", trick=k, rumour=rumour, info=info)
        self._log({"kind": "coffee", "player": pid, "trick": bool(k)})
        self.st["stage"] = "done"

    # ---------- mini-games (server-authoritative)
    def _mini(self, pid: str, game: str, why: str, office: str | None = None) -> None:
        now = self.now()
        m = {"game": game, "why": why, "office": office, "start": now, "until": now + MINI_SECONDS[game]}
        if game == "form":
            m["boxes"] = self.rng.sample(FORM_BOXES, 3)
        elif game == "stamp":
            m.update(center=round(0.25 + self.rng.random() * 0.5, 3), width=STAMP_WINDOW, period=STAMP_PERIOD)
        elif game == "speak":
            item = self.rng.choice(SPEAK_ITEMS)
            opts = [item] + self.rng.sample([x for x in SPEAK_ITEMS if x != item], 2)
            self.rng.shuffle(opts)
            m.update(article=self.rng.randint(2, 19), paragraph=self.rng.randint(1, 9), item=item, options=opts,
                     extra=self.rng.randint(1, 4))
        if not self.st.get("cur"):
            self.st["cur"] = {}
        self.st["cur"]["mini"] = m
        self.st["stage"] = "mini"
        self.st["turn_at"] = now
        if not self.r.get("minigames", True) or self.is_bot(pid):
            self._mini_done(pid, self.rng.random() < BOT_SKILL.get(self.level(pid), 0.65) if self.is_bot(pid) else self.rng.random() < 0.6, auto=True)

    @staticmethod
    def stamp_pos(m: dict, t: float) -> float:
        x = ((t - m["start"]) / m["period"]) % 2.0
        return x if x <= 1 else 2 - x

    def mini(self, pid: str, data: dict) -> None:
        self._check(pid, ("mini",))
        m = self.st["cur"]["mini"]
        now = self.now()
        if now > m["until"] + MINI_GRACE:
            return self._mini_done(pid, False)
        g = m["game"]
        if g == "form":
            ok = int(data.get("ticked") or 0) >= len(m["boxes"])
        elif g == "stamp":
            pos = self.stamp_pos(m, now - LATENCY)
            ok = abs(pos - m["center"]) <= m["width"]
            m["hit"] = round(pos, 3)
        else:
            try:
                ok = m["options"][int(data.get("answer"))] == m["item"]
            except (TypeError, ValueError, IndexError):
                ok = False
        self._mini_done(pid, ok)

    def _mini_done(self, pid: str, ok: bool, auto: bool = False) -> None:
        cur = self.st["cur"]
        m = cur["mini"]
        m.update(ok=ok, auto=auto)
        self._stat(pid, "minis")
        if ok:
            self._stat(pid, "minis_ok")
        self._log({"kind": "mini", "player": pid, "game": m["game"], "ok": ok, "why": m["why"]})
        self.st["stage"] = "done"
        if m["why"] == "card":
            cur["result"] = "mini_ok" if ok else "mini_no"
            if ok:
                self._gain(pid, 1, m.get("office") or "info")
        elif m["why"] == "preform":
            t = self.team(pid)
            if ok and t["todo"]:
                if len(t["folder"]) >= 3:
                    t["folder"].pop(0)
                t["folder"].append(t["todo"])
                cur.update(result="doc", doc=t["todo"])
            else:
                cur["result"] = "preform_no"
        else:                                                  # the administration's form: fill it first
            if ok:
                cur["result"] = None
                self.st["cur"] = None
                self.st["stage"] = "go"
            else:
                cur["result"] = "form_no"

    def end_turn(self, pid: str) -> None:
        self._check(pid, ("done",))
        self._next_turn()

    # ---------- the administration
    def admin_card(self, pid: str, idx, target) -> None:
        self._check(pid, ("admin",))
        hand = self.st["admin_hand"]
        try:
            card = hand[int(idx)]
        except (TypeError, ValueError, IndexError):
            raise CommunityError("Unknown action") from None
        target = str(target or "")
        if target not in self.builders():
            raise CommunityError("Choose a team")
        t = self.team(target)
        blocked = None
        if card == "a_refer":
            if self._consume(target, "connections"):
                blocked = "connections"
            else:
                to = self.rng.choice(DESKS)
                self._refer(target, "admin", to)
        elif card == "a_lunch":
            if self._consume(target, "friendly"):
                blocked = "friendly"
            else:
                t["skip"] += 1
                self._stat(target, "lunch")
        elif card == "a_regulation":
            if self._consume(target, "folder"):
                blocked = "folder"
            else:
                t["folder"] = []
        elif card == "a_form":
            t["form_due"] = True
        elif card == "a_revoke":
            if self._consume(target, "friendly"):
                blocked = "friendly"
            else:
                self._lose(target)
        hand.pop(int(idx))
        hand.append(self._admin_card())
        self._log({"kind": "admin", "player": pid, "card": card, "to": target, "blocked": blocked})
        self._next_turn()

    def admin_toggle(self, pid: str, counter: str) -> None:
        self._check(pid, ("admin",))
        if counter not in DESKS + ("archive",):
            raise CommunityError("Unknown counter")
        cl = self.st.setdefault("closed", [])
        if counter in cl:
            cl.remove(counter)
            on = False
        else:
            if len(cl) >= 2:
                raise CommunityError("At most two counters can be closed")
            cl.append(counter)
            on = True
        self._log({"kind": "toggle", "player": pid, "counter": counter, "closed": on})
        self._next_turn()

    # ---------- the end
    def _finish(self) -> None:
        order = self.order()
        adm = self.admin()
        score = {}
        for p in order:
            if p == adm:
                score[p] = 1000 if self.st.get("admin_won") else -1
            else:
                score[p] = self.stamps(p) + (100 if self.st.get("winner") == p else 0)
        self.st["places"] = places(order, score)
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st.update(phase="done", stage=None, finished=self.now())
        self.st["moments"] = self.moments()

    def end(self) -> None:
        if self.st.get("phase") in ("play", "projects"):
            if self.st.get("phase") == "projects":
                for p in self.builders():
                    if not self.team(p)["project"]:
                        self.team(p)["project"] = "treehouse"
            self._finish()

    def moments(self) -> list[dict]:
        """The funniest moments: per kind the team with the most (at least the minimum)."""
        out = []
        teams = self.st.get("teams") or {}
        for key, least in (("ref_to", 2), ("pingpong", 2), ("booked", 2), ("lunch", 1), ("caught", 1), ("cheats_caught", 1),
                           ("tree_no", 1), ("objections_won", 1), ("postponed", 2), ("computer_no", 1), ("missing", 2),
                           ("croissants", 1), ("calls", 3), ("friendly", 1)):
            best = None
            for p, t in teams.items():
                s = t.get("stats") or {}
                if key == "ref_to":
                    for c, n in (s.get("ref_to") or {}).items():
                        if n >= least and (not best or n > best["n"]):
                            best = {"k": key, "p": p, "n": n, "c": c}
                elif s.get(key, 0) >= least and (not best or s[key] > best["n"]):
                    best = {"k": key, "p": p, "n": s[key]}
            if best:
                out.append(best)
        return out[:5]

    # ---------- bots
    def _bot_go(self, p: str) -> None:
        t = self.team(p)
        lvl = self.level(p)
        if t["mayor"] and (self.stamps(p) >= self.target - 2 or self.st["round"] > 8) and self.rng.random() < 0.6:
            return self.play(p, "mayor")
        if "gift" in t["tricks"] and self.rng.random() < {"easy": 0.5, "normal": 0.25, "hard": 0.1}[lvl]:
            return self.play(p, "gift")
        if "objection" in t["tricks"]:
            rivals = [q for q in self.builders() if q != p and self.stamps(q) >= max(2, self.stamps(p))]
            if rivals and self.rng.random() < 0.7:
                return self.play(p, "objection", max(rivals, key=self.stamps))
        allowed = self.allowed(p)
        if len(allowed) == 1:
            return self.go(p, allowed[0])
        want = None
        if t["todo"] and t["todo"] in t["folder"]:
            want = next((c for c in ("building", "green", "info", "slow") if c in allowed), None)
        elif t["todo"] and "archive" in allowed:
            want = "archive"
        elif "building" in allowed and lvl != "easy":
            want = "building"
        elif self.meets() and "slow" in allowed:
            want = "slow"
        elif len(t["tricks"]) < 2 and "coffee" in allowed and self.rng.random() < 0.6:
            want = "coffee"
        if not want or self.rng.random() < (0.35 if lvl == "easy" else 0.1):
            pool = [c for c in allowed if c != "archive" or t["todo"]]
            want = self.rng.choice(pool or allowed)
        self.go(p, want)

    def _bot_argue(self, p: str) -> None:
        t = self.team(p)
        opts = [a for a, (_, _, need) in ARGS.items() if not need or need in t["tricks"]]
        self.argue(p, max(opts, key=lambda a: (self.argue_chance(p, a), -len(a))))

    def _bot_queue(self, p: str) -> None:
        cur = self.st["cur"]
        t = self.team(p)
        opts = [c for c in cur.get("cheats") or [] if (c != "folder" or t["folder"]) and (c != "croissant" or "croissant" in t["tricks"])]
        best = max(opts, key=lambda c: CHEATS[c][0], default=None)
        if best and CHEATS[best][0] >= 0.7 or (best and self.level(p) == "easy" and self.rng.random() < 0.5):
            return self.queue(p, best)
        self.queue(p, "wait")

    def _bot_defend(self, p: str) -> None:
        t = self.team(p)
        if t["folder"]:
            return self.defend(p, "report")
        self.defend(p, "signatures" if SIG_BASE + SIG_REL * t["relations"] >= COMPROMISE else "compromise")

    def _bot_admin(self, p: str) -> None:
        bs = self.builders()
        lead = max(bs, key=lambda q: (self.stamps(q), self.rng.random()))
        hand = self.st["admin_hand"]
        if self.rng.random() < 0.2 and self.team(lead)["sent_to"] in DESKS and len(self.st.get("closed") or []) < 2:
            return self.admin_toggle(p, self.team(lead)["sent_to"])
        pref = ["a_revoke", "a_lunch", "a_form", "a_refer", "a_regulation"] if self.stamps(lead) >= 2 else ["a_lunch", "a_form", "a_refer", "a_regulation", "a_revoke"]
        idx = min(range(len(hand)), key=lambda i: pref.index(hand[i]))
        if (self.st.get("closed") or []) and self.rng.random() < 0.3:
            return self.admin_toggle(p, self.st["closed"][0])
        self.admin_card(p, idx, lead)

    def bot_step(self, p: str) -> None:
        stage = self.st.get("stage")
        if stage == "go":
            self._bot_go(p)
        elif stage == "appt":
            self.appt(p, "appointment" in self.team(p)["tricks"])
        elif stage == "argue":
            self._bot_argue(p)
        elif stage == "queue":
            self._bot_queue(p)
        elif stage == "card":
            self.react(p, True)
        elif stage == "objection":
            self._bot_defend(p)
        elif stage == "admin":
            self._bot_admin(p)
        elif stage == "mini":
            self._mini_done(p, self.rng.random() < BOT_SKILL.get(self.level(p), 0.65), auto=True)
        elif stage == "done":
            self.end_turn(p)

    def nudge(self) -> None:
        """Who leads helps a team that does not act: its step is done as a bot would (a mini-game: not solved)."""
        if self.st.get("phase") == "projects":
            return self.projects_done()
        if self.st.get("phase") != "play":
            return
        p = self.actor()
        if self.st.get("stage") == "mini":
            return self._mini_done(p, False)
        self.bot_step(p)

    def tick(self) -> bool:
        """Bots act after their reaction time, a mini-game runs out. True if something changed."""
        changed = False
        delay = bot_delay(self.r, BOT_DELAY)
        for _ in range(MAX_ROUNDS * 60 if delay == 0 else 3):
            if self.st.get("phase") != "play":
                break
            p = self.actor()
            if self.st.get("stage") == "mini" and not self.is_bot(p):
                m = (self.st.get("cur") or {}).get("mini") or {}
                if self.now() > m.get("until", 0) + MINI_GRACE:
                    self._mini_done(p, False)
                    changed = True
                    continue
                break
            if not self.is_bot(p):
                break
            wait = delay if self.st.get("stage") in ("go", "admin") else delay * 0.7
            if self.now() - self.st.get("turn_at", 0) < wait:
                break
            self.bot_step(p)
            self.st["turn_at"] = self.now()
            changed = True
        return changed


# ================================================================ the games in the database (table card_game, kind "stempeljagd")
class Stempeljagd(CardGames):
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
        return {**self.default_rules(), "rewards": rewards_of(self.db), "max_players": MAX_PLAYERS,
                "targets": LENGTHS, "admin_rounds": ADMIN_ROUNDS}

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
        out["length"] = out["length"] if out["length"] in LENGTHS else "normal"
        out["mode"] = out["mode"] if out["mode"] in MODES else "teams"
        out["admin"] = out["admin"] if out["admin"] in ("bot", "host") or out["admin"].isdigit() else "bot"
        out["projects"] = out["projects"] if out["projects"] in ("pick", "random") else "pick"
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
            teams = st.get("teams") or {}
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                t = teams.get(p["id"]) or {}
                s = t.get("stats") or {}
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]),
                        "stamps": len(t.get("stamps") or []), "target": LENGTHS.get(st["rules"].get("length"), 7),
                        "project": t.get("project"), "admin": p["id"] == st.get("admin_id"), "mode": st["rules"].get("mode"),
                        "referrals": s.get("referrals", 0), "turns": t.get("turns", 0),
                        "seconds": t.get("seconds") if st.get("winner") == p["id"] else None,
                        "won": st["places"].get(p["id"]) == 1, "complete": bool(st.get("complete")), "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
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
        if need > 0 and self.bots_off(KIND, st["players"]):
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
        r = st["rules"]
        admin_mode = r["mode"] == "admin"
        admin_human = admin_mode and r["admin"] != "bot" and any(p["id"] == r["admin"] for p in humans)
        builders_h = [p for p in humans if not (admin_human and p["id"] == r["admin"])]
        n = r["bots"]
        if st.get("solo") and not (admin_mode and not admin_human):
            n = max(1, n)                                  # alone: at least one bot (against a bot administration: none needed)
        n = max(0, min(n, MAX_PLAYERS - len(builders_h)))
        bots = self._bots(st, n + (1 if admin_mode and not admin_human else 0))
        st.pop("bot_pool", None)
        if admin_mode and not admin_human:
            if not bots:
                raise CommunityError("Playing with bots is switched off for this game")
            adm = bots.pop()
            adm.update(name="Amtsrat Bot", emoji="🏛️", id="botadmin")
            st["players"] = builders_h + bots + [adm]
            st["admin_id"] = adm["id"]
        elif admin_human:
            adm = next(p for p in humans if p["id"] == r["admin"])
            st["players"] = builders_h + bots + [adm]
            st["admin_id"] = adm["id"]
        else:
            st["players"] = humans + bots
            st["admin_id"] = None
        builders = [p for p in st["players"] if p["id"] != st.get("admin_id")]
        if len(st["players"]) < 2 or not builders or len(builders) > MAX_PLAYERS:
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
            if r["admin"] == "host":
                r["admin"] = str(host)
            self.db.set_setting(f"game_rules.{KIND}", {**r, "admin": "bot" if r["admin"] == "bot" else "host"})
            st = {"kind": KIND, "rules": r, "players": [self._person(host)], "phase": "lobby", "solo": solo, "bot_pool": list(bots or [])}
            gid = self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, int(solo), json.dumps(st))
            if solo:
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
            if len(st["players"]) >= MAX_PLAYERS + (1 if st["rules"]["mode"] == "admin" else 0):
                raise CommunityError("The table is full")
            st["players"].append(self._person(pid))
            self._save(row, st)

    def set_admin(self, viewer: int, who: str) -> None:
        """Lobby: who leads chooses who plays the administration (a seated person or "bot") and the mode."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            who = str(who or "")
            if who == "teams":
                st["rules"]["mode"] = "teams"
            elif who == "bot" or any(p["id"] == who for p in st["players"]):
                st["rules"].update(mode="admin", admin=who)
            else:
                raise CommunityError("Choose a team")
            self._save(row, st)

    def begin(self, kind: str, viewer: int, starter=None) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            apply_starter(st, starter_mode(self.db), starter, leader=row["host_id"])
            self._deal(st)
            self._save(row, st)

    ACTIONS = ("project", "play", "go", "appt", "argue", "queue", "react", "mini", "defend", "end_turn",
               "admin_card", "admin_toggle")

    def act(self, pid: int, action: str, data: dict | None = None):
        if action not in self.ACTIONS:
            raise CommunityError("Unknown action")
        d = data or {}
        me = str(pid)

        def run(t: Table):
            if action == "project":
                return t.pick_project(me, str(d.get("key") or ""))
            if action == "play":
                return t.play(me, str(d.get("trick") or ""), d.get("target"))
            if action == "go":
                return t.go(me, str(d.get("counter") or ""))
            if action == "appt":
                return t.appt(me, bool(d.get("yes")))
            if action == "argue":
                return t.argue(me, str(d.get("key") or ""))
            if action == "queue":
                return t.queue(me, str(d.get("key") or ""))
            if action == "react":
                return t.react(me, bool(d.get("use")))
            if action == "mini":
                return t.mini(me, d)
            if action == "defend":
                return t.defend(me, str(d.get("key") or ""))
            if action == "admin_card":
                return t.admin_card(me, d.get("idx"), d.get("target"))
            if action == "admin_toggle":
                return t.admin_toggle(me, str(d.get("counter") or ""))
            return t.end_turn(me)
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

    def nudge(self, viewer: int) -> None:
        self._with(viewer, lambda t: t.nudge())

    def end(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] in ("play", "projects"):
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
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2, "max_players": MAX_PLAYERS,
                "target": LENGTHS.get(st["rules"].get("length"), 7), "me": me if joined else None}
        seat = lambda p: {"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"),  # noqa: E731
                          "bot": bool(p.get("bot")), "guest": bool(p.get("guest")), "color": p.get("color")}
        if st["phase"] == "lobby":
            players = [seat(p) for p in st["players"]]
            bots = st["rules"]["bots"] if not st.get("solo") else max(1, st["rules"]["bots"])
            return {**base, "players": players, "bots": max(0, min(bots, MAX_PLAYERS - len(players)))}
        t = self.table(st)
        coins, pl = st.get("coins") or {}, st.get("places") or {}
        teams = st.get("teams") or {}
        players = []
        for i, p in enumerate(st["players"]):
            tm = teams.get(p["id"])
            d = {**seat(p), "seat": i, "admin": p["id"] == st.get("admin_id"), "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0)}
            if tm:
                d.update(stamps=tm["stamps"], fines=tm["fines"], project=tm["project"], compromise=tm["compromise"],
                         tricks=len(tm["tricks"]), mayor=tm["mayor"], relations=tm["relations"], skip=tm["skip"],
                         sent_to=tm["sent_to"], held=tm["held"], pending=tm["pending"], todo=tm["todo"],
                         folder=len(tm["folder"]), stats=tm.get("stats") if ph == "done" else None, seconds=tm.get("seconds"))
            players.append(d)
        live = ph == "play"
        actor = t.actor() if live else None
        mine = teams.get(me) if joined else None
        cur = st.get("cur") or None
        if cur and cur.get("mini") and actor != me:
            cur = {**cur, "mini": {k: v for k, v in cur["mini"].items() if k not in ("item",)}}
        out = {**base, "players": players, "round": st.get("round", 1), "turn": st.get("turn") if live else None,
               "stage": st.get("stage") if live else None, "actor": actor, "my_turn": bool(joined and actor == me),
               "weekday": t.weekday(), "moon": t.moon(), "event": t.event() if live else None,
               "building_open": t.building_open(), "meets": t.meets(), "meets_in": next(n for n in range(0, 3) if t.meets(st.get("round", 1) + n)),
               "closed": {c: t.closed(c) for c in COUNTERS if live and t.closed(c)}, "scenes": st.get("scenes") or {},
               "ticket": st.get("ticket"), "display": st.get("display"), "cur": cur, "obj": st.get("obj"),
               "admin_id": st.get("admin_id"), "admin_rounds": ADMIN_ROUNDS.get(st["rules"].get("length"), 16),
               "last": st.get("last"), "log": (st.get("log") or [])[-14:], "projects_taken": [tm["project"] for tm in teams.values() if tm.get("project")],
               "ranking": st.get("ranking"), "complete": bool(st.get("complete")), "winner": st.get("winner"),
               "admin_won": bool(st.get("admin_won")), "moments": st.get("moments"), "now": self.now()}
        if mine:
            out["mine"] = {"tricks": mine["tricks"], "folder": mine["folder"], "todo": mine["todo"], "mayor": mine["mayor"],
                           "allowed": t.allowed(me) if live and actor == me and st.get("stage") == "go" else [],
                           "visited": mine["visited"]}
            if live and actor == me and st.get("stage") == "argue":
                out["mine"]["chances"] = {a: round(t.argue_chance(me, a), 2) for a in ARGS}
        if joined and me == st.get("admin_id") and live:
            out["mine"] = {"hand": st.get("admin_hand") or [], "tricks": [], "folder": []}
        return out

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
