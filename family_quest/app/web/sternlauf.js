// «Star Runner» (Sternschnuppen-Lauf) – a live endless runner (familyquest/sternlauf.py): at night the lantern of the
// village went out; the children run as forest messengers along a forest path with three lanes and catch the falling
// star sparks to light it again. Swipe left / right = change the lane, up = jump (logs, puddles), down = duck (low
// branches); rocks and stumps block a lane. Arrow keys / WASD / space on a computer, four buttons for everybody.
// Everybody runs the same course (from the server's seed, made here with the same generator) at the same time; the
// others run along as translucent ghosts (from the inputs the server relays). The app simulates the run for smooth
// 60 fps and reports only its inputs – the server replays them and decides hits and sparks itself.
// sternlaufLive(box, me, back) runs a table (family or alone), sternlaufStartDialog(solo, onStarted) sets the rules.
// Uses botPicker() from cards.js, withoutBots() and guestInvite() from community.js, gameMenu() from shared/ui.js.
"use strict";

const SR_ICON = "🌠";
const srName = () => I18N.tr(T("Star Runner"));
const srCoins = list => list.join(" / ") + " 🪙";
// the course and the rules – the same numbers as in sternlauf.py
const SR = { V0: 9, VMAX: 18, ACC: 0.07, FIRST: 3, JT: 0.65, AIR0: 0.07, DT: 0.75, INVULN: 1, SPARK_PTS: 10, MIN_STEP: 0.04 };
SR.T1 = (SR.VMAX - SR.V0) / SR.ACC;
SR.D1 = SR.V0 * SR.T1 + SR.ACC * SR.T1 * SR.T1 / 2;
const SR_LOG = 0, SR_PUDDLE = 1, SR_BRANCH = 2, SR_ROCK = 3, SR_SPARK = 4, SR_SKY = 5;
const SR_GHOST_DELAY = 0.45;
const SR_GHOST_SCALE = 0.42;                     // the ghosts at less than half the size of your own runner                    // the others are drawn this much later (their inputs need to arrive)
const SR_VIEW = 60;                             // metres of path ahead on the screen
const SR_COLORS = ["#f2545b", "#2f8fdd", "#33a852", "#f2b705", "#8b5cf6", "#14b8a6", "#ec4899", "#f97316"];

function srDist(t) { return t <= 0 ? 0 : t < SR.T1 ? SR.V0 * t + SR.ACC * t * t / 2 : SR.D1 + SR.VMAX * (t - SR.T1); }
function srTimeAt(x) { return x <= 0 ? 0 : x < SR.D1 ? (-SR.V0 + Math.sqrt(SR.V0 * SR.V0 + 2 * SR.ACC * x)) / SR.ACC : SR.T1 + (x - SR.D1) / SR.VMAX; }
function srSpeedAt(x) { return Math.min(SR.VMAX, Math.sqrt(SR.V0 * SR.V0 + 2 * SR.ACC * x)); }
function srRand(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), a | 1) >>> 0;
    t = (((t + Math.imul(t ^ (t >>> 7), t | 61)) >>> 0) ^ t) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
// everything on the path up to this distance: [x, lane 0–2, kind, game time when it passes]
function srCourse(seed, upto) {
  const rnd = srRand(seed), out = [];
  const add = (x, lane, kind) => out.push([x, lane, kind, srTimeAt(x)]);
  let x = SR.V0 * SR.FIRST;
  while (x <= upto) {
    const v = srSpeedAt(x), prog = (v - SR.V0) / (SR.VMAX - SR.V0);
    const r = rnd(), a = rnd(), b = rnd(), c = rnd();
    const lane = Math.floor(a * 3);
    if (r < 0.34) add(x, lane, Math.floor(b * 4));
    else if (r < 0.58) {
      for (let k = 0; k < 3; k++) if (k !== lane) add(x, k, SR_ROCK);
      if (c < 0.5 * prog) add(x, lane, b < 0.5 ? SR_LOG : SR_BRANCH);
    } else if (r < 0.8) {
      const k = b < 0.55 ? SR_LOG : SR_BRANCH;
      for (let j = 0; j < 3; j++) add(x, j, k);
      if (k === SR_LOG && c < 0.6) add(x, lane, SR_SKY);
    } else {
      const kinds = b < 0.33 ? [SR_ROCK, SR_LOG, SR_BRANCH] : b < 0.66 ? [SR_LOG, SR_BRANCH, SR_ROCK] : [SR_BRANCH, SR_ROCK, SR_LOG];
      for (let j = 0; j < 3; j++) add(x, (lane + j) % 3, kinds[j]);
    }
    const gap = v * (1.05 - 0.25 * prog + rnd() * (0.9 - 0.4 * prog));
    if (c > 0.35) {
      const sl = Math.floor(rnd() * 3), n = 3 + Math.floor(rnd() * 3), step = gap / (n + 2);
      for (let k = 1; k <= n; k++) add(x + step * (k + 0.5), sl, SR_SPARK);
    }
    x = x + gap;
  }
  return out;
}
// one runner: the inputs on the state {lane, lj, ld} – the same rules as on the server
function srApply(s, t, c) {
  if (c === "l") s.lane = Math.max(0, s.lane - 1);
  else if (c === "r") s.lane = Math.min(2, s.lane + 1);
  else if (c === "u") { if (!(s.lj > s.ld && t - s.lj < SR.JT)) s.lj = t; }
  else if (c === "d") s.ld = t;
}
function srStateAt(base, ev, t) {
  const s = { ...base };
  for (const [te, c] of ev) { if (te > t) break; srApply(s, te, c); }
  return s;
}
function srMeets(s, t, lane, kind) {
  if (s.lane !== lane) return null;
  const air = s.lj > s.ld && t - s.lj >= SR.AIR0 && t - s.lj <= SR.JT - SR.AIR0;
  const duck = s.ld > s.lj && t - s.ld >= 0 && t - s.ld <= SR.DT;
  if (kind === SR_SPARK) return "spark";
  if (kind === SR_SKY) return air ? "spark" : null;
  if (kind === SR_ROCK) return "hit";
  if (kind === SR_LOG || kind === SR_PUDDLE) return air ? null : "hit";
  if (kind === SR_BRANCH) return duck ? null : "hit";
  return null;
}
// how a runner looks at game time t: the lane (sliding), the height of the jump (m), ducking (0…1)
function srPose(base, ev, t) {
  const s = { ...base };
  let from = s.lane, at = -99;
  for (const [te, c] of ev) {
    if (te > t) break;
    const before = s.lane;
    srApply(s, te, c);
    if (s.lane !== before) { from = before; at = te; }
  }
  const k = Math.min(1, (t - at) / 0.14);
  const lanePos = from + (s.lane - from) * (k < 1 ? k * (2 - k) : 1);
  let hgt = 0, duck = 0;
  if (s.lj > s.ld && t - s.lj < SR.JT) { const q = (t - s.lj) / SR.JT; hgt = 4 * 1.3 * q * (1 - q); }
  if (s.ld > s.lj && t - s.ld < SR.DT) { const q = (t - s.ld) / SR.DT; duck = q < 0.12 ? q / 0.12 : q > 0.85 ? (1 - q) / 0.15 : 1; }
  return { lane: s.lane, lanePos, hgt, duck };
}
const srPoints = (dist, sparks) => Math.floor(dist) + SR.SPARK_PTS * (sparks || 0);

function sternlaufRulesView(r, rewards) {
  r = r || {};
  const items = [
    T("The lantern of the village went out! Run along the forest path and catch the falling star sparks ✨ to light it again."),
    T("Swipe left or right to change the lane, up to jump (logs, puddles), down to duck (low branches). Rocks and stumps block a lane – go around them."),
    T("On a computer: arrow keys or W A S D (space jumps). The four buttons below the path work too."),
    I18N.tr(T("Everything you hit costs a life (then you blink for a moment). You have {0} lives.")).replace("{0}", r.lives || 3),
    T("Everybody runs the same course at the same time – the others run along as ghosts, you never bump into them. It gets faster and faster."),
    I18N.tr(T("Points: every metre 1, every spark {0}. The run ends when everybody is out or after {1} minutes.")).replace("{0}", SR.SPARK_PTS).replace("{1}", r.minutes || 3),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", srCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function sternlaufStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/sternlauf/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(r.bots ?? 0, [0, 1, 2, 3, 4, 5, 6, 7].map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const lives = sel(r.lives || 3, [1, 3, 5].map(n => [n, "❤️ " + n]));
  const minutes = sel(r.minutes || 3, [2, 3, 5].map(n => [n, "⏱ " + n + " min"]));
  const picker = botPicker(1400);
  const speed = picker.el.querySelector(".bot-speed");             // bots run by their level – no reaction time here
  if (speed) speed.remove();
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", srCoins(rw)), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", SR_ICON, " ", srName(), solo ? " – " + I18N.tr(T("Alone")) : ""),
    h("p.small.muted", T("Run along the forest path, dodge logs, branches and rocks and catch the star sparks – everybody runs the same course at the same time.")),
    h("div.grid2", h("label.field", solo ? T("Practice bots") : T("Bots"), bots), h("label.field", T("Bots play"), level)),
    h("div.grid2", h("label.field", T("Lives"), lives), h("label.field", T("Time"), minutes)),
    solo ? null : h("p.small.muted", T("1 to 8 players: the family joins on their own devices, guests via QR code.")),
    picker.el,
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: +bots.value, level: level.value, lives: +lives.value, minutes: +minutes.value, bot_ids: picker.ids() };
      try { await api("community/sternlauf/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("sternlauf", bots, level, picker.el);          // parent area › Games: without bots
}

function sternlaufLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, raf = 0, syncing = false, lastSync = 0;
  let canvas = null, ctx = null, wrap = null, hud = null, board = null, cw = 0, ch = 0, dpr = 1;
  let offset = null, bestRtt = 1e9;               // server clock − performance clock (seconds)
  let course = [], courseSeed = null, courseUpto = 0, gameKey = "";
  // my runner: the inputs (all of this game, the same base as the server's), what is not sent yet, what the app decided
  let myBase = { lane: 1, lj: -99, ld: -99 }, myEv = [], pend = [], locNext = 0, locHits = new Map(), locGot = new Set(), srv = null;
  let flash = 0, pops = [];
  const ghosts = {};                              // id → {base, ev} merged from the server's answers
  const imgs = {};
  const myId = String(me.id);
  box.classList.add("sr-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => {
    alive = false; clearTimeout(timer); cancelAnimationFrame(raf); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open");
    window.removeEventListener("keydown", onKey);
  };
  window.addEventListener("hashchange", stop, { once: true });
  const nowS = () => performance.now() / 1000;
  const gameT = () => (st && offset != null ? nowS() + offset - st.t0 : -9);
  const playing = () => st && st.phase === "play" && st.status !== "done";
  const lives0 = () => (st && st.lives0) || 3;
  const limit = () => (st && st.limit) || 180;
  const dark = () => { const t = document.documentElement.dataset.theme; return t === "dark" || (t !== "light" && matchMedia("(prefers-color-scheme: dark)").matches); };

  // ---------- what counts for me: the server's settled part + the app's own part after it
  const srvNext = () => (srv ? srv.next : 0);
  const hitTimes = () => [...((srv && srv.hits) || []).map(x => x[1]), ...[...locHits].filter(([i]) => i >= srvNext()).map(([, t]) => t)];
  const myLives = () => Math.max(0, lives0() - hitTimes().length);
  const mySparks = () => ((srv && srv.sparks) || 0) + [...locGot].filter(i => i >= srvNext()).length;
  const myOut = () => {
    if (srv && srv.out != null) return srv.out;
    if (myLives() > 0) return null;
    const ts = hitTimes();
    return ts.length ? Math.max(...ts) : null;
  };

  function clock(s, t1, t2) {                    // the server's clock: the answer with the shortest way counts
    if (!s || typeof s.now !== "number") return;
    const rtt = t2 - t1;
    if (rtt <= bestRtt * 1.15 || offset == null) { bestRtt = Math.min(bestRtt, rtt); offset = s.now - (t1 + t2) / 2; }
  }
  const req = async (path, opts) => {
    const t1 = nowS();
    const s = await api("community/sternlauf" + path, opts);
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
  function adoptMine(mine, reset) {               // the server's view of my runner
    srv = mine ? { next: mine.next || 0, hits: mine.hits || [], sparks: mine.sparks || 0, out: mine.out, h: mine.h || 0 } : null;
    if (!mine) return;
    if (reset) {                                  // rebuild my inputs from the server (a reload, or inputs it did not take)
      myBase = { ...mine.base }; myEv = (mine.ev || []).map(e => [e[0], e[1]]).concat(pend);
      locNext = srv.next; locHits = new Map(); locGot = new Set();
    }
  }
  function setState(s, sent) {
    if (s && !Array.isArray(s.players)) s = null;
    st = s;
    if (!st || !st.seed) return;
    const key = st.game + ":" + st.seed;
    const mine = st.players.find(p => p.id === myId);
    if (key !== gameKey) {                         // a new game (or a reload in the middle): my runner from the server
      gameKey = key; pend = []; cheered = false; flash = 0; pops = [];
      Object.keys(ghosts).forEach(k => delete ghosts[k]);
      adoptMine(mine, true);
    } else adoptMine(mine, sent != null && typeof st.taken === "number" && st.taken < sent);
    for (const p of st.players) {                  // the ghosts: the inputs the server relays (since its base state)
      if (p.id !== myId && p.base) ghosts[p.id] = { base: p.base, ev: (p.ev || []).map(e => [e[0], e[1]]) };
    }
  }
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    if (!playing() || !st.joined) {
      try { const s = await req(""); if (!busy) { setState(s); draw(); } } catch {}
    } else if (nowS() - lastSync > 0.24) sync();
    timer = setTimeout(poll, playing() ? 250 : 1000);
  }
  async function sync() {                         // my inputs to the server – everybody's progress back
    if (syncing || !playing() || !st.joined) return;
    syncing = true; lastSync = nowS();
    const inputs = pend.slice();
    try {
      const s = await req("/sync", { method: "POST", body: { inputs } });
      pend = pend.filter(x => !inputs.includes(x));
      setState(s, inputs.length); draw(); board && drawBoard();
    } catch {}
    syncing = false;
  }

  // ---------- my inputs
  function input(c) {
    if (!playing() || !st.joined || myOut() != null) return;
    let t = gameT();
    if (t < 0 || t > limit()) return;
    t = Math.round(t * 1000) / 1000;
    const last = myEv.length ? myEv[myEv.length - 1][0] : -9;
    if (t < last + SR.MIN_STEP + 0.001) t = Math.round((last + SR.MIN_STEP + 0.005) * 1000) / 1000;
    const e = [t, c];
    myEv.push(e); pend.push(e);
    if (c === "u") { try { Sound.play("tap"); } catch {} }
    sync();
  }
  const KEYS = { ArrowLeft: "l", KeyA: "l", ArrowRight: "r", KeyD: "r", ArrowUp: "u", KeyW: "u", Space: "u", ArrowDown: "d", KeyS: "d" };
  function onKey(e) {
    if (!alive || !box.isConnected || !canvas) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || "")) return;
    const c = KEYS[e.code];
    if (c) { e.preventDefault(); if (!e.repeat) input(c); }
  }
  window.addEventListener("keydown", onKey);
  function swipes(el) {                           // a swipe counts as soon as it is long enough (no waiting for the release)
    let sx = 0, sy = 0, on = false;
    el.addEventListener("pointerdown", e => { on = true; sx = e.clientX; sy = e.clientY; try { el.setPointerCapture(e.pointerId); } catch {} e.preventDefault(); });
    el.addEventListener("pointermove", e => {
      if (!on) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 26) return;
      on = false;
      input(Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? "l" : "r") : (dy < 0 ? "u" : "d"));
    });
    const up = () => { on = false; };
    el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  }

  // ---------- the course: what passed me (the app decides at once – the server decides the same a moment later)
  function ensureCourse(t) {
    const need = srDist(t) + SR_VIEW + 20;
    if (courseSeed !== st.seed || courseUpto < need) { courseSeed = st.seed; courseUpto = need + 400; course = srCourse(st.seed, courseUpto); }
  }
  function resolve(t) {
    if (!st.joined) return;
    t = Math.min(t, limit());
    while (locNext < course.length && course[locNext][3] <= t && myOut() == null) {
      const [, lane, kind, tr] = course[locNext], i = locNext++;
      if (i < srvNext()) continue;
      const what = srMeets(srStateAt(myBase, myEv, tr), tr, lane, kind);
      if (what === "spark") {
        locGot.add(i); pops.push({ t: tr, lane });
        try { Sound.play("right"); } catch {}
      } else if (what === "hit") {
        const ts = hitTimes();
        if (ts.length && tr < Math.max(...ts) + SR.INVULN) continue;
        locHits.set(i, tr); flash = tr;
        try { Sound.play("wrong"); } catch {}
        if (navigator.vibrate) try { navigator.vibrate(myLives() <= 0 ? [80, 60, 160] : 60); } catch {}
        sync();
      }
    }
  }

  // ---------- drawing
  function avatarImg(p) {
    if (p.bot) return null;
    if (imgs[p.id] !== undefined) return imgs[p.id];
    imgs[p.id] = null;
    try {
      const a = p.avatar || {}, items = { ...(a.items || {}) };
      delete items.pet; delete items.background;
      const svg = avatarSvg({ ...a, items, pet: undefined }, 120, { transparent: true }).querySelector("svg");
      svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const img = new Image();
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(svg));
      imgs[p.id] = img;
    } catch {}
    return imgs[p.id];
  }
  function fit() {
    if (!canvas || !wrap) return;
    const r = wrap.getBoundingClientRect();
    dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(100, Math.floor(r.width)), hh = Math.max(120, Math.floor(r.height));
    if (w !== cw || hh !== ch) { cw = w; ch = hh; canvas.width = w * dpr; canvas.height = hh * dpr; canvas.style.width = w + "px"; canvas.style.height = hh + "px"; }
  }
  // the camera: depth z (m ahead of me) → scale; lanes 0–2 (and beyond for the forest)
  const F = 6;
  let yh = 0, y0 = 0, LW = 0;
  const sc = z => F / (F + z);
  const Y = z => yh + (y0 - yh) * sc(z);
  const X = (lane, z) => cw / 2 + (lane - 1) * LW * sc(z);
  const U = z => LW * 0.62 * sc(z);                // one metre up, in pixels
  function star4(x, y, r, color, glow) {
    ctx.save();
    if (glow) { const g = ctx.createRadialGradient(x, y, 0, x, y, r * 2.4); g.addColorStop(0, "rgba(255,226,120,.75)"); g.addColorStop(1, "rgba(255,226,120,0)"); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 2.4, 0, 7); ctx.fill(); }
    ctx.fillStyle = color; ctx.beginPath();
    for (let k = 0; k < 8; k++) { const a = k * Math.PI / 4 - Math.PI / 2, rr = k % 2 ? r * 0.38 : r; ctx[k ? "lineTo" : "moveTo"](x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  function scenery(d, t, night, glow) {
    // the sky with stars, a falling star now and then, the village with its lantern on the horizon
    const g = ctx.createLinearGradient(0, 0, 0, yh);
    if (night) { g.addColorStop(0, "#060a1f"); g.addColorStop(1, "#27235a"); } else { g.addColorStop(0, "#3554a5"); g.addColorStop(1, "#b9a8e6"); }
    ctx.fillStyle = g; ctx.fillRect(0, 0, cw, yh + 2);
    const rnd = srRand(7);
    for (let k = 0; k < 46; k++) {
      const sx = rnd() * cw, sy = rnd() * yh * 0.92, tw = 0.5 + 0.5 * Math.sin(t * 2 + k);
      ctx.fillStyle = `rgba(255,255,230,${(night ? 0.45 : 0.3) + 0.4 * tw})`;
      ctx.fillRect(sx, sy, k % 7 ? 1.6 : 2.6, k % 7 ? 1.6 : 2.6);
    }
    const fs = (t * 0.37) % 1;                    // a falling star
    if (fs < 0.25) {
      const p = fs / 0.25, fx = cw * (0.15 + 0.7 * ((Math.floor(t * 0.37) * 0.618) % 1)), fy = yh * 0.12;
      const x2 = fx + p * cw * 0.25, y2 = fy + p * yh * 0.45;
      const lg = ctx.createLinearGradient(x2 - cw * 0.08, y2 - yh * 0.15, x2, y2);
      lg.addColorStop(0, "rgba(255,240,180,0)"); lg.addColorStop(1, "rgba(255,240,180,.95)");
      ctx.strokeStyle = lg; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x2 - cw * 0.08, y2 - yh * 0.15); ctx.lineTo(x2, y2); ctx.stroke();
      star4(x2, y2, 4, "#fff7c2", true);
    }
    // the village: little houses, a tower with the lantern – the more sparks, the brighter
    const vx = cw / 2, vy = yh, s = Math.max(0.6, Math.min(1.2, cw / 420));
    const lg = ctx.createRadialGradient(vx, vy - 34 * s, 0, vx, vy - 34 * s, (26 + 60 * glow) * s);
    lg.addColorStop(0, `rgba(255,214,102,${0.35 + 0.55 * glow})`); lg.addColorStop(1, "rgba(255,214,102,0)");
    ctx.fillStyle = lg; ctx.beginPath(); ctx.arc(vx, vy - 34 * s, (26 + 60 * glow) * s, 0, 7); ctx.fill();
    ctx.fillStyle = night ? "#141432" : "#4a4782";
    [[-58, 14, 16], [-38, 18, 20], [30, 16, 18], [52, 12, 14], [-16, 12, 12]].forEach(([dx, w, hh]) => {
      ctx.beginPath(); ctx.moveTo(vx + (dx - w / 2) * s, vy); ctx.lineTo(vx + (dx - w / 2) * s, vy - hh * s); ctx.lineTo(vx + dx * s, vy - (hh + 8) * s);
      ctx.lineTo(vx + (dx + w / 2) * s, vy - hh * s); ctx.lineTo(vx + (dx + w / 2) * s, vy); ctx.fill();
    });
    ctx.fillRect(vx - 6 * s, vy - 30 * s, 12 * s, 30 * s);
    ctx.beginPath(); ctx.moveTo(vx - 9 * s, vy - 30 * s); ctx.lineTo(vx, vy - 44 * s); ctx.lineTo(vx + 9 * s, vy - 30 * s); ctx.fill();
    ctx.fillStyle = `rgba(255,${200 + 40 * glow},${90 + 60 * glow},${0.45 + 0.55 * glow})`;
    ctx.beginPath(); ctx.arc(vx, vy - 34 * s, 4 * s, 0, 7); ctx.fill();
    // the forest floor
    const fg = ctx.createLinearGradient(0, yh, 0, ch);
    if (night) { fg.addColorStop(0, "#0d2419"); fg.addColorStop(1, "#163d27"); } else { fg.addColorStop(0, "#2a5a3b"); fg.addColorStop(1, "#3f8a4f"); }
    ctx.fillStyle = fg; ctx.fillRect(0, yh, cw, ch - yh);
    // the path (three lanes) and its stripes
    const zf = SR_VIEW, zn = -F * 0.6;
    ctx.fillStyle = night ? "#4a3a2a" : "#9a7650";
    ctx.beginPath(); ctx.moveTo(X(-0.55, zf), Y(zf)); ctx.lineTo(X(2.55, zf), Y(zf)); ctx.lineTo(X(2.55, zn), Y(zn)); ctx.lineTo(X(-0.55, zn), Y(zn)); ctx.fill();
    ctx.fillStyle = night ? "rgba(255,240,200,.12)" : "rgba(255,255,255,.22)";
    const off = ((d % 5) + 5) % 5;
    for (let z = -off - 1; z < zf; z += 5) {
      for (const b of [0.5, 1.5]) {
        const za = Math.max(zn, z), zb = Math.min(zf, z + 2.2);
        if (zb <= za) continue;
        const w0 = LW * 0.035;
        ctx.beginPath(); ctx.moveTo(X(b, za) - w0 * sc(za), Y(za)); ctx.lineTo(X(b, za) + w0 * sc(za), Y(za));
        ctx.lineTo(X(b, zb) + w0 * sc(zb), Y(zb)); ctx.lineTo(X(b, zb) - w0 * sc(zb), Y(zb)); ctx.fill();
      }
    }
  }
  function tree(z, side, k, night) {
    const lane = side < 0 ? -1.4 - (k % 3) * 0.55 : 3.4 + (k % 3) * 0.55, x = X(lane, z), y = Y(z), u = U(z);
    const hh = u * (3.2 + (k % 4) * 0.5), w = u * 1.5;
    ctx.fillStyle = night ? "#2b1d14" : "#5b3b22"; ctx.fillRect(x - u * 0.12, y - u * 0.7, u * 0.24, u * 0.7);
    ctx.fillStyle = night ? ["#0f3324", "#12402b", "#0b2a1d"][k % 3] : ["#1f6b3e", "#2b7f48", "#185c35"][k % 3];
    for (let j = 0; j < 3; j++) {
      const top = y - u * 0.5 - hh * (0.45 + j * 0.27), bw = w * (1 - j * 0.22);
      ctx.beginPath(); ctx.moveTo(x, top - hh * 0.28); ctx.lineTo(x + bw / 2, top + hh * 0.22); ctx.lineTo(x - bw / 2, top + hh * 0.22); ctx.fill();
    }
  }
  function thing(kind, lane, z, i, t, night) {
    const x = X(lane, z), y = Y(z), u = U(z), w = LW * 0.82 * sc(z);
    if (kind === SR_SPARK || kind === SR_SKY) {
      const bob = Math.sin(t * 5 + i) * 0.08;
      star4(x, y - u * ((kind === SR_SKY ? 1.9 : 0.55) + bob), Math.max(3, u * 0.3), "#ffe066", true);
      return;
    }
    ctx.fillStyle = "rgba(0,0,0,.22)";
    ctx.beginPath(); ctx.ellipse(x, y, w * 0.5, Math.max(1, w * 0.08), 0, 0, 7); ctx.fill();
    if (kind === SR_LOG) {                        // a fallen log: jump
      const hh = u * 0.55;
      ctx.fillStyle = night ? "#6b4428" : "#8a5a32"; ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x - w / 2, y - hh, w, hh, hh / 2) : ctx.rect(x - w / 2, y - hh, w, hh); ctx.fill();
      ctx.strokeStyle = night ? "#4a2d18" : "#5e3a1d"; ctx.lineWidth = Math.max(1, u * 0.05);
      ctx.beginPath(); ctx.moveTo(x - w * 0.35, y - hh * 0.62); ctx.lineTo(x + w * 0.2, y - hh * 0.62); ctx.moveTo(x - w * 0.15, y - hh * 0.3); ctx.lineTo(x + w * 0.38, y - hh * 0.3); ctx.stroke();
      ctx.fillStyle = night ? "#c9a06a" : "#e3bd85"; ctx.beginPath(); ctx.ellipse(x + w / 2 - hh * 0.25, y - hh / 2, hh * 0.25, hh * 0.48, 0, 0, 7); ctx.fill();
      ctx.strokeStyle = "#9b7243"; ctx.beginPath(); ctx.ellipse(x + w / 2 - hh * 0.25, y - hh / 2, hh * 0.12, hh * 0.26, 0, 0, 7); ctx.stroke();
    } else if (kind === SR_PUDDLE) {              // a puddle: jump
      ctx.fillStyle = night ? "#2b5f8f" : "#4ea3d8"; ctx.beginPath(); ctx.ellipse(x, y - u * 0.05, w * 0.5, Math.max(2, u * 0.22), 0, 0, 7); ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,.55)"; ctx.lineWidth = Math.max(1, u * 0.04);
      ctx.beginPath(); ctx.ellipse(x - w * 0.12, y - u * 0.1, w * 0.18, Math.max(1, u * 0.06), 0, 0, 7); ctx.stroke();
      star4(x + w * 0.2, y - u * 0.08, Math.max(2, u * 0.08), "rgba(255,240,180,.8)", false);
    } else if (kind === SR_BRANCH) {              // a low branch with leaves and hanging vines: duck
      const by = y - u * 1.22;
      ctx.strokeStyle = night ? "#5a3a22" : "#6e4526"; ctx.lineWidth = Math.max(2, u * 0.2); ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(x - w * 0.6, by - u * 0.25); ctx.quadraticCurveTo(x, by + u * 0.1, x + w * 0.6, by - u * 0.15); ctx.stroke();
      ctx.strokeStyle = night ? "#2f7a46" : "#3f9c58"; ctx.lineWidth = Math.max(1, u * 0.05);
      for (let k = 0; k < 5; k++) { const vx = x - w * 0.4 + k * w * 0.2; ctx.beginPath(); ctx.moveTo(vx, by); ctx.quadraticCurveTo(vx + u * 0.08, by + u * 0.25, vx, by + u * (0.35 + (k % 2) * 0.12)); ctx.stroke(); }
      ctx.fillStyle = night ? "#2a8a4c" : "#45b866";
      for (let k = 0; k < 6; k++) { ctx.beginPath(); ctx.ellipse(x - w * 0.5 + k * w * 0.2, by - u * (0.2 + (k % 2) * 0.12), u * 0.18, u * 0.11, k, 0, 7); ctx.fill(); }
      ctx.lineCap = "butt";
    } else if (kind === SR_ROCK) {                // a rock or a tree stump: go around
      if (i % 2) {
        const hh = u * 1.0, rw = w * 0.42;
        ctx.fillStyle = night ? "#5b3a24" : "#7a4e2e"; ctx.fillRect(x - rw, y - hh, rw * 2, hh);
        ctx.fillStyle = night ? "#b98f5c" : "#d6ab72"; ctx.beginPath(); ctx.ellipse(x, y - hh, rw, rw * 0.32, 0, 0, 7); ctx.fill();
        ctx.strokeStyle = "#8a6238"; ctx.lineWidth = Math.max(1, u * 0.04); ctx.beginPath(); ctx.ellipse(x, y - hh, rw * 0.55, rw * 0.17, 0, 0, 7); ctx.stroke();
      } else {
        const hh = u * 1.1;
        ctx.fillStyle = night ? "#5d6470" : "#8a929e";
        ctx.beginPath(); ctx.moveTo(x - w * 0.46, y); ctx.quadraticCurveTo(x - w * 0.5, y - hh * 0.8, x - w * 0.12, y - hh);
        ctx.quadraticCurveTo(x + w * 0.4, y - hh * 1.02, x + w * 0.46, y); ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,.18)"; ctx.beginPath(); ctx.ellipse(x - w * 0.15, y - hh * 0.72, w * 0.12, hh * 0.1, -0.4, 0, 7); ctx.fill();
        ctx.fillStyle = night ? "#3f7d4f" : "#5fae6c"; ctx.beginPath(); ctx.ellipse(x + w * 0.2, y - hh * 0.2, w * 0.14, hh * 0.08, 0, 0, 7); ctx.fill();
      }
    }
  }
  // a runner: the avatar (face, hair, outfit) on running legs, arms swinging; ghosts translucent with a name tag
  function runner(p, pose, z, phase, alpha, tag, color) {
    // the others (with a name tag) are drawn small – they should not distract from your own run
    const x = X(pose.lanePos, z), gy = Y(z), u = U(z) * (tag ? SR_GHOST_SCALE : 1);
    ctx.save();
    ctx.globalAlpha = alpha * 0.5;
    ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.beginPath(); ctx.ellipse(x, gy, u * 0.45 * (1 - pose.hgt * 0.2), u * 0.1, 0, 0, 7); ctx.fill();
    ctx.globalAlpha = alpha;
    const lift = pose.hgt * u, duck = pose.duck;
    const legLen = u * (0.62 - 0.3 * duck), hipY = gy - lift - legLen;
    const a = p.avatar || {}, outfit = p.bot ? (p.color || color) : (a.outfitColor || color), skin = p.bot ? "#e9c79a" : (a.skin || "#f1c27d");
    const run = pose.hgt > 0.05 ? 0.25 : Math.sin(phase), lw = Math.max(2, u * 0.14);
    ctx.lineCap = "round";
    ctx.strokeStyle = "#2d3a5a"; ctx.lineWidth = lw;      // the legs (trousers) and shoes
    for (const sgn of [1, -1]) {
      const sw = pose.hgt > 0.05 ? 0.35 * sgn : run * 0.55 * sgn, kx = x + sgn * u * 0.1 + sw * u * 0.25, ky = hipY + legLen * 0.55;
      const fx = x + sgn * u * 0.12 + sw * u * 0.45, fy = pose.hgt > 0.05 ? hipY + legLen * 0.8 : gy - Math.max(0, -sw) * u * 0.12;
      ctx.beginPath(); ctx.moveTo(x + sgn * u * 0.1, hipY); ctx.lineTo(kx, ky - duck * u * 0.1); ctx.lineTo(fx, fy); ctx.stroke();
      ctx.fillStyle = "#1f2433"; ctx.beginPath(); ctx.ellipse(fx, fy, lw * 0.9, lw * 0.55, 0, 0, 7); ctx.fill();
    }
    const S = u * (1.25 - 0.25 * duck), top = hipY - S * 0.97;          // the avatar: head and shoulders
    ctx.strokeStyle = outfit; ctx.lineWidth = lw * 1.05;                // the arms behind
    const shY = top + S * 0.8;
    for (const sgn of [1, -1]) {
      const sw = (pose.hgt > 0.05 ? -0.9 : -run * sgn * 0.8), hx = x + sgn * S * 0.36 + sw * u * 0.08 * sgn, hy = shY + u * 0.42 - Math.abs(sw) * u * 0.12 - (pose.hgt > 0.05 ? u * 0.55 : 0);
      ctx.beginPath(); ctx.moveTo(x + sgn * S * 0.3, shY); ctx.lineTo(hx, hy); ctx.stroke();
      ctx.fillStyle = skin; ctx.beginPath(); ctx.arc(hx, hy, lw * 0.6, 0, 7); ctx.fill();
    }
    const img = avatarImg(p);
    if (img && img.complete && img.naturalWidth) ctx.drawImage(img, x - S / 2, top, S, S);
    else {                                        // a bot (or the picture is still loading): a round head with the emoji
      ctx.fillStyle = outfit; ctx.beginPath(); ctx.ellipse(x, top + S * 0.86, S * 0.32, S * 0.2, 0, Math.PI, 0); ctx.fill();
      ctx.fillStyle = p.bot ? "#fff" : skin; ctx.beginPath(); ctx.arc(x, top + S * 0.45, S * 0.3, 0, 7); ctx.fill();
      ctx.font = Math.round(S * 0.42) + "px system-ui, 'Apple Color Emoji', 'Noto Color Emoji', sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = "#000";
      ctx.fillText(p.bot ? (p.emoji || "🤖") : "🙂", x, top + S * 0.47);
    }
    if (tag) {
      const fs = Math.max(10, Math.min(14, u * 0.32));
      ctx.font = "700 " + fs + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "bottom";
      const tw = Math.min(cw * 0.4, ctx.measureText(tag).width + 10);
      ctx.fillStyle = color; ctx.globalAlpha = alpha * 1.3;
      ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x - tw / 2, top - fs - 6, tw, fs + 5, 6) : ctx.rect(x - tw / 2, top - fs - 6, tw, fs + 5); ctx.fill();
      ctx.fillStyle = "#fff"; ctx.fillText(tag, x, top - 2, tw - 8);
    }
    ctx.restore();
  }
  function frame() {
    if (!alive || !box.isConnected) return stop();
    raf = requestAnimationFrame(frame);
    if (!canvas || !playing()) return;
    fit();
    const t = gameT(), tt = Math.max(0, Math.min(t, limit()));
    ensureCourse(tt + 4);
    resolve(tt);
    const out = st.joined ? myOut() : null;
    const myT = out != null ? Math.min(out, tt) : tt, d = srDist(myT);
    const night = dark();
    yh = ch * 0.3; y0 = ch * 0.84; LW = Math.min(cw * 0.29, ch * 0.21);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const sparks = st.joined ? mySparks() : 0;
    scenery(d, t, night, Math.min(1, sparks / 60));
    // the forest at the sides: far first
    const items = [];
    const tOff = Math.floor(d / 7);
    for (let k = tOff + 9; k >= tOff - 1; k--) for (const side of [-1, 1]) { const z = k * 7 + (side > 0 ? 3.5 : 0) - d; if (z > -F * 0.5 && z < SR_VIEW) items.push({ z, f: () => tree(z, side, k * 2 + (side > 0), night) }); }
    // the things on the path
    const first = d - F * 0.5, lastX = d + SR_VIEW;
    for (let i = 0; i < course.length; i++) {
      const [x, lane, kind] = course[i];
      if (x < first) continue;
      if (x > lastX) break;
      if ((kind === SR_SPARK || kind === SR_SKY) && (locGot.has(i) || (srv && i < srv.next && x < d + 0.5))) continue;
      const z = x - d;
      items.push({ z: z + (kind === SR_BRANCH ? 0.01 : 0), f: () => thing(kind, lane, z, i, t, night) });
    }
    // the ghosts: everybody runs the same distance – ahead by the sparks, behind when out
    const mySrvSparks = (srv && srv.sparks) || 0, myPose = srPose(myBase, myEv, myT);
    const order = st.players;
    let n = 0, pushed = 0;
    for (const p of order) {
      if (p.id === myId || n >= 8) continue;
      const g = ghosts[p.id];
      if (!g) continue;
      const gt = Math.max(0, Math.min(t - SR_GHOST_DELAY, limit()));
      const theirT = p.out != null ? Math.min(p.out, gt) : gt;
      if (p.out != null && srDist(p.out) < d - 2) continue;              // out: left behind
      const pose = srPose(g.base, g.ev, gt), col = SR_COLORS[order.indexOf(p) % SR_COLORS.length];
      let z = st.joined ? Math.max(-0.8, srDist(theirT) - d + 0.9 * ((p.sparks || 0) - mySrvSparks)) : 1.5 + n * 1.2;
      if (z > SR_VIEW - 5) continue;
      if (st.joined && z < 1.8 && Math.abs(pose.lanePos - myPose.lanePos) < 0.7) z = 1.8 + 1.4 * pushed++;   // never hidden behind / in front of me
      n++;
      items.push({ z: z + 0.02, f: () => runner(p, pose, z, srDist(gt) * 0.9 + order.indexOf(p), 0.42, p.name, col) });
    }
    if (st.joined) {                              // me
      const mine = order.find(p => p.id === myId) || me;
      const pose = myPose;
      const blink = hitTimes().some(x => myT >= x && myT < x + SR.INVULN) && Math.floor(t * 10) % 2 === 0;
      items.push({ z: 0, f: () => runner(mine, pose, 0, d * 0.9, out != null ? 0.35 : blink ? 0.3 : 1, null, SR_COLORS[order.indexOf(mine) % SR_COLORS.length]) });
    }
    items.sort((a, b) => b.z - a.z);
    for (const it of items) it.f();
    // a spark caught: a small pop; a hit: a red flash
    pops = pops.filter(p => tt - p.t < 0.5);
    for (const p of pops) { const k = (tt - p.t) / 0.5; ctx.globalAlpha = 1 - k; star4(X(p.lane, 0), Y(0) - U(0) * (1.4 + k * 1.5), U(0) * 0.3 * (1 + k), "#fff3b0", true); ctx.globalAlpha = 1; }
    if (flash && tt - flash >= 0 && tt - flash < 0.35) { ctx.fillStyle = `rgba(242,84,91,${0.35 * (1 - (tt - flash) / 0.35)})`; ctx.fillRect(0, 0, cw, ch); }
    // the countdown, out, time up
    const big = (txt, sub) => {
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineWidth = 6; ctx.strokeStyle = "rgba(15,23,42,.7)"; ctx.fillStyle = "#fff";
      ctx.font = "900 " + Math.round(Math.min(cw * 0.16, ch * 0.1)) + "px system-ui, sans-serif";
      ctx.strokeText(txt, cw / 2, ch * 0.45); ctx.fillText(txt, cw / 2, ch * 0.45);
      if (sub) {
        let fs = Math.round(Math.min(cw * 0.05, 20));
        ctx.font = "700 " + fs + "px system-ui, sans-serif";
        const w = ctx.measureText(sub).width;
        if (w > cw - 24) { fs = Math.max(9, Math.floor(fs * (cw - 24) / w)); ctx.font = "700 " + fs + "px system-ui, sans-serif"; }
        ctx.lineWidth = 4; ctx.strokeText(sub, cw / 2, ch * 0.45 + Math.min(cw * 0.12, 60)); ctx.fillText(sub, cw / 2, ch * 0.45 + Math.min(cw * 0.12, 60)); }
    };
    if (t < 0.7) big(t < 0 ? String(Math.ceil(-t)) : I18N.tr(T("Run!")), t < 0 ? I18N.tr(T("Swipe: ← → lane · ↑ jump · ↓ duck")) : null);
    else if (out != null) big("💥 " + I18N.tr(T("Out!")), I18N.tr(T("Watch the others run …")));
    else if (t >= limit()) big("⏱ " + I18N.tr(T("Time is up!")));
    // the bar above the path
    if (hud) {
      const left = Math.max(0, Math.ceil(limit() - Math.max(0, t)));
      hud.lives.textContent = st.joined ? "❤️".repeat(myLives()) + "🤍".repeat(Math.min(lives0(), lives0() - myLives())) : "";
      hud.sparks.textContent = "✨ " + sparks;
      hud.dist.textContent = Math.floor(d) + " m";
      hud.time.textContent = "⏱ " + Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
    }
  }

  // ---------- the screen
  function drawBoard() {                          // the live mini ranking: points, sparks, who is still running
    if (!board || !st || !st.players) return;
    const t = Math.max(0, Math.min(gameT(), limit()));
    const pts = p => {
      const own = p.id === myId && st.joined;
      const out = own ? myOut() : p.out, tt = own ? t : Math.max(0, t - SR_GHOST_DELAY);
      return { p, sparks: own ? mySparks() : p.sparks, out, pts: srPoints(srDist(out != null ? Math.min(out, tt) : tt), own ? mySparks() : p.sparks) };
    };
    const rows = st.players.map(pts).sort((a, b) => b.pts - a.pts);
    board.replaceChildren(...rows.map((r, k) => h("div.sr-chip" + (r.p.id === myId ? ".sr-mine" : "") + (r.out != null ? ".sr-outp" : ""),
      h("b.sr-rank", r.out != null ? "💥" : String(k + 1)), seatIcon(r.p, 20), C(r.p.name, "span.sr-nm"),
      h("span.sr-pts", String(r.pts)))));
  }
  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return !st.solo && !me.guest && st.status !== "done" ? "sternlauf" : null; }
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, st.players.map(p => [p.id, p.place]), st.phase === "lobby" ? st.players.length : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    canvas = null; hud = null; board = null;
    if (!st) return show(h("section.card.center", h("div.big-ic", SR_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    // ☰: rules, guests, End (whoever leads), language – only the main action (Start) stays as a big button
    const menu = gameMenu({ rules: () => sternlaufRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: invite(),
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", SR_ICON, " ", srName())));
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))) : null;
    if (st.phase === "done") return show(head, result());
    if (st.phase === "lobby") {
      const story = h("p.small.muted", T("The lantern of the village went out! Run along the forest path and catch the falling star sparks ✨ to light it again."));
      if (!st.joined) return show(head, h("section.card.center", story, h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), lobbySeats(), host);
      return show(head, h("section.card.center", h("h2", T("Waiting for the start …")), story,
        h("p.muted", T("Everybody joins on their own device.")), lobbySeats(), inviteBtn(invite()),
        st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", srCoins(st.rewards))) : null), host);
    }
    // the run
    canvas = h("canvas.sr-canvas");
    ctx = canvas.getContext("2d");
    wrap = h("div.sr-wrap", canvas);
    swipes(wrap);
    hud = { lives: h("span.sr-lives"), sparks: h("strong.sr-sparks"), dist: h("strong.sr-dist", "0 m"), time: h("span.sr-time") };
    const bar = h("div.sr-bar", hud.lives, hud.sparks, hud.dist, hud.time);
    board = st.players.length > 1 ? h("div.sr-board") : null;
    const btn = (c, ic, label) => h("button.sr-btn", { type: "button", "aria-label": label, title: label,
      onpointerdown: e => { e.preventDefault(); input(c); }, onclick: e => { if (e.detail === 0) input(c); } }, ic);
    const pad = st.joined ? h("div.sr-pad", btn("l", "◀", T("Move left")), btn("u", "▲", T("Jump!")), btn("d", "▼", T("Duck!")), btn("r", "▶", T("Move right")))
      : h("p.muted.center", T("The game has already started"));
    show(head, bar, board, wrap, pad, host);
    drawBoard();
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
      try { await api("community/sternlauf/start", { method: "POST", body: { solo: true } }); setState(await req("")); draw(true); } catch (e) { toast(e.message, "bad"); }
    } }, "🔄 ", T("Play again")) : null;
    const total = st.players.reduce((s, p) => s + (p.bot ? 0 : p.sparks || 0), 0);
    return h("section.card.center.sr-result",
      st.players.length > 1 ? h("h2", "🏆 ", C(winners)) : h("h2", SR_ICON, " ", I18N.tr(T("{0} points")).replace("{0}", m.score || 0)),
      m.record ? h("p.sr-record", "🎉 ", T("New personal best!")) : null,
      st.joined && st.best ? h("p.small.muted", "🏆 ", I18N.tr(T("Your best: {0}")).replace("{0}", I18N.tr(T("{0} points")).replace("{0}", st.best))) : null,
      total ? h("p.small", "🏮 ", I18N.tr(T("Together you brought {0} star sparks to the village lantern.")).replace("{0}", total)) : null,
      h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".sr-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 30),
        h("span.grow", C(p.name, "strong"), h("br"), h("span.small.muted", (p.dist || 0) + " m · " + (p.sparks || 0) + " ✨")),
        h("span", I18N.tr(T("{0} points")).replace("{0}", p.score || 0)), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on || st.players.length < 2 ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", again, h("button.btn" + (again ? ".ghost" : ""), { onclick: back }, T("Back"))));
  }
  (async () => { try { setState(await req("")); } catch {} draw(true); poll(); })();
  const boardTimer = setInterval(() => { if (!alive) clearInterval(boardTimer); else if (board && playing()) drawBoard(); }, 500);
  raf = requestAnimationFrame(frame);
}

async function sternlaufView() {
  const box = h("div.sr-live");
  screen("games", box);
  sternlaufLive(box, S.profile, () => go("games"));
}

async function sternlaufFamilyCard() {
  const c = S.me && S.me.community, g = c && c.sternlauf;
  return h("section.card.quiz-card", h("h2", SR_ICON, " ", srName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("sternlauf") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("The lantern of the village went out! Run along the forest path, dodge logs, branches and rocks and catch the star sparks – everybody runs the same course at the same time.")),
         gameStartRow(() => sternlaufStartDialog(true, () => go("sternlauf")), () => sternlaufStartDialog(false, () => go("sternlauf")))]);
}
