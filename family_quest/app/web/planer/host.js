// Runs the Family Planer UI (taken over from Family Planer, MIT, magibuilds) inside Family Quest.
// It was built for Home Assistant: it expects a `hass` object, <ha-icon>/<ha-card> and path routes.
// This file provides all of that on top of the Family Quest API (/api/planer/ws and /api/planer/ha/…).
"use strict";

// ---------------------------------------------------------------- routes: #/listen instead of /family-planer/listen
window.FPLOC = () => ["family-planer", (location.hash.replace(/^#\/?/, "").split("?")[0] || window.FQ_PLANER_DEFAULT || "planer")];
// views this page does not show (the app: chore plan and settings are in the parent area) → back to the planner
const fqAllowed = seg => (!window.FQ_PLANER_ONLY || window.FQ_PLANER_ONLY.includes(seg)) && !(window.FQ_PLANER_HIDE || []).includes(seg);
function fqGuard() {
  const seg = window.FPLOC()[1];
  if (!fqAllowed(seg)) { history.replaceState(null, "", "#/" + (window.FQ_PLANER_DEFAULT || "planer")); return false; }
  return true;
}
fqGuard();
window.addEventListener("hashchange", () => { fqGuard(); window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } })); });

// ---------------------------------------------------------------- the app's own buttons right in the planer's top bar
window.FQ_NAV_HOOK = root => {
  if (window.FQ_PLANER_MODE === "parent") return fqParentState(root);
  // the same header as the other pages of the app: ☰ menu at the left, «check holidays» next to the calendar,
  // only «refresh» stays on the right (home, language and log out are in the ☰ menu)
  const left = root.querySelector(".bar .t");
  // the planer's own ☰ (it opens the Home Assistant sidebar) does nothing here – the app's ☰ replaces it
  root.querySelectorAll(".bar .t button.menu[data-menu]").forEach(b => { b.style.display = "none"; });
  if (left && !left.querySelector(".fq-menu")) {
    const btn = document.createElement("button");
    btn.className = "ic sq fq-menu";
    btn.title = btn.ariaLabel = I18N.tr("Menu");
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>';
    btn.style.cssText = "margin-right:10px;flex:none";
    btn.onclick = e => { e.stopPropagation(); openAppMenu({ active: "planer",
      onGo: k => { location.href = k === "planer" ? "planer" : "app#/" + (k === "home" ? "" : k); },
      onLogout: () => { Auth.kid = ""; Auth.parent = ""; location.href = "app"; } }); };
    left.prepend(btn);
    left.style.display = "flex"; left.style.alignItems = "center";
  }
  const mid = root.querySelector(".mid"), vac = root.querySelector(".rt [data-vac]");
  if (mid && vac) {
    const cal = mid.querySelector("button");
    cal ? cal.after(vac) : mid.prepend(vac);
  }
};

// ---------------------------------------------------------------- parent area (planer?mode=parent, in a frame)
// The planer's own top bar (clock, season, its buttons) is hidden there (planer.html): the parent area shows its
// functions as buttons in its own section head (parent.js planerChoresSection). The frame tells the parent page
// whether holidays are on and how many wait for a decision; the buttons there call FQ_PLANER_DO.
function fqParentState(root) {
  const vac = root.querySelector("[data-vac]"), dot = vac && vac.querySelector(".dot");
  const nav = root.host;
  const state = { vac: !!vac, pending: dot ? +dot.textContent || 0 : 0, open: !!(nav && nav._open === "vac") };
  const key = JSON.stringify(state);
  if (key === fqParentState.last) return;
  fqParentState.last = key;
  try { if (window.frameElement) window.frameElement.dispatchEvent(new CustomEvent("fq-planer-state", { detail: state })); } catch {}
}
// The frame is as high as its content (parent.js planerFrame), so «position:fixed» windows of the planer (parent PIN,
// «+ Special chore», holidays …) would sit in the middle of the whole frame – maybe far outside the screen. They are
// moved into the part of the frame that is visible on the screen just now.
window.FQ_VIS = () => {
  try {
    const r = window.frameElement.getBoundingClientRect(), H = window.parent.innerHeight;
    const top = Math.max(0, -r.top), h = Math.max(160, Math.min(r.bottom, H) - Math.max(r.top, 0));
    return { top: Math.round(top), h: Math.round(Math.min(h, innerHeight - top)) };
  } catch { return { top: 0, h: innerHeight }; }
};
if (window.FQ_PLANER_MODE === "parent" && window.frameElement) {
  const pin = el => {
    if (!(el instanceof HTMLElement) || el.style.position !== "fixed" || el.style.inset !== "0px") return;
    const v = window.FQ_VIS();
    Object.assign(el.style, { top: v.top + "px", bottom: "auto", height: v.h + "px", transform: "translateZ(0)" });  // own frame for fixed children
  };
  new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(pin))).observe(document.body || document.documentElement, { childList: true });
}
window.FQ_PLANER_DO = async act => {
  const panel = document.querySelector("family-planer-panel");
  const nav = panel && panel.querySelector("family-planer-nav-card"), card = panel && panel.querySelector("family-planer-card");
  if (act === "vac" && nav && nav.shadowRoot) {
    const b = nav.shadowRoot.querySelector("[data-vac]");
    if (b) b.click();                                     // opens / closes the holiday window (as the button in the bar)
  } else if (act === "refresh" && nav && nav._refresh) {
    await nav._refresh();                                 // the server pulls calendars and lists again
  } else if ((act === "special" || act === "todo") && card) {
    card.dispatchEvent(new CustomEvent("fp-plan-add", { detail: { kind: act } }));   // as «+ Special chore» / «+ To-do»
  }
};

// ---------------------------------------------------------------- <ha-icon> and <ha-card>
class FqHaIcon extends HTMLElement {
  static get observedAttributes() { return ["icon"]; }
  set icon(v) { this._icon = v; this._draw(); }
  get icon() { return this._icon || this.getAttribute("icon"); }
  connectedCallback() { this._draw(); }
  attributeChangedCallback() { this._draw(); }
  _draw() {
    const name = String(this.icon || "").replace(/^mdi:/, "");
    const path = (window.FP_MDI || {})[name] || (window.FP_MDI || {})["help-circle-outline"] || "";
    if (this._drawn === path) return;
    this._drawn = path;
    this.style.display = this.style.display || "inline-flex";
    this.style.width = this.style.width || "var(--mdc-icon-size, 24px)";
    this.style.height = this.style.height || "var(--mdc-icon-size, 24px)";
    this.innerHTML = `<svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor" aria-hidden="true"><path d="${path}"/></svg>`;
  }
}
if (!customElements.get("ha-icon")) customElements.define("ha-icon", FqHaIcon);
class FqHaCard extends HTMLElement {
  connectedCallback() {
    if (!this.style.display) this.style.display = "block";
    this.style.borderRadius = this.style.borderRadius || "var(--ha-card-border-radius, 16px)";
    this.style.background = this.style.background || "var(--ha-card-background, var(--fp-bg1, #1e1e1e))";
  }
}
if (!customElements.get("ha-card")) customElements.define("ha-card", FqHaCard);

// ---------------------------------------------------------------- no planner PIN in Family Quest
// The old Family Planer ran on one shared screen and asked for a parent PIN for every change. In Family Quest the
// signed-in profile is the identity (familyquest/planer/websocket.py): parents (also signed in with Home Assistant)
// just do it, a child gets a clear «only parents» message instead of a PIN pad. pin.js asks FQ_NO_PIN (build_fq.py).
const FQ_DENIED = ["parent_only", "parent_network", "own_only", "points_parent"];
window.FQ_NO_PIN = async (store, type, data, CANCEL) => {
  try { return await store.ws(type, data || {}); }
  catch (e) {
    if (e && FQ_DENIED.includes(e.code)) { toast(e.message, "bad"); throw CANCEL; }
    throw e;
  }
};
window.FQ_NO_PIN.change = CANCEL => {                     // «Change PIN»: the parents' PINs are in Family Quest
  toast(I18N.tr("Parent PINs are changed in Family Quest: parent area → Profiles"));
  return Promise.reject(CANCEL);
};

// ---------------------------------------------------------------- connection (Home Assistant websocket format)
class FqConnection {
  constructor() {
    this._id = 1; this._pending = new Map(); this._subs = new Map(); this._listeners = {};
    this._open();
  }
  _url() {
    const base = new URL("api/planer/ws", location.href.replace(/[#?].*$/, "").replace(/[^/]*$/, ""));
    base.protocol = location.protocol === "https:" ? "wss:" : "ws:";
    if (Auth.kid && !window.FQ_PARENT_AREA) base.searchParams.set("token", Auth.kid);
    if (Auth.parent) base.searchParams.set("parent", Auth.parent);
    return base.toString();
  }
  _open() {
    this._ready = new Promise(res => { this._resolveReady = res; });
    const ws = new WebSocket(this._url());
    this.ws = ws;
    ws.onopen = () => {
      this._resolveReady();
      for (const [id, s] of this._subs) ws.send(JSON.stringify({ ...s.msg, id }));     // re-subscribe after a reconnect
      this._fire("ready");
    };
    ws.onmessage = ev => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.type === "event") { const s = this._subs.get(m.id); if (s) s.cb(m.event); return; }
      if (m.type === "result") {
        const p = this._pending.get(m.id); if (!p) return;
        this._pending.delete(m.id);
        if (!m.success && m.error && FQ_DENIED.includes(m.error.code)) m.error = { ...m.error, message: I18N.tr(m.error.message) };
        m.success ? p.resolve(m.result) : p.reject(m.error || { code: "error", message: "error" });
      }
    };
    ws.onclose = ev => {
      for (const p of this._pending.values()) p.reject({ code: "disconnected", message: "Connection lost" });
      this._pending.clear();
      this._fire("disconnected");
      if (ev.code === 4401) {                                           // not logged in (any more)
        if (window.FQ_PLANER_MODE === "parent") { try { window.parent.location.reload(); } catch {} return; }
        location.href = "app"; return;
      }
      setTimeout(() => this._open(), 3000);
    };
  }
  _fire(type) { (this._listeners[type] || []).forEach(cb => { try { cb(this); } catch {} }); }
  addEventListener(type, cb) { (this._listeners[type] = this._listeners[type] || []).push(cb); }
  removeEventListener(type, cb) { this._listeners[type] = (this._listeners[type] || []).filter(x => x !== cb); }
  async sendMessagePromise(msg) {
    await this._ready;
    const id = this._id++;
    return new Promise((resolve, reject) => {
      this._pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ ...msg, id }));
    });
  }
  async subscribeMessage(cb, msg) {
    await this._ready;
    const id = this._id++;
    this._subs.set(id, { cb, msg });
    await new Promise((resolve, reject) => {
      this._pending.set(id, { resolve, reject: e => { this._subs.delete(id); reject(e); } });
      this.ws.send(JSON.stringify({ ...msg, id }));
    });
    return async () => {
      this._subs.delete(id);
      try { await this.sendMessagePromise({ type: "unsubscribe_events", subscription: id }); } catch {}
    };
  }
}

// ---------------------------------------------------------------- the `hass` object
async function fqHass(conn, prev) {
  let states = prev ? prev.states : {};
  try {
    const list = await api("planer/ha/states");
    states = {};
    for (const s of list) states[s.entity_id] = s;
  } catch {}
  const lang = (I18N.base || "de").slice(0, 2) === "de" ? "de" : "en";
  return {
    connection: conn,
    states,
    language: lang,
    locale: { language: lang, time_format: "24", number_format: "language" },
    user: { is_admin: !!Auth.parent, name: "Family Quest" },
    themes: { darkMode: matchMedia("(prefers-color-scheme: dark)").matches },
    async callService(domain, service, data, target) {
      // like Home Assistant: the target (e.g. { entity_id }) is the 4th argument – sent together with the data
      return api("planer/ha/service", { method: "POST", body: { domain, service, data: { ...(target || {}), ...(data || {}) } } });
    },
    async callApi(method, path) {
      const m = String(path).match(/^calendars\/([^?]+)\?(.*)$/);
      if (method === "GET" && m && m[1] === "familyquest") return api(`planer/fq-events?${m[2]}`);      // the family calendar of Family Quest
      if (method === "GET" && m) return api(`planer/ha/calendars/${encodeURIComponent(m[1])}?${m[2]}`);
      throw new Error("not available in Family Quest: " + path);
    },
  };
}

async function startPlaner(root) {
  // the family calendars for the «Termine» row (bridge.js adds them to the persons' calendars)
  try { window.FQ_EXTRA_CALENDARS = await api("planer/fq-calendars"); } catch { window.FQ_EXTRA_CALENDARS = []; }
  const conn = new FqConnection();
  const panel = document.createElement("family-planer-panel");
  panel.panel = { config: { entry_id: "familyquest" } };
  const narrow = () => matchMedia("(max-width: 870px)").matches;
  panel.narrow = narrow();
  window.addEventListener("resize", () => { const n = narrow(); if (n !== panel._narrow) panel.narrow = n; });
  let hass = await fqHass(conn);
  panel.hass = hass;
  root.replaceChildren(panel);
  // states change slowly (calendars, lists, weather) – refresh them every minute and on reconnect
  const refresh = async () => { hass = await fqHass(conn, hass); panel.hass = hass; };
  setInterval(refresh, 60000);
  conn.addEventListener("ready", refresh);
}
