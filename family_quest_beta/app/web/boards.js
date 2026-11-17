// Bulletin boards: endless pin boards of the family (familyquest/boards.py) – sticky notes, texts, freehand lines and
// shapes; zoom from 5 % to 400 %, live with everybody on the board (their pointer, what they edit).
// Uses shared/ui.js (h, C, api, toast, modal, avatarSvg). The children's app (kid.js) and the parent area (parent.js)
// show the list with boardsSection() and open a board with boardLive().
"use strict";

const BB_NOTE = ["#fff1a8", "#ffd8a8", "#ffc9c9", "#fcc2d7", "#d0bfff", "#a5d8ff", "#99e9f2", "#c3fae8"];
const BB_INK = ["var(--fg)", "#e03131", "#f08c00", "#2f9e44", "#1c7ed6", "#7048e8", "#d6336c", "#868e96"];
const BB_EMOJI = ["📌", "💡", "🏖️", "🎄", "🎂", "🍝", "🧳", "🏡", "🎨", "📚", "⚽", "🎉", "🛒", "🌱", "🐾", "❤️"];
const BB_MIN = 0.05, BB_MAX = 4, BB_SYNC_MS = 1000, BB_PTR_MS = 300, BB_UNDO = 50;

// ---------------------------------------------------------------- the list on the Family page
async function boardsSection(me = S.profile, open = id => go("board/" + id)) {
  const sec = h("section.card.bb-sec");
  const draw = async () => {
    let list;
    try { list = await api("community/boards"); } catch (e) { return sec.replaceChildren(h("p.bad", e.message)); }
    const act = list.filter(b => !b.archived), old = list.filter(b => b.archived);
    const tile = b => h("div.bb-tile" + (b.archived ? ".archived" : ""),
      h("button.bb-open", { onclick: () => open(b.id, draw) },
        h("span.bb-emoji", b.emoji), h("span.bb-tt", C(b.title, "strong"),
          h("span.small.muted", I18N.tr(T("Items: {0}")).replace("{0}", b.items), " · ", C(b.author))),
        b.new ? h("span.chip.vote.bb-new", I18N.tr(T("New: {0}")).replace("{0}", b.new)) : null,
        b.here.length ? h("span.bb-here", ...b.here.slice(0, 4).map(p => h("span.bb-av", { title: p.name, style: { "--who": p.color } }, avatarSvg(p.avatar, 26)))) : null),
      b.manage ? h("button.icon-btn.bb-more", { title: T("Edit board"), onclick: () => boardDialog(b, draw) }, "⋯") : null);
    sec.replaceChildren(h("div.sec-head", h("h2", "📌 ", T("Bulletin boards")),
      h("div.head-actions", h("button.btn", { onclick: () => boardDialog(null, draw) }, "+ ", T("New board")))),
      h("p.small.muted", T("Endless pin boards for the whole family: sticky notes, texts and drawings – everybody works on them at the same time.")),
      act.length ? h("div.bb-tiles", ...act.map(tile)) : h("p.small.muted", T("No board yet – make the first one!")),
      old.length ? h("details.bb-archived", h("summary.small", I18N.tr(T("Archived ({0})")).replace("{0}", old.length)), h("div.bb-tiles", ...old.map(tile))) : "");
  };
  await draw();
  return sec;
}

// new board, or rename / archive / remove one
function boardDialog(b, done) {
  let emoji = b ? b.emoji : BB_EMOJI[0];
  const title = h("input", { type: "text", maxlength: 60, value: b ? b.title : "", placeholder: I18N.tr(T("e.g. Summer holidays")) });
  const own = h("input.bb-own-emoji", { type: "text", maxlength: 8, placeholder: "🙂", "aria-label": T("Own emoji") });
  const pick = h("div.bb-emojis");
  const drawPick = () => pick.replaceChildren(...BB_EMOJI.map(e => h("button.bb-ej" + (e === emoji ? ".on" : ""), { type: "button", onclick: () => { emoji = e; own.value = ""; drawPick(); } }, e)), own);
  own.oninput = () => { if (own.value.trim()) { emoji = own.value.trim(); pick.querySelectorAll(".bb-ej").forEach(x => x.classList.remove("on")); } };
  drawPick();
  const call = async (fn, msg) => { try { await fn(); m.close(); if (msg) toast(msg, "good"); done(); } catch (e) { toast(e.message, "bad"); } };
  const save = () => {
    if (!title.value.trim()) return title.focus();
    call(() => b ? api("community/boards/" + b.id, { method: "PUT", body: { title: title.value, emoji } })
      : api("community/boards", { method: "POST", body: { title: title.value, emoji } }), T("Saved"));
  };
  const m = modal(h("div.form", h("h2", "📌 ", b ? T("Edit board") : T("New board")),
    h("label.field", T("Title"), title), h("div.field", h("b", T("Emoji")), pick),
    h("div.row", h("button.btn", { onclick: save }, "💾 ", T("Save")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel"))),
    b ? h("div.row.bb-danger",
      h("button.btn.small.ghost", { onclick: () => call(() => api("community/boards/" + b.id, { method: "PUT", body: { archived: !b.archived } })) },
        b.archived ? "📤 " : "🗄️ ", b.archived ? T("Take out of the archive") : T("Archive")),
      h("button.btn.small.ghost", { onclick: () => confirm(I18N.tr(T("Remove this board with everything on it?"))) && call(() => api("community/boards/" + b.id, { method: "DELETE" })) },
        "🗑️ ", T("Remove"))) : null));
  title.focus();
}

// the children's app: #/board/<id>
async function boardView(id) {
  const box = h("div");
  screen("family", box);
  boardLive(box, S.profile, id, () => go("family"));
}

// ---------------------------------------------------------------- one board, full screen
function boardLive(box, me, boardId, back) {
  const items = new Map();                 // key (String id, or "t…" before the server gave one) → {id, k, d, z, by, ub}
  const els = new Map();                   // key → element
  const tmp = {};                          // temporary id → real id
  const people = {};
  let others = [], board = null, since = 0, alive = true, timer = null, inflight = false, lastSend = 0, ptrDirty = false;
  let queue = [], pend = new Map(), undo = [], tmpN = 0;
  let tool = "select", noteC = 0, inkC = 0, penW = 4, shapeF = "rect", sel = null, editing = null, readOnly = false;
  const view = { s: 1, x: 0, y: 0 };      // screen = world * s + (x, y)
  let ptr = null;                          // own pointer (world) for the others
  const key = id => String(tmp[id] != null ? tmp[id] : id);
  const real = id => { const r = tmp[id] != null ? tmp[id] : id; return typeof r === "number" ? r : (/^\d+$/.test(r) ? +r : r); };

  // ---------- layout
  const world = h("div.bb-world", { translate: "no" });
  const cursors = h("div.bb-cursors", { translate: "no" });
  const vp = h("div.bb-view", world, cursors);
  const titleEl = h("div.bb-title");
  const bar = h("div.bb-people");
  const opts = h("div.bb-opts");
  const tools = h("div.bb-tools");
  const zoomPct = h("button.bb-zbtn.bb-pct", { title: T("100 %"), onclick: () => zoomTo(1) }, "100 %");
  const zoom = h("div.bb-zoom",
    h("button.bb-zbtn", { title: T("Zoom in"), onclick: () => zoomTo(view.s * 1.5) }, "+"), zoomPct,
    h("button.bb-zbtn", { title: T("Zoom out"), onclick: () => zoomTo(view.s / 1.5) }, "−"),
    h("button.bb-zbtn", { title: T("Show everything"), onclick: () => fitAll() }, "⤢"));
  const top = h("div.bb-top", h("button.icon-btn.bb-close", { title: T("Close"), onclick: () => close() }, "✕"), titleEl, bar);
  box.classList.add("bb-full", "quiz-full");
  document.body.classList.add("quiz-open");
  box.replaceChildren(top, vp, zoom, h("div.bb-bottom", opts, tools));

  function close() { stop(); back(); }
  function stop() {
    if (!alive) return;
    alive = false; clearTimeout(timer);
    commitEdit();
    if (queue.length) api(`community/boards/${boardId}/sync`, { method: "POST", body: { since, ops: queue.map(fixOp) } }).catch(() => {});
    api(`community/boards/${boardId}/leave`, { method: "POST" }).catch(() => {});
    try { localStorage.setItem("fq.board." + boardId, JSON.stringify(view)); } catch {}
    window.removeEventListener("hashchange", onHash); window.removeEventListener("keydown", onKey); window.removeEventListener("resize", onResize);
    box.classList.remove("bb-full", "quiz-full"); document.body.classList.remove("quiz-open");
  }
  const onHash = () => { stop(); if (box.parentNode === document.body) box.remove(); };
  window.addEventListener("hashchange", onHash);

  // ---------- view: pan and zoom (one transformed layer)
  const rect = () => vp.getBoundingClientRect();
  const toWorld = (cx, cy) => { const r = rect(); return { x: (cx - r.left - view.x) / view.s, y: (cy - r.top - view.y) / view.s }; };
  function applyView() {
    world.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.s})`;
    world.style.setProperty("--inv", String(1 / view.s));
    const g = 32 * view.s * (view.s < 0.25 ? 8 : 1);
    vp.style.backgroundSize = `${g}px ${g}px`;
    vp.style.backgroundPosition = `${view.x}px ${view.y}px`;
    zoomPct.textContent = Math.round(view.s * 100) + " %";
    drawCursors();
    ptrDirty = true;
  }
  function zoomAt(s, cx, cy) {                       // cx/cy: screen point relative to the view that stays put
    s = Math.min(BB_MAX, Math.max(BB_MIN, s));
    view.x = cx - (cx - view.x) * s / view.s; view.y = cy - (cy - view.y) * s / view.s; view.s = s;
    applyView();
  }
  function zoomTo(s) { const r = rect(); zoomAt(s, r.width / 2, r.height / 2); }
  function showRect(b, maxS = 1.5) {                // world box → fits into the view
    const r = rect(), pad = 30, t = top.offsetHeight, hh = Math.max(100, r.height - t - box.querySelector(".bb-bottom").offsetHeight);
    const s = Math.min(maxS, Math.max(BB_MIN, Math.min((r.width - 2 * pad - 50) / Math.max(1, b.w), (hh - 2 * pad) / Math.max(1, b.h))));
    view.s = s; view.x = (r.width - 50) / 2 - (b.x + b.w / 2) * s; view.y = t + hh / 2 - (b.y + b.h / 2) * s;
    applyView();
  }
  function bbox(it) {
    const d = it.d, el = els.get(key(it.id));
    if (it.k === "note") return { x: d.x, y: d.y, w: d.w, h: d.h };
    if (it.k === "text") return { x: d.x, y: d.y, w: d.w, h: el ? el.offsetHeight : d.s * 1.4 };
    if (it.k === "shape") return { x: Math.min(d.x, d.x + d.w), y: Math.min(d.y, d.y + d.h), w: Math.abs(d.w), h: Math.abs(d.h) };
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < d.p.length; i += 2) { x0 = Math.min(x0, d.p[i]); x1 = Math.max(x1, d.p[i]); y0 = Math.min(y0, d.p[i + 1]); y1 = Math.max(y1, d.p[i + 1]); }
    return { x: d.x + x0, y: d.y + y0, w: x1 - x0, h: y1 - y0 };
  }
  function fitAll() {
    if (!items.size) { const r = rect(); view.s = 1; view.x = r.width / 2; view.y = r.height / 2; return applyView(); }
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const it of items.values()) { const b = bbox(it); x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y); x1 = Math.max(x1, b.x + b.w); y1 = Math.max(y1, b.y + b.h); }
    showRect({ x: x0, y: y0, w: x1 - x0, h: y1 - y0 }, 1);
  }

  // ---------- drawing the items
  const ink = c => BB_INK[c] || BB_INK[0];
  const svgEl = (tag, attrs) => { const e = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const [k, v] of Object.entries(attrs)) k === "stroke" ? (e.style.stroke = v) : e.setAttribute(k, v); return e; };
  const pathOf = p => { let s = "M" + p[0] + " " + p[1]; for (let i = 2; i < p.length; i += 2) s += "L" + p[i] + " " + p[i + 1]; if (p.length === 2) s += "l0.01 0"; return s; };
  function shapeParts(d) {
    const st = { fill: "none", stroke: ink(d.c), "stroke-width": d.sw, "stroke-linecap": "round", "stroke-linejoin": "round" };
    if (d.f === "rect") return [svgEl("rect", { ...st, x: 0, y: 0, width: d.w, height: d.h, rx: Math.min(12, d.w / 4, d.h / 4) })];
    if (d.f === "ellipse") return [svgEl("ellipse", { ...st, cx: d.w / 2, cy: d.h / 2, rx: d.w / 2, ry: d.h / 2 })];
    const out = [svgEl("line", { ...st, x1: 0, y1: 0, x2: d.w, y2: d.h })];
    if (d.f === "arrow") {
      const a = Math.atan2(d.h, d.w), L = Math.max(12, d.sw * 4);
      const p = (da) => (d.w - L * Math.cos(a + da)).toFixed(1) + " " + (d.h - L * Math.sin(a + da)).toFixed(1);
      out.push(svgEl("path", { ...st, d: `M${p(0.45)}L${d.w} ${d.h}L${p(-0.45)}` }));
    }
    return out;
  }
  function hitPath(it) {
    const d = it.d;
    if (it.k === "stroke") return pathOf(d.p);
    if (d.f === "rect" || d.f === "ellipse") return `M0 0H${d.w}V${d.h}H0Z`;
    return `M0 0L${d.w} ${d.h}`;
  }
  function render(it) {
    const k = key(it.id);
    if (editing && editing.key === k) return;                 // being written: drawn when done
    const old = els.get(k);
    const d = it.d;
    let el;
    if (it.k === "note" || it.k === "text") {
      const by = people[it.by];
      el = h("div.bb-item.bb-" + it.k, { style: { left: d.x + "px", top: d.y + "px", width: d.w + "px", zIndex: it.z,
        height: it.k === "note" ? d.h + "px" : null, background: it.k === "note" ? BB_NOTE[d.c] : null,
        color: it.k === "text" ? ink(d.c) : null, fontSize: it.k === "text" ? d.s + "px" : null } },
        h("div.bb-txt", d.t || ""),
        it.k === "note" && by ? h("span.bb-by", { style: { "--who": by.color } }, h("i", by.name.slice(0, 1)), by.name) : null,
        h("span.bb-handle", { title: T("Change the size") }));
    } else {
      const svg = svgEl("svg", { class: "bb-item bb-svg", width: 1, height: 1 });
      svg.style.left = d.x + "px"; svg.style.top = d.y + "px"; svg.style.zIndex = it.z;
      if (it.k === "stroke") svg.append(svgEl("path", { d: pathOf(d.p), fill: "none", stroke: ink(d.c), "stroke-width": d.w, "stroke-linecap": "round", "stroke-linejoin": "round" }));
      else svg.append(...shapeParts(d));
      svg.append(svgEl("path", { class: "bb-hit", d: hitPath(it), fill: "none" }));
      el = svg;
    }
    el.dataset.id = k; el.dataset.k = it.k;
    if (old) old.replaceWith(el); else world.append(el);
    els.set(k, el);
    markBusy();
    if (sel === k) el.classList.add("bb-sel");
  }
  function unrender(k) { const el = els.get(k); if (el) el.remove(); els.delete(k); if (sel === k) select(null); }

  // ---------- changes: drawn here at once, sent with the next sync, undone with ↶
  function fixOp(op) { const o = { ...op }; if (o.id != null) o.id = real(o.id); return o; }
  function send(op) {
    queue.push(op);
    if (op.id != null) { const k = key(op.id); pend.set(k, (pend.get(k) || 0) + 1); }
    soon();
  }
  function remember(entry) { undo.push(entry); if (undo.length > BB_UNDO) undo.shift(); drawTools(); }
  function addItem(k, d) {
    const id = "t" + (++tmpN);
    const it = { id, k, d, z: Math.max(0, ...[...items.values()].map(x => x.z)) + 1, by: me.id, ub: me.id };
    items.set(id, it); render(it);
    send({ op: "add", tmp: id, kind: k, data: d });
    remember({ tmp: id, undo: () => removeItem(id, false) });
    return id;
  }
  function setItem(k, patch, rememberIt = true) {
    const it = items.get(k); if (!it) return;
    const prev = {}; for (const f of Object.keys(patch)) prev[f] = it.d[f];
    it.d = { ...it.d, ...patch }; it.ub = me.id; render(it);
    if (sel === k) drawOpts();
    send({ op: "set", id: it.id, data: patch });
    if (rememberIt) remember({ undo: () => setItem(key(it.id), prev, false) });
  }
  function removeItem(k, rememberIt = true) {
    const it = items.get(key(k)); if (!it) return;
    items.delete(key(k)); unrender(key(k));
    send({ op: "del", id: it.id });
    if (rememberIt) remember({ undo: () => { items.set(key(it.id), it); render(it); send({ op: "restore", id: it.id }); } });
  }
  function front(k) {
    const it = items.get(k); if (!it) return;
    it.z = Math.max(0, ...[...items.values()].map(x => x.z)) + 1; render(it);
    send({ op: "front", id: it.id });
  }
  function doUndo() { commitEdit(); const e = undo.pop(); if (e) e.undo(); drawTools(); }

  // ---------- sync: own changes and pointer out, everything new in
  function soon() { if (!alive || inflight) return; clearTimeout(timer); timer = setTimeout(sync, Math.max(0, BB_PTR_MS - (Date.now() - lastSend))); }
  function later() {
    if (!alive) return;
    clearTimeout(timer);
    const wait = queue.length || ptrDirty ? Math.max(BB_PTR_MS - (Date.now() - lastSend), 0) : document.hidden ? 5000 : BB_SYNC_MS;
    timer = setTimeout(sync, queue.length || ptrDirty ? Math.max(wait, 60) : wait);
  }
  function presence() {
    const r = rect();
    return { x: ptr ? Math.round(ptr.x) : null, y: ptr ? Math.round(ptr.y) : null,
      view: [-view.x / view.s, -view.y / view.s, r.width / view.s, r.height / view.s],
      edit: editing ? (typeof real(editing.id) === "number" ? real(editing.id) : null) : drag && drag.moved && typeof real(drag.id) === "number" ? real(drag.id) : null };
  }
  async function sync() {
    if (!alive || inflight) return;
    if (!box.isConnected) return stop();
    inflight = true; lastSend = Date.now(); ptrDirty = false;
    const ops = queue.splice(0, 200);
    const sent = ops.map(fixOp);
    try {
      const r = await api(`community/boards/${boardId}/sync`, { method: "POST", body: { since, ops: sent, presence: presence() } });
      for (const op of ops) if (op.id != null) { const k = key(op.id); const n = (pend.get(k) || 1) - 1; n ? pend.set(k, n) : pend.delete(k); }
      if (alive) receive(r);
    } catch (e) {
      if (e.status === 400 || e.status === 401 || e.status === 403 || e.status === 423) { toast(e.message, "bad"); inflight = false; return close(); }
      queue = ops.concat(queue);                        // offline a moment: try again
    }
    inflight = false;
    later();
  }
  function receive(r) {
    for (const p of r.people || []) people[p.id] = p;
    for (const [t, id] of Object.entries(r.ids || {})) {
      if (id == null) { items.delete(t); unrender(t); continue; }
      tmp[t] = id;
      const it = items.get(t);
      if (it) { items.delete(t); it.id = id; items.set(String(id), it); }
      const el = els.get(t);
      if (el) { els.delete(t); el.dataset.id = String(id); els.set(String(id), el); }
      if (sel === t) sel = String(id);
      if (editing && editing.key === t) editing.key = String(id);
      if (pend.has(t)) { pend.set(String(id), pend.get(t)); pend.delete(t); }
    }
    for (const e of r.errors || []) { toast(e, "bad"); break; }
    const busy = k => pend.has(k) || (editing && editing.key === k) || (drag && drag.moved && key(drag.id) === k);
    if (r.full) {
      const seen = new Set(r.items.map(x => String(x.id)));
      for (const k of [...items.keys()]) if (!seen.has(k) && !k.startsWith("t") && !busy(k)) { items.delete(k); unrender(k); }
    }
    for (const x of r.items) {
      const k = String(x.id);
      if (busy(k)) continue;
      if (x.del) { items.delete(k); unrender(k); continue; }
      const it = { id: x.id, k: x.k, d: x.d, z: x.z, by: x.by, ub: x.ub };
      items.set(k, it); render(it);
    }
    since = r.version;
    board = r.board;
    if (board) {
      titleEl.replaceChildren(h("span.bb-emoji", board.emoji), C(board.title, "strong"), board.archived ? h("span.chip.closed", T("archived")) : "");
      if (readOnly !== board.archived) { readOnly = board.archived; if (readOnly) { tool = "select"; select(null); } drawTools(); }
    }
    others = r.presence || [];
    drawPeople(); drawCursors(); markBusy();
  }

  // ---------- the others: avatars, pointers, what they edit
  function drawPeople() {
    const list = [{ id: me.id }, ...others];
    bar.replaceChildren(...list.slice(0, 6).map(o => {
      const p = people[o.id] || { name: "?", color: "#888" };
      return h("button.bb-av" + (o.id === me.id ? ".me" : ""), { title: p.name, style: { "--who": p.color },
        onclick: () => { if (o.view) showRect({ x: o.view[0], y: o.view[1], w: o.view[2], h: o.view[3] }, BB_MAX); } }, avatarSvg(p.avatar, 30));
    }), list.length > 6 ? h("span.small.bb-more-n", "+" + (list.length - 6)) : "");
  }
  function drawCursors() {
    const r = { w: vp.clientWidth, h: vp.clientHeight };
    cursors.replaceChildren(...others.filter(o => o.x != null).map(o => {
      const p = people[o.id] || { name: "?", color: "#888" };
      const sx = o.x * view.s + view.x, sy = o.y * view.s + view.y;
      if (sx < -20 || sy < -20 || sx > r.w + 20 || sy > r.h + 20) return null;
      return h("div.bb-cursor", { style: { transform: `translate(${sx}px, ${sy}px)`, "--who": p.color } },
        h("i.bb-arrow"), h("span", p.name));
    }).filter(Boolean));
  }
  function markBusy() {
    for (const el of world.querySelectorAll(".bb-busy")) { el.classList.remove("bb-busy"); el.removeAttribute("data-who"); }
    for (const o of others) {
      if (o.edit == null) continue;
      const el = els.get(String(o.edit)), p = people[o.id];
      if (el && p) { el.classList.add("bb-busy"); el.style.setProperty("--who", p.color); el.setAttribute("data-who", p.name); }
    }
  }

  // ---------- selection and writing
  function select(k) {
    if (sel && els.get(sel)) els.get(sel).classList.remove("bb-sel");
    sel = k && items.has(k) ? k : null;
    if (sel && els.get(sel)) els.get(sel).classList.add("bb-sel");
    drawOpts();
  }
  function edit(k) {
    const it = items.get(k), el = els.get(k);
    if (!it || !el || readOnly || (it.k !== "note" && it.k !== "text")) return;
    commitEdit();
    if (view.s < 0.6 || view.s > 2.5) { const b = bbox(it); const r = rect(); showRect({ x: b.x, y: b.y, w: b.w, h: Math.max(b.h, 1) }, Math.min(1.2, (r.width - 80) / Math.max(1, b.w))); }
    const ta = h("textarea.bb-edit", { maxlength: it.k === "note" ? 1000 : 2000, value: it.d.t || "" });
    const grow = () => { if (it.k === "text") { ta.style.height = "auto"; ta.style.height = ta.scrollHeight + "px"; } };
    ta.addEventListener("input", grow);
    ta.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); commitEdit(); } e.stopPropagation(); });
    ta.addEventListener("blur", () => setTimeout(() => { if (editing && editing.ta === ta) commitEdit(); }, 0));
    el.querySelector(".bb-txt").replaceWith(ta);
    editing = { key: k, id: it.id, ta };
    ptrDirty = true; soon();
    ta.focus(); grow();
  }
  function commitEdit() {
    if (!editing) return;
    const { key: k, ta } = editing;
    editing = null;
    const it = items.get(k);
    if (!it) return;
    const t = ta.value;
    if (it.k === "text" && !t.trim()) {                       // an empty text is no text
      items.delete(k); unrender(k); send({ op: "del", id: it.id });
      undo = undo.filter(e => e.tmp == null || key(e.tmp) !== k); drawTools();
      return;
    }
    if (t !== (it.d.t || "")) setItem(k, { t }); else render(it);
  }

  // ---------- tools
  const TOOLS = [["select", "👆", T("Move and choose")], ["note", "🗒️", T("Sticky note")], ["text", "🔤", T("Text")],
    ["pen", "✏️", T("Pen")], ["eraser", "🧽", T("Eraser")], ["shape", "🔷", T("Shapes")]];
  function drawTools() {
    tools.replaceChildren(...(readOnly ? TOOLS.slice(0, 1) : TOOLS).map(([k, ic, n]) =>
      h("button.bb-tool" + (tool === k ? ".on" : ""), { title: n, "aria-label": n, onclick: () => { commitEdit(); tool = k; select(null); drawTools(); } },
        k === "note" ? h("span.bb-swatch", { style: { background: BB_NOTE[noteC] } }, ic) : ic)),
      readOnly ? null : h("button.bb-tool", { title: T("Undo"), "aria-label": T("Undo"), disabled: !undo.length, onclick: doUndo }, "↶"));
    vp.dataset.tool = tool;
    drawOpts();
  }
  function swatches(list, cur, set, note) {
    return list.map((c, i) => h("button.bb-col" + (i === cur ? ".on" : ""), { style: { "--c": note ? c : (i === 0 ? "var(--fg)" : c) }, "aria-label": T("Colour"), onclick: () => set(i) }));
  }
  function drawOpts() {
    let row = [];
    if (sel && items.has(sel) && !readOnly) {
      const it = items.get(sel), by = people[it.by];
      row = [by ? h("span.bb-who.small", { style: { "--who": by.color } }, C(by.name)) : null,
        it.k === "note" || it.k === "text" ? h("button.bb-opt", { title: T("Write"), onclick: () => edit(sel) }, "✏️") : null,
        h("button.bb-opt", { title: T("Remove"), onclick: () => removeItem(sel) }, "🗑️"),
        h("button.bb-opt", { title: T("Bring to front"), onclick: () => front(sel) }, "⬆️"),
        it.k === "text" ? [h("button.bb-opt", { title: T("Smaller"), onclick: () => setItem(sel, { s: Math.max(10, Math.round(it.d.s / 1.25)) }) }, "A−"),
          h("button.bb-opt", { title: T("Bigger"), onclick: () => setItem(sel, { s: Math.min(400, Math.round(it.d.s * 1.25)) }) }, "A+")] : null,
        ...swatches(it.k === "note" ? BB_NOTE : BB_INK, it.d.c, i => setItem(sel, { c: i }), it.k === "note")];
    } else if (tool === "note") row = swatches(BB_NOTE, noteC, i => { noteC = i; drawTools(); }, true);
    else if (tool === "pen" || tool === "text" || tool === "shape") {
      row = [...(tool === "shape" ? [["rect", "⬜"], ["ellipse", "⚪"], ["arrow", "↗"], ["line", "╱"]].map(([f, ic]) =>
        h("button.bb-opt" + (shapeF === f ? ".on" : ""), { onclick: () => { shapeF = f; drawOpts(); } }, ic)) : []),
        ...swatches(BB_INK, inkC, i => { inkC = i; drawOpts(); }),
        ...(tool === "pen" ? [2, 4, 10].map(w => h("button.bb-opt.bb-w" + (penW === w ? ".on" : ""), { title: T("Line width"), onclick: () => { penW = w; drawOpts(); } },
          h("i", { style: { height: w + "px", width: w + "px" } }))) : [])];
    } else if (tool === "eraser") row = [h("span.small.muted.bb-hint", T("Wipe over lines and shapes to remove them"))];
    else if (readOnly) row = [h("span.small.muted.bb-hint", T("This board is archived – it can only be looked at"))];
    else row = [h("span.small.muted.bb-hint", T("Drag to move · two fingers to zoom · double tap to write"))];
    opts.replaceChildren(...row.flat().filter(Boolean));
  }

  // ---------- pointer: pan, pinch, move, draw, erase, place
  const pts = new Map();               // pointerId → {x, y} (screen, relative to the view)
  let drag = null, pinch = null, line = null, shape = null, lastTap = { k: null, t: 0 };
  const local = e => { const r = rect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  function startPinch() {
    const [a, b] = [...pts.values()];
    pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, s: view.s, cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2, vx: view.x, vy: view.y };
    cancelGesture();
  }
  function cancelGesture() {
    if (line) { line.el.remove(); line = null; }
    if (shape) { shape.el.remove(); shape = null; }
    if (drag && drag.moved) { const it = items.get(key(drag.id)); if (it) render(it); }
    drag = null;
  }
  vp.addEventListener("pointerdown", e => {
    if (e.target.closest(".bb-edit")) return;
    e.preventDefault();                                   // no mouse events after a touch: they would take the focus off a new note
    const p = local(e);
    if (e.isPrimary) { pts.clear(); pinch = null; }      // a new gesture: forget fingers whose «up» never came
    pts.set(e.pointerId, p);
    try { vp.setPointerCapture(e.pointerId); } catch {}
    if (pts.size === 2) return startPinch();
    if (pts.size > 2) return;
    if (editing && !e.target.closest(".bb-edit")) commitEdit();
    const w = toWorld(e.clientX, e.clientY);
    const hit = e.target.closest("[data-id]");
    const k = hit && hit.dataset.id;
    const panning = e.button === 1 || e.button === 2;
    if (!panning && !readOnly && tool === "pen") {
      line = { pts: [w.x, w.y], el: svgEl("svg", { class: "bb-item bb-svg", width: 1, height: 1 }) };
      line.path = svgEl("path", { fill: "none", stroke: ink(inkC), "stroke-width": penW / view.s, "stroke-linecap": "round", "stroke-linejoin": "round" });
      line.el.style.zIndex = 2 ** 30; line.el.append(line.path); world.append(line.el);
      line.path.setAttribute("d", pathOf(line.pts));
      return;
    }
    if (!panning && !readOnly && tool === "shape") {
      shape = { x: w.x, y: w.y, el: svgEl("svg", { class: "bb-item bb-svg", width: 1, height: 1 }) };
      shape.el.style.zIndex = 2 ** 30; world.append(shape.el);
      return;
    }
    if (!panning && !readOnly && tool === "eraser") { erase(e); drag = { erase: true }; return; }
    if (!panning && tool === "select" && k && items.has(k) && !readOnly) {
      const it = items.get(k);
      drag = { id: it.id, sx: p.x, sy: p.y, ox: it.d.x, oy: it.d.y, moved: false, el: els.get(k), resize: !!e.target.closest(".bb-handle") };
      return;
    }
    drag = { pan: true, sx: p.x, sy: p.y, vx: view.x, vy: view.y, moved: false, k, w };
  });
  vp.addEventListener("pointermove", e => {
    const p = local(e);
    if (e.pointerType === "mouse" || pts.has(e.pointerId)) { ptr = toWorld(e.clientX, e.clientY); ptrDirty = true; if (!inflight && Date.now() - lastSend > BB_PTR_MS) soon(); }
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, p);
    if (pinch && pts.size >= 2) {
      const [a, b] = [...pts.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y) || 1, cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const s = Math.min(BB_MAX, Math.max(BB_MIN, pinch.s * d / pinch.d));
      view.x = cx - (pinch.cx - pinch.vx) * s / pinch.s; view.y = cy - (pinch.cy - pinch.vy) * s / pinch.s; view.s = s;
      return applyView();
    }
    const w = toWorld(e.clientX, e.clientY);
    if (line) {
      const lx = line.pts[line.pts.length - 2], ly = line.pts[line.pts.length - 1];
      if (Math.hypot(w.x - lx, w.y - ly) * view.s >= 2) { line.pts.push(w.x, w.y); line.path.setAttribute("d", pathOf(line.pts)); }
      return;
    }
    if (shape) {
      const d = shapeData(shape.x, shape.y, w.x, w.y);
      shape.el.replaceChildren(...shapeParts(d));
      shape.el.style.left = d.x + "px"; shape.el.style.top = d.y + "px";
      return;
    }
    if (!drag) return;
    if (drag.erase) return erase(e);
    const dx = p.x - drag.sx, dy = p.y - drag.sy;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    drag.moved = true;
    if (drag.pan) { view.x = drag.vx + dx; view.y = drag.vy + dy; return applyView(); }
    const it = items.get(key(drag.id));
    if (!it) { drag = null; return; }
    if (drag.resize) {
      if (!drag.ow) { drag.ow = it.d.w; drag.oh = it.d.h; }
      const nw = Math.max(40, drag.ow + dx / view.s), nh = Math.max(40, (drag.oh || 0) + dy / view.s);
      drag.el.style.width = nw + "px";
      if (it.k === "note") drag.el.style.height = nh + "px";
      drag.size = it.k === "note" ? { w: Math.round(nw), h: Math.round(nh) } : { w: Math.round(nw) };
      return;
    }
    drag.el.style.left = (drag.ox + dx / view.s) + "px"; drag.el.style.top = (drag.oy + dy / view.s) + "px";
    drag.nx = Math.round(drag.ox + dx / view.s); drag.ny = Math.round(drag.oy + dy / view.s);
    drag.el.classList.add("bb-moving");
  });
  const up = e => {
    if (!pts.has(e.pointerId)) return;
    pts.delete(e.pointerId);
    if (pinch) { if (pts.size < 2) pinch = null; if (pts.size === 1) { const [q] = [...pts.values()]; drag = { pan: true, sx: q.x, sy: q.y, vx: view.x, vy: view.y, moved: true }; } return; }
    if (e.type === "pointercancel") return cancelGesture();
    const w = toWorld(e.clientX, e.clientY);
    if (line) {
      const l = line; line = null; l.el.remove();
      const pts2 = simplify(l.pts, 0.8 / view.s);
      const x0 = Math.round(pts2[0]), y0 = Math.round(pts2[1]);
      addItem("stroke", { x: x0, y: y0, c: inkC, w: Math.max(1, Math.min(80, Math.round(penW / view.s))), p: pts2.map((v, i) => Math.round(v - (i % 2 ? y0 : x0))) });
      return;
    }
    if (shape) {
      const s = shape; shape = null; s.el.remove();
      const d = shapeData(s.x, s.y, w.x, w.y);
      if (Math.hypot(d.w, d.h) * view.s < 8) { d.w = Math.round(160 / view.s); d.h = Math.round((d.f === "rect" || d.f === "ellipse" ? 100 : 0) / view.s); if (d.f === "arrow" || d.f === "line") d.h = 0; }
      addItem("shape", d);
      tool = "select"; drawTools();
      return;
    }
    const g = drag; drag = null;
    if (!g || g.erase) return;
    if (g.pan) {
      if (g.moved) return;
      if (!readOnly && (tool === "note" || tool === "text")) {               // place a note / a text where tapped
        const s = Math.max(0.25, view.s);
        const d = tool === "note" ? { x: Math.round(g.w.x - 100), y: Math.round(g.w.y - 100), w: 200, h: 200, c: noteC, t: "" }
          : { x: Math.round(g.w.x), y: Math.round(g.w.y - 20 / s), w: Math.round(320 / s), s: Math.round(Math.min(400, Math.max(10, 28 / s))), c: inkC, t: "" };
        const id = addItem(tool, d);
        tool = "select"; drawTools();
        select(key(id)); edit(key(id));
        return;
      }
      if (g.k && items.has(g.k)) return tapItem(g.k);                         // archived board: just look
      select(null);
      return;
    }
    const k = key(g.id);
    if (g.moved) {
      g.el && g.el.classList.remove("bb-moving");
      if (g.resize && g.size) setItem(k, g.size);
      else if (g.nx != null) setItem(k, { x: g.nx, y: g.ny });
      return;
    }
    tapItem(k);
  };
  function tapItem(k) {
    const now = Date.now();
    if (lastTap.k === k && now - lastTap.t < 400) { lastTap = { k: null, t: 0 }; return edit(k); }
    lastTap = { k, t: now };
    select(k);
  }
  vp.addEventListener("pointerup", up);
  vp.addEventListener("pointercancel", up);
  vp.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") { ptr = null; ptrDirty = true; } });
  vp.addEventListener("contextmenu", e => e.preventDefault());
  vp.addEventListener("dblclick", e => { const t = e.target.closest("[data-id]"); if (t && tool === "select") edit(t.dataset.id); });
  vp.addEventListener("wheel", e => {
    e.preventDefault();
    const p = local(e);
    if (e.ctrlKey || (Math.abs(e.deltaY) >= 40 && !e.deltaX)) zoomAt(view.s * Math.exp(-Math.max(-300, Math.min(300, e.deltaY)) * (e.ctrlKey ? 0.01 : 0.0015)), p.x, p.y);
    else { view.x -= e.deltaX; view.y -= e.deltaY; applyView(); }
  }, { passive: false });
  function erase(e) {
    for (const el of document.elementsFromPoint(e.clientX, e.clientY)) {
      const t = el.closest && el.closest("[data-id]");
      if (t && (t.dataset.k === "stroke" || t.dataset.k === "shape") && items.has(t.dataset.id)) { removeItem(t.dataset.id); break; }
    }
  }
  function shapeData(x0, y0, x1, y1) {
    const base = { c: inkC, sw: Math.max(1, Math.min(60, Math.round(4 / view.s))), f: shapeF };
    if (shapeF === "arrow" || shapeF === "line") return { ...base, x: Math.round(x0), y: Math.round(y0), w: Math.round(x1 - x0), h: Math.round(y1 - y0) };
    return { ...base, x: Math.round(Math.min(x0, x1)), y: Math.round(Math.min(y0, y1)), w: Math.max(4, Math.round(Math.abs(x1 - x0))), h: Math.max(4, Math.round(Math.abs(y1 - y0))) };
  }
  // fewer points, same line (Ramer–Douglas–Peucker)
  function simplify(p, eps) {
    const n = p.length / 2;
    if (n < 3) return p.slice();
    const keep = new Uint8Array(n); keep[0] = keep[n - 1] = 1;
    const stack = [[0, n - 1]];
    while (stack.length) {
      const [a, b] = stack.pop();
      const ax = p[2 * a], ay = p[2 * a + 1], bx = p[2 * b], by = p[2 * b + 1];
      const L = Math.hypot(bx - ax, by - ay) || 1;
      let md = 0, mi = -1;
      for (let i = a + 1; i < b; i++) {
        const d = Math.abs((bx - ax) * (ay - p[2 * i + 1]) - (ax - p[2 * i]) * (by - ay)) / L;
        if (d > md) { md = d; mi = i; }
      }
      if (md > eps && mi > 0) { keep[mi] = 1; stack.push([a, mi], [mi, b]); }
    }
    const out = [];
    for (let i = 0; i < n; i++) if (keep[i]) out.push(p[2 * i], p[2 * i + 1]);
    return out.slice(0, 1200);
  }
  function onKey(e) {
    if (!alive || editing || ["INPUT", "TEXTAREA"].includes((document.activeElement || {}).tagName)) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); doUndo(); }
    else if ((e.key === "Delete" || e.key === "Backspace") && sel && !readOnly) { e.preventDefault(); removeItem(sel); }
    else if (e.key === "Escape") { if (sel) select(null); else close(); }
  }
  const onResize = () => applyView();
  window.addEventListener("keydown", onKey);
  window.addEventListener("resize", onResize);

  // ---------- start: the last view of this board on this device, else everything
  drawTools();
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("fq.board." + boardId) || "null"); } catch {}
  (async () => {
    await sync();
    if (!alive) return;
    if (saved && saved.s) { Object.assign(view, saved); applyView(); } else fitAll();
  })();
}
