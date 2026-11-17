"""«Werwölfe» – the classic social deduction party game, played in one room; the app is the game master.

Everybody has the app on their own device (family and guests via QR code), 2 to 12 people; a game has 5 to 12
players: when the leader begins with fewer than 5 at the table, bots (the animal bots of the card games) fill the table
up to 5 – or up to the number the leader chose (rule `fill`, 5–12). The tables live in the `card_game` table with kind
"werwolf" (lobby, join, summary and may_lead come from cardgames.CardGames). Who opens the table (or a parent) leads:
starts, advances a phase when somebody is idle and ends.

Roles (dealt at random when the game begins; the leader chooses them – `auto` picks a set by the number of players):
  wolf      1–3 – wake up at night and choose a victim together
  villager  no special power
  seer      every night looks at the role of one living player (only she sees the result)
  witch     one healing potion (saves the wolves' victim) and one poison potion (kills a player) for the whole game
  hunter    when he dies (night or vote) he shoots one living player who dies too
  amor      in the first night links two players as lovers: when one dies, the other dies of grief
Rules (start dialog / lobby, remembered): auto (the role set by the number of players, see `preset`) or the number of
wolves (1–3) and seer / witch / hunter / amor on or off; talk – the minutes to talk during the day (1, 2, 3, 5, 10);
fill – bots fill the table up to this number of players (5–12).
A custom set needs fewer wolves than half of the players and must fit the number of players.

The phases:
  roles    everybody looks at their role (tap to reveal, hide again); the leader lets the night fall
  night    the phones show «eyes closed»; only the active role gets its buttons, in this order:
             amor (night 1) → wolves → seer → witch (a step whose role is dead – or not in play – is left out)
           wolves: every living wolf taps a victim and sees the others' taps; when all living wolves agree, the
           victim is chosen. When the leader advances: the target with the most wolf votes – a tie: nobody.
           seer: taps a player, sees the role, taps «close eyes». witch: sees the victim, may heal it and/or poison
           somebody (each potion once per game, also both in one night), then the night ends.
  hunter   a hunter died: he chooses whom he takes with him (the leader may advance: nobody)
  day      the village wakes up: who died (the role is revealed – not how), then the talk timer runs (the leader may
           skip to the vote)
  vote     every living player votes on their phone (or abstains); the vote closes when everybody voted or the
           leader closes it. The player with the most votes is out – a tie (or no vote): nobody is out
  verdict  who is out and their role (and the hunter, and the lover); the leader lets the next night fall
  done     the end: every role is shown
A lover dies with the other (cause "love"); the hunter shoots also when he dies of grief.
Win (checked after every night and every vote, after the hunter shot):
  lovers   the two lovers – one wolf and one not – are the last two alive: they win together (only the two)
  village  no wolf is alive: all who are not wolves win (dead or alive)
  wolves   at least as many wolves alive as others: all wolves win
Dead players are spectators: they see every role, the lovers and the wolves' votes – and cannot act (only a dead
hunter shoots once). Secrecy: the state of a player holds only what that player may know (`_view`) – a bot's role
too: it is shown like a person's (dead, the own wolves, the seer's vision, the end).
Bots (lazy like the card games: every state request moves them, no background thread; `Table.tick`) act after a
"thinking" time – at night 4–10 s after the step began (it varies, so the length of a step does not tell whether a
bot holds the role), in the vote 3 s plus 1.5 s per bot:
  amor     links two random living players (night 1)
  wolves   a bot wolf bites the pick of a human wolf (if one chose already), else the pick of a fellow bot wolf, else a
           random living non-wolf – so the bot wolves always agree with each other
  seer     looks at a random living player not seen yet, then closes the eyes
  witch    heals the victim with 50 % (potion left), poisons with 15 % a random living other player (not the victim)
  hunter   shoots a random living player
  vote     a bot wolf votes for a random living non-wolf; any other bot for a random living other player – a bot seer
           votes for a wolf it saw (rather not for one it saw innocent) and the other village bots lean towards it
           while the bot seer lives
Roles, day and verdict wait for the leader as before (the talk timer still runs for the people).
Coins (setting `game_rewards["werwolf"]`, the amount of place 1): every person of the family on the winning side (never
bots or guests) –
only with at least two people of the family at the table, only for a game played to the end (not ended by the leader);
paid once (flag `paid`, a unique ledger `ref` per player). The winners get the «No. 1» hat, everybody of the family a
history entry (bots and guests none).
"""
from __future__ import annotations

import json
import random
import time

from .cardgames import BOTS, CardGames
from .community import CommunityError
from .pairhunt import rewards_of as _rewards_of

KIND = "werwolf"
TITLE = "Werwölfe"
EMOJI = "🐺"
MIN_PLAYERS, MAX_PLAYERS = 5, 12               # the size of a game (bots fill up to MIN_PLAYERS – or to the rule `fill`)
MIN_HUMANS = 2                                  # people at the table to begin
SPECIALS = ("seer", "witch", "hunter", "amor")
ROLES = ("wolf", "villager") + SPECIALS
TALKS = (60, 120, 180, 300, 600)
DEFAULTS = {"auto": True, "wolves": 2, "seer": True, "witch": True, "hunter": True, "amor": True, "talk": 180, "fill": MIN_PLAYERS}
STEPS = ("amor", "wolves", "seer", "witch")
ACTIONS = ("lovers", "bite", "look", "sleep", "potion", "shoot", "vote")
# the bots: the animals of the card games and a few more (up to 10 bots at a table of 2 people)
BOT_NAMES = list(BOTS) + [("Maus Mimi", "🐭"), ("Dachs Dani", "🦡"), ("Reh Rosi", "🦌"), ("Biber Benno", "🦫")]
BOT_NIGHT, BOT_NIGHT_SPREAD = 4.0, 7            # seconds before a bot acts at night: 4 … 10 (varies by night and step)
BOT_VOTE, BOT_STAGGER = 3.0, 1.5                # the vote: 3 s, then one bot after the other
WITCH_HEAL, WITCH_POISON = 0.5, 0.15


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def preset(n: int) -> dict:
    """The role set for n players: 5 → 1 wolf + seer, 6 → + witch, 7 → 2 wolves, 8 → + hunter, 9–10 → + amor,
    11–12 → 3 wolves."""
    wolves = 1 if n <= 6 else 2 if n <= 10 else 3
    return {"wolves": wolves, "seer": True, "witch": n >= 6, "hunter": n >= 8, "amor": n >= 9}


def deck_for(rules: dict, n: int) -> dict:
    """The roles in play for n players: {"wolves": k, "seer": bool, …} – raises when a custom set does not fit."""
    if rules.get("auto", True):
        return preset(n)
    d = {"wolves": int(rules.get("wolves") or 1), **{s: bool(rules.get(s)) for s in SPECIALS}}
    if d["wolves"] * 2 >= n:
        raise CommunityError("Too many wolves for this number of players")
    if d["wolves"] + sum(d[s] for s in SPECIALS) > n:
        raise CommunityError("Too many roles for this number of players")
    return d


def deck_list(d: dict) -> list[str]:
    return ["wolf"] * d["wolves"] + [s for s in SPECIALS if d.get(s)]


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

    def role(self, pid: str | None) -> str | None:
        return (self.st.get("roles") or {}).get(pid)

    def alive(self, pid: str) -> bool:
        return pid in self.order() and pid not in (self.st.get("dead") or [])

    def living(self) -> list[str]:
        return [p for p in self.order() if self.alive(p)]

    def holder(self, role: str) -> str | None:
        return next((p for p in self.order() if self.role(p) == role), None)

    def wolves(self) -> list[str]:
        return [p for p in self.living() if self.role(p) == "wolf"]

    def lover_of(self, pid: str) -> str | None:
        lv = self.st.get("lovers") or []
        return (lv[1] if lv[0] == pid else lv[0]) if pid in lv else None

    def is_bot(self, pid: str | None) -> bool:
        return any(p["id"] == pid and p.get("bot") for p in self.st["players"])

    # ---------- the start
    def begin(self) -> None:
        order = self.order()
        n = len(order)
        if n < MIN_PLAYERS:
            raise CommunityError("At least 5 players are needed")
        d = deck_for(self.r, n)
        cards = deck_list(d)
        cards += ["villager"] * (n - len(cards))
        self.rng.shuffle(cards)
        self.st.update(roles=dict(zip(order, cards)), deck=d, dead=[], lovers=None, night=0, day=0, phase="roles",
                       step=None, step_at=self.now(), potions={"heal": True, "poison": True}, seen=[], wolf_votes={},
                       victim=None, saved=False, poisoned=None, looked=False, votes={}, lynch=None, deaths=[],
                       hunter=None, hunter_due=[], after=None, log=[], winner=None, winners=[], deadline=None,
                       started_at=None, ended=False)

    # ---------- the night
    def _night(self) -> None:
        self.st["night"] += 1
        self.st.update(phase="night", step=None, wolf_votes={}, victim=None, saved=False, poisoned=None, looked=False,
                       votes={}, lynch=None, deaths=[], deadline=None, started_at=None)
        self._next_step()

    def steps(self) -> list[str]:
        """The steps of this night: amor only in the first night, a step only while its role lives."""
        out = []
        for s in STEPS:
            if s == "amor":
                a = self.holder("amor")
                if self.st["night"] == 1 and a and self.alive(a):
                    out.append(s)
            elif s == "wolves":
                if self.wolves():
                    out.append(s)
            else:
                h = self.holder(s)
                if h and self.alive(h):
                    out.append(s)
        return out

    def _next_step(self) -> None:
        cur = self.st.get("step")
        later = STEPS[STEPS.index(cur) + 1:] if cur in STEPS else STEPS
        nxt = next((s for s in later if s in self.steps()), None)
        if nxt:
            self.st.update(step=nxt, step_at=self.now())
        else:
            self._dawn()

    def actors(self) -> list[str]:
        """Who may act just now."""
        ph, step = self.st.get("phase"), self.st.get("step")
        if ph == "night":
            if step == "wolves":
                return self.wolves()
            h = self.holder(step) if step else None
            return [h] if h and self.alive(h) else []
        if ph == "hunter":
            return [self.st["hunter"]] if self.st.get("hunter") else []
        if ph == "vote":
            return self.living()
        return []

    def _target(self, t, *, me: str | None = None, self_ok: bool = False) -> str:
        t = None if t is None else str(t)
        if not t or not self.alive(t):
            raise CommunityError("Choose a living player")
        if t == me and not self_ok:
            raise CommunityError("Not yourself")
        return t

    def act(self, pid: str, action: str, target=None, target2=None, heal: bool = False, poison=None) -> None:
        if pid not in self.order():
            raise CommunityError("You are not at this table")
        if action not in ACTIONS:
            raise CommunityError("Unknown action")
        if pid not in self.actors():
            raise CommunityError("It is not your turn")
        ph, step = self.st["phase"], self.st.get("step")
        need = {"lovers": ("night", "amor"), "bite": ("night", "wolves"), "look": ("night", "seer"), "sleep": ("night", "seer"),
                "potion": ("night", "witch"), "shoot": ("hunter", None), "vote": ("vote", None)}[action]
        if ph != need[0] or (need[1] and step != need[1]):
            raise CommunityError("It is not your turn")
        if action == "lovers":
            a, b = self._target(target, self_ok=True), self._target(target2, self_ok=True)
            if a == b:
                raise CommunityError("Choose two different players")
            self.st["lovers"] = [a, b]
            self._next_step()
        elif action == "bite":
            t = self._target(target)
            if self.role(t) == "wolf":
                raise CommunityError("Choose a player who is not a wolf")
            self.st["wolf_votes"][pid] = t
            wolves = self.wolves()
            picks = {self.st["wolf_votes"].get(w) for w in wolves}
            if len(picks) == 1 and None not in picks:             # all living wolves agree
                self.st["victim"] = t
                self._next_step()
        elif action == "look":
            if self.st.get("looked"):
                raise CommunityError("You already looked tonight")
            t = self._target(target, me=pid)
            self.st["seen"].append({"night": self.st["night"], "id": t, "role": self.role(t)})
            self.st["looked"] = True
        elif action == "sleep":
            self._next_step()
        elif action == "potion":
            pot = self.st["potions"]
            if heal:
                if not pot["heal"]:
                    raise CommunityError("The healing potion is used up")
                if not self.st.get("victim"):
                    raise CommunityError("Nobody to heal tonight")
            p = None
            if poison not in (None, ""):
                if not pot["poison"]:
                    raise CommunityError("The poison potion is used up")
                p = self._target(poison, me=pid)
            if heal:
                pot["heal"], self.st["saved"] = False, True
            if p:
                pot["poison"], self.st["poisoned"] = False, p
            self._next_step()
        elif action == "shoot":
            t = self._target(target, me=pid)
            self._kill(t, "shot")
            self._hunter_done()
        elif action == "vote":
            t = "" if target in (None, "") else self._target(target, me=pid)
            self.st["votes"][pid] = t
            if all(p in self.st["votes"] for p in self.living()):
                self._close_vote()

    # ---------- deaths
    def _kill(self, pid: str, cause: str) -> None:
        if not self.alive(pid):
            return
        self.st["dead"].append(pid)
        self.st["deaths"].append({"id": pid, "role": self.role(pid), "cause": cause})
        if self.role(pid) == "hunter":
            self.st["hunter_due"].append(pid)
        lv = self.lover_of(pid)
        if lv and self.alive(lv):
            self._kill(lv, "love")

    def _dawn(self) -> None:
        self.st.update(step=None, day=self.st["night"])
        if self.st.get("victim") and not self.st.get("saved"):
            self._kill(self.st["victim"], "wolves")
        if self.st.get("poisoned"):
            self._kill(self.st["poisoned"], "poison")
        self._after_deaths("day")

    def _after_deaths(self, nxt: str) -> None:
        self.st["after"] = nxt
        due = self.st["hunter_due"]
        if due:
            self.st.update(phase="hunter", hunter=due.pop(0), step=None, step_at=self.now())
            return
        self.st.update(hunter=None)
        self._settle(nxt)

    def _hunter_done(self) -> None:
        self._after_deaths(self.st.get("after") or "day")

    def _settle(self, nxt: str) -> None:
        kind = "night" if nxt == "day" else "day"
        self.st["log"].append({"kind": kind, "n": self.st["night"], "deaths": list(self.st["deaths"]),
                               "lynch": self.st.get("lynch") if kind == "day" else None,
                               "votes": dict(self.st.get("votes") or {}) if kind == "day" else None})
        w = self.winner()
        if w:
            self._finish(w)
            return
        if nxt == "day":
            now = self.now()
            self.st.update(phase="day", started_at=now, deadline=now + int(self.r.get("talk") or DEFAULTS["talk"]), step_at=now)
        else:
            self.st.update(phase="verdict", step_at=self.now())

    # ---------- the day
    def _open_vote(self) -> None:
        self.st.update(phase="vote", votes={}, lynch=None, deaths=[], deadline=None, step_at=self.now())

    def tally(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p, t in (self.st.get("votes") or {}).items():
            if t and self.alive(p):
                out[t] = out.get(t, 0) + 1
        return out

    def _close_vote(self) -> None:
        """The most votes is out – a tie (or no vote at all): nobody."""
        c = self.tally()
        top = max(c.values()) if c else 0
        best = [p for p, n in c.items() if n == top]
        self.st["lynch"] = best[0] if top and len(best) == 1 else None
        if self.st["lynch"]:
            self._kill(self.st["lynch"], "vote")
        self._after_deaths("verdict")

    def tick(self) -> bool:
        """Time moves the game on: the talk timer runs out, the bots act. True if something changed."""
        changed = False
        for _ in range(8 * MAX_PLAYERS):
            if self.st.get("phase") == "day" and self.now() >= (self.st.get("deadline") or 0):
                self._open_vote()
            elif not self._bots_move():
                break
            changed = True
        return changed

    # ---------- the bots (one move per call; tick calls again until nobody moves)
    def bot_wait(self) -> float:
        """Seconds a bot thinks in this night step – 4 … 10, not the same in every step."""
        step = self.st.get("step")
        k = STEPS.index(step) if step in STEPS else 0
        return BOT_NIGHT + (int(self.st.get("night") or 0) * 5 + k * 3) % BOT_NIGHT_SPREAD

    def _bots_move(self) -> bool:
        ph, step = self.st.get("phase"), self.st.get("step")
        bots = [p for p in self.actors() if self.is_bot(p)]
        if not bots:
            return False
        waited = self.now() - (self.st.get("step_at") or 0)
        if ph in ("night", "hunter") and waited < self.bot_wait():
            return False
        rng = self.rng
        b = bots[0]
        if ph == "night" and step == "wolves":
            return self._bot_wolves(bots)
        if ph == "night" and step == "amor":
            a, c = rng.sample(self.living(), 2)
            self.act(b, "lovers", a, c)
        elif ph == "night" and step == "seer":
            others = [p for p in self.living() if p != b]
            seen = {s["id"] for s in self.st.get("seen") or []}
            fresh = [p for p in others if p not in seen] or others
            if not self.st.get("looked") and fresh:
                self.act(b, "look", rng.choice(fresh))
            else:
                self.act(b, "sleep")
        elif ph == "night" and step == "witch":
            pot, victim = self.st["potions"], self.st.get("victim")
            heal = bool(victim and pot["heal"] and rng.random() < WITCH_HEAL)
            poison = None
            if pot["poison"] and rng.random() < WITCH_POISON:
                cands = [p for p in self.living() if p != b and (heal or p != victim)]
                poison = rng.choice(cands) if cands else None
            self.act(b, "potion", heal=heal, poison=poison)
        elif ph == "hunter":
            others = [p for p in self.living() if p != b]
            if others:
                self.act(b, "shoot", rng.choice(others))
            else:
                self._hunter_done()
        elif ph == "vote":
            votes = self.st.get("votes") or {}
            for i, v in enumerate(bots):
                if v not in votes and waited >= BOT_VOTE + i * BOT_STAGGER:
                    self.act(v, "vote", self._bot_vote(v))
                    return True
            return False
        else:
            return False
        return True

    def _bot_wolves(self, bots: list[str]) -> bool:
        """A bot wolf bites what a human wolf chose, else what a fellow bot wolf chose, else a random non-wolf."""
        wv = self.st["wolf_votes"]
        targets = [p for p in self.living() if self.role(p) != "wolf"]
        if not targets:
            return False
        human = next((wv[w] for w in self.wolves() if not self.is_bot(w) and wv.get(w) in targets), None)
        for b in bots:
            want = human or next((wv[w] for w in bots if wv.get(w) in targets), None) or self.rng.choice(targets)
            if wv.get(b) != want:
                self.act(b, "bite", want)
                return True
        return False

    def _bot_vote(self, b: str) -> str:
        others = [p for p in self.living() if p != b]
        if self.role(b) == "wolf":
            others = [p for p in others if self.role(p) != "wolf"]
        if not others:
            return ""
        weight = {p: 1.0 for p in others}
        if self.role(b) != "wolf":
            seer = self.holder("seer")
            if seer and self.is_bot(seer) and self.alive(seer):
                for s in self.st.get("seen") or []:
                    if s["id"] in weight:
                        if s["role"] == "wolf":
                            weight[s["id"]] = 8.0 if b == seer else 3.0
                        elif b == seer:
                            weight[s["id"]] = 0.2
        return self.rng.choices(others, [weight[p] for p in others])[0]

    # ---------- the end
    def winner(self) -> str | None:
        live = self.living()
        wolves = [p for p in live if self.role(p) == "wolf"]
        lv = self.st.get("lovers") or []
        if len(lv) == 2 and len(live) == 2 and set(live) == set(lv) and len(wolves) == 1:
            return "lovers"
        if not wolves:
            return "village"
        if len(wolves) >= len(live) - len(wolves):
            return "wolves"
        return None

    def _finish(self, side: str | None) -> None:
        order = self.order()
        if side == "lovers":
            winners = list(self.st["lovers"])
        elif side == "village":
            winners = [p for p in order if self.role(p) != "wolf"]
        elif side == "wolves":
            winners = [p for p in order if self.role(p) == "wolf"]
        else:
            winners = []
        self.st.update(phase="done", winner=side, winners=winners, step=None, deadline=None, finished=self.now())

    # ---------- the leader
    def advance(self) -> None:
        """The leader moves on (somebody is idle): every phase has a default."""
        ph, step = self.st.get("phase"), self.st.get("step")
        if ph == "roles" or ph == "verdict":
            self._night()
        elif ph == "night":
            if step == "wolves":
                c: dict[str, int] = {}
                for w in self.wolves():
                    t = self.st["wolf_votes"].get(w)
                    if t and self.alive(t):
                        c[t] = c.get(t, 0) + 1
                top = max(c.values()) if c else 0
                best = [p for p, n in c.items() if n == top]
                self.st["victim"] = best[0] if top and len(best) == 1 else None
            self._next_step()
        elif ph == "hunter":
            self._hunter_done()
        elif ph == "day":
            self._open_vote()
        elif ph == "vote":
            self._close_vote()
        else:
            raise CommunityError("The game is not running")

    def end(self) -> None:
        if self.st.get("phase") not in ("lobby", "done"):
            self.st["ended"] = True
            self._finish(None)


# ================================================================ the games in the database (table card_game, kind "werwolf")
class Werwolf(CardGames):
    """The family table – the same rows and lobby as the card games (join, summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng: random.Random | None = None):
        super().__init__(db, add_history)
        self.rewards = rewards
        self.now = now
        self.rng = rng

    def table(self, st: dict) -> Table:
        return Table(st, self.rng, now=lambda: self.now())

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, self.db.get_setting(f"game_rules.{KIND}") or {})

    def clean_rules(self, kind: str, r: dict) -> dict:
        r = {**DEFAULTS, **(r or {})}
        try:
            wolves = int(r.get("wolves"))
        except (TypeError, ValueError):
            wolves = DEFAULTS["wolves"]
        try:
            talk = int(r.get("talk"))
        except (TypeError, ValueError):
            talk = DEFAULTS["talk"]
        try:
            fill = max(MIN_PLAYERS, min(MAX_PLAYERS, int(r.get("fill"))))
        except (TypeError, ValueError):
            fill = DEFAULTS["fill"]
        return {"auto": bool(r.get("auto")), "wolves": wolves if wolves in (1, 2, 3) else DEFAULTS["wolves"],
                **{s: bool(r.get(s)) for s in SPECIALS}, "talk": talk if talk in TALKS else DEFAULTS["talk"], "fill": fill}

    def rules_info(self) -> dict:
        """The remembered rules, the choices, the role sets per number of players and the coins (start dialog)."""
        return {**self.default_rules(), "rewards": rewards_of(self.db), "talks": list(TALKS), "min": MIN_PLAYERS,
                "max": MAX_PLAYERS, "min_humans": MIN_HUMANS, "presets": {str(n): preset(n) for n in range(MIN_PLAYERS, MAX_PLAYERS + 1)}}

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st, separators=(",", ":")), status, status, row["id"])
        if status != "done" or st.get("paid"):
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st, separators=(",", ":")), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", f"{TITLE} – Sieg", ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        if not st.get("winner"):
            return                                   # ended by the leader: no hat, no history
        self._champion(st, list(st.get("winners") or []))
        if self.add_history:
            t = self.table(st)
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "won": p["id"] in (st.get("winners") or []), "side": st["winner"], "role": t.role(p["id"]),
                        "players": len(st["players"]), "survived": t.alive(p["id"]), "nights": st.get("night", 0),
                        "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins of place 1 for every person of the family on the winning side – only with at least two people of the
        family at the table and only for a game played to the end."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if len(people) < 2 or st.get("phase") != "done" or not st.get("winner"):
            return {}
        amount = rewards_of(self.db)[0]
        if amount <= 0:
            return {}
        win = set(st.get("winners") or [])
        return {p["id"]: amount for p in people if p["id"] in win}

    # ---------- the table
    def start(self, kind: str, host: int, rules: dict | None = None, solo: bool = False, bots: list[dict] | None = None) -> int:
        if kind != KIND:
            raise CommunityError("Unknown game")
        if solo:
            raise CommunityError("This game needs at least two people")
        r = self.clean_rules(KIND, {**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
        with self.lock:
            if self._row(KIND):
                raise CommunityError("This game is already running")
            self.db.set_setting(f"game_rules.{KIND}", r)
            st = {"kind": KIND, "rules": r, "players": [self._person(host)], "phase": "lobby", "solo": False}
            return self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, 0, json.dumps(st))

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

    def set_rules(self, viewer: int, rules: dict) -> None:
        """Who leads changes the roles / the talk time in the lobby."""
        def go(st):
            st["rules"] = self.clean_rules(KIND, {**st["rules"], **{k: v for k, v in (rules or {}).items() if v is not None}})
            self.db.set_setting(f"game_rules.{KIND}", st["rules"])
        self._lobby(viewer, go)

    def seats(self, st: dict) -> int:
        """How many players the game will have: the people, filled up with bots to 5 (or to the rule `fill`)."""
        humans = sum(1 for p in st["players"] if not p.get("bot"))
        if self.bots_off(KIND, st["players"]):                          # parent area › Games: without bots – no filling up
            return humans
        return max(humans, min(MAX_PLAYERS, max(MIN_PLAYERS, int(st["rules"].get("fill") or MIN_PLAYERS))))

    def _bots(self, n: int) -> list[dict]:
        rng = self.rng or random
        return [{"id": f"bot{i + 1}", "name": name, "emoji": emoji, "bot": True}
                for i, (name, emoji) in enumerate(rng.sample(BOT_NAMES, len(BOT_NAMES))[:n])]

    def begin(self, kind: str, viewer: int) -> None:
        """Who leads begins: at least 2 people – bots fill the table up to 5 (or `fill`), the roles are dealt."""
        def go(st):
            humans = [p for p in st["players"] if not p.get("bot")]
            if len(humans) < MIN_HUMANS:
                raise CommunityError("At least 2 players are needed")
            if len(humans) < MIN_PLAYERS and self.bots_off(KIND, humans):
                raise CommunityError("Without bots Werwölfe needs at least 5 players")
            st["players"] = humans + self._bots(self.seats(st) - len(humans))
            self.table(st).begin()
        self._lobby(viewer, go)

    def _act(self, pid: int, fn):
        with self.lock:
            row = self._row(KIND, pid)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            if st["phase"] == "done":
                raise CommunityError("The game is over")
            t = self.table(st)
            t.tick()
            try:
                return fn(t)
            finally:
                self._save(row, st)

    def act(self, pid: int, action: str, target=None, target2=None, heal: bool = False, poison=None) -> None:
        self._act(pid, lambda t: t.act(str(pid), action, target, target2, heal, poison))

    def advance(self, pid: int) -> None:
        self._act(pid, lambda t: t.advance())

    def end(self, kind: str, viewer: int) -> None:
        """Who leads ends the game: every role is shown – no winner, no coins."""
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] not in ("lobby", "done"):
                self.table(st).end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def state(self, kind: str, viewer: int) -> dict | None:
        with self.lock:
            row = self._row(KIND, viewer)
            if row:
                st = json.loads(row["state"])
                if st["phase"] not in ("lobby", "done") and self.table(st).tick():
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
            else:
                row = self.db.q1("""SELECT * FROM card_game WHERE kind=? AND status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                    AND solo=0 ORDER BY id DESC LIMIT 1""", KIND)
                if not row:
                    return None
                st = json.loads(row["state"])
                if not any(p["id"] == str(viewer) for p in st["players"]):
                    return None
        return self._view(row, st, str(viewer))

    def _view(self, row, st: dict, me: str) -> dict:
        """What one player may know – nothing more: the own role, fellow wolves (for wolves), the lover (for the
        lovers and amor), the seer's results (for the seer), the victim and the potions (for the witch), the roles of
        the dead (everybody), everything for the dead (spectators) and at the end."""
        t = self.table(st)
        ph = st["phase"]
        if row["status"] == "done" and ph != "lobby":
            ph = "done"
        order = t.order()
        joined = me in order
        playing = ph not in ("lobby", "done")
        my_role = t.role(me) if joined and ph != "lobby" else None
        alive = joined and ph != "lobby" and t.alive(me)
        spectator = joined and playing and not alive
        everything = ph == "done" or spectator
        known: dict[str, str] = {}
        if ph != "lobby":
            for p in order:
                if everything or p == me or not t.alive(p) or (alive and my_role == "wolf" and t.role(p) == "wolf"):
                    known[p] = t.role(p)
            if my_role == "seer":
                for s in st.get("seen") or []:
                    known.setdefault(s["id"], s["role"])
        lovers = st.get("lovers") or []
        see_lovers = bool(lovers) and (everything or me in lovers or my_role == "amor")
        my_lover = t.lover_of(me) if joined and lovers else None
        actors = t.actors() if playing else []
        coins = st.get("coins") or {}
        step = st.get("step") if ph == "night" else None
        votes = st.get("votes") or {}

        def cause(c: str) -> str:
            return c if everything or c in ("love", "shot", "vote") else "night"

        def deaths(ds):
            return [{"id": d["id"], "role": d["role"], "cause": cause(d["cause"])} for d in ds or []]
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "guest": bool(p.get("guest")),
                    "bot": bool(p.get("bot")), "emoji": p.get("emoji"), "color": p.get("color"),
                    "alive": ph == "lobby" or t.alive(p["id"]), "role": known.get(p["id"]),
                    "lover": see_lovers and p["id"] in lovers, "coins": coins.get(p["id"], 0),
                    "won": ph == "done" and p["id"] in (st.get("winners") or [])} for p in st["players"]]
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        try:
            deck = deck_for(st["rules"], self.seats(st)) if ph == "lobby" else st.get("deck")
            deck_error = None
        except CommunityError as e:
            deck, deck_error = None, str(e)
        now = self.now()
        no_bots = ph == "lobby" and self.bots_off(KIND, st["players"])
        out = {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph, "step": step,
               "night": st.get("night", 0), "host": row["host_id"], "rules": st["rules"], "players": players,
               "joined": joined, "me": me if joined else None, "my_role": my_role, "alive": alive, "spectator": spectator,
               "my_lover": my_lover, "lovers": list(lovers) if see_lovers else None,
               "my_turn": me in actors, "deck": deck, "deck_error": deck_error, "min": MIN_PLAYERS, "max": MAX_PLAYERS,
               "min_humans": MIN_PLAYERS if no_bots else MIN_HUMANS, "no_bots": no_bots, "bots": self.seats(st) - len(order) if ph == "lobby" else None,
               "step_ms": int((now - (st.get("step_at") or now)) * 1000) if playing else None,
               "left_ms": None, "time_ms": None, "deaths": None, "hunter": st.get("hunter") if ph == "hunter" else None,
               "voted": None, "my_vote": None, "votes": None, "lynch": None, "wolf_votes": None, "victim": None,
               "potions": None, "seen": None, "looked": None, "log": [{"kind": e["kind"], "n": e["n"], "deaths": deaths(e["deaths"]),
                                                     "lynch": e.get("lynch")} for e in st.get("log") or []],
               "winner": st.get("winner") if ph == "done" else None, "ended": bool(st.get("ended")) if ph == "done" else False,
               "rewards": rewards_of(self.db), "coins_on": people >= 2}
        if ph in ("day", "hunter", "verdict"):
            out["deaths"] = deaths(st.get("deaths"))
        if ph == "day" and st.get("deadline"):
            out["left_ms"] = max(0, int((st["deadline"] - now) * 1000))
            out["time_ms"] = int((st["deadline"] - st["started_at"]) * 1000)
        if ph == "vote":
            out["voted"] = [p for p in order if p in votes]
            out["my_vote"] = votes.get(me) if joined else None
            if spectator:
                out["votes"] = dict(votes)
        if ph in ("verdict", "done") or (ph == "hunter" and st.get("after") == "verdict"):
            out["votes"], out["lynch"] = dict(votes), st.get("lynch")
        # the night: what only the active roles (and the dead) may know
        if ph == "night" and step == "wolves" and ((alive and my_role == "wolf") or spectator):
            out["wolf_votes"] = dict(st.get("wolf_votes") or {})
        if ph == "night" and ((step == "witch" and alive and my_role == "witch") or spectator):
            out["victim"] = st.get("victim")
        if my_role == "witch" or everything:
            out["potions"] = dict(st.get("potions") or {})
        if my_role == "seer" or everything:
            out["seen"] = list(st.get("seen") or [])
            out["looked"] = bool(st.get("looked")) if ph == "night" and step == "seer" else None
        return out

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
