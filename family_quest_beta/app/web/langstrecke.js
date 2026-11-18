// «24h Endurance» (24-Stunden-Rennen) – a live team endurance race on the fictional «Circuit des Tannes»
// (familyquest/langstrecke.py). Teams are racing stables with one car each; the roles (driver, pit crew, race
// engineer) rotate at every pit stop, each person on their own phone. The driver steers on three lanes (swipe /
// arrow keys) with a throttle lever; the crew does the pit-stop jobs as mini-games (wheel nuts, fuel nozzle, cables or
// screws) while a stopwatch runs; the engineer watches the telemetry and the rain radar and sends radio calls.
// The server simulates every car (the same step function as below) – the driver's app only reports its inputs and
// predicts its own car from the server's snapshot for a smooth picture.
// langstreckeLive(box, me, back) runs a table, langstreckeStartDialog(solo, onStarted) sets the rules.
// Uses botPicker() from cards.js, withoutBots() and guestInvite() from community.js, gameMenu() from shared/ui.js.
"use strict";

const LE_ICON = "🏎️";
const leName = () => I18N.tr(T("24h Endurance"));
const leCoins = list => list.join(" / ") + " 🪙";
const leLapsTxt = n => n + " " + I18N.tr(n === 1 ? T("lap") : T("laps"));
// the car – the same numbers as in langstrecke.py
const LE = { L: 1500, DT: 0.1, VMIN: 10, VMAX: 62, ACC: 9, BRAKE: 22, VLIMP: 18, VDRY: 8, VSC: 26, VSLOW: 16, VBACK: 24,
  HEAT: 1.5, HEAT_JR: 0.8, COOL_AT: 7.4, YELLOW: 75, RED: 90, GRACE: 3, GRACE_JR: 6, COUNTDOWN: 8, HOLD_MIN: 0.5, FILL_RATE: 30 };
LE.FUEL_M = 100 / (7 * LE.L);
LE.WEAR_M = 100 / (12 * LE.L);
const LE_GRAVEL = 0, LE_OIL = 1, LE_SLOW = 2, LE_DEBRIS = 3;

function leRand(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), a | 1) >>> 0;
    t = (((t + Math.imul(t ^ (t >>> 7), t | 61)) >>> 0) ^ t) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const _leThings = new Map();
// what lies on the track in this lap: [[x in the lap, lane, kind], …]
function leThings(seed, lap, jr) {
  const key = seed + ":" + lap + ":" + (jr ? 1 : 0);
  let got = _leThings.get(key);
  if (!got) {
    const rnd = leRand((seed + lap * 7919) >>> 0);
    const n = jr ? 2 + Math.floor(rnd() * 2) : 4 + Math.floor(rnd() * 3);
    got = [];
    for (let i = 0; i < n; i++) {
      const x = 160 + (LE.L - 320) * (i + 0.15 + 0.7 * rnd()) / n;
      const lane = Math.floor(rnd() * 3), r = rnd();
      got.push([Math.floor(x * 10 + 0.5) / 10, lane, r < 0.28 ? LE_GRAVEL : r < 0.48 ? LE_OIL : r < 0.76 ? LE_SLOW : LE_DEBRIS]);
    }
    if (_leThings.size > 600) _leThings.clear();
    _leThings.set(key, got);
  }
  return got;
}
function leFog(seed, lap) {
  const rnd = leRand((seed * 3 + lap * 104729 + 17) >>> 0);
  return Math.floor((300 + (LE.L - 600) * rnd()) * 10 + 0.5) / 10;
}
const leInWin = (wins, s) => (wins || []).some(([a, b]) => a <= s && s < b);
const leLaps = d => Math.max(0, Math.floor(d / LE.L));
const leHour = (s, limit) => (15 + 24 * Math.max(0, s) / limit) % 24;
function leDark(s, limit) {
  const hr = leHour(s, limit);
  if (hr >= 21.5 || hr < 5.5) return 1;
  if (hr >= 20.5 && hr < 21.5) return hr - 20.5;
  if (hr >= 5.5 && hr < 6.5) return 6.5 - hr;
  return 0;
}
function leApply(car, c, v) {
  if (c === "l") { if (!car.pit) car.lane = Math.max(0, car.lane - 1); }
  else if (c === "r") { if (!car.pit) car.lane = Math.min(2, car.lane + 1); }
  else if (c === "u") car.thr = Math.max(0, Math.min(10, Math.trunc(v)));
  else if (c === "b") car.box = !(car.eng || car.wheel || car.fuel <= 0) ? Math.max(0, Math.min(2, Math.trunc(v))) : Math.max(1, Math.trunc(v));
}
// one step of DT seconds from game time s – the same as step() in langstrecke.py
function leStep(car, s, seed, jr, rain, sc) {
  const ev = [], DT = LE.DT;
  if (car.out != null) return ev;
  if (car.pit) { car.temp = Math.max(55, car.temp - 8 * DT); return ev; }
  const thr = car.thr, w = car.wear;
  let g = w < 100 ? 1 - 0.3 * (w / 100) * (w / 100) : 0.55;
  if (rain) g *= car.tyre === "r" ? 0.97 : 0.75;
  else if (car.tyre === "r") g *= 0.93;
  let vt = (LE.VMIN + (LE.VMAX - LE.VMIN) * thr / 10) * g;
  if (car.wing) vt *= 0.88;
  if (car.eng || car.wheel) vt = Math.min(vt, LE.VLIMP);
  if (car.fuel <= 0) vt = Math.min(vt, LE.VDRY);
  if (car.slow > 0) { vt = Math.min(vt, LE.VSLOW); car.slow = Math.max(0, car.slow - DT); }
  if (sc) vt = Math.min(vt, LE.VSC);
  let v = car.v;
  v = v < vt ? Math.min(vt, v + LE.ACC * DT) : Math.max(vt, v - LE.BRAKE * DT);
  const d0 = car.d;
  let d1 = d0 + v * DT;
  const heat = (jr ? LE.HEAT_JR : LE.HEAT) * (car.eng ? 0.5 : 1);
  car.temp = Math.min(110, Math.max(50, car.temp + ((thr - LE.COOL_AT) * heat - (rain ? 0.4 : 0)) * DT));
  if (car.temp >= LE.RED && thr > LE.COOL_AT) {
    car.red += DT;
    if (car.red > (jr ? LE.GRACE_JR : LE.GRACE) + 1e-9) {
      car.blow += 1; car.red = 0; car.temp = 70;
      if (car.blow >= 2) { car.out = Math.round((s + DT) * 100) / 100; car.v = 0; ev.push("retired"); return ev; }
      car.eng = 1; car.box = Math.max(car.box, 1); ev.push("blow");
    }
  } else if (car.temp < LE.RED) car.red = 0;
  const dist = d1 - d0, had = car.fuel > 0;
  car.fuel = Math.max(0, car.fuel - dist * LE.FUEL_M * (0.55 + 0.045 * thr));
  if (had && car.fuel <= 0) { car.box = Math.max(car.box, 1); ev.push("dry"); }
  car.wear = Math.min(100, car.wear + dist * LE.WEAR_M * (0.5 + 0.05 * thr) * (car.tyre === "r" && !rain ? 2 : 1));
  for (;;) {
    const things = leThings(seed, car.olap, jr);
    if (car.ob >= things.length) { car.olap += 1; car.ob = 0; if (car.olap * LE.L > d1) break; continue; }
    const [x, lane, kind] = things[car.ob], xa = car.olap * LE.L + x;
    if (xa > d1) break;
    car.ob += 1;
    if (xa <= d0 || sc || lane !== car.lane) continue;
    if (kind === LE_GRAVEL) { car.slow = 1.5; car.wear = Math.min(100, car.wear + 6); ev.push("gravel"); }
    else if (kind === LE_OIL) { car.slow = rain && car.tyre !== "r" ? 3 : 2; car.wear = Math.min(100, car.wear + 3); ev.push("oil"); }
    else if (kind === LE_DEBRIS) { car.wear = Math.min(100, car.wear + 12); if (v > 40) car.wing = 1; ev.push("debris"); }
    else if (v > LE.VBACK + 4) { car.wing = 1; car.wear = Math.min(100, car.wear + 8); car.slow = 1; ev.push(v > 45 ? "bigcrash" : "crash"); v = Math.min(v, 20); }
    else continue;
    car.hits += 1;
  }
  if (car.loose >= 0 && d1 >= car.loose) { car.wheel = 1; car.loose = -1; car.box = Math.max(car.box, 1); ev.push("wheel"); }
  const n0 = Math.floor(d0 / LE.L), n1 = Math.floor(d1 / LE.L);
  if (n1 > n0 && n0 >= 0) {
    const lt = s + DT - car.ls;
    if (car.ls > 0 || n0 >= 1) car.best = !car.best || lt < car.best ? Math.round(lt * 100) / 100 : car.best;
    car.ls = Math.round((s + DT) * 100) / 100;
    ev.push("lap");
    if (car.box) { d1 = n1 * LE.L; v = 0; car.pit = 1; car.boxed = car.box; car.box = 0; ev.push("pit"); }
  } else if (n1 > n0) car.ls = Math.round((s + DT) * 100) / 100;
  car.d = d1; car.v = v;
  return ev;
}

// ---------------------------------------------------------------- the rules, the start
const LE_RADIO = { box: ["📦", T("Box this lap!")], save: ["🧊", T("Save the engine")], push: ["🔥", T("Push!")],
  rain: ["🌧️", T("Rain tyres?")], dry: ["☀️", T("Slicks?")] };
const LE_JOBS = { tyres: ["🛞", T("Tyres")], fuel: ["⛽", T("Fuel")], repair: ["🔧", T("Repair")] };
const LE_ROLES = { driver: ["🏎️", T("Driver")], engineer: ["🎧", T("Race engineer")], crew: ["🔧", T("Pit crew")] };

function langstreckeRulesView(r, rewards) {
  r = r || {};
  const items = [
    I18N.tr(T("24 race hours on the Circuit des Tannes in {0} minutes – through the night and into the next afternoon. The most laps wins.")).replace("{0}", r.minutes || 15),
    T("Every team is a racing stable with one car. Roles rotate at every pit stop: driver, pit crew and – with 4 or more – a race engineer. Nobody drives more than 2 stints in a row."),
    T("Driver: swipe or use the arrow keys to change the lane, set the throttle with the lever. Dodge gravel, oil, debris and slow cars."),
    T("Pushing is faster but heats the engine: yellow = hot, red = lift off within a few seconds! Otherwise the engine is damaged (limp to the pits); a second time and the team retires."),
    T("Pushing also costs tyres and fuel. Box at the line: the crew changes the tyres (tap the wheel nuts in order and hold until tight), refuels (let go in the green zone) and repairs damage – all at the same time while the stopwatch runs."),
    T("Race engineer: sees tyres, fuel, temperature, the rain radar and the gaps and sends radio calls to the driver."),
    r.weather ? T("Rain may come: slicks slide in the wet, rain tyres wear fast in the dry.") : null,
    T("After a crash the safety car comes out: everybody slow, no overtaking – a cheap moment for a pit stop."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", leCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

const leSel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
const leMinutes = v => leSel(v || 15, [10, 15, 20].map(n => [n, "⏱ " + n + " min"]));
const leWeather = v => leSel(v ? 1 : 0, [[1, "🌦️ " + I18N.tr(T("Rain may come"))], [0, "☀️ " + I18N.tr(T("Always dry"))]]);
const leDiff = v => leSel(v || "normal", [["junior", "🧒 " + I18N.tr(T("Junior"))], ["normal", "🏁 " + I18N.tr(T("Normal"))]]);
const leSize = v => leSel(v || 4, [1, 2, 3, 4, 5].map(n => [n, "👥 " + n]));

async function langstreckeStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/langstrecke/rules"); } catch {}
  const bots = leSel(r.bots ?? (solo ? 3 : 2), [0, 1, 2, 3, 4, 5].map(n => [n, String(n)]));
  const level = leSel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const minutes = leMinutes(r.minutes), weather = leWeather(r.weather ?? 1), diff = leDiff(r.difficulty), size = leSize(r.team_size);
  const teams = leSel(r.teams || 2, [1, 2, 3, 4].map(n => [n, String(n)]));
  const picker = botPicker(1400);
  const speed = picker.el.querySelector(".bot-speed");
  if (speed) speed.remove();
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", leCoins(rw))) : null;
  const m = modal(h("div.form", h("h2", LE_ICON, " ", leName(), solo ? " – " + I18N.tr(T("Alone")) : ""),
    h("p.small.muted", T("Racing stables, one car each: drive, change tyres, refuel and repair as a team – 24 race hours, day and night.")),
    h("div.grid2", h("label.field", T("Race length"), minutes), h("label.field", T("Weather"), weather)),
    h("div.grid2", h("label.field", T("Difficulty"), diff), solo ? null : h("label.field", T("People per team"), size)),
    solo ? null : h("div.grid2", h("label.field", T("Teams of people"), teams)),
    h("div.grid2", h("label.field", T("Bot teams"), bots), h("label.field", T("Bots play"), level)),
    solo ? h("p.small.muted", T("Alone: you drive and do the pit stops yourself.")) : h("p.small.muted", T("Everybody joins on their own device and picks a team – guests via QR code.")),
    picker.el, coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: +bots.value, level: level.value, minutes: +minutes.value, weather: +weather.value, difficulty: diff.value,
        bot_ids: picker.ids(), ...(solo ? {} : { team_size: +size.value, teams: +teams.value }) };
      try { await api("community/langstrecke/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("langstrecke", bots, level, picker.el);
}

// ---------------------------------------------------------------- sounds: the engine, the wrench, the radio, the lights
const LeAudio = {
  eng: null,
  ctx() { if (!Sound.on) return null; try { Sound.ctx = Sound.ctx || new (window.AudioContext || window.webkitAudioContext)(); return Sound.ctx; } catch { return null; } },
  engine(on, rpm) {
    const c = on ? this.ctx() : null;
    if (!c) { if (this.eng) { try { this.eng.g.gain.setTargetAtTime(0.0001, Sound.ctx.currentTime, 0.05); this.eng.o.stop(Sound.ctx.currentTime + 0.3); this.eng.o2.stop(Sound.ctx.currentTime + 0.3); } catch {} this.eng = null; } return; }
    if (!this.eng) {
      const o = c.createOscillator(), o2 = c.createOscillator(), f = c.createBiquadFilter(), g = c.createGain();
      o.type = "sawtooth"; o2.type = "square"; f.type = "lowpass"; f.frequency.value = 520; g.gain.value = 0.0001;
      o.connect(f); o2.connect(f); f.connect(g).connect(c.destination); o.start(); o2.start();
      this.eng = { o, o2, f, g };
    }
    const fr = 38 + rpm * 120;
    this.eng.o.frequency.setTargetAtTime(fr, c.currentTime, 0.08);
    this.eng.o2.frequency.setTargetAtTime(fr * 0.5, c.currentTime, 0.08);
    this.eng.g.gain.setTargetAtTime(0.025 + rpm * 0.02, c.currentTime, 0.1);
  },
  tone(freqs, type = "sine", len = 0.14, vol = 0.12, gap = 0.1) {
    const c = this.ctx(); if (!c) return;
    freqs.forEach((fq, i) => {
      const o = c.createOscillator(), g = c.createGain(), t = c.currentTime + i * gap;
      o.type = type; o.frequency.value = fq;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.015); g.gain.exponentialRampToValueAtTime(0.0001, t + len);
      o.connect(g).connect(c.destination); o.start(t); o.stop(t + len + 0.02);
    });
  },
  radio() { this.tone([1250, 1250], "square", 0.07, 0.05, 0.12); },
  wrench() { this.tone([180, 220, 200, 240, 210], "square", 0.06, 0.05, 0.05); },
  light(go) { this.tone(go ? [880, 1320] : [440], "sine", go ? 0.4 : 0.18, 0.14); },
  roar() { this.tone([70, 95, 140, 120], "sawtooth", 0.35, 0.07, 0.12); },
  fanfare() { this.tone([523, 659, 784, 1046, 784, 1046], "triangle", 0.2, 0.12, 0.13); },
};
const leBuzz = p => { try { if (Sound.on && navigator.vibrate) navigator.vibrate(p); } catch {} };
const leReduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const leClock = (s, limit) => { const hr = leHour(s, limit), m = Math.floor((hr % 1) * 60); return String(Math.floor(hr)).padStart(2, "0") + ":" + String(m).padStart(2, "0"); };
const leRaceLeft = (s, limit) => { const left = Math.max(0, 24 * (1 - Math.max(0, s) / limit)); return Math.floor(left) + ":" + String(Math.floor((left % 1) * 60)).padStart(2, "0") + " h"; };

// ---------------------------------------------------------------- drawing: cars, people, the track
function leCarRear(ctx, x, y, w, col, num, o = {}) {
  // a car from behind: body, rear wing, wheels, lights, the start number
  const hgt = w * 0.5;
  ctx.save();
  ctx.globalAlpha = o.alpha ?? 1;
  ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.beginPath(); ctx.ellipse(x, y, w * 0.6, w * 0.08, 0, 0, 7); ctx.fill();
  ctx.fillStyle = "#15171c";                                         // wheels
  ctx.fillRect(x - w * 0.52, y - hgt * 0.55, w * 0.2, hgt * 0.55); ctx.fillRect(x + w * 0.32, y - hgt * 0.55, w * 0.2, hgt * 0.55);
  ctx.fillStyle = col;                                               // body
  ctx.beginPath(); ctx.moveTo(x - w * 0.42, y - hgt * 0.15); ctx.lineTo(x - w * 0.36, y - hgt * 0.72); ctx.lineTo(x - w * 0.16, y - hgt * 0.98);
  ctx.lineTo(x + w * 0.16, y - hgt * 0.98); ctx.lineTo(x + w * 0.36, y - hgt * 0.72); ctx.lineTo(x + w * 0.42, y - hgt * 0.15); ctx.closePath(); ctx.fill();
  ctx.fillStyle = "rgba(20,30,50,.85)"; ctx.fillRect(x - w * 0.14, y - hgt * 0.93, w * 0.28, hgt * 0.2);   // window
  ctx.fillStyle = "#222"; ctx.fillRect(x - w * 0.38, y - hgt * 0.24, w * 0.76, hgt * 0.12);                // diffuser
  const lit = o.brake ? "#ff3b3b" : o.night ? "#e0282899" : "#b3262699";
  ctx.fillStyle = lit; ctx.fillRect(x - w * 0.36, y - hgt * 0.52, w * 0.12, hgt * 0.1); ctx.fillRect(x + w * 0.24, y - hgt * 0.52, w * 0.12, hgt * 0.1);
  if (o.night || o.brake) {
    const g = ctx.createRadialGradient(x, y - hgt * 0.47, 0, x, y - hgt * 0.47, w * 0.6);
    g.addColorStop(0, o.brake ? "rgba(255,50,50,.35)" : "rgba(255,40,40,.18)"); g.addColorStop(1, "rgba(255,40,40,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y - hgt * 0.47, w * 0.6, 0, 7); ctx.fill();
  }
  ctx.strokeStyle = "#1d1f24"; ctx.lineWidth = Math.max(1, w * 0.04);  // the rear wing (broken: hanging)
  ctx.fillStyle = "#1d1f24";
  if (o.wing) { ctx.save(); ctx.translate(x, y - hgt * 1.05); ctx.rotate(0.35); ctx.fillRect(-w * 0.45, -hgt * 0.05, w * 0.6, hgt * 0.1); ctx.restore(); }
  else {
    ctx.beginPath(); ctx.moveTo(x - w * 0.25, y - hgt * 0.95); ctx.lineTo(x - w * 0.25, y - hgt * 1.12); ctx.moveTo(x + w * 0.25, y - hgt * 0.95); ctx.lineTo(x + w * 0.25, y - hgt * 1.12); ctx.stroke();
    ctx.fillRect(x - w * 0.47, y - hgt * 1.2, w * 0.94, hgt * 0.12);
  }
  if (num != null && w > 22) {
    ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(x, y - hgt * 0.5, w * 0.1, 0, 7); ctx.fill();
    ctx.fillStyle = "#111"; ctx.font = "800 " + Math.max(7, Math.round(w * 0.12)) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(String(num), x, y - hgt * 0.49);
  }
  if (o.hazard) { ctx.fillStyle = "#ffa94d"; ctx.fillRect(x - w * 0.42, y - hgt * 0.62, w * 0.08, hgt * 0.08); ctx.fillRect(x + w * 0.34, y - hgt * 0.62, w * 0.08, hgt * 0.08); }
  if (o.smoke) { ctx.fillStyle = "rgba(180,180,180,.5)"; for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.arc(x + (k - 1) * w * 0.2, y - hgt * (1.3 + k * 0.2), w * 0.12 * (1 + k * 0.4), 0, 7); ctx.fill(); } }
  ctx.restore();
}
function leCarTop(ctx, x, y, len, ang, col, num, door) {
  // a car from above (the intro): long body, cockpit, wheels, the number on the bonnet
  ctx.save(); ctx.translate(x, y); ctx.rotate(ang);
  const w = len * 0.42;
  ctx.fillStyle = "#15171c";
  for (const [dx, dy] of [[-0.32, -0.55], [0.3, -0.55], [-0.32, 0.55], [0.3, 0.55]]) ctx.fillRect(dx * len - len * 0.08, dy * w - w * 0.12, len * 0.16, w * 0.24);
  ctx.fillStyle = col;
  ctx.beginPath(); ctx.ellipse(0, 0, len / 2, w / 2, 0, 0, 7); ctx.fill();
  ctx.fillStyle = "rgba(20,30,50,.85)"; ctx.beginPath(); ctx.ellipse(-len * 0.05, 0, len * 0.16, w * 0.3, 0, 0, 7); ctx.fill();
  ctx.fillStyle = "#1d1f24"; ctx.fillRect(-len * 0.5, -w * 0.48, len * 0.07, w * 0.96);
  if (door) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-len * 0.12, w * 0.45); ctx.lineTo(-len * 0.12 + Math.cos(door) * len * 0.22, w * 0.45 + Math.sin(door) * len * 0.22); ctx.stroke(); }
  ctx.rotate(-ang);
  ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(len * 0.22 * Math.cos(ang), len * 0.22 * Math.sin(ang), len * 0.1, 0, 7); ctx.fill();
  ctx.fillStyle = "#111"; ctx.font = "800 " + Math.round(len * 0.12) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(String(num), len * 0.22 * Math.cos(ang), len * 0.22 * Math.sin(ang) + 0.5);
  ctx.restore();
}

function langstreckeLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", busy = false, raf = 0, syncing = false, lastSync = 0, cheered = false;
  let offset = null, bestRtt = 1e9;
  let pend = [], inflight = [], thrLocal = 0, boxLocal = 0;
  const fired = new Set();
  let ui = {}, introSkip = false, introSound = 0, radioSeen = null, radioUntil = 0, finalCue = false, scSeen = 0, lastTempWarn = 0;
  let pitKey = "", pitDone = {};
  const imgs = {};
  const myId = String(me.id);
  box.classList.add("le-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => {
    alive = false; clearTimeout(timer); cancelAnimationFrame(raf); LeAudio.engine(false);
    box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); window.removeEventListener("keydown", onKey);
  };
  window.addEventListener("hashchange", stop, { once: true });
  const nowS = () => performance.now() / 1000;
  const gameT = () => (st && offset != null ? nowS() + offset - st.t0 : -99);
  const playing = () => st && st.phase === "play" && st.status !== "done";
  const limit = () => (st && st.limit) || 900;
  const jr = () => st && st.rules && st.rules.difficulty === "junior";
  const simT = () => (st ? st.k / 10 : 0);
  const myTeam = () => (st && st.teams && st.my_team != null ? st.teams[st.my_team] : null);
  const role = () => { const t = myTeam(); return t && t.roles ? t.roles[myId] || "crew" : null; };
  const pName = id => { const p = st.players.find(x => x.id === id); return p ? p.name : "?"; };
  const person = id => st.players.find(x => x.id === id);
  const dark = () => { const t = document.documentElement.dataset.theme; return t === "dark" || (t !== "light" && matchMedia("(prefers-color-scheme: dark)").matches); };

  function clock(s, t1, t2) {
    if (!s || typeof s.now !== "number") return;
    const rtt = t2 - t1;
    if (rtt <= bestRtt * 1.15 || offset == null) { bestRtt = Math.min(bestRtt, rtt); offset = s.now - (t1 + t2) / 2; }
  }
  const req = async (path, opts) => {
    const t1 = nowS();
    const s = await api("community/langstrecke" + path, opts);
    clock(s && s.state ? s.state : s, t1, nowS());
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
    const prev = st;
    st = s;
    if (!st || st.phase !== "play") return;
    const t = myTeam();
    if (t && t.car && (!prev || prev.game !== st.game)) { thrLocal = t.car.thr; boxLocal = t.car.box; }
    if (t && t.car && t.driver !== myId) { pend = []; inflight = []; }
    // a new radio call for my team: big on the driver's screen
    if (t && t.radio && (!radioSeen || radioSeen !== t.radio.t)) {
      const fresh = radioSeen !== null;
      radioSeen = t.radio.t;
      if (fresh || gameT() - t.radio.t < 3) { radioUntil = nowS() + 3.2; LeAudio.radio(); if (t.driver === myId) leBuzz([60, 50, 60]); }
    }
    if ((st.sc || []).length > scSeen) { if (scSeen || gameT() < (st.sc[st.sc.length - 1][1])) { LeAudio.tone([660, 520, 660, 520], "square", 0.12, 0.05, 0.16); } scSeen = st.sc.length; }
  }
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    if (!playing() || !st.joined) {
      try { const s = await req(""); if (!busy) { setState(s); draw(); } } catch {}
    } else if (nowS() - lastSync > 0.24) sync();
    timer = setTimeout(poll, playing() ? 250 : 1000);
  }
  async function sync() {
    if (syncing || !playing() || !st.joined) return;
    syncing = true; lastSync = nowS();
    inflight = inflight.concat(pend); pend = [];
    const inputs = inflight.slice();
    try {
      const s = await req("/sync", { method: "POST", body: { inputs } });
      inflight = inflight.filter(x => !inputs.includes(x));
      setState(s); draw();
    } catch { pend = inflight.concat(pend); inflight = []; }
    syncing = false;
  }

  // ---------- the driver's inputs
  const amDriver = () => { const t = myTeam(); return !!(t && t.driver === myId && t.car && t.car.out == null && playing()); };
  function input(c, v = 0) {
    if (!amDriver()) return;
    let t = gameT();
    if (t < 0 || t > limit()) return;
    t = Math.round(t * 1000) / 1000;
    pend.push([t, c, v]);
    if (c === "u") thrLocal = v;
    if (c === "b") boxLocal = v;
    sync();
  }
  const setThr = v => { v = Math.max(0, Math.min(10, Math.round(v))); if (v !== thrLocal) { input("u", v); drawThrottle(); } };
  function toggleBox() {
    const t = myTeam(); if (!t) return;
    const car = predicted() || t.car;
    if (car.box) { if (!(car.eng || car.wheel || car.fuel <= 0)) input("b", 0); return; }
    if (t.members.length > 1 && (t.streak || 1) < 2) {
      const m = modal(h("div.form.center", h("h2", "📦 ", T("Box this lap")),
        h("p.small.muted", T("At the line the car stops in the pits.")),
        h("div.row.center.wrap", h("button.btn", { onclick: () => { m.close(); input("b", 1); } }, "🔄 ", T("Driver change")),
          h("button.btn.ghost", { onclick: () => { m.close(); input("b", 2); } }, "💪 ", T("Stay in (2nd stint)"))),
        h("button.btn.ghost.small", { onclick: () => m.close() }, T("Cancel"))));
    } else input("b", 1);
  }
  const KEYS = { ArrowLeft: "l", KeyA: "l", ArrowRight: "r", KeyD: "r" };
  function onKey(e) {
    if (!alive || !box.isConnected || !amDriver()) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || "")) return;
    if (KEYS[e.code]) { e.preventDefault(); if (!e.repeat) input(KEYS[e.code]); }
    else if (e.code === "ArrowUp" || e.code === "KeyW") { e.preventDefault(); setThr(thrLocal + 1); }
    else if (e.code === "ArrowDown" || e.code === "KeyS") { e.preventDefault(); setThr(thrLocal - 1); }
    else if (e.code === "Space") { e.preventDefault(); setThr(0); }
    else if ((e.code === "KeyB" || e.code === "KeyP") && !e.repeat) toggleBox();
  }
  window.addEventListener("keydown", onKey);
  function swipes(el) {
    let sx = 0, sy = 0, on = false;
    el.addEventListener("pointerdown", e => {
      if (gameT() < 0 && !introSkip) { introSkip = true; return; }       // a tap skips the intro
      on = true; sx = e.clientX; sy = e.clientY; try { el.setPointerCapture(e.pointerId); } catch {} e.preventDefault();
    });
    el.addEventListener("pointermove", e => {
      if (!on) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
      on = false;
      if (Math.abs(dx) > Math.abs(dy)) input(dx < 0 ? "l" : "r"); else setThr(thrLocal + (dy < 0 ? 2 : -2));
    });
    const up = () => { on = false; };
    el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  }

  // ---------- my car as the server will see it (the snapshot + my inputs up to now)
  let predCache = null;
  function predicted(tNow) {
    const t = myTeam();
    if (!t || !t.car) return null;
    tNow = tNow ?? Math.min(gameT(), limit());
    if (predCache && predCache.k === st.k && predCache.n === pend.length + inflight.length && Math.abs(predCache.at - tNow) < 0.001) return predCache.car;
    const car = { ...t.car };
    if (t.driver !== myId) return car;
    const evs = (t.ev || []).concat(inflight, pend).map(e => [Math.max(e[0], simT()), e[1], e[2]]).sort((a, b) => a[0] - b[0]);
    let k = st.k, i = 0, n = 0;
    const seed = st.seed, j = jr();
    while ((k + 1) / 10 <= tNow + 1e-9 && n < 80) {
      const s = k / 10;
      while (i < evs.length && evs[i][0] <= s + 1e-9) { leApply(car, evs[i][1], evs[i][2]); i++; }
      const ev = leStep(car, s, seed, j, leInWin(st.rain, s), leInWin(st.sc, s));
      for (const e of ev) effect(e, car, s);
      k++; n++;
    }
    car._s = k / 10;
    predCache = { k: st.k, n: pend.length + inflight.length, at: tNow, car };
    return car;
  }
  function effect(e, car, s) {
    const key = e + ":" + (e === "lap" || e === "pit" ? Math.floor(car.d / LE.L) : car.olap + ":" + car.ob);
    if (fired.has(key)) return;
    fired.add(key);
    if (fired.size > 400) fired.clear();
    if (gameT() - s > 1.5) return;                     // old news (a reload)
    if (["gravel", "oil", "debris", "crash", "bigcrash", "wheel"].includes(e)) { try { Sound.play("wrong"); } catch {} leBuzz(e === "bigcrash" || e === "wheel" ? [90, 50, 160] : 60); ui.flash = nowS(); }
    else if (e === "blow" || e === "retired") { LeAudio.tone([200, 120, 80], "sawtooth", 0.3, 0.12, 0.2); leBuzz([200, 80, 200]); ui.flash = nowS(); }
    else if (e === "lap") { try { Sound.play("tap"); } catch {} }
    else if (e === "pit") { LeAudio.tone([500, 400], "sine", 0.15, 0.1, 0.12); }
  }

  // ---------- drawing the race (pseudo-3D from behind the car)
  function avatarImg(p) {
    if (!p || p.bot) return null;
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
  function fit(c) {
    const r = c.wrap.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(100, Math.floor(r.width)), hh = Math.max(100, Math.floor(r.height));
    if (w !== c.w || hh !== c.h || dpr !== c.dpr) { c.w = w; c.h = hh; c.dpr = dpr; c.el.width = w * dpr; c.el.height = hh * dpr; c.el.style.width = w + "px"; c.el.style.height = hh + "px"; }
    c.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  const bend = x => 0.55 * Math.sin(2 * Math.PI * x / LE.L * 2 + 0.7) + 0.35 * Math.sin(2 * Math.PI * x / LE.L * 5 + 2.1);
  function race(c, car, team, t, opts = {}) {
    const ctx = c.ctx, cw = c.w, ch = c.h, F = 9, VIEW = 120;
    const dk = leDark(t, limit()), rain = leInWin(st.rain, t), sc = leInWin(st.sc, t);
    const view = VIEW - 55 * dk;
    const d = car.d + (car.pit || car.out != null ? 0 : car.v * Math.max(0, Math.min(0.1, t - (car._s ?? t))));
    const yh = ch * 0.34, y0 = ch * 0.98, LW = Math.min(cw * 0.3, ch * 0.3);
    const sc_ = z => F / (F + Math.max(-F * 0.5, z));
    const bd = bend(d + 40);
    const shift = z => bd * cw * 0.9 * Math.pow(Math.max(0, z) / VIEW, 2);
    const Y = z => yh + (y0 - yh) * sc_(z);
    const X = (lane, z) => cw / 2 + shift(z) + (lane - 1) * LW * sc_(z) - (ui.lanePos != null && !opts.tv ? (ui.lanePos - 1) * LW * 0.35 : 0) * sc_(z);
    // the sky: day blue → dusk → night with stars; the pine forest on the horizon
    const g = ctx.createLinearGradient(0, 0, 0, yh);
    const sky = [[[95, 160, 230], [190, 220, 245]], [[8, 12, 34], [38, 40, 84]]];
    const mix = (a, b) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * dk)).join(",")})`;
    g.addColorStop(0, rain ? "#7d8796" : mix(sky[0][0], sky[1][0])); g.addColorStop(1, rain ? "#aab3bf" : mix(sky[0][1], sky[1][1]));
    ctx.fillStyle = g; ctx.fillRect(0, 0, cw, yh + 1);
    if (dk > 0.3) { const r = leRand(11); ctx.fillStyle = `rgba(255,255,235,${0.6 * dk})`; for (let k = 0; k < 40; k++) ctx.fillRect(r() * cw, r() * yh * 0.85, 1.6, 1.6); }
    const hz = bd * cw * 0.15;
    ctx.fillStyle = dk > 0.5 ? "#0b1f17" : "#24573a";
    for (let k = -2; k < 26; k++) {                               // fir silhouettes (Les Tannes)
      const px = ((k * 37 - hz - (d * 0.05) % 37) % (cw + 80)) - 40, hh = 18 + ((k * 13) % 5) * 6;
      ctx.beginPath(); ctx.moveTo(px - 12, yh); ctx.lineTo(px, yh - hh); ctx.lineTo(px + 12, yh); ctx.fill();
    }
    ctx.fillStyle = dk > 0.5 ? "#0f2a1c" : rain ? "#3d6b4a" : "#4f9a5e"; ctx.fillRect(0, yh, cw, ch - yh);
    // the road in slices from far to near: kerbs red/white, the lane lines
    const step = 4, seg = Math.floor(d / step);
    for (let z = VIEW; z > -F * 0.4; z -= step) {
      const z2 = z - step, za = Math.max(-F * 0.4, z2);
      const k = Math.floor((d + z) / step);
      const pts = (lane, zz) => X(lane, zz);
      ctx.fillStyle = dk > 0.5 ? "#2a2d33" : rain ? "#4b5059" : (k % 2 ? "#6b6f78" : "#666a73");
      ctx.beginPath(); ctx.moveTo(pts(-0.6, z), Y(z)); ctx.lineTo(pts(2.6, z), Y(z)); ctx.lineTo(pts(2.6, za), Y(za)); ctx.lineTo(pts(-0.6, za), Y(za)); ctx.fill();
      ctx.fillStyle = k % 2 ? "#e03131" : "#f1f3f5";
      for (const [a, b] of [[-0.72, -0.6], [2.6, 2.72]]) { ctx.beginPath(); ctx.moveTo(pts(a, z), Y(z)); ctx.lineTo(pts(b, z), Y(z)); ctx.lineTo(pts(b, za), Y(za)); ctx.lineTo(pts(a, za), Y(za)); ctx.fill(); }
      if (k % 3 === 0) {
        ctx.fillStyle = "rgba(255,255,255,.55)";
        for (const b of [0.5, 1.5]) { const w0 = 0.03; ctx.beginPath(); ctx.moveTo(pts(b - w0, z), Y(z)); ctx.lineTo(pts(b + w0, z), Y(z)); ctx.lineTo(pts(b + w0, za), Y(za)); ctx.lineTo(pts(b - w0, za), Y(za)); ctx.fill(); }
      }
      const xl = ((d + z) % LE.L + LE.L) % LE.L;                // the start / finish line, the pit straight
      if (xl < step) { ctx.fillStyle = "#fff"; ctx.fillRect(pts(-0.6, z), Y(z) - 1, pts(2.6, z) - pts(-0.6, z), Math.max(2, (Y(za) - Y(z)) * 0.6)); }
    }
    void seg;
    // things beside and on the track, the other cars – far first
    const items = [];
    for (let k = Math.floor((d - 10) / 30); k * 30 < d + view; k++) {
      const z = k * 30 - d; if (z < -F * 0.4) continue;
      for (const side of [-1, 1]) items.push({ z, f: () => { const x = X(side < 0 ? -1.4 - (k % 2) * 0.5 : 3.4 + (k % 2) * 0.5, z), y = Y(z), u = LW * sc_(z) * 0.5;
        ctx.fillStyle = dk > 0.5 ? "#0b2018" : ["#1f6b3e", "#2b7f48"][k % 2]; ctx.beginPath(); ctx.moveTo(x, y - u * 2.6); ctx.lineTo(x + u * 0.7, y); ctx.lineTo(x - u * 0.7, y); ctx.fill(); } });
    }
    const lap0 = Math.floor(d / LE.L) - 1, j = jr();
    for (let lp = Math.max(0, lap0); lp <= lap0 + 2; lp++) {
      leThings(st.seed, lp, j).forEach(([x, lane, kind], i) => {
        const z = lp * LE.L + x - d;
        if (z < -F * 0.3 || z > view) return;
        if (sc) return;
        if (opts.car && (lp < car.olap || (lp === car.olap && i < car.ob)) && z < 0) return;
        items.push({ z, f: () => thing(ctx, kind, X(lane, z), Y(z), LW * sc_(z), t, i, dk) });
      });
      if (dk > 0.5) { const zf = lp * LE.L + leFog(st.seed, lp) - d; if (zf > 0 && zf < view) items.push({ z: zf, f: () => { ctx.fillStyle = `rgba(200,210,225,${0.5 * Math.min(1, (view - zf) / 30)})`; ctx.fillRect(0, Y(zf) - LW * sc_(zf) * 1.4, cw, LW * sc_(zf) * 1.6); } }); }
    }
    for (const o of st.teams) {
      if (o === team || o.out != null) continue;
      let rel = (((o.d + (o.pit ? 0 : o.v * Math.max(0, t - simT()))) - d) % LE.L + LE.L) % LE.L;
      if (rel > LE.L / 2) rel -= LE.L;
      if (rel < 3 || rel > view || o.pit) continue;
      items.push({ z: rel, f: () => leCarRear(ctx, X(o.lane, rel), Y(rel), LW * sc_(rel) * 0.7, o.color, o.num, { night: dk > 0.4, alpha: 0.95 }) });
    }
    if (sc) items.push({ z: 26, f: () => { const blink = Math.floor(t * 4) % 2; leCarRear(ctx, X(1, 26), Y(26), LW * sc_(26) * 0.7, "#f8f9fa", null, { night: dk > 0.4 });
      ctx.fillStyle = blink ? "#ffa94d" : "#ffd43b"; ctx.fillRect(X(1, 26) - LW * sc_(26) * 0.2, Y(26) - LW * sc_(26) * 0.45, LW * sc_(26) * 0.4, LW * sc_(26) * 0.06);
      ctx.fillStyle = "#111"; ctx.font = "800 " + Math.max(8, Math.round(LW * sc_(26) * 0.14)) + "px system-ui"; ctx.textAlign = "center"; ctx.fillText("SC", X(1, 26), Y(26) - LW * sc_(26) * 0.2); } });
    items.sort((a, b) => b.z - a.z).forEach(it => it.f());
    // night: dark all around, the headlights light the road ahead
    if (dk > 0) {
      ctx.save();
      const hx = cw / 2, hy = Y(14);
      const grad = ctx.createRadialGradient(hx, hy, LW * 0.2, hx, hy, Math.max(cw, ch) * 0.75);
      grad.addColorStop(0, "rgba(4,8,22,0)"); grad.addColorStop(0.35, `rgba(4,8,22,${0.35 * dk})`); grad.addColorStop(1, `rgba(4,8,22,${0.78 * dk})`);
      ctx.fillStyle = grad; ctx.fillRect(0, 0, cw, ch);
      ctx.globalCompositeOperation = "lighter";
      const beam = ctx.createLinearGradient(0, ch, 0, Y(view * 0.6));
      beam.addColorStop(0, `rgba(255,240,190,${0.12 * dk})`); beam.addColorStop(1, "rgba(255,240,190,0)");
      ctx.fillStyle = beam; ctx.beginPath(); ctx.moveTo(cw * 0.3, ch); ctx.lineTo(X(0.2, view * 0.6), Y(view * 0.6)); ctx.lineTo(X(1.8, view * 0.6), Y(view * 0.6)); ctx.lineTo(cw * 0.7, ch); ctx.fill();
      ctx.restore();
    }
    // my car (or the team's car on the TV)
    if (car.out == null || opts.tv) {
      const lp = ui.lanePos != null && !opts.tv ? ui.lanePos : car.lane;
      const xs = cw / 2 + (lp - 1) * LW * sc_(0) * (opts.tv ? 1 : 0.65);
      const shake = car.v > 0 && !leReduced() ? Math.sin(t * 40) * 0.6 : 0;
      leCarRear(ctx, xs, ch * 0.97 + shake, LW * 1.05, team.color, team.num, { brake: car.thr <= 2 && car.v > 15, night: dk > 0.4, wing: car.wing, smoke: car.eng || car.out != null, alpha: car.out != null ? 0.5 : 1 });
    }
    if (rain) {
      ctx.strokeStyle = "rgba(200,215,235,.55)"; ctx.lineWidth = 1;
      const r = leRand(Math.floor(t * 12));
      ctx.beginPath(); for (let k = 0; k < 70; k++) { const x = r() * cw, y = r() * ch; ctx.moveTo(x, y); ctx.lineTo(x - 3, y + 12); } ctx.stroke();
    }
    if (ui.flash && nowS() - ui.flash < 0.35 && !opts.tv) { ctx.fillStyle = `rgba(242,84,91,${0.35 * (1 - (nowS() - ui.flash) / 0.35)})`; ctx.fillRect(0, 0, cw, ch); }
  }
  function thing(ctx, kind, x, y, w, t, i, dk) {
    const u = w * 0.5;
    if (kind === LE_GRAVEL) {
      ctx.fillStyle = dk > 0.5 ? "#6d5a3c" : "#c9a86a"; ctx.beginPath(); ctx.ellipse(x, y - u * 0.05, w * 0.48, Math.max(2, u * 0.25), 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#8a6d42"; const r = leRand(i + 3); for (let k = 0; k < 9; k++) ctx.fillRect(x + (r() - 0.5) * w * 0.8, y - u * 0.2 + r() * u * 0.3, Math.max(1, u * 0.06), Math.max(1, u * 0.06));
    } else if (kind === LE_OIL) {
      ctx.fillStyle = "#101114"; ctx.beginPath(); ctx.ellipse(x, y - u * 0.04, w * 0.42, Math.max(2, u * 0.2), 0, 0, 7); ctx.fill();
      ctx.strokeStyle = "rgba(130,90,255,.6)"; ctx.lineWidth = Math.max(1, u * 0.05); ctx.beginPath(); ctx.ellipse(x - w * 0.08, y - u * 0.06, w * 0.18, Math.max(1, u * 0.07), 0, 0, 7); ctx.stroke();
    } else if (kind === LE_DEBRIS) {
      ctx.fillStyle = "#adb5bd"; const r = leRand(i + 7);
      for (let k = 0; k < 6; k++) { const px = x + (r() - 0.5) * w * 0.7, py = y - r() * u * 0.3; ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px + u * 0.18, py - u * 0.12); ctx.lineTo(px + u * 0.08, py + u * 0.04); ctx.fill(); }
    } else if (kind === LE_SLOW) leCarRear(ctx, x, y, w * 0.7, "#ced4da", null, { hazard: Math.floor(t * 3 + i) % 2 === 0, night: dk > 0.4 });
  }

  // ---------- the intro: drivers next to the track run to their cars, doors, engines, lights
  function intro(c, t) {
    const ctx = c.ctx, cw = c.w, ch = c.h, ti = t + LE.COUNTDOWN, red = leReduced();
    const skip = introSkip || red;
    ctx.fillStyle = "#3f8a4f"; ctx.fillRect(0, 0, cw, ch);
    const ty0 = ch * 0.34, ty1 = ch * 0.62;
    ctx.fillStyle = "#6b6f78"; ctx.fillRect(0, ty0, cw, ty1 - ty0);
    ctx.fillStyle = "#f1f3f5"; for (let x = 0; x < cw; x += 24) { ctx.fillRect(x, ty0 - 4, 12, 4); ctx.fillRect(x + 12, ty1, 12, 4); }
    ctx.fillStyle = "#e03131"; for (let x = 12; x < cw; x += 24) { ctx.fillRect(x, ty0 - 4, 12, 4); ctx.fillRect(x - 12, ty1, 12, 4); }
    ctx.fillStyle = "#1f6b3e"; for (let x = 8; x < cw; x += 30) { ctx.beginPath(); ctx.moveTo(x - 10, ty0 - 8); ctx.lineTo(x, ty0 - 34 - (x % 3) * 4); ctx.lineTo(x + 10, ty0 - 8); ctx.fill(); }
    ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.font = "800 " + Math.round(Math.min(cw * 0.06, 22)) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.fillText("Circuit des Tannes · 24h", cw / 2, 8);
    const teams = st.teams, n = teams.length, gap = cw / (n + 1), len = Math.min(gap * 0.9, 64);
    const run = skip ? 1 : Math.max(0, Math.min(1, (ti - 1.8) / 1.8)), inCar = skip || ti > 3.7;
    teams.forEach((tm, k) => {
      const cx = gap * (k + 1), cy = ty0 + (ty1 - ty0) * 0.3;
      const door = inCar ? (ti < 4.2 && !skip ? 1.2 * (4.2 - ti) / 0.5 : 0) : 1.2;
      const roar = !skip && ti > 4.2 && ti < 5.4 ? Math.sin(ti * 60) * 1.2 : 0;
      leCarTop(ctx, cx + roar, cy, len, -Math.PI / 2 + 0.5, tm.color, tm.num, door);
      if (!skip && ti > 4.2 && ti < 5.6) { ctx.fillStyle = "rgba(200,200,200,.5)"; ctx.beginPath(); ctx.arc(cx - len * 0.3, cy + len * 0.45 + (ti - 4.2) * 10, 5 + (ti - 4.2) * 6, 0, 7); ctx.fill(); }
      if (!inCar) {                                             // the driver runs from the far edge of the track
        const p = person(tm.driver) || {}, sx = cx, sy = ch * 0.8, ex = cx - len * 0.25, ey = cy + len * 0.2;
        const x = sx + (ex - sx) * run, y = sy + (ey - sy) * run - (run > 0.85 ? Math.sin((run - 0.85) / 0.15 * Math.PI) * 10 : 0);
        const S = Math.min(gap * 0.75, 44), leg = run > 0 && run < 1 ? Math.sin(ti * 18) : 0;
        ctx.strokeStyle = "#2d3a5a"; ctx.lineWidth = Math.max(2, S * 0.1); ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(x - S * 0.1, y + S * 0.35); ctx.lineTo(x - S * 0.1 + leg * S * 0.18, y + S * 0.62); ctx.moveTo(x + S * 0.1, y + S * 0.35); ctx.lineTo(x + S * 0.1 - leg * S * 0.18, y + S * 0.62); ctx.stroke();
        ctx.fillStyle = tm.color; ctx.beginPath(); ctx.ellipse(x, y + S * 0.28, S * 0.26, S * 0.16, 0, 0, 7); ctx.fill();
        const img = avatarImg(p);
        if (img && img.complete && img.naturalWidth) ctx.drawImage(img, x - S / 2, y - S * 0.6, S, S);
        else { ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(x, y - S * 0.1, S * 0.28, 0, 7); ctx.fill(); ctx.font = Math.round(S * 0.36) + "px system-ui, 'Apple Color Emoji', 'Noto Color Emoji'"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = "#000"; ctx.fillText(p.bot ? (p.emoji || "🤖") : "🙂", x, y - S * 0.08); }
        if (n <= 6) { ctx.font = "700 11px system-ui"; ctx.fillStyle = "#fff"; ctx.textBaseline = "top"; ctx.fillText(String(p.name || "").slice(0, 10), x, y + S * 0.66); }
      }
    });
    // the start lights
    const lw = Math.min(cw * 0.6, 240), lx = cw / 2 - lw / 2, ly = ch * 0.86, r = lw / 12;
    ctx.fillStyle = "#1d1f24"; ctx.beginPath(); ctx.roundRect ? ctx.roundRect(lx, ly - r * 1.4, lw, r * 2.8, 8) : ctx.rect(lx, ly - r * 1.4, lw, r * 2.8); ctx.fill();
    const lit = Math.max(0, Math.min(5, Math.floor((ti - 5.4) / 0.4) + 1));
    for (let k = 0; k < 5; k++) { ctx.fillStyle = ti >= LE.COUNTDOWN ? "#40c057" : k < lit ? "#fa5252" : "#3a3d44"; ctx.beginPath(); ctx.arc(lx + lw * (k + 0.5) / 5, ly, r, 0, 7); ctx.fill(); }
    if (lit !== introSound && ti >= 5.4) { introSound = lit; LeAudio.light(false); leBuzz(30); }
    ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.textBaseline = "bottom"; ctx.font = "900 " + Math.round(Math.min(cw * 0.07, 28)) + "px system-ui, sans-serif";
    ctx.lineWidth = 5; ctx.lineJoin = "round"; ctx.strokeStyle = "rgba(15,23,42,.7)";
    const msg = red ? I18N.tr(T("The race starts in {0} s")).replace("{0}", Math.ceil(-t)) : ti < 3.7 ? I18N.tr(T("Drivers, to your cars!")) : ti < 5.4 ? I18N.tr(T("Start your engines!")) : I18N.tr(T("It's starting now!"));
    ctx.strokeText(msg, cw / 2, ly - r * 1.8); ctx.fillText(msg, cw / 2, ly - r * 1.8);
    if (!skip && ti < 5) { ctx.font = "600 12px system-ui"; ctx.textBaseline = "top"; ctx.fillStyle = "rgba(255,255,255,.85)"; ctx.fillText(I18N.tr(T("Tap to skip")), cw / 2, ch * 0.92); }
    if (!skip && ti > 4.2 && !ui.roared) { ui.roared = true; LeAudio.roar(); leBuzz([40, 30, 80]); }
  }

  // ---------- the frame
  function frame() {
    if (!alive || !box.isConnected) return stop();
    raf = requestAnimationFrame(frame);
    if (!st || st.phase !== "play") { LeAudio.engine(false); return; }
    const t = gameT();
    const team = myTeam();
    if (ui.go && t >= 0 && t < 0.2) { ui.go = false; LeAudio.light(true); leBuzz(120); }
    const c = ui.cv;
    if (ui.thr) ui.thr.hidden = t < 0;
    if (c) {
      fit(c);
      if (t < 0) intro(c, t);
      else {
        let car, tm = team;
        if (ui.mode === "drive") car = predicted(Math.min(t, limit()));
        else {
          tm = team || st.teams[st.standings[0]];
          car = { ...tm.car || {}, d: tm.d, v: tm.v, lane: tm.lane, pit: tm.pit, out: tm.out, thr: (tm.car || {}).thr ?? 8, wing: (tm.dmg || []).includes("wing"), eng: (tm.dmg || []).includes("eng") };
          car.d = tm.pit || tm.out != null ? tm.d : tm.d + tm.v * Math.max(0, Math.min(1.5, t - simT()));
          car._s = t;
        }
        if (car) {
          if (ui.mode === "drive") {                       // the car slides to its lane
            ui.lanePos = ui.lanePos == null ? car.lane : ui.lanePos + (car.lane - ui.lanePos) * 0.25;
          }
          race(c, car, tm, t, { tv: ui.mode !== "drive", car: ui.mode === "drive" });
          const big = (txt, sub, col) => {
            const ctx = c.ctx;
            ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineWidth = 6; ctx.lineJoin = "round"; ctx.strokeStyle = "rgba(15,23,42,.75)"; ctx.fillStyle = col || "#fff";
            ctx.font = "900 " + Math.round(Math.min(c.w * 0.1, c.h * 0.09)) + "px system-ui, sans-serif";
            ctx.strokeText(txt, c.w / 2, c.h * 0.4); ctx.fillText(txt, c.w / 2, c.h * 0.4);
            if (sub) { ctx.font = "700 " + Math.round(Math.min(c.w * 0.045, 18)) + "px system-ui, sans-serif"; ctx.lineWidth = 4; ctx.strokeText(sub, c.w / 2, c.h * 0.4 + 34); ctx.fillText(sub, c.w / 2, c.h * 0.4 + 34); }
          };
          if (t < 1) big(I18N.tr(T("GO!")), null, "#69db7c");
          else if (car.out != null) big("🏳️ " + I18N.tr(T("Retired")), I18N.tr(T("The team keeps its laps.")));
          else if (leInWin(st.sc, t) && ui.mode === "drive") big("🟨 " + I18N.tr(T("Safety car")), I18N.tr(T("No overtaking – cheap pit stop!")), "#ffd43b");
          else if (t >= limit()) big("🏁 " + I18N.tr(T("Finish!")));
          else if (ui.mode === "drive" && car.temp >= LE.RED && Math.floor(t * 4) % 2 === 0) big("🔥 " + I18N.tr(T("Lift off!")), null, "#ff6b6b");
          if (ui.mode === "drive" && car.temp >= LE.RED && t - lastTempWarn > 1.2) { lastTempWarn = t; leBuzz(80); LeAudio.tone([900], "square", 0.08, 0.05); }
          if (ui.mode === "drive") LeAudio.engine(!document.hidden && !car.pit && car.out == null && t < limit(), Math.min(1, car.v / LE.VMAX * 0.6 + car.thr / 25));
          else LeAudio.engine(false);
          hud(car, tm, t);
        }
      }
    }
    if (!c) { LeAudio.engine(false); if (team && team.car && t >= 0) hud(team.car, team, t); }
    if (t >= 0 && t >= limit() * 22 / 24 && !finalCue && t < limit()) { finalCue = true; if (gameT() - limit() * 22 / 24 < 5) { LeAudio.fanfare(); toast("🏁 " + I18N.tr(T("The final 2 race hours!")), "good"); } }
    if (ui.pit) pitTick();
    if (ui.radio) {
      const tm = team, on = tm && tm.radio && nowS() < radioUntil;
      ui.radio.hidden = !on;
      if (on) { const [ic, txt] = LE_RADIO[tm.radio.m] || ["📻", ""]; ui.radio.replaceChildren(h("span.le-radio-ic", "📻 ", ic), h("span", I18N.tr(txt)), h("small", " – ", C(pName(tm.radio.from)))); }
    }
  }
  // ---------- the bars: position, lap, clock, gauges, standings
  function bar(el, v, lo, hi) { el.style.setProperty("--v", Math.max(0, Math.min(100, v)) + "%"); el.dataset.lvl = v >= hi ? "red" : v >= lo ? "yellow" : "ok"; }
  function hud(car, tm, t) {
    const hd = ui.hud;
    if (!hd) return;
    const pos = st.standings.indexOf(tm.i) + 1, tt = Math.max(0, Math.min(t, limit())), night = leDark(tt, limit()) > 0.5;
    hd.pos.textContent = "P" + pos + "/" + st.teams.length;
    hd.lap.textContent = I18N.tr(T("Lap {0}")).replace("{0}", leLaps(car.d) + 1);
    hd.clock.textContent = (night ? "🌙 " : "☀️ ") + leClock(tt, limit()) + (leInWin(st.rain, tt) ? " 🌧️" : "");
    hd.left.textContent = "⏳ " + leRaceLeft(tt, limit());
    hd.left.classList.toggle("le-final", tt >= limit() * 22 / 24);
    if (hd.speed) {
      hd.speed.textContent = Math.round(car.v * 5) + " km/h";
      bar(hd.temp, (car.temp - 50) / 60 * 100, (LE.YELLOW - 50) / 60 * 100, (LE.RED - 50) / 60 * 100);
      hd.temp.dataset.lvl = car.temp >= LE.RED ? "red" : car.temp >= LE.YELLOW ? "yellow" : "ok";
      bar(hd.fuel, car.fuel, 101, 101); hd.fuel.dataset.lvl = car.fuel < 15 ? "red" : car.fuel < 30 ? "yellow" : "ok";
      bar(hd.tyre, 100 - car.wear, 101, 101); hd.tyre.dataset.lvl = car.wear > 80 ? "red" : car.wear > 55 ? "yellow" : "ok";
      hd.tyreIc.textContent = car.tyre === "r" ? "🌧️" : "☀️";
      hd.dmg.textContent = (car.eng ? "💥" : "") + (car.wing ? "🪽" : "") + (car.wheel ? "🛞❌" : "") + (car.loose >= 0 ? "⚠️" : "");
      if (hd.boxBtn) { hd.boxBtn.classList.toggle("on", !!car.box); hd.boxBtn.textContent = car.box ? "📦 " + I18N.tr(T("Boxing")) + " ✓" : "📦 " + I18N.tr(T("Box")); }
    }
    if (ui.board && (!ui.boardAt || nowS() - ui.boardAt > 0.5)) { ui.boardAt = nowS(); drawBoard(); }
    if (ui.tele && (!ui.teleAt || nowS() - ui.teleAt > 0.5)) { ui.teleAt = nowS(); drawTele(); }
  }
  const gapText = (o, lead) => {
    const dd = lead.d - o.d;
    if (o === lead) return I18N.tr(T("Leader"));
    if (dd >= LE.L) { const n = Math.floor(dd / LE.L); return "+" + n + " " + I18N.tr(n === 1 ? T("lap") : T("laps")); }
    return "+" + (dd / 45).toFixed(1) + " s";
  };
  function drawBoard() {
    if (!ui.board || !st.teams) return;
    const lead = st.teams[st.standings[0]];
    ui.board.replaceChildren(...st.standings.map((i, k) => {
      const o = st.teams[i];
      return h("div.le-chip" + (i === st.my_team ? ".le-mine" : "") + (o.out != null ? ".le-outc" : ""), { style: { "--tc": o.color } },
        h("b.le-rank", String(k + 1)), h("span.le-num", String(o.num)),
        h("span.le-gap", o.out != null ? "🏳️" : o.pit ? "🅿️" : gapText(o, lead)), h("span.le-laps", o.laps + "L"));
    }));
  }
  function drawTele() {
    const tm = myTeam(), car = tm && tm.car;
    if (!ui.tele || !car) return;
    const t = Math.max(0, Math.min(gameT(), limit()));
    const row = (ic, label, val, lvl) => h("div.le-tl" + (lvl ? ".le-" + lvl : ""), h("span", ic), h("span.small.muted", I18N.tr(label)), h("b", val));
    const items = [row("🏎️", T("Driver"), pName(tm.driver) + (tm.auto ? " 🤖" : "")),
      row("🌡️", T("Engine"), Math.round(car.temp) + "°", car.temp >= LE.RED ? "red" : car.temp >= LE.YELLOW ? "yellow" : null),
      row("⛽", T("Fuel"), Math.round(car.fuel) + " %", car.fuel < 15 ? "red" : car.fuel < 30 ? "yellow" : null),
      row(car.tyre === "r" ? "🌧️" : "☀️", T("Tyres"), Math.round(100 - car.wear) + " %", car.wear > 80 ? "red" : car.wear > 55 ? "yellow" : null),
      row("🔧", T("Damage"), [car.eng ? "💥" : "", car.wing ? "🪽" : "", car.wheel ? "🛞" : ""].join("") || "–", car.eng || car.wing || car.wheel ? "red" : null),
      row("⏱", T("Best lap"), car.best ? car.best.toFixed(1) + " s" : "–"),
      row("📦", T("Box"), car.box ? "✓" : "–", car.box ? "yellow" : null),
      row("🅿️", T("Stops"), String((tm.pits || []).length) + (tm.best_pit ? " · " + tm.best_pit.toFixed(1) + " s" : ""))];
    ui.tele.replaceChildren(...items);
    if (ui.radar) {                                          // the rain radar: the next 2 race hours
      const span = limit() * 2 / 24, wins = (st.rain || []).filter(([a, b]) => b > t && a < t + span);
      const next = (st.rain || []).find(([a, b]) => b > t);
      const inMin = s => { const m = Math.max(1, Math.round(s / limit() * 1440)); return m < 90 ? m + " min" : Math.round(m / 60) + " h"; };
      const label = !st.rules.weather ? I18N.tr(T("Dry all race")) : leInWin(st.rain, t) ? "🌧️ " + I18N.tr(T("Raining now")) + (next ? " · " + I18N.tr(T("dry in {0}")).replace("{0}", inMin(next[1] - t)) : "")
        : next ? "🌧️ " + I18N.tr(T("Rain in {0}")).replace("{0}", inMin(next[0] - t)) : "☀️ " + I18N.tr(T("No rain in sight"));
      ui.radar.replaceChildren(h("div.le-radar-bar", ...wins.map(([a, b]) => h("i", { style: { left: Math.max(0, (a - t) / span * 100) + "%", width: Math.min(100, (Math.min(b, t + span) - Math.max(a, t)) / span * 100) + "%" } }))),
        h("div.small", "📡 ", label));
    }
  }

  // ---------- the pit stop: stopwatch, the jobs, my mini-game
  function pitTick() {
    const tm = myTeam(), stp = tm && tm.stop;
    if (!stp || !ui.pit) return;
    const t = gameT(), el = (stp.end != null && t >= stp.end ? stp.end : t) - stp.t;
    ui.pit.watch.textContent = "⏱ " + Math.max(0, el).toFixed(1) + " s";
    ui.pit.watch.classList.toggle("le-done", stp.end != null && t >= stp.end);
    for (const [job, node] of Object.entries(ui.pit.status)) {
      const d = stp.done[job] || pitDone[job];
      node.textContent = d ? "✓ " + (d.at ? (d.at - stp.t).toFixed(1) + " s" : "") : "…";
      node.parentNode.classList.toggle("le-jobok", !!d);
    }
    if (ui.pit.fuel) ui.pit.fuel();
    if (ui.pit.garage) garage(ui.pit.garage, tm, stp, t);
  }
  function garage(cv, tm, stp, t) {                    // the car in its pit box, the jobs around it
    const r = cv.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
    if (!r.width) return;
    if (cv.width !== Math.round(r.width * dpr)) { cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr); }
    const ctx = cv.getContext("2d"), w = r.width, hh = r.height;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#5c6370"; ctx.fillRect(0, 0, w, hh);
    ctx.strokeStyle = "#fcc419"; ctx.lineWidth = 3; ctx.setLineDash([10, 8]); ctx.strokeRect(w * 0.2, hh * 0.12, w * 0.6, hh * 0.76); ctx.setLineDash([]);
    const len = Math.min(w * 0.5, hh * 1.4);
    const lift = stp.done.tyres || pitDone.tyres ? 0 : Math.sin(t * 20) * 1.5;
    leCarTop(ctx, w / 2 + lift, hh / 2, len, 0, tm.color, tm.num, 0);
    const mark = (job, x, y, ic) => { const done = stp.done[job] || pitDone[job]; ctx.font = "22px system-ui, 'Apple Color Emoji', 'Noto Color Emoji'"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.globalAlpha = done ? 1 : 0.5 + 0.5 * Math.abs(Math.sin(t * 4)); ctx.fillText(done ? "✅" : ic, x, y); ctx.globalAlpha = 1; };
    mark("tyres", w / 2 - len * 0.32, hh * 0.13, "🛞"); mark("fuel", w / 2 + len * 0.1, hh * 0.87, "⛽");
    if (stp.tasks.repair) mark("repair", w / 2 + len * 0.42, hh * 0.13, "🔧");
  }
  function myJob(stp) {
    return ["tyres", "fuel", "repair"].find(j => stp.tasks[j] && stp.who[j] === myId && !stp.done[j] && !pitDone[j]) || null;
  }
  const sendJob = async (task, data) => {
    try {
      const r = await req("/pit", { method: "POST", body: { task, data } });
      if (r.state) setState(r.state);
      return r;
    } catch (e) { toast(e.message, "bad"); return null; }
  };
  function jobTyres(stp) {
    const order = stp.tasks.tyres.order;
    let tyre = (myTeam().radio && myTeam().radio.m === "rain" && gameT() - myTeam().radio.t < 120) ? "r" : (myTeam().radio && myTeam().radio.m === "dry" ? "s" : stp.tasks.tyres.from);
    const holds = [], pos = [[0.27, 0.27], [0.73, 0.27], [0.73, 0.73], [0.27, 0.73]];
    let cur = 0, down = 0, raf2 = 0;
    const comp = h("div.row.center.le-comp");
    const drawComp = () => comp.replaceChildren(...[["s", "☀️ " + I18N.tr(T("Slicks"))], ["r", "🌧️ " + I18N.tr(T("Rain tyres"))]].map(([k, n]) => h("button.btn.small" + (tyre === k ? "" : ".ghost"), { onclick: () => { tyre = k; drawComp(); } }, n)));
    drawComp();
    const nuts = order.map((n, i) => h("button.le-nut", { type: "button", style: { left: pos[n][0] * 100 + "%", top: pos[n][1] * 100 + "%" }, "aria-label": I18N.tr(T("Wheel nut")) + " " + (i + 1) }, h("i")));
    const wheel = h("div.le-wheel", h("div.le-hub"), ...nuts);
    const tip = h("p.small.center", T("Tap the glowing nut and hold until it is tight – then the next one."));
    const mark = () => nuts.forEach((b, i) => { b.classList.toggle("next", i === cur); });
    mark();
    nuts.forEach((b, i) => {
      b.addEventListener("pointerdown", e => {
        e.preventDefault(); if (i !== cur || down) return;
        down = performance.now(); b.classList.add("hold"); LeAudio.wrench(); leBuzz(25);
        const fill = () => { const k = Math.min(1, (performance.now() - down) / 1000 / LE.HOLD_MIN); b.style.setProperty("--p", k * 100 + "%"); if (k >= 1 && !b.classList.contains("tight")) { b.classList.add("tight"); leBuzz(15); } if (down) raf2 = requestAnimationFrame(fill); };
        fill();
      });
      const up = async () => {
        if (i !== cur || !down) return;
        cancelAnimationFrame(raf2);
        const s = (performance.now() - down) / 1000; down = 0;
        b.classList.remove("hold"); b.classList.add(s >= LE.HOLD_MIN ? "tight" : "loose");
        holds.push([order[i], Math.round(s * 1000) / 1000]); cur++; mark();
        if (cur === 4) {
          tip.textContent = "…";
          const r = await sendJob("tyres", { tyre, nuts: holds });
          if (r && r.ok) { pitDone.tyres = { at: gameT() }; tip.textContent = r.loose && r.loose.length ? "⚠️ " + I18N.tr(T("A nut is loose – that wheel may come off!")) : "✅ " + I18N.tr(T("All four tight!")); setTimeout(() => drawPit(true), 700); }
          else { holds.length = 0; cur = 0; nuts.forEach(x => x.classList.remove("tight", "loose")); mark(); tip.textContent = I18N.tr(T("Tap the glowing nut and hold until it is tight – then the next one.")); }
        }
      };
      b.addEventListener("pointerup", up); b.addEventListener("pointercancel", up); b.addEventListener("pointerleave", up);
    });
    return h("div.le-job", h("h3", "🛞 ", T("Tyres")), comp, wheel, tip);
  }
  function jobFuel(stp) {
    const from = stp.tasks.fuel.from, [g0] = stp.tasks.fuel.green;
    let down = 0, held = 0, sent = false;
    const lvl = h("div.le-tank-lvl"), tank = h("div.le-tank", h("div.le-tank-green", { style: { bottom: g0 + "%", height: (100 - g0) + "%" } }), lvl);
    const val = h("b", Math.round(from) + " %");
    const tip = h("p.small.center", T("Hold the nozzle – let go in the green zone. Too much spills!"));
    const set = () => { const v = from + LE.FILL_RATE * (held + (down ? (performance.now() - down) / 1000 : 0)); lvl.style.height = Math.min(100, v) + "%"; lvl.classList.toggle("spill", v > 100); val.textContent = Math.round(Math.min(100, v)) + " %"; tank.classList.toggle("ok", v >= g0 && v <= 100); };
    set();
    const btn = h("button.le-nozzle", { type: "button" }, "⛽ ", T("Hold to fill"));
    btn.addEventListener("pointerdown", e => { e.preventDefault(); if (sent || down) return; down = performance.now(); LeAudio.tone([140], "sawtooth", 0.25, 0.04); try { btn.setPointerCapture(e.pointerId); } catch {} });
    const up = async () => {
      if (!down || sent) return;
      held += (performance.now() - down) / 1000; down = 0; sent = true; set();
      const r = await sendJob("fuel", { hold: Math.round(held * 1000) / 1000 });
      if (r && r.ok) { pitDone.fuel = { at: gameT() }; tip.textContent = r.spill ? "💦 " + I18N.tr(T("Spilled! +3 s")) : r.green ? "✅ " + I18N.tr(T("Full enough!")) : "⚠️ " + I18N.tr(T("Not much fuel – the car may run dry.")); setTimeout(() => drawPit(true), 800); }
      else { sent = false; held = 0; set(); }
    };
    btn.addEventListener("pointerup", up); btn.addEventListener("pointercancel", up);
    ui.pit.fuel = () => { if (down) set(); };
    return h("div.le-job", h("h3", "⛽ ", T("Fuel")), h("div.le-fuelrow", tank, h("div.le-fuelside", val, btn)), tip);
  }
  function jobRepair(stp) {
    const rp = stp.tasks.repair, cols = ["#e03131", "#1c7ed6", "#f08c00", "#2f9e44"];
    const tip = h("p.small.center");
    if (rp.kind === "screws") {
      const rot = rp.rot.slice(), taps = rot.map(() => 0);
      tip.textContent = I18N.tr(T("Turn every screw until its slot stands straight up."));
      const screws = rot.map((r0, i) => {
        const b = h("button.le-screw", { type: "button", style: { "--a": (r0 * 45) + "deg" } }, h("i"));
        b.addEventListener("click", async () => {
          if ((rot[i] + taps[i]) % 4 === 0) return;
          taps[i]++; b.style.setProperty("--a", ((rot[i] + taps[i]) * 45) + "deg"); LeAudio.wrench();
          b.classList.toggle("ok", (rot[i] + taps[i]) % 4 === 0);
          if (rot.every((r, k) => (r + taps[k]) % 4 === 0)) { const r = await sendJob("repair", { answer: taps }); if (r && r.ok) { pitDone.repair = { at: gameT() }; tip.textContent = "✅ " + I18N.tr(T("Repaired!")); setTimeout(() => drawPit(true), 700); } }
        });
        return b;
      });
      return h("div.le-job", h("h3", "🔧 ", T("Repair")), h("div.row.center.le-screws", ...screws), tip);
    }
    // cables: connect each plug on the left to the socket of the same colour on the right
    tip.textContent = I18N.tr(T("Connect every cable to the socket of the same colour."));
    const ans = [-1, -1, -1, -1];
    let pick = -1;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 100 100"); svg.setAttribute("class", "le-cables-svg");
    const lines = () => { svg.replaceChildren(...ans.map((j, i) => { if (j < 0) return null; const l = document.createElementNS("http://www.w3.org/2000/svg", "line"); l.setAttribute("x1", 10); l.setAttribute("y1", 12 + i * 25); l.setAttribute("x2", 90); l.setAttribute("y2", 12 + j * 25); l.setAttribute("stroke", cols[i]); l.setAttribute("stroke-width", 4); l.setAttribute("stroke-linecap", "round"); return l; }).filter(Boolean)); };
    const right = [0, 1, 2, 3].map(j => cols[rp.perm.indexOf(j)]);
    const lb = cols.map((c, i) => h("button.le-plug", { type: "button", style: { background: c, top: (12 + i * 25) + "%" }, onclick: () => { pick = i; lb.forEach((b, k) => b.classList.toggle("sel", k === i)); } }));
    const rb = right.map((c, j) => h("button.le-sock", { type: "button", style: { borderColor: c, top: (12 + j * 25) + "%" }, onclick: async () => {
      if (pick < 0) return;
      for (let k = 0; k < 4; k++) if (ans[k] === j) ans[k] = -1;
      ans[pick] = j; pick = -1; lb.forEach(b => b.classList.remove("sel")); lines(); LeAudio.tone([700], "square", 0.04, 0.04);
      if (ans.every(x => x >= 0)) {
        const r = await sendJob("repair", { answer: ans });
        if (r && r.ok) { pitDone.repair = { at: gameT() }; tip.textContent = "✅ " + I18N.tr(T("Repaired!")); setTimeout(() => drawPit(true), 700); }
        else if (r) { tip.textContent = "❌ " + I18N.tr(T("Wrong – +2 s. Try again!")); ans.fill(-1); lines(); leBuzz([80, 40, 80]); }
      }
    } }));
    return h("div.le-job", h("h3", "🔧 ", T("Repair")), h("div.le-cables", svg, ...lb, ...rb), tip);
  }
  function drawPit(force) {
    const tm = myTeam(), stp = tm && tm.stop;
    if (!stp || !ui.pitBox) return;
    const key = stp.t + ":" + (myJob(stp) || "-");
    if (key === pitKey && !force) return;
    if (!String(pitKey).startsWith(stp.t + ":")) pitDone = {};
    pitKey = stp.t + ":" + (myJob(stp) || "-");
    const job = myJob(stp);
    ui.pit = { watch: h("div.le-watch", "⏱ 0.0 s"), status: {}, fuel: null };
    const jobs = ["tyres", "fuel", "repair"].filter(j => stp.tasks[j]).map(j => {
      const st_ = h("span.le-jobst", "…");
      ui.pit.status[j] = st_;
      const who = stp.who[j];
      return h("div.le-jobchip", h("span", LE_JOBS[j][0]), h("span.grow", I18N.tr(LE_JOBS[j][1]), " · ", who === "bot" ? "🤖" : C(who === myId ? I18N.tr(T("you")) : pName(who))), st_);
    });
    const change = stp.change ? I18N.tr(T("Driver change: {0} → {1}")).replace("{0}", pName(tm.driver)).replace("{1}", pName(stp.next))
      : I18N.tr(T("{0} stays in the car")).replace("{0}", pName(tm.driver));
    const game = job === "tyres" ? jobTyres(stp) : job === "fuel" ? jobFuel(stp) : job === "repair" ? jobRepair(stp)
      : h("div.le-job.center", (ui.pit.garage = h("canvas.le-garage")), h("p", Object.keys(stp.tasks).some(j => stp.who[j] === myId) ? "✅ " + I18N.tr(T("Your jobs are done – wait for the others.")) : I18N.tr(T("The crew is working – watch the stopwatch!"))),
        stp.next === myId && stp.change ? h("p.le-next", "🏎️ ", T("You drive next – get ready!")) : null);
    ui.pitBox.replaceChildren(h("div.le-pithead", h("strong", "🅿️ ", I18N.tr(T("Pit stop {0}")).replace("{0}", stp.n)), ui.pit.watch),
      h("div.small.muted.center", "🔄 ", change, stp.pen ? " · +" + stp.pen + " s" : ""), h("div.le-jobs", ...jobs), game);
    pitTick();
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const tm = myTeam();
    const inPit = !!(tm && tm.stop && tm.car && tm.car.pit);
    const mode = !st ? "none" : st.phase === "lobby" ? "lobby" : st.phase === "done" ? "done" : !st.joined || !tm ? "watch"
      : tm.car.out != null ? "out" : inPit ? "pit" : tm.driver === myId ? "drive" : "wall";
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, mode, tm && tm.driver, tm && tm.roles && tm.roles[myId],
      st.phase === "lobby" ? st.players.map(p => [p.id, p.team]) : 0, st.phase === "done" ? st.players.map(p => p.place) : 0]);
    if (mode === "pit" && ui.pitBox && sig === lastSig) { drawPit(); return; }
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running); box.classList.toggle("le-scroll", mode === "lobby");
    ui = { go: true, roared: ui.roared, mode };
    pitKey = "";
    if (!st) return show(h("section.card.center", h("div.big-ic", LE_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const menu = gameMenu({ rules: () => langstreckeRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "langstrecke" : null,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", LE_ICON, " ", leName())));
    if (st.phase === "done") { LeAudio.engine(false); return show(head, result()); }
    if (st.phase === "lobby") return show(head, lobby());
    // the race: driver, pit wall, pit stop, retired or watching
    const cv = h("canvas.le-canvas"), wrap = h("div.le-wrap" + (mode === "drive" ? ".le-big" : ".le-tv"), cv);
    ui.cv = { el: cv, ctx: cv.getContext("2d"), wrap, w: 0, h: 0, dpr: 0 };
    swipes(wrap);
    ui.radio = h("div.le-radio", { hidden: true });
    wrap.append(ui.radio);
    ui.hud = { pos: h("b.le-pos"), lap: h("span.le-lap"), clock: h("span.le-clock"), left: h("span.le-left") };
    const top = h("div.le-top", ui.hud.pos, ui.hud.lap, ui.hud.clock, ui.hud.left);
    ui.board = h("div.le-board");
    const roleTag = tm && tm.roles ? h("div.le-role", LE_ROLES[tm.roles[myId] || "crew"][0], " ", I18N.tr(LE_ROLES[tm.roles[myId] || "crew"][1]),
      h("span.le-teamtag", { style: { "--tc": tm.color } }, "#" + tm.num, " ", C(tm.name))) : null;
    if (mode === "drive") {
      Object.assign(ui.hud, { speed: h("b.le-speed"), temp: h("div.le-gauge.le-temp"), fuel: h("div.le-gauge"), tyre: h("div.le-gauge"), tyreIc: h("span"), dmg: h("span.le-dmg") });
      const gauges = h("div.le-gauges", ui.hud.speed, h("span.le-g", "🌡️", ui.hud.temp), h("span.le-g", "⛽", ui.hud.fuel), h("span.le-g", ui.hud.tyreIc, ui.hud.tyre), ui.hud.dmg);
      ui.thr = h("div.le-thr", { role: "slider", "aria-label": T("Throttle"), "aria-valuemin": 0, "aria-valuemax": 10, tabindex: 0 }, h("div.le-thr-fill"), h("div.le-thr-knob"), h("span.le-thr-lbl"));
      thrLever(ui.thr);
      wrap.append(ui.thr);
      const btn = (c, ic, label) => h("button.le-btn", { type: "button", "aria-label": label, title: label, onpointerdown: e => { e.preventDefault(); input(c); }, onclick: e => { if (e.detail === 0) input(c); } }, ic);
      ui.hud.boxBtn = h("button.le-btn.le-boxbtn", { type: "button", onclick: toggleBox }, "📦 ", T("Box"));
      const pad = h("div.le-pad", btn("l", "◀", T("Move left")), btn("r", "▶", T("Move right")), ui.hud.boxBtn);
      show(head, top, ui.board, gauges, wrap, pad);
      drawThrottle();
    } else if (mode === "pit") {
      ui.pitBox = h("div.le-pit");
      show(head, top, ui.board, roleTag, ui.pitBox);
      ui.cv = null;
      drawPit(true);
    } else {
      ui.tele = mode === "wall" || mode === "out" ? h("div.le-tele") : null;
      const showRadar = mode === "wall" && (tm.roles[myId] === "engineer" || !Object.values(tm.roles).includes("engineer"));
      ui.radar = showRadar ? h("div.le-radar") : null;
      const radio = mode === "wall" ? h("div.le-radios", ...Object.entries(LE_RADIO).map(([k, [ic, txt]]) => h("button.btn.small.ghost", { onclick: async () => {
        try { setState(await req("/radio", { method: "POST", body: { msg: k } })); LeAudio.radio(); toast("📻 " + I18N.tr(txt), "good"); } catch (e) { toast(e.message, "bad"); } } }, ic, " ", I18N.tr(txt)))) : null;
      const note = mode === "out" ? h("p.center.muted", "🏳️ ", T("Your team retired – it keeps its laps.")) : mode === "watch" ? h("p.center.muted.small", T("You are watching the leader.")) : null;
      show(head, top, ui.board, roleTag, wrap, note, ui.tele, ui.radar, radio);
    }
    drawBoard(); drawTele();
  }
  function thrLever(el) {
    let on = false;
    const setFrom = e => { const r = el.getBoundingClientRect(); setThr((1 - (e.clientY - r.top) / r.height) * 10); };
    el.addEventListener("pointerdown", e => { e.preventDefault(); e.stopPropagation(); if (gameT() < 0 && !introSkip) { introSkip = true; } on = true; try { el.setPointerCapture(e.pointerId); } catch {} setFrom(e); });
    el.addEventListener("pointermove", e => { if (on) { e.stopPropagation(); setFrom(e); } });
    const up = () => { on = false; };
    el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    el.addEventListener("keydown", e => { if (e.key === "ArrowUp") { e.preventDefault(); e.stopPropagation(); setThr(thrLocal + 1); } else if (e.key === "ArrowDown") { e.preventDefault(); e.stopPropagation(); setThr(thrLocal - 1); } });
  }
  function drawThrottle() {
    if (!ui.thr) return;
    ui.thr.style.setProperty("--v", thrLocal * 10 + "%");
    ui.thr.setAttribute("aria-valuenow", thrLocal);
    ui.thr.dataset.push = thrLocal >= 9 ? "hot" : thrLocal >= 8 ? "warm" : "ok";
    ui.thr.querySelector(".le-thr-lbl").textContent = String(thrLocal);
  }
  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobby() {
    const n = st.nteams || 1, styles = [["Comet Racing", "#e03131"], ["Blue Falcon Works", "#1c7ed6"], ["Pine Cone Motors", "#2f9e44"], ["Sunrise Speedsters", "#f08c00"]];
    const mine = (st.players.find(p => p.id === myId) || {}).team;
    const cards = Array.from({ length: n }, (_, i) => {
      const ps = st.players.filter(p => !p.bot && p.team === i), full = ps.length >= st.rules.team_size;
      return h("div.le-tcard", { style: { "--tc": styles[i][1] } }, h("div.le-tname", C(styles[i][0])),
        h("div.le-tseats", ...ps.map(p => h("span.le-tseat" + (p.id === myId ? ".me" : ""), seatIcon(p, 28), C(p.name, "small")))),
        st.joined && mine !== i && !full ? h("button.btn.small.ghost", { onclick: () => act("team", { team: i }) }, T("Join this team")) : null,
        h("div.small.muted", ps.length + " / " + st.rules.team_size));
    });
    const host = isHost() && st.status !== "done" ? h("div.row.center.host-bar", n > 1 ? h("button.btn.ghost", { onclick: () => act("mix") }, "🔀 ", T("Mix teams")) : null,
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))) : null;
    const story = h("p.small.muted", I18N.tr(T("24 race hours on the Circuit des Tannes in {0} minutes – through the night and into the next afternoon. The most laps wins.")).replace("{0}", st.rules.minutes));
    const roles = h("p.small", "🏎️ ", T("Alone: drive and do the pit stops yourself. 2–3 people: driver and pit crew. 4–5: also a race engineer. The roles rotate at every pit stop."));
    return [h("section.card.center", st.joined ? h("h2", T("Waiting for the start …")) : h("p", T("Play along on this device?")), story, roles,
      st.joined ? null : h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))),
      h("div.le-teams", ...cards), st.bots ? h("p.small.muted.center", "🤖 ", I18N.tr(T("+{0} bot teams")).replace("{0}", st.bots)) : null,
      st.coins_on ? h("p.small.center", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", leCoins(st.rewards))) : null, host];
  }
  function result() {
    const ts = st.teams || [];
    const ranked = (st.ranking || ts.map((_, i) => i)).map(i => ts[i]);
    const m = st.players.find(p => p.id === myId) || {};
    const myT = m.team != null ? ts[m.team] : null;
    if (!cheered && myT && myT.place && myT.place <= 3 && st.complete) { cheered = true; if (!leReduced()) confetti(); try { Sound.play("done"); } catch {} LeAudio.fanfare(); }
    const members = t => t.members.map(id => person(id)).filter(Boolean);
    const step = (t, n) => t ? h("div.le-step.le-p" + n, { style: { "--tc": t.color } },
      n === 1 && st.complete ? h("div.le-bubbly", { "aria-hidden": "true" }, h("span.le-bottle", "🍾"), ...Array.from({ length: leReduced() ? 0 : 18 }, (_, k) => h("i", { style: { "--k": k } }))) : null,
      h("div.le-pmembers", ...members(t).map(p => seatIcon(p, n === 1 ? 40 : 32))), h("b.le-pnum", "#" + t.num), C(t.name, "div.small.le-pname"),
      h("div.le-block", h("span.le-medal", ["🥇", "🥈", "🥉"][n - 1]), h("small", leLapsTxt(t.laps)))) : h("div.le-step.le-empty");
    const top3 = [ranked[1], ranked[0], ranked[2]];
    const again = st.solo && st.host === me.id ? h("button.btn", { onclick: async () => {
      try { await api("community/langstrecke/start", { method: "POST", body: { solo: true } }); setState(await req("")); draw(true); } catch (e) { toast(e.message, "bad"); }
    } }, "🔄 ", T("Race again")) : null;
    const lead = ranked[0];
    return h("section.card.center.le-result",
      h("h2", "🏆 ", C(lead ? lead.name : ""), " ", T("wins!")),
      h("div.le-podium", step(top3[0], 2), step(top3[1], 1), step(top3[2], 3)),
      st.complete ? h("p.small.le-juice", "🍇 ", T("A shower of sparkling grape juice for the winners!")) : null,
      m.record && m.record.laps ? h("p.le-record", "🎉 ", T("New record: most laps!")) : null,
      m.record && m.record.pit ? h("p.le-record", "⏱ ", T("New record: fastest pit stop!")) : null,
      h("ol.pk-rank.le-rank-list", ...ranked.map(t => h("li" + (t === myT ? ".le-me" : ""), h("span.pj-medal", ["🥇", "🥈", "🥉"][t.place - 1] || t.place + "."),
        h("span.le-swatch", { style: { background: t.color } }, String(t.num)),
        h("span.grow", C(t.name, "strong"), h("br"), h("span.small.muted", members(t).map(p => p.name).join(", "))),
        h("span.small", leLapsTxt(t.laps), t.out != null ? " 🏳️" : "", h("br"), t.best_pit ? "🅿️ " + t.best_pit.toFixed(1) + " s" : ""),
        (() => { const c = members(t).reduce((s, p) => s + (p.coins || 0), 0); return c ? h("b.pj-plus", "+" + (members(t).find(p => p.coins) || {}).coins + " 🪙") : null; })()))),
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on || st.players.filter(p => !p.bot).length < 2 ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", again, h("button.btn" + (again ? ".ghost" : ""), { onclick: back }, T("Back"))));
  }
  (async () => { try { setState(await req("")); } catch {} draw(true); poll(); })();
  const redraw = setInterval(() => { if (!alive) clearInterval(redraw); else if (playing()) draw(); }, 300);
  document.addEventListener("visibilitychange", () => { if (document.hidden) LeAudio.engine(false); });
  raf = requestAnimationFrame(frame);
}

async function langstreckeView() {
  const box = h("div.le-live");
  screen("games", box);
  langstreckeLive(box, S.profile, () => go("games"));
}

async function langstreckeFamilyCard() {
  const c = S.me && S.me.community, g = c && c.langstrecke;
  return h("section.card.quiz-card", h("h2", LE_ICON, " ", leName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("langstrecke") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Racing stables, one car each: drive, change tyres, refuel and repair as a team – 24 race hours, day and night.")),
         h("div.row.wrap", h("button.btn", { onclick: () => langstreckeStartDialog(false, () => go("langstrecke")) }, "👨‍👩‍👧 ", T("Open a family table")),
           h("button.btn.ghost", { onclick: () => langstreckeStartDialog(true, () => go("langstrecke")) }, LE_ICON, " ", T("Alone")))]);
}
