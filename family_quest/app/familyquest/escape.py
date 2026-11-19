"""«Escape Room» – the live riddle game for the family: solve the riddles of a room together to find the door code,
then on to the next room until you are out. Everybody plays on their own device (family table, guests via QR code);
no bots. The tables live in the `card_game` table with kind "escape" (lobby, join, summary, may_lead from
cardgames.CardGames, like «Verbotene Wörter»).

Rules (chosen by who opens the table, remembered):
  rooms   1–5 rooms (each a scene of its own world: the wizard's tower, the pirate cabin, the space station …)
  level   easy / medium / hard / mixed (mixed: the rooms get harder one after the other)
  types   which kinds of riddles (escape_riddles.TYPES – logic, words, pictures, patterns, maths, memory, maps,
          mechanical puzzles, knowledge)
  mode    together (everybody in one team, one shared state) or teams (two teams, every team plays the same rooms
          with the same riddles on its own – the other team's progress shows as a bar only)
  time    a time limit: none / 15 / 30 / 45 minutes
A room: 2 riddles (easy) or 3 (medium, hard; mixed 2–3) hidden in its objects, plus a decoration with a tip. Every
solved riddle reveals a part of the door code (a digit with a symbol, a number, or a gem with its position); the exit
needs all parts together (the combined lock): the digits in the order of the symbols, the sum of the numbers, or the
gems in the order of their positions. Hints (up to 3 per riddle, shown to the whole team) cost HINT_S seconds each,
a wrong answer WRONG_S seconds – the team's time is the real time plus these.
The riddles are made fresh for every game (escape_riddles.make, the server's random numbers); the app never gets a
solution. Which templates were played is kept per family (setting `escape_played`: a counter per template): a new
game takes the templates played least (fresh ones first) – so all are played before one comes again. The round
(shown in the start dialog) = the lowest counter + 1.
The end: together – when the team is out (or the time is over, or who leads ends it); teams – the first team out wins
(with the hint and error time: the game ends as soon as the other team cannot be faster any more), or the time is
over (then nobody escaped and nobody wins).
Coins (setting `game_rewards["escape"]`, the amount of place 1): every person of the family in the team that escaped
and won – only at a table with at least two people of the family, never to guests; paid once (flag `paid`, a unique
ledger `ref`). History for everybody of the family, the «No. 1» hat for the winners.
"""
from __future__ import annotations

import json
import random
import secrets
import time

from . import escape_riddles as er
from .cardgames import CardGames
from .community import CommunityError
from .i18n import _t
from .pairhunt import rewards_of as _rewards_of
from .running import win_reason

KIND = "escape"
TITLE = "Escape Room"
EMOJI = "🗝️"
MAX_PLAYERS = 10
LEVELS = ("easy", "medium", "hard", "mixed")
MODES = ("together", "teams")
ROOMS = (1, 2, 3, 4, 5)
TIMES = (0, 15, 30, 45)
DEFAULTS = {"rooms": 3, "level": "mixed", "types": list(er.TYPES), "mode": "together", "time": 0}
HINT_S = 60                      # a hint costs this many seconds
WRONG_S = 10                     # a wrong answer
LOG_MAX = 12

# the worlds: name, emoji, the objects that hide riddles, the decoration with its tip
THEMES = {
    "wizard": (_t("The wizard's tower"), "🧙", [("🔮", _t("Crystal ball")), ("📚", _t("Bookshelf")), ("🧪", _t("Potion shelf")),
                                              ("🕯️", _t("Candlestick")), ("🦉", _t("Owl")), ("🧹", _t("Broom"))],
               ("🐈‍⬛", _t("A black cat purrs: «Every riddle hides a part of the door code.»"))),
    "pirate": (_t("The pirate cabin"), "🏴‍☠️", [("🗺️", _t("Sea chart")), ("🧭", _t("Compass")), ("🦜", _t("Parrot")),
                                             ("🛢️", _t("Barrel")), ("⚓", _t("Anchor")), ("💰", _t("Money bag"))],
               ("🐀", _t("A rat squeaks: «Arr! Look at everything, matey!»"))),
    "space": (_t("The space station"), "🚀", [("🖥️", _t("Control desk")), ("🛰️", _t("Satellite model")), ("🧑‍🚀", _t("Space suit")),
                                            ("🔭", _t("Telescope")), ("🪐", _t("Planet globe")), ("🤖", _t("Robot"))],
              ("👽", _t("A friendly alien blinks: «Beep! Solve all riddles, then the hatch opens.»"))),
    "treehouse": (_t("The treehouse"), "🌳", [("🪜", _t("Rope ladder")), ("🐿️", _t("Squirrel")), ("🍯", _t("Honey pot")),
                                             ("🪺", _t("Bird's nest")), ("🎒", _t("Backpack")), ("🔦", _t("Torch"))],
                  ("🐞", _t("A ladybird whispers: «The door code is hidden in the riddles.»"))),
    "clock": (_t("The clock workshop"), "⏰", [("🕰️", _t("Mantel clock")), ("⚙️", _t("Gearbox")), ("⏳", _t("Hourglass")),
                                             ("🔔", _t("Bell")), ("🧰", _t("Toolbox")), ("📻", _t("Old radio"))],
              ("🐭", _t("A mouse ticks along: «Tick, tock – every riddle gives a part of the code!»"))),
    "ice": (_t("The ice castle"), "❄️", [("⛄", _t("Snowman")), ("🧊", _t("Ice block")), ("🦭", _t("Seal")),
                                        ("👑", _t("Ice crown")), ("🪞", _t("Frozen mirror")), ("🎿", _t("Skis"))],
            ("🐧", _t("A penguin waddles by: «Brrr! Find all the parts of the code!»"))),
    "jungle": (_t("The jungle temple"), "🗿", [("🗿", _t("Stone head")), ("🐍", _t("Snake")), ("🌺", _t("Giant flower")),
                                             ("🏺", _t("Old vase")), ("🐒", _t("Monkey")), ("🥥", _t("Coconut"))],
               ("🦎", _t("A lizard nods: «Every riddle hides a part of the door code!»"))),
    "dragon": (_t("The dragon's cave"), "🐉", [("🐉", _t("Sleeping dragon")), ("💎", _t("Pile of gems")), ("🦇", _t("Bat")),
                                              ("🔥", _t("Fire bowl")), ("🥚", _t("Dragon egg")), ("📜", _t("Old scroll"))],
               ("🐌", _t("A snail says slowly: «Take your time … but not too much!»"))),
}
FRAG_SYM = ["⭐", "🌙", "☀️"]
FRAG_COL = ["red", "yellow", "blue", "green"]


def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


def room_levels(level: str, rooms: int) -> list[str]:
    """The level of every room – mixed: from easy to hard."""
    if level != "mixed":
        return [level] * rooms
    if rooms == 1:
        return ["medium"]
    return [er.LEVELS[min(2, round(i * 2 / (rooms - 1)))] for i in range(rooms)]


def pick_templates(levels: list[str], types: list[str], counts: dict, rng) -> list[str]:
    """One template per wanted level: of the chosen types, a template that has this level (none: the nearest level),
    the least played first (fresh ones before played ones), never twice in a game while others are left."""
    chosen: list[str] = []
    for lv in levels:
        pool = [t for t, x in er.TEMPLATES.items() if x[0] in types and lv in x[1]]
        if not pool:
            pool = [t for t, x in er.TEMPLATES.items() if x[0] in types]
            best = min(abs(er.LEVELS.index(er.nearest_level(t, lv)) - er.LEVELS.index(lv)) for t in pool)
            pool = [t for t in pool if abs(er.LEVELS.index(er.nearest_level(t, lv)) - er.LEVELS.index(lv)) == best]
        fresh = [t for t in pool if t not in chosen] or pool
        key = {t: (int(counts.get(t, 0)) + chosen.count(t), rng.random()) for t in fresh}
        chosen.append(min(fresh, key=key.get))
    return chosen


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random(secrets.randbits(64))
        self.now = now

    @property
    def r(self) -> dict:
        return self.st["rules"]

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    def team_of(self, pid: str) -> str | None:
        return (self.st.get("team_of") or {}).get(pid)

    def teams(self) -> list[str]:
        return sorted(set((self.st.get("team_of") or {}).values()))

    def elapsed(self) -> float:
        end = self.st.get("end_at")
        t = (end if end is not None else self.now()) - self.st["t0"]
        lim = self.st.get("deadline")
        if lim is not None:
            t = min(t, lim - self.st["t0"])
        return max(0.0, t)

    def eff(self, team: str) -> float:
        """The team's time: real time (until it was out) plus the hint and error seconds."""
        p = self.st["prog"][team]
        base = p["done_t"] if p["done_t"] is not None else self.elapsed()
        return base + p["pen"]

    # ---------- the start
    def begin(self, counts: dict | None = None, seats: list[str] | None = None) -> list[str]:
        """Make the rooms and riddles; returns the templates used (for the counter of played riddles)."""
        order = self.order()
        teams = self.r.get("mode") == "teams" and len(order) >= 2
        if teams:
            seats = [p for p in (seats or []) if p in order] + [p for p in order if p not in (seats or [])]
            team_of = {p: str(seats.index(p) % 2) for p in order}
        else:
            team_of = {p: "0" for p in order}
        rng = self.rng
        n_rooms = int(self.r.get("rooms") or 3)
        lv_rooms = room_levels(self.r.get("level") or "mixed", n_rooms)
        per = [2 if lv == "easy" else 3 if self.r.get("level") != "mixed" or lv == "hard" else rng.choice([2, 3]) for lv in lv_rooms]
        levels = [lv for lv, k in zip(lv_rooms, per) for _ in range(k)]
        types = [t for t in (self.r.get("types") or []) if t in er.TYPES] or list(er.TYPES)
        tids = pick_templates(levels, types, counts or {}, rng)
        themes = list(THEMES)
        rng.shuffle(themes)
        rooms, k = [], 0
        for i in range(n_rooms):
            th = themes[i % len(themes)]
            objs = list(range(len(THEMES[th][2])))
            rng.shuffle(objs)
            riddles = []
            for j in range(per[i]):
                rd = er.make(tids[k], rng, levels[k])
                rd["obj"] = objs[j]
                riddles.append(rd)
                k += 1
            rooms.append({"theme": th, "level": lv_rooms[i], "riddles": riddles, "door": self._door(len(riddles), lv_rooms[i]),
                          "spots": rng.sample(range(5), len(riddles) + 1)})
        now = self.now()
        lim = int(self.r.get("time") or 0)
        prog = {tm: {"room": 0, "solved": {}, "hints": {}, "wrong": {}, "peek": {}, "pen": 0, "done_t": None, "log": []}
                for tm in sorted(set(team_of.values()))}
        self.st.update(phase="play", team_of=team_of, teams=teams, rooms=rooms, prog=prog, t0=now,
                       deadline=now + lim * 60 if lim else None, end_at=None, places=None, result=None)
        return tids

    def _door(self, k: int, level: str) -> dict:
        """The combined lock of a room: the parts the riddles reveal and the code they make together."""
        rng = self.rng
        kind = rng.choice(["order", "sum"] if level == "easy" else ["order", "sum", "colours"])
        if kind == "order":
            frags = [{"sym": FRAG_SYM[i], "d": rng.randrange(10)} for i in range(k)]
            order = list(range(k))
            rng.shuffle(order)
            return {"kind": kind, "frags": frags, "order": [FRAG_SYM[i] for i in order],
                    "sol": "".join(str(frags[i]["d"]) for i in order)}
        if kind == "sum":
            frags = [{"n": rng.randint(1, 9 if level == "easy" else 25)} for _ in range(k)]
            return {"kind": kind, "frags": frags, "sol": str(sum(f["n"] for f in frags))}
        cols = rng.sample(range(len(FRAG_COL)), k)
        pos = list(range(1, k + 1))
        rng.shuffle(pos)
        frags = [{"c": c, "pos": p} for c, p in zip(cols, pos)]
        return {"kind": kind, "frags": frags, "sol": [f["c"] for f in sorted(frags, key=lambda f: f["pos"])]}

    # ---------- acting
    def _team(self, pid: str) -> tuple[str, dict]:
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        if pid not in self.order():
            raise CommunityError("You are not at this table")
        tm = self.team_of(pid)
        p = self.st["prog"][tm]
        if p["done_t"] is not None:
            raise CommunityError("Your team is already out")
        return tm, p

    def _riddle(self, p: dict, key: str) -> tuple[int, dict]:
        try:
            room, i = (int(x) for x in str(key).split("."))
        except (TypeError, ValueError):
            raise CommunityError("Unknown riddle") from None
        if room != p["room"]:
            raise CommunityError("This riddle is in another room")
        rd = self.st["rooms"][room]["riddles"]
        if not 0 <= i < len(rd):
            raise CommunityError("Unknown riddle")
        return room, rd[i]

    def _log(self, p: dict, pid: str, what: str, key: str | None = None) -> None:
        p["log"].append({"who": pid, "what": what, "key": key, "t": round(self.elapsed())})
        del p["log"][:-LOG_MAX]

    def answer(self, pid: str, key: str, answer) -> bool:
        tm, p = self._team(pid)
        room, rd = self._riddle(p, key)
        if key in p["solved"]:
            return True
        if er.check(rd, answer):
            p["solved"][key] = {"by": pid, "t": round(self.elapsed())}
            self._log(p, pid, "solved", key)
            return True
        p["wrong"][key] = p["wrong"].get(key, 0) + 1
        p["pen"] += WRONG_S
        return False

    def hint(self, pid: str, key: str) -> None:
        tm, p = self._team(pid)
        room, rd = self._riddle(p, key)
        if key in p["solved"]:
            raise CommunityError("This riddle is solved already")
        n = p["hints"].get(key, 0)
        if n >= len(rd["hints"]):
            raise CommunityError("There are no more hints")
        p["hints"][key] = n + 1
        p["pen"] += HINT_S
        self._log(p, pid, "hint", key)

    def peek(self, pid: str, key: str) -> None:
        tm, p = self._team(pid)
        room, rd = self._riddle(p, key)
        if not rd.get("peek"):
            raise CommunityError("Nothing to look at")
        p["peek"][key] = self.now() + int(rd["peek"])

    def door(self, pid: str, answer) -> bool:
        tm, p = self._team(pid)
        room = p["room"]
        d = self.st["rooms"][room]["door"]
        ok = er.check({"check": {"order": "digits", "sum": "int", "colours": "seq"}[d["kind"]], "sol": d["sol"], "input": {}}, answer)
        if not ok:
            p["wrong"][f"{room}.d"] = p["wrong"].get(f"{room}.d", 0) + 1
            p["pen"] += WRONG_S
            return False
        p["solved"][f"{room}.d"] = {"by": pid, "t": round(self.elapsed())}
        p["room"] = room + 1
        p["peek"] = {}
        if p["room"] >= len(self.st["rooms"]):
            p["done_t"] = round(self.elapsed(), 1)
            self._log(p, pid, "out")
        else:
            self._log(p, pid, "door", f"{room}.d")
        self.maybe_end()
        return True

    # ---------- the end
    def tick(self) -> bool:
        if self.st.get("phase") != "play":
            return False
        self.maybe_end()
        return self.st.get("phase") != "play"

    def maybe_end(self) -> None:
        if self.st.get("phase") != "play":
            return
        prog = self.st["prog"]
        out = [tm for tm, p in prog.items() if p["done_t"] is not None]
        lim = self.st.get("deadline")
        if lim is not None and self.now() >= lim:
            return self._finish(True)
        if not out:
            return
        if len(out) == len(prog):
            return self._finish(True)
        best = min(self.eff(tm) for tm in out)
        if all(self.eff(tm) >= best for tm in prog if tm not in out):      # nobody can be faster any more
            self._finish(True)

    def solved_count(self, tm: str) -> int:
        return sum(1 for k in self.st["prog"][tm]["solved"] if not k.endswith(".d"))

    def score(self, tm: str) -> int:
        p = self.st["prog"][tm]
        s = 100 * self.solved_count(tm) + 250 * min(p["room"], len(self.st["rooms"]))
        if p["done_t"] is not None:
            s += max(0, 1200 - int(self.eff(tm)) // 3)
        return s

    def _finish(self, complete: bool) -> None:
        self.st["end_at"] = self.now()
        prog = self.st["prog"]
        res = {}
        for tm, p in prog.items():
            res[tm] = {"out": p["done_t"] is not None, "time": round(self.eff(tm)), "real": round(p["done_t"] if p["done_t"] is not None else self.elapsed()),
                       "rooms": min(p["room"], len(self.st["rooms"])), "riddles": self.solved_count(tm),
                       "hints": sum(p["hints"].values()), "wrong": sum(p["wrong"].values()), "score": self.score(tm)}
        key = {tm: ((0, res[tm]["time"]) if res[tm]["out"] else (1, -res[tm]["rooms"], -res[tm]["riddles"], res[tm]["time"])) for tm in res}
        for tm in res:
            res[tm]["place"] = 1 + sum(1 for o in res if key[o] < key[tm])
        winners = [tm for tm in res if res[tm]["place"] == 1 and res[tm]["out"]]
        self.st["result"] = res
        self.st["winners"] = winners
        self.st["places"] = {p: res[self.team_of(p)]["place"] for p in self.order()}
        self.st.update(phase="done", complete=complete, finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: as it stands (nobody escaped in the meantime: no winner)."""
        if self.st.get("phase") == "play":
            self._finish(False)


# ================================================================ the games in the database (table card_game, kind "escape")
class Escape(CardGames):
    """The family table – the same rows and lobby as the card games (join, summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng: random.Random | None = None):
        super().__init__(db, add_history)
        self.rewards = rewards
        self.now = now
        self.rng = rng

    def table(self, st: dict) -> Table:
        return Table(st, self.rng, now=lambda: self.now())

    # ---------- the rules and the played riddles
    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, self.db.get_setting(f"game_rules.{KIND}") or {})

    def clean_rules(self, kind: str, r: dict) -> dict:
        r = {**DEFAULTS, **(r or {})}

        def num(k, allowed):
            try:
                v = int(r.get(k))
            except (TypeError, ValueError):
                return DEFAULTS[k]
            return v if v in allowed else DEFAULTS[k]
        types = r.get("types")
        types = [t for t in er.TYPES if isinstance(types, list) and t in types] or list(er.TYPES)
        lv, mode = str(r.get("level") or ""), str(r.get("mode") or "")
        return {"rooms": num("rooms", ROOMS), "level": lv if lv in LEVELS else DEFAULTS["level"], "types": types,
                "mode": mode if mode in MODES else DEFAULTS["mode"], "time": num("time", TIMES)}

    def counts(self) -> dict:
        c = (self.db.get_setting("escape_played") or {}).get("counts") or {}
        return {t: int(c.get(t, 0) or 0) for t in er.TEMPLATES}

    def played_info(self) -> dict:
        """How many riddles are new (not played in this round) – in total and per type; the round."""
        c = self.counts()
        low = min(c.values())
        types = {}
        for t, x in er.TEMPLATES.items():
            d = types.setdefault(x[0], {"total": 0, "new": 0})
            d["total"] += 1
            d["new"] += c[t] == low
        return {"total": len(c), "new": sum(1 for v in c.values() if v == low), "round": low + 1, "types": types,
                "levels": {lv: [t for t, x in er.TEMPLATES.items() if lv in x[1]] for lv in er.LEVELS}}

    def _mark_played(self, tids: list[str]) -> None:
        c = self.counts()
        for t in set(tids):
            c[t] = c.get(t, 0) + 1
        self.db.set_setting("escape_played", {"counts": c})

    def rules_info(self) -> dict:
        return {**self.default_rules(), "rewards": rewards_of(self.db), "levels": list(LEVELS), "times": list(TIMES),
                "rooms_choice": list(ROOMS), "modes": list(MODES), "types_all": list(er.TYPES),
                "type_names": er.TYPE_NAMES, "type_icons": er.TYPE_ICONS, "played": self.played_info(),
                "riddles": [{"id": t, "type": x[0], "levels": list(x[1]), "name": x[2]} for t, x in er.TEMPLATES.items()],
                "max_players": MAX_PLAYERS, "hint_s": HINT_S, "wrong_s": WRONG_S}

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    # ---------- the end: coins once, history, the hat
    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st, separators=(",", ":"), ensure_ascii=False), status, status, row["id"])
        if status != "done" or st.get("paid") or st.get("result") is None:
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st, separators=(",", ":"), ensure_ascii=False), row["id"])
        self._payout(KIND, row["id"], coins, lambda pid: win_reason(KIND, 1))
        winners = [p for p in (st.get("team_of") or {}) if (st.get("team_of") or {}).get(p) in (st.get("winners") or [])]
        if len(st["players"]) >= 2:
            self._champion(st, winners)
        if self.add_history:
            res = st.get("result") or {}
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                tm = (st.get("team_of") or {}).get(p["id"])
                r = res.get(tm) or {}
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "out": bool(r.get("out")), "won": p["id"] in winners, "teams": bool(st.get("teams")),
                        "rooms": r.get("rooms", 0), "of": len(st.get("rooms") or []), "time": r.get("time", 0),
                        "hints": r.get("hints", 0), "score": r.get("score", 0), "players": len(st["players"]),
                        "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins of place 1 for every person of the family in the team that escaped and won – only with at least two
        people of the family at the table."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if len(people) < 2 or st.get("phase") != "done" or not st.get("winners"):
            return {}
        amount = rewards_of(self.db)[0]
        if amount <= 0:
            return {}
        team_of = st.get("team_of") or {}
        return {p["id"]: amount for p in people if team_of.get(p["id"]) in st["winners"]}

    # ---------- the table
    def start(self, kind: str, host: int, rules: dict | None = None, solo: bool = False, bots=None) -> int:
        if kind != KIND:
            raise CommunityError("Unknown game")
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
            fn(st, row)
            self._save(row, st)

    def begin(self, kind: str, viewer: int, starter=None) -> None:
        def go(st, row):
            if st["rules"].get("mode") == "teams" and len(st["players"]) < 2:
                raise CommunityError("Two teams need at least two players")
            seats = [p["id"] for p in st["players"]]
            used = self.table(st).begin(self.counts(), seats)
            self._mark_played(used)
        self._lobby(viewer, go)

    def mix(self, viewer: int) -> None:
        """Who leads mixes the seats in the lobby (the teams: every second seat)."""
        self._lobby(viewer, lambda st, row: (self.rng or random).shuffle(st["players"]))

    def _act(self, pid: int, fn):
        with self.lock:
            row = self._row(KIND, pid)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] == "lobby":
                raise CommunityError("The game has not started yet")
            t = self.table(st)
            t.tick()
            if st["phase"] != "play":
                self._save(row, st)
                raise CommunityError("The game is over")
            try:
                return fn(t)
            finally:
                self._save(row, st)

    def answer(self, pid: int, key: str, answer) -> bool:
        return self._act(pid, lambda t: t.answer(str(pid), key, answer))

    def door(self, pid: int, answer) -> bool:
        return self._act(pid, lambda t: t.door(str(pid), answer))

    def hint(self, pid: int, key: str) -> None:
        self._act(pid, lambda t: t.hint(str(pid), key))

    def peek(self, pid: int, key: str) -> None:
        self._act(pid, lambda t: t.peek(str(pid), key))

    def end(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] == "play":
                t = self.table(st)
                t.tick()
                t.end()
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
                                    AND solo=0 ORDER BY id DESC LIMIT 1""", KIND)
                if not row:
                    return None
                st = json.loads(row["state"])
                if not any(p["id"] == str(viewer) for p in st["players"]):
                    return None
        return self._view(row, st, str(viewer))

    # ---------- what one player sees (never a solution)
    def _view(self, row, st: dict, me: str) -> dict:
        ph = st["phase"]
        if row["status"] == "done" and ph != "lobby":
            ph = "done"
        joined = any(p["id"] == me for p in st["players"])
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        lobby_teams = ph == "lobby" and st["rules"].get("mode") == "teams" and len(st["players"]) >= 2
        team_of = {p["id"]: str(i % 2) for i, p in enumerate(st["players"])} if lobby_teams else (st.get("team_of") or {})
        teams = lobby_teams or bool(st.get("teams"))
        coins = st.get("coins") or {}
        players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "guest": bool(p.get("guest")),
                    "team": team_of.get(p["id"]) if teams else None, "coins": coins.get(p["id"], 0),
                    "place": (st.get("places") or {}).get(p["id"])} for p in st["players"]]
        out = {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph, "solo": False,
               "host": row["host_id"], "rules": st["rules"], "players": players, "joined": joined, "teams": teams,
               "rewards": rewards_of(self.db), "coins_on": people >= 2, "hint_s": HINT_S, "wrong_s": WRONG_S,
               "my_team": team_of.get(me) if teams else ("0" if joined else None), "now": self.now()}
        if ph == "lobby":
            return out
        t = self.table(st)
        mine = (st.get("team_of") or {}).get(me)
        out.update(elapsed=round(t.elapsed(), 1), limit=int(st["rules"].get("time") or 0) * 60 or None,
                   n_rooms=len(st["rooms"]), progress={tm: self._progress(t, tm) for tm in st["prog"]})
        if ph == "done":
            out.update(result=st.get("result"), winners=st.get("winners") or [], complete=bool(st.get("complete")))
        if mine is not None:
            out["room"] = self._room_view(t, mine)
        return out

    def _progress(self, t: Table, tm: str) -> dict:
        p = t.st["prog"][tm]
        total = sum(len(r["riddles"]) + 1 for r in t.st["rooms"])
        return {"room": min(p["room"], len(t.st["rooms"])), "done": len(p["solved"]), "total": total, "out": p["done_t"] is not None,
                "time": round(t.eff(tm)), "pen": p["pen"], "hints": sum(p["hints"].values())}

    def _room_view(self, t: Table, tm: str) -> dict:
        st, p = t.st, t.st["prog"][tm]
        ri = min(p["room"], len(st["rooms"]) - 1)
        room = st["rooms"][ri]
        name, emoji, objects, decor = THEMES[room["theme"]]
        now = self.now()
        riddles = []
        for i, rd in enumerate(room["riddles"]):
            key = f"{ri}.{i}"
            solved = p["solved"].get(key)
            showing = (p["peek"].get(key) or 0) > now
            view = er.public(rd, showing)
            view.update(key=key, obj=objects[rd["obj"]][0], obj_name=objects[rd["obj"]][1], spot=room["spots"][i],
                        solved=solved, hints=rd["hints"][:p["hints"].get(key, 0)], n_hints=len(rd["hints"]),
                        wrong=p["wrong"].get(key, 0), frag=room["door"]["frags"][i] if solved else None,
                        show_ms=max(0, int(((p["peek"].get(key) or 0) - now) * 1000)) if showing else 0)
            riddles.append(view)
        d = room["door"]
        door = {"kind": d["kind"], "n": len(d["frags"]), "order": d.get("order"), "colours": [er.col(c) for c in FRAG_COL] if d["kind"] == "colours" else None,
                "wrong": p["wrong"].get(f"{ri}.d", 0), "open": f"{ri}.d" in p["solved"]}
        log = [{"who": e["who"], "what": e["what"], "t": e["t"],
                "obj": objects[room["riddles"][int(e["key"].split(".")[1])]["obj"]][0] if e.get("key") and not e["key"].endswith(".d") and int(e["key"].split(".")[0]) == ri else None}
               for e in p["log"][-5:]]
        return {"index": ri, "theme": room["theme"], "name": name, "emoji": emoji, "level": room["level"], "riddles": riddles,
                "door": door, "decor": {"emoji": decor[0], "text": decor[1], "spot": room["spots"][-1]}, "log": log,
                "out": p["done_t"] is not None}

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
