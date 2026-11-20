// Family Quest – parent area. Every action needs the parent PIN (token in sessionStorage, 30 min).
"use strict";

const P = { info: null, meta: null, tab: "overview", profiles: [], accounts: [] };
const app = $("#app");
const TABS = [["overview", "📊", T("Overview")], ["calendar", "📅", T("Calendar")], ["packs", "📦", T("Learning packs")],
  ["chores", "🧹", T("Chores")], ["community", "👨‍👩‍👧", T("Family")], ["history", "📜", T("History")], ["deals", "🤝", T("Deals")], ["games", "🎲", T("Games")], ["rewards", "🎁", T("Rewards")], ["shop", "🛍️", T("Shop")], ["dashboard", "🖥️", T("Dashboard")], ["settings", "⚙️", T("Settings")]];
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
const TAB_ALIAS = { goals: ["community", "fam.goals"], weather: ["overview"], ledger: ["history"] };
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
  const nav = h("nav.side", h("div.brand", h("img", { src: "img/icon.svg", alt: "", width: 34, height: 34 }), h("strong.grow", "Family Quest"), refreshBtn()),
    ...TABS.map(([k, ic, n]) => h("button" + (P.tab === k || (k === "packs" && P.tab === "import") ? ".on" : ""), { onclick: () => { P.tab = k; location.hash = k; render(); } }, h("span", ic), h("span", n))),
    h("div.side-foot",
      // four items one below the other, written out: app, light / dark, language, log out
      h("a.foot-item", appLinkAttrs({ dialog: true }), h("span.foot-ic", "⭐"), h("span", "Family Quest App")),
      footTheme(), footLang(),
      h("button.foot-item", { onclick: () => { Auth.parent = ""; loginView(false); } }, h("span.foot-ic", "🔒"), h("span", T("Log out"))),
      h("button.foot-item", { onclick: releaseNotes }, h("span.foot-ic", "📝"), h("span", T("Release notes"))),
      h("div.small.muted.foot-ver", P.haSlug ? h("a.muted", { href: `/config/app/${P.haSlug}/info`, target: "_top", title: T("Open in Home Assistant") }, "v" + P.meta.version)
        : "v" + P.meta.version, " · ", P.meta.ha ? "🟢 Home Assistant" : "⚪ " + I18N.tr(T("without Home Assistant")))));
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
  let navOpener = null;
  const closeNav = () => { const was = nav.classList.contains("open"); nav.classList.remove("open"); back.classList.remove("open"); setInert();
    if (was && navOpener && navOpener.isConnected && nav.contains(document.activeElement)) navOpener.focus(); };
  const openNav = () => { navOpener = document.activeElement; nav.classList.add("open"); back.classList.add("open"); setInert();
    requestAnimationFrame(() => (nav.querySelector("button.on") || nav.querySelector("button")).focus({ preventScroll: true })); };
  nav.addEventListener("keydown", e => { if (e.key === "Escape" && nav.classList.contains("open")) closeNav(); });
  nav.addEventListener("click", e => { if (e.target.closest(".side > button, .side-foot button, .side-foot a")) closeNav(); });
  const cur = TABS.find(t => t[0] === (P.tab === "import" ? "packs" : P.tab)) || TABS[0];
  const mob = h("header.mob-bar",
    h("button.icon-btn.mob-menu", { "aria-label": T("Menu"), title: T("Menu"), onclick: openNav }, "☰"),
    h("span.mob-ic", cur[1]), h("strong.mob-title", cur[2]), h("span.grow"), refreshBtn());
  app.replaceChildren(h("div.layout", nav, back, h("div.main-wrap", mob, main)));
  setInert();
  const titled = () => { const t = main.querySelector("h1"); mob.classList.toggle("titled", !t || t.getBoundingClientRect().bottom < mob.getBoundingClientRect().bottom); };
  window.onscroll = titled; setTimeout(titled, 600);
  const views = { deals: dealsParentView, dashboard: dashboardView, community: communityView, games: gamesView, chores: choresView, overview: overviewView, weather: weatherView, calendar: calendarView, packs: packsView, import: importView, rewards: rewardsView, shop: shopSettingsView, settings: settingsView, history: historyView };
  // a page that cannot load shows why and offers to try again – instead of an empty or broken page
  views[P.tab](main).catch(e => {
    if (!main.isConnected) return;                 // another page was opened meanwhile
    main.replaceChildren(h("section.card.page-error", h("h2", "⚠️ ", T("This page could not be loaded")),
      h("p.muted", e && e.message ? e.message : String(e)),
      h("button.btn", { onclick: () => render() }, "⟳ ", T("Try again"))));
  });
}

function section(title, ...content) { return h("section.card.sec", h("h2", title), ...content); }
// the standard: «add» buttons sit top right – of the page (pageHead) or of a box (sectionAdd)
function pageHead(title, ...actions) { return h("div.page-head", h("h1", title), h("div.head-actions", ...actions)); }
function sectionAdd(title, actions, ...content) {
  return h("section.card.sec", h("div.sec-head", h("h2", title), h("div.head-actions", ...[].concat(actions))), ...content);
}
const chip = (t, cls = "") => h("span.chip" + (cls ? "." + cls : ""), t);

// ---------------------------------------------------------------- overview
async function overviewView(main) {
  const [d, accounts, profiles, persons] = await Promise.all([call("parent/overview"), call("parent/accounts"), call("parent/profiles"),
    P.meta.planer ? call("parent/ha/persons").catch(() => []) : []]);
  P.accounts = accounts; P.profiles = profiles;
  const full = id => profiles.find(x => x.id === id);
  const pend = d.pending.length ? section("⏳ " + I18N.tr(T("Waiting for your approval")), h("ul.list", ...d.pending.map(r => h("li.row",
    h("span.big-ic", r.icon), h("span.grow", C(r.profile_name, "strong"), " – ", r.name, h("span.small.muted", " · " + fmt(r.cost))),
    h("button.btn.small.good", { onclick: () => decide(r.id, true) }, "✓ ", T("Approve")),
    h("button.btn.small.bad", { onclick: () => decide(r.id, false) }, "✗ ", T("Decline")))))) : null;
  async function decide(id, approve) { await call(`parent/redemptions/${id}`, { method: "POST", body: { approve } }); toast(approve ? T("Approved") : T("Declined"), "good"); render(); }
  const chorePend = d.chores_pending.length ? section("🧹 " + I18N.tr(T("Chores to confirm")), choreConfirmList(d.chores_pending, render)) : null;
  // every child a folded row: folded it shows the weather of the day to pick and «Edit profile»; open: everything else
  const wd = await call("parent/weather").catch(() => null);
  const kids = d.kids.map(k => {
    const wk = wd && wd.config.enabled ? wd.kids.find(x => x.profile.id === k.profile.id) : null;
    const w = wk ? kidWeather(wk, wd.config) : null;
    const id = k.profile.id;
    return h("details.card.sec.kid.kid-fold", { "data-kid": id, open: KID_OPEN.has(id), ontoggle: e => e.currentTarget.open ? KID_OPEN.add(id) : KID_OPEN.delete(id) },
      h("summary",
        h("div.row.kid-head", avatarSvg(k.profile.avatar, 48), h("div.grow", C(k.profile.name, "h2"),
          h("span.muted", I18N.tr(T("Level {0}")).replace("{0}", k.level.level) + " · 🔥 " + k.streak), " ", loginChip(k.profile),
          k.sad_since ? h("span.mood-flag", { title: I18N.tr(T("feels sad")) }, " 😢") : null), w ? w.now : null),
        // a tap on these buttons does not open the row
        h("div.row.wrap.kid-quick", { onclick: e => { if (e.target.closest("button")) e.preventDefault(); } },
          h("button.btn.small.ghost", { onclick: () => profileDialog(full(id) || k.profile, persons) }, "✏️ ", T("Edit profile")),
          w ? w.pick : null)),
      k.sad_since ? h("div.mood-note", "😢 ", T("feels sad"), " (", T("since"), " ",
        new Date(k.sad_since).toLocaleString(I18N.locale, { weekday: "short", hour: "2-digit", minute: "2-digit" }), ")") : null,
      k.mood_text || k.mood ? h("div.mood-text", h("span.mood-emoji", k.mood || "💬"), " ", T("Today I feel …"), " ", k.mood_text ? C("«" + k.mood_text + "»", "strong") : null,
        k.mood_text_at ? h("span.small.muted", " · " + new Date(k.mood_text_at).toLocaleString(I18N.locale, { weekday: "short", hour: "2-digit", minute: "2-digit" })) : null) : null,
      h("div.row.kid-actions",
        h("button.btn.small" + (k.profile.crown ? "" : ".ghost"), { title: T("Crown for today"), onclick: async () => {
          await call(`parent/profiles/${id}/crown`, { method: "POST", body: { on: !k.profile.crown } });
          toast(k.profile.crown ? T("Crown taken off") : T("👑 Crown for today!"), "good"); render();
        } }, "👑"),
        h("button.btn.small.ghost", { onclick: () => bookDialog(k.profile) }, "± ", T("Book points"))),
    h("div.kpis",
      kpi(T("XP this week"), fmt(k.week.xp)), kpi(T("Daily goal this week"), k.week.goal_percent + " %"),
      kpi(T("Days with goal"), String(k.week.days_met)), kpi(T("Minutes this week"), fmt(k.week.minutes)),
      ...P.accounts.filter(a => a.active && a.spendable && !(a.key === "internet" && k.internet)).map(a => kpi(a.icon + " " + I18N.tr(a.name), fmt(k.balances[a.key], 1))),
      k.chores && k.chores.reliability != null ? kpi("🧹 " + I18N.tr(T("Chores reliability")), fmt(k.chores.reliability) + " %") : null,
      k.internet ? h("div.kpi" + (k.internet.running ? ".net-on" : ""), h("b", (k.internet.running ? "🟢 " : "🌐 ") + fmt(k.internet.minutes) + " min"),
        h("span.small.muted", k.internet.running ? I18N.tr(T("Internet is on")) : I18N.tr(T("Internet time"))),
        k.internet.running ? h("button.btn.small.bad", { onclick: async () => { await call(`parent/internet/${k.profile.id}/stop`, { method: "POST" }); toast(T("Internet stopped"), "good"); render(); } }, "⏸ ", T("Stop")) : null) : null),
    k.pets && k.pets.length ? petsBox(k, render) : null,
    h("div.cols",
      h("div", h("h3", T("Packs")), k.packs.length ? h("ul.list", ...k.packs.map(p => h("li", h("div.row", C(p.title, "span.grow"), h("b", p.percent + " %"),
        p.due ? chip(p.due + " " + I18N.tr(T("due")), "warn") : null), bar(p.percent, 100, p.color)))) : h("p.muted", T("No packs active."))),
      h("div", h("h3", T("Learning time per subject (7 days)")), k.subjects.length ? h("table.tbl", h("tbody", ...k.subjects.map(s =>
        h("tr", h("td", subjectName(s.subject)), h("td.num", s.answers + " " + I18N.tr(T("answers"))), h("td.num", Math.round(100 * s.right / Math.max(1, s.answers)) + " %"),
          h("td.num", fmt(s.minutes, 1) + " min"))))) : h("p.muted", T("Nothing learnt yet this week."))),
      h("div", h("h3", T("Weak spots")), k.weak.length ? h("ul.list.weak", ...k.weak.map(w => h("li", C(w.label, "strong"),
        h("div.small.muted", C(w.unit), " · ", w.wrong + " / " + w.tries + " " + I18N.tr(T("wrong")))))) : h("p.muted", T("No weak spots yet – great!")))),
    w ? h("div.kid-weather", h("h3", "⛅ ", T("Weather of the day")), w.hist) : null);
  });
  const failed = await call("parent/logins/failed?days=30").catch(() => []);
  // folded, the number in the title – details only when wanted
  const failBox = failed.length ? h("details.card.sec.fold", h("summary", h("h2", "🔐 " + I18N.tr(T("Failed logins (30 days)")) + " ", chip(String(failed.length), "warn"))),
    h("div.scroll", h("table.tbl.logins",
      h("thead", h("tr", h("th", T("When")), h("th", T("Profile")), h("th", T("IP address")), h("th", "MAC"), h("th", T("Device")), h("th", T("Usually")))),
      h("tbody", ...failed.map(r => h("tr",
        h("td", new Date(r.at.replace(" ", "T")).toLocaleString(I18N.locale, { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })),
        h("td", r.kind === "parent" ? I18N.tr(T("Parent area")) : r.kind === "blocked" ? "🛡️ " + I18N.tr(T("Blocked network")) : C(r.profile_name || "?")),
        h("td.mono", r.ip || "–"), h("td.mono", r.mac || "–"), h("td", r.device ? C(r.device) : "–"),
        h("td", r.usual ? h("span", C(r.usual.name), h("span.small.muted", " (" + r.usual.n + "×)")) : h("span.warn-text", T("nobody yet")))))))))
    : null;
  main.append(pageHead(T("Overview"),
      P.meta.planer ? h("button.btn.ghost", { onclick: importPersons }, "📅 ", T("Take over from Family Planer")) : null,
      h("button.btn.ghost", { onclick: () => profileDialog(null, persons, "parent") }, "+ ", T("Add parent")),
      h("button.btn", { onclick: () => profileDialog(null, persons, "kid") }, "+ ", T("Add child"))), d.kids.length ? partyCard() : null, pend || (chorePend ? null : h("p.muted", "✓ ", T("No open approvals."))), chorePend,
    d.family_goal ? section("🤝 " + I18N.tr(T("Family goal")), h("div.row", C(d.family_goal.title, "strong.grow"), h("b", fmt(d.family_goal.value) + " / " + fmt(d.family_goal.target))),
      bar(d.family_goal.value, d.family_goal.target, "var(--good)")) : null,
    ...(kids.length ? kids : [h("div.card", h("p", T("No child profile yet.")))]),
    section("👪 " + I18N.tr(T("Parents")),
      profileCards(profiles.filter(p => p.role === "parent"), persons)),
    await archivedSection(),
    failBox);                                    // the failed logins: at the very bottom
  async function importPersons() {
    const r = await call("parent/ha/import_persons", { method: "POST" });
    toast(r.created.length ? I18N.tr(T("Created: {0}")).replace("{0}", r.created.join(", ")) : T("All persons are already linked"), "good");
    render();
  }
}

// the pets of a child (pets.py): bars and status, «holiday care» pauses them
function petsBox(k, render) {
  const paused = k.pets_paused, away = !paused && k.pets.some(p => p.paused === "away");
  return h("div.pets-box",
    h("div.row", h("h3.grow", "🐾 ", T("Pets")),
      away ? chip(I18N.tr(T("away (Family Planer)")), "") : null,
      h("button.btn.small" + (paused ? "" : ".ghost"), { title: T("While holiday care is on, the pets do not get hungry, sad or dirty."), onclick: async () => {
        await call(`parent/profiles/${k.profile.id}/pet-pause`, { method: "PUT", body: { on: !paused } });
        toast(paused ? T("Holiday care ended") : T("Holiday care is on"), "good"); render();
      } }, paused ? "▶ " : "⏸ ", paused ? T("End holiday care") : T("Holiday care"))),
    h("div.pet-mini-list", ...k.pets.map(p => h("div.pet-mini" + (p.dying ? ".dying" : ""),
      h("span.pet-mini-ic", petIcon(p.kind, 34, p.emoji)), h("div.grow", h("div", C(p.name, "strong"), h("span.small.muted", " · " + I18N.tr(p.age === 1 ? T("1 day old") : T("{0} days old")).replace("{0}", p.age))),
        h("div.pet-mini-bars", ...[["hunger", "🍖"], ["mood", "😊"], ["clean", "🫧"]].map(([b, ic]) => h("span.pet-mini-bar", { title: ic + " " + p[b] }, ic,
          bar(p[b], 100, p[b] < 25 ? "var(--bad)" : p[b] < 50 ? "var(--warn)" : "var(--good)")))),
        p.dying ? h("div.small.warn-text", "🆘 ", I18N.tr(T("All bars empty – dies in {0} days")).replace("{0}", Math.max(0, Math.ceil(p.days_left)))) : null)))));
}

// archived (inactive) profiles: restore or delete for good
async function archivedSection() {
  let list = []; try { list = await call("parent/profiles/archived"); } catch {}
  if (!list.length) return null;
  return section("🗄️ " + I18N.tr(T("Archived profiles")),
    h("ul.list", ...list.map(p => h("li.row", avatarSvg(p.avatar, 36), C(p.name, "strong.grow"),
      h("button.btn.small.ghost", { onclick: async () => { await call(`parent/profiles/${p.id}/restore`, { method: "POST" }); toast(T("Restored"), "good"); render(); } }, "↩️ ", T("Restore")),
      h("button.btn.small.bad", { onclick: () => removeDialog(p, true) }, "🗑 ", T("Delete"))))));
}

// removing a profile: type the name again, choose archive (inactive) or delete (gone), confirm
function removeDialog(p, archived = false, done) {
  let mode = archived ? "delete" : "archive";
  const name = h("input", { type: "text", autocomplete: "off", placeholder: p.name });
  const ok = h("input", { type: "checkbox" });
  const btn = h("button.btn.bad", { disabled: true, onclick: go });
  const modes = h("div.grid2.remove-modes");
  const okText = h("span");
  const draw = () => {
    modes.replaceChildren(...[["archive", "🗄️", T("Archive"), T("The profile becomes inactive: it disappears from the app, its history stays and you can restore it.")],
      ["delete", "🗑", T("Delete for good"), T("The profile and all its data (points, progress, history) are deleted. This cannot be undone.")]]
      .filter(([k]) => !(archived && k === "archive"))
      .map(([k, ic, n, hint]) => h("button.remove-mode" + (mode === k ? ".on" : ""), { type: "button", onclick: () => { mode = k; draw(); } },
        h("strong", ic + " ", n), h("span.small.muted", hint))));
    okText.textContent = I18N.tr(mode === "delete" ? T("Yes, delete this profile for good.") : T("Yes, archive this profile."));
    btn.textContent = I18N.tr(mode === "delete" ? T("Delete for good") : T("Archive"));
    check();
  };
  const check = () => { btn.disabled = !(ok.checked && name.value.trim().toLowerCase() === p.name.trim().toLowerCase()); };
  name.oninput = check; ok.onchange = check;
  const m = modal(h("div.form",
    h("h2", "⚠️ ", T("Remove profile")), h("div.row", avatarSvg(p.avatar, 48), C(p.name, "strong")),
    modes,
    h("label.field", I18N.tr(T("Type the name «{0}» to confirm")).replace("{0}", p.name), name),
    h("label.check", ok, okText),
    h("div.row", btn, h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  draw();
  async function go() {
    try {
      await call(`parent/profiles/${p.id}?mode=${mode}&name=${encodeURIComponent(name.value.trim())}`, { method: "DELETE" });
      m.close(); toast(mode === "delete" ? T("Profile deleted") : T("Profile archived"), "good"); done && done(); render();
    } catch (e) { toast(e.message, "bad"); }
  }
}

const kpi = (label, value) => h("div.kpi", h("b", value), h("span.small.muted", label));
const subjectName = k => { const s = (P.meta.subjects || []).find(s => s.key === k); return s ? s.icon + " " + I18N.tr(s.name) : k || "–"; };

function bookDialog(profile) {
  const acc = h("select", ...P.accounts.filter(a => a.active).map(a => h("option", { value: a.key }, a.icon + " " + I18N.tr(a.name))));
  const amount = h("input", { type: "number", value: "10", step: "1" });
  const reason = h("input", { type: "text", placeholder: T("e.g. helped with cooking") });
  const m = modal(h("div.form", h("h2", T("Book points")), C(profile.name, "strong"),
    h("label.field", T("Account"), acc), h("label.field", T("Amount (negative = deduct)"), amount), h("label.field", T("Reason"), reason),
    h("div.row", h("button.btn", { onclick: async () => {
      await call("parent/book", { method: "POST", body: { profile_id: profile.id, account: acc.value, amount: Number(amount.value), reason: reason.value } });
      m.close(); toast(T("Booked"), "good"); render();
    } }, T("Book points")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

// ---------------------------------------------------------------- profiles
// how a profile signs in (profile setting «login», see the profile dialog)
const LOGIN_CHIP = { none: ["🪄", T("No sign-in")], pin: ["🔢", T("PIN")], ha: ["🏠", T("Home Assistant only")], pin_ha: ["🔢🏠", T("PIN or Home Assistant")] };
function loginChip(p) {
  const c = LOGIN_CHIP[p.login];
  return c ? h("span.chip.login-chip", { title: I18N.tr(T("Sign-in")) }, c[0], " ", c[1]) : null;
}
function profileCards(list, persons) {
  if (!list.length) return h("p.muted", T("Nobody yet."));
  return h("div.profile-cards", ...list.map(p => h("div.card.pcard", avatarSvg(p.avatar, 72),
    h("div.grow", C(p.name, "h2"), h("div.small.muted", p.role === "parent" ? T("Parent") : T("Child"),
      p.planer_person_id ? " · 📅 Family Planer" : "", p.id === P.meta.me.id ? " · " + I18N.tr(T("that's you")) : ""),
      loginChip(p),
      p.role === "kid" ? h("div.small", T("Daily goal"), ": ", p.settings.daily_goal + " XP · ", T("Lesson"), ": ", p.settings.lesson_length) : null,
      p.role === "parent" && p.settings.notify_service ? h("div.small", "🔔 ", C(p.settings.notify_service)) : null),
    h("button.btn.small.ghost", { onclick: () => profileDialog(p, persons) }, "✏️ ", T("Edit")))));
}

// a select with the Home Assistant entities of some domains (the current value stays even if it is not found)
function entitySelect(current, domains) {
  const sel = h("select.grow", h("option", { value: "" }, "–"));
  const keep = v => { if (v && ![...sel.options].some(o => o.value === v)) sel.append(h("option", { value: v }, v)); sel.value = v || ""; };
  keep(current);
  if (P.meta.ha) Promise.all(domains.map(d => call("parent/ha/entities?domain=" + d).catch(() => []))).then(lists => {
    const v = sel.value;
    sel.replaceChildren(h("option", { value: "" }, "–"), ...lists.flat().map(e => h("option", { value: e.entity_id }, (e.name && e.name !== e.entity_id ? e.name + " – " : "") + e.entity_id)));
    keep(v);
  });
  else if (!current) sel.replaceChildren(h("option", { value: "" }, I18N.tr(T("Home Assistant is not connected"))));
  sel.setValue = keep;
  return sel;
}

// ---------------------------------------------------------------- time sliders (games, learning, internet per day)
// positions of the slider → minutes: minutes first, then hours; the last position (far right) is ∞ = unlimited
const LIMIT_STEPS = [0, 5, 10, 15, 20, 30, 45, 60, 75, 90, 120, 150, 180, 240, 300, 360, 480, 600, 720];
const LIMIT_STEPS_WEEK = [0, 30, 60, 90, 120, 180, 240, 300, 360, 420, 480, 600, 720, 900, 1080, 1200, 1500, 1800, 2400];

/** A master slider with a «Days» button: 7 weekday sliders (Mon … Sun) docked to it – they move with the master
 *  until one is moved on its own (undocked: own limit); moved back to the master's value it docks again.
 *  value {all: minutes|null, days: {"0".."6": minutes|null}} – null = ∞, days only the undocked ones. */
function limitSlider({ icon, label, value, steps = LIMIT_STEPS, extra = null }) {
  const v = Object.assign({ all: null, days: {} }, value || {});
  let master = v.all;                                         // minutes or null (∞)
  const own = {};                                             // undocked weekdays: own minutes or null
  for (const [k, x] of Object.entries(v.days || {})) if (/^[0-6]$/.test(k) && x !== master) own[k] = x;
  const INF = () => steps.length;                            // index of ∞
  const toMin = i => i >= INF() ? null : steps[i];
  const toIdx = m => {                                       // the nearest position (a value between steps stays as it is until moved)
    if (m == null) return INF();
    let best = 0;
    steps.forEach((x, i) => { if (Math.abs(x - m) < Math.abs(steps[best] - m)) best = i; });
    return best;
  };
  const paint = (inp, m) => { const i = toIdx(m); inp.max = INF(); inp.value = i; inp.style.setProperty("--p", (i / INF() * 100) + "%");
    inp.setAttribute("aria-valuetext", fmtMinutes(m)); };
  const masterOut = h("output.lim-val");
  const masterIn = h("input.lim-range", { type: "range", min: 0, step: 1, "aria-label": label });
  const scale = h("div.lim-scale", { "aria-hidden": "true" });
  const drawScale = () => scale.replaceChildren(...[0, Math.round(INF() * .37), Math.round(INF() * .63), INF()]
    .map(i => h("span", { style: { "--p": i / INF() } }, i === INF() ? "∞" : fmtMinutes(steps[i]))));
  const dayRows = WEEKDAYS.map((d, i) => {
    const k = String(i);
    const inp = h("input.lim-range.lim-day-range", { type: "range", min: 0, step: 1, "aria-label": I18N.tr(label) + " – " + I18N.tr(d) });
    const out = h("output.lim-val");
    const pin = h("button.lim-pin", { type: "button", onclick: () => { delete own[k]; draw(); } });
    const row = h("div.lim-day", h("span.lim-dname", d), inp, out, pin);
    inp.addEventListener("input", () => {
      const m = toMin(+inp.value);
      if (+inp.value === toIdx(master)) delete own[k]; else own[k] = m;     // back on the master's value: docked again
      draw();
    });
    return { k, row, inp, out, pin };
  });
  const week = h("div.lim-week", { hidden: true }, ...dayRows.map(r => r.row));
  const daysBtn = h("button.btn.small.ghost.lim-days", { type: "button", "aria-expanded": "false",
    onclick: () => { week.hidden = !week.hidden; draw(); } }, "📅 ", T("Days"));
  masterIn.addEventListener("input", () => { master = toMin(+masterIn.value); draw(); });
  function draw() {
    paint(masterIn, master);
    masterOut.textContent = fmtMinutes(master);
    masterIn.classList.toggle("inf", master == null);
    const n = Object.keys(own).length;
    daysBtn.setAttribute("aria-expanded", String(!week.hidden));
    daysBtn.classList.toggle("on", !week.hidden);
    daysBtn.replaceChildren(...["📅 ", I18N.tr(T("Days")), n ? h("span.lim-badge", String(n)) : ""].filter(Boolean));
    for (const r of dayRows) {
      const docked = !(r.k in own), m = docked ? master : own[r.k];
      paint(r.inp, m);
      r.out.textContent = fmtMinutes(m);
      r.row.classList.toggle("own", !docked);
      r.pin.textContent = docked ? "🔗" : "🔓";
      r.pin.title = I18N.tr(docked ? T("Moves with the slider above") : T("Own time – tap to dock again"));
      r.pin.disabled = docked;
    }
  }
  drawScale();
  if (Object.keys(own).length) week.hidden = false;         // a weekday with its own time: the days are open
  draw();
  const el = h("div.lim", h("div.lim-head", h("span.lim-ic", icon), h("b.grow", label), masterOut, extra, daysBtn),
    h("div.lim-master", masterIn, scale), week);
  return {
    el,
    value: () => ({ all: master, days: daysBtn.hidden ? {} : Object.fromEntries(Object.entries(own).filter(([, x]) => x !== master)) }),
    /** per week: no weekday sliders; other steps */
    setMode(withDays, newSteps) {
      daysBtn.hidden = !withDays;
      if (!withDays) week.hidden = true;
      if (newSteps && newSteps !== steps) { steps = newSteps; drawScale(); }
      draw();
    },
  };
}

/** Internet budget of a child: the slider (minutes per day / week, own minutes per weekday) for the time sliders,
 *  reset time and block times. A budget of 0 without weekdays and block times = no plan (only earned minutes). */
function internetPlanEditor(cur) {
  const p = Object.assign({ budget: 0, period: "day", reset: "00:00", reset_day: 0, days: {}, blocks: [] }, cur || {});
  const period = h("select.lim-period", { "aria-label": T("Internet") }, h("option", { value: "day", selected: p.period === "day" }, T("per day")), h("option", { value: "week", selected: p.period === "week" }, T("per week")));
  const slider = limitSlider({ icon: "🌐", label: T("Internet"), value: { all: p.budget, days: p.period === "day" ? p.days : {} },
    steps: p.period === "week" ? LIMIT_STEPS_WEEK : LIMIT_STEPS, extra: period });
  const reset = h("input", { type: "time", value: p.reset });
  const resetDay = h("select", ...WEEKDAYS.map((d, i) => h("option", { value: i, selected: +p.reset_day === i }, d)));
  const resetDayField = h("label.field", T("Reset on"), resetDay);
  const blocks = p.blocks.map(b => Object.assign({}, b));
  const blockBox = h("div.plan-blocks");
  const MODES = { internet: T("Family Quest works normally"), games: T("Family Quest without games"), app: T("Only a message: OfflineTime") };
  const drawBlocks = () => blockBox.replaceChildren(...blocks.map((b, bi) => h("div.plan-block",
    h("div.row.wrap", ...WEEKDAYS.map((d, i) => h("label.check", h("input", { type: "checkbox", checked: b.days.includes(i),
      onchange: e => { b.days = e.target.checked ? [...b.days, i] : b.days.filter(x => x !== i); } }), d))),
    h("div.row.wrap", h("input", { type: "time", value: b.from, onchange: e => { b.from = e.target.value; } }), "–",
      h("input", { type: "time", value: b.to, onchange: e => { b.to = e.target.value; } }),
      h("select", { onchange: e => { b.mode = e.target.value; } }, ...Object.entries(MODES).map(([k, n]) => h("option", { value: k, selected: b.mode === k }, n))),
      h("button.icon-btn", { type: "button", title: T("Delete"), onclick: () => { blocks.splice(bi, 1); drawBlocks(); } }, "🗑️")))),
    h("button.btn.small.ghost", { type: "button", onclick: () => { blocks.push({ days: [0, 1, 2, 3, 4], from: "20:00", to: "07:00", mode: "internet" }); drawBlocks(); } }, "+ ", T("Block time")));
  drawBlocks();
  const sync = () => { resetDayField.hidden = period.value !== "week"; slider.setMode(period.value === "day", period.value === "week" ? LIMIT_STEPS_WEEK : LIMIT_STEPS); };
  period.onchange = sync;
  sync();
  return {
    slider,
    el: h("div.plan", h("b", T("Internet budget and block times"), fieldInfo(T("Minutes from the shop or rewards come on top; the budget is used first and starts again at the reset."))),
      h("div.field-row", resetDayField, h("label.field", T("Reset at"), reset)),
      h("div.field", h("b", T("Block times"), fieldInfo(T("The internet is off – and you choose what Family Quest still allows."))), blockBox)),
    value: () => {
      const sv = slider.value(), bl = blocks.filter(b => b.days.length);
      if (sv.all === 0 && !Object.keys(sv.days).length && !bl.length) return null;      // no plan: only earned minutes
      return { budget: sv.all, period: period.value, reset: reset.value || "00:00", reset_day: +resetDay.value, days: sv.days, blocks: bl };
    },
  };
}

async function profileDialog(p, persons, role = "kid") {
  const isNew = !p;
  p = p || { name: "", role, color: role === "parent" ? "#495057" : "#4f8cff", settings: Object.assign({}, P.meta.profile_defaults), planer_person_id: null };
  const s = Object.assign({}, P.meta.profile_defaults, p.settings);
  const f = {
    name: h("input", { type: "text", value: p.name }),
    role: h("select", h("option", { value: "kid", selected: p.role === "kid" }, T("Child")), h("option", { value: "parent", selected: p.role === "parent" }, T("Parent"))),
    color: h("input", { type: "color", value: p.color }),
    pin: h("input", { type: "password", inputmode: "numeric", autocomplete: "new-password" }),
    daily_goal: h("input", { type: "number", min: 5, max: 1000, value: s.daily_goal }),
    lesson_length: h("input", { type: "number", min: 4, max: 40, value: s.lesson_length }),
    new_per_lesson: h("input", { type: "number", min: 0, max: 20, value: s.new_per_lesson }),
    learning_hours: h("input", { type: "text", placeholder: "07:00-20:00", value: s.learning_hours || "" }),
    auto_logout_min: h("input", { type: "number", min: 0, max: 240, value: s.auto_logout_min }),
    internet_entity: entitySelect(s.internet_entity, ["input_number", "number"]),
    internet_daily_limit: h("input", { type: "number", min: 0, max: 600, value: s.internet_daily_limit }),
    planer: h("select", h("option", { value: "" }, "–"), ...persons.map(x => h("option", { value: x.id, selected: x.id === p.planer_person_id }, x.name))),
    notify_service: h("input", { type: "text", placeholder: "notify.mobile_app_phone", value: s.notify_service || "", list: "notify-ents" }),
    internet_rule: entitySelect(s.internet_rule, ["switch", "input_boolean"]),
    internet_rule_blocks: h("input", { type: "checkbox", checked: s.internet_rule_blocks !== false }),
  };
  const ruleList = null;
  // budget entity: create a helper in Home Assistant with one click
  const createBudget = P.meta.ha ? h("button.btn.small.ghost", { type: "button", onclick: async () => {
    const name = I18N.tr(T("Internet minutes")) + " " + (f.name.value.trim() || "");
    try { const r = await call("parent/ha/input_number", { method: "POST", body: { name } }); f.internet_entity.setValue(r.entity_id); toast(T("Created in Home Assistant"), "good"); } catch {}
  } }, "➕ ", T("Create")) : null;
  const notifyList = h("datalist#notify-ents");
  if (P.meta.ha) call("parent/ha/entities?domain=notify").then(l => notifyList.replaceChildren(...l.map(e => h("option", { value: e.entity_id })))).catch(() => {});
  const ents = null;
  const plan = internetPlanEditor(s.internet_plan);
  // daily time: games, learning, internet – three sliders, each with its weekdays (children only)
  const gameLimit = limitSlider({ icon: "🎮", label: T("Games per day"), value: s.game_limit });
  const learnLimit = limitSlider({ icon: "📚", label: T("Learning per day"), value: s.learn_limit });
  const timePart = h("div.form.lim-box", h("h3", { "data-ik": "prof.time" }, "⏱️ ", T("Time per day")),
    gameLimit.el, learnLimit.el, plan.slider.el);
  const batteryPart = !isNew && p.role === "kid" ? kidBatteryBox(p.id) : null;
  const kidPart = h("div.form", h("h3", { "data-ik": "prof.internet" }, T("Internet minutes")),
    h("div.grid2", h("label.field", h("span", T("UniFi firewall rule (switch)"), fieldInfo(T("The child starts and stops the internet time in the app; the budget is the account «Internet minutes»."))), f.internet_rule, ruleList),
      h("label.check", f.internet_rule_blocks, T("The rule blocks the internet while the switch is on"))),
    h("div.grid2", h("label.field", h("span", T("Budget entity in Home Assistant"), fieldInfo(T("Receives the minutes from the shop, e.g. for your own automations."))), h("div.row", f.internet_entity, createBudget)),
      h("label.field", T("Maximum minutes per day from the shop"), f.internet_daily_limit)),
    plan.el);
  const parentPart = h("div.form", h("h3", { "data-ik": "prof.push" }, "🔔 ", T("Push messages")),
    h("label.field", T("Notify service of this parent"), f.notify_service, notifyList));
  // Home Assistant devices this profile may switch (light in the own room, …)
  const devSel = new Set(s.devices || []);
  const devSearch = h("input", { type: "search", placeholder: I18N.tr(T("Search …")) });
  const devList = h("div.dev-pick");
  const devPick = h("div", { hidden: true }, devSearch, devList);
  const devPills = h("div.dev-pills");
  let devNames = {};
  const drawPills = () => devPills.replaceChildren(...[...devSel].map(id => h("span.chip.dev-pill", { title: id, translate: "no" }, devNames[id] || id)),
    !devSel.size ? h("span.small.muted", T("No devices yet.")) : null,
    h("button.btn.small.ghost", { type: "button", onclick: () => { devPick.hidden = !devPick.hidden; if (!devPick.hidden) devSearch.focus(); } }, "✏️ ", T("Edit")));
  const devBox = h("div", devPills, devPick);
  drawPills();
  if (P.meta.ha) Promise.all([call("parent/ha/areas").then(l => l.map(a => ({ entity_id: "area." + a.area_id,
      name: "🏠 " + a.name + " · " + I18N.tr(T("whole room ({0} devices)")).replace("{0}", a.count) }))).catch(() => []),
    ...["light", "switch", "fan", "cover", "scene", "script", "input_boolean"].map(d => call("parent/ha/entities?domain=" + d).catch(() => []))])
    .then(lists => {
      const all = lists.flat();
      for (const e of all) devNames[e.entity_id] = e.name || e.entity_id;
      drawPills();
      // devices with the person's name on top (chosen ones first, lights before switches …), then other chosen ones, then the rest
      const DOM_ORDER = ["area", "light", "switch", "fan", "cover", "input_boolean", "scene", "script"];
      const rank = e => {
        const n = f.name.value.trim().toLowerCase(), txt = (e.name + " " + e.entity_id).toLowerCase();
        const dom = Math.max(0, DOM_ORDER.indexOf(e.entity_id.split(".")[0]));
        const match = n.length >= 2 && txt.includes(n), on = devSel.has(e.entity_id);
        return (match ? (on ? 0 : 100) : on ? 200 : 1000) + dom * 10;
      };
      const draw = () => { const q = devSearch.value.trim().toLowerCase();
        const list = all.filter(e => devSel.has(e.entity_id) || !q || (e.name + " " + e.entity_id).toLowerCase().includes(q))
          .map(e => [rank(e), e]).sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name, I18N.locale)).map(x => x[1]);
        devList.replaceChildren(...list.slice(0, 80).map(e =>
          h("label.check.dev", h("input", { type: "checkbox", checked: devSel.has(e.entity_id), onchange: ev => { ev.target.checked ? devSel.add(e.entity_id) : devSel.delete(e.entity_id); drawPills(); } }),
            C(e.name), h("span.small.muted.mono", " " + e.entity_id)))); };
      devSearch.oninput = draw; draw();
    });
  // avatar of this profile (not for a new one – it has no profile id yet)
  const avBox = h("div", h("p.small.muted", "…"));
  let avatar = null;
  if (!isNew) call(`parent/profiles/${p.id}/avatar`).then(d => { avatar = JSON.parse(JSON.stringify(d.avatar)); avBox.replaceChildren(avatarEditorBox(d, avatar)); }).catch(() => avBox.replaceChildren());
  // 🔐 Sign-in: one explicit choice per profile (profile setting «login», enforced by the server – db.login_mode):
  // 🪄 no sign-in (tap, children only) · 🔢 PIN · 🏠 Home Assistant only · 🔢🏠 PIN or Home Assistant.
  // The Home Assistant user shows only for the Home Assistant options, the PIN entry only for the PIN options.
  const hasHaLink = !!(p.settings && p.settings.ha_user_id);
  const haOk = () => !!(P.meta.ha || hasHaLink);          // without Home Assistant (and no link yet) the HA options are off
  let loginMode = p.login || (isNew ? (role === "parent" ? (P.meta.ha ? "ha" : "pin") : "none")
    : p.has_pin ? (hasHaLink ? "pin_ha" : "pin") : hasHaLink ? "ha" : (p.role === "parent" ? "pin" : "none"));
  const usesPin = () => loginMode === "pin" || loginMode === "pin_ha";
  const usesHa = () => loginMode === "ha" || loginMode === "pin_ha";
  const haUser = h("select", h("option", { value: "" }, "– " + I18N.tr(T("Choose a Home Assistant user")) + " –"),
    hasHaLink ? h("option", { value: p.settings.ha_user_id, selected: true, "data-name": p.settings.ha_user_name || "" }, p.settings.ha_user_name || p.settings.ha_user_id) : null);
  const haInfo = h("span.hint");
  if (P.meta.ha) call("parent/ha/users").then(list => {
    const cur = p.settings && p.settings.ha_user_id;
    haUser.replaceChildren(h("option", { value: "" }, "– " + I18N.tr(T("Choose a Home Assistant user")) + " –"), ...list.map(u => h("option", { value: u.id, selected: u.id === cur, "data-name": u.name },
      u.name + (u.linked_to && u.id !== cur ? " (" + u.linked_to + ")" : ""))));
    if (cur && !list.some(u => u.id === cur)) haUser.append(h("option", { value: cur, selected: true, "data-name": p.settings.ha_user_name || "" }, p.settings.ha_user_name || cur));
    if (!list.length) haInfo.textContent = I18N.tr(T("No Home Assistant user found – a user needs a person in Home Assistant (Settings › People)."));
  }).catch(() => {});
  // choosing a Home Assistant user: the name comes along (unless the parent typed one)
  let autoName = isNew ? "" : null;
  haUser.addEventListener("change", () => {
    const n = haUser.value ? haUser.selectedOptions[0]?.dataset.name || "" : "";
    if (n && (!f.name.value.trim() || f.name.value === autoName)) { f.name.value = n; autoName = n; }
  });
  let haKid = true;
  const haLabel = h("span");
  const haPart = h("div.login-sub", h("label.field", h("span", haLabel, fieldInfo(() => haKid
    ? T("Home Assistant sidebar and «Sign in with Home Assistant» on tablets – only the children's app, never the parent area.")
    : T("Home Assistant sidebar opens the parent area; on tablets «Sign in with Home Assistant»."))), haUser, haInfo));
  const syncHa = kid => {
    haKid = kid;
    haLabel.textContent = I18N.tr(kid ? T("Logs in to the children's app as") : T("Logs in to the parent area as"));
  };
  // PIN: children a picture PIN (4 symbols) or digits, parents digits – an existing PIN stays unless «Change PIN»
  const symbolKind = (p.settings && p.settings.pin_kind) === "symbols";
  let pinKind = p.has_pin ? (symbolKind && p.role !== "parent" ? "symbols" : "digits") : (p.role === "parent" ? "digits" : "symbols");
  let pad = null;
  const pinArea = h("div");
  const kindBtns = h("div.pin-kind");
  let changing = isNew || !p.has_pin;
  const pinForm = h("div.login-sub", kindBtns, pinArea);
  const drawPin = () => {
    const kid = f.role.value === "kid";
    if (!kid && pinKind === "symbols") pinKind = "digits";
    if (!changing) {
      kindBtns.replaceChildren();
      pinArea.replaceChildren(h("div.row",
        h("span.small.muted", "✓ " + I18N.tr(symbolKind && kid ? T("Picture PIN is set.") : T("Digit PIN is set."))),
        h("button.btn.small.ghost", { type: "button", onclick: () => { changing = true; drawPin(); } }, "🔑 ", T("Change PIN"))));
      return;
    }
    kindBtns.replaceChildren(...(kid ? [["symbols", "🐱 " + I18N.tr(T("Symbols"))], ["digits", "🔢 " + I18N.tr(T("Digits"))]] : [])
      .map(([k, n]) => h("button.btn.small" + (pinKind === k ? "" : ".ghost"), { type: "button", onclick: () => { pinKind = k; pad = null; drawPin(); } }, n)));
    if (pinKind === "symbols") pinArea.replaceChildren(pad = pad || symbolPad({ mode: "set", cancel: false }));
    else pinArea.replaceChildren(h("label.field", p.has_pin ? T("New PIN") : "PIN", f.pin, h("span.hint", kid ? T("4 digits") : T("4–8 digits"))));
  };
  const LOGIN_OPTS = [
    ["none", "🪄", T("No sign-in – tap the profile"), () => T("The child taps its picture and is in – no PIN, no Home Assistant.")],
    ["pin", "🔢", T("PIN"), kid => kid ? T("A picture PIN or a 4-digit PIN – on every device.") : T("A digit PIN (4–8 digits) – in the app and the parent area.")],
    ["ha", "🏠", T("Home Assistant only"), () => T("Only with the linked Home Assistant user (sidebar, «Sign in with Home Assistant» on tablets) – no PIN.")],
    ["pin_ha", "🔢🏠", T("PIN or Home Assistant"), () => T("Both ways: the PIN on any device, or the linked Home Assistant user.")],
  ];
  const loginList = h("div.login-opts", { role: "radiogroup" });
  const loginHint = h("p.small.muted");
  const loginForm = h("div.form.login-box", h("h3", { "data-ik": "prof.login" }, "🔐 ", T("Sign-in")), loginList, loginHint, haPart, pinForm);
  const drawLogin = () => {
    const kid = f.role.value === "kid";
    if (!kid && loginMode === "none") loginMode = "pin";          // parents always sign in
    if (!haOk() && usesHa()) loginMode = kid ? "none" : "pin";
    loginList.replaceChildren(...LOGIN_OPTS.filter(o => kid || o[0] !== "none").map(([k, icon, label, expl]) => {
      const off = (k === "ha" || k === "pin_ha") && !haOk();
      return h("label.login-opt" + (loginMode === k ? ".on" : "") + (off ? ".off" : ""),
        h("input", { type: "radio", name: "fq-login", value: k, checked: loginMode === k, disabled: off,
          onchange: () => { loginMode = k; drawLogin(); } }),
        h("span.login-ic", { "aria-hidden": "true" }, icon),
        h("span.login-txt", h("strong", label), h("span.small.muted", expl(kid))));
    }));
    loginHint.textContent = !haOk() ? I18N.tr(T("Home Assistant is not connected – the Home Assistant options need it.")) : "";
    loginHint.hidden = !loginHint.textContent;
    haPart.hidden = !usesHa();
    pinForm.hidden = !usesPin();
    drawPin();
  };
  // the dialog in parts (tabs): profile · learning · time & battery · internet & devices – Save / Cancel always at the bottom,
  // «Remove» set apart at the end of the profile tab
  const danger = !isNew && p.id !== P.meta.me.id ? h("div.danger-zone", h("h3", { "data-ik": "Remove profile" }, "⚠️ ", T("Remove profile")),
    h("p.small.muted", T("Archive the profile or delete it for good – you confirm it in the next step.")),
    h("button.btn.small.bad", { type: "button", onclick: remove }, "🗑 ", T("Remove"))) : null;
  const tabs = tabbed([
    { key: "profile", label: "👤 " + I18N.tr(T("Profile")), content: [
      h("div.grid2", h("label.field", T("Name"), f.name), h("label.field", T("Role"), f.role), h("label.field", T("Colour"), f.color)),
      loginForm,
      isNew ? null : h("div.form", h("h3", { "data-ik": "prof.avatar" }, "🧑‍🎨 ", T("Avatar")), avBox),
      persons.length ? h("label.field", h("span", T("Person in the Family Planer"), fieldInfo(T("Shows the chores of this person and counts them."))), f.planer) : null,
      parentPart, danger] },
    { key: "learn", label: "📚 " + I18N.tr(T("Learning")), content: [
      h("h3", { "data-ik": "prof.learn" }, "📚 ", T("Learning")),
      h("div.field-row", h("label.field", T("Daily goal (XP)"), f.daily_goal), h("label.field", T("Exercises per lesson"), f.lesson_length),
        h("label.field", T("New cards per lesson"), f.new_per_lesson),
        h("label.field", h("span", T("Learning hours"), fieldInfo(T("Empty = always. Example: 07:00-20:00"))), f.learning_hours),
        h("label.field", h("span", T("Log out after minutes without touch"), fieldInfo(T("0 = never"))), f.auto_logout_min))] },
    { key: "time", label: "⏱️ " + I18N.tr(T("Time & battery")), content: [timePart, batteryPart] },
    { key: "net", label: "🌐 " + I18N.tr(T("Internet & devices")), content: [kidPart, P.meta.ha ? h("div.form", h("h3", { "data-ik": "prof.devices" }, "🏠 ", T("Devices")), devBox) : null] },
  ]);
  const syncRole = () => {
    const kid = f.role.value === "kid";
    kidPart.hidden = timePart.hidden = !kid; if (batteryPart) batteryPart.hidden = !kid; parentPart.hidden = kid; syncHa(kid);
    tabs.setVisible("time", kid); tabs.setVisible("net", kid || !!P.meta.ha);
    drawLogin();
  };
  f.role.addEventListener("change", syncRole); syncRole();
  const m = modal(h("div.form.profile-dlg",
    h("h2", isNew ? (p.role === "parent" ? T("New parent") : T("New child")) : T("Edit profile")),
    tabs.el,
    h("div.dlg-foot", h("button.btn", { onclick: save }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
  const focusIn = el => { tabs.reveal(el); el.focus(); };
  async function save() {
    // the sign-in decides what is sent: the PIN only for the PIN options, the Home Assistant user only for the HA options
    let pin = null, pinSymbols;
    if (usesPin() && changing) {
      if (pinKind === "symbols") {
        const v = pad && pad.value();
        if (!v || v.symbols.length !== 4) { tabs.show("profile"); return toast(T("Choose 4 symbols"), "bad"); }
        pinSymbols = v;
      } else {
        pin = f.pin.value || null;
        if (!pin) { focusIn(f.pin); return toast(p.has_pin ? T("Enter the new digit PIN") : T("Set a PIN for this sign-in"), "bad"); }
      }
    }
    if (usesHa() && !haUser.value) { focusIn(haUser); return toast(T("Choose the Home Assistant user for this sign-in"), "bad"); }
    const isParent = f.role.value === "parent";
    const body = { name: f.name.value, role: f.role.value, color: f.color.value, pin, planer_person_id: f.planer.value || null, login: loginMode,
      ha_user_id: usesHa() ? haUser.value : "", ha_user_name: usesHa() ? haUser.selectedOptions[0]?.dataset.name || "" : "",
      ...(pinSymbols ? { pin_symbols: pinSymbols.symbols, symbol_set: pinSymbols.set } : {}),
      settings: { daily_goal: +f.daily_goal.value, lesson_length: +f.lesson_length.value, new_per_lesson: +f.new_per_lesson.value,
        learning_hours: f.learning_hours.value.trim(), auto_logout_min: +f.auto_logout_min.value, internet_entity: f.internet_entity.value,
        internet_daily_limit: +f.internet_daily_limit.value, notify_service: f.notify_service.value.trim(),
        internet_rule: f.internet_rule.value, internet_rule_blocks: f.internet_rule_blocks.checked, internet_plan: plan.value(),
        ...(isParent ? {} : { game_limit: gameLimit.value(), learn_limit: learnLimit.value() }),
        ...(P.meta.ha ? { devices: [...devSel] } : {}) } };
    const saved = await call(isNew ? "parent/profiles" : `parent/profiles/${p.id}`, { method: isNew ? "POST" : "PUT", body });
    if (saved && saved.parent_token) Auth.parent = saved.parent_token;
    if (avatar) await call(`parent/profiles/${p.id}/avatar`, { method: "PUT", body: { avatar } });
    m.close(); toast(T("Saved"), "good"); render();
  }
  function remove() { removeDialog(p, false, () => m.close()); }
}

// ---------------------------------------------------------------- packs
// a search that finds nothing: say so, with a link that clears the search
function noMatch(text, reset) {
  return h("p.muted.no-match", { hidden: true }, "🔍 ", text, " · ",
    h("a", { href: "#", onclick: e => { e.preventDefault(); reset(); } }, T("Reset search")));
}

// an open «⋯» menu closes with a tap anywhere else
document.addEventListener("click", e => document.querySelectorAll("details.more-menu[open]").forEach(d => { if (!d.contains(e.target)) d.open = false; }));

const LANG_FLAG = { de: "🇩🇪", en: "🇬🇧", fr: "🇫🇷", it: "🇮🇹", es: "🇪🇸", nl: "🇳🇱", pl: "🇵🇱", pt: "🇧🇷", sv: "🇸🇪" };
const LANG_NAME = { de: T("German"), en: T("English"), fr: T("French"), it: T("Italian"), es: T("Spanish"), nl: T("Dutch"), pl: T("Polish"), pt: T("Portuguese"), sv: T("Swedish") };

async function packsView(main) {
  const [d, profiles] = await Promise.all([call("parent/packs"), call("parent/profiles")]);
  const kids = profiles.filter(p => p.role === "kid");
  const drafts = d.packs.filter(p => p.status === "draft");
  const imported = p => !["builtin", "share"].includes(p.source);      // own packs: imported, made with the AI or edited – shown on top
  // «More packs»: optional packs of the app (e.g. German content only) – not installed until a parent adds them
  const available = d.packs.filter(p => p.status === "available");
  const shown = d.packs.filter(p => p.status !== "available");
  const importedPacks = shown.filter(p => p.status !== "draft" && imported(p));
  const bundles = shown.filter(p => p.kind === "bundle" && p.status !== "draft");
  const packs = shown.filter(p => p.kind === "pack" && p.status !== "draft");
  const actRow = p => h("div.act", ...kids.map(k => h("label.check", h("input", { type: "checkbox", checked: p.profiles.includes(k.id),
    onchange: async e => {
      try { await call("parent/packs/activate", { method: "POST", body: { profile_id: k.id, pack_id: p.id, on: e.target.checked } }); toast(T("Saved"), "good"); }
      catch { e.target.checked = !e.target.checked; return; }   // call() showed the error
      if (p.kind === "bundle") render();
    } }),
    C(k.name))));
  const byId = Object.fromEntries(d.packs.map(p => [p.id, p]));
  // «⋯»: the rarely used actions (export, delete) – the row keeps room for the title
  const moreMenu = p => h("details.more-menu",
    h("summary.btn.small.ghost", { title: T("More"), "aria-label": T("More") }, "⋯"),
    h("div.more-pop",
      h("button.btn.small.ghost", { title: T("Export as ZIP (with pictures)"), onclick: e => { e.target.closest("details").open = false; download(p.id, "zip"); } }, "⬇️ ", T("Export as ZIP (with pictures)")),
      h("button.btn.small.ghost", { onclick: e => { e.target.closest("details").open = false; download(p.id, "json"); } }, "⬇️ ", T("Export as JSON")),
      // an optional pack of the app goes back to «More packs» (deleting it would only bring it back at the next start)
      p.optional && !imported(p)
        ? h("button.btn.small.ghost", { onclick: e => { e.target.closest("details").open = false; uninstall(p); } }, "↩️ ", T("Remove from the family"))
        : h("button.btn.small.ghost.danger-text", { onclick: e => { e.target.closest("details").open = false; del(p); } }, "🗑️ ", T("Delete"))));
  // the language the content is written in (packs that do not follow the app language)
  const langNote = p => (p.content_langs || []).length ? h("span.chip.pack-lang", { title: T("The questions and answers of this pack are written in this language") },
    (p.content_langs || []).map(l => (LANG_FLAG[l] || "🗣️") + " ").join(""), I18N.tr(T("Content in {0}")).replace("{0}", p.content_langs.map(l => langInText(I18N.tr(LANG_NAME[l] || l))).join(", "))) : null;
  const card = p => h("div.card.pack" + (p.status === "draft" ? ".draft" : ""), { "data-find": [p.id, p.title, p.level, p.subject && I18N.tr(p.subject.name), ...(p.units || []).map(u => u.title)].filter(Boolean).join(" ") },
    h("div.row.pack-head", h("span.big-ic", p.kind === "bundle" ? "🎒" : (p.icon || "📚")), h("div.grow", C(p.title, "strong"),
      h("div.small.muted", p.kind === "bundle" ? T("Level pack") : subjectName(p.subject.key), p.level ? h("span", { translate: "no" }, " · " + p.level) : null, " · ",
        STATUS[p.status] || p.status, p.private ? " · 🔒 " + I18N.tr(T("private")) : ""), langNote(p)), moreMenu(p)),
    h("div.row.wrap.pack-acts",
      // a draft is checked, then published – the same two verbs as on the import page
      p.kind === "pack" ? h("button.btn.small.ghost", { onclick: () => packEditor(p.id) }, "✏️ ", p.status === "draft" ? T("Check") : T("Edit")) : null,
      p.kind === "pack" ? h("button.btn.small.ghost", { title: T("XP and coins per finished lesson of this pack"), onclick: () => packRewards(p) },
        "🏅 ", p.rewards && (p.rewards.xp != null || p.rewards.coins != null)
          ? [p.rewards.xp != null ? p.rewards.xp + " XP" : "", p.rewards.xp != null && p.rewards.coins != null ? " · " : "", p.rewards.coins != null ? p.rewards.coins + " 🪙" : ""]
          : T("Rewards")) : null,
      p.kind === "pack" ? h("button.btn.small.ghost", { title: T("Opens the pack in the app in a new tab – parents can try every pack"), onclick: () => openInApp("pack/" + encodeURIComponent(p.id)) }, "▶ ", T("Try in the app")) : null,
      p.status === "draft" ? h("button.btn.small.good", { onclick: () => setStatus(p.id, "active") }, "✓ ", T("Publish"))
        : h("button.btn.small.ghost", { onclick: () => setStatus(p.id, p.status === "active" ? "disabled" : "active") }, p.status === "active" ? T("Switch off") : T("Switch on"))),
    p.kind === "pack" ? h("div.small.units", ...p.units.map(u => chip([u.icon ? u.icon + " " : "", C(u.title), " · " + u.count]))) :
      // level pack: its packs by title (the internal ids mean nothing to parents)
      h("div.small", ...(p.semesters || []).map(s => h("div", C(s.titel || s.id, "strong"), ": ",
        C(s.pakete.map(id => byId[id] ? byId[id].title : id).join(", ") || "–")))),
    kids.length ? (p.status === "draft" ? h("div", h("div.small.muted", "👧 ", T("Assign now – the child sees it as soon as you publish it:")), actRow(p)) : actRow(p)) : null);
  // switch: sorted by packs (which children have a pack) or grouped by children (which packs a child has)
  let mode = "packs"; try { mode = localStorage.getItem("fq.packs.view") || "packs"; } catch {}
  if (!kids.length) mode = "packs";
  const seg = h("div.seg", { role: "radiogroup", "aria-label": T("Show") }, ...[["packs", "📚 ", T("By pack")], ["kids", "👧 ", T("By child")]].map(([k, ic, n]) =>
    h("button" + (mode === k ? ".on" : ""), { type: "button", role: "radio", "aria-checked": String(mode === k), disabled: k === "kids" && !kids.length,
      onclick: () => { try { localStorage.setItem("fq.packs.view", k); } catch {} render(); } }, ic, n)));
  const toggle = async (kid, pack, on) => {
    await call("parent/packs/activate", { method: "POST", body: { profile_id: kid.id, pack_id: pack.id, on } });
    render();
  };
  const byKid = () => kids.map(k => {
    const mine = [...bundles, ...packs].filter(p => p.profiles.includes(k.id));
    const others = [...bundles, ...packs].filter(p => !p.profiles.includes(k.id) && p.status === "active");
    const add = h("select", { onchange: () => { const p = others.find(x => x.id === add.value); if (p) toggle(k, p, true); } },
      h("option", { value: "" }, "＋ " + I18N.tr(T("Add pack …"))),
      ...others.map(p => h("option", { value: p.id, translate: "no" }, (p.kind === "bundle" ? "🎒 " : (p.icon || "📚") + " ") + p.title)));
    return h("section.card.sec.kid-packs",
      h("div.row", avatarSvg(k.avatar, 44), C(k.name, "h2.grow"), h("span.muted", I18N.tr(T("Packs: {0}")).replace("{0}", mine.length))),
      mine.length ? h("ul.pack-mini-list", ...mine.map(p => h("li.row.pack-mini" + (p.status !== "active" ? ".off" : ""),
        h("span.big-ic", p.kind === "bundle" ? "🎒" : (p.icon || "📚")),
        h("div.grow", C(p.title, "strong"), h("div.small.muted", p.kind === "bundle" ? T("Level pack") : subjectName(p.subject.key),
          p.level ? h("span", { translate: "no" }, " · " + p.level) : null, p.status !== "active" ? " · " + I18N.tr(STATUS[p.status] || p.status) : "")),
        h("button.btn.small.ghost", { title: T("Remove"), onclick: () => toggle(k, p, false) }, "✕")))) : h("p.muted", T("No packs yet.")),
      others.length ? add : null);
  });
  // search: filters the pack cards (title, subject, level, units, id) – remembered while the page is open
  const search = h("input.pack-search", { type: "search", placeholder: "🔍 " + I18N.tr(T("Search packs …")), value: P.packSearch || "",
    "aria-label": T("Search packs …"), oninput: () => { P.packSearch = search.value; filterPacks(); } });
  const noPacks = noMatch(T("No packs found"), () => { search.value = ""; P.packSearch = ""; filterPacks(); });
  const filterPacks = () => {
    const q = (search.value || "").trim().toLowerCase();
    const all = [...main.querySelectorAll(".card.pack, .pack-mini")];
    all.forEach(c => { c.hidden = !!q && !((c.dataset.find || c.textContent).toLowerCase().includes(q)); });
    noPacks.hidden = !q || all.some(c => !c.hidden);
    main.querySelectorAll("section.sec, section.card.sec").forEach(sec => {
      const cards = sec.querySelectorAll(".card.pack, .pack-mini");
      if (!cards.length) return;
      const fold = sec.closest("details.set-fold") || sec, hit = [...cards].some(c => !c.hidden);
      fold.hidden = !!q && !hit && !sec.classList.contains("kid-packs");
      if (q && hit && fold.tagName === "DETAILS") fold.open = true;          // a search opens the boxes with what it found
    });
  };
  setTimeout(filterPacks);
  main.append(pageHead(T("Learning packs"), seg,
    h("button.btn.ghost", { title: T("All packs in one JSON file"), onclick: () => download(null, "json") }, "⬇️ ", T("Export all")),
    h("button.btn", { onclick: () => { P.tab = "import"; render(); } }, "📥 ", T("Import"))));
  main.append(search, noPacks);
  // 💡 Code Workshop (codelab.js): only in the dev channel (channel.DEV_FEATURES)
  const codeSec = P.info && P.info.codelab ? await codelabSection().catch(e => section("💡 " + I18N.tr(T("Code Workshop")), h("p.bad", e.message))) : null;
  const german = String(I18N.lang || "").startsWith("de");
  const more = moreSection(german);
  // every box folded like the settings (the grouping stays): its title and how many packs it holds in the row
  const packCount = sec => sec.classList.contains("kid-packs") ? "" : I18N.tr(T("Packs: {0}")).replace("{0}", sec.querySelectorAll(".card.pack").length);
  const kidStatus = sec => { const r = sec.querySelector(":scope > .row > span.muted"); return r ? r.textContent : ""; };
  if (mode === "kids") {
    main.append(...byKid(), drafts.length ? section("📝 " + I18N.tr(T("To check")), ...drafts.map(card)) : null, codeSec, more);
    return foldBoxes(main, "packs", sec => kidStatus(sec) || packCount(sec));
  }
  const levelPacks = bundles.filter(p => !imported(p)), ownPacks = packs.filter(p => !imported(p));
  main.append(
    german ? more : null,
    drafts.length ? section("📝 " + I18N.tr(T("Imported as draft – to check")), ...drafts.map(card)) : null,
    importedPacks.length ? section("⭐ " + I18N.tr(T("Own packs")), ...importedPacks.map(card)) : null,
    levelPacks.length ? section("🎒 " + I18N.tr(T("Level packs")), ...levelPacks.map(card)) : null,
    ownPacks.length ? section("📚 " + I18N.tr(T("Packs")), ...ownPacks.map(card)) : null, codeSec, german ? null : more);
  foldBoxes(main, "packs", sec => sec.querySelector(".cw-pk, table") && !sec.querySelector(".card.pack") ? "" : packCount(sec));
  // ➕ More packs: optional packs of the app, added with one click (then switched on per child as every other pack)
  function moreSection(top) {
    if (!available.length) return null;
    const de = available.filter(p => (p.content_langs || []).includes("de"));
    const avCard = p => h("div.card.pack.pack-avail", { "data-find": [p.id, p.title, p.level, p.subject && I18N.tr(p.subject.name), ...(p.units || []).map(u => u.title)].filter(Boolean).join(" ") },
      h("div.row.pack-head", h("span.big-ic", p.kind === "bundle" ? "🎒" : (p.icon || "📚")), h("div.grow", C(p.title, "strong"),
        h("div.small.muted", p.kind === "bundle" ? T("Level pack") : subjectName(p.subject.key), p.level ? h("span", { translate: "no" }, " · " + p.level) : null), langNote(p)),
        h("button.btn.small.good", { onclick: () => install([p.id]) }, "＋ ", T("Add"))),
      p.description ? C(p.description, "p.small.muted") : null,
      p.kind === "pack" ? h("div.small.units", ...p.units.map(u => chip([u.icon ? u.icon + " " : "", C(u.title), " · " + u.count]))) :
        h("div.small", ...(p.semesters || []).map(s => h("div", C(s.titel || s.id, "strong"), ": ",
          C(s.pakete.map(id => byId[id] ? byId[id].title : id).join(", ") || "–")))));
    return section("➕ " + I18N.tr(T("More packs")),
      de.length > 1 ? h("button.btn", { onclick: () => install(de.map(p => p.id)) }, "🇩🇪 ", T("Add all German-language packs")) : null,
      ...available.map(avCard));
  }
  async function install(ids) {
    try { await call("parent/packs/install", { method: "POST", body: { ids, on: true } }); toast(T("Added"), "good"); } catch { return; }
    render();
  }
  async function uninstall(p) {
    if (!(await confirmDialog(I18N.tr(T("Remove {0} from the family? It is switched off for every child and goes back to «More packs». The learning progress is kept.")).replace("{0}", p.title)))) return;
    try { await call("parent/packs/install", { method: "POST", body: { ids: [p.id], on: false } }); } catch { return; }
    render();
  }
  function packRewards(p) {
    const r = p.rewards || {};
    const xp = h("input", { type: "number", min: 0, max: 10000, value: r.xp ?? "", placeholder: "–", inputmode: "numeric" });
    const coins = h("input", { type: "number", min: 0, max: 10000, value: r.coins ?? "", placeholder: "–", inputmode: "numeric" });
    const num = el => el.value === "" ? null : Math.max(0, parseInt(el.value, 10) || 0);
    const save = async () => {
      try { await call(`parent/packs/${encodeURIComponent(p.id)}/rewards`, { method: "POST", body: { xp: num(xp), coins: num(coins) } }); m.close(); toast(T("Saved"), "good"); render(); }
      catch (e) { toast(e.message, "bad"); }
    };
    const m = modal(h("div.form", h("h2", "🏅 ", C(p.title), fieldInfo(T("What a finished lesson of this pack gives. Empty: the family rule (Rewards › Rules «Lesson finished»). The daily limit of the rule still applies."))),
      // both numbers side by side, the icon inline in the label; empty = the family rule, «Reset» empties both
      h("div.reward-nums", h("label.field", { title: T("XP per finished lesson") }, h("span", "⭐ XP"), xp),
        h("label.field", { title: T("Coins per finished lesson") }, h("span", "🪙 ", T("Coins")), coins)),
      h("p.small.muted", T("Empty = family rule"), " · ", h("a", { href: "#", onclick: e => { e.preventDefault(); xp.value = ""; coins.value = ""; } }, T("Reset"))),
      h("div.row", h("button.btn", { onclick: save }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  }
  async function setStatus(id, status) { await call(`parent/packs/${encodeURIComponent(id)}/status`, { method: "POST", body: { status } }); render(); }
  async function del(p) { if (!(await confirmDialog(I18N.tr(T("Delete {0}? Learning progress for it is lost.")).replace("{0}", p.title)))) return; await call(`parent/packs/${encodeURIComponent(p.id)}`, { method: "DELETE" }); render(); }
}

// 💡 Code Workshop (familyquest/codelab.py): on / off per child, puzzle rewards, the progress of every child, the programs
// the family shares (open in the app, remove) – of private programs only that they exist
async function codelabSection() {
  const d = await call("codelab/overview");
  const s = d.settings;
  const on = d.kids.map(k => [k.id, h("input", { type: "checkbox", checked: !s.off.includes(k.id) })]);
  const num = v => h("input", { type: "number", min: 0, max: 10000, value: v, inputmode: "numeric" });
  const xp = num(s.level_xp), coins = num(s.level_coins);
  const save = async () => {
    const body = { off: on.filter(([, c]) => !c.checked).map(([id]) => id), level_xp: Math.max(0, Math.round(+xp.value || 0)), level_coins: Math.max(0, Math.round(+coins.value || 0)) };
    try { await call("codelab/settings", { method: "PUT", body }); toast(T("Saved"), "good"); } catch {}
  };
  const worlds = [...new Set(d.levels.map(l => l.world))];
  const kidRow = k => h("tr", h("td", h("div.row.cw-pk", avatarSvg(k.avatar, 30), C(k.name, "strong"))),
    h("td", { translate: "no" }, k.solved + " / " + d.total), h("td", { translate: "no" }, "⭐ " + k.stars),
    ...worlds.map(w => h("td.cw-pw", { translate: "no" }, d.levels.filter(l => l.world === w).map(l => k.levels[l.id] ? "★".repeat(k.levels[l.id]) : "·").join(" "))));
  const proj = d.projects;
  const shared = [...proj.mine, ...proj.others];
  const remove = async p => {
    if (!(await confirmDialog(I18N.tr(T("Remove the program «{0}»?")).replace("{0}", p.title)))) return;
    try { await call("codelab/projects/" + p.id, { method: "DELETE" }); render(); } catch {}
  };
  const VIS = { me: "🔒", kids: "🧒", family: "👨‍👩‍👧" };
  return section("💡 " + I18N.tr(T("Code Workshop")),
    h("div.field", h("b", T("Code Workshop for")), d.kids.length ? h("div.row.wrap", ...on.map(([id, c]) => h("label.check", c, " ", C(d.kids.find(k => k.id === id).name)))) : h("span.small.muted", T("No child profile yet"))),
    h("div.sb-rew", h("b", T("Reward for the first solve of a puzzle level")),
      h("label.field", h("span", "⭐ XP"), xp), h("label.field", h("span", "🪙 ", T("Coins")), coins)),
    h("button.btn", { onclick: save }, "💾 ", T("Save")),
    d.kids.length ? h("div.cw-ptable", h("h3", "🧩 ", T("Puzzle progress")), h("div.tbl-wrap", h("table.tbl",
      h("thead", h("tr", h("th", T("Child")), h("th", T("Levels")), h("th", "⭐"), ...worlds.map(w => h("th", { translate: "no" }, "#" + w)))),
      h("tbody", ...d.kids.map(kidRow))))) : null,
    h("h3", "🎨 ", T("Programs of the family")),
    shared.length ? h("ul.cw-plist-p", ...shared.map(p => h("li.row",
      h("span", VIS[p.visibility] || ""), h("div.grow", C(p.title, "strong"), h("div.small.muted", C(p.author.name), " · 🧱 " + p.blocks + " · " + fmtDate(p.updated_at))),
      h("button.btn.small.ghost", { onclick: () => openInApp("codelab/play/" + p.id) }, "▶ ", T("Open in the app")),
      h("button.btn.small.ghost", { "aria-label": T("Remove"), onclick: () => remove(p) }, "🗑️")))) : h("p.small.muted", T("No shared programs yet.")),
    proj.private.length ? h("div", h("p.small.muted", "🔒 ", T("Private programs – only the child can open them:")),
      h("ul.cw-plist-p", ...proj.private.map(p => h("li.row.small", h("span", "🔒"), C(p.author.name, "strong"), h("span.muted", " · 🧱 " + p.blocks + " · " + fmtDate(p.updated_at)))))) : null);
}

async function download(id, format = "zip") {
  const path = id ? `api/parent/packs/${encodeURIComponent(id)}/export?format=${format}` : "api/parent/packs/export";
  const r = await fetch(path, { headers: { "X-FQ-Parent": Auth.parent } });
  if (!r.ok) return toast(T("Export failed"), "bad");
  const url = URL.createObjectURL(await r.blob());
  const a = h("a", { href: url, download: (id || "family-quest-packs") + "." + format }); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// Phone photos are large: scale down to max. 1024 px as JPEG before uploading.
// photos made smaller (and turned into JPEG) in the browser before the upload – also iPhone photos (HEIC), which Safari can read
async function shrinkPhoto(file, max = 1024, { short = false } = {}) {
  if (file.type === "image/gif") return file;                       // keep animations
  const heic = /hei[cf]$/i.test(file.type) || /\.hei[cf]$/i.test(file.name || "");
  if (!/^image\//.test(file.type) && !heic) return file;
  const decode = async () => {
    try { return await createImageBitmap(file); } catch {}
    const url = URL.createObjectURL(file);                          // fallback: some browsers only decode through <img>
    try { const img = new Image(); img.src = url; await img.decode(); return img; } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
  };
  try {
    const bmp = await decode();
    const w0 = bmp.width || bmp.naturalWidth, h0 = bmp.height || bmp.naturalHeight;
    const k = Math.min(1, max / (short ? Math.min(w0, h0) : Math.max(w0, h0)));   // short: the shorter edge counts
    const cv = h("canvas", { width: Math.round(w0 * k), height: Math.round(h0 * k) });
    cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
    const alpha = /^image\/(png|webp)$/.test(file.type);          // keep transparency (a drawn crest) – photos become JPEG
    return await new Promise(res => cv.toBlob(b => res(b || file), alpha ? "image/png" : "image/jpeg", 0.85));
  } catch {
    if (heic) throw new Error(I18N.tr(T("This photo format cannot be read – please use JPEG or PNG.")));
    return file;
  }
}

async function packEditor(id, { afterSave } = {}) {
  const d = await call(`parent/packs/${encodeURIComponent(id)}/raw`);
  const pack = d.data;
  let mode = "cards";
  const body = h("div");
  const yamlBox = h("textarea.yaml", { spellcheck: false, rows: 24 });
  const subjects = P.meta.subjects;
  const metaF = {
    titel: h("input", { type: "text", value: pack.titel || "" }),
    fach: h("select", ...subjects.map(s => h("option", { value: s.key, selected: s.key === pack.fach }, s.icon + " " + I18N.tr(s.name)))),
    stufe: h("input", { type: "text", value: pack.stufe || "" }),
    sprache: h("input", { type: "text", value: pack.sprache || "", placeholder: "fr / en / it" }),
    pfad: h("input", { type: "checkbox", checked: pack.pfad === true }),
    privat: h("input", { type: "checkbox", checked: !!pack.privat }),
  };
  if (!subjects.some(s => s.key === pack.fach)) metaF.fach.append(h("option", { value: pack.fach, selected: true }, pack.fach));
  const src = pack.quellsprache || "de", tgt = pack.sprache || "";
  const promptOf = c => c.frage ?? c[src] ?? "", answerOf = c => c.antwort ?? (tgt ? c[tgt] : undefined) ?? "";
  const drawCards = () => {
    body.replaceChildren(
      h("div.grid3", h("label.field", T("Title"), metaF.titel), h("label.field", T("Subject"), metaF.fach), h("label.field", T("Level"), metaF.stufe),
        h("label.field", T("Language learnt"), metaF.sprache), h("label.check", metaF.pfad, T("Units unlock one after the other")),
        h("label.check", metaF.privat, T("Private (from school material, never share)"))),
      ...(pack.einheiten || []).map((u, ui) => unitEditor(u, ui)),
      h("button.btn.ghost", { onclick: () => { pack.einheiten.push({ id: "einheit-" + (pack.einheiten.length + 1), titel: I18N.tr(T("New unit")), karten: [{ frage: "", antwort: "" }] }); drawCards(); } }, "+ ", T("Add unit")));
  };
  function unitEditor(u, ui) {
    if (u.generator) return h("div.unit-ed", h("h3", u.icon || "🧮", " ", C(u.titel || u.id)), h("p.small.muted", T("Generator"), ": ", u.generator, " ", C(JSON.stringify(u.parameter || {}))));
    const rows = h("tbody");
    const draw = () => rows.replaceChildren(...u.karten.map((c, i) => h("tr",
      h("td", h("input", { type: "text", value: promptOf(c), "aria-label": T("Question"), oninput: e => { c.frage = e.target.value; delete c[src]; } })),
      h("td", h("input", { type: "text", value: answerOf(c), "aria-label": T("Answer"), oninput: e => { c.antwort = e.target.value; if (tgt) delete c[tgt]; } })),
      h("td.narrow", h("input", { type: "text", value: c.emoji || "", "aria-label": "Emoji", oninput: e => { c.emoji = e.target.value || undefined; } })),
      h("td.narrow", photoCell(c, draw)),
      h("td", h("input", { type: "text", value: c.satz || "", placeholder: "… ___ …", "aria-label": T("Sentence with gap"), oninput: e => { c.satz = e.target.value || undefined; } })),
      h("td", h("input", { type: "text", value: (c.optionen || []).join(" | "), placeholder: "a | b | c", "aria-label": T("Wrong options"), oninput: e => { c.optionen = e.target.value ? e.target.value.split("|").map(x => x.trim()).filter(Boolean) : undefined; } })),
      h("td.narrow", h("button.icon-btn", { title: T("Delete"), onclick: () => { u.karten.splice(i, 1); draw(); } }, "✕")))));
    draw();
    const ex = h("div.row.small", ...Object.entries(EXERCISES).map(([k, n]) => h("label.check", h("input", { type: "checkbox", checked: (u.uebungen || []).includes(k),
      onchange: e => { u.uebungen = u.uebungen || []; if (e.target.checked) u.uebungen.push(k); else u.uebungen = u.uebungen.filter(x => x !== k); } }), n)));
    return h("div.unit-ed",
      h("div.row", h("input.unit-title", { type: "text", value: u.titel || "", "aria-label": T("Unit title"), oninput: e => { u.titel = e.target.value; } }),
        h("button.btn.small.ghost", { onclick: () => { pack.einheiten.splice(ui, 1); drawCards(); } }, "🗑️ ", T("Remove unit"))),
      ex,
      h("table.tbl.cards-tbl", h("thead", h("tr", h("th", T("Question")), h("th", T("Answer")), h("th", "Emoji"), h("th", T("Photo")), h("th", T("Sentence with gap")), h("th", T("Wrong options")), h("th"))), rows),
      h("div.row", h("button.btn.small.ghost", { onclick: () => { u.karten.push({ frage: "", antwort: "" }); draw(); } }, "+ ", T("Add card")),
        h("button.btn.small.ghost", { onclick: () => pickPhotos(true, async files => {
          for (const f of files) { const n = await uploadPhoto(f); if (n) u.karten.push({ bild: n, antwort: "" }); }
          draw();
        }) }, "📷 ", T("Add photos as cards")),
        fieldInfo(T("Own photos: one card per photo – write the answer (e.g. the name) next to it. Shown in «Pairs», quiz and flash cards."), { title: T("Add photos as cards") })));
  }
  function pickPhotos(multiple, cb) { pickFiles({ accept: "image/*", multiple }, cb); }
  async function uploadPhoto(file) {
    try {
      const blob = await shrinkPhoto(file);
      const fd = new FormData(); fd.append("file", blob, "foto.jpg");
      const r = await call(`parent/packs/${encodeURIComponent(id)}/media`, { method: "POST", form: fd });
      return r.name;
    } catch { return null; }
  }
  function photoCell(c, redraw) {
    const set = n => { c.bild = n || undefined; redraw(); };
    if (c.bild) return h("div.photo-cell",
      h("img.card-thumb", { src: /^(https?:|data:)/.test(c.bild) ? c.bild : `media/${encodeURIComponent(id)}/${encodeURIComponent(c.bild)}`, alt: "" }),
      h("button.icon-btn", { title: T("Remove photo"), onclick: () => set(null) }, "✕"));
    return h("button.icon-btn", { title: T("Upload photo"), onclick: () => pickPhotos(false, async ([f]) => set(await uploadPhoto(f))) }, "📷");
  }
  const tabs = h("div.row.tabs",
    h("button.btn.small" + (mode === "cards" ? "" : ".ghost"), { onclick: () => { mode = "cards"; syncFromYaml(); drawCards(); tabsRedraw(); } }, T("Cards")),
    h("button.btn.small.ghost", { onclick: () => { mode = "yaml"; collectMeta(); yamlBox.value = toYaml(); body.replaceChildren(yamlBox); tabsRedraw(); } }, "YAML"));
  const tabsRedraw = () => { const [a, b] = tabs.children; a.className = "btn small" + (mode === "cards" ? "" : " ghost"); b.className = "btn small" + (mode === "yaml" ? "" : " ghost"); };
  function collectMeta() {
    pack.titel = metaF.titel.value; pack.fach = metaF.fach.value; pack.stufe = metaF.stufe.value; pack.sprache = metaF.sprache.value;
    pack.pfad = metaF.pfad.checked; pack.privat = metaF.privat.checked;
  }
  const toYaml = () => JSON.stringify(pack, null, 2);   // JSON is valid YAML – the server stores either
  function syncFromYaml() { if (mode === "yaml") try { Object.assign(pack, JSON.parse(yamlBox.value)); } catch {} }
  drawCards();
  const m = modal(h("div.form", h("div.row", h("h2.grow", T("Edit pack")), tabs), d.summary && d.summary.status === "draft" ? h("p.small.warn-text", T("This is a draft – check every card, then publish it.")) : null,
    body,
    h("div.row.sticky-actions", h("button.btn", { onclick: save }, "💾 ", T("Save")),
      d.summary && d.summary.status === "draft" ? h("button.btn.good", { onclick: () => save(true) }, "✓ ", T("Save and publish")) : null,
      h("button.btn.ghost", { onclick: () => m.close() }, T("Close")))), { wide: true });
  async function save(publish) {
    let payload;
    if (mode === "yaml") payload = { yaml: yamlBox.value };
    else {
      collectMeta();
      for (const u of pack.einheiten || []) if (u.karten) u.karten = u.karten.filter(c => (c.frage ?? c[src]) || (c.antwort ?? c[tgt]) || c.bild);
      payload = { data: JSON.parse(JSON.stringify(pack)) };
    }
    await call(`parent/packs/${encodeURIComponent(id)}/raw`, { method: "PUT", body: payload });
    if (publish) await call(`parent/packs/${encodeURIComponent(id)}/status`, { method: "POST", body: { status: "active" } });
    toast(T("Saved"), "good"); m.close(); afterSave ? afterSave() : render();
  }
}

// ---------------------------------------------------------------- import
async function importView(main) {
  const file = h("input", { type: "file", accept: ".yaml,.yml,.json,.zip,.csv,.tsv,.xlsx" + (P.meta.ai ? ",.pdf,.png,.jpg,.jpeg,.webp" : "") });
  const paste = h("textarea.ai-paste", { rows: 6, placeholder: "{ … }", spellcheck: false });
  const out = h("div");
  const drop = h("label.drop", file, h("span.big-ic", "📄"), h("strong", T("Choose or drop a file")),
    h("span.small.muted", P.meta.ai ? T("YAML, JSON, ZIP, CSV, Excel, PDF or photo") : T("YAML, JSON, ZIP, CSV or Excel")));
  ["dragover", "dragenter"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, () => drop.classList.remove("over")));
  drop.addEventListener("drop", e => { e.preventDefault(); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); });
  file.addEventListener("change", () => file.files[0] && upload(file.files[0]));
  main.append(pageHead(T("Import"), h("button.btn.ghost", { onclick: () => { P.tab = "packs"; location.hash = "packs"; render(); } }, "← ", T("Learning packs"))),
    out,                                        // the imported drafts: on top, right where you look after the upload
    section(T("From a file"), drop,
      P.meta.ai ? null : h("p.small.muted", "📸 ", T("Photo/PDF import: set up an AI in Home Assistant (Settings › Devices & services › AI Task, e.g. OpenAI, Google, Anthropic or a local Ollama)."))),
    section("🤖 " + I18N.tr(T("Made with your AI")),
      aiPromptBox(T("Make me a learning pack for Family Quest.\nSubject: [e.g. French vocabulary]\nSchool year: [e.g. 5th grade]\nTopic or textbook unit: [e.g. unit 3 – at school]\nAbout [20] cards, my child speaks [English]."),
        { template: "api/ai-template/pack", name: "family-quest-pack-template.json" }),
      // the answer of the AI pasted right here – no file needed (like the import of the library)
      h("label.field", T("Paste the answer of the AI here …"), paste),
      h("div.row", h("button.btn", { onclick: importPaste }, "📥 ", T("Import")))));
  async function importPaste() {
    const t = paste.value.trim();                 // text or ``` fences around the JSON: the import reads past them
    if (!t) { paste.focus(); return toast(T("Paste the answer of the AI first"), "bad"); }
    await upload(new File([t], "ai-answer.json", { type: "application/json" }));
  }
  async function upload(f) {
    const fd = new FormData(); fd.append("file", f);
    out.replaceChildren(h("p", "⏳ ", T("Reading…")));
    let r;
    try { r = await call("parent/import/file", { method: "POST", form: fd }); } catch { out.replaceChildren(); return; }
    if (r.table) return tableMapping(r.table, out);
    showDrafts(r.drafts, out);
  }
}

async function showDrafts(drafts, out) {
  setTimeout(() => out.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  let kids = [];
  try { kids = (await call("parent/profiles")).filter(p => p.role === "kid"); } catch {}
  const assign = d => kids.length ? h("div.act.draft-assign", h("span.small.muted", "👧 ", T("For:")), ...kids.map(k => h("label.check",
    h("input", { type: "checkbox", onchange: async e => { try { await call("parent/packs/activate", { method: "POST", body: { profile_id: k.id, pack_id: d.id, on: e.target.checked } }); toast(T("Saved"), "good"); } catch (err) { toast(err.message, "bad"); } } }),
    C(k.name)))) : null;
  out.replaceChildren(section("✓ " + I18N.tr(T("Imported as draft")), ...drafts.map(d => h("div.draft-box", h("div.row.draft-row",
    h("span.big-ic", d.kind === "bundle" ? "🎒" : (d.icon || "📚")), h("div.grow", C(d.title, "strong"),
      h("div.small.muted", d.units ? d.units.map(u => u.title + " (" + u.count + ")").join(", ") : ""),
      d.replaces ? h("div.small.warn-text", T("Replaces the existing pack with the same id.")) : null,
      d.uncertain && d.uncertain.length ? h("div.small.warn-text", T("Not readable for sure:"), " ", C(d.uncertain.join(", "))) : null),
    d.kind !== "bundle" ? h("button.btn.small", { onclick: () => packEditor(d.id, { afterSave: () => { P.tab = "packs"; render(); } }) }, "✏️ ", T("Check")) : null,
    h("button.btn.small.good", { onclick: async () => { await call(`parent/packs/${encodeURIComponent(d.id)}/status`, { method: "POST", body: { status: "active" } }); toast(T("Published"), "good"); P.tab = "packs"; render(); } }, "✓ ", T("Publish"))),
    assign(d)))));
}

function tableMapping(t, out) {
  const opt = (sel) => h("select", h("option", { value: "" }, "–"), ...t.header.map((c, i) => h("option", { value: i, selected: sel === i }, c)));
  const cols = { prompt: opt(t.columns.prompt), answer: opt(t.columns.answer), unit: opt(t.columns.unit), image: opt(t.columns.image),
    sentence: opt(t.columns.sentence), hint: opt(t.columns.hint), also: opt(t.columns.also) };
  const meta = {
    titel: h("input", { type: "text", value: t.meta.titel }),
    fach: h("select", ...P.meta.subjects.map(s => h("option", { value: s.key, selected: s.key === t.meta.fach }, s.icon + " " + I18N.tr(s.name)))),
    stufe: h("input", { type: "text", value: t.meta.stufe }),
    sprache: h("input", { type: "text", value: t.meta.sprache, placeholder: "fr / en / it" }),
    privat: h("input", { type: "checkbox", checked: true }),
  };
  out.replaceChildren(section(T("Assign the columns"),
    h("p.small.muted", I18N.tr(T("{0} rows found.")).replace("{0}", t.count)),
    h("div.scroll", h("table.tbl", h("thead", h("tr", ...t.header.map(c => h("th", C(c))))), h("tbody", ...t.preview.map(r => h("tr", ...r.map(c => h("td", C(c)))))))),
    h("div.grid3",
      h("label.field", T("Question (what the child sees)"), cols.prompt), h("label.field", T("Answer"), cols.answer),
      h("label.field", T("Unit (optional)"), cols.unit), h("label.field", T("Picture or emoji (optional)"), cols.image),
      h("label.field", T("Sentence with gap (optional)"), cols.sentence), h("label.field", T("Hint (optional)"), cols.hint),
      h("label.field", T("Also correct (optional, separated by |)"), cols.also)),
    h("h3", T("Pack")),
    h("div.grid3", h("label.field", T("Title"), meta.titel), h("label.field", T("Subject"), meta.fach), h("label.field", T("Level"), meta.stufe),
      h("label.field", T("Language learnt"), meta.sprache), h("label.check", meta.privat, T("Private (from school material, never share)"))),
    h("div.row", h("button.btn", { onclick: build }, T("Create draft")),
      h("button.btn.ghost", { onclick: () => out.replaceChildren() }, T("Cancel")))));
  async function build() {
    const c = {}; for (const [k, s] of Object.entries(cols)) if (s.value !== "") c[k] = +s.value;
    const m = { titel: meta.titel.value, fach: meta.fach.value, stufe: meta.stufe.value, sprache: meta.sprache.value, privat: meta.privat.checked };
    const r = await call("parent/import/table", { method: "POST", body: { upload_id: t.upload_id, meta: m, columns: c } });
    showDrafts(r.drafts, out);
  }
}

// ---------------------------------------------------------------- chore plan (Ämtliplan)
const WEEKDAYS = [T("Mon"), T("Tue"), T("Wed"), T("Thu"), T("Fri"), T("Sat"), T("Sun")];
const FREQ = { daily: T("every day"), weekdays: T("on certain weekdays"), weekly: T("once a week"), once: T("once") };

function choreConfirmList(list, after) {
  return h("ul.list", ...list.map(t => h("li.row",
    h("span.big-ic", t.icon), h("span.grow", C(t.profile_name, "strong"), " – ", C(t.name), h("span.small.muted", " · +" + fmt(t.points))),
    h("button.btn.small.good", { onclick: () => decideChore(t.id, true) }, "✓ ", T("OK")),
    h("button.btn.small.ghost", { onclick: () => decideChore(t.id, false) }, "↻ ", T("Once more")))));
  async function decideChore(id, ok) {
    await call(`parent/chores/tasks/${id}`, { method: "POST", body: { ok } });
    toast(ok ? T("Confirmed – points booked") : T("Back to open"), "good");
    after();
  }
}

// ---------------------------------------------------------------- behaviour weather
const WEATHER_NAMES = [T("Sunny"), T("Cloudy"), T("Rain"), T("Thunderstorm")];   // default names (translated)
const WEATHER_ICONS = ["☀️", "🌤️", "⛅", "🌥️", "☁️", "🌦️", "🌧️", "⛈️", "🌩️", "🌨️", "❄️", "🌪️", "🌫️", "🌈", "🌙", "⭐"];
const wName = n => n ? I18N.tr(n) : "";
function weatherColor(rank, n) {
  const pal = ["#f7b801", "#9bc53d", "#adb5bd", "#4d96ff", "#6c4ab6", "#c1121f"];
  return pal[Math.round(rank / Math.max(1, n - 1) * (pal.length - 1))];
}
function weatherGraph(days, n) {
  const W = 300, H = 46, bw = W / days.length;
  const svg = (t, a, ...c) => { const e = document.createElementNS("http://www.w3.org/2000/svg", t); for (const k in a) e.setAttribute(k, a[k]); e.append(...c); return e; };
  const bars = days.map((d, i) => {
    const x = i * bw + 1, w = Math.max(2, bw - 2);
    const title = svg("title", {}, new Date(d.date).toLocaleDateString(I18N.locale, { weekday: "short", day: "numeric", month: "short" }) + (d.icon ? " " + d.icon : " –"));
    if (d.rank == null) return svg("rect", { x, y: H - 3, width: w, height: 3, rx: 1, fill: "currentColor", opacity: .18 }, title);
    const hh = 6 + (H - 8) * (n - 1 - Math.min(d.rank, n - 1)) / Math.max(1, n - 1);
    return svg("rect", { x, y: H - hh, width: w, height: hh, rx: 2, fill: weatherColor(Math.min(d.rank, n - 1), n) }, title);
  });
  return svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "weather-graph", preserveAspectRatio: "none", role: "img", "aria-label": I18N.tr(T("Weather of the last 30 days")) }, ...bars);
}

/** Behaviour weather: part "set" (today's weather per child – in the overview) or "config" (in the settings). */
async function weatherView(main, part = "both") {
  const d = await call("parent/weather");
  if (!P.accounts.length) P.accounts = await call("parent/accounts");
  const cfg = d.config, n = cfg.levels.length;
  const list = section("⛅ " + I18N.tr(T("Weather of the day")),
    h("p.muted", I18N.tr(T("Everybody is back at {0} at {1}.")).replace("{0}", cfg.levels.find(l => l.key === cfg.default)?.icon || "").replace("{1}", cfg.reset)),
    !cfg.enabled ? h("p.bad", T("The weather is switched off.")) : null,
    !d.kids.length ? h("p.muted", T("No children yet.")) : null,
    h("ul.weather-list", ...d.kids.map(k => {
      const li = h("li.weather-row");
      const draw = (cur, days) => {
        const counts = {};
        days.forEach(x => { if (x.icon) counts[x.icon] = (counts[x.icon] || 0) + 1; });
        li.replaceChildren(
          h("div.row.weather-who", avatarSvg(k.profile.avatar, 44), C(k.profile.name, "strong.grow"),
            cur ? h("span.weather-now", { title: wName(cur.name) }, cur.icon) : null),
          h("div.weather-btns", ...cfg.levels.map(l => h("button.btn.small" + (cur && cur.key === l.key ? ".on" : ".ghost"), {
            disabled: !cfg.enabled, title: wName(l.name),
            onclick: async () => {
              try {
                const r = await call(`parent/weather/${k.profile.id}`, { method: "POST", body: { level: l.key } });
                toast(l.icon + " " + k.profile.name + (l.points ? " · " + (l.points > 0 ? "+" : "") + fmt(l.points) : ""), l.points < 0 ? "" : "good");
                draw(r.current, r.days);
              } catch (e) { toast(e.message, "bad"); }
            } }, h("span.big-ic", l.icon), l.points ? h("span.small", (l.points > 0 ? " +" : " ") + fmt(l.points)) : null))),
          h("div.weather-hist", weatherGraph(days, n),
            h("div.small.muted.row", h("span.grow", T("Last 30 days")),
              ...cfg.levels.filter(l => counts[l.icon]).map(l => h("span", l.icon + " " + counts[l.icon])))));
      };
      draw(k.current, k.days);
      return li;
    })));

  // ---- configuration
  let lastIcon = null;
  const rows = h("div.weather-cfg");
  const addRow = l => {
    const icon = h("input.weather-icon", { type: "text", value: l.icon || "", maxlength: 8, onfocus: () => { lastIcon = icon; } });
    const name = h("input.grow", { type: "text", value: wName(l.name), placeholder: I18N.tr(T("Name")) });
    const pts = h("input", { type: "number", step: "1", value: l.points ?? 0 });
    const row = h("div.row.weather-cfg-row", icon, name, pts, h("span.small.muted", T("points")),
      h("button.icon-btn", { title: T("Up"), onclick: () => row.previousElementSibling && rows.insertBefore(row, row.previousElementSibling) }, "▲"),
      h("button.icon-btn", { title: T("Delete"), onclick: () => row.remove() }, "🗑"));
    row.read = () => ({ key: l.key, icon: icon.value.trim(), points: Number(pts.value || 0),
      // keep the English source name when the parent did not change the translated one – it stays translated
      name: name.value.trim() === wName(l.name) ? l.name : name.value.trim() });
    rows.append(row);
    if (!l.icon) lastIcon = icon;
  };
  cfg.levels.forEach(addRow);
  const palette = h("div.row.weather-palette", ...WEATHER_ICONS.map(ic => h("button.icon-btn", { onclick: () => { if (lastIcon) lastIcon.value = ic; } }, ic)));
  const def = h("select", ...cfg.levels.map(l => h("option", { value: l.key, selected: l.key === cfg.default }, l.icon + " " + wName(l.name))));
  const time = h("input", { type: "time", value: cfg.reset });
  const acc = h("select", ...P.accounts.filter(a => a.active && a.key !== "xp").map(a => h("option", { value: a.key, selected: a.key === cfg.account }, a.icon + " " + I18N.tr(a.name))));
  const on = h("input", { type: "checkbox", checked: cfg.enabled });
  const conf = section("☀️ " + I18N.tr(T("Bonus/malus points")),
    rows, h("div.row", h("button.btn.small.ghost", { onclick: () => addRow({ icon: "", name: "", points: 0 }) }, "＋ ", T("Add weather"))),
    h("div.small.muted", T("Tap a symbol to put it into the field you edited last:")), palette,
    h("div.grid3", h("label.field", h("span", T("Reset every day at")), time),
      h("label.field", h("span", T("After the reset everybody has")), def),
      h("label.field", h("span", T("Book the points on")), acc)),
    h("label.row", on, " ", T("Use the weather")),
    h("div.row", h("button.btn", { onclick: async () => {
      try {
        await call("parent/weather/config", { method: "PUT", body: { enabled: on.checked, levels: [...rows.children].map(r => r.read()),
          default: def.value, reset: time.value || "12:00", account: acc.value } });
        toast(T("Saved"), "good"); render();
      } catch (e) { toast(e.message, "bad"); }
    } }, T("Save"))));
  if (part === "set" && !cfg.enabled) return;
  main.append(...(part === "config" ? [conf] : part === "set" ? [list] : [list, conf]));
}

/** Season designs of the app header: seasons, Halloween, Christmas (on/off, dates) and own designs. */
function themesSection() {
  const sec = section("🎨 " + I18N.tr(T("Season, time of day & weather designs")));
  const VIS = { alltag: "🏡", fruehling: "🌷", sommer: "🏖️", herbst: "🍂", winter: "❄️", halloween: "🎃", weihnachten: "🎄", silvester: "🎆", fasnacht: "🎭",
    ostern: "🐣", liebe: "💕", pfingsten: "🪁", august: "🇨🇭", schule: "🎒", geburtstag: "🎂", sport: "⛷️" };
  const md = v => { const [m, d] = String(v).split("-"); return fmtDate(new Date(2024, +m - 1, +d), { day: "numeric", month: "short" }); };
  const toMd = v => v ? v.slice(5) : "";            // <input type=date> → MM-DD
  const toDate = v => "2026-" + v;
  let cfg = null;
  const save = async () => {
    try { const r = await call("parent/themes", { method: "PUT", body: cfg }); draw(r); toast(T("Saved"), "good"); } catch (e) { /* call shows the error */ }
  };
  const ownDialog = (o, idx) => {
    o = Object.assign({ name: "", icon: "🎨", vis: "alltag", accent: "#5b5bd6", from: "", to: "" }, o || {});
    const name = h("input", { type: "text", maxlength: 40, value: o.name, placeholder: I18N.tr(T("e.g. Mia's birthday")) });
    const icon = h("input", { type: "text", maxlength: 8, value: o.icon, style: { width: "5em" } });
    const vis = h("select", ...Object.entries(VIS).map(([k, ic]) => h("option", { value: k, selected: k === o.vis }, ic + " " + k)));
    const accent = h("input", { type: "color", value: o.accent || "#5b5bd6" });
    const from = h("input", { type: "date", value: o.from ? toDate(o.from) : "" }), to = h("input", { type: "date", value: o.to ? toDate(o.to) : "" });
    const m = modal(h("div.form", h("h2", "🎨 ", o.name ? C(o.name) : T("Own design")),
      h("div.row", h("label.field.grow", T("Name"), name), h("label.field", T("Icon"), icon)),
      h("div.grid2", h("label.field", T("Scene"), vis), h("label.field", T("Colour"), accent)),
      h("div.grid2", h("label.field", h("span", T("From"), fieldInfo(T("Every year on these days (the year is ignored). Own designs come before Halloween, Christmas and the seasons."))), from), h("label.field", T("To"), to)),
      h("div.row", h("button.btn", { onclick: () => {
        if (!name.value.trim() || !from.value || !to.value) return toast(T("A design needs a name and a date from – to"), "bad");
        const d = { ...o, name: name.value.trim(), icon: icon.value || "🎨", vis: vis.value, accent: accent.value, from: toMd(from.value), to: toMd(to.value) };
        if (idx == null) cfg.own.push(d); else cfg.own[idx] = d;
        m.close(); save();
      } }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  };
  const draw = d => {
    cfg = { builtin: {}, own: [] };
    d.designs.forEach(x => { if (x.builtin) cfg.builtin[x.id] = { on: x.on, from: x.from, to: x.to }; else cfg.own.push({ id: x.id, name: x.name, icon: x.icon, vis: x.vis, accent: x.accent, from: x.from, to: x.to, on: x.on }); });
    const row = (x, i) => h("li.row.theme-row" + (x.on ? "" : ".off"),
      h("span.big-ic", x.icon), h("div.grow", x.builtin ? h("strong", T(x.name)) : C(x.name, "strong"),
        h("div.small.muted", md(x.from) + " – " + md(x.to), " · ", VIS[x.vis] || "", x.kind === "season" ? " · " + I18N.tr(T("season")) : "")),
      d.active && d.active.id === x.id ? h("span.chip.good", T("active now")) : null,
      h("label.check", { title: T("On / off") }, h("input", { type: "checkbox", checked: x.on, onchange: e => {
        if (x.builtin) cfg.builtin[x.id].on = e.target.checked; else cfg.own[i].on = e.target.checked; save(); } })),
      x.builtin ? h("button.icon-btn", { title: T("Dates"), onclick: () => {
        const from = h("input", { type: "date", value: toDate(x.from) }), to = h("input", { type: "date", value: toDate(x.to) });
        const m = modal(h("div.form", h("h2", x.icon, " ", T(x.name)), h("div.grid2", h("label.field", T("From"), from), h("label.field", T("To"), to)),
          h("div.row", h("button.btn", { onclick: () => { cfg.builtin[x.id].from = toMd(from.value); cfg.builtin[x.id].to = toMd(to.value); m.close(); save(); } }, T("Save")),
            h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
      } }, "📅") : [
        h("button.icon-btn", { title: T("Edit"), onclick: () => ownDialog(cfg.own[i], i) }, "✏️"),
        h("button.icon-btn", { title: T("Delete"), onclick: () => { cfg.own.splice(i, 1); save(); } }, "🗑️")]);
    let ownIdx = -1;
    sec.replaceChildren(sec.firstChild,
      h("ul.list", ...d.designs.map(x => row(x, x.builtin ? null : ++ownIdx))),
      h("button.btn.ghost", { onclick: () => ownDialog(null, null) }, "+ ", T("Own design")));
  };
  call("parent/themes").then(draw).catch(() => {});
  return sec;
}

const KID_OPEN = new Set();               // overview: the children's rows that are open (while the page lives)

/** The weather of the day of one child (overview row): the symbol now, the buttons to pick it, the last 30 days. */
function kidWeather(k, cfg) {
  const now = h("span.weather-now"), pick = h("div.weather-btns"), hist = h("div.weather-hist");
  const back = cfg.levels.find(l => l.key === cfg.default);
  const info = fieldInfo(() => [T("Give each child its weather – the bonus or malus is booked right away. Only the child sees its own weather."),
    I18N.tr(T("Everybody is back at {0} at {1}.")).replace("{0}", back ? back.icon : "").replace("{1}", cfg.reset)], { title: T("Weather of the day") });
  const draw = (cur, days) => {
    now.textContent = cur ? cur.icon : ""; now.title = cur ? wName(cur.name) : "";
    const counts = {};
    days.forEach(x => { if (x.icon) counts[x.icon] = (counts[x.icon] || 0) + 1; });
    pick.replaceChildren(...cfg.levels.map(l => h("button.btn.small" + (cur && cur.key === l.key ? ".on" : ".ghost"), { type: "button", title: wName(l.name),
      onclick: async () => {
        try {
          const r = await call(`parent/weather/${k.profile.id}`, { method: "POST", body: { level: l.key } });
          toast(l.icon + " " + k.profile.name + (l.points ? " · " + (l.points > 0 ? "+" : "") + fmt(l.points) : ""), l.points < 0 ? "" : "good");
          draw(r.current, r.days);
        } catch (e) { toast(e.message, "bad"); }
      } }, h("span.big-ic", l.icon), l.points ? h("span.small", (l.points > 0 ? " +" : " ") + fmt(l.points)) : null)), info);
    hist.replaceChildren(weatherGraph(days, cfg.levels.length), h("div.small.muted.row", h("span.grow", T("Last 30 days")),
      ...cfg.levels.filter(l => counts[l.icon]).map(l => h("span", l.icon + " " + counts[l.icon]))));
  };
  draw(k.current, k.days);
  return { now, pick, hist };
}

function weatherBox(part) {
  const box = h("div");
  weatherView(box, part).catch(e => box.append(h("p.bad", e.message)));
  return box;
}

async function choresView(main) {
  const [d, profiles] = await Promise.all([call("parent/chores"), call("parent/profiles")]);
  P.accounts = await call("parent/accounts");
  const kids = profiles.filter(p => p.role === "kid");
  const kidName = id => (kids.find(k => k.id === id) || {}).name || "?";
  const today = new Date().toISOString().slice(0, 10);
  const plan = h("div.scroll", h("table.tbl.weekplan",
    h("thead", h("tr", ...d.week.days.map((day, i) => h("th" + (day.day === today ? ".today" : ""), WEEKDAYS[i], h("br"),
      h("span.small", new Date(day.day + "T12:00").toLocaleDateString(I18N.locale, { day: "numeric", month: "numeric" })))))),
    h("tbody", h("tr", ...d.week.days.map(day => h("td" + (day.day === today ? ".today" : ""), ...day.entries.map(e =>
      h("div.plan-entry" + (e.weekly ? ".weekly" : ""), h("span", e.icon + " "), C(e.name, "strong"),
        h("div.small", ...e.profiles.map(pid => C(kidName(pid), "span.plan-kid")))))))))));
  const status = { open: "○", pending: "⏳", done: "✓" };
  const own = d.chores.filter(c => c.active);
  const planerBox = planerChoresSection(
    h("div.row", own.some(c => c.frequency !== "once") ? h("button.btn.ghost", { onclick: async () => {
        if (!(await confirmDialog(I18N.tr(T("Move the chores of this list into the Planner? They are switched off here (their history stays)."))))) return;
        const r = await call("planer/chores/take-over", { method: "POST" });
        toast(I18N.tr(T("{0} chores moved to the Planner")).replace("{0}", r.moved.length), "good");
        if (r.kept.length) toast(I18N.tr(T("One-off chores stay here – create them as special chores in the Planner: {0}")).replace("{0}", r.kept.join(", ")));
        render();
      } }, "➡️ ", T("Move my chores to the Planner")) : null));
  main.append(pageHead(T("Chores"), h("button.btn", { onclick: () => choreDialog(null, kids) }, "+ ", T("Add chore"))),
    planerBox,
    d.pending.length ? section("⏳ " + I18N.tr(T("Chores to confirm")), choreConfirmList(d.pending, render)) : null,
    section("📅 " + I18N.tr(T("This week")), d.chores.some(c => c.active) ? plan : h("p.muted", T("No chores yet – add the first one."))),
    d.today.length ? section("✅ " + I18N.tr(T("Today")), h("ul.list", ...d.today.map(t => h("li.row", h("span.status-ic." + t.status, status[t.status] || ""),
      h("span", t.icon), C(t.name, "span.grow"), C(t.profile_name, "span.muted"))))) : null,
    section("🧹 " + I18N.tr(T("All chores")), h("ul.list", ...d.chores.map(c => h("li.row" + (c.active ? "" : ".off"),
      h("span.big-ic", c.icon), h("div.grow", C(c.name, "strong"),
        h("div.small.muted", FREQ[c.frequency] || c.frequency,
          c.frequency === "weekdays" ? " (" + c.weekdays.map(i => I18N.tr(WEEKDAYS[i])).join(", ") + ")" : "",
          c.frequency === "once" ? " " + fmtDate(c.date) : "", " · ",
          c.assign === "rotate" ? I18N.tr(T("rotating")) : I18N.tr(T("fixed")), ": ", C(c.profiles.map(kidName).join(", ")), " · ",
          c.kind === "duty" ? I18N.tr(T("duty")) : I18N.tr(T("bonus")), " · +" + fmt(c.points), c.energy ? " · 🔋+" + c.energy : "",
          c.confirm ? " · 👪 " + I18N.tr(T("parents confirm")) : "", c.active ? "" : " · " + I18N.tr(T("switched off")))),
      h("button.btn.small.ghost", { onclick: () => choreDialog(c, kids) }, "✏️ ", T("Edit")))))),
    planerSettingsSection());
}

// 📅 The Family Planer's chore plan in the parent area (planer?mode=parent in a frame). The planer's own top bar
// (clock, season, its buttons) is hidden there (planer.html) – its functions are buttons in this section head:
// 🏖️ holidays (only when the planer checks holidays; the number = holidays waiting for a decision), «+ Special chore»,
// «+ To-do». They call the planer in the frame (planer/host.js FQ_PLANER_DO) – same windows, PIN rules and API calls.
// «Refresh» (the planer pulls calendars and lists again) is the app's ⟳ button (planerRefresh). Settings: below.
function planerChoresSection(...more) {
  const frame = planerFrame("planner?mode=parent#/aemtliplan", T("Chore plan"));
  const act = kind => {
    const w = frame.contentWindow;
    if (!w || !w.FQ_PLANER_DO) return;
    w.FQ_PLANER_DO(kind);
  };
  const dot = h("span.chip.warn.planer-dot", { hidden: true });
  const vac = h("button.btn.small.ghost", { hidden: true, title: T("Holidays and absences in the calendar: who is away, are chores paused?"),
    onclick: () => act("vac") }, "🏖️ ", T("Holidays"), dot);
  frame.addEventListener("fq-planer-state", e => {
    const st = e.detail || {};
    vac.hidden = !st.vac; vac.classList.toggle("on", !!st.open);
    dot.hidden = !st.pending; dot.textContent = st.pending ? String(st.pending) : "";
  });
  return sectionAdd("📅 " + I18N.tr(T("One chore plan: the Planner")), [vac,
      h("button.btn.small.ghost", { onclick: () => act("special") }, "+ ", T("Special chore")),
      h("button.btn.small.ghost", { onclick: () => act("todo") }, "+ ", T("To-do"))],
    frame, ...more);
}

// ⚙️ the planer's settings (persons, points, holidays, lists …, with the planer's own parent PIN) – folded at the
// bottom like the settings of the other sections; the frame loads only when opened
function planerSettingsSection() {
  const box = h("details.card.sec.fold.planer-settings", h("summary", h("h2", "⚙️ " + I18N.tr(T("Planner settings")))));
  box.addEventListener("toggle", () => {
    if (box.open && !box.querySelector(".planer-frame")) box.append(planerFrame("planner?mode=parent#/einstellungen", T("Planner settings")));
  });
  return box;
}

// the app's ⟳ button: on the Chores page the planer first pulls its calendars and lists again (at most 8 s)
function planerRefresh() {
  const w = [...document.querySelectorAll(".planer-frame")].map(f => f.contentWindow).find(x => x && x.FQ_PLANER_DO);
  return w ? Promise.race([w.FQ_PLANER_DO("refresh"), new Promise(r => setTimeout(r, 8000))]).catch(() => {}) : Promise.resolve();
}

function choreDialog(c, kids) {
  const isNew = !c;
  c = c || { name: "", icon: "🧹", points: 10, account: "coins", frequency: "daily", weekdays: [], date: "", assign: "fixed",
    rotate_every: "week", profiles: kids.map(k => k.id), kind: "bonus", confirm: true, active: true };
  const f = {
    icon: h("input.icon-in", { type: "text", value: c.icon }), name: h("input", { type: "text", value: c.name, placeholder: T("e.g. set the table") }),
    points: h("input", { type: "number", min: 0, value: c.points }),
    account: h("select", ...P.accounts.filter(a => a.active).map(a => h("option", { value: a.key, selected: a.key === c.account }, a.icon + " " + I18N.tr(a.name)))),
    frequency: h("select", ...Object.entries(FREQ).map(([k, n]) => h("option", { value: k, selected: k === c.frequency }, n))),
    date: h("input", { type: "date", value: c.date || "" }),
    assign: h("select", h("option", { value: "fixed", selected: c.assign === "fixed" }, T("Fixed: every chosen child")),
      h("option", { value: "rotate", selected: c.assign === "rotate" }, T("Rotating: one child after the other"))),
    rotate_every: h("select", h("option", { value: "week", selected: c.rotate_every === "week" }, T("changes every week")),
      h("option", { value: "day", selected: c.rotate_every === "day" }, T("changes every day"))),
    kind: h("select", h("option", { value: "bonus", selected: c.kind === "bonus" }, T("Bonus chore (full points)")),
      h("option", { value: "duty", selected: c.kind === "duty" }, T("Duty (few or no points)"))),
    confirm: h("input", { type: "checkbox", checked: !!c.confirm }), active: h("input", { type: "checkbox", checked: !!c.active }),
    energy: h("input", { type: "number", min: 0, max: 20, step: 1, inputmode: "numeric", value: c.energy || 0 }),
  };
  const days = WEEKDAYS.map((n, i) => h("label.check", h("input", { type: "checkbox", value: i, checked: c.weekdays.includes(i) }), n));
  const who = kids.map(k => h("label.check", h("input", { type: "checkbox", value: k.id, checked: c.profiles.includes(k.id) }), C(k.name)));
  const dayRow = h("div.row", ...days), dateRow = h("label.field", T("Date"), f.date), rotRow = h("label.field", T("Rotation"), f.rotate_every);
  const sync = () => { dayRow.hidden = f.frequency.value !== "weekdays"; dateRow.hidden = f.frequency.value !== "once"; rotRow.hidden = f.assign.value !== "rotate"; };
  f.frequency.addEventListener("change", sync); f.assign.addEventListener("change", sync); sync();
  const m = modal(h("div.form",
    h("h2", isNew ? T("New chore") : T("Edit chore")),
    h("div.row", f.icon, h("label.field.grow", T("Name"), f.name)),
    h("div.field-row", h("label.field", T("Points"), f.points), h("label.field", T("Account"), f.account), h("label.field", T("Type"), f.kind),
      h("label.field", h("span", "⚡ ", T("Energy bonus"), fieldInfo(T("Segments of the game battery the child gets when the chore is done (0 = none). Never more than the battery holds."))), f.energy)),
    h("div.grid3", h("label.field", T("How often"), f.frequency), dateRow, h("label.field", T("Assignment"), f.assign), rotRow), dayRow,
    h("div", h("strong", T("Who")), h("div.row", ...who)),
    h("label.check", f.confirm, T("Parents confirm before points are booked")), h("label.check", f.active, T("Active")),
    h("div.row", h("button.btn", { onclick: save }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")), h("span.grow"),
      !isNew ? h("button.btn.small.bad", { onclick: remove }, T("Remove")) : null)), { wide: true });
  async function save() {
    const body = { name: f.name.value, icon: f.icon.value || "🧹", points: +f.points.value, account: f.account.value, frequency: f.frequency.value,
      weekdays: days.map(l => l.querySelector("input")).filter(x => x.checked).map(x => +x.value), date: f.date.value || null,
      assign: f.assign.value, rotate_every: f.rotate_every.value, profiles: who.map(l => l.querySelector("input")).filter(x => x.checked).map(x => +x.value),
      kind: f.kind.value, confirm: f.confirm.checked, active: f.active.checked, sort: c.sort || 0, energy: Math.max(0, Math.min(20, Math.round(+f.energy.value || 0))) };
    await call(isNew ? "parent/chores" : `parent/chores/${c.id}`, { method: isNew ? "POST" : "PUT", body });
    m.close(); toast(T("Saved"), "good"); render();
  }
  async function remove() {
    if (!(await confirmDialog(I18N.tr(T("Remove this chore? Chores already done stay in the history."))))) return;
    await call(`parent/chores/${c.id}`, { method: "DELETE" }); m.close(); render();
  }
}

// ---------------------------------------------------------------- rewards: accounts, rules, shop
// phones: a table with class «stack» shows each row as a small card – every cell gets its column name (also rows added later)
function stackTable(table) {
  const names = [...table.querySelectorAll("thead th")].map(th => { const c = th.cloneNode(true); c.querySelectorAll(".info-btn").forEach(x => x.remove()); return I18N.tr(c.textContent.trim()); });
  const label = tr => [...tr.children].forEach((td, i) => { if (names[i]) td.dataset.label = names[i]; });
  table.querySelectorAll("tbody tr").forEach(label);
  new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => { if (n.nodeName === "TR") label(n); }))).observe(table.tBodies[0], { childList: true });
  return table;
}

async function rewardsView(main, opts = {}) {
  const [accounts, rules, rewards] = await Promise.all([call("parent/accounts"), call("parent/rules"), call("parent/rewards")]);
  P.accounts = accounts;
  const accOpts = sel => accounts.map(a => h("option", { value: a.key, selected: a.key === sel }, (a.icon || "") + " " + I18N.tr(a.name)));

  const accRows = accounts.map(a => {
    const f = { name: h("input", { type: "text", value: I18N.tr(a.name) }), unit: h("input", { type: "text", value: a.unit }), icon: h("input", { type: "text", value: a.icon }),
      spendable: h("input", { type: "checkbox", checked: !!a.spendable, disabled: a.key === "xp" }), active: h("input", { type: "checkbox", checked: !!a.active, disabled: a.key === "xp" }) };
    const save = () => call("parent/accounts", { method: "PUT", body: { key: a.key, name: f.name.value, unit: f.unit.value, icon: f.icon.value,
      spendable: f.spendable.checked, active: f.active.checked, sort: a.sort } }).then(() => toast(T("Saved"), "good"));
    Object.values(f).forEach(x => x.addEventListener("change", save));
    return h("tr", h("td.key-col", { translate: "no" }, h("code", a.key)), h("td", f.icon), h("td", f.name), h("td", f.unit), h("td.c", f.spendable), h("td.c", f.active));
  });
  const newAcc = h("input", { type: "text", placeholder: T("key, e.g. stars") });

  const ruleRows = rules.map(r => ruleRow(r));
  function ruleRow(r) {
    const f = { event: h("select", ...Object.entries(P.meta.events).map(([k, n]) => h("option", { value: k, selected: k === r.event }, n))),
      account: h("select", ...accOpts(r.account)), amount: h("input", { type: "number", value: r.amount, step: "1" }),
      daily_limit: h("input", { type: "number", value: r.daily_limit ?? "", placeholder: "–" }), label: h("input", { type: "text", value: I18N.tr(r.label || "") }),
      active: h("input", { type: "checkbox", checked: !!r.active }) };
    const save = () => call(r.id ? `parent/rules/${r.id}` : "parent/rules", { method: r.id ? "PUT" : "POST", body: { event: f.event.value, account: f.account.value,
      amount: +f.amount.value, daily_limit: f.daily_limit.value === "" ? null : +f.daily_limit.value, condition: r.condition || {}, label: f.label.value, active: f.active.checked } })
      .then(x => { if (!r.id && x) r.id = x.id; toast(T("Saved"), "good"); });
    Object.values(f).forEach(x => x.addEventListener("change", save));
    return h("tr", h("td", f.event), h("td.num", f.amount), h("td", f.account), h("td.num", f.daily_limit), h("td", f.label), h("td.c", f.active),
      h("td", h("button.icon-btn", { title: T("Delete"), onclick: async e => { if (r.id) await call(`parent/rules/${r.id}`, { method: "DELETE" }); e.target.closest("tr").remove(); } }, "✕")));
  }
  const rulesBody = h("tbody", ...ruleRows);

  const rewardCards = rewards.map(r => rewardCard(r));
  function rewardCard(r) {
    const f = { icon: h("input.icon-in", { type: "text", value: r.icon }), name: h("input", { type: "text", value: I18N.tr(r.name) }),   // built-in names are English keys – show (and save) the translation the children see
      kind: h("select", ...Object.entries(KIND_NAMES).map(([k, n]) => h("option", { value: k, selected: k === r.kind }, n))),
      account: h("select", ...accOpts(r.account)), cost: h("input", { type: "number", min: 0, value: r.cost }),
      approval: h("input", { type: "checkbox", checked: !!r.approval }), weekly_limit: h("input", { type: "number", min: 0, value: r.weekly_limit ?? "", placeholder: "–" }),
      active: h("input", { type: "checkbox", checked: !!r.active }), cfg: h("input", { type: "text" }) };
    const cfgLabel = h("span");
    const cfgKey = () => ({ internet_minutes: "minutes", planer_points: "points", ha_script: "script", avatar_item: "item" })[f.kind.value];
    const drawCfg = () => { const k = cfgKey(); cfgLabel.textContent = k ? I18N.tr({ minutes: T("Minutes"), points: T("Points"), script: T("Script (script.xyz)"), item: T("Avatar item id") }[k]) : ""; f.cfg.hidden = !k; f.cfg.value = k ? (r.config || {})[k] ?? "" : ""; };
    f.kind.addEventListener("change", drawCfg); drawCfg();
    const save = async () => {
      const k = cfgKey(); const config = {}; if (k && f.cfg.value !== "") config[k] = ["minutes", "points"].includes(k) ? +f.cfg.value : f.cfg.value;
      const body = { name: f.name.value, kind: f.kind.value, account: f.account.value, cost: +f.cost.value, approval: f.approval.checked,
        weekly_limit: f.weekly_limit.value === "" ? null : +f.weekly_limit.value, icon: f.icon.value || "🎁", config, active: f.active.checked, sort: r.sort || 0 };
      const x = await call(r.id ? `parent/rewards/${r.id}` : "parent/rewards", { method: r.id ? "PUT" : "POST", body });
      if (!r.id && x) r.id = x.id; r.config = config; toast(T("Saved"), "good");
    };
    return h("div.card.reward-ed" + (r.active ? "" : ".off"),
      h("div.row", f.icon, h("label.field.grow", T("Name"), f.name)),
      h("div.grid3", h("label.field", T("Type"), f.kind), h("label.field", T("Paid from"), f.account), h("label.field", T("Price"), f.cost),
        h("label.field", T("Max. per week"), f.weekly_limit), h("label.field", cfgLabel, f.cfg),
        h("div", h("label.check", f.approval, T("Parents must approve")), h("label.check", f.active, T("In the shop")))),
      h("button.btn.small", { onclick: save }, T("Save")));
  }
  const rewardBox = h("div.reward-grid", ...rewardCards);

  main.append(h("h1", T("Rewards")),
    sectionAdd(T("Accounts"), h("button.btn.small", { onclick: () => {
        const m = modal(h("div.form", h("h2", "+ ", T("Add account")), h("label.field", T("Key"), newAcc), h("p.small.muted", T("Short name without spaces, e.g. stars – the name and icon can be changed afterwards.")),
          h("div.row", h("button.btn", { onclick: async () => { const k = newAcc.value.trim().toLowerCase(); if (!k) return newAcc.focus();
            await call("parent/accounts", { method: "PUT", body: { key: k, name: k, unit: "", icon: "⭐", spendable: true, active: true, sort: 9 } }); m.close(); render(); } }, "💾 ", T("Save")),
            h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
        newAcc.focus();
      } }, "+ ", T("Add account")),
      h("div.scroll", stackTable(h("table.tbl.stack", h("thead", h("tr", h("th.key-col", T("Key"), fieldInfo(T("The short internal name of the account, without spaces – rules and rewards use it."))), h("th", "Icon"), h("th", T("Name")),
        h("th", T("Unit"), fieldInfo(T("What the points of this account are called, e.g. «min» – shown next to the amounts."))),
        h("th", T("Spendable"), fieldInfo(T("XP shows progress and is never spent. Spendable accounts can be used in the shop."))),
        h("th", T("Active"), fieldInfo(T("An inactive account is hidden in the app and nothing is booked on it any more – what it holds is kept."))))), h("tbody", ...accRows))))),
    sectionAdd(T("Rules: which action gives how much on which account"),
      h("button.btn.small", { onclick: () => rulesBody.append(ruleRow({ event: "lesson_done", account: "coins", amount: 5, daily_limit: null, label: "", active: 1, condition: {} })) }, "+ ", T("Add rule")),
      h("div.scroll", stackTable(h("table.tbl.stack", h("thead", h("tr", h("th", T("Event"), fieldInfo(T("What gives the points: a right answer, a finished lesson, the daily goal, a chore …"))),
        h("th", T("Amount"), fieldInfo(T("How many points one such event gives; a negative amount takes points away."))), h("th", T("Account")),
        h("th", T("Daily limit"), fieldInfo(T("The most points this rule gives a child per day. Empty = no limit."))),
        h("th", T("Label"), fieldInfo(T("An own name for the rule, e.g. in the list of points – empty: the name of the event."))),
        h("th", T("Active"), fieldInfo(T("An inactive rule gives no points until you switch it on again."))), h("th"))), rulesBody)))),
    section("🛍️ " + I18N.tr(T("Shop")),
      h("button.btn.small", { onclick: () => { P.tab = "shop"; location.hash = "shop"; render(); } }, "🛍️ ", T("Open the shop settings"))));
  if (opts.onlyShop) { main.replaceChildren(); return { rewardBox, rewardCard }; }
}

// ---------------------------------------------------------------- shop: own rewards on top, then every avatar item
async function shopSettingsView(main) {
  const scratch = h("div");
  const { rewardBox, rewardCard } = await rewardsView(scratch, { onlyShop: true });
  const d = await call("parent/shop/items");
  const SLOT_NAMES = { background: T("Background"), hat: T("Hat"), hairclip: T("Hair clip"), eyewear: T("Glasses"), face: T("Face"), teeth: T("Teeth"),
    ear: T("Ears"), neck: T("Neck"), suit: T("Clothes"), figure: T("Figure"), back: T("On the back"), hand: T("In the hand"), pet: T("Pet") };
  const howText = b => b.free ? T("free") : b.level ? I18N.tr(T("From level {0}")).replace("{0}", b.level) : b.badge ? T("With a badge")
    : b.season ? T("Only in season") : b.xp ? b.xp + " " + I18N.tr(T("new XP")) : b.cost != null ? b.cost + " 🪙" : "";
  const row = it => {
    const o = it.override || {};
    const base = it.base, baseCur = base.xp ? "xp" : "coins", basePrice = base.xp ?? base.cost ?? null;
    const f = { on: h("input", { type: "checkbox", checked: !o.off }),
      price: h("input", { type: "number", min: 0, max: 100000, value: o.price ?? "", placeholder: basePrice != null ? String(basePrice) : "–" }),
      cur: h("select", h("option", { value: "" }, I18N.tr(T("as in the app")) + " (" + (baseCur === "xp" ? "✨ XP" : "🪙") + ")"),
        h("option", { value: "coins", selected: o.currency === "coins" }, "🪙 " + I18N.tr(T("Coins"))),
        h("option", { value: "xp", selected: o.currency === "xp" }, "✨ " + I18N.tr(T("new XP")))) };
    const tr = h("tr" + (o.off ? ".off" : ""));
    const save = async () => {
      try {
        const r = await call(`parent/shop/items/${encodeURIComponent(it.id)}`, { method: "PUT",
          body: { off: !f.on.checked, price: f.price.value === "" ? null : +f.price.value, currency: f.cur.value || null } });
        tr.classList.toggle("off", !f.on.checked); toast(T("Saved"), "good"); it.override = r.override;
      } catch (e) { toast(e.message, "bad"); }
    };
    Object.values(f).forEach(x => x.addEventListener("change", save));
    tr.append(h("td", avatarSvg({ ...DEFAULT_AV, items: { [it.slot]: it.id } }, 44)), h("td", C(I18N.tr(it.name), "strong"), h("div.small.muted", SLOT_NAMES[it.slot] || it.slot)),
      h("td.small.muted", howText(base)), h("td.c", f.on), h("td.num", f.price), h("td", f.cur));
    return tr;
  };
  const DEFAULT_AV = { skin: "#f1c27d", hair: "short", hairColor: "#6b3e1f", eyes: "round", mouth: "smile", outfit: "tshirt", outfitColor: "#4f8cff", items: {} };
  const bySlot = d.slots.map(sl => [sl, d.items.filter(i => i.slot === sl)]).filter(([, l]) => l.length);
  // search: own rewards (name) and avatar items (name, kind) – matching groups open, the others hide
  const search = h("input.pack-search", { type: "search", placeholder: "🔍 " + I18N.tr(T("Search the shop …")), value: P.shopSearch || "",
    "aria-label": T("Search the shop …"), oninput: () => { P.shopSearch = search.value; filterShop(); } });
  const noShop = noMatch(T("Nothing found in the shop"), () => { search.value = ""; P.shopSearch = ""; filterShop(); });
  const filterShop = () => {
    const q = (search.value || "").trim().toLowerCase();
    main.querySelectorAll(".reward-ed").forEach(c => { c.hidden = !!q && ![...c.querySelectorAll("input")].some(i => (i.value || "").toLowerCase().includes(q)); });
    const rf = rewardBox.closest("details.set-fold");
    if (rf) { const any = [...rewardBox.querySelectorAll(".reward-ed")].some(c => !c.hidden); rf.hidden = !!q && !any; if (q && any) rf.open = true; }
    main.querySelectorAll("details.shop-slot").forEach(dt => {
      const rows = [...dt.querySelectorAll("tbody tr")];
      rows.forEach(r => { r.hidden = !!q && !r.textContent.toLowerCase().includes(q) && !dt.querySelector("summary").textContent.toLowerCase().includes(q); });
      const any = rows.some(r => !r.hidden);
      dt.hidden = !!q && !any;
      if (q && any) dt.open = true;
    });
    noShop.hidden = !q || [...main.querySelectorAll(".reward-ed, details.shop-slot")].some(x => !x.hidden);
  };
  setTimeout(filterShop);
  main.append(pageHead(T("Shop")), search, noShop,
    sectionAdd("🎁 " + I18N.tr(T("Own rewards")), h("button.btn.small", { onclick: () => rewardBox.prepend(rewardCard({ name: "", kind: "voucher", account: "coins", cost: 50, approval: 1, weekly_limit: null, icon: "🎁", config: {}, active: 1 })) }, "+ ", T("Add reward")),
      rewardBox),
    // the avatar items: one folded box per kind (background, hat, …) under their group heading – like every fold
    h("h2.set-group", { "data-ik": "Avatar items" }, "🧑‍🎨 ", T("Avatar items")),
    ...bySlot.map(([sl, list]) => {
      const off = list.filter(i => i.override && i.override.off).length;
      const d = setFold("shop." + sl, SLOT_NAMES[sl] || sl, h("section.card.sec",
        h("div.scroll", h("table.tbl.shop-tbl", h("thead", h("tr", h("th"), h("th", T("Item")), h("th", T("In the app")), h("th", T("In the shop")), h("th", T("Price")), h("th", T("Paid with")))),
          h("tbody", ...list.map(row))))));
      d.classList.add("shop-slot");
      d.querySelector(".set-status").textContent = I18N.tr(T("Items: {0}")).replace("{0}", list.length) + (off ? " · " + I18N.tr(T("switched off: {0}")).replace("{0}", off) : "");
      return d;
    }));
  foldBoxes(main, "shop", () => I18N.tr(T("Rewards: {0}")).replace("{0}", rewardBox.children.length));
}

// ---------------------------------------------------------------- goals
/** Family › 🎯 Goals: the running goals, «+ Add goal» / «+ Start family goal» (was its own page «Goals»). */
async function goalsSection() {
  const [goals, profiles, packs] = await Promise.all([call("parent/goals"), call("parent/profiles"), call("parent/packs")]);
  P.accounts = await call("parent/accounts");
  const kids = profiles.filter(p => p.role === "kid");
  const list = goals.map(g => {
    const kid = kids.find(k => k.id === g.profile_id);
    const pack = packs.packs.find(p => p.id === g.pack_id);
    const unit = pack && pack.units ? pack.units.find(u => u.id === g.unit_id) : null;
    return h("li.row", h("span.big-ic", g.kind === "family" ? "🤝" : "🎯"), h("div.grow",
      C(g.title || (pack ? pack.title + (unit ? " – " + unit.title : "") : ""), "strong"),
      h("div.small.muted", g.kind === "family" ? I18N.tr(T("Family goal")) + " · " + fmt(g.target) + " " + (g.account || "") : [C(kid ? kid.name : "?"), " · ", unit ? g.target + " ★" : g.target + " %"])),
      h("button.icon-btn", { title: T("Delete"), onclick: async () => { await call(`parent/goals/${g.id}`, { method: "DELETE" }); render(); } }, "✕"));
  });
  const f = { kid: h("select", ...kids.map(k => h("option", { value: k.id }, k.name))),
    pack: h("select", ...packs.packs.filter(p => p.kind === "pack" && p.status === "active").map(p => h("option", { value: p.id }, p.title))),
    unit: h("select"), target: h("input", { type: "number", min: 1, max: 100, value: 3 }), title: h("input", { type: "text", placeholder: T("e.g. French unit 3 done") }) };
  const fillUnits = () => { const p = packs.packs.find(x => x.id === f.pack.value); f.unit.replaceChildren(h("option", { value: "" }, I18N.tr(T("whole pack (%)"))), ...((p && p.units) || []).map(u => h("option", { value: u.id }, u.title))); };
  f.pack.addEventListener("change", fillUnits); fillUnits();
  const fg = { title: h("input", { type: "text", placeholder: T("e.g. pizza evening") }), account: h("select", ...P.accounts.filter(a => a.active).map(a => h("option", { value: a.key }, a.icon + " " + I18N.tr(a.name)))),
    target: h("input", { type: "number", min: 1, value: 2000 }) };
  const goalDialog = family => { const m = modal(h("div.form", family ? formFamily : formKid, h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))); };
  const formKid = h("div.form", h("h2", T("Weekly goal for a child")),
      h("div.grid3", h("label.field", T("Child"), f.kid), h("label.field", T("Pack"), f.pack), h("label.field", T("Unit"), f.unit),
        h("label.field", T("Target (stars or %)"), f.target), h("label.field", T("Title (optional)"), f.title)),
      h("button.btn", { onclick: async () => { await call("parent/goals", { method: "POST", body: { kind: "unit", profile_id: +f.kid.value, pack_id: f.pack.value,
        unit_id: f.unit.value || null, target: +f.target.value, title: f.title.value } }); document.querySelector(".modal-back")?.remove(); render(); } }, "💾 ", T("Add goal")));
  const formFamily = h("div.form", h("h2", T("Family goal")),
      h("div.grid3", h("label.field", T("What for?"), fg.title), h("label.field", T("Account"), fg.account), h("label.field", T("Target"), fg.target)),
      h("button.btn", { onclick: async () => { if (!fg.title.value) return fg.title.focus(); await call("parent/goals", { method: "POST", body: { kind: "family", title: fg.title.value,
        account: fg.account.value, target: +fg.target.value } }); document.querySelector(".modal-back")?.remove(); render(); } }, "💾 ", T("Start family goal")));
  const sec = sectionAdd("🎯 " + I18N.tr(T("Current goals")), [h("button.btn.small.ghost", { onclick: () => goalDialog(true) }, "+ ", T("Start family goal")),
      h("button.btn.small", { onclick: () => goalDialog(false) }, "+ ", T("Add goal"))],
    goals.length ? h("ul.list", ...list) : h("p.muted", T("No goals yet.")));
  sec.dataset.fold = "goals";
  sec.dataset.status = goals.length ? I18N.tr(T("Current goals")) + ": " + goals.length : I18N.tr(T("No goals yet."));
  return sec;
}

// ---------------------------------------------------------------- link + QR code for tablets and phones
function linkSection() {
  const url = h("input", { type: "url", spellcheck: false, onfocus: e => e.target.select() });
  const qr = h("div.qr-box"), warn = h("div");
  const draw = () => qr.replaceChildren(url.value ? qrSvg(url.value.trim()) : "");
  url.addEventListener("input", draw);
  call("parent/direct-access").then(d => {
    const host = (d.ips && d.ips[0]) || location.hostname;
    url.value = `http://${host}:${d.port || d.default_port || 8099}/`; draw();
    if (!d.enabled) warn.replaceChildren(h("p.warn-text",
      T("Direct access is still off: in Home Assistant open the app → Configuration, switch on direct_access and restart the app.")));
  }).catch(() => { url.value = `http://${location.hostname}:8099/`; draw(); });
  return section("📱 " + I18N.tr(T("Link for tablets and phones")),
    warn,
    h("div.qr-row", qr, h("div.grow",
      h("label.field", h("span", T("Address in the home network"), fieldInfo(T("Only reachable at home (Wi-Fi). Change it if the address is not right."))), url),
      h("div.row", h("button.btn", { onclick: () => printPoster(url.value.trim()) }, "🖨️ ", T("Print poster"))))));
}

async function printPoster(link) {
  if (!link) return;
  document.querySelector("#poster")?.remove();
  let crest = null;
  try { crest = (await call("parent/memory")).crest; } catch {}
  const poster = h("div#poster",
    crest ? h("div.poster-crest", crestSvg(crest)) : h("img.poster-logo", { src: "img/icon.svg", alt: "" }),
    h("h1", "Family Quest"),
    h("p.poster-lead", T("Scan me – then pick your profile!")),
    qrSvg(link),
    h("p.poster-steps", T("Open the camera, point it at the code and tap the link.")),
    h("p.poster-url", { translate: "no" }, link),
    h("p.poster-note", T("Works in our home Wi-Fi.")));
  document.body.append(poster);
  document.body.classList.add("printing");
  const done = () => { document.body.classList.remove("printing"); poster.remove(); window.removeEventListener("afterprint", done); };
  window.addEventListener("afterprint", done);
  setTimeout(() => window.print(), 300);       // the translations of the poster texts need a moment
}

// ---------------------------------------------------------------- the games of the app (parent area › Games)
const GAME_LIST = [["quiz", "🎯", T("Family quiz")], ["bingo", "🎱", "Bingo"], ["song", "🎵", T("Guess the song")], ["tschau", "🂡", "Tschau Sepp"], ["karussell", "🎠", T("Card Carousel")], ["domino", "🁫", "Domino"], ["paarjagd", "🧠", T("Pair Hunt")], ["werbinich", "🎭", T("Who am I?")],
    ["kartenlauf", "🏁", T("Card Race")], ["stadtland", "🏙️", T("City, Country, River")], ["zeichnen", "🎨", T("Draw & Guess")], ["wuerfel", "🎲", T("Five Dice")], ["heimwaerts", "🏠", T("Homeward")], ["jump", "🦘", "Jump"], ["sternlauf", "🌠", T("Star Runner")], ["snack", "🍔", T("Snack Rush")], ["verkehr", "🚦", T("Traffic Cadet")], ["klatsch", "👏", T("Clap the Beat")], ["verboten", "🚫", T("Forbidden Words")], ["jass", "♣️", T("Jass")], ["werwolf", "🐺", T("Werewolves")], ["schach", "♟️", T("Chess")], ["dorfmarkt", "🏘️", T("Village Market")], ["escape", "🗝️", T("Escape Room")], ["stempeljagd", "🏛️", T("Beat the Bureaucracy")], ["poker", "🃏", "Texas Hold'em"], ["ttt", "⭕", T("Tic-Tac-Toe")], ["sudoku", "🔢", T("Sudoku")], ["patience", "🃏", T("Patience")], ["cube", "🧊", T("Cube solver")],
    ["pingpong", "🏓", T("Ping-Pong")], ["slots", "🎰", T("One-armed bandit")]];
GAME_LIST.splice(GAME_LIST.findIndex(g => g[0] === "verkehr") + 1, 0, ["langstrecke", "🏎️", T("24h Endurance")]);
GAME_LIST.push(["adventuregame", "🗝️", T("Adventure games")]);
// 🛠️ Custom games: the games with the family's own content (quizzes, photo sets, adventure games) – on top of the page
const CUSTOM_GAMES = ["quiz", "paarjagd", "adventuregame"];
// the built-in games in the groups of the children's games page (kid.js gamesView, minigames.js «Game corner»)
const GAME_GROUPS = [["night", "🎲", T("For a game night"), ["tschau", "karussell", "domino", "jass", "poker", "dorfmarkt", "heimwaerts", "langstrecke", "kartenlauf",
    "werwolf", "escape", "stempeljagd", "werbinich", "verboten", "zeichnen", "stadtland", "song", "bingo", "schach"]],
  ["quick", "⚡", T("Quick games for in between"), ["wuerfel", "jump", "klatsch", "sternlauf", "snack", "verkehr"]],
  ["corner", "🕹️", T("Game corner"), ["ttt", "pingpong", "sudoku", "patience", "slots", "cube"]]];
const FREE_GAMES = new Set(["adventuregame"]);             // no price, no rent (services.py FREE_GAMES)

// per game: active / active without bots (only games with bots) / inactive – and for whom (everybody or chosen children)
// ---------------------------------------------------------------- game battery and party mode (familyquest/battery.py)
const UNL_CHOICES = () => [["off", T("Off")], ["forever", T("Permanent")], ["day", T("For 1 day")], ["week", T("For 1 week")], ["month", T("For 1 month")]];
const unlRunning = v => v && v !== "forever" && new Date(v.replace(" ", "T")) > new Date();

/** The values of the game battery – the family default (`own` null) or one child's own values («as the family»). */
function batteryForm(values, own, onSave, ...more) {
  const fam = values, kid = own != null;
  const has = k => kid && Object.prototype.hasOwnProperty.call(own, k);
  const num = (k, min, max) => {
    const inp = h("input", { type: "number", min, max, step: 1, inputmode: "numeric", value: kid ? (has(k) ? own[k] : "") : fam[k],
      placeholder: kid ? I18N.tr(T("as family")) + " (" + fam[k] + ")" : "",
      onchange: () => onSave({ [k]: inp.value === "" ? (kid ? null : fam[k]) : Math.max(min, Math.min(max, Math.round(+inp.value || 0))) }) });
    return inp;
  };
  const on = kid ? h("select", { onchange: () => onSave({ on: on.value === "" ? null : on.value === "1" }) },
      h("option", { value: "", selected: !has("on") }, I18N.tr(T("as family")) + " (" + I18N.tr(fam.on ? T("On") : T("Off")) + ")"),
      h("option", { value: "1", selected: has("on") && own.on }, T("On")), h("option", { value: "0", selected: has("on") && !own.on }, T("Off")))
    : h("input", { type: "checkbox", checked: fam.on, onchange: () => onSave({ on: on.checked }) });
  const cur = kid ? (has("unlimited") ? own.unlimited : null) : fam.unlimited;
  const running = unlRunning(cur);
  const unl = h("select", { onchange: () => onSave({ unlimited: unl.value }) },
    kid ? h("option", { value: "family", selected: !has("unlimited") }, T("as family")) : null,
    running ? h("option", { value: "keep", selected: true }, "∞ " + untilWhen(cur)) : null,
    ...UNL_CHOICES().map(([v, n]) => h("option", { value: v, selected: !running && (v === "forever" ? cur === "forever" : v === "off" && (kid ? has("unlimited") && cur === "" : !cur)) }, n)));
  return h("div.form.bat-form",
    kid ? h("label.field", h("span", "🔋 ", T("Game battery")), on) : h("label.check", on, h("span", "🔋 ", T("Game battery on – starting a game costs a segment"))),
    // the small fields side by side (two per row on a phone)
    h("div.field-row", h("label.field", h("span", T("Capacity (segments)"), fieldInfo(T("1 to 20 – starts full."))), num("cap", 1, 20)),
      h("label.field", h("span", "⚡ ", T("Recharging costs (coins)"), fieldInfo(T("0 = recharging is free."))), num("cost", 0, 10000)),
      h("label.field", h("span", "∞ ", T("Unlimited energy")), unl,
        running || cur === "forever" ? h("button.btn.small.ghost", { type: "button", onclick: () => onSave({ unlimited: kid ? "family" : "off" }) }, "⏹ ", T("End")) : null),
      ...more));
}

/** Parent area › Games: the family default of the game battery, the daily goal, every child's charge now. */
function batterySettingsCard() {
  const box = h("details.card.sec.bat-settings", h("summary", h("b", { "data-ik": "Game battery" }, "🔋 ", T("Game battery"))));
  const draw = d => {
    const save = async v => { try { draw(await call("parent/battery", { method: "PUT", body: v })); toast(T("Saved"), "good"); } catch {} };
    const fam = d.family;
    const goal = h("select", { onchange: () => save({ goal: goal.value }) }, ...[["off", T("Nothing")], ["full", T("Battery full")], ["plus", T("Extra segments")]]
      .map(([v, n]) => h("option", { value: v, selected: fam.goal === v }, n)));
    const plus = h("input", { type: "number", min: 1, max: 20, step: 1, value: fam.goal_plus, inputmode: "numeric", onchange: () => save({ goal_plus: +plus.value }) });
    box.replaceChildren(box.firstChild,
      batteryForm(fam, null, save, h("label.field", h("span", "🎯 ", T("Daily goal reached")), goal), fam.goal === "plus" ? h("label.field", h("span", T("Extra segments")), plus) : null),
      h("ul.list.bat-kids", ...d.kids.map(k => h("li.row", k.state ? batteryIcon(k.state) : null, C(k.name, "strong.grow"),
        h("span.small.muted", k.state && k.state.free ? (k.state.party ? "🎉 " : "∞ ") + (k.state.until ? untilWhen(k.state.until) : "") : k.state ? k.state.charge + " / " + k.state.cap : ""),
        k.state && !k.state.free && k.state.charge < k.state.cap ? h("button.btn.small.ghost", { onclick: async () => { draw(await call(`parent/battery/${k.id}/recharge`, { method: "POST" })); toast(T("Battery recharged"), "good"); } }, "🎁 ", T("Recharge")) : null))));
  };
  call("parent/battery").then(draw).catch(() => {});
  return box;
}

/** Profile dialog of a child: its own battery values (empty = as the family). */
function kidBatteryBox(pid) {
  const box = h("div.form.lim-box", h("h3", { "data-ik": "Game battery" }, "🔋 ", T("Game battery")), h("p.small.muted", "…"));
  const draw = d => {
    const k = d.kids.find(x => x.id === pid);
    if (!k) return box.replaceChildren();
    const save = async v => { try { draw(await call(`parent/battery/${pid}`, { method: "PUT", body: v })); toast(T("Saved"), "good"); } catch {} };
    box.replaceChildren(box.firstChild,
      k.state ? h("div.row", batteryIcon(k.state, true), h("span.grow", k.state.party ? "🎉 " + I18N.tr(T("Party mode")) : k.state.free ? "∞" + (k.state.until ? " " + untilWhen(k.state.until) : "") : k.state.charge + " / " + k.state.cap),
        !k.state.free && k.state.charge < k.state.cap ? h("button.btn.small.ghost", { type: "button", onclick: async () => { draw(await call(`parent/battery/${pid}/recharge`, { method: "POST" })); } }, "🎁 ", T("Recharge")) : null) : null,
      batteryForm(d.family, k.own, save));
  };
  call("parent/battery").then(draw).catch(() => box.replaceChildren());
  return box;
}

/** 🎉 Party mode: a switch with a chooser – for whom, what, how long (Games page and overview). */
function partyCard() {
  const box = h("section.card.sec.party-card");
  const draw = async () => {
    let p = null, kids = [];
    try { [p, kids] = await Promise.all([call("parent/party"), call("parent/profiles").then(l => l.filter(x => x.role === "kid"))]); } catch { return; }
    const sw = h("input.party-switch", { type: "checkbox", role: "switch", checked: !!p, "aria-label": T("Party mode"),
      onchange: async () => {
        if (sw.checked) { sw.checked = false; return partyDialog(kids, draw); }
        if (!(await confirmDialog(I18N.tr(T("End the party mode?"))))) { sw.checked = true; return; }
        await call("parent/party", { method: "DELETE" }); toast(T("Party mode ended"), "good"); draw();
      } });
    const who = p ? (p.kids === "all" ? I18N.tr(T("all children")) : p.kids.map(id => (kids.find(k => k.id === id) || {}).name || "?").join(", ")) : "";
    const what = p ? [p.unlock ? T("all games open") : null, p.battery ? T("starting is free") : null, p.limits ? T("no game time limit") : null].filter(Boolean).map(t => I18N.tr(t)).join(" · ") : "";
    box.classList.toggle("on", !!p);
    box.replaceChildren(h("div.row", h("span.big-ic", "🎉"), h("div.grow", h("h2", { "data-ik": "Party mode" }, T("Party mode")),
        p ? h("div.small", h("b", p.until ? untilWhen(p.until) : I18N.tr(T("until switched off"))), " · ", C(who), what ? h("div.small.muted", what) : null) : null),
      h("label.switch-wrap", sw, h("span.switch-ui"))));
  };
  draw();
  return box;
}

function partyDialog(kids, after) {
  const all = h("input", { type: "radio", name: "pk", checked: true }), some = h("input", { type: "radio", name: "pk" });
  const picks = kids.map(k => h("label.check", h("input", { type: "checkbox", value: k.id, checked: true }), C(k.name)));
  const pickRow = h("div.row", { hidden: true }, ...picks);
  all.onchange = some.onchange = () => { pickRow.hidden = !some.checked; };
  const chk = (label, hint) => { const i = h("input", { type: "checkbox", checked: true }); return [i, h("label.check", i, h("span", label, hint ? h("span.small.muted", " – ", hint) : null))]; };
  const [unlock, unlockL] = chk("🔓 " + I18N.tr(T("Unlock all games")), T("price, rent and «inactive» do not count"));
  const [batt, battL] = chk("🔋 " + I18N.tr(T("Unlimited battery")), null);
  const [lim, limL] = chk("⏱️ " + I18N.tr(T("Also lift limits")), T("daily game time, game block times and the OfflineTime game lock – internet and learning stay as they are"));
  let dur = "forever";
  const durs = h("div.pin-kind.party-durs");
  const drawDur = () => durs.replaceChildren(...[["forever", T("Until switched off")], ["1h", "1 h"], ["3h", "3 h"], ["midnight", T("Until midnight")], ["day", T("1 day")]]
    .map(([v, n]) => h("button.btn.small" + (dur === v ? "" : ".ghost"), { type: "button", "aria-pressed": String(dur === v), onclick: () => { dur = v; drawDur(); } }, n)));
  drawDur();
  const m = modal(h("div.form.party-dialog", h("h2", "🎉 ", T("Party mode")),
    h("h3", T("For whom")), h("div.row", h("label.check", all, T("All children")), h("label.check", some, T("Chosen children"))), pickRow,
    h("h3", T("What")), unlockL, battL, limL,
    h("h3", T("How long")), durs,
    h("div.row", h("button.btn", { onclick: async () => {
      const body = { kids: all.checked ? "all" : picks.map(l => l.querySelector("input")).filter(i => i.checked).map(i => +i.value),
        unlock: unlock.checked, battery: batt.checked, limits: lim.checked, for: dur };
      try { await call("parent/party", { method: "POST", body }); } catch { return; }
      m.close(); confetti(); toast(T("Party mode on – have fun!"), "good"); after();
    } }, "🎉 ", T("Start the party")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function gameAccess(kids, data) {
  let acc = data.access, returns = data.slots_returns || {};
  const botGames = new Set(data.bot_games || []), bars = {}, chipRows = {};
  const save = async k => {
    try { const r = await call("parent/games", { method: "PUT", body: { access: k ? { [k]: acc[k] } : acc } }); acc = r.access; returns = r.slots_returns || returns; toast(T("Saved"), "good"); } catch {}
    new Set([...Object.keys(bars), ...Object.keys(chipRows)]).forEach(draw);
  };
  // the folded row of a game shows its settings at a glance: status, who, price / rent
  const drawChips = k => {
    const a = acc[k] || { mode: "all", profiles: [], bots: true }, row = chipRows[k];
    if (!row) return;
    const state = a.mode === "off" ? "off" : a.bots === false ? "nobots" : "on";
    const per = I18N.tr({ day: T("Day"), week: T("Week"), month: T("Month") }[a.period || "week"] || T("Week"));
    row.replaceChildren(
      state === "off" ? chip("✕ " + I18N.tr(T("Inactive")), "bad") : chip(state === "nobots" ? "🚫 " + I18N.tr(T("Active without bots")) : "✓ " + I18N.tr(T("Active")), "good"),
      state !== "off" && a.mode === "some" ? chip("👥 " + I18N.tr(T("Only chosen children"))) : null,
      state === "off" || FREE_GAMES.has(k) ? null : a.price > 0 || a.rent > 0
        ? null : chip(I18N.tr(T("Free"))),
      state !== "off" && a.price > 0 ? chip("🪙 " + fmt(a.price)) : null,
      state !== "off" && a.rent > 0 ? chip("🔁 " + fmt(a.rent) + " 🪙/" + per) : null);
  };
  const draw = k => {
    drawChips(k);
    const a = acc[k] || { mode: "all", profiles: [], bots: true }, bar = bars[k];
    if (!bar) return;
    const state = a.mode === "off" ? "off" : a.bots === false ? "nobots" : "on";
    const set = v => { acc[k] = v === "off" ? { ...a, mode: "off" } : { ...a, mode: a.mode === "off" ? "all" : a.mode, bots: v === "on" }; save(k); };
    bar.classList.toggle("off", state === "off");                  // the section is dimmed (parent.css)
    bar.replaceChildren(...[
      h("div.pin-kind.game-state", ...[["on", "✓ ", T("Active")], botGames.has(k) ? ["nobots", "🚫 ", T("Active without bots")] : null, ["off", "✕ ", T("Inactive")]].filter(Boolean)
        .map(([v, ic, n]) => h("button.btn.small" + (state === v ? (v === "off" ? ".bad" : "") : ".ghost"), { "aria-pressed": String(state === v), onclick: () => set(v) }, ic, n)),
        botGames.has(k) ? fieldInfo(T("No «alone against bots», no bots at the table, no games against the app – only people play. Parents are not bound."), { title: T("Active without bots") }) : null),
      state === "off" ? null : h("div.pin-kind", ...[["all", T("For everybody")], ["some", T("Only chosen children")]].map(([m, n]) =>
        h("button.btn.small" + (a.mode === m ? "" : ".ghost"), { onclick: () => { acc[k] = { ...a, mode: m }; save(k); } }, n))),
      state !== "off" && a.mode === "some" ? h("div.row.game-kids", ...kids.map(kid => h("label.check", h("input", { type: "checkbox", checked: a.profiles.includes(kid.id),
        onchange: e => { const ids = new Set(a.profiles); e.target.checked ? ids.add(kid.id) : ids.delete(kid.id); acc[k] = { ...a, profiles: [...ids] }; save(k); } }), C(kid.name)))) : null,
      state === "off" || FREE_GAMES.has(k) ? null : gamePriceBox(k, a, v => { acc[k] = { ...a, ...v }; save(k); }, returns)].filter(Boolean));
  };
  return {
    bar: k => { if (!bars[k]) { bars[k] = h("div.game-status"); setTimeout(() => draw(k)); } return bars[k]; },
    chips: k => { if (!chipRows[k]) { chipRows[k] = h("span.game-chips"); drawChips(k); } return chipRows[k]; },
    allTo: mode => { for (const [k] of GAME_LIST) if (k in acc) acc[k] = { ...(acc[k] || { profiles: [] }), mode }; return save(null); },
  };
}

// what a child pays for a game (familyquest/gamepasses.py): buy once, or rent per day / week / month – 0 and 0 = free;
// the fields show the defaults (quick games 100 a week, game corner 20 a day) – saving stores them as shown; free tries;
// the one-armed bandit also gets its luck (1–10, what comes back on average). Parents always play for free.
function gamePriceBox(k, a, set, returns) {
  const num = (v, max = 100000) => Math.max(0, Math.min(max, Math.round(+v || 0)));
  const price = h("input", { type: "number", min: 0, max: 100000, step: 1, inputmode: "numeric", value: a.price || 0,
    onchange: () => set({ price: num(price.value) }) });
  const rent = h("input", { type: "number", min: 0, max: 100000, step: 1, inputmode: "numeric", value: a.rent || 0,
    oninput: () => periods.querySelectorAll("button").forEach(b => { b.disabled = !num(rent.value); }),
    onchange: () => set({ rent: num(rent.value) }) });
  const periods = h("div.pin-kind.gp-periods", ...[["day", T("Day")], ["week", T("Week")], ["month", T("Month")]].map(([v, n]) =>
    h("button.btn.small" + ((a.period || "week") === v ? "" : ".ghost"), { disabled: !(a.rent > 0), "aria-pressed": String((a.period || "week") === v),
      onclick: () => set({ period: v }) }, n)));
  // free tries before buying / renting (default 1) – only with a price or a rent
  const preview = h("input.gp-preview", { type: "number", min: 0, max: 20, step: 1, inputmode: "numeric", value: a.preview ?? 1,
    onchange: () => set({ preview: num(preview.value, 20) }) });
  let luck = null;
  if (k === "slots") {
    const pct = v => I18N.tr(T("≈ {0} % comes back on average")).replace("{0}", returns[v] ?? "?");
    const hint = h("span.hint", pct(a.luck || 5));          // the live value stays visible
    const range = h("input.gp-luck", { type: "range", min: 1, max: 10, step: 1, value: a.luck || 5,
      oninput: () => { hint.textContent = pct(range.value); val.textContent = range.value; }, onchange: () => set({ luck: +range.value }) });
    const val = h("b", String(a.luck || 5));
    luck = h("label.field", h("span", "🍀 ", T("Win chance"), " ", val, " / 10",
      fieldInfo(T("5 = like a typical casino machine. Higher: better odds for the children, lower: worse."))), range, hint);
  }
  // side by side: price · free tries · rent with its period (the rent spans two columns, so day / week / month stay next to it)
  rent.setAttribute("aria-label", T("Rent price (coins)"));
  return h("div.gp-box",
    h("div.field-row",
      h("label.field", h("span", "🪙 ", T("Price for children (coins)"),
        fieldInfo(T("0 = free. Bought once, the game stays the child's for good – also when you change the price."), T("With a price the children buy or rent the game in the shop. Parents always play for free."))), price),
      h("label.field", h("span", "🎁 ", T("Free tries before buying"),
        fieldInfo(T("How often a child may play the game for free before buying or renting it. Only matters with a price or a rent."))), preview),
      h("div.field.span2", h("span", "🔁 ", T("Rent price (coins)"),
        fieldInfo(T("0 = no renting. Renting opens the game for one day, week or month; renting again adds the time."))), h("div.gp-rent", rent, periods))),
    luck);
}

// ---------------------------------------------------------------- pairs game: own photo sets and the family crest
// pick pictures from Home Assistant Media (Media → My media, mapped read-only): folders, thumbnails, choose
const MAX_PICK = 40;                                           // as many as a photo set holds (memorygame.MAX_PHOTOS)
async function haMediaPicker({ single = false } = {}) {
  return new Promise(resolve => {
    let picked = new Set(), cur = "", data = null, done = false;
    const body = h("div.hm-body"), foot = h("div.row");
    const finish = v => { if (done) return; done = true; if (seen) seen.disconnect(); m.close(); resolve(v);
      setTimeout(() => urls.forEach(p => p.then(u => u && URL.revokeObjectURL(u))), 5000); };
    const urls = new Map();                                    // thumbnails loaded once (the parent header cannot go into <img src>)
    const load = (el, rel) => {
      if (!urls.has(rel)) urls.set(rel, fetch("api/parent/ha-media/file?path=" + encodeURIComponent(rel), { headers: { "X-FQ-Parent": Auth.parent } })
        .then(r => r.ok ? r.blob() : null).then(b => b ? URL.createObjectURL(b) : null).catch(() => null));
      urls.get(rel).then(u => { if (u) el.src = u; });
    };
    // only the pictures that come into view are loaded – a camera folder with hundreds of photos stays light
    const seen = "IntersectionObserver" in window ? new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { seen.unobserve(e.target); load(e.target, e.target.dataset.rel); }
    }), { rootMargin: "200px" }) : null;
    const thumb = (img, rel) => {
      const el = h("img", { alt: "" });
      el.dataset.rel = rel;
      if (seen) seen.observe(el); else load(el, rel);
      return el;
    };
    const drawFoot = () => foot.replaceChildren(...[
      !single && data && data.images.length ? h("button.btn.ghost.small", { onclick: () => {
        const all = data.images.map(x => (cur ? cur + "/" : "") + x.name).slice(0, MAX_PICK);
        picked = picked.size === all.length ? new Set() : new Set(all); draw(); } }, T("Select all")) : null,
      !single && picked.size >= MAX_PICK ? h("span.small.muted", I18N.tr(T("At most {0} pictures at once")).replace("{0}", MAX_PICK)) : null,
      h("span.grow"), h("button.btn.ghost", { onclick: () => finish(null) }, T("Cancel")),
      single ? null : h("button.btn", { disabled: !picked.size, onclick: () => finish([...picked]) }, "✓ ", I18N.tr(T("Add ({0})")).replace("{0}", picked.size))].filter(Boolean));
    const draw = () => {
      if (!data) return;
      if (!data.available) {
        body.replaceChildren(h("p", T("No Home Assistant Media found.")),
          h("p.small.muted", T("Put photos into Home Assistant → Media → My media (e.g. with the File editor, Samba or the upload in the Media browser). After an update of the app, restart it once so it can see the folder.")));
        return drawFoot();
      }
      const parts = cur ? cur.split("/") : [];
      body.replaceChildren(...[
        h("div.hm-crumbs", h("button.link", { onclick: () => open("") }, "🏠 ", T("My media")),
          ...parts.map((p, i) => [" / ", h("button.link", { onclick: () => open(parts.slice(0, i + 1).join("/")) }, C(p))])),
        data.folders.length ? h("div.hm-folders", ...data.folders.map(f => h("button.hm-folder", { onclick: () => open((cur ? cur + "/" : "") + f) }, "📁 ", C(f)))) : null,
        data.images.length ? h("div.hm-grid", ...data.images.map(x => {
          const rel = (cur ? cur + "/" : "") + x.name;
          return h("button.hm-pic" + (picked.has(rel) ? ".on" : ""), { title: x.name, onclick: () => {
            if (single) return finish([rel]);
            if (picked.has(rel)) picked.delete(rel); else if (picked.size < MAX_PICK) picked.add(rel);
            draw(); } }, thumb(x, rel));
        })) : !data.folders.length ? h("p.small.muted", T("No pictures in this folder.")) : null].filter(Boolean));
      drawFoot();
    };
    const open = async path => {
      cur = path; body.replaceChildren(h("div.spinner"));
      try { data = await call("parent/ha-media?path=" + encodeURIComponent(path)); cur = data.path || ""; } catch { data = { available: true, path: cur, folders: [], images: [] }; }
      draw();
    };
    const m = modal(h("div", h("div.sec-head", h("h2", "🏠 ", T("Home Assistant Media")),
        h("div.head-actions", haMediaOpenBtn(), h("button.btn.small.ghost", { title: T("Refresh"), onclick: () => open(cur) }, "🔄 ", T("Refresh")))),
      body, foot), { wide: true, onClose: () => finish(null) });
    open("");
  });
}

// photos for the pairs game and the crest: upload from this device or take them from Home Assistant Media
// The cards of the pairs game are small: the shorter edge becomes at most PHOTO_EDGE px (sharp enough on phones and
// tablets, a few KB per photo instead of megabytes).
const PHOTO_EDGE = 240;
// a file dialog that works reliably in phone browsers and the Home Assistant app: the input must be part of the page
// while the dialog is open (a detached one is sometimes collected before «change» fires); removed afterwards
function pickFiles({ accept = "image/*", multiple = false } = {}, then) {
  const inp = h("input", { type: "file", accept, multiple, style: { position: "fixed", left: "-1000px", top: "0", opacity: "0" } });
  const done = () => setTimeout(() => inp.remove(), 1000);
  inp.addEventListener("change", () => { const files = [...inp.files]; done(); if (files.length) then(files); });
  inp.addEventListener("cancel", done);
  document.body.append(inp);
  inp.click();
}

const Photos = {
  async upload(file, edge = PHOTO_EDGE) {          // the crest (printed on the poster) passes a larger edge
    const blob = await shrinkPhoto(file, edge, { short: true });
    for (let attempt = 0; ; attempt++) {            // one more try after a network hiccup (phones on Wi-Fi)
      const fd = new FormData(); fd.append("file", blob, "foto.jpg");
      try { return (await api("parent/memory/photo", { method: "POST", form: fd })).name; }
      catch (e) { if (attempt >= 1 || /\b(400|413|415)\b|large|photos? \(/i.test(e.message || "")) throw e; await new Promise(r => setTimeout(r, 800)); }
    }
  },
  async uploadAll(files, edge) {                           // every photo on its own – one bad file does not stop the others
    const out = [];
    for (const [i, file] of files.entries()) {
      if (files.length > 1) toast("⏳ " + I18N.tr(T("Uploading photo {0} of {1} …")).replace("{0}", i + 1).replace("{1}", files.length));
      try { out.push(await Photos.upload(file, edge)); } catch (e) { toast(`${file.name}: ${e.message}`, "bad"); }
    }
    return out;
  },
  pick(multiple, then, edge) {
    pickFiles({ accept: "image/*", multiple }, async files => { const names = await Photos.uploadAll(files, edge); if (names.length) await then(names); });
  },
  async fromHa(single, then, edge) {
    const paths = await haMediaPicker({ single });
    if (!paths || !paths.length) return;
    // a small copy of every picture (the original in Home Assistant Media stays as it is); a picture that cannot be
    // loaded here falls back to the reference «ha:<path>» as before
    const names = [], refs = [];
    for (const rel of paths) {
      try {
        const res = await fetch("api/parent/ha-media/file?path=" + encodeURIComponent(rel), { headers: { "X-FQ-Parent": Auth.parent } });
        if (!res.ok) throw new Error(res.status);
        const blob = await res.blob();
        names.push(await Photos.upload(new File([blob], rel.split("/").pop() || "foto.jpg", { type: blob.type || "image/jpeg" }), edge));
      } catch { refs.push(rel); }
    }
    if (refs.length) try { names.push(...(await call("parent/memory/ha-media", { method: "POST", body: { paths: refs } })).names); } catch {}
    if (names.length) await then(names);
  },
};

// the media browser of Home Assistant (upload photos there), in a new tab
async function haMediaHref() {
  if (P.info && P.info.via_ha) return "/media-browser/browser";
  try { const p = await api("ha-panel"); if (p.port) return `${p.ssl ? "https" : "http"}://${location.hostname}:${p.port}/media-browser/browser`; } catch {}
  return null;
}
function haMediaOpenBtn() {
  const a = h("a.btn.small.ghost", { href: "/media-browser/browser", target: "_blank", rel: "noopener" }, "↗ ", T("Open Home Assistant Media"));
  haMediaHref().then(u => { if (u) a.href = u; else a.hidden = true; });
  return a;
}

// family crest (Settings): drawn from colours, pattern and symbol – or an own picture
async function crestSection() {
  let d = { crest: null };
  try { d = await call("parent/memory"); } catch {}
  const crest = d.crest || { name: "", icon: "🏠", colors: ["#5b5bd6", "#fcc419"], pattern: "split", motto: "", image: null };
  let useCrest = !!d.crest;
  const preview = h("div.crest-prev");
  const drawCrest = () => preview.replaceChildren(useCrest ? crestSvg(crest) : h("p.small.muted", T("No family crest yet.")));
  const inp = (key, attrs = {}) => h("input", { type: "text", value: crest[key] || "", ...attrs, oninput: e => { crest[key] = e.target.value; drawCrest(); } });
  const color = i => h("input", { type: "color", value: crest.colors[i], oninput: e => { crest.colors[i] = e.target.value; drawCrest(); } });
  const PATTERNS = { plain: T("plain"), split: T("split"), quarter: T("quartered"), band: T("diagonal band"), chevron: T("chevron") };
  const save = async (quiet = false) => {
    try { d = await call("parent/memory", { method: "PUT", body: { crest: useCrest ? crest : null } }); if (!quiet) toast(T("Saved"), "good"); }
    catch (e) { toast(e.message, "bad"); }
  };
  const setImage = async ([n]) => { crest.image = n; drawCrest(); drawPictureRow(); await save(true); };
  const pictureRow = h("div.row.wrap");
  const drawnFields = h("div",
    h("div.grid2", h("label.field", T("Symbol (emoji)"), inp("icon", { maxlength: 8 })),
      h("label.field", T("Pattern"), h("select", { onchange: e => { crest.pattern = e.target.value; drawCrest(); } },
        ...Object.entries(PATTERNS).map(([k, n]) => h("option", { value: k, selected: crest.pattern === k }, I18N.tr(n)))))),
    h("label.field", T("Colours"), h("div.row", color(0), color(1))));
  const drawPictureRow = () => { drawnFields.hidden = !!crest.image; pictureRow.replaceChildren(...[
    h("button.btn.small.ghost", { onclick: () => Photos.pick(false, setImage, 800) }, "📷 ", T("Upload picture")),
    crest.image ? h("button.btn.small.ghost", { onclick: () => { crest.image = null; drawCrest(); drawPictureRow(); } }, "✕ ", T("Remove picture")) : null].filter(Boolean)); };
  const crestForm = h("div.form",
    h("label.field", T("Family name"), inp("name", { maxlength: 40, placeholder: T("e.g. Miller") })),
    h("div.field", h("span", T("Own picture as crest"), fieldInfo(T("A photo or drawing of your crest – it is shown in the shield. Without a picture the crest is drawn from colours, pattern and symbol."))), pictureRow),
    drawnFields);
  const onOff = h("input", { type: "checkbox", checked: useCrest, onchange: e => { useCrest = e.target.checked; crestForm.hidden = !useCrest; drawCrest(); } });
  crestForm.hidden = !useCrest;
  drawCrest(); drawPictureRow();
  return section("🛡️ " + I18N.tr(T("Family crest")),
    h("label.check", onOff, h("span", T("We have a family crest"))),
    h("div.crest-edit", preview, crestForm),
    h("div.row", h("button.btn", { onclick: () => save() }, "💾 ", T("Save"))));
}

// photo sets of the pairs game and the Paarjagd (parent area › Games › Custom games › Pair Hunt): the list of the sets,
// «+ New» starts with a preset (an empty set with a name), «📥 Import» takes photos or a ZIP file, ⬇️ a set as ZIP
const PHOTO_PRESETS = () => [["👨‍👩‍👧", T("Family")], ["🐾", T("Pets")], ["🏖️", T("Holidays")], ["🎂", T("Birthdays")], ["👵", T("Grandparents")], ["🏠", T("Our home")]];
async function photoSets(onCount = null) {
  let d = { sets: [] };
  try { d = await call("parent/memory"); } catch {}
  const setsBox = h("div.mm-sets");
  const save = async (quiet = false) => {
    for (const st of d.sets) if (!st.name.trim()) {               // a set without a name gets a free «Photos n»
      let n = 1; const taken = new Set(d.sets.map(x => x.name));
      while (taken.has(I18N.tr(T("Photos {0}")).replace("{0}", n))) n++;
      st.name = I18N.tr(T("Photos {0}")).replace("{0}", n);
    }
    try {
      const r = await call("parent/memory", { method: "PUT", body: { sets: d.sets } });
      // keep the objects on screen (an upload still running adds to them), only take over what the server decided
      r.sets.forEach((x, i) => { if (d.sets[i]) Object.assign(d.sets[i], { id: x.id, name: x.name }); });
      drawSets(); if (!quiet) toast(T("Saved"), "good");
    }
    catch (e) { toast(e.message, "bad"); }
  };
  const addTo = st => async names => { st.photos.push(...names.filter(n => !st.photos.includes(n))); drawSets(); await save(true); toast(I18N.tr(T("{0} photos added")).replace("{0}", names.length), "good"); };
  const drawSets = () => {
    if (onCount) onCount(d.sets.length);
    setsBox.replaceChildren(...(d.sets.length ? [] : [h("p.small.muted.sb-empty", T("Nothing here yet – start with «+ New»."))]), ...d.sets.map((st, i) => h("div.card.qe",
    h("div.row", h("input.grow", { type: "text", maxlength: 60, value: st.name, placeholder: I18N.tr(T("e.g. Our holidays")), oninput: e => { st.name = e.target.value; } }),
      st.id && st.photos.length ? h("button.icon-btn", { title: T("Export as ZIP file"), onclick: () => downloadApi(`parent/memory/sets/${st.id}/export`, "family-quest-photos.zip") }, "⬇️") : null,
      h("button.icon-btn", { title: T("Delete"), onclick: async () => { if ((await confirmDialog(I18N.tr(T("Delete the photo set «{0}»?")).replace("{0}", st.name || "–")))) { d.sets.splice(i, 1); drawSets(); save(true); } } }, "🗑️")),
    h("div.mm-thumbs", ...st.photos.map((ph, j) => h("div.mm-thumb", h("img", { src: memPhotoUrl(ph), alt: "", loading: "lazy" }),
      h("button", { title: T("Remove photo"), onclick: () => { st.photos.splice(j, 1); drawSets(); } }, "✕")))),
    h("div.row.wrap",
      h("button.btn.ghost.small", { onclick: () => Photos.pick(true, addTo(st)) }, "📷 ", T("Add photos"))),
    h("p.small.muted", I18N.tr(T("Photos: {0}")).replace("{0}", st.photos.length), st.photos.length < 3 ? [" – ", T("at least 3 photos for a game")] : null))));
  };
  const free = name => { const taken = new Set(d.sets.map(x => x.name)); let n = name, i = 2; while (taken.has(n)) n = name + " " + i++; return n; };
  const add = async (name, photos = []) => {
    if (d.sets.length >= 20) return toast(T("At most 20 photo sets – delete one first"), "bad");
    d.sets.unshift({ name: free(name), photos }); drawSets(); await save(true);
    toast(photos.length ? I18N.tr(T("{0} photos added")).replace("{0}", photos.length) : T("Photo set added – now add photos"), "good");
  };
  // «+ New»: a preset (an empty set with its name) or an empty set without a name
  const newDialog = () => {
    const tile = (ic, name, go) => h("button.mm-preset", { onclick: () => { m.close(); go(); } }, h("span.big-ic", ic), h("strong", name));
    const m = modal(h("div.form", h("h2", "🧠 ", T("New photo set")),
      h("div.mm-presets", tile("📄", T("Empty set"), () => { d.sets.unshift({ name: "", photos: [] }); drawSets(); setsBox.querySelector("input").focus(); }),
        ...PHOTO_PRESETS().map(([ic, n]) => tile(ic, n, () => add(ic + " " + I18N.tr(n))))),
      h("div.row", h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))), { wide: true });
  };
  // «📥 Import»: one or several photos at once – becomes a new set
  const importDialog = () => pickFiles({ accept: "image/*", multiple: true }, async files => {
    const names = [...new Set(await Photos.uploadAll(files))].slice(0, 40);
    if (names.length) await add(I18N.tr(T("Photos {0}")).replace("{0}", d.sets.length + 1), names);
  });
  drawSets();
  return { newDialog, importDialog, el: h("div.mm-box",
    setsBox,
    h("div.row", h("button.btn", { onclick: () => save() }, "💾 ", T("Save")))) };
}

// ---------------------------------------------------------------- mini firewall: allowed networks
// parent area with the Home Assistant login instead of the PIN
function haLoginSection(s) {
  const u = P.meta.ha_user, mine = P.meta.my_ha_user;
  const only = h("input", { type: "checkbox", checked: !!s.parent_ha_only, disabled: !(u && mine) && !s.parent_ha_only });
  return section("🏠 " + I18N.tr(T("Log in with Home Assistant")),
    h("div.row.wrap",
      h("span.grow", mine ? ["✓ ", I18N.tr(T("Linked with «{0}»")).replace("{0}", mine)] : u ? I18N.tr(T("You are logged in to Home Assistant as «{0}».")).replace("{0}", u.name || u.user)
        : I18N.tr(T("Open the parent area through Home Assistant to link your user."))),
      mine ? h("button.btn.small.ghost", { onclick: async () => { await call("parent/ha-link", { method: "POST", body: { on: false } }); P.meta = await call("parent/meta"); render(); } }, T("Unlink"))
        : u ? h("button.btn.small", { onclick: async () => { await call("parent/ha-link", { method: "POST", body: { on: true } }); P.meta = await call("parent/meta"); toast(T("Linked with Home Assistant"), "good"); render(); } }, "🔗 ", T("Link my user")) : null),
    h("label.check", only, h("span", T("Parent area only through Home Assistant (no PIN login for the parent area)"),
      fieldInfo(T("Then the app port (tablets, phones) is only for the children's app – the parent area opens only in the Home Assistant sidebar with your Home Assistant login. No second port is needed.")))),
    h("button.btn.small", { onclick: async () => {
      try {
        await call("parent/settings", { method: "PUT", body: { parent_ha_only: only.checked } });
        s.parent_ha_only = only.checked; toast(T("Saved"), "good");
      } catch (e) { only.checked = !!s.parent_ha_only; }
    } }, "💾 ", T("Save")),
    haAppLoginBox());
}

// «Sign in with Home Assistant» in the app on tablets and phones (direct port, api/haauth.py)
function haAppLoginBox() {
  const box = h("div.ha-app-box");
  (async () => {
    let st;
    try { st = await call("parent/ha-app-login"); } catch { return; }
    const on = h("input", { type: "checkbox", checked: st.on });
    const url = h("input", { type: "url", value: st.url, placeholder: st.auto || "http://192.168.1.10:8123", "aria-label": T("Home Assistant address for the sign-in"), autocomplete: "off" });
    const result = h("p.small");
    const names = st.linked.map(p => p.name).join(", ");
    box.replaceChildren(
      h("h3", { "data-ik": "ha.app" }, "📱 ", T("Sign in with Home Assistant in the app")),
      h("label.check", on, h("span", T("Allow sign-in with Home Assistant in the app (tablets, phones)"))),
      h("p.small", names ? [T("Can sign in:"), " ", C(names)] : h("span.muted", T("Nobody can sign in yet – link a Home Assistant user with a profile (Profiles › edit)."))),
      h("label.field", h("span", T("Home Assistant address for the sign-in"), fieldInfo(T("The tablets must reach Home Assistant at this address."))), url,
        h("span.hint", st.auto ? I18N.tr(T("Empty = automatic: {0}")).replace("{0}", st.auto) : T("Empty = automatic (this host with the port of Home Assistant)."))),
      st.suggestions.length ? h("div.row.wrap.small", h("span.muted", T("From Home Assistant:")),
        ...st.suggestions.map(u => h("button.btn.small.ghost", { type: "button", onclick: () => { url.value = u; } }, C(u)))) : null,
      h("div.row.wrap",
        h("button.btn.small.ghost", { type: "button", onclick: async () => {
          result.textContent = "…";
          let r;
          try { r = await call("parent/ha-app-login/test", { method: "POST", body: { url: url.value.trim() } }); } catch (e) { result.textContent = ""; return; }
          // this device: an answer at all (no-cors) means the address is reachable from here
          let here = false;
          try { await fetch(r.url + "/auth/providers", { mode: "no-cors", cache: "no-store" }); here = true; } catch {}
          result.replaceChildren((here ? "✓ " : "✗ ") + I18N.tr(here ? T("This device reaches Home Assistant at {0}.") : T("This device does not reach Home Assistant at {0}.")).replace("{0}", r.url),
            h("br"), (r.server ? "✓ " : "✗ ") + I18N.tr(r.server ? T("Family Quest reaches Home Assistant.") : T("Family Quest does not reach Home Assistant at this address.")));
        } }, "🔍 ", T("Test")),
        h("button.btn.small", { type: "button", onclick: async () => {
          try {
            const r = await call("parent/settings", { method: "PUT", body: { ha_app_login: on.checked, ha_app_login_url: url.value.trim() } });
            url.value = r.ha_app_login_url || ""; toast(T("Saved"), "good");
          } catch (e) { /* call() shows the error */ }
        } }, "💾 ", T("Save"))),
      result);
  })();
  return box;
}

// ---------------------------------------------------------------- Family Quest HA integration (custom component)
// on: a token (shown once) and the component in /config/custom_components/familyquest; off: the token is refused
async function integrationSection() {
  const box = h("section.card.sec");
  let st, token = "";
  try { st = await call("parent/integration"); } catch { return null; }
  const copyField = (value, label) => {
    const inp = h("input", { type: "text", readonly: true, value, spellcheck: false, translate: "no", onfocus: e => e.target.select() });
    return h("label.field", label, h("div.row", h("span.grow", inp), h("button.btn.small", { onclick: async () => {
      try { await navigator.clipboard.writeText(value); toast(T("Copied"), "good"); } catch { inp.focus(); inp.select(); }
    } }, "📋 ", T("Copy"))));
  };
  const apply = r => { st = r; if (r.token) token = r.token; draw(); };
  async function switchTo(on) {
    try { apply(await call("parent/integration", { method: "PUT", body: { enabled: on } })); toast(T("Saved"), "good"); }
    catch { draw(); }
    if (st.install_error) toast(st.install_error, "bad");
  }
  function draw() {
    const comp = st.component || {};
    const on = h("input", { type: "checkbox", checked: st.enabled, onchange: () => switchTo(on.checked) });
    box.replaceChildren(...[h("h2", "🏠 ", T("Family Quest HA integration")),
      h("label.check", on, h("strong", T("Family Quest HA integration"))),
      !st.config_writable ? h("p.warn-text", T("The Home Assistant configuration folder cannot be written – the component cannot be copied (update the app).")) : null,
      st.enabled ? [
        token ? h("div.card.note",
          h("p", h("strong", "🔑 ", T("Integration token")), " – ", T("shown only now. Copy it and keep it until Home Assistant asks for it.")),
          copyField(token, T("Token"))) : null,
        copyField(st.url, T("Address of Family Quest (for Home Assistant)")),
        h("p.small", comp.installed ? ["✓ ", I18N.tr(T("Installed in {0} (version {1})")).replace("{0}", comp.path).replace("{1}", comp.version || "?")]
          : h("span.warn-text", T("Not installed in Home Assistant yet."))),
        h("h3", T("Next steps")),
        h("ol.small",
          h("li", T("Restart Home Assistant (Settings › System › Restart).")),
          h("li", T("Settings › Devices & services › Add integration › Family Quest.")),
          h("li", T("Keep the suggested address and paste the token."))),
        st.last_poll ? h("p.small.muted", I18N.tr(T("Home Assistant last asked: {0}")).replace("{0}", st.last_poll.replace("T", " "))) : null,
        h("div.row.wrap",
          h("button.btn.small.ghost", { onclick: async () => {
            if (!(await confirmDialog(I18N.tr(T("Make a new token? Home Assistant asks for the new one; the old token stops working."))))) return;
            apply(await call("parent/integration/token", { method: "POST" }));
          } }, "🔄 ", T("New token")),
          h("button.btn.small.ghost", { onclick: async () => { apply(await call("parent/integration/install", { method: "POST" })); toast(T("Copied to Home Assistant – restart Home Assistant"), "good"); } },
            "⬇️ ", T("Install again")))]
      : [h("p.small.muted", T("Off: Home Assistant gets no data and the token does not work.")),
        comp.installed ? h("div.row.wrap", h("span.small.grow", I18N.tr(T("Still installed in {0}")).replace("{0}", comp.path)),
          h("button.btn.small.ghost", { onclick: async () => {
            if (!(await confirmDialog(I18N.tr(T("Remove the component from Home Assistant? Delete the integration under Devices & services first, then restart Home Assistant."))))) return;
            apply(await call("parent/integration/component", { method: "DELETE" })); toast(T("Removed – restart Home Assistant"), "good");
          } }, "🗑️ ", T("Remove from Home Assistant"))) : null]].flat(2).filter(x => x != null));
  }
  draw();
  return box;
}

// IPv4 helpers for the range editor (IPv6 entries stay as written)
const ip2n = ip => { const m = String(ip).trim().match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/); if (!m || m.slice(1).some(x => +x > 255)) return null; return ((+m[1] << 24) >>> 0) + (+m[2] << 16) + (+m[3] << 8) + +m[4]; };
const n2ip = n => [n >>> 24, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].join(".");
function cidrRange(c) {   // "192.168.35.0/24" → [from, to] or null
  const [ip, len = "32"] = String(c).split("/"); const n = ip2n(ip), l = +len;
  if (n == null || !(l >= 0 && l <= 32)) return null;
  const size = 2 ** (32 - l), start = Math.floor(n / size) * size;
  return [n2ip(start), n2ip(start + size - 1)];
}
function rangeCidr(from, to) {   // exactly one network? → "a.b.c.d/len"
  const a = ip2n(from), b = ip2n(to); if (a == null || b == null || b < a) return null;
  const size = b - a + 1, l = 32 - Math.log2(size);
  return Number.isInteger(l) && a % size === 0 ? n2ip(a) + "/" + l : null;
}

// editable list of address ranges: from – to, one row per range
function networkEditor(values, myIp) {
  const rows = h("div.net-rows");
  const addRow = (from = "", to = "") => {
    const f = h("input.mono", { type: "text", value: from, placeholder: "192.168.35.1", spellcheck: false, inputmode: "decimal" });
    const t = h("input.mono", { type: "text", value: to, placeholder: "192.168.35.254", spellcheck: false, inputmode: "decimal" });
    const info = h("span.small.muted.net-info");
    const upd = () => {
      const a = ip2n(f.value), b = ip2n(t.value || f.value);
      row.classList.toggle("net-bad", !!(f.value.trim() && !f.value.includes(":") && (a == null || b == null || b < a)));
      if (a == null || b == null || b < a) { info.textContent = f.value.includes(":") ? "IPv6" : ""; return; }
      const n = b - a + 1, c = rangeCidr(n2ip(a), n2ip(b));
      info.textContent = (n === 1 ? I18N.tr(T("1 address")) : I18N.tr(T("{0} addresses")).replace("{0}", n.toLocaleString(I18N.locale))) + (c && n > 1 ? " · " + c : "");
    };
    f.oninput = upd; t.oninput = upd;
    const row = h("div.net-row", h("span.small.muted", T("from")), f, h("span.small.muted", T("to")), t, info,
      h("button.icon-btn", { type: "button", title: T("Delete"), onclick: () => row.remove() }, "🗑"));
    row.read = () => { const x = f.value.trim(), y = t.value.trim(); return !x ? "" : !y || y === x ? x : x + "-" + y; };
    rows.append(row); upd();
    return row;
  };
  for (const v of values || []) {
    if (v.includes("-")) { const [x, y] = v.split("-"); addRow(x, y); }
    else { const r = cidrRange(v); r ? addRow(r[0], r[0] === r[1] ? "" : r[1]) : addRow(v.replace(/\/128$/, ""), ""); }
  }
  const box = h("div.net-editor", rows,
    h("div.row.wrap",
      h("button.btn.small.ghost", { type: "button", onclick: () => addRow().querySelector("input").focus() }, "＋ ", T("Add range")),
      myIp && ip2n(myIp) != null ? h("button.btn.small.ghost", { type: "button", onclick: () => addRow(myIp, "") }, "＋ ", T("This device")) : null,
      myIp && ip2n(myIp) != null ? h("button.btn.small.ghost", { type: "button", onclick: () => { const r = cidrRange(myIp + "/24"); addRow(r[0], r[1]); } }, "＋ ", T("Whole network of this device")) : null),
    !(values || []).length ? h("p.small.muted", T("No range = every network is allowed.")) : null);
  box.value = () => [...rows.children].map(r => r.read()).filter(Boolean);
  return box;
}

async function firewallSection(s) {
  let my = {}; try { my = await call("parent/my-address"); } catch {}
  const me = h("p.small.muted", T("This device"), ": ", h("span.mono", my.ip || "?"),
    my.device ? h("span", " · ", C(my.device)) : null, my.mac ? h("span.mono", " · " + my.mac) : null);
  const app = networkEditor(s.allowed_networks, my.ip), par = networkEditor(s.parent_networks, my.ip), gst = networkEditor(s.guest_networks, null);
  return section("🛡️ " + I18N.tr(T("Access from the network")),
    me,
    h("h3", { "data-ik": "net.app" }, T("Whole app")), app,
    h("h3", { "data-ik": "net.parent" }, T("Parent area (additionally)")), par,
    h("h3", { "data-ik": "net.guest" }, "👥 ", T("Guest networks")), gst,
    h("button.btn", { onclick: async () => {
      try { await call("parent/settings", { method: "PUT", body: { allowed_networks: app.value(), parent_networks: par.value(), guest_networks: gst.value() } }); toast(T("Saved"), "good"); render(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "💾 ", T("Save")));
}

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

// the planner in a frame (same origin): on phones as tall as its content – no second scroll area inside the page
// the frame is as high as the planer's content (no scrolling inside a scrolling page; planer.html drops its min-height
// in the parent area) – its windows open in the part visible on the screen (planer/host.js FQ_VIS)
function planerFrame(src, title) {
  const f = h("iframe.planer-frame", { src, title: I18N.tr(title) });
  const fit = () => {
    if (!f.isConnected) return clearInterval(timer);
    try {
      const root = f.contentDocument && f.contentDocument.getElementById("planer-root");
      if (root && root.offsetHeight) f.style.height = Math.max(200, Math.ceil(root.getBoundingClientRect().height) + 4) + "px";
    } catch {}
  };
  const timer = setInterval(fit, 700);
  f.addEventListener("load", fit);
  return f;
}

// ---------------------------------------------------------------- running games: end one or all (familyquest/running.py)
function runningGamesBox() {
  const box = h("div");
  const draw = list => {
    if (!list.length) return box.replaceChildren();
    const endOne = async g => {
      if (!(await confirmDialog(I18N.tr(T("End «{0}» now?")).replace("{0}", I18N.tr(g.title))))) return;
      try { draw((await call("parent/games/end", { method: "POST", body: { key: g.key } })).running); toast(T("Game ended"), "good"); render(); } catch {}
    };
    const endAll = async () => {
      if (!(await confirmDialog(I18N.tr(T("End all {0} running games?")).replace("{0}", list.length)))) return;
      try { draw((await call("parent/games/end", { method: "POST", body: { all: true } })).running); toast(T("All games ended"), "good"); render(); } catch {}
    };
    box.replaceChildren(sectionAdd("⏹ " + I18N.tr(T("Running games")),
      list.length > 1 ? h("button.btn.small.ghost", { onclick: endAll }, "⏹ ", T("End all")) : null,
      h("div.run-list", ...list.map(g => h("div.row.run-item",
        h("span.run-ic", g.icon), h("div.grow", h("strong", I18N.tr(g.title)), h("br"),
          h("span.small.muted", [g.solo ? T("alone against bots") : T("family table"), g.host ? " · " + g.host : "",
            " · ", I18N.tr(T("Players: {0}")).replace("{0}", g.players), g.status === "lobby" ? [" · ", T("waiting to start")] : null,
            g.status === "paused" ? [" · ⏸ ", T("paused")] : null])),
        h("button.btn.small.ghost", { onclick: () => endOne(g) }, "⏹ ", T("End")))))));
  };
  call("parent/games/running").then(draw).catch(() => {});
  return box;
}

// ---------------------------------------------------------------- community: family council, polls, Wichteln, history (the games: gamesView)
async function communityView(main) {
  const me = P.meta.me;
  const [profiles, s, mem] = await Promise.all([call("parent/profiles"), call("parent/settings"), call("parent/memory").catch(() => null)]);
  const t = k => I18N.tr(k), f = (k, ...v) => v.reduce((a, x, i) => a.split("{" + i + "}").join(String(x)), I18N.tr(k));
  const mark = (sec, id, status) => { if (sec) { sec.dataset.fold = id; if (status != null) sec.dataset.status = status; } return sec; };
  // the same folds as the settings: groups with their ⓘ, every box folded with a short status in its row
  const group = (ik, icon, title) => h("h2.set-group", { "data-ik": ik }, icon + " ", title);
  const price = s.familytime_game_price ?? 150, c = mem && mem.crest;
  const vis = { percent: T("Only percentages"), goal: T("Only the family goal") }[s.family_visibility] || T("Everything");
  main.append(h("h1", T("Family")),
    group("Goals", "🎯", T("Goals")), mark(await goalsSection(), "goals"),
    group("fam.together", "🤝", T("Together")),
    mark(await familyTimeSection(me, { settings: redraw => familyTimeSettings(redraw, true) }), "familytime",
      s.familytime_wishes === false ? t(T("Game wishes off")) : price > 0 ? f(T("Game wishes on · fix a game: {0} coins"), price) : t(T("Game wishes on"))),
    mark(await councilSection(me), "council"), mark(await pollsSection(me), "polls"),
    mark(await boardsSection(me, (id, refresh) => { const b = h("div"); document.body.append(b); boardLive(b, me, id, () => { b.remove(); refresh(); }); }), "boards"),
    mark(await wichtelnSection(me), "wichteln"),
    group("fam.ours", "🏡", T("Our family")),
    mark(await storiesSection(), "library"),
    mark(await crestSection(), "crest", !c ? t(T("No family crest")) : [t(c.image ? T("Own picture") : T("Drawn crest")), c.name || null].filter(Boolean).join(" · ")),
    mark(familyViewSection(s), "view", f(T("Comparison: {0}"), t(vis)) + " · " + t(s.sound !== false ? T("Sound on") : T("Sound off"))));
  foldBoxes(main, "fam", sec => {
    // lists with «Active / Closed»: how many of each; the bookshelf: how many books are on it
    const seg = sec.querySelectorAll(".inst-filter .inst-n");
    if (seg.length === 2) return t(T("Active")) + " " + seg[0].textContent + " · " + t(T("Closed")) + " " + seg[1].textContent;
    if (sec.dataset.fold === "library") return t(T("On the shelf")) + ": " + sec.querySelectorAll(".sb-shelf > *").length;
    return "";
  });
}

// ---------------------------------------------------------------- 📜 History: everything that happened, one list
// points and coins (ledger), shop rewards (redemptions) and the family history (games, quiz wins, council decisions …) –
// for one child or everybody, filtered by kind; the newest first
const HIST_KINDS = () => [["all", "📜", T("Everything")], ["points", "🪙", T("Points & coins")], ["rewards", "🎁", T("Rewards")], ["family", "👨‍👩‍👧", T("Games & family")]];
async function historyView(main) {
  const [profiles, accounts] = await Promise.all([call("parent/profiles"), call("parent/accounts")]);
  P.accounts = accounts;
  const people = [...profiles.filter(p => p.role === "kid"), ...profiles.filter(p => p.role !== "kid")];
  if (P.histWho == null) P.histWho = people.length ? String(people[0].id) : "all";
  P.histKind = P.histKind || "all";
  const who = h("select", { "aria-label": T("Profile"), onchange: () => { P.histWho = who.value; load(); } },
    h("option", { value: "all", selected: P.histWho === "all" }, I18N.tr(T("Everybody"))),
    ...people.map(p => h("option", { value: p.id, selected: String(p.id) === P.histWho }, p.name)));
  const kinds = h("div.seg.hist-kinds", { role: "radiogroup", "aria-label": T("Show") });
  const drawKinds = () => kinds.replaceChildren(...HIST_KINDS().map(([k, ic, n]) => h("button" + (P.histKind === k ? ".on" : ""), { type: "button", role: "radio",
    "aria-checked": String(P.histKind === k), onclick: () => { P.histKind = k; drawKinds(); load(); } }, ic + " ", n)));
  drawKinds();
  const box = h("div.hist-box");
  const acc = k => accounts.find(a => a.key === k) || { icon: "", name: k };
  const when = at => new Date(String(at).replace(" ", "T")).toLocaleString(I18N.locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const STATUS = { pending: ["⏳", T("Waiting")], approved: ["✓", T("Approved")], rejected: ["✗", T("Declined")], failed: ["⚠️", T("Failed")] };
  async function rows(p) {
    const k = P.histKind, out = [];
    const [led, red, fam] = await Promise.all([
      k === "all" || k === "points" ? call(`parent/ledger/${p.id}`).catch(() => []) : [],
      k === "all" || k === "rewards" ? call(`parent/redemptions?profile_id=${p.id}`).catch(() => []) : [],
      k === "all" || k === "family" ? api(`community/history?profile_id=${p.id}`).catch(() => []) : []]);
    for (const r of led) {
      const a = acc(r.account);
      out.push({ at: r.at, ic: a.icon || "🪙", who: p.name, txt: I18N.tr(r.reason || r.event || ""),
        extra: (r.amount > 0 ? "+" : "") + fmt(r.amount, 1) + " " + I18N.tr(a.name), cls: r.amount < 0 ? "bad" : "good" });
    }
    for (const r of red) {
      const [sic, sn] = STATUS[r.status] || ["", r.status];
      out.push({ at: r.created_at, ic: r.icon || "🎁", who: p.name, txt: r.name, own: true, extra: "−" + fmt(r.cost) + " · " + sic + " " + I18N.tr(sn) });
    }
    for (const e of fam) { const [ic, txt, extra] = historyText(e); out.push({ at: e.at, ic, who: p.name, txt, own: true, extra: extra || "" }); }
    return out;
  }
  async function load() {
    box.replaceChildren(h("p.muted", "…"));
    const list = (await Promise.all((P.histWho === "all" ? people : people.filter(p => String(p.id) === P.histWho)).map(rows))).flat()
      .sort((a, b) => String(b.at).localeCompare(String(a.at)));
    if (!list.length) return box.replaceChildren(h("p.muted", T("Nothing yet.")));
    const ul = h("ul.list.history"), PAGE = 50;
    let n = 0;
    const more = h("button.btn.small.ghost.history-more", { onclick: () => page() }, T("Show more"));
    const line = e => h("li.row", h("span.big-ic", e.ic), h("span.grow", e.own ? h("span", { translate: "no" }, e.txt) : h("span", e.txt),
        P.histWho === "all" ? h("span.small.muted", { translate: "no" }, " · " + e.who) : null),
      e.extra ? h("b" + (e.cls ? "." + e.cls + "-text" : ""), " ", e.extra) : null, h("span.small.muted", " " + when(e.at)));
    const page = () => { ul.append(...list.slice(n, n + PAGE).map(line)); n += PAGE; more.hidden = n >= list.length; };
    page();
    box.replaceChildren(ul, more);
  }
  main.append(pageHead("📜 " + I18N.tr(T("History"))), h("div.row.wrap.hist-filter", who, kinds), section("📜 " + I18N.tr(T("History")), box));
  load();
}

/** Family › Family view: what children see in the comparison, the sound (was a part of the settings). */
function familyViewSection(s) {
  const vis = h("select", ...[["all", T("Everything")], ["percent", T("Only percentages")], ["goal", T("Only the family goal")]].map(([k, n]) => h("option", { value: k, selected: s.family_visibility === k }, n)));
  const sound = h("input", { type: "checkbox", checked: s.sound !== false });
  return section(T("Family view"), h("label.field", T("What children see in the comparison"), vis), h("label.check", sound, T("Sound on by default")),
    h("div.row", h("button.btn", { onclick: async () => {
      try { await call("parent/settings", { method: "PUT", body: { family_visibility: vis.value, sound: sound.checked } }); toast(T("Saved"), "good"); } catch {}
    } }, "💾 ", T("Save"))));
}

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

// FamilyTime games (community.js familyTimeSection): on/off, the coin price of «fix a game», when the wishes close –
// in the «Family» tab (`inBox`: a small ⚙️ box at the end of the section) and in «Settings» (own section)
function familyTimeSettings(after = null, inBox = false) {
  const box = h("div" + (inBox ? ".game-settings.ftg-settings" : ""), h("p.small.muted", "…"));
  call("parent/settings").then(s => {
    const on = h("input", { type: "checkbox", checked: s.familytime_wishes !== false });
    const price = h("input", { type: "number", min: 0, max: 10000, value: s.familytime_game_price ?? 150 });
    const hours = h("input", { type: "number", min: 0, max: 336, value: s.familytime_vote_hours ?? 24 });
    const save = async () => {
      await call("parent/settings", { method: "PUT", body: { familytime_wishes: on.checked,
        familytime_game_price: Math.max(0, Math.min(10000, Math.round(+price.value || 0))),
        familytime_vote_hours: Math.max(0, Math.min(336, Math.round(+hours.value || 0))) } });
      toast(T("Saved"), "good"); if (after) after();
    };
    box.replaceChildren(inBox ? h("div.small.muted.game-settings-h", "⚙️ ", T("Settings")) : null,
      h("label.check", on, T("Game wishes for FamilyTime (wishes, vote, buying a game)")),
      h("div.field-row",
        h("label.field", h("span", "🪙 ", T("Fix a game: price in coins"), fieldInfo(T("A child pays this to set the game of a FamilyTime that has none yet. 0 = buying is off."))), price),
        h("label.field", h("span", "⏰ ", T("Wishes close (hours before)"), fieldInfo(T("Then the vote starts by itself – one wish is set directly."))), hours)),
      h("button.btn.small", { onclick: () => save().catch(() => {}) }, "💾 ", T("Save")));
  }).catch(() => box.replaceChildren());
  return box;
}

// ---------------------------------------------------------------- games: per game active / without bots / inactive, start, coins, running tables
async function gamesView(main) {
  const me = P.meta.me;
  const [s, profiles, data] = await Promise.all([call("parent/settings"), call("parent/profiles"), call("parent/games")]);
  const access = gameAccess(profiles.filter(p => p.role === "kid"), data);
  // every game folded, always (the page is long on phones; a search opens the games found) – a game running now
  // shows «● running now»; inside: first what to play, then – set apart – its settings (status, coins)
  const runningNow = new Set((await call("parent/games/running").catch(() => [])).map(g => g.game));
  const gsec = (k, title, actions, ...content) => {
    const flat = content.flat(Infinity).filter(x => x != null && x !== false);
    const settings = flat.filter(x => x.classList && x.classList.contains("pj-rewards")), play = flat.filter(x => !settings.includes(x));
    return h("details.card.sec.game-sec", { "data-game": k },
      h("summary.sec-head", h("h2", { "data-ik": (GAME_LIST.find(g => g[0] === k) || [])[2] }, title, runningNow.has(k) ? h("span.chip.run-chip", "● ", T("running now")) : null), h("div.head-actions", ...[].concat(actions)), access.chips(k)),
      play.length ? h("div.game-play", ...play) : null,
      h("div.game-settings", h("div.small.muted.game-settings-h", "⚙️ ", T("Settings")), access.bar(k), ...settings));
  };
  // 🛠️ Custom games: the same structure for each – what it is and how many, «📥 Import» and «+ New» (templates first),
  // the own content (quizzes, photo sets, adventure games), then the settings (status, coins)
  // the same order everywhere: play (family table / alone / ↗ in the app), then the own content under its title with
  // «+ New» (and «📥 Import» where it makes sense) next to that title, then the settings
  const csec = (k, head, contentTitle, ...settings) => {
    const [, ic, name] = GAME_LIST.find(g => g[0] === k);
    const count = h("span.chip.cg-count", "…"), actions = h("div.row.wrap.cg-actions"), list = h("div.cg-list");
    const play = h("div.row.wrap.cg-play-btns"), playRow = h("div.game-play.cg-play", play, head ? Object.assign(head, { className: head.className + " cg-app" }) : null);
    const el = h("details.card.sec.game-sec.cg-sec", { "data-game": k },
      h("summary.sec-head", h("h2", { "data-ik": name }, ic, " ", I18N.tr(name), " ", count, runningNow.has(k) ? h("span.chip.run-chip", "● ", T("running now")) : null),
        access.chips(k)),
      playRow,
      h("div.row.wrap.cg-content-head", h("h3.cg-sub.grow", { "data-ik": "cg." + k }, contentTitle), actions), list,
      h("div.game-settings", h("div.small.muted.game-settings-h", "⚙️ ", T("Settings")), access.bar(k), ...settings));
    return { el, actions, list, play, count: n => { count.textContent = String(n); } };
  };
  const live = h("div"), quizzes = h("div"), bingo = h("div"), poker = h("div"), cardBoxes = { tschau: h("div"), karussell: h("div") }, domino = h("div"), paarjagd = h("div"), werbinich = h("div"), kartenlauf = h("div"), stadtland = h("div"), zeichnen = h("div"), wuerfel = h("div"), heimwaerts = h("div"), jump = h("div"), sternlauf = h("div"), snack = h("div"), verkehr = h("div"), klatsch = h("div"), verboten = h("div"), jass = h("div"), werwolf = h("div"), schach = h("div"), dorfmarkt = h("div"), escape = h("div"), stempeljagd = h("div");
  const langstrecke = h("div");
  const showLive = async () => {
    let st = null; try { st = await call("community/quiz"); } catch {}
    if (!st || st.status === "done") return live.replaceChildren();
    // a running quiz is a card here – it opens full screen only on «Open» (✕ comes back to the card, not into the quiz again)
    const open = () => {
      const box = h("div.quiz-live");
      live.replaceChildren(sectionAdd("🎯 " + I18N.tr(T("Running quiz")), appBtn("quiz"), box));
      quizLive(box, me, () => showLive());
    };
    const end = async () => {
      if (!(await confirmDialog(I18N.tr(T("End the running quiz?"))))) return;
      try { await call("community/quiz/abort", { method: "POST" }); } catch {}
      showLive();
    };
    live.replaceChildren(sectionAdd("🎯 " + I18N.tr(T("Running quiz")), appBtn("quiz"),
      h("div.row.wrap", C("«" + quizTitle(st.title, st.langs) + "»", "strong.grow"),
        h("span.small.muted", I18N.tr((st.players || []).length === 1 ? T("1 playing") : T("{0} playing")).replace("{0}", (st.players || []).length)),
        h("button.btn.small", { onclick: open }, "▶ ", T("Open")),
        h("button.btn.small.ghost", { onclick: end }, "⏹ ", T("End")))));
  };
  // bingo: start it here, lead and play in the full-screen view
  const showBingo = async () => {
    let b = null; try { b = await call("community/bingo"); } catch {}
    const open = () => { const box = h("div.bingo-live"); bingo.replaceChildren(box); bingoLive(box, me, () => render()); };
    bingo.replaceChildren(gsec("bingo", "🎱 Bingo", appBtn("bingo"), b && b.status !== "done"
      ? h("button.btn", { onclick: open }, b.card ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => bingoStartDialog(open) }, "▶ ", T("Start bingo"))]));
  };
  const showPoker = async () => {
    let g = null; try { g = await call("community/poker"); } catch {}
    const open = () => { const box = h("div.poker-live"); poker.replaceChildren(box); pokerLive(box, me, () => render()); };
    poker.replaceChildren(gsec("poker", "🃏 Texas Hold'em", appBtn("poker"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => pokerStartDialog(open) }, "▶ ", T("Open a table"))]));
  };
  const song = h("div");
  const showSong = async () => {
    let g = null; try { g = await call("community/song"); } catch {}
    const open = () => { const b = h("div.song-live"); song.replaceChildren(b); songLive(b, me, () => render()); };
    song.replaceChildren(gsec("song", "🎵 " + I18N.tr(T("Guess the song")), appBtn("song"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => songStartDialog(open) }, "▶ ", T("Open the game"))]));
  };
  const showCards = async kind => {
    let g = null; try { g = await call("community/cards/" + kind); } catch {}
    const box = cardBoxes[kind];
    const open = () => { const b = h("div.cards-live"); box.replaceChildren(b); cardsLive(b, me, () => render(), kind); };
    box.replaceChildren(gsec(kind, CARD_GAMES[kind].icon + " " + CARD_GAMES[kind].title, appBtn(kind), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : h("div.row.wrap", h("button.btn", { onclick: () => cardsStartDialog(kind, false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
          h("button.btn.ghost", { onclick: () => cardsStartDialog(kind, true, open) }, "🤖 ", T("Alone against bots")))));
  };
  const showDomino = async () => {
    let g = null; try { g = await call("community/domino"); } catch {}
    const open = () => { const b = h("div.dm-live"); domino.replaceChildren(b); dominoLive(b, me, () => render()); };
    domino.replaceChildren(gsec("domino", "🁫 Domino", appBtn("domino"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : h("div.row.wrap", h("button.btn", { onclick: () => dominoStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
          h("button.btn.ghost", { onclick: () => dominoStartDialog(true, open) }, "🤖 ", T("Alone against bots")))));
  };
  // Pair Hunt: play, then its own content – the photo sets (shared with the pairs game of the game corner)
  const pjPlay = h("div"), pjSets = h("div"), pjRewards = h("div");
  const cPair = csec("paarjagd", appBtn("paarjagd"), "📷 " + I18N.tr(T("Photo sets")), pjRewards);
  cPair.play.append(pjPlay); cPair.list.append(pjSets);
  paarjagd.append(cPair.el);
  const showPaarjagd = async () => {
    let g = null; try { g = await call("community/paarjagd"); } catch {}
    const open = () => { const b = h("div.pj-live"); paarjagd.replaceChildren(b); paarjagdLive(b, me, () => render()); };
    pjPlay.replaceChildren(g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : h("div.row.wrap", h("button.btn", { onclick: () => paarjagdStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
          h("button.btn.ghost", { onclick: () => paarjagdStartDialog(true, open) }, "🤖 ", T("Alone against bots"))));
    pjRewards.replaceChildren(await gameRewardsRow("paarjagd"));
    const ps = await photoSets(cPair.count);
    cPair.actions.replaceChildren(h("button.btn", { onclick: ps.newDialog }, "+ ", T("New")));
    pjSets.replaceChildren(ps.el);
  };
  const showWerbinich = async () => {
    let g = null; try { g = await call("community/werbinich"); } catch {}
    const open = () => { const b = h("div.wb-live"); werbinich.replaceChildren(b); werbinichLive(b, me, () => render()); };
    werbinich.replaceChildren(gsec("werbinich", "🎭 " + I18N.tr(T("Who am I?")), appBtn("werbinich"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => werbinichStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("werbinich")));
  };
  const showKartenlauf = async () => {
    let g = null; try { g = await call("community/kartenlauf"); } catch {}
    const open = () => { const b = h("div.kl-live"); kartenlauf.replaceChildren(b); kartenlaufLive(b, me, () => render()); };
    kartenlauf.replaceChildren(gsec("kartenlauf", "🏁 " + I18N.tr(T("Card Race")), appBtn("kartenlauf"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => kartenlaufStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => kartenlaufStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("kartenlauf")));
  };
  const showStadtland = async () => {
    let g = null; try { g = await call("community/stadtland"); } catch {}
    const open = () => { const b = h("div.sl-live"); stadtland.replaceChildren(b); stadtlandLive(b, me, () => render()); };
    stadtland.replaceChildren(gsec("stadtland", "🏙️ " + I18N.tr(T("City, Country, River")), appBtn("stadtland"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => stadtlandStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("stadtland")));
  };
  const showZeichnen = async () => {
    let g = null; try { g = await call("community/zeichnen"); } catch {}
    const open = () => { const b = h("div.zr-live"); zeichnen.replaceChildren(b); zeichnenLive(b, me, () => render()); };
    zeichnen.replaceChildren(gsec("zeichnen", "🎨 " + I18N.tr(T("Draw & Guess")), appBtn("zeichnen"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => zeichnenStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("zeichnen")));
  };
  const showWuerfel = async () => {
    let g = null; try { g = await call("community/wuerfel"); } catch {}
    const open = () => { const b = h("div.fw-live"); wuerfel.replaceChildren(b); wuerfelLive(b, me, () => render()); };
    wuerfel.replaceChildren(gsec("wuerfel", "🎲 " + I18N.tr(T("Five Dice")), appBtn("wuerfel"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => wuerfelStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => wuerfelStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("wuerfel")));
  };
  const showHeimwaerts = async () => {
    let g = null; try { g = await call("community/heimwaerts"); } catch {}
    const open = () => { const b = h("div.hw-live"); heimwaerts.replaceChildren(b); heimwaertsLive(b, me, () => render()); };
    heimwaerts.replaceChildren(gsec("heimwaerts", "🏠 " + I18N.tr(T("Homeward")), appBtn("heimwaerts"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => heimwaertsStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => heimwaertsStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("heimwaerts")));
  };
  const showJump = async () => {
    let g = null; try { g = await call("community/jump"); } catch {}
    const open = () => { const b = h("div.ju-live"); jump.replaceChildren(b); jumpLive(b, me, () => render()); };
    jump.replaceChildren(gsec("jump", "🦘 Jump", appBtn("jump"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => jumpStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => jumpStartDialog(true, open) }, JU_ICON, " ", T("Alone")))],
      await gameRewardsRow("jump")));
  };
  const showSternlauf = async () => {
    let g = null; try { g = await call("community/sternlauf"); } catch {}
    const open = () => { const b = h("div.sr-live"); sternlauf.replaceChildren(b); sternlaufLive(b, me, () => render()); };
    sternlauf.replaceChildren(gsec("sternlauf", "🌠 " + I18N.tr(T("Star Runner")), appBtn("sternlauf"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => sternlaufStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => sternlaufStartDialog(true, open) }, SR_ICON, " ", T("Alone")))],
      await gameRewardsRow("sternlauf")));
  };
  const showSnack = async () => {
    let g = null; try { g = await call("community/snack"); } catch {}
    const open = () => { const b = h("div.sn-live"); snack.replaceChildren(b); snackLive(b, me, () => render()); };
    snack.replaceChildren(gsec("snack", "🍔 " + I18N.tr(T("Snack Rush")), appBtn("snack"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => snackStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => snackStartDialog(true, open) }, SN_ICON, " ", T("Alone")))],
      await gameRewardsRow("snack")));
  };
  const showVerkehr = async () => {
    let g = null; try { g = await call("community/verkehr"); } catch {}
    const open = () => { const b = h("div.vk-live"); verkehr.replaceChildren(b); vkLive(b, me, () => render()); };
    verkehr.replaceChildren(gsec("verkehr", "🚦 " + I18N.tr(T("Traffic Cadet")), appBtn("verkehr"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => vkStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => vkStartDialog(true, open) }, VK_ICON, " ", T("Alone")))],
      await gameRewardsRow("verkehr")));
  };
  const showLangstrecke = async () => {
    let g = null; try { g = await call("community/langstrecke"); } catch {}
    let r = {}; try { r = await call("community/langstrecke/rules"); } catch {}
    const open = () => { const b = h("div.le-live"); langstrecke.replaceChildren(b); langstreckeLive(b, me, () => render()); };
    const f = { minutes: leMinutes(r.minutes), weather: leWeather(r.weather ?? 1), difficulty: leDiff(r.difficulty), team_size: leSize(r.team_size) };
    const defaults = h("div.pj-rewards", h("b", "⚙️ ", T("Race defaults")),
      h("div.grid2", h("label.field", T("Race length"), f.minutes), h("label.field", T("Weather"), f.weather),
        h("label.field", T("Difficulty"), f.difficulty), h("label.field", T("People per team"), f.team_size)),
      h("div.row", h("button.btn.small", { onclick: async () => {
        try { await call("community/langstrecke/rules", { method: "PUT", body: { minutes: +f.minutes.value, weather: +f.weather.value, difficulty: f.difficulty.value, team_size: +f.team_size.value } }); toast(T("Saved"), "good"); } catch (e) { toast(e.message, "bad"); }
      } }, T("Save"))));
    langstrecke.replaceChildren(gsec("langstrecke", "🏎️ " + I18N.tr(T("24h Endurance")), appBtn("langstrecke"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => langstreckeStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => langstreckeStartDialog(true, open) }, LE_ICON, " ", T("Alone")))],
      defaults, await gameRewardsRow("langstrecke")));
  };
  const showKlatsch = async () => {
    let g = null; try { g = await call("community/klatsch"); } catch {}
    const open = () => { const b = h("div.kb-live"); klatsch.replaceChildren(b); klatschLive(b, me, () => render()); };
    klatsch.replaceChildren(gsec("klatsch", "👏 " + I18N.tr(T("Clap the Beat")), appBtn("klatsch"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => klatschStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => klatschStartDialog(true, open) }, KB_ICON, " ", T("Alone")))],
      await gameRewardsRow("klatsch")));
  };
  const showVerboten = async () => {
    let g = null; try { g = await call("community/verboten"); } catch {}
    const open = () => { const b = h("div.vw-live"); verboten.replaceChildren(b); verbotenLive(b, me, () => render()); };
    verboten.replaceChildren(gsec("verboten", "🚫 " + I18N.tr(T("Forbidden Words")), appBtn("verboten"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => verbotenStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("verboten")));
  };
  const showJass = async () => {
    let g = null; try { g = await call("community/jass"); } catch {}
    const open = () => { const b = h("div.ja-live"); jass.replaceChildren(b); jassLive(b, me, () => render()); };
    jass.replaceChildren(gsec("jass", "♣️ " + I18N.tr(T("Jass")), appBtn("jass"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => jassStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => jassStartDialog(true, open) }, "🤖 ", T("With 3 bots")))],
      await gameRewardsRow("jass")));
  };
  const showWerwolf = async () => {
    let g = null; try { g = await call("community/werwolf"); } catch {}
    const open = () => { const b = h("div.ww-live"); werwolf.replaceChildren(b); werwolfLive(b, me, () => render()); };
    werwolf.replaceChildren(gsec("werwolf", "🐺 " + I18N.tr(T("Werewolves")), appBtn("werwolf"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("button.btn", { onclick: () => werwolfStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("werwolf")));
  };
  const showSchach = async () => {
    const open = id => { const b = h("div.ch-live"); schach.replaceChildren(b); schachLive(b, me, () => render(), id); };
    schach.replaceChildren(gsec("schach", "♟️ " + I18N.tr(T("Chess")), appBtn("schach"),
      await schachPanel(me, open), await gameRewardsRow("schach")));
  };
  const showDorfmarkt = async () => {
    let g = null; try { g = await call("community/dorfmarkt"); } catch {}
    const open = () => { const b = h("div.mk-live"); dorfmarkt.replaceChildren(b); dorfmarktLive(b, me, () => render()); };
    dorfmarkt.replaceChildren(gsec("dorfmarkt", "🏘️ " + I18N.tr(T("Village Market")), appBtn("dorfmarkt"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => dorfmarktStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => dorfmarktStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("dorfmarkt")));
  };
  const showEscape = async () => {
    let g = null; try { g = await call("community/escape"); } catch {}
    const open = () => { const b = h("div.er-live"); escape.replaceChildren(b); escapeLive(b, me, () => render()); };
    let info = null; try { info = (await call("community/escape/rules")).played; } catch {}
    escape.replaceChildren(gsec("escape", "🗝️ " + I18N.tr(T("Escape Room")), appBtn("escape"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [info ? h("p.small", "🧩 ", I18N.tr(T("{0} of {1} riddles not played yet – round {2}")).replace("{0}", info.new).replace("{1}", info.total).replace("{2}", info.round)) : null,
         h("button.btn", { onclick: () => escapeStartDialog(open) }, "👨‍👩‍👧 ", T("Open a family table"))],
      await gameRewardsRow("escape")));
  };
  const showStempeljagd = async () => {
    let g = null; try { g = await call("community/stempeljagd"); } catch {}
    const open = () => { const b = h("div.sj-live"); stempeljagd.replaceChildren(b); stempeljagdLive(b, me, () => render()); };
    stempeljagd.replaceChildren(gsec("stempeljagd", "🏛️ " + I18N.tr(T("Beat the Bureaucracy")), appBtn("stempeljagd"), g && g.status !== "done"
      ? h("button.btn", { onclick: open }, g.joined ? T("Back to the game") : T("Join"))
      : [h("div.row.wrap", h("button.btn", { onclick: () => stempeljagdStartDialog(false, open) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => stempeljagdStartDialog(true, open) }, "🤖 ", T("Alone against bots")))],
      await gameRewardsRow("stempeljagd")));
  };
  // the small games of the game corner: only the status (they run on the device)
  const arcade = ["ttt", "pingpong", "sudoku", "patience", "slots"].map(k => {
    const [, ic, name] = GAME_LIST.find(g => g[0] === k);
    return h("div", gsec(k, ic + " " + I18N.tr(name), appBtn("arcade/" + k)));
  });
  // the special quiz «Family Quest Facts» (questions from the family's data) – on by default
  const factsOn = h("input", { type: "checkbox", checked: s.quiz_facts !== false, onchange: async () => {
    await call("parent/settings", { method: "PUT", body: { quiz_facts: factsOn.checked } }); toast(T("Saved"), "good"); } });
  const factsSet = h("div.pj-rewards", h("label.check", factsOn, h("span", "📊 ", T("Special quiz «Family Quest Facts»: questions from our own data (chores, games, records, shop, pets) – nothing from the parent area"))));
  const cQuiz = csec("quiz", appBtn("quiz"), "🎯 " + I18N.tr(T("Quizzes")), factsSet);
  cQuiz.list.append(live, quizzes);
  const quiz = h("div", cQuiz.el);
  // adventure games: the ones of the family (stories.js storyShelf, type «game») – approve, edit, import, new
  const cAdv = csec("adventuregame", null, "🗝️ " + I18N.tr(T("Adventure games")));
  cAdv.play.append(h("button.btn", { onclick: () => openInApp("advgames") }, "🧭 ", T("Play alone")));
  const adventuregame = h("div", cAdv.el);
  const blocks = { quiz, adventuregame, bingo, song, tschau: cardBoxes.tschau, karussell: cardBoxes.karussell, domino, paarjagd, werbinich, kartenlauf, stadtland, zeichnen, wuerfel,
    langstrecke,
    heimwaerts, jump, sternlauf, snack, verkehr, klatsch, verboten, jass, werwolf, schach, dorfmarkt, escape, stempeljagd, poker, ...Object.fromEntries(["ttt", "pingpong", "sudoku", "patience", "slots"].map((k, i) => [k, arcade[i]])) };
  // only the games of this app's channel: the server leaves out games still in development (channel.py DEV_GAMES)
  for (const k of Object.keys(blocks)) if (!(k in data.access)) delete blocks[k];
  const custom = h("section.cg-group", h("h2.cg-title", "🛠️ ", T("Custom games")),
    ...CUSTOM_GAMES.filter(k => blocks[k]).map(k => blocks[k]));
  // the other games in the groups of the children's app; a game in no group goes to the game night
  const grouped = new Set(GAME_GROUPS.flatMap(g => g[3]));
  const groups = GAME_GROUPS.map(([id, ic, name, keys], i) => h("section.cg-group.game-group", { "data-group": id }, h("h2.cg-title", ic, " ", name),
    ...[...keys, ...(i ? [] : Object.keys(blocks).filter(k => !grouped.has(k) && !CUSTOM_GAMES.includes(k)))].filter(k => blocks[k]).map(k => blocks[k])));
  for (const [k, el] of Object.entries(blocks)) {
    const g = GAME_LIST.find(x => x[0] === k);
    el.classList.add("game-block");
    el.dataset.find = [k, g ? I18N.tr(g[2]) : "", g ? g[2] : ""].join(" ").toLowerCase();
  }
  // search: filters the games by name – remembered while the page is open
  const search = h("input.pack-search", { type: "search", placeholder: "🔍 " + I18N.tr(T("Search games …")), value: P.gameSearch || "",
    "aria-label": T("Search games …"), oninput: () => { P.gameSearch = search.value; filter(); } });
  const none = noMatch(T("No game found."), () => { search.value = ""; P.gameSearch = ""; filter(); });
  const filter = () => {
    const q = (search.value || "").trim().toLowerCase();
    let shown = 0;
    for (const el of Object.values(blocks)) {
      el.hidden = !!q && !el.dataset.find.includes(q); if (!el.hidden) shown++;
      if (q && !el.hidden) el.querySelectorAll("details.game-sec").forEach(d => { d.open = true; });   // a game searched for opens
    }
    none.hidden = !q || shown > 0;
    custom.hidden = CUSTOM_GAMES.every(k => !blocks[k] || blocks[k].hidden);
    for (const g of groups) g.hidden = !g.querySelector(":scope > .game-block:not([hidden])");
  };
  // for every game: who begins, guests, all on / off
  const starter = h("select", { onchange: async () => { await call("parent/settings", { method: "PUT", body: { game_starter: starter.value } }); toast(T("Saved"), "good"); } },
    ...[["dice", "🎲 " + I18N.tr(T("The dice decides"))], ["leader", "👑 " + I18N.tr(T("Whoever leads the game"))], ["choose", "👉 " + I18N.tr(T("Whoever leads chooses a player"))]]
      .map(([k, n]) => h("option", { value: k, selected: (s.game_starter || "dice") === k }, n)));
  const guests = h("input", { type: "checkbox", checked: s.games_guests !== false, onchange: async () => {
    await call("parent/settings", { method: "PUT", body: { games_guests: guests.checked } }); toast(T("Saved"), "good"); } });
  const general = h("details.card.sec.games-general", h("summary", h("b", { "data-ik": "games.general" }, "⚙️ ", T("For all games"))),
    h("div.row", h("button.btn.small.ghost", { onclick: async () => { await access.allTo("all"); render(); } }, "✓ ", T("All on")),
      h("button.btn.small.ghost", { onclick: async () => { await access.allTo("off"); render(); } }, "✕ ", T("All off"))),
    h("label.field", T("Who begins a game (card and board games)"), starter),
    h("label.check", guests, h("span", T("Guests may join (whoever leads a game shows a QR code; guests type a name and play – nothing else of the app is open to them)"))));
  main.append(h("h1", T("Games")), partyCard(),
    search, general, batterySettingsCard(), runningGamesBox(), custom, none, ...groups);
  filter();
  showLive(); showBingo(); showSong(); showPoker(); showCards("tschau"); showCards("karussell"); showDomino(); showPaarjagd(); showWerbinich(); showKartenlauf(); showStadtland(); showZeichnen(); showWuerfel(); showHeimwaerts(); showJump(); showSternlauf(); showSnack(); showVerkehr(); showKlatsch(); showVerboten(); showJass(); showWerwolf(); showSchach(); showDorfmarkt(); showEscape();
  if (blocks.langstrecke) showLangstrecke();
  if (blocks.stempeljagd) showStempeljagd();
  quizzesPanel(quizzes, me, showLive, { actions: cQuiz.actions, withImport: true, onCount: cQuiz.count, play: cQuiz.play });
  if (blocks.adventuregame) storyShelf(cAdv.list, { types: ["game"], actions: cAdv.actions, onCount: cAdv.count });
}

// live games (Paarjagd, «Wer bin ich?», Kartenlauf, Stadt-Land-Fluss, «Zeichnen & Raten», «Fünf Würfel», «Verbotene Wörter»): coins for places 1 / 2 / 3 (only family tables with at least two people of the family)
// Jass: only place 1 – the coins for each person of the family in the winning team
async function gameRewardsRow(game) {
  let r = {};
  try { r = await call("parent/game-rewards"); } catch {}
  const cur = r[game] || [10, 5, 2];
  const inputs = cur.map(v => h("input.pj-reward", { type: "number", min: 0, max: 1000, step: 1, value: v, inputmode: "numeric" }));
  if (game === "jass" || game === "escape") {
    const save1 = async () => {
      const v = Number(inputs[0].value);
      if (!Number.isInteger(v) || v < 0 || v > 1000) return toast(T("Three numbers of coins (0 to 1000) are needed"), "bad");
      try { await call("parent/game-rewards", { method: "PUT", body: { [game]: [v, cur[1], cur[2]] } }); toast(T("Saved"), "good"); } catch {}
    };
    return h("div.pj-rewards", h("b", "🪙 ", T("Coins for each person of the family in the winning team"),
        fieldInfo(game === "escape" ? T("Only when the team escaped (together: everybody; two teams: the team out first) – at a family table with at least two people of the family, not for guests.")
          : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))),
      h("div.row", inputs[0], h("button.btn.small", { onclick: save1 }, T("Save"))));
  }
  const save = async () => {
    const vals = inputs.map(i => Number(i.value));
    if (vals.some(v => !Number.isInteger(v) || v < 0 || v > 1000)) return toast(T("Three numbers of coins (0 to 1000) are needed"), "bad");
    try { await call("parent/game-rewards", { method: "PUT", body: { [game]: vals } }); toast(T("Saved"), "good"); } catch {}
  };
  // when coins are paid: in the ⓘ of the row (the photo sets of the Paarjagd: in its section of «Custom games», photoSets)
  const rule = game === "schach" ? T("Only the winner gets coins, only after at least 10 own moves – not against the easy bot, not on one device, not against guests.")
    : game === "werwolf" ? T("Werwölfe: everybody of the family on the winning side gets the coins of place 1 – only at a table with at least two people of the family, only for a game played to the end, not for guests.")
    : game !== "paarjagd" ? T("Coins only at a table with at least two people of the family – not for guests.")
    : T("Coins only at a family table with at least two people of the family – not alone against bots, not for guests or bots.");
  return h("div.pj-rewards", h("b", "🪙 ", game === "schach" ? T("Coins for a win: against the family / the hard bot / the normal bot") : T("Coins for place 1 / 2 / 3"), fieldInfo(rule)),
    h("div.row", ...inputs.flatMap((i, k) => [k ? h("span.muted", "/") : null, i]).filter(Boolean), h("button.btn.small", { onclick: save }, T("Save"))));
}

// ---------------------------------------------------------------- Family Planer (built in)
// one-off: take over the data of a Family Planer integration that ran in Home Assistant before
// shopping list: a to-do list of Home Assistant (Bring!, the HA shopping list …) as a smart list in the planner
function shoppingSection() {
  const box = h("div", h("p.small.muted", "…"));
  const load = () => call("planer/shopping").then(r => {
    if (!r.ha) return box.replaceChildren(h("p.small.muted", T("Needs the connection to Home Assistant.")));
    if (!r.lists.length) return box.replaceChildren(h("p.small.muted", T("No to-do list found in Home Assistant. Add the Bring! integration there (Settings › Devices & services).")));
    box.replaceChildren(...(r.lists.some(x => x.bring) ? [] : [h("p.small.muted", T("No Bring! list found – the Bring! integration of Home Assistant brings your shopping lists here."))]),
      ...r.lists.map(x => h("div.row.sec-row", h("span", x.bring ? "🛒" : "☑️"), h("span.grow", C(x.name, "strong"), " ",
          h("span.small.muted", x.bring ? "Bring!" : x.entity_id)),
        x.linked ? h("span.chip.good", "✓ ", T("in the planner"))
          : h("button.btn.small" + (x.bring ? "" : ".ghost"), { onclick: async () => {
              try { await call("planer/shopping", { method: "POST", body: { entity: x.entity_id } }); toast(T("Added to the planner"), "good"); load(); } catch {}
            } }, "+ ", T("Show in the planner")))));
  }).catch(() => box.replaceChildren());
  load();
  return section("🛒 " + I18N.tr(T("Shopping list (Bring!)")),
    box);
}

function planerSection(s) {
  const box = h("div");
  const file = h("input", { type: "file", accept: ".json,application/json,*/*" });
  const show = (sum, go) => box.replaceChildren(h("div.card.restore-box",
    h("p", h("strong", T("Persons")), ": ", C(sum.persons.map(p => `${p.name} (${p.points})`).join(", ") || "–")),
    h("p.small.muted", T("Chores"), ": ", String(sum.chores), " · ", T("Lists"), ": ", String(sum.lists), " · ", T("Rewards"), ": ", String(sum.rewards), " · ", T("To-dos"), ": ", String(sum.todos)),
    h("p.warn-text", T("The planner in Family Quest is replaced by this one. Persons are matched to the profiles by name, new persons become profiles, points are added up. Download a backup first.")),
    h("div.row", h("button.btn.bad", { onclick: async () => {
      if (!(await confirmDialog(I18N.tr(T("Really take over this Family Planer?"))))) return;
      await go(); toast(T("Family Planer taken over"), "good"); setTimeout(() => location.reload(), 800);
    } }, "📥 ", T("Take over now")), h("button.btn.ghost", { onclick: () => { box.replaceChildren(); file.value = ""; } }, T("Cancel")))));
  file.addEventListener("change", async () => {
    const f = file.files[0]; if (!f) return;
    const form = () => { const fd = new FormData(); fd.append("file", f); return fd; };
    let r; try { r = await call("planer/import/file?check=1", { method: "POST", form: form() }); } catch { file.value = ""; return; }
    show(r.summary, () => call("planer/import/file", { method: "POST", form: form() }));
  });
  const found = h("div", h("p.small.muted", "…"));
  call("planer/import/sources").then(r => {
    if (!r.config_visible) return found.replaceChildren(h("p.small.muted", T("The Home Assistant configuration is not visible – update the app, or upload the file below.")));
    if (!r.sources.length) return found.replaceChildren(h("p.small.muted", T("No Family Planer found in Home Assistant.")));
    found.replaceChildren(...r.sources.map(src => h("div.row",
      h("span.grow", "📅 ", C(src.persons.map(p => p.name).join(", ") || src.id), h("span.small.muted", " · ", T("Chores"), ": ", String(src.chores), " · ", new Date(src.modified).toLocaleDateString(I18N.locale))),
      h("button.btn.small", { onclick: () => show(src, () => call("planer/import", { method: "POST", body: { source: src.id } })) }, T("Take over…")))));
  }).catch(() => found.replaceChildren());
  return section("📥 " + I18N.tr(T("Take over an existing Family Planer")),
    found,
    h("label.field", T("…or upload the file family_planer.<id> from /config/.storage"), file), box);
}

// ---------------------------------------------------------------- backup & restore
function backupSection() {
  const file = h("input", { type: "file", accept: ".zip" });
  const info = h("div");
  // in pieces of 4 MB: Home Assistant (ingress) refuses bigger uploads with «HTTP 413»
  const CHUNK = 4 * 1024 * 1024;
  const sendInPieces = async f => {
    const upload = Array.from(crypto.getRandomValues(new Uint8Array(12)), b => b.toString(16).padStart(2, "0")).join("");
    const n = Math.max(1, Math.ceil(f.size / CHUNK));
    for (let i = 0; i < n; i++) {
      info.replaceChildren(h("div.card.restore-box", h("p", "⏫ ", I18N.tr(T("Uploading the backup … {0} %")).replace("{0}", Math.round(i * 100 / n))),
        h("progress", { max: n, value: i, style: { width: "100%" } })));
      const r = await fetch(`api/parent/backup/chunk?upload=${upload}&index=${i}`, { method: "POST",
        headers: { "X-FQ-Parent": Auth.parent, "Content-Type": "application/octet-stream" }, body: f.slice(i * CHUNK, (i + 1) * CHUNK) });
      if (!r.ok) {
        let msg = "HTTP " + r.status; try { msg = (await r.json()).detail || msg; } catch {}
        throw new Error(msg);
      }
    }
    return upload;
  };
  file.addEventListener("change", async () => {
    const f = file.files[0]; if (!f) return;
    let upload, m;
    try {
      upload = await sendInPieces(f);
      m = (await call("parent/backup/inspect-upload", { method: "POST", body: { upload } })).manifest;
    } catch (e) { toast(e.message, "bad"); info.replaceChildren(); file.value = ""; return; }
    info.replaceChildren(restoreBox(m, upload, () => { info.replaceChildren(); file.value = ""; }));
  });
  // what takes how much room – pictures of Home Assistant Media and the app's own packs are not in the backup
  const sizes = h("p.small.muted");
  const mb = n => (n / 1048576).toLocaleString(I18N.locale, { maximumFractionDigits: n < 10485760 ? 1 : 0 }) + " MB";
  call("parent/backup/sizes").then(s => sizes.replaceChildren(
    T("Size of the full backup: about {0}").replace("{0}", mb(s.backup)), " (",
    T("Data"), " ", mb(s.database), " · ", T("Photo sets"), " ", mb(s.photo_sets), " · ",
    T("Pack pictures"), " ", mb(s.pack_pictures), " · ", T("Planner photos"), " ", mb(s.planner_photos), ")")).catch(() => {});
  // Home Assistant's own (automatic) backups: a hint and a way to their settings
  let haUrl = null;
  const haBtn = h("button.btn.ghost", { type: "button", hidden: true, onclick: () => {
    if (!haUrl) return;
    if (P.info && P.info.via_ha) window.top.location.href = haUrl;     // the Home Assistant window around the app
    else window.open(haUrl, "_blank", "noopener");
  } }, "⚙️ ", T("Open backup settings in Home Assistant"));
  haBackupHref().then(u => { haUrl = u; haBtn.hidden = !u; });
  return section("💾 " + I18N.tr(T("Backup & restore")),
    sizes,
    h("div.row.backup-kinds",
      h("button.btn", { onclick: () => downloadBackup("full") }, "⬇️ ", T("Download full backup")),
      h("button.btn.ghost", { onclick: () => downloadBackup("data") }, "⬇️ ", T("Download data backup")),
      h("button.btn.ghost", { onclick: () => downloadBackup("customizing") }, "⬇️ ", T("Download customizing backup"))),
    h("p.small.muted", T("Full: everything. Data: only what the family did (points, progress, games, chores done …). Customizing: settings, profiles and your own content – e.g. to set up a test installation without the data.")),
    h("label.field", T("Restore from a backup file"), file), info,
    h("p.small.ha-backup-hint", { "data-ik": "Automatic backups" }, T("For automatic backups, include Family Quest in the Home Assistant backup settings (Apps).")),
    h("div.row", haBtn));
}

// Home Assistant's backup settings: inside Home Assistant the top window goes there (same origin), from the app's own
// port the address of Home Assistant on this host; without Home Assistant null (no button)
async function haBackupHref() {
  if (P.info && P.info.via_ha) return "/config/backup/settings";
  try { const p = await api("ha-panel"); if (p.port) return `${p.ssl ? "https" : "http"}://${location.hostname}:${p.port}/config/backup/settings`; } catch {}
  return null;
}

// the restore dialog: what kind of backup it is, what it replaces and what stays, how the profiles match
function restoreBox(m, upload, cancel) {
  const kind = m.kind || "full", plan = m.plan || {};
  const when = new Date(m.created).toLocaleString(I18N.locale);
  const KIND = { full: T("Full backup"), data: T("Data backup"), customizing: T("Customizing backup") };
  const USAGE = T("usage data (points, coins, XP, learning progress, games and history, chores done, deals, redemptions, weather, planner, logs)");
  const SETUP = T("profiles and settings");
  const OWN = T("own content (packs, quizzes, books and adventure games, photo sets, shop, rewards, chores, designs, texts, crest, reports and dashboards)");
  const replaces = { full: [SETUP, OWN, USAGE], data: [USAGE], customizing: [SETUP, OWN] }[kind] || [];
  const keeps = { full: [], data: [SETUP, OWN], customizing: [USAGE] }[kind] || [];
  const names = list => list.map(p => p.name).join(", ");
  const li = t => h("li", t);
  const question = { full: T("Really replace all data with this backup?"),
    data: T("Really replace the usage data with this data backup? Profiles, settings and own content stay."),
    customizing: T("Really replace settings, profiles and own content with this customizing backup? The usage data stay.") }[kind];
  return h("div.card.restore-box", { "data-kind": kind },
    h("p", h("strong", "📦 ", KIND[kind] || KIND.full), " · ", T("Backup from {0}").replace("{0}", when), " · Family Quest " + (m.app_version || "?")),
    m.counts ? h("p.small.muted", T("Profiles"), ": ", String((m.profiles || []).length || m.counts.profile || "–"),
      kind === "data" ? null : [" · ", T("Packs"), ": ", String(m.counts.pack ?? "–")]) : null,
    m.compat && m.compat.status === "older" ? h("div.card.warn-box",
      h("p", h("strong", "⚠️ ", T("This backup comes from an older version")), " ",
        I18N.tr(T("(Family Quest {0} – now {1})")).replace("{0}", m.compat.from).replace("{1}", m.compat.to)),
      h("p.small", "✓ ", T("Checked: the backup is not damaged, and the update of its data to the current version worked on a test copy.")),
      h("p.small", T("Things that are new since then start with their standard settings. Please check the profiles, points and packs after restoring.")))
      : h("p.small.muted", "✓ ", T("Checked: the backup is not damaged and fits this version.")),
    h("p.warn-text", T("Replaced:")), h("ul.small.restore-list", ...replaces.map(li)),
    keeps.length ? [h("p", h("strong", T("Stays as it is:"))), h("ul.small.restore-list", ...keeps.map(li))] : null,
    plan.missing && plan.missing.length ? h("div.card.warn-box", h("p.small", "⚠️ ",
      T("These profiles are not here – their entries are skipped: {0}").replace("{0}", names(plan.missing)))) : null,
    plan.renamed && plan.renamed.length ? h("div.card.warn-box", h("p.small", "⚠️ ", T("Profiles are matched by their number. Different names:"), " ",
      plan.renamed.map(r => `${r.backup} → ${r.here}`).join(", "))) : null,
    plan.kept && plan.kept.length ? h("p.small", "👤 ", T("Not in the backup, they stay with their data: {0}").replace("{0}", names(plan.kept))) : null,
    h("p.small.muted", "🏠 ", T("Values of this installation stay (Home Assistant panel path and address, integration token, dashboard link, last backup).")),
    h("p.small.muted", "🛟 ", T("Before restoring, the current data are saved once more as before-restore.zip in the data folder of the app.")),
    h("div.row", h("button.btn.bad", { onclick: async e => {
      if (!(await confirmDialog(question, { danger: true }))) return;
      const btn = e.currentTarget; btn.disabled = true;
      let r;
      try { r = await call("parent/restore-upload", { method: "POST", body: { upload } }); }
      catch { btn.disabled = false; return; }
      const skipped = ((r.manifest || {}).report || {}).skipped || [];
      toast(T("Restored") + (skipped.length ? " · " + T("Skipped (profile not here): {0}").replace("{0}", skipped.map(x => `${x.name} (${x.rows})`).join(", ")) : ""), "good");
      setTimeout(() => location.reload(), skipped.length ? 3000 : 800);
    } }, "♻️ ", T("Restore now")), h("button.btn.ghost", { onclick: cancel }, T("Cancel"))));
}

async function downloadBackup(kind = "full") {
  const r = await fetch("api/parent/backup?kind=" + encodeURIComponent(kind), { headers: { "X-FQ-Parent": Auth.parent } });
  if (!r.ok) return toast(T("Backup failed"), "bad");
  const name = (r.headers.get("content-disposition") || "").match(/filename="([^"]+)"/)?.[1] || "family-quest-backup.zip";
  const url = URL.createObjectURL(await r.blob());
  const a = h("a", { href: url, download: name }); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  if (P.onChange) P.onChange("parent/backup");          // «last backup» in the folded settings
}

// ---------------------------------------------------------------- settings
// ---------------------------------------------------------------- own texts and languages
async function translationsSection() {
  const box = h("div");
  // folded in the settings like every part (setFold)
  const sec = h("section.card.sec", h("h2", "🌐 " + I18N.tr(T("Own texts and languages"))),
    box);
  const nameOf = code => (I18N.LANGS.find(([k]) => k === code) || [code, code])[1];
  let lang = I18N.custom.some(l => l.code === I18N.lang) || I18N.LANGS.some(([k]) => k === I18N.lang) ? I18N.lang : "de-DE";
  async function draw() {
    const info = await call("parent/translations");
    const own = info.languages;
    if (!info.builtin.includes(lang) && !own.some(l => l.code === lang)) lang = "de-DE";
    const sel = h("select", { onchange: () => { lang = sel.value; draw(); } },
      h("optgroup", { label: I18N.tr(T("Languages")) }, ...info.builtin.map(k => h("option", { value: k, selected: k === lang, translate: "no" },
        nameOf(k) + (info.counts[k] ? ` (${info.counts[k]})` : "")))),
      own.length ? h("optgroup", { label: I18N.tr(T("Own languages")) }, ...own.map(l => h("option", { value: l.code, selected: l.code === lang, translate: "no" },
        (l.flag || "🗣️") + " " + l.name + (info.counts[l.code] ? ` (${info.counts[l.code]})` : "")))) : null);
    const cur = own.find(l => l.code === lang);
    const file = h("input", { type: "file", accept: ".csv,text/csv,text/plain", hidden: true, onchange: async () => {
      const f = file.files[0]; if (!f) return;
      try { const r = await call(`parent/translations/${lang}/csv`, { method: "POST", body: { csv: await f.text() } }); toast(I18N.tr(T("{0} own texts imported")).replace("{0}", r.imported), "good"); draw(); }
      catch (e) { toast(e.message, "bad"); }
    } });
    const exportCsv = async () => {
      const r = await fetch(`api/parent/translations/${lang}/csv`, { headers: { "X-FQ-Parent": Auth.parent } });
      if (!r.ok) return toast(T("Export failed"), "bad");
      const url = URL.createObjectURL(await r.blob());
      const a = h("a", { href: url, download: `family-quest-${lang}.csv` }); document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    };
    // new language
    const nName = h("input", { type: "text", placeholder: I18N.tr(T("e.g. Bärndütsch")) });
    const nFlag = h("input", { type: "text", maxlength: 8, placeholder: "🐻", style: "width:4.5em;text-align:center" });
    const nBase = h("select", ...info.builtin.map(k => h("option", { value: k, selected: k === "de-CH", translate: "no" }, nameOf(k))));
    const newLang = h("details.tr-new", h("summary", "＋ ", T("New language")),
      h("div.grid3", h("label.field", T("Name"), nName), h("label.field", T("Symbol"), nFlag), h("label.field", T("Starts from"), nBase)),
      h("button.btn.small", { onclick: async () => {
        try { const l = await call("parent/translations/languages", { method: "POST", body: { name: nName.value, flag: nFlag.value, base: nBase.value } });
          lang = l.code; toast(T("Saved"), "good"); draw(); } catch (e) { toast(e.message, "bad"); }
      } }, T("Create")));
    const langTools = cur ? h("div.row",
      h("span.muted", T("Starts from"), " ", nameOf(cur.base)),
      h("button.btn.small.ghost", { onclick: async () => {
        const n = (await promptDialog(I18N.tr(T("Name")), cur.name)); if (n == null) return;
        const fl = (await promptDialog(I18N.tr(T("Symbol")), cur.flag || "")); if (fl == null) return;
        await call(`parent/translations/languages/${cur.code}`, { method: "PUT", body: { name: n, flag: fl } }); draw();
      } }, "✏️ ", T("Rename")),
      h("button.btn.small.bad", { onclick: async () => {
        if (!(await confirmDialog(I18N.tr(T("Delete this language with all its texts?"))))) return;
        await call(`parent/translations/languages/${cur.code}`, { method: "DELETE" }); lang = "de-DE"; draw();
      } }, "🗑 ", T("Delete"))) : null;

    // texts
    const d = await call(`parent/translations/${lang}`);
    const keys = [...new Set([...d.keys, ...Object.keys(d.own)])];
    const q = h("input", { type: "text", placeholder: I18N.tr(T("Search …")), oninput: () => list() });
    const onlyOwn = h("input", { type: "checkbox", onchange: () => list() });
    const changed = {};
    const rows = h("div.tr-rows");
    const MAX = 60;
    function list() {
      const s = q.value.trim().toLowerCase();
      const hit = keys.filter(k => (!onlyOwn.checked || d.own[k] != null) &&
        (!s || k.toLowerCase().includes(s) || String(d.standard[k] || "").toLowerCase().includes(s) || String(d.own[k] || "").toLowerCase().includes(s)));
      rows.replaceChildren(...hit.slice(0, MAX).map(k => {
        const inp = h("textarea", { rows: 1, placeholder: d.standard[k] || k, translate: "no",
          oninput: () => { changed[k] = inp.value; inp.classList.toggle("tr-changed", true); } });
        inp.value = changed[k] ?? d.own[k] ?? "";
        return h("div.tr-row" + (d.own[k] != null ? ".tr-own" : ""),
          h("div.tr-src", { translate: "no" }, k), h("div.tr-std.small.muted", { translate: "no" }, lang === "en" ? "" : (d.standard[k] || "–")), inp);
      }), hit.length > MAX ? h("p.small.muted", I18N.tr(T("{0} more – narrow the search")).replace("{0}", hit.length - MAX)) : null,
        !hit.length ? h("p.muted", T("Nothing found.")) : null);
    }
    list();
    const save = h("button.btn", { onclick: async () => {
      if (!Object.keys(changed).length) return toast(T("Nothing changed"));
      try {
        await call(`parent/translations/${lang}`, { method: "PUT", body: { texts: changed, merge: true } });
        toast(T("Saved"), "good");
        if (lang === I18N.lang) { if ((await confirmDialog(I18N.tr(T("Reload the page now to see the new texts?"))))) location.reload(); else draw(); } else draw();
      } catch (e) { toast(e.message, "bad"); }
    } }, "💾 ", T("Save texts"));
    box.replaceChildren(
      h("div.row.wrap", h("label.field.grow", T("Language"), sel),
        h("button.btn.small.ghost", { onclick: exportCsv }, "⬇️ ", T("Export CSV")),
        h("button.btn.small.ghost", { onclick: () => file.click() }, "⬆️ ", T("Import CSV")),
        fieldInfo(T("CSV with the columns key and translation (separated by ; or ,). An empty translation goes back to the standard."), { title: T("Import CSV") }), file),
      langTools, newLang,
      h("div.row.wrap", q, h("label.check", onlyOwn, T("Only own texts"))),
      h("div.tr-head.small.muted", h("span", "English"), h("span", T("Standard")), h("span", T("Your text"))),
      rows, save);
  }
  await draw();
  return sec;
}

// ---------------------------------------------------------------- family calendar
const isoDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const EVENT_ICONS = ["🎂", "🏖️", "🎉", "🏫", "⚽", "🎵", "🩺", "✈️", "🎄", "⭐"];
async function calendarView(main) {
  // views: list · day · week · month · year – anchored at P.calDate
  const VIEWS = [["list", T("List")], ["day", T("Day")], ["week", T("Week")], ["month", T("Month")], ["year", T("Year")]];
  const view = P.calView || (innerWidth <= 760 ? "list" : "month");      // phones start with the list
  const anchor = P.calDate ? new Date(P.calDate + "T12:00") : new Date();       // local noon – not UTC midnight
  anchor.setHours(12, 0, 0, 0);
  const addDays = (x, n) => { const y = new Date(x); y.setDate(y.getDate() + n); return y; };
  const monday = x => addDays(x, -((x.getDay() + 6) % 7));
  let from, to;
  if (view === "day") { from = to = anchor; }
  else if (view === "week") { from = monday(anchor); to = addDays(from, 6); }
  else if (view === "year") { from = new Date(anchor.getFullYear(), 0, 1, 12); to = new Date(anchor.getFullYear(), 11, 31, 12); }
  else {
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1, 12), last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0, 12);
    from = view === "month" ? monday(first) : first; to = view === "month" ? addDays(last, 6 - (last.getDay() + 6) % 7) : last;
  }
  const d = await call(`parent/calendar?start=${isoDay(from)}&end=${isoDay(to)}`);
  const evs = d.events;
  const onDay = day => evs.filter(e => e.start.slice(0, 10) <= day && (e.end || e.start).slice(0, 10) >= day);
  const time = e => e.all_day ? "" : fmtTime(e.start) + " ";
  const open = e => e.readonly ? toast("🔒 " + I18N.tr(T("From Home Assistant – read only"))) : eventDialog(e);
  const chip = e => h("button.cal-ev" + (e.readonly ? ".ro" : "") + (e.kind ? "." + e.kind : ""), {
    title: (e.readonly ? "🔒 " + e.calendar + " · " : "") + e.title + (e.game ? " · " + ftGameLine(e.game) : ""), onclick: ev => { ev.stopPropagation(); open(e); } },
    e.icon ? e.icon + " " : "", time(e), C(e.title), e.game ? h("span.cal-game", " · " + e.game.icon + " ", C(ftTitle(e.game))) : null);
  const today = isoDay(new Date());
  const go = (v, date) => { P.calView = v; P.calDate = date ? isoDay(date) : P.calDate; render(); };
  const step = n => {
    const x = new Date(anchor);
    if (view === "day") x.setDate(x.getDate() + n);
    else if (view === "week") x.setDate(x.getDate() + 7 * n);
    else if (view === "year") x.setFullYear(x.getFullYear() + n);
    else x.setMonth(x.getMonth() + n, 1);
    P.calDate = isoDay(x); render();
  };
  const title = view === "day" ? anchor.toLocaleDateString(I18N.locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })
    : view === "week" ? fmtDate(from, { day: "numeric", month: "short" }) + " – " + fmtDate(to, { day: "numeric", month: "short", year: "numeric" })
    : view === "year" ? String(anchor.getFullYear()) : anchor.toLocaleDateString(I18N.locale, { month: "long", year: "numeric" });
  const fmtRange = e => { const a = new Date(e.start.slice(0, 10) + "T12:00"), b = new Date((e.end || e.start).slice(0, 10) + "T12:00");
    const f = x => x.toLocaleDateString(I18N.locale, { weekday: "short", day: "numeric", month: "short" });
    return f(a) + (b > a ? " – " + f(b) : "") + (e.all_day ? "" : " · " + fmtTime(e.start)); };
  const wd = [...Array(7).keys()].map(i => new Date(2024, 0, 1 + i).toLocaleDateString(I18N.locale, { weekday: "short" }));
  const sorted = list => [...list].sort((a, b) => (a.all_day === b.all_day ? 0 : a.all_day ? -1 : 1) || a.start.localeCompare(b.start));

  let body;
  if (view === "month") {
    const cells = [];
    for (let x = new Date(from); x <= to; x = addDays(x, 1)) {
      const day = isoDay(x), other = x.getMonth() !== anchor.getMonth(), list = sorted(onDay(day));
      cells.push(h("div.cal-day" + (other ? ".other" : "") + (day === today ? ".today" : ""), { onclick: () => eventDialog({ start: day, end: day, all_day: true }) },
        h("button.cal-n", { onclick: ev => { ev.stopPropagation(); go("day", x); } }, String(x.getDate())),
        ...list.slice(0, 4).map(chip), list.length > 4 ? h("span.small.muted", "+" + (list.length - 4)) : null));
    }
    body = h("div.cal-grid", ...wd.map(w => h("div.cal-wd", w)), ...cells);
  } else if (view === "week") {
    const cols = [];
    for (let x = new Date(from); x <= to; x = addDays(x, 1)) {
      const day = isoDay(x), list = sorted(onDay(day));
      cols.push(h("div.cal-wcol" + (day === today ? ".today" : ""), { onclick: () => eventDialog({ start: day, end: day, all_day: true }) },
        h("button.cal-whead", { onclick: ev => { ev.stopPropagation(); go("day", x); } }, h("span.small.muted", wd[(x.getDay() + 6) % 7]), h("b", String(x.getDate()))),
        ...list.map(chip)));
    }
    body = h("div.cal-week", ...cols);
  } else if (view === "day") {
    const list = sorted(onDay(isoDay(anchor)));
    const allDay = list.filter(e => e.all_day), timed = list.filter(e => !e.all_day);
    const hours = [...Array(24).keys()].filter(hh => hh >= 6 || timed.some(e => +e.start.slice(11, 13) === hh));
    body = h("div.cal-dayview",
      allDay.length ? h("div.cal-allday", ...allDay.map(chip)) : null,
      ...hours.map(hh => h("div.cal-hour", { onclick: () => eventDialog({ start: isoDay(anchor) + "T" + String(hh).padStart(2, "0") + ":00",
          end: isoDay(anchor) + "T" + String(Math.min(23, hh + 1)).padStart(2, "0") + ":00", all_day: false }) },
        h("span.cal-hh", fmtTime(new Date(2024, 0, 1, hh))), h("div.grow", ...timed.filter(e => +e.start.slice(11, 13) === hh).map(chip)))));
  } else if (view === "year") {
    body = h("div.cal-year", ...[...Array(12).keys()].map(mi => {
      const f = new Date(anchor.getFullYear(), mi, 1, 12), l = new Date(anchor.getFullYear(), mi + 1, 0, 12);
      const cells = [...Array((f.getDay() + 6) % 7)].map(() => h("span"));
      for (let x = new Date(f); x <= l; x = addDays(x, 1)) {
        const day = isoDay(x), n = onDay(day).length;
        cells.push(h("button.cal-yd" + (n ? ".has" : "") + (day === today ? ".today" : ""), { title: n ? onDay(day).map(e => e.title).join(", ") : "", onclick: () => go("day", x) }, String(x.getDate())));
      }
      return h("div.cal-ymonth", h("button.cal-ytitle", { onclick: () => go("month", f) }, f.toLocaleDateString(I18N.locale, { month: "long" })),
        h("div.cal-ygrid", ...wd.map(w => h("span.cal-ywd", w.slice(0, 2))), ...cells));
    }));
  } else {
    const list = sorted(evs).sort((a, b) => a.start.localeCompare(b.start));
    body = h("ul.cal-list", ...list.map(e => h("li.row", { onclick: () => open(e) },
      h("span.cal-when", fmtRange(e)), h("span.grow", e.icon ? e.icon + " " : "", C(e.title),
        e.game ? [h("br"), h("span.small.ftg-line", e.game.icon + " ", C(ftGameLine(e.game)))] : null), e.readonly ? h("span.small.muted", "🔒 ", C(e.calendar)) : null)),
      !list.length ? h("li.muted", T("No events this month.")) : null);
  }
  main.append(
    pageHead(["📅 ", T("Calendar")],
      h("button.btn.ghost", { onclick: () => eventDialog({ kind: "familytime", start: today + "T18:00", end: today + "T20:00", all_day: false }) }, "+ 👨‍👩‍👧 FamilyTime"),
      h("button.btn.ghost", { onclick: () => eventDialog({ kind: "offlinetime", start: today + "T14:00", end: today + "T17:00", all_day: false, options: { internet: true, games: true } }) }, "+ 📵 OfflineTime"),
      h("button.btn", { onclick: () => eventDialog({ start: today, end: today, all_day: true }) }, "+ ", T("New event"))),
    h("section.card.sec",
      h("div.row.wrap.cal-head",
        h("div.seg.cal-views", ...VIEWS.map(([k, n]) => h("button" + (k === view ? ".on" : ""), { onclick: () => go(k) }, n))),
        h("div.row.grow.cal-nav", h("button.icon-btn", { onclick: () => step(-1), title: T("Back") }, "‹"), h("h2.grow.center", title),
          h("button.btn.small.ghost", { onclick: () => { P.calDate = null; render(); } }, T("Today")), h("button.icon-btn", { onclick: () => step(1), title: T("Next") }, "›"))),
      body),
    await holidaySection(), importSection(d.sources), haCalendarSection(d.settings));
}

function eventDialog(e) {
  const isNew = !e.id;
  const title = h("input", { type: "text", maxlength: 120, value: e.title || "", placeholder: I18N.tr(T("e.g. Ski camp")) });
  const allDay = h("input", { type: "checkbox", checked: e.all_day !== false });
  const from = h("input"), to = h("input");
  const setType = () => {
    const t = allDay.checked ? "date" : "datetime-local";
    const conv = v => allDay.checked ? (v || "").slice(0, 10) : ((v || "").length > 10 ? v : (v || "") + "T09:00");
    from.type = t; to.type = t; from.value = conv(from.value || e.start); to.value = conv(to.value || e.end || e.start);
  };
  setType(); allDay.onchange = setType;
  const icon = h("input.weather-icon", { type: "text", maxlength: 8, value: e.icon || "" });
  const note = h("input", { type: "text", maxlength: 500, value: e.note || "", placeholder: I18N.tr(T("Note (optional)")) });
  // the kind: an ordinary event, FamilyTime (highlighted with a countdown) or OfflineTime (internet / games off)
  const KINDS = { event: [T("Event"), ""], familytime: ["FamilyTime", "👨‍👩‍👧"], offlinetime: ["OfflineTime", "📵"] };
  let kind = KINDS[e.kind] ? e.kind : (e.kind || "event");
  const o = Object.assign({ internet: false, games: false, profiles: [] }, e.options || {});
  const offBox = h("div.form.offline-opts");
  let kids = (P.profiles || []).filter(p => p.role === "kid");
  if (!P.profiles) call("parent/profiles").then(l => { P.profiles = l; kids = l.filter(p => p.role === "kid"); drawOff(); }).catch(() => {});
  const drawOff = () => offBox.replaceChildren(...(kind !== "offlinetime" ? [] : [
    h("b", T("During the OfflineTime"), fieldInfo(T("Without a tick it is only a notice in the calendar and on the start page."))),
    h("label.check", h("input", { type: "checkbox", checked: o.internet, onchange: ev => { o.internet = ev.target.checked; } }), "🌐 ", T("Internet off (the internet time cannot be started)")),
    h("label.check", h("input", { type: "checkbox", checked: o.games, onchange: ev => { o.games = ev.target.checked; } }), "🎲 ", T("Games of the app locked (learning stays open)")),
    kids.length ? h("div.row.wrap", h("span.small", T("For:")), ...kids.map(k => h("label.check", h("input", { type: "checkbox", checked: o.profiles.includes(k.id),
      onchange: ev => { o.profiles = ev.target.checked ? [...o.profiles, k.id] : o.profiles.filter(x => x !== k.id); } }), C(k.name))),
      h("span.small.muted", T("(none ticked = all children)"))) : null].filter(Boolean)));
  const kindSel = h("div.pin-kind");
  const drawKind = () => kindSel.replaceChildren(...Object.entries(KINDS).filter(([k]) => k === kind || ["event", "familytime", "offlinetime"].includes(kind))
    .map(([k, [n, ic]]) => h("button.btn.small" + (kind === k ? "" : ".ghost"), { type: "button", onclick: () => {
      if (!icon.value || Object.values(KINDS).some(x => x[1] === icon.value)) icon.value = ic;
      if (!title.value || Object.values(KINDS).some(x => x[0] === title.value)) title.value = k === "event" ? "" : n;
      kind = k; drawKind(); drawOff(); } }, ic ? ic + " " : "", I18N.tr(n))));
  if (isNew && kind !== "event" && !title.value) { title.value = KINDS[kind][0]; icon.value = KINDS[kind][1]; }
  drawKind(); drawOff();
  const m = modal(h("div.form", h("h2", isNew ? T("New event") : T("Edit event")),
    ["event", "familytime", "offlinetime"].includes(kind) ? kindSel : null,
    h("label.field", T("Title"), title),
    h("label.check", allDay, T("All day")),
    h("div.grid2", h("label.field", T("From"), from), h("label.field", T("To"), to)),
    h("label.field", T("Symbol"), h("div.row.wrap", icon, ...EVENT_ICONS.map(ic => h("button.icon-btn", { type: "button", onclick: () => { icon.value = ic; } }, ic)))),
    offBox, note,
    e.game ? h("p.small.ftg-line", e.game.icon + " ", C(ftGameLine(e.game)), " · ", h("button.link.small", { type: "button", onclick: () => { m.close(); P.tab = "community"; location.hash = "community"; render(); } }, T("FamilyTime games ›"))) : null,
    h("div.row", h("button.btn", { onclick: save }, T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")), h("span.grow"),
      !isNew ? h("button.btn.small.bad", { onclick: async () => { if (!(await confirmDialog(I18N.tr(T("Delete this event?"))))) return; await call(`parent/calendar/${e.id}`, { method: "DELETE" }); m.close(); render(); } }, "🗑 ", T("Delete")) : null)));
  title.focus();
  async function save() {
    const body = { title: title.value, start: from.value, end: to.value || from.value, icon: icon.value, note: note.value, kind,
      color: kind === "familytime" ? "#f59f00" : kind === "offlinetime" ? "#495057" : (e.color || ""), options: kind === "offlinetime" ? o : {} };
    try { await call(isNew ? "parent/calendar" : `parent/calendar/${e.id}`, { method: isNew ? "POST" : "PUT", body }); m.close(); toast(T("Saved"), "good"); render(); }
    catch {}
  }
}

// preview of events to take over: checkboxes, duplicates are marked and not chosen
function eventPreview(events, source, done) {
  const box = h("div.cal-preview");
  const sel = events.map(e => !e.duplicate);
  const btn = h("button.btn");
  const count = () => { const n = sel.filter(Boolean).length; btn.textContent = I18N.tr(T("Take over {0} events")).replace("{0}", n); btn.disabled = !n; };
  box.append(h("ul.list", ...events.map((e, i) => h("li.row" + (e.duplicate ? ".dup" : ""),
    h("input", { type: "checkbox", checked: sel[i], onchange: ev => { sel[i] = ev.target.checked; count(); } }),
    h("span.cal-when", fmtDate(e.start.slice(0, 10)) + (e.end && e.end.slice(0, 10) !== e.start.slice(0, 10) ? " – " + fmtDate(e.end.slice(0, 10)) : "")
      + (e.all_day === false ? " · " + fmtTime(e.start) : "")),
    h("span.grow", e.icon ? e.icon + " " : "", C(e.title)), e.duplicate ? h("span.chip.warn", T("already in the calendar")) : null))),
    h("div.row", btn, h("button.btn.ghost", { onclick: () => box.remove() }, T("Cancel"))));
  btn.onclick = async () => {
    const r = await call("parent/calendar/import", { method: "POST", body: { events: events.filter((e, i) => sel[i]), source } });
    toast(I18N.tr(T("{0} events added")).replace("{0}", r.added) + (r.duplicates ? " · " + I18N.tr(T("{0} duplicates skipped")).replace("{0}", r.duplicates) : ""), "good");
    done ? done() : render();
  };
  count();
  return box;
}

async function holidaySection() {
  let cantons = {}; try { cantons = await call("parent/calendar/cantons"); } catch {}
  let last = "CH-TG"; try { last = localStorage.getItem("fq.canton") || last; } catch {}
  const canton = h("select", { translate: "no" }, ...Object.entries(cantons).map(([k, n]) => h("option", { value: k, selected: k === last }, n)));
  const y = new Date().getFullYear();
  const year = h("select", ...[y, y + 1, y + 2].map(v => h("option", { value: v }, String(v))));
  const school = h("input", { type: "checkbox", checked: true }), pub = h("input", { type: "checkbox", checked: true });
  const out = h("div");
  const lang = ({ de: "DE", fr: "FR", it: "IT" })[(I18N.base || "de").slice(0, 2)] || "EN";
  return section("🏖️ " + I18N.tr(T("Templates: school and public holidays")),
    h("div.grid3", h("label.field", T("Canton"), canton), h("label.field", T("Year"), year)),
    h("div.row.wrap", h("label.check", school, T("School holidays")), h("label.check", pub, T("Public holidays")),
      h("button.btn", { onclick: async () => {
        try { localStorage.setItem("fq.canton", canton.value); } catch {}
        out.replaceChildren(h("p.small.muted", "…"));
        try {
          const list = await call(`parent/calendar/holidays?canton=${canton.value}&year=${year.value}&school=${school.checked}&public=${pub.checked}&lang=${lang}`);
          out.replaceChildren(list.length ? eventPreview(list, `holidays:${canton.value}:${year.value}`) : h("p.muted", T("Nothing found.")));
        } catch { out.replaceChildren(); }
      } }, "👀 ", T("Preview"))), out);
}

function importSection(sources) {
  const file = h("input", { type: "file", accept: ".csv,.ics,.ical,text/csv,text/calendar" });
  const out = h("div");
  file.addEventListener("change", async () => {
    const f = file.files[0]; if (!f) return;
    try {
      const list = await call("parent/calendar/parse", { method: "POST", body: { name: f.name, text: await f.text() } });
      out.replaceChildren(list.length ? eventPreview(list, "file:" + f.name, () => { file.value = ""; render(); }) : h("p.muted", T("No events found in the file.")));
    } catch { file.value = ""; }
  });
  return section("📥 " + I18N.tr(T("Import a calendar file")),
    file, out,
    sources.length ? h("div", h("h3", T("Imports")), h("ul.list", ...sources.map(src => h("li.row",
      h("span.grow", C(src.source.replace(/^holidays:/, "🏖️ ").replace(/^file:/, "📄 ")), h("span.small.muted", " · " + src.n + " · " + fmtDate(src.first.slice(0, 10)) + " – " + fmtDate(src.last.slice(0, 10)))),
      h("button.btn.small.ghost", { onclick: async () => {
        if (!(await confirmDialog(I18N.tr(T("Remove all {0} events of this import?")).replace("{0}", src.n)))) return;
        await call(`parent/calendar/source/${encodeURIComponent(src.source)}`, { method: "DELETE" }); render();
      } }, "🗑 ", T("Remove")))))) : null);
}

function haCalendarSection(settings) {
  const chosen = new Set(settings.ha_calendars || []);
  const list = h("div.row.wrap", h("span.small.muted", "…"));
  if (P.meta.ha) call("parent/ha/entities?domain=calendar").then(cals => list.replaceChildren(...(cals.length ? cals.map(c => h("label.check",
    h("input", { type: "checkbox", checked: chosen.has(c.entity_id), onchange: e => e.target.checked ? chosen.add(c.entity_id) : chosen.delete(c.entity_id) }),
    C(c.name || c.entity_id))) : [h("p.small.muted", T("No calendars found in Home Assistant."))]))).catch(() => list.replaceChildren());
  else list.replaceChildren(h("p.small.muted", T("Home Assistant is not connected")));
  return section("🏠 " + I18N.tr(T("Calendars from Home Assistant")),
    list, h("button.btn.small", { onclick: async () => { await call("parent/calendar/settings", { method: "PUT", body: { ha_calendars: [...chosen] } }); toast(T("Saved"), "good"); render(); } }, "💾 ", T("Save")));
}

// ---------------------------------------------------------------- kiosk dashboard
const DASH_WIDGETS = [
  ["clock", "🕒", T("Clock and date")], ["weather_alarm", "🌂", T("Weather alarm (what to take along today)")], ["crown", "👑", T("Crown")], ["weather", "⛅", T("Weather of each child")],
  ["learning", "⭐", T("Learning progress (daily goal, level)")], ["streak", "🔥", T("Streak")], ["coins", "🪙", T("Coins and other points")],
  ["chores", "🧹", T("Open chores of today")], ["family_goal", "🤝", T("Family goal")], ["todos", "✅", T("Open to-dos (Planer)")],
  ["events", "📅", T("Events (family calendar and Home Assistant calendars)")]];
async function dashboardView(main) {
  const [c, profiles] = await Promise.all([call("parent/dashboard"), call("parent/profiles")]);
  const kids = profiles.filter(p => p.role === "kid");
  const on = h("input", { type: "checkbox", checked: c.enabled });
  const title = h("input", { type: "text", value: c.title, maxlength: 60 });
  const theme = h("select", ...[["auto", T("Like the device")], ["light", T("Light")], ["dark", T("Dark")]].map(([k, n]) => h("option", { value: k, selected: c.theme === k }, n)));
  const refresh = h("input", { type: "number", min: 15, max: 3600, value: c.refresh });
  const kidSel = new Set(c.kids.length ? c.kids : kids.map(k => k.id));
  const kidBox = h("div.row.wrap", ...kids.map(k => h("label.check", h("input", { type: "checkbox", checked: kidSel.has(k.id),
    onchange: e => e.target.checked ? kidSel.add(k.id) : kidSel.delete(k.id) }), avatarSvg(k.avatar, 28), " ", C(k.name))));
  const wSel = new Set(c.widgets);
  const wBox = h("div.dash-widgets", ...DASH_WIDGETS.map(([k, ic, n]) => h("label.check", h("input", { type: "checkbox", checked: wSel.has(k),
    onchange: e => { e.target.checked ? wSel.add(k) : wSel.delete(k); calBox.hidden = !wSel.has("events"); } }), ic + " ", n)));
  const calSel = new Set(c.calendars);
  const calBox = h("div", { hidden: !wSel.has("events") }, h("h3", { "data-ik": "dash.calendars" }, "📅 ", T("Calendars")));
  if (P.meta.ha) call("parent/ha/entities?domain=calendar").then(list => calBox.append(list.length
    ? h("div.row.wrap", ...list.map(e => h("label.check", h("input", { type: "checkbox", checked: calSel.has(e.entity_id),
        onchange: ev => ev.target.checked ? calSel.add(e.entity_id) : calSel.delete(e.entity_id) }), C(e.name || e.entity_id))))
    : h("p.small.muted", T("No calendars found in Home Assistant.")))).catch(() => {});
  else calBox.append(h("p.small.muted", T("Home Assistant is not connected")));
  // weather alarm: a weather entity of Home Assistant
  const wxEnt = entitySelect(c.weather_entity, ["weather"]);
  const wxHours = h("select", ...[6, 12, 24].map(v => h("option", { value: v, selected: c.weather_hours === v }, I18N.tr(T("next {0} hours")).replace("{0}", v))));
  const wxRain = h("select", ...[30, 40, 50, 60, 70].map(v => h("option", { value: v, selected: c.rain_chance === v }, v + " %")));
  const wxKids = h("input", { type: "checkbox", checked: c.kids_alarm !== false });
  const wxBox = h("div", h("h3", { "data-ik": "dash.weather" }, "🌂 ", T("Weather alarm")),
    h("div.grid3", h("label.field", T("Weather entity"), wxEnt), h("label.field", T("Look ahead"), wxHours), h("label.field", T("Rain hint from a chance of"), wxRain)),
    h("label.check", wxKids, T("Also on the children's start page")));
  // link for the kiosk browser: the home network address (like the tablet link), plus the key
  const url = h("input", { type: "url", spellcheck: false, readonly: true, onfocus: e => e.target.select() });
  const qr = h("div.qr-box");
  let base = `http://${location.hostname}:8099/`;
  const drawLink = key => { url.value = key ? base + "dashboard?key=" + key : ""; qr.replaceChildren(url.value ? qrSvg(url.value) : ""); };
  call("parent/direct-access").then(d => { base = `http://${(d.ips && d.ips[0]) || location.hostname}:${d.port || d.default_port || 8099}/`; drawLink(c.key); }).catch(() => drawLink(c.key));
  drawLink(c.key);
  const linkSec = section("🔗 " + I18N.tr(T("Link for the kiosk browser")),
    h("p.small.muted", T("Open this link in any browser on a wall tablet, TV or old phone – no login needed. Whoever has the link sees the dashboard, so only use it at home. Add &lang=fr-FR for a fixed language.")),
    c.key ? h("div.qr-row", qr, h("div.grow", h("label.field", T("Address"), url),
      h("div.row.wrap",
        h("a.btn", { href: "dashboard?key=" + encodeURIComponent(c.key), target: "_blank", rel: "noopener" }, "👀 ", T("Open")),
        h("button.btn.ghost", { onclick: async () => {
          if (!(await confirmDialog(I18N.tr(T("Make a new link? Screens with the old link stop showing the dashboard."))))) return;
          await call("parent/dashboard/key", { method: "POST" }); toast(T("New link made"), "good"); render();
        } }, "🔄 ", T("New link")))))
      : h("p.muted", T("Switch the dashboard on and save – then the link appears here.")));
  main.append(h("h1", "🖥️ ", T("Dashboard")),
    section("⚙️ " + I18N.tr(T("What the dashboard shows")),
      h("label.check", on, h("strong", T("Dashboard on"))),
      h("div.grid3", h("label.field", T("Title"), title), h("label.field", T("Look"), theme), h("label.field", T("Refresh every … seconds"), refresh)),
      h("h3", { "data-ik": "dash.children" }, "🧒 ", T("Children")), kidBox,
      h("h3", { "data-ik": "dash.content" }, "🧩 ", T("Content")), wBox,
      h("p.small.muted", "ℹ️ ", T("The weather is otherwise only seen by each child itself – on the dashboard everybody sees it. Moods and texts to the parents are never shown.")),
      calBox, wxBox,
      h("button.btn", { onclick: async () => {
        try {
          await call("parent/dashboard", { method: "PUT", body: { enabled: on.checked, title: title.value, theme: theme.value, refresh: +refresh.value,
            kids: kidSel.size === kids.length ? [] : [...kidSel], widgets: DASH_WIDGETS.map(x => x[0]).filter(k => wSel.has(k)), calendars: [...calSel],
            weather_entity: wxEnt.value, weather_hours: +wxHours.value, rain_chance: +wxRain.value, kids_alarm: wxKids.checked } });
          toast(T("Saved"), "good"); render();
        } catch (e) { toast(e.message, "bad"); }
      } }, "💾 ", T("Save"))),
    linkSec);
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

/** The status texts of the folded settings – fetched fresh (after every change on the page too). */
async function settingsStatus(main) {
  const get = path => api(path).catch(() => null);
  const [s, mem, link, themes, weather, haApp, integ, tr, backup, shop, planer] = await Promise.all([
    get("parent/settings"), get("parent/memory"), get("parent/direct-access"), get("parent/themes"), get("parent/weather"),
    get("parent/ha-app-login"), get("parent/integration"), get("parent/translations"), get("parent/backup/sizes"),
    get("planer/shopping"), get("planer/import/sources")]);
  const t = k => I18N.tr(k), f = (k, ...v) => v.reduce((a, x, i) => a.split("{" + i + "}").join(String(x)), I18N.tr(k));
  const n = (one, many, x) => x === 1 ? t(one) : f(many, x);
  const st = {};
  if (s) {
    const vis = { percent: T("Only percentages"), goal: T("Only the family goal") }[s.family_visibility] || T("Everything");
    st.family = f(T("Comparison: {0}"), t(vis)) + " · " + t(s.sound !== false ? T("Sound on") : T("Sound off"));
    const ha = [s.reminder_time ? f(T("Learning reminder {0}"), s.reminder_time) : null,
      s.chore_reminder_time ? f(T("Chore reminder {0}"), s.chore_reminder_time) : null,
      s.notify_service ? t(T("Push for approvals")) : null].filter(Boolean);
    st.ha = [P.meta.ha ? null : t(T("Not connected")), ...(ha.length ? ha : [t(T("No reminders"))])].filter(Boolean).join(" · ");
    st.learning = f(T("Perfect lesson: {0} coins"), s.lesson_perfect_coins ?? 5) + " · " + f(T("Pet food: {0} coins"), s.pet_food_cost ?? 2);
    const lv = s.levels || [];
    st.levels = lv.length ? f(T("{0} levels · the highest from {1} XP"), lv.length, Number(lv[lv.length - 1]).toLocaleString(I18N.locale)) : "";
    const price = s.familytime_game_price ?? 150;
    st.familytime = s.familytime_wishes === false ? t(T("Game wishes off"))
      : price > 0 ? f(T("Game wishes on · fix a game: {0} coins"), price) : t(T("Game wishes on"));
    st.halogin = [P.meta.my_ha_user ? f(T("Linked with «{0}»"), P.meta.my_ha_user) : t(T("Not linked")),
      haApp ? t(haApp.on ? T("app sign-in on") : T("app sign-in off")) : null,
      s.parent_ha_only ? t(T("parent area only in Home Assistant")) : null].filter(Boolean).join(" · ");
    const nets = (s.allowed_networks || []).length + (s.parent_networks || []).length, guests = (s.guest_networks || []).length;
    st.network = (nets ? n(T("IP restriction active (1 network)"), T("IP restriction active ({0} networks)"), nets) : t(T("No restrictions")))
      + (guests ? " · " + n(T("1 guest network"), T("{0} guest networks"), guests) : "");
  }
  if (mem) {
    const c = mem.crest;
    st.crest = !c ? t(T("No family crest")) : [t(c.image ? T("Own picture") : T("Drawn crest")), c.name || null].filter(Boolean).join(" · ");
  }
  if (link) st.link = link.enabled ? `${(link.ips && link.ips[0]) || location.hostname}:${link.port || link.default_port || 8099}` : t(T("Direct access is off"));
  if (themes) {
    const on = themes.designs.filter(x => x.on).length, a = themes.active;
    st.themes = f(T("{0} of {1} designs on"), on, themes.designs.length) + (a ? " · " + (a.icon || "") + " " + (a.builtin ? t(a.name) : a.name) : "");
  }
  if (weather) st.weather = weather.config.enabled ? f(T("On · {0} weather levels"), weather.config.levels.length) : t(T("Off"));
  if (integ) st.integration = !integ.enabled ? t(T("Off"))
    : t(integ.component && integ.component.installed ? T("On · installed in Home Assistant") : T("On · not installed in Home Assistant yet"));
  if (tr) {
    const lang = (I18N.LANGS.find(([k]) => k === I18N.lang) || [])[1] || (tr.languages.find(l => l.code === I18N.lang) || {}).name || I18N.lang;
    const own = tr.languages.length, texts = Object.values(tr.counts || {}).reduce((a, b) => a + b, 0);
    st.texts = [lang, own ? n(T("1 own language"), T("{0} own languages"), own) : null,
      texts ? n(T("1 own text"), T("{0} own texts"), texts) : t(T("No own texts"))].filter(Boolean).join(" · ");
  }
  if (backup) {
    const mb = x => (x / 1048576).toLocaleString(I18N.locale, { maximumFractionDigits: x < 10485760 ? 1 : 0 }) + " MB";
    st.backup = (backup.last_backup ? f(T("Last backup: {0}"), fmtDate(backup.last_backup)) : t(T("No backup yet"))) + " · ≈ " + mb(backup.backup || 0);
  }
  if (shop) {
    const linked = shop.lists.filter(x => x.linked);
    st.shopping = !shop.ha ? t(T("Needs Home Assistant")) : linked.length ? f(T("In the planner: {0}"), linked.map(x => x.name).join(", "))
      : shop.lists.length ? t(T("Not in the planner yet")) : t(T("No to-do list found"));
  }
  if (planer) st.planer = !planer.config_visible ? t(T("Only from a file"))
    : planer.sources.length ? f(T("Found in Home Assistant: {0}"), planer.sources.length) : t(T("Nothing found in Home Assistant"));
  st.about = "Family Quest v" + P.meta.version + " · " + (P.meta.ha ? "Home Assistant ✓" : t(T("without Home Assistant")));
  for (const el of main.querySelectorAll(".set-status[data-set]")) {
    const v = st[el.dataset.set];
    if (v != null) { el.textContent = v; el.title = v; }
    else if (el.textContent === "…") el.textContent = "";
  }
}

async function settingsView(main) {
  const s = await call("parent/settings");
  let notifyOpts = [];
  if (P.meta.ha) { try { notifyOpts = await call("parent/ha/entities?domain=notify"); } catch {} }
  const f = {
    reminder_time: h("input", { type: "text", placeholder: "17:30", value: s.reminder_time || "" }),
    chore_reminder_time: h("input", { type: "text", placeholder: "18:00", value: s.chore_reminder_time || "" }),
    notify_service: h("input", { type: "text", placeholder: "notify.mobile_app_phone", value: s.notify_service || "", list: "notify-list" }),
    planer_points: h("input", { type: "checkbox", checked: !!s.planer_points }),
    planer_points_factor: h("input", { type: "number", step: "0.1", min: 0, value: s.planer_points_factor ?? 1 }),
    levels: h("input", { type: "text", value: (s.levels || []).join(", ") }),
    lesson_perfect_coins: h("input", { type: "number", min: 0, max: 1000, value: s.lesson_perfect_coins ?? 5 }),
    pet_food_cost: h("input", { type: "number", min: 0, max: 100, value: s.pet_food_cost ?? 2 }),
    pet_hotel_cost: h("input", { type: "number", min: 0, max: 1000, value: s.pet_hotel_cost ?? 10 }),
    hamster_coins_per_day: h("input", { type: "number", min: 0, max: 1000, value: s.hamster_coins_per_day ?? 15 }),
    pet_shop_currency: h("select", ...[["coins", T("Coins")], ["xp", "XP"], ["mixed", T("Both (the child chooses)")]]
      .map(([k, n]) => h("option", { value: k, selected: (s.pet_shop_currency || "coins") === k }, n))),
  };
  const dl = h("datalist#notify-list", ...notifyOpts.map(o => h("option", { value: o.entity_id })));
  const saveBtn = () => h("div.row", h("button.btn", { onclick: () => save().catch(() => {}) }, "💾 ", T("Save")));
  const fold = (id, title, sec) => setFold(id, title, sec);
  // four groups, each a heading with its ⓘ and its folds; the fold ids (data-set) stay as they were
  const group = (ik, icon, title) => h("h2.set-group", { "data-ik": ik }, icon + " ", title);
  main.append(h("h1", T("Settings")),
    group("set.app", "📱", T("App")),
    fold("link", "📱 " + I18N.tr(T("Link for tablets and phones")), linkSection()),
    fold("themes", "🎨 " + I18N.tr(T("Season, time of day & weather designs")), themesSection()),
    fold("levels", T("Levels"), section(T("Levels"), h("label.field", T("XP needed per level (comma separated)"), f.levels), saveBtn())),
    fold("learning", "📚 " + I18N.tr(T("Learning")), section("📚 " + I18N.tr(T("Learning")), h("div.field-row",
      h("label.field", h("span", T("Coins for a perfect lesson"), fieldInfo(T("A lesson finished without a single mistake. Comes on top of the coins for a finished lesson; 0 = none."))), f.lesson_perfect_coins),
      h("label.field", h("span", "🐾 ", T("Pets: food costs (coins)"), fieldInfo(T("Feeding a pet once. Playing and washing are free; 0 = food is free."))), f.pet_food_cost),
      h("label.field", h("span", "🏨 ", T("Pet hotel: coins per day"), fieldInfo(T("The Family Quest pet hotel looks after a pet while the child is away (e.g. at a camp) – paid per day in advance; the pet comes back fed, happy and clean. 0 = free."))), f.pet_hotel_cost),
      h("label.field", h("span", "🐹 ", T("Hamster: coins per day"), fieldInfo(T("While the hamster is healthy (every bar at least 50) it runs in its wheel and mines this many coins per day for its owner."))), f.hamster_coins_per_day),
      h("label.field", h("span", "🐾 ", T("Pet shop: pay with"), fieldInfo(T("Outfits, houses and furniture for the pets. XP spent there do not lower the level."))), f.pet_shop_currency)), saveBtn())),
    group("set.personal", "🎨", T("Personalisation")),
    fold("texts", "🌐 " + I18N.tr(T("Own texts and languages")), await translationsSection()),
    fold("weather", "☀️ " + I18N.tr(T("Bonus/malus points")), weatherBox("config")),
    group("set.ha", "🏠", T("Home Assistant")),
    fold("halogin", "🏠 " + I18N.tr(T("Log in with Home Assistant")), haLoginSection(s)),
    fold("integration", "🏠 " + I18N.tr(T("Family Quest HA integration")), await integrationSection()),
    fold("ha", "🔔 " + I18N.tr(T("Home Assistant reminders")), section("🔔 " + I18N.tr(T("Home Assistant reminders")), P.meta.ha ? null : h("p.warn-text", T("Home Assistant is not connected – these settings take effect once it is.")),
      h("div.field-row",
        h("label.field", h("span", T("Learning reminder at"), fieldInfo(T("Children without the daily goal get an announcement (Family Planer) and the event family_quest_erinnerung."))), f.reminder_time),
        h("label.field", h("span", T("Chore reminder at"), fieldInfo(T("Children with open chores get an announcement (Family Planer) and the event family_quest_aemtli_erinnerung."))), f.chore_reminder_time),
        h("label.field.span2", h("span", T("Push messages for approvals"), fieldInfo(T("Notify service of the Companion app – with buttons OK / No."))), f.notify_service, dl)),
      h("label.check", f.planer_points, T("Also book learning coins as Family Planer points")),
      h("label.field", T("Factor for Family Planer points"), f.planer_points_factor), saveBtn())),
    fold("shopping", "🛒 " + I18N.tr(T("Shopping list (Bring!)")), shoppingSection()),
    group("set.system", "🛠️", T("System")),
    fold("backup", "💾 " + I18N.tr(T("Backup & restore")), backupSection()),
    fold("network", "🛡️ " + I18N.tr(T("Access from the network")), await firewallSection(s)),
    fold("planer", "📥 " + I18N.tr(T("Take over an existing Family Planer")), planerSection(s)),
    fold("about", T("About"), section(T("About"), h("p.small", "Family Quest v" + P.meta.version), h("ul.small",
      h("li", "Home Assistant: ", P.meta.ha ? "✓" : h("span", { translate: "no" }, "– ", P.meta.ha_status || "")), h("li", I18N.tr(T("Planner")) + ": ✓ ", h("span.small.muted", T("(built in)"))),
      P.meta.planer ? h("li", T("Family Planer integration in Home Assistant: found – take it over under «Family Planer» above.")) : null,
      h("li", I18N.tr(T("Photo/PDF import")) + ": ", P.meta.ai ? "✓" : h("span.small.muted", "– ", T("needs an AI Task in Home Assistant")))))));
  // the status in the rows: now, and again after every change made on this page (call() reports it)
  const refresh = () => settingsStatus(main).catch(() => {});
  let timer = 0;
  P.onChange = () => { clearTimeout(timer); timer = setTimeout(() => { if (main.isConnected) refresh(); }, 350); };
  refresh();
  async function save() {
    const body = { reminder_time: f.reminder_time.value.trim(),
      chore_reminder_time: f.chore_reminder_time.value.trim(),
      notify_service: f.notify_service.value.trim(), planer_points: f.planer_points.checked, planer_points_factor: +f.planer_points_factor.value,
      levels: f.levels.value.split(/[,; ]+/).map(Number).filter(n => !isNaN(n)).sort((a, b) => a - b),
      lesson_perfect_coins: Math.max(0, Math.min(1000, Math.round(+f.lesson_perfect_coins.value || 0))),
      pet_food_cost: Math.max(0, Math.min(100, Math.round(+f.pet_food_cost.value || 0))), pet_shop_currency: f.pet_shop_currency.value,
      pet_hotel_cost: Math.max(0, Math.min(1000, Math.round(+f.pet_hotel_cost.value || 0))),
      hamster_coins_per_day: Math.max(0, Math.min(1000, Math.round(+f.hamster_coins_per_day.value || 0))) };
    await call("parent/settings", { method: "PUT", body }); toast(T("Saved"), "good");
  }
}

boot();
