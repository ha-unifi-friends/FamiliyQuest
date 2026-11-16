"""Photo or PDF of a word list → draft pack, using the Claude API (optional).

Only active when an Anthropic API key is configured. The result is always a draft:
a parent checks it in the editor before children see it. Packs made from school
material stay private (privat: true) and are never published.
"""
from __future__ import annotations

import base64
import json
import logging

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


def draft_from_document(fq, name: str, raw: bytes) -> list[dict]:
    try:
        import anthropic
    except ImportError:
        raise PackError("the anthropic package is not installed") from None
    if len(raw) > MAX_BYTES:
        raise PackError("file too large (max. 20 MB)")
    ext = "." + name.lower().rsplit(".", 1)[-1]
    data = base64.standard_b64encode(raw).decode("ascii")
    if ext == ".pdf":
        block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
    else:
        block = {"type": "image", "source": {"type": "base64", "media_type": IMAGE_TYPES[ext], "data": data}}
    client = anthropic.Anthropic(api_key=fq.settings.anthropic_api_key)
    try:
        # server-side fallback: if the model declines, the API retries on a suitable model in the same call
        resp = client.beta.messages.create(
            model=fq.settings.anthropic_model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": [block, {"type": "text", "text": PROMPT.format(name=name)}]}],
        )
    except anthropic.AuthenticationError:
        raise PackError("the Anthropic API key is not valid") from None
    except anthropic.RateLimitError:
        raise PackError("too many requests to the Claude API – try again in a minute") from None
    except anthropic.APIStatusError as e:
        raise PackError(f"Claude API error {e.status_code}: {e.message}") from None
    except anthropic.APIConnectionError:
        raise PackError("cannot reach the Claude API") from None
    if resp.stop_reason == "refusal":
        raise PackError("the page could not be processed")
    if resp.stop_reason == "max_tokens":
        raise PackError("the page is too long – split it into several photos")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        out = json.loads(text)
    except ValueError:
        raise PackError("unexpected answer from the Claude API") from None
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
