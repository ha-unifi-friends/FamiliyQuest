// «24h Endurance» (24-Stunden-Rennen) – a short, fast live team race on the fictional «Circuit des Tannes»
// (familyquest/langstrecke.py). Teams are racing stables with one car each. One short lap, then the car drives into
// the pits by itself and the next person of the team drives. The driver dodges on three lanes (swipe / arrow keys)
// and holds the pedal for full speed (it heats the engine and drains the battery much faster – empty: the emergency
// drive mode); the pit crew – everybody else of the team – prepares the stop on their phones during the lap: plug the
// spare battery in (it charges over time – the next driver gets it with whatever charge it has), lay out the 4 tyres,
// after an overheat the spare engine. The stop takes longer when the tyres were not ready – a stopwatch for the whole team. Sudden rain showers
// (slicks or rain tyres – the crew chooses), day and night, two chicanes with kerbs, cheering stands at the pits.
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
const LE = { L: 640, DT: 0.1, VLIFT: 20, VFULL: 30, ACC: 7, BRAKE: 14, COAST: 5, VBRAKE: 8, VLIMP: 13, VSLOW: 10, SLOW_T: 1.2,
  SAFE: 23, SAFE_TRICKY: 18, VOFF: 6, OFF_T: 3,
  HEAT: 2.6, HEAT_JR: 1.7, COOL: 4, TMIN: 60, YELLOW: 85, RED: 100, COUNTDOWN: 6,
  E_FULL: 0.16, E_LIFT: 0.07, REGEN: 0.3, VEMERG: 7,
  STOP_BASE: 2, BAT_SWAP: 1, PEN_PREP: 4, ENG_READY: 2, ENG_SWAP: 6, GARAGE: 4, CHARGE_RATE: 4, GARAGE_PLUG: 8, ENGINE_HOLD: 2,
  WET_SLICK: 0.8, DRY_RAIN: 0.9, KERB_T: 0.6, KERB_T_WET: 1 };
// the spare battery's charge at game time `at` (the server's timestamps; the server decides at the stop)
const leSpare = (sp, at) => (!sp ? 0 : sp.plug == null || at <= sp.plug ? sp.c0 : Math.min(100, sp.c0 + LE.CHARGE_RATE * (at - sp.plug)));
// what the rest of the lap needs: lifted off all the way / a normal mix of full throttle and lifting
const leNeed = d => { const left = LE.L - (((d % LE.L) + LE.L) % LE.L); return { lift: left * LE.E_LIFT, mix: left * (LE.E_FULL + LE.E_LIFT) / 2 }; };
const LE_OIL = 0, LE_CONES = 1, LE_SLOWCAR = 2;
const LE_CHICANES = [[210, 245, 2, 0], [450, 485, 0, 2]];          // gate a, gate b, kerb lane at a, at b
const LE_FREE = [[100, 180], [285, 420], [525, 600]];              // the parts of the lap without a chicane
function leFreeX(u) {
  let x = u * LE_FREE.reduce((s, [a, b]) => s + b - a, 0);
  for (const [a, b] of LE_FREE) { if (x <= b - a) return a + x; x -= b - a; }
  return LE_FREE[LE_FREE.length - 1][1];
}
// the chicane gates: [[x in the lap, [kerb lanes]], …] – in the rain or at night the kerb reaches the middle lane
const leKerbs = tricky => LE_CHICANES.flatMap(([xa, xb, la, lb]) => [[xa, tricky ? [la, 1] : [la]], [xb, tricky ? [lb, 1] : [lb]]]);
const leGrip = (tyre, rain) => (rain ? (tyre !== "r" ? LE.WET_SLICK : 1) : (tyre === "r" ? LE.DRY_RAIN : 1));
const leInWin = (wins, s) => (wins || []).some(([a, b]) => a <= s && s < b);

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
    const n = jr ? 2 : 3 + Math.floor(rnd() * 2);
    got = [];
    for (let i = 0; i < n; i++) {
      const x = leFreeX((i + 0.15 + 0.7 * rnd()) / n);
      const lane = Math.floor(rnd() * 3), r = rnd();
      got.push([Math.floor(x * 10 + 0.5) / 10, lane, r < 0.35 ? LE_OIL : r < 0.7 ? LE_CONES : LE_SLOWCAR]);
    }
    if (_leThings.size > 600) _leThings.clear();
    _leThings.set(key, got);
  }
  return got;
}
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
  else if (c === "u") car.thr = Math.trunc(v) > 0 ? 1 : Math.trunc(v) < 0 ? -1 : 0;     // full throttle, lifted, braking
}
// one step of DT seconds from game time s – the same as step() in langstrecke.py
function leStep(car, s, seed, jr, rain = false, dark = false) {
  const ev = [], DT = LE.DT;
  if (car.pit) { car.temp = Math.max(LE.TMIN, car.temp - LE.COOL * DT); return ev; }
  const emg = car.bat <= 0;                          // the battery is empty: the emergency drive mode
  const full = car.thr > 0 && !car.eng && !emg;
  let vt = car.eng ? LE.VLIMP : (full ? LE.VFULL : LE.VLIFT) * leGrip(car.tyre, rain);
  if (emg) vt = Math.min(vt, LE.VEMERG);
  let dec = LE.COAST;
  if (car.thr < 0) { vt = Math.min(vt, LE.VBRAKE); dec = LE.BRAKE; }
  if (car.slow > 0) { vt = Math.min(vt, (car.off || 0) > 0 ? LE.VOFF : LE.VSLOW); dec = LE.BRAKE; car.slow = Math.max(0, car.slow - DT); }
  car.off = Math.max(0, (car.off || 0) - DT);
  const v0 = car.v;
  let v = v0 < vt ? Math.min(vt, v0 + LE.ACC * DT) : Math.max(vt, v0 - dec * DT);
  if (!emg) {                                        // the battery: by the metre – full throttle much more; braking gives a little back
    let use = (full ? LE.E_FULL : LE.E_LIFT) * v * DT;
    if (car.thr < 0 && v < v0) use -= LE.REGEN * (v0 - v);
    car.bat = Math.max(0, Math.min(100, car.bat - use));
    if (car.bat <= 0) { car.flat += 1; ev.push("empty"); }
  }
  const d0 = car.d;
  let d1 = d0 + v * DT;
  if (full) car.temp = Math.min(LE.RED, car.temp + (jr ? LE.HEAT_JR : LE.HEAT) * DT);
  else car.temp = Math.max(LE.TMIN, car.temp - LE.COOL * DT);
  if (full && car.temp >= LE.RED - 1e-9) { car.eng = 1; car.blows += 1; car.temp = 80; ev.push("blow"); }
  for (;;) {
    const things = leThings(seed, car.olap, jr);
    if (car.ob >= things.length) { car.olap += 1; car.ob = 0; if (car.olap * LE.L > d1) break; continue; }
    const [x, lane] = things[car.ob], xa = car.olap * LE.L + x;
    if (xa > d1) break;
    car.ob += 1;
    if (xa <= d0 || lane !== car.lane) continue;
    car.slow = LE.SLOW_T; car.hits += 1; v = Math.min(v, LE.VSLOW + 4); ev.push("hit");
  }
  const lap0 = Math.floor(d0 / LE.L);                // the chicanes: too fast into one – off into the gravel; a kerb at the gate in my lane
  if (lap0 >= 0) for (const [xa0] of LE_CHICANES) {
    const xa = lap0 * LE.L + xa0;
    if (d0 < xa && xa <= d1 && v > (rain || dark ? LE.SAFE_TRICKY : LE.SAFE) + 1e-9) {
      car.slow = Math.max(car.slow, LE.OFF_T); car.off = LE.OFF_T; car.offs = (car.offs || 0) + 1; v = Math.min(v, LE.VOFF); ev.push("off");
    }
  }
  if (lap0 >= 0) for (const [x, lanes] of leKerbs(rain || dark)) {
    const xa = lap0 * LE.L + x;
    if (d0 < xa && xa <= d1 && lanes.includes(car.lane)) { car.slow = Math.max(car.slow, rain ? LE.KERB_T_WET : LE.KERB_T); car.kerb += 1; v = Math.min(v, LE.VSLOW + 6); ev.push("kerb"); }
  }
  const n0 = Math.floor(d0 / LE.L), n1 = Math.floor(d1 / LE.L);
  if (n1 > n0 && n0 >= 0) {
    const lt = s + DT - car.ls;
    car.best = !car.best || lt < car.best ? Math.round(lt * 100) / 100 : car.best;
    car.ls = Math.round((s + DT) * 100) / 100;
    d1 = n1 * LE.L; v = 0; car.pit = 1;
    ev.push("lap", "pit");
  } else if (n1 > n0) car.ls = Math.round((s + DT) * 100) / 100;
  car.d = d1; car.v = v;
  return ev;
}

// The server's clock on this device: offset = server time − performance.now() (in s). The sample with the shortest
// round trip is the most exact one – but a phone that slept (in the lobby, before the start) comes back with a
// performance.now() that stood still (iOS, Android), and later samples are slower (the canvas is busy) than the best
// one from the lobby. So a sample that PROVES the offset wrong – the server's time lies between sending (t1) and
// receiving (t2), the offset between now − t2 and now − t1 – replaces it at once. Else the app stays that far behind:
// the intro with the start lights for the whole race, the crew jobs below it, the driver's inputs too old.
function leClockSample(ck, now, t1, t2) {
  const rtt = Math.max(0, t2 - t1), mid = now - (t1 + t2) / 2;
  if (ck.offset == null || ck.offset < now - t2 - 0.05 || ck.offset > now - t1 + 0.05) return { offset: mid, rtt };
  if (rtt <= ck.rtt * 1.15) return { offset: mid, rtt: Math.min(ck.rtt, rtt) };
  return { offset: ck.offset, rtt: ck.rtt * 1.01 };                // the best round trip ages: a slower network later counts again
}
// Which screen this player sees – decided in ONE place, from the server's roles and the race clock (t = game time,
// < 0 during the 6 s start countdown): lobby | done | watch | pit | drive | crew. `intro`: the start lights are on the
// stage – for everybody at the start, never during a pit stop; the crew gets its jobs only after the start.
function leScreen(st, myId, t) {
  if (!st) return { mode: "none", intro: false };
  if (st.phase === "lobby" || st.phase === "done") return { mode: st.phase, intro: false };
  const tm = st.teams && st.my_team != null ? st.teams[st.my_team] : null;
  const intro = st.phase === "play" && st.status !== "done" && t < 0;
  if (!st.joined || !tm) return { mode: "watch", intro };
  if (tm.car && tm.car.pit && tm.stop) return { mode: "pit", intro: false };
  return { mode: tm.driver === String(myId) ? "drive" : "crew", intro };
}

// ---------------------------------------------------------------- the rules, the start
const LE_PARTS = { base: ["🔄", T("Stop and driver change")], garage: ["🏠", T("The garage prepares")],
  tyres: ["🛞", T("Tyres")], battery: ["🔋", T("Battery swap")], engine: ["🔧", T("Engine swap")] };
// the countries a team can race for (ISO codes, the same list as langstrecke.COUNTRIES), by region
const LE_COUNTRIES = {
  BE: T("Belgium"), BG: T("Bulgaria"), DK: T("Denmark"), DE: T("Germany"), FI: T("Finland"), FR: T("France"), GR: T("Greece"), GB: T("Great Britain"),
  IE: T("Ireland"), IT: T("Italy"), LV: T("Latvia"), LI: T("Liechtenstein"), LU: T("Luxembourg"), MC: T("Monaco"), NL: T("Netherlands"), NO: T("Norway"),
  AT: T("Austria"), PL: T("Poland"), PT: T("Portugal"), RO: T("Romania"), RU: T("Russia"), SM: T("San Marino"), SE: T("Sweden"), CH: T("Switzerland"),
  SK: T("Slovakia"), SI: T("Slovenia"), ES: T("Spain"), CZ: T("Czechia"), TR: T("Türkiye"), HU: T("Hungary"), BY: T("Belarus"),
  AR: T("Argentina"), BO: T("Bolivia"), BR: T("Brazil"), CL: T("Chile"), DO: T("Dominican Republic"), EC: T("Ecuador"), GT: T("Guatemala"), CA: T("Canada"),
  CO: T("Colombia"), CU: T("Cuba"), MX: T("Mexico"), PA: T("Panama"), PR: T("Puerto Rico"), KN: T("Saint Kitts and Nevis"), US: T("USA"), VE: T("Venezuela"),
  CN: T("China"), HK: T("Hong Kong"), IN: T("India"), ID: T("Indonesia"), JP: T("Japan"), QA: T("Qatar"), MY: T("Malaysia"), OM: T("Oman"),
  SA: T("Saudi Arabia"), SG: T("Singapore"), KR: T("South Korea"), SY: T("Syria"), TW: T("Taiwan"), TH: T("Thailand"), AE: T("United Arab Emirates"),
  AU: T("Australia"), MA: T("Morocco"), NZ: T("New Zealand"), ZA: T("South Africa") };
const LE_REGIONS = [[T("Europe"), "BE BG DK DE FI FR GR GB IE IT LV LI LU MC NL NO AT PL PT RO RU SM SE CH SK SI ES CZ TR HU BY"],
  [T("Americas"), "AR BO BR CL DO EC GT CA CO CU MX PA PR KN US VE"], [T("Asia & Middle East"), "CN HK IN ID JP QA MY OM SA SG KR SY TW TH AE"],
  [T("Africa & Oceania"), "AU MA NZ ZA"]].map(([n, cs]) => [n, cs.split(" ")]);
// the family's own country from the app's language (de-CH → CH …), else none
const leHomeCountry = () => ({ "de-CH": "CH", "de-DE": "DE", "fr-FR": "FR", "it-IT": "IT", "es-ES": "ES", "nl-NL": "NL", "pl-PL": "PL", "pt-BR": "BR", "sv-SE": "SE" })[I18N.base || I18N.lang] || null;
// flags as emoji – where the system has no emoji flags (Windows) the ISO code as a small chip instead
let _leFlagOk = null;
function leFlagOk() {
  if (_leFlagOk != null) return _leFlagOk;
  _leFlagOk = false;
  try {
    const c = document.createElement("canvas"); c.width = c.height = 24;
    const x = c.getContext("2d", { willReadFrequently: true }); x.font = "18px sans-serif"; x.textBaseline = "top"; x.fillText("\u{1F1E8}\u{1F1ED}", 0, 0);
    const d = x.getImageData(0, 0, 24, 24).data;
    for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 100 && d[i] > 150 && d[i + 1] < 90) { _leFlagOk = true; break; }    // red of the Swiss flag
  } catch {}
  return _leFlagOk;
}
const leFlag = c => (c && /^[A-Z]{2}$/.test(c) ? (leFlagOk() ? String.fromCodePoint(...[...c].map(x => 0x1F1E6 + x.charCodeAt(0) - 65)) : c) : "");
const leFlagEl = c => (c && /^[A-Z]{2}$/.test(c) ? (leFlagOk() ? h("span.le-flag", { title: I18N.tr(LE_COUNTRIES[c] || c) }, leFlag(c)) : h("span.le-cc", { title: I18N.tr(LE_COUNTRIES[c] || c) }, c)) : null);
// the picker: «no country», then the regions, each alphabetical in the viewer's language
function leCountrySelect(cur, onchange) {
  const name = c => I18N.tr(LE_COUNTRIES[c] || c);
  return h("select.le-country", { onchange: e => onchange(e.target.value), "aria-label": I18N.tr(T("Country")) },
    h("option", { value: "", selected: !cur }, "— ", I18N.tr(T("No country"))),
    ...LE_REGIONS.map(([rg, cs]) => h("optgroup", { label: I18N.tr(rg) },
      ...cs.slice().sort((a, b) => name(a).localeCompare(name(b), I18N.lang)).map(c => h("option", { value: c, selected: c === cur }, (leFlagOk() ? leFlag(c) + " " : "") + name(c))))));
}
const leTyreName = ty => (ty === "r" ? "🌧️ " + I18N.tr(T("Rain tyres")) : "☀️ " + I18N.tr(T("Slicks")));

function langstreckeRulesView(r, rewards) {
  r = r || {};
  const items = [
    I18N.tr(T("24 race hours in {0} minutes on the Circuit des Tannes. The most laps wins.")).replace("{0}", r.minutes || 8),
    T("A short lap, then the car drives into the pits by itself – and the next person of the team drives."),
    T("Driver: swipe or ◀ ▶ to dodge, hold the pedal for full speed. In the red the engine overheats – it has to be swapped at the stop."),
    T("Brake (🛑) before the two chicanes – the boards show 150 / 100 / 50 m. Too fast and you go off into the gravel. Then change the lane past the kerbs."),
    T("Electric car: full throttle drains the battery much faster than cruising. Empty – emergency drive mode: the car crawls to the pits."),
    T("Two batteries per team: at every stop the spare goes in with whatever charge it has. Plug the used one in first – it needs about a lap to charge."),
    T("Pit crew (everybody else): during the lap plug in the spare battery and lay out the 4 tyres. After an overheat also prepare the spare engine."),
    T("The stop takes 3 s with the battery swap, +4 s if the tyres are not ready, +6 s for an engine swap (+2 s if prepared)."),
    r.weather ?? 1 ? T("Sudden rain showers: the crew picks slicks or rain tyres – watch the forecast. The wrong tyres are slower.") : null,
    T("In the rain and at night the chicanes need slower speed and the kerbs are wider."),
    T("Alone in a team: the garage prepares, every stop takes 5 s – it plugs the spare battery in only after 8 s."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", leCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

const leSel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
const leMinutes = v => leSel(v || 8, [5, 8, 12].map(n => [n, "⏱ " + n + " min"]));
const leWeather = v => leSel(v ? 1 : 0, [[1, "🌦️ " + I18N.tr(T("Rain showers"))], [0, "☀️ " + I18N.tr(T("Always dry"))]]);
const leDiff = v => leSel(v || "normal", [["junior", "🧒 " + I18N.tr(T("Junior"))], ["normal", "🏁 " + I18N.tr(T("Normal"))]]);
const leSize = v => leSel(v || 3, [1, 2, 3, 4, 5].map(n => [n, "👥 " + n]));

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
    h("p.small.muted", T("Short laps and a pit stop after every lap: one drives, the others charge the spare battery and get the tyres ready – then the next one drives.")),
    h("div.grid2", h("label.field", T("Race length"), minutes), h("label.field", T("Weather"), weather)),
    h("div.grid2", h("label.field", T("Difficulty"), diff)),
    solo ? null : h("div.grid2", h("label.field", T("Teams of people"), teams), h("label.field", T("People per team"), size)),
    h("div.grid2", h("label.field", T("Bot teams"), bots), h("label.field", T("Bots play"), level)),
    solo ? h("p.small.muted", T("Alone: you drive, the garage prepares the stops.")) : h("p.small.muted", T("Everybody joins on their own device and picks a team – guests via QR code.")),
    picker.el, coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: +bots.value, level: level.value, minutes: +minutes.value, weather: +weather.value, difficulty: diff.value, country: leHomeCountry(),
        bot_ids: picker.ids(), ...(solo ? {} : { team_size: +size.value, teams: +teams.value }) };
      try { await api("community/langstrecke/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("langstrecke", bots, level, picker.el);
}

// ---------------------------------------------------------------- sounds: the engine, the wrench, the lights
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
  wrench() { this.tone([180, 220, 200, 240, 210], "square", 0.06, 0.05, 0.05); },
  ok() { this.tone([660, 990], "triangle", 0.12, 0.1, 0.09); },
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
  ctx.strokeStyle = "#1d1f24"; ctx.lineWidth = Math.max(1, w * 0.04); ctx.fillStyle = "#1d1f24";   // the rear wing
  ctx.beginPath(); ctx.moveTo(x - w * 0.25, y - hgt * 0.95); ctx.lineTo(x - w * 0.25, y - hgt * 1.12); ctx.moveTo(x + w * 0.25, y - hgt * 0.95); ctx.lineTo(x + w * 0.25, y - hgt * 1.12); ctx.stroke();
  ctx.fillRect(x - w * 0.47, y - hgt * 1.2, w * 0.94, hgt * 0.12);
  if (num != null && w > 22) {
    ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(x, y - hgt * 0.5, w * 0.1, 0, 7); ctx.fill();
    ctx.fillStyle = "#111"; ctx.font = "800 " + Math.max(7, Math.round(w * 0.12)) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(String(num), x, y - hgt * 0.49);
  }
  if (o.hazard) {
    ctx.fillStyle = "#ffa94d"; ctx.fillRect(x - w * 0.42, y - hgt * 0.62, w * 0.08, hgt * 0.08); ctx.fillRect(x + w * 0.34, y - hgt * 0.62, w * 0.08, hgt * 0.08);
    if (o.emg) {                                                     // the emergency drive mode: big orange hazard lights
      for (const sx of [-0.38, 0.38]) {
        const g = ctx.createRadialGradient(x + sx * w, y - hgt * 0.58, 0, x + sx * w, y - hgt * 0.58, w * 0.28);
        g.addColorStop(0, "rgba(255,169,77,.75)"); g.addColorStop(1, "rgba(255,169,77,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x + sx * w, y - hgt * 0.58, w * 0.28, 0, 7); ctx.fill();
      }
    }
  }
  if (o.bat != null && w > 40) leBattery(ctx, x + w * 0.3, y - hgt * 1.42, w * 0.2, w * 0.09, o.bat);   // my battery above the rear wing
  if (o.flag && w > 30) {                                            // the country: a flag (or its code) on the rear
    ctx.font = (o.flag.length > 2 ? "" : "800 ") + Math.round(w * (o.flag.length > 2 ? 0.16 : 0.1)) + "px system-ui, 'Apple Color Emoji', 'Noto Color Emoji'"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    if (o.flag.length <= 2) { ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.fillRect(x - w * 0.36, y - hgt * 0.9, w * 0.2, hgt * 0.17); ctx.fillStyle = "#111"; }
    ctx.fillText(o.flag, x - w * 0.26, y - hgt * 0.82);
  }
  if (o.smoke) { ctx.fillStyle = "rgba(180,180,180,.5)"; for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.arc(x + (k - 1) * w * 0.2, y - hgt * (1.3 + k * 0.2), w * 0.12 * (1 + k * 0.4), 0, 7); ctx.fill(); } }
  ctx.restore();
}
// a battery lying on its side (x, y: the centre, w × hh), filled to pct – green / orange / red; a ⚡ while charging
function leBattery(ctx, x, y, w, hh, pct, charging) {
  ctx.save();
  const p = Math.max(0, Math.min(100, pct)) / 100, lw = Math.max(1, hh * 0.14), x0 = x - w / 2, y0 = y - hh / 2;
  ctx.fillStyle = "rgba(20,24,30,.85)"; ctx.fillRect(x0, y0, w, hh); ctx.fillRect(x0 + w, y - hh * 0.22, w * 0.07, hh * 0.44);
  ctx.fillStyle = p >= 0.5 ? "#40c057" : p >= 0.2 ? "#fd7e14" : "#fa5252";
  ctx.fillRect(x0 + lw, y0 + lw, (w - 2 * lw) * p, hh - 2 * lw);
  ctx.strokeStyle = "#f1f3f5"; ctx.lineWidth = lw; ctx.strokeRect(x0, y0, w, hh);
  if (charging && hh > 8) { ctx.fillStyle = "#ffe066"; ctx.font = "900 " + Math.round(hh * 0.8) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("⚡", x, y + 1); }
  ctx.restore();
}
// trackside advertising (own, invented): «Family Quest», «Home Assistant» with an own simple house, «Snowman Tyres»
// with a snowman made of three tyres – a board of w × hh with its top left corner at x, y
function leBanner(ctx, kind, x, y, w, hh) {
  ctx.save();
  ctx.fillStyle = ["#5b5bd6", "#f8f9fa", "#0b7285"][kind]; ctx.fillRect(x, y, w, hh);
  ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.lineWidth = Math.max(1, hh * 0.06); ctx.strokeRect(x, y, w, hh);
  const cy = y + hh / 2, s = hh * 0.7;
  ctx.textBaseline = "middle"; ctx.textAlign = "left";
  ctx.font = "900 " + Math.max(6, Math.round(hh * 0.42)) + "px system-ui, sans-serif";
  if (kind === 0) {
    ctx.fillStyle = "#ffd43b"; ctx.beginPath();                        // a star
    for (let k = 0; k < 10; k++) { const r = k % 2 ? s * 0.22 : s * 0.5, a = -Math.PI / 2 + k * Math.PI / 5; ctx.lineTo(x + hh * 0.55 + Math.cos(a) * r, cy + Math.sin(a) * r); }
    ctx.fill(); ctx.fillStyle = "#fff"; ctx.fillText("Family Quest", x + hh * 1.1, cy);
  } else if (kind === 1) {
    ctx.strokeStyle = "#1c7ed6"; ctx.lineWidth = Math.max(1, hh * 0.09); ctx.lineJoin = "round";   // an own simple house outline
    const hx = x + hh * 0.2, hw = s * 0.9;
    ctx.beginPath(); ctx.moveTo(hx, cy + s * 0.4); ctx.lineTo(hx, cy - s * 0.05); ctx.lineTo(hx + hw / 2, cy - s * 0.45); ctx.lineTo(hx + hw, cy - s * 0.05); ctx.lineTo(hx + hw, cy + s * 0.4); ctx.closePath(); ctx.stroke();
    ctx.fillStyle = "#1c7ed6"; ctx.fillRect(hx + hw * 0.4, cy + s * 0.1, hw * 0.2, s * 0.3);
    ctx.fillStyle = "#212529"; ctx.fillText("Home Assistant", x + hh * 1.1, cy);
  } else {
    for (let k = 0; k < 3; k++) {                                         // the snowman: three stacked tyres, a face on the top one
      const r = s * (0.24 - k * 0.04), ty = cy + s * 0.32 - k * s * 0.36;
      ctx.fillStyle = "#212529"; ctx.beginPath(); ctx.arc(x + hh * 0.55, ty, r, 0, 7); ctx.fill();
      ctx.fillStyle = "#f8f9fa"; ctx.beginPath(); ctx.arc(x + hh * 0.55, ty, r * 0.45, 0, 7); ctx.fill();
    }
    ctx.fillStyle = "#f76707"; ctx.fillRect(x + hh * 0.55, cy - s * 0.42, s * 0.14, s * 0.06);
    ctx.fillStyle = "#fff"; ctx.fillText(I18N.tr(T("Snowman Tyres")), x + hh * 1.1, cy);
  }
  ctx.restore();
}
// fans camping beside the track: a tent, a camper van, a campfire at night and a fan waving a sign «I ❤️ #7 🇨🇭»
function leCamp(ctx, x, y, u, t, k, sign, col, night) {
  ctx.save();
  ctx.fillStyle = ["#f08c00", "#2f9e44", "#1c7ed6"][k % 3];                       // the tent
  ctx.beginPath(); ctx.moveTo(x - u * 1.5, y); ctx.lineTo(x - u * 1.0, y - u * 0.7); ctx.lineTo(x - u * 0.5, y); ctx.fill();
  ctx.fillStyle = "rgba(0,0,0,.25)"; ctx.beginPath(); ctx.moveTo(x - u * 1.05, y); ctx.lineTo(x - u * 1.0, y - u * 0.4); ctx.lineTo(x - u * 0.9, y); ctx.fill();
  if (k % 2) {                                                                       // a camper van
    ctx.fillStyle = "#f1f3f5"; ctx.fillRect(x + u * 0.6, y - u * 0.75, u * 1.3, u * 0.65);
    ctx.fillStyle = "#74c0fc"; ctx.fillRect(x + u * 1.45, y - u * 0.65, u * 0.35, u * 0.25);
    ctx.fillStyle = "#212529"; ctx.beginPath(); ctx.arc(x + u * 0.9, y - u * 0.08, u * 0.12, 0, 7); ctx.arc(x + u * 1.6, y - u * 0.08, u * 0.12, 0, 7); ctx.fill();
  }
  if (night) {                                                                       // a campfire
    const f = 0.8 + 0.2 * Math.sin(t * 13 + k);
    ctx.fillStyle = "rgba(255,146,43,.35)"; ctx.beginPath(); ctx.arc(x - u * 0.2, y - u * 0.1, u * 0.45 * f, 0, 7); ctx.fill();
    ctx.fillStyle = "#ff922b"; ctx.beginPath(); ctx.moveTo(x - u * 0.32, y); ctx.lineTo(x - u * 0.2, y - u * 0.35 * f); ctx.lineTo(x - u * 0.08, y); ctx.fill();
  }
  const fx = x + u * 0.25, wave = Math.sin(t * 6 + k) * 0.35;                       // the fan: body, head, arms up with the sign
  ctx.fillStyle = col; ctx.fillRect(fx - u * 0.1, y - u * 0.55, u * 0.2, u * 0.35);
  ctx.fillStyle = "#f8d7b8"; ctx.beginPath(); ctx.arc(fx, y - u * 0.65, u * 0.1, 0, 7); ctx.fill();
  ctx.strokeStyle = "#f8d7b8"; ctx.lineWidth = Math.max(1, u * 0.05);
  ctx.beginPath(); ctx.moveTo(fx - u * 0.1, y - u * 0.5); ctx.lineTo(fx - u * 0.25 + wave * u * 0.2, y - u * 0.95); ctx.moveTo(fx + u * 0.1, y - u * 0.5); ctx.lineTo(fx + u * 0.25 + wave * u * 0.2, y - u * 0.95); ctx.stroke();
  const sw = u * 1.5, sh = u * 0.42, sx = fx - sw / 2 + wave * u * 0.2, sy = y - u * 1.38;
  ctx.fillStyle = "#fff"; ctx.fillRect(sx, sy, sw, sh); ctx.strokeStyle = col; ctx.lineWidth = Math.max(1, u * 0.04); ctx.strokeRect(sx, sy, sw, sh);
  ctx.fillStyle = "#c92a2a"; ctx.font = "900 " + Math.max(6, Math.round(sh * 0.62)) + "px system-ui, 'Apple Color Emoji', 'Noto Color Emoji'"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(sign, sx + sw / 2, sy + sh / 2 + 0.5);
  ctx.restore();
}
function leCarTop(ctx, x, y, len, ang, col, num, door, o = {}) {
  // a car from above (the intro, the pits): long body, cockpit, wheels, the number on the bonnet
  ctx.save(); ctx.translate(x, y); ctx.rotate(ang);
  const w = len * 0.42;
  ctx.fillStyle = "#15171c";
  [[-0.32, -0.55], [0.3, -0.55], [-0.32, 0.55], [0.3, 0.55]].forEach(([dx, dy], i) => { if (!(o.off || [])[i]) ctx.fillRect(dx * len - len * 0.08, dy * w - w * 0.12, len * 0.16, w * 0.24); });
  ctx.fillStyle = col;
  ctx.beginPath(); ctx.ellipse(0, 0, len / 2, w / 2, 0, 0, 7); ctx.fill();
  ctx.fillStyle = "rgba(20,30,50,.85)"; ctx.beginPath(); ctx.ellipse(-len * 0.05, 0, len * 0.16, w * 0.3, 0, 0, 7); ctx.fill();
  ctx.fillStyle = "#1d1f24"; ctx.fillRect(-len * 0.5, -w * 0.48, len * 0.07, w * 0.96);
  if (o.hood) { ctx.fillStyle = "#adb5bd"; ctx.fillRect(len * 0.08, -w * 0.3, len * 0.3, w * 0.6); }
  if (door) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-len * 0.12, w * 0.45); ctx.lineTo(-len * 0.12 + Math.cos(door) * len * 0.22, w * 0.45 + Math.sin(door) * len * 0.22); ctx.stroke(); }
  ctx.rotate(-ang);
  ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(len * 0.22 * Math.cos(ang), len * 0.22 * Math.sin(ang), len * 0.1, 0, 7); ctx.fill();
  ctx.fillStyle = "#111"; ctx.font = "800 " + Math.round(len * 0.12) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(String(num), len * 0.22 * Math.cos(ang), len * 0.22 * Math.sin(ang) + 0.5);
  ctx.restore();
}

function langstreckeLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", busy = false, raf = 0, syncing = false, lastSync = 0, cheered = false;
  let ck = { offset: null, rtt: 1e9 };                          // the server's clock (leClockSample)
  let pend = [], inflight = [], thrLocal = 0;
  const fired = new Set();
  let ui = {}, introSkip = false, introSound = 0, finalCue = false, lastTempWarn = 0, wasDriver = false, stopSeen = null;
  const local = { tyres: [false, false, false, false], plug: 0, engHold: 0, compound: null };    // my own taps until the server has them
  const imgs = {};
  const myId = String(me.id);
  box.classList.add("le-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => {
    alive = false; clearTimeout(timer); cancelAnimationFrame(raf); LeAudio.engine(false);
    box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open");
    window.removeEventListener("keydown", onKey); window.removeEventListener("keyup", onKeyUp);
  };
  window.addEventListener("hashchange", stop, { once: true });
  const nowS = () => performance.now() / 1000;
  const gameT = () => (st && ck.offset != null ? nowS() + ck.offset - st.t0 : -99);
  const playing = () => st && st.phase === "play" && st.status !== "done";
  const limit = () => (st && st.limit) || 480;
  const jr = () => st && st.rules && st.rules.difficulty === "junior";
  const simT = () => (st ? st.k / 10 : 0);
  const myTeam = () => (st && st.teams && st.my_team != null ? st.teams[st.my_team] : null);
  const pName = id => { const p = st.players.find(x => x.id === id); return p ? p.name : "?"; };
  const person = id => st.players.find(x => x.id === id);

  function clock(s, t1, t2) {
    if (!s || typeof s.now !== "number") return;
    ck = leClockSample(ck, s.now, t1, t2);
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
    st = s;
    if (!st || st.phase !== "play") return;
    const t = myTeam();
    if (!t) return;
    const drv = t.driver === myId;
    if (drv && !wasDriver) { thrLocal = 0; held.gas = false; held.brake = false; pend = []; inflight = []; }      // my turn: the pedals start released
    if (!drv) { pend = []; inflight = []; }
    wasDriver = drv;
    if (t.stop && stopSeen !== t.stop.t) {                                     // the car is in: the stopwatch starts
      stopSeen = t.stop.t;
      local.tyres = [false, false, false, false]; local.plug = 0; local.engHold = 0;
      if (gameT() - t.stop.t < 3) { LeAudio.tone([500, 400], "sine", 0.15, 0.1, 0.12); leBuzz([60, 40, 60]); }
    }
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
  const amDriver = () => { const t = myTeam(); return !!(t && t.driver === myId && t.car && !t.car.pit && playing()); };
  function input(c, v = 0) {
    if (!amDriver()) return;
    let t = gameT();
    if (t < 0 || t > limit()) return;
    t = Math.round(t * 1000) / 1000;
    pend.push([t, c, v]);
    if (c === "u") thrLocal = v;
    sync();
  }
  // the pedals: gas (hold = full throttle) and the brake (wins while held); neither = lifted off
  const held = { gas: false, brake: false };
  const pedals = () => {
    const v = held.brake ? -1 : held.gas ? 1 : 0;
    if (v !== thrLocal) input("u", v);
    if (ui.pedal) ui.pedal.classList.toggle("on", held.gas && !held.brake);
    if (ui.brake) ui.brake.classList.toggle("on", held.brake);
  };
  const pedal = on => { held.gas = !!on; pedals(); };
  const brake = on => { held.brake = !!on; pedals(); };
  const KEYS = { ArrowLeft: "l", KeyA: "l", ArrowRight: "r", KeyD: "r" };
  const GAS = ["ArrowUp", "KeyW", "Space"], BRAKE = ["ArrowDown", "KeyS"];
  function onKey(e) {
    if (!alive || !box.isConnected || !amDriver()) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || "")) return;
    if (KEYS[e.code]) { e.preventDefault(); if (!e.repeat) input(KEYS[e.code]); }
    else if (GAS.includes(e.code)) { e.preventDefault(); if (!e.repeat) pedal(1); }
    else if (BRAKE.includes(e.code)) { e.preventDefault(); if (!e.repeat) brake(1); }
  }
  function onKeyUp(e) {
    if (!amDriver()) return;
    if (GAS.includes(e.code)) { e.preventDefault(); pedal(0); } else if (BRAKE.includes(e.code)) { e.preventDefault(); brake(0); }
  }
  window.addEventListener("keydown", onKey);
  window.addEventListener("keyup", onKeyUp);
  function swipes(el) {
    let sx = 0, sy = 0, on = false;
    el.addEventListener("pointerdown", e => {
      if (gameT() < 0 && !introSkip) { introSkip = true; return; }       // a tap skips the intro
      on = true; sx = e.clientX; sy = e.clientY; try { el.setPointerCapture(e.pointerId); } catch {} e.preventDefault();
    });
    el.addEventListener("pointermove", e => {
      if (!on) return;
      const dx = e.clientX - sx;
      if (Math.abs(dx) < 24) return;
      on = false;
      input(dx < 0 ? "l" : "r");
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
    while ((k + 1) / 10 <= tNow + 1e-9 && n < 80 && !car.pit) {
      const s = k / 10;
      while (i < evs.length && evs[i][0] <= s + 1e-9) { leApply(car, evs[i][1], evs[i][2]); i++; }
      for (const e of leStep(car, s, seed, j, leInWin(st.rain, s), leDark(s, limit()) > 0.5)) effect(e, car, s);
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
    if (e === "hit" || e === "kerb") { try { Sound.play("wrong"); } catch {} leBuzz(e === "kerb" ? 40 : 70); ui.flash = nowS(); }
    else if (e === "off") { LeAudio.tone([160, 120, 90], "sawtooth", 0.25, 0.08, 0.12); leBuzz([120, 60, 120]); ui.flash = nowS(); ui.offAt = nowS(); }
    else if (e === "blow") { LeAudio.tone([200, 120, 80], "sawtooth", 0.3, 0.12, 0.2); leBuzz([200, 80, 200]); ui.flash = nowS(); }
    else if (e === "empty") { LeAudio.tone([660, 440, 330, 220], "square", 0.18, 0.08, 0.16); leBuzz([150, 80, 150, 80, 150]); ui.flash = nowS(); }
    else if (e === "lap") { try { Sound.play("tap"); } catch {} }
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
    const w = Math.max(100, Math.floor(r.width)), hh = Math.max(60, Math.floor(r.height));
    if (w !== c.w || hh !== c.h || dpr !== c.dpr) { c.w = w; c.h = hh; c.dpr = dpr; c.el.width = w * dpr; c.el.height = hh * dpr; c.el.style.width = w + "px"; c.el.style.height = hh + "px"; }
    c.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  const bend = x => {
    const xl = ((x % LE.L) + LE.L) % LE.L;
    let b = 0.4 * Math.sin(2 * Math.PI * x / LE.L * 2 + 0.7);
    for (const [xa, xb, la] of LE_CHICANES) {                 // the S of a chicane: one way, then the other
      const u = (xl - xa + 20) / (xb - xa + 40);
      if (u > 0 && u < 1) b += (la === 2 ? -1 : 1) * 0.9 * Math.sin(u * 2 * Math.PI);
    }
    return b;
  };
  function race(c, car, team, t, opts = {}) {
    const ctx = c.ctx, cw = c.w, ch = c.h, F = 9, VIEW = 110;
    const dk = leDark(t, limit()), rain = leInWin(st.rain, t);
    const view = VIEW - 40 * dk - (rain ? 15 : 0);
    const d = car.d + (car.pit ? 0 : car.v * Math.max(0, Math.min(0.1, t - (car._s ?? t))));
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
    g.addColorStop(0, rain ? (dk > 0.5 ? "#1c2230" : "#7d8796") : mix(sky[0][0], sky[1][0])); g.addColorStop(1, rain ? (dk > 0.5 ? "#2b3242" : "#aab3bf") : mix(sky[0][1], sky[1][1]));
    ctx.fillStyle = g; ctx.fillRect(0, 0, cw, yh + 1);
    if (dk > 0.3) { const r = leRand(11); ctx.fillStyle = `rgba(255,255,235,${0.6 * dk})`; for (let k = 0; k < 40; k++) ctx.fillRect(r() * cw, r() * yh * 0.85, 1.6, 1.6); }
    const hz = bd * cw * 0.15;
    ctx.fillStyle = dk > 0.5 ? "#0b1f17" : "#24573a";
    for (let k = -2; k < 26; k++) {                               // fir silhouettes (Les Tannes)
      const px = ((k * 37 - hz - (d * 0.05) % 37) % (cw + 80)) - 40, hh = 18 + ((k * 13) % 5) * 6;
      ctx.beginPath(); ctx.moveTo(px - 12, yh); ctx.lineTo(px, yh - hh); ctx.lineTo(px + 12, yh); ctx.fill();
    }
    ctx.fillStyle = dk > 0.5 ? "#0f2a1c" : rain ? "#3d6b4a" : "#4f9a5e"; ctx.fillRect(0, yh, cw, ch - yh);
    // the road in slices from far to near: kerbs red/white, the lane lines, the line before the pits
    const step = 4;
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
      const xl = ((d + z) % LE.L + LE.L) % LE.L;
      if (xl < step) { ctx.fillStyle = "#fff"; ctx.fillRect(pts(-0.6, z), Y(z) - 1, pts(2.6, z) - pts(-0.6, z), Math.max(2, (Y(za) - Y(z)) * 0.6)); }
    }
    // trees beside the track, things on it, the other cars – far first
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
        if (opts.car && (lp < car.olap || (lp === car.olap && i < car.ob)) && z < 0) return;
        items.push({ z, f: () => thing(ctx, kind, X(lane, z), Y(z), LW * sc_(z), t, i, dk) });
      });
    }
    for (let lp = Math.max(0, lap0); lp <= lap0 + 2; lp++) {    // now and then a banner beside the track (it changes from lap to lap)
      [25, 275, 580].forEach((x, i) => {
        const z = lp * LE.L + x - d;
        if (z < -F * 0.3 || z > view || (lp + i) % 4 === 3) return;
        const side = i % 2 ? 3.5 : -1.5;
        items.push({ z, f: () => { const u = LW * sc_(z), bx = X(side, z), y = Y(z), bw = u * 2.4, bh = u * 0.42;
          ctx.fillStyle = "#495057"; ctx.fillRect(bx - bw * 0.42, y - bh * 1.6, u * 0.04, bh * 1.6); ctx.fillRect(bx + bw * 0.38, y - bh * 1.6, u * 0.04, bh * 1.6);
          if (bw > 30) leBanner(ctx, (lp + i) % 3, bx - bw / 2, y - bh * 1.9, bw, bh); } });
      });
    }
    for (let lp = Math.max(0, lap0); lp <= lap0 + 2; lp++) {    // now and then fans camping beside the track – mostly for my team
      [140, 395].forEach((x, i) => {
        const z = lp * LE.L + x - d;
        if (z < -F * 0.3 || z > view || (lp * 2 + i) % 3 === 2) return;
        const others = st.teams.filter(o => o !== team), fan = (lp + i) % 4 === 3 && others.length ? others[(lp + i) % others.length] : team;
        const sign = "I ❤️ #" + fan.num + (fan.country ? " " + leFlag(fan.country) : "");
        items.push({ z, f: () => { const u = LW * sc_(z) * 0.5; if (u > 5) leCamp(ctx, X(i ? 3.9 : -1.9, z), Y(z), u, t, lp + i, sign, fan.color, dk > 0.5); } });
      });
    }
    const tricky = rain || dk > 0.5;
    for (let lp = Math.max(0, lap0); lp <= lap0 + 2; lp++) {    // the braking zones: boards 150 / 100 / 50 m before each chicane
      for (const [xa] of LE_CHICANES) for (const m of [150, 100, 50]) {
        const z = lp * LE.L + xa - m - d;
        if (z < -F * 0.3 || z > view) continue;
        items.push({ z, f: () => { const u = LW * sc_(z), bx = X(-1.0, z), y = Y(z), bw = u * 0.42, bh = u * 0.3;
          if (bw < 6) return;
          ctx.fillStyle = "#495057"; ctx.fillRect(bx - u * 0.02, y - bh * 1.8, u * 0.04, bh * 1.8);
          ctx.fillStyle = "#fff"; ctx.fillRect(bx - bw / 2, y - bh * 2.6, bw, bh); ctx.strokeStyle = "#e03131"; ctx.lineWidth = Math.max(1, u * 0.03); ctx.strokeRect(bx - bw / 2, y - bh * 2.6, bw, bh);
          ctx.fillStyle = "#111"; ctx.font = "900 " + Math.max(6, Math.round(bh * 0.7)) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(String(m), bx, y - bh * 2.1); } });
      }
    }
    for (let lp = Math.max(0, lap0); lp <= lap0 + 2; lp++) {
      for (const [x, lanes] of leKerbs(tricky)) {                // the chicane kerbs: red and white blocks across the lanes
        const z = lp * LE.L + x - d;
        if (z < -F * 0.3 || z > view) continue;
        items.push({ z, f: () => { for (const ln of lanes) { const u = LW * sc_(z), x0 = X(ln, z) - u * 0.48, y = Y(z);
          for (let q = 0; q < 6; q++) { ctx.fillStyle = q % 2 ? "#f1f3f5" : "#e03131"; ctx.fillRect(x0 + q * u * 0.16, y - u * 0.22, u * 0.16, u * 0.22); } } } });
      }
    }
    for (const o of st.teams) {
      if (o === team || o.pit) continue;
      let rel = (((o.d + o.v * Math.max(0, t - simT())) - d) % LE.L + LE.L) % LE.L;
      if (rel > LE.L / 2) rel -= LE.L;
      if (rel < 3 || rel > view) continue;
      // overtaking: a car close to mine in my lane moves over to a free lane (it never drives through my car)
      const mine = ui.lanePos != null && !opts.tv ? Math.round(ui.lanePos) : car.lane;
      let ln = o.lane;
      if (o.lane === mine) {
        const goal = mine === 1 ? (o.num % 2 ? 0 : 2) : 1, near = Math.max(0, Math.min(1, (24 - Math.abs(rel)) / 12));
        ln = o.lane + (goal - o.lane) * near;
      }
      const haz = o.emg && Math.floor(t * 2.5) % 2 === 0;           // a car in the emergency drive mode: hazard lights
      items.push({ z: rel, f: () => leCarRear(ctx, X(ln, rel), Y(rel), LW * sc_(rel) * 0.7, o.color, o.num, { night: dk > 0.4, alpha: 0.95, flag: leFlag(o.country), hazard: haz, emg: haz }) });
    }
    items.sort((a, b) => b.z - a.z).forEach(it => it.f());
    if (dk > 0) {                                     // night: dark all around, the headlights light the road ahead
      ctx.save();
      const hx = cw / 2, hy = Y(14);
      const grad = ctx.createRadialGradient(hx, hy, LW * 0.2, hx, hy, Math.max(cw, ch) * 0.75);
      grad.addColorStop(0, "rgba(4,8,22,0)"); grad.addColorStop(0.35, `rgba(4,8,22,${0.3 * dk})`); grad.addColorStop(1, `rgba(4,8,22,${0.7 * dk})`);
      ctx.fillStyle = grad; ctx.fillRect(0, 0, cw, ch);
      ctx.globalCompositeOperation = "lighter";
      const beam = ctx.createLinearGradient(0, ch, 0, Y(view * 0.6));
      beam.addColorStop(0, `rgba(255,240,190,${0.12 * dk})`); beam.addColorStop(1, "rgba(255,240,190,0)");
      ctx.fillStyle = beam; ctx.beginPath(); ctx.moveTo(cw * 0.3, ch); ctx.lineTo(X(0.2, view * 0.6), Y(view * 0.6)); ctx.lineTo(X(1.8, view * 0.6), Y(view * 0.6)); ctx.lineTo(cw * 0.7, ch); ctx.fill();
      ctx.restore();
    }
    const lp = ui.lanePos != null && !opts.tv ? ui.lanePos : car.lane;     // my car (or the team's car on the TV)
    const xs = cw / 2 + (lp - 1) * LW * sc_(0) * (opts.tv ? 1 : 0.65);
    const shake = car.v > 0 && !leReduced() ? Math.sin(t * 40) * 0.6 : 0;
    const slide = rain && car.tyre !== "r" && car.v > 5 && !leReduced() ? Math.sin(t * 7) * LW * 0.06 : 0;    // slicks in the rain slide
    const emg = car.bat != null && car.bat <= 0 && !car.pit, haz = emg && Math.floor(t * 2.5) % 2 === 0;
    leCarRear(ctx, xs + slide, ch * 0.97 + shake, LW * 1.05, team.color, team.num, { brake: !car.thr && car.v > LE.VLIFT + 1, night: dk > 0.4, smoke: !!car.eng, flag: leFlag(team.country),
      hazard: haz, emg: haz, bat: car.bat });
    if (rain) {
      ctx.strokeStyle = "rgba(200,215,235,.55)"; ctx.lineWidth = 1;
      const r = leRand(Math.floor(t * 12));
      ctx.beginPath(); for (let k = 0; k < 70; k++) { const x = r() * cw, y = r() * ch; ctx.moveTo(x, y); ctx.lineTo(x - 3, y + 12); } ctx.stroke();
    }
    if (ui.flash && nowS() - ui.flash < 0.35 && !opts.tv) { ctx.fillStyle = `rgba(242,84,91,${0.35 * (1 - (nowS() - ui.flash) / 0.35)})`; ctx.fillRect(0, 0, cw, ch); }
  }
  function thing(ctx, kind, x, y, w, t, i, dk) {
    const u = w * 0.5;
    if (kind === LE_OIL) {
      ctx.fillStyle = "#101114"; ctx.beginPath(); ctx.ellipse(x, y - u * 0.04, w * 0.42, Math.max(2, u * 0.2), 0, 0, 7); ctx.fill();
      ctx.strokeStyle = "rgba(130,90,255,.6)"; ctx.lineWidth = Math.max(1, u * 0.05); ctx.beginPath(); ctx.ellipse(x - w * 0.08, y - u * 0.06, w * 0.18, Math.max(1, u * 0.07), 0, 0, 7); ctx.stroke();
    } else if (kind === LE_CONES) {
      for (const dx of [-0.3, 0, 0.3]) {
        const cx = x + dx * w, s = u * 0.55;
        ctx.fillStyle = "#f76707"; ctx.beginPath(); ctx.moveTo(cx - s * 0.4, y); ctx.lineTo(cx, y - s * 1.3); ctx.lineTo(cx + s * 0.4, y); ctx.fill();
        ctx.fillStyle = "#fff"; ctx.fillRect(cx - s * 0.22, y - s * 0.7, s * 0.44, s * 0.16);
      }
    } else leCarRear(ctx, x, y, w * 0.7, "#ced4da", null, { hazard: Math.floor(t * 3 + i) % 2 === 0, night: dk > 0.4 });
  }

  // ---------- the intro: drivers next to the track run to their cars, doors, engines, lights (6 s)
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
    const run = skip ? 1 : Math.max(0, Math.min(1, (ti - 0.2) / 1.4)), inCar = skip || ti > 1.7;
    teams.forEach((tm, k) => {
      const cx = gap * (k + 1), cy = ty0 + (ty1 - ty0) * 0.3;
      const door = inCar ? (ti < 2.1 && !skip ? 1.2 * (2.1 - ti) / 0.4 : 0) : 1.2;
      const roar = !skip && ti > 2.1 && ti < 3.1 ? Math.sin(ti * 60) * 1.2 : 0;
      leCarTop(ctx, cx + roar, cy, len, -Math.PI / 2 + 0.5, tm.color, tm.num, door);
      if (!skip && ti > 2.1 && ti < 3.3) { ctx.fillStyle = "rgba(200,200,200,.5)"; ctx.beginPath(); ctx.arc(cx - len * 0.3, cy + len * 0.45 + (ti - 2.1) * 10, 5 + (ti - 2.1) * 6, 0, 7); ctx.fill(); }
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
    const lit = Math.max(0, Math.min(5, Math.floor((ti - 3.4) / 0.5) + 1));
    for (let k = 0; k < 5; k++) { ctx.fillStyle = ti >= LE.COUNTDOWN ? "#40c057" : k < lit ? "#fa5252" : "#3a3d44"; ctx.beginPath(); ctx.arc(lx + lw * (k + 0.5) / 5, ly, r, 0, 7); ctx.fill(); }
    if (lit !== introSound && ti >= 3.4) { introSound = lit; LeAudio.light(false); leBuzz(30); }
    ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.textBaseline = "bottom"; ctx.font = "900 " + Math.round(Math.min(cw * 0.07, 28)) + "px system-ui, sans-serif";
    ctx.lineWidth = 5; ctx.lineJoin = "round"; ctx.strokeStyle = "rgba(15,23,42,.7)";
    const msg = red ? I18N.tr(T("The race starts in {0} s")).replace("{0}", Math.ceil(-t)) : ti < 1.7 ? I18N.tr(T("Drivers, to your cars!")) : ti < 3.4 ? I18N.tr(T("Start your engines!")) : I18N.tr(T("It's starting now!"));
    ctx.strokeText(msg, cw / 2, ly - r * 1.8); ctx.fillText(msg, cw / 2, ly - r * 1.8);
    if (!skip && ti < 3) { ctx.font = "600 12px system-ui"; ctx.textBaseline = "top"; ctx.fillStyle = "rgba(255,255,255,.85)"; ctx.fillText(I18N.tr(T("Tap to skip")), cw / 2, ch * 0.92); }
    if (!skip && ti > 2.1 && !ui.roared) { ui.roared = true; LeAudio.roar(); leBuzz([40, 30, 80]); }
  }

  // ---------- the pit stop: the car in its box, the crew at work, the stopwatch
  function garage(c, tm, stp, t) {
    const ctx = c.ctx, w = c.w, hh = c.h, el = Math.max(0, t - stp.t), p = Math.min(1, el / stp.time), done = t >= stp.end;
    ctx.fillStyle = "#5c6370"; ctx.fillRect(0, 0, w, hh);
    ctx.fillStyle = "#4a5059"; for (let x = 0; x < w; x += 40) ctx.fillRect(x, 0, 20, hh);
    ctx.strokeStyle = "#fcc419"; ctx.lineWidth = 4; ctx.setLineDash([12, 9]); ctx.strokeRect(w * 0.14, hh * 0.16, w * 0.72, hh * 0.68); ctx.setLineDash([]);
    ctx.fillStyle = tm.color; ctx.fillRect(0, 0, w, 8);
    const len = Math.min(w * 0.56, hh * 1.25);
    const slideIn = leReduced() ? 0 : Math.max(0, 1 - el / 0.5), slideOut = done && !leReduced() ? Math.min(1, (t - stp.end) / 0.6) : 0;
    const cx = w / 2 - slideIn * w * 0.7 + slideOut * w * 0.8, cy = hh / 2;
    const working = !done && slideIn === 0;
    const lift = working ? Math.sin(t * 24) * 1.2 : 0;
    // the wheels come off and on again one after the other while the stop runs
    const off = [0, 1, 2, 3].map(i => working && p > 0.1 + i * 0.15 && p < 0.25 + i * 0.15);
    leCarTop(ctx, cx + lift, cy, len, 0, tm.color, tm.num, 0, { off, hood: working && stp.eng });
    const S = Math.min(34, hh * 0.2);
    const crew = tm.members.filter(m => m !== stp.next).map(person).filter(Boolean);
    const spots = [[-0.32, -1], [0.3, -1], [-0.32, 1], [0.3, 1]];
    if (working) {
      spots.forEach(([dx, side], i) => {                       // a tyre beside every wheel, a mechanic at it
        const x = cx + dx * len, y = cy + side * (len * 0.42 * 0.5 + S * 0.7);
        ctx.font = Math.round(S * 0.7) + "px system-ui, 'Apple Color Emoji', 'Noto Color Emoji'"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(off[i] ? "🔧" : "🛞", x, y + (off[i] ? Math.sin(t * 30) * 2 : 0));
      });
      if (stp.eng) { ctx.fillText(Math.floor(t * 3) % 2 ? "🏗️" : "⚙️", cx + len * 0.22, cy - len * 0.36); }
      crew.slice(0, 4).forEach((pp, i) => {                     // the crew (their avatars) around the car
        const [dx, side] = spots[i], x = cx + dx * len + (i % 2 ? 1 : -1) * S * 0.9, y = cy + side * (len * 0.42 * 0.5 + S * 0.7);
        const img = avatarImg(pp);
        if (img && img.complete && img.naturalWidth) ctx.drawImage(img, x - S / 2, y - S / 2 + Math.sin(t * 12 + i) * 1.5, S, S);
      });
    }
    // the battery swap: the used battery slides out to the charger at the pit wall, the spare slides in
    const chx = w * 0.9, chy = hh * 0.2, bw = Math.min(46, len * 0.34), bh = bw * 0.42;
    ctx.fillStyle = "#343a40"; ctx.fillRect(chx - 16, chy - 22, 32, 44);                         // the charger
    ctx.fillStyle = "#ffe066"; ctx.font = "900 18px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("⚡", chx, chy - 4);
    ctx.fillStyle = "#69db7c"; ctx.fillRect(chx - 10, chy + 12, 20, 4);
    const sw = Math.max(0, Math.min(1, (el - 0.5) / LE.BAT_SWAP)), slot = [cx + len * 0.05, cy];
    const outAt = [slot[0] + (chx - 40 - slot[0]) * sw, slot[1] + (hh * 0.82 - slot[1]) * sw];       // out: to the charger (below it)
    const inAt = [chx - 40 + (slot[0] - chx + 40) * sw, hh * 0.82 - (hh * 0.82 - slot[1]) * sw - (sw > 0 && sw < 1 ? bh * 1.4 : 0)];
    if (sw > 0) {
      ctx.save(); ctx.strokeStyle = "#ffd43b"; ctx.lineWidth = 3; ctx.setLineDash([7, 5]); ctx.lineDashOffset = leReduced() ? 0 : -t * 40;   // the cable to the used battery
      ctx.beginPath(); ctx.moveTo(chx, chy + 22); ctx.quadraticCurveTo(chx, outAt[1] + bh, outAt[0] + bw / 2, outAt[1]); ctx.stroke(); ctx.restore();
      leBattery(ctx, outAt[0], outAt[1], bw, bh, stp.bat_out ?? 0, sw >= 1);
    }
    if (sw < 1) leBattery(ctx, inAt[0], inAt[1], bw, bh, stp.bat_in ?? 100);
    else if (!done || slideOut < 1) leBattery(ctx, cx + len * 0.05 + slideOut * w * 0.8, cy, bw * 0.7, bh * 0.7, stp.bat_in ?? 100);
    if (done) { ctx.fillStyle = "rgba(64,192,87,.9)"; ctx.font = "900 " + Math.round(Math.min(w * 0.1, 40)) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(I18N.tr(T("GO!")), w / 2, hh / 2); }
  }
  function pitTick(t) {
    const tm = myTeam(), stp = tm && tm.stop;
    if (!stp || !ui.watch) return;
    const el = Math.max(0, Math.min(t, stp.end) - stp.t), done = t >= stp.end;
    ui.watch.textContent = (done ? "✓ " : "⏱ ") + el.toFixed(1) + " s";
    ui.watch.classList.toggle("le-done", done);
    ui.watchHand.style.setProperty("--a", (el % 10) * 36 + "deg");
    let sum = 0;                                               // the parts appear one after the other as the time runs
    ui.parts.forEach(([node, part]) => { const on = el >= sum - 1e-9; node.classList.toggle("le-on", on); sum += part[1]; });
    if (done && ui.crowd && !ui.crowd.dataset.cheered) {        // the stands cheer – loud for a fast stop
      ui.crowd.dataset.cheered = "1";
      ui.crowd.classList.add("cheer", ...(stp.time <= 4 ? ["big"] : []));
      if (stp.time <= 4) { LeAudio.tone([523, 784, 1046], "triangle", 0.18, 0.1, 0.1); toast("🎉 " + I18N.tr(T("Super fast stop!")), "good"); }
    }
  }
  // the stands beside the pits: people and the flags of the teams, waving when a stop is done
  function crowd(tm) {
    const people = ["🙋", "🧒", "👩", "🧑", "👨", "👧", "🧓", "👦", "🙌", "👩‍🦰", "🧔", "👱"];
    const flags = leFlagOk() ? [...new Set(st.teams.map(o => leFlag(o.country)).filter(Boolean))] : [];
    const r = leRand(tm.num * 31 + 7);
    const ad = h("canvas.le-ad", { width: 360, height: 26, "aria-hidden": "true" });     // the pit wall: a banner (another one at every stop)
    const ctx = ad.getContext("2d");
    if (ctx) leBanner(ctx, (tm.stop ? tm.stop.n : 0) % 3, 0, 0, 360, 26);
    return h("div.le-stands", h("div.le-crowd", { "aria-hidden": "true" }, ...Array.from({ length: 16 }, (_, k) =>
      h("span", { style: { "--k": k, "--d": (r() * 0.4).toFixed(2) + "s" } }, k % 4 === 1 && flags.length ? flags[(k >> 2) % flags.length] : people[Math.floor(r() * people.length)]))), ad);
  }

  // ---------- the frame
  function frame() {
    if (!alive || !box.isConnected) return stop();
    raf = requestAnimationFrame(frame);
    if (!st || st.phase !== "play") { LeAudio.engine(false); return; }
    const t = gameT();
    if (leScreen(st, myId, t).intro !== !!ui.intro) draw();     // the green light: the intro goes, the crew gets its jobs
    const team = myTeam();
    if (ui.go && t >= 0 && t < 0.2) { ui.go = false; LeAudio.light(true); leBuzz(120); }
    const c = ui.cv;
    if (c) {
      fit(c);
      if (ui.intro) intro(c, t);
      else if (ui.mode === "pit") { if (team && team.stop) garage(c, team, team.stop, t); }
      else {
        let car, tm = team;
        if (ui.mode === "drive") car = predicted(Math.min(t, limit()));
        else {
          tm = team || st.teams[st.standings[0]];
          car = { ...tm.car || {}, d: tm.d, v: tm.v, lane: tm.lane, pit: tm.pit, thr: (tm.car || {}).thr ?? 1, eng: tm.eng };
          car.d = tm.pit ? tm.d : tm.d + tm.v * Math.max(0, Math.min(1.5, t - simT()));
          car._s = t;
          if (car.bat == null && tm.emg) car.bat = 0;
        }
        if (car) {
          if (ui.mode === "drive") ui.lanePos = ui.lanePos == null ? car.lane : ui.lanePos + (car.lane - ui.lanePos) * 0.25;
          race(c, car, tm, t, { tv: ui.mode !== "drive", car: ui.mode === "drive" });
          const big = (txt, sub, col) => {
            const ctx = c.ctx;
            ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineWidth = 6; ctx.lineJoin = "round"; ctx.strokeStyle = "rgba(15,23,42,.75)"; ctx.fillStyle = col || "#fff";
            let fs = Math.round(Math.min(c.w * 0.1, c.h * 0.11));
            ctx.font = "900 " + fs + "px system-ui, sans-serif";
            const tw = ctx.measureText(txt).width;
            if (tw > c.w * 0.94) { fs = Math.floor(fs * c.w * 0.94 / tw); ctx.font = "900 " + fs + "px system-ui, sans-serif"; }     // a long word fits the screen
            ctx.strokeText(txt, c.w / 2, c.h * 0.4); ctx.fillText(txt, c.w / 2, c.h * 0.4);
            if (sub) {                                         // the line below – wrapped when it is too long for the screen
              const ss = Math.round(Math.min(c.w * 0.045, 18)), lines = [];
              ctx.font = "700 " + ss + "px system-ui, sans-serif"; ctx.lineWidth = 4;
              for (const w of sub.split(" ")) { const l = lines.length ? lines[lines.length - 1] + " " + w : w; if (lines.length && ctx.measureText(l).width > c.w * 0.92) lines.push(w); else lines[Math.max(0, lines.length - 1)] = l; }
              lines.forEach((l, i) => { const y = c.h * 0.4 + 34 + i * (ss + 4); ctx.strokeText(l, c.w / 2, y); ctx.fillText(l, c.w / 2, y); });
            }
          };
          if (t < 1 && ui.mode === "drive") big(I18N.tr(T("GO!")), null, "#69db7c");
          else if (t >= limit()) big("🏁 " + I18N.tr(T("Finish!")));
          else if (car.bat != null && car.bat <= 0 && !car.pit) big("⚠️ " + I18N.tr(T("Emergency drive mode")), I18N.tr(T("Battery empty – crawling to the pits.")), "#ffa94d");
          else if (car.eng) big("💥 " + I18N.tr(T("Engine overheated!")), I18N.tr(T("Limp to the pits – it gets swapped.")), "#ff8787");
          else if (ui.mode === "drive" && ui.offAt && nowS() - ui.offAt < 2.5) big("🟫 " + I18N.tr(T("Off the track!")), I18N.tr(T("Too fast into the chicane – brake earlier.")), "#ffd8a8");
          else if (ui.mode === "drive" && brakeHint(car, t)) big("🛑 " + I18N.tr(T("Brake!")), I18N.tr(T("Chicane ahead")), "#ff8787");
          else if (ui.mode === "drive" && car.thr > 0 && car.bat < leNeed(car.d).mix && Math.floor(t * 3) % 2 === 0)
            big("🔋 " + I18N.tr(T("Save energy!")), I18N.tr(T("Lift off – the battery won't last the lap at full throttle.")), "#ffd43b");
          else if (ui.mode === "drive" && car.temp >= 92 && Math.floor(t * 4) % 2 === 0) big("🔥 " + I18N.tr(T("Let go!")), null, "#ff6b6b");
          if (ui.mode === "drive" && car.temp >= 92 && !car.eng && t - lastTempWarn > 1) { lastTempWarn = t; leBuzz(80); LeAudio.tone([900], "square", 0.08, 0.05); }
          if (ui.mode === "drive") LeAudio.engine(!document.hidden && !car.pit && t < limit(), Math.min(1, car.v / LE.VFULL * 0.7 + car.thr * 0.3));
          else LeAudio.engine(false);
          hud(car, tm, t);
        }
      }
    }
    if (ui.mode !== "drive") LeAudio.engine(false);
    if (ui.mode === "pit") pitTick(t);
    if (ui.mode === "crew") crewTick(t);
    if (ui.mode !== "drive" && team && t >= 0) hud(team.car || team, team, t);
    if (t >= 0 && t >= limit() * 22 / 24 && !finalCue && t < limit()) { finalCue = true; if (gameT() - limit() * 22 / 24 < 5) { LeAudio.fanfare(); toast("🏁 " + I18N.tr(T("The final 2 race hours!")), "good"); } }
  }
  // «Brake!» for beginners: juniors always, everybody else in the first two laps – before a chicane while too fast
  function brakeHint(car, t) {
    if (!jr() && leLaps(car.d) >= 2) return false;
    const tricky = leInWin(st.rain, t) || leDark(t, limit()) > 0.5, safe = tricky ? LE.SAFE_TRICKY : LE.SAFE, x = ((car.d % LE.L) + LE.L) % LE.L;
    return car.thr >= 0 && car.v > safe - 0.5 && LE_CHICANES.some(([xa]) => xa - x > 0 && xa - x <= (car.v * car.v - safe * safe) / (2 * LE.BRAKE) + car.v * 0.8 + 10);
  }
  // ---------- the bars: position, lap, clock, temperature, standings
  function hud(car, tm, t) {
    const hd = ui.hud;
    if (!hd || !tm) return;
    const pos = st.standings.indexOf(tm.i) + 1, tt = Math.max(0, Math.min(t, limit())), night = leDark(tt, limit()) > 0.5;
    hd.pos.textContent = "P" + pos + "/" + st.teams.length;
    hd.lap.textContent = I18N.tr(T("Lap {0}")).replace("{0}", leLaps(car.d) + 1);
    hd.clock.textContent = (night ? "🌙 " : "☀️ ") + leClock(tt, limit()) + (leInWin(st.rain, tt) ? " 🌧️" : "");
    hd.left.textContent = "⏳ " + leRaceLeft(tt, limit());
    hd.left.classList.toggle("le-final", tt >= limit() * 22 / 24);
    if (hd.temp) {
      const v = (car.temp - LE.TMIN) / (LE.RED - LE.TMIN) * 100;
      hd.temp.style.setProperty("--v", Math.max(0, Math.min(100, v)) + "%");
      hd.temp.dataset.lvl = car.eng ? "red" : car.temp >= 92 ? "red" : car.temp >= LE.YELLOW ? "yellow" : "ok";
      hd.speed.textContent = Math.round(car.v * 7) + " km/h";
      hd.tyre.textContent = car.tyre === "r" ? "🌧️" : "☀️";
      hd.tyre.classList.toggle("le-wrong", leGrip(car.tyre, leInWin(st.rain, tt)) < 1);
    }
    if (hd.bat) {                                              // the battery: green, orange (it won't last the lap flat out), red
      const b = Math.max(0, car.bat ?? 0), need = leNeed(car.d), lvl = b <= 0 || b < need.lift ? "red" : b < need.mix ? "yellow" : "ok";
      hd.bat.style.setProperty("--v", Math.min(100, b) + "%");
      hd.bat.dataset.lvl = lvl;
      hd.batTxt.textContent = Math.ceil(b) + "%";
      hd.batTxt.dataset.lvl = lvl;
      hd.save.hidden = lvl === "ok" || car.pit;
      hd.save.textContent = b <= 0 ? "⚠️ " + I18N.tr(T("Emergency drive mode")) : "🔋 " + I18N.tr(T("Save energy!"));
      hd.save.classList.toggle("le-emg", b <= 0);
    }
    if (hd.cast) hd.cast.textContent = forecast(tt);
    if (hd.crew) drawCrewStrip(tm);
    if (ui.board && (!ui.boardAt || nowS() - ui.boardAt > 0.5)) { ui.boardAt = nowS(); drawBoard(); }
  }
  // the forecast: rain now, rain soon (within about a lap), dry soon
  function forecast(t) {
    if (!st.rules.weather && !(st.rain || []).length) return "☀️ " + I18N.tr(T("Dry all race"));
    const now = (st.rain || []).find(([a, b]) => a <= t && t < b), next = (st.rain || []).find(([a]) => a > t);
    if (now) return "🌧️ " + I18N.tr(T("Rain – dry in ~{0} s")).replace("{0}", Math.ceil(now[1] - t));
    if (next && next[0] - t < 45) return "🌦️ " + I18N.tr(T("Rain in ~{0} s")).replace("{0}", Math.ceil(next[0] - t));
    return "☀️ " + I18N.tr(T("Dry for now"));
  }
  const gapText = (o, lead) => {
    const dd = lead.d - o.d;
    if (o === lead) return I18N.tr(T("Leader"));
    if (dd >= LE.L) { const n = Math.floor(dd / LE.L); return "+" + n + " " + I18N.tr(n === 1 ? T("lap") : T("laps")); }
    return "+" + Math.round(dd) + " m";
  };
  function drawBoard() {
    if (!ui.board || !st.teams) return;
    const lead = st.teams[st.standings[0]];
    ui.board.replaceChildren(...st.standings.map((i, k) => {
      const o = st.teams[i];
      return h("div.le-chip" + (i === st.my_team ? ".le-mine" : ""), { style: { "--tc": o.color } },
        h("b.le-rank", String(k + 1)), leFlagEl(o.country), h("span.le-num", String(o.num)),
        h("span.le-gap", o.pit ? "🅿️" : gapText(o, lead)), h("span.le-laps", o.laps + "L"));
    }));
  }
  // the driver sees what the crew has ready – and the spare battery charging («spare 🔋 63 %»)
  function drawCrewStrip(tm) {
    const pr = tm.prep, el = ui.hud.crew, sp = tm.spare;
    if (!pr) return;
    const ch = Math.floor(leSpare(sp, gameT())), plugged = !!sp && sp.plug != null;
    const sig = JSON.stringify([pr.ready.tyres, pr.ready.engine, pr.need_eng, tm.members.length, ch, plugged]);
    if (el.dataset.sig === sig) return;
    el.dataset.sig = sig;
    const spare = h("span.le-ready.le-sparechip" + (ch >= 100 ? ".ok" : ""), I18N.tr(T("spare")), " 🔋 ", ch + " %", plugged && ch < 100 ? " ⚡" : !plugged && ch < 100 ? " 🔌?" : "");
    if (tm.members.length < 2) { el.replaceChildren(h("span.le-ready", "🏠"), spare); return; }
    const chip = (ic, ok) => h("span.le-ready" + (ok ? ".ok" : ""), ic, " ", ok ? "✓" : "…");
    el.replaceChildren(...[spare, chip("🛞", pr.ready.tyres), pr.need_eng ? chip("⚙️", pr.ready.engine) : null].filter(Boolean));
  }

  // ---------- the pit crew: the jobs during the lap
  const sendPrep = async (action, spot) => {
    try {
      const r = await req("/prep", { method: "POST", body: { action, spot } });
      if (r && r.state) { setState(r.state); }
      return r;
    } catch (e) { toast(e.message, "bad"); return null; }
  };
  function jobTyres() {
    const spots = [0, 1, 2, 3].map(i => h("button.le-spot.le-s" + i, { type: "button", "aria-label": I18N.tr(T("Tyre")) + " " + (i + 1), onpointerdown: async e => {
      e.preventDefault();
      const tm = myTeam();
      if (!tm || tm.car.pit || tm.prep.tyres[i] || local.tyres[i]) return;
      local.tyres[i] = true; LeAudio.wrench(); leBuzz(20); crewTick(gameT());
      const r = await sendPrep("tyre", i);
      if (!r) { local.tyres[i] = false; crewTick(gameT()); }
      else if (r.tyres === 4) { LeAudio.ok(); leBuzz([30, 30, 60]); }
    } }, h("span", "🛞")));
    const comp = ["s", "r"].map(k => h("button.le-comp", { type: "button", "data-k": k, onclick: async () => {
      const tm = myTeam(); if (!tm || tm.car.pit) return;
      local.compound = k; crewTick(gameT()); await sendPrep(k === "r" ? "rain" : "slicks"); local.compound = null; crewTick(gameT());
    } }, k === "r" ? "🌧️" : "☀️"));
    ui.job.tyres = { spots, comp };
    return h("div.le-job.le-jtyres", h("div.le-jhead", h("b", "🛞 ", T("Lay out 4 tyres")), h("span.le-jok")),
      h("div.le-comps", ...comp), h("div.le-tyrepad", h("div.le-mini", { style: { "--tc": myTeam().color } }), ...spots));
  }
  function holdBtn(label, cls, onDown, onUp) {
    const b = h("button.le-hold" + cls, { type: "button" }, label);
    let on = false;
    b.addEventListener("pointerdown", e => { e.preventDefault(); if (on) return; on = true; try { b.setPointerCapture(e.pointerId); } catch {} b.classList.add("on"); onDown(); });
    const up = () => { if (!on) return; on = false; b.classList.remove("on"); onUp(); };
    b.addEventListener("pointerup", up); b.addEventListener("pointercancel", up); b.addEventListener("lostpointercapture", up);
    return b;
  }
  // the spare battery: plug it in (the server keeps the time) – then it charges by itself until the car comes in
  function jobBattery() {
    const lvl = h("div.le-bat-lvl"), bat = h("div.le-bat", lvl, h("span.le-bat-zap", "⚡"));
    const val = h("b.le-batval", "0 %"), status = h("span.le-batst");
    const cable = h("div.le-cable", { "aria-hidden": "true" });
    const btn = h("button.le-hold.le-plugbtn", { type: "button", onclick: async () => {
      const tm = myTeam();
      if (!tm || tm.car.pit || !tm.spare || tm.spare.plug != null || local.plug) return;
      local.plug = Math.max(0, gameT()); LeAudio.tone([300, 600], "square", 0.08, 0.06, 0.06); leBuzz(30); crewTick(gameT());
      const r = await sendPrep("plug");
      if (!r) local.plug = 0; else { LeAudio.ok(); leBuzz([30, 30, 60]); }
      crewTick(gameT());
    } }, "🔌 ", T("Plug in"));
    const row = h("div.le-batrow", bat, h("div.le-batside", val, status, btn), cable);
    ui.job.battery = { lvl, bat, val, status, btn, row };
    return h("div.le-job.le-jbattery", h("div.le-jhead", h("b", "🔌 ", T("Charge the spare battery")), h("span.le-jok")), row,
      h("div.small.muted.center", T("Plug in first – it needs about a lap!")));
  }
  function jobEngine() {
    const bar = h("div.le-engbar", h("i"));
    const btn = holdBtn(["⚙️ ", I18N.tr(T("Hold"))], ".le-engbtn", () => {
      const tm = myTeam(); if (!tm || tm.prep.ready.engine) return;
      local.engHold = nowS(); LeAudio.wrench(); sendPrep("eng_on");
    }, async () => {
      if (!local.engHold) return;
      const r = await sendPrep("eng_off");
      local.engHold = 0;
      if (r && r.ready) { LeAudio.ok(); leBuzz([30, 30, 60]); }
      crewTick(gameT());
    });
    ui.job.engine = { bar, btn };
    return h("div.le-job.le-jeng", h("div.le-jhead", h("b", "🔧 ", T("Prepare the spare engine")), h("span.le-jok")), h("div.le-engrow", bar, btn));
  }
  function crewTick(t) {
    const tm = myTeam(), j = ui.job;
    if (!tm || !j || !tm.prep) return;
    const pr = tm.prep, rd = pr.ready;
    const mark = (key, ok) => { const card = box.querySelector(".le-j" + key); if (card) { card.classList.toggle("le-ok", !!ok); card.querySelector(".le-jok").textContent = ok ? "✓ " + I18N.tr(T("ready")) : ""; } };
    if (j.tyres) {
      const cp = local.compound || pr.compound;
      j.tyres.spots.forEach((b, i) => { b.classList.toggle("set", !!(pr.tyres[i] || local.tyres[i])); b.classList.toggle("wet", cp === "r"); });
      j.tyres.comp.forEach(b => b.classList.toggle("on", b.dataset.k === cp));
      mark("tyres", rd.tyres);
    }
    if (ui.cast) ui.cast.textContent = forecast(Math.max(0, t));
    if (j.battery && tm.spare) {                                // the charge rises from the server's plug-in time
      const sp = tm.spare, plug = sp.plug != null ? sp.plug : local.plug ? Math.max(local.plug, sp.t) : null;
      const ch = leSpare({ ...sp, plug }, t), plugged = plug != null, full = ch >= 100 - 1e-9;
      j.battery.lvl.style.height = ch + "%";
      j.battery.lvl.dataset.lvl = ch >= 50 ? "ok" : ch >= 20 ? "mid" : "low";
      j.battery.val.textContent = Math.floor(ch) + " %";
      j.battery.row.classList.toggle("chg", plugged && !full);
      j.battery.row.classList.toggle("full", full);
      j.battery.status.textContent = full ? I18N.tr(T("full")) : plugged ? "⚡ " + I18N.tr(T("charging")) : I18N.tr(T("not plugged in"));
      j.battery.btn.disabled = plugged || full;
      mark("battery", full);
    }
    if (j.engine) {
      let v = pr.eng;
      if (local.engHold) v += nowS() - local.engHold;
      else if (pr.eng_on) v += Math.max(0, t - pr.eng_on[1]);
      if (rd.engine) v = LE.ENGINE_HOLD;
      j.engine.bar.style.setProperty("--v", Math.min(100, v / LE.ENGINE_HOLD * 100) + "%");
      j.engine.btn.disabled = !!rd.engine;
      mark("eng", rd.engine);
    }
    if (ui.eta) {                                               // how far the car is from the pits
      const left = tm.d < 0 ? LE.L - tm.d : LE.L - (tm.d % LE.L), secs = Math.max(0, left / Math.max(10, tm.v || LE.VLIFT));
      ui.eta.style.setProperty("--v", Math.max(0, Math.min(100, (1 - left / LE.L) * 100)) + "%");
      ui.etaTxt.textContent = t < 0 ? I18N.tr(T("Get ready!")) : I18N.tr(T("The car is in in about {0} s")).replace("{0}", Math.round(secs));
    }
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const tm = myTeam();
    const { mode, intro: introOn } = leScreen(st, myId, gameT());
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, mode, introOn, tm && tm.driver, mode === "pit" && tm.stop.t,
      mode === "crew" && tm.prep && tm.prep.need_eng, st.phase === "lobby" ? st.players.map(p => [p.id, p.team]) : 0, st.phase === "done" ? st.players.map(p => p.place) : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running); box.classList.toggle("le-scroll", mode === "lobby");
    ui = { go: ui.go ?? true, roared: ui.roared, mode, intro: introOn, lanePos: mode === "drive" ? ui.lanePos : null };
    if (!st) return show(h("section.card.center", h("div.big-ic", LE_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const menu = gameMenu({ rules: () => langstreckeRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "langstrecke" : null,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", LE_ICON, " ", leName())));
    if (st.phase === "done") { LeAudio.engine(false); return show(head, result()); }
    if (st.phase === "lobby") return show(head, lobby());
    const cv = h("canvas.le-canvas"), wrap = h("div.le-wrap" + (mode === "drive" || introOn ? ".le-big" : mode === "pit" ? ".le-gar" : ".le-tv"), cv);
    ui.cv = { el: cv, ctx: cv.getContext("2d"), wrap, w: 0, h: 0, dpr: 0 };
    swipes(wrap);
    ui.hud = { pos: h("b.le-pos"), lap: h("span.le-lap"), clock: h("span.le-clock"), left: h("span.le-left") };
    const top = h("div.le-top", ui.hud.pos, ui.hud.lap, ui.hud.clock, ui.hud.left);
    ui.board = h("div.le-board");
    const teamTag = tm ? h("span.le-teamtag", { style: { "--tc": tm.color } }, leFlagEl(tm.country), " #" + tm.num, " ", C(tm.name)) : null;
    if (mode === "drive") {
      Object.assign(ui.hud, { speed: h("b.le-speed"), temp: h("div.le-gauge.le-temp"), crew: h("div.le-crewstrip"), tyre: h("span.le-tyre"), cast: h("span.le-cast"),
        bat: h("div.le-gauge.le-batg"), batTxt: h("b.le-battxt"), save: h("span.le-save", { hidden: true }) });
      const gauges = h("div.le-gauges", ui.hud.speed, ui.hud.tyre, h("span.le-g", "🌡️", ui.hud.temp), h("span.le-g.le-gb", "🔋", ui.hud.bat, ui.hud.batTxt));
      wrap.append(ui.hud.crew, ui.hud.save);
      const btn = (c, ic, label) => h("button.le-btn", { type: "button", "aria-label": label, title: label, onpointerdown: e => { e.preventDefault(); input(c); }, onclick: e => { if (e.detail === 0) input(c); } }, ic);
      ui.pedal = h("button.le-btn.le-pedal", { type: "button", "aria-label": I18N.tr(T("Full throttle")) }, "🚀 ", T("Gas"));
      ui.pedal.addEventListener("pointerdown", e => { e.preventDefault(); if (gameT() < 0 && !introSkip) introSkip = true; try { ui.pedal.setPointerCapture(e.pointerId); } catch {} pedal(1); });
      for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) ui.pedal.addEventListener(ev, () => pedal(0));
      ui.pedal.classList.toggle("on", thrLocal > 0);
      ui.brake = h("button.le-btn.le-brake", { type: "button", "aria-label": I18N.tr(T("Brake")) }, "🛑");
      ui.brake.addEventListener("pointerdown", e => { e.preventDefault(); try { ui.brake.setPointerCapture(e.pointerId); } catch {} brake(1); });
      for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) ui.brake.addEventListener(ev, () => brake(0));
      const pad = h("div.le-pad", btn("l", "◀", T("Move left")), ui.brake, ui.pedal, btn("r", "▶", T("Move right")));
      show(head, top, ui.board, h("div.le-role", "🏎️ ", T("You drive!"), ui.hud.cast, teamTag), gauges, wrap, pad);
    } else if (mode === "pit") {
      const stp = tm.stop;
      ui.watch = h("div.le-watch", "⏱ 0.0 s");
      ui.watchHand = h("div.le-dial", h("i"));
      ui.parts = stp.parts.map(part => {
        const [ic, label] = LE_PARTS[part[0]] || ["•", part[0]];
        const fixed = part[0] === "base" || part[0] === "garage" || part[0] === "battery";
        const val = fixed ? part[1].toFixed(1) + " s" : part[1] ? "+" + part[1].toFixed(0) + " s" : "+0 s";
        const note = part[0] === "base" || part[0] === "garage" ? "" : part[0] === "battery" ? (part[2] ? I18N.tr(T("full")) : I18N.tr(T("{0} % charged")).replace("{0}", Math.floor(stp.bat_in ?? 0)))
          : part[0] === "engine" ? (part[2] ? I18N.tr(T("prepared")) : I18N.tr(T("not prepared"))) : part[2] ? I18N.tr(T("ready")) : I18N.tr(T("not ready"));
        const cls = part[0] === "base" || part[0] === "garage" ? "" : part[0] === "battery" ? (part[2] ? ".good" : ".warn") : part[2] ? ".good" : ".bad";
        return [h("div.le-part" + cls, h("span", ic), h("span.grow", I18N.tr(label), note ? h("small", " · ", note) : null), h("b", val)), part];
      });
      const change = stp.change ? h("div.le-change", "🔄 ", C(pName(stp.prev)), " → ", h("b", C(pName(stp.next))), " 🏎️")
        : h("div.le-change", "🏎️ ", I18N.tr(T("{0} drives on")).replace("{0}", pName(stp.next)));
      const low = stp.next === myId && (stp.bat_in ?? 100) < 100 ? h("p.le-next.le-low", "🔋 " + Math.floor(stp.bat_in) + " % – ", T("Save energy!")) : null;
      const next = low ? null : stp.next === myId && stp.change ? h("p.le-next", "🏎️ ", T("You drive next – get ready!")) : null;
      ui.crowd = crowd(tm);
      show(head, top, ui.board, h("div.le-pithead", h("strong", "🅿️ ", I18N.tr(T("Pit stop {0}")).replace("{0}", stp.n)), h("span.small", leTyreName(stp.tyre)), teamTag),
        ui.crowd, wrap, h("div.le-watchrow", ui.watchHand, ui.watch), h("div.le-parts", ...ui.parts.map(x => x[0])), change, next, low);
    } else if (mode === "crew" && introOn) {                   // the start: the lights for everybody – the jobs come with the green light
      const next = tm.next === myId && tm.members.length > 1 ? h("span.le-nextme", "🏎️ ", T("You drive next!")) : null;
      show(head, top, ui.board, h("div.le-role", "🔧 ", T("Pit crew"), " · ", C(pName(tm.driver), "span.small"), " 🏎️", teamTag),
        wrap, h("div.le-etarow.le-introrow", h("span.small", T("Get ready!")), next));
    } else if (mode === "crew") {
      ui.job = {};
      ui.eta = h("div.le-eta"); ui.etaTxt = h("span.small.le-etatxt"); ui.cast = h("span.le-cast");
      const next = tm.next === myId && tm.members.length > 1 ? h("span.le-nextme", "🏎️ ", T("You drive next!")) : null;
      const jobs = h("div.le-jobs2", jobBattery(), jobTyres());
      show(head, top, ui.board, h("div.le-role", "🔧 ", T("Pit crew"), " · ", C(pName(tm.driver), "span.small"), " 🏎️", teamTag),
        wrap, h("div.le-etarow", ui.eta, ui.etaTxt, next), h("div.le-castrow", "📡 ", ui.cast), jobs, tm.prep && tm.prep.need_eng ? jobEngine() : null);
      crewTick(gameT());
    } else {
      show(head, top, ui.board, wrap, h("p.center.muted.small", T("You are watching the leader.")));
    }
    drawBoard();
  }
  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobby() {
    const n = st.nteams || 1, styles = [["Comet Racing", "#e03131"], ["Blue Falcon Works", "#1c7ed6"], ["Pine Cone Motors", "#2f9e44"], ["Sunrise Speedsters", "#f08c00"]];
    const mine = (st.players.find(p => p.id === myId) || {}).team;
    const looks = st.looks || [];
    const cards = Array.from({ length: n }, (_, i) => {
      const ps = st.players.filter(p => !p.bot && p.team === i), full = ps.length >= st.rules.team_size;
      const lk = looks[i] || { color: styles[i][1], country: "CH" }, mineT = st.joined && mine === i;
      const taken = looks.filter((_, k) => k !== i && k < n).map(x => x.color);
      const numIn = mineT ? h("input.le-numin", { type: "number", min: 1, max: 99, value: lk.num || "", "aria-label": I18N.tr(T("Car number")),
        onchange: e => { const v = Math.round(+e.target.value); if (v >= 1 && v <= 99) act("look", { num: v }); else { e.target.value = lk.num || ""; toast(I18N.tr(T("Car numbers go from 1 to 99")), "bad"); } } }) : null;
      const colors = mineT ? h("div.le-colors", ...(st.palette || []).map(c => h("button.le-color" + (c.color === lk.color ? ".on" : ""), { type: "button",
        style: { background: c.color }, disabled: taken.includes(c.color), "aria-label": c.name, onclick: () => act("look", { color: c.color }) }))) : null;
      const country = mineT ? leCountrySelect(lk.country, v => act("look", { country: v }))
        : lk.country ? h("div.small", leFlagEl(lk.country), " ", I18N.tr(LE_COUNTRIES[lk.country] || "")) : null;
      return h("div.le-tcard", { style: { "--tc": lk.color } }, h("div.le-tname", leFlagEl(lk.country), " ", C(styles[i][0])),
        h("div.le-carno", mineT ? [h("span.small", "#"), numIn] : h("b", "#" + (lk.num || "?"))), colors, country,
        h("div.le-tseats", ...ps.map(p => h("span.le-tseat" + (p.id === myId ? ".me" : ""), seatIcon(p, 28), C(p.name, "small")))),
        st.joined && mine !== i && !full ? h("button.btn.small.ghost", { onclick: () => act("team", { team: i }) }, T("Join this team")) : null,
        h("div.small.muted", ps.length + " / " + st.rules.team_size));
    });
    const host = isHost() && st.status !== "done" ? h("div.row.center.host-bar", n > 1 ? h("button.btn.ghost", { onclick: () => act("mix") }, "🔀 ", T("Mix teams")) : null,
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))) : null;
    const story = h("p.small.muted", I18N.tr(T("24 race hours in {0} minutes on the Circuit des Tannes. The most laps wins.")).replace("{0}", st.rules.minutes));
    const roles = h("p.small", "🔄 ", T("After every lap the car comes into the pits and the next person of the team drives – the others charge the spare battery and prepare the tyres."));
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
      h("div.le-pmembers", ...members(t).map(p => seatIcon(p, n === 1 ? 40 : 32))), h("b.le-pnum", leFlagEl(t.country), " #" + t.num), C(t.name, "div.small.le-pname"),
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
        h("span.le-swatch", { style: { background: t.color } }, String(t.num)), leFlagEl(t.country),
        h("span.grow", C(t.name, "strong"), h("br"), h("span.small.muted", members(t).map(p => p.name).join(", "))),
        h("span.small", leLapsTxt(t.laps), h("br"), t.best_pit ? "🅿️ " + t.best_pit.toFixed(1) + " s" : ""),
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
      : [h("p.muted", T("Short laps and a pit stop after every lap: one drives, the others charge the spare battery and get the tyres ready – then the next one drives.")),
         gameStartRow(() => langstreckeStartDialog(true, () => go("langstrecke")), () => langstreckeStartDialog(false, () => go("langstrecke")))]);
}
