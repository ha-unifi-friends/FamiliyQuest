// «Jump» – a live jumping race (familyquest/jump.py): everybody has their own lane, the obstacles come from the left,
// jump over them with the big button (or a tap on your lane, or the space bar). Crates carry you, cacti sting, and from
// time to time comes a cloud parcours (crates on clouds over a cactus field). Same obstacles for everybody (a course
// from the server's seed, made here with the same generator), 3 lives, it gets faster – the last one running wins.
// jumpLive(box, me, back) runs a table (family or alone), jumpStartDialog(solo, onStarted) sets the rules.
// The jump physics run here (JuRunner – step by step, the same as Runner in jump.py); the app reports its jumps and hits,
// the others' lanes are drawn by their own runners from their reported jump times a moment late (JU_DELAY).
// Uses botPicker() from cards.js and guestInvite() from community.js.
"use strict";

const JU_ICON = "🦘";
const juName = () => "Jump";
const juCoins = list => list.join(" / ") + " 🪙";
// the course – the same numbers as in jump.py. Kinds: 0 crate, 1 double crate (stand on them, their side costs a life),
// 2 long hedge, 3 cactus (touching costs a life), 4 a crate on a cloud (a platform), 5 the cactus field under the clouds
const JU = { V0: 5, VMAX: 12, ACC: 0.05, JT: 0.6, JH: 1.5, OH: 0.7, AW: 0.25, WIDTH: [0.6, 1.6, 2.6, 0.5], TALL: [0.7, 0.7, 0.7, 0.8],
  FIELD_H: 0.55, FIRST: 2.5, CLOUD_T: 45, CLOUD_EVERY: 60, CLOUD_LEAD: 1.6, INVULN: 1.2, VIEW: 12,
  HZ: 120, LG: 0.2, COYOTE: 0.1 };
JU.T1 = (JU.VMAX - JU.V0) / JU.ACC;
JU.D1 = JU.V0 * JU.T1 + JU.ACC * JU.T1 * JU.T1 / 2;
JU.G = 8 * JU.JH / (JU.JT * JU.JT);
JU.VJ = 4 * JU.JH / JU.JT;
JU.VB = 0.6 * JU.VJ;
const JU_DELAY = 0.45;                         // the others' lanes are drawn this much later (their jumps need to arrive)
const JU_COLORS = ["#f2545b", "#2f8fdd", "#33a852", "#f2b705", "#8b5cf6", "#14b8a6"];

function juDist(t) { return t <= 0 ? 0 : t < JU.T1 ? JU.V0 * t + JU.ACC * t * t / 2 : JU.D1 + JU.VMAX * (t - JU.T1); }
function juTimeAt(x) { return x <= 0 ? 0 : x < JU.D1 ? (-JU.V0 + Math.sqrt(JU.V0 * JU.V0 + 2 * JU.ACC * x)) / JU.ACC : JU.T1 + (x - JU.D1) / JU.VMAX; }
function juSpeedAt(x) { return Math.min(JU.VMAX, Math.sqrt(JU.V0 * JU.V0 + 2 * JU.ACC * x)); }
function juRand(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), a | 1) >>> 0;
    t = (((t + Math.imul(t ^ (t >>> 7), t | 61)) >>> 0) ^ t) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function juClouds(out, x, rnd) {               // a cloud parcours: crates on clouds, a dense cactus field below
  const v = juSpeedAt(x), n = 4 + Math.floor(rnd() * 3), plats = [];
  x = x + v * JU.CLOUD_LEAD;
  let top = 1.0;
  for (let k = 0; k < n; k++) {
    const w = v * ((k === 0 ? 0.85 : 0.6) + 0.25 * rnd());
    plats.push([x, w, top]);
    x = x + w + v * (0.24 + 0.1 * rnd());
    top = Math.min(1.3, Math.max(0.9, top + (rnd() - 0.5) * 0.8));
  }
  for (let k = 0; k < n; k++) {
    const [px, w, tp] = plats[k];
    out.push([px, 4, w, tp]);
    const fs = k === 0 ? px + 0.4 : px, fe = k + 1 < n ? plats[k + 1][0] : px + w - 0.4;
    out.push([fs, 5, fe - fs, JU.FIELD_H]);
  }
  return plats[n - 1][0] + plats[n - 1][1] + v * 1.4;
}
// the course up to this distance: [x of the front edge, kind, width, height of the top, window start, window end]
function juCourse(seed, upto) {
  const rnd = juRand(seed), out = [];
  let x = JU.V0 * JU.FIRST, nc = juDist(JU.CLOUD_T);
  while (x <= upto) {
    if (x >= nc) { x = juClouds(out, x, rnd); nc = juDist(juTimeAt(x) + JU.CLOUD_EVERY); continue; }
    const v = juSpeedAt(x), r1 = rnd(), r2 = rnd(), r3 = rnd(), prog = (v - JU.V0) / (JU.VMAX - JU.V0);
    let kind = r3 < 0.4 ? 3 : 0;
    if (v >= 10 && r1 < 0.2) kind = 2;
    else if (v >= 7 && r1 < 0.5) kind = 1;
    out.push([x, kind, JU.WIDTH[kind], JU.TALL[kind]]);
    x = x + JU.WIDTH[kind] + v * (0.95 + r2 * (1.3 - 0.4 * prog));
  }
  for (const o of out) o.push(juTimeAt(o[0] - JU.AW), juTimeAt(o[0] + o[2] + JU.AW));
  return out;
}
// the jump physics of one runner, step by step – the same as Runner in jump.py (the others' lanes come out exactly)
class JuRunner {
  constructor() { this.k = 0; this.y = 0; this.vy = 0; this.ground = true; this.walk = false; this.left = -99; this.jt = -99; this.last = -99; this.lo = 0; this.ids = new Set(); this.jumped = false; }
  clone() { const c = Object.assign(new JuRunner(), this); c.ids = new Set(this.ids); return c; }
  canJump() { return this.ground || (this.walk && (this.k + 1) / JU.HZ - this.left <= JU.COYOTE); }
  near(obs, d) {
    while (this.lo < obs.length && obs[this.lo][0] + obs[this.lo][2] < d - JU.AW) this.lo++;
    const out = [];
    for (let i = this.lo; i < obs.length && obs[i][0] <= d + JU.AW; i++) if (obs[i][0] + obs[i][2] >= d - JU.AW) out.push(i);
    return out;
  }
  step(obs, jumps, ji) {                       // → [ji, hit [index, time] or null]
    const k1 = this.k + 1, t1 = k1 / JU.HZ;
    let want = false;
    while (ji < jumps.length && jumps[ji] < t1) { want = true; this.jt = jumps[ji]; ji++; }
    this.jumped = false;
    if (want && this.canJump()) { this.vy = JU.VJ; this.ground = false; this.walk = false; this.jumped = true; }
    const near = this.near(obs, juDist(t1)), y0 = this.y;
    if (this.ground) {
      let s = 0;
      for (const i of near) { const o = obs[i]; if ((o[1] <= 1 || o[1] === 4) && s < o[3] && o[3] <= y0 + 1e-6) s = o[3]; }
      if (s < y0 - 1e-6) { this.ground = false; this.walk = true; this.left = t1; this.vy = 0; }
      else this.y = s;
    }
    if (!this.ground) {
      const y1 = y0 + this.vy / JU.HZ - JU.G / (2 * JU.HZ * JU.HZ);
      this.vy = this.vy - JU.G / JU.HZ;
      let land = null;
      if (this.vy <= 0) {
        if (y1 <= 0) land = 0;
        for (const i of near) {
          const o = obs[i];
          if ((o[1] <= 1 || o[1] === 4) && y1 <= o[3] && o[3] <= y0 + JU.LG && (land == null || o[3] > land)) land = o[3];
        }
      }
      if (land != null) { this.y = land; this.vy = 0; this.ground = true; this.walk = false; }
      else this.y = y1;
    }
    this.k = k1;
    if (t1 >= this.last + JU.INVULN) {
      for (const i of near) {
        const o = obs[i];
        if (o[1] === 4 || this.ids.has(i)) continue;
        if (this.y < (o[1] <= 1 ? o[3] - JU.LG : o[3])) {
          this.ids.add(i); this.last = t1; this.vy = JU.VB; this.ground = false; this.walk = false;
          return [ji, [i, t1]];
        }
      }
    }
    return [ji, null];
  }
  run(obs, jumps, t, onHit) {                  // on to game time t (jumps: sorted start times)
    let ji = jumps.length;
    while (ji > 0 && jumps[ji - 1] > this.jt) ji--;
    while ((this.k + 1) / JU.HZ <= t) {
      const r = this.step(obs, jumps, ji);
      ji = r[0];
      if (r[1] && onHit) onHit(r[1]);
    }
  }
}
function juDark() {
  const th = document.documentElement.getAttribute("data-theme");
  return th === "dark" || (th !== "light" && !!(window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches));
}

function jumpRulesView(r, rewards) {
  r = r || {};
  const items = [
    T("Everybody has their own lane – your runner is on the right, the obstacles come from the left."),
    T("Tap the big button (or your lane, or press the space bar) to jump. Everybody gets the same obstacles."),
    T("Crates are safe: land on top and run along – only running into their side costs a life."),
    T("Cacti and hedges sting – touching one costs a life (you hop up and blink for a moment)."),
    I18N.tr(T("After {0} seconds comes the cloud course (and later again): crates on clouds, dense cacti below. Jump from crate to crate – falling onto the cacti costs a life.")).replace("{0}", JU.CLOUD_T),
    T("It gets faster and faster – later come double and long obstacles."),
    I18N.tr(T("Every obstacle you hit costs a life (then you blink for a moment). You have {0} lives.")).replace("{0}", r.lives || 3),
    T("The last one still running wins. Alone: run as far as you can – your best distance is kept."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", juCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function jumpStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/jump/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(r.bots ?? 0, [0, 1, 2, 3, 4, 5].map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const lives = sel(r.lives || 3, [1, 3, 5].map(n => [n, "❤️ " + n]));
  const picker = botPicker(1400);
  const speed = picker.el.querySelector(".bot-speed");             // bots jump by their level – no reaction time here
  if (speed) speed.remove();
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", juCoins(rw)), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", JU_ICON, " ", juName(), solo ? " – " + I18N.tr(T("Alone")) : ""),
    h("p.small.muted", T("Jump over the obstacles – everybody gets the same ones, and it gets faster. Who keeps running longest wins!")),
    h("div.grid2", h("label.field", solo ? T("Practice bots") : T("Bots"), bots), h("label.field", T("Bots play"), level)),
    h("label.field", T("Lives"), lives),
    solo ? null : h("p.small.muted", T("1 to 6 players: the family joins on their own devices, guests via QR code.")),
    picker.el,
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: +bots.value, level: level.value, lives: +lives.value, bot_ids: picker.ids() };
      try { await api("community/jump/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("jump", bots, level, picker.el);          // parent area › Games: without bots
}

function jumpLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, raf = 0, syncing = false, lastSync = 0;
  let canvas = null, ctx = null, wrap = null, livesEl = null, distEl = null, jumpBtn = null, cw = 0, ch = 0, dpr = 1;
  let offset = null, bestRtt = 1e9;               // server clock − performance clock (seconds)
  let course = [], courseSeed = null, courseUpto = 0, cloudAt = [];
  let myJumps = [], myHits = new Map(), myOut = null, myRun = null, silentT = -99, pendJ = [], pendH = [], gameKey = "";
  let lanesRun = {};                               // the others' runners: {run, js (sorted), seen (Set), cps (checkpoints)}
  const imgs = {};
  const myId = String(me.id);
  box.classList.add("ju-live");
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
  const myLives = () => Math.max(0, lives0() - myHits.size);

  function clock(s, t1, t2) {                    // the server's clock: the answer with the shortest way counts
    if (!s || typeof s.now !== "number") return;
    const rtt = t2 - t1;
    if (rtt <= bestRtt * 1.15 || offset == null) { bestRtt = Math.min(bestRtt, rtt); offset = s.now - (t1 + t2) / 2; }
  }
  const req = async (path, opts) => {
    const t1 = nowS();
    const s = await api("community/jump" + path, opts);
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
    if (key !== gameKey) {                         // a new game: my lane from the server (a reload in the middle keeps it)
      gameKey = key;
      const mine = st.players.find(p => p.id === myId);
      myJumps = mine ? [...mine.jumps] : []; myHits = new Map((mine ? mine.hits : []).map(([i, t]) => [i, t]));
      myOut = mine ? mine.out : null; myRun = null; silentT = -99; lanesRun = {}; pendJ = []; pendH = []; cheered = false;
    }
  }
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    if (!playing() || !st.joined) {
      try { const s = await req(""); if (!busy) { setState(s); draw(); } } catch {}
    } else if (nowS() - lastSync > 0.24) sync();
    timer = setTimeout(poll, playing() ? 250 : 1000);
  }
  async function sync() {                         // my jumps and hits to the server – the others' lanes back
    if (syncing || !playing() || !st.joined) return;
    syncing = true; lastSync = nowS();
    const jumps = pendJ.slice(), hits = pendH.slice();
    try {
      const s = await req("/sync", { method: "POST", body: { t: Math.round(gameT() * 1000) / 1000, jumps, hits } });
      pendJ = pendJ.filter(j => !jumps.includes(j)); pendH = pendH.filter(x => !hits.includes(x));
      setState(s); draw();
    } catch {}
    syncing = false;
  }

  // ---------- my runner
  function jump() {
    if (!playing() || !st.joined || myOut != null) return;
    const t = gameT();
    if (t < -0.2) return;
    ensureCourse(Math.max(0, t) + 2);
    stepMine(t);
    if (!myRun || myOut != null || !myRun.canJump()) return;     // only from the ground or a crate
    const now = Math.max(t, myRun.k / JU.HZ, 0);
    if (myJumps.length && myJumps[myJumps.length - 1] >= myRun.k / JU.HZ) return;   // one is waiting for the next step
    const j = Math.ceil(now * 1000) / 1000;      // never before the step my runner is at (the others' runners agree)
    myJumps.push(j); if (myJumps.length > 60) myJumps.shift();
    pendJ.push(j);
    try { Sound.play("tap"); } catch {}
    if (jumpBtn) { jumpBtn.classList.remove("hop"); void jumpBtn.offsetWidth; jumpBtn.classList.add("hop"); }
    sync();
  }
  function onKey(e) {
    if (!alive || !box.isConnected) return;
    if ((e.code === "Space" || e.key === " " || e.code === "ArrowUp") && !/^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || "")) {
      e.preventDefault(); jump();
    }
  }
  window.addEventListener("keydown", onKey);
  function ensureCourse(t) {
    const need = juDist(t) + 40;
    if (courseSeed !== st.seed || courseUpto < need) {
      courseSeed = st.seed; courseUpto = need + 300; course = juCourse(st.seed, courseUpto);
      cloudAt = course.map((o, i) => o[1] === 4 && (i === 0 || course[i - 1][1] < 4) ? i : -1).filter(i => i >= 0);
    }
  }
  function stepMine(t) {                          // my runner on to t: its hits cost my lives
    if (myOut != null || !st || !st.joined) return;
    if (!myRun) {                                  // (a reload in the middle: the past runs silently, the server's hits count)
      myRun = new JuRunner();
      for (const [i, th] of myHits) { myRun.ids.add(i); myRun.last = Math.max(myRun.last, th); }
      silentT = t - 0.05;
    }
    if (t - myRun.k / JU.HZ > 1.5) silentT = Math.max(silentT, t - 1.5);   // the app was asleep: no hits for that time
    myRun.run(course, myJumps, t, ([i, th]) => {
      if (myOut != null || th <= silentT || myHits.has(i)) return;
      const tr = Math.round(th * 1000) / 1000;
      myHits.set(i, tr); pendH.push([i, tr]);
      if (myLives() <= 0) myOut = tr;
      try { Sound.play("wrong"); } catch {}
      if (navigator.vibrate) try { navigator.vibrate(myOut != null ? [80, 60, 160] : 60); } catch {}
      sync();
    });
  }
  function laneY(p, t) {                          // another lane: its runner from the reported jumps (rewound when one comes late)
    let c = lanesRun[p.id];
    if (!c) c = lanesRun[p.id] = { run: new JuRunner(), js: [], seen: new Set(), cps: [] };
    let early = Infinity;
    for (const j of p.jumps || []) if (!c.seen.has(j)) { c.seen.add(j); c.js.push(j); early = Math.min(early, j); }
    if (early < Infinity) {
      c.js.sort((a, b) => a - b);
      if (early < (c.run.k + 1) / JU.HZ) {
        while (c.cps.length && c.cps[c.cps.length - 1].k / JU.HZ >= early - 1 / JU.HZ) c.cps.pop();
        c.run = c.cps.length ? c.cps[c.cps.length - 1].clone() : new JuRunner();
      }
    }
    const until = p.out != null ? Math.min(t, p.out) : t;
    while ((c.run.k + 1) / JU.HZ <= until) {
      c.run.run(course, c.js, Math.min(until, (Math.floor(c.run.k / JU.HZ) + 1)));
      if (c.run.k % JU.HZ === 0) c.cps.push(c.run.clone());
    }
    return c.run.y;
  }

  // ---------- drawing the lanes
  function avatarImg(p) {
    if (p.bot || imgs[p.id]) return imgs[p.id] || null;
    try {
      const svg = avatarSvg(p.avatar || {}, 96).querySelector("svg");
      svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const img = new Image();
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(svg));
      imgs[p.id] = img;
      return img;
    } catch { return null; }
  }
  function fit() {
    if (!canvas || !wrap) return;
    const r = wrap.getBoundingClientRect();
    dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(100, Math.floor(r.width)), hh = Math.max(120, Math.floor(r.height));
    if (w !== cw || hh !== ch) { cw = w; ch = hh; canvas.width = w * dpr; canvas.height = hh * dpr; canvas.style.width = w + "px"; canvas.style.height = hh + "px"; }
  }
  function lanes() {                              // my lane at the bottom (big), the others stacked above
    const ps = st.players, mine = ps.find(p => p.id === myId), others = ps.filter(p => p.id !== myId);
    const gap = 5, out = [];
    if (!mine) {
      const lh = Math.min(140, (ch - gap * (ps.length - 1)) / ps.length);
      ps.forEach((p, k) => out.push({ p, y: k * (lh + gap), h: lh, own: false, color: JU_COLORS[k % 6] }));
      return out;
    }
    const meH = others.length ? Math.max(130, Math.min(180, ch * 0.36)) : Math.min(ch, 260);
    const oh = others.length ? Math.min(110, (ch - meH - gap * others.length) / others.length) : 0;
    let y = ch - meH - gap * others.length - oh * others.length;
    y = Math.max(0, y / 2);
    others.forEach(p => { out.push({ p, y, h: oh, own: false, color: JU_COLORS[ps.indexOf(p) % 6] }); y += oh + gap; });
    out.push({ p: mine, y: ch - meH, h: meH, own: true, color: JU_COLORS[ps.indexOf(mine) % 6] });
    return out;
  }
  function rr(x, y, w, hh, r) { ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, hh, r) : ctx.rect(x, y, w, hh); }
  // the course pieces – own drawings: wooden crates, round cacti with spikes, crates resting on clouds, the cactus field
  function drawCrate(bx, by, bw, bh) {
    ctx.fillStyle = "#c97a2b"; rr(bx + 0.5, by, bw - 1, bh, 3); ctx.fill();
    ctx.fillStyle = "#e09a4f"; ctx.fillRect(bx + 1.5, by + 1, bw - 3, Math.max(2, bh * 0.12));
    ctx.strokeStyle = "#8a4f14"; ctx.lineWidth = Math.max(1, bw * 0.06);
    ctx.strokeRect(bx + bw * 0.18, by + bh * 0.18, bw * 0.64, bh * 0.64);
    ctx.beginPath(); ctx.moveTo(bx + bw * 0.18, by + bh * 0.18); ctx.lineTo(bx + bw * 0.82, by + bh * 0.82); ctx.stroke();
  }
  function drawCactus(cx, base, cw0, chh, dark) {   // a round-topped column with two arms, little spikes and a flower
    const body = dark ? "#2f8f4e" : "#3aa35c", rib = dark ? "#226b3a" : "#2b7d45", w = cw0 * 0.42;
    ctx.fillStyle = body;
    rr(cx - w / 2, base - chh, w, chh, w / 2); ctx.fill();
    const arm = (side, y0, len) => {             // an L-shaped arm
      const ax = cx + side * w / 2, aw = w * 0.62;
      rr(side > 0 ? ax - 1 : ax - cw0 * 0.32 + 1, y0, cw0 * 0.32, aw, aw / 2); ctx.fill();
      rr(side > 0 ? ax + cw0 * 0.32 - aw : ax - cw0 * 0.32, y0 - len, aw, len + aw, aw / 2); ctx.fill();
    };
    if (chh > 14) { arm(-1, base - chh * 0.5, chh * 0.25); arm(1, base - chh * 0.68, chh * 0.2); }
    ctx.strokeStyle = rib; ctx.lineWidth = Math.max(1, w * 0.08);
    ctx.beginPath(); ctx.moveTo(cx, base - chh + w * 0.4); ctx.lineTo(cx, base - 2); ctx.stroke();
    ctx.strokeStyle = dark ? "#e6f5d0" : "#fdfde8"; ctx.lineWidth = 1;
    ctx.beginPath();
    for (let yy = base - chh + w * 0.35; yy < base - 2; yy += Math.max(4, chh / 6)) {
      ctx.moveTo(cx - w / 2, yy); ctx.lineTo(cx - w / 2 - 3, yy - 2);
      ctx.moveTo(cx + w / 2, yy + 2); ctx.lineTo(cx + w / 2 + 3, yy);
    }
    ctx.stroke();
    if (chh > 14) { ctx.fillStyle = "#ff7eb6"; ctx.beginPath(); ctx.arc(cx, base - chh, Math.max(2, w * 0.22), 0, 7); ctx.fill(); }
  }
  function drawCloud(cx, cy, w, r0, dark) {
    ctx.fillStyle = dark ? "rgba(203,213,235,.9)" : "#ffffff";
    const n = Math.max(2, Math.round(w / (r0 * 1.4)));
    ctx.beginPath();
    for (let k = 0; k < n; k++) { const px = cx - w / 2 + r0 + k * (w - 2 * r0) / Math.max(1, n - 1); ctx.moveTo(px + r0, cy); ctx.arc(px, cy - (k % 2) * r0 * 0.35, r0 * (k % 2 ? 1.1 : 0.95), 0, 7); }
    ctx.fill();
    ctx.fillStyle = dark ? "rgba(148,163,196,.5)" : "rgba(186,214,240,.75)";
    rr(cx - w / 2 + r0 * 0.3, cy, w - r0 * 0.6, r0 * 0.7, r0 * 0.35); ctx.fill();
  }
  function drawSign(fx, ground, sx, sy, dark) {   // a little post before the cloud parcours: a cloud and an arrow up
    const ph = 1.25 * sy, bw = 0.9 * sx, bh = 0.62 * sy;
    ctx.fillStyle = "#8a5a2b"; ctx.fillRect(fx - 2, ground - ph, 4, ph);
    ctx.fillStyle = dark ? "#f4d58d" : "#ffe9a8"; ctx.strokeStyle = "#8a5a2b"; ctx.lineWidth = 2;
    rr(fx - bw / 2, ground - ph - bh * 0.6, bw, bh, 5); ctx.fill(); ctx.stroke();
    drawCloud(fx - bw * 0.12, ground - ph - bh * 0.05, bw * 0.5, Math.max(3, bh * 0.2), false);
    ctx.strokeStyle = "#d9480f"; ctx.lineWidth = Math.max(2, bw * 0.06);
    const ax = fx + bw * 0.3, ay = ground - ph - bh * 0.45;
    ctx.beginPath(); ctx.moveTo(ax, ay + bh * 0.62); ctx.lineTo(ax, ay); ctx.moveTo(ax - bw * 0.1, ay + bh * 0.14); ctx.lineTo(ax, ay); ctx.lineTo(ax + bw * 0.1, ay + bh * 0.14); ctx.stroke();
  }
  function drawLane(L, t) {
    const { p, y, h: lh, own, color } = L;
    const dark = juDark();
    const sx = cw / JU.VIEW, ground = y + lh - Math.max(8, Math.min(30, lh * 0.14)), top = y + Math.max(14, lh * 0.12);
    const sy = Math.min((ground - top) / (JU.JH + 2.2), sx * 1.25), avX = cw - 1.6 * sx;
    const d = juDist(t);
    const hits = own ? [...myHits.values()] : (p.hits || []).map(x => x[1]);
    const out = own ? myOut : p.out;
    const isOut = out != null && out <= t;
    const lost = hits.filter(x => x <= t).length;
    // the sky and the ground
    ctx.save();
    rr(0, y, cw, lh, 12); ctx.clip();
    const g = ctx.createLinearGradient(0, y, 0, y + lh);
    if (dark) { g.addColorStop(0, own ? "#1e3a5f" : "#1b2c44"); g.addColorStop(1, "#2c3e5a"); }
    else { g.addColorStop(0, own ? "#bfe3ff" : "#d9ecfb"); g.addColorStop(1, "#f4fbff"); }
    ctx.fillStyle = g; ctx.fillRect(0, y, cw, lh);
    ctx.fillStyle = color; ctx.globalAlpha = 0.16; ctx.fillRect(0, y, 6, lh); ctx.globalAlpha = 1;
    if (lh > 70) {                                 // slow clouds
      ctx.fillStyle = dark ? "rgba(203,213,235,.18)" : "rgba(255,255,255,.85)";
      const span = cw + 120;
      for (let k = 0; k < 3; k++) {
        const cx = ((k * 157 + d * sx * 0.25) % span + span) % span - 60, cy = y + lh * (0.22 + 0.13 * (k % 2)), r0 = Math.min(16, lh * 0.08);
        ctx.beginPath(); ctx.arc(cx, cy, r0, 0, 7); ctx.arc(cx + r0, cy - r0 * 0.5, r0 * 1.15, 0, 7); ctx.arc(cx + r0 * 2.1, cy, r0 * 0.9, 0, 7); ctx.fill();
      }
    }
    ctx.fillStyle = dark ? "#4d7a2c" : "#8bc34a"; ctx.fillRect(0, ground, cw, y + lh - ground);
    ctx.fillStyle = dark ? "#3a5f20" : "#6a9f2f";
    const step = 1.5 * sx, off = ((d * sx) % step + step) % step;
    for (let x = -step + off; x < cw; x += step) ctx.fillRect(x, ground + 3, sx * 0.5, 2);
    // the course (the same for everybody)
    const first = d - (JU.VIEW - 1.6) - 3, last = d + 3;
    for (const ci of cloudAt) {                    // the signpost before a cloud parcours
      const sxp = course[ci][0] - juSpeedAt(course[ci][0]) * 0.9, fx = avX + (d - sxp) * sx;
      if (fx > -40 && fx < cw + 40) drawSign(fx, ground, sx, sy, dark);
    }
    for (let i = 0; i < course.length; i++) {
      const [x, kind, ww, hh] = course[i];
      if (x + ww < first) continue;
      if (x > last + JU.VIEW) break;
      const fx = avX + (d - x) * sx, w = ww * sx, oh = hh * sy;   // fx: the front edge (right), the piece goes left
      if (fx < -2 || fx - w > cw + 2) continue;
      if (kind === 2) {                            // a long hedge
        ctx.fillStyle = dark ? "#237a36" : "#2f9e44"; rr(fx - w, ground - oh, w, oh, Math.min(10, oh / 2)); ctx.fill();
        ctx.fillStyle = dark ? "#2f9e44" : "#40c057";
        for (let k = 0; k < 4; k++) { ctx.beginPath(); ctx.arc(fx - w + (k + 0.5) * w / 4, ground - oh + 2, Math.min(w / 8, oh / 2.2), Math.PI, 0); ctx.fill(); }
      } else if (kind === 3) {                     // a cactus
        drawCactus(fx - w / 2, ground, Math.max(w * 1.6, 10), oh, dark);
      } else if (kind === 5) {                     // the dense cactus field
        const n = Math.max(1, Math.round(ww / 0.42)), cwid = w / n;
        for (let k = 0; k < n; k++) drawCactus(fx - (k + 0.5) * cwid, ground, cwid * 1.5, oh * (k % 2 ? 0.85 : 1), dark);
      } else if (kind === 4) {                     // crates resting on a cloud
        const bh = 0.5 * sy, n = Math.max(1, Math.round(ww / 0.8)), bw = w / n;
        drawCloud(fx - w / 2, ground - oh + bh + 0.12 * sy, w + 0.4 * sx, Math.max(5, 0.26 * sy), dark);
        for (let k = 0; k < n; k++) drawCrate(fx - (k + 1) * bw, ground - oh, bw, bh);
      } else {
        const n = kind === 1 ? 2 : 1, bw = w / n;
        for (let k = 0; k < n; k++) drawCrate(fx - (k + 1) * bw, ground - oh, bw, oh);   // crates
      }
    }
    // the runner
    const size = Math.max(16, Math.min(1.05 * sy, 1.3 * sx));
    const yy = ground - (own ? (myRun ? myRun.y : 0) : laneY(p, t)) * sy - size;
    const blink = hits.some(x => t >= x && t < x + JU.INVULN) && Math.floor(t * 10) % 2 === 0;
    ctx.globalAlpha = isOut ? 0.35 : blink ? 0.25 : 1;
    ctx.fillStyle = "rgba(0,0,0,.18)";
    ctx.beginPath(); ctx.ellipse(avX, ground + 2, size * 0.38, size * 0.1, 0, 0, Math.PI * 2); ctx.fill();
    const img = avatarImg(p);
    if (img && img.complete && img.naturalWidth) ctx.drawImage(img, avX - size / 2, yy, size, size);
    else {
      ctx.font = Math.round(size * 0.86) + "px system-ui, 'Apple Color Emoji', 'Noto Color Emoji', sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "alphabetic"; ctx.fillStyle = "#000";
      ctx.fillText(p.bot ? (p.emoji || "🤖") : "🙂", avX, yy + size * 0.85);
    }
    ctx.globalAlpha = 1;
    // name and lives
    const fs = Math.max(11, Math.min(15, lh * 0.2));
    ctx.font = "700 " + fs + "px system-ui, sans-serif"; ctx.textBaseline = "top"; ctx.textAlign = "left";
    ctx.fillStyle = "rgba(255,255,255,.75)";
    const label = (own ? "⭐ " : "") + p.name;
    const lw = Math.min(cw * 0.55, ctx.measureText(label).width + 10);
    rr(8, y + 4, lw, fs + 6, 6); ctx.fill();
    ctx.fillStyle = "#1f2937"; ctx.fillText(label, 13, y + 7, lw - 10);
    const hearts = isOut ? "💥" : "❤️".repeat(Math.max(0, lives0() - lost)) + "🤍".repeat(Math.min(lives0(), lost));
    ctx.textAlign = "right"; ctx.font = fs + "px system-ui, sans-serif";
    ctx.fillText(hearts, cw - 8, y + 6);
    if (isOut) {
      ctx.fillStyle = "rgba(15,23,42,.45)"; ctx.fillRect(0, y, cw, lh);
      ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.font = "800 " + Math.max(14, Math.min(26, lh * 0.22)) + "px system-ui, sans-serif";
      ctx.fillText("💥 " + I18N.tr(T("Out!")) + " · " + Math.floor(juDist(out)) + " m", cw / 2, y + lh / 2);
    }
    ctx.restore();
  }
  function frame() {
    if (!alive || !box.isConnected) return stop();
    raf = requestAnimationFrame(frame);
    if (!canvas || !playing()) return;
    fit();
    const t = gameT();
    ensureCourse(Math.max(0, t) + 2);
    if (st.joined) stepMine(t);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    const ls = lanes();
    for (const L of ls) drawLane(L, L.own ? Math.max(0, t) : Math.max(0, t - JU_DELAY));
    if (ls.length === 1 && ls[0].y > 90) {          // alone: the distance big above the lane
      ctx.fillStyle = "rgba(91,91,214,.22)"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.font = "900 " + Math.round(Math.min(cw * 0.22, ls[0].y * 0.45)) + "px system-ui, sans-serif";
      ctx.fillText(Math.floor(juDist(myOut != null ? myOut : Math.max(0, t))) + " m", cw / 2, ls[0].y / 2);
    }
    const warn = cloudAt.map(i => course[i][4] - t).find(dt => dt > -0.6 && dt < 3.2);
    if (warn != null && t > 0) {                    // the cloud parcours is coming: a banner over my lane (or the bottom lane)
      const L = ls.find(l => l.own) || ls[ls.length - 1], pulse = 0.85 + 0.15 * Math.sin(t * 9);
      const fs = Math.max(13, Math.min(20, cw * 0.05)), bw = Math.min(cw - 24, fs * 17), bh = fs * 2.9;
      const bx = (cw - bw) / 2, by = L.y + Math.max(fs * 1.9, L.h * 0.2);
      ctx.globalAlpha = pulse;
      ctx.fillStyle = juDark() ? "rgba(30,41,59,.92)" : "rgba(255,255,255,.93)"; ctx.strokeStyle = "#f59f00"; ctx.lineWidth = 3;
      rr(bx, by, bw, bh, 12); ctx.fill(); ctx.stroke();
      ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = juDark() ? "#f8fafc" : "#1f2937";
      ctx.font = "900 " + fs + "px system-ui, sans-serif";
      ctx.fillText("☁️ " + I18N.tr(T("Cloud course ahead!")), cw / 2, by + bh * 0.33, bw - 12);
      ctx.font = "700 " + Math.round(fs * 0.8) + "px system-ui, sans-serif";
      ctx.fillText(I18N.tr(T("Jump from crate to crate!")), cw / 2, by + bh * 0.72, bw - 12);
      ctx.globalAlpha = 1;
    }
    if (t < 0.7) {                                  // the countdown
      const txt = t < 0 ? String(Math.ceil(-t)) : I18N.tr(T("Go!"));
      ctx.fillStyle = "rgba(255,255,255,.8)"; ctx.strokeStyle = "rgba(15,23,42,.6)"; ctx.lineWidth = 6;
      ctx.font = "900 " + Math.round(Math.min(cw, ch) * 0.22) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.strokeText(txt, cw / 2, ch / 2); ctx.fillStyle = "#1f2937"; ctx.fillText(txt, cw / 2, ch / 2);
    }
    if (livesEl) livesEl.textContent = st.joined ? "❤️".repeat(myLives()) + "🤍".repeat(Math.min(lives0(), myHits.size)) : "";
    if (distEl) distEl.textContent = Math.floor(juDist(st.joined && myOut != null ? myOut : Math.max(0, t))) + " m";
    if (jumpBtn) jumpBtn.disabled = !st.joined || myOut != null;
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, st.players.map(p => [p.id, p.place]), st.phase === "lobby" ? st.players.length : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    canvas = null; jumpBtn = null; livesEl = null; distEl = null;
    if (!st) return show(h("section.card.center", h("div.big-ic", JU_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests, End (whoever leads), language – only the main action (Start) stays as a big button
    const menu = gameMenu({ rules: () => jumpRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "jump" : null,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", JU_ICON, " ", juName())));
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))) : null;
    if (st.phase === "done") return show(head, result());
    if (st.phase === "lobby") {
      if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), lobbySeats(), host);
      return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
        h("p.muted", T("Everybody joins on their own device.")), lobbySeats(),
        st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", juCoins(st.rewards))) : null), host);
    }
    // the race
    canvas = h("canvas.ju-canvas");
    ctx = canvas.getContext("2d");
    wrap = h("div.ju-wrap", canvas);
    canvas.addEventListener("pointerdown", e => {   // a tap on my lane jumps too
      if (!st || !st.joined) return;
      const r = canvas.getBoundingClientRect(), L = lanes().find(l => l.own);
      if (L && e.clientY - r.top >= L.y) { e.preventDefault(); jump(); }
    });
    livesEl = h("span.ju-lives"); distEl = h("strong.ju-dist", "0 m");
    const bar = h("div.ju-bar", livesEl, distEl, st.joined && st.best ? h("span.ju-best", "🏆 ", I18N.tr(T("Your best: {0}")).replace("{0}", st.best + " m")) : h("span"));
    jumpBtn = st.joined ? h("button.ju-jump", { type: "button", onpointerdown: e => { e.preventDefault(); jump(); }, onclick: e => { if (e.detail === 0) jump(); } },
      h("span.ju-arrow", "⤒"), " ", T("Jump!")) : h("p.muted.center", T("The game has already started"));
    show(close, head, bar, wrap, jumpBtn, host);
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
      try { await api("community/jump/start", { method: "POST", body: { solo: true } }); setState(await req("")); draw(true); } catch (e) { toast(e.message, "bad"); }
    } }, "🔄 ", T("Play again")) : null;
    return h("section.card.center.ju-result",
      st.players.length > 1 ? h("h2", "🏆 ", C(winners)) : h("h2", JU_ICON, " ", (m.score || 0) + " m"),
      m.record ? h("p.ju-record", "🎉 ", T("New personal best!")) : null,
      st.joined && st.best ? h("p.small.muted", "🏆 ", I18N.tr(T("Your best: {0}")).replace("{0}", (st.best || 0) + " m")) : null,
      st.players.length > 1 ? h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".ju-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 30), C(p.name, "strong.grow"),
        h("span", (p.score || 0) + " m"), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))) : null,
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on || st.players.length < 2 ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", again, h("button.btn" + (again ? ".ghost" : ""), { onclick: back }, T("Back"))));
  }
  (async () => { try { setState(await req("")); } catch {} draw(true); poll(); })();
  raf = requestAnimationFrame(frame);
}

async function jumpView() {
  const box = h("div.ju-live");
  screen("games", box);
  jumpLive(box, S.profile, () => go("games"));
}

async function jumpFamilyCard() {
  const c = S.me && S.me.community, g = c && c.jump;
  return h("section.card.quiz-card", h("h2", JU_ICON, " ", juName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("jump") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Jump over the obstacles in your own lane – everybody gets the same ones, and it gets faster. The last one running wins coins at the family table.")),
         h("div.row.wrap", h("button.btn", { onclick: () => jumpStartDialog(true, () => go("jump")) }, JU_ICON, " ", T("Alone")),
           h("button.btn.ghost", { onclick: () => jumpStartDialog(false, () => go("jump")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}
