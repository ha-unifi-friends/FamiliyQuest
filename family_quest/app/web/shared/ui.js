// Small helpers shared by the children's app and the parent area. No framework, no build step.
"use strict";

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

async function api(path, { method = "GET", body, form, parent = false } = {}) {
  const headers = {};
  // the parent area acts as the parent – a child still logged in on this device must not be used there
  if (Auth.kid && !window.FQ_PARENT_AREA) headers["X-FQ-Token"] = Auth.kid;
  if (Auth.parent) headers["X-FQ-Parent"] = Auth.parent;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const r = await fetch("api/" + path.replace(/^\//, ""), { method, headers, body: payload });
  let data = null;
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("json")) data = await r.json().catch(() => null);
  if (!r.ok) {
    const msg = data && (typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(", ") : "") || ("HTTP " + r.status);
    throw new ApiError(r.status, msg);
  }
  return data;
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

const Sound = {
  ctx: null,
  get on() { try { return localStorage.getItem("fq.sound") !== "0"; } catch { return true; } },
  set on(v) { try { localStorage.setItem("fq.sound", v ? "1" : "0"); } catch {} },
  play(kind) {
    if (!this.on) return;
    try {
      this.ctx = this.ctx || new (window.AudioContext || window.webkitAudioContext)();
      const notes = { right: [660, 880], wrong: [300, 220], done: [523, 659, 784, 1046], tap: [500] }[kind] || [440];
      notes.forEach((f, i) => {
        const o = this.ctx.createOscillator(), g = this.ctx.createGain(), t = this.ctx.currentTime + i * 0.11;
        o.type = kind === "wrong" ? "triangle" : "sine"; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.18, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
        o.connect(g).connect(this.ctx.destination); o.start(t); o.stop(t + 0.2);
      });
    } catch {}
  },
};

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
/** Dates and times always in the format of the chosen language. Accepts "2026-12-24", "2026-12-24 18:30" or ISO. */
const _when = v => v instanceof Date ? v : new Date(/^\d{4}-\d\d-\d\d$/.test(String(v)) ? v + "T12:00" : String(v).replace(" ", "T"));
const fmtDate = (v, o = { day: "numeric", month: "numeric", year: "numeric" }) => v ? _when(v).toLocaleDateString(I18N.locale, o) : "";
const fmtTime = v => v ? _when(v).toLocaleTimeString(I18N.locale, { hour: "2-digit", minute: "2-digit" }) : "";
const fmtDateTime = v => v ? fmtDate(v) + " " + fmtTime(v) : "";

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

function modal(content, { onClose, wide = false } = {}) {
  const back = h("div.modal-back", { onclick: e => { if (e.target === back) close(); } });
  const box = h("div.modal" + (wide ? ".wide" : ""), { role: "dialog", "aria-modal": "true" }, content);
  back.append(box);
  const close = () => { back.remove(); document.removeEventListener("keydown", esc); onClose && onClose(); };
  const esc = e => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", esc);
  back.addEventListener("cancel", close);
  document.body.append(back);
  return { close, box };
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
  ["avatar", "🧑‍🎨", T("Me")], ["family", "👨‍👩‍👧", T("Family")], ["games", "🎲", T("Games")], ["planer", "📅", T("Planner")]];

// link to the parent area: when it is only offered in Home Assistant, straight to the Family Quest panel there
let _parentHref = null;
async function parentAreaHref() {
  if (_parentHref) return _parentHref;
  let href = "eltern";
  try {
    const i = await api("info");
    if (i.parent_ha_only && !i.via_ha) {
      const p = await api("ha-panel");
      if (p.slug) href = `${p.ssl ? "https" : "http"}://${location.hostname}:${p.port}/${p.slug}`;
    }
  } catch { /* «eltern» explains where the parent area is */ }
  return (_parentHref = href);
}

function openAppMenu({ active, onGo, onLogout, season = null, seasonOn = true, onSeason = null }) {
  const close = () => { back.remove(); document.removeEventListener("keydown", esc); };
  const esc = e => { if (e.key === "Escape") close(); };
  const soundItem = h("button.foot-item", { onclick: () => { Sound.on = !Sound.on; drawSound(); } });
  const drawSound = () => soundItem.replaceChildren(h("span.foot-ic", Sound.on ? "🔊" : "🔇"), h("span", Sound.on ? T("Sound on") : T("Sound off")));
  drawSound();
  const seasonItem = season && onSeason ? h("button.foot-item", { onclick: () => { close(); onSeason(); } },
    h("span.foot-ic", season.icon || "🎨"), h("span", seasonOn ? T("Season design on") : T("Season design off"))) : null;
  const parentItem = h("a.foot-item.parent-item", { href: "eltern" }, h("span.foot-ic", "🔐"), h("span", T("Parent area")));
  const drawer = h("nav.drawer", { role: "dialog", "aria-label": T("Menu") },
    h("div.drawer-head", h("button.icon-btn", { "aria-label": T("Close"), onclick: close }, "✕"), h("strong", "Family Quest")),
    ...APP_NAV().map(([k, ic, n]) => h("button.drawer-item" + (k === active ? ".on" : ""), { onclick: () => { close(); onGo(k); } }, h("span.foot-ic", ic), h("span", n))),
    h("hr"),
    footLang(), footTheme(), soundItem, seasonItem,
    h("button.foot-item", { onclick: () => { close(); onLogout(); } }, h("span.foot-ic", "🔒"), h("span", T("Log out"))),
    parentItem);
  parentAreaHref().then(href => { parentItem.href = href; });
  const back = h("div.drawer-back", { onclick: e => { if (e.target === back) close(); } }, drawer);
  document.body.append(back);
  document.addEventListener("keydown", esc);
  requestAnimationFrame(() => back.classList.add("open"));
}
