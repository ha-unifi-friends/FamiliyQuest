"""The word content of the word games in the players' languages: «Zeichnen & Raten» (zeichnen_data.py), «Wer bin ich?»
(whoami_data.py) and «Verbotene Wörter» (verboten_cards.json).

Every word, character and card is an English source text with its translations in web/i18n/<lang>.json – like every
other text of the app, so the parents' translation editor shows (and overrides) them too. The games keep the English
key in their state and translate it when one player's view is built, in that player's language: the app sends it with
every request (header X-FQ-Lang, shared/ui.js). English shows the key without a «(…)» note ("Book (to read)" → "Book").

A forbidden-words card has two keys: the word and its five forbidden words in one text "bark · cat · pet · leash · bone",
so every language can name the associations that are obvious in it (not just literal translations).

Tables and history entries from before the translation hold the German words: `legacy` maps them back to their key
(else they are shown as they are).
"""
from __future__ import annotations

import re

from .translations import BUILTIN, CODE_RE, Translations, builtin_dict

LANG_HEADER = "x-fq-lang"
LANGS = [l for l in BUILTIN if l != "en"]
SEP = " · "
_NOTE = re.compile(r"\s*\([^()]*\)$")


def clean_lang(code) -> str:
    """A language code the app knows the shape of ("fr-FR", "x-baernduetsch"), else "en"."""
    s = str(code or "").strip()
    if s in BUILTIN or CODE_RE.fullmatch(s):
        return s
    low = s.lower().split("-")[0]
    return next((l for l in LANGS if l.lower().startswith(low + "-")), "en") if re.fullmatch(r"[a-z]{2}", low) else "en"


def lang_of(request) -> str | None:
    """The language of the viewer (header X-FQ-Lang); None without it (the views are English then, and a guess
    counts in every language)."""
    try:
        h = request.headers.get(LANG_HEADER)
    except Exception:  # noqa: BLE001
        return None
    return clean_lang(h) if h else None


def english(key: str) -> str:
    """The English text of a key: without its «(…)» note."""
    return _NOTE.sub("", key) or key


class Words:
    """Translates word keys. With a database the parents' own texts and own languages count too."""

    def __init__(self, db=None):
        self.tx = Translations(db) if db is not None else None

    def base(self, lang: str) -> str:
        lang = clean_lang(lang)
        if lang in BUILTIN:
            return lang
        try:
            return (self.tx.base_of(lang) if self.tx else None) or "en"
        except Exception:  # noqa: BLE001
            return "en"

    def table(self, lang: str) -> dict:
        """key → text for one language (built-in dictionary of its base language, then the family's own texts)."""
        lang = clean_lang(lang)
        base = builtin_dict(self.base(lang))          # cached – never changed here
        own = {}
        if self.tx:
            try:
                own = {k: v for k, v in self.tx.overrides(lang).items() if v}
            except Exception:  # noqa: BLE001
                own = {}
        return {**base, **own} if own else base

    def tr(self, key: str, lang: str, table: dict | None = None) -> str:
        if not key:
            return key
        t = self.table(lang) if table is None else table
        return t.get(key) or english(key)

    def translator(self, lang: str):
        """A function key → text in `lang` (one dictionary lookup for a whole view)."""
        t = self.table(lang)
        return lambda key: (t.get(key) or english(key)) if key else key

    def card(self, word: str, taboo: list[str], lang: str) -> dict:
        """A forbidden-words card in `lang`: the word and its five forbidden words."""
        t = self.table(lang)
        key = SEP.join(taboo)
        words = [w.strip() for w in str(t.get(key) or "").split("·")]
        if len(words) != len(taboo) or not all(words):
            words = [t.get(w) or english(w) for w in taboo]
        return {"word": t.get(word) or english(word), "taboo": words}

    def forms(self, key: str, langs, german: list[str] | None = None) -> list[str]:
        """Every text that names `key` in one of `langs` (and English); the German names (`german`, e.g. the old
        aliases «Rüebli», «Velo») when a German language is among them."""
        langs = {clean_lang(l) for l in (langs or []) if l}
        out = [english(key)]
        de = False
        for l in langs:
            b = self.base(l)
            de = de or b.startswith("de")
            for x in {l, b}:
                if x != "en":
                    out.append(self.tr(key, x))
        if de:
            out += [self.tr(key, "de-DE"), self.tr(key, "de-CH"), *(german or [])]
        seen, res = set(), []
        for s in out:
            if s and s not in seen:
                seen.add(s)
                res.append(s)
        return res
