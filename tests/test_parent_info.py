"""ⓘ in the parent area (web/parent-info.js): every section, sub-section, game and settings part has its explanation.

Static checks of the sources: the titles of the boxes (section / sectionAdd / folded headings), the page titles, every
game of GAME_LIST, the folded settings parts (setFold) and every `data-ik` must be a key of PARENT_INFO – and every
key must have its translation in all 9 languages."""
from __future__ import annotations

import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
LANGS = ["de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]
S = r'"((?:[^"\\]|\\.)*)"'
# an optional emoji prefix, then the English title: T("…"), I18N.tr(T("…")) or a plain name («Home Assistant»)
TITLE = r'(?:"[^"\w]*"\s*(?:\+|,)\s*)?(?:I18N\.tr\()?(?:T\()?' + S


def _src(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def info_keys() -> tuple[set[str], dict[str, str]]:
    src = _src("parent-info.js")
    body = src[src.index("const PARENT_INFO = {"):src.index("\n};\n")]
    keys, texts = set(), {}
    for m in re.finditer(r'^\s*(?:\[T\(' + S + r'\)\]|' + S + r'): T\(' + S + r'\)', body, re.M):
        k = json.loads('"' + (m.group(1) or m.group(2)) + '"')
        assert k not in keys, f"PARENT_INFO has «{k}» twice"
        keys.add(k)
        texts[k] = json.loads('"' + m.group(3) + '"')
    return keys, texts


def headings(src: str) -> set[str]:
    """The titles of boxes, folds and pages in a source file."""
    out = set()
    pats = [r'\bsection\(\s*' + TITLE, r'\bsectionAdd\(\s*' + TITLE, r'\bpageHead\(\s*' + TITLE,
            r'h\("summary[\w.-]*",\s*h\("h2",\s*(?:\{[^{}]*\},\s*)?' + TITLE,
            r'h\("div\.sec-head",\s*h\("h2",\s*' + TITLE,
            r'h\("section\.card[\w.-]*",\s*h\("h2",\s*' + TITLE,
            r'replaceChildren\(\s*(?:\.\.\.\[)?h\("h2",\s*' + TITLE,
            r'main\.append\(h\("h1",\s*' + TITLE,
            r'h\("h2\.cg-title",\s*' + TITLE,
            r'\bsetFold\(\s*"\w+",\s*' + TITLE, r'\bfold\(\s*"\w+",\s*' + TITLE]
    for p in pats:
        for m in re.finditer(p, src):
            out.add(json.loads('"' + m.group(1) + '"'))
    return out


# headings that are no box of their own (error pages, the login, a person's name …)
NOT_SECTIONS = {"This page could not be loaded", "Parent area", "Family Quest"}


def test_every_section_head_has_an_info_entry():
    keys, _ = info_keys()
    found = set()
    for name in ["parent.js", "deals.js"]:
        found |= headings(_src(name))
    found -= NOT_SECTIONS
    # the check must see the real page: these are on it for sure
    for must in ["Overview", "Games", "Settings", "Custom games", "Access from the network", "Backup & restore",
                 "Log in with Home Assistant", "Family Quest HA integration", "Own texts and languages", "Deal settings",
                 "Weather settings", "Library"] :
        assert must in found or must in keys, must
    assert len(found) > 60, sorted(found)
    missing = sorted(t for t in found if t not in keys)
    assert not missing, f"sections without ⓘ (add them to PARENT_INFO in parent-info.js): {missing}"


def test_every_game_and_data_ik_has_an_info_entry():
    keys, _ = info_keys()
    src = _src("parent.js")
    gl = src[src.index("const GAME_LIST = ["):src.index("// 🛠️ Custom games")]
    games = {json.loads('"' + m.group(1) + '"') for m in re.finditer(r'\["\w+", "[^"]+", (?:T\()?' + S + r'\)?\]', gl)}
    assert {"Family quiz", "Pair Hunt", "Adventure games", "Card Race", "Bingo"} <= games, games
    assert not sorted(games - keys), sorted(games - keys)
    iks = set()
    for f in WEB.glob("*.js"):
        iks |= {m.group(1) for m in re.finditer(r'"data-ik":\s*"([^"]+)"(?!\s*\+)', f.read_text(encoding="utf-8"))}
    iks |= {"cg." + k for k in ["quiz", "paarjagd", "adventuregame"]}          # "data-ik": "cg." + k
    assert len(iks) > 15
    assert not sorted(iks - keys), sorted(iks - keys)


def test_every_settings_part_is_folded():
    src = _src("parent.js")
    view = src[src.index("async function settingsView(main)"):]
    view = view[:view.index("\n}\n")]
    body = view[view.index('main.append(h("h1", T("Settings"))'):view.index("// the status in the rows")]
    # every part of the page is a fold: no section, no part function outside fold(…)
    parts = re.findall(r'^    (\S.*)$', body, re.M)
    loose = [p for p in parts if not p.startswith(("fold(", 'h("p.small.muted.set-intro"'))]
    assert not loose, loose
    ids = re.findall(r'fold\("(\w+)"', body)
    assert len(ids) == len(set(ids)) >= 17, ids
    status = src[src.index("async function settingsStatus(main)"):src.index("async function settingsView(main)")]
    no_status = [i for i in ids if not re.search(r"\bst\." + i + r"\b", status)]
    assert not no_status, f"settings parts without a status in their row: {no_status}"


def test_info_texts_are_translated():
    _, texts = info_keys()
    for lang in LANGS:
        d = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        missing = sorted(k for k, v in texts.items() if v not in d)
        assert not missing, (lang, missing[:5], len(missing))
