"""🗝️ Adventure games on the family bookshelf: point & click games that children and parents build and the family plays.

The shelf, visibility, approval, rewards, ratings and the parent area are the ones of every book type (stories.py); this
module holds the content of a game (`clean`), the checker with a solvability search (`check`), the play engine (`act`,
`view` – it runs on the server, so readers never get the solution and cannot cheat), the templates and the file format.

A game (the working copy `data` of a book with type «game»):
- rooms: a background (a library scene, an own drawing of the drawing editor – cleaned SVG, 800×600 – or a photo), a description and up to 30 hotspots –
  rectangles in percent of the picture (so they scale with the screen). Up to 3 variants change the description and the
  picture while a condition holds («the light is on»).
- hotspots: 🚪 door (to a room or straight to an ending; can be locked by a condition), 📦 object (a look text; can be
  taken into the inventory – it disappears, or with `keep` it stays and only gives its item once: a chest with a key),
  🧙 person (starts a dialogue). Every hotspot can be hidden until a condition holds and
  can show a picture (one of the shipped assets in web/img/adventure, an emoji or an own drawing: SVG, 200×200, transparent).
Own drawings are SVG text inside the game (svgsafe.py: rooms max. BG_MAX, things max. ART_MAX); older painted PNG drawings
and photos are files (stories.py).
- items 🎒, flags 🚩 (switches like «dragon sleeps»), endings (🏆 win / 💀 lose), dialogue lines (text + answers – an
  answer can have a condition, actions and the next line), rules: «use item X on hotspot Y» (also without an item:
  «pull the lever») and «combine item A with item B».
- conditions: a list of up to 4 checks that all must hold: {"k": "flag"|"item", "id": …, "not": bool}.
- actions: {"k": "say", "v": text} · give / take an item · set / clear a flag · go to a room · end (an ending).

Ids are numbers; hotspot ids are unique in the whole game. A game is in one language like every book.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .community import CommunityError
from .i18n import _t

FORMAT = "family-quest-adventuregame/1"
MAX_ROOMS = 40
MAX_SPOTS = 30               # per room
MAX_ITEMS = 60
MAX_FLAGS = 100
MAX_LINES = 200
MAX_ANSWERS = 6
MAX_RULES = 200
MAX_ENDINGS = 20
MAX_ACTIONS = 8
MAX_COND = 4
MAX_VARIANTS = 3
NAME = 40
ROOM_TEXT = 800
LOOK = 400
LINE = 400
ANSWER = 120
SAY = 300
END_TEXT = 800
MAX_BYTES = 2_000_000        # JSON of one game (inline SVG pictures included)
SEARCH_STATES = 6000         # the solvability search stops after so many game states …
SEARCH_SECONDS = 1.5         # … or after this time («too big to test every way»)
MAX_ID = 99_999
SPOT_KINDS = ("door", "object", "person")
ACTIONS = ("say", "give", "take", "set", "clear", "go", "end")
ENDINGS = ("win", "lose")

# own SVG pictures in web/img/adventure/<key>.svg (tools/adventure_assets.py) – English names, the app translates them
ASSETS = {
    "door": "Wooden door", "door_arch": "Stone gate", "door_metal": "Metal door", "hatch": "Hatch", "window": "Window",
    "key": "Key", "chest": "Chest", "lever": "Lever", "lamp": "Lamp", "candle": "Candle", "book": "Book",
    "potion": "Potion", "rope": "Rope", "stick": "Stick", "ladder": "Ladder", "crystal": "Crystal", "magnet": "Magnet",
    "battery": "Battery", "cable": "Cable", "card": "Key card", "button": "Button", "screen": "Screen",
    "cauldron": "Cauldron", "bookshelf": "Bookshelf", "table": "Table", "bed": "Bed", "box": "Box", "plant": "Plant",
    "well": "Well", "wand": "Magic wand",
    "wizard": "Wizard", "robot": "Robot", "cat": "Cat", "dragon": "Dragon", "ghost": "Ghost", "knight": "Knight",
    "pirate": "Pirate", "alien": "Alien", "owl": "Owl",
}
# room backgrounds for games only (web/img/adventure/<key>.svg) – the scenes of the books (stories.BACKGROUNDS) work too
ROOMS = {"tower": "Tower room", "library": "Library", "hall": "Stone hall", "hallway": "Hallway", "cabin": "Spaceship cabin",
         "corridor": "Spaceship corridor", "bridge": "Spaceship bridge", "engine": "Engine room", "storage": "Storage room", "dark": "Dark room"}

MSG = {
    "title": _t("Give the game a title"),
    "no_rooms": _t("The game has no rooms yet"),
    "start": _t("Choose the start room"),
    "room_name": _t("Room {0} has no name yet"),
    "room_text": _t("Room «{0}» has no description yet"),
    "spot_name": _t("Room «{0}»: a hotspot has no name yet"),
    "door_target": _t("Room «{0}»: the door «{1}» leads nowhere yet"),
    "take_item": _t("Room «{0}»: «{1}» can be taken but is no item yet"),
    "person_talk": _t("Room «{0}»: «{1}» has nothing to say yet"),
    "unknown": _t("{0}: uses something that does not exist any more"),
    "item_name": _t("An item has no name yet"),
    "flag_name": _t("A switch has no name yet"),
    "item_never": _t("Nobody can ever get the item «{0}»"),
    "flag_never": _t("The switch «{0}» is needed but never switched on"),
    "door_key": _t("Room «{0}»: the door «{1}» can never be opened"),
    "line_text": _t("A dialogue line has no text yet"),
    "line_dead": _t("Dialogue «{0}»: no answer always works – the talk gets stuck"),
    "line_lost": _t("Dialogue «{0}» is never said"),
    "answer_text": _t("Dialogue «{0}»: an answer has no text yet"),
    "rule_incomplete": _t("A rule is not complete yet"),
    "ending_text": _t("An ending has no text yet"),
    "no_win": _t("No way to a winning ending (🏆) yet"),
    "unreachable": _t("Room «{0}» cannot be reached"),
    "unsolvable": _t("The game cannot be won – no way leads to a 🏆 ending"),
    "never_reached": _t("Room «{0}» can never be reached when playing"),
    "stuck": _t("Players can get stuck in «{0}» – then only starting again helps"),
    "too_big": _t("The game is too big to test every way – play it through yourself"),
}
WARN = {"line_lost", "never_reached", "stuck", "too_big"}

# messages of the engine that are not texts of the game – codes, the app translates them
CODE_TEXT = {
    "nothing": _t("Nothing special."),
    "locked": _t("It is locked."),
    "no_use": _t("That does not work."),
    "no_combine": _t("These two things do not fit together."),
    "got": _t("You get: {0}"),
}


# ---------------------------------------------------------------- cleaning
def _text(v, n: int) -> str:
    return str(v or "").replace("\r\n", "\n").replace("\x00", "")[:n].strip()


def _id(v) -> int | None:
    if isinstance(v, bool):
        return None
    try:
        i = int(v)
    except (TypeError, ValueError):
        return None
    return i if 1 <= i <= MAX_ID else None


def _num(v, lo: float, hi: float, default: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = default
    if f != f or f in (float("inf"), float("-inf")):    # NaN, infinity
        f = default
    return round(min(max(f, lo), hi), 1)


def clean_bg(p, folder: Path | None) -> dict | None:
    """The picture of a room: a scene of the library, an own drawing / photo (stories.py upload) or a cleaned SVG."""
    from .stories import BACKGROUNDS, clean_pic
    from .svgsafe import BG_MAX, safe_svg
    if not isinstance(p, dict):
        return None
    if p.get("k") == "lib":
        return {"k": "lib", "v": p["v"]} if p.get("v") in BACKGROUNDS or p.get("v") in ROOMS else None
    if p.get("k") == "svg":
        svg = safe_svg(p.get("v"), BG_MAX)
        return {"k": "svg", "v": svg} if svg else None
    if p.get("k") == "img":
        return clean_pic(p, folder)
    return None


def clean_art(p, folder: Path | None) -> dict | None:
    """The picture of a hotspot or an item: an asset, an emoji, an own drawing or a cleaned SVG."""
    from .stories import EMOJI, clean_pic
    from .svgsafe import ART_MAX, safe_svg
    if not isinstance(p, dict):
        return None
    if p.get("k") == "asset":
        return {"k": "asset", "v": p["v"]} if p.get("v") in ASSETS else None
    if p.get("k") == "emoji":
        v = _text(p.get("v"), EMOJI)
        return {"k": "emoji", "v": v} if v else None
    if p.get("k") == "svg":
        svg = safe_svg(p.get("v"), ART_MAX)
        return {"k": "svg", "v": svg} if svg else None
    if p.get("k") == "img":
        return clean_pic(p, folder)
    return None


def clean_cond(c) -> list[dict]:
    out = []
    for a in (c if isinstance(c, list) else [])[:50]:
        if isinstance(a, dict) and a.get("k") in ("flag", "item") and _id(a.get("id")) and len(out) < MAX_COND:
            out.append({"k": a["k"], "id": _id(a["id"]), "not": bool(a.get("not"))})
    return out


def clean_do(d) -> list[dict]:
    out = []
    for a in (d if isinstance(d, list) else [])[:50]:
        if not isinstance(a, dict) or a.get("k") not in ACTIONS or len(out) >= MAX_ACTIONS:
            continue
        if a["k"] == "say":
            v = _text(a.get("v"), SAY)
            if v:
                out.append({"k": "say", "v": v})
        elif _id(a.get("id")):
            out.append({"k": a["k"], "id": _id(a["id"])})
    return out


def _list(data: dict, key: str, limit: int, msg: str) -> list[dict]:
    raw = data.get(key) if isinstance(data.get(key), list) else []
    if len(raw) > limit:
        raise CommunityError(msg)
    return [x for x in raw if isinstance(x, dict)]


def _unique(rows: list[dict], fn) -> list[dict]:
    out, seen = [], set()
    for r in rows:
        i = _id(r.get("id"))
        if i is None or i in seen:
            continue
        seen.add(i)
        out.append(fn(r, i))
    return out


def clean(data, folder: Path | None = None) -> dict:
    """A valid game (working copy): every field checked and limited, incomplete games are fine – `check` says what is
    missing. Too many rooms, hotspots, items … or too much text is refused. References to things that are gone stay as
    they are (the checker shows them; the engine ignores them) – only doors and dialogue lines lose a missing target."""
    if not isinstance(data, dict):
        data = {}
    rooms_raw = _list(data, "rooms", MAX_ROOMS, "A game can have at most 40 rooms")
    items = _unique(_list(data, "items", MAX_ITEMS, "A game can have at most 60 items"),
                    lambda r, i: {"id": i, "name": _text(r.get("name"), NAME), "icon": clean_art(r.get("icon"), folder)})
    flags = _unique(_list(data, "flags", MAX_FLAGS, "A game can have at most 100 switches"),
                    lambda r, i: {"id": i, "name": _text(r.get("name"), NAME)})
    endings = _unique(_list(data, "endings", MAX_ENDINGS, "A game can have at most 20 endings"),
                      lambda r, i: {"id": i, "kind": r.get("kind") if r.get("kind") in ENDINGS else "win",
                                    "text": _text(r.get("text"), END_TEXT)})

    def line(r, i):
        answers = []
        for a in (r.get("answers") if isinstance(r.get("answers"), list) else [])[:MAX_ANSWERS]:
            if isinstance(a, dict):
                answers.append({"t": _text(a.get("t"), ANSWER), "if": clean_cond(a.get("if")), "do": clean_do(a.get("do")),
                                "next": _id(a.get("next"))})
        return {"id": i, "text": _text(r.get("text"), LINE), "answers": answers}
    lines = _unique(_list(data, "lines", MAX_LINES, "A game can have at most 200 dialogue lines"), line)

    spot_ids: set[int] = set()
    rooms = []
    for r in rooms_raw:
        rid = _id(r.get("id"))
        if rid is None or any(x["id"] == rid for x in rooms):
            continue
        raw_spots = r.get("spots") if isinstance(r.get("spots"), list) else []
        if len(raw_spots) > MAX_SPOTS:
            raise CommunityError("A room can have at most 30 hotspots")
        spots = []
        for s in raw_spots:
            sid = _id(s.get("id")) if isinstance(s, dict) else None
            if sid is None or sid in spot_ids:
                continue
            spot_ids.add(sid)
            x, y = _num(s.get("x"), 0, 98, 40), _num(s.get("y"), 0, 98, 40)
            spots.append({
                "id": sid, "kind": s.get("kind") if s.get("kind") in SPOT_KINDS else "object", "name": _text(s.get("name"), NAME),
                "x": x, "y": y, "w": _num(s.get("w"), 2, 100 - x, 20), "h": _num(s.get("h"), 2, 100 - y, 20),
                "art": clean_art(s.get("art"), folder), "if": clean_cond(s.get("if")), "look": _text(s.get("look"), LOOK),
                "to": _id(s.get("to")), "end": _id(s.get("end")), "lock": clean_cond(s.get("lock")), "locked": _text(s.get("locked"), LOOK),
                "take": bool(s.get("take")), "keep": bool(s.get("keep")), "item": _id(s.get("item")), "talk": _id(s.get("talk"))})
        variants = []
        for v in (r.get("variants") if isinstance(r.get("variants"), list) else [])[:MAX_VARIANTS]:
            if isinstance(v, dict):
                variants.append({"if": clean_cond(v.get("if")), "text": _text(v.get("text"), ROOM_TEXT), "bg": clean_bg(v.get("bg"), folder)})
        rooms.append({"id": rid, "name": _text(r.get("name"), NAME), "text": _text(r.get("text"), ROOM_TEXT),
                      "bg": clean_bg(r.get("bg"), folder), "variants": variants, "spots": spots})
    room_ids, line_ids, end_ids = {r["id"] for r in rooms}, {x["id"] for x in lines}, {e["id"] for e in endings}
    for r in rooms:                                     # a door to a room / an ending that is gone leads nowhere
        for s in r["spots"]:
            if s["to"] not in room_ids:
                s["to"] = None
            if s["end"] not in end_ids:
                s["end"] = None
            if s["talk"] not in line_ids:
                s["talk"] = None
    for x in lines:
        for a in x["answers"]:
            if a["next"] not in line_ids:
                a["next"] = None

    def rule(r, i):
        kind = r.get("kind") if r.get("kind") in ("use", "combine") else "use"
        out = {"id": i, "kind": kind, "item": _id(r.get("item")), "if": clean_cond(r.get("if")), "do": clean_do(r.get("do"))}
        if kind == "use":
            out["spot"] = _id(r.get("spot"))
        else:
            out["item2"] = _id(r.get("item2"))
        return out
    rules = _unique(_list(data, "rules", MAX_RULES, "A game can have at most 200 rules"), rule)
    start = _id(data.get("start"))
    if start not in room_ids:
        start = rooms[0]["id"] if rooms else None
    out = {"start": start, "rooms": rooms, "items": items, "flags": flags, "lines": lines, "rules": rules, "endings": endings}
    if len(json.dumps(out, ensure_ascii=False)) > MAX_BYTES:
        raise CommunityError("The game is too big – use fewer or smaller pictures")
    return out


def empty_game() -> dict:
    return {"start": 1, "rooms": [{"id": 1, "name": "", "text": "", "bg": {"k": "lib", "v": "tower"}, "variants": [], "spots": []}],
            "items": [], "flags": [], "lines": [], "rules": [], "endings": [{"id": 1, "kind": "win", "text": ""}]}


def size(data: dict) -> int:
    return len((data or {}).get("rooms") or [])


def endings(data: dict | None) -> list[int]:
    return [e["id"] for e in (data or {}).get("endings") or []]


# ---------------------------------------------------------------- the engine (also used by the checker's search)
def new_state(data: dict, room: int | None = None) -> dict:
    rooms = {r["id"] for r in data.get("rooms") or []}
    room = room if room in rooms else data.get("start")
    return {"room": room, "inv": [], "flags": [], "taken": [], "talk": None, "end": None}


def clean_state(data: dict, st) -> dict:
    """A saved or sent state that fits this game (a new version of the game may have removed things)."""
    if not isinstance(st, dict):
        return new_state(data)
    rooms = {r["id"] for r in data.get("rooms") or []}
    if st.get("room") not in rooms:
        return new_state(data)
    items, flags = {i["id"] for i in data["items"]}, {f["id"] for f in data["flags"]}
    spots = {s["id"]: r["id"] for r in data["rooms"] for s in r["spots"]}
    lines = {x["id"] for x in data["lines"]}
    talk = st.get("talk") if isinstance(st.get("talk"), dict) else None
    if talk and not (talk.get("line") in lines and spots.get(talk.get("spot")) == st["room"]):
        talk = None
    end = st.get("end") if st.get("end") in set(endings(data)) else None
    lst = lambda k, ok: [x for x in dict.fromkeys(st.get(k) if isinstance(st.get(k), list) else []) if x in ok][:500]   # noqa: E731
    return {"room": st["room"], "inv": lst("inv", items), "flags": lst("flags", flags), "taken": lst("taken", set(spots)),
            "talk": {"spot": talk["spot"], "line": talk["line"]} if talk else None, "end": end}


def cond_ok(cond: list[dict], st: dict) -> bool:
    for a in cond or []:
        have = a["id"] in (st["flags"] if a["k"] == "flag" else st["inv"])
        if have == a["not"]:
            return False
    return True


class Index:
    """Quick look-ups of one game (the engine and the search use them many times)."""
    def __init__(self, data: dict):
        self.data = data
        self.rooms = {r["id"]: r for r in data["rooms"]}
        self.spots = {s["id"]: (s, r["id"]) for r in data["rooms"] for s in r["spots"]}
        self.items = {i["id"]: i for i in data["items"]}
        self.flags = {f["id"]: f for f in data["flags"]}
        self.lines = {x["id"]: x for x in data["lines"]}
        self.endings = {e["id"]: e for e in data["endings"]}
        self.use: dict[tuple, list[dict]] = {}
        self.combine: dict[frozenset, list[dict]] = {}
        for r in data["rules"]:
            if r["kind"] == "use" and r.get("spot"):
                self.use.setdefault((r["spot"], r["item"]), []).append(r)
            elif r["kind"] == "combine" and r["item"] and r.get("item2") and r["item"] != r["item2"]:
                self.combine.setdefault(frozenset((r["item"], r["item2"])), []).append(r)

    def visible(self, st: dict) -> list[dict]:
        room = self.rooms.get(st["room"])
        if not room:
            return []
        return [s for s in room["spots"] if (s["id"] not in st["taken"] or s.get("keep")) and cond_ok(s["if"], st)]

    def verbs(self, s: dict, st: dict) -> list[str]:
        out = ["look"]
        if s["kind"] == "door":
            out.append("go")
        elif s["kind"] == "person" and s["talk"]:
            out.append("talk")
        elif s["kind"] == "object" and s["take"] and s["item"] in self.items and s["id"] not in st["taken"]:
            out.append("take")
        if (s["id"], None) in self.use:
            out.append("use")
        return out


class PlayError(CommunityError):
    pass


def _msg(code: str, *args) -> dict:
    return {"c": code, "a": [str(a) for a in args]}


def _item_label(ix: Index, iid: int) -> str:
    it = ix.items.get(iid)
    if not it:
        return "?"
    icon = it["icon"]["v"] if it.get("icon") and it["icon"]["k"] == "emoji" else ""
    return (icon + " " + it["name"]).strip()


def run(ix: Index, st: dict, do: list[dict], msgs: list) -> None:
    """Carry out actions in their order (an ending stops the rest)."""
    for a in do:
        k = a["k"]
        if k == "say":
            msgs.append({"t": a["v"]})
        elif k == "give" and a["id"] in ix.items:
            if a["id"] not in st["inv"]:
                st["inv"].append(a["id"])
                msgs.append(_msg("got", _item_label(ix, a["id"])))
        elif k == "take":
            if a["id"] in st["inv"]:
                st["inv"].remove(a["id"])
        elif k == "set" and a["id"] in ix.flags:
            if a["id"] not in st["flags"]:
                st["flags"].append(a["id"])
        elif k == "clear":
            if a["id"] in st["flags"]:
                st["flags"].remove(a["id"])
        elif k == "go" and a["id"] in ix.rooms:
            st["room"], st["talk"] = a["id"], None
        elif k == "end" and a["id"] in ix.endings:
            st["end"], st["talk"] = a["id"], None
            return


def act(ix: Index, st: dict, a: dict) -> list[dict]:
    """One move of the player – changes `st` and returns the messages. Moves that are not possible raise PlayError."""
    if not isinstance(a, dict):
        raise PlayError(_t("This is not possible"))
    if st.get("end"):
        raise PlayError(_t("The game is over – start again"))
    verb = a.get("verb")
    msgs: list[dict] = []
    if st.get("talk"):
        line = ix.lines.get(st["talk"]["line"])
        if verb == "leave" or not line:
            st["talk"] = None
            return msgs
        if verb != "answer":
            raise PlayError(_t("Finish the talk first"))
        i = a.get("answer")
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(line["answers"]) or not cond_ok(line["answers"][i]["if"], st):
            raise PlayError(_t("This is not possible"))
        ans = line["answers"][i]
        talk = st["talk"]
        run(ix, st, ans["do"], msgs)
        if st["talk"] is talk:                               # no «go» / «end» in the answer: on to the next line (or the end of the talk)
            st["talk"] = {"spot": talk["spot"], "line": ans["next"]} if ans["next"] in ix.lines else None
        return msgs
    if verb == "combine":
        a1, a2 = a.get("item"), a.get("item2")
        if a1 not in st["inv"] or a2 not in st["inv"] or a1 == a2:
            raise PlayError(_t("This is not possible"))
        for r in ix.combine.get(frozenset((a1, a2)), []):
            if cond_ok(r["if"], st):
                run(ix, st, r["do"], msgs)
                return msgs
        return [_msg("no_combine")]
    spot = next((s for s in ix.visible(st) if s["id"] == a.get("spot")), None)
    if not spot:
        raise PlayError(_t("This is not possible"))
    if verb == "look":
        return [{"t": spot["look"]} if spot["look"] else _msg("nothing")]
    if verb == "use":
        item = a.get("item")
        if item is not None and item not in st["inv"]:
            raise PlayError(_t("This is not possible"))
        for r in ix.use.get((spot["id"], item), []):
            if cond_ok(r["if"], st):
                run(ix, st, r["do"], msgs)
                return msgs
        if spot["kind"] == "door":                          # a key on a door without an own rule: try to go through
            verb = "go"
        else:
            return [_msg("no_use")]
    if verb == "go" and spot["kind"] == "door":
        if not cond_ok(spot["lock"], st):
            return [{"t": spot["locked"]} if spot["locked"] else _msg("locked")]
        if spot["end"] in ix.endings:
            st["end"] = spot["end"]
        elif spot["to"] in ix.rooms:
            st["room"] = spot["to"]
        else:
            return [_msg("nothing")]
        return msgs
    if verb == "take" and spot["kind"] == "object" and spot["take"] and spot["item"] in ix.items and spot["id"] not in st["taken"]:
        st["taken"].append(spot["id"])
        if spot["item"] not in st["inv"]:
            st["inv"].append(spot["item"])
        return [_msg("got", _item_label(ix, spot["item"]))]
    if verb == "talk" and spot["kind"] == "person" and spot["talk"] in ix.lines:
        st["talk"] = {"spot": spot["id"], "line": spot["talk"]}
        return msgs
    raise PlayError(_t("This is not possible"))


def room_look(ix: Index, st: dict) -> tuple[str, dict | None]:
    """The description and the picture of the current room – the first variant whose condition holds wins."""
    room = ix.rooms[st["room"]]
    for v in room["variants"]:
        if v["if"] and cond_ok(v["if"], st):
            return v["text"] or room["text"], v["bg"] or room["bg"]
    return room["text"], room["bg"]


def view(ix: Index, st: dict) -> dict:
    """What the player sees – never the hidden hotspots, the rules or the solution."""
    room = ix.rooms[st["room"]]
    text, bg = room_look(ix, st)
    talk = None
    if st.get("talk"):
        s, _ = ix.spots[st["talk"]["spot"]]
        line = ix.lines[st["talk"]["line"]]
        talk = {"spot": {"id": s["id"], "name": s["name"], "art": s["art"]}, "line": {"id": line["id"], "text": line["text"]},
                "answers": [{"i": i, "t": a["t"]} for i, a in enumerate(line["answers"]) if cond_ok(a["if"], st)]}
    end = ix.endings.get(st.get("end"))
    return {"room": {"id": room["id"], "name": room["name"], "text": text, "bg": bg},
            "spots": [{"id": s["id"], "kind": s["kind"], "name": s["name"], "x": s["x"], "y": s["y"], "w": s["w"], "h": s["h"],
                       "art": s["art"], "verbs": ix.verbs(s, st)} for s in ix.visible(st)],
            "inv": [{"id": i, "name": ix.items[i]["name"], "icon": ix.items[i]["icon"]} for i in st["inv"] if i in ix.items],
            "talk": talk, "end": {"id": end["id"], "kind": end["kind"], "text": end["text"]} if end else None}


# ---------------------------------------------------------------- the checker
def _key(st: dict) -> tuple:
    t = st["talk"]
    return (st["room"], tuple(sorted(st["inv"])), tuple(sorted(st["flags"])), tuple(sorted(st["taken"])),
            (t["spot"], t["line"]) if t else None, st["end"])


def _moves(ix: Index, st: dict) -> list[dict]:
    """Every move that can change the state (looking never does)."""
    if st["talk"]:
        line = ix.lines.get(st["talk"]["line"])
        out = [{"verb": "leave"}]
        if line:
            out += [{"verb": "answer", "answer": i} for i, a in enumerate(line["answers"]) if cond_ok(a["if"], st)]
        return out
    out = []
    for s in ix.visible(st):
        if s["kind"] == "door":
            out.append({"verb": "go", "spot": s["id"]})
        elif s["kind"] == "object" and s["take"] and s["item"] in ix.items and s["id"] not in st["taken"]:
            out.append({"verb": "take", "spot": s["id"]})
        elif s["kind"] == "person" and s["talk"] in ix.lines:
            out.append({"verb": "talk", "spot": s["id"]})
        for item in [None, *st["inv"]]:
            if (s["id"], item) in ix.use:
                out.append({"verb": "use", "spot": s["id"], "item": item})
    inv = st["inv"]
    for i, a in enumerate(inv):
        for b in inv[i + 1:]:
            if frozenset((a, b)) in ix.combine:
                out.append({"verb": "combine", "item": a, "item2": b})
    return out


def search(data: dict, limit: int | None = None, seconds: float | None = None) -> dict:
    """Play every way through the game (breadth first, bounded): which rooms, items, switches, lines and endings can be
    reached, can it be won, and can a player get stuck (a state from which no way leads to a win any more)?"""
    limit, seconds = limit or SEARCH_STATES, seconds or SEARCH_SECONDS
    ix = Index(data)
    out = {"complete": True, "win": False, "rooms": set(), "items": set(), "flags": set(), "lines": set(), "endings": set(),
           "stuck": None, "states": 0}
    if data.get("start") not in ix.rooms:
        return out
    t0 = time.monotonic()
    first = new_state(data)
    seen = {_key(first): 0}
    states, edges, todo = [first], [[]], [first]
    head = 0
    while head < len(todo):
        if len(seen) >= limit or time.monotonic() - t0 > seconds:
            out["complete"] = False
            break
        st = todo[head]
        n = seen[_key(st)]
        head += 1
        out["rooms"].add(st["room"])
        out["items"].update(st["inv"])
        out["flags"].update(st["flags"])
        if st["talk"]:
            out["lines"].add(st["talk"]["line"])
        if st["end"]:
            out["endings"].add(st["end"])
            if ix.endings[st["end"]]["kind"] == "win":
                out["win"] = True
            continue
        for mv in _moves(ix, st):
            nxt = json.loads(json.dumps(st))
            try:
                act(ix, nxt, mv)
            except PlayError:
                continue
            k = _key(nxt)
            if k not in seen:
                seen[k] = len(states)
                states.append(nxt)
                edges.append([])
                todo.append(nxt)
            edges[n].append(seen[k])
    out["states"] = len(states)
    if out["complete"] and out["win"]:                      # stuck: a state from which no way leads to a win any more
        back: list[list[int]] = [[] for _ in states]
        for a, outs in enumerate(edges):
            for b in outs:
                back[b].append(a)
        good = {i for i, s in enumerate(states) if s["end"] and ix.endings[s["end"]]["kind"] == "win"}
        todo2 = list(good)
        while todo2:
            for a in back[todo2.pop()]:
                if a not in good:
                    good.add(a)
                    todo2.append(a)
        for i, s in enumerate(states):
            if i not in good and not s["end"]:
                out["stuck"] = s["room"]
                break
    return out


def _refs(data: dict) -> list[tuple[str, list[dict], list[dict]]]:
    """Every condition and action list of the game with a label where it is: [(label, conditions, actions)]."""
    out = []
    for r in data["rooms"]:
        for v in r["variants"]:
            out.append((r["name"] or "?", v["if"], []))
        for s in r["spots"]:
            out.append((f"{r['name'] or '?'} › {s['name'] or '?'}", s["if"] + s["lock"], []))
    for x in data["lines"]:
        for a in x["answers"]:
            out.append((_short(x["text"]), a["if"], a["do"]))
    for rl in data["rules"]:
        out.append(("⚙️ " + str(data["rules"].index(rl) + 1), rl["if"], rl["do"]))
    return out


def _short(t: str, n: int = 24) -> str:
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def check(data: dict, title: str = "x") -> list[dict]:
    """What is missing or wrong: [{code, msg, args, level, room, spot, line, rule}] – level «error» stops publishing,
    «warn» does not. Besides the static checks a bounded search plays every way through the game."""
    out: list[dict] = []

    def add(code: str, *args, room=None, spot=None, line=None, rule=None) -> None:
        out.append({"code": code, "msg": MSG[code], "args": [str(a) for a in args], "level": "warn" if code in WARN else "error",
                    "room": room, "spot": spot, "line": line, "rule": rule, "page": room})

    if not str(title or "").strip():
        add("title")
    rooms = data.get("rooms") or []
    if not rooms:
        add("no_rooms")
        return out
    ix = Index(data)
    if data.get("start") not in ix.rooms:
        add("start")
    # what the game can give and switch on at all
    gives = {s["item"] for r in rooms for s in r["spots"] if s["kind"] == "object" and s["take"] and s["item"]}
    sets = set()
    for _, _, do in _refs(data):
        for a in do:
            if a["k"] == "give":
                gives.add(a["id"])
            elif a["k"] == "set":
                sets.add(a["id"])
    needed_items = {a["id"] for _, c, _ in _refs(data) for a in c if a["k"] == "item" and not a["not"]}
    needed_items |= {rl["item"] for rl in data["rules"] if rl["item"]} | {rl.get("item2") for rl in data["rules"] if rl.get("item2")}
    needed_flags = {a["id"] for _, c, _ in _refs(data) for a in c if a["k"] == "flag" and not a["not"]}
    for i, r in enumerate(rooms, start=1):
        rn = r["name"] or str(i)
        if not r["name"]:
            add("room_name", i, room=r["id"])
        if not r["text"]:
            add("room_text", rn, room=r["id"])
        for s in r["spots"]:
            sn = s["name"] or "?"
            if not s["name"]:
                add("spot_name", rn, room=r["id"], spot=s["id"])
            if s["kind"] == "door":
                if not s["to"] and not s["end"]:
                    add("door_target", rn, sn, room=r["id"], spot=s["id"])
                elif any((a["k"] == "item" and a["id"] not in gives) or (a["k"] == "flag" and a["id"] not in sets)
                         for a in s["lock"] if not a["not"]):
                    add("door_key", rn, sn, room=r["id"], spot=s["id"])
            elif s["kind"] == "object" and s["take"] and s["item"] not in ix.items:
                add("take_item", rn, sn, room=r["id"], spot=s["id"])
            elif s["kind"] == "person" and not s["talk"]:
                add("person_talk", rn, sn, room=r["id"], spot=s["id"])
    for label, cond, do in _refs(data):
        bad = any((a["k"] == "item" and a["id"] not in ix.items) or (a["k"] == "flag" and a["id"] not in ix.flags) for a in cond)
        bad = bad or any((a["k"] in ("give", "take") and a["id"] not in ix.items) or (a["k"] in ("set", "clear") and a["id"] not in ix.flags)
                         or (a["k"] == "go" and a["id"] not in ix.rooms) or (a["k"] == "end" and a["id"] not in ix.endings) for a in do)
        if bad:
            add("unknown", label)
    needed_items.discard(None)
    for it in data["items"]:
        if not it["name"]:
            add("item_name")
        elif it["id"] not in gives and it["id"] in needed_items:
            add("item_never", it["name"])
    for f in data["flags"]:
        if not f["name"]:
            add("flag_name")
        elif f["id"] in needed_flags and f["id"] not in sets:
            add("flag_never", f["name"])
    # dialogues
    said = {s["talk"] for s, _ in ix.spots.values() if s["kind"] == "person" and s["talk"]}
    said |= {a["next"] for x in data["lines"] for a in x["answers"] if a["next"]}
    for x in data["lines"]:
        ln = _short(x["text"]) or "?"
        if not x["text"]:
            add("line_text", line=x["id"])
        if not any(not a["if"] for a in x["answers"]):
            add("line_dead", ln, line=x["id"])
        if any(not a["t"] for a in x["answers"]):
            add("answer_text", ln, line=x["id"])
        if x["id"] not in said:
            add("line_lost", ln, line=x["id"])
    for rl in data["rules"]:
        if (rl["kind"] == "use" and (not rl.get("spot") or rl["spot"] not in ix.spots)) or not rl["do"] or \
                (rl["kind"] == "combine" and (not rl["item"] or not rl.get("item2") or rl["item"] == rl["item2"])):
            add("rule_incomplete", rule=rl["id"])
    for e in data["endings"]:
        if not e["text"]:
            add("ending_text")
    wins = {e["id"] for e in data["endings"] if e["kind"] == "win"}
    win_used = any(s["end"] in wins for s, _ in ix.spots.values() if s["kind"] == "door") or \
        any(a["k"] == "end" and a["id"] in wins for _, _, do in _refs(data) for a in do)
    if not win_used:
        add("no_win")
    # rooms that no door or «go» reaches (locks not counted)
    links: dict[int, set] = {r["id"]: set() for r in rooms}
    go_any = {a["id"] for _, _, do in _refs(data) for a in do if a["k"] == "go"}
    for r in rooms:
        links[r["id"]] |= {s["to"] for s in r["spots"] if s["kind"] == "door" and s["to"]}
    reach, todo = set(), [data.get("start")]
    while todo:
        rid = todo.pop()
        if rid in reach or rid not in links:
            continue
        reach.add(rid)
        todo += list(links[rid])
    reach |= go_any                                          # a «go» action can come from anywhere – counted as reachable
    for r in rooms:
        if r["id"] not in reach:
            add("unreachable", r["name"] or "?", room=r["id"])
    # play every way through it
    if any(i["level"] == "error" for i in out) and data.get("start") not in ix.rooms:
        return out
    res = search(data)
    if not res["complete"]:
        add("too_big")
    else:
        if win_used and not res["win"]:
            add("unsolvable")
        for r in rooms:
            if r["id"] in reach and r["id"] not in res["rooms"]:
                add("never_reached", r["name"] or "?", room=r["id"])
        if res["stuck"]:
            add("stuck", ix.rooms[res["stuck"]]["name"] or "?", room=res["stuck"])
    return out


def blocking(issues: list[dict]) -> list[dict]:
    return [i for i in issues if i.get("level", "error") == "error"]


# ---------------------------------------------------------------- templates (texts in adventuregame_templates.json)
# Every string that starts with «@» is a text key of the template; the texts come in every app language.
def _spot(sid, kind, name, box, art=None, look=None, **kw):
    x, y, w, h = box
    out = {"id": sid, "kind": kind, "name": name, "x": x, "y": y, "w": w, "h": h, "art": {"k": "asset", "v": art} if art else None,
           "if": [], "look": look or "", "to": None, "end": None, "lock": [], "locked": "", "take": False, "keep": False, "item": None, "talk": None}
    out.update(kw)
    return out


def _c(*atoms) -> list[dict]:
    """Template conditions: ("f", 1) flag set, ("!f", 1) flag not set, ("i", 2) has item, ("!i", 2) has not."""
    return [{"k": "flag" if k.endswith("f") else "item", "id": i, "not": k.startswith("!")} for k, i in atoms]


def _a(*acts) -> list[dict]:
    """Template actions: ("say", "@key"), ("give", 1), ("set", 2), ("go", 3), ("end", 1) …"""
    return [{"k": k, "v": v} if k == "say" else {"k": k, "id": v} for k, v in acts]


def _ans(t, nxt=None, do=(), cond=()) -> dict:
    return {"t": t, "if": _c(*cond), "do": _a(*do), "next": nxt}


TEMPLATES: dict[str, dict] = {
    # 🧙 Escape from the wizard tower: chamber → stairway → library (dark until the candle is lit; the owl's riddle gives
    # the star crystal) and laboratory (the cauldron: a 💀 ending). Stick + crystal = magic wand → breaks the seal.
    "tower": {"emoji": "🧙", "color": 6, "game": {
        "start": 1,
        "items": [{"id": 1, "name": "@i1", "icon": {"k": "asset", "v": "stick"}}, {"id": 2, "name": "@i2", "icon": {"k": "asset", "v": "candle"}},
                  {"id": 3, "name": "@i3", "icon": {"k": "asset", "v": "crystal"}}, {"id": 4, "name": "@i4", "icon": {"k": "asset", "v": "wand"}}],
        "flags": [{"id": 1, "name": "@f1"}, {"id": 2, "name": "@f2"}, {"id": 3, "name": "@f3"}],
        "endings": [{"id": 1, "kind": "win", "text": "@e1"}, {"id": 2, "kind": "lose", "text": "@e2"}],
        "rooms": [
            {"id": 1, "name": "@r1", "text": "@r1t", "bg": {"k": "lib", "v": "tower"}, "variants": [], "spots": [
                _spot(11, "object", "@s11", (8, 52, 30, 30), "bed", "@s11l"),
                _spot(12, "object", "@s12", (44, 60, 18, 22), "chest", "@s12l", take=True, keep=True, item=1),
                _spot(13, "object", "@s13", (68, 48, 10, 20), "candle", "@s13l", take=True, item=2),
                _spot(14, "door", "@s14", (80, 22, 17, 58), "door", "@s14l", to=2)]},
            {"id": 2, "name": "@r2", "text": "@r2t", "bg": {"k": "lib", "v": "hall"}, "variants": [
                {"if": _c(("f", 2)), "text": "@r2v", "bg": None}], "spots": [
                _spot(21, "door", "@s21", (2, 30, 16, 50), "door", None, to=1),
                _spot(22, "door", "@s22", (24, 26, 16, 48), "door_arch", "@s22l", to=3),
                _spot(23, "door", "@s23", (60, 26, 16, 48), "door_arch", "@s23l", to=4),
                _spot(24, "door", "@s24", (80, 18, 19, 66), "door_metal", "@s24l", end=1, lock=_c(("f", 2)), locked="@s24k")]},
            {"id": 3, "name": "@r3", "text": "@r3t", "bg": {"k": "lib", "v": "dark"}, "variants": [
                {"if": _c(("f", 1)), "text": "@r3v", "bg": {"k": "lib", "v": "library"}}], "spots": [
                _spot(31, "object", "@s31", (6, 14, 30, 64), "bookshelf", "@s31l"),
                _spot(32, "object", "@s32", (44, 40, 12, 22), "lamp", "@s32l"),
                _spot(33, "person", "@s33", (62, 22, 22, 32), "owl", "@s33l", talk=1, **{"if": _c(("f", 1))}),
                _spot(34, "door", "@s34", (86, 30, 13, 50), "door_arch", None, to=2)]},
            {"id": 4, "name": "@r4", "text": "@r4t", "bg": {"k": "lib", "v": "lab"}, "variants": [], "spots": [
                _spot(41, "object", "@s41", (38, 50, 26, 34), "cauldron", "@s41l"),
                _spot(42, "person", "@s42", (6, 46, 18, 30), "cat", "@s42l", talk=4),
                _spot(43, "door", "@s43", (84, 30, 15, 50), "door_arch", None, to=2)]}],
        "lines": [
            {"id": 1, "text": "@l1", "answers": [_ans("@l1a", 2), _ans("@l1b")]},
            {"id": 2, "text": "@l2", "answers": [
                _ans("@l2a", 3, do=[("give", 3), ("set", 3)], cond=[("!f", 3)]), _ans("@l2b", 2, do=[("say", "@l2bs")]), _ans("@l2c")]},
            {"id": 3, "text": "@l3", "answers": [_ans("@l3a")]},
            {"id": 4, "text": "@l4", "answers": [_ans("@l4a", 5), _ans("@l4b")]},
            {"id": 5, "text": "@l5", "answers": [_ans("@l5a")]}],
        "rules": [
            {"id": 1, "kind": "use", "item": 2, "spot": 32, "if": _c(("!f", 1)), "do": _a(("set", 1), ("take", 2), ("say", "@u1"))},
            {"id": 2, "kind": "combine", "item": 1, "item2": 3, "if": [], "do": _a(("take", 1), ("take", 3), ("give", 4), ("say", "@u2"))},
            {"id": 3, "kind": "use", "item": 4, "spot": 24, "if": [], "do": _a(("set", 2), ("say", "@u3"))},
            {"id": 4, "kind": "use", "item": None, "spot": 41, "if": [], "do": _a(("say", "@u4"), ("end", 2))}]}},
    # 📦 The secret of the attic: kids' room (magnet + string = magnet line) → hallway (the cat knows where the key is) →
    # garden (fish the key out of the well; climbing in: 💀) → attic (the hatch needs the key; the trunk holds the secret).
    "attic": {"emoji": "📦", "color": 1, "game": {
        "start": 1,
        "items": [{"id": 1, "name": "@i1", "icon": {"k": "asset", "v": "magnet"}}, {"id": 2, "name": "@i2", "icon": {"k": "asset", "v": "rope"}},
                  {"id": 3, "name": "@i3", "icon": {"k": "emoji", "v": "🎣"}}, {"id": 4, "name": "@i4", "icon": {"k": "asset", "v": "key"}}],
        "flags": [{"id": 1, "name": "@f1"}, {"id": 2, "name": "@f2"}],
        "endings": [{"id": 1, "kind": "win", "text": "@e1"}, {"id": 2, "kind": "lose", "text": "@e2"}],
        "rooms": [
            {"id": 1, "name": "@r1", "text": "@r1t", "bg": {"k": "lib", "v": "kidsroom"}, "variants": [], "spots": [
                _spot(11, "object", "@s11", (40, 66, 16, 18), "box", "@s11l", take=True, keep=True, item=1),
                _spot(12, "object", "@s12", (66, 56, 22, 26), "table", "@s12l", take=True, keep=True, item=2),
                _spot(13, "object", "@s13", (63, 12, 26, 28), None, "@s13l"),
                _spot(14, "door", "@s14", (2, 20, 14, 60), "door", None, to=2)]},
            {"id": 2, "name": "@r2", "text": "@r2t", "bg": {"k": "lib", "v": "hallway"}, "variants": [
                {"if": _c(("f", 2)), "text": "@r2v", "bg": None}], "spots": [
                _spot(21, "door", "@s21", (4, 28, 15, 52), "door", None, to=1),
                _spot(22, "door", "@s22", (78, 28, 15, 52), "door", "@s22l", to=3),
                _spot(23, "door", "@s23", (38, 2, 24, 16), "hatch", "@s23l", to=4, lock=_c(("f", 2)), locked="@s23k"),
                _spot(24, "person", "@s24", (40, 58, 18, 24), "cat", "@s24l", talk=1)]},
            {"id": 3, "name": "@r3", "text": "@r3t", "bg": {"k": "lib", "v": "village"}, "variants": [], "spots": [
                _spot(31, "object", "@s31", (14, 52, 24, 34), "well", "@s31l"),
                _spot(32, "object", "@s32", (70, 64, 14, 22), "plant", "@s32l"),
                _spot(33, "door", "@s33", (88, 40, 11, 44), "door", None, to=2)]},
            {"id": 4, "name": "@r4", "text": "@r4t", "bg": {"k": "lib", "v": "attic"}, "variants": [], "spots": [
                _spot(41, "object", "@s41", (36, 58, 28, 26), "chest", "@s41l"),
                _spot(42, "person", "@s42", (70, 30, 18, 30), "ghost", "@s42l", talk=3),
                _spot(43, "door", "@s43", (4, 70, 22, 18), "hatch", None, to=2)]}],
        "lines": [
            {"id": 1, "text": "@l1", "answers": [_ans("@l1a", 2, do=[("set", 1)]), _ans("@l1b")]},
            {"id": 2, "text": "@l2", "answers": [_ans("@l2a")]},
            {"id": 3, "text": "@l3", "answers": [_ans("@l3a", 4), _ans("@l3b")]},
            {"id": 4, "text": "@l4", "answers": [_ans("@l4a")]}],
        "rules": [
            {"id": 1, "kind": "combine", "item": 1, "item2": 2, "if": [], "do": _a(("take", 1), ("take", 2), ("give", 3), ("say", "@u1"))},
            {"id": 2, "kind": "use", "item": 3, "spot": 31, "if": _c(("f", 1), ("!i", 4), ("!f", 2)), "do": _a(("give", 4), ("say", "@u2"))},
            {"id": 6, "kind": "use", "item": 3, "spot": 31, "if": [], "do": _a(("say", "@u6"))},
            {"id": 3, "kind": "use", "item": 4, "spot": 23, "if": [], "do": _a(("set", 2), ("take", 4), ("say", "@u3"))},
            {"id": 4, "kind": "use", "item": None, "spot": 31, "if": [], "do": _a(("say", "@u4"), ("end", 2))},
            {"id": 5, "kind": "use", "item": None, "spot": 41, "if": [], "do": _a(("say", "@u5"), ("end", 1))}]}},
    # 🚀 Lost in the spaceship: cabin (battery, tape) → corridor (the robot needs power, then it gives the key card) →
    # storage (a broken cable; tape + cable = repaired cable) → engine room (repair; the red button: 💀) → bridge (home!).
    "spaceship": {"emoji": "🚀", "color": 5, "game": {
        "start": 1,
        "items": [{"id": 1, "name": "@i1", "icon": {"k": "asset", "v": "battery"}}, {"id": 2, "name": "@i2", "icon": {"k": "emoji", "v": "🩹"}},
                  {"id": 3, "name": "@i3", "icon": {"k": "asset", "v": "cable"}}, {"id": 4, "name": "@i4", "icon": {"k": "emoji", "v": "🔌"}},
                  {"id": 5, "name": "@i5", "icon": {"k": "asset", "v": "card"}}],
        "flags": [{"id": 1, "name": "@f1"}, {"id": 2, "name": "@f2"}],
        "endings": [{"id": 1, "kind": "win", "text": "@e1"}, {"id": 2, "kind": "lose", "text": "@e2"}],
        "rooms": [
            {"id": 1, "name": "@r1", "text": "@r1t", "bg": {"k": "lib", "v": "cabin"}, "variants": [], "spots": [
                _spot(11, "object", "@s11", (6, 50, 34, 30), "bed", "@s11l"),
                _spot(12, "object", "@s12", (50, 56, 16, 24), "box", "@s12l", take=True, keep=True, item=1),
                _spot(13, "object", "@s13", (46, 10, 26, 30), "window", "@s13l"),
                _spot(14, "object", "@s14", (70, 66, 10, 12), None, "@s14l", take=True, item=2),
                _spot(15, "door", "@s15", (82, 24, 16, 58), "door_metal", None, to=2)]},
            {"id": 2, "name": "@r2", "text": "@r2t", "bg": {"k": "lib", "v": "corridor"}, "variants": [], "spots": [
                _spot(21, "door", "@s21", (2, 26, 15, 56), "door_metal", None, to=1),
                _spot(22, "door", "@s22", (22, 30, 13, 46), "door_metal", "@s22l", to=3),
                _spot(23, "door", "@s23", (65, 30, 13, 46), "door_metal", "@s23l", to=4),
                _spot(24, "door", "@s24", (83, 26, 15, 56), "door_metal", "@s24l", to=5, lock=_c(("i", 5)), locked="@s24k"),
                _spot(25, "person", "@s25", (40, 44, 18, 36), "robot", "@s25l", talk=1)]},
            {"id": 3, "name": "@r3", "text": "@r3t", "bg": {"k": "lib", "v": "storage"}, "variants": [], "spots": [
                _spot(31, "object", "@s31", (10, 46, 26, 36), "box", "@s31l", take=True, keep=True, item=3),
                _spot(32, "object", "@s32", (50, 24, 24, 30), "screen", "@s32l"),
                _spot(33, "door", "@s33", (86, 30, 13, 50), "door_metal", None, to=2)]},
            {"id": 4, "name": "@r4", "text": "@r4t", "bg": {"k": "lib", "v": "engine"}, "variants": [
                {"if": _c(("f", 2)), "text": "@r4v", "bg": None}], "spots": [
                _spot(41, "object", "@s41", (30, 20, 34, 44), "screen", "@s41l"),
                _spot(42, "object", "@s42", (72, 52, 12, 16), "button", "@s42l"),
                _spot(43, "door", "@s43", (2, 30, 13, 50), "door_metal", None, to=2)]},
            {"id": 5, "name": "@r5", "text": "@r5t", "bg": {"k": "lib", "v": "bridge"}, "variants": [], "spots": [
                _spot(51, "object", "@s51", (40, 56, 20, 20), "button", "@s51l"),
                _spot(52, "person", "@s52", (6, 42, 18, 36), "alien", "@s52l", talk=4),
                _spot(53, "door", "@s53", (84, 28, 15, 54), "door_metal", None, to=2)]}],
        "lines": [
            {"id": 1, "text": "@l1", "answers": [_ans("@l1a", 2, do=[("give", 5)], cond=[("f", 1)]), _ans("@l1c", 3, cond=[("!f", 1)]),
                                                 _ans("@l1b")]},
            {"id": 2, "text": "@l2", "answers": [_ans("@l2a")]},
            {"id": 3, "text": "@l3", "answers": [_ans("@l3a")]},
            {"id": 4, "text": "@l4", "answers": [_ans("@l4a", 5), _ans("@l4b")]},
            {"id": 5, "text": "@l5", "answers": [_ans("@l5a")]}],
        "rules": [
            {"id": 1, "kind": "use", "item": 1, "spot": 25, "if": [], "do": _a(("set", 1), ("take", 1), ("say", "@u1"))},
            {"id": 2, "kind": "combine", "item": 2, "item2": 3, "if": [], "do": _a(("take", 2), ("take", 3), ("give", 4), ("say", "@u2"))},
            {"id": 3, "kind": "use", "item": 4, "spot": 41, "if": [], "do": _a(("set", 2), ("take", 4), ("say", "@u3"))},
            {"id": 4, "kind": "use", "item": None, "spot": 42, "if": [], "do": _a(("say", "@u4"), ("end", 2))},
            {"id": 5, "kind": "use", "item": None, "spot": 51, "if": _c(("f", 2)), "do": _a(("say", "@u5"), ("end", 1))},
            {"id": 6, "kind": "use", "item": None, "spot": 51, "if": [], "do": _a(("say", "@u6"))}]}},
}
_TEXTS: dict | None = None


def template_texts() -> dict:
    global _TEXTS
    if _TEXTS is None:
        _TEXTS = json.loads((Path(__file__).parent / "adventuregame_templates.json").read_text(encoding="utf-8"))
    return _TEXTS


def _fill(v, tx: dict):
    if isinstance(v, str) and v.startswith("@"):
        return tx[v[1:]]
    if isinstance(v, list):
        return [_fill(x, tx) for x in v]
    if isinstance(v, dict):
        return {k: _fill(x, tx) for k, x in v.items()}
    return v


def template(key: str, lang: str) -> dict:
    """A template as a game in one language: {title, emoji, color, lang, data}."""
    from .stories import template_lang
    t = TEMPLATES.get(key)
    if not t:
        raise CommunityError("Unknown template")
    texts = template_texts()
    lang = lang if lang in texts else template_lang(lang)
    lang = lang if lang in texts else "en"
    tx = texts[lang][key]
    return {"title": tx["title"], "emoji": t["emoji"], "color": t["color"], "lang": lang, "data": clean(_fill(t["game"], tx))}


def templates(lang: str) -> list[dict]:
    return [{"key": k, "emoji": t["emoji"], "color": t["color"], "title": template(k, lang)["title"]} for k, t in TEMPLATES.items()]


# ---------------------------------------------------------------- file format (export, template for an AI, import)
AI_INSTRUCTIONS = [
    "This file belongs to Family Quest, a family app in Home Assistant. Children (about 6–14) and adults build and play "
    "point & click adventure games with it: rooms with a picture, hotspots to look at, take, talk to and use, items, "
    "switches, dialogues and endings.",
    "Your answer must be ONE JSON object in exactly this structure – no text before or after it, no Markdown code fence, "
    "no comments. Keep all keys that start with '_' unchanged (they only explain the format).",
    "If you got this file with a game (an export), change, extend or translate it as the user asks. If you got it as a "
    "template, replace the example game with a new game about the idea the user describes.",
    "A game is a list of 'rooms'. Every room has a 'background' (an id of '_backgrounds' or an own SVG, see "
    "'_svg_rules'), a short 'text' and 'hotspots': rectangles on the picture ('box': [x, y, width, height] in percent of "
    "the picture, 0–100; the picture is landscape 4:3). Put hotspots where the thing is on the background and do not "
    "let them cover each other much.",
    "Hotspots: 'door' (leads to a room or straight to an ending with 'goes_to'; can be locked with 'needs' – a list of "
    "conditions), 'object' (can be looked at; with 'takeable': true and 'item' it goes into the inventory) and "
    "'character' (talks: 'dialogue' = the id of the first dialogue line). Every hotspot can show a 'picture' "
    "('asset:<id>' of '_assets', one emoji or an own drawing {'svg': '<svg …>'} – square, transparent, see '_svg_rules') "
    "and be hidden until conditions hold ('visible_if').",
    "Conditions are strings: 'item:<id>' (the player has it), '!item:<id>' (has it not), 'flag:<id>' (the switch is on), "
    "'!flag:<id>'. A list of conditions means: all must hold. Actions ('do') are a list of objects: {'say': 'text'}, "
    "{'give': '<item id>'}, {'take': '<item id>'} (removes it), {'set': '<flag id>'}, {'clear': '<flag id>'}, "
    "{'go': '<room id>'}, {'end': '<ending id>'}.",
    "'rules' say what happens when the player uses an item on a hotspot ({'type': 'use', 'item': '<id>', 'on': "
    "'<hotspot id>'}; 'item': null for just using the hotspot, e.g. pulling a lever) or combines two items ({'type': "
    "'combine', 'items': ['<a>', '<b>']}) – with optional 'if' conditions and the actions 'do'. A key on a locked door needs "
    "no rule: the door opens when its 'needs' hold.",
    "Dialogue lines ('dialogue') have a 'text' (what the character says) and 2–4 'answers' {'text', optional 'if', "
    "optional 'do', 'next': the id of the next line or null to end the talk}. Every line needs at least one answer without "
    "'if' (e.g. 'Bye!').",
    "Rules the app checks: every id is unique; every door leads somewhere; at least one 'win' ending; every item that is "
    "needed can be got; the game can be won – the app plays every way through it. Aim for 3–8 rooms, 3–8 items, at least "
    "one locked door, one combination and one dialogue; one or two funny 'lose' endings are welcome.",
    "Suitable for children: exciting but never cruel; 'lose' endings are mild ('you fall asleep – try again'). Short "
    f"texts: names max. {NAME} characters, room texts max. {ROOM_TEXT}, look texts and dialogue lines max. {LOOK}, answers "
    f"max. {ANSWER}.",
    "Write in the language the user writes in (or the one they ask for) and set 'language' to it: one of "
    "en, de-DE, de-CH, fr-FR, it-IT, es-ES, nl-NL, pl-PL, pt-BR, sv-SE.",
]
AI_GUIDE = {
    "games[]": {
        "type": "Always 'adventure_game'.",
        "title": "Title of the game, max. 80 characters.",
        "emoji": "One emoji for the shelf.",
        "language": "Language of the texts (see the instructions).",
        "start": "The id of the room where the player starts.",
        "rooms": "The rooms (max. 40).", "items": "The items (max. 60): {'id', 'name', 'icon': 'asset:<id>', one emoji or {'svg': …}}.",
        "flags": "The switches (max. 100): {'id', 'name'} – e.g. 'light_on', 'dragon_sleeps'.",
        "endings": "{'id', 'type': 'win' | 'lose', 'text'} – what the player reads at the end.",
        "dialogue": "The dialogue lines (max. 200).", "rules": "Use and combine rules (max. 200).",
    },
    "rooms[]": {
        "id": "A short unique name, e.g. 'hall'.", "name": "Name shown to the player.", "text": "What the player sees in the room.",
        "background": "An id of '_backgrounds' or {'svg': '<svg …>'} (see '_svg_rules').",
        "variants": "Optional, max. 3: [{'if': [conditions], 'text': '…', 'background': …}] – the first that holds replaces "
                    "the text / picture (e.g. after the light is switched on).",
        "hotspots": "Max. 30 per room.",
    },
    "hotspots[]": {
        "id": "Unique in the whole game.", "kind": "'door', 'object' or 'character'.", "name": "Short name, e.g. 'Old chest'.",
        "box": "[x, y, width, height] in percent of the picture.", "picture": "Optional: 'asset:<id>', one emoji or {'svg': '<svg …>'} (see '_svg_rules').",
        "look": "Text when the player looks at it.", "visible_if": "Optional conditions.",
        "goes_to": "Doors: a room id or an ending id.", "needs": "Doors, optional: conditions to open it.",
        "locked_text": "Doors, optional: what the player reads when it is locked.",
        "takeable": "Objects: true if it goes into the inventory.", "item": "Objects that can be taken: the item id.",
        "stays": "Objects that can be taken, optional: true if the hotspot stays in the room and only gives its item (once) – "
                 "e.g. a chest with a key inside.",
        "dialogue": "Characters: the id of the first dialogue line.",
    },
}


def _cond_out(cond: list[dict], ids: dict) -> list[str]:
    return [("!" if a["not"] else "") + a["k"] + ":" + ids[a["k"]].get(a["id"], str(a["id"])) for a in cond]


def _art_out(p: dict | None) -> str | dict | None:
    if not p:
        return None
    if p["k"] == "asset":
        return "asset:" + p["v"]
    if p["k"] == "emoji":
        return p["v"]
    if p["k"] == "svg":
        return {"svg": p["v"]}
    return None                                          # photos (and old painted PNG drawings) are files of this family


def _bg_out(p: dict | None):
    if not p:
        return None
    if p["k"] == "lib":
        return p["v"]
    if p["k"] == "svg":
        return {"svg": p["v"]}
    return None


def export_game(title: str, emoji: str, lang: str, data: dict) -> dict:
    """A game in the file format – readable ids; own drawings (SVG) go along, photos stay out."""
    ids = {"room": {r["id"]: f"room{i + 1}" for i, r in enumerate(data["rooms"])},
           "item": {x["id"]: f"item{i + 1}" for i, x in enumerate(data["items"])},
           "flag": {x["id"]: f"flag{i + 1}" for i, x in enumerate(data["flags"])},
           "line": {x["id"]: f"line{i + 1}" for i, x in enumerate(data["lines"])},
           "end": {x["id"]: f"end{i + 1}" for i, x in enumerate(data["endings"])}}
    ids["spot"] = {s["id"]: f"spot{i + 1}" for i, s in enumerate(s for r in data["rooms"] for s in r["spots"])}
    act_key = {"give": "item", "take": "item", "set": "flag", "clear": "flag", "go": "room", "end": "end"}

    def do_out(do):
        return [{"say": a["v"]} if a["k"] == "say" else {a["k"]: ids[act_key[a["k"]]].get(a["id"], str(a["id"]))} for a in do]

    def keep(d: dict) -> dict:
        return {k: v for k, v in d.items() if v not in (None, [], "", False)}

    rooms = []
    for r in data["rooms"]:
        spots = []
        for s in r["spots"]:
            sp = {"id": ids["spot"][s["id"]], "kind": "character" if s["kind"] == "person" else s["kind"], "name": s["name"],
                  "box": [s["x"], s["y"], s["w"], s["h"]], "picture": _art_out(s["art"]), "look": s["look"],
                  "visible_if": _cond_out(s["if"], ids)}
            if s["kind"] == "door":
                sp.update({"goes_to": ids["end"].get(s["end"]) if s["end"] else ids["room"].get(s["to"]),
                           "needs": _cond_out(s["lock"], ids), "locked_text": s["locked"]})
            elif s["kind"] == "object":
                sp.update({"takeable": s["take"], "item": ids["item"].get(s["item"]) if s["take"] else None, "stays": s["take"] and s["keep"]})
            else:
                sp["dialogue"] = ids["line"].get(s["talk"])
            spots.append(keep(sp))
        rooms.append(keep({"id": ids["room"][r["id"]], "name": r["name"], "text": r["text"], "background": _bg_out(r["bg"]),
                           "variants": [keep({"if": _cond_out(v["if"], ids), "text": v["text"], "background": _bg_out(v["bg"])})
                                        for v in r["variants"]],
                           "hotspots": spots}))
    rules = []
    for rl in data["rules"]:
        if rl["kind"] == "use":
            r = {"type": "use", "item": ids["item"].get(rl["item"]) if rl["item"] else None, "on": ids["spot"].get(rl.get("spot"))}
        else:
            r = {"type": "combine", "items": [ids["item"].get(rl["item"]), ids["item"].get(rl.get("item2"))]}
        r.update({"if": _cond_out(rl["if"], ids), "do": do_out(rl["do"])})
        rules.append(r)
    return {"type": "adventure_game", "title": title, "emoji": emoji, "language": lang, "start": ids["room"].get(data["start"]),
            "rooms": rooms,
            "items": [keep({"id": ids["item"][x["id"]], "name": x["name"], "icon": _art_out(x["icon"])}) for x in data["items"]],
            "flags": [{"id": ids["flag"][x["id"]], "name": x["name"]} for x in data["flags"]],
            "endings": [{"id": ids["end"][x["id"]], "type": x["kind"], "text": x["text"]} for x in data["endings"]],
            "dialogue": [{"id": ids["line"][x["id"]], "text": x["text"],
                          "answers": [keep({"text": a["t"], "if": _cond_out(a["if"], ids), "do": do_out(a["do"]),
                                            "next": ids["line"].get(a["next"])}) for a in x["answers"]]} for x in data["lines"]],
            "rules": rules}


def document(games: list[dict], example: bool = False) -> dict:
    from .stories import BACKGROUNDS, SVG_EXAMPLE_SCENE, SVG_EXAMPLE_THING, svg_rules
    if example:
        t = template("tower", "en")
        games = [export_game(t["title"], t["emoji"], t["lang"], t["data"])]
        g = games[0]
        if len(g["rooms"]) > 1:                          # an own scene as the background of the second room
            g["rooms"][1]["background"] = {"svg": SVG_EXAMPLE_SCENE}
        if g["items"]:                                   # an own drawing as the picture of an item (transparent)
            g["items"][-1]["icon"] = {"svg": SVG_EXAMPLE_THING}
    return {"_format": FORMAT, "_ai_instructions": AI_INSTRUCTIONS, "_field_guide": AI_GUIDE, "_svg_rules": svg_rules("game"),
            "_backgrounds": {**BACKGROUNDS, **ROOMS}, "_assets": ASSETS,
            "_note": "Own drawings (SVG), library scenes, assets and emoji are part of the file, photos are not.", "games": games}


def is_game(doc_format, b: dict) -> bool:
    if "adventuregame" in str(doc_format or "").replace("_", "").replace("-", ""):
        return True
    t = str(b.get("type") or "").strip().lower().replace(" ", "_").replace("-", "_")
    return t in ("adventure_game", "adventuregame", "game", "point_and_click") or isinstance(b.get("rooms"), list)


def _art_in(v) -> dict | None:
    from .stories import EMOJI
    if isinstance(v, dict):
        if isinstance(v.get("svg"), str):
            return clean_art({"k": "svg", "v": v["svg"]}, None)
        v = v.get("asset") or v.get("emoji")
        if isinstance(v, str) and v in ASSETS:
            return {"k": "asset", "v": v}
    if not isinstance(v, str):
        return None
    s = v.strip()
    if s.startswith("<"):
        return clean_art({"k": "svg", "v": s}, None)
    if s.lower().startswith("asset:"):
        s = s[6:].strip()
        return {"k": "asset", "v": s} if s in ASSETS else None
    if s in ASSETS:
        return {"k": "asset", "v": s}
    return {"k": "emoji", "v": s} if s and len(s) <= EMOJI else None


def _bg_in(v) -> dict | None:
    from .stories import BACKGROUNDS
    if isinstance(v, dict):
        if isinstance(v.get("svg"), str):
            return clean_bg({"k": "svg", "v": v["svg"]}, None)
        v = v.get("library") or v.get("background")
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("<"):
            return clean_bg({"k": "svg", "v": s}, None)
        if s in BACKGROUNDS or s in ROOMS:
            return {"k": "lib", "v": s}
    return None


def import_game(b: dict) -> dict:
    """One game from a file or a pasted AI answer: {type, title, emoji, lang, data} – cleaned and limited; ids are the
    file's own names, mapped to numbers (anything that does not fit is left out, the checker shows what is missing)."""
    from .stories import EMOJI, LANGS, TITLE, template_lang
    seq: dict[str, dict[str, int]] = {k: {} for k in ("room", "spot", "item", "flag", "line", "end")}

    def num(kind: str, v, make: bool = True) -> int | None:
        if v is None or isinstance(v, (dict, list, bool)):
            return None
        k = str(v).strip()
        if not k:
            return None
        if k not in seq[kind] and make and len(seq[kind]) < 5000:
            seq[kind][k] = len(seq[kind]) + 1
        return seq[kind].get(k)

    def lst(v, limit: int) -> list:
        if not isinstance(v, list):
            return []
        if len(v) > limit:
            raise CommunityError("The game is too big for the app")
        return v

    def cond_in(c) -> list[dict]:
        if isinstance(c, (str, dict)):
            c = [c]
        out = []
        for a in c if isinstance(c, list) else []:
            if isinstance(a, dict):
                neg = bool(a.get("not")) or a.get("is") is False or a.get("has") is False
                kind = "item" if "item" in a else "flag" if "flag" in a else None
                if kind is None:
                    continue
                a = ("!" if neg else "") + kind + ":" + str(a[kind])
            if not isinstance(a, str):
                continue
            s = a.strip().replace(" ", "")
            neg = s.startswith(("!", "not:", "no:"))
            s = s.lstrip("!").removeprefix("not:").removeprefix("no:")
            kind, _, ref = s.partition(":")
            kind = {"item": "item", "has": "item", "flag": "flag", "switch": "flag"}.get(kind.lower())
            if kind and ref:
                out.append({"k": kind, "id": num(kind, ref), "not": neg})
        return out

    act_kind = {"give": "item", "take": "item", "remove": "item", "set": "flag", "clear": "flag", "unset": "flag", "go": "room",
                "end": "end", "win": "end", "lose": "end"}

    def do_in(d) -> list[dict]:
        out = []
        for a in d if isinstance(d, list) else [d] if isinstance(d, (dict, str)) else []:
            if isinstance(a, str):
                k, _, v = a.partition(":")
                a = {k.strip(): v.strip()}
            if not isinstance(a, dict):
                continue
            if "type" in a or "action" in a:
                k = str(a.get("type") or a.get("action")).lower()
                v = a.get("text") or a.get("value") or a.get("item") or a.get("flag") or a.get("room") or a.get("ending") or a.get("target")
                a = {k: v}
            for k, v in a.items():
                k = str(k).lower()
                if k in ("say", "text", "message", "show"):
                    out.append({"k": "say", "v": v})
                elif k in act_kind:
                    kk = {"remove": "take", "unset": "clear", "win": "end", "lose": "end"}.get(k, k)
                    out.append({"k": kk, "id": num(act_kind[k], v)})
                break
        return out

    for r in lst(b.get("rooms"), MAX_ROOMS):           # first all ids in the order of their lists (a round trip keeps the numbers),
        if isinstance(r, dict):                       # so «goes_to» knows whether it means a room or an ending
            num("room", r.get("id"))
    for key, kind, limit in (("items", "item", MAX_ITEMS), ("flags", "flag", MAX_FLAGS)):
        for x in lst(b.get(key), limit):
            if isinstance(x, dict):
                num(kind, x.get("id"))
    for e in lst(b.get("endings"), MAX_ENDINGS):
        if isinstance(e, dict):
            num("end", e.get("id"))
    lines_raw = lst(b.get("dialogue") if "dialogue" in b else b.get("lines"), MAX_LINES)
    for x in lines_raw:
        if isinstance(x, dict):
            num("line", x.get("id"))
    rooms = []
    for r in lst(b.get("rooms"), MAX_ROOMS):
        if not isinstance(r, dict):
            continue
        spots = []
        for s in lst(r.get("hotspots") if "hotspots" in r else r.get("spots"), MAX_SPOTS):
            if not isinstance(s, dict):
                continue
            kind = str(s.get("kind") or s.get("type") or "object").lower()
            kind = "person" if kind in ("character", "person", "npc") else "door" if kind in ("door", "exit") else "object"
            box = s.get("box") if isinstance(s.get("box"), list) and len(s.get("box")) == 4 else [s.get("x"), s.get("y"), s.get("w") or s.get("width"),
                                                                                                   s.get("h") or s.get("height")]
            to = s.get("goes_to") or s.get("to")
            sp = {"id": num("spot", s.get("id") or f"_spot{len(seq['spot'])}"), "kind": kind, "name": s.get("name"),
                  "x": box[0], "y": box[1], "w": box[2], "h": box[3], "art": _art_in(s.get("picture") or s.get("asset")),
                  "if": cond_in(s.get("visible_if") or s.get("if")), "look": s.get("look") or s.get("description"),
                  "to": num("room", to, False), "end": num("end", to, False) if num("room", to, False) is None else None,
                  "lock": cond_in(s.get("needs") or s.get("locked_until")), "locked": s.get("locked_text"),
                  "take": bool(s.get("takeable") or s.get("take")), "keep": bool(s.get("stays") or s.get("keep")), "item": num("item", s.get("item")),
                  "talk": num("line", s.get("dialogue") or s.get("talk"), False)}
            spots.append(sp)
        rooms.append({"id": num("room", r.get("id")), "name": r.get("name"), "text": r.get("text") or r.get("description"),
                      "bg": _bg_in(r.get("background")), "spots": spots,
                      "variants": [{"if": cond_in(v.get("if")), "text": v.get("text"), "bg": _bg_in(v.get("background"))}
                                   for v in lst(r.get("variants"), 50) if isinstance(v, dict)]})
    lines = [{"id": num("line", x.get("id")), "text": x.get("text"),
              "answers": [{"t": a.get("text"), "if": cond_in(a.get("if")), "do": do_in(a.get("do")), "next": num("line", a.get("next"), False)}
                          for a in lst(x.get("answers"), 50) if isinstance(a, dict)]}
             for x in lines_raw if isinstance(x, dict)]
    rules = []
    for rl in lst(b.get("rules"), MAX_RULES):
        if not isinstance(rl, dict):
            continue
        if str(rl.get("type") or rl.get("kind")).lower() == "combine":
            its = rl.get("items") if isinstance(rl.get("items"), list) else [rl.get("item"), rl.get("item2")]
            its = (its + [None, None])[:2]
            rules.append({"id": len(rules) + 1, "kind": "combine", "item": num("item", its[0]), "item2": num("item", its[1]),
                          "if": cond_in(rl.get("if")), "do": do_in(rl.get("do"))})
        else:
            rules.append({"id": len(rules) + 1, "kind": "use", "item": num("item", rl.get("item")) if rl.get("item") else None,
                          "spot": num("spot", rl.get("on") or rl.get("hotspot"), False), "if": cond_in(rl.get("if")), "do": do_in(rl.get("do"))})
    items = [{"id": num("item", x.get("id")), "name": x.get("name"), "icon": _art_in(x.get("icon"))}
             for x in lst(b.get("items"), MAX_ITEMS) if isinstance(x, dict)]
    known = {x["id"] for x in items}
    for k, i in seq["item"].items():                     # items only named in a hotspot or a rule
        if i not in known and len(items) < MAX_ITEMS:
            items.append({"id": i, "name": k.replace("_", " ")[:NAME], "icon": None})
    flags = [{"id": num("flag", x.get("id")), "name": x.get("name")} for x in lst(b.get("flags"), MAX_FLAGS) if isinstance(x, dict)]
    known = {x["id"] for x in flags}
    for k, i in seq["flag"].items():
        if i not in known and len(flags) < MAX_FLAGS:
            flags.append({"id": i, "name": k.replace("_", " ")[:NAME]})
    endings_ = [{"id": num("end", e.get("id")), "kind": "lose" if str(e.get("type") or e.get("kind")).lower() in ("lose", "bad", "bad_ending") else "win",
                 "text": e.get("text")} for e in lst(b.get("endings"), MAX_ENDINGS) if isinstance(e, dict)]
    data = clean({"start": num("room", b.get("start"), False), "rooms": rooms, "items": items, "flags": flags, "lines": lines,
                  "rules": rules, "endings": endings_})
    lang = b.get("language") if b.get("language") in LANGS else template_lang(str(b.get("language") or "en"))
    return {"type": "game", "title": _text(b.get("title"), TITLE) or "?", "emoji": _text(b.get("emoji"), EMOJI) or "🗝️", "lang": lang,
            "data": data}
