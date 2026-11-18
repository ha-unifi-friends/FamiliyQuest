#!/usr/bin/env python3
"""Collect the English source texts of the UI and check the translation files.

    python3 tools/i18n_extract.py            # write tools/i18n_keys.json
    python3 tools/i18n_extract.py --check    # report missing/unknown keys and placeholder errors per language

Sources: T("…") in the web app, _t("…") in Python, and error messages passed to
HTTPException / LearnError / ShopError / PackError (they end up in toasts).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "family_quest" / "app" / "web"
PY = ROOT / "family_quest" / "app" / "familyquest"
I18N = WEB / "i18n"
LANGS = ["de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]

STR = r'"((?:[^"\\]|\\.)*)"'
JS_PATTERNS = [re.compile(r"\bT\(" + STR + r"\)")]
PY_PATTERNS = [re.compile(r"\b_t\(" + STR + r"\)"),
               re.compile(r"HTTPException\(\d+,\s*" + STR + r"\)"),
               re.compile(r"(?:LearnError|ShopError|PackError|ChoreError|BackupError|InternetError|ImportError_|CommunityError|LimitError|DeviceError|MemoryError_|DuelError|DoublesError|DeckError|ThemeError|PetError)\(" + STR + r"\)")]
EXTRA = ["Level", "Family Quest", "Family Quest – Parents", "Family Quest needs JavaScript.", "XP"]


def unescape(s: str) -> str:
    return json.loads('"' + s + '"')


def keys() -> list[str]:
    found: set[str] = set(EXTRA)
    for f in list(WEB.glob("*.js")) + list((WEB / "shared").glob("*.js")):
        text = f.read_text(encoding="utf-8")
        for p in JS_PATTERNS:
            found.update(unescape(m) for m in p.findall(text))
    for f in PY.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        for p in PY_PATTERNS:
            found.update(unescape(m) for m in p.findall(text))
    return sorted(k for k in found if k.strip() and re.search(r"[A-Za-z]", k))


def placeholders(s: str) -> set[str]:
    return set(re.findall(r"\{\d+\}", s))


def check(ks: list[str]) -> int:
    bad = 0
    want = set(ks)
    for lang in LANGS:
        f = I18N / f"{lang}.json"
        if not f.is_file():
            print(f"{lang}: file missing")
            bad += 1
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        missing = sorted(want - set(d))
        unknown = sorted(set(d) - want)
        ph = [k for k, v in d.items() if v and placeholders(k) != placeholders(v)]
        empty = [k for k, v in d.items() if not v]
        print(f"{lang}: {len(d)} entries, {len(missing)} missing, {len(unknown)} unknown, {len(ph)} placeholder errors, {len(empty)} empty")
        for k in missing[:15]:
            print("   missing:", k)
        for k in ph:
            print("   placeholder:", k, "→", d[k])
        bad += len(missing) + len(ph)
    return bad


if __name__ == "__main__":
    ks = keys()
    if "--check" in sys.argv:
        sys.exit(1 if check(ks) else 0)
    out = ROOT / "tools" / "i18n_keys.json"
    out.write_text(json.dumps(ks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(ks)} keys → {out.relative_to(ROOT)}")
