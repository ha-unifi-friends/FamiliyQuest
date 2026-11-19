// «Traffic Cadet» (Verkehrskadett) – a live game (familyquest/verkehr.py): everybody regulates the traffic lights of
// their own map. Tap a light (or its button below the map) to switch the group: green → amber → red, red → green.
// Cars, buses, bikes and now and then an ambulance drive by simple rules: stop at red, go at green, keep a gap, turn as
// their route says – two cars of crossing routes in the junction at the same time crash (💥). Waiting makes the
// drivers annoyed (😐 → 😠) and angry (😡). Too many accidents or angry drivers: out. Worlds: a simple crossing, a
// T-junction, turning lanes, two crossings, a roundabout – everybody still in moves on together.
// vkLive(box, me, back) runs a table (family or alone), vkStartDialog(solo, onStarted) sets the rules.
// The map is simulated here (vkStep – integer steps, the same as step() in verkehr.py) from the server's worlds and my
// switches; the server re-simulates it a moment later (its result counts). The others' stats come from the server.
// Uses botPicker() from cards.js and guestInvite() from community.js.
"use strict";

const VK_ICON = "🚦";
const vkName = () => I18N.tr(T("Traffic Cadet"));
const vkCoins = list => list.join(" / ") + " 🪙";
// the simulation – the same numbers as in verkehr.py
const VK = { HZ: 10, INTRO: 5, PLAY: 90, KLEN: [18, 30, 10, 20], KV: [4, 3, 2, 5], KPTS: [1, 2, 1, 3], GAP: 6, AMBER: 15, BLOCK: 40,
  AMB_MOOD: [30, 60], LANE: 20 };
VK.WT = (VK.INTRO + VK.PLAY) * VK.HZ;
const VK_COLORS = ["#e8590c", "#1c7ed6", "#2f9e44", "#ae3ec9", "#f08c00", "#0c8599", "#d6336c", "#5c7cfa", "#495057"];
const VK_MOODS = ["", "😐", "😠", "😡"];
const VK_WORLDS = [T("Simple crossing"), T("T-junction"), T("Crossing with turning lanes"), T("Two crossings"), T("Roundabout")];   // the names come from the server

function vkPrep(w) {                             // what the step needs of a world, precomputed (Prep in verkehr.py)
  const paths = w.paths, n = paths.length;
  const lidx = paths.map(p => { const o = new Map(); p.links.forEach((lk, i) => o.set(lk, i)); return o; });
  const shares = paths.map(p => paths.map(q => p.links.some(lk => q.links.includes(lk))));
  const cbp = paths.map(() => []);
  for (const [i, a, b, j, c, d] of w.conf) { cbp[i].push([a, b, j, c, d]); cbp[j].push([c, d, i, a, b]); }
  return { w, paths, lidx, shares, cbp, n };
}
function vkNewState(w, la, lg) {
  return { k: 0, nid: 1, ai: 0, ei: 0, cars: [], pend: w.entries.map(() => []), lights: w.groups.map(() => [0, 0]),
    acc: 0, ann: 0, ang: 0, pas: 0, pts: 0, la, lg, out: null, crash: [] };
}
// a car: [id, path, pos (front), kind, wait, mood, wreck (ticks left), moved]
function vkCur(prep, c) {
  const cum = prep.paths[c[1]].cum;
  let k = 0;
  while (k + 2 < cum.length && cum[k + 1] <= c[2]) k++;
  return k;
}
function vkMood(S, kind, wait, mood, thr) {
  const [a, g] = kind === 3 ? VK.AMB_MOOD : thr;
  const lvl = wait >= g ? 3 : wait >= a ? 2 : wait * 2 >= a ? 1 : 0;
  if (lvl <= mood) return mood;
  if (lvl >= 2 && mood < 2) S.ann++;
  if (lvl >= 3 && mood < 3) S.ang++;
  return lvl;
}
// one tick of a map (integer arithmetic only – the same as step() in verkehr.py)
function vkStep(prep, S, ev, thr) {
  if (S.out != null) return;
  const W = prep.w, P = prep.paths, KLEN = VK.KLEN, GAP = VK.GAP;
  const k1 = S.k + 1, lights = S.lights;
  for (const L of lights) if (L[0] === 2) { L[1]--; if (L[1] <= 0) { L[0] = 0; L[1] = 0; } }
  while (S.ei < ev.length && ev[S.ei][0] <= k1) {
    const [, g, want] = ev[S.ei]; S.ei++;
    if (g >= 0 && g < lights.length) {
      if (want) lights[g] = [1, 0];
      else if (lights[g][0] === 1) lights[g] = [2, VK.AMBER];
    }
  }
  const arr = W.arrivals;
  while (S.ai < arr.length && arr[S.ai][0] <= k1) {
    const [, p, kind] = arr[S.ai]; S.ai++;
    S.pend[P[p].entry].push([p, kind, 0, 0]);
  }
  const cars = S.cars;
  S.pend.forEach((q, e) => {
    if (q.length && cars.every(c => !(P[c[1]].entry === e && c[2] - KLEN[c[3]] < GAP))) {
      const [p, kind, wait, mood] = q.shift();
      cars.push([S.nid, p, 0, kind, wait, mood, 0, 1]); S.nid++;
    }
  });
  let cur = cars.map(c => vkCur(prep, c));
  const wrecks = cars.filter(c => c[6] > 0);
  const nw = [];
  cars.forEach((A, ia) => {
    const pos = A[2];
    if (A[6] > 0) { nw.push(pos); return; }
    const pa = A[1], kind = A[3], p = P[pa], v = VK.KV[kind];
    let lim = pos + v;
    for (const [sp, g, yi] of p.stops) {
      if (pos <= sp) {
        const stl = g >= 0 ? lights[g][0] : 1;
        if (stl === 0 || (stl === 2 && !(A[7] && sp - pos > 0 && sp - pos <= 2 * v))) lim = Math.min(lim, sp);
        else if (yi >= 0 && lim > sp) {
          for (const [lk, a, b, need] of W.yields[yi]) {
            cars.forEach((B, ib) => {
              if (P[B[1]].links[cur[ib]] === lk && (need < 0 || prep.lidx[B[1]].has(need))) {
                const f = B[2] - P[B[1]].cum[cur[ib]];
                if (a <= f && f <= b) lim = Math.min(lim, sp);
              }
            });
          }
        }
      }
    }
    const ka = cur[ia], lidx = prep.lidx[pa], sh = prep.shares[pa];
    cars.forEach((B, ib) => {
      if (ib === ia || !sh[B[1]]) return;
      const pb = P[B[1]], lb = pb.links[cur[ib]];
      let x = lidx.get(lb);
      if (x !== undefined && x >= ka) {
        const front = p.cum[x] + B[2] - pb.cum[cur[ib]];
        if (front > pos) lim = Math.min(lim, front - KLEN[B[3]] - GAP);
      } else {
        const rear = B[2] - KLEN[B[3]];
        let kr = 0;
        while (kr + 2 < pb.cum.length && pb.cum[kr + 1] <= rear) kr++;
        x = lidx.get(pb.links[kr]);
        if (x !== undefined && x >= ka) {
          const r = p.cum[x] + rear - pb.cum[kr];
          if (r + KLEN[B[3]] > pos) lim = Math.min(lim, r - GAP);
        }
      }
    });
    if (wrecks.length) {
      for (const [a, , q, c, d] of prep.cbp[pa]) {
        if (pos < a) for (const Wc of wrecks) if (Wc[1] === q && Wc[2] > c && Wc[2] - KLEN[Wc[3]] < d) lim = Math.min(lim, a - 2);
      }
    }
    nw.push(Math.max(pos, lim));
  });
  cars.forEach((c, i) => { c[7] = nw[i] > c[2] ? 1 : 0; c[2] = nw[i]; });
  if (cars.length) {
    cur = cars.map(c => vkCur(prep, c));
    const by = new Map();
    cars.forEach((c, i) => { if (!by.has(c[1])) by.set(c[1], []); by.get(c[1]).push(i); });
    const fresh = new Set(), old = new Set();
    cars.forEach((c, i) => { if (c[6] > 0) old.add(i); });
    for (const [i, a, b, j, c, d] of W.conf) {
      if (!by.has(i) || !by.has(j)) continue;
      for (const x of by.get(i)) {
        const A = cars[x];
        if (old.has(x) || !(A[2] > a && A[2] - KLEN[A[3]] < b)) continue;
        for (const y of by.get(j)) {
          const B = cars[y];
          if (old.has(y) || !(B[2] > c && B[2] - KLEN[B[3]] < d)) continue;
          if (prep.lidx[A[1]].has(P[B[1]].links[cur[y]]) || prep.lidx[B[1]].has(P[A[1]].links[cur[x]])) continue;
          if (!fresh.has(x) && !fresh.has(y)) { S.acc++; S.crash.push([k1, A[0], B[0]]); }
          for (const z of [x, y]) if (!fresh.has(z)) { fresh.add(z); cars[z][6] = VK.BLOCK + 1; }
        }
      }
    }
    if (S.crash.length > 6) S.crash.splice(0, S.crash.length - 6);
  }
  const keep = [];
  for (const c of cars) {
    if (c[6] > 0) { c[6]--; if (c[6] > 0) keep.push(c); continue; }
    if (!c[7]) { c[4]++; c[5] = vkMood(S, c[3], c[4], c[5], thr); }
    if (c[2] - KLEN[c[3]] >= P[c[1]].len) { S.pas++; S.pts += VK.KPTS[c[3]]; continue; }
    keep.push(c);
  }
  S.cars = keep;
  for (const q of S.pend) for (const c of q) { c[2]++; c[3] = vkMood(S, c[1], c[2], c[3], thr); }
  S.k = k1;
  if (S.acc >= S.la || S.ang >= S.lg) S.out = k1;
}

// ---------------------------------------------------------------- the rules, the start
function vkRulesView(r, rewards, limits) {
  r = r || {};
  const lim = limits || { acc: 3, ang: 10 };
  const items = [
    T("Everybody has their own map – the same streets and the same cars for everybody."),
    T("Tap a traffic light (or its button below the map) to switch its group: green → amber → red, red → green."),
    T("At red the cars stop, at amber those that still can – at green they go. Cars of crossing routes at the same time in the junction crash 💥 (a short blockage)."),
    T("Waiting makes the drivers annoyed 😐 → 😠 and then angry 😡 – the ambulance 🚑 is in a hurry and gets angry much sooner."),
    I18N.tr(T("Out: {0} accidents or {1} angry drivers.")).replace("{0}", lim.acc).replace("{1}", lim.ang),
    T("Worlds: a simple crossing, a T-junction, turning lanes, two crossings, a roundabout (the drivers yield to the ring – you have a light at every entry). Everybody still in moves on together."),
    T("Points: every car through (bus 2, ambulance 3), minus 5 per accident and 2 per angry driver. Who is still in wins by points – the last one standing at a family table."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", vkCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function vkStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/verkehr/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(r.bots ?? 0, [0, 1, 2, 3, 4, 5].map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const diff = sel(r.difficulty || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const names = r.worlds_names || [];
  const worlds = sel(r.worlds || 3, [1, 2, 3, 4, 5].map(n => [n, "🌍 " + n + (names[n - 1] ? " – " + I18N.tr(names[n - 1]) : "")]));
  const picker = botPicker(1400);
  const speed = picker.el.querySelector(".bot-speed");
  if (speed) speed.remove();
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", vkCoins(rw)), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", VK_ICON, " ", vkName(), solo ? " – " + I18N.tr(T("Alone")) : ""),
    h("p.small.muted", T("Switch the traffic lights – no accidents, no angry drivers! Everybody gets the same streets and cars.")),
    h("div.grid2", h("label.field", T("Difficulty"), diff), h("label.field", T("Worlds"), worlds)),
    h("div.grid2", h("label.field", solo ? T("Practice bots") : T("Bots"), bots), h("label.field", T("Bots play"), level)),
    solo ? null : h("p.small.muted", T("1 to 6 players: the family joins on their own devices, guests via QR code.")),
    picker.el,
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: +bots.value, level: level.value, difficulty: diff.value, worlds: +worlds.value, bot_ids: picker.ids() };
      try { await api("community/verkehr/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("verkehr", bots, level, picker.el);       // parent area › Games: without bots
}

function vkDark() {
  const th = document.documentElement.getAttribute("data-theme");
  return th === "dark" || (th !== "light" && !!(window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches));
}
function vkHonk() {                              // a short double honk (angry driver)
  if (!Sound.on) return;
  try {
    Sound.ctx = Sound.ctx || new (window.AudioContext || window.webkitAudioContext)();
    const ctx = Sound.ctx;
    [0, 0.16].forEach(dt => {
      const o = ctx.createOscillator(), g = ctx.createGain(), t = ctx.currentTime + dt;
      o.type = "square"; o.frequency.value = 392;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.06, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
      o.connect(g).connect(ctx.destination); o.start(t); o.stop(t + 0.13);
    });
  } catch {}
}

// ---------------------------------------------------------------- the live table
function vkLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, raf = 0, syncing = false, lastSync = 0;
  let offset = null, bestRtt = 1e9;
  let canvas = null, ctx = null, wrap = null, barEl = null, groupsEl = null, statEl = null, cw = 0, ch = 0, dpr = 1;
  let worlds = null, worldsKey = "", preps = [], geo = [];
  let myW = 0, myS = null, myTot = null, myEvs = {}, myOut = null, pendEv = [], prevPos = new Map(), lastStepAt = 0, gameKey = "";
  let rebasing = false, seenCrash = 0, seenAng = 0, tapFlash = null;
  const myId = String(me.id);
  box.classList.add("vk-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); cancelAnimationFrame(raf); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const nowS = () => performance.now() / 1000;
  const gameT = () => (st && offset != null ? nowS() + offset - st.t0 : -9);
  const playing = () => st && st.phase === "play" && st.status !== "done";
  const nW = () => (st && st.rules && st.rules.worlds) || 1;
  const lim = () => (st && st.limits) || { acc: 3, ang: 10, annoy: 100, angry: 200 };
  const thr = () => [lim().annoy, lim().angry];

  function clock(s, t1, t2) {
    if (!s || typeof s.now !== "number") return;
    const rtt = t2 - t1;
    if (rtt <= bestRtt * 1.15 || offset == null) { bestRtt = Math.min(bestRtt, rtt); offset = s.now - (t1 + t2) / 2; }
  }
  const req = async (path, opts) => {
    const t1 = nowS();
    const s = await api("community/verkehr" + path, opts);
    clock(s, t1, nowS());
    return s;
  };
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { setState(await req("/" + path, { method: "POST", body: body || {} })); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); }
  };
  function setState(s) {
    if (s && !Array.isArray(s.players)) s = null;
    st = s;
    if (!st || !st.seed) return;
    const key = st.game + ":" + st.seed;
    if (key !== gameKey) { gameKey = key; myS = null; myOut = null; pendEv = []; cheered = false; prevPos = new Map(); }
    if (st.my) rebase(st.my);
  }
  function rebase(my) {                           // my map from the server's snapshot (+ my switches it did not see yet)
    myW = my.w; myTot = { ...my.tot }; myOut = my.out;
    myEvs = {};
    for (const [w, ev] of Object.entries(my.evs || {})) myEvs[w] = ev.map(e => e.slice());
    for (const [gk, g, want] of pendEv) {
      const w = Math.floor(gk / VK.WT), k = gk % VK.WT;
      const ev = myEvs[w] = myEvs[w] || [];
      if (!ev.length || ev[ev.length - 1][0] <= k) ev.push([k, g, want]);
    }
    myS = my.sim ? JSON.parse(JSON.stringify(my.sim)) : null;
    if (myS) myS.ei = Math.min(myS.ei, (myEvs[myW] || []).length);
    prevPos = new Map();
  }
  async function loadWorlds() {
    if (!st || !st.seed || worldsKey === gameKey) return;
    worldsKey = gameKey;
    try {
      const d = await req("/worlds");
      if (!d || !d.worlds) { worldsKey = ""; return; }
      worlds = d.worlds; preps = worlds.map(vkPrep);
      geo = worlds.map(w => w.links.map(lk => {           // the real lengths of the polylines (drawing only)
        const p = lk.pts, segs = [];
        let tot = 0;
        for (let i = 0; i + 3 < p.length; i += 2) { const l = Math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1]); segs.push(l); tot += l; }
        return { segs, tot };
      }));
      if (st.joined && st.phase === "play" && !myS) { const s = await req("?mine=1"); setState(s); }
    } catch { worldsKey = ""; }
  }
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    if (!playing() || !st.joined) {
      try { const s = await req(""); if (!busy) { setState(s); draw(); } } catch {}
    } else if (nowS() - lastSync > 0.45) sync();
    if (st && st.seed && worldsKey !== gameKey) loadWorlds();
    timer = setTimeout(poll, playing() ? 250 : 1000);
  }
  async function sync() {
    if (syncing || !playing() || !st.joined) return;
    syncing = true; lastSync = nowS();
    const events = pendEv.slice();
    try {
      const s = await req("/sync" + (myS ? "" : "?mine=1"), { method: "POST", body: { t: Math.round(gameT() * 1000) / 1000, events } });
      pendEv = pendEv.filter(e => !events.includes(e));
      setState(s); draw();
    } catch {}
    syncing = false;
  }

  // ---------- my map
  function stepTo(gk) {                           // my map on to the global tick gk (worlds one after the other)
    if (!myS || !preps.length) return;
    let n = 0;
    while (myOut == null && myW < nW() && myW * VK.WT + myS.k < gk && n < 600) {
      for (const c of myS.cars) prevPos.set(c[0], c[2]);
      vkStep(preps[myW], myS, myEvs[myW] || (myEvs[myW] = []), thr());
      n++;
      if (myS.out != null) { myOut = myW * VK.WT + myS.out; try { Sound.play("wrong"); } catch {} break; }
      if (myS.k >= VK.WT) {                        // the world is over: on to the next one
        for (const k of ["acc", "ann", "ang", "pas", "pts"]) myTot[k] += myS[k];
        delete myEvs[myW];
        myW++;
        if (myW < nW()) myS = vkNewState(worlds[myW], lim().acc - myTot.acc, lim().ang - myTot.ang);
        prevPos = new Map();
      }
    }
    if (n) lastStepAt = nowS();
    if (myS.acc > seenCrash) { seenCrash = myS.acc; try { Sound.play("wrong"); } catch {} if (navigator.vibrate) try { navigator.vibrate(120); } catch {} }
    if (myS.ang > seenAng) { seenAng = myS.ang; vkHonk(); }
    if (myS.k === 0) { seenCrash = 0; seenAng = 0; }
  }
  function myStats() {
    if (!myS || !myTot) return null;
    const cur = myW < nW() ? myS : { acc: 0, ann: 0, ang: 0, pas: 0, pts: 0 };
    const o = {};
    for (const k of ["acc", "ann", "ang", "pas", "pts"]) o[k] = myTot[k] + cur[k];
    o.score = o.pts - 5 * o.acc - 2 * o.ang;
    return o;
  }
  function tap(g) {
    if (!playing() || !st.joined || !myS || myOut != null || myW >= nW()) return;
    const gk = myW * VK.WT + myS.k + 1;
    const L = myS.lights[g];
    if (!L) return;
    const want = L[0] === 1 ? 0 : 1;
    const ev = myEvs[myW] = myEvs[myW] || [];
    ev.push([myS.k + 1, g, want]);
    pendEv.push([gk, g, want]);
    tapFlash = { g, at: nowS() };
    try { Sound.play("tap"); } catch {}
    drawGroups();
    sync();
  }

  // ---------- drawing the map
  function fit() {
    if (!canvas || !wrap) return;
    const r = wrap.getBoundingClientRect();
    dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(100, Math.floor(r.width)), hh = Math.max(120, Math.floor(r.height));
    if (w !== cw || hh !== ch) { cw = w; ch = hh; canvas.width = w * dpr; canvas.height = hh * dpr; canvas.style.width = w + "px"; canvas.style.height = hh + "px"; }
  }
  function view(W) {                              // map units → pixels: the whole map fits, centred
    const s = Math.min(cw / W.w, ch / W.h);
    return { s, ox: (cw - W.w * s) / 2, oy: (ch - W.h * s) / 2 };
  }
  function at(wi, lk, local) {                    // a point (and the direction) on a link at an integer position
    const W = worlds[wi], L = W.links[lk], g = geo[wi][lk], p = L.pts;
    let d = Math.max(0, Math.min(g.tot, local * g.tot / L.len));
    for (let i = 0; i < g.segs.length; i++) {
      const seg = g.segs[i];
      if (d <= seg || i === g.segs.length - 1) {
        const f = seg ? Math.min(1, d / seg) : 0, x0 = p[2 * i], y0 = p[2 * i + 1], x1 = p[2 * i + 2], y1 = p[2 * i + 3];
        return [x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, Math.atan2(y1 - y0, x1 - x0)];
      }
      d -= seg;
    }
    return [p[0], p[1], 0];
  }
  function onPath(wi, pi, pos) {
    const P = worlds[wi].paths[pi];
    let k = 0;
    while (k + 2 < P.cum.length && P.cum[k + 1] <= pos) k++;
    return at(wi, P.links[k], pos - P.cum[k]);
  }
  function rr(x, y, w, hh, r) { ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, hh, r) : ctx.rect(x, y, w, hh); }
  function drawMap(t) {
    const wi = Math.min(myW, nW() - 1), W = worlds[wi], dark = vkDark();
    const { s, ox, oy } = view(W);
    ctx.fillStyle = dark ? "#1d3524" : "#a9d99a"; ctx.fillRect(0, 0, cw, ch);
    ctx.save(); ctx.translate(ox, oy); ctx.scale(s, s);
    ctx.fillStyle = dark ? "#244a2e" : "#b9e3ab"; ctx.fillRect(0, 0, W.w, W.h);
    // little trees in the corners
    ctx.fillStyle = dark ? "#2f6b3d" : "#7cc46a";
    for (let i = 0; i < 14; i++) { const x = (i * 97 + 31) % W.w, y = (i * 61 + 17) % W.h; ctx.beginPath(); ctx.arc(x, y, 7 + (i % 3) * 2, 0, 7); ctx.fill(); }
    const asphalt = dark ? "#3b4250" : "#5f6673", mark = dark ? "rgba(230,230,230,.55)" : "rgba(255,255,255,.85)";
    ctx.lineCap = "butt"; ctx.lineJoin = "round";
    ctx.strokeStyle = asphalt; ctx.lineWidth = VK.LANE + 1.5;
    for (const L of W.links) { const p = L.pts; ctx.beginPath(); ctx.moveTo(p[0], p[1]); for (let i = 2; i < p.length; i += 2) ctx.lineTo(p[i], p[i + 1]); ctx.stroke(); }
    ctx.fillStyle = asphalt;
    for (const [x0, y0, x1, y1] of W.boxes) ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    if (W.ring) {
      const [cx, cy, R] = W.ring;
      ctx.lineWidth = VK.LANE + 4; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.stroke();
      ctx.fillStyle = dark ? "#2f6b3d" : "#8fd07c"; ctx.beginPath(); ctx.arc(cx, cy, R - VK.LANE / 2 - 2, 0, 7); ctx.fill();
      ctx.fillStyle = dark ? "#3f8a4f" : "#5fb24f"; ctx.beginPath(); ctx.arc(cx, cy, R * 0.35, 0, 7); ctx.fill();
    }
    // dashed lines between the lanes of the straight roads, stop lines at the lights
    ctx.strokeStyle = mark; ctx.lineWidth = 1.2; ctx.setLineDash([7, 7]);
    for (const L of W.links) {
      const p = L.pts;
      if (p.length !== 4) continue;
      const dx = p[2] - p[0], dy = p[3] - p[1], l = Math.hypot(dx, dy) || 1, nx = dy / l * 10, ny = -dx / l * 10;
      ctx.beginPath(); ctx.moveTo(p[0] + nx, p[1] + ny); ctx.lineTo(p[2] + nx, p[3] + ny); ctx.stroke();
    }
    ctx.setLineDash([]);
    const lights = myS ? myS.lights : W.groups.map(() => [0, 0]);
    const stopsDone = new Set();
    W.paths.forEach((P, pi) => {
      for (const [sp, g] of P.stops) {
        let k = 0;
        while (k + 2 < P.cum.length && P.cum[k + 1] <= sp) k++;
        const key = P.links[k];
        if (stopsDone.has(key)) continue;
        stopsDone.add(key);
        const [x, y, a] = at(wi, P.links[k], sp + 3 - P.cum[k]);
        const st0 = g >= 0 ? lights[g][0] : 1;
        ctx.save(); ctx.translate(x, y); ctx.rotate(a);
        ctx.fillStyle = st0 === 1 ? "#40c057" : st0 === 2 ? "#fab005" : "#fa5252";
        ctx.fillRect(0, -VK.LANE / 2 + 1, 3, VK.LANE - 2);
        ctx.restore();
      }
    });
    // the cars
    const frac = myS && myOut == null ? Math.max(0, Math.min(1, (nowS() - lastStepAt) * VK.HZ)) : 1;
    const cars = myS ? myS.cars : [];
    const PEND = myS ? myS.pend : [];
    for (const c of cars) {
      const [id, pi, pos, kind, , mood, wreck, mv] = c;
      const p0 = prevPos.has(id) ? prevPos.get(id) : pos;
      const ip = wreck ? pos : p0 + (pos - p0) * frac;
      const len = VK.KLEN[kind], mid = onPath(wi, pi, ip - len / 2), [x, y, a] = mid;
      ctx.save(); ctx.translate(x, y); ctx.rotate(a);
      const wd = kind === 2 ? 5 : kind === 1 ? 11 : 10;
      ctx.fillStyle = "rgba(0,0,0,.25)"; rr(-len / 2 + 1, -wd / 2 + 1.5, len, wd, 3); ctx.fill();
      let body = kind === 1 ? "#f59f00" : kind === 3 ? "#f8f9fa" : kind === 2 ? "#12b886" : VK_COLORS[id % VK_COLORS.length];
      if (wreck) body = "#868e96";
      ctx.fillStyle = body; rr(-len / 2, -wd / 2, len, wd, kind === 2 ? 2.5 : 3); ctx.fill();
      if (kind === 2) { ctx.fillStyle = "#343a40"; ctx.beginPath(); ctx.arc(0, 0, 2.6, 0, 7); ctx.fill(); }
      else {
        ctx.fillStyle = "rgba(30,40,60,.55)";                         // the windscreen
        ctx.fillRect(len / 2 - 6.5, -wd / 2 + 1.5, 3, wd - 3);
        if (kind === 1) { ctx.fillStyle = "rgba(30,40,60,.35)"; for (let k = 0; k < 4; k++) ctx.fillRect(-len / 2 + 3 + k * 5.5, -wd / 2 + 1, 3.5, wd - 2); }
        if (kind === 3) {
          ctx.fillStyle = "#e03131"; ctx.fillRect(-3, -1, 6, 2); ctx.fillRect(-1, -3, 2, 6);
          if (Math.floor(t * 4) % 2 === 0) { ctx.fillStyle = "#339af0"; ctx.fillRect(len / 2 - 9, -wd / 2, 2.5, wd); }
        }
      }
      ctx.restore();
      if (wreck) {
        ctx.font = "16px system-ui, 'Apple Color Emoji', 'Noto Color Emoji', sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText("💥", x, y);
      } else if (mood) {
        ctx.font = (mood === 3 ? 15 : 12) + "px system-ui, 'Apple Color Emoji', 'Noto Color Emoji', sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(VK_MOODS[mood], x, y - 12);
      }
      void mv;
    }
    // cars queuing outside the map: a badge at the entry
    PEND.forEach((q, e) => {
      if (!q.length) return;
      const [x, y] = at(wi, W.entries[e], 6);
      const worst = Math.max(...q.map(c => c[3]));
      ctx.fillStyle = worst >= 3 ? "#e03131" : "rgba(15,23,42,.8)";
      rr(x - 15, y - 9, 30, 18, 9); ctx.fill();
      ctx.fillStyle = "#fff"; ctx.font = "700 11px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText("+" + q.length, x, y + 0.5);
    });
    ctx.restore();
    // the light heads (fixed size on the screen – big enough to tap)
    const R = vkHeadR();
    W.groups.forEach((G, g) => {
      const L = lights[g] || [0, 0];
      for (const [hx, hy] of G.heads) {
        const x = ox + hx * s, y = oy + hy * s;
        ctx.fillStyle = dark ? "#0b0f17" : "#212529";
        ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fill();
        const col = L[0] === 1 ? "#51cf66" : L[0] === 2 ? "#fcc419" : "#ff6b6b";
        ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, y, R * 0.72, 0, 7); ctx.fill();
        if (tapFlash && tapFlash.g === g && nowS() - tapFlash.at < 0.3) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, R + 3, 0, 7); ctx.stroke(); }
        ctx.fillStyle = "#111"; ctx.font = "900 " + Math.round(R * 0.8) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(String(g + 1), x, y + 1);
      }
    });
  }
  const vkHeadR = () => 23;
  function headAt(px, py) {                        // the light group under a tap (or null)
    if (!worlds || !myS) return null;
    const W = worlds[Math.min(myW, nW() - 1)], { s, ox, oy } = view(W), R = vkHeadR() + 6;
    let best = null, bd = R * R;
    W.groups.forEach((G, g) => { for (const [hx, hy] of G.heads) { const dx = ox + hx * s - px, dy = oy + hy * s - py, d = dx * dx + dy * dy; if (d <= bd) { bd = d; best = g; } } });
    return best;
  }
  function banner(lines, sub) {                    // a box in the middle of the map
    const fs = Math.max(15, Math.min(24, cw * 0.06)), bw = Math.min(cw - 24, fs * 16), bh = fs * (sub ? 3.4 : 2.2), bx = (cw - bw) / 2, by = ch * 0.38 - bh / 2;
    ctx.fillStyle = vkDark() ? "rgba(30,41,59,.94)" : "rgba(255,255,255,.95)"; ctx.strokeStyle = "#f59f00"; ctx.lineWidth = 3;
    rr(bx, by, bw, bh, 14); ctx.fill(); ctx.stroke();
    ctx.fillStyle = vkDark() ? "#f8fafc" : "#1f2937"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.font = "900 " + fs + "px system-ui, sans-serif"; ctx.fillText(lines, cw / 2, by + (sub ? bh * 0.33 : bh / 2), bw - 14);
    if (sub) { ctx.font = "700 " + Math.round(fs * 0.72) + "px system-ui, sans-serif"; ctx.fillText(sub, cw / 2, by + bh * 0.7, bw - 14); }
  }
  function frame() {
    if (!alive || !box.isConnected) return stop();
    raf = requestAnimationFrame(frame);
    if (!canvas || !playing() || !worlds) return;
    fit();
    const t = gameT();
    const gk = Math.floor(Math.max(0, t) * VK.HZ);
    if (st.joined && myS) stepTo(gk);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    drawMap(t);
    const wi = Math.min(myW, nW() - 1), local = gk - wi * VK.WT;
    if (t < 0) banner(String(Math.ceil(-t)), I18N.tr(T("World {0}: {1}")).replace("{0}", wi + 1).replace("{1}", I18N.tr(worlds[wi].name)));
    else if (myOut != null) banner("💥 " + I18N.tr(T("Out!")), I18N.tr(T("You can watch the others.")));
    else if (myW >= nW()) banner("🏁 " + I18N.tr(T("All worlds done!")), I18N.tr(T("Waiting for the others …")));
    else if (local < VK.INTRO * VK.HZ) banner(I18N.tr(T("World {0}: {1}")).replace("{0}", wi + 1).replace("{1}", I18N.tr(worlds[wi].name)),
      I18N.tr(T("Set the lights – the cars come in {0} s")).replace("{0}", Math.max(1, Math.ceil(VK.INTRO - local / VK.HZ))));
    drawStats(gk);
    drawGroups();
  }
  // ---------- the live bar: my stats and everybody else's
  let statsSig = "";
  function drawStats(gk) {
    if (!statEl || !barEl) return;
    const ms = st.joined ? myStats() : null;
    const wi = Math.min(st.joined ? myW : Math.floor(Math.max(0, gk) / VK.WT), nW() - 1);
    const left = Math.max(0, Math.ceil(((wi + 1) * VK.WT - gk) / VK.HZ));
    const L = lim();
    const mine = ms ? ["💥" + ms.acc + "/" + L.acc, "😠" + ms.ann, "😡" + ms.ang + "/" + L.ang, "🚗" + ms.pas, "⭐" + ms.score].join("  ") : "";
    const head = "🌍 " + (wi + 1) + "/" + nW() + "  ⏱ " + Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
    const others = st.players.filter(p => p.id !== myId);
    const sig = JSON.stringify([mine, head, others.map(p => [p.acc, p.ann, p.ang, p.pas, p.out, p.w])]);
    if (sig === statsSig) return;
    statsSig = sig;
    statEl.replaceChildren(h("span.vk-world", head), h("span.vk-mine", mine));
    barEl.replaceChildren(...others.map(p => h("div.vk-chip" + (p.out != null ? ".out" : ""),
      p.bot ? h("span.vk-av", p.emoji || "🤖") : h("span.vk-av", avatarSvg(p.avatar || {}, 20)),
      C(p.name, "strong.vk-nm"),
      h("span.vk-nums", p.out != null ? "💥 " + I18N.tr(T("Out!")) : "💥" + p.acc + "\u2009😠" + p.ann + "\u2009😡" + p.ang + "\u2009🚗" + p.pas))));
  }
  let groupsSig = "";
  function drawGroups() {
    if (!groupsEl || !worlds) return;
    const wi = Math.min(myW, nW() - 1), W = worlds[wi];
    const lights = myS ? myS.lights : W.groups.map(() => [0, 0]);
    const off = !st.joined || myOut != null || myW >= nW();
    const sig = JSON.stringify([wi, lights.map(l => l[0]), off]);
    if (sig === groupsSig) return;
    groupsSig = sig;
    groupsEl.replaceChildren(...W.groups.map((G, g) => {
      const s0 = lights[g][0];
      return h("button.vk-grp" + (s0 === 1 ? ".green" : s0 === 2 ? ".amber" : ".red"), { type: "button", disabled: off,
        onpointerdown: e => { e.preventDefault(); tap(g); }, onclick: e => { if (e.detail === 0) tap(g); } },
        h("span.vk-dot"), h("b", String(g + 1)), h("span.vk-lbl", G.label));
    }));
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, st.players.map(p => [p.id, p.place]), st.phase === "lobby" ? st.players.length : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    canvas = null; groupsEl = null; statEl = null; barEl = null; statsSig = ""; groupsSig = "";
    if (!st) return show(h("section.card.center", h("div.big-ic", VK_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    const menu = gameMenu({ rules: () => vkRulesView(st.rules, st.coins_on ? st.rewards : null, st.limits),
      invite: !st.solo && !me.guest && st.status !== "done" ? "verkehr" : null,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", VK_ICON, " ", vkName())));
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))) : null;
    if (st.phase === "done") return show(head, result());
    if (st.phase === "lobby") {
      const info = h("p.small.muted", "🌍 ", st.worlds_names.map(n => I18N.tr(n)).join(" → "));
      if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), lobbySeats(), info, host);
      return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
        h("p.muted", T("Everybody joins on their own device.")), lobbySeats(), info,
        st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", vkCoins(st.rewards))) : null), host);
    }
    canvas = h("canvas.vk-canvas");
    ctx = canvas.getContext("2d");
    wrap = h("div.vk-wrap", canvas);
    canvas.addEventListener("pointerdown", e => {
      const r = canvas.getBoundingClientRect(), g = headAt(e.clientX - r.left, e.clientY - r.top);
      if (g != null) { e.preventDefault(); tap(g); }
    });
    statEl = h("div.vk-stats");
    barEl = h("div.vk-others");
    groupsEl = st.joined ? h("div.vk-groups") : h("p.muted.center.small", T("The game has already started"));
    show(close, head, barEl, statEl, wrap, groupsEl, host);
    cw = ch = 0;
  }
  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobbySeats() {
    const free = Array.from({ length: st.bots || 0 }, () => h("div.dm-seat", h("span.bot-av", { style: { width: "30px", height: "30px", fontSize: "18px" } }, "🤖"), h("span.small.muted", T("Bot"))));
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), seatIcon(p, 30), C(p.name, "strong.small.dm-name"))), ...free);
  }
  function result() {
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99));
    const m = st.players.find(p => p.id === myId) || {};
    if (!cheered && ((m.place === 1 && st.complete && st.players.length > 1) || m.record)) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    const winners = ranked.filter(p => p.place === 1).map(p => p.name).join(" & ");
    const again = st.solo && st.host === me.id ? h("button.btn", { onclick: async () => {
      try { await api("community/verkehr/start", { method: "POST", body: { solo: true } }); setState(await req("")); draw(true); } catch (e) { toast(e.message, "bad"); }
    } }, "🔄 ", T("Play again")) : null;
    const line = p => "🚗" + p.pas + " 💥" + p.acc + " 😠" + p.ann + " 😡" + p.ang;
    return h("section.card.center.vk-result",
      st.players.length > 1 ? h("h2", "🏆 ", C(winners)) : h("h2", VK_ICON, " ", (m.score || 0) + " ⭐"),
      st.players.length > 1 ? null : h("p", line(m)),
      m.record ? h("p.vk-record", "🎉 ", T("New personal best!")) : null,
      st.joined && st.best ? h("p.small.muted", "🏆 ", I18N.tr(T("Your best: {0}")).replace("{0}", (st.best || 0) + " ⭐")) : null,
      st.players.length > 1 ? h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".vk-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 30),
        h("span.grow", C(p.name, "strong"), h("br"), h("span.small.muted", line(p) + (p.out != null ? " · " + I18N.tr(T("Out!")) : ""))),
        h("span", (p.score || 0) + " ⭐"), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))) : null,
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on || st.players.length < 2 ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", again, h("button.btn" + (again ? ".ghost" : ""), { onclick: back }, T("Back"))));
  }
  (async () => { try { setState(await req("?mine=1")); } catch {} draw(true); await loadWorlds(); poll(); })();
  raf = requestAnimationFrame(frame);
  void rebasing;
}

async function verkehrView() {
  const box = h("div.vk-live");
  screen("games", box);
  vkLive(box, S.profile, () => go("games"));
}

async function verkehrFamilyCard() {
  const c = S.me && S.me.community, g = c && c.verkehr;
  return h("section.card.quiz-card", h("h2", VK_ICON, " ", vkName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("verkehr") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Switch the traffic lights of your own crossing – no accidents, no angry drivers. Everybody gets the same streets and cars; who keeps the traffic flowing best wins.")),
         gameStartRow(() => vkStartDialog(true, () => go("verkehr")), () => vkStartDialog(false, () => go("verkehr")))]);
}
