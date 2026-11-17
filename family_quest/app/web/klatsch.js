// «Klatsch den Beat» – a live rhythm game (familyquest/klatsch.py): every round the app plays a beat (own sounds,
// made here with WebAudio: kick, clap, hi-hat), then everybody claps it back on the big clap button – at the same time,
// each on their own device. A round on the shared game clock: count-in (4 clicks) → listen (the pattern sounds, its
// dots appear on the bar) → clap (the dots stay, a playhead sweeps over them – clap when it reaches a dot) → results.
// The app knows the server clock (offset from the answers' `now`, the shortest round trip counts), subtracts the delay
// of this device (calibration: tap along to 8 clicks, kept in localStorage) and reports its taps as game times; the
// server judges them (perfect / good / miss) and ranks everybody the same way.
// klatschLive(box, me, back) runs a table (family or alone), klatschStartDialog(solo, onStarted) sets the rules.
// Uses botPicker() from cards.js and guestInvite() from community.js.
"use strict";

const KB_ICON = "👏";
const kbName = () => T("Klatsch den Beat");
const kbCoins = list => list.join(" / ") + " 🪙";
const KB_PERFECT = 0.06, KB_GOOD = 0.13;     // the same windows as klatsch.py (the server judges, the app shows)

// ---------------------------------------------------------------- the device delay (calibration)
const KbLat = {
  get() { try { const v = parseFloat(localStorage.getItem("fq.klatsch.lat")); return Number.isFinite(v) ? v : null; } catch { return null; } },
  set(ms) { try { if (ms == null) localStorage.removeItem("fq.klatsch.lat"); else localStorage.setItem("fq.klatsch.lat", String(Math.round(ms))); } catch {} },
  ms() { return this.get() || 0; },
};

// ---------------------------------------------------------------- the drum machine (WebAudio, no sound files)
const KbAudio = {
  ctx: null, noise: null,
  get muted() { try { return localStorage.getItem("fq.klatsch.mute") === "1"; } catch { return false; } },
  set muted(v) { try { localStorage.setItem("fq.klatsch.mute", v ? "1" : "0"); } catch {} },
  ensure() {                                   // after a tap / click (browsers allow audio only then)
    try {
      if (!this.ctx) {
        this.ctx = (typeof Sound !== "undefined" && Sound.ctx) || new (window.AudioContext || window.webkitAudioContext)();
        if (typeof Sound !== "undefined") Sound.ctx = this.ctx;
      }
      if (this.ctx.state === "suspended") this.ctx.resume();
      if (!this.noise) {
        const n = this.ctx.sampleRate, b = this.ctx.createBuffer(1, n, n), d = b.getChannelData(0);
        for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
        this.noise = b;
      }
    } catch {}
    return this.ctx;
  },
  ready() { return !!(this.ctx && this.ctx.state === "running"); },
  // the audio time at which a sound is heard at this performance time (seconds) – null: too late
  at(perfS) {
    const c = this.ctx;
    if (!c) return null;
    let a;
    const ts = c.getOutputTimestamp ? c.getOutputTimestamp() : null;
    if (ts && ts.contextTime > 0 && ts.performanceTime > 0) a = ts.contextTime + (perfS - ts.performanceTime / 1000);
    else a = c.currentTime + (perfS - performance.now() / 1000) - (c.outputLatency || c.baseLatency || 0);
    if (a < c.currentTime - 0.03) return null;
    return Math.max(a, c.currentTime);
  },
  _noise(t, dur, filter, freq, vol, q) {
    const c = this.ctx, s = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
    s.buffer = this.noise; f.type = filter; f.frequency.value = freq; if (q) f.Q.value = q;
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.002); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(f).connect(g).connect(c.destination); s.start(t, Math.random() * 0.5); s.stop(t + dur + 0.02);
  },
  play(kind, t, vol = 1) {
    if (!this.ctx || this.muted || t == null) return;
    try {
      const c = this.ctx;
      if (kind === "kick") {
        const o = c.createOscillator(), g = c.createGain();
        o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(45, t + 0.18);
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.9 * vol, t + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.32);
        o.connect(g).connect(c.destination); o.start(t); o.stop(t + 0.35);
      } else if (kind === "hat") {
        this._noise(t, 0.05, "highpass", 7000, 0.22 * vol);
      } else if (kind === "clap") {                // three quick bursts and a tail – a hand clap
        for (const [d, v] of [[0, 0.5], [0.011, 0.45], [0.022, 0.5]]) this._noise(t + d, 0.03, "bandpass", 1300, v * vol, 1.2);
        this._noise(t + 0.03, 0.14, "bandpass", 1100, 0.35 * vol, 0.9);
      } else if (kind === "click") {                // the count-in / calibration click
        const o = c.createOscillator(), g = c.createGain();
        o.type = "square"; o.frequency.value = vol > 1 ? 1760 : 1320;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.18, t + 0.002); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
        o.connect(g).connect(c.destination); o.start(t); o.stop(t + 0.06);
      }
    } catch {}
  },
};
function kbBuzz(ms) { try { if (navigator.vibrate) navigator.vibrate(ms); } catch {} }
function kbTapTime(e) {                         // the moment of the touch (performance clock, seconds)
  const now = performance.now();
  return (e && typeof e.timeStamp === "number" && e.timeStamp > 0 && Math.abs(now - e.timeStamp) < 1000 ? e.timeStamp : now) / 1000;
}

// ---------------------------------------------------------------- calibration: tap along to 8 clicks
function klatschCalibrate(onDone) {
  KbAudio.ensure();
  const BEAT = 0.6, LEAD = 4, N = 8;
  let t0 = null, taps = [], raf = 0, done = false;
  const info = h("p.center.kb-cal-info", T("Tap the button along with the 8 clicks after the 4 count-in clicks."));
  const dot = h("div.kb-cal-dot");
  const count = h("div.kb-cal-count", "");
  const cur = KbLat.get();
  const res = h("p.center.small.muted", cur != null ? I18N.tr(T("Delay of this device: {0} ms")).replace("{0}", Math.round(cur)) : T("Not calibrated yet."));
  const pad = h("button.kb-clap.kb-cal-pad", { type: "button", onpointerdown: e => { e.preventDefault(); tap(kbTapTime(e)); } }, KB_ICON);
  const startBtn = h("button.btn", { onclick: () => begin() }, "▶ ", T("Start"));
  const m = modal(h("div.form.kb-cal", h("h2", "🎚️ ", T("Calibrate")),
    h("p.small.muted", T("Phones and headphones play sounds a little late. Tap along once – the game subtracts this delay on this device.")),
    h("div.kb-cal-stage", dot, count), info, pad, res,
    h("div.row", startBtn, h("button.btn.ghost", { onclick: () => { KbLat.set(0); res.textContent = I18N.tr(T("Delay of this device: {0} ms")).replace("{0}", 0); } }, T("Reset")),
      h("button.btn.ghost", { onclick: () => close() }, T("Close")))));
  function close() { done = true; cancelAnimationFrame(raf); m.close(); if (onDone) onDone(); }
  function begin() {
    KbAudio.ensure();
    taps = []; t0 = performance.now() / 1000 + 0.6;
    for (let k = 0; k < LEAD + N; k++) KbAudio.play("click", KbAudio.at(t0 + k * BEAT), k < LEAD ? 1 : 2);
    info.textContent = I18N.tr(T("Listen … then tap along!"));
    startBtn.disabled = true;
    cancelAnimationFrame(raf); raf = requestAnimationFrame(frame);
  }
  function tap(p) {
    KbAudio.ensure(); kbBuzz(12);
    pad.classList.remove("pop"); void pad.offsetWidth; pad.classList.add("pop");
    if (t0 != null) taps.push(p);
  }
  function frame() {
    if (done || !m || !document.body.contains(dot)) return;
    const t = performance.now() / 1000 - t0;
    const k = Math.floor(t / BEAT), f = t / BEAT - k;
    dot.style.opacity = t >= 0 && k < LEAD + N ? String(Math.max(0.15, 1 - f * 2.2)) : "0.15";
    dot.classList.toggle("lead", k < LEAD);
    count.textContent = t >= 0 && k < LEAD ? String(k + 1) : t >= 0 && k < LEAD + N ? "👏 " + (k - LEAD + 1) : "";
    if (t < (LEAD + N) * BEAT + 0.5) { raf = requestAnimationFrame(frame); return; }
    // the result: every click takes the nearest tap within 0.3 s – the median of the differences
    const d = [];
    for (let k2 = LEAD; k2 < LEAD + N; k2++) {
      const c = t0 + k2 * BEAT;
      let best = null;
      for (const p of taps) if (Math.abs(p - c) <= 0.3 && (best == null || Math.abs(p - c) < Math.abs(best))) best = p - c;
      if (best != null) d.push(best);
    }
    startBtn.disabled = false;
    if (d.length < 5) { info.textContent = I18N.tr(T("Too few taps – try again.")); return; }
    d.sort((a, b) => a - b);
    const ms = Math.max(-150, Math.min(350, d[Math.floor(d.length / 2)] * 1000));
    KbLat.set(ms);
    info.textContent = I18N.tr(T("Done!"));
    res.textContent = I18N.tr(T("Delay of this device: {0} ms")).replace("{0}", Math.round(ms));
  }
}

function klatschRulesView(r, rewards) {
  r = r || {};
  const items = [
    T("Every round: listen to the beat (the dots light up), then clap it back on the big button – a playhead runs over the dots, clap when it reaches one."),
    I18N.tr(T("{0} rounds – it gets faster (80 to 140 BPM), with syncopes and pauses.")).replace("{0}", r.rounds || 6),
    T("Perfect (±60 ms) 100 points, good (±130 ms) 50 – an extra clap costs 25. Everybody plays at the same time and is judged by the server the same way."),
    T("Phones play sounds a little late: calibrate once (🎚️) – the delay is kept on this device."),
    T("Most points win. Alone: your accuracy of a full game is your personal best."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", kbCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function klatschStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/klatsch/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(r.bots ?? 0, [0, 1, 2, 3, 4, 5, 6, 7].map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const rounds = sel(r.rounds || 6, [5, 6, 7, 8].map(n => [n, String(n)]));
  const picker = botPicker(1400);
  const speed = picker.el.querySelector(".bot-speed");             // bots clap by their level – no reaction time here
  if (speed) speed.remove();
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", kbCoins(rw)), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const lat = KbLat.get();
  const m = modal(h("div.form", h("h2", KB_ICON, " ", kbName(), solo ? " – " + I18N.tr(T("Alone")) : ""),
    h("p.small.muted", T("Listen to the beat, then clap it back in time – everybody at once on their own device. It gets faster every round!")),
    h("div.grid2", h("label.field", T("Rounds"), rounds), h("label.field", solo ? T("Practice bots") : T("Bots"), bots)),
    h("label.field", T("Bots play"), level),
    solo ? null : h("p.small.muted", T("1 to 8 players: the family joins on their own devices, guests via QR code.")),
    picker.el,
    h("div.row.wrap", h("button.btn.ghost.small", { type: "button", onclick: () => klatschCalibrate() }, "🎚️ ", T("Calibrate")),
      h("span.small.muted", lat != null ? I18N.tr(T("Delay of this device: {0} ms")).replace("{0}", Math.round(lat)) : T("Not calibrated yet."))),
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      KbAudio.ensure();
      const body = { solo, bots: +bots.value, level: level.value, rounds: +rounds.value, bot_ids: picker.ids() };
      try { await api("community/klatsch/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("klatsch", bots, level, picker.el);          // parent area › Games: without bots
}

function klatschLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, raf = 0, sched = 0, syncing = false;
  let offset = null, bestRtt = 1e9;              // server clock − performance clock (seconds)
  let lastTry = 0, gameKey = "", done = new Set(), myTaps = {}, sent = {}, claimed = {}, judged = {}, flash = null, syncAgain = false;
  let el = {};                                    // the parts of the play screen, updated every frame
  const myId = String(me.id);
  box.classList.add("kb-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => {
    alive = false; clearTimeout(timer); clearInterval(sched); cancelAnimationFrame(raf);
    box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open");
    window.removeEventListener("keydown", onKey);
  };
  window.addEventListener("hashchange", stop, { once: true });
  const nowS = () => performance.now() / 1000;
  const gameT = (p = nowS()) => (st && offset != null ? p + offset - st.t0 : -99);
  const perfOf = g => g + st.t0 - offset;
  const playing = () => st && st.phase === "play" && st.status !== "done";
  const rounds = () => (st && st.rounds) || [];
  const times = rd => { const bar = 240 / rd.bpm; return [rd.start, rd.start + bar, rd.start + 2 * bar, rd.start + 3 * bar, bar]; };
  const notesAt = (rd, from) => rd.notes.map(x => from + x * 60 / rd.bpm / 4);

  function clock(s, t1, t2) {                    // the server's clock: the answer with the shortest way counts
    if (!s || typeof s.now !== "number") return;
    const rtt = t2 - t1;
    if (rtt <= bestRtt * 1.15 || offset == null) { bestRtt = Math.min(bestRtt, rtt); offset = s.now - (t1 + t2) / 2; }
  }
  const req = async (path, opts) => {
    const t1 = nowS();
    const s = await api("community/klatsch" + path, opts);
    clock(s, t1, nowS());
    return s;
  };
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    KbAudio.ensure();
    try { setState(await req("/" + path, { method: "POST", body: body || {} })); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); }
  };
  function setState(s) {
    if (s && !Array.isArray(s.players)) s = null;
    st = s;
    if (!st || !st.t0) return;
    const key = st.game + ":" + st.t0;
    if (key !== gameKey) { gameKey = key; done = new Set(); myTaps = {}; sent = {}; claimed = {}; judged = {}; cheered = false; }
  }
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { const s = await req(""); if (!busy && !syncing) { setState(s); draw(); } } catch {}
    timer = setTimeout(poll, playing() ? 400 : 1000);
  }
  async function sync(i) {                       // my taps of round i to the server (all of them – it keeps each once)
    if (!playing() || !st.joined) return;
    if (syncing) { syncAgain = i; return; }
    syncing = true;
    const taps = (myTaps[i] || []).slice();
    try {
      const s = await req("/sync", { method: "POST", body: { round: i, taps } });
      sent[i] = taps.length;
      setState(s); draw();
    } catch {}
    syncing = false;
    if (syncAgain !== false) { const j = syncAgain; syncAgain = false; sync(j); }
  }

  // ---------- the beat: every sound a moment ahead on the audio clock
  function events(rd) {                          // [game time, sound, volume] of a round
    const [s, listen, clap, , bar] = times(rd), beat = bar / 4, out = [];
    for (let k = 0; k < 4; k++) out.push([s + k * beat, "click", k === 0 ? 2 : 1]);
    for (const from of [listen, clap]) {
      for (let k = 0; k < 4; k++) { if (k % 2 === 0) out.push([from + k * beat, "kick", 0.9]); out.push([from + k * beat, "hat", from === clap ? 0.6 : 0.8]); }
      if (from === listen) for (let k = 0; k < 4; k++) out.push([from + (k + 0.5) * beat, "hat", 0.45]);
    }
    for (const n of notesAt(rd, listen)) out.push([n, "clap", 1]);
    return out;
  }
  function schedule() {
    if (!alive || !playing() || offset == null || !KbAudio.ctx) return;
    const t = gameT();
    for (const rd of rounds()) {
      const [s, , , end] = times(rd);
      if (end < t || s > t + 1) continue;
      events(rd).forEach(([g, kind, vol], k) => {
        const key = rd.i + ":" + k;
        if (done.has(key) || g > t + 0.3) return;
        done.add(key);
        if (g < t - 0.03) return;                  // missed (the tab was asleep)
        KbAudio.play(kind, KbAudio.at(perfOf(g)), vol);
      });
    }
  }

  // ---------- my claps
  function clap(e) {
    KbAudio.ensure();
    const p = kbTapTime(e);
    try { KbAudio.play("clap", KbAudio.ctx && KbAudio.ctx.currentTime, 0.8); } catch {}
    kbBuzz(15);
    if (el.clap) { el.clap.classList.remove("pop"); void el.clap.offsetWidth; el.clap.classList.add("pop"); }
    if (!playing() || !st.joined || offset == null) return;
    const g = gameT(p) - KbLat.ms() / 1000;
    const rd = rounds().find(r => { const [, , c, end] = times(r); return g >= c - 0.3 && g <= end + 0.3; });
    if (!rd || rd.i < (st.scored || 0)) return;
    const [, , c, end] = times(rd);
    if (gameT() > end + (st.grace || 1)) return;
    const list = myTaps[rd.i] = myTaps[rd.i] || [];
    if (list.length >= 48) return;
    list.push(Math.round(g * 10000) / 10000);
    // my own quick verdict (the server's counts): the nearest free note
    const notes = notesAt(rd, c), cl = claimed[rd.i] = claimed[rd.i] || {};
    let best = -1;
    notes.forEach((n, k) => { if (!cl[k] && Math.abs(g - n) <= KB_GOOD && (best < 0 || Math.abs(g - n) < Math.abs(g - notes[best]))) best = k; });
    if (best >= 0) {
      const d = g - notes[best];
      cl[best] = Math.abs(d) <= KB_PERFECT ? "perfect" : "good";
      flash = { txt: cl[best] === "perfect" ? T("Perfect!") : d < 0 ? T("Good – a bit early") : T("Good – a bit late"), cls: cl[best], at: nowS() };
    } else flash = { txt: T("Too much!"), cls: "extra", at: nowS() };
    sync(rd.i);
  }
  function onKey(e) {
    if (!alive || !box.isConnected) return;
    if ((e.code === "Space" || e.key === " ") && !e.repeat && !/^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test((e.target && e.target.tagName) || "")) {
      e.preventDefault(); clap(e);
    }
  }
  window.addEventListener("keydown", onKey);

  // ---------- one frame: the phase, the dots, the playhead, the pulse
  function phaseAt(t) {
    if (t < 0) return { ph: "ready", i: 0 };
    const rs = rounds();
    for (const rd of rs) {
      const [s, listen, clap, end] = times(rd);
      if (t < s) return { ph: "results", i: rd.i - 1, rd: rs.find(r => r.i === rd.i - 1), next: rd };
      if (t < listen) return { ph: "count", i: rd.i, rd };
      if (t < clap) return { ph: "listen", i: rd.i, rd };
      if (t < end) return { ph: "clap", i: rd.i, rd };
    }
    const last = rs[rs.length - 1];
    return { ph: "results", i: last ? last.i : 0, rd: last, next: null };
  }
  function frame() {
    if (!alive || !box.isConnected) return stop();
    raf = requestAnimationFrame(frame);
    if (!el.stage || !playing()) return;
    schedule();
    const t = gameT(), P = phaseAt(t), rd = P.rd;
    let label = "", sub = "", head = null, beatPos = null;
    if (P.ph === "ready") { label = t > -50 ? String(Math.max(1, Math.ceil(-t))) : "…"; sub = T("Get ready!"); }
    if (rd) {
      const [s, listen, clap, end, bar] = times(rd);
      if (P.ph === "count") { const k = Math.floor((t - s) / (bar / 4)); label = String(k + 1); sub = T("Count-in"); beatPos = (t - s) / (bar / 4); }
      if (P.ph === "listen") { label = "👂"; sub = T("Listen!"); head = (t - listen) / bar; beatPos = (t - listen) / (bar / 4); }
      if (P.ph === "clap") { label = KB_ICON; sub = st.joined ? T("Your turn – clap!") : T("Clap!"); head = (t - clap) / bar; beatPos = (t - clap) / (bar / 4); }
      // the dots: in the listen bar they appear as they sound, in the clap bar they stay
      const sig = rd.i + ":" + rd.notes.join(",");
      if (el.track.dataset.sig !== sig) {
        el.track.dataset.sig = sig;
        el.dots = rd.notes.map(x => h("span.kb-dot", { style: { left: (x / 16 * 100) + "%" } }));
        el.notes.replaceChildren(...el.dots);
      }
      const cl = claimed[rd.i] || {}, res = P.ph === "results" ? myResult(rd.i) : null;
      el.dots.forEach((d, k) => {
        const tn = listen + rd.notes[k] * bar / 16;
        const on = P.ph === "clap" || P.ph === "results" || (P.ph === "listen" && t >= tn - 0.02);
        let mark = "";
        if (res && res.d) mark = res.d[k] == null ? "miss" : Math.abs(res.d[k]) <= KB_PERFECT * 1000 ? "perfect" : "good";
        else if (cl[k]) mark = cl[k];
        else if (st.joined && (P.ph === "clap" || P.ph === "results") && t > clap + rd.notes[k] * bar / 16 + KB_GOOD) mark = "late";
        d.className = "kb-dot" + (on ? " on" : "") + (mark ? " " + mark : "") + (P.ph === "listen" && Math.abs(t - tn) < 0.12 ? " ping" : "");
      });
      el.stage.dataset.ph = P.ph;
      if (P.ph === "results") {
        const r = myResult(rd.i);
        label = r ? "+" + r.pts : "…";
        sub = r ? I18N.tr(T("{0} perfect · {1} good · {2} missed")).replace("{0}", r.p).replace("{1}", r.g).replace("{2}", r.m)
          + (r.x ? " · " + I18N.tr(T("{0} too much")).replace("{0}", r.x) : "") : T("Counting …");
        if (!st.joined) sub = T("Round over");
        if (P.next) { const w = P.next.start - t; if (w < 2.5) sub = I18N.tr(T("Next round in {0} s")).replace("{0}", Math.max(1, Math.ceil(w))); }
      }
    } else el.stage.dataset.ph = P.ph;
    el.label.textContent = label; el.sub.textContent = I18N.tr(sub);
    el.head.style.display = head == null ? "none" : "";
    if (head != null) el.head.style.left = (Math.min(1, Math.max(0, head)) * 100) + "%";
    const pulse = beatPos == null || beatPos < 0 ? 0 : Math.max(0, 1 - (beatPos % 1) * 3.2);
    el.stage.style.setProperty("--kb-pulse", pulse.toFixed(3));
    el.stage.classList.toggle("down", beatPos != null && beatPos >= 0 && Math.floor(beatPos) % 4 === 0 && pulse > 0);
    const ri = P.ph === "ready" ? 0 : P.i;
    el.round.textContent = I18N.tr(T("Round {0} of {1}")).replace("{0}", Math.min(st.n_rounds, ri + 1)).replace("{1}", st.n_rounds) + (rd || P.next ? " · " + (rd || P.next).bpm + " BPM" : "");
    if (flash && nowS() - flash.at < 0.7) { el.judge.textContent = I18N.tr(flash.txt); el.judge.className = "kb-judge " + flash.cls; }
    else el.judge.textContent = "";
    if (el.clap) el.clap.classList.toggle("go", P.ph === "clap");
    // the last taps of a clap bar: once more to the server right after the bar
    if (rd && P.ph === "results" && st.joined && myTaps[rd.i] && sent[rd.i] !== myTaps[rd.i].length && !syncing && nowS() - lastTry > 0.5) {
      lastTry = nowS(); sync(rd.i);
    }
  }
  function myResult(i) {
    const m = st && st.players.find(p => p.id === myId);
    if (!m || !st.scored || st.scored <= i || !m.last) return null;
    return st.scored === i + 1 ? m.last : { pts: (m.pts || [])[i] || 0, p: "–", g: "–", m: "–", x: 0 };
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, st.scored, st.players.map(p => [p.id, p.place, p.total]), st.phase === "lobby" ? st.players.length : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) { el = {}; return show(h("section.card.center", h("div.big-ic", KB_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back")))); }
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests, calibrate, the beat's sound, End (whoever leads), language – only Start stays as a big button
    const menu = gameMenu({ rules: () => klatschRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "klatsch" : null,
      actions: [
        { ic: "🎚️", label: T("Calibrate"), hidden: st.phase === "done", onclick: () => klatschCalibrate() },
        { get ic() { return KbAudio.muted ? "🔇" : "🔊"; }, get label() { return KbAudio.muted ? T("Beat sound off") : T("Beat sound on"); },
          hidden: st.phase === "done", onclick: () => { KbAudio.muted = !KbAudio.muted; } },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
          onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", KB_ICON, " ", kbName())));
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))) : null;
    if (st.phase === "done") { el = {}; return show(head, result()); }
    const calHint = KbLat.get() == null ? h("p.small.center", h("button.btn.ghost.small", { onclick: () => klatschCalibrate() }, "🎚️ ", T("Calibrate")), " ",
      h("span.muted", T("Not calibrated yet."))) : null;
    if (st.phase === "lobby") {
      el = {};
      if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), lobbySeats(), host);
      return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
        h("p.muted", T("Everybody joins on their own device – turn the sound on!")), lobbySeats(), calHint,
        st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", kbCoins(st.rewards))) : null), host);
    }
    // the game – the stage stays, only the ranking and the bar are made anew
    if (!el.stage) {
      el.label = h("div.kb-label"); el.sub = h("div.kb-sub"); el.judge = h("div.kb-judge");
      el.notes = h("div.kb-notes"); el.head = h("div.kb-head");
      el.track = h("div.kb-track", ...[0, 1, 2, 3].map(k => h("span.kb-beat", { style: { left: (k * 25) + "%" } })), el.notes, el.head);
      el.stage = h("div.kb-stage", h("div.kb-pulse"), el.label, el.sub, el.track, el.judge);
      el.round = h("span.kb-round"); el.pts = h("strong.kb-pts");
      el.rank = h("ol.kb-rank");
      el.clap = st.joined ? h("button.kb-clap", { type: "button", onpointerdown: e => { e.preventDefault(); clap(e); }, onclick: e => { if (e.detail === 0) clap(e); } },
        h("span.kb-hands", KB_ICON), h("span.kb-clap-txt", T("Clap!"))) : h("p.muted.center", T("The game has already started"));
      el.bar = h("div.kb-bar", el.round, el.pts);
      show(close, head, el.bar, el.stage, el.rank, el.clap, host);
      if (!KbAudio.ready()) {                     // a reload in the middle: the sound needs one tap
        const unlock = h("button.btn.kb-unlock", { onclick: () => { KbAudio.ensure(); unlock.remove(); } }, "🔊 ", T("Tap for sound"));
        el.stage.append(unlock);
      }
    } else show(close, head, el.bar, el.stage, el.rank, el.clap, host);
    const m = st.players.find(p => p.id === myId);
    el.pts.textContent = m ? m.total + " " + I18N.tr(T("points")) : "";
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99) || b.total - a.total);
    el.rank.replaceChildren(...ranked.map(p => h("li" + (p.id === myId ? ".kb-me" : ""), h("span.kb-place", (p.place || "–") + "."), seatIcon(p, 22),
      C(p.name, "span.grow.kb-name"), p.last ? h("span.small.muted", "+" + p.last.pts) : null, h("strong", String(p.total)))));
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
      KbAudio.ensure();
      try { await api("community/klatsch/start", { method: "POST", body: { solo: true } }); setState(await req("")); draw(true); } catch (e) { toast(e.message, "bad"); }
    } }, "🔄 ", T("Play again")) : null;
    const acc = p => I18N.tr(T("{0} % on the beat")).replace("{0}", p.acc || 0);
    return h("section.card.center.kb-result",
      st.players.length > 1 ? h("h2", "🏆 ", C(winners)) : h("h2", KB_ICON, " ", (m.total || 0) + " ", T("points")),
      st.joined ? h("p.kb-acc", acc(m)) : null,
      m.record ? h("p.ju-record", "🎉 ", T("New personal best!")) : null,
      st.joined && st.best ? h("p.small.muted", "🏆 ", I18N.tr(T("Your best: {0}")).replace("{0}", st.best + " %")) : null,
      st.players.length > 1 ? h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".kb-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 30), C(p.name, "strong.grow"),
        h("span", p.total + " · " + (p.acc || 0) + " %"), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))) : null,
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on || st.players.length < 2 ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", again, h("button.btn" + (again ? ".ghost" : ""), { onclick: back }, T("Back"))));
  }
  (async () => { try { setState(await req("")); } catch {} draw(true); poll(); })();
  sched = setInterval(schedule, 50);
  raf = requestAnimationFrame(frame);
}

async function klatschView() {
  const box = h("div.kb-live");
  screen("games", box);
  klatschLive(box, S.profile, () => go("games"));
}

async function klatschFamilyCard() {
  const c = S.me && S.me.community, g = c && c.klatsch;
  return h("section.card.quiz-card", h("h2", KB_ICON, " ", kbName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => { KbAudio.ensure(); go("klatsch"); } }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("A rhythm game for everybody at once: listen to the beat, then clap it back in time on your phone. It gets faster every round – the best clappers win coins at the family table.")),
         h("div.row.wrap", h("button.btn", { onclick: () => klatschStartDialog(true, () => go("klatsch")) }, KB_ICON, " ", T("Alone")),
           h("button.btn.ghost", { onclick: () => klatschStartDialog(false, () => go("klatsch")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}
