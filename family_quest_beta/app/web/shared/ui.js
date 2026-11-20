// Small helpers shared by the children's app and the parent area. No framework, no build step.
"use strict";

// optional parts are passed as null / undefined / false everywhere (like in h()): the DOM methods would print them as
// the text «null» – leave them out instead (append, prepend, replaceChildren, before, after, replaceWith)
(() => {
  const keep = x => x != null && x !== false;
  for (const proto of [Element.prototype, DocumentFragment.prototype, CharacterData.prototype]) {
    for (const k of ["append", "prepend", "replaceChildren", "before", "after", "replaceWith"]) {
      const orig = proto[k];
      if (typeof orig !== "function" || orig._fqKeep) continue;
      const fn = function (...xs) { return orig.apply(this, xs.some(x => !keep(x)) ? xs.filter(keep) : xs); };
      fn._fqKeep = true;
      proto[k] = fn;
    }
  }
})();

// h("div.card#x", {onclick, translate: "no"}, child, "text", [more])
function h(sel, attrs, ...kids) {
  if (attrs == null || typeof attrs !== "object" || attrs instanceof Node || Array.isArray(attrs)) { kids.unshift(attrs); attrs = {}; }
  const m = sel.match(/^([a-z0-9]+)?((?:[.#][\w-]+)*)$/i) || [];
  const el = document.createElement(m[1] || "div");
  for (const p of (m[2] || "").match(/[.#][\w-]+/g) || []) p[0] === "." ? el.classList.add(p.slice(1)) : (el.id = p.slice(1));
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") for (const [sk, sv] of Object.entries(v)) { if (sv == null) continue; sk.startsWith("--") ? el.style.setProperty(sk, sv) : (el.style[sk] = sv); }
    else if (k === "html") el.innerHTML = v;
    else if (k === "class") el.className += " " + v;
    else if (k in el && !["list", "form", "translate"].includes(k) && typeof v !== "string") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  const add = c => { if (c == null || c === false) return; if (Array.isArray(c)) c.forEach(add); else el.append(c instanceof Node ? c : document.createTextNode(String(c))); };
  kids.forEach(add);
  return el;
}
// content that must never be translated (names, words to learn, pack titles)
const C = (text, sel = "span") => h(sel, { translate: "no" }, text);
// a photo of a photo set / the crest: in the photo folder, or «ha:<path>» = stays in Home Assistant Media (memorygame.py)
const memPhotoUrl = name => String(name || "").startsWith("ha:")
  ? "hamedia/" + name.slice(3).split("/").map(encodeURIComponent).join("/") : "media/_memory/" + encodeURIComponent(name || "");
// like C, but flag emoji become crisp SVG flags (web/flags, country-flag-icons, MIT) – emoji flags are blurry or just letters on Windows
const CF = (text, sel = "span") => {
  const parts = String(text ?? "").split(/([\u{1F1E6}-\u{1F1FF}]{2})/u);
  if (parts.length === 1) return C(text, sel);
  return h(sel, { translate: "no" }, ...parts.filter(Boolean).map(p => /^[\u{1F1E6}-\u{1F1FF}]{2}$/u.test(p)
    ? h("img.flag-img", { src: "flags/" + [...p].map(c => String.fromCharCode(c.codePointAt(0) - 0x1F1E6 + 65)).join("") + ".svg", alt: p, draggable: false })
    : p));
};
const $ = (s, root = document) => root.querySelector(s);

// ---------------------------------------------------------------- API
const Auth = {
  get kid() { try { return localStorage.getItem("fq.token") || ""; } catch { return ""; } },
  set kid(v) { try { v ? localStorage.setItem("fq.token", v) : localStorage.removeItem("fq.token"); } catch {} },
  get parent() { try { return sessionStorage.getItem("fq.parent") || ""; } catch { return ""; } },
  set parent(v) { try { v ? sessionStorage.setItem("fq.parent", v) : sessionStorage.removeItem("fq.parent"); } catch {} },
};

class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }

// a 401 in the parent area: the page may set window.FQ_ON_401 (renew the session – true: try again once)
let renewing = null;
const NO_RENEW = /^parent\/(login|ha-login|refresh|meta)\b/;
async function api(path, opts = {}) {
  try { return await apiOnce(path, opts); }
  catch (e) {
    if (e.status !== 401 || opts._again || !window.FQ_ON_401 || NO_RENEW.test(path.replace(/^\//, ""))) throw e;
    renewing = renewing || Promise.resolve(window.FQ_ON_401()).finally(() => { setTimeout(() => { renewing = null; }, 0); });
    if (await renewing) return apiOnce(path, { ...opts, _again: true });
    throw new ApiError(401, I18N.tr(T("Session expired – please log in again")));
  }
}

async function apiOnce(path, { method = "GET", body, form, parent = false } = {}) {
  const headers = {};
  // the parent area acts as the parent – a child still logged in on this device must not be used there
  if (Auth.kid && !window.FQ_PARENT_AREA) headers["X-FQ-Token"] = Auth.kid;
  if (Auth.parent) headers["X-FQ-Parent"] = Auth.parent;
  // the language of the app: the word games show their words in it (familyquest/gamewords.py)
  if (window.I18N && I18N.lang) headers["X-FQ-Lang"] = I18N.lang;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const r = await fetch("api/" + path.replace(/^\//, ""), { method, headers, body: payload });
  let data = null;
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("json")) data = await r.json().catch(() => null);
  if (!r.ok) {
    const msg = data && (typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(", ") : "") || ("HTTP " + r.status);
    // the game battery is empty (familyquest/battery.py): the kid app offers to recharge it (kid.js)
    if (r.status === 403 && window.FQ_BATTERY_EMPTY && /^Your game battery is empty/.test(msg)) setTimeout(window.FQ_BATTERY_EMPTY, 300);
    throw new ApiError(r.status, msg);
  }
  return botNamesTr(data);
}

// the built-in bots have German names (familyquest/cardgames.py, werwolf.py) – shown in the app language («Eule Olga» → «Chouette Olga»).
// Names are drawn as content (translate="no"), so they are translated here, where the game states come in.
const BOT_NAMES = new Set([T("Fuchs Fridolin"), T("Bär Bruno"), T("Eule Olga"), T("Frosch Fritz"), T("Katze Kiki"), T("Hase Hoppel"), T("Pinguin Pino"),
  T("Igel Ida"), T("Maus Mimi"), T("Dachs Dani"), T("Reh Rosi"), T("Biber Benno")]);
function botNamesTr(v, depth = 0) {
  if (typeof v === "string") return BOT_NAMES.has(v) ? I18N.tr(v) : v;
  if (!v || typeof v !== "object" || depth > 8 || I18N.lang === "en") return v;
  if (Array.isArray(v)) { for (let i = 0; i < v.length; i++) if (v[i] && (typeof v[i] === "object" || BOT_NAMES.has(v[i]))) v[i] = botNamesTr(v[i], depth + 1); return v; }
  for (const k in v) { const x = v[k]; if (x && (typeof x === "object" || BOT_NAMES.has(x))) v[k] = botNamesTr(x, depth + 1); }
  return v;
}

// ---------------------------------------------------------------- feedback
function toast(msg, kind = "") {
  let box = $("#toasts");
  if (!box) { box = h("div#toasts"); document.body.append(box); }
  const t = h("div.toast" + (kind ? "." + kind : ""), msg);
  box.append(t);
  setTimeout(() => t.classList.add("out"), 2600);
  setTimeout(() => t.remove(), 3100);
}

// a hint only in a tooltip (title) cannot be read on a phone: a tap on such a small badge (🔥 streak, 👑, 🔒 …) shows it
document.addEventListener("click", e => {
  const el = e.target.closest && e.target.closest("[title]");
  if (!el || el.closest("button, a, input, select, textarea, label, summary, [role=button], .modal-back, .drawer, svg") || !el.title.trim()) return;
  if (getSelection && String(getSelection()).length) return;          // selecting text
  toast(el.title);
});

const Sound = {
  ctx: null,
  get on() { try { return localStorage.getItem("fq.sound") !== "0"; } catch { return true; } },
  set on(v) { try { localStorage.setItem("fq.sound", v ? "1" : "0"); } catch {} },
  play(kind) {
    if (!this.on) return;
    try {
      this.ctx = this.ctx || new (window.AudioContext || window.webkitAudioContext)();
      const notes = { right: [660, 880], wrong: [300, 220], done: [523, 659, 784, 1046], tap: [500], turn: [784, 1046, 1318],
        ding: [1318, 1760], sizzle: [170, 150, 130], trash: [240, 160] }[kind] || [440];
      notes.forEach((f, i) => {
        const o = this.ctx.createOscillator(), g = this.ctx.createGain(), t = this.ctx.currentTime + i * 0.11;
        o.type = { wrong: "triangle", sizzle: "sawtooth", trash: "square" }[kind] || "sine"; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(kind === "sizzle" || kind === "trash" ? 0.06 : 0.18, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
        o.connect(g).connect(this.ctx.destination); o.start(t); o.stop(t + 0.2);
      });
    } catch {}
  },
};

// «Your turn» cue: a short chime (and a buzz on phones) when it becomes my turn – only on the change, not on every redraw
const _turnState = {};
function turnCue(key, mine) {
  mine = !!mine;
  const was = _turnState[key];
  _turnState[key] = mine;
  if (mine && was === false) {
    Sound.play("turn");
    try { if (Sound.on && navigator.vibrate) navigator.vibrate([60, 40, 60]); } catch {}
  }
}

function speak(text, lang) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    const tag = { fr: "fr-FR", en: "en-GB", de: "de-CH", it: "it-IT", es: "es-ES" }[lang] || lang || "en-GB";
    u.lang = tag; u.rate = 0.85;
    const v = speechSynthesis.getVoices().find(v => v.lang && v.lang.toLowerCase().startsWith(tag.slice(0, 2)));
    if (v) u.voice = v;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
    return true;
  } catch { return false; }
}

function confetti(root = document.body) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const colors = ["#ff6b6b", "#fcc419", "#51cf66", "#4f8cff", "#845ef7", "#ff922b"];
  const box = h("div.confetti", { "aria-hidden": "true" });
  for (let i = 0; i < 60; i++) {
    box.append(h("i", { style: { left: Math.random() * 100 + "%", background: colors[i % colors.length],
      animationDelay: Math.random() * 0.6 + "s", animationDuration: 1.6 + Math.random() * 1.4 + "s", transform: `rotate(${Math.random() * 360}deg)` } }));
  }
  root.append(box);
  setTimeout(() => box.remove(), 3600);
}

const fmt = (n, d = 0) => Number(n || 0).toLocaleString(I18N.locale, { maximumFractionDigits: d });
// a time span in minutes: «45 min», «2 h», «2 h 30» – null = unlimited «∞»
const fmtMinutes = m => m == null ? "∞" : m < 60 ? fmt(m) + " min" : Math.floor(m / 60) + " h" + (m % 60 ? " " + String(m % 60).padStart(2, "0") : "");
/** Dates and times always in the format of the chosen language. Accepts "2026-12-24", "2026-12-24 18:30" or ISO. */
const _when = v => v instanceof Date ? v : new Date(/^\d{4}-\d\d-\d\d$/.test(String(v)) ? v + "T12:00" : String(v).replace(" ", "T"));
const fmtDate = (v, o = { day: "numeric", month: "numeric", year: "numeric" }) => v ? _when(v).toLocaleDateString(I18N.locale, o) : "";
const fmtTime = v => v ? _when(v).toLocaleTimeString(I18N.locale, { hour: "2-digit", minute: "2-digit" }) : "";
const fmtDateTime = v => v ? fmtDate(v) + " " + fmtTime(v) : "";

// «until 21:00» today, else «until Tue, 21:00» / a date further away (party mode, unlimited game battery)
function untilWhen(v) {
  if (!v) return "";
  const d = _when(v), now = new Date(), days = (d - now) / 864e5;
  const when = d.toDateString() === now.toDateString() ? fmtTime(d)
    : days < 6 ? d.toLocaleDateString(I18N.locale, { weekday: "short" }) + ", " + fmtTime(d) : fmtDate(d) + " " + fmtTime(d);
  return I18N.tr(T("until {0}")).replace("{0}", when);
}

/** The game battery (familyquest/battery.py) as a small battery with charge segments: green → orange → red, empty
 * dashed red, ∞ while unlimited. b: {charge, cap, free} */
function batteryIcon(b, big = false) {
  const cap = Math.max(1, Math.min(20, b.cap || 5)), n = Math.max(0, Math.min(cap, b.charge || 0)), r = n / cap;
  const lvl = b.free ? "inf" : n <= 0 ? "empty" : r <= .25 ? "low" : r <= .5 ? "mid" : "full";
  const label = b.free ? "∞" : n + " / " + cap;
  return h("span.bat." + lvl + (big ? ".big" : ""), { role: "img", "aria-label": I18N.tr(T("Game battery")) + " " + label, title: I18N.tr(T("Game battery")) + " " + label },
    h("span.bat-body", b.free ? h("b.bat-inf", "∞") : Array.from({ length: cap }, (_, i) => h("i" + (i < n ? ".on" : "")))), h("span.bat-tip"));
}

// SVG progress ring
function ring(value, max, { size = 120, stroke = 12, color = "var(--accent)", label = "" } = {}) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, p = Math.max(0, Math.min(1, max ? value / max : 0));
  const wrap = h("div.ring", { style: { width: size + "px", height: size + "px" } });
  wrap.innerHTML = `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" aria-hidden="true">
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="var(--ring-bg)" stroke-width="${stroke}"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - p)}" transform="rotate(-90 ${size / 2} ${size / 2})" style="transition:stroke-dashoffset .8s"/></svg>`;
  wrap.append(h("div.ring-label", label));
  return wrap;
}

function bar(value, max, color) {
  const p = Math.max(0, Math.min(100, max ? 100 * value / max : 0));
  return h("div.bar", h("i", { style: { width: p + "%", background: color || "" } }));
}

function stars(n, max = 5) {
  return h("span.stars", { "aria-label": `${n} / ${max}` }, ...Array.from({ length: max }, (_, i) => h("i" + (i < n ? ".on" : ""), "★")));
}

// PIN pad: resolves with the digits (or null on cancel)
function pinPad({ title, length = 4, maxLength = 8, onSubmit, cancel = true }) {
  let pin = "";
  const dots = h("div.pin-dots");
  const err = h("div.pin-err");
  const draw = () => { dots.replaceChildren(...Array.from({ length: Math.max(length, pin.length) }, (_, i) => h("i" + (i < pin.length ? ".on" : "")))); };
  const press = d => {
    err.textContent = "";
    if (d === "⌫") pin = pin.slice(0, -1);
    else if (d === "✓") { submit(); return; }
    else if (pin.length < maxLength) pin += d;
    draw();
    if (pin.length === length && length === maxLength) submit();
  };
  const submit = async () => {
    if (pin.length < length) return;
    try { await onSubmit(pin); } catch (e) { err.textContent = e.message; pin = ""; draw(); dots.classList.add("shake"); setTimeout(() => dots.classList.remove("shake"), 400); }
  };
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "✓"];
  const pad = h("div.pin-pad", ...keys.map(k => h("button.pin-key", { type: "button", onclick: () => press(k), "aria-label": k === "⌫" ? T("Delete") : k === "✓" ? T("OK") : k }, k)));
  const box = h("div.pin-box", h("h2", title), dots, err, pad,
    cancel ? h("button.link", { type: "button", onclick: () => box.dispatchEvent(new CustomEvent("cancel", { bubbles: true })) }, T("Cancel")) : null);
  const onKey = e => { if (!box.isConnected) { document.removeEventListener("keydown", onKey); return; } if (/^\d$/.test(e.key)) press(e.key); else if (e.key === "Backspace") press("⌫"); else if (e.key === "Enter") press("✓"); };
  document.addEventListener("keydown", onKey);
  draw();
  return box;
}

// ---------- picture PIN: 4 symbols out of 12 (3 × 4), tap them or draw a line through them ----------
function randomSymbolSet(n = 12) {
  const ids = Object.keys(window.SYMBOLS || {});
  for (let i = ids.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [ids[i], ids[j]] = [ids[j], ids[i]]; }
  return ids.slice(0, n);
}

// mode "enter": 4 symbols → onSubmit(ids) (a thrown error shakes and starts over)
// mode "set": choose 4 symbols, 🔀 brings 12 new ones; box.value() → { symbols: [4 ids], set: [12 ids] }
function symbolPad({ title, symbols, mode = "enter", length = 4, onSubmit, cancel = true }) {
  let set = symbols && symbols.length ? symbols.slice() : randomSymbolSet(), seq = [], cells = [], drawing = false;
  const SVGNS = "http://www.w3.org/2000/svg";
  const grid = h("div.sym-grid", { translate: "no" });
  const line = document.createElementNS(SVGNS, "svg"); line.setAttribute("class", "sym-line");
  const poly = document.createElementNS(SVGNS, "polyline"); line.append(poly);
  const wrap = h("div.sym-wrap", grid, line);
  const dots = h("div.pin-dots"), err = h("div.pin-err"), chosen = h("div.sym-chosen", { translate: "no" });
  const build = () => {
    seq = [];
    cells = set.map(id => h("button.sym-cell", { type: "button", "data-id": id, "aria-label": id }, (window.SYMBOLS || {})[id] || "?"));
    grid.replaceChildren(...cells); paint();
  };
  const paint = () => {
    cells.forEach(c => { const i = seq.indexOf(c.dataset.id); c.classList.toggle("on", i >= 0); c.dataset.n = i >= 0 ? i + 1 : ""; });
    dots.replaceChildren(...Array.from({ length }, (_, i) => h("i" + (i < seq.length ? ".on" : ""))));
    chosen.replaceChildren(...seq.map(id => h("span", (window.SYMBOLS || {})[id])));
    const base = wrap.getBoundingClientRect();
    line.setAttribute("viewBox", `0 0 ${base.width || 1} ${base.height || 1}`);
    poly.setAttribute("points", seq.map(id => { const r = cells.find(c => c.dataset.id === id).getBoundingClientRect();
      return `${r.left - base.left + r.width / 2},${r.top - base.top + r.height / 2}`; }).join(" "));
  };
  const add = id => {
    if (!id || seq.includes(id) || seq.length >= length) return;
    seq.push(id); err.textContent = ""; try { Sound.play("tap"); } catch {}
    paint();
    if (seq.length === length && mode === "enter") submit();
  };
  const submit = async () => {
    try { await onSubmit(seq.slice()); }
    catch (e) { err.textContent = e.message; seq = []; paint(); wrap.classList.add("shake"); setTimeout(() => wrap.classList.remove("shake"), 400); }
  };
  // while drawing, a symbol only counts near its centre – so a line that just grazes a neighbour does not pick it
  const cellAt = (x, y) => {
    const el = document.elementFromPoint(x, y), c = el && el.closest && el.closest(".sym-cell");
    if (!c) return null;
    const r = c.getBoundingClientRect(), dx = x - (r.left + r.width / 2), dy = y - (r.top + r.height / 2);
    return Math.hypot(dx, dy) <= r.width * 0.32 ? c : null;
  };
  grid.addEventListener("pointerdown", e => { const c = e.target.closest(".sym-cell"); if (!c) return; e.preventDefault(); drawing = true; add(c.dataset.id); });
  grid.addEventListener("pointermove", e => { if (!drawing) return; const c = cellAt(e.clientX, e.clientY); if (c && grid.contains(c)) add(c.dataset.id); });
  const stop = () => { drawing = false; };
  window.addEventListener("pointerup", stop); window.addEventListener("pointercancel", stop);
  const again = h("button.btn.small.ghost", { type: "button", onclick: () => { seq = []; err.textContent = ""; paint(); } }, "↺ ", T("Start over"));
  const shuffle = mode === "set" ? h("button.btn.small.ghost", { type: "button", onclick: () => { set = randomSymbolSet(); build(); } }, "🔀 ", T("Other symbols")) : null;
  const box = h("div.pin-box.sym-box", title ? h("h2", title) : null,
    mode === "enter" ? dots : h("div.sym-hint", h("span.small.muted", T("Choose 4 symbols in your order – tap them or draw a line.")), chosen),
    err, wrap, h("div.row.center", again, shuffle),
    cancel && mode === "enter" ? h("button.link", { type: "button", onclick: () => box.dispatchEvent(new CustomEvent("cancel", { bubbles: true })) }, T("Cancel")) : null);
  box.value = () => ({ symbols: seq.slice(), set: set.slice() });
  build();
  requestAnimationFrame(paint);
  return box;
}

// keyboard and screen readers in a dialog or a drawer: focus goes in (the first control – on touch screens the dialog
// itself, so no keyboard pops up), Tab stays inside, Escape closes the topmost one only, focus returns to the opener
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
function focusTrap(back, box, close) {
  const opener = document.activeElement;
  const items = () => [...box.querySelectorAll(FOCUSABLE)].filter(e => e.getClientRects().length && !e.closest("[hidden], [inert]"));
  const top = () => [...document.querySelectorAll(".modal-back, .drawer-back")].pop() === back;
  const key = e => {
    if (!back.isConnected) return release();
    if (!top()) return;
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "Tab") return;
    const l = items();
    if (!l.length) { e.preventDefault(); box.focus(); return; }
    const i = l.indexOf(document.activeElement);
    if (e.shiftKey && i <= 0) { e.preventDefault(); l[l.length - 1].focus(); }
    else if (!e.shiftKey && (i === -1 || i === l.length - 1)) { e.preventDefault(); l[0].focus(); }
  };
  const release = (restore = true) => {
    document.removeEventListener("keydown", key);
    if (restore && opener && opener.isConnected && typeof opener.focus === "function" && !document.querySelector(".modal-back, .drawer-back")) opener.focus({ preventScroll: true });
  };
  document.addEventListener("keydown", key);
  if (!box.hasAttribute("tabindex")) box.tabIndex = -1;
  requestAnimationFrame(() => {
    if (!back.isConnected || box.contains(document.activeElement)) return;
    const auto = box.querySelector("[autofocus]");
    const first = auto || (matchMedia("(pointer: coarse)").matches ? null : items().find(e => e.tagName !== "SUMMARY"));
    (first || box).focus({ preventScroll: true });
  });
  return release;
}

function modal(content, { onClose, wide = false } = {}) {
  const back = h("div.modal-back", { onclick: e => { if (e.target === back) close(); } });
  const box = h("div.modal" + (wide ? ".wide" : ""), { role: "dialog", "aria-modal": "true" }, content);
  back.append(box);
  let release = null;
  const close = () => { if (!back.isConnected) return; back.remove(); release && release(); onClose && onClose(); };
  back.addEventListener("cancel", close);
  document.body.append(back);
  release = focusTrap(back, box, close);
  return { close, box };
}

// the app's own «OK / Cancel» and «enter a name» dialogs instead of the browser's confirm() / prompt() (those look
// foreign, block the page and cannot be styled): await confirmDialog(text) → true / false; await promptDialog(text, value) → text / null
function confirmDialog(msg, { ok = T("OK"), cancel = T("Cancel"), danger = null } = {}) {
  const text = I18N.tr(msg);
  if (danger == null) danger = /delete|remove|end|resign|give up|reset|replace|clear|throw|lösch|entfern/i.test(String(msg));
  return new Promise(resolve => {
    let answer = false;
    const done = v => { answer = v; m.close(); };
    const m = modal(h("div.form.ask-dlg", h("p.ask-text", text),
      h("div.row.ask-btns", h("button.btn" + (danger ? ".bad" : ""), { type: "button", autofocus: true, onclick: () => done(true) }, I18N.tr(ok)),
        h("button.btn.ghost", { type: "button", onclick: () => done(false) }, I18N.tr(cancel)))), { onClose: () => resolve(answer) });
    m.box.setAttribute("role", "alertdialog");
  });
}
function promptDialog(msg, value = "", { ok = T("OK"), cancel = T("Cancel"), maxLength = 200 } = {}) {
  return new Promise(resolve => {
    let answer = null;
    const input = h("input", { type: "text", value: value == null ? "" : String(value), maxLength, autofocus: true,
      onkeydown: e => { if (e.key === "Enter") { e.preventDefault(); done(input.value); } } });
    const done = v => { answer = v; m.close(); };
    const m = modal(h("div.form.ask-dlg", h("label.field", h("span.ask-text", I18N.tr(msg)), input),
      h("div.row.ask-btns", h("button.btn", { type: "button", onclick: () => done(input.value) }, I18N.tr(ok)),
        h("button.btn.ghost", { type: "button", onclick: () => done(null) }, I18N.tr(cancel)))), { onClose: () => resolve(answer) });
    requestAnimationFrame(() => input.select());
  });
}

// tabs (e.g. a long dialog in parts): tabbed([{ key, label, content: [...] }]) → { el, bar, show(key), setVisible(key, on), reveal(el) }
function tabbed(tabs) {
  const btns = {}, panes = {};
  let cur = null;
  const order = tabs.map(t => t.key);
  const visible = k => !btns[k].hidden;
  const show = k => {
    if (!panes[k]) return;
    cur = k;
    for (const x of order) { const on = x === k; btns[x].setAttribute("aria-selected", String(on)); btns[x].tabIndex = on ? 0 : -1; panes[x].hidden = !on; }
    btns[k].scrollIntoView({ block: "nearest", inline: "nearest" });
  };
  const move = (k, d) => { const l = order.filter(visible); const n = l[(l.indexOf(k) + d + l.length) % l.length]; show(n); btns[n].focus(); };
  const bar = h("div.tabbar", { role: "tablist" }, ...tabs.map(t => (btns[t.key] = h("button.tab", { type: "button", role: "tab", id: "tab-" + t.key,
    onclick: () => show(t.key), onkeydown: e => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); move(t.key, e.key === "ArrowRight" ? 1 : -1); } } }, t.label))));
  for (const t of tabs) panes[t.key] = h("div.tab-pane", { role: "tabpanel", "aria-labelledby": "tab-" + t.key }, ...[].concat(t.content));
  show(order[0]);
  return {
    el: h("div.tabbed", bar, ...order.map(k => panes[k])), bar, show,
    setVisible: (k, on) => { btns[k].hidden = !on; if (!on && cur === k) show(order.find(visible)); },
    reveal: el => { const k = order.find(x => panes[x].contains(el)); if (k) { btns[k].hidden = false; show(k); } },
  };
}

function themeInit() {
  try { const t = localStorage.getItem("fq.theme"); if (t) document.documentElement.dataset.theme = t; } catch {}
}
themeInit();

// light / dark: the button switches and remembers it on this device (otherwise the system or Home Assistant decides)
function currentTheme() {
  return document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}
// written-out menu items (parent menu, app drawer): light / dark and the language
function footTheme() {
  const btn = h("button.foot-item");
  const draw = () => { const dark = currentTheme() === "dark";
    btn.replaceChildren(h("span.foot-ic", dark ? "☀️" : "🌙"), h("span", dark ? T("Light mode") : T("Dark mode"))); };
  btn.onclick = () => { const t = currentTheme() === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t;
    try { localStorage.setItem("fq.theme", t); } catch {} draw(); };
  draw();
  return btn;
}
function footLang() {
  const pick = langPicker();
  const cur = I18N.custom.find(l => l.code === I18N.pref) ? I18N.custom.find(l => l.code === I18N.pref).name
    : (I18N.LANGS.find(([k]) => k === I18N.pref) || ["", "Auto"])[1];
  return h("div.foot-item.foot-lang", { onclick: e => { if (!e.target.closest(".lang-menu, .lang-btn")) { e.stopPropagation(); pick.querySelector(".lang-btn").click(); } } },
    pick, h("span", T("Language"), h("span.small.muted", { translate: "no" }, " · ", cur === "auto" ? "Auto" : cur)));
}

function themeBtn() {
  const btn = h("button.icon-btn.theme-btn", { title: T("Light / dark"), "aria-label": T("Light / dark") });
  const draw = () => { btn.textContent = currentTheme() === "dark" ? "☀️" : "🌙"; };
  btn.onclick = () => {
    const t = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("fq.theme", t); } catch {}
    draw();
  };
  draw();
  return btn;
}

// QR code as SVG (needs shared/qrcode.js on the page)
function qrSvg(text) {
  if (typeof qrcode !== "function") return h("div.qr");
  const q = qrcode(0, "M"); q.addData(text, "Byte"); q.make();
  const wrap = h("div.qr"); wrap.innerHTML = q.createSvgTag({ cellSize: 8, margin: 2, scalable: true }); return wrap;
}

// family crest (parent area › Settings › Pairs game): a shield in two colours with a pattern, an emoji and the name
let crestSeq = 0;
function crestSvg(c, { ribbon = true } = {}) {
  c = c || { icon: "🏠", colors: ["#5b5bd6", "#fcc419"], pattern: "split" };
  const [a, b] = c.colors || ["#5b5bd6", "#fcc419"], id = "crest" + (++crestSeq);
  const shield = "M6 6 H94 V58 C94 88 72 106 50 116 C28 106 6 88 6 58 Z";
  const pat = {
    plain: "",
    split: `<rect x="50" y="0" width="50" height="120" fill="${b}"/>`,
    quarter: `<rect x="50" y="0" width="50" height="60" fill="${b}"/><rect x="0" y="60" width="50" height="60" fill="${b}"/>`,
    band: `<path d="M-10 20 L20 -10 L110 80 L80 110 Z" fill="${b}"/>`,
    chevron: `<path d="M0 70 L50 30 L100 70 L100 95 L50 55 L0 95 Z" fill="${b}"/>`,
  }[c.pattern] ?? "";
  const esc = t => String(t || "").replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[m]);
  const H = ribbon && c.name ? 142 : 122;
  // own picture as crest (photo folder of the pairs game), drawn into the shield
  const img = c.image && (/^[\w.-]+$/.test(c.image) || /^ha:[^<>"]+$/.test(c.image)) ? memPhotoUrl(c.image) : null;
  const box = h("span.crest");
  box.innerHTML = `<svg viewBox="0 0 100 ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${esc(c.name)}">
    <defs><clipPath id="${id}"><path d="${shield}"/></clipPath></defs>
    ${img ? `<g clip-path="url(#${id})"><rect width="100" height="120" fill="#fff"/><image href="${esc(img)}" x="0" y="0" width="100" height="120" preserveAspectRatio="xMidYMid slice"/></g>`
      : `<g clip-path="url(#${id})"><rect width="100" height="120" fill="${a}"/>${pat}</g>`}
    <path d="${shield}" fill="none" stroke="#fff" stroke-width="4"/><path d="${shield}" fill="none" stroke="rgba(0,0,0,.35)" stroke-width="1.2"/>
    ${img ? "" : `<circle cx="50" cy="56" r="25" fill="#fff" opacity=".9"/>
    <text x="50" y="57" font-size="30" text-anchor="middle" dominant-baseline="central">${esc(c.icon || "🏠")}</text>`}
    ${ribbon && c.name ? `<path d="M4 120 H96 L90 130 L96 140 H4 L10 130 Z" fill="#fff" stroke="rgba(0,0,0,.3)"/><text x="50" y="131" font-size="11" font-weight="800" text-anchor="middle" dominant-baseline="central" fill="#1f2433">${esc(c.name)}</text>` : ""}
  </svg>`;
  return box;
}

// ---------------------------------------------------------------- coins: own icon instead of the 🪙 emoji
// (the emoji looks like a grey moon on some devices) – every 🪙 in the page, also in texts from the server, becomes
// a small golden coin (img/coin.svg). Not inside form fields, options or SVG text, where only text is possible.
(function coinIcons() {
  const COIN = "\u{1FA99}", SKIP = new Set(["OPTION", "TEXTAREA", "INPUT", "SCRIPT", "STYLE", "TITLE", "text", "tspan"]);
  const swap = node => {
    const p = node.parentNode;
    if (!p || SKIP.has(p.nodeName) || (p.closest && p.closest("svg, select, [contenteditable]"))) return;
    const parts = node.nodeValue.split(COIN);
    if (parts.length < 2) return;
    const frag = document.createDocumentFragment();
    parts.forEach((t, i) => {
      if (i) {
        const img = document.createElement("img");
        img.src = "img/coin.svg"; img.alt = COIN; img.className = "coin-ic"; img.draggable = false;
        frag.append(img);
      }
      if (t) frag.append(document.createTextNode(t));
    });
    p.replaceChild(frag, node);
  };
  const scan = root => {
    if (root.nodeType === 3) { if (root.nodeValue.includes(COIN)) swap(root); return; }
    if (root.nodeType !== 1 || SKIP.has(root.nodeName)) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => n.nodeValue.includes(COIN) ? 1 : 3 });
    const found = []; while (w.nextNode()) found.push(w.currentNode);
    found.forEach(swap);
  };
  const start = () => {
    scan(document.body);
    new MutationObserver(ms => { for (const m of ms) { if (m.type === "characterData") scan(m.target); else m.addedNodes.forEach(scan); } })
      .observe(document.body, { childList: true, subtree: true, characterData: true });
  };
  if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
})();

// ---------------------------------------------------------------- ☰ the menu of the app (also on the planner page)
const APP_NAV = () => [["home", "🏠", T("Home")], ["courses", "🌍", T("Learning")], ["deck", "📇", T("My card box")], ["shop", "🛍️", T("Shop")],
  ...(window.FQ_STORIES === false ? [] : [["stories", "📚", T("Library")]]),       // stories.js – off per child (kid.js)
  ["avatar", "🧑‍🎨", T("Me")], ["family", "👨‍👩‍👧", T("Family")], ["deals", "🤝", T("Deals")], ["games", "🎲", T("Games")], ["planer", "📅", T("Planner")]]
  .filter(([k]) => k !== "deals" || !window.FQ_DEALS_OFF);      // deals (deals.js): hidden when trading is off for this profile

// ---------------------------------------------------------------- ☰ in a running game: rules, guests, actions, language
// gameMenu({ rules, invite, actions, onLeave }) → the ☰ button for the header of a live game.
//   rules:   a view (or a function returning one) shown in a popup – e.g. cardsRulesView(st.rules)
//   invite:  game key or [game, gid] → guestInvite (only for family members, not at solo tables)
//   actions: [{ ic, label, onclick, confirm, danger, hidden }] – the actions of whoever leads (skip, mix, pause, end …)
//   onLeave: leave the game screen (like ✕)
function gameMenu({ rules = null, invite = null, actions = [], onLeave = null } = {}) {
  return h("button.icon-btn.game-menu-btn", { title: T("Menu"), "aria-label": T("Menu"),
    onclick: () => openGameMenu({ rules, invite, actions, onLeave }) }, "☰");
}

function openGameMenu({ rules, invite, actions, onLeave }) {
  let release = null;
  const close = () => { back.remove(); release && release(); window.removeEventListener("hashchange", close); };
  window.addEventListener("hashchange", close);              // another page: the menu of the game goes away
  const item = (ic, label, fn, cls = "") => h("button.drawer-item" + cls, { onclick: () => { close(); fn(); } }, h("span.foot-ic", ic), h("span", label));
  const showRules = () => { const view = typeof rules === "function" ? rules() : rules;
    const m = modal(h("div", view, h("button.btn", { onclick: () => m.close() }, T("Close")))); };
  const soundItem = h("button.foot-item", { onclick: () => { Sound.on = !Sound.on; drawSound(); } });
  const drawSound = () => soundItem.replaceChildren(h("span.foot-ic", Sound.on ? "🔊" : "🔇"), h("span", Sound.on ? T("Sound on") : T("Sound off")));
  drawSound();
  const acts = (actions || []).filter(a => a && !a.hidden);
  const drawer = h("nav.drawer.game-drawer", { role: "dialog", "aria-label": T("Menu") },
    h("div.drawer-head", h("button.icon-btn", { "aria-label": T("Close"), onclick: close }, "✕"), h("strong", T("Game"))),
    rules ? item("📜", T("Rules"), showRules) : null,
    invite ? item("👥", T("Invite guests"), () => guestInvite(...[].concat(invite))) : null,
    ...acts.map(a => item(a.ic || "▶", a.label, async () => { if (a.confirm && !(await confirmDialog(I18N.tr(a.confirm)))) return; a.onclick(); }, a.danger ? ".danger" : "")),
    h("hr"),
    footLang(), footTheme(), soundItem,
    onLeave ? item("🚪", T("Leave the game"), onLeave) : null);
  const back = h("div.drawer-back.game-menu-back", { onclick: e => { if (e.target === back) close(); } }, drawer);
  document.body.append(back);
  release = focusTrap(back, drawer, close);
  requestAnimationFrame(() => back.classList.add("open"));
}

// who begins (parent area › Games): «choose» → the leader picks a player when starting the game.
// beginGame(path, players) posts to path (e.g. "community/cards/tschau/begin") – with {starter} when chosen.
let _starterMode = null;
async function beginGame(path, players, body = {}) {
  if (_starterMode === null) { try { _starterMode = (await api("community/starter")).mode; } catch { _starterMode = "dice"; } }
  if (_starterMode !== "choose" || !(players || []).length) return api(path, { method: "POST", body });
  const pick = await new Promise(resolve => {
    const m = modal(h("div.form.center", h("h2", "👉 ", T("Who begins?")),
      h("div.starter-pick", ...players.map(p => h("button.starter-btn", { onclick: () => { resolve(p.id); m.close(); } },
        p.bot ? h("span.starter-emoji", p.emoji || "🤖") : avatarSvg(p.avatar || {}, 52), C(p.name, "strong")))),
      h("button.btn.ghost", { onclick: () => { m.close(); resolve(undefined); } }, T("Cancel"))), { onClose: () => resolve(undefined) });
  });
  if (pick === undefined) return null;
  return api(path, { method: "POST", body: { ...body, starter: String(pick) } });
}

// «🎲 Mia begins!» – once per game on every device (st.starter from cardgames.apply_starter)
// deals: the starter gets the dealer button (poker) – the first to act sits left of the big blind, so «… deals!»
function starterBanner(starter, key, deals) {
  if (!starter || !starter.id) return;
  const k = "fq.starter." + key + "." + (starter.at || "");
  try { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, "1"); } catch {}
  if (starter.at && Date.now() / 1000 - starter.at > 120) return;           // an old game: no banner any more
  const text = I18N.tr(deals ? (starter.how === "dice" ? T("The dice decided: {0} deals!") : T("{0} deals!"))
    : starter.how === "dice" ? T("The dice decided: {0} begins!") : T("{0} begins!")).replace("{0}", starter.name);
  const b = h("div.starter-banner" + (starter.how === "dice" ? ".dice" : ""), h("span.starter-die", starter.how === "dice" ? "🎲" : "👉"), h("span", text));
  document.body.append(b);
  setTimeout(() => b.classList.add("gone"), 2600);
  setTimeout(() => b.remove(), 3200);
}

// «Made with your AI»: the English instructions + format for an AI (familyquest/ai_format.py: self-describing JSON) – download or copy
// a file from the API (with the login of this device) as a download
async function downloadApi(path, name) {
  const headers = {};
  if (Auth.kid && !window.FQ_PARENT_AREA) headers["X-FQ-Token"] = Auth.kid;
  if (Auth.parent) headers["X-FQ-Parent"] = Auth.parent;
  try {
    const r = await fetch("api/" + path, { headers });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "HTTP " + r.status);
    const url = URL.createObjectURL(await r.blob());
    const a = h("a", { href: url, download: name }); document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (e) { toast(e.message, "bad"); }
}

// «Made with your AI» (packs, quizzes, books, adventure games): the same box everywhere, in this order –
// 1. «⬇️ Download template for the AI» (a self-describing JSON: familyquest/ai_format.py, stories.py, picturebooks.py,
// adventuregame.py), 2. the example prompt (a monospace block, the parts to fill in [like this] highlighted),
// 3. «📋 Copy prompt», 4. a short hint, 5. «📤 Import the AI's JSON file» – the AI hands back a file, nothing is pasted
// (copying long answers broke them). `onFile(file, text)` gets the chosen file and its text (UTF-8, a BOM removed).
function aiPromptBox(promptText, { template, name, onFile, accept = ".json,.txt,application/json,text/plain" } = {}) {
  const text = I18N.tr(promptText) + (template ? "\n" + I18N.tr(T("Use exactly the format of the attached Family Quest template and give me the result as a downloadable .json file.")) : "");
  const pre = h("pre.ai-prompt-text", { translate: "no", tabindex: "0" },
    ...text.split(/(\[[^\]\n]+\])/).map((p, i) => i % 2 ? h("mark.ai-ph", p) : p));
  const selectPrompt = () => { const r = document.createRange(); r.selectNodeContents(pre); const s = getSelection(); s.removeAllRanges(); s.addRange(r); pre.focus(); };
  const copy = async () => {
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch {}
    if (!ok) {                                  // no clipboard API (plain http in the home network): the old way
      const ta = h("textarea", { readonly: true, style: { position: "fixed", top: "0", left: "0", opacity: "0", width: "1px", height: "1px" } });
      ta.value = text; (pre.closest("dialog, .modal") || document.body).append(ta); ta.select();
      try { ok = document.execCommand("copy"); } catch {}
      ta.remove();
    }
    if (ok) return toast(I18N.tr(T("Copied – paste it into the chat of your AI")), "good");
    selectPrompt();
    toast(I18N.tr(T("Copying is blocked here – the prompt is selected: copy it yourself and attach the template file.")), "bad");
  };
  const file = h("input.ai-file", { type: "file", accept, hidden: true, onchange: async () => {
    const f = file.files[0]; file.value = "";
    if (!f || !onFile) return;
    if (f.size > 5e6) return toast(I18N.tr(T("The file is too large")), "bad");
    let t = "";
    try { t = (await f.text()).replace(/^\uFEFF/, ""); } catch {}
    onFile(f, t);
  } });
  return h("div.ai-prompt",
    template ? h("div.row.wrap.ai-tpl-row", h("a.btn.ai-tpl", { style: { textDecoration: "none" }, href: template, download: name || "family-quest-template.json" },
      "⬇️ ", T("Download template for the AI"))) : null,
    h("div.ai-prompt-head", h("b", "💬 ", T("Example prompt"))),
    pre,
    h("div.row.wrap", h("button.btn.small.ghost.ai-copy", { type: "button", onclick: copy }, "📋 ", T("Copy prompt"))),
    h("p.small.muted.ai-hint", template ? T("Download the template, copy the prompt, then attach the template in the chat of your AI (ChatGPT, Claude, Gemini …) and fill in the highlighted [parts]. Upload the JSON file you get back.")
      : T("Copy the prompt into the chat of your AI and fill in the highlighted [parts].")),
    onFile ? h("div.row.wrap.ai-upload", h("button.btn.ai-import", { type: "button", onclick: () => file.click() }, "📤 ", T("Import the AI's JSON file")), file) : null);
}

// link to the parent area: when it is only offered in Home Assistant, straight to the Family Quest panel there
let _parentHref = null;
async function parentAreaHref() {
  if (_parentHref) return _parentHref;
  let href = "parents";
  try {
    const i = await api("info");
    if (i.parent_ha_only && !i.via_ha) {
      const p = await api("ha-panel");
      if (p.slug) href = `${p.ssl ? "https" : "http"}://${location.hostname}:${p.port}${p.path || "/app/" + p.slug}`;
    }
  } catch { /* «parents» explains where the parent area is */ }
  return (_parentHref = href);
}

function openAppMenu({ active, onGo, onLogout, season = null, seasonOn = true, onSeason = null }) {
  let release = null;
  const close = () => { back.remove(); release && release(); };
  const soundItem = h("button.foot-item", { onclick: () => { Sound.on = !Sound.on; drawSound(); } });
  const drawSound = () => soundItem.replaceChildren(h("span.foot-ic", Sound.on ? "🔊" : "🔇"), h("span", Sound.on ? T("Sound on") : T("Sound off")));
  drawSound();
  const seasonItem = season && onSeason ? h("button.foot-item", { onclick: () => { close(); onSeason(); } },
    h("span.foot-ic", season.icon || "🎨"), h("span", seasonOn ? T("Season design on") : T("Season design off"))) : null;
  const parentItem = h("a.foot-item.parent-item", { href: "parents" }, h("span.foot-ic", "🔐"), h("span", T("Parent area")));
  const drawer = h("nav.drawer", { role: "dialog", "aria-label": T("Menu") },
    h("div.drawer-head", h("button.icon-btn", { "aria-label": T("Close"), onclick: close }, "✕"), h("strong", "Family Quest")),
    ...APP_NAV().map(([k, ic, n]) => h("button.drawer-item" + (k === active ? ".on" : ""), { onclick: () => { close(); onGo(k); } }, h("span.foot-ic", ic), h("span", n),
      (window.FQ_NAV_BADGES || {})[k] ? h("span.deal-badge", String(window.FQ_NAV_BADGES[k])) : null)),
    h("hr"),
    footLang(), footTheme(), soundItem, seasonItem,
    pwaStandalone() ? null : h("button.foot-item.pwa-item", { onclick: () => { close(); installAppDialog(); } }, h("span.foot-ic", "📲"), h("span", T("Install app"))),
    h("button.foot-item", { onclick: () => { close(); onLogout(); } }, h("span.foot-ic", "🔒"), h("span", T("Log out"))),
    parentItem);
  parentAreaHref().then(href => { parentItem.href = href; });
  const back = h("div.drawer-back", { onclick: e => { if (e.target === back) close(); } }, drawer);
  document.body.append(back);
  release = focusTrap(back, drawer, close);
  requestAnimationFrame(() => back.classList.add("open"));
}

// ---------------------------------------------------------------- «📲 Install app»: Family Quest on the home screen
// The browser's own install offer (Chrome, Edge, Samsung Internet; only over https): kept for the «Install now» button.
let _pwaPrompt = null;
window.addEventListener("beforeinstallprompt", e => { e.preventDefault(); _pwaPrompt = e; });
window.addEventListener("appinstalled", () => { _pwaPrompt = null; });
// already opened from the home screen icon: no install entry
function pwaStandalone() {
  try { return matchMedia("(display-mode: standalone)").matches || matchMedia("(display-mode: fullscreen)").matches || navigator.standalone === true; }
  catch { return false; }
}
// the device from the user agent: iPhone / iPad (iPadOS says «Macintosh» but has a touch screen), Android, else null
function pwaDevice(ua = navigator.userAgent || "") {
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && (navigator.maxTouchPoints || 0) > 1);
  if (ios) return { os: "ios", browser: /CriOS|FxiOS|EdgiOS|OPiOS|OPT\/|GSA\/|YaBrowser|DuckDuckGo/.test(ua) ? "other" : "safari" };
  if (/Android/i.test(ua)) return { os: "android", browser: /SamsungBrowser/.test(ua) ? "samsung" : "chrome" };
  return { os: null, browser: null };
}
// the buttons as the phone draws them (outline icons, inline SVG)
const PWA_ICONS = {
  share: '<path d="M12 3v12M7.5 7.5 12 3l4.5 4.5"/><path d="M8 10H6a1.5 1.5 0 0 0-1.5 1.5v8A1.5 1.5 0 0 0 6 21h12a1.5 1.5 0 0 0 1.5-1.5v-8A1.5 1.5 0 0 0 18 10h-2"/>',
  addhome: '<rect x="4" y="4" width="16" height="16" rx="3.5"/><path d="M12 8.5v7M8.5 12h7"/>',
  kebab: '<circle cx="12" cy="5.5" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="18.5" r="1.4" fill="currentColor" stroke="none"/>',
  burger: '<path d="M4.5 7h15M4.5 12h15M4.5 17h15"/>',
  install: '<rect x="7" y="2.5" width="10" height="19" rx="2.2"/><path d="M12 7.5v7M9.2 11.8 12 14.6l2.8-2.8"/>',
};
const pwaIcon = (k, label) => h("span.pwa-ic", { role: "img", "aria-label": label || "", html:
  `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PWA_ICONS[k]}</svg>` });

// forOther: the parent area shows it for a child's device (no «Install now», the address to open first)
function installAppDialog({ forOther = false, link = null } = {}) {
  const dev = forOther ? { os: null, browser: null } : pwaDevice();
  let os = dev.os || (/Mac|iPhone|iPad/.test(navigator.platform || "") ? "ios" : "android");
  const step = (text, icon, hint) => h("li", h("div.pwa-step", h("span", text), icon), hint ? h("div.small.muted", hint) : null);
  const block = (title, here, steps, note) => h("div.pwa-block" + (here ? ".here" : ""),
    h("h3", title, here ? h("span.chip.good", T("this browser")) : null), h("ol.pwa-steps", ...steps), note ? h("p.small.muted", note) : null);
  const homeStep = () => step(T("Scroll down and tap «Add to Home Screen»."), pwaIcon("addhome", T("Add to Home Screen")));
  const ios = () => {
    const safari = block("Safari", dev.os === "ios" && dev.browser === "safari", [
      step(T("Tap the menu icon to the left of the address."), pwaIcon("burger", T("Menu")), T("At the bottom of the screen. Older iOS versions show the Share button directly – then skip this step.")),
      step(T("Tap «Share»."), pwaIcon("share", T("Share")), T("On the iPad: the Share button at the top right.")),
      homeStep(), step(T("Tap «Add» at the top right."))]);
    const other = block(T("Chrome, Firefox, Edge …"), dev.os === "ios" && dev.browser === "other", [
      step(T("Tap the Share button in the address bar."), pwaIcon("share", T("Share")), T("At the top right next to the address. If it is missing: open the menu and choose «Share».")),
      homeStep(), step(T("Tap «Add» at the top right."))], T("Before iOS 16.4 this only works in Safari."));
    return dev.browser === "other" ? [other, safari] : [safari, other];
  };
  const android = () => {
    const chrome = block(T("Chrome (and most other browsers)"), dev.os === "android" && dev.browser === "chrome", [
      step(T("Tap the menu."), pwaIcon("kebab", T("Menu")), T("The three dots at the top right.")),
      step(T("Tap «Install app» or «Add to home screen»."), pwaIcon("install", T("Install app"))),
      step(T("Confirm with «Install» or «Add»."))]);
    const samsung = block("Samsung Internet", dev.os === "android" && dev.browser === "samsung", [
      step(T("Tap the menu."), pwaIcon("burger", T("Menu")), T("The three lines at the bottom right.")),
      step(T("Tap «Add page to»."), pwaIcon("addhome", T("Add page to"))),
      step(T("Choose «Home screen»."))]);
    return dev.browser === "samsung" ? [samsung, chrome] : [chrome, samsung];
  };
  const seg = h("div.seg.pwa-seg", { role: "tablist", "aria-label": T("Device") });
  const body = h("div.pwa-body");
  const draw = () => {
    seg.replaceChildren(...[["ios", "iPhone / iPad"], ["android", "Android"]].map(([k, n]) =>
      h("button" + (k === os ? ".on" : ""), { type: "button", role: "tab", "aria-selected": String(k === os), translate: "no", onclick: () => { os = k; draw(); } }, n)));
    body.replaceChildren(...(os === "ios" ? ios() : android()));
  };
  draw();
  const now = !forOther && _pwaPrompt ? h("div.pwa-now", h("p", T("This browser can install it right away:")),
    h("button.btn", { type: "button", onclick: async () => {
      const ev = _pwaPrompt; if (!ev) return;
      try { ev.prompt(); const r = await ev.userChoice; _pwaPrompt = null; if (r && r.outcome === "accepted") m.close(); } catch {}
    } }, "📲 ", T("Install now"))) : null;
  const ingress = !forOther && location.pathname.includes("/hassio_ingress/");
  const m = modal(h("div.form.pwa-dlg", h("h2", "📲 ", T("Install app")),
    h("p", T("Put Family Quest on the home screen: it opens like an app – full screen, without the address bar.")),
    forOther ? h("p", T("On the child's phone or tablet: scan the QR code or open the address, then follow the steps.")) : null,
    forOther && link ? h("p.small.center", { translate: "no" }, h("a", { href: link, target: "_blank", rel: "noopener" }, link)) : null,
    ingress ? h("p.small.muted", "ℹ️ ", T("Open the app on its own address first (parent area › ⭐ Family Quest App): an icon of the Home Assistant address needs a Home Assistant login.")) : null,
    now, seg, body,
    !forOther && !dev.os ? h("p.small.muted", T("On a computer: Chrome and Edge show an install button in the address bar.")) : null,
    h("p.small.muted", T("Then open Family Quest with its icon on the home screen.")),
    h("div.row.wrap", h("button.btn.ghost", { type: "button", onclick: () => m.close() }, T("Close")))));
  return m;
}

// the card of a game (app › Games): the same two choices in the same order everywhere – «🤖 Alone against bots» (the
// main button; null when bots are switched off for the game) and «👨‍👩‍👧 Open a family table»
function gameStartRow(solo, table, { bots = true } = {}) {
  return h("div.row.wrap.game-start-row",
    solo ? h("button.btn", { onclick: solo }, bots ? "🤖 " : "🙋 ", bots ? T("Alone against bots") : T("Alone")) : null,
    h("button.btn" + (solo ? ".ghost" : ""), { onclick: table }, "👨‍👩‍👧 ", T("Open a family table")));
}

// a game page opened directly (link, bookmark) while no table is open: in the app the child can open one right here –
// the start dialog of the game, then the page shows the new table. Elsewhere (parent area, guests) only «Back».
function noTableActions(game, back) {
  const backBtn = h("button.btn.ghost", { onclick: back }, T("Back"));
  if (window.FQ_PARENT_AREA || typeof canPlay !== "function" || !canPlay(game) || typeof route !== "function") return h("div.row.center", h("button.btn", { onclick: back }, T("Back")));
  const again = () => route();
  const fn = { tschau: () => cardsStartDialog("tschau", false, again), karussell: () => cardsStartDialog("karussell", false, again),
    domino: () => dominoStartDialog(false, again), dorfmarkt: () => dorfmarktStartDialog(false, again), heimwaerts: () => heimwaertsStartDialog(false, again),
    jass: () => jassStartDialog(false, again), kartenlauf: () => kartenlaufStartDialog(false, again), klatsch: () => klatschStartDialog(false, again),
    paarjagd: () => paarjagdStartDialog(false, again), song: () => songStartDialog(again), stadtland: () => stadtlandStartDialog(again),
    verboten: () => verbotenStartDialog(again), werwolf: () => werwolfStartDialog(again), werbinich: () => werbinichStartDialog(again),
    wuerfel: () => wuerfelStartDialog(false, again), zeichnen: () => zeichnenStartDialog(again),
    stempeljagd: () => stempeljagdStartDialog(false, again) }[game];
  return h("div.row.center.wrap", fn ? h("button.btn", { onclick: () => fn() }, "👨‍👩‍👧 ", T("Open a family table")) : null, backBtn);
}
