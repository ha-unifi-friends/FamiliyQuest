"""Build the planer UI for Family Quest.

1. src/build.py (unchanged from Family Planer) concatenates the sources into family-planer-cards.js.
2. Afterwards the navigation is switched from paths (/family-planer/listen) to hash routes (#/listen):
   inside Family Quest the page lives under the Home Assistant ingress path, so absolute paths do not work.
   window.FPLOC() (defined by web/planer/host.js) returns the same segments the original read from the path.

Run: python3 family_quest/app/web/planer/build_fq.py
"""
import pathlib
import runpy

here = pathlib.Path(__file__).parent
out = here / "family-planer-cards.js"
before = out.read_text(encoding="utf-8") if out.is_file() else None
runpy.run_path(str(here / "src" / "build.py"), run_name="__main__")
js = out.read_text(encoding="utf-8")

REPLACE = [
    # fpNavigate (week + plan UIs, German and English variant)
    ("history.pushState(null, '', `/${parts[0] || 'family-planer'}/${p}${location.search}`);",
     "location.hash = '#/' + p;"),
    ("location.pathname.split('/').filter(Boolean)", "window.FPLOC()"),
    # person photos: /family_planer_files/… is relative to the Family Quest page (ingress path)
    ("<img src=\"${esc(b.slice(4))}\"", "<img src=\"${esc(b.slice(4).replace(/^\\//, ''))}\""),
]
# language: Family Quest decides (German → German planer, anything else → English planer + Family Quest dictionaries)
REPLACE += [
    ("const fixed = store && store.snap && store.snap.settings && store.snap.settings.language;",
     "const fixed = window.FQ_PLANER_LANG || (store && store.snap && store.snap.settings && store.snap.settings.language);"),
    ("String((this.snap && this.snap.settings && this.snap.settings.language) || document.documentElement.lang || 'de')",
     "String(window.FQ_PLANER_LANG || (this.snap && this.snap.settings && this.snap.settings.language) || document.documentElement.lang || 'de')"),
    ("String((s.settings && s.settings.language !== 'auto' && s.settings.language) || document.documentElement.lang || 'de')",
     "String(window.FQ_PLANER_LANG || (s.settings && s.settings.language !== 'auto' && s.settings.language) || document.documentElement.lang || 'de')"),
]
# weekday and month names of the English planer in the Family Quest language (web/planer/fq-pre.js)
for kind, names in (("wdSun", "'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'"),
                    ("wdMon", "'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'"),
                    ("wd3Sun", "'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'"),
                    ("wd3Mon", "'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'"),
                    ("wd2Mon", "'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'"),
                    ("mon", "'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'")):
    REPLACE.append((f"[{names}]", f"FQN('{kind}', [{names}])"))
# hints that point to Home Assistant menus – in Family Quest everything is in the planer's own settings
REPLACE += [
    ("Einstellungen → Geräte & Dienste → Family Planer → Konfigurieren → Smarte Listen.", "Elternbereich → Aufgaben → Einstellungen → Listen."),
    ("Settings → Devices & services → Family Planer → Configure → Smart lists.", "Parent area → Chores → Settings → Lists."),
    ("Einschalten unter Einstellungen → Geräte & Dienste → Family Planer → Konfigurieren → Module.",
     "Einschalten unter Elternbereich → Aufgaben → Einstellungen → Allgemein."),
    ("Switch it on under Settings → Devices & services → Family Planer → Configure → Modules.",
     "Switch it on under Parent area → Chores → Settings → General."),
    ("Wird quadratisch zugeschnitten und nur in deinem Home Assistant gespeichert.",
     "Wird quadratisch zugeschnitten und nur in Family Quest gespeichert."),
    ("Cropped to a square and stored only in your Home Assistant.", "Cropped to a square and stored only in Family Quest."),
]
# Family Quest decides which planer views a page shows (web/planer.html): the app hides the chore plan and the
# settings (they live in the parent area → Chores), the parent area shows only those two; the app adds its own
# buttons (language, log out) to the right of the top bar
REPLACE += [
    ("const order = this._cfg.order || nav.order.filter((k) => !nav.hidden.includes(k));",
     "const order = window.FQ_PLANER_ONLY || (this._cfg.order || nav.order.filter((k) => !nav.hidden.includes(k))).filter((k) => !(window.FQ_PLANER_HIDE || []).includes(k));"),
    ("this._popLayer(this._popHtml, NAV_POPCSS);",
     "if (window.FQ_NAV_HOOK) window.FQ_NAV_HOOK(this.shadowRoot); this._popLayer(this._popHtml, NAV_POPCSS);"),
]
# parent area: the planer takes the look of the Family Quest parent area (its CSS variables, also dark mode),
# without the season scene in the top bar
REPLACE += [
    ("  const THEME_ALIAS = { loxone: 'dark'",
     "  THEMES.fq = { bg0: 'var(--bg)', bg1: 'var(--card)', bg2: 'var(--bg)', bg3: 'var(--hover)', bg4: 'var(--line)', line: 'var(--line)', "
     "text: 'var(--fg)', text2: 'var(--muted)', text3: 'var(--muted)', accent: 'var(--accent)', 'on-accent': 'var(--accent-fg)', "
     "radius: 'var(--radius)', font: 'var(--font)', grad: 'var(--accent)', page: 'var(--bg)', glow: 'var(--shadow)' };\n"
     "  const THEME_ALIAS = { loxone: 'dark'"),
    ("  const applyTheme = (el, name, style) => {",
     "  const applyTheme = (el, name, style) => { if (window.FQ_PLANER_THEME) { name = window.FQ_PLANER_THEME; style = 'standard'; }"),
    ("const SE = window.FPSEASON; const sPage = SE ? SE.page() : ''; const sBand = SE ? SE.band() : '';",
     "const SE = window.FQ_PLANER_THEME ? null : window.FPSEASON; const sPage = SE ? SE.page() : ''; const sBand = SE ? SE.band() : '';"),
    # search field of the chore plan and the settings had fixed dark colours – follow the design instead
    ("height:32px;padding:0 12px;border-radius:var(--fp-radius,16px);border:1px solid var(--fp-line,#3a3a3a);background:#1b1b1b;",
     "height:32px;padding:0 12px;border-radius:var(--fp-radius,16px);border:1px solid var(--fp-line,#3a3a3a);background:var(--fp-bg2,#1b1b1b);"),
    ("const sc = this._sceneHtml(s, lang);", "const sc = window.FQ_PLANER_THEME ? { key: '', html: '' } : this._sceneHtml(s, lang);"),
]
# parent area (planer?mode=parent): the top bar is hidden (planer.html) – its holiday window opens at the top right of
# the frame instead of below the bar; the chore plan drops its own title and «+» buttons (they are in the section head
# of the parent area, web/planer/host.js FQ_PLANER_DO), the settings drop their «Chores» tab (the plan is right above)
REPLACE += [
    ("const bar = this.shadowRoot.querySelector('.bar'); const r = bar ? bar.getBoundingClientRect() : { bottom: 60, right: window.innerWidth - 8 };",
     "const bar = window.FQ_PARENT_AREA ? null : this.shadowRoot.querySelector('.bar'); const r = bar ? bar.getBoundingClientRect() : { bottom: window.FQ_PARENT_AREA ? 2 : 60, right: window.innerWidth - 8 };"),
    ('<div class="card">\n        <div class="head"><div class="badge"><ha-icon icon="mdi:clipboard-text-clock-outline"></ha-icon></div>',
     '<div class="card${window.FQ_PARENT_AREA ? \' fqe\' : \'\'}">\n        <div class="head"><div class="badge"><ha-icon icon="mdi:clipboard-text-clock-outline"></ha-icon></div>'),
    ("const tabs = ORDER.map((id) => TABS.find((x) => x.id === id)).filter((x) => x && ",
     "const tabs = ORDER.map((id) => TABS.find((x) => x.id === id)).filter((x) => x && !(window.FQ_PARENT_AREA && x.id === 'chores') && "),
]
# trade marks: activity suggestion without a brand name
REPLACE += [("lego: ['🧱', 'Lego-Challenge', 'Lego challenge']", "lego: ['🧱', 'Bauklotz-Challenge', 'Building block challenge']")]
for old, new in REPLACE:
    n = js.count(old)
    if not n:
        if before is not None:
            out.write_text(before, encoding="utf-8")       # keep the last good build instead of an unpatched one
        raise SystemExit(f"pattern not found: {old}")
    js = js.replace(old, new)
out.write_text(js, encoding="utf-8")
print("family-planer-cards.js patched for Family Quest")
