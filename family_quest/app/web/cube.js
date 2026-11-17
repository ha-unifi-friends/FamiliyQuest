// Cube solver of the game corner: paint the colours of your puzzle cube on a 3D cube (or a flat net), check them and
// follow the moves step by step. Model and solvers: web/cubesolver.js (also as a Web Worker). Runs on this device only;
// the painted colours and the guide are kept in this browser (arcadeStore).
"use strict";

const CUBE_HEX = { W: "#ffffff", Y: "#ffd500", R: "#c8102e", O: "#ff6d00", B: "#0046ad", G: "#009b48" };
const CUBE_NAME = { W: T("white"), Y: T("yellow"), R: T("red"), O: T("orange"), B: T("blue"), G: T("green") };
const CUBE_ORDER = ["W", "Y", "R", "O", "B", "G"];
const CUBE_PHASE = {
  cross: [T("White cross"), T("The four white edges go to the bottom, each one under the side with its colour.")],
  corners: [T("White corners"), T("The corners with white go into the bottom layer – then the whole bottom is white.")],
  middle: [T("Middle layer"), T("The edges without yellow go into the middle layer – two layers are done.")],
  ycross: [T("Yellow cross"), T("Now a yellow cross appears on top.")],
  yedges: [T("Yellow edges"), T("The edges of the yellow cross move to the side with their colour.")],
  ycorners: [T("Yellow corners to their place"), T("Every top corner moves to its own place – it may still be twisted.")],
  yorient: [T("Turn the yellow corners"), T("The bottom gets messy for a while – keep going, at the end it is tidy again!")],
  solve2: [T("Solve the cube"), T("The shortest way: follow the moves – after the last one every side has one colour.")],
};
// what a move does, said for children (the cube is held still: front towards you, top up)
const CUBE_MOVE = {
  "U": ["←", T("Turn the TOP layer to the left")], "U'": ["→", T("Turn the TOP layer to the right")], "U2": ["←←", T("Turn the TOP layer twice")],
  "D": ["→", T("Turn the BOTTOM layer to the right")], "D'": ["←", T("Turn the BOTTOM layer to the left")], "D2": ["→→", T("Turn the BOTTOM layer twice")],
  "R": ["↑", T("Turn the RIGHT side up")], "R'": ["↓", T("Turn the RIGHT side down")], "R2": ["↑↑", T("Turn the RIGHT side twice")],
  "L": ["↓", T("Turn the LEFT side down")], "L'": ["↑", T("Turn the LEFT side up")], "L2": ["↓↓", T("Turn the LEFT side twice")],
  "F": ["↻", T("Turn the FRONT clockwise")], "F'": ["↺", T("Turn the FRONT anticlockwise")], "F2": ["↻↻", T("Turn the FRONT twice")],
  "B": ["↺", T("Turn the BACK – its top goes to the left")], "B'": ["↻", T("Turn the BACK – its top goes to the right")], "B2": ["↺↺", T("Turn the BACK twice")],
};
const CUBE_VIEWS = [["F", T("Front side"), -22, -22], ["B", T("Back side"), 158, -22], ["L", T("Left side"), 68, -22],
  ["R", T("Right side"), -68, -22], ["U", T("Top side"), -22, -68], ["D", T("Bottom side"), -22, 68]];
const CUBE_FACE_CSS = ["rotateX(90deg)", "rotateY(90deg)", "", "rotateX(-90deg)", "rotateY(-90deg)", "rotateY(180deg)"];   // U R F D L B

// the 3D cube: stickers as tiles turned into place with CSS 3D; drag to look around, tap a sticker to paint it
function cube3d(n, { onTap } = {}) {
  const g = CubeSolver.geom(n), scene = h("div.cb-scene"), body = h("div.cb-cube");
  scene.append(body);
  let yaw = -30, pitch = -24, size = 240, colors = [], marks = new Set(), anim = null;
  const tiles = g.pos.map((p, i) => h("div.cb-st", { "data-i": i }));
  body.append(...tiles);
  const base = i => {
    const s = size / n, p = g.pos[i], nr = [[0, 1, 0], [1, 0, 0], [0, 0, 1], [0, -1, 0], [-1, 0, 0], [0, 0, -1]][g.face[i]];
    const x = (p[0] + nr[0]) * s / 2, y = -(p[1] + nr[1]) * s / 2, z = (p[2] + nr[2]) * s / 2;
    return `translate3d(${x}px,${y}px,${z}px) ${CUBE_FACE_CSS[g.face[i]]}`;
  };
  const place = () => {
    const s = size / n;
    tiles.forEach((t, i) => { t.style.width = t.style.height = s + "px"; t.style.margin = -s / 2 + "px"; t.style.transform = base(i); });
    view();
  };
  // which faces look at the viewer (only those can be tapped)
  const facing = () => {
    const ry = yaw * Math.PI / 180, rx = pitch * Math.PI / 180;
    return [[0, -1, 0], [1, 0, 0], [0, 0, 1], [0, 1, 0], [-1, 0, 0], [0, 0, -1]].map(([x, y, z]) => {
      const z1 = -x * Math.sin(ry) + z * Math.cos(ry);           // rotateY, then rotateX (css: y down)
      return y * Math.sin(rx) + z1 * Math.cos(rx) > 0.08;
    });
  };
  const view = () => {
    body.style.transform = `rotateX(${pitch}deg) rotateY(${yaw}deg)`;
    const f = facing();
    tiles.forEach((t, i) => t.classList.toggle("hidden", !f[g.face[i]]));
  };
  const paint = () => tiles.forEach((t, i) => {
    const c = colors[i];
    t.style.setProperty("--c", CUBE_HEX[c] || "");
    t.classList.toggle("empty", !CUBE_HEX[c]);
    t.classList.toggle("mark", marks.has(i));
    t.classList.toggle("fixed", n === 3 && i % 9 === 4);
  });
  // drag to turn the view, a short tap paints
  let down = null;
  scene.addEventListener("pointerdown", e => {
    down = { x: e.clientX, y: e.clientY, yaw, pitch, moved: false, tile: e.target.closest(".cb-st") };
    try { scene.setPointerCapture(e.pointerId); } catch {}
  });
  scene.addEventListener("pointermove", e => {
    if (!down) return;
    const dx = e.clientX - down.x, dy = e.clientY - down.y;
    if (!down.moved && Math.hypot(dx, dy) < 8) return;
    down.moved = true;
    yaw = down.yaw + dx * 0.55; pitch = Math.max(-89, Math.min(89, down.pitch - dy * 0.55));
    body.classList.remove("smooth"); view();
  });
  const up = () => {
    if (down && !down.moved && down.tile && !down.tile.classList.contains("hidden") && onTap) onTap(+down.tile.dataset.i);
    down = null;
  };
  scene.addEventListener("pointerup", up);
  scene.addEventListener("pointercancel", () => { down = null; });
  const ro = new ResizeObserver(() => {
    const w = scene.clientWidth, hh = scene.clientHeight;
    if (!w || !hh) return;
    const ns = Math.round(Math.min(w, hh) * 0.56);
    if (ns !== size) { size = ns; place(); }
  });
  ro.observe(scene);
  place();
  return {
    el: scene,
    set(c, m) { colors = c.slice(); marks = new Set(m || []); paint(); },
    look(y, p, smooth = true) { yaw = y; pitch = p; body.classList.toggle("smooth", smooth); view(); },
    // turn one layer: the tiles of the layer rotate about the face axis, then the new colours are shown
    turn(move, ms = 420) {
      if (anim) { cancelAnimationFrame(anim.raf); anim.done(); }
      const f = CubeSolver.FACES.indexOf(move[0]), ax = [[0, 1, 0], [1, 0, 0], [0, 0, 1], [0, -1, 0], [-1, 0, 0], [0, 0, -1]][f];
      const deg = move.endsWith("2") ? 180 : move.endsWith("'") ? -90 : 90, k = n - 1;
      const layer = tiles.filter((t, i) => g.pos[i][0] * ax[0] + g.pos[i][1] * ax[1] + g.pos[i][2] * ax[2] === k);
      const after = CubeSolver.apply(colors, move, n);
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) { this.set(after, []); return Promise.resolve(); }
      const t0 = performance.now(), dur = deg === 180 ? ms * 1.4 : ms;
      return new Promise(res => {
        const done = () => { anim = null; layer.forEach(t => { t.style.transform = base(+t.dataset.i); }); this.set(after, []); res(); };
        const frame = now => {
          const p = Math.min(1, (now - t0) / dur), e = p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
          layer.forEach(t => { t.style.transform = `rotate3d(${ax[0]},${-ax[1]},${ax[2]},${deg * e}deg) ` + base(+t.dataset.i); });
          if (p < 1) anim.raf = requestAnimationFrame(frame); else done();
        };
        anim = { done, raf: requestAnimationFrame(frame) };
      });
    },
  };
}

// the flat net: top above, then left, front, right, back, then bottom – for small phones
function cubeNet(n, colors, marks, onTap) {
  const g = CubeSolver.geom(n), at = { 0: [0, 1], 4: [1, 0], 2: [1, 1], 1: [1, 2], 5: [1, 3], 3: [2, 1] };
  const net = h("div.cb-net", { style: { gridTemplateColumns: `repeat(${4 * n}, 1fr)` } });
  colors.forEach((c, i) => {
    const f = g.face[i], r = Math.floor((i % (n * n)) / n), col = i % n, [fr, fc] = at[f];
    net.append(h("button.cb-nst" + (CUBE_HEX[c] ? "" : ".empty") + (marks.has(i) ? ".mark" : "") + (n === 3 && i % 9 === 4 ? ".fixed" : ""),
      { style: { "--c": CUBE_HEX[c] || "", gridRow: fr * n + r + 1, gridColumn: fc * n + col + 1 }, "aria-label": I18N.tr(CUBE_NAME[c] || T("no colour")),
        onclick: () => onTap(i) }));
  });
  return net;
}

function cubeGame(box) {
  box.closest(".quiz-full")?.classList.add("cb-live");
  const saved = arcadeStore.get().cube || {};
  let n = saved.n === 2 ? 2 : 3, pick = saved.pick || "W", netView = !!saved.net, marks = new Set(), msg = null;
  const input = { 2: blank(2), 3: blank(3) };
  for (const k of [2, 3]) if (Array.isArray((saved.st || {})[k]) && saved.st[k].length === 6 * k * k) input[k] = saved.st[k].map(c => CUBE_HEX[c] ? c : "");
  let guide = saved.guide && saved.guide.phases ? saved.guide : null;
  function blank(k) { const c = Array(6 * k * k).fill(""); if (k === 3) CubeSolver.COLORS.forEach((col, f) => { c[f * 9 + 4] = col; }); return c; }
  const store = () => arcadeStore.set("cube", { n, pick, net: netView, st: input, guide });

  // ------------------------------------------------ painting the colours
  let viewer = null;
  const tap = i => {
    if (n === 3 && i % 9 === 4) return toast(I18N.tr(T("The middle sticker shows the colour of this side – it cannot change.")));
    input[n][i] = pick; marks.delete(i); msg = null; store();
    try { Sound.play("tap"); } catch {}
    if (netView) drawEdit(); else { viewer.set(input[n], marks); drawMsg(); }
  };
  const msgBox = h("div.cb-msg");
  const drawMsg = () => msgBox.replaceChildren(...(msg ? [h("p" + (msg.bad ? ".bad" : ".muted"), msg.text)] : []));
  const counts = () => { const c = {}; for (const x of input[n]) if (x) c[x] = (c[x] || 0) + 1; return c; };
  const drawEdit = () => {
    const cnt = counts(), want = n * n;
    const sizes = segmented([[2, "2×2"], [3, "3×3"]], n, v => { n = v; marks = new Set(); msg = null; store(); drawEdit(); });
    const big = h("button.cb-soon", { disabled: true, title: T("coming later") }, "4×4 ", h("small", T("coming later")));
    const area = h("div.cb-area");
    if (netView) area.append(cubeNet(n, input[n], marks, tap));
    else {
      viewer = cube3d(n, { onTap: tap }); viewer.set(input[n], marks); area.append(viewer.el);
    }
    const views = netView ? null : h("div.cb-views", ...CUBE_VIEWS.map(([k, label, y, p]) => h("button", { onclick: () => viewer.look(y, p) }, label)));
    const palette = h("div.cb-palette", ...CUBE_ORDER.map(c => h("button.cb-sw" + (c === pick ? ".on" : ""), {
      style: { "--c": CUBE_HEX[c] }, title: CUBE_NAME[c], "aria-label": CUBE_NAME[c], onclick: () => { pick = c; store(); drawEdit(); } },
      h("small", (cnt[c] || 0) + "/" + want))));
    box.replaceChildren(h("div.cb-wrap",
      h("div.cb-top", sizes, big, h("button.btn.small.ghost.cb-toggle", { onclick: () => { netView = !netView; store(); drawEdit(); } }, netView ? "🧊 3D" : "▦ " + I18N.tr(T("Net")))),
      h("p.small.muted.cb-hint", n === 3 ? T("Hold your cube with the yellow centre on top and the green centre in front. Pick a colour, then tap the stickers.")
        : T("Hold your cube still: front towards you, top up. Pick a colour, then tap the stickers.")),
      area, views, palette, msgBox,
      h("div.cb-actions",
        h("button.btn.ghost", { title: T("Clear all colours"), onclick: () => { input[n] = blank(n); marks = new Set(); msg = null; store(); drawEdit(); } }, "🧽"),
        h("button.btn.ghost", { title: T("Fill in a solved cube"), onclick: () => { input[n] = CubeSolver.solvedColors(n); marks = new Set(); msg = null; store(); drawEdit(); } }, "✨"),
        h("button.btn.ghost", { title: T("Mix the cube (to try it out)"), onclick: () => { input[n] = CubeSolver.scrambledColors(n, CubeSolver.scramble(n === 2 ? 12 : 22, n)); marks = new Set(); msg = null; store(); drawEdit(); } }, "🎲"),
        h("button.btn.grow", { onclick: start }, "▶ ", T("Solve")))));
    drawMsg();
  };

  // ------------------------------------------------ check and solve (in a Web Worker, so the page stays smooth)
  let worker = null, wid = 0;
  const solveAsync = (k, st) => new Promise(res => {
    try {
      worker = worker || new Worker("cubesolver.js");
      const id = ++wid, t = setTimeout(() => res(CubeSolver.solve(st, k)), 8000);
      worker.onmessage = e => { if (e.data.id === id) { clearTimeout(t); res(e.data.result); } };
      worker.onerror = () => { clearTimeout(t); res(CubeSolver.solve(st, k)); };
      worker.postMessage({ id, n: k, stickers: st });
    } catch { res(CubeSolver.solve(st, k)); }
  });
  const colorList = cs => (cs || []).map(c => I18N.tr(CUBE_NAME[c])).join("-");
  const errorText = r => {
    const tr = s => I18N.tr(s);
    switch (r.code) {
      case "blank": return tr(T("{0} stickers have no colour yet.")).replace("{0}", r.count);
      case "count": return tr(T("There are {0} stickers in {1} – there must be exactly {2}.")).replace("{0}", r.have).replace("{1}", tr(CUBE_NAME[r.color])).replace("{2}", r.want);
      case "corner-impossible": return tr(T("This corner cannot exist: {0}. Check its colours.")).replace("{0}", colorList(r.colors));
      case "corner-mirror": return tr(T("Two colours of this corner are swapped: {0}.")).replace("{0}", colorList(r.colors));
      case "corner-twice": return tr(T("This corner is there twice: {0}.")).replace("{0}", colorList(r.colors));
      case "edge-impossible": return tr(T("This edge cannot exist: {0}. Check its colours.")).replace("{0}", colorList(r.colors));
      case "edge-twice": return tr(T("This edge is there twice: {0}.")).replace("{0}", colorList(r.colors));
      case "twist": return tr(T("Check the colours – one corner is twisted."));
      case "flip": return tr(T("Check the colours – one edge is flipped."));
      case "parity": return tr(T("Check the colours – two pieces are swapped."));
      case "centre": return tr(T("The middle stickers are wrong – tap 🧽 to start again."));
      default: return tr(T("Something went wrong – please check the colours."));
    }
  };
  async function start() {
    msg = { text: I18N.tr(T("Thinking…")) }; drawMsg();
    const st = input[n].slice(), r = await solveAsync(n, st);
    if (!r.ok) {
      marks = new Set(r.stickers || []); msg = { bad: true, text: "🤔 " + errorText(r) };
      try { Sound.play("wrong"); } catch {}
      // show the first marked sticker
      if (!netView && marks.size) { const f = CubeSolver.geom(n).face[[...marks][0]], v = CUBE_VIEWS.find(x => x[0] === CubeSolver.FACES[f]); viewer.look(v[2], v[3]); }
      if (netView) drawEdit(); else { viewer.set(input[n], marks); drawMsg(); }
      return;
    }
    if (!r.total) { msg = { text: "🎉 " + I18N.tr(T("This cube is already solved!")) }; drawMsg(); return; }
    guide = { n, stickers: st, phases: r.phases, ref: r.ref, step: 0 };
    store(); drawGuide(true);
  }

  // ------------------------------------------------ the step-by-step guide
  const steps = () => guide.phases.flatMap((p, pi) => p.moves.map(m => ({ m, pi })));
  const stateAt = k => CubeSolver.applyAll(guide.stickers, steps().slice(0, k).map(s => s.m), guide.n);
  let gv = null;
  const lookFor = m => m[0] === "L" ? [32, -24] : m[0] === "D" ? [-30, 26] : m[0] === "B" ? [-40, -38] : [-30, -24];
  function drawGuide(intro = false, animate = false) {
    const all = steps(), k = guide.step, total = all.length;
    gv = cube3d(guide.n);
    const head = h("div.cb-ghead"), card = h("div.cb-move"), nav = h("div.cb-nav");
    if (intro || k === 0) {
      gv.set(guide.stickers, []); gv.look(-30, -24, false);
      const hold = guide.n === 3
        ? h("p", T("Hold your cube with the yellow centre on top and the green centre in front – and keep it like that until the end."))
        : h("p", I18N.tr(T("Hold your cube exactly as you painted it: front towards you, top up. The corner {0} at the back, bottom left never moves."))
          .replace("{0}", colorList([guide.ref[3], guide.ref[5], guide.ref[4]])));
      head.append(h("strong", "🧊 ", I18N.tr(T("{0} moves")).replace("{0}", total)), guide.phases.length > 1 ? h("span.muted.small", " · " + I18N.tr(T("{0} phases")).replace("{0}", guide.phases.length)) : null);
      card.append(h("div.cb-hold", guide.n === 3 ? [h("span.cb-dot", { style: { "--c": CUBE_HEX.Y } }), h("span.cb-dot", { style: { "--c": CUBE_HEX.G } })] : null), hold);
      nav.append(h("button.btn.ghost", { onclick: edit }, "✎ ", T("Colours")), h("button.btn.grow", { onclick: () => go1(1) }, T("Let's go"), " ▶"));
    } else if (k > total) {
      gv.set(stateAt(total), []); gv.look(-30, -24, false);
      head.append(h("strong", "🎉 ", T("Solved! Great job!")));
      card.append(h("p", I18N.tr(T("You made it in {0} moves.")).replace("{0}", total)));
      nav.append(h("button.btn.ghost", { onclick: () => go1(total) }, "◀ ", T("Back")), h("button.btn.grow", { onclick: () => { guide = null; input[n] = blank(n); store(); drawEdit(); } }, T("Next cube")));
    } else {
      const s = all[k - 1], ph = guide.phases[s.pi], [arrow, text] = CUBE_MOVE[s.m], [pname, ptext] = CUBE_PHASE[ph.key];
      const inPhase = all.slice(0, k).filter(x => x.pi === s.pi).length;
      gv.set(stateAt(animate ? k - 1 : k), []);
      const [ly, lp] = lookFor(s.m); gv.look(ly, lp, false);
      head.append(h("div.cb-prog", h("i", { style: { width: (k / total * 100).toFixed(1) + "%" } })),
        h("div.row.cb-ph", h("strong.grow", pname), h("span.small.muted", I18N.tr(T("Step {0} of {1}")).replace("{0}", k).replace("{1}", total))));
      card.append(h("div.cb-mv", h("b.cb-note", { translate: "no" }, s.m), h("span.cb-arrow", arrow), h("span.cb-text", text)),
        h("p.small.muted.cb-ptext", h("span", ptext), " (" + inPhase + "/" + ph.moves.length + ")"),
        h("p.small.muted.cb-then", I18N.tr(T("Then:")) + " " + (all.slice(k, k + 6).map(x => x.m).join(" ") || "🎉")));
      nav.append(h("button.btn.ghost", { onclick: () => go1(k - 1) }, "◀ ", T("Back")),
        h("button.btn.ghost", { title: T("Show again"), onclick: () => { gv.set(stateAt(k - 1), []); gv.turn(s.m); } }, "🔁"),
        h("button.btn.grow.cb-next", { onclick: () => go1(k + 1, true) }, T("Next"), " ▶"));
    }
    box.replaceChildren(h("div.cb-wrap.cb-guide", head, h("div.cb-area", gv.el), card, nav));
    if (animate && k >= 1 && k <= total) setTimeout(() => gv.turn(all[k - 1].m), 120);
  }
  function go1(k, forward = false) {
    const total = steps().length;
    guide.step = Math.max(0, Math.min(total + 1, k)); store();
    if (guide.step === total + 1) { confetti(); try { Sound.play("done"); } catch {} }
    drawGuide(false, forward && guide.step <= total);
  }
  function edit() { input[guide.n] = guide.stickers.slice(); n = guide.n; guide = null; store(); drawEdit(); }

  // keyboard: arrows go through the guide
  document.addEventListener("keydown", function key(e) {
    if (!box.isConnected) return document.removeEventListener("keydown", key);
    if (!guide || e.target.closest?.("input, textarea, select")) return;
    if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); go1(guide.step + 1, true); }
    else if (e.key === "ArrowLeft") go1(guide.step - 1);
  });
  if (guide) drawGuide(); else drawEdit();
}
