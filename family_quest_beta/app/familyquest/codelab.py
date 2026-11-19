"""💡 Code Workshop: children program with blocks on the phone – stage 1 (web/codelab.js: editor and engine).

A program is a JSON tree (`clean_program`): a stage with backdrops and up to MAX_SPRITES sprites, each with costumes
and scripts. A script is a hat block (an event: ▶ clicked, sprite tapped, arrow pressed, message received) whose
`body` is the list of blocks it runs; C blocks (repeat, forever, if, if-else) have a `body` (and an `else`), slots
(`args`) hold a number / text – or a reporter block (random, comparisons, and / or / not, touching?). The server never
runs a free program; it checks it: only known blocks (OPS), every slot of its type, at most MAX_BLOCKS blocks,
MAX_DEPTH nested levels and MAX_BYTES of JSON – own drawings (svgpaint.js) are cleaned like the pictures of the
books (svgsafe.py).

Two modes:
- 🧩 Puzzles (codelab_levels.json): 15 levels in 3 worlds on a grid – bring the fox to the star with only the blocks
  of the level (`palette`, a block limit `max`). The app runs them; «solved» is checked here again: `simulate` runs
  the program (and the taps / arrows the player gave, `inputs`) on the grid with the same rules as the app (one script
  after the other, a move goes cell by cell: a stone or the edge ends the try, the star wins, more than MAX_STEPS blocks
  is a loop that runs for ever). ⭐⭐⭐ by the number of blocks (`stars`: the most blocks for 3 and 2 stars). The best
  result per child is kept; the first solve of a level pays XP / coins once (`Rewards.book_once`, parent setting).
- 🎨 Own programs: autosaved, with the visibility of the books (stories.py `can_see`): 🔒 only me (parents neither –
  in the parent area they only see that it exists), 🧒 the other children, 👨‍👩‍👧 the whole family (default).
  Who may see a program can play it and make a «Remix»: an own copy.

Time in the workshop is learning time (timelimits «learn»): the app sends a heartbeat (`tick`) while it is open; the
minutes count to the daily learning limit, and with the limit used up the workshop does not open (saving still works).
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from .community import CommunityError
from .stories import BACKGROUNDS, VISIBILITY, _int, _text, can_see

MAX_PROJECTS = 300               # programs of the family
MAX_PER_AUTHOR = 60
MAX_SPRITES = 12
MAX_COSTUMES = 8
MAX_BACKDROPS = 10
MAX_SCRIPTS = 40                 # scripts of one sprite
MAX_BLOCKS = 800                 # blocks of the whole program (reporters included)
MAX_DEPTH = 12                   # nested levels of C blocks
MAX_REPORTER = 6                 # … and of reporters in slots below that
MAX_BYTES = 700_000              # JSON of one program (own drawings included)
TITLE = 60
NAME = 20
TEXT = 120
MSG = 30
NUM = 1_000_000
MAX_STEPS = 1000                 # puzzles: blocks run before «this loop runs for ever»
MAX_INPUTS = 300                 # puzzles: taps / arrows replayed
TICK_MAX = 45                    # learning time: seconds booked per heartbeat at most
DEFAULT = {"off": [], "level_xp": 10, "level_coins": 0}

# room backgrounds of the adventure games (web/img/adventure/<key>.svg) – also stage backdrops here
ROOMS = ("tower", "library", "hall", "hallway", "cabin", "corridor", "bridge", "engine", "storage", "dark")
BACKDROPS = tuple(BACKGROUNDS) + ROOMS

# own sprites (web/img/codelab/<key>-<n>.svg): key → (costumes, rotation style)
SPRITES = {"fox": (3, "lr"), "cat": (3, "lr"), "dog": (2, "lr"), "robot": (3, "lr"), "ball": (2, "all"), "star": (2, "all"),
           "rocket": (3, "all"), "fish": (2, "lr"), "dragon": (3, "lr"), "apple": (2, "none"), "ghost": (2, "lr"),
           "bird": (3, "lr"), "car": (2, "lr"), "frog": (2, "lr"), "bee": (2, "lr"), "stone": (2, "none")}
ROT = ("all", "lr", "none")
KEYS = ("left", "right", "up", "down")

# ---------------------------------------------------------------- the blocks
# op: (kind, {slot: type}, body, else) – kinds: hat (starts a script), cmd, bool / num (reporters in slots)
# slot types: num (a number or a number reporter), bool (a boolean reporter or empty), text, key, msg, costume /
# backdrop (1-based number), target (a sprite id or "_random"), touch (a sprite id or "_edge")
OPS: dict[str, tuple[str, dict[str, str], bool, bool]] = {
    "ev_start": ("hat", {}, True, False),
    "ev_tap": ("hat", {}, True, False),
    "ev_key": ("hat", {"key": "key"}, True, False),
    "ev_msg": ("hat", {"msg": "msg"}, True, False),
    "broadcast": ("cmd", {"msg": "msg"}, False, False),
    "move": ("cmd", {"n": "num"}, False, False),
    "turn_r": ("cmd", {"deg": "num"}, False, False),
    "turn_l": ("cmd", {"deg": "num"}, False, False),
    "goto_xy": ("cmd", {"x": "num", "y": "num"}, False, False),
    "goto": ("cmd", {"to": "target"}, False, False),
    "glide": ("cmd", {"secs": "num", "x": "num", "y": "num"}, False, False),
    "point": ("cmd", {"dir": "num"}, False, False),
    "change_x": ("cmd", {"n": "num"}, False, False),
    "change_y": ("cmd", {"n": "num"}, False, False),
    "bounce": ("cmd", {}, False, False),
    "say": ("cmd", {"text": "text", "secs": "num"}, False, False),
    "think": ("cmd", {"text": "text", "secs": "num"}, False, False),
    "costume": ("cmd", {"c": "costume"}, False, False),
    "next_costume": ("cmd", {}, False, False),
    "backdrop": ("cmd", {"b": "backdrop"}, False, False),
    "size_add": ("cmd", {"n": "num"}, False, False),
    "size_set": ("cmd", {"n": "num"}, False, False),
    "show": ("cmd", {}, False, False),
    "hide": ("cmd", {}, False, False),
    "repeat": ("cmd", {"n": "num"}, True, False),
    "forever": ("cmd", {}, True, False),
    "if": ("cmd", {"cond": "bool"}, True, False),
    "if_else": ("cmd", {"cond": "bool"}, True, True),
    "wait": ("cmd", {"secs": "num"}, False, False),
    "wait_until": ("cmd", {"cond": "bool"}, False, False),
    "stop": ("cmd", {}, False, False),
    "touching": ("bool", {"what": "touch"}, False, False),
    "blocked": ("bool", {}, False, False),          # puzzles only: a stone or the edge in front of the fox
    "random": ("num", {"a": "num", "b": "num"}, False, False),
    "eq": ("bool", {"a": "num", "b": "num"}, False, False),
    "lt": ("bool", {"a": "num", "b": "num"}, False, False),
    "gt": ("bool", {"a": "num", "b": "num"}, False, False),
    "and": ("bool", {"a": "bool", "b": "bool"}, False, False),
    "or": ("bool", {"a": "bool", "b": "bool"}, False, False),
    "not": ("bool", {"a": "bool"}, False, False),
}
PUZZLE_ONLY = {"blocked"}
FREE_OPS = frozenset(OPS) - PUZZLE_ONLY
HATS = {k for k, v in OPS.items() if v[0] == "hat"}
LOOP_END = {"forever"}                              # nothing runs after it


def _num(v, lo: float = -NUM, hi: float = NUM, default: float = 0) -> float | int:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    f = max(lo, min(hi, f))
    return int(f) if f == int(f) else round(f, 3)


class _Ctx:
    def __init__(self, ops: frozenset | set, sprites: set[str]):
        self.ops, self.sprites, self.blocks, self.ids = ops, sprites, 0, set()


def _block_id(v, ctx: _Ctx) -> str:
    s = str(v or "")
    if not (1 <= len(s) <= 12 and s.isalnum() and s.isascii()) or s in ctx.ids:
        s = "b%d" % (len(ctx.ids) + 1)
        while s in ctx.ids:
            s += "x"
    ctx.ids.add(s)
    return s


def _op(b, ctx: _Ctx, kinds: tuple[str, ...]) -> str:
    if not isinstance(b, dict):
        raise CommunityError("The program contains something that is not a block")
    op = b.get("op")
    if op not in OPS or op not in ctx.ops:
        raise CommunityError("The program uses a block that is not allowed here")
    if OPS[op][0] not in kinds:
        raise CommunityError("A block is in a place where it does not fit")
    ctx.blocks += 1
    if ctx.blocks > MAX_BLOCKS:
        raise CommunityError("The program is too big – at most 800 blocks")
    return op


def _slot(kind: str, v, ctx: _Ctx, depth: int):
    """One slot value of its type – a number reporter in number slots, a boolean reporter in condition slots."""
    if depth > MAX_DEPTH + MAX_REPORTER:
        raise CommunityError("The program is nested too deeply")
    if isinstance(v, dict):
        if kind == "num":
            return _reporter(v, ctx, depth, ("num",))
        if kind == "bool":
            return _reporter(v, ctx, depth, ("bool",))
        v = None
    if kind == "num":
        return _num(v)
    if kind == "bool":
        return None                                     # an empty condition is false
    if kind == "text":
        return str(v if v is not None else "").replace("\x00", "")[:TEXT]
    if kind == "msg":
        return _text(v, MSG) or "1"
    if kind == "key":
        return v if v in KEYS else "right"
    if kind in ("costume", "backdrop"):
        return int(_num(v, 1, 99, 1))
    if kind == "target":
        return v if v == "_random" or v in ctx.sprites else "_random"
    if kind == "touch":
        return v if v == "_edge" or v in ctx.sprites else "_edge"
    return None


def _reporter(b, ctx: _Ctx, depth: int, kinds: tuple[str, ...]) -> dict:
    op = _op(b, ctx, kinds)
    args = b.get("args") if isinstance(b.get("args"), dict) else {}
    return {"op": op, "args": {k: _slot(t, args.get(k), ctx, depth + 1) for k, t in OPS[op][1].items()}}


def _blocks(lst, ctx: _Ctx, depth: int) -> list[dict]:
    if lst is None:
        return []
    if not isinstance(lst, list):
        raise CommunityError("The program contains something that is not a block")
    if depth > MAX_DEPTH:
        raise CommunityError("The program is nested too deeply")
    return [_block(b, ctx, depth, ("cmd",)) for b in lst]


def _block(b, ctx: _Ctx, depth: int, kinds: tuple[str, ...]) -> dict:
    op = _op(b, ctx, kinds)
    kind, slots, body, other = OPS[op]
    args = b.get("args") if isinstance(b.get("args"), dict) else {}
    out = {"id": _block_id(b.get("id"), ctx), "op": op, "args": {k: _slot(t, args.get(k), ctx, depth + 1) for k, t in slots.items()}}
    if b.get("off"):
        out["off"] = True
    if body:
        out["body"] = _blocks(b.get("body"), ctx, depth + 1)
    if other:
        out["else"] = _blocks(b.get("else"), ctx, depth + 1)
    return out


def clean_scripts(scripts, ops=FREE_OPS, sprites: set[str] | None = None, ctx: _Ctx | None = None) -> list[dict]:
    """The scripts of one sprite: hat blocks with their bodies – only the blocks of `ops`."""
    ctx = ctx or _Ctx(frozenset(ops), sprites or set())
    if not isinstance(scripts, list):
        scripts = []
    if len(scripts) > MAX_SCRIPTS:
        raise CommunityError("The program is too big – at most 800 blocks")
    out = []
    for s in scripts:
        hat = _block(s, ctx, 1, ("hat",))
        for k in ("x", "y"):                             # where the script is in the list (not used yet, kept)
            if isinstance(s, dict) and k in s:
                hat[k] = int(_num(s[k], 0, 9999))
        out.append(hat)
    return out


def _costume(c) -> dict | None:
    if not isinstance(c, dict):
        return None
    if c.get("k") == "lib":
        key, _, n = str(c.get("v") or "").rpartition("-")
        if key in SPRITES and n.isdigit() and 1 <= int(n) <= SPRITES[key][0]:
            return {"k": "lib", "v": f"{key}-{int(n)}"}
        return None
    if c.get("k") == "svg":
        from .svgsafe import ART_MAX, safe_svg
        svg = safe_svg(c.get("v"), ART_MAX)
        return {"k": "svg", "v": svg} if svg else None
    return None


def _backdrop(v):
    if isinstance(v, str):
        return v if v in BACKDROPS else None
    if isinstance(v, dict) and v.get("k") == "svg":
        from .svgsafe import BG_MAX, safe_svg
        svg = safe_svg(v.get("v"), BG_MAX)
        return {"k": "svg", "v": svg} if svg else None
    return None


def clean_program(data) -> dict:
    """A valid program: stage, sprites, costumes and scripts checked and limited. Unknown blocks, slots of the wrong
    type, too many blocks, too deep nesting or too much data are refused (CommunityError)."""
    if not isinstance(data, dict):
        data = {}
    try:
        raw_len = len(json.dumps(data, ensure_ascii=False))
    except (TypeError, ValueError):
        raise CommunityError("The program contains something that is not a block") from None
    if raw_len > MAX_BYTES * 2:
        raise CommunityError("The program is too big – remove a drawing or some blocks")
    stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
    bds = [b for b in (_backdrop(x) for x in (stage.get("backdrops") or [])[:MAX_BACKDROPS] if isinstance(stage.get("backdrops"), list)) if b]
    raw = data.get("sprites") if isinstance(data.get("sprites"), list) else []
    if len(raw) > MAX_SPRITES:
        raise CommunityError("A program can have at most 12 sprites")
    ids: list[str] = []
    for n, s in enumerate(raw):                          # sprite ids «s<n>», unique (scripts refer to them)
        sid = str(s.get("id") or "") if isinstance(s, dict) else ""
        if not (sid.startswith("s") and sid[1:].isdigit() and len(sid) <= 6) or sid in ids:
            sid = next(f"s{i}" for i in range(n + 1, n + 100) if f"s{i}" not in ids and f"s{i}" not in
                       [str(x.get("id")) for x in raw if isinstance(x, dict)])
        ids.append(sid)
    ctx = _Ctx(FREE_OPS, set(ids))
    sprites = []
    for sid, s in zip(ids, raw):
        if not isinstance(s, dict):
            continue
        costumes = [c for c in (_costume(x) for x in (s.get("costumes") or [])[:MAX_COSTUMES] if isinstance(s.get("costumes"), list)) if c]
        if not costumes:
            costumes = [{"k": "lib", "v": "ball-1"}]
        sprites.append({
            "id": sid, "name": _text(s.get("name"), NAME) or sid, "costumes": costumes,
            "c": int(_num(s.get("c"), 0, len(costumes) - 1)),
            "x": _num(s.get("x"), -240, 240), "y": _num(s.get("y"), -180, 180), "dir": _num(s.get("dir", 90), -180, 180, 90),
            "size": _num(s.get("size", 100), 5, 500, 100), "show": s.get("show", True) is not False,
            "rot": s.get("rot") if s.get("rot") in ROT else "all",
            "scripts": clean_scripts(s.get("scripts"), ctx=ctx)})
    out = {"v": 1, "stage": {"backdrops": bds, "bd": int(_num(stage.get("bd"), 0, max(0, len(bds) - 1)))}, "sprites": sprites}
    if len(json.dumps(out, ensure_ascii=False)) > MAX_BYTES:
        raise CommunityError("The program is too big – remove a drawing or some blocks")
    return out


def count_blocks(blocks: list[dict], hats: bool = False) -> int:
    """Blocks of a list (with what is inside C blocks; reporters in slots and hat blocks are not counted)."""
    n = 0
    for b in blocks or []:
        if OPS.get(b.get("op"), ("cmd",))[0] != "hat" or hats:
            n += 1
        n += count_blocks(b.get("body") or []) + count_blocks(b.get("else") or [])
    return n


def depth_of(blocks: list[dict]) -> int:
    return max((1 + max(depth_of(b.get("body") or []), depth_of(b.get("else") or [])) for b in blocks or []), default=0)


# ---------------------------------------------------------------- puzzles
_LEVELS: dict | None = None


def levels_doc() -> dict:
    global _LEVELS
    if _LEVELS is None:
        _LEVELS = json.loads((Path(__file__).parent / "codelab_levels.json").read_text(encoding="utf-8"))
    return _LEVELS


def levels() -> list[dict]:
    return levels_doc()["levels"]


def level(lid: str) -> dict:
    lv = next((x for x in levels() if x["id"] == lid), None)
    if not lv:
        raise CommunityError("Unknown level")
    return lv


def level_ops(lv: dict) -> frozenset:
    """The blocks a level allows: its palette, its hats and the reporters of its palette."""
    return frozenset(p["op"] for p in lv["palette"])


def expand(c) -> dict:
    """A compact block (levels file: solutions and start programs) as a block: [op, {args}, [body], [else]]."""
    op = c[0]
    args = c[1] if len(c) > 1 and isinstance(c[1], dict) else {}
    rest = [x for x in c[1:] if isinstance(x, list)]
    b = {"op": op, "args": {k: (expand(v) if isinstance(v, list) else v) for k, v in args.items()}}
    spec = OPS.get(op, ("", {}, bool(rest), len(rest) > 1))         # unknown blocks stay (clean_program refuses them)
    if spec[2]:
        b["body"] = [expand(x) for x in (rest[0] if rest else [])]
    if spec[3]:
        b["else"] = [expand(x) for x in (rest[1] if len(rest) > 1 else [])]
    return b


def stars_for(lv: dict, blocks: int) -> int:
    three, two = lv["stars"]
    return 3 if blocks <= three else 2 if blocks <= two else 1


class _Stop(Exception):
    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


DIRS = {0: (0, -1), 90: (1, 0), 180: (0, 1), -90: (-1, 0)}


def _round(x: float) -> int:
    """Rounding like the app (JavaScript Math.round: .5 up)."""
    return int(math.floor(float(x) + 0.5))


def _snap(d: float) -> int:
    d = _round(float(d) / 90.0) * 90 % 360
    return {0: 0, 90: 90, 180: 180, 270: -90}[d]


class Grid:
    """The puzzle world: the fox on a grid of cells, stones, the star. The same rules as the app (codelab.js CwGrid)."""

    def __init__(self, lv: dict):
        self.cols, self.rows = lv["cols"], lv["rows"]
        self.c, self.r, self.dir = lv["fox"][0], lv["fox"][1], _snap(lv["fox"][2])
        self.star = tuple(lv["star"])
        self.stones = {tuple(s) for s in lv.get("stones") or []}
        self.steps = 0

    def ahead(self, back: bool = False) -> tuple[int, int]:
        dc, dr = DIRS[self.dir]
        k = -1 if back else 1
        return self.c + dc * k, self.r + dr * k

    def free(self, c: int, r: int) -> bool:
        return 0 <= c < self.cols and 0 <= r < self.rows and (c, r) not in self.stones

    def step(self) -> None:
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise _Stop("forever")

    def move(self, n) -> None:
        n = _round(_num(n, -20, 20))
        for _ in range(abs(n)):
            c, r = self.ahead(back=n < 0)
            if not (0 <= c < self.cols and 0 <= r < self.rows):
                raise _Stop("edge")
            if (c, r) in self.stones:
                raise _Stop("stone")
            self.c, self.r = c, r
            if (c, r) == self.star:
                raise _Stop("win")

    # -------- running a program
    def value(self, v):
        if isinstance(v, dict):
            op, a = v["op"], v["args"]
            if op == "blocked":
                return not self.free(*self.ahead())
            if op == "touching":
                return False
            if op == "not":
                return not self.value(a["a"])
            if op == "and":
                return bool(self.value(a["a"])) and bool(self.value(a["b"]))
            if op == "or":
                return bool(self.value(a["a"])) or bool(self.value(a["b"]))
            if op in ("eq", "lt", "gt"):
                x, y = float(self.value(a["a"]) or 0), float(self.value(a["b"]) or 0)
                return x == y if op == "eq" else x < y if op == "lt" else x > y
            return 0
        return v

    def run(self, blocks: list[dict]) -> None:
        for b in blocks:
            if b.get("off"):
                continue
            self.step()
            op, a = b["op"], b["args"]
            if op == "move":
                self.move(self.value(a["n"]))
            elif op in ("turn_r", "turn_l"):
                deg = float(self.value(a["deg"]) or 0)
                self.dir = _snap(self.dir + (deg if op == "turn_r" else -deg))
            elif op == "point":
                self.dir = _snap(float(self.value(a["dir"]) or 0))
            elif op == "repeat":
                for _ in range(_round(_num(self.value(a["n"]), 0, 100000))):
                    self.run(b["body"])
                    self.step()                          # every round of a loop counts (an empty loop too)
            elif op == "forever":
                while True:
                    self.run(b["body"])
                    self.step()
            elif op == "if":
                if self.value(a["cond"]):
                    self.run(b["body"])
            elif op == "if_else":
                self.run(b["body"] if self.value(a["cond"]) else b["else"])
            elif op == "stop":
                raise _Stop("stop")


def simulate(lv: dict, scripts: list[dict], inputs: list | None = None) -> str:
    """Run a puzzle program like the app does: the ▶ scripts one after the other, then every tap / arrow of `inputs`
    with the scripts it starts. → «win» (the fox reached the star), «stone», «edge», «forever» (too many blocks run)
    or «short» (the program ended before the star)."""
    g = Grid(lv)
    todo = [("start", None)] + [tuple(str(i).split(":", 1)) if ":" in str(i) else (str(i), None) for i in (inputs or [])[:MAX_INPUTS]]
    try:
        for kind, arg in todo:
            for s in scripts:
                if s.get("off"):
                    continue
                if (kind == "start" and s["op"] == "ev_start") or (kind == "tap" and s["op"] == "ev_tap") or \
                        (kind == "key" and s["op"] == "ev_key" and s["args"].get("key") == arg):
                    try:
                        g.run(s["body"])
                    except _Stop as e:
                        if e.why != "stop":
                            raise
                        break
    except _Stop as e:
        return e.why
    return "short"


# ---------------------------------------------------------------- the workshop
class Codelab:
    def __init__(self, db, rewards):
        self.db = db
        self.rewards = rewards
        self._ticks: dict[int, float] = {}            # learning time: the last heartbeat per profile
        self.hours_ok = lambda prof: True              # learning hours of the child (services: lesson._check_hours)

    # ---------------------------------------------------------------- settings
    @staticmethod
    def _clean_settings(d: dict, s: dict) -> dict:
        s = dict(s)
        if isinstance(d.get("off"), list):
            s["off"] = sorted({int(x) for x in d["off"] if isinstance(x, int) or str(x).isdecimal()})
        for k in ("level_xp", "level_coins"):
            if k in d and d[k] is not None:
                s[k] = _int(d[k], 0, 10000, s[k])
        return s

    def settings(self) -> dict:
        got = self.db.get_setting("codelab")
        return self._clean_settings(got if isinstance(got, dict) else {}, DEFAULT)

    def save_settings(self, d: dict) -> dict:
        s = self._clean_settings(d if isinstance(d, dict) else {}, self.settings())
        self.db.set_setting("codelab", s)
        return s

    def enabled_for(self, prof: dict) -> bool:
        return prof.get("role") == "parent" or prof["id"] not in self.settings()["off"]

    def _need(self, prof: dict) -> None:
        if not self.enabled_for(prof):
            raise CommunityError("The Code Workshop is switched off for you")

    def _need_time(self, prof: dict) -> None:
        """Opening the workshop is learning: not with the daily learning time used up (or outside the learning hours)."""
        from . import timelimits
        if timelimits.used_up(self.db, prof, "learn"):
            raise CommunityError("Learning time for today is used up – see you tomorrow!")
        if not self.hours_ok(prof):
            raise CommunityError("learning time is over for today")

    @staticmethod
    def _parent(prof: dict) -> bool:
        return prof.get("role") == "parent"

    # ---------------------------------------------------------------- learning time
    def tick(self, prof: dict, now: float | None = None) -> dict:
        """A heartbeat of the open workshop (every ~30 s): the time since the last one counts as learning time (at most
        TICK_MAX seconds – a pause, a closed tab or two devices do not count twice)."""
        from . import timelimits
        now = time.monotonic() if now is None else now
        last = self._ticks.get(prof["id"])
        self._ticks[prof["id"]] = now
        if prof.get("role") == "kid" and last is not None and now - last >= 5:
            self.rewards.add_time(prof["id"], int(min(now - last, TICK_MAX)))
        return {"learn_left": timelimits.left(self.db, prof, "learn")}

    # ---------------------------------------------------------------- overview
    def _people(self) -> dict[int, dict]:
        return {p["id"]: {"id": p["id"], "name": p["name"], "avatar": json.loads(p["avatar"] or "{}"), "role": p["role"]}
                for p in self.db.q("SELECT id, name, avatar, role FROM profile")}

    def _progress(self, pid: int) -> dict[str, dict]:
        return {r["level"]: r for r in self.db.q("SELECT * FROM codelab_progress WHERE profile_id=?", pid)}

    def level_list(self, prof: dict) -> list[dict]:
        prog = self._progress(prof["id"])
        out, prev_ok = [], True
        for lv in levels():
            p = prog.get(lv["id"]) or {}
            solved = bool(p.get("solved_at"))
            out.append({"id": lv["id"], "world": lv["world"], "title": lv["title"], "stars": p.get("stars") or 0, "solved": solved,
                        "open": prev_ok or self._parent(prof)})
            prev_ok = solved
        return out

    def home(self, prof: dict) -> dict:
        self._need(prof)
        from . import timelimits
        s = self.settings()
        return {"worlds": levels_doc()["worlds"], "levels": self.level_list(prof), "projects": self.projects(prof),
                "reward": {"xp": s["level_xp"], "coins": s["level_coins"]}, "learn_left": timelimits.left(self.db, prof, "learn"),
                "parent": self._parent(prof)}

    # ---------------------------------------------------------------- puzzles
    def level_get(self, prof: dict, lid: str) -> dict:
        self._need(prof)
        self._need_time(prof)
        lv = level(lid)
        p = self._progress(prof["id"]).get(lid) or {}
        out = {k: v for k, v in lv.items() if k not in ("solution", "solution_inputs")}
        out["start"] = [expand(x) for x in lv.get("start") or []]
        ids = [x["id"] for x in levels()]
        i = ids.index(lid)
        out.update(best=p.get("stars") or 0, best_blocks=p.get("blocks"), solved=bool(p.get("solved_at")),
                   program=json.loads(p["program"]) if p.get("program") else None,
                   next=ids[i + 1] if i + 1 < len(ids) else None, n=i + 1, total=len(ids))
        return out

    def _level_scripts(self, lv: dict, scripts) -> list[dict]:
        return clean_scripts(scripts, ops=level_ops(lv), sprites={"s1"})

    def level_save(self, prof: dict, lid: str, scripts) -> None:
        """The try so far (the program opens again where the child stopped)."""
        self._need(prof)
        lv = level(lid)
        raw = json.dumps(self._level_scripts(lv, scripts), ensure_ascii=False)
        self.db.x("""INSERT INTO codelab_progress(profile_id, level, program) VALUES(?,?,?)
                     ON CONFLICT(profile_id, level) DO UPDATE SET program=excluded.program, updated_at=datetime('now','localtime')""",
                  prof["id"], lid, raw)

    def solve(self, prof: dict, lid: str, scripts, inputs=None) -> dict:
        """The app says «solved»: run it here again – the best ⭐ is kept, the first solve pays the reward once."""
        self._need(prof)
        lv = level(lid)
        clean = self._level_scripts(lv, scripts)
        n = sum(count_blocks(s["body"]) for s in clean if not s.get("off"))
        if lv.get("max") and n > lv["max"]:
            raise CommunityError("Too many blocks for this level")
        inputs = [str(x)[:12] for x in (inputs if isinstance(inputs, list) else [])][:MAX_INPUTS]
        why = simulate(lv, clean, inputs)
        if why != "win":
            return {"ok": False, "why": why}
        stars = stars_for(lv, n)
        raw = json.dumps(clean, ensure_ascii=False)
        with self.db.tx():
            old = self._progress(prof["id"]).get(lid) or {}
            first = not old.get("solved_at")
            best = max(stars, old.get("stars") or 0)
            blocks = n if old.get("blocks") is None else min(n, old["blocks"])
            self.db.x("""INSERT INTO codelab_progress(profile_id, level, stars, blocks, program, solved_at) VALUES(?,?,?,?,?,datetime('now','localtime'))
                         ON CONFLICT(profile_id, level) DO UPDATE SET stars=excluded.stars, blocks=excluded.blocks, program=excluded.program,
                         solved_at=COALESCE(solved_at, excluded.solved_at), updated_at=datetime('now','localtime')""",
                      prof["id"], lid, best, blocks, raw)
        reward = self._reward(prof, lv) if first else None
        return {"ok": True, "stars": stars, "best": best, "blocks": n, "first": first, "reward": reward}

    def _reward(self, prof: dict, lv: dict) -> dict | None:
        s = self.settings()
        got = {}
        reason = f"💡 {lv['id']} {lv['title']}"
        for acc, amount in (("xp", s["level_xp"]), ("coins", s["level_coins"])):
            if amount and self.rewards.book_once(prof["id"], acc, float(amount), "codelab_level", reason,
                                                 f"codelab:{prof['id']}:{lv['id']}:{acc}"):
                got[acc] = amount
        return got or None

    # ---------------------------------------------------------------- programs
    def _row(self, pid: int) -> dict:
        r = self.db.q1("SELECT * FROM codelab_project WHERE id=?", pid)
        if not r:
            raise CommunityError("Unknown program")
        return r

    @staticmethod
    def visible(prof: dict, r: dict, oversee: bool = False) -> bool:
        return can_see(prof, r["author_id"], r["visibility"], oversee)

    def _card(self, prof: dict, r: dict, people: dict) -> dict:
        a = people.get(r["author_id"]) or {"id": None, "name": "?", "avatar": {}}
        return {"id": r["id"], "title": r["title"], "author": {"id": a["id"], "name": a["name"], "avatar": a["avatar"]},
                "mine": r["author_id"] == prof["id"], "visibility": r["visibility"], "blocks": r["blocks"], "sprites": r["sprites"],
                "cover": r["cover"], "remix_of": r["remix_of"], "remix_title": r["remix_title"],
                "created_at": r["created_at"], "updated_at": r["updated_at"]}

    def projects(self, prof: dict, oversee: bool = False) -> dict:
        """Own programs and the programs of the others this person may see – private ones of others: in the parent area
        only that they exist (author, size, date)."""
        people = self._people()
        mine, others, private = [], [], []
        rows = self.db.q("""SELECT id, title, author_id, visibility, remix_of, remix_title, blocks, sprites, created_at, updated_at,
                                   CASE WHEN visibility='me' AND author_id != ? THEN NULL ELSE cover END AS cover
                            FROM codelab_project ORDER BY updated_at DESC, id DESC""", prof["id"])
        for r in rows:
            if r["author_id"] == prof["id"]:
                mine.append(self._card(prof, r, people))
            elif self.visible(prof, r, oversee):
                others.append(self._card(prof, r, people))
            elif oversee and self._parent(prof) and r["visibility"] == "me":
                a = people.get(r["author_id"]) or {"id": None, "name": "?", "avatar": {}}
                private.append({"id": r["id"], "private": True, "author": {"id": a["id"], "name": a["name"], "avatar": a["avatar"]},
                                "blocks": r["blocks"], "created_at": r["created_at"], "updated_at": r["updated_at"]})
        return {"mine": mine, "others": others, "private": private}

    def _room_for(self, prof: dict) -> None:
        if int(self.db.val("SELECT COUNT(*) FROM codelab_project", default=0)) >= MAX_PROJECTS:
            raise CommunityError("There are too many programs – remove an old one first")
        if int(self.db.val("SELECT COUNT(*) FROM codelab_project WHERE author_id=?", prof["id"], default=0)) >= MAX_PER_AUTHOR:
            raise CommunityError("You have as many programs as one person can keep – remove an old one first")

    @staticmethod
    def _cover(data: dict) -> str | None:
        """What the program card shows: the first costume of the first sprite (a library sprite – own drawings: none)."""
        for s in data["sprites"]:
            c = s["costumes"][s["c"]]
            if c["k"] == "lib":
                return c["v"]
        return None

    @staticmethod
    def _stats(data: dict) -> tuple[int, int]:
        return sum(count_blocks(s["scripts"], hats=True) for s in data["sprites"]), len(data["sprites"])

    def create(self, prof: dict, title: str, data, visibility: str = "family", remix: dict | None = None) -> int:
        self._need(prof)
        self._room_for(prof)
        title = _text(title, TITLE)
        if not title:
            raise CommunityError("Give the program a title")
        clean = clean_program(data)
        blocks, sprites = self._stats(clean)
        return self.db.x("""INSERT INTO codelab_project(title, author_id, data, visibility, blocks, sprites, cover, remix_of, remix_title)
                            VALUES(?,?,?,?,?,?,?,?,?)""",
                         title, prof["id"], json.dumps(clean, ensure_ascii=False), visibility if visibility in VISIBILITY else "family",
                         blocks, sprites, self._cover(clean), (remix or {}).get("id"), (remix or {}).get("title"))

    def get(self, prof: dict, pid: int, oversee: bool = False) -> dict:
        """A program to play (everybody who may see it) – the author also edits it. Both are learning (time limit)."""
        self._need(prof)
        if not oversee:
            self._need_time(prof)
        r = self._row(pid)
        if not self.visible(prof, r, oversee):
            raise CommunityError("Only the author can open this program")
        people = self._people()
        return {**self._card(prof, r, people), "data": json.loads(r["data"]), "edit": r["author_id"] == prof["id"],
                "remove": self._may_remove(prof, r)}

    def _may_remove(self, prof: dict, r: dict) -> bool:
        return r["author_id"] == prof["id"] or (self._parent(prof) and r["visibility"] != "me")

    def save(self, prof: dict, pid: int, data=None, title=None, visibility=None) -> dict:
        self._need(prof)
        with self.db.tx():
            r = self._row(pid)
            if r["author_id"] != prof["id"]:
                raise CommunityError("Only the author can change this program")
            if title is not None:
                t = _text(title, TITLE)
                if not t:
                    raise CommunityError("Give the program a title")
                r["title"] = t
            if data is not None:
                clean = clean_program(data)
                r["data"] = json.dumps(clean, ensure_ascii=False)
                r["blocks"], r["sprites"] = self._stats(clean)
                r["cover"] = self._cover(clean)
            if visibility in VISIBILITY:
                r["visibility"] = visibility
            self.db.x("""UPDATE codelab_project SET title=?, data=?, visibility=?, blocks=?, sprites=?, cover=?,
                         updated_at=datetime('now','localtime') WHERE id=?""",
                      r["title"], r["data"], r["visibility"], r["blocks"], r["sprites"], r["cover"], pid)
        return {"id": pid, "title": r["title"], "visibility": r["visibility"], "blocks": r["blocks"]}

    def remix(self, prof: dict, pid: int) -> int:
        """An own copy of a program this person may see – a new program of this person (for the whole family, like a new
        one); the card names the original."""
        self._need(prof)
        r = self._row(pid)
        if not self.visible(prof, r):
            raise CommunityError("Only the author can open this program")
        title = _text(r["title"] + " (Remix)", TITLE)
        return self.create(prof, title, json.loads(r["data"]), "family", remix={"id": r["id"], "title": r["title"]})

    def delete(self, prof: dict, pid: int) -> None:
        r = self._row(pid)
        if not self._may_remove(prof, r):
            if r["visibility"] == "me":
                raise CommunityError("Only the author can open this program")
            raise CommunityError("Only the author or a parent can remove this program")
        self.db.x("DELETE FROM codelab_project WHERE id=?", pid)

    def author_removed(self, pid: int) -> None:
        """A profile is deleted for good: its programs go too (a later profile must never see them)."""
        self.db.x("DELETE FROM codelab_project WHERE author_id=?", pid)

    # ---------------------------------------------------------------- parent area
    def overview(self, prof: dict) -> dict:
        """Parents: the puzzle progress of every child, the programs they may see and that private ones exist."""
        if not self._parent(prof):
            raise CommunityError("Only a parent can see this")
        lv = levels()
        kids = []
        for k in self.db.q("SELECT id, name, avatar FROM profile WHERE role='kid' AND archived=0 ORDER BY id"):
            prog = self._progress(k["id"])
            kids.append({"id": k["id"], "name": k["name"], "avatar": json.loads(k["avatar"] or "{}"),
                         "on": k["id"] not in self.settings()["off"],
                         "solved": sum(1 for x in prog.values() if x.get("solved_at")),
                         "stars": sum(x.get("stars") or 0 for x in prog.values()),
                         "levels": {x["id"]: (prog.get(x["id"]) or {}).get("stars") or 0 for x in lv}})
        return {"kids": kids, "levels": [{"id": x["id"], "world": x["world"], "title": x["title"]} for x in lv],
                "total": len(lv), "projects": self.projects(prof, oversee=True), "settings": self.settings()}

