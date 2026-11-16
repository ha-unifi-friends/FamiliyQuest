"""Photo or PDF of a word list → draft pack, using the AI of Home Assistant (optional).

Uses Home Assistant's «AI Task» (ai_task.generate_data) – whatever AI the family set up there (OpenAI, Google,
Anthropic, a local Ollama …). Only active when Home Assistant has an AI Task entity. The file is put into the media
folder for the moment of the call (Home Assistant hands it to the AI as an attachment) and deleted right after.
The result is always a draft: a parent checks it in the editor before children see it. Packs made from school
material stay private (privat: true) and are never published.
"""
from __future__ import annotations

import json
import logging
import secrets

from ..packs.loader import PackError
from .common import draft_from_dict, suggest_meta

log = logging.getLogger("familyquest.ai")

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
DOC_EXT = tuple(IMAGE_TYPES) + (".pdf",)
MAX_BYTES = 20 * 1024 * 1024

SCHEMA = {
    "type": "object",
    "properties": {
        "titel": {"type": "string"},
        "fach": {"type": "string", "enum": ["deutsch", "mathematik", "nmg", "englisch", "franzoesisch", "italienisch", "allgemein"]},
        "stufe": {"type": "string"},
        "sprache": {"type": "string", "description": "language that is learnt (answer side), e.g. fr, en; empty if none"},
        "quellsprache": {"type": "string"},
        "einheiten": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titel": {"type": "string"},
                    "karten": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "frage": {"type": "string"},
                                "antwort": {"type": "string"},
                                "satz": {"type": "string", "description": "optional example sentence with ___ for the answer"},
                                "hinweis": {"type": "string"},
                                "emoji": {"type": "string"},
                            },
                            "required": ["frage", "antwort", "satz", "hinweis", "emoji"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["titel", "karten"],
                "additionalProperties": False,
            },
        },
        "unsicher": {"type": "array", "items": {"type": "string"},
                     "description": "words or lines that could not be read reliably"},
    },
    "required": ["titel", "fach", "stufe", "sprache", "quellsprache", "einheiten", "unsicher"],
    "additionalProperties": False,
}

PROMPT = """This is a page of school material for a primary school child in Switzerland (word list, vocabulary, \
facts). Turn it into learning cards for a family learning app.

- One card per word or fact. `frage` is what the child sees (usually the German side), `antwort` what it should \
answer (e.g. the French word including its article: "la maison").
- Keep the spelling exactly as printed, with accents. Do not invent words that are not on the page.
- If the page has sections or units, make one unit per section; otherwise one unit.
- `satz`: only when the page has an example sentence – write it with ___ in place of the answer, else "".
- `emoji`: one fitting emoji for concrete nouns, else "". `hinweis`: "" unless the page gives one.
- List anything you could not read reliably in `unsicher`.
The file name was: {name}"""


def is_document(name: str) -> bool:
    return name.lower().endswith(DOC_EXT)


IMPORT_DIR = "family_quest_import"          # inside Home Assistant's media folder, only for the moment of the call


def available(fq) -> bool:
    ha = fq.ha
    return bool(ha and getattr(ha, "connected", False) and hasattr(ha, "ai_task") and ha.ai_task_entities())


def _json(text: str) -> dict:
    """The JSON object in the answer (some AIs wrap it in ``` fences or add a sentence)."""
    text = (text or "").strip()
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        raise PackError("unexpected answer from the AI")
    try:
        return json.loads(text[a:b + 1])
    except ValueError:
        raise PackError("unexpected answer from the AI") from None


def draft_from_document(fq, name: str, raw: bytes) -> list[dict]:
    if len(raw) > MAX_BYTES:
        raise PackError("file too large (max. 20 MB)")
    if not available(fq):
        raise PackError("Photo/PDF import needs an AI in Home Assistant (Settings › Devices & services › AI Task)")
    ext = "." + name.lower().rsplit(".", 1)[-1]
    mime = "application/pdf" if ext == ".pdf" else IMAGE_TYPES[ext]
    folder = fq.settings.ha_media_dir / IMPORT_DIR
    tmp = folder / f"{secrets.token_hex(8)}{ext}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(raw)
    except OSError as e:
        raise PackError(f"cannot write to the media folder of Home Assistant ({e.strerror})") from None
    instructions = PROMPT.format(name=name) + "\n\nAnswer ONLY with one JSON object (no text around it) of this JSON schema:\n" + json.dumps(SCHEMA, ensure_ascii=False)
    try:
        text = fq.ha.ai_task(instructions, f"media-source://media_source/local/{IMPORT_DIR}/{tmp.name}", mime)
    except PackError:
        raise
    except Exception as e:  # noqa: BLE001
        log.warning("AI task failed: %s", e)
        raise PackError(f"the AI in Home Assistant did not answer ({str(e)[:160]})") from None
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    out = _json(text)
    meta = suggest_meta(name)
    pack = {
        "id": meta["id"],
        "titel": out.get("titel") or meta["titel"],
        "fach": out.get("fach") or meta["fach"],
        "stufe": out.get("stufe") or meta["stufe"],
        "sprache": out.get("sprache") or meta["sprache"],
        "quellsprache": out.get("quellsprache") or "de",
        "privat": True,
        "quelle": f"KI-Entwurf aus {name} – bitte prüfen",
        "einheiten": [],
    }
    for i, u in enumerate(out.get("einheiten") or []):
        cards = []
        for c in u.get("karten") or []:
            card = {"frage": c["frage"], "antwort": c["antwort"]}
            for k in ("satz", "hinweis", "emoji"):
                if c.get(k):
                    card[k] = c[k]
            cards.append(card)
        if cards:
            pack["einheiten"].append({"id": f"einheit-{i + 1}", "titel": u.get("titel") or f"Einheit {i + 1}", "karten": cards})
    if not pack["einheiten"]:
        raise PackError("no words found on the page")
    s = draft_from_dict(fq, pack, "ai")
    s["uncertain"] = out.get("unsicher") or []
    return [s]
