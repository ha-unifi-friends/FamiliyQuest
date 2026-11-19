"""UX review (responsive / touch / a11y), checked in the sources: no native dialogs, no «null» text, back button in the
parent area, focus handling of dialogs, the shared start row of the game cards, safe areas and contrast tokens."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
JS = sorted(WEB.glob("*.js")) + sorted((WEB / "shared").glob("*.js"))


def src(name):
    return (WEB / name).read_text(encoding="utf-8")


def test_no_native_confirm_prompt_alert():
    for f in JS:
        code = re.sub(r"//.*", "", f.read_text(encoding="utf-8"))
        assert not re.search(r"(?<![\w.$])(confirm|prompt|alert)\(", code), f.name


def test_dom_methods_leave_out_null():
    ui = src("shared/ui.js")
    assert '["append", "prepend", "replaceChildren", "before", "after", "replaceWith"]' in ui
    assert "xs.filter(keep)" in ui


def test_dialogs_and_drawers_keep_the_focus():
    ui = src("shared/ui.js")
    assert "function focusTrap(" in ui
    assert ui.count("release = focusTrap(") == 3                 # modal, game menu, app menu
    assert "function confirmDialog(" in ui and "function promptDialog(" in ui and "function tabbed(" in ui


def test_parent_area_follows_back_and_hides_the_closed_menu():
    p = src("parent.js")
    assert 'window.addEventListener("hashchange"' in p
    assert "nav.inert = narrow.matches" in p


def test_game_cards_use_one_start_row():
    for f in ["cards.js", "domino.js", "dorfmarkt.js", "heimwaerts.js", "jass.js", "jump.js", "kartenlauf.js", "klatsch.js",
              "langstrecke.js", "paarjagd.js", "poker.js", "snack.js", "stempeljagd.js", "sternlauf.js", "verkehr.js", "wuerfel.js"]:
        assert "gameStartRow(" in src(f), f
    assert 'T("With 3 bots")' not in src("jass.js")


def test_start_dialogs_check_the_battery_first():
    assert "(StartDialog|SoloDialog)$" in src("kid.js") and "rechargeBattery(() => start(...a))" in src("kid.js")


def test_css_tokens_safe_areas_and_targets():
    css = src("shared/base.css")
    assert "--accent-bg: #6363de" in css and "--good-text: #69db7c" in css and "--bad-text: #ff8787" in css
    assert "env(safe-area-inset-top)" in css and "max-height: 92dvh" in css
    assert "touch-action: manipulation" in css and "min-height: 44px" in css
    assert css.count("@media (orientation: landscape) and (max-height: 500px)") >= 5   # clap, snack, domino, dice, Heimwärts
