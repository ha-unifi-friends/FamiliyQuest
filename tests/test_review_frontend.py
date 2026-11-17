"""Frontend fixes of the code review, checked in the sources: shop price 0, the poker banner, start dialogs without bots."""
import json
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
LANGS = ["de-CH", "de-DE", "es-ES", "fr-FR", "it-IT", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]


def src(name):
    return (WEB / name).read_text(encoding="utf-8")


def test_shop_price_zero_is_free_not_missing():
    kid = src("kid.js")
    assert "i.rule.xp && !i.rule.off" not in kid and "i.rule.xp != null && !i.rule.off" in kid      # XP items with price 0 shown
    assert "if (i.rule.cost && confirm(" not in kid and "else if (i.rule.xp && confirm(" not in kid   # pickItem: 0 is a price
    assert "r.cost != null ? (r.cost > 0" in kid and "r.xp != null ? (r.xp > 0" in kid                  # ruleText: «Free»
    assert 'i.rule.cost > 0 && !confirm(' in kid and 'i.rule.xp > 0 && !confirm(' in kid               # no question for 0


def test_poker_banner_names_who_deals():
    assert 'starterBanner(st.starter, "poker", true)' in src("poker.js")
    assert 'T("{0} deals!")' in src("shared/ui.js") and 'T("The dice decided: {0} deals!")' in src("shared/ui.js")


def test_start_dialogs_without_bots_do_not_promise_bots():
    kl, ja = src("kartenlauf.js"), src("jass.js")
    assert 'botsOn("kartenlauf") ? T("Free seats are taken by bots when the game starts.")' in kl
    assert 'botsOn("jass") ? T("4 players in 2 teams – your partner sits opposite. Free seats are taken by bots.")' in ja
    assert 'botsOn("jass") ? T("4 seats: the family joins on their own devices, guests via QR code – bots take the free seats.")' in ja


def test_new_strings_are_translated():
    keys = ["Free", "{0} deals!", "The dice decided: {0} deals!", "Without bots only the people at the table play (2 to 4).",
            "4 players in 2 teams – your partner sits opposite. Without bots 4 people are needed.",
            "4 seats: the family joins on their own devices, guests via QR code – without bots 4 people are needed."]
    for lang in LANGS:
        d = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert all(d.get(k) for k in keys), lang
