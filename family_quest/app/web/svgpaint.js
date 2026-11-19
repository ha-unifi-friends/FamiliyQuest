// ---------------------------------------------------------------- the drawing editor (vector pictures as SVG)
// One editor for every book type (stories.js 📖 adventure books, picturebook.js 📕 picture books, adventure.js 🗝️ games):
// pen (smoothed, pen pressure), lines, rectangles, ellipses / circles, triangles, polygons, stamps, a word of text,
// fill bucket, colour palette + own colour, background presets, select / move / scale / stretch / rotate, layers,
// duplicate, undo / redo, two-finger zoom of the picture (never of the page). svgPaint({kind, svg}) resolves with the
// cleaned SVG of the server (stories/svg, svgsafe.py) – or null.
// kind «bg»: a scene that fills a page / a room (viewBox 800×600, max. 60 KB); «art»: a thing or a character
// (200×200, see-through background, max. 20 KB).
// The SVG is its own shape model: the editor writes every shape as one element with transform="translate() rotate()
// scale()" and marks the picture with id="fq-draw", so it can open its own pictures again shape by shape. A picture
// from somewhere else (pasted code, an AI) becomes one locked layer («draw on top»).
"use strict";

const SVP_SPEC = { bg: { w: 800, h: 600, max: 60000, bg: { p: "white" } }, art: { w: 200, h: 200, max: 20000, bg: null } };
const SVP_INK = ["#1f2433", "#ffffff", "#868e96", "#e03131", "#f76707", "#fcc419", "#ffe066", "#2f9e44", "#94d82d", "#0b7285",
  "#74c0fc", "#1c7ed6", "#7048e8", "#f783ac", "#8d5524", "#ffd8a8"];
// background presets: vertical gradients (offset, colour) – «none» is see-through
const SVP_BGS = () => ({
  none: [T("See-through"), null], white: [T("White paper"), [[0, "#ffffff"]]],
  sky: [T("Sky"), [[0, "#4dabf7"], [1, "#e7f5ff"]]], meadow: [T("Meadow"), [[0, "#74c0fc"], [0.6, "#d0ebff"], [0.6, "#69db7c"], [1, "#2b8a3e"]]],
  grass: [T("Grass"), [[0, "#b2f2bb"], [1, "#2f9e44"]]], sea: [T("Sea"), [[0, "#4dabf7"], [1, "#0b3d6e"]]],
  beach: [T("Beach"), [[0, "#74c0fc"], [0.45, "#d0ebff"], [0.45, "#1c7ed6"], [0.62, "#4dabf7"], [0.62, "#ffe8a3"], [1, "#e9b44c"]]],
  night: [T("Night"), [[0, "#0b1340"], [1, "#3b4a9a"]]], sunset: [T("Sunset"), [[0, "#5f3dc4"], [0.5, "#f783ac"], [1, "#ff922b"]]],
  room: [T("Room"), [[0, "#fff4e6"], [0.68, "#ffd8a8"], [0.68, "#a0522d"], [1, "#7c4a1e"]]], cave: [T("Cave"), [[0, "#212529"], [1, "#5c5f66"]]],
  snow: [T("Snow"), [[0, "#a5d8ff"], [0.65, "#e7f5ff"], [0.65, "#ffffff"], [1, "#e9ecef"]]],
  space: [T("Space"), [[0, "#000814"], [1, "#2b2d6e"]]],
});
// stamps, drawn in a box from -50 to 50: parts [d, own colour or null = the chosen colour]
const SVP_STAMPS = (() => {
  const star = [];
  for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 21 : 50; star.push((i ? "L" : "M") + Math.round(Math.cos(a) * r) + " " + Math.round(Math.sin(a) * r)); }
  let rays = "";
  for (let i = 0; i < 8; i++) {
    const a = i * Math.PI / 4, p = (r, d) => Math.round(Math.cos(a + d) * r) + " " + Math.round(Math.sin(a + d) * r);
    rays += "M" + p(31, -0.2) + "L" + p(50, 0) + "L" + p(31, 0.2) + "Z";
  }
  return {
    star: ["⭐", [[star.join("") + "Z", null]], "#fcc419"],
    heart: ["❤️", [["M0 45C-25 25-50 5-50-15C-50-35-30-48-14-42C-6-39-2-33 0-28C2-33 6-39 14-42C30-48 50-35 50-15C50 5 25 25 0 45Z", null]], "#e03131"],
    tree: ["🌳", [["M-8 50V8H8V50Z", "#8d5524"], ["M0-50C25-50 40-30 37-10C46 6 30 22 10 18H-10C-30 22-46 6-37-10C-40-30-25-50 0-50Z", null]], "#2f9e44"],
    cloud: ["☁️", [["M-30 25C-50 25-55 0-38-6C-40-28-12-36-2-20C6-38 36-34 34-10C52-10 54 25 32 25Z", null]], "#ffffff"],
    sun: ["☀️", [["M-27 0A27 27 0 1 0 27 0A27 27 0 1 0-27 0Z" + rays, null]], "#ffd43b"],
    house: ["🏠", [["M-38-5H38V50H-38Z", null], ["M-48-2L0-46L48-2Z", "#e03131"], ["M-10 50V20H10V50Z", "#8d5524"], ["M16 6H32V22H16Z", "#d0ebff"]], "#ffe8cc"],
    door: ["🚪", [["M-30 50V-20A30 30 0 0 1 30-20V50Z", null], ["M8 12A6 6 0 1 0 20 12A6 6 0 1 0 8 12Z", "#fcc419"]], "#a0522d"],
    window: ["🪟", [["M-40-40H40V40H-40Z", null], ["M-32-32H-4V-4H-32ZM4-32H32V-4H4ZM-32 4H-4V32H-32ZM4 4H32V32H4Z", "#a5d8ff"]], "#ffffff"],
  };
})();
const SVP_SHAPES = () => ({ rect: ["▭", T("Rectangle")], ellipse: ["⬭", T("Ellipse")], circle: ["◯", T("Circle")], tri: ["△", T("Triangle")],
  poly: ["⬠", T("Polygon")] });
const SVP_STAMP_NAMES = () => ({ star: T("Star"), heart: T("Heart"), tree: T("Tree"), cloud: T("Cloud"), sun: T("Sunshine"), house: T("House"),
  door: T("Door"), window: T("Window") });
const SVP_NS = "http://www.w3.org/2000/svg";

const svgDataUrl = svg => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
// is this an own drawing of the editor (it opens shape by shape) – or a picture from somewhere else (one locked layer)?
const svgIsOwn = svg => /^<svg\b[^>]*\bid="fq-draw"/.test(String(svg || ""));

// ---------------------------------------------------------------- model ⇄ SVG text
function svpRound(v, dec) { const k = dec ? 10 : 1; const r = Math.round(v * k) / k; return Object.is(r, -0) ? "0" : String(r); }
function svpEsc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function svpTransform(s) {
  const n = v => svpRound(v, 1), sx = s.sx ?? 1, sy = s.sy ?? 1;
  let t = `translate(${n(s.tx || 0)} ${n(s.ty || 0)})`;
  if (s.r) t += ` rotate(${n(s.r)})`;
  if (Math.abs(sx - 1) > 0.001 || Math.abs(sy - 1) > 0.001) t += Math.abs(sx - sy) < 0.001 ? ` scale(${svpRound(sx * 1000, 0) / 1000})` : ` scale(${svpRound(sx * 1000, 0) / 1000} ${svpRound(sy * 1000, 0) / 1000})`;
  return t;
}
// one shape as [tag, attributes, children (parts of a stamp) or text]
function svpSpec(s) {
  const n = v => svpRound(v, 1);
  const a = {};
  const open = s.t === "line" || (s.t === "path" && (!s.fill || s.fill === "none"));
  if (s.t !== "line") a.fill = s.fill || "none";
  if (s.stroke && s.stroke !== "none") {
    a.stroke = s.stroke; a["stroke-width"] = n(s.sw || 1);
    if (open || s.t === "path") a["stroke-linecap"] = "round";
    a["stroke-linejoin"] = "round";
  }
  if (s.op != null && s.op < 1) a.opacity = n(s.op);
  a.transform = svpTransform(s);
  if (s.t === "path") return ["path", { d: s.d, ...a }];
  if (s.t === "line") return ["line", { x1: n(s.x1), y1: n(s.y1), x2: n(s.x2), y2: n(s.y2), ...a }];
  if (s.t === "rect") return ["rect", { x: n(s.x), y: n(s.y), width: n(s.w), height: n(s.h), ...(s.rx ? { rx: n(s.rx) } : {}), ...a }];
  if (s.t === "ellipse") return ["ellipse", { ...(s.cx ? { cx: n(s.cx) } : {}), ...(s.cy ? { cy: n(s.cy) } : {}), rx: n(s.rx), ry: n(s.ry), ...a }];
  if (s.t === "poly") return ["polygon", { points: s.points, ...a }];
  if (s.t === "text") return ["text", { x: 0, y: 0, "font-size": n(s.fs), "font-family": "sans-serif", "font-weight": "bold", "text-anchor": "middle",
    "dominant-baseline": "central", ...a }, s.text];
  if (s.t === "g") return ["g", a, s.kids.map(k => ["path", k.fill ? { d: k.d, fill: k.fill } : { d: k.d }])];
  return null;
}
function svpStr(spec) {
  const [tag, attrs, kids] = spec;
  const head = "<" + tag + Object.entries(attrs).map(([k, v]) => ` ${k}="${svpEsc(v)}"`).join("");
  if (typeof kids === "string") return head + ">" + svpEsc(kids) + `</${tag}>`;
  if (Array.isArray(kids) && kids.length) return head + ">" + kids.map(svpStr).join("") + `</${tag}>`;
  return head + "/>";
}
function svpBgStr(bg, W, H) {
  if (!bg) return "";
  if (bg.c) return `<rect id="fq-bg" width="${W}" height="${H}" fill="${svpEsc(bg.c)}"/>`;
  const stops = (SVP_BGS()[bg.p] || [])[1];
  if (!stops) return "";
  if (stops.length === 1) return `<rect id="fq-bg-${bg.p}" width="${W}" height="${H}" fill="${stops[0][1]}"/>`;
  return `<defs><linearGradient id="fq-g" x1="0" y1="0" x2="0" y2="1">` + stops.map(([o, c]) => `<stop offset="${o}" stop-color="${c}"/>`).join("") +
    `</linearGradient></defs><rect id="fq-bg-${bg.p}" width="${W}" height="${H}" fill="url(#fq-g)"/>`;
}
function svpToSvg(st, W, H) {
  return `<svg xmlns="${SVP_NS}" viewBox="0 0 ${W} ${H}" id="fq-draw">` + svpBgStr(st.bg, W, H) + (st.locked || "") +
    st.shapes.map(s => svpStr(svpSpec(s))).join("") + "</svg>";
}
function svpParseTransform(t, s) {
  t = t || "";
  const num = "(-?[\\d.]+(?:e-?\\d+)?)";
  const tr = t.match(new RegExp("translate\\(\\s*" + num + "(?:[\\s,]+" + num + ")?\\s*\\)")), ro = t.match(new RegExp("rotate\\(\\s*" + num + "\\s*\\)")),
    sc = t.match(new RegExp("scale\\(\\s*" + num + "(?:[\\s,]+" + num + ")?\\s*\\)"));
  const rest = t.replace(/translate\([^)]*\)|rotate\([^)]*\)|scale\([^)]*\)/g, "").trim();
  if (rest) return false;                                   // matrix(), skew …: not a shape of the editor
  s.tx = tr ? +tr[1] : 0; s.ty = tr && tr[2] != null ? +tr[2] : 0; s.r = ro ? +ro[1] : 0;
  s.sx = sc ? +sc[1] : 1; s.sy = sc ? (sc[2] != null ? +sc[2] : +sc[1]) : 1;
  return true;
}
function svpParseShape(el) {
  const g = k => el.getAttribute(k), f = k => parseFloat(g(k)) || 0;
  const s = { fill: g("fill") || (el.localName === "line" ? null : "#000000"), stroke: g("stroke") || null, sw: f("stroke-width") || 1,
    op: g("opacity") != null ? parseFloat(g("opacity")) : null };
  if (!svpParseTransform(g("transform"), s)) return null;
  switch (el.localName) {
    case "path": return g("d") ? { t: "path", d: g("d"), ...s } : null;
    case "line": return { t: "line", x1: f("x1"), y1: f("y1"), x2: f("x2"), y2: f("y2"), ...s };
    case "rect": return { t: "rect", x: f("x"), y: f("y"), w: f("width"), h: f("height"), rx: f("rx"), ...s };
    case "ellipse": return { t: "ellipse", cx: f("cx"), cy: f("cy"), rx: f("rx"), ry: f("ry"), ...s };
    case "circle": return { t: "ellipse", cx: f("cx"), cy: f("cy"), rx: f("r"), ry: f("r"), ...s };
    case "polygon": return g("points") ? { t: "poly", points: g("points"), ...s } : null;
    case "text": return { t: "text", text: el.textContent.trim().slice(0, 60), fs: f("font-size") || 16, ...s };
    case "g": {
      const kids = [...el.children];
      if (!kids.length || kids.some(k => k.localName !== "path" || !k.getAttribute("d"))) return null;
      return { t: "g", kids: kids.map(k => ({ d: k.getAttribute("d"), fill: k.getAttribute("fill") || null })), ...s };
    }
  }
  return null;
}
// SVG text → {bg, locked, shapes} in the size of this kind; a foreign picture becomes one locked layer, scaled to fit
function svpFromSvg(svg, W, H) {
  const st = { bg: null, locked: "", shapes: [] };
  if (!svg) return st;
  let root;
  try {
    const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
    root = doc.documentElement;
    if (!root || root.localName !== "svg" || doc.querySelector("parsererror")) return st;
  } catch { return st; }
  const ser = new XMLSerializer();
  const vb = (root.getAttribute("viewBox") || `0 0 ${W} ${H}`).trim().split(/[\s,]+/).map(Number);
  const strip = s => s.replace(/ xmlns="http:\/\/www\.w3\.org\/2000\/svg"/g, "");
  if (root.id === "fq-draw" && vb[2] === W && vb[3] === H) {
    for (const el of root.children) {
      if (el.localName === "defs") continue;
      if (el.localName === "rect" && /^fq-bg/.test(el.id)) {
        const p = el.id.slice(6);
        st.bg = p && SVP_BGS()[p] ? { p } : { c: el.getAttribute("fill") || "#ffffff" };
        continue;
      }
      const s = el.id === "fq-locked" ? null : svpParseShape(el);
      if (s) st.shapes.push(s); else st.locked += strip(ser.serializeToString(el));
    }
    return st;
  }
  if (!(vb[2] > 0 && vb[3] > 0)) return st;
  const k = Math.min(W / vb[2], H / vb[3]), ox = (W - vb[2] * k) / 2, oy = (H - vb[3] * k) / 2;
  const inner = [...root.childNodes].map(c => c.nodeType === 1 ? strip(ser.serializeToString(c)) : "").join("");
  if (inner) st.locked = `<g id="fq-locked" transform="translate(${svpRound(ox, 1)} ${svpRound(oy, 1)}) scale(${svpRound(k * 1000, 0) / 1000}) translate(${-vb[0]} ${-vb[1]})">${inner}</g>`;
  return st;
}

// smoothing: drop points that lie on the line (Ramer–Douglas–Peucker), then quadratic curves through the midpoints
function svpSimplify(pts, eps) {
  if (pts.length < 3) return pts;
  const [a, b] = [pts[0], pts[pts.length - 1]];
  let best = -1, at = 0;
  const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
  for (let i = 1; i < pts.length - 1; i++) {
    const d = Math.abs(dy * pts[i][0] - dx * pts[i][1] + b[0] * a[1] - b[1] * a[0]) / len;
    if (d > best) { best = d; at = i; }
  }
  if (best <= eps) return [a, b];
  return [...svpSimplify(pts.slice(0, at + 1), eps).slice(0, -1), ...svpSimplify(pts.slice(at), eps)];
}
function svpSmoothPath(pts, dec) {
  const n = v => svpRound(v, dec), P = p => n(p[0]) + " " + n(p[1]);
  if (pts.length === 1) return "M" + P(pts[0]) + "l0.1 0";
  if (pts.length === 2) return "M" + P(pts[0]) + "L" + P(pts[1]);
  let d = "M" + P(pts[0]);
  for (let i = 1; i < pts.length - 1; i++) d += "Q" + P(pts[i]) + " " + P([(pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2]);
  return d + "L" + P(pts[pts.length - 1]);
}

// ---------------------------------------------------------------- the editor
function svgPaint({ kind = "bg", svg = null, title = null } = {}) {
  return new Promise(resolve => {
    const spec = SVP_SPEC[kind] || SVP_SPEC.bg, W = spec.w, H = spec.h, DEC = W < 400 ? 1 : 0, U = W / 800;
    const SIZES = [4, 10, 20, 40].map(v => Math.max(1.5, v * U * (kind === "art" ? 2 : 1)));
    let st = svpFromSvg(svg, W, H);
    if (!svg) st.bg = spec.bg ? { ...spec.bg } : null;
    const foreign = !!svg && !svgIsOwn(svg) && !!st.locked;
    let tool = "pen", shapeKind = "rect", stampKind = "star", color = kind === "art" ? "#1f2433" : "#1f2433", size = SIZES[1], outline = true;
    let sel = -1, panel = null, done = false, gesture = null, zoom = 1, panX = 0, panY = 0;
    const undo = [], redo = [];
    const snap = () => { undo.push(JSON.stringify(st)); if (undo.length > 60) undo.shift(); redo.length = 0; };
    const svgEl = (tag, attrs = {}) => { const e = document.createElementNS(SVP_NS, tag); for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v); return e; };
    const canvas = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "svp-canvas" + (kind === "art" ? " art" : ""), role: "img", "aria-label": I18N.tr(T("Drawing")) });
    const bgLayer = svgEl("g"), lockLayer = svgEl("g"), shapeLayer = svgEl("g"), tmpLayer = svgEl("g"), overLayer = svgEl("g", { class: "svp-over" });
    canvas.append(bgLayer, lockLayer, shapeLayer, tmpLayer, overLayer);
    const meter = h("span.svp-meter"), bar1 = h("div.svp-tools"), bar2 = h("div.svp-row"), selBar = h("div.svp-row.svp-selbar");
    // the bar of the selected shape floats over the picture, so the picture never jumps
    const zoomBox = h("div.svp-zoom", canvas), stage = h("div.svp-stage", zoomBox, selBar);   // (+ ⤢ the whole picture again, after zooming)
    const useBtn = h("button.btn.small", { onclick: () => finishUse() }, "✓ ", T("Use picture"));
    const undoBtn = h("button.svp-tool", { title: T("Undo"), "aria-label": T("Undo"), onclick: () => history(undo, redo) }, "↶");
    const redoBtn = h("button.svp-tool", { title: T("Redo"), "aria-label": T("Redo"), onclick: () => history(redo, undo) }, "↷");
    const zoomBtn = h("button.svp-tool.svp-unzoom", { title: T("Whole picture"), "aria-label": T("Whole picture"), onclick: () => { zoom = 1; panX = panY = 0; applyZoom(); } }, "⤢");
    const history = (from, to) => { if (!from.length) return; to.push(JSON.stringify(st)); st = JSON.parse(from.pop()); sel = -1; render(); };
    const els = [];

    // ---------- drawing the model
    const renderBg = () => {
      bgLayer.replaceChildren();
      if (st.bg) { const tmp = svgEl("g"); tmp.innerHTML = svpBgStr(st.bg, W, H); bgLayer.append(...tmp.childNodes); }
      lockLayer.replaceChildren();
      if (st.locked) lockLayer.append(svgEl("image", { href: svgDataUrl(`<svg xmlns="${SVP_NS}" viewBox="0 0 ${W} ${H}">${st.locked}</svg>`), x: 0, y: 0, width: W, height: H }));
    };
    const shapeNode = (s, i) => {
      const [tag, attrs, kids] = svpSpec(s);
      const e = svgEl(tag, attrs);
      if (typeof kids === "string") e.textContent = kids;
      else if (kids) for (const [kt, ka] of kids) e.append(svgEl(kt, ka));
      e.dataset.i = i;
      return e;
    };
    const render = () => {
      renderBg();
      shapeLayer.replaceChildren(...st.shapes.map(shapeNode));
      els.length = 0; els.push(...shapeLayer.children);
      if (sel >= st.shapes.length) sel = -1;
      drawOver(); drawBars(); measure();
    };
    const measure = () => {
      const n = svpToSvg(st, W, H).length, over = n > spec.max;
      sbSet(meter, h("span.svp-mbar", h("i", { style: { width: Math.min(100, n / spec.max * 100) + "%" } })), (n / 1000).toFixed(1) + " / " + spec.max / 1000 + " KB");
      meter.classList.toggle("over", over);
      meter.title = over ? I18N.tr(T("The drawing is too large – remove some shapes")) : "";
      useBtn.disabled = over;
      undoBtn.disabled = !undo.length; redoBtn.disabled = !redo.length;
    };
    // the box of a shape in its own coordinates, its corners and handles on the picture
    const upx = () => W / (canvas.getBoundingClientRect().width || W);          // picture units per screen pixel
    const toWorld = (s, x, y) => {
      const a = (s.r || 0) * Math.PI / 180, X = x * (s.sx ?? 1), Y = y * (s.sy ?? 1);
      return [s.tx + X * Math.cos(a) - Y * Math.sin(a), s.ty + X * Math.sin(a) + Y * Math.cos(a)];
    };
    const toLocal = (s, x, y) => {
      const a = -(s.r || 0) * Math.PI / 180, dx = x - s.tx, dy = y - s.ty;
      return [(dx * Math.cos(a) - dy * Math.sin(a)) / (s.sx || 1), (dx * Math.sin(a) + dy * Math.cos(a)) / (s.sy || 1)];
    };
    const box = i => { try { const b = els[i].getBBox(); return { x: b.x, y: b.y, w: b.width, h: b.height }; } catch { return { x: -10, y: -10, w: 20, h: 20 }; } };
    const handles = i => {
      const s = st.shapes[i], b = box(i), pad = 6 * upx() / Math.max(0.05, Math.abs(s.sx ?? 1));
      const x0 = b.x - pad, y0 = b.y - pad, x1 = b.x + b.w + pad, y1 = b.y + b.h + pad;
      const corners = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(([x, y]) => toWorld(s, x, y));
      const top = toWorld(s, (x0 + x1) / 2, y0), a = (s.r || 0) * Math.PI / 180, L = 34 * upx();
      return { corners, scale: corners[2], sx: toWorld(s, x1, (y0 + y1) / 2), sy: toWorld(s, (x0 + x1) / 2, y1),
        rot: [top[0] + Math.sin(a) * L, top[1] - Math.cos(a) * L], top };
    };
    const drawOver = () => {
      overLayer.replaceChildren();
      if (sel < 0 || !els[sel]) return;
      const hd = handles(sel), u = upx(), R = 11 * u;
      overLayer.append(svgEl("polygon", { points: hd.corners.map(p => p.join(",")).join(" "), fill: "none", stroke: "#5b5bd6", "stroke-width": 2 * u, "stroke-dasharray": `${6 * u} ${4 * u}` }),
        svgEl("line", { x1: hd.top[0], y1: hd.top[1], x2: hd.rot[0], y2: hd.rot[1], stroke: "#5b5bd6", "stroke-width": 2 * u }));
      for (const [k, p] of [["rot", hd.rot], ["sx", hd.sx], ["sy", hd.sy], ["scale", hd.scale]])
        overLayer.append(svgEl("circle", { cx: p[0], cy: p[1], r: k === "scale" || k === "rot" ? R : R * 0.75, fill: k === "rot" ? "#fcc419" : "#ffffff", stroke: "#5b5bd6", "stroke-width": 2.5 * u, "data-h": k }));
    };
    const applyZoom = () => {
      zoomBox.style.transform = zoom === 1 && !panX && !panY ? "" : `translate(${panX}px, ${panY}px) scale(${zoom})`;
      zoomBtn.hidden = zoom === 1 && !panX && !panY;
      drawOver();
    };
    const fit = () => {
      const r = stage.getBoundingClientRect(), k = Math.min(r.width / W, (r.height - 4) / H);
      if (k > 0) { canvas.style.width = Math.floor(W * k) + "px"; canvas.style.height = Math.floor(H * k) + "px"; }
      drawOver();
    };

    // ---------- hit tests
    const pt = e => { const r = canvas.getBoundingClientRect(); return [(e.clientX - r.left) * W / r.width, (e.clientY - r.top) * H / r.height]; };
    const hitHandle = (p) => {
      if (sel < 0 || !els[sel]) return null;
      const hd = handles(sel), R = 22 * upx();
      for (const k of ["rot", "scale", "sx", "sy"]) if (Math.hypot(p[0] - hd[k][0], p[1] - hd[k][1]) < R) return k;
      return null;
    };
    const hitShape = (e, p) => {
      for (const el of document.elementsFromPoint(e.clientX, e.clientY)) {
        const g = el.closest && el.closest("[data-i]");
        if (g && shapeLayer.contains(g)) return +g.dataset.i;
      }
      let best = -1, area = Infinity;                       // thin lines: the box of the shape (with a finger's margin)
      for (let i = st.shapes.length - 1; i >= 0; i--) {
        const s = st.shapes[i], b = box(i), [x, y] = toLocal(s, p[0], p[1]);
        const pad = (s.stroke ? (s.sw || 0) / 2 : 0) + 14 * upx() / Math.max(0.05, Math.min(Math.abs(s.sx ?? 1), Math.abs(s.sy ?? 1)));
        if (x >= b.x - pad && x <= b.x + b.w + pad && y >= b.y - pad && y <= b.y + b.h + pad && b.w * b.h < area) { best = i; area = b.w * b.h; }
      }
      return best;
    };

    // ---------- new shapes
    const outlineOf = () => outline ? { stroke: color === "#1f2433" ? "#000000" : "#1f2433", sw: Math.max(1, size / 2) } : { stroke: null, sw: 0 };
    const add = s => { snap(); st.shapes.push(s); sel = st.shapes.length - 1; render(); };
    const boxShape = (a, b) => {
      let x0 = Math.min(a[0], b[0]), y0 = Math.min(a[1], b[1]), w = Math.abs(a[0] - b[0]), hh = Math.abs(a[1] - b[1]);
      const tap = w < 10 * upx() && hh < 10 * upx();
      const D = W * 0.2;
      if (tap) { x0 = a[0] - D / 2; y0 = a[1] - D / 2; w = hh = D; }
      const cx = x0 + w / 2, cy = y0 + hh / 2, base = { tx: cx, ty: cy, r: 0, sx: 1, sy: 1, fill: color, ...outlineOf() };
      if (tool === "line") {
        const e = Math.hypot(b[0] - a[0], b[1] - a[1]) < 10 * upx() ? [a[0] + D, a[1]] : b, mx = (a[0] + e[0]) / 2, my = (a[1] + e[1]) / 2;
        return { t: "line", x1: a[0] - mx, y1: a[1] - my, x2: e[0] - mx, y2: e[1] - my, tx: mx, ty: my, r: 0, sx: 1, sy: 1, fill: null, stroke: color, sw: size };
      }
      if (tool === "stamp") {
        const [, parts] = SVP_STAMPS[stampKind], k = Math.max(w, hh) / 100;
        return { t: "g", kids: parts.map(([d, f]) => ({ d, fill: f })), ...base, sx: k, sy: k, stroke: outline ? "#1f2433" : null, sw: outline ? Math.max(1, size / 2) / k : 0 };
      }
      if (shapeKind === "ellipse") return { t: "ellipse", cx: 0, cy: 0, rx: w / 2, ry: hh / 2, ...base };
      if (shapeKind === "circle") { const r = Math.max(w, hh) / 2; return { t: "ellipse", cx: 0, cy: 0, rx: r, ry: r, ...base }; }
      if (shapeKind === "tri") {
        const n = v => svpRound(v, DEC);
        return { t: "poly", points: `0,${n(-hh / 2)} ${n(w / 2)},${n(hh / 2)} ${n(-w / 2)},${n(hh / 2)}`, ...base };
      }
      return { t: "rect", x: -w / 2, y: -hh / 2, w, h: hh, rx: 0, ...base };
    };
    let poly = null;                                          // the polygon being drawn: its points
    const drawPoly = () => {
      tmpLayer.replaceChildren();
      if (!poly) return;
      const u = upx();
      tmpLayer.append(svgEl("polyline", { points: poly.map(p => p.join(",")).join(" "), fill: "none", stroke: color, "stroke-width": 3 * u, "stroke-dasharray": `${6 * u} ${4 * u}` }),
        ...poly.map((p, i) => svgEl("circle", { cx: p[0], cy: p[1], r: (i ? 6 : 10) * u, fill: i ? color : "#ffffff", stroke: "#5b5bd6", "stroke-width": 2 * u })));
      drawBars();
    };
    const closePoly = () => {
      if (poly && poly.length >= 3) {
        const xs = poly.map(p => p[0]), ys = poly.map(p => p[1]), cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const n = v => svpRound(v, DEC);
        poly = poly.map(p => n(p[0] - cx) + "," + n(p[1] - cy)).join(" ");
        const s = { t: "poly", points: poly, tx: cx, ty: cy, r: 0, sx: 1, sy: 1, fill: color, ...outlineOf() };
        poly = null; tmpLayer.replaceChildren(); add(s);
      } else { poly = null; tmpLayer.replaceChildren(); drawBars(); }
    };
    const askText = p => {
      const inp = h("input", { type: "text", maxlength: 40, placeholder: I18N.tr(T("A word or two")) });
      const ok = () => {
        const t = inp.value.trim(); m.close(); if (!t) return;
        add({ t: "text", text: t, fs: 48 * U * (kind === "art" ? 2 : 1), tx: p[0], ty: p[1], r: 0, sx: 1, sy: 1, fill: color, stroke: null, sw: 0 });
      };
      inp.onkeydown = e => { if (e.key === "Enter") ok(); };
      const m = modal(h("div.form", h("h2", "🔤 ", T("Text")), inp, h("p.small.muted", T("Pictures speak – keep it to a word or two.")),
        h("div.row", h("button.btn", { onclick: ok }, "✓ ", T("Add")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
      setTimeout(() => inp.focus(), 50);
    };

    // ---------- pointers: one finger draws / moves, two fingers zoom and pan the picture
    const pointers = new Map();
    let pinch = null;
    const cancelGesture = () => {
      if (gesture && gesture.undoTo) { st = JSON.parse(gesture.undoTo); undo.pop(); }
      gesture = null; tmpLayer.replaceChildren(); if (!poly) render(); else drawPoly();
    };
    canvas.addEventListener("pointerdown", e => {
      if (e.button > 0) return;
      e.preventDefault();
      pointers.set(e.pointerId, [e.clientX, e.clientY]);
      try { canvas.setPointerCapture(e.pointerId); } catch {}
      if (pointers.size === 2) {
        cancelGesture();
        const [a, b] = [...pointers.values()];
        pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, mx: (a[0] + b[0]) / 2, my: (a[1] + b[1]) / 2, zoom, panX, panY };
        return;
      }
      if (pointers.size > 2 || pinch) return;
      const p = pt(e), hd = hitHandle(p);
      if (hd) {
        const s = st.shapes[sel];
        gesture = { k: "handle", h: hd, o: { ...s }, p0: p, l0: toLocal(s, p[0], p[1]), undoTo: JSON.stringify(st) }; snap();
        return;
      }
      if (tool === "select") {
        const i = hitShape(e, p);
        sel = i;
        if (i >= 0) { gesture = { k: "move", o: { ...st.shapes[i] }, p0: p, moved: false }; }
        drawOver(); drawBars();
        return;
      }
      if (tool === "fill") {
        const i = hitShape(e, p);
        snap();
        if (i >= 0) { const s = st.shapes[i]; if (s.t === "line") s.stroke = color; else s.fill = color; sel = -1; }
        else st.bg = { c: color };
        render();
        return;
      }
      if (tool === "text") { askText(p); return; }
      if (tool === "shape" && shapeKind === "poly") {
        if (!poly) poly = [];
        const u = upx();
        if (poly.length >= 3 && Math.hypot(p[0] - poly[0][0], p[1] - poly[0][1]) < 22 * u) closePoly();
        else { poly.push(p); drawPoly(); }
        return;
      }
      sel = -1; drawOver();
      if (tool === "pen") {
        const pr = e.pointerType === "pen" && e.pressure > 0 ? e.pressure : null;
        gesture = { k: "pen", pts: [p], pr: pr ? [pr] : [], el: svgEl("path", { fill: "none", stroke: color, "stroke-width": size, "stroke-linecap": "round", "stroke-linejoin": "round" }) };
        tmpLayer.append(gesture.el);
        gesture.el.setAttribute("d", svpSmoothPath([p], 1));
        return;
      }
      gesture = { k: "box", p0: p, p1: p };
    });
    canvas.addEventListener("pointermove", e => {
      if (!pointers.has(e.pointerId)) return;
      e.preventDefault();
      pointers.set(e.pointerId, [e.clientX, e.clientY]);
      if (pinch && pointers.size >= 2) {
        const [a, b] = [...pointers.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
        const z = Math.min(6, Math.max(1, pinch.zoom * d / pinch.d));
        const r = stage.getBoundingClientRect(), ox = pinch.mx - r.left, oy = pinch.my - r.top;
        // the point under the fingers stays under the fingers
        panX = mx - r.left - (ox - pinch.panX) * z / pinch.zoom; panY = my - r.top - (oy - pinch.panY) * z / pinch.zoom;
        zoom = z;
        if (z === 1) { panX = panY = 0; }
        applyZoom();
        return;
      }
      if (!gesture) return;
      const p = pt(e);
      if (gesture.k === "pen") {
        for (const ev of (e.getCoalescedEvents ? e.getCoalescedEvents() : null) || [e]) {
          gesture.pts.push(pt(ev));
          if (ev.pointerType === "pen" && ev.pressure > 0) gesture.pr.push(ev.pressure);
        }
        gesture.el.setAttribute("d", svpSmoothPath(gesture.pts, 1));
      } else if (gesture.k === "box") {
        gesture.p1 = p;
        tmpLayer.replaceChildren(shapeNode(boxShape(gesture.p0, p), -1));
      } else if (gesture.k === "move") {
        const s = st.shapes[sel], dx = p[0] - gesture.p0[0], dy = p[1] - gesture.p0[1];
        if (!gesture.moved && Math.hypot(dx, dy) < 4 * upx()) return;
        if (!gesture.moved) { gesture.moved = true; snap(); gesture.undoTo = undo[undo.length - 1]; }
        s.tx = gesture.o.tx + dx; s.ty = gesture.o.ty + dy;
        els[sel].setAttribute("transform", svpTransform(s)); drawOver();
      } else if (gesture.k === "handle") {
        const s = st.shapes[sel], o = gesture.o;
        if (gesture.h === "rot") {
          const a0 = Math.atan2(gesture.p0[1] - o.ty, gesture.p0[0] - o.tx), a1 = Math.atan2(p[1] - o.ty, p[0] - o.tx);
          let r = (o.r || 0) + (a1 - a0) * 180 / Math.PI;
          r = ((r % 360) + 540) % 360 - 180;
          const near = Math.round(r / 45) * 45;
          s.r = Math.abs(r - near) < 4 ? near : Math.round(r);
        } else if (gesture.h === "scale") {
          const f = Math.max(0.05, Math.hypot(p[0] - o.tx, p[1] - o.ty) / (Math.hypot(gesture.p0[0] - o.tx, gesture.p0[1] - o.ty) || 1));
          s.sx = Math.min(40, (o.sx ?? 1) * f); s.sy = Math.min(40, (o.sy ?? 1) * f);
        } else {
          const l = toLocal(o, p[0], p[1]), i = gesture.h === "sx" ? 0 : 1;
          const f = Math.max(0.05, Math.min(40, l[i] / (gesture.l0[i] || 1)));
          if (i === 0) s.sx = (o.sx ?? 1) * f; else s.sy = (o.sy ?? 1) * f;
        }
        els[sel].setAttribute("transform", svpTransform(s)); drawOver();
      }
    });
    const up = e => {
      if (!pointers.has(e.pointerId)) return;
      pointers.delete(e.pointerId);
      if (pinch) { if (!pointers.size) pinch = null; return; }
      if (!gesture) return;
      const g = gesture; gesture = null;
      if (e.type === "pointercancel") { tmpLayer.replaceChildren(); if (g.undoTo) { st = JSON.parse(g.undoTo); undo.pop(); } render(); return; }
      if (g.k === "pen") {
        tmpLayer.replaceChildren();
        const pts = svpSimplify(g.pts, 0.8 * U * (kind === "art" ? 0.5 : 1) + 0.15);
        const xs = pts.map(q => q[0]), ys = pts.map(q => q[1]), cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const pr = g.pr.length ? g.pr.reduce((a, b) => a + b, 0) / g.pr.length : null;
        add({ t: "path", d: svpSmoothPath(pts.map(q => [q[0] - cx, q[1] - cy]), DEC), tx: cx, ty: cy, r: 0, sx: 1, sy: 1, fill: "none", stroke: color,
          sw: pr ? Math.round(size * (0.35 + pr * 1.3) * 10) / 10 : size });
        sel = -1; drawOver(); drawBars();
      } else if (g.k === "box") {
        tmpLayer.replaceChildren();
        add(boxShape(g.p0, g.p1));
      } else if (g.k === "move" || g.k === "handle") {
        if (g.k === "handle" || g.moved) render();
      }
    };
    canvas.addEventListener("pointerup", up); canvas.addEventListener("pointercancel", up);
    stage.addEventListener("wheel", e => {                     // a mouse: ctrl + wheel (or a touchpad pinch) zooms
      if (!e.ctrlKey) return;
      e.preventDefault();
      const r = stage.getBoundingClientRect(), z = Math.min(6, Math.max(1, zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
      const ox = e.clientX - r.left, oy = e.clientY - r.top;
      panX = ox - (ox - panX) * z / zoom; panY = oy - (oy - panY) * z / zoom; zoom = z;
      if (z === 1) panX = panY = 0;
      applyZoom();
    }, { passive: false });

    // ---------- the selected shape
    const selDo = fn => { if (sel < 0) return; snap(); fn(st.shapes[sel]); render(); };
    const layer = d => selDo(() => { const j = sel + d; if (j < 0 || j >= st.shapes.length) return; [st.shapes[sel], st.shapes[j]] = [st.shapes[j], st.shapes[sel]]; sel = j; });
    const dup = () => selDo(s => { const c = JSON.parse(JSON.stringify(s)); c.tx += 24 * U * (kind === "art" ? 2 : 1); c.ty += 24 * U * (kind === "art" ? 2 : 1); st.shapes.splice(sel + 1, 0, c); sel = sel + 1; });
    const del = () => selDo(() => { st.shapes.splice(sel, 1); sel = -1; });
    const recolor = c => selDo(s => { if (s.t === "line" || (s.t === "path" && (!s.fill || s.fill === "none"))) s.stroke = c; else s.fill = c; });

    // ---------- the bars
    const btn = (on, ic, label, onclick, extra = "") => h("button.svp-tool" + (on ? ".on" : "") + extra, { type: "button", title: label, "aria-label": label, onclick }, ic);
    const setTool = t => { if (poly && t !== "shape") closePoly(); tool = t; drawBars(); };
    const drawBars = () => {
      const SH = SVP_SHAPES();
      sbSet(bar1,
        btn(tool === "select", "👆", T("Select and move"), () => setTool("select")),
        btn(tool === "pen", "✏️", T("Pen"), () => setTool("pen")),
        btn(tool === "line", "╱", T("Line"), () => setTool("line")),
        btn(tool === "shape", SH[shapeKind][0], T("Shapes"), () => { setTool("shape"); panel = panel === "shape" ? null : "shape"; drawBars(); }, ".svp-more"),
        btn(tool === "stamp", SVP_STAMPS[stampKind][0], T("Stamps"), () => { setTool("stamp"); panel = panel === "stamp" ? null : "stamp"; drawBars(); }, ".svp-more"),
        btn(tool === "text", "🔤", T("Text"), () => setTool("text")),
        btn(tool === "fill", "🪣", T("Fill"), () => setTool("fill")),
        btn(panel === "bg", "🌄", T("Background"), () => { panel = panel === "bg" ? null : "bg"; drawBars(); }, ".svp-more"));
      const custom = h("input.svp-custom", { type: "color", value: /^#[0-9a-f]{6}$/i.test(color) ? color : "#1f2433", title: T("Own colour"), "aria-label": T("Own colour") });
      custom.oninput = () => { color = custom.value; if (sel >= 0 && tool === "select") recolor(color); else drawBars(); };
      let row;
      if (panel === "shape") row = [h("span.svp-plabel", T("Shapes")), ...Object.entries(SH).map(([k, [ic, n]]) => btn(shapeKind === k, ic, n, () => { shapeKind = k; tool = "shape"; panel = null; drawBars(); }))];
      else if (panel === "stamp") row = [h("span.svp-plabel", T("Stamps")), ...Object.entries(SVP_STAMP_NAMES()).map(([k, n]) => btn(stampKind === k, SVP_STAMPS[k][0], n,
        () => { stampKind = k; tool = "stamp"; panel = null; color = SVP_STAMPS[k][2]; drawBars(); }))];
      else if (panel === "bg") row = Object.entries(SVP_BGS()).map(([k, [n, stops]]) => h("button.svp-bgp" + (st.bg && st.bg.p === k || (!st.bg && k === "none") ? ".on" : ""),
        { type: "button", title: n, "aria-label": n, style: { background: stops ? (stops.length > 1 ? `linear-gradient(${stops.map(([o, c]) => c + " " + o * 100 + "%").join(",")})` : stops[0][1]) : null },
          onclick: () => { snap(); st.bg = k === "none" ? null : { p: k }; panel = null; render(); } }, h("span", n)));
      else row = [
        ...SIZES.map(sz => btn(size === sz, h("i", { style: { width: Math.min(24, sz / U / (kind === "art" ? 2 : 1) / 1.7 + 3) + "px", height: Math.min(24, sz / U / (kind === "art" ? 2 : 1) / 1.7 + 3) + "px" } }), sz + "",
          () => { size = sz; drawBars(); }, ".svp-size")),
        btn(outline, "◻️", outline ? T("Outline on") : T("Outline off"), () => { outline = !outline; drawBars(); }, ".svp-outline" + (outline ? "" : ".off")),
        h("span.svp-sep"),
        ...SVP_INK.map(c => h("button.svp-col" + (c === color ? ".on" : ""), { type: "button", "aria-label": c, title: c, style: { background: c },
          onclick: () => { color = c; if (sel >= 0 && tool === "select") recolor(c); else drawBars(); } })),
        custom];
      sbSet(bar2, row);
      bar2.classList.toggle("panel", !!panel);
      const s = st.shapes[sel];
      selBar.hidden = !(s || poly);
      if (poly) sbSet(selBar, h("span.small.grow", "⬠ ", T("Tap the corners – tap the first point again to close")),
        h("button.btn.small", { onclick: closePoly, disabled: poly.length < 3 }, "✓ ", T("Close shape")),
        h("button.svp-tool", { title: T("Cancel"), "aria-label": T("Cancel"), onclick: () => { poly = null; drawPoly(); } }, "✕"));
      else if (s) sbSet(selBar,
        btn(false, "🗑", T("Remove"), del), btn(false, "⧉", T("Duplicate"), dup),
        btn(false, "⬆", T("Bring forward"), () => layer(1), sel >= st.shapes.length - 1 ? ".dis" : ""), btn(false, "⬇", T("Send backward"), () => layer(-1), sel <= 0 ? ".dis" : ""),
        btn(false, "↻", T("Straighten"), () => selDo(x => { x.r = 0; })),
        h("span.grow"), btn(false, "✕", T("Done"), () => { sel = -1; drawOver(); drawBars(); }));
    };

    // ---------- open, use, close
    const keys = e => {
      if (e.target.closest && e.target.closest("input, textarea")) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? history(redo, undo) : history(undo, redo); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); history(redo, undo); }
      else if ((e.key === "Delete" || e.key === "Backspace") && sel >= 0 && !document.querySelector(".modal-back")) { e.preventDefault(); del(); }
    };
    const ro = new ResizeObserver(fit);
    const finish = val => {
      if (done) return; done = true;
      ro.disconnect(); document.removeEventListener("keydown", keys); window.removeEventListener("hashchange", onHash);
      wrap.remove(); resolve(val);
    };
    const cancel = async () => {
      if (undo.length && !(await confirmDialog(I18N.tr(T("Throw away this drawing?"))))) return;
      finish(null);
    };
    const finishUse = async () => {
      if (poly) closePoly();
      sel = -1; drawOver();
      const out = svpToSvg(st, W, H);
      if (out.length > spec.max) return toast(I18N.tr(T("The drawing is too large – remove some shapes")), "bad");
      if (!st.shapes.length && !st.locked && !st.bg) return toast(I18N.tr(T("The picture is still empty")), "bad");
      useBtn.disabled = true;
      try { const r = await api("stories/svg", { method: "POST", body: { svg: out, use: kind } }); finish(r.svg); }
      catch (e) { toast(e.message, "bad"); useBtn.disabled = false; }
    };
    const onHash = () => finish(null);
    window.addEventListener("hashchange", onHash);
    document.addEventListener("keydown", keys);
    const wrap = h("div.quiz-full.sb-full.svp-full",
      h("div.svp-top", h("button.icon-btn", { title: T("Cancel"), "aria-label": T("Cancel"), onclick: cancel }, "✕"),
        h("strong.svp-title", title || (kind === "art" ? ["🎨 ", T("Draw a thing")] : ["🎨 ", T("Draw a picture")])),
        meter, h("span.grow"), undoBtn, redoBtn, useBtn),
      bar1, bar2,
      foreign ? h("p.small.muted.svp-note", "🔒 ", T("The picture you had is one locked layer – draw on top of it.")) : null,
      stage);
    stage.append(zoomBtn);
    document.body.append(wrap);
    ro.observe(stage);
    render(); fit(); applyZoom();
  });
}
