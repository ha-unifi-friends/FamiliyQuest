"""Own translations: parents overwrite single texts of a language or create their own language.

Stored in the setting `translations`:
  {"languages": [{"code": "x-baernduetsch", "name": "Bärndütsch", "base": "de-CH", "flag": "🐻"}],
   "overrides": {"de-CH": {"<English source text>": "<own text>"}, "x-baernduetsch": {...}}}
A custom language starts from its base language (every text it does not overwrite comes from there).
English is the source language – its texts can be overwritten too. CSV import / export per language.
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .db import Database
from .settings import WEB_DIR

BUILTIN = ["en", "de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]
CODE_RE = re.compile(r"x-[a-z0-9]{1,24}")
KEY = "translations"
MAX_TEXT = 2000


class TranslationError(ValueError):
    pass


@lru_cache(maxsize=32)
def _dict(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def builtin_dict(lang: str, extra: str = "") -> dict:
    sub = WEB_DIR / "i18n" / (extra or "")
    return _dict(str(sub / f"{lang}.json")) if lang != "en" else {}


@lru_cache(maxsize=1)
def source_keys() -> list[str]:
    """Every English source text the app knows (app + planer)."""
    keys = set(_dict(str(WEB_DIR / "i18n" / "de-DE.json")))
    keys |= set(_dict(str(WEB_DIR / "i18n" / "planer" / "keys.json")) or [])
    return sorted(keys, key=str.lower)


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)[:24]


class Translations:
    def __init__(self, db: Database):
        self.db = db

    def _data(self) -> dict:
        d = self.db.get_setting(KEY) or {}
        return {"languages": list(d.get("languages") or []), "overrides": dict(d.get("overrides") or {})}

    def _save(self, d: dict) -> None:
        self.db.set_setting(KEY, d)

    # ---------------------------------------------------------------- languages
    def languages(self) -> list[dict]:
        return self._data()["languages"]

    def language(self, code: str) -> dict | None:
        return next((l for l in self.languages() if l["code"] == code), None)

    def base_of(self, code: str) -> str | None:
        if code in BUILTIN:
            return code
        lang = self.language(code)
        return lang["base"] if lang else None

    def add_language(self, name: str, base: str, flag: str = "") -> dict:
        name = (name or "").strip()[:40]
        if not name:
            raise TranslationError("The language needs a name")
        if base not in BUILTIN:
            raise TranslationError("Unknown base language")
        d = self._data()
        code = "x-" + (slug(name) or "lang")
        n = 2
        while any(l["code"] == code for l in d["languages"]):
            code = f"x-{(slug(name) or 'lang')[:22]}{n}"
            n += 1
        lang = {"code": code, "name": name, "base": base, "flag": (flag or "").strip()[:8]}
        d["languages"].append(lang)
        self._save(d)
        return lang

    def update_language(self, code: str, name: str | None = None, flag: str | None = None, base: str | None = None) -> dict:
        d = self._data()
        lang = next((l for l in d["languages"] if l["code"] == code), None)
        if not lang:
            raise TranslationError("Unknown language")
        if name is not None and name.strip():
            lang["name"] = name.strip()[:40]
        if flag is not None:
            lang["flag"] = flag.strip()[:8]
        if base is not None:
            if base not in BUILTIN:
                raise TranslationError("Unknown base language")
            lang["base"] = base
        self._save(d)
        return lang

    def delete_language(self, code: str) -> None:
        d = self._data()
        d["languages"] = [l for l in d["languages"] if l["code"] != code]
        d["overrides"].pop(code, None)
        self._save(d)

    # ---------------------------------------------------------------- texts
    def overrides(self, lang: str) -> dict:
        return dict(self._data()["overrides"].get(lang) or {})

    def standard(self, lang: str) -> dict:
        """What the app shows without own texts: the built-in dictionary (custom language: of its base)."""
        base = self.base_of(lang)
        if base is None:
            raise TranslationError("Unknown language")
        return {**builtin_dict(base, "planer"), **builtin_dict(base)}

    def set_overrides(self, lang: str, texts: dict, merge: bool = False) -> dict:
        if self.base_of(lang) is None:
            raise TranslationError("Unknown language")
        d = self._data()
        cur = dict(d["overrides"].get(lang) or {}) if merge else {}
        for k, v in texts.items():
            k = str(k).strip()
            v = "" if v is None else str(v).strip()
            if not k or len(k) > MAX_TEXT or len(v) > MAX_TEXT:
                continue
            if v:
                cur[k] = v
            else:
                cur.pop(k, None)
        d["overrides"][lang] = cur
        self._save(d)
        return cur

    # ---------------------------------------------------------------- CSV
    def export_csv(self, lang: str) -> str:
        std, own = self.standard(lang), self.overrides(lang)
        out = io.StringIO()
        w = csv.writer(out, delimiter=";", lineterminator="\r\n")
        w.writerow(["key", "standard", "translation"])
        for k in sorted(set(source_keys()) | set(own), key=str.lower):
            w.writerow([k, std.get(k, "" if lang != "en" else k), own.get(k, "")])
        return "﻿" + out.getvalue()      # BOM: Excel opens UTF-8 correctly

    def import_csv(self, lang: str, text: str) -> int:
        """Rows key;…;translation – an empty translation removes the own text. Returns the number of own texts read."""
        text = text.lstrip("﻿")
        if not text.strip():
            raise TranslationError("The file is empty")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"
        rows = list(csv.reader(io.StringIO(text), dialect))
        head = [c.strip().lower() for c in rows[0]] if rows else []
        if "key" in head:
            ki = head.index("key")
            ti = next((head.index(c) for c in ("translation", lang.lower(), "text", "value") if c in head), len(head) - 1)
            rows = rows[1:]
        else:
            ki, ti = 0, 1
        if ti == ki:
            raise TranslationError("The file needs the columns key and translation")
        texts = {}
        for r in rows:
            if len(r) > max(ki, ti) and r[ki].strip():
                texts[r[ki].strip()] = r[ti]
        self.set_overrides(lang, texts, merge=True)
        return sum(1 for v in texts.values() if v.strip())
