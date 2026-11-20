// ---------------------------------------------------------------- ⚙️ Settings: season designs, weather, link, Home Assistant, firewall, Planer, backup, translations, dashboard
// A part of the parent area (parent.js): loaded after it, before boot() runs (eltern.html).
"use strict";

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
      h("button.btn.ghost", { onclick: () => ownDialog(null, null) }, "+ ", T("Own design")), live);
  };
  const live = seasonLiveBox();
  call("parent/themes").then(draw).catch(() => {});
  return sec;
}

/** Live weather and daylight of the scenes (seasonlive.py): the weather entity is the one of the Family Planer
 *  (one setting for the planner cards and the app), the sun switch only for the app. */
function seasonLiveBox() {
  const none = () => h("option", { value: "" }, I18N.tr(T("None")));
  const sel = h("select.grow", none()), sun = h("input", { type: "checkbox", checked: true }), now = h("div.small.muted");
  const keep = v => { if (v && ![...sel.options].some(o => o.value === v)) sel.append(h("option", { value: v }, v)); sel.value = v || ""; };
  const show = d => {
    sun.checked = d.sun; keep(d.weather);
    const l = d.live, w = l && l.wx;
    const light = l && l.night != null ? (l.night ? T("Night") : l.dusk === "dawn" ? T("Dawn") : l.dusk === "dusk" ? T("Dusk") : T("Day")) : null;
    now.replaceChildren(...(w || light ? [T("Now"), ": ", w ? w.icon + (w.temp != null ? " " + w.temp + w.unit : "") : "", w && light ? " · " : "", light || ""] : []));
  };
  const save = async body => { try { show(await call("parent/season-live", { method: "PUT", body })); toast(T("Saved"), "good"); } catch (e) { /* call shows the error */ } };
  sel.onchange = () => save({ weather: sel.value || null });
  sun.onchange = () => save({ sun: sun.checked });
  call("parent/season-live").then(d => {
    show(d);
    if (d.ha || P.meta.ha) call("parent/ha/entities?domain=weather").then(list => {
      const v = sel.value;
      sel.replaceChildren(none(), ...list.map(e => h("option", { value: e.entity_id }, (e.name && e.name !== e.entity_id ? e.name + " – " : "") + e.entity_id)));
      keep(v);
    }).catch(() => {});
  }).catch(() => {});
  return h("div.form.live-box",
    h("h3", { "data-ik": "Weather for the designs" }, "🌦️ ", T("Weather for the designs")),
    h("div.row", sel),
    h("label.row", sun, " ", h("span", { "data-ik": "Day and night follow the sun" }, T("Day and night follow the sun"))),
    now);
}

function weatherBox(part) {
  const box = h("div");
  weatherView(box, part).catch(e => box.append(h("p.bad", e.message)));
  return box;
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
      st.server_known === false && !st.url ? h("p.small.bad", "⚠️ ", T("Family Quest does not know where Home Assistant is – enter its address below and save, otherwise the sign-in in the app is refused.")) : null,
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
    h("div.field", h("span", T("…or upload the file family_planer.<id> from /config/.storage")), fileButton(file, "📤 ", T("Choose file…"))), box);
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
    // the three kinds explained first, then the buttons
    h("p.small.muted", T("Full: everything. Data: only what the family did (points, progress, games, chores done …). Customizing: settings, profiles and your own content – e.g. to set up a test installation without the data.")),
    h("div.row.backup-kinds",
      h("button.btn", { onclick: () => downloadBackup("full") }, "⬇️ ", T("Download full backup")),
      h("button.btn.ghost", { onclick: () => downloadBackup("data") }, "⬇️ ", T("Download data backup")),
      h("button.btn.ghost", { onclick: () => downloadBackup("customizing") }, "⬇️ ", T("Download customizing backup"))),
    sizes,
    h("div.field", h("span", T("Restore from a backup file")), fileButton(file, "📤 ", T("Choose a backup file…"))), info,
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

// ---------------------------------------------------------------- kiosk dashboard (Settings › App: two folds)
const DASH_WIDGETS = [
  ["clock", "🕒", T("Clock and date")], ["weather_alarm", "🌂", T("Weather alarm (what to take along today)")], ["crown", "👑", T("Crown")], ["weather", "⛅", T("Weather of each child")],
  ["learning", "⭐", T("Learning progress (daily goal, level)")], ["streak", "🔥", T("Streak")], ["coins", "🪙", T("Coins and other points")],
  ["chores", "🧹", T("Open chores of today")], ["family_goal", "🤝", T("Family goal")], ["todos", "✅", T("Open to-dos (Planer)")],
  ["events", "📅", T("Events (family calendar and Home Assistant calendars)")]];
/** The kiosk dashboard: what it shows (with the save button) and the link for the kiosk browser – two boxes for
 *  the folds «dashboard» and «kiosk» of the settings (old address #dashboard opens the first). */
async function dashboardSections() {
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
  return { link: linkSec, settings: section("🖥️ " + I18N.tr(T("What the dashboard shows")),
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
      } }, "💾 ", T("Save"))) };
}

/** The status texts of the folded settings – fetched fresh (after every change on the page too). */
async function settingsStatus(main) {
  const get = path => api(path).catch(() => null);
  const [s, mem, link, themes, weather, haApp, integ, tr, backup, shop, planer, dash] = await Promise.all([
    get("parent/settings"), get("parent/memory"), get("parent/direct-access"), get("parent/themes"), get("parent/weather"),
    get("parent/ha-app-login"), get("parent/integration"), get("parent/translations"), get("parent/backup/sizes"),
    get("planer/shopping"), get("planer/import/sources"), get("parent/dashboard")]);
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
  if (dash) {
    st.dashboard = !dash.enabled ? t(T("Off")) : [t(T("On")), dash.title || null, n(T("1 tile"), T("{0} tiles"), (dash.widgets || []).length)].filter(Boolean).join(" · ");
    st.kiosk = dash.key ? t(T("Link made")) : t(T("No link yet"));
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
  const group = setGroup;
  const dash = await dashboardSections();
  main.append(h("h1", T("Settings")),
    group("set.app", "📱", T("App")),
    fold("link", "📱 " + I18N.tr(T("Link for tablets and phones")), linkSection()),
    fold("themes", "🎨 " + I18N.tr(T("Season, time of day & weather designs")), themesSection()),
    fold("dashboard", "🖥️ " + I18N.tr(T("Dashboard")), dash.settings),
    fold("kiosk", "🔗 " + I18N.tr(T("Link for the kiosk browser")), dash.link),
    fold("levels", "🏅 " + I18N.tr(T("Levels")), section(T("Levels"), h("label.field", T("XP needed per level (comma separated)"), f.levels), saveBtn())),
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
    fold("about", T("About"), section(T("About"), h("div.row", h("p.small.grow", "Family Quest v" + P.meta.version),
      h("button.btn.small.ghost", { type: "button", onclick: releaseNotes }, "📝 ", T("Release notes"))), h("ul.small",
      h("li", "Home Assistant: ", P.meta.ha ? "✓" : h("span", { translate: "no" }, "– ", P.meta.ha_status || "")), h("li", I18N.tr(T("Planner")) + ": ✓ ", h("span.small.muted", T("(built in)"))),
      P.meta.planer ? h("li", T("Family Planer integration in Home Assistant: found – take it over under «Family Planer» above.")) : null,
      h("li", I18N.tr(T("Photo/PDF import")) + ": ", P.meta.ai ? "✓" : h("span.small.muted", "– ", T("needs an AI Task in Home Assistant")))))));
  foldToShow(main);                              // an old address (#dashboard) opens its fold
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
