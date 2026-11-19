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


def info_keys() -> tuple[set[str], dict[str, list[str]]]:
    """The keys of PARENT_INFO and the texts of each entry – one text or a list of paragraphs (some given by a function)."""
    src = _src("parent-info.js")
    body = src[src.index("const PARENT_INFO = {"):src.index("\n};\n")]
    starts = list(re.finditer(r'^  (?:\[T\(' + S + r'\)\]|' + S + r'):', body, re.M))
    keys, texts = set(), {}
    for i, m in enumerate(starts):
        k = json.loads('"' + (m.group(1) or m.group(2)) + '"')
        assert k not in keys, f"PARENT_INFO has «{k}» twice"
        keys.add(k)
        value = body[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(body)]
        texts[k] = [json.loads('"' + t + '"') for t in re.findall(r'\bT\(' + S + r'\)', value)]
        assert texts[k], k
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
    # every part of the page is a fold: no section, no part function outside fold(…) – the intro lives in the ⓘ of the title
    parts = re.findall(r'^    (\S.*)$', body, re.M)
    loose = [p for p in parts if not p.startswith("fold(")]
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
        missing = sorted(k for k, v in texts.items() for t in v if t not in d)
        assert not missing, (lang, missing[:5], len(missing))


# ---------------------------------------------------------------- explanations in the ⓘ, small fields side by side
def _calls(src: str, name: str) -> list[str]:
    """The argument text of every call name(…) (balanced parentheses, strings skipped)."""
    out, i = [], 0
    while (i := src.find(name + "(", i)) >= 0:
        j, depth, k = i + len(name) + 1, 1, i + len(name) + 1
        while depth:
            c = src[k]
            if c == '"':
                k += 1
                while src[k] != '"':
                    k += 2 if src[k] == "\\" else 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            k += 1
        out.append(src[j:k - 1])
        i = k
    return out


def test_merged_intros_are_paragraphs_of_the_info():
    _, texts = info_keys()
    # the explanations that stood under these titles are paragraphs of their ⓘ now
    for k, part in [("Game battery", "Every child has a game battery."), ("Parents", "Every parent has an own PIN"),
                    ("Deals", "Children trade coins"), ("Settings", "Every part is folded"), ("prof.time", "Far right ∞"),
                    ("net.guest", "e.g. your guest Wi-Fi"), ("Library", "Children and parents write books")]:
        assert len(texts[k]) >= 2 and any(t.startswith(part) for t in texts[k][1:]), (k, texts[k])
    page = _src("parent.js") + _src("deals.js")
    for t in ["Every child has a game battery.", "Every parent has an own PIN for the parent area",
              "Every part is folded – tap a row to open it.", "Children trade coins, chores, pets"]:
        assert t not in page, t


def test_field_explanations_are_info_buttons():
    pi = _src("parent-info.js")
    assert "function fieldInfo(" in pi and "function showInfo(" in pi
    for name in ["parent.js", "deals.js"]:
        src = _src(name)
        if name == "deals.js":
            src = src[src.index("async function dealsParentView"):]          # the children's deal pages keep their texts
        # no explaining text under a field any more – only the PIN rule (needed while typing) and live values
        hints = re.findall(r'h\("span\.hint", ([^)]*\))', src)
        static = [x for x in hints if x.startswith(("T(", "kid ? T(")) and "4 digits" not in x]
        assert not static, (name, static)
        # no intro paragraph right after the title of a box
        # (the kiosk link keeps its warning: whoever has the link sees the dashboard)
        intro = re.findall(r'\b(?:section|sectionAdd)\(([^\n]*?)\)\),\s*h\("p\.(?:small\.)?muted", T\(', src)
        assert [x for x in intro if "Link for the kiosk browser" not in x] == [], (name, intro)
    infos = _calls(_src("parent.js"), "fieldInfo") + _calls(_src("deals.js"), "fieldInfo")
    assert len(infos) >= 40, len(infos)
    langs = {lang: json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8")) for lang in LANGS}
    for args in infos:
        for t in re.findall(r'\bT\(' + S + r'\)', args):
            t = json.loads('"' + t + '"')
            for lang, d in langs.items():
                assert t in d, (lang, t)


def test_small_fields_side_by_side():
    css = _src("parent-ha.css")
    assert re.search(r"\.field-row \{[^}]*grid-template-columns: repeat\(auto-fit, minmax\(150px, 1fr\)\)", css)
    assert ".field-info" in css and ".gp-rent" in css
    src = _src("parent.js")
    price = src[src.index("function gamePriceBox("):src.index("// ---------------------------------------------------------------- pairs game")]
    assert 'h("div.field-row"' in price and 'h("div.gp-rent", rent, periods)' in price and price.count("fieldInfo(") == 4
    battery = src[src.index("function batteryForm("):src.index("/** Parent area › Games: the family default")]
    assert 'h("div.field-row"' in battery and "...more" in battery
    learning = src[src.index('fold("learning"'):src.index('fold("levels"')]
    assert learning.count("fieldInfo(") == 5 and 'h("div.field-row"' in learning
    assert 'h("div.field-row"' in _src("deals.js")
