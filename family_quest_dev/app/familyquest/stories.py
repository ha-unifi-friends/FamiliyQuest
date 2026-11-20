"""Interactive books (formerly «adventure books»): stories children and parents write and the family reads like a
book – most pages simply go on, at a few pages the reader decides how the story continues.

A book is a list of pages. A page is a 📄 scene, a 🏆 good ending or a 💀 bad ending (bad endings are optional – every
ending of a book may be a happy one). A scene either goes on (`next`: the one page that follows, «Next ▶» in the
reader – a linear page) or is a branch point (`choices`: 2–4 choices A–D that each point to another page). Books of
older versions only have branch points – they stay valid. Paths may merge (two choices pointing to the same page) and
even go back. Items 🎒: a page can give one item («🍌 Banana»), a choice can need one – it is only shown to a reader
who has it.

Every book is in one language (`lang`, a tag – no translations inside a book). The author works on a working copy
(`data`); readers only ever see the published copy (`live`). Publishing checks the book (`check`): a linear page has
its next page, a branch point 2–4 choices with a target and one that needs no item, there is a good ending, every page
can be reached from the start and from every page a path leads to an ending.

Who reads it is the author's choice (`visibility`, «family» for new books, «me» for imported drafts):
- «me»: only the author – parents neither. Nobody else gets its title, text or pictures from any endpoint; in the
  parent area parents only see that a private book exists (author, page count, date) and cannot open, change or remove
  it. Never needs approval.
- «kids»: the children of the family (and the author). «family»: everybody.
With «approval» on (parent setting, off by default) a child's book for «kids» / «family» waits as `pending` until a
parent approves it; `approved` says that the published copy may be shown to the others. In the parent area (`oversee`:
the parent login without an app login) parents open every book that is not private (moderation); in the app everybody –
parents too – sees what the visibility allows. Parents edit, unpublish and remove books that are not private.
The author gets the writing reward once per book, when the others can first see it, and – per reader who is somebody
else – the reading reward once, when that reader reaches an ending for the first time.

Reading runs on the server (page, items, endings found per reader), so items cannot be cheated and every reader
collects own endings («2 of 5 endings found») and gives ⭐ after finishing a book. The pages a reader went through are
kept (`story_read.state` {"back": [[page, items], …]}), so ◀ turns back to the page actually read before (with the
backpack of then).

Pictures: an emoji, an own drawing or a photo. Own drawings are vector pictures of the drawing editor (web/svgpaint.js):
cleaned SVG text inside the book data ({"k": "svg", "v": "<svg …>"}, svgsafe.py – a picture on a page max. ART_MAX, a page
background max. BG_MAX), so they belong to the book: the same privacy, backups and export as its texts. Photos (and the
painted PNG drawings of older versions) are files in media/_stories (checked by their first bytes, max. IMAGE_MAX), named
after their content; files no book uses any more are removed after an hour. A page background is a library scene (its
key) or an own drawing ({"k": "svg", …}).

Book types (`type`, the badge and filter on the shelf): 📕 «picture» – picture books (picturebooks.py: pages with a
picture and a text, read page by page), 📖 «adventure» – the adventure books of this module, 🗝️ «game» – point & click
adventure games (adventuregame.py: rooms, hotspots, items, switches, dialogues; played on the server, state per player).
Visibility, approval, rewards, ratings, the parent area and privacy are the same for every type; only the content
(`clean` / `check`), reading and the file format differ. Sample books (`sample`: a key of picturebooks.SAMPLES) come with the app: author «Family Quest», visible to the
whole family in the reader's app language, never changed; parents hide them (settings «samples_off»).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from .community import CommunityError
from .i18n import _t

FOLDER = "_stories"
KINDS = ("scene", "good", "bad")
LANGS = ("en", "de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE")
MAX_BOOKS = 300
MAX_PER_AUTHOR = 60              # books of one person (one child cannot fill the family's shelf)
MAX_PAGES = 200
MAX_CHOICES = 4
MIN_CHOICES = 2
TITLE = 80
TEXT = 1500                     # characters of one page
CHOICE = 120
ITEM = 40
EMOJI = 16
MAX_BYTES = 2_000_000           # JSON of one book (own drawings included)
IMAGE_MAX = 2 * 1024 * 1024     # one picture (the app makes them smaller before the upload)
FOLDER_MAX = 300 * 1024 * 1024  # all pictures of all books
COLORS = 8
# backgrounds of a page (own SVG scenes in web/img/stories/<key>.svg) – English names (the app translates them)
BACKGROUNDS = {"jungle": "Jungle", "beach": "Beach and island", "deepsea": "Deep sea", "space": "Space and planets",
               "castle": "Haunted castle", "forest": "Enchanted forest", "mountains": "Snowy mountains", "desert": "Desert and pyramids",
               "pirate": "Pirate ship", "cave": "Crystal cave", "city": "City at night", "village": "Village and farm",
               "dragon": "Dragon's lair", "candy": "Candy land", "dino": "Dinosaur valley", "volcano": "Volcano",
               "northpole": "North Pole", "mine": "Underground mine", "clouds": "Castle in the clouds", "station": "Train station",
               "school": "School", "kidsroom": "Kids' room", "attic": "Attic", "lab": "Laboratory"}
VISIBILITY = ("me", "kids", "family")   # only the author (parents neither) · the children and the author · everybody
GC_EVERY = 3600                 # seconds between two picture clean-ups after autosaves (Stories._gc)
COVER_CACHE = 2000              # book texts whose shelf data is kept (Stories._cover_meta)
BACK_MAX = 300                  # pages a reader can turn back
IMG_NAME = re.compile(r"s-[0-9a-f]{16}\.(jpg|png|webp|gif)")
DEFAULT = {"off": [], "approval": False, "write_coins": 20, "write_xp": 0, "read_coins": 0, "read_xp": 0, "samples_off": []}
TYPES = ("picture", "adventure", "game")        # 📕 picture book · 📖 adventure book · 🗝️ adventure game
CREATABLE = ("picture", "adventure", "game")
TYPE_ICON = {"picture": "📕", "adventure": "📖", "game": "🗝️"}

# messages of the checker – English source text, the app translates them ({0} page, {1} choice letter, {2} item)
MSG = {
    "title": _t("Give the book a title"),
    "empty": _t("The book has no pages yet"),
    "start": _t("The first page must be a scene"),
    "no_text": _t("Page {0} has no text yet"),
    "dead_end": _t("Page {0} has no continuation"),
    "no_next": _t("Page {0}: choose the page that comes next"),
    "no_way_out": _t("Page {0}: from here no path leads to an ending"),
    "one_choice": _t("Page {0} needs at least 2 choices"),
    "no_target": _t("Page {0}: choice {1} has no target"),
    "choice_text": _t("Page {0}: choice {1} has no text"),
    "all_gated": _t("Page {0}: at least one choice must work without an item"),
    "item_never": _t("Page {0}: choice {1} needs «{2}», but no page gives it"),
    "no_good": _t("No good ending yet"),
    "unreachable": _t("Page {0} cannot be reached from the start"),
}


def can_see(prof: dict, author_id, visibility: str, oversee: bool = False) -> bool:
    """Who sees something of a family member (books here, programs of the Code Workshop codelab.py): the author always;
    «me» nobody else (parents neither); in the parent area (`oversee`) a parent everything that is not private; else
    «family» everybody and «kids» the children."""
    if author_id == prof["id"]:
        return True
    if visibility == "me":
        return False
    if oversee and prof.get("role") == "parent":
        return True
    return visibility == "family" or prof.get("role") != "parent"


def _text(v, n: int) -> str:
    return str(v or "").replace("\r\n", "\n").replace("\x00", "")[:n].strip()


def _int(v, lo: int, hi: int, default: int | None = None) -> int | None:
    try:
        i = int(v)
    except (TypeError, ValueError):
        return default
    return i if lo <= i <= hi else default


def clean_pic(p, folder: Path | None) -> dict | None:
    """A picture on a page: an emoji, an own drawing (SVG, max. ART_MAX) or an uploaded file (photo, older PNG drawing)."""
    if not isinstance(p, dict):
        return None
    if p.get("k") == "svg":
        from .svgsafe import ART_MAX, safe_svg
        svg = safe_svg(p.get("v"), ART_MAX)
        return {"k": "svg", "v": svg} if svg else None
    if p.get("k") == "emoji":
        v = _text(p.get("v"), EMOJI)
        return {"k": "emoji", "v": v} if v else None
    if p.get("k") == "img":
        v = str(p.get("v") or "")
        if not IMG_NAME.fullmatch(v) or (folder is not None and not (folder / v).is_file()):
            return None
        return {"k": "img", "v": v, "src": "draw" if p.get("src") == "draw" else "photo"}
    return None


def clean_bg(v) -> str | dict | None:
    """The background of a page: the key of a library scene – or an own drawing {"k": "svg", "v": …} (max. BG_MAX)."""
    if isinstance(v, str):
        return v if v in BACKGROUNDS else None
    if isinstance(v, dict):
        if v.get("k") == "lib":
            return v.get("v") if v.get("v") in BACKGROUNDS else None
        if v.get("k") == "svg":
            from .svgsafe import BG_MAX, safe_svg
            svg = safe_svg(v.get("v"), BG_MAX)
            return {"k": "svg", "v": svg} if svg else None
    return None


def clean(data, folder: Path | None = None) -> dict:
    """A valid book (working copy): every field checked and limited. Incomplete books are fine – `check` tells what
    is missing. Too many pages or too much text is refused."""
    if not isinstance(data, dict):
        data = {}
    raw = data.get("pages") if isinstance(data.get("pages"), list) else []
    if len(raw) > MAX_PAGES:
        raise CommunityError("A book can have at most 200 pages")
    pages, seen = [], set()
    for p in raw:
        if not isinstance(p, dict):
            continue
        pid = _int(p.get("id"), 1, 9999)
        if pid is None or pid in seen:
            continue
        seen.add(pid)
        kind = p.get("kind") if p.get("kind") in KINDS else "scene"
        out = {"id": pid, "kind": kind, "text": _text(p.get("text"), TEXT), "pic": clean_pic(p.get("pic"), folder),
               "bg": clean_bg(p.get("bg"))}
        if kind == "scene":
            give = _text(p.get("give"), ITEM)
            out["give"] = give or None
            ch = []
            for c in (p.get("choices") if isinstance(p.get("choices"), list) else [])[:MAX_CHOICES]:
                if not isinstance(c, dict):
                    continue
                ch.append({"t": _text(c.get("t"), CHOICE), "to": _int(c.get("to"), 1, 9999), "need": _text(c.get("need"), ITEM) or None})
            if "next" in p and not ch:                      # a linear page: goes on to one page («Next ▶»)
                out["next"] = _int(p.get("next"), 1, 9999)
            out["choices"] = ch
        pages.append(out)
    for p in pages:                                         # a target that is gone: the choice has no target
        for c in p.get("choices", []):
            if c["to"] not in seen:
                c["to"] = None
        if p.get("next") is not None and p["next"] not in seen:
            p["next"] = None
    start = _int(data.get("start"), 1, 9999)
    if start not in seen:
        start = pages[0]["id"] if pages else None
    out = {"start": start, "pages": pages}
    if len(json.dumps(out, ensure_ascii=False)) > MAX_BYTES:
        raise CommunityError("The book is too long – make some pages shorter")
    return out


def letter(i: int) -> str:
    return "ABCD"[i] if 0 <= i < 4 else str(i + 1)


def linear(p: dict) -> bool:
    """A scene that simply goes on to one page (no choice)."""
    return p.get("kind", "scene") == "scene" and "next" in p and not p.get("choices")


def targets(p: dict) -> list[int]:
    """The pages this page leads to: its next page or the targets of its choices."""
    if linear(p):
        return [p["next"]] if p.get("next") else []
    return [c["to"] for c in p.get("choices") or [] if c.get("to")]


def reachable(data: dict) -> set[int]:
    by = {p["id"]: p for p in data["pages"]}
    todo, seen = [data.get("start")], set()
    while todo:
        pid = todo.pop()
        if pid in seen or pid not in by:
            continue
        seen.add(pid)
        todo += targets(by[pid])
    return seen


def way_out(data: dict) -> set[int]:
    """The pages from which some path leads to an ending (items left aside)."""
    pages = data.get("pages") or []
    back: dict[int, list[int]] = {}
    for p in pages:
        for t in targets(p):
            back.setdefault(t, []).append(p["id"])
    todo = [p["id"] for p in pages if p.get("kind", "scene") != "scene"]
    seen: set[int] = set()
    while todo:
        pid = todo.pop()
        if pid in seen:
            continue
        seen.add(pid)
        todo += back.get(pid, [])
    return seen


def check(data: dict, title: str = "x") -> list[dict]:
    """What is still missing before the book can be published: [{msg, args, page}] – empty means ready.
    `page` is the page the problem is on (None: the whole book)."""
    out: list[dict] = []

    def add(key: str, page: int | None = None, *args) -> None:
        out.append({"code": key, "msg": MSG[key], "args": [str(a) for a in args], "page": page})

    if not str(title or "").strip():
        add("title")
    pages = data.get("pages") or []
    if not pages:
        add("empty")
        return out
    by = {p["id"]: p for p in pages}
    num = {p["id"]: i + 1 for i, p in enumerate(pages)}       # pages are numbered as they are listed
    if by.get(data.get("start"), {}).get("kind") != "scene":
        add("start", data.get("start"))
    given = {p.get("give") for p in pages if p.get("give")}
    for p in pages:
        n = num[p["id"]]
        if not p["text"]:
            add("no_text", p["id"], n)
        if p["kind"] != "scene":
            continue
        if linear(p):
            if not p.get("next") or p["next"] == p["id"]:
                add("no_next", p["id"], n)
            continue
        ch = p.get("choices") or []
        if not ch:
            add("dead_end", p["id"], n)
            continue
        if len(ch) < MIN_CHOICES:
            add("one_choice", p["id"], n)
        for i, c in enumerate(ch):
            if not c["t"]:
                add("choice_text", p["id"], n, letter(i))
            if not c["to"]:
                add("no_target", p["id"], n, letter(i))
            if c["need"] and c["need"] not in given:
                add("item_never", p["id"], n, letter(i), c["need"])
        if all(c["need"] for c in ch):
            add("all_gated", p["id"], n)
    if not any(p["kind"] == "good" for p in pages):
        add("no_good")
    reach, out_ok = reachable(data), way_out(data)
    for p in pages:
        if p["id"] not in reach:
            add("unreachable", p["id"], num[p["id"]])
    if any(p["kind"] != "scene" for p in pages):          # loops nobody gets out of (only when there is an ending at all)
        for p in pages:
            if p["id"] in reach and p["id"] not in out_ok and targets(p) and p["kind"] == "scene":
                add("no_way_out", p["id"], num[p["id"]])
    return out


def endings(data: dict | None) -> list[int]:
    if data and "rooms" in data:
        from .adventuregame import endings as game_endings
        return game_endings(data)
    return [p["id"] for p in (data or {}).get("pages", []) if p.get("kind", "scene") != "scene"]


def size_of(data: dict | None) -> int:
    """Pages of a book – rooms of a game."""
    data = data or {}
    return len(data["rooms"]) if "rooms" in data else len(data.get("pages") or [])


def cover_meta(kind: str, data: dict) -> dict:
    """What the shelf needs of a book (the published copy, else the working copy): cover, endings, start, pages."""
    data = data or {}
    if kind == "picture":
        return {"n": len(data.get("pages") or []), "cover": (data.get("cover") or {}).get("pic"), "cover_bg": None,
                "ends": [], "start": None, "scenes": []}
    if kind == "game":
        first = next((x for x in data.get("rooms") or [] if x["id"] == data.get("start")), None)
        bg = (first or {}).get("bg")
        return {"cover": bg if bg and bg["k"] in ("img", "svg") else None, "cover_bg": bg["v"] if bg and bg["k"] == "lib" else None,
                "ends": endings(data), "start": data.get("start"), "scenes": []}
    pages = data.get("pages") or []
    first = next((p for p in pages if p["id"] == data.get("start")), None)
    return {"cover": first["pic"] if first and first.get("pic") and first["pic"]["k"] in ("img", "svg") else None,
            "cover_bg": first.get("bg") if first else None, "ends": endings(data), "start": data.get("start"),
            "scenes": [p["id"] for p in pages if p.get("kind") == "scene"]}


def clean_as(kind: str, data, folder: Path | None = None) -> dict:
    """`clean` of the book type."""
    if kind == "picture":
        from . import picturebooks
        return picturebooks.clean(data, folder)
    if kind == "game":
        from . import adventuregame
        return adventuregame.clean(data, folder)
    return clean(data, folder)


def check_as(kind: str, data: dict, title: str = "x") -> list[dict]:
    """`check` of the book type."""
    if kind == "picture":
        from . import picturebooks
        return picturebooks.check(data, title)
    if kind == "game":
        from . import adventuregame
        return adventuregame.check(data, title)
    return check(data, title)


def blocking_as(kind: str, data: dict, title: str = "x") -> list[dict]:
    """The problems that stop publishing (games also have hints that do not)."""
    return [i for i in check_as(kind, data, title) if i.get("level", "error") == "error"]


def empty_book(kind: str) -> dict:
    if kind == "game":
        from .adventuregame import empty_game
        return empty_game()
    if kind == "picture":
        return {"cover": {"pic": None}, "pages": [{"id": 1, "layout": "top", "text": "", "pic": None}]}
    return {"start": 1, "pages": [{"id": 1, "kind": "scene", "text": "", "pic": None, "give": None, "next": None, "choices": []}]}


# ---------------------------------------------------------------- templates (texts in stories_templates.json)
# page: (id, kind, emoji, gives item key, [(target, needs item key), …] – or the id of the next page: a linear page)
# "bgs": the background of every page that is not in "bg"
TEMPLATES: dict[str, dict] = {
    "jungle": {"emoji": "🌴", "color": 3, "bgs": "jungle", "bg": {}, "pages": [
        (1, "scene", "🌴", None, [(2, None), (3, None)]),
        (2, "scene", "🍌", "banana", [(8, None), (3, None)]),
        (3, "scene", "🦁", None, [(4, None), (5, None), (6, None), (7, "banana")]),
        (4, "bad", "🌳", None, []),
        (5, "scene", "😴", None, [(9, None), (4, None)]),
        (6, "scene", "🦜", None, [(9, None), (4, None)]),
        (7, "good", "🦁", None, []),
        (8, "bad", "🐊", None, []),
        (9, "good", "🛕", None, []),
    ]},
    "space": {"emoji": "🚀", "color": 5, "bgs": "space", "bg": {3: "desert", 4: "desert", 5: "desert", 7: "kidsroom"}, "pages": [
        (1, "scene", "🚀", None, [(2, None), (3, None)]),
        (2, "scene", "🌕", "stone", [(3, None), (6, None)]),
        (3, "scene", "👽", None, [(4, None), (5, None), (8, "stone")]),
        (4, "scene", "🛸", None, [(8, None), (7, None)]),
        (5, "bad", "🪨", None, []),
        (6, "bad", "🌑", None, []),
        (7, "good", "📸", None, []),
        (8, "good", "🌌", None, []),
    ]},
    "castle": {"emoji": "🏰", "color": 7, "bgs": "castle", "bg": {2: "attic", 3: "cave", 5: "attic", 7: "attic"}, "pages": [
        (1, "scene", "🏰", None, [(2, None), (3, None)]),
        (2, "scene", "🕯️", None, [(4, None), (5, None)]),
        (3, "scene", "🦇", None, [(2, None), (6, None)]),
        (4, "scene", "👻", None, [(7, "key"), (8, None), (9, None)]),
        (5, "scene", "📚", "key", [(4, None), (6, None)]),
        (6, "bad", "💦", None, []),
        (7, "good", "🍫", None, []),
        (8, "bad", "😱", None, []),
        (9, "good", "🙈", None, []),
    ]},
    "sea": {"emoji": "🐠", "color": 4, "bgs": "deepsea", "bg": {1: "beach", 4: "pirate", 6: "beach", 7: "pirate"}, "pages": [
        (1, "scene", "🤿", None, [(2, None), (3, None)]),
        (2, "scene", "🪸", "shell", [(4, None), (3, None)]),
        (3, "scene", "🐙", None, [(5, "shell"), (6, None), (8, None)]),
        (4, "scene", "🐢", None, [(7, None), (3, None)]),
        (5, "good", "🧜", None, []),
        (6, "bad", "🩴", None, []),
        (7, "good", "💰", None, []),
        (8, "bad", "🖤", None, []),
    ]},
    # interactive books: most pages go on, two branch points, only happy endings
    "princess": {"emoji": "👸", "color": 2, "bgs": "clouds", "bg": {4: "forest", 5: "forest", 6: "forest", 7: "mountains", 8: "dragon",
                                                                  9: "dragon", 10: "dragon", 13: "village", 14: "village"}, "pages": [
        (1, "scene", "👸", None, 2),
        (2, "scene", "🤴", None, 3),
        (3, "scene", "🌙", None, [(4, None), (7, None), (12, None)]),
        (4, "scene", "🌹", None, 5),
        (5, "scene", "👑", None, 6),
        (6, "good", "💞", None, []),
        (7, "scene", "⛰️", None, 8),
        (8, "scene", "🐉", None, 9),
        (9, "scene", "🥺", None, [(10, None), (4, None)]),
        (10, "scene", "🐲", None, 11),
        (11, "good", "🐉", None, []),
        (12, "scene", "🥖", None, 13),
        (13, "scene", "🥐", None, 14),
        (14, "good", "🎂", None, []),
    ]},
    "fox": {"emoji": "🦊", "color": 1, "bgs": "forest", "bg": {4: "village", 5: "mountains", 10: "candy", 13: "candy"}, "pages": [
        (1, "scene", "🦊", None, 2),
        (2, "scene", "🎈", None, 3),
        (3, "scene", "💌", None, [(4, None), (5, None), (6, None)]),
        (4, "scene", "🐰", None, 7),
        (5, "scene", "🐻", None, 7),
        (6, "scene", "🦔", None, 7),
        (7, "scene", "🎂", None, [(8, None), (9, None), (10, None)]),
        (8, "scene", "🥕", None, 11),
        (9, "scene", "🍯", None, 12),
        (10, "scene", "🍓", None, 13),
        (11, "good", "🎉", None, []),
        (12, "good", "🥳", None, []),
        (13, "good", "🍰", None, []),
    ]},
}
_TEXTS: dict | None = None


def template_texts() -> dict:
    global _TEXTS
    if _TEXTS is None:
        _TEXTS = json.loads((Path(__file__).parent / "stories_templates.json").read_text(encoding="utf-8"))
    return _TEXTS


def template_lang(lang: str) -> str:
    texts = template_texts()
    if lang in texts:
        return lang
    base = str(lang or "").split("-")[0]
    return next((k for k in texts if k.split("-")[0] == base), "en")


def template(key: str, lang: str) -> dict:
    """A template as a book in one language: {title, emoji, color, lang, data}."""
    t = TEMPLATES.get(key)
    if not t:
        raise CommunityError("Unknown template")
    lang = template_lang(lang)
    tx = template_texts()[lang][key]
    pages = []
    for pid, kind, emoji, give, choices in t["pages"]:
        p = {"id": pid, "kind": kind, "text": tx[f"p{pid}"], "pic": {"k": "emoji", "v": emoji}, "bg": t["bg"].get(pid, t["bgs"])}
        if kind == "scene" and isinstance(choices, int):
            p.update(give=tx["items"][give] if give else None, next=choices, choices=[])
        elif kind == "scene":
            p["give"] = tx["items"][give] if give else None
            p["choices"] = [{"t": tx[f"p{pid}{letter(i).lower()}"], "to": to, "need": tx["items"][need] if need else None}
                            for i, (to, need) in enumerate(choices)]
        pages.append(p)
    return {"title": tx["title"], "emoji": t["emoji"], "color": t["color"], "lang": lang, "data": {"start": 1, "pages": pages}}


def templates(lang: str) -> list[dict]:
    lang = template_lang(lang)
    return [{"key": k, "emoji": t["emoji"], "color": t["color"], "title": template_texts()[lang][k]["title"]} for k, t in TEMPLATES.items()]


# ---------------------------------------------------------------- file format (export, template for an AI, import)
STORY_FORMAT = "family-quest-story/1"
IMPORT_MAX = 4_000_000            # characters of a pasted answer / file (own drawings included)
IMPORT_BOOKS = 5                  # books in one file
_KIND_OUT = {"scene": "scene", "good": "good_ending", "bad": "bad_ending"}
_KIND_IN = {v: k for k, v in _KIND_OUT.items()} | {"good": "good", "bad": "bad", "ending": "good"}
AI_INSTRUCTIONS = [
    "This file belongs to Family Quest, a family app in Home Assistant. Children (about 4–14) and adults write and read "
    "interactive books with it: stories that read like a book, and at a few pages the reader decides how it goes on.",
    "Your answer must be ONE JSON object in exactly this structure – no text before or after it, no Markdown code fence, "
    "no comments. Keep all keys that start with '_' unchanged (they only explain the format).",
    "If you got this file with a book (an export), change, extend or translate it as the user asks. If you got it as a "
    "template, replace the example book with a new book about the idea the user describes.",
    "A book is a list of pages. 'scene' pages tell what happens. MOST scenes simply go on like a book: they have 'next' = "
    "the 'id' of the page that follows (the reader taps «Next ▶») and no choices. A FEW scenes are branch points: "
    "instead of 'next' they offer 2 to 4 'choices'; each choice leads to another page ('goes_to' = the 'id' of that page). "
    "'good_ending' and 'bad_ending' pages end the story and have neither 'next' nor choices.",
    "Rules (the app checks them): the first page in 'start' is a scene; every scene has EITHER 'next' (a page that "
    "exists, not itself) OR 2–4 choices, every choice has a short text and a 'goes_to' that exists; at least one good "
    "ending; every page can be reached from the start; from every page a path leads to an ending (no endless loops); "
    "paths may meet again (two choices may lead to the same page). Aim for 10–20 pages with 2–4 branch points – the "
    "pages in between go on with 'next' – and 2–5 endings. Several endings may all be happy ones; bad endings are "
    "optional.",
    "Items (optional, keep it simple): a scene can give ONE item with 'gives' (an emoji and a short name, e.g. "
    "'🍌 Banana'). A choice can need an item with 'needs' (exactly the same text); it is only shown to readers who have "
    "it. Every scene needs at least one choice without 'needs', and only use items that some page gives.",
    "Pictures: 'picture' is ONE emoji per page or an own drawing {'svg': '<svg …>'} (a thing or a character on a "
    "transparent background, see '_svg_rules'). 'background' is one id from '_backgrounds', an own drawing {'svg': …} "
    "(a whole scene, see '_svg_rules') or left out. No images, no links.",
    "Suitable for children: exciting but never cruel or scary in a bad way; bad endings are funny or mild ('you have to "
    "walk home wet'). Short sentences; max. 1500 characters per page, 120 per choice, 40 per item, 80 for the title.",
    "Write in the language the user writes in (or the one they ask for) and set 'language' to it: one of " + ", ".join(LANGS) + ".",
]
AI_GUIDE = {
    "books[]": {
        "title": "Title of the book, max. 80 characters.",
        "emoji": "One emoji for the cover.",
        "language": "Language of the texts: " + ", ".join(LANGS) + ".",
        "start": "The 'id' of the first page (a scene).",
        "pages": "The pages, in any order. Every page has 'id', 'type' and 'text'.",
    },
    "pages[]": {
        "id": "A short unique name of the page, e.g. 'p1' or 'lion'.",
        "type": "'scene', 'good_ending' or 'bad_ending'.",
        "text": "What happens on this page.",
        "picture": "One emoji or {'svg': '<svg …>'} (optional, see '_svg_rules').",
        "background": "One background id from '_backgrounds' or {'svg': '<svg …>'} (optional, see '_svg_rules').",
        "gives": "Scenes only, optional: the item the reader finds here, e.g. '🗝️ Old key'.",
        "next": "Scenes that simply go on (most of them): the 'id' of the page that follows. Leave out 'choices' then.",
        "choices": "Branch points only (instead of 'next'): 2–4 choices {'text', 'goes_to', optional 'needs'}.",
    },
}


def svg_rules(kind: str) -> list[str]:
    """The rules for own SVG drawings in a file (`_svg_rules`) – the same for every book type, the sizes of svgsafe.py."""
    from .svgsafe import ART_MAX, BG_MAX
    where = {"adventure": "a page 'background'", "picture": "a page 'picture' or the cover", "game": "a room 'background'"}[kind]
    thing = {"adventure": "a page 'picture'", "picture": "not used in picture books",
             "game": "the 'picture' of a hotspot or an item"}[kind]
    return [
        "An own drawing is ONE <svg> element as a JSON string inside {'svg': '…'}. Use single quotes inside it so the JSON "
        "stays valid, and always give a viewBox.",
        f"Scenes – {where}: viewBox='0 0 800 600' (landscape 4:3). Paint the whole area (sky, wall, floor …) as the first "
        f"shape, so it works on light and dark screens. Max. {BG_MAX // 1000} KB after cleaning – aim for 2–12 KB.",
        f"Things and characters – {thing}: viewBox='0 0 200 200' (square), NO background: leave the area around it "
        f"transparent so it stands in the scene. Max. {ART_MAX // 1000} KB – aim for 1–5 KB.",
        "Allowed: svg, g, path, rect, circle, ellipse, line, polyline, polygon, defs, linearGradient, radialGradient, stop, "
        "clipPath and text (a word at most). Attributes: fill, stroke, stroke-width, stroke-linecap, stroke-linejoin, "
        "opacity, fill-opacity, transform, points, d, x/y/width/height, cx/cy/r/rx/ry, gradient stops, id (for "
        "fill='url(#id)' inside the same picture). Colours as #hex or names.",
        "Not allowed (removed, or the picture is refused): script, foreignObject, image, use, style elements and style "
        "attributes, class, links (href), events (onload, onclick …), animation, external files or fonts, DOCTYPE, "
        "entities, CSS, data: URLs.",
        "Flat, simple shapes with few points look best and stay small. No text-heavy pictures – the story text is on the "
        "page. Keep characters the same (colours, clothes) wherever they appear.",
    ]


SVG_EXAMPLE_THING = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><path d='M60 150 Q40 70 120 40 Q100 100 150 "
                     "150 Z' fill='#fcc419' stroke='#8d5524' stroke-width='6' stroke-linejoin='round'/><path d='M120 40 l12 -14' "
                     "stroke='#8d5524' stroke-width='8' stroke-linecap='round'/></svg>")
SVG_EXAMPLE_CARROT = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><path d='M100 62 Q128 52 138 66 L106 186 Q100 "
                      "192 94 186 L62 66 Q72 52 100 62 Z' fill='#f76707' stroke='#c2410c' stroke-width='6' stroke-linejoin='round'/>"
                      "<path d='M100 60 Q84 28 66 18 M100 60 Q100 26 100 12 M100 60 Q116 28 134 18' fill='none' stroke='#2f9e44' "
                      "stroke-width='10' stroke-linecap='round'/><path d='M80 100 h18 M86 130 h16 M92 158 h10' stroke='#c2410c' "
                      "stroke-width='5' stroke-linecap='round'/></svg>")
SVG_EXAMPLE_SCENE = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 600'><defs><linearGradient id='sky' x1='0' y1='0' "
                     "x2='0' y2='1'><stop offset='0' stop-color='#74c0fc'/><stop offset='1' stop-color='#d0ebff'/></linearGradient>"
                     "</defs><rect width='800' height='600' fill='url(#sky)'/><circle cx='660' cy='110' r='60' fill='#ffd43b'/>"
                     "<path d='M0 430 Q200 360 400 420 T800 400 V600 H0 Z' fill='#2f9e44'/><path d='M120 430 v-120' stroke='#8d5524' "
                     "stroke-width='26'/><ellipse cx='120' cy='290' rx='80' ry='60' fill='#37b24d'/></svg>")


def export_pic(p: dict | None):
    """A picture of a page in the file format: an emoji – or {'svg': …} for an own drawing; photos stay out."""
    if not p:
        return None
    if p["k"] == "emoji":
        return p["v"]
    if p["k"] == "svg":
        return {"svg": p["v"]}
    return None                                  # photos (and old painted PNG drawings) are files of this family


def export_bg(bg):
    if isinstance(bg, dict):
        return {"svg": bg["v"]} if bg.get("k") == "svg" else None
    return bg or None


def import_pic(v) -> dict | None:
    if isinstance(v, dict):
        if isinstance(v.get("svg"), str):
            return clean_pic({"k": "svg", "v": v["svg"]}, None)
        v = v.get("emoji")
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    if s.startswith("<"):
        return clean_pic({"k": "svg", "v": s}, None)
    return {"k": "emoji", "v": s} if len(s) <= EMOJI else None


def import_bg(v):
    if isinstance(v, dict):
        if isinstance(v.get("svg"), str):
            return clean_bg({"k": "svg", "v": v["svg"]})
        v = v.get("library") or v.get("background")
    if isinstance(v, str):
        s = v.strip()
        return clean_bg({"k": "svg", "v": s}) if s.startswith("<") else clean_bg(s)
    return None


def export_book(title: str, emoji: str, lang: str, data: dict) -> dict:
    """A book in the file format. Own drawings (SVG) go along; photos stay out (they are files of this family)."""
    ids = {p["id"]: f"p{i + 1}" for i, p in enumerate(data.get("pages") or [])}
    pages = []
    for p in data.get("pages") or []:
        out = {"id": ids[p["id"]], "type": _KIND_OUT[p["kind"]], "text": p["text"]}
        pic, bg = export_pic(p.get("pic")), export_bg(p.get("bg"))
        if pic:
            out["picture"] = pic
        if bg:
            out["background"] = bg
        if p["kind"] == "scene":
            if p.get("give"):
                out["gives"] = p["give"]
            if linear(p):
                out["next"] = ids.get(p.get("next"))
                pages.append(out)
                continue
            out["choices"] = [{k: v for k, v in (("text", c["t"]), ("goes_to", ids.get(c["to"])), ("needs", c["need"])) if v is not None}
                              for c in p.get("choices") or []]
        pages.append(out)
    return {"title": title, "emoji": emoji, "language": lang, "start": ids.get(data.get("start")), "pages": pages}


def story_document(books: list[dict], example: bool = False) -> dict:
    if example:                                    # a mostly linear book with two branch points and three happy endings
        t = template("fox", "en")
        books = [export_book(t["title"], t["emoji"], t["lang"], t["data"])]
        books[0]["pages"][7]["picture"] = {"svg": SVG_EXAMPLE_CARROT}         # the carrot cake page: an own drawing (a thing)
        books[0]["pages"][0]["background"] = {"svg": SVG_EXAMPLE_SCENE}       # the first page: an own scene
    return {"_format": STORY_FORMAT, "_ai_instructions": AI_INSTRUCTIONS, "_field_guide": AI_GUIDE, "_svg_rules": svg_rules("adventure"),
            "_backgrounds": BACKGROUNDS, "_note": "Own drawings (SVG) are part of the file, photos are not.",
            "books": books}


def import_books(text) -> list[dict]:
    """Books from a file or a pasted AI answer (JSON, also in a code fence with sentences around it): [{type, title,
    emoji, lang, data}] – cleaned and limited; ids, authors and anything else from the file are not trusted.
    Adventure books (family-quest-story/1), picture books (family-quest-picturebook/1) and adventure games
    (family-quest-adventuregame/1) – also together in one file."""
    from . import picturebooks
    from .ai_format import strip_meta
    from .jsonish import loads
    if not isinstance(text, str) or not text.strip():
        raise CommunityError("The file is empty – choose the JSON file of the AI")
    if len(text) > IMPORT_MAX:
        raise CommunityError("The file is too large")
    try:
        doc = loads(text)
        fmt = doc.get("_format") if isinstance(doc, dict) else None
        doc = strip_meta(doc)
    except (ValueError, RecursionError):
        raise CommunityError("No book found – is it the JSON of an adventure book?") from None
    from . import adventuregame
    raw = doc.get("books") if isinstance(doc, dict) and isinstance(doc.get("books"), list) else \
        doc.get("games") if isinstance(doc, dict) and isinstance(doc.get("games"), list) else [doc] if isinstance(doc, dict) else doc
    if not isinstance(raw, list):
        raw = []
    out = []
    for b in raw[:IMPORT_BOOKS]:
        if isinstance(b, dict) and isinstance(b.get("rooms"), list) and adventuregame.is_game(fmt, b):
            g = adventuregame.import_game(b)
            if g["data"]["rooms"]:
                out.append(g)
            continue
        if not isinstance(b, dict) or not isinstance(b.get("pages"), list):
            continue
        if picturebooks.is_picture_book(fmt, b):
            pb = picturebooks.import_book(b)
            if pb["data"]["pages"]:
                out.append(pb)
            continue
        if len(b["pages"]) > MAX_PAGES:
            raise CommunityError("A book can have at most 200 pages")
        ids: dict[str, int] = {}
        for p in b["pages"]:
            if isinstance(p, dict) and str(p.get("id")) not in ids and len(ids) < MAX_PAGES:
                ids[str(p.get("id"))] = len(ids) + 1
        pages, seen = [], set()
        for p in b["pages"]:
            if not isinstance(p, dict) or ids.get(str(p.get("id"))) in seen:
                continue
            pid = ids[str(p.get("id"))]
            seen.add(pid)
            kind = _KIND_IN.get(str(p.get("type") or p.get("kind") or "scene").strip().lower(), "scene")
            page = {"id": pid, "kind": kind, "text": p.get("text"), "bg": import_bg(p.get("background")), "pic": import_pic(p.get("picture"))}
            if kind == "scene":
                page["give"] = p.get("gives") if isinstance(p.get("gives"), str) else None
                page["choices"] = [{"t": c.get("text"), "to": ids.get(str(c.get("goes_to"))),
                                    "need": c.get("needs") if isinstance(c.get("needs"), str) else None}
                                   for c in (p.get("choices") if isinstance(p.get("choices"), list) else []) if isinstance(c, dict)]
                nxt = p.get("next", p.get("goes_to"))          # a linear page (family-quest-story/1 since the interactive books)
                if not page["choices"] and nxt is not None:
                    page["next"] = ids.get(str(nxt))
            pages.append(page)
        if not pages:
            continue
        lang = b.get("language") if b.get("language") in LANGS else template_lang(str(b.get("language") or "en"))
        title = _text(b.get("title"), TITLE) or "?"
        out.append({"type": "adventure", "title": title, "emoji": _text(b.get("emoji"), EMOJI) or "📖", "lang": lang,
                    "data": clean({"start": ids.get(str(b.get("start"))), "pages": pages})})
    if not out:
        raise CommunityError("No book found – is it the JSON of an adventure book?")
    return out


# ---------------------------------------------------------------- the books
class Stories:
    def __init__(self, db, rewards, media_dir: Path):
        self.db = db
        self.rewards = rewards
        self.folder = Path(media_dir) / FOLDER
        # may this person play and write adventure games (parent area › Games: «Adventure games» active for the child)?
        self.games_ok = lambda prof: True
        self._covers: dict[tuple, dict] = {}     # _cover_meta: what the shelf shows of a book text
        self._gc_at = 0.0                        # last picture clean-up (_gc)

    def _types(self, prof: dict) -> tuple:
        """The book types this person sees and writes – adventure games only while that game is open to them."""
        return TYPES if self.games_ok(prof) else tuple(t for t in TYPES if t != "game")

    def _need_type(self, prof: dict, kind: str) -> None:
        if kind == "game" and not self.games_ok(prof):
            raise CommunityError("Adventure games are switched off for you")

    # ---------------------------------------------------------------- settings
    @staticmethod
    def _clean_settings(d: dict, s: dict) -> dict:
        from .picturebooks import SAMPLES
        s = dict(s)
        if isinstance(d.get("off"), list):
            s["off"] = sorted({int(x) for x in d["off"] if isinstance(x, int) or str(x).isdecimal()})
        if "approval" in d:
            s["approval"] = bool(d["approval"])
        if isinstance(d.get("samples_off"), list):
            s["samples_off"] = sorted({x for x in d["samples_off"] if x in SAMPLES})
        for k in ("write_coins", "write_xp", "read_coins", "read_xp"):
            if k in d and d[k] is not None:
                s[k] = _int(d[k], 0, 10000, s[k])
        return s

    def settings(self) -> dict:
        got = self.db.get_setting("stories")
        return self._clean_settings(got if isinstance(got, dict) else {}, DEFAULT)

    def save_settings(self, d: dict) -> dict:
        s = self._clean_settings(d if isinstance(d, dict) else {}, self.settings())
        self.db.set_setting("stories", s)
        return s

    def enabled_for(self, prof: dict) -> bool:
        return prof.get("role") == "parent" or prof["id"] not in self.settings()["off"]

    def _need(self, prof: dict) -> None:
        if not self.enabled_for(prof):
            raise CommunityError("Adventure books are switched off for you")

    @staticmethod
    def _parent(prof: dict) -> bool:
        return prof.get("role") == "parent"

    def _book(self, sid: int) -> dict:
        b = self.db.q1("SELECT * FROM story WHERE id=?", sid)
        if not b:
            raise CommunityError("Unknown book")
        return b

    def _approval(self, prof: dict) -> bool:
        """Does a change by this person need a parent's approval before the others see it?"""
        return self.settings()["approval"] and not self._parent(prof)

    @staticmethod
    def _private(prof: dict, b: dict) -> bool:
        """A private book of somebody else: nothing of it for this person (parents neither)."""
        return b["visibility"] == "me" and b["author_id"] != prof["id"]

    def visible(self, prof: dict, b: dict, oversee: bool = False) -> bool:
        """May this person read the published copy? The author always; a parent in the parent area every book that
        is not private; the others what the visibility allows (once approved). A hidden sample book: nobody."""
        if b.get("sample"):
            return b["sample"] not in self.settings()["samples_off"]
        if b["author_id"] == prof["id"] or b["visibility"] == "me" or (oversee and self._parent(prof)):
            return can_see(prof, b["author_id"], b["visibility"], oversee)
        if not b["live"] or not b["approved"]:
            return False
        return can_see(prof, b["author_id"], b["visibility"])

    def _shared(self, sid: int) -> None:
        """The others can see it now: the writing reward, once per book."""
        b = self._book(sid)
        if b["live"] and b["approved"] and b["visibility"] != "me" and not b["rewarded"] and b["author_id"]:
            self.db.x("UPDATE story SET rewarded=1 WHERE id=?", sid)
            s = self.settings()
            self._pay(b["author_id"], s["write_coins"], s["write_xp"], "story_written", f"{TYPE_ICON.get(b['type'], '📖')} {b['title']}",
                      f"story:{sid}:written")

    def _may_edit(self, prof: dict, b: dict) -> bool:
        if b.get("sample"):
            return False
        return b["author_id"] == prof["id"] or (self._parent(prof) and b["visibility"] != "me")

    def _edit(self, prof: dict, sid: int) -> dict:
        self._need(prof)
        b = self._book(sid)
        self._need_type(prof, b["type"])
        if b.get("sample"):
            raise CommunityError("The sample book cannot be changed")
        if self._private(prof, b):
            raise CommunityError("Only the author can open this book")
        if not self._may_edit(prof, b):
            raise CommunityError("Only the author or a parent can change this book")
        return b

    def _people(self) -> dict[int, dict]:
        return {p["id"]: {"id": p["id"], "name": p["name"], "avatar": json.loads(p["avatar"] or "{}"), "role": p["role"]}
                for p in self.db.q("SELECT id, name, avatar, role FROM profile")}

    @staticmethod
    def _meta(title, emoji, color, lang) -> dict:
        out = {}
        if title is not None:
            out["title"] = _text(title, TITLE)
        if emoji is not None:
            out["emoji"] = _text(emoji, EMOJI) or "📖"
        if color is not None:
            out["color"] = _int(color, 0, COLORS - 1, 0)
        if lang is not None:
            out["lang"] = lang if lang in LANGS else "en"
        return out

    # ---------------------------------------------------------------- sample books (picturebooks.SAMPLES)
    def _samples(self) -> dict[str, dict]:
        """The rows of the sample books – made the first time the shelf is opened (the readers' progress and ⭐ need them)."""
        from . import picturebooks
        rows = {r["sample"]: r for r in self.db.q("SELECT * FROM story WHERE sample IS NOT NULL")}
        for key in picturebooks.SAMPLES:
            if key not in rows:
                s = picturebooks.sample(key, "en")
                raw = json.dumps(s["data"], ensure_ascii=False)
                sid = self.db.x("""INSERT INTO story(title, emoji, color, lang, author_id, data, live, visibility, approved, rewarded, type,
                                   sample, published_at) VALUES(?,?,?,?,NULL,?,?,'family',1,1,'picture',?,datetime('now','localtime'))""",
                                s["title"], s["emoji"], s["color"], s["lang"], raw, raw, key)
                rows[key] = self._book(sid)
        return rows

    @staticmethod
    def _localized(b: dict, lang: str | None) -> tuple[dict, dict]:
        """A sample book in the reader's language: (the row with that title and language, the book)."""
        from . import picturebooks
        s = picturebooks.sample(b["sample"], lang or "en")
        return {**b, "title": s["title"], "lang": s["lang"]}, s["data"]

    # ---------------------------------------------------------------- the shelf
    def _cover_meta(self, kind: str, raw: str) -> dict:
        """cover_meta of a stored book text – cached per text (the shelf is opened often, books change rarely)."""
        key = (kind, len(raw), hash(raw))
        got = self._covers.get(key)
        if got is None:
            if len(self._covers) >= COVER_CACHE:
                self._covers.clear()
            got = self._covers[key] = cover_meta(kind, json.loads(raw))
        return got

    def shelf(self, prof: dict, oversee: bool = False, lang: str | None = None) -> dict:
        self._need(prof)
        pid, parent = prof["id"], self._parent(prof)
        oversee = oversee and parent
        people = self._people()
        samples = self._samples()
        hidden = self.settings()["samples_off"]
        types = self._types(prof)
        reads = {r["story_id"]: r for r in self.db.q("SELECT * FROM story_read WHERE profile_id=?", pid)}
        stats = {r["story_id"]: r for r in self.db.q(
            """SELECT story_id, COUNT(*) AS readers, AVG(rating) AS avg, COUNT(rating) AS votes FROM story_read
               WHERE finished > 0 GROUP BY story_id""")}
        books, privates, sample_list = [], [], []
        # the book texts (up to MAX_BYTES each) only for the books this person may see – and parsed once per version
        # (_cover_meta); pages and «changed» come from SQLite, others' private books are never read or parsed
        rows = self.db.q("""SELECT id, title, emoji, color, lang, author_id, visibility, approved, rewarded, created_at, updated_at,
                                   published_at, type, sample, live IS NOT NULL AS live, pending IS NOT NULL AS pending,
                                   live IS NOT NULL AND live != data AS changed,
                                   COALESCE(json_array_length(data, CASE WHEN type='game' THEN '$.rooms' ELSE '$.pages' END), 0) AS size,
                                   CASE WHEN visibility='me' AND (author_id IS NULL OR author_id != ?) THEN NULL
                                        ELSE COALESCE(live, data) END AS raw
                            FROM story ORDER BY COALESCE(published_at, updated_at) DESC, id DESC""", pid)
        for b in rows:
            mine = b["author_id"] == pid and not b["sample"]
            a = people.get(b["author_id"]) or {"id": None, "name": "?", "avatar": {}}
            if b["type"] not in types:                         # adventure games switched off for this child
                continue
            if b["sample"]:
                if b["sample"] not in samples:
                    continue
                b, data = self._localized(b, lang)
                b.update(live=True, changed=False, size=size_of(data))
                meta = cover_meta(b["type"], data)
                a = {"id": None, "name": "Family Quest", "avatar": {}}
            elif self._private(prof, b):
                if oversee:                                    # parents: only that it exists – no title, no content
                    privates.append({"id": b["id"], "private": True, "visibility": "me", "type": b["type"],
                                     "author": {"id": a["id"], "name": a["name"], "avatar": a["avatar"]},
                                     "pages": b["size"], "created_at": b["created_at"], "updated_at": b["updated_at"]})
                continue
            elif not (mine or (oversee and not b["live"]) or self.visible(prof, b, oversee)):
                continue
            else:
                meta = self._cover_meta(b["type"], b["raw"])
            live = bool(b["live"])                             # meta: of the published copy (else the working copy)
            r = reads.get(b["id"])
            st = stats.get(b["id"]) or {}
            book = {
                "id": b["id"], "type": b["type"], "title": b["title"], "emoji": b["emoji"], "color": b["color"], "lang": b["lang"],
                "author": {"id": a["id"], "name": a["name"], "avatar": a["avatar"]}, "mine": mine, "sample": b["sample"],
                "edit": self._may_edit(prof, b), "live": live, "pending": bool(b["pending"]),
                "visibility": b["visibility"], "shared": bool(live and b["approved"] and b["visibility"] != "me"),
                "changed": bool(b["changed"]) and not b["sample"], "pages": b["size"],
                "finished": (r or {}).get("finished", 0),
                "rating": round(st["avg"], 1) if st.get("avg") else None, "votes": st.get("votes", 0),
                "readers": st.get("readers", 0), "my_rating": (r or {}).get("rating"),
                "updated_at": b["updated_at"], "published_at": b["published_at"]}
            ends = meta["ends"] if live else []
            if b["type"] == "picture":
                n = meta["n"]
                at = min(max((r or {}).get("page") or 0, 0), n) if live else 0
                book.update({"cover": meta["cover"], "cover_bg": None, "endings": 0, "found": 0,
                             "at": at, "reading": bool(live and 0 < at < n)})
            elif b["type"] == "game":
                found = [e for e in json.loads(r["endings"]) if e in ends] if r else []
                st = json.loads(r["state"]) if r and r.get("state") else None
                book.update({"cover": meta["cover"], "cover_bg": meta["cover_bg"], "endings": len(ends), "found": len(found),
                             "reading": bool(live and isinstance(st, dict) and not st.get("end")
                                             and (st.get("room") != meta["start"] or st.get("inv") or st.get("flags")))})
            else:
                found = [e for e in json.loads(r["endings"]) if e in ends] if r else []
                book.update({"cover": meta["cover"], "cover_bg": meta["cover_bg"], "endings": len(ends), "found": len(found),
                             "reading": bool(r and live and r["page"] != meta["start"] and r["page"] in meta["scenes"])})
            if b["sample"]:
                book["hidden"] = b["sample"] in hidden
                if not book["hidden"] or oversee:
                    sample_list.append(book)
                continue
            books.append(book)
        s = self.settings()
        return {"books": books, "samples": sample_list, "private": privates, "approval": s["approval"],
                "rewards": {k: s[k] for k in ("write_coins", "write_xp", "read_coins", "read_xp")}, "types": list(types),
                "creatable": [t for t in CREATABLE if t in types], "pending": sum(1 for b in books if b["pending"]) if oversee else 0,
                "parent": parent, "oversee": oversee}

    def pending_count(self) -> int:
        return int(self.db.val("SELECT COUNT(*) FROM story WHERE pending IS NOT NULL", default=0))

    def _count(self) -> int:
        return int(self.db.val("SELECT COUNT(*) FROM story WHERE sample IS NULL", default=0))

    def _room_for(self, prof: dict, n: int = 1) -> None:
        if self._count() + n > MAX_BOOKS:
            raise CommunityError("The bookshelf is full – remove an old book first")
        mine = int(self.db.val("SELECT COUNT(*) FROM story WHERE sample IS NULL AND author_id=?", prof["id"], default=0))
        if mine + n > MAX_PER_AUTHOR:
            raise CommunityError("You have written as many books as one person can keep – remove an old one first")

    # ---------------------------------------------------------------- writing
    def create(self, prof: dict, title: str = "", emoji: str = "📖", color: int = 0, lang: str = "en", tpl: str | None = None,
               visibility: str = "family", kind: str = "adventure") -> int:
        self._need(prof)
        if kind not in CREATABLE:
            raise CommunityError("Unknown book type")
        self._need_type(prof, kind)
        self._room_for(prof)
        if tpl and kind == "adventure":
            t = template(tpl, lang)
            m = self._meta(title or t["title"], t["emoji"], t["color"], lang if lang in LANGS else t["lang"])
            data = clean(t["data"])
        elif tpl and kind == "game":
            from . import adventuregame
            t = adventuregame.template(tpl, lang)
            m = self._meta(title or t["title"], t["emoji"], t["color"], lang if lang in LANGS else t["lang"])
            data = t["data"]
        else:
            m = self._meta(title, emoji if kind == "adventure" or emoji != "📖" else {"picture": "📕", "game": "🗝️"}[kind], color, lang)
            data = empty_book(kind)
        if not m["title"]:
            raise CommunityError("Give the book a title")
        return self.db.x("INSERT INTO story(title, emoji, color, lang, author_id, data, visibility, type) VALUES(?,?,?,?,?,?,?,?)",
                         m["title"], m["emoji"], m["color"], m["lang"], prof["id"], json.dumps(data, ensure_ascii=False),
                         visibility if visibility in VISIBILITY else "family", kind)

    def import_(self, prof: dict, text: str) -> list[int]:
        """Import books (file or AI answer) as private drafts of this person – the checker tells what is missing."""
        self._need(prof)
        books = import_books(text)
        for b in books:
            self._need_type(prof, b["type"])
        self._room_for(prof, len(books))
        return [self.db.x("INSERT INTO story(title, emoji, color, lang, author_id, data, visibility, type) VALUES(?,?,?,?,?,?,'me',?)",
                          b["title"], b["emoji"], 0, b["lang"], prof["id"], json.dumps(b["data"], ensure_ascii=False), b["type"])
                for b in books]

    def export(self, prof: dict, sid: int) -> dict:
        b = self._edit(prof, sid)
        if b["type"] == "picture":
            from . import picturebooks
            return picturebooks.document([picturebooks.export_book(b["title"], b["emoji"], b["lang"], json.loads(b["data"]))])
        if b["type"] == "game":
            from . import adventuregame
            return adventuregame.document([adventuregame.export_game(b["title"], b["emoji"], b["lang"], json.loads(b["data"]))])
        return story_document([export_book(b["title"], b["emoji"], b["lang"], json.loads(b["data"]))])

    def _editor(self, prof: dict, b: dict) -> dict:
        data = json.loads(b["data"])
        live = json.loads(b["live"]) if b["live"] else None
        a = self._people().get(b["author_id"]) or {"name": "?"}
        return {"id": b["id"], "type": b["type"], "title": b["title"], "emoji": b["emoji"], "color": b["color"], "lang": b["lang"],
                "author": a["name"], "author_id": b["author_id"], "mine": b["author_id"] == prof["id"],
                "data": data, "live": bool(live), "pending": json.loads(b["pending"]) if b["pending"] else None,
                "changed": bool(live) and live != data, "issues": check_as(b["type"], data, b["title"]),
                "visibility": b["visibility"], "shared": bool(live and b["approved"] and b["visibility"] != "me"),
                "approval": self._approval(prof), "parent": self._parent(prof),
                "reward": None if b["rewarded"] else {k: self.settings()[k] for k in ("write_coins", "write_xp")}}

    def get(self, prof: dict, sid: int) -> dict:
        return self._editor(prof, self._edit(prof, sid))

    def save(self, prof: dict, sid: int, data=None, title=None, emoji=None, color=None, lang=None, visibility=None) -> dict:
        with self.db.tx():
            b = self._edit(prof, sid)
            m = self._meta(title, emoji, color, lang)
            if "title" in m and not m["title"]:
                raise CommunityError("Give the book a title")
            if data is not None:
                b["data"] = json.dumps(clean_as(b["type"], data, self.folder), ensure_ascii=False)
            b.update(m)
            self.db.x("UPDATE story SET title=?, emoji=?, color=?, lang=?, data=?, updated_at=datetime('now','localtime') WHERE id=?",
                      b["title"], b["emoji"], b["color"], b["lang"], b["data"], sid)
            if visibility in VISIBILITY and visibility != b["visibility"]:
                if b["author_id"] != prof["id"]:
                    raise CommunityError("Only the author decides who reads the book")
                self._visibility(prof, b, visibility)
        self._gc()
        return self._editor(prof, self._book(sid))

    def _visibility(self, prof: dict, b: dict, vis: str) -> None:
        """«me» never waits for approval; for the others an unapproved published copy waits for a parent (approval on)."""
        self.db.x("UPDATE story SET visibility=? WHERE id=?", vis, b["id"])
        if vis == "me":
            self.db.x("UPDATE story SET pending=NULL WHERE id=?", b["id"])
        elif b["live"] and not b["approved"]:
            if self._approval(prof):
                self.db.x("UPDATE story SET pending=COALESCE(pending, live) WHERE id=?", b["id"])
            else:
                self.db.x("UPDATE story SET approved=1, pending=NULL WHERE id=?", b["id"])
        self._shared(b["id"])

    def publish(self, prof: dict, sid: int) -> str:
        """Publish the working copy: «live» – or «pending» when a parent has to approve it first (never for «only me»).
        The checker runs before the transaction (a game's search takes a while); inside only: still the same text?"""
        b = self._edit(prof, sid)
        if blocking_as(b["type"], json.loads(b["data"]), b["title"]):
            raise CommunityError("The book is not finished yet – the checker shows what is missing")
        checked = (b["data"], b["title"])
        with self.db.tx():
            b = self._edit(prof, sid)
            if (b["data"], b["title"]) != checked:                   # saved meanwhile: check that version again
                raise CommunityError("The book was changed meanwhile – try again")
            need = self._approval(prof)
            if b["visibility"] != "me" and need:
                self.db.x("UPDATE story SET pending=? WHERE id=?", b["data"], sid)
                return "pending"
            self._go_live(b, b["data"], approved=not need)
        self._gc(force=True)
        return "live"

    def _go_live(self, b: dict, raw: str, approved: bool = True) -> None:
        self.db.x("""UPDATE story SET live=?, pending=NULL, approved=?, published_at=COALESCE(published_at, datetime('now','localtime'))
                     WHERE id=?""", raw, int(approved), b["id"])
        self._shared(b["id"])

    def _pay(self, pid: int, coins: int, xp: int, event: str, reason: str, ref: str) -> None:
        if not pid or not self.db.q1("SELECT 1 FROM profile WHERE id=?", pid):
            return
        if coins:
            self.rewards.book(pid, "coins", float(coins), event, reason, ref)
        if xp:
            self.rewards.book(pid, "xp", float(xp), event, reason, ref)

    def approve(self, prof: dict, sid: int) -> None:
        if not self._parent(prof):
            raise CommunityError("Only a parent can approve a book")
        b = self._book(sid)
        if not b["pending"] or b["visibility"] == "me":
            raise CommunityError("This book does not wait for approval")
        if blocking_as(b["type"], json.loads(b["pending"]), b["title"]):
            raise CommunityError("The book is not finished yet – the checker shows what is missing")
        with self.db.tx():
            again = self._book(sid)
            if (again["pending"], again["title"], again["visibility"]) != (b["pending"], b["title"], b["visibility"]):
                raise CommunityError("The book was changed meanwhile – try again")
            self._go_live(b, b["pending"])

    def reject(self, prof: dict, sid: int) -> None:
        if not self._parent(prof):
            raise CommunityError("Only a parent can approve a book")
        if self._book(sid)["visibility"] == "me":
            raise CommunityError("This book does not wait for approval")
        self.db.x("UPDATE story SET pending=NULL WHERE id=?", sid)

    def unpublish(self, prof: dict, sid: int) -> None:
        self._edit(prof, sid)
        self.db.x("UPDATE story SET live=NULL, pending=NULL, approved=0 WHERE id=?", sid)

    def delete(self, prof: dict, sid: int) -> None:
        b = self._book(sid) if self.db.q1("SELECT 1 FROM story WHERE id=? AND sample IS NOT NULL", sid) else None
        if b:                                                  # a sample book: parents take it off the shelf (and back)
            self.sample_hidden(prof, b["sample"], True)
            return
        self._edit(prof, sid)
        with self.db.tx():
            self.db.x("DELETE FROM story_read WHERE story_id=?", sid)
            self.db.x("DELETE FROM story WHERE id=?", sid)
        self._gc(force=True)

    def author_removed(self, pid: int) -> None:
        """A profile is deleted for good: its books go too (with the readers' progress and the pictures only they use) –
        a later profile must never see them (profile ids are not used again either, db.py migration 42)."""
        with self.db.tx():
            self.db.x("DELETE FROM story_read WHERE story_id IN (SELECT id FROM story WHERE author_id=? AND sample IS NULL)", pid)
            self.db.x("DELETE FROM story WHERE author_id=? AND sample IS NULL", pid)
        self._gc(force=True)

    def sample_hidden(self, prof: dict, key: str, hidden: bool) -> None:
        from .picturebooks import SAMPLES
        if not self._parent(prof):
            raise CommunityError("Only a parent can take the sample book off the shelf")
        if key not in SAMPLES:
            raise CommunityError("Unknown book")
        off = set(self.settings()["samples_off"])
        off = off | {key} if hidden else off - {key}
        self.save_settings({"samples_off": sorted(off)})

    # ---------------------------------------------------------------- pictures
    def save_image(self, prof: dict, raw: bytes, kind: str | None) -> dict:
        self._need(prof)
        if not kind:
            raise CommunityError("Only pictures (JPEG, PNG, WebP, GIF) can be uploaded")
        if len(raw) > IMAGE_MAX:
            raise CommunityError("The picture is too large (max. 2 MB)")
        self.folder.mkdir(parents=True, exist_ok=True)
        name = "s-" + hashlib.sha1(raw).hexdigest()[:16] + kind
        f = self.folder / name
        if not f.is_file():
            used = sum(x.stat().st_size for x in self.folder.iterdir() if x.is_file())
            if used + len(raw) > FOLDER_MAX:
                raise CommunityError("There is no room for more pictures – remove old books first")
            f.write_bytes(raw)
        else:
            f.touch()
        return {"name": name, "url": f"media/{FOLDER}/{name}"}

    def check_svg(self, prof: dict, svg: str, use: str = "bg") -> str:
        """An own SVG drawing (drawing editor or pasted code), cleaned – what the book will keep – or why it cannot be used.
        `use`: «bg» a scene that fills a page or a room (max. BG_MAX), «art» a thing / a character (max. ART_MAX)."""
        from .svgsafe import LIMITS, SvgError, clean_svg
        self._need(prof)
        try:
            return clean_svg(svg, LIMITS.get(use, LIMITS["bg"]))
        except SvgError as e:
            if str(e) in ("too large", "too many parts"):
                raise CommunityError(_t("The drawing is too large (max. 20 KB)") if use == "art"
                                     else _t("The drawing is too large (max. 60 KB)")) from None
            raise CommunityError("This is not a usable SVG picture (<svg viewBox=…> with simple shapes)") from None

    def _gc(self, force: bool = False) -> None:
        """Remove pictures no book uses any more (not fresh uploads: the book that uses them is not saved yet) – it reads
        every book: after an autosave at most every GC_EVERY seconds, after deleting / publishing always."""
        now = time.time()
        if not force and now - self._gc_at < GC_EVERY:
            return
        self._gc_at = now
        if not self.folder.is_dir():
            return
        used = set()
        for r in self.db.q("SELECT data, live, pending FROM story"):
            for raw in (r["data"], r["live"], r["pending"]):
                if raw:
                    used.update(re.findall(r"s-[0-9a-f]{16}\.(?:jpg|png|webp|gif)", raw))
        old = time.time() - 3600
        for f in self.folder.iterdir():
            try:
                if f.name not in used and f.stat().st_mtime < old:
                    f.unlink()
            except OSError:
                pass

    # ---------------------------------------------------------------- reading (the published copy only)
    def _live(self, prof: dict, sid: int, oversee: bool = False, lang: str | None = None) -> tuple[dict, dict]:
        self._need(prof)
        b = self._book(sid)
        self._need_type(prof, b["type"])
        if not b["live"] or not self.visible(prof, b, oversee):
            raise CommunityError("This book is not published")
        if b["sample"]:
            return self._localized(b, lang)
        return b, json.loads(b["live"])

    def _row(self, b: dict, live: dict, pid: int) -> dict:
        r = self.db.q1("SELECT * FROM story_read WHERE story_id=? AND profile_id=?", b["id"], pid)
        if not r:
            self.db.x("INSERT INTO story_read(story_id, profile_id) VALUES(?,?)", b["id"], pid)
            r = self.db.q1("SELECT * FROM story_read WHERE story_id=? AND profile_id=?", b["id"], pid)
        if b["type"] == "picture":
            r["page"] = min(max(r["page"] or 0, 0), len(live["pages"]))
            return r
        if b["type"] == "game":
            return r
        ids = {p["id"] for p in live["pages"]}
        if r["page"] not in ids:                              # new reader – or the page is gone in a new version
            self._back_save(r, [])
            self._move(r, live, live["start"], [])
        return r

    @staticmethod
    def _back_of(r: dict) -> list:
        """The pages this reader went through before the current one: [[page, items], …] (the last one is the page before)."""
        try:
            st = json.loads(r.get("state") or "null")
        except ValueError:
            st = None
        back = st.get("back") if isinstance(st, dict) else None
        return back if isinstance(back, list) else []

    def _back_save(self, r: dict, back: list) -> None:
        r["state"] = json.dumps({"back": back[-BACK_MAX:]}, ensure_ascii=False) if back else None
        self.db.x("UPDATE story_read SET state=? WHERE story_id=? AND profile_id=?", r["state"], r["story_id"], r["profile_id"])

    def _move(self, r: dict, live: dict, page: int, items: list) -> None:
        p = next(x for x in live["pages"] if x["id"] == page)
        if p.get("give") and p["give"] not in items:
            items = items + [p["give"]]
        r["page"], r["items"] = page, json.dumps(items, ensure_ascii=False)
        self.db.x("UPDATE story_read SET page=?, items=?, updated_at=datetime('now','localtime') WHERE story_id=? AND profile_id=?",
                  page, r["items"], r["story_id"], r["profile_id"])

    def _author_name(self, b: dict) -> str:
        if b["sample"]:
            return "Family Quest"
        return (self._people().get(b["author_id"]) or {"name": "?"})["name"]

    def _picture_view(self, b: dict, live: dict, r: dict, prof: dict, new_finish: bool = False) -> dict:
        """A picture book: every page at once (the reader turns them in the app) and where this reader is."""
        from .picturebooks import view_page
        return {"id": b["id"], "type": "picture", "title": b["title"], "emoji": b["emoji"], "color": b["color"], "lang": b["lang"],
                "author": self._author_name(b), "sample": b["sample"], "cover": (live.get("cover") or {}).get("pic"),
                "pages": [view_page(p) for p in live["pages"]], "at": r["page"], "finished": r["finished"],
                "new_finish": new_finish, "rating": r["rating"], "may_rate": r["finished"] > 0 and b["author_id"] != prof["id"]}

    def _view(self, b: dict, live: dict, r: dict, prof: dict, new_ending: bool = False) -> dict:
        if b["type"] == "picture":
            return self._picture_view(b, live, r, prof, new_ending)
        if b["type"] == "game":
            return self._game_view(b, live, r, prof, [], new_ending)
        p = next(x for x in live["pages"] if x["id"] == r["page"])
        items = json.loads(r["items"])
        ends = endings(live)
        found = [e for e in json.loads(r["endings"]) if e in ends]
        back = self._back_of(r)
        page = {"id": p["id"], "kind": p["kind"], "text": p["text"], "pic": p["pic"], "bg": p.get("bg"), "give": p.get("give"),
                "start": p["id"] == live["start"], "linear": linear(p), "next": bool(linear(p) and p.get("next")),
                "choices": [{"i": i, "t": c["t"], "need": c["need"]} for i, c in enumerate(p.get("choices", []))
                            if not c["need"] or c["need"] in items]}
        return {"id": b["id"], "type": b["type"], "title": b["title"], "emoji": b["emoji"], "color": b["color"], "lang": b["lang"],
                "page": page, "items": items, "endings": len(ends), "found": len(found), "new_ending": new_ending,
                "back": len(back) > 0, "step": len(back) + 1,
                "finished": r["finished"], "rating": r["rating"], "may_rate": r["finished"] > 0 and b["author_id"] != prof["id"],
                "number": [x["id"] for x in live["pages"]].index(p["id"]) + 1}

    def read(self, prof: dict, sid: int, oversee: bool = False, lang: str | None = None) -> dict:
        with self.db.tx():
            b, live = self._live(prof, sid, oversee, lang)
            r = self._row(b, live, prof["id"])
        return self._view(b, live, r, prof)

    def restart(self, prof: dict, sid: int, oversee: bool = False, lang: str | None = None) -> dict:
        with self.db.tx():
            b, live = self._live(prof, sid, oversee, lang)
            r = self._row(b, live, prof["id"])
            if b["type"] == "picture":
                self._turn(r, 0)
            elif b["type"] == "game":
                self._game_save(r, None)
            else:
                self._back_save(r, [])
                self._move(r, live, live["start"], [])
        return self._view(b, live, r, prof)

    def _turn(self, r: dict, page: int) -> None:
        r["page"] = page
        self.db.x("UPDATE story_read SET page=?, updated_at=datetime('now','localtime') WHERE story_id=? AND profile_id=?",
                  page, r["story_id"], r["profile_id"])

    def _finished(self, b: dict, r: dict, prof: dict) -> None:
        """A reader reached an end: counted; the author's reading reward once per reader who is somebody else."""
        r["finished"] += 1
        self.db.x("UPDATE story_read SET endings=?, finished=? WHERE story_id=? AND profile_id=?",
                  r["endings"], r["finished"], b["id"], prof["id"])
        if b["author_id"] and b["author_id"] != prof["id"] and not r["rewarded"] and b["approved"] and b["visibility"] != "me":
            self.db.x("UPDATE story_read SET rewarded=1 WHERE story_id=? AND profile_id=?", b["id"], prof["id"])
            s = self.settings()
            self._pay(b["author_id"], s["read_coins"], s["read_xp"], "story_read",
                      f"{TYPE_ICON.get(b['type'], '📖')} {b['title']} – {prof['name']}", f"story:{b['id']}:read:{prof['id']}")

    def turn(self, prof: dict, sid: int, page: int, oversee: bool = False, lang: str | None = None) -> dict:
        """A picture book: this reader is on page `page` now (0 = the cover). Arriving at the last page reads it to the end."""
        with self.db.tx():
            b, live = self._live(prof, sid, oversee, lang)
            if b["type"] != "picture":
                raise CommunityError("This choice is not possible")
            n = len(live["pages"])
            if not isinstance(page, int) or not 0 <= page <= n:
                raise CommunityError("This page does not exist")
            r = self._row(b, live, prof["id"])
            done = page == n and r["page"] != n
            self._turn(r, page)
            if done:
                self._finished(b, r, prof)
        return {"at": r["page"], "finished": r["finished"], "new_finish": done and r["finished"] == 1, "rating": r["rating"],
                "may_rate": r["finished"] > 0 and b["author_id"] != prof["id"]}

    def choose(self, prof: dict, sid: int, i: int, oversee: bool = False) -> dict:
        with self.db.tx():
            b, live = self._live(prof, sid, oversee)
            if b["type"] != "adventure":
                raise CommunityError("This choice is not possible")
            r = self._row(b, live, prof["id"])
            p = next(x for x in live["pages"] if x["id"] == r["page"])
            items = json.loads(r["items"])
            ch = p.get("choices") or []
            if p["kind"] != "scene" or not isinstance(i, int) or not 0 <= i < len(ch):
                raise CommunityError("This choice is not possible")
            c = ch[i]
            if c["need"] and c["need"] not in items:
                raise CommunityError("You need something for this first")
            new = self._arrive(b, live, r, prof, c["to"], items)
        return self._view(b, live, r, prof, new_ending=new)

    def _arrive(self, b: dict, live: dict, r: dict, prof: dict, to: int, items: list) -> bool:
        """The reader turns to page `to` (the page they leave goes into the history for ◀). True: a new ending."""
        self._back_save(r, self._back_of(r) + [[r["page"], items]])
        self._move(r, live, to, items)
        nxt = next(x for x in live["pages"] if x["id"] == to)
        if nxt["kind"] == "scene":
            return False
        found = json.loads(r["endings"])
        new = nxt["id"] not in found
        if new:
            found.append(nxt["id"])
        r["endings"] = json.dumps(found)
        self._finished(b, r, prof)
        return new

    def forward(self, prof: dict, sid: int, oversee: bool = False) -> dict:
        """«Next ▶» on a linear page: the page that follows."""
        with self.db.tx():
            b, live = self._live(prof, sid, oversee)
            if b["type"] != "adventure":
                raise CommunityError("This choice is not possible")
            r = self._row(b, live, prof["id"])
            p = next(x for x in live["pages"] if x["id"] == r["page"])
            if not linear(p) or not p.get("next"):
                raise CommunityError("This choice is not possible")
            new = self._arrive(b, live, r, prof, p["next"], json.loads(r["items"]))
        return self._view(b, live, r, prof, new_ending=new)

    def back(self, prof: dict, sid: int, oversee: bool = False) -> dict:
        """◀: back to the page this reader read before (with the backpack of then) – endings found stay found."""
        with self.db.tx():
            b, live = self._live(prof, sid, oversee)
            if b["type"] != "adventure":
                raise CommunityError("This choice is not possible")
            r = self._row(b, live, prof["id"])
            back = self._back_of(r)
            ids = {p["id"] for p in live["pages"]}
            while back and (not isinstance(back[-1], list) or len(back[-1]) != 2 or back[-1][0] not in ids):
                back.pop()                                  # a page that is gone in a new version
            if not back:
                raise CommunityError("This is the first page")
            page, items = back.pop()
            self._back_save(r, back)
            r["page"], r["items"] = page, json.dumps([i for i in items if isinstance(i, str)] if isinstance(items, list) else [], ensure_ascii=False)
            self.db.x("UPDATE story_read SET page=?, items=?, updated_at=datetime('now','localtime') WHERE story_id=? AND profile_id=?",
                      page, r["items"], r["story_id"], r["profile_id"])
        return self._view(b, live, r, prof)

    # ---------------------------------------------------------------- 🗝️ adventure games (adventuregame.py)
    def _game_save(self, r: dict, st: dict | None) -> None:
        r["state"] = json.dumps(st) if st is not None else None
        self.db.x("UPDATE story_read SET state=?, updated_at=datetime('now','localtime') WHERE story_id=? AND profile_id=?",
                  r["state"], r["story_id"], r["profile_id"])

    def _game_view(self, b: dict, live: dict, r: dict, prof: dict, msgs: list, new_ending: bool = False) -> dict:
        from . import adventuregame as A
        ix = A.Index(live)
        st = A.clean_state(live, json.loads(r["state"]) if r.get("state") else None)
        ends = endings(live)
        found = [e for e in json.loads(r["endings"]) if e in ends]
        return {"id": b["id"], "type": "game", "title": b["title"], "emoji": b["emoji"], "color": b["color"], "lang": b["lang"],
                **A.view(ix, st), "msgs": msgs, "endings": len(ends), "found": len(found), "new_ending": new_ending,
                "finished": r["finished"], "rating": r["rating"], "may_rate": r["finished"] > 0 and b["author_id"] != prof["id"],
                "fresh": st == A.new_state(live)}

    def play(self, prof: dict, sid: int, move: dict, oversee: bool = False) -> dict:
        """One move of a player in a published game – the engine runs here, the state is saved per player (resume)."""
        from . import adventuregame as A
        with self.db.tx():
            b, live = self._live(prof, sid, oversee)
            if b["type"] != "game":
                raise CommunityError("This choice is not possible")
            r = self._row(b, live, prof["id"])
            ix = A.Index(live)
            st = A.clean_state(live, json.loads(r["state"]) if r.get("state") else None)
            msgs = A.act(ix, st, move)
            new = False
            if st["end"]:
                found = json.loads(r["endings"])
                new = st["end"] not in found
                if new:
                    found.append(st["end"])
                r["endings"] = json.dumps(found)
                self._finished(b, r, prof)
            self._game_save(r, st)
        return self._game_view(b, live, r, prof, msgs, new)

    def try_game(self, prof: dict, sid: int, state=None, move=None, room=None, pending: bool = False) -> dict:
        """▶ in the editor (and 👀 of a game waiting for approval): play the working copy from any room – nothing is
        saved, the state goes back and forth with the app (and is checked again every time)."""
        from . import adventuregame as A
        b = self._edit(prof, sid)
        if b["type"] != "game":
            raise CommunityError("This choice is not possible")
        if pending and not b["pending"]:
            raise CommunityError("This book does not wait for approval")
        data = json.loads(b["pending"] if pending else b["data"])
        if not data["rooms"]:
            raise CommunityError("The game has no rooms yet")
        ix = A.Index(data)
        if state is not None and not A.valid_state(state):
            raise A.PlayError(_t("This is not possible"))
        st = A.clean_state(data, state) if isinstance(state, dict) else A.new_state(data, room)
        msgs = A.act(ix, st, move) if move else []
        ends = endings(data)
        return {"id": b["id"], "type": "game", "title": b["title"], "emoji": b["emoji"], "color": b["color"], "lang": b["lang"],
                **A.view(ix, st), "msgs": msgs, "state": st, "endings": len(ends), "found": 0, "new_ending": bool(st["end"]),
                "finished": 0, "rating": None, "may_rate": False, "fresh": False}

    def rate(self, prof: dict, sid: int, stars: int, oversee: bool = False) -> None:
        b, live = self._live(prof, sid, oversee)
        if b["author_id"] == prof["id"]:
            raise CommunityError("You cannot rate your own book")
        if not isinstance(stars, int) or not 1 <= stars <= 5:
            raise CommunityError("Give 1 to 5 stars")
        if not self.db.x("UPDATE story_read SET rating=? WHERE story_id=? AND profile_id=? AND finished > 0", stars, sid, prof["id"]):
            raise CommunityError("Read the book to an end first")
