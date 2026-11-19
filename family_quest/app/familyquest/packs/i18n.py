"""Packs in the viewer's language.

main.py sets the viewer's language for every request (header X-FQ-Lang, see gamewords.lang_of); PackStore.get then
hands out the pack in that language: title, unit titles, description and – for packs whose cards carry several prompt
languages (`quellsprachen`) – the prompt side of every card. The card keys (progress) are always made from the
canonical prompt (`quellsprache`), so switching the language keeps the learning progress.

Fallback for the prompt language: the app language, else the family language (setting `family_lang`, the language of
the parent area), else English, else the canonical prompt. A language course never uses the language it teaches as
prompt language.
"""
from __future__ import annotations

from contextvars import ContextVar, Token

APP_LANGS = ("de", "en", "fr", "it", "es", "nl", "pl", "pt", "sv")
LANG_NAMES = {"de": "German", "en": "English", "fr": "French", "it": "Italian", "es": "Spanish", "nl": "Dutch",
              "pl": "Polish", "pt": "Portuguese", "sv": "Swedish"}

_VIEWER: ContextVar[str] = ContextVar("familyquest_pack_lang", default="")


def base(code: str | None) -> str:
    """'fr-FR' → 'fr', 'de-CH' → 'de'; own languages ('x-…') and unknown codes → ''."""
    b = str(code or "").strip().lower().split("-")[0]
    return b if b in APP_LANGS else ""


def set_viewer(code: str | None) -> Token:
    return _VIEWER.set(base(code))


def reset_viewer(token: Token) -> None:
    _VIEWER.reset(token)


def viewer() -> str:
    return _VIEWER.get()


def chain(lang: str, family: str = "") -> list[str]:
    """Languages to try, best first."""
    out = []
    for l in (lang, family, "en"):
        if l and l not in out:
            out.append(l)
    return out


def pick(texts: dict | None, default: str, lang: str, family: str = "") -> str:
    """A text in the viewer's language: the own language if there is one; for an own (x-…) language or none, the
    family language or English. Else the default (the text as written in the pack)."""
    if not texts or not lang:
        return default
    if texts.get(lang):
        return texts[lang]
    return default


def source_lang(canon: str, available: list[str], target: str, lang: str, family: str = "") -> str:
    """The prompt language for this viewer: one the cards carry, never the language that is learnt."""
    have = [l for l in [canon, *available] if l and l != target]
    for l in chain(lang, family):
        if l in have:
            return l
    return canon
