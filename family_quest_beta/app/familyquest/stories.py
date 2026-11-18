"""My adventure books: branching choose-your-path stories that children and parents write and the family reads.

A book is a list of pages. A page is a 📄 scene (text, a picture, 2–4 choices A–D that each point to another page), a
🏆 good ending or a 💀 bad ending. Paths may merge (two choices pointing to the same page) and even go back. Items 🎒:
a page can give one item («🍌 Banana»), a choice can need one – it is only shown to a reader who has it.

Every book is in one language (`lang`, a tag – no translations inside a book). The author works on a working copy
(`data`); readers only ever see the published copy (`live`). Publishing checks the book (`check`): every scene has at
least 2 choices with a target and one that needs no item, there is a good ending, every page can be reached from the
start.

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
collects own endings («2 of 5 endings found») and gives ⭐ after finishing a book.

Pictures: an emoji, an own drawing or a photo – drawings and photos are files in media/_stories (checked by their first
bytes, max. IMAGE_MAX), named after their content. Files no book uses any more are removed after an hour.

Book types (`type`, the badge and filter on the shelf): 📕 «picture» – picture books (picturebooks.py: pages with a
picture and a text, read page by page), 📖 «adventure» – the adventure books of this module, 🗝️ «game» – adventure
games (reserved: the shelf knows the type, it cannot be made yet). Visibility, approval, rewards, ratings, the parent
area and privacy are the same for every type; only the content (`clean` / `check`), reading and the file format
differ. Sample books (`sample`: a key of picturebooks.SAMPLES) come with the app: author «Family Quest», visible to the
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
MAX_PAGES = 200
MAX_CHOICES = 4
MIN_CHOICES = 2
TITLE = 80
TEXT = 1500                     # characters of one page
CHOICE = 120
ITEM = 40
EMOJI = 16
MAX_BYTES = 400_000             # JSON of one book
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
IMG_NAME = re.compile(r"s-[0-9a-f]{16}\.(jpg|png|webp|gif)")
DEFAULT = {"off": [], "approval": False, "write_coins": 20, "write_xp": 0, "read_coins": 0, "read_xp": 0, "samples_off": []}
TYPES = ("picture", "adventure", "game")        # 📕 picture book · 📖 adventure book · 🗝️ adventure game (reserved)
CREATABLE = ("picture", "adventure")
TYPE_ICON = {"picture": "📕", "adventure": "📖", "game": "🗝️"}

# messages of the checker – English source text, the app translates them ({0} page, {1} choice letter, {2} item)
MSG = {
    "title": _t("Give the book a title"),
    "empty": _t("The book has no pages yet"),
    "start": _t("The first page must be a scene"),
    "no_text": _t("Page {0} has no text yet"),
    "dead_end": _t("Page {0} has no continuation"),
    "one_choice": _t("Page {0} needs at least 2 choices"),
    "no_target": _t("Page {0}: choice {1} has no target"),
    "choice_text": _t("Page {0}: choice {1} has no text"),
    "all_gated": _t("Page {0}: at least one choice must work without an item"),
    "item_never": _t("Page {0}: choice {1} needs «{2}», but no page gives it"),
    "no_good": _t("No good ending yet"),
    "unreachable": _t("Page {0} cannot be reached from the start"),
}


def _text(v, n: int) -> str:
    return str(v or "").replace("\r\n", "\n").replace("\x00", "")[:n].strip()


def _int(v, lo: int, hi: int, default: int | None = None) -> int | None:
    try:
        i = int(v)
    except (TypeError, ValueError):
        return default
    return i if lo <= i <= hi else default


def clean_pic(p, folder: Path | None) -> dict | None:
    if not isinstance(p, dict):
        return None
    if p.get("k") == "emoji":
        v = _text(p.get("v"), EMOJI)
        return {"k": "emoji", "v": v} if v else None
    if p.get("k") == "img":
        v = str(p.get("v") or "")
        if not IMG_NAME.fullmatch(v) or (folder is not None and not (folder / v).is_file()):
            return None
        return {"k": "img", "v": v, "src": "draw" if p.get("src") == "draw" else "photo"}
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
               "bg": p.get("bg") if p.get("bg") in BACKGROUNDS else None}
        if kind == "scene":
            give = _text(p.get("give"), ITEM)
            out["give"] = give or None
            ch = []
            for c in (p.get("choices") if isinstance(p.get("choices"), list) else [])[:MAX_CHOICES]:
                if not isinstance(c, dict):
                    continue
                ch.append({"t": _text(c.get("t"), CHOICE), "to": _int(c.get("to"), 1, 9999), "need": _text(c.get("need"), ITEM) or None})
            out["choices"] = ch
        pages.append(out)
    for p in pages:                                         # a target that is gone: the choice has no target
        for c in p.get("choices", []):
            if c["to"] not in seen:
                c["to"] = None
    start = _int(data.get("start"), 1, 9999)
    if start not in seen:
        start = pages[0]["id"] if pages else None
    out = {"start": start, "pages": pages}
    if len(json.dumps(out, ensure_ascii=False)) > MAX_BYTES:
        raise CommunityError("The book is too long – make some pages shorter")
    return out


def letter(i: int) -> str:
    return "ABCD"[i] if 0 <= i < 4 else str(i + 1)


def reachable(data: dict) -> set[int]:
    by = {p["id"]: p for p in data["pages"]}
    todo, seen = [data.get("start")], set()
    while todo:
        pid = todo.pop()
        if pid in seen or pid not in by:
            continue
        seen.add(pid)
        todo += [c["to"] for c in by[pid].get("choices", []) if c["to"]]
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
    reach = reachable(data)
    for p in pages:
        if p["id"] not in reach:
            add("unreachable", p["id"], num[p["id"]])
    return out


def endings(data: dict | None) -> list[int]:
    return [p["id"] for p in (data or {}).get("pages", []) if p.get("kind", "scene") != "scene"]


def clean_as(kind: str, data, folder: Path | None = None) -> dict:
    """`clean` of the book type."""
    if kind == "picture":
        from . import picturebooks
        return picturebooks.clean(data, folder)
    return clean(data, folder)


def check_as(kind: str, data: dict, title: str = "x") -> list[dict]:
    """`check` of the book type."""
    if kind == "picture":
        from . import picturebooks
        return picturebooks.check(data, title)
    return check(data, title)


def empty_book(kind: str) -> dict:
    if kind == "picture":
        return {"cover": {"pic": None}, "pages": [{"id": 1, "layout": "top", "text": "", "pic": None}]}
    return {"start": 1, "pages": [{"id": 1, "kind": "scene", "text": "", "pic": None, "give": None,
                                   "choices": [{"t": "", "to": None, "need": None}, {"t": "", "to": None, "need": None}]}]}


# ---------------------------------------------------------------- templates (texts in stories_templates.json)
# page: (id, kind, emoji, gives item key, [(target, needs item key), …])
TEMPLATES: dict[str, dict] = {
    "jungle": {"emoji": "🌴", "color": 3, "bg": {}, "pages": [
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
    "space": {"emoji": "🚀", "color": 5, "bg": {3: "desert", 4: "desert", 5: "desert", 7: "kidsroom"}, "pages": [
        (1, "scene", "🚀", None, [(2, None), (3, None)]),
        (2, "scene", "🌕", "stone", [(3, None), (6, None)]),
        (3, "scene", "👽", None, [(4, None), (5, None), (8, "stone")]),
        (4, "scene", "🛸", None, [(8, None), (7, None)]),
        (5, "bad", "🪨", None, []),
        (6, "bad", "🌑", None, []),
        (7, "good", "📸", None, []),
        (8, "good", "🌌", None, []),
    ]},
    "castle": {"emoji": "🏰", "color": 7, "bg": {2: "attic", 3: "cave", 5: "attic", 7: "attic"}, "pages": [
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
    "sea": {"emoji": "🐠", "color": 4, "bg": {1: "beach", 4: "pirate", 6: "beach", 7: "pirate"}, "pages": [
        (1, "scene", "🤿", None, [(2, None), (3, None)]),
        (2, "scene", "🪸", "shell", [(4, None), (3, None)]),
        (3, "scene", "🐙", None, [(5, "shell"), (6, None), (8, None)]),
        (4, "scene", "🐢", None, [(7, None), (3, None)]),
        (5, "good", "🧜", None, []),
        (6, "bad", "🩴", None, []),
        (7, "good", "💰", None, []),
        (8, "bad", "🖤", None, []),
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
        p = {"id": pid, "kind": kind, "text": tx[f"p{pid}"], "pic": {"k": "emoji", "v": emoji},
             "bg": t["bg"].get(pid, {"jungle": "jungle", "space": "space", "castle": "castle", "sea": "deepsea"}[key])}
        if kind == "scene":
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
IMPORT_MAX = 1_000_000            # characters of a pasted answer / file
IMPORT_BOOKS = 5                  # books in one file
_KIND_OUT = {"scene": "scene", "good": "good_ending", "bad": "bad_ending"}
_KIND_IN = {v: k for k, v in _KIND_OUT.items()} | {"good": "good", "bad": "bad", "ending": "good"}
AI_INSTRUCTIONS = [
    "This file belongs to Family Quest, a family app in Home Assistant. Children (about 6–14) and adults write and read "
    "choose-your-path adventure books with it.",
    "Your answer must be ONE JSON object in exactly this structure – no text before or after it, no Markdown code fence, "
    "no comments. Keep all keys that start with '_' unchanged (they only explain the format).",
    "If you got this file with a book (an export), change, extend or translate it as the user asks. If you got it as a "
    "template, replace the example book with a new book about the idea the user describes.",
    "A book is a list of pages. 'scene' pages tell what happens and offer 2 to 4 choices; each choice leads to another "
    "page ('goes_to' = the 'id' of that page). 'good_ending' and 'bad_ending' pages end the story and have no choices.",
    "Rules (the app checks them): the first page in 'start' is a scene; every scene has 2–4 choices, every choice has a "
    "short text and a 'goes_to' that exists; at least one good ending; every page can be reached from the start; paths "
    "may meet again (two choices may lead to the same page). Aim for 8–20 pages and 2–5 endings, good and bad ones.",
    "Items (optional, keep it simple): a scene can give ONE item with 'gives' (an emoji and a short name, e.g. "
    "'🍌 Banana'). A choice can need an item with 'needs' (exactly the same text); it is only shown to readers who have "
    "it. Every scene needs at least one choice without 'needs', and only use items that some page gives.",
    "Pictures: 'picture' is ONE emoji per page (no images, no links). 'background' is one id from '_backgrounds' (or "
    "leave it out).",
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
        "picture": "One emoji (optional).",
        "background": "One background id from '_backgrounds' (optional).",
        "gives": "Scenes only, optional: the item the reader finds here, e.g. '🗝️ Old key'.",
        "choices": "Scenes only: 2–4 choices {'text', 'goes_to', optional 'needs'}.",
    },
}


def export_book(title: str, emoji: str, lang: str, data: dict) -> dict:
    """A book in the file format. Own drawings and photos stay out (they are files of this family) – only emoji pictures."""
    ids = {p["id"]: f"p{i + 1}" for i, p in enumerate(data.get("pages") or [])}
    pages = []
    for p in data.get("pages") or []:
        out = {"id": ids[p["id"]], "type": _KIND_OUT[p["kind"]], "text": p["text"]}
        if p.get("pic") and p["pic"]["k"] == "emoji":
            out["picture"] = p["pic"]["v"]
        if p.get("bg"):
            out["background"] = p["bg"]
        if p["kind"] == "scene":
            if p.get("give"):
                out["gives"] = p["give"]
            out["choices"] = [{k: v for k, v in (("text", c["t"]), ("goes_to", ids.get(c["to"])), ("needs", c["need"])) if v is not None}
                              for c in p.get("choices") or []]
        pages.append(out)
    return {"title": title, "emoji": emoji, "language": lang, "start": ids.get(data.get("start")), "pages": pages}


def story_document(books: list[dict], example: bool = False) -> dict:
    if example:
        t = template("jungle", "en")
        books = [export_book(t["title"], t["emoji"], t["lang"], t["data"])]
    return {"_format": STORY_FORMAT, "_ai_instructions": AI_INSTRUCTIONS, "_field_guide": AI_GUIDE,
            "_backgrounds": BACKGROUNDS, "_note": "Own drawings and photos are not part of the file – only emoji pictures.",
            "books": books}


def import_books(text) -> list[dict]:
    """Books from a file or a pasted AI answer (JSON, also in a code fence with sentences around it): [{type, title,
    emoji, lang, data}] – cleaned and limited; ids, authors and anything else from the file are not trusted.
    Adventure books (family-quest-story/1) and picture books (family-quest-picturebook/1) – also both in one file."""
    from . import picturebooks
    from .ai_format import strip_meta
    from .jsonish import loads
    if not isinstance(text, str) or not text.strip():
        raise CommunityError("Paste the answer of the AI or choose a file")
    if len(text) > IMPORT_MAX:
        raise CommunityError("The file is too large")
    try:
        doc = loads(text)
        fmt = doc.get("_format") if isinstance(doc, dict) else None
        doc = strip_meta(doc)
    except (ValueError, RecursionError):
        raise CommunityError("No book found – is it the JSON of an adventure book?") from None
    raw = doc.get("books") if isinstance(doc, dict) and isinstance(doc.get("books"), list) else [doc] if isinstance(doc, dict) else doc
    if not isinstance(raw, list):
        raw = []
    out = []
    for b in raw[:IMPORT_BOOKS]:
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
            pic = p.get("picture")
            page = {"id": pid, "kind": kind, "text": p.get("text"), "bg": p.get("background"),
                    "pic": {"k": "emoji", "v": pic} if isinstance(pic, str) and pic.strip() and len(pic) <= EMOJI else None}
            if kind == "scene":
                page["give"] = p.get("gives") if isinstance(p.get("gives"), str) else None
                page["choices"] = [{"t": c.get("text"), "to": ids.get(str(c.get("goes_to"))),
                                    "need": c.get("needs") if isinstance(c.get("needs"), str) else None}
                                   for c in (p.get("choices") if isinstance(p.get("choices"), list) else []) if isinstance(c, dict)]
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

    # ---------------------------------------------------------------- settings
    @staticmethod
    def _clean_settings(d: dict, s: dict) -> dict:
        from .picturebooks import SAMPLES
        s = dict(s)
        if isinstance(d.get("off"), list):
            s["off"] = sorted({int(x) for x in d["off"] if isinstance(x, int) or str(x).isdigit()})
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
        if b["author_id"] == prof["id"]:
            return True
        if b["visibility"] == "me":
            return False
        if oversee and self._parent(prof):
            return True
        if not b["live"] or not b["approved"]:
            return False
        return b["visibility"] == "family" or prof.get("role") != "parent"

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
    def shelf(self, prof: dict, oversee: bool = False, lang: str | None = None) -> dict:
        self._need(prof)
        pid, parent = prof["id"], self._parent(prof)
        oversee = oversee and parent
        people = self._people()
        samples = self._samples()
        hidden = self.settings()["samples_off"]
        reads = {r["story_id"]: r for r in self.db.q("SELECT * FROM story_read WHERE profile_id=?", pid)}
        stats = {r["story_id"]: r for r in self.db.q(
            """SELECT story_id, COUNT(*) AS readers, AVG(rating) AS avg, COUNT(rating) AS votes FROM story_read
               WHERE finished > 0 GROUP BY story_id""")}
        books, privates, sample_list = [], [], []
        for b in self.db.q("SELECT * FROM story ORDER BY COALESCE(published_at, updated_at) DESC, id DESC"):
            mine = b["author_id"] == pid and not b["sample"]
            a = people.get(b["author_id"]) or {"id": None, "name": "?", "avatar": {}}
            if b["sample"]:
                if b["sample"] not in samples:
                    continue
                b, live = self._localized(b, lang)
                data = live
                a = {"id": None, "name": "Family Quest", "avatar": {}}
            elif self._private(prof, b):
                if oversee:                                    # parents: only that it exists – no title, no content
                    privates.append({"id": b["id"], "private": True, "visibility": "me", "type": b["type"],
                                     "author": {"id": a["id"], "name": a["name"], "avatar": a["avatar"]},
                                     "pages": len(json.loads(b["data"])["pages"]), "created_at": b["created_at"], "updated_at": b["updated_at"]})
                continue
            elif not (mine or (oversee and not b["live"]) or self.visible(prof, b, oversee)):
                continue
            else:
                live = json.loads(b["live"]) if b["live"] else None
                data = json.loads(b["data"])
            r = reads.get(b["id"])
            st = stats.get(b["id"]) or {}
            book = {
                "id": b["id"], "type": b["type"], "title": b["title"], "emoji": b["emoji"], "color": b["color"], "lang": b["lang"],
                "author": {"id": a["id"], "name": a["name"], "avatar": a["avatar"]}, "mine": mine, "sample": b["sample"],
                "edit": self._may_edit(prof, b), "live": bool(live), "pending": bool(b["pending"]),
                "visibility": b["visibility"], "shared": bool(live and b["approved"] and b["visibility"] != "me"),
                "changed": bool(live) and live != data and not b["sample"], "pages": len(data["pages"]),
                "finished": (r or {}).get("finished", 0),
                "rating": round(st["avg"], 1) if st.get("avg") else None, "votes": st.get("votes", 0),
                "readers": st.get("readers", 0), "my_rating": (r or {}).get("rating"),
                "updated_at": b["updated_at"], "published_at": b["published_at"]}
            if b["type"] == "picture":
                n = len((live or data)["pages"])
                at = min(max((r or {}).get("page") or 0, 0), n) if live else 0
                book.update({"cover": (live or data).get("cover", {}).get("pic"), "cover_bg": None, "endings": 0, "found": 0,
                             "at": at, "reading": bool(live and 0 < at < n)})
            else:
                ends = endings(live)
                found = [e for e in json.loads(r["endings"]) if e in ends] if r else []
                cover = (live or data).get("pages") or []
                first = next((p for p in cover if p["id"] == (live or data).get("start")), None)
                book.update({"cover": first["pic"] if first and first.get("pic") and first["pic"]["k"] == "img" else None,
                             "cover_bg": first.get("bg") if first else None, "endings": len(ends), "found": len(found),
                             "reading": bool(r and live and r["page"] != live["start"]
                                             and any(p["id"] == r["page"] and p.get("kind") == "scene" for p in live["pages"]))})
            if b["sample"]:
                book["hidden"] = b["sample"] in hidden
                if not book["hidden"] or oversee:
                    sample_list.append(book)
                continue
            books.append(book)
        s = self.settings()
        return {"books": books, "samples": sample_list, "private": privates, "approval": s["approval"],
                "rewards": {k: s[k] for k in ("write_coins", "write_xp", "read_coins", "read_xp")}, "types": list(TYPES),
                "creatable": list(CREATABLE), "pending": sum(1 for b in books if b["pending"]) if oversee else 0,
                "parent": parent, "oversee": oversee}

    def pending_count(self) -> int:
        return int(self.db.val("SELECT COUNT(*) FROM story WHERE pending IS NOT NULL", default=0))

    def _count(self) -> int:
        return int(self.db.val("SELECT COUNT(*) FROM story WHERE sample IS NULL", default=0))

    # ---------------------------------------------------------------- writing
    def create(self, prof: dict, title: str = "", emoji: str = "📖", color: int = 0, lang: str = "en", tpl: str | None = None,
               visibility: str = "family", kind: str = "adventure") -> int:
        self._need(prof)
        if kind == "game":
            raise CommunityError("Adventure games are coming later")
        if kind not in CREATABLE:
            raise CommunityError("Unknown book type")
        if self._count() >= MAX_BOOKS:
            raise CommunityError("The bookshelf is full – remove an old book first")
        if tpl and kind == "adventure":
            t = template(tpl, lang)
            m = self._meta(title or t["title"], t["emoji"], t["color"], lang if lang in LANGS else t["lang"])
            data = clean(t["data"])
        else:
            m = self._meta(title, emoji if kind == "adventure" or emoji != "📖" else "📕", color, lang)
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
        if self._count() + len(books) > MAX_BOOKS:
            raise CommunityError("The bookshelf is full – remove an old book first")
        return [self.db.x("INSERT INTO story(title, emoji, color, lang, author_id, data, visibility, type) VALUES(?,?,?,?,?,?,'me',?)",
                          b["title"], b["emoji"], 0, b["lang"], prof["id"], json.dumps(b["data"], ensure_ascii=False), b["type"])
                for b in books]

    def export(self, prof: dict, sid: int) -> dict:
        b = self._edit(prof, sid)
        if b["type"] == "picture":
            from . import picturebooks
            return picturebooks.document([picturebooks.export_book(b["title"], b["emoji"], b["lang"], json.loads(b["data"]))])
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
        """Publish the working copy: «live» – or «pending» when a parent has to approve it first (never for «only me»)."""
        with self.db.tx():
            b = self._edit(prof, sid)
            data = json.loads(b["data"])
            if check_as(b["type"], data, b["title"]):
                raise CommunityError("The book is not finished yet – the checker shows what is missing")
            need = self._approval(prof)
            if b["visibility"] != "me" and need:
                self.db.x("UPDATE story SET pending=? WHERE id=?", b["data"], sid)
                return "pending"
            self._go_live(b, b["data"], approved=not need)
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
        with self.db.tx():
            b = self._book(sid)
            if not b["pending"] or b["visibility"] == "me":
                raise CommunityError("This book does not wait for approval")
            if check_as(b["type"], json.loads(b["pending"]), b["title"]):
                raise CommunityError("The book is not finished yet – the checker shows what is missing")
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
        self._gc()

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

    def check_svg(self, prof: dict, svg: str) -> str:
        """An own SVG drawing for a picture book, cleaned (the editor shows what is left) – or why it cannot be used."""
        from .svgsafe import SvgError, clean_svg
        self._need(prof)
        try:
            return clean_svg(svg)
        except SvgError as e:
            if str(e) == "too large":
                raise CommunityError("The SVG picture is too large (max. 12 KB)") from None
            raise CommunityError("This is not a usable SVG picture (<svg viewBox=…> with simple shapes)") from None

    def _gc(self) -> None:
        """Remove pictures no book uses any more (not fresh uploads: the book that uses them is not saved yet)."""
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
        ids = {p["id"] for p in live["pages"]}
        if r["page"] not in ids:                              # new reader – or the page is gone in a new version
            self._move(r, live, live["start"], [])
        return r

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
        p = next(x for x in live["pages"] if x["id"] == r["page"])
        items = json.loads(r["items"])
        ends = endings(live)
        found = [e for e in json.loads(r["endings"]) if e in ends]
        page = {"id": p["id"], "kind": p["kind"], "text": p["text"], "pic": p["pic"], "bg": p.get("bg"), "give": p.get("give"),
                "start": p["id"] == live["start"],
                "choices": [{"i": i, "t": c["t"], "need": c["need"]} for i, c in enumerate(p.get("choices", []))
                            if not c["need"] or c["need"] in items]}
        return {"id": b["id"], "type": b["type"], "title": b["title"], "emoji": b["emoji"], "color": b["color"], "lang": b["lang"],
                "page": page, "items": items, "endings": len(ends), "found": len(found), "new_ending": new_ending,
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
            else:
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
            self._move(r, live, c["to"], items)
            nxt = next(x for x in live["pages"] if x["id"] == c["to"])
            new = False
            if nxt["kind"] != "scene":
                found = json.loads(r["endings"])
                new = nxt["id"] not in found
                if new:
                    found.append(nxt["id"])
                r["endings"] = json.dumps(found)
                self._finished(b, r, prof)
        return self._view(b, live, r, prof, new_ending=new)

    def rate(self, prof: dict, sid: int, stars: int, oversee: bool = False) -> None:
        b, live = self._live(prof, sid, oversee)
        if b["author_id"] == prof["id"]:
            raise CommunityError("You cannot rate your own book")
        if not isinstance(stars, int) or not 1 <= stars <= 5:
            raise CommunityError("Give 1 to 5 stars")
        if not self.db.x("UPDATE story_read SET rating=? WHERE story_id=? AND profile_id=? AND finished > 0", stars, sid, prof["id"]):
            raise CommunityError("Read the book to an end first")
