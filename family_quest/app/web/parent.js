// Family Quest – parent area. Every action needs the parent PIN (token in sessionStorage, 30 min).
"use strict";

const P = { info: null, meta: null, tab: "overview", profiles: [], accounts: [] };
const app = $("#app");
const TABS = [["overview", "📊", T("Overview")], ["community", "👨‍👩‍👧", T("Family")], ["chores", "🧹", T("Chores")], ["packs", "📦", T("Learning packs")],
  ["rewards", "🪙", T("Points & rules")], ["games", "🎲", T("Games")], ["shop", "🛍️", T("Shop")], ["calendar", "📅", T("Calendar")], ["analytics", "📈", T("Analytics")], ["history", "📜", T("History")], ["privacy", "🛡️", T("Privacy")], ["settings", "⚙️", T("Settings")]];
const KIND_NAMES = { voucher: T("Voucher (parents fulfil it)"), internet_minutes: T("Internet minutes"), planer_points: T("Family Planer points"),
  ha_script: T("Home Assistant script"), avatar_item: T("Avatar item") };
const EXERCISES = { auswahl: T("Multiple choice"), eintippen: T("Typing"), paare: T("Pairs"), lueckentext: T("Gap text"),
  karteikarte: T("Flash cards"), zuordnen: T("Drag & drop"), hoeren: T("Listening") };
const STATUS = { active: T("active"), draft: T("draft – to check"), disabled: T("switched off"), available: T("not added") };

async function boot() {
  try { P.info = await api("info"); if (P.info.via_ha) P.appLink = await api("app-link").catch(() => null); } catch (e) { return app.replaceChildren(h("div.login", h("div.card", h("h2", T("Family Quest cannot be reached")), h("p", e.message)))); }
  if (P.info.setup_needed) return setupView();
  if (P.info.parent_ha_only && !P.info.via_ha) {
    let ha = null;
    try { const p = await api("ha-panel"); if (p.slug) ha = `${p.ssl ? "https" : "http"}://${location.hostname}:${p.port}${p.path || "/app/" + p.slug}`; } catch (e) { /* no link then */ }
    return app.replaceChildren(h("div.login", h("div.card.login-card.center",
      h("h2", "🏠 ", T("Parent area")), h("p", T("The parent area opens only in Home Assistant – in the sidebar under Family Quest.")),
      h("div.row.center", ha ? h("a.btn", { href: ha }, "🏠 ", T("Open in Home Assistant")) : null,
        h("a.btn.ghost", { href: "app" }, "← ", T("To the app"))))));
  }
  if (!Auth.parent) return loginView();
  try { P.meta = await api("parent/meta"); } catch (e) { Auth.parent = ""; return loginView(); }
  if (P.info.via_ha) { try { P.haSlug = (await api("ha-panel")).slug || ""; } catch (e) { P.haSlug = ""; } }   // version links to the add-on page
  if (P.info.via_ha && P.haSlug) {   // remember where this HA version shows the panel (/app/<slug> or /hassio/ingress/<slug>)
    let top = ""; try { top = window.top.location.pathname; } catch (e) { /* not readable */ }
    const m = top.match(new RegExp("^/(app|hassio/ingress)/" + P.haSlug.replace(/[^\w-]/g, "") + "(?=/|$)"));
    if (m) api("parent/ha-panel-path", { method: "POST", body: { path: m[0] } }).catch(() => {});
  }
  setInterval(refreshToken, 10 * 60 * 1000);
  P.tab = tabFromHash();
  render();
  // browser / Android back and forward change only the hash: show that page (open dialogs close)
  if (!P.hashWatch) {
    P.hashWatch = true;
    window.addEventListener("hashchange", () => {
      if (!Auth.parent) return;
      const t = tabFromHash();
      if (t === P.tab && !P.foldTo) return;
      document.querySelectorAll(".modal-back").forEach(b => b.dispatchEvent(new Event("cancel")));
      P.tab = t; render(); scrollTo(0, 0);
    });
  }
}

// old addresses: #goals is a part of «Family» now (its fold opens), #weather the overview (the weather of each child)
// #dashboard: the kiosk dashboard is a part of «Settings › App» now (its fold opens)
const TAB_ALIAS = { goals: ["community", "fam.goals"], deals: ["community", "fam.deals-mine"], weather: ["overview"], ledger: ["history"], dashboard: ["settings", "dashboard"] };
function tabFromHash() {
  let t = location.hash.replace("#", "") || "overview";
  const a = TAB_ALIAS[t];
  if (a) {
    if (a[1]) { SET_OPEN.add(a[1]); P.foldTo = a[1]; }
    t = a[0];
    try { history.replaceState(null, "", "#" + t); } catch {}
  }
  if (!TABS.some(x => x[0] === t) && t !== "import") t = "overview";
  return t;
}

async function refreshToken() {
  try { Auth.parent = (await api("parent/refresh", { method: "POST" })).parent_token; } catch {}
}

// opened through Home Assistant with a linked user: a fresh parent token without PIN (null otherwise)
async function haLogin() {
  try { const r = await api("parent/ha-login", { method: "POST" }); if (r.parent_token) { Auth.parent = r.parent_token; return r; } return r; }
  catch { return null; }
}

// inside Home Assistant (sidebar, same origin): light or dark like the active HA theme – the colours stay ours
(function haTheme() {
  try {
    if (window.parent === window) return;
    try { if (localStorage.getItem("fq.theme")) return; } catch {}       // the own choice (☀️ / 🌙) comes first
    const bg = getComputedStyle(window.parent.document.documentElement).getPropertyValue("--primary-background-color").trim();
    const m = bg.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i);
    if (m) document.documentElement.dataset.theme = (parseInt(m[1], 16) + parseInt(m[2], 16) + parseInt(m[3], 16)) / 3 < 100 ? "dark" : "light";
  } catch {}
})();

// the parent session ran out (30 minutes): Home Assistant logs in again – else the PIN login (shared/ui.js api)
window.FQ_ON_401 = async () => {
  const r = await haLogin();
  if (r && r.parent_token) return true;
  Auth.parent = ""; loginView();
  return false;
};

async function call(path, opts) {
  try {
    const r = await api(path, opts);
    // a change (not a GET): the page may show a status of it – the folded settings update their rows (settingsView)
    if (opts && opts.method && opts.method !== "GET" && P.onChange) P.onChange(path);
    return r;
  }
  catch (e) {
    if (e.status === 401 && Auth.parent) { Auth.parent = ""; loginView(); }       // could not be renewed (api did try)
    toast(e.message, "bad");
    throw e;
  }
}

// ---------------------------------------------------------------- setup and login
function setupView() {
  const name = h("input", { type: "text", placeholder: T("Your name"), "aria-label": T("Your name"), value: P.info.setup_ha_user || "" });
  const viaHA = !!P.info.setup_ha_user;            // through Home Assistant with a known user: the PIN is optional
  let step = 1, first = "";
  const create = async pin => {
    const r = await api("setup", { method: "POST", body: { name: name.value.trim(), pin: pin || "" } });
    Auth.parent = r.parent_token;
    P.info.setup_needed = false;
    toast(T("Done! Now add the children."), "good");
    location.hash = "#profiles";
    boot();
  };
  const box = h("div.card.login-card",
    h("img", { src: "img/icon.svg", alt: "", width: 72, height: 72 }),
    h("h1", T("Welcome to Family Quest")),
    h("p", viaHA ? T("First create the parent profile.") : T("First create the parent profile. It is always protected by a PIN.")),
    h("label.field", T("Your name"), name),
    viaHA ? h("p.small.muted", "🏠 ", I18N.tr(T("Your parent profile is linked with the Home Assistant user «{0}»: you need no PIN. On tablets and phones you sign in with «Sign in with Home Assistant» – or you set a PIN later in your profile.")).replace("{0}", P.info.setup_ha_user)) : null,
    viaHA ? h("button.btn.big", { onclick: async () => {
      if (!name.value.trim()) return name.focus();
      try { await create(""); } catch (e) { toast(e.message, "bad"); }
    } }, "✓ ", T("Create")) : null,
    h("button.btn" + (viaHA ? ".ghost.small" : ".big"), { onclick: () => { if (!name.value.trim()) return name.focus(); pinStep(); } },
      viaHA ? "🔑 " + I18N.tr(T("Also choose a PIN")) : T("Next")),
    langPicker());
  app.replaceChildren(h("div.login", box));
  function pinStep() {
    box.replaceChildren(pinPad({ title: step === 1 ? T("Choose a PIN (4–8 digits)") : T("Repeat the PIN"), length: 4, maxLength: 8, cancel: false,
      onSubmit: async pin => {
        if (step === 1) { first = pin; step = 2; return pinStep(); }
        if (pin !== first) { step = 1; throw new Error(I18N.tr(T("The PINs do not match"))); }
        await create(pin);
      } }));
  }
}

async function loginView(auto = true) {
  const keep = Auth.parent;
  const ha = await haLogin();
  if (ha && ha.parent_token && auto) return boot();
  if (ha && ha.parent_token) Auth.parent = keep;     // after «log out»: offer it as a button instead
  const linked = ha && ha.linked;
  const haUser = ha && ha.ha_user;
  const done = async r => {
    Auth.parent = r.parent_token;
    // first PIN login through Home Assistant: offer to skip the PIN next time
    if (haUser && !linked && !ha.kid && (await confirmDialog(I18N.tr(T("Log in with your Home Assistant user «{0}» from now on – without PIN?")).replace("{0}", haUser.name || haUser.user)))) {
      try { await api("parent/ha-link", { method: "POST", body: { on: true } }); toast(T("Linked with Home Assistant"), "good"); } catch (e) { toast(e.message, "bad"); }
    }
    boot();
  };
  const card = h("div.card.login-card");
  const digits = () => card.replaceChildren(...[
    h("div.row", h("a.link", appLinkAttrs({ dialog: true }), "⭐ Family Quest App ↗"), h("span.grow"), themeBtn(), langPicker()),
    linked ? h("div.center", h("button.btn", { onclick: () => loginView(true) }, "🏠 ", I18N.tr(T("Log in as {0}")).replace("{0}", haUser.name || haUser.user)))
      : haUser ? h("p.small.muted.center", "🏠 ", I18N.tr(T("Home Assistant user: {0}")).replace("{0}", haUser.name || haUser.user)) : null,
    pinPad({ title: T("Parent PIN"), length: 4, maxLength: 8, cancel: false, onSubmit: async pin => done(await api("parent/login", { method: "POST", body: { pin } })) }),
    symbolParents].filter(Boolean));
  // parents with a picture PIN: choose the parent, then the symbols (they come in a new order every time)
  const symbolParents = h("div.row.center.sym-parents");
  api("profiles").then(list => {
    const sym = list.filter(p => p.role === "parent" && p.pin_kind === "symbols" && p.symbol_set);
    symbolParents.replaceChildren(...(sym.length ? [h("span.small.muted", T("With symbols:"))] : []),
      ...sym.map(p => h("button.btn.small.ghost", { onclick: () => card.replaceChildren(
        symbolPad({ title: C(p.name), symbols: p.symbol_set, onSubmit: async ids =>
          done(await api("parent/login", { method: "POST", body: { pin: "sym:" + ids.join(","), profile_id: p.id } })) }),
        h("button.link", { onclick: digits }, "🔢 ", T("Use the digit PIN"))) }, avatarSvg(p.avatar, 26), " ", C(p.name))));
  }).catch(() => {});
  card.addEventListener("cancel", digits);
  digits();
  app.replaceChildren(h("div.login", card));
}

// ---------------------------------------------------------------- release notes (CHANGELOG.md: "## version" and "- point")
async function releaseNotes() {
  let text = "";
  try { text = (await api("parent/changelog")).text; } catch (e) { return toast(e.message, "bad"); }
  // the release notes exist in English only: shown as they are (single words translated in between would mix two languages)
  const out = h("div.release-notes", { translate: "no", lang: "en" });
  let ul = null, li = null;
  // **bold** as <strong>, everything else as plain text
  const md = t => t.split(/\*\*(.+?)\*\*/).map((x, i) => i % 2 ? h("strong", x) : x);
  for (const line of text.split("\n").slice(0, 600)) {
    if (line.startsWith("## ")) { ul = li = null; out.append(h("h3", line.slice(3))); }
    else if (/^[-*] /.test(line)) { if (!ul) out.append(ul = h("ul")); ul.append(li = h("li", ...md(line.slice(2)))); }
    else if (li && /^\s+\S/.test(line)) li.append(" ", ...md(line.trim()));         // wrapped bullet line
    else if (!line.trim()) li = null;
  }
  const upd = h("p.small.muted");
  api("parent/update-info").then(u => {
    if (u.version) upd.replaceChildren(u.update ? h("b", "🆕 ", I18N.tr(T("Update available: {0}")).replace("{0}", u.latest)) : "✓ " + I18N.tr(T("Up to date ({0})")).replace("{0}", u.version));
  }).catch(() => {});
  const m = modal(h("div", h("h2", "📝 ", T("Release notes")), upd,
    I18N.base !== "en" && out.childNodes.length ? h("p.small.muted", T("The release notes are written in English.")) : null, out.childNodes.length ? out : h("p.muted", T("No release notes found.")),
    h("div.row.wrap",
      // the add-ons page of Home Assistant: the store is checked there and the update is one click
      P.info.via_ha ? h("a.btn.ghost", { href: "/config/apps/installed", target: "_blank", rel: "noopener" }, "🔄 ", T("Check for updates")) : null,
      h("button.btn", { onclick: () => m.close() }, T("Close")))), { wide: true });
}

// link to the kid app: in Home Assistant through the direct access (http://<host>:<port>/app) – an ingress address opened
// in a new tab outside of Home Assistant (Safari from the companion app) only shows «401: Unauthorized»
// «⭐ Family Quest App»: a dialog with the QR code of the kids' app, print and open in a new tab – so it is clear where
// the app is and how the children sign in
function appLinkDialog(href) {
  const link = new URL(href, location.href).href, direct = !!(P.appLink && P.appLink.port) || !(P.info && P.info.via_ha);
  const close = () => m.close();
  // without direct access the address is the Home Assistant ingress one – no use for the children's devices
  // (long QR code, 401 without a Home Assistant login): only the hint how to switch it on
  const m = direct ? modal(h("div.form.app-link-dlg", h("h2", "⭐ ", T("Family Quest App")),
    h("p", T("The children use their own app: scan the code with the phone or tablet, pick your profile and enter your PIN.")),
    h("div.center.app-link-qr", qrSvg(link)),
    h("p.small.center", { translate: "no" }, h("a", { href: link, target: "_blank", rel: "noopener" }, link)),
    h("p.small.muted", "📶 ", T("Works in the home Wi-Fi.")),
    h("div.row.wrap", h("a.btn", { href: link, target: "_blank", rel: "noopener", onclick: close }, "↗ ", T("Open in a new tab")),
      h("button.btn.ghost", { onclick: () => { m.close(); printPoster(link); } }, "🖨️ ", T("Print poster")),
      h("button.btn.ghost", { onclick: () => { m.close(); installAppDialog({ forOther: true, link }); } }, "📲 ", T("Install app")),
      h("button.btn.ghost", { onclick: close }, T("Close")))))
    : modal(h("div.form.app-link-dlg", h("h2", "⭐ ", T("Family Quest App")),
      h("p.app-link-off", "ℹ️ ", T("Direct access is still off: in Home Assistant open the app → Configuration, switch on direct_access and restart the app.")),
      h("div.row.wrap", h("button.btn", { onclick: close }, T("Close")))));
}

function appLinkAttrs({ dialog = false } = {}) {
  if (dialog) {
    const a = appLinkAttrs();
    return { ...a, onclick: e => { if (e.ctrlKey || e.metaKey || e.shiftKey || e.button === 1) return; e.preventDefault(); appLinkDialog(a.href); } };
  }
  const base = { rel: "noopener", translate: "no" };
  if (!P.info || !P.info.via_ha) return { ...base, href: "app", target: "_blank" };
  const l = P.appLink;
  if (!l || !l.port) return { ...base, href: "app" };            // no direct access: open it right here inside Home Assistant
  const host = location.hostname, local = /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.)|\.local$|^[^.]+$/.test(host);
  const ip = (local ? host : (l.ips || [])[0] || host).replace(/^\[|\]$/g, "");
  return { ...base, href: `http://${ip.includes(":") ? `[${ip}]` : ip}:${l.port}/app`, target: "_blank" };
}

// ---------------------------------------------------------------- layout
// load the page anew – well visible top right (phone: in the bar with ☰)
const refreshBtn = () => h("button.icon-btn.refresh-btn", { title: T("Refresh"), "aria-label": T("Refresh"), onclick: async e => { e.currentTarget.disabled = true; await planerRefresh(); location.reload(); } }, "⟳");

function render() {
  P.onChange = null;
  const nav = h("nav.side", h("div.brand-box",   // the header on its own background: name and ⟳, below it the link to the kids' app (QR code dialog)
      h("div.brand", h("img", { src: "img/icon.svg", alt: "", width: 34, height: 34 }), h("strong.grow", "Family Quest"), refreshBtn(),
        // phones: the ☰ menu closes with ✕ (like the kids' menu), Esc or a tap beside it
        h("button.icon-btn.side-close", { type: "button", "aria-label": T("Close"), title: T("Close"), onclick: () => closeNav() }, "✕")),
      h("a.brand-app", (a => ({ ...a, onclick: e => { closeNav(); a.onclick(e); } }))(appLinkAttrs({ dialog: true })),   // phone: the ☰ menu closes first, the QR dialog then lies on top
        h("span", "⭐"), h("span.grow", "Family Quest App"), h("span.brand-go", { "aria-hidden": "true" }, "↗"))),
    ...TABS.map(([k, ic, n]) => h("button" + (P.tab === k || (k === "packs" && P.tab === "import") ? ".on" : ""), { "data-tab": k, onclick: () => { P.tab = k; location.hash = k; render(); } }, h("span", ic), h("span", n))),
    h("div.side-foot",
      // the personal part, on its own background: light / dark, language, log out – and the version (release notes)
      footTheme(), footLang(),
      h("button.foot-item", { onclick: () => { Auth.parent = ""; loginView(false); } }, h("span.foot-ic", "🔒"), h("span", T("Log out"))),
      // the version opens the release notes
      h("div.small.muted.foot-ver", h("button.link.muted.ver-link", { type: "button", title: T("Release notes"), onclick: releaseNotes }, "v" + P.meta.version),
        " · ", P.meta.ha ? "🟢 Home Assistant" : "⚪ " + I18N.tr(T("without Home Assistant")))));
  const main = h("main.main");
  // views pass optional sections as null – DOM append would print them as the text "null"
  // until the page has its data: a loading spinner (the first content the view adds replaces it)
  const spinner = h("div.page-loading", { role: "status", "aria-label": T("Loading…") }, h("span.spinner"), h("span.small.muted", T("Loading…")));
  main.append = (...xs) => { spinner.remove(); Element.prototype.append.apply(main, xs.flat().filter(x => x != null && x !== false)); };
  Element.prototype.append.call(main, spinner);
  // phone: the side bar is a ☰ menu that slides in from the left; a slim bar shows ☰ and the page
  const back = h("div.side-back", { onclick: () => closeNav() });
  // the closed menu is off screen: not reachable with Tab or a screen reader (inert) – on wide screens it is the side bar
  const narrow = matchMedia("(max-width: 820px)");
  const setInert = () => { nav.inert = narrow.matches && !nav.classList.contains("open"); };
  narrow.onchange = setInert;
  let navOpener = null, navRelease = null;
  // open: focus stays inside the menu (Tab wraps around), Esc closes it wherever the focus is (shared/ui.js focusTrap)
  const closeNav = () => { const was = nav.classList.contains("open"); nav.classList.remove("open"); back.classList.remove("open"); setInert();
    if (navRelease) { navRelease(false); navRelease = null; }
    if (was && navOpener && navOpener.isConnected && (nav.contains(document.activeElement) || document.activeElement === document.body)) navOpener.focus(); };
  const openNav = () => { navOpener = document.activeElement; nav.classList.add("open"); back.classList.add("open"); setInert();
    requestAnimationFrame(() => (nav.querySelector("button[data-tab].on") || nav.querySelector("button[data-tab]")).focus({ preventScroll: true }));
    if (navRelease) navRelease(false);
    navRelease = focusTrap(back, nav, closeNav); };
  nav.addEventListener("click", e => { if (e.target.closest(".side > button, .side-foot button, .side-foot a")) closeNav(); });
  const cur = TABS.find(t => t[0] === (P.tab === "import" ? "packs" : P.tab)) || TABS[0];
  const mob = h("header.mob-bar",
    h("button.icon-btn.mob-menu", { "aria-label": T("Menu"), title: T("Menu"), onclick: openNav }, "☰"),
    h("span.mob-ic", cur[1]), h("strong.mob-title", cur[2]), h("span.grow"), refreshBtn());
  app.replaceChildren(h("div.layout", nav, back, h("div.main-wrap", mob, main)));
  setInert();
  const titled = () => { const t = main.querySelector("h1"); mob.classList.toggle("titled", !t || t.getBoundingClientRect().bottom < mob.getBoundingClientRect().bottom); };
  window.onscroll = titled; setTimeout(titled, 600);
  const views = { community: communityView, games: gamesView, chores: choresView, overview: overviewView, weather: weatherView, calendar: calendarView, packs: packsView, import: importView, rewards: rewardsView, shop: shopSettingsView, settings: settingsView, history: historyView, privacy: m => privacyView(m) };   // privacy: parent-privacy.js
  views.analytics = m => analyticsView(m);          // 📈 Analytics (parent-analytics.js)
  // a page that cannot load shows why and offers to try again – instead of an empty or broken page
  views[P.tab](main).catch(e => {
    if (!main.isConnected) return;                 // another page was opened meanwhile
    main.replaceChildren(h("section.card.page-error", h("h2", "⚠️ ", T("This page could not be loaded")),
      h("p.muted", e && e.message ? e.message : String(e)),
      h("button.btn", { onclick: () => render() }, "⟳ ", T("Try again"))));
  });
}

function section(title, ...content) { return h("section.card.sec", h("h2", title), ...content); }
/** A group heading on the page background (Family, Settings, Overview, Games, Calendar, Privacy): its ⓘ by `ik`
 *  (a key of PARENT_INFO), the boxes or folds of the group follow it. Actions (buttons) stand on its right. */
function setGroup(ik, icon, title, ...actions) {
  const head = h("h2.set-group", { "data-ik": ik }, icon + " ", title);
  const act = actions.flat().filter(Boolean);
  return act.length ? h("div.set-group-row", head, h("div.head-actions", ...act)) : head;
}
/** An old address (TAB_ALIAS) named a fold of a page that draws its folds itself (setFold): open it and show it. */
function foldToShow(root) {
  if (!P.foldTo) return;
  const d = root.querySelector(`details.set-fold[data-set="${P.foldTo}"]`);
  if (!d) return;
  P.foldTo = null; d.open = true;
  setTimeout(() => d.scrollIntoView({ block: "start" }), 50);
}
// the standard: «add» buttons sit top right – of the page (pageHead) or of a box (sectionAdd)
function pageHead(title, ...actions) { return h("div.page-head", h("h1", title), h("div.head-actions", ...actions)); }
function sectionAdd(title, actions, ...content) {
  return h("section.card.sec", h("div.sec-head", h("h2", title), h("div.head-actions", ...[].concat(actions))), ...content);
}
const chip = (t, cls = "") => h("span.chip" + (cls ? "." + cls : ""), t);

// a search that finds nothing: say so, with a link that clears the search
function noMatch(text, reset) {
  return h("p.muted.no-match", { hidden: true }, "🔍 ", text, " · ",
    h("a", { href: "#", onclick: e => { e.preventDefault(); reset(); } }, T("Reset search")));
}

// an open «⋯» menu closes with a tap anywhere else
document.addEventListener("click", e => document.querySelectorAll("details.more-menu[open]").forEach(d => { if (!d.contains(e.target)) d.open = false; }));

// the foot of the menu: light / dark and the language as written-out items
// «open in the app»: the game in the app (frontend) in a new tab – logged in as this parent
function openInApp(path) {
  const win = window.open("about:blank", "_blank");          // opened right away: browsers block windows opened later
  call("parent/app-token", { method: "POST" }).then(r => {
    const url = "app#/as/" + r.token + "/" + path;
    if (win) win.location.href = url; else location.href = url;
  }).catch(() => win && win.close());
}
const appBtn = path => h("button.btn.small.ghost", { title: T("Opens the game in the app in a new tab"), onclick: () => openInApp(path) }, "↗ ", T("Open in the app"));

/** A page of folds like the settings (setFold): every box of `root` folded, its title in the row and a short status below it –
 *  `sec.dataset.status`, else `statusOf(sec)`. The fold id is `prefix.` + `sec.dataset.fold` (or the title); open ones stay open
 *  while the page is drawn again. `P.foldTo` (an old address, e.g. #goals) opens and shows one fold. */
function foldBoxes(root, prefix, statusOf = () => "") {
  for (const sec of [...root.querySelectorAll(":scope > section.card")]) {
    const head = sec.querySelector(":scope > h2, :scope > .sec-head > h2, :scope > .row > h2, :scope > div > .sec-head > h2");
    if (!head) continue;
    const row = head.parentElement.classList.contains("row") ? head.parentElement : null;     // avatar · name · count (packs by child)
    const title = [row && row.querySelector("svg") ? row.querySelector("svg").cloneNode(true) : null, ...[...head.childNodes].map(n => n.cloneNode(true))].filter(Boolean);
    title.forEach(n => n.querySelectorAll && n.querySelectorAll(".info-btn").forEach(x => x.remove()));
    const id = prefix + "." + (sec.dataset.fold || _infoNorm(head.textContent));
    const spot = document.createComment("");
    sec.replaceWith(spot);
    const d = setFold(id, title, sec);
    if (head.dataset.ik) d.querySelector(".set-head > h2").dataset.ik = head.dataset.ik;
    if (row) row.hidden = true;
    else head.classList.add("fold-title");                   // shown in the row of the fold – hidden in the box
    spot.replaceWith(d);
    const st = d.querySelector(".set-status");
    st.textContent = sec.dataset.status != null ? sec.dataset.status : statusOf(sec) || "";
    if (sec.hidden) d.hidden = true;
  }
  if (P.foldTo && P.foldTo.startsWith(prefix + ".")) {
    const d = root.querySelector(`details.set-fold[data-set="${P.foldTo}"]`);
    P.foldTo = null;
    if (d) { d.open = true; setTimeout(() => d.scrollIntoView({ block: "start" }), 50); }
  }
}

/** A file picker in the language of the app: the browser's own «Choose File / No file chosen» stays in the browser's
 *  language – so the input is hidden (still in the page, «change» works as before) and a translated button opens it. */
function fileButton(input, ...label) {
  input.classList.add("file-hidden");
  input.tabIndex = -1;
  const name = h("span.small.muted.file-name", T("No file chosen"));
  input.addEventListener("change", () => { name.textContent = input.files[0] ? input.files[0].name : I18N.tr(T("No file chosen")); });
  return h("div.row.file-pick", h("button.btn.ghost", { type: "button", onclick: () => input.click() }, ...label), name, input);
}

// ---------------------------------------------------------------- settings: every part folded, with its status
// Each part is a fold (details, a 44 px row – the whole row opens it) with its title and a short status of how it is
// set now («No restrictions», «Last backup: 12.11.2026» …). The part itself stays as it is inside the fold (its own
// title is hidden there). Open folds stay open when the page is drawn again (e.g. after saving).
const SET_OPEN = new Set();
function setFold(id, title, sec) {
  if (!sec) return null;
  sec.classList.add("set-body");
  const d = h("details.card.sec.fold.set-fold", { "data-set": id },
    h("summary", h("div.set-head", h("h2", title), h("span.set-status", { "data-set": id }, "…"))), sec);
  d.open = SET_OPEN.has(id);
  d.addEventListener("toggle", () => { if (d.open) SET_OPEN.add(id); else SET_OPEN.delete(id); });
  return d;
}

// the pages live in the other parent-*.js files (eltern.html): start when every script of the page is loaded
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => boot()); else boot();
