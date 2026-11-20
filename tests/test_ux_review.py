"""UX review (responsive / touch / a11y), checked in the sources: no native dialogs, no «null» text, back button in the
parent area, focus handling of dialogs, the shared start row of the game cards, safe areas and contrast tokens."""
import re
from pathlib import Path

from websrc import PARENT_JS, parent_js, web_src

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
JS = sorted(WEB.glob("*.js")) + sorted((WEB / "shared").glob("*.js"))


def src(name):
    return web_src(name)                      # "parent.js": the whole parent area (parent.js and its parts)


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


# ---------------------------------------------------------------- UX review 2 (parent area)
def _fn(text, head):
    body = text[text.index(head):]
    return body[:body.index("\n}\n")]


def test_parent_area_parts_load_before_boot():
    """parent.js is split into parts (parent-overview.js …): eltern.html loads all of them, in order, and boot() runs
    only once every script of the page is loaded – the views map of render() names functions of every part."""
    html = src("eltern.html")
    loaded = re.findall(r'<script src="(parent[^"?]*\.js)\?v=__VERSION__"></script>', html)
    assert loaded == [*PARENT_JS, "parent-info.js", "parent-analytics.js", "parent-privacy.js"]
    assert sorted(f.name for f in WEB.glob("parent*.js")) == sorted(loaded)
    core = (WEB / "parent.js").read_text(encoding="utf-8")
    assert core.rstrip().endswith('if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => boot()); else boot();')
    assert not re.search(r"^boot\(\);", parent_js(), re.M)
    for f in PARENT_JS:
        assert '\n"use strict";\n' in "\n" + "\n".join((WEB / f).read_text(encoding="utf-8").split("\n")[:4]) + "\n", f
    names = re.findall(r"^(?:async )?function (\w+)|^(?:const|let) (\w+)", parent_js(), re.M)
    names = [a or b for a, b in names]
    assert len(names) > 120 and len(names) == len(set(names)), sorted({n for n in names if names.count(n) > 1})


def test_parent_menu_and_period_picker_trap_the_focus():
    ui, p, an = src("shared/ui.js"), src("parent.js"), src("parent-analytics.js")
    assert '".modal-back, .drawer-back, .side-back.open, .an-pick-back"' in ui            # the ☰ menu and the picker count as layers
    r = _fn(p, "function render()")
    assert "navRelease = focusTrap(back, nav, closeNav)" in r and "button.icon-btn.side-close" in r
    assert 'nav.addEventListener("keydown"' not in r                                      # Esc: the trap, wherever the focus is
    css = src("parent.css")
    assert ".side-close { display: none !important; }" in css and ".side-close { display: inline-flex !important; }" in css
    pick = _fn(an, "function anPicker(")
    assert "release = focusTrap(back, sheet, close)" in pick and '"aria-pressed": String(on)' in pick and "quickOn(k)" in pick
    assert ".an-pick-quick button.on" in src("parent-analytics.css")


def test_segments_info_buttons_and_page_titles():
    css, ha = src("parent.css"), src("parent-ha.css")
    seg = css[css.index(".seg {"):css.index(".seg button.on")]
    assert "border-radius: 14px" in seg and "white-space: nowrap" in seg and "@media (pointer: coarse) { .seg button { min-height: 44px; } }" in seg
    info = src("parent-info.js")
    assert "function glueInfo(" in info and "I18N.ready.then(() => { try { glueInfo(); labelFields(); }" in info
    assert ".ib-glue { white-space: nowrap; }" in css and "> .ib-glue > .info-btn" in ha
    assert "html.ha h1 { font-size: 1.6rem; font-weight: 600; }" in ha
    # page titles without emoji (the menu shows the icon); the History page names itself once
    for f, t in [("parent.js", 'pageHead(T("History"))'), ("parent.js", 'pageHead(T("Calendar")'), ("parent-privacy.js", 'pageHead(T("Privacy"))'),
                 ("parent-analytics.js", 'h("h1", T("Analytics"))')]:
        assert t in src(f), t
    assert 'h("h2", T("Dashboards"))' not in src("parent-analytics.js")


def test_chores_page_shows_the_plan_in_use_first():
    p = src("parent.js")
    v = _fn(p, "async function choresView(main)")
    assert "const useOwn = own.length > 0;" in v
    assert 'setGroup("chores.own", "🧹", T("Family Quest chores"))' in v and 'setGroup("chores.planer", "📅", T("Planner"), moveBtn)' in v
    assert 'foldBoxes(ownList, "chores")' in v and 'setFold("chores.planer"' in v and 'T("Old chore list")' in v
    assert '"fq-planer-chores"' in v and 'new CustomEvent("fq-planer-chores"' in _fn(p, "function planerFrame(")
    keys = src("parent-info.js")
    assert '"chores.own":' in keys and '"chores.planer":' in keys and '[T("Old chore list")]' in keys
    # the planer's week overview on phones: the names readable (no «M…» twice)
    for f in ["planer/build_fq.py", "planer/family-planer-cards.js"]:
        assert "minmax(48px,max-content) repeat(7,minmax(20px,1fr)) 30px" in src(f), f
    # German and Swiss German use the planer's own German texts: no planer dictionary is fetched (no 404)
    assert 'const extra = /^de/.test(base) ? [] : (window.I18N_EXTRA || []);' in src("shared/i18n.js")


def test_points_page_shop_backup_and_contrast():
    p = src("parent.js")
    assert '["rewards", "🪙", T("Points & rules")]' in p
    rv = _fn(p, "async function rewardsView(main, opts = {})")
    assert 'h("h1", T("Points & rules"))' in rv and 'foldBoxes(main, "rew")' in rv and '"aria-label": T("Daily limit")' in rv
    shop = _fn(p, "async function shopSettingsView(main)")
    assert 'stackTable(h("table.tbl.stack.shop-tbl"' in shop and '"aria-label": T("Paid with")' in shop
    bk = _fn(p, "function backupSection()")
    assert "fileButton(file," in bk and bk.index("Full: everything.") < bk.index('downloadBackup("full")')
    assert "function fileButton(" in p and ".file-hidden {" in src("parent.css")
    ov = _fn(p, "async function overviewView(main)")
    assert "fmt(k.balances[a.key] || 0, 1)" in ov
    kw = _fn(p, "function kidWeather(")
    assert 'T("Today\'s weather:")' in kw and 'T("No weather recorded yet – pick one above.")' in kw
    games = _fn(p, "async function gamesView(main)")
    assert 'setFold("games.general"' in games and 'setFold("games.battery"' in _fn(p, "function batterySettingsCard()")
    assert ".offer.cant { opacity" not in src("kid.css") and ".inst-n { font-size: .78rem; opacity" not in src("shared/base.css")
    assert ".switch-wrap input:checked + .switch-ui { background: var(--accent-bg); }" in src("parent.css")
