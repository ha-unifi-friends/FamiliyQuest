"""Etappe G: the planer UI in every Family Quest language.

German and Swiss German use the planer's own German texts; every other language uses its English texts,
translated with i18n/planer/<lang>.json (keys collected by tools/planer_i18n_keys.js).
"""
import json
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
PLANER_I18N = WEB / "i18n" / "planer"
LANGS = ["fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]
PH = re.compile(r"\{\d+\}")


def keys() -> list[str]:
    return json.loads((PLANER_I18N / "keys.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("lang", LANGS)
def test_planer_dictionary_complete(lang):
    d = json.loads((PLANER_I18N / f"{lang}.json").read_text(encoding="utf-8"))
    k = keys()
    assert set(d) == set(k), f"{lang}: missing {sorted(set(k) - set(d))[:5]} unknown {sorted(set(d) - set(k))[:5]}"
    for key, val in d.items():
        assert val.strip(), f"{lang}: empty translation for {key!r}"
        assert set(PH.findall(key)) == set(PH.findall(val)), f"{lang}: placeholders differ in {key!r} → {val!r}"


def test_planer_page_loads_the_translation():
    html = (WEB / "planer.html").read_text(encoding="utf-8")
    assert 'window.I18N_EXTRA = ["planer"]' in (WEB / "planer" / "page-pre.js").read_text(encoding="utf-8")
    assert html.index("planer/page-pre.js") < html.index("shared/i18n.js")
    assert html.index("planer/fq-pre.js") < html.index("planer/family-planer-cards.js")
    bundle = (WEB / "planer" / "family-planer-cards.js").read_text(encoding="utf-8")
    assert "window.FQ_PLANER_LANG" in bundle and "FQN('mon'" in bundle
    assert "Devices & services" not in bundle and "Geräte & Dienste" not in bundle
