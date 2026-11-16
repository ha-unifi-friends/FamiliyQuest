"""Shared import logic: merge duplicates, suggest exercise types, store as draft."""
from __future__ import annotations

import re

from ..learning.grading import norm
from ..packs.loader import PackError, parse_doc
from ..packs.schema import Bundle, Pack, card_view, slug

SUBJECT_WORDS = {
    "franzoesisch": ["franz", "français", "francais", "french"],
    "englisch": ["engl", "english"],
    "mathematik": ["mathe", "math", "rechnen"],
    "deutsch": ["deutsch", "german", "artikel"],
    "nmg": ["nmg", "natur", "geo", "thurgau", "kanton", "geschichte"],
    "italienisch": ["ital"],
}
LANG_OF = {"franzoesisch": "fr", "englisch": "en", "italienisch": "it"}


def suggest_meta(name: str) -> dict:
    low = name.lower()
    subject = next((s for s, words in SUBJECT_WORDS.items() if any(w in low for w in words)), "allgemein")
    m = re.search(r"(\d{1,2})\s*\.?\s*(kl|klasse|class|grade)", low)
    level = f"{m.group(1)}. Klasse" if m else ""
    title = re.sub(r"\.(csv|xlsx|xls|yaml|yml|zip|pdf|png|jpe?g|heic|webp)$", "", name, flags=re.I)
    title = re.sub(r"[_]+", " ", title).strip() or "Import"
    return {"titel": title, "fach": subject, "stufe": level, "sprache": LANG_OF.get(subject, ""),
            "quellsprache": "de", "id": slug(title)}


def suggest_exercises(pack: dict, unit: dict) -> list[str]:
    cards = unit.get("karten") or []
    views = [card_view(pack, c) for c in cards]
    if any(v["sentence"] for v in views):
        return ["lueckentext", "auswahl"]
    answers = [norm(v["answer"]) for v in views if v["answer"]]
    distinct = len(set(answers))
    if answers and distinct <= 6 and len(answers) >= 2 * distinct and distinct >= 2:
        return ["zuordnen"]                        # few categories, many items → sort by drag & drop
    if pack.get("sprache"):
        return ["auswahl", "eintippen", "paare", "hoeren", "karteikarte"]
    return ["auswahl", "paare", "karteikarte"]


def merge_duplicates(pack: dict) -> tuple[dict, int]:
    """Cards with the same prompt and answer inside a unit are merged; returns (pack, removed)."""
    removed = 0
    for unit in pack.get("einheiten") or []:
        seen: dict[str, dict] = {}
        keep = []
        for c in unit.get("karten") or []:
            v = card_view(pack, c)
            k = norm(v["prompt"]) + "␟" + norm(v["answer"])
            if k in seen:
                removed += 1
                continue
            seen[k] = c
            keep.append(c)
        if unit.get("karten") is not None:
            unit["karten"] = keep
    return pack, removed


def finish_pack(data: dict) -> dict:
    """Fill gaps a hand-made or generated pack often has."""
    data = dict(data)
    data["id"] = slug(str(data.get("id") or data.get("titel") or "import"))
    for i, u in enumerate(data.get("einheiten") or []):
        u.setdefault("id", f"einheit-{i + 1}")
        if u.get("karten") and not u.get("uebungen"):
            u["uebungen"] = suggest_exercises(data, u)
    data, _ = merge_duplicates(data)
    return data


def store_draft(fq, model: Pack | Bundle, source: str, media: dict | None = None, note: str = "") -> dict:
    existed = fq.db.q1("SELECT status FROM pack WHERE id=?", model.id)
    fq.packs.upsert(model, source, status="draft", media=media, force=True)
    info = fq.packs.get(model.id)
    s = info.summary() if info else {"id": model.id}
    s["replaces"] = bool(existed)
    if note:
        s["note"] = note
    return s


def draft_from_dict(fq, data: dict, source: str, media: dict | None = None) -> dict:
    if "stufenpaket" not in data:
        data = finish_pack(data)
    try:
        model = parse_doc(data)
    except PackError:
        raise
    return store_draft(fq, model, source, media)
