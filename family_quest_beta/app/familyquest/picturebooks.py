"""📕 Picture books on the family bookshelf (the shelf, visibility, approval, rewards and reading progress: stories.py).

A picture book is a cover and a list of pages, read page by page (no choices). A page has a layout – «top» (the picture
on top, the text below), «full» (the picture fills the page, the text lies on it) or «text» (text only) – a text and a
picture:
- {"k": "lib", "v": key}   one of the shipped SVG scenes (web/img/stories/<key>.svg, stories.BACKGROUNDS)
- {"k": "svg", "v": "<svg …>"}  an SVG drawing inside the book – strictly cleaned (svgsafe.py), shown as an <img>
- {"k": "img", "v": name, "src": "draw" | "photo"}  an own drawing or a photo (the upload rules of the adventure books)
- {"k": "emoji", "v": "🐻"}  one big emoji
Reading progress per reader: the last page read (0 = the cover) and how often the book was read to the end.

The app ships sample books (`SAMPLES`, texts in every app language in picturebook_sample.json, author «Family Quest»);
each reader gets the sample in the language of the app.
"""
from __future__ import annotations

import json
from pathlib import Path

from .community import CommunityError
from .i18n import _t
from .svgsafe import SVG_MAX, safe_svg

LAYOUTS = ("top", "full", "text")
MAX_PAGES = 60
TEXT = 600                      # characters of one page
MAX_BYTES = 900_000             # JSON of one book (inline SVG pictures included)
MSG = {
    "title": _t("Give the book a title"),
    "empty": _t("The book has no pages yet"),
    "no_text": _t("Page {0} has no text yet"),
    "no_pic": _t("Page {0} has no picture yet"),
}


def _text(v, n: int) -> str:
    return str(v or "").replace("\r\n", "\n").replace("\x00", "")[:n].strip()


def clean_pic(p, folder: Path | None) -> dict | None:
    from .stories import BACKGROUNDS, clean_pic as story_pic
    if not isinstance(p, dict):
        return None
    if p.get("k") == "lib":
        return {"k": "lib", "v": p["v"]} if p.get("v") in BACKGROUNDS else None
    if p.get("k") == "svg":
        svg = safe_svg(p.get("v"))
        return {"k": "svg", "v": svg} if svg else None
    return story_pic(p, folder)


def clean(data, folder: Path | None = None) -> dict:
    """A valid picture book (working copy): every field checked and limited – incomplete books are fine."""
    if not isinstance(data, dict):
        data = {}
    raw = data.get("pages") if isinstance(data.get("pages"), list) else []
    if len(raw) > MAX_PAGES:
        raise CommunityError("A book can have at most 60 pages")
    pages, seen = [], set()
    for p in raw:
        if not isinstance(p, dict):
            continue
        try:
            pid = int(p.get("id"))
        except (TypeError, ValueError):
            continue
        if not 1 <= pid <= 9999 or pid in seen:
            continue
        seen.add(pid)
        layout = p.get("layout") if p.get("layout") in LAYOUTS else "top"
        pic = None if layout == "text" else clean_pic(p.get("pic"), folder)
        pages.append({"id": pid, "layout": layout, "text": _text(p.get("text"), TEXT), "pic": pic})
    cover = data.get("cover") if isinstance(data.get("cover"), dict) else {}
    out = {"cover": {"pic": clean_pic(cover.get("pic"), folder)}, "pages": pages}
    if len(json.dumps(out, ensure_ascii=False)) > MAX_BYTES:
        raise CommunityError("The book is too long – make some pages shorter")
    return out


def check(data: dict, title: str = "x") -> list[dict]:
    """What is missing before the book can be published: [{code, msg, args, page}] – empty means ready."""
    out: list[dict] = []

    def add(key: str, page: int | None = None, *args) -> None:
        out.append({"code": key, "msg": MSG[key], "args": [str(a) for a in args], "page": page})

    if not str(title or "").strip():
        add("title")
    pages = data.get("pages") or []
    if not pages:
        add("empty")
    for n, p in enumerate(pages, start=1):
        if not p["text"] and (p["layout"] == "text" or not p.get("pic")):
            add("no_text", p["id"], n)
        if p["layout"] != "text" and not p.get("pic"):
            add("no_pic", p["id"], n)
    return out


def view_page(p: dict) -> dict:
    return {"id": p["id"], "layout": p["layout"], "text": p["text"], "pic": p.get("pic")}


# ---------------------------------------------------------------- file format (export, template for an AI, import)
FORMAT = "family-quest-picturebook/1"
_LAYOUT_OUT = {"top": "picture_top", "full": "full_picture", "text": "text_only"}
_LAYOUT_IN = {v: k for k, v in _LAYOUT_OUT.items()} | {k: k for k in LAYOUTS} | {
    "picture_on_top": "top", "image_top": "top", "full_page": "full", "full_page_picture": "full", "fullpage": "full",
    "overlay": "full", "text": "text", "textonly": "text"}
SVG_RULES = [
    "An own picture is ONE <svg> element as a JSON string: start with <svg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 400 300'> (landscape 4:3 – always give a viewBox) and use single quotes inside it so the JSON stays valid.",
    f"Max. {SVG_MAX // 1000} KB per picture after cleaning – simple, flat shapes look best: path, circle, ellipse, rect, line, "
    "polyline, polygon, g, defs with linearGradient / radialGradient / clipPath. Attributes: fill, stroke, stroke-width, "
    "opacity, transform, gradient stops; colours as #hex or names.",
    "Not allowed (removed, or the picture is refused): script, foreignObject, image, use, style elements and style "
    "attributes, links (href), events (onload, onclick …), external files or fonts, DOCTYPE, CSS.",
    "Paint a full background (sky, room, cave …) as the first shape so the picture works on light and dark screens. "
    "Avoid text in pictures – the story text is on the page; at most a word or two.",
    "Keep the characters the same on every page (same colours, same hat, same clothes) so the reader recognises them.",
]
AI_INSTRUCTIONS = [
    "This file belongs to Family Quest, a family app in Home Assistant. Children (about 3–12) and adults write and read "
    "picture books with it: pages with a picture and a short text, read page by page.",
    "Your answer must be ONE JSON object in exactly this structure – no text before or after it, no Markdown code fence, "
    "no comments. Keep all keys that start with '_' unchanged (they only explain the format).",
    "If you got this file with a book (an export), change, extend or translate it as the user asks. If you got it as a "
    "template, replace the example book with a new picture book about the idea the user describes.",
    "A picture book has a 'title', a 'cover' picture and 6–20 'pages'. Every page has a 'layout' ('picture_top', "
    "'full_picture' or 'text_only'), a 'text' (1–4 short sentences, max. 600 characters) and – except 'text_only' – a 'picture'.",
    "A 'picture' is exactly one of: {'svg': '<svg …>…</svg>'} (an own drawing, see '_svg_rules'), {'library': '<id>'} "
    "(one of the ready-made scenes in '_library') or {'emoji': '🐻'} (one emoji).",
    "Suitable for children: friendly, funny, warm; no violence, nothing scary in a bad way. Short sentences, read aloud well.",
    "Write in the language the user writes in (or the one they ask for) and set 'language' to it: one of "
    "en, de-DE, de-CH, fr-FR, it-IT, es-ES, nl-NL, pl-PL, pt-BR, sv-SE.",
]
AI_GUIDE = {
    "books[]": {
        "type": "Always 'picture_book'.",
        "title": "Title of the book, max. 80 characters.",
        "emoji": "One emoji for the shelf.",
        "language": "Language of the texts (see the instructions).",
        "cover": "{'picture': {…}} – the picture of the cover page (the app writes the title and the author on it).",
        "pages": "The pages in reading order.",
    },
    "pages[]": {
        "layout": "'picture_top' (picture on top, text below), 'full_picture' (the picture fills the page, the text lies on "
                  "it – keep the text short) or 'text_only'.",
        "text": "What the page tells, max. 600 characters.",
        "picture": "{'svg': …} or {'library': …} or {'emoji': …} – not for 'text_only'.",
    },
}


def export_pic(p: dict | None) -> dict | None:
    if not p:
        return None
    if p["k"] == "svg":
        return {"svg": p["v"]}
    if p["k"] == "lib":
        return {"library": p["v"]}
    if p["k"] == "emoji":
        return {"emoji": p["v"]}
    return None                                  # own drawings and photos are files of this family


def export_book(title: str, emoji: str, lang: str, data: dict) -> dict:
    pages = []
    for p in data.get("pages") or []:
        out = {"layout": _LAYOUT_OUT[p["layout"]], "text": p["text"]}
        pic = export_pic(p.get("pic"))
        if pic:
            out["picture"] = pic
        pages.append(out)
    cover = export_pic((data.get("cover") or {}).get("pic"))
    return {"type": "picture_book", "title": title, "emoji": emoji, "language": lang, **({"cover": {"picture": cover}} if cover else {}),
            "pages": pages}


def document(books: list[dict], example: bool = False) -> dict:
    from .stories import BACKGROUNDS
    if example:
        s = sample("dwarf", "en")
        books = [export_book(s["title"], s["emoji"], s["lang"], s["data"])]
    return {"_format": FORMAT, "_ai_instructions": AI_INSTRUCTIONS, "_svg_rules": SVG_RULES, "_field_guide": AI_GUIDE,
            "_library": BACKGROUNDS, "_note": "Own drawings and photos are not part of the file – SVG, library and emoji pictures are.",
            "books": books}


def import_pic(v) -> dict | None:
    from .stories import BACKGROUNDS, EMOJI
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("<"):
            v = {"svg": s}
        elif s in BACKGROUNDS:
            v = {"library": s}
        elif s and len(s) <= EMOJI:
            v = {"emoji": s}
    if not isinstance(v, dict):
        return None
    if isinstance(v.get("svg"), str):
        return clean_pic({"k": "svg", "v": v["svg"]}, None)
    lib = v.get("library") or v.get("background")
    if isinstance(lib, str):
        return clean_pic({"k": "lib", "v": lib.strip()}, None)
    e = v.get("emoji")
    if isinstance(e, str) and e.strip() and len(e.strip()) <= EMOJI:
        return {"k": "emoji", "v": e.strip()}
    return None


def is_picture_book(doc_format, b: dict) -> bool:
    if str(b.get("type") or "").strip().lower().replace(" ", "_") in ("picture_book", "picturebook", "picture"):
        return True
    if "picturebook" in str(doc_format or ""):
        return True
    pages = b.get("pages") if isinstance(b.get("pages"), list) else []
    return bool(pages) and not any(isinstance(p, dict) and p.get("choices") for p in pages) \
        and any(isinstance(p, dict) and ("layout" in p or isinstance(p.get("picture"), dict)) for p in pages)


def import_book(b: dict) -> dict:
    """One picture book from a file or an AI answer: {type, title, emoji, lang, data} – cleaned and limited."""
    from .stories import EMOJI, LANGS, TITLE, template_lang
    raw = b.get("pages") if isinstance(b.get("pages"), list) else []
    if len(raw) > MAX_PAGES:
        raise CommunityError("A book can have at most 60 pages")
    pages = []
    for p in raw:
        if isinstance(p, str):
            p = {"text": p}
        if not isinstance(p, dict):
            continue
        lay = _LAYOUT_IN.get(str(p.get("layout") or "").strip().lower().replace("-", "_"))
        pic = import_pic(p.get("picture") if "picture" in p else p.get("image"))
        if lay is None:
            lay = "top" if pic else "text"
        pages.append({"id": len(pages) + 1, "layout": lay, "text": p.get("text"), "pic": pic})
    cover = b.get("cover")
    cpic = import_pic(cover.get("picture") if isinstance(cover, dict) else cover)
    lang = b.get("language") if b.get("language") in LANGS else template_lang(str(b.get("language") or "en"))
    return {"type": "picture", "title": _text(b.get("title"), TITLE) or "?", "emoji": _text(b.get("emoji"), EMOJI) or "📕",
            "lang": lang, "data": clean({"cover": {"pic": cpic}, "pages": pages})}


# ---------------------------------------------------------------- the sample books (picturebook_sample.json)
SAMPLES = ("dwarf",)
_SAMPLE: dict | None = None


def sample_file() -> dict:
    global _SAMPLE
    if _SAMPLE is None:
        _SAMPLE = json.loads((Path(__file__).parent / "picturebook_sample.json").read_text(encoding="utf-8"))
    return _SAMPLE


def sample(key: str, lang: str) -> dict:
    """A sample book in one language (the nearest one, English as the last choice): {title, emoji, color, lang, data}."""
    s = sample_file()[key]
    texts = s["texts"]
    lang = lang if lang in texts else next((k for k in texts if k.split("-")[0] == str(lang or "").split("-")[0]), "en")
    tx = texts[lang]
    pages = [{"id": i + 1, "layout": lay, "text": t, "pic": {"k": "svg", "v": svg}}
             for i, (lay, t, svg) in enumerate(zip(s["layouts"], tx["pages"], s["pics"]))]
    return {"title": tx["title"], "emoji": s["emoji"], "color": s["color"], "lang": lang,
            "data": {"cover": {"pic": {"k": "svg", "v": s["cover"]}}, "pages": pages}}
