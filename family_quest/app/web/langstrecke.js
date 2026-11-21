// «24h Endurance» (24-Stunden-Rennen) – a short, fast live team race on the fictional «Circuit des Tannes»
// (familyquest/langstrecke.py). Teams are racing stables with one car each. One short lap, then the car drives into
// the pits by itself and the next person of the team drives. The driver steers freely across the track with the virtual
// joystick bottom left on the picture (up gas, down brake – or the arrow keys) and gives full gas (it heats the engine and drains the battery much faster – empty: the emergency
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
// the circuit and the car – the same numbers as in langstrecke.py
const LE = { L: 640, DT: 0.1, VLIFT: 20, VFULL: 30, ACC: 8.5, BRAKE: 14, COAST: 5, VBRAKE: 8, VLIMP: 13,
  HEAT: 2.6, HEAT_JR: 1.7, COOL: 4, TMIN: 60, YELLOW: 85, RED: 100, COUNTDOWN: 6,
  E_FULL: 0.16, E_LIFT: 0.07, REGEN: 0.3, VEMERG: 7,
  STOP_BASE: 2, BAT_SWAP: 1, PEN_PREP: 4, ENG_READY: 2, ENG_SWAP: 6, GARAGE: 4, CHARGE_RATE: 4, GARAGE_PLUG: 8, ENGINE_HOLD: 2,
  WET_SLICK: 0.8, DRY_RAIN: 0.9, RAIN_C: 0.85,
  HW: 5.5, KERB: 1.5, XMAX: 11, STEER_V: 7, VSTEER: 10, WHEEL: 6, PUSH: 0.75, VGRASS: 9, GRASS_DEC: 16, KERB_F: 0.9,
  SLIP_D: 30, SLIP_W: 2.2, SLIP_V: 3.5, BUMP_D: 4.5, CAR_W: 1.9, NUDGE: 1.5, PIT_Z: 25,
  LINE_D: 40, LINE_OUT: 3.5, LINE_APEX: 3.5, LMAX: 4, ASSIST_K: 0.5, AK_ASSIST: 0.92,
  LUG: 0.35, EBRAKE: 7, LIM_HEAT: 1.5, NEUTRAL_DEC: 3, VREV_ON: 0.75, VREV: 2.5, VCREEP: 1, REV_ACC: 3, GRIND_DEC: 22, GRIND_HEAT: 30, AUTO_UP: 0.9, AUTO_DOWN: 0.75, AUTO_GAP: 0.2,
  // the pit lane on the right of the main straight (its metres = the lap's metres beside it; pl 0 racing, 1 entry up to
  // the line, 2 to the box, 3 out to the pit exit and back onto the track) – as in langstrecke.py
  PIT_IN: 595, PIT_ENTRY: 22, PIT_OUT: 60, PIT_MERGE: 15, PL_X: 9.5, PL_HW: 2, SIDE_X: 3.5, PIT_V: 100 / 7, KEEP_R: 1.5, KEEP_ST: 20,
  AP_LATE: 12, AP_K: 0.7, FUNNEL: 0.6, BOX0: 10, BOX_GAP: 6, BOX_DEC: 6 };
LE.PZ_IN = LE.PIT_IN - LE.L;
// the gearbox (manual): the limiter, the low end (below: the gear lugs) and the pull of gears 1–6 – as in langstrecke.py
const LE_GEAR_TOP = [9, 13.5, 18, 22.5, 27, 30], LE_GEAR_LOW = [0, 5, 8.5, 12.5, 16.5, 21], LE_GEAR_ACC = [1.15, 1.1, 1.05, 1, 0.95, 0.9];
// the gear the automatic gearbox would be in at speed v
const leAutoGear = v => { for (let i = 0; i < LE_GEAR_TOP.length; i++) if (v < LE_GEAR_TOP[i] * LE.AUTO_UP) return i + 1; return LE_GEAR_TOP.length; };
// the corners: start, end (metres in the lap), angle (degrees, + = right), safe speed (m/s, dry, the right tyres)
const LE_CORNERS = [[90, 130, 90, 20], [210, 240, -45, 25], [300, 350, 150, 13], [420, 450, 75, 21], [500, 550, 90, 17]];
// the spare battery's charge at game time `at` (the server's timestamps; the server decides at the stop)
const leSpare = (sp, at) => (!sp ? 0 : sp.plug == null || at <= sp.plug ? sp.c0 : Math.min(100, sp.c0 + LE.CHARGE_RATE * (at - sp.plug)));
// what the rest of the lap needs: lifted off all the way / a normal mix of full throttle and lifting
const leNeed = d => { const left = LE.L - (((d % LE.L) + LE.L) % LE.L); return { lift: left * LE.E_LIFT, mix: left * (LE.E_FULL + LE.E_LIFT) / 2 }; };
const leGrip = (tyre, rain) => (rain ? (tyre !== "r" ? LE.WET_SLICK : 1) : (tyre === "r" ? LE.DRY_RAIN : 1));
const leInWin = (wins, s) => (wins || []).some(([a, b]) => a <= s && s < b);
const leClamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
const leLapPos = d => d - LE.L * Math.floor(d / LE.L);
const leCornerAt = xl => LE_CORNERS.find(c => c[0] <= xl && xl < c[1]) || null;
// the corner the car is in or the next one ahead: [corner, metres to its start – 0 inside it]
function leNextCorner(xl) {
  let best = null, dz = 0;
  for (const c of LE_CORNERS) {
    if (c[0] <= xl && xl < c[1]) return [c, 0];
    const z = c[0] > xl ? c[0] - xl : c[0] + LE.L - xl;
    if (best === null || z < dz) { best = c; dz = z; }
  }
  return [best, dz];
}
const leSafe = (c, tyre, rain) => c[3] * leGrip(tyre, rain) * (rain ? LE.RAIN_C : 1);
const leEase = u => { u = leClamp(u, 0, 1); return u * u * (3 - 2 * u); };
// the pit lane (as pit_z(), pit_x(), pit_bounds() in langstrecke.py): metres from the line of this stop (− before it),
// the lane's middle there and where a car in it can be across
const lePitZ = (d, pl) => { const xl = leLapPos(d); return pl === 1 ? xl - LE.L : xl; };
function lePitX(pz) {
  if (pz < LE.PZ_IN + LE.PIT_ENTRY) return LE.SIDE_X + (LE.PL_X - LE.SIDE_X) * leEase((pz - LE.PZ_IN) / LE.PIT_ENTRY);
  if (pz < LE.PIT_OUT) return LE.PL_X;
  return LE.PL_X + (LE.SIDE_X - LE.PL_X) * leEase((pz - LE.PIT_OUT) / LE.PIT_MERGE);
}
function lePitBounds(pz) {
  if (pz < LE.PZ_IN + LE.PIT_ENTRY) return [Math.max(-LE.XMAX, LE.PL_X - LE.PL_HW - (LE.PZ_IN + LE.PIT_ENTRY - pz) * LE.FUNNEL), LE.PL_X + LE.PL_HW];
  const c = lePitX(pz);
  return [c - LE.PL_HW, c + LE.PL_HW];
}
const leBoxOf = i => LE.BOX0 + LE.BOX_GAP * i;
// the racing line across the track: outside before a corner, the apex inside, outside at the exit (as race_line())
function leLine(xl) {
  let y = 0;
  for (const [a, b, ang] of LE_CORNERS) {
    const dr = ang > 0 ? 1 : -1;
    if (a - LE.LINE_D <= xl && xl < a) y -= dr * LE.LINE_OUT * leEase((xl - (a - LE.LINE_D)) / LE.LINE_D);
    else if (a <= xl && xl < b) { const u = (xl - a) / (b - a); y += -dr * LE.LINE_OUT + dr * (LE.LINE_OUT + LE.LINE_APEX) * 4 * u * (1 - u); }
    else if (b <= xl && xl < b + LE.LINE_D) y -= dr * LE.LINE_OUT * (1 - leEase((xl - b) / LE.LINE_D));
  }
  return leClamp(y, -LE.LMAX, LE.LMAX);
}

function leRand(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), a | 1) >>> 0;
    t = (((t + Math.imul(t ^ (t >>> 7), t | 61)) >>> 0) ^ t) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
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
// one input of the driver: "s" steering −100 … 100, "u" 1 gas / 0 lifted / −1 brake, "a" the assist on / off,
// "m" manual gears on / off (on: the gear that fits the speed), "g" the gear −1 R / 0 N / 1–6 (anything else: ignored)
function leApply(car, c, v) {
  if (c === "s") car.st = Math.max(-100, Math.min(100, Math.trunc(v)));
  else if (c === "u") car.thr = Math.trunc(v) > 0 ? 1 : Math.trunc(v) < 0 ? -1 : 0;
  else if (c === "a") { car.ast = Math.trunc(v) ? 1 : 0; car.ak = LE.AK_ASSIST; }
  else if (c === "m") { car.man = Math.trunc(v) ? 1 : 0; car.gear = leAutoGear(car.v); }
  else if (c === "g" && Math.trunc(v) >= -1 && Math.trunc(v) <= LE_GEAR_TOP.length) car.gear = Math.trunc(v);
}
// the virtual joystick: the thumb's way (dx, dy in px from the centre, y down) on a ring of radius r → the knob clamped
// to the ring (kx, ky), the steering s −100 … 100 in steps of 5 (a small dead zone in the middle, full lock a little
// before the edge so a diagonal still steers hard) and the pedal u: up beyond 30 % gas 1, down beyond 30 % brake −1,
// in between lifted off 0 – the same inputs as the arrow keys, the server's protocol does not change
const LE_JOY = { DEAD: 0.12, LOCK: 0.85, PEDAL: 0.3 };
function leJoy(dx, dy, r) {
  dx = +dx || 0; dy = +dy || 0; r = Math.max(1, +r || 1);
  const d = Math.hypot(dx, dy), k = d > r ? r / d : 1, kx = dx * k, ky = dy * k, nx = kx / r, ny = ky / r, ax = Math.abs(nx);
  const s = ax <= LE_JOY.DEAD ? 0 : Math.sign(nx) * Math.round(Math.min(1, (ax - LE_JOY.DEAD) / (LE_JOY.LOCK - LE_JOY.DEAD)) * 20) * 5;
  return { kx, ky, s: s || 0, u: ny <= -LE_JOY.PEDAL ? 1 : ny >= LE_JOY.PEDAL ? -1 : 0 };
}
// the H shifter's open gate (x −1 … 1 left → right, y −1 top … 1 bottom; the neutral rail at y = 0) – four columns:
// R (top only) | 1 top, 2 bottom | 3 top, 4 bottom | 5 top, 6 bottom. leGate: where the thumb is → the lever on the
// nearest point of the gate (the rail or a slot – it never leaves the gate) and the gear it is in: deeper than IN into
// a slot = that gear, else N (0). leGatePos: where the lever sits in a gear (R = −1).
const LE_GATE = { COLS: [-0.75, -0.25, 0.25, 0.75], IN: 0.6, SLOTS: [[0, -1, -1], [1, -1, 1], [1, 1, 2], [2, -1, 3], [2, 1, 4], [3, -1, 5], [3, 1, 6]] };
function leGate(nx, ny) {
  nx = +nx || 0; ny = +ny || 0;
  let x = leClamp(nx, LE_GATE.COLS[0], LE_GATE.COLS[3]), y = 0, slot = null, bd = Math.hypot(nx - x, ny);
  for (const sl of LE_GATE.SLOTS) {
    const sx = LE_GATE.COLS[sl[0]], sy = sl[1] < 0 ? leClamp(ny, -1, 0) : leClamp(ny, 0, 1), dd = Math.hypot(nx - sx, ny - sy);
    if (dd <= bd) { bd = dd; x = sx; y = sy; slot = sl; }
  }
  return { x, y: y || 0, gear: slot && Math.abs(y) >= LE_GATE.IN ? slot[2] : 0 };
}
const leGatePos = g => { const sl = LE_GATE.SLOTS.find(z => z[2] === g); return sl ? [LE_GATE.COLS[sl[0]], sl[1]] : [0, 0]; };
// the rev / shift light: the gear (manual: the lever's, automatic: the one it would be in), how high it revs (0 … 1+)
// and the limiter (≥ 97 % of the gear's top)
function leRev(car, rain) {
  const g = car.man ? (car.gear ?? 1) : leAutoGear(car.v);
  if (g < 1) return { g, r: 0, lim: false };
  const r = Math.abs(car.v) / (LE_GEAR_TOP[g - 1] * leGrip(car.tyre, rain));
  return { g, r, lim: r >= 0.97 };
}
// one step of DT seconds from game time s – the same as step() in langstrecke.py; `others`: [[d, x, v], …] of the
// other cars on the track at the start of the step
function leStep(car, s, jr, rain = false, others = []) {
  const ev = [], DT = LE.DT;
  if (car.pit) { car.temp = Math.max(LE.TMIN, car.temp - LE.COOL * DT); return ev; }
  const d0 = car.d, x0 = car.x, v0 = car.v, xl = leLapPos(d0);
  // the pit lane: from the entry line every car is on its way into the pits – the driver steers in (keeping right or
  // steering right at the line), else the autopilot takes over; out of the pit exit it races again
  let pl = car.pl || 0;
  if (pl === 0 && d0 >= 0 && xl >= LE.PIT_IN) {
    pl = car.pl = 1; car.ap = x0 >= LE.KEEP_R || car.st >= LE.KEEP_ST ? 0 : 1;
    ev.push("pitlane"); if (car.ap) ev.push("autopilot");
  } else if (pl === 3 && LE.PIT_OUT + LE.PIT_MERGE <= xl && xl < LE.PIT_IN) pl = car.pl = 0;
  const pz = pl ? lePitZ(d0, pl) : 0;
  if (pl === 1 && !car.ap && pz >= LE.PZ_IN + LE.PIT_ENTRY - LE.AP_LATE && x0 < lePitX(pz) - LE.PL_HW) { car.ap = 1; ev.push("autopilot"); }
  const ap = pl > 0 && car.ap === 1, cn = leCornerAt(xl);
  let th = ap ? 0 : car.thr, stc = ap ? 0 : car.st / 100;   // the autopilot: lifted off – the limiter brings it to the pit speed
  const emg = car.bat <= 0;                          // the battery is empty: the emergency drive mode
  const bite = Math.min(1, 0.2 + Math.abs(v0) / LE.VSTEER);   // how much the steering bites at this speed
  let push = 0;                                      // a corner pushes outward, ∝ speed²
  if (cn !== null) { const q = v0 / leSafe(cn, car.tyre, rain); push = (cn[2] > 0 ? -1 : 1) * LE.STEER_V * LE.PUSH * q * q; }
  if (ap) stc = leClamp((lePitX(pz) - x0) * LE.AP_K, -1, 1);   // the autopilot steers smoothly along the pit lane
  else if (car.ast) {                                // the assist: towards the racing line (the pit lane), brake before a corner
    const aim = pl ? lePitX(pz) : leClamp(leLine(xl) + car.lo, -LE.LMAX, LE.LMAX);
    const help = leClamp((aim - x0) * LE.ASSIST_K - push / (LE.STEER_V * bite), -1, 1);
    stc = leClamp(stc + (1 - Math.abs(stc)) * help, -1, 1);
    const [nc, dz] = leNextCorner(xl);
    if (nc !== null) { const tv = leSafe(nc, car.tyre, rain) * car.ak; if (v0 > tv && dz <= (v0 * v0 - tv * tv) / (2 * LE.BRAKE) + v0 * 0.3 + 2) th = -1; }
  }
  car.sw += leClamp(stc - car.sw, -LE.WHEEL * DT, LE.WHEEL * DT);
  let full = th > 0 && !car.eng && !emg;
  const pitlim = pl > 0 && pz < LE.PIT_OUT;         // the pit limiter: on by itself from the entry line to the exit
  if (pitlim && v0 >= LE.PIT_V - 0.3) full = false; // holding the limit: no full throttle (no heat, lifted drain)
  const gr = leGrip(car.tyre, rain), man = ap ? 0 : car.man || 0, g = car.gear ?? 1;   // the autopilot: automatic gears
  let acc = LE.ACC, dec = LE.COAST, lim = false, grind = false, rev = false, top = 0, vt;
  let gap = false;
  if (!man) {                                        // automatic: the plain car – with a torque gap at every shift
    vt = car.eng ? LE.VLIMP : (full ? LE.VFULL : LE.VLIFT) * gr;
    let ga = g;
    if (!(ga >= 1 && ga <= LE_GEAR_TOP.length)) ga = car.gear = leAutoGear(v0);   // from N / R: the gear that fits, no gap
    if (ga < LE_GEAR_TOP.length && v0 >= LE_GEAR_TOP[ga - 1] * LE.AUTO_UP) { car.gear = Math.max(ga + 1, leAutoGear(v0)); car.sg = LE.AUTO_GAP; }
    else if (ga > 1 && v0 < LE_GEAR_TOP[ga - 2] * LE.AUTO_DOWN) car.gear = ga - 1;
    gap = (car.sg || 0) > 1e-9;
    car.sg = Math.max(0, (car.sg || 0) - DT);
  }
  else if (g >= 1) {                                 // a gear: its band, its limiter, too high = weak pull
    top = LE_GEAR_TOP[g - 1] * gr;
    vt = car.eng ? Math.min(LE.VLIMP, top) : full ? top : Math.min(LE.VLIFT * gr, top);
    acc = LE.ACC * LE_GEAR_ACC[g - 1] * (v0 < LE_GEAR_LOW[g - 1] ? LE.LUG : 1);
    lim = v0 >= top - 0.3 && (full || v0 > top + 0.3);
    if (v0 > top + 0.3) dec = LE.EBRAKE;             // over the limiter after a downshift: engine braking
  } else {                                           // N: no drive – R: grinding while rolling, else backwards
    full = false; vt = 0;
    grind = g < 0 && v0 > LE.VREV_ON; rev = g < 0 && !grind;
    dec = grind ? LE.GRIND_DEC : LE.NEUTRAL_DEC;
  }
  if (emg) vt = Math.min(vt, LE.VEMERG);
  if (th < 0) { vt = Math.min(vt, LE.VBRAKE); dec = Math.max(dec, LE.BRAKE); }
  if (pitlim) { vt = Math.min(vt, LE.PIT_V); if (v0 > LE.PIT_V) dec = Math.max(dec, LE.BRAKE); }   // the limiter (manual gears too)
  if (pl === 2) { vt = Math.min(vt, Math.max(2, Math.sqrt(2 * LE.BOX_DEC * Math.max(0, (car.box ?? LE.BOX0) - pz)))); dec = Math.max(dec, LE.BOX_DEC); }   // into the box
  let tow = 0, bump = null, nudge = 0;               // the other cars: the slipstream on a straight, a gentle bump (never with the pit lane)
  if (!pl && LE.PIT_Z <= xl && xl <= LE.L - LE.PIT_Z) {
    for (const [od, ox, ov] of others) {
      const ol = leLapPos(od);
      if (ol < LE.PIT_Z || ol > LE.L - LE.PIT_Z) continue;
      const rel = leLapPos(od - d0), dx = ox - x0;
      if (rel <= 0 || rel > LE.SLIP_D) continue;
      if (cn === null && Math.abs(dx) < LE.SLIP_W) tow = Math.max(tow, 1 - rel / (LE.SLIP_D * 1.5));
      if (rel < LE.BUMP_D && Math.abs(dx) < LE.CAR_W && (bump === null || ov < bump)) { bump = ov; nudge = dx > 0 ? -LE.NUDGE : LE.NUDGE; }
    }
  }
  car.tow = tow;
  if (tow > 0 && th >= 0 && (!man || g >= 1)) vt += LE.SLIP_V * tow;
  if (car.sf === 2) { vt = Math.min(vt, LE.VGRASS); dec = Math.max(dec, LE.GRASS_DEC); }   // on the grass: heavy slowdown
  else if (car.sf === 1) vt *= LE.KERB_F;
  let v = v0 < vt ? (gap ? v0 : Math.min(vt, v0 + acc * DT)) : Math.max(vt, v0 - dec * DT);
  if (rev) {                                         // backwards, slowly: gas / lifted creeps / the brake stops
    const tg = th < 0 ? 0 : th > 0 ? -LE.VREV : -LE.VCREEP;
    v = v0 > tg ? Math.max(tg, v0 - LE.REV_ACC * DT) : Math.min(tg, v0 + (th < 0 ? LE.BRAKE : LE.REV_ACC) * DT);
  }
  car.bc = Math.max(0, car.bc - DT);
  if (bump !== null && v > bump) {
    v = Math.max(0, bump);
    if (car.bc <= 0) { car.bc = 1; car.bumps += 1; ev.push("bump"); }
  } else nudge = 0;
  const [lo, hi] = pl ? lePitBounds(pz) : [-LE.XMAX, LE.XMAX];   // in the pit lane: its white line, the pit wall, the boxes
  let x = leClamp(x0 + (car.sw * LE.STEER_V * bite + push + nudge) * DT, lo, hi);   // across the track
  const ax = Math.abs(x), sf = ax <= LE.HW || (pl && x > 0) ? 0 : ax <= LE.HW + LE.KERB ? 1 : 2;
  if (sf === 2 && car.sf !== 2) { car.offs += 1; ev.push("off"); }
  else if (sf === 1 && car.sf === 0) { car.kerb += 1; ev.push("kerb"); }
  car.sf = sf;
  if (!emg) {                                        // the battery: by the metre – full throttle much more; braking gives a little back
    let use = (full ? LE.E_FULL : LE.E_LIFT) * Math.abs(v) * DT;
    if (th < 0 && v < v0) use -= LE.REGEN * (v0 - v);
    car.bat = Math.max(0, Math.min(100, car.bat - use));
    if (car.bat <= 0) { car.flat += 1; ev.push("empty"); }
  }
  let d1 = d0 + v * DT;
  if (v < 0 && d1 < Math.floor(d0 / LE.L) * LE.L) { d1 = Math.floor(d0 / LE.L) * LE.L; v = 0; }   // backwards never over the line
  if (grind) { car.temp = Math.min(LE.RED, car.temp + LE.GRIND_HEAT * DT); ev.push("grind"); }
  else if (lim) car.temp = Math.min(LE.RED, car.temp + (jr ? LE.HEAT_JR : LE.HEAT) * LE.LIM_HEAT * DT);
  else if (full) car.temp = Math.min(LE.RED, car.temp + (jr ? LE.HEAT_JR : LE.HEAT) * DT);
  else car.temp = Math.max(LE.TMIN, car.temp - LE.COOL * DT);
  if ((full || lim || grind) && car.temp >= LE.RED - 1e-9) { car.eng = 1; car.blows += 1; car.temp = 80; ev.push("blow"); }
  const n0 = Math.floor(d0 / LE.L), n1 = Math.floor(d1 / LE.L);
  const tc = n1 > n0 ? s + (n1 * LE.L - d0) / v : 0;  // the moment the car crossed the line (within the step)
  if (n1 > n0 && n0 >= 0) {                          // the line (across the track and the pit lane): a lap – on to the box
    const lt = Math.floor((tc - car.ls) * 100 + 0.5) / 100;
    car.last = lt;
    car.best = !car.best || lt < car.best ? lt : car.best;
    car.ls = Math.floor(tc * 100 + 0.5) / 100;
    pl = car.pl = 2;
    ev.push("lap");
  } else if (n1 > n0) car.ls = Math.floor(tc * 100 + 0.5) / 100;
  if (pl === 2 && d1 >= n1 * LE.L + (car.box ?? LE.BOX0)) {       // at the box: the car stops – the pit stop begins
    d1 = n1 * LE.L + (car.box ?? LE.BOX0); v = 0;
    car.pit = 1; car.sw = 0; car.sf = 0; car.tow = 0; car.ap = 0;
    ev.push("pit");
  }
  car.d = d1; car.x = x; car.v = v;
  return ev;
}
// the circuit seen from above (the minimap): points every 4 m along the lap, the heading turned in the corners –
// the small gap where the drawing would not close is spread over the lap; normalised to 0 … 1 (aspect kept)
let _leMap = null;
function leTrackMap() {
  if (_leMap) return _leMap;
  const pts = [];
  let x = 0, y = 0, hd = 0;
  for (let d = 0; d <= LE.L; d += 4) {
    pts.push([x, y]);
    const c = leCornerAt(d + 2);
    if (c) hd += c[2] * Math.PI / 180 / (c[1] - c[0]) * 4;
    x += Math.cos(hd) * 4; y += Math.sin(hd) * 4;
  }
  const n = pts.length - 1, ex = pts[n][0] - pts[0][0], ey = pts[n][1] - pts[0][1];
  pts.forEach((p, i) => { p[0] -= ex * i / n; p[1] -= ey * i / n; });
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const x0 = Math.min(...xs), y0 = Math.min(...ys), w = Math.max(...xs) - x0, h = Math.max(...ys) - y0, s = Math.max(w, h);
  _leMap = { pts: pts.map(([a, b]) => [(a - x0) / s, (b - y0) / s]), w: w / s, h: h / s };
  return _leMap;
}
const leMapAt = d => { const m = leTrackMap(), u = leLapPos(d) / 4, i = Math.floor(u), f = u - i, a = m.pts[i], b = m.pts[Math.min(m.pts.length - 1, i + 1)]; return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]; };
// the curvature of the track at d (radians per metre, + = right) – the pseudo-3D picture bends with it
const leCurve = d => { const c = leCornerAt(leLapPos(d)); return c ? c[2] * Math.PI / 180 / (c[1] - c[0]) : 0; };
const leKmh = v => Math.round(v * 7);
const leLapTime = s => (s > 0 ? Math.floor(s / 60) + ":" + (s % 60).toFixed(1).padStart(4, "0") : "–:––.–");

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
    T("Driver: the joystick bottom left on the picture – up gas, down brake, sideways steering (or the arrow keys). In the red the engine overheats – it has to be swapped at the stop."),
    T("Gears: «A / M» on the picture switches at any time – automatic, or manual with the H shifter bottom right (R | 1 2 | 3 4 | 5 6, keys 1–6, R, N). Every gear has its speed band – shift up when the light turns red, a gear too high pulls weakly. Shifted well, manual is a little faster. R only when stopped: at speed it grinds the gearbox and overheats the engine."),
    T("Five corners per lap: the sign shows the direction and the suggested speed, the boards 150 / 100 / 50 m. Brake before the corner and steer through it – too fast and the car runs wide onto the kerb and the grass."),
    T("Racing line: come in from the outside, touch the inside in the middle of the corner, let the car run out again."),
    T("Close behind another car on a straight you get the slipstream – more speed to overtake. Running into a car only slows you down."),
    T("Driving assist (🧒, on for juniors): the car brakes before the corners and helps to steer. Everybody can switch it for themselves."),
    T("Electric car: full throttle drains the battery much faster than cruising. Empty – emergency drive mode: the car crawls to the pits."),
    T("Two batteries per team: at every stop the spare goes in with whatever charge it has. Plug the used one in first – it needs about a lap to charge."),
    T("Pit crew (everybody else): during the lap plug in the spare battery and lay out the 4 tyres. After an overheat also prepare the spare engine."),
    T("The stop takes 3 s with the battery swap, +4 s if the tyres are not ready, +6 s for an engine swap (+2 s if prepared)."),
    r.weather ?? 1 ? T("Sudden rain showers: the crew picks slicks or rain tyres – watch the forecast. The wrong tyres are slower.") : null,
    T("In the rain every corner needs less speed – even less with slicks. At night the headlights only reach a short way."),
    T("Alone in a team: the garage prepares, every stop takes 5 s – it plugs the spare battery in only after 8 s."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", leCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

const leSel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
const leMinutes = v => leSel(v || 8, [5, 8, 12].map(n => [n, "⏱ " + n + " min"]));
const leWeather = v => leSel(v ? 1 : 0, [[1, "🌦️ " + I18N.tr(T("Rain showers"))], [0, "☀️ " + I18N.tr(T("Always dry"))]]);
const leDiff = v => leSel(v || "normal", [["junior", "🧒 " + I18N.tr(T("Junior – with driving assist"))], ["normal", "🏁 " + I18N.tr(T("Normal"))]]);
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
    if (drv && !wasDriver) { thrLocal = 0; held.gas = held.brake = held.jgas = held.jbrake = false; pend = []; inflight = []; steer.sent = 0; ui.xs = null; }      // my turn: the pedals start released
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
    const inputs = inflight.slice(0, 36);                      // the server takes 40 at most per request – the rest next time
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
    predCache = null;
    sync();
  }
  // the pedals: gas (held = full throttle) and the brake (wins while held); neither = lifted off – from the keys
  // (↑ / W / Space, ↓ / S) and from the joystick's upper / lower zone
  const held = { gas: false, brake: false, jgas: false, jbrake: false };
  const pedals = () => {
    const v = held.brake || held.jbrake ? -1 : held.gas || held.jgas ? 1 : 0;
    if (v !== thrLocal) input("u", v);
    if (ui.joy) { ui.joy.classList.toggle("le-jgas", v > 0); ui.joy.classList.toggle("le-jbrake", v < 0); }
  };
  const pedal = on => { held.gas = !!on; pedals(); };
  const brake = on => { held.brake = !!on; pedals(); };
  // the steering: −100 … 100 – the arrow keys give full lock while held, the joystick steers by how far the knob is
  // pushed sideways (leJoy); sent in steps of 5, at most every 60 ms
  const steer = { kl: false, kr: false, joy: 0, sent: 0, at: 0, timer: 0 };
  function steerNow() {
    clearTimeout(steer.timer); steer.timer = 0;
    const b = (steer.kl ? -1 : 0) + (steer.kr ? 1 : 0);
    const v = b ? b * 100 : Math.round(leClamp(steer.joy, -100, 100) / 5) * 5;
    if (v === steer.sent) return;
    const wait = 0.06 - (nowS() - steer.at);
    if (wait > 0 && v !== 0 && Math.abs(v) !== 100) { steer.timer = setTimeout(steerNow, wait * 1000 + 1); return; }
    steer.sent = v; steer.at = nowS();
    input("s", v);
    if (ui.joy) { ui.joy.classList.toggle("le-jl", v < 0); ui.joy.classList.toggle("le-jr", v > 0); }
  }
  const KEYS = { ArrowLeft: "kl", KeyA: "kl", ArrowRight: "kr", KeyD: "kr" };
  const GAS = ["ArrowUp", "KeyW", "Space"], BRAKE = ["ArrowDown", "KeyS"];
  // manual gears on the keyboard: 1–6, R, N / 0
  const GEARKEYS = { KeyR: -1, KeyN: 0, Digit0: 0, Numpad0: 0 };
  for (let g = 1; g <= 6; g++) { GEARKEYS["Digit" + g] = g; GEARKEYS["Numpad" + g] = g; }
  // a gear in: to the server (validated there), a short click and a tick in the hand (not with reduced motion)
  function shiftTo(g, lever) {
    if (!amDriver()) return;
    const c = predicted();
    if (c && c.gear === g) return;
    input("g", g);
    if (ui.shift) ui.shift.set(g, lever);
    if (g !== 0) { LeAudio.tone([g < 0 ? 300 : 1500], "square", 0.03, 0.05); if (!leReduced()) leBuzz(15); }
    if (g < 0 && c && c.v > LE.VREV_ON) ui.grind = nowS();
  }
  function onKey(e) {
    if (!alive || !box.isConnected || !amDriver()) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || "")) return;
    if (KEYS[e.code]) { e.preventDefault(); if (!e.repeat) { steer[KEYS[e.code]] = true; steerNow(); } }
    else if (GAS.includes(e.code)) { e.preventDefault(); if (!e.repeat) pedal(1); }
    else if (BRAKE.includes(e.code)) { e.preventDefault(); if (!e.repeat) brake(1); }
    else if (GEARKEYS[e.code] != null) { const c = predicted(); if (c && c.man) { e.preventDefault(); if (!e.repeat) shiftTo(GEARKEYS[e.code]); } }
  }
  function onKeyUp(e) {
    if (KEYS[e.code]) { steer[KEYS[e.code]] = false; if (amDriver()) { e.preventDefault(); steerNow(); } return; }
    if (!amDriver()) return;
    if (GAS.includes(e.code)) { e.preventDefault(); pedal(0); } else if (BRAKE.includes(e.code)) { e.preventDefault(); brake(0); }
  }
  window.addEventListener("keydown", onKey);
  window.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", () => { steer.kl = steer.kr = false; held.gas = held.brake = false; if (amDriver()) { steerNow(); pedals(); } });
  // the first-drive hint under the joystick: until the gas was given with it once (remembered on this device)
  const JOY_SEEN = "fq-le-joy";
  const joySeen = () => { try { return localStorage.getItem(JOY_SEEN) === "1"; } catch { return false; } };
  // the virtual joystick (bottom left on the picture): up gas, down brake, sideways steering. It follows only its own
  // finger (pointerId + pointer capture) – a second thumb elsewhere never moves it; the knob stays on the ring and
  // springs back to the middle on release (= straight ahead, lifted off)
  function joystick() {
    const NS = "http://www.w3.org/2000/svg";
    const S_ = (tag, attrs, ...kids) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); e.append(...kids); return e; };
    const pt = a => { const r = a * Math.PI / 180; return (50 + 44 * Math.sin(r)).toFixed(2) + " " + (50 - 44 * Math.cos(r)).toFixed(2); };
    const arc = (a0, a1, cls) => S_("path", { d: "M " + pt(a0) + " A 44 44 0 0 1 " + pt(a1), class: cls });
    const ring = S_("svg", { viewBox: "0 0 100 100", class: "le-joyring", "aria-hidden": "true" },
      S_("circle", { cx: 50, cy: 50, r: 44, class: "le-jbase" }),
      arc(-52, 52, "le-jarc le-jagas"), arc(128, 232, "le-jarc le-jabrake"),
      S_("path", { d: "M 4 50 L 13 43 L 13 57 Z", class: "le-jarrow le-jal" }), S_("path", { d: "M 96 50 L 87 43 L 87 57 Z", class: "le-jarrow le-jar" }),
      S_("text", { x: 50, y: 21, class: "le-jtxt" }, I18N.tr(T("Gas"))), S_("text", { x: 50, y: 85, class: "le-jtxt" }, I18N.tr(T("Brake"))));
    const knob = h("div.le-knob");
    const el = h("div.le-joy", { role: "application", "aria-label": I18N.tr(T("Joystick: up gas, down brake, sideways steering")) }, ring, knob);
    const hint = joySeen() ? null : h("div.le-joyhint", "🕹️ ", T("Joystick: up gas, down brake"));
    let pid = null, cx = 0, cy = 0, zone = 0;
    steer.joy = 0; held.jgas = held.jbrake = false;                  // a new screen: an older joystick's thumb is gone
    const move = e => {
      const j = leJoy(e.clientX - cx, e.clientY - cy, el.clientWidth * 0.3);
      knob.style.transform = "translate(" + j.kx.toFixed(1) + "px, " + j.ky.toFixed(1) + "px)";
      steer.joy = j.s; steerNow();
      held.jgas = j.u > 0; held.jbrake = j.u < 0; pedals();
      if (j.u && j.u !== zone && !leReduced()) leBuzz(12);           // a small tick into the gas / brake zone
      if (j.u > 0 && hint && hint.isConnected && amDriver()) { hint.remove(); try { localStorage.setItem(JOY_SEEN, "1"); } catch {} }
      zone = j.u;
    };
    el.addEventListener("pointerdown", e => {
      e.preventDefault(); e.stopPropagation();
      if (gameT() < 0 && !introSkip) introSkip = true;
      if (pid != null) return;
      pid = e.pointerId; try { el.setPointerCapture(pid); } catch {}
      const b = el.getBoundingClientRect(); cx = b.left + b.width / 2; cy = b.top + b.height / 2;
      el.classList.add("le-jon"); move(e);
    });
    el.addEventListener("pointermove", e => { if (e.pointerId === pid) { e.preventDefault(); move(e); } });
    const up = e => {
      if (e.pointerId !== pid) return;
      pid = null; zone = 0; knob.style.transform = ""; el.classList.remove("le-jon");
      steer.joy = 0; held.jgas = held.jbrake = false; steerNow(); pedals();
    };
    for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) el.addEventListener(ev, up);
    el.addEventListener("contextmenu", e => e.preventDefault());
    return [el, hint];
  }
  // the H shifter (bottom right on the picture, manual gears only): a polished metal plate with the open gate, a short
  // chrome shaft and a chrome ball. The right thumb drags the ball along the gate (leGate) – its own pointerId, so it
  // works together with the joystick under the left thumb; it snaps into a gear, N on the rail.
  function shifter() {
    const NS = "http://www.w3.org/2000/svg";
    const S_ = (tag, attrs, ...kids) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); e.append(...kids); return e; };
    const X = nx => 60 + nx * 42, Y = ny => 52 + ny * 30;
    const grad = (id, kind, stops, at) => S_(kind, { id, ...at }, ...stops.map(([o, c]) => S_("stop", { offset: o, "stop-color": c })));
    const defs = S_("defs", {},
      grad("le-plate-g", "linearGradient", [["0", "#f8f9fa"], ["0.45", "#adb5bd"], ["0.55", "#ced4da"], ["1", "#6c757d"]], { x1: 0, y1: 0, x2: 1, y2: 1 }),
      grad("le-ball-g", "radialGradient", [["0", "#ffffff"], ["0.35", "#e9ecef"], ["0.7", "#868e96"], ["1", "#343a40"]], { cx: "0.38", cy: "0.32", r: "0.7" }));
    const gate = "M " + X(-0.75) + " " + Y(0) + " L " + X(0.75) + " " + Y(0) + " M " + X(-0.75) + " " + Y(-1) + " L " + X(-0.75) + " " + Y(0)
      + [-0.25, 0.25, 0.75].map(c => " M " + X(c) + " " + Y(-1) + " L " + X(c) + " " + Y(1)).join("");
    const labels = LE_GATE.SLOTS.map(([c, d, g]) => S_("text", { x: X(LE_GATE.COLS[c]), y: d < 0 ? 9 : 97, class: "le-gl" + (g < 0 ? " le-glr" : ""), "data-g": g }, g < 0 ? "R" : String(g)));
    const shaft = S_("line", { class: "le-shaft" }), ball = S_("circle", { r: 11.5, class: "le-ball", fill: "url(#le-ball-g)" }), shine = S_("circle", { r: 3.2, class: "le-shine" });
    const lever = S_("g", { class: "le-lever" }, shaft, ball, shine);
    const svg = S_("svg", { viewBox: "0 0 120 104", class: "le-plate", "aria-hidden": "true" }, defs,
      S_("rect", { x: 2, y: 2, width: 116, height: 100, rx: 14, fill: "url(#le-plate-g)", class: "le-platebg" }),
      ...[[10, 10], [110, 10], [10, 94], [110, 94]].map(([cx, cy]) => S_("circle", { cx, cy, r: 2.6, class: "le-screw" })),
      S_("path", { d: gate, class: "le-gate" }), S_("path", { d: gate, class: "le-gatein" }), ...labels, lever);
    const big = h("b.le-gearbig", "1");
    const el = h("div.le-shift", { role: "application", "aria-label": I18N.tr(T("Gear shifter: R, 1–6, N – keys 1–6, R, N")), title: I18N.tr(T("R only when stopped")) }, big, svg);
    let pid = null, pos = leGatePos(1), shown = null, nX = 0;
    const place = (x, y) => {
      pos = [x, y];
      const bx = X(x), by = Y(y);
      shaft.setAttribute("x1", bx); shaft.setAttribute("y1", by + 10); shaft.setAttribute("x2", bx); shaft.setAttribute("y2", by);
      for (const c of [ball, shine]) { c.setAttribute("cx", c === shine ? bx - 3.5 : bx); c.setAttribute("cy", c === shine ? by - 4 : by); }
    };
    const label = g => { const txt = g < 0 ? "R" : g === 0 ? "N" : String(g); if (big.textContent !== txt) big.textContent = txt; el.dataset.g = String(g);
      for (const l of labels) l.classList.toggle("on", +l.dataset.g === g); };
    const at = e => { const b = svg.getBoundingClientRect(); return leGate((e.clientX - b.left) / b.width * 120 / 42 - 60 / 42, ((e.clientY - b.top) / b.height * 104 - 52) / 30); };
    let live = 0;
    const move = e => { const r = at(e); place(r.x, r.y); if (r.gear !== live) { live = r.gear; label(live); shiftTo(live, true); } };
    el.addEventListener("pointerdown", e => {
      e.preventDefault(); e.stopPropagation();
      if (pid != null) return;
      pid = e.pointerId; try { el.setPointerCapture(pid); } catch {}
      const c = predicted(); live = c ? (c.gear ?? 1) : 1;
      el.classList.add("le-son"); move(e);
    });
    el.addEventListener("pointermove", e => { if (e.pointerId === pid) { e.preventDefault(); move(e); } });
    const up = e => {
      if (e.pointerId !== pid) return;
      pid = null; el.classList.remove("le-son");
      if (live) { const [x, y] = leGatePos(live); place(x, y); } else { nX = pos[0]; place(pos[0], 0); }   // snaps into the gear / onto the rail
    };
    for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) el.addEventListener(ev, up);
    el.addEventListener("contextmenu", e => e.preventDefault());
    place(...pos); label(1);
    return { el, set(g, lever) { shown = g; label(g); if (!lever && pid == null) { const p = g === 0 ? [nX, 0] : leGatePos(g); place(...p); } },
      sync(g) { if (pid == null && g !== shown) this.set(g); } };
  }

  // ---------- my car as the server will see it (the snapshot + my inputs up to now; the other cars moved on)
  let predCache = null;
  function predicted(tNow) {
    const t = myTeam();
    if (!t || !t.car) return null;
    tNow = tNow ?? Math.min(gameT(), limit());
    if (predCache && predCache.k === st.k && predCache.n === pend.length + inflight.length && Math.abs(predCache.at - tNow) < 0.001) return predCache.car;
    const car = { ...t.car };
    if (t.driver !== myId) return car;
    const evs = (t.ev || []).concat(inflight, pend).map(e => [Math.max(e[0], simT()), e[1], e[2]]).sort((a, b) => a[0] - b[0]);
    const oth = st.teams.filter(o => o.i !== t.i && !o.pit).map(o => [o.d, o.x || 0, o.v]);
    let k = st.k, i = 0, n = 0;
    const j = jr(), s0 = simT();
    while ((k + 1) / 10 <= tNow + 1e-9 && n < 80 && !car.pit) {
      const s = k / 10;
      while (i < evs.length && evs[i][0] <= s + 1e-9) { leApply(car, evs[i][1], evs[i][2]); i++; }
      for (const e of leStep(car, s, j, leInWin(st.rain, s), oth.map(([d, x, v]) => [d + v * (s - s0), x, v]))) effect(e, car, s);
      k++; n++;
    }
    car._s = k / 10;
    predCache = { k: st.k, n: pend.length + inflight.length, at: tNow, car };
    return car;
  }
  function effect(e, car, s) {
    const key = e + ":" + (e === "lap" || e === "pit" ? Math.floor(car.d / LE.L) : Math.floor(car.d / 25));
    if (fired.has(key)) return;
    fired.add(key);
    if (fired.size > 400) fired.clear();
    if (gameT() - s > 1.5) return;                     // old news (a reload)
    if (e === "kerb") { leBuzz(25); ui.rumble = nowS(); }
    else if (e === "bump") { try { Sound.play("wrong"); } catch {} leBuzz(60); ui.flash = nowS(); }
    else if (e === "off") { LeAudio.tone([160, 120, 90], "sawtooth", 0.25, 0.08, 0.12); leBuzz([120, 60, 120]); ui.flash = nowS(); ui.offAt = nowS(); }
    else if (e === "blow") { LeAudio.tone([200, 120, 80], "sawtooth", 0.3, 0.12, 0.2); leBuzz([200, 80, 200]); ui.flash = nowS(); }
    else if (e === "empty") { LeAudio.tone([660, 440, 330, 220], "square", 0.18, 0.08, 0.16); leBuzz([150, 80, 150, 80, 150]); ui.flash = nowS(); }
    else if (e === "lap") { try { Sound.play("tap"); } catch {} }
    else if (e === "grind") { ui.grind = nowS(); LeAudio.tone([140, 95, 140, 90], "sawtooth", 0.09, 0.1, 0.06); leBuzz([90, 30, 90, 30, 90]); }
  }

  // ---------- drawing the race (pseudo-3D from behind the car, the road bends with the corners)
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
  // the corner sign: an arrow bent like the corner, the suggested speed, the distance – red when braking is due
  function cornerSign(ctx, x, y, w, c, dz, kmh, hot) {
    const hh = w * 0.62;
    ctx.save();
    ctx.fillStyle = hot ? "rgba(201,42,42,.92)" : "rgba(15,23,42,.72)";
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, hh, 10) : ctx.rect(x, y, w, hh); ctx.fill();
    const dir = c[2] > 0 ? 1 : -1, sharp = Math.min(1, Math.abs(c[2]) / 150);
    const bx = x + w * 0.24, by = y + hh * 0.86, my = y + hh * 0.5, cy = y + hh * 0.2;
    const ex = bx + dir * w * 0.17, ey = y + hh * (0.18 + 0.32 * sharp);   // a hairpin turns back down
    ctx.strokeStyle = "#fff"; ctx.fillStyle = "#fff"; ctx.lineWidth = Math.max(3, w * 0.06); ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx, my); ctx.quadraticCurveTo(bx, cy, ex, ey); ctx.stroke();
    const ang = Math.atan2(ey - cy, ex - bx), hs = w * 0.1;
    ctx.beginPath(); ctx.moveTo(ex + Math.cos(ang) * hs, ey + Math.sin(ang) * hs);
    ctx.lineTo(ex + Math.cos(ang + 2.3) * hs, ey + Math.sin(ang + 2.3) * hs); ctx.lineTo(ex + Math.cos(ang - 2.3) * hs, ey + Math.sin(ang - 2.3) * hs); ctx.fill();
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.font = "900 " + Math.round(hh * 0.3) + "px system-ui, sans-serif";
    ctx.fillText(String(kmh), x + w * 0.7, y + hh * 0.36);
    ctx.font = "700 " + Math.round(hh * 0.17) + "px system-ui, sans-serif";
    ctx.fillText(dz > 0 ? Math.round(dz / 10) * 10 + " m" : "km/h", x + w * 0.7, y + hh * 0.72);
    ctx.restore();
  }
  // the minimap: the circuit from above, every car a dot in its colour, mine with a white ring
  function minimap(ctx, x, y, size, t, me) {
    const m = leTrackMap(), pad = size * 0.1, s = size - 2 * pad, ox = x + pad + (s - s * m.w) / 2, oy = y + pad + (s - s * m.h) / 2;
    ctx.save();
    ctx.fillStyle = "rgba(15,23,42,.55)"; ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, size, size, 10) : ctx.rect(x, y, size, size); ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = Math.max(2.5, size * 0.04); ctx.lineJoin = "round";
    ctx.beginPath(); m.pts.forEach(([a, b], i) => (i ? ctx.lineTo(ox + a * s, oy + b * s) : ctx.moveTo(ox + a * s, oy + b * s))); ctx.closePath(); ctx.stroke();
    const [sx, sy] = m.pts[0];                                       // the start / finish line and the pits
    ctx.fillStyle = "#ffd43b"; ctx.fillRect(ox + sx * s - 2, oy + sy * s - 4, 4, 8);
    const dot = (d, col, mine) => {
      const [a, b] = leMapAt(d), px = ox + a * s, py = oy + b * s, r = mine ? size * 0.06 : size * 0.045;
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(px, py, r, 0, 7); ctx.fill();
      ctx.strokeStyle = mine ? "#fff" : "rgba(0,0,0,.5)"; ctx.lineWidth = mine ? 2 : 1; ctx.stroke();
    };
    for (const o of st.teams) if (o.i !== me.i && !o.pit) dot(o.d + o.v * Math.max(0, Math.min(1.5, t - simT())), o.color, false);
    if (!me.pit) dot(me.d, me.color, true);
    ctx.restore();
  }
  function race(c, car, team, t, opts = {}) {
    const ctx = c.ctx, cw = c.w, ch = c.h, red = leReduced();
    const dk = leDark(t, limit()), rain = leInWin(st.rain, t);
    const VIEW = Math.round(150 - 60 * dk - (rain ? 25 : 0)), CAMZ = 5, F = 6, STEP = 3;
    const d = car.d + (car.pit ? 0 : car.v * Math.max(0, Math.min(0.1, t - (car._s ?? t))));
    const cd = d - CAMZ;                                              // the camera: CAMZ metres behind my car
    const yh = ch * 0.36, y0 = ch * 1.02;
    const sc = z => F / (F + Math.max(-F * 0.6, z));
    const unit = Math.min(cw, ch * 1.25) * 0.98 / (2 * (LE.HW + LE.KERB)) / sc(CAMZ);   // pixels per metre at z = 0
    const camX = (opts.xs ?? car.x) * 0.75;
    // the road ahead: the middle line bends with the curvature (slices of STEP metres from the camera)
    const n = Math.ceil(VIEW / STEP) + 1, offs = new Float32Array(n + 1);
    let slope = 0;
    for (let i = 1; i <= n; i++) { slope += leCurve(cd + (i - 0.5) * STEP) * STEP; offs[i] = offs[i - 1] + slope * STEP; }
    const offAt = z => { const u = Math.max(0, z) / STEP, i = Math.min(n - 1, Math.floor(u)), f = Math.min(1, u - i); return offs[i] + (offs[i + 1] - offs[i]) * f; };
    const X = (z, xm) => cw / 2 + (offAt(z) + xm - camX) * unit * sc(z);
    const Y = z => yh + (y0 - yh) * sc(z);
    // the sky: day blue → dusk → night with stars; the pine forest on the horizon turns with the corners
    const g = ctx.createLinearGradient(0, 0, 0, yh);
    const sky = [[[95, 160, 230], [190, 220, 245]], [[8, 12, 34], [38, 40, 84]]];
    const mix = (a, b) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * dk)).join(",")})`;
    g.addColorStop(0, rain ? (dk > 0.5 ? "#1c2230" : "#7d8796") : mix(sky[0][0], sky[1][0])); g.addColorStop(1, rain ? (dk > 0.5 ? "#2b3242" : "#aab3bf") : mix(sky[0][1], sky[1][1]));
    ctx.fillStyle = g; ctx.fillRect(0, 0, cw, yh + 1);
    if (dk > 0.3) { const r = leRand(11); ctx.fillStyle = `rgba(255,255,235,${0.6 * dk})`; for (let k = 0; k < 40; k++) ctx.fillRect(r() * cw, r() * yh * 0.85, 1.6, 1.6); }
    const pan = (ui.pan || 0) * cw * 0.35 + offs[n] * unit * sc(VIEW) * 0.15;
    ctx.fillStyle = dk > 0.5 ? "#0b1f17" : "#24573a";
    for (let k = -2; k < 26; k++) {                                   // fir silhouettes (Les Tannes)
      const px = ((((k * 37 - pan) % (cw + 80)) + cw + 80) % (cw + 80)) - 40, hh = 18 + ((k * 13) % 5) * 6;
      ctx.beginPath(); ctx.moveTo(px - 12, yh); ctx.lineTo(px, yh - hh); ctx.lineTo(px + 12, yh); ctx.fill();
    }
    ctx.fillStyle = dk > 0.5 ? "#0f2a1c" : rain ? "#3d6b4a" : "#4f9a5e"; ctx.fillRect(0, yh, cw, ch - yh);
    // the road in slices from far to near: grass stripes, kerbs red / white in the corners, white edges, the line
    const asphalt = dk > 0.5 ? ["#2a2d33", "#2d3037"] : rain ? ["#4b5059", "#4f545d"] : ["#6b6f78", "#666a73"];
    const grass = dk > 0.5 ? ["#0f2a1c", "#123020"] : rain ? ["#3d6b4a", "#426f4f"] : ["#4f9a5e", "#57a366"];
    const quad = (z1, z2, a1, b1, a2, b2) => { ctx.beginPath(); ctx.moveTo(X(z1, a1), Y(z1)); ctx.lineTo(X(z1, b1), Y(z1)); ctx.lineTo(X(z2, b2), Y(z2)); ctx.lineTo(X(z2, a2), Y(z2)); ctx.fill(); };
    for (let i = n - 1; i >= 0; i--) {
      const z1 = (i + 1) * STEP, z2 = i * STEP, k = Math.floor((cd + z2) / STEP), dd = cd + z2;
      if (z2 > VIEW) continue;
      ctx.fillStyle = grass[k % 2 ? 1 : 0]; quad(z1, z2, -40, 40, -40, 40);
      ctx.fillStyle = asphalt[k % 2 ? 1 : 0]; quad(z1, z2, -LE.HW, LE.HW, -LE.HW, LE.HW);
      const cn = leCornerAt(leLapPos(dd)) || leCornerAt(leLapPos(dd + 15)) || leCornerAt(leLapPos(dd - 15));
      if (cn) { ctx.fillStyle = k % 2 ? "#e03131" : "#f1f3f5"; quad(z1, z2, -LE.HW - LE.KERB, -LE.HW, -LE.HW - LE.KERB, -LE.HW); quad(z1, z2, LE.HW, LE.HW + LE.KERB, LE.HW, LE.HW + LE.KERB); }
      ctx.fillStyle = "rgba(255,255,255,.8)"; quad(z1, z2, -LE.HW - 0.25, -LE.HW, -LE.HW - 0.25, -LE.HW); quad(z1, z2, LE.HW, LE.HW + 0.25, LE.HW, LE.HW + 0.25);
      if (opts.line && k % 3 === 0) { const l1 = leLine(leLapPos(cd + z1)), l2 = leLine(leLapPos(dd)); ctx.fillStyle = "rgba(255,212,59,.45)"; quad(z1, z2, l1 - 0.15, l1 + 0.15, l2 - 0.15, l2 + 0.15); }
      if (leLapPos(dd) > LE.L - STEP && leLapPos(dd) <= LE.L) {             // the start / finish line: chequered
        for (let q = 0; q < 12; q++) { ctx.fillStyle = q % 2 ? "#111" : "#fff"; const a = -LE.HW + q * LE.HW / 6; quad(z1, z2, a, a + LE.HW / 6, a, a + LE.HW / 6); }
      }
    }
    // beside the track: trees, banners, camping fans, the braking boards; the other cars – far first
    const items = [];
    const at = (rel, xm, f) => { const z = rel + CAMZ; if (z > 0.5 && z < VIEW) items.push({ z, f: () => f(X(z, xm), Y(z), unit * sc(z), z) }); };
    for (let k = Math.floor((d - 10) / 24); k * 24 < d + VIEW; k++) {
      for (const side of [-1, 1]) at(k * 24 - d, side * (LE.HW + LE.KERB + 4 + (k % 3) * 2.5), (x, y, u) => {
        ctx.fillStyle = dk > 0.5 ? "#0b2018" : ["#1f6b3e", "#2b7f48"][((k % 2) + 2) % 2]; ctx.beginPath(); ctx.moveTo(x, y - u * 6); ctx.lineTo(x + u * 1.7, y); ctx.lineTo(x - u * 1.7, y); ctx.fill(); });
    }
    const lap0 = Math.floor(d / LE.L) - 1;
    for (let lp = lap0; lp <= lap0 + 2; lp++) {
      [20, 270, 590].forEach((x0, i) => {                           // now and then a banner (it changes from lap to lap)
        if (((lp + i) % 4 + 4) % 4 === 3) return;
        at(lp * LE.L + x0 - d, (i % 2 ? 1 : -1) * (LE.HW + LE.KERB + 3), (x, y, u) => { const bw = u * 6, bh = u * 1.05;
          ctx.fillStyle = "#495057"; ctx.fillRect(x - bw * 0.42, y - bh * 1.6, u * 0.1, bh * 1.6); ctx.fillRect(x + bw * 0.38, y - bh * 1.6, u * 0.1, bh * 1.6);
          if (bw > 30) leBanner(ctx, (((lp + i) % 3) + 3) % 3, x - bw / 2, y - bh * 1.9, bw, bh); });
      });
      [175, 385].forEach((x0, i) => {                                // fans camping beside the track – mostly for my team
        if (((lp * 2 + i) % 3 + 3) % 3 === 2) return;
        const others = st.teams.filter(o => o !== team), k = ((lp + i) % 4 + 4) % 4, fan = k === 3 && others.length ? others[(lp + i + 40) % others.length] : team;
        const sign = "I ❤️ #" + fan.num + (fan.country ? " " + leFlag(fan.country) : "");
        at(lp * LE.L + x0 - d, (i ? 1 : -1) * (LE.HW + LE.KERB + 6), (x, y, u) => { if (u * 1.25 > 5) leCamp(ctx, x, y, u * 1.25, t, lp + i, sign, fan.color, dk > 0.5); });
      });
      for (const cn of LE_CORNERS) {                                 // the braking boards 150 / 100 / 50 m on the outside of the corner
        const out = cn[2] > 0 ? -1 : 1;
        for (const m of [150, 100, 50]) at(lp * LE.L + cn[0] - m - d, out * (LE.HW + LE.KERB + 1.2), (x, y, u) => { const bw = u * 1.4, bh = u * 1;
          if (bw < 5) return;
          ctx.fillStyle = "#495057"; ctx.fillRect(x - u * 0.06, y - bh * 1.8, u * 0.12, bh * 1.8);
          ctx.fillStyle = "#fff"; ctx.fillRect(x - bw / 2, y - bh * 2.6, bw, bh); ctx.strokeStyle = "#e03131"; ctx.lineWidth = Math.max(1, u * 0.1); ctx.strokeRect(x - bw / 2, y - bh * 2.6, bw, bh);
          ctx.fillStyle = "#111"; ctx.font = "900 " + Math.max(6, Math.round(bh * 0.7)) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(String(m), x, y - bh * 2.1); });
        at(lp * LE.L + cn[0] - d, out * (LE.HW + LE.KERB + 1.5), (x, y, u) => {     // chevrons at the turn-in
          const bw = u * 2.6, bh = u * 1.1; if (bw < 6) return;
          ctx.fillStyle = "#fff"; ctx.fillRect(x - bw / 2, y - bh * 1.5, bw, bh); ctx.fillStyle = "#e03131";
          for (let q = 0; q < 3; q++) { const cx = x - bw * 0.3 + q * bw * 0.3, dir = cn[2] > 0 ? 1 : -1; ctx.beginPath(); ctx.moveTo(cx - dir * bw * 0.1, y - bh * 1.4); ctx.lineTo(cx + dir * bw * 0.08, y - bh); ctx.lineTo(cx - dir * bw * 0.1, y - bh * 0.6); ctx.lineTo(cx - dir * bw * 0.02, y - bh); ctx.fill(); } });
      }
    }
    for (const o of st.teams) {                                      // the other cars where they are on the track
      if (o === team || o.pit) continue;
      let rel = leLapPos((o.d + o.v * Math.max(0, Math.min(1.5, t - simT()))) - d);
      if (rel > LE.L / 2) rel -= LE.L;
      if (rel < -CAMZ + 1 || rel > VIEW) continue;
      const haz = o.emg && Math.floor(t * 2.5) % 2 === 0;           // a car in the emergency drive mode: hazard lights
      at(rel, o.x || 0, (x, y, u) => leCarRear(ctx, x, y, u * 2.8, o.color, o.num, { night: dk > 0.4, alpha: 0.97, flag: leFlag(o.country), hazard: haz, emg: haz }));
    }
    items.sort((a, b) => b.z - a.z).forEach(it => it.f());
    if (dk > 0) {                                     // night: dark all around, the headlights light the road ahead
      ctx.save();
      const hx = X(CAMZ + 14, car.x), hy = Y(CAMZ + 14);
      const grad = ctx.createRadialGradient(hx, hy, unit * 0.5, hx, hy, Math.max(cw, ch) * 0.75);
      grad.addColorStop(0, "rgba(4,8,22,0)"); grad.addColorStop(0.35, `rgba(4,8,22,${0.3 * dk})`); grad.addColorStop(1, `rgba(4,8,22,${0.72 * dk})`);
      ctx.fillStyle = grad; ctx.fillRect(0, 0, cw, ch);
      ctx.globalCompositeOperation = "lighter";
      const zb = Math.min(VIEW, 45), beam = ctx.createLinearGradient(0, Y(CAMZ), 0, Y(zb));
      beam.addColorStop(0, `rgba(255,240,190,${0.16 * dk})`); beam.addColorStop(1, "rgba(255,240,190,0)");
      ctx.fillStyle = beam; ctx.beginPath(); ctx.moveTo(X(CAMZ, car.x - 1), Y(CAMZ)); ctx.lineTo(X(zb, car.x - 4), Y(zb)); ctx.lineTo(X(zb, car.x + 4), Y(zb)); ctx.lineTo(X(CAMZ, car.x + 1), Y(CAMZ)); ctx.fill();
      ctx.restore();
    }
    // my car (or the team's car on the TV): rumble on the kerb, dust on the grass, wind lines in the slipstream
    const cx0 = X(CAMZ, opts.xs ?? car.x), cy0 = Y(CAMZ), cwid = unit * sc(CAMZ) * 2.8;
    const rumble = !red && (car.sf === 1 || (ui.rumble && nowS() - ui.rumble < 0.25)) ? Math.sin(t * 90) * 1.5 : 0;
    const grinding = !opts.tv && ui.grind && nowS() - ui.grind < 0.9;     // R at speed: the gearbox grinds – sparks, a hard shake
    const shake = (car.v > 0 && !red ? Math.sin(t * 40) * 0.5 + rumble : 0) + (grinding && !red ? Math.sin(t * 110) * 4 : 0);
    if (car.sf === 2 && car.v > 2 && !red) {
      ctx.fillStyle = "rgba(160,130,90,.45)";
      for (let k = 0; k < 6; k++) { const a = leRand(Math.floor(t * 20) + k)(); ctx.beginPath(); ctx.arc(cx0 + (a - 0.5) * cwid, cy0 - cwid * 0.05 + a * 8, cwid * (0.08 + a * 0.08), 0, 7); ctx.fill(); }
    }
    if ((car.tow || 0) > 0.05 && !red) {
      ctx.strokeStyle = `rgba(255,255,255,${0.25 + 0.4 * car.tow})`; ctx.lineWidth = 2;
      const r = leRand(Math.floor(t * 15));
      ctx.beginPath(); for (let k = 0; k < 8; k++) { const sx = cx0 + (r() - 0.5) * cwid * 1.6, sy = cy0 - cwid * (0.2 + r() * 0.6); ctx.moveTo(sx, sy); ctx.lineTo(sx + (sx - cw / 2) * 0.08, sy + cwid * 0.35); } ctx.stroke();
    }
    if (grinding) {
      const r = leRand(red ? 3 : Math.floor(t * 30));
      ctx.lineWidth = 2;
      for (let k = 0; k < 14; k++) {
        const sx = cx0 + (r() - 0.5) * cwid * 0.9, sy = cy0 + cwid * 0.08, a = -Math.PI / 2 + (r() - 0.5) * 2.4, len = cwid * (0.15 + r() * 0.35);
        ctx.strokeStyle = r() < 0.5 ? "#ffd43b" : "#ff922b";
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + Math.cos(a) * len, sy + Math.sin(a) * len); ctx.stroke();
      }
    }
    const emg = car.bat != null && car.bat <= 0 && !car.pit, haz = emg && Math.floor(t * 2.5) % 2 === 0;
    leCarRear(ctx, cx0, cy0 + shake, cwid, team.color, team.num, { brake: car.thr < 0 || (car.v > LE.VLIFT + 1 && !car.thr), night: dk > 0.4, smoke: !!car.eng, flag: leFlag(team.country),
      hazard: haz, emg: haz, bat: car.bat });
    if (rain) {
      ctx.strokeStyle = "rgba(200,215,235,.55)"; ctx.lineWidth = 1;
      const r = leRand(red ? 5 : Math.floor(t * 12));
      ctx.beginPath(); for (let k = 0; k < 70; k++) { const x = r() * cw, y = r() * ch; ctx.moveTo(x, y); ctx.lineTo(x - 3, y + 12); } ctx.stroke();
    }
    if (ui.flash && nowS() - ui.flash < 0.35 && !opts.tv) { ctx.fillStyle = `rgba(242,84,91,${0.35 * (1 - (nowS() - ui.flash) / 0.35)})`; ctx.fillRect(0, 0, cw, ch); }
    // the minimap (top right) and the next corner (top left)
    const ms = Math.round(Math.min(110, Math.max(70, Math.min(cw, ch) * 0.26)));
    minimap(ctx, cw - ms - 6, 6, ms, t, { ...team, d, pit: car.pit });
    const [nc, dz] = leNextCorner(leLapPos(d));
    if (nc && dz < 220 && !car.pit) {
      const vs = leSafe(nc, car.tyre, rain), kmh = Math.round(leKmh(vs * 0.95) / 5) * 5;
      const hot = car.v > vs * 1.02 && dz <= (car.v * car.v - vs * vs) / (2 * LE.BRAKE) + car.v * 0.6 + 8;
      cornerSign(ctx, 6, 6, Math.min(ms * 1.15, 120), nc, dz, kmh, hot);
    }
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
  let lastFrame = 0;
  function frame() {
    if (!alive || !box.isConnected) return stop();
    raf = requestAnimationFrame(frame);
    if (!st || st.phase !== "play") { LeAudio.engine(false); return; }
    const t = gameT(), fdt = Math.min(0.1, Math.max(0, nowS() - lastFrame));
    lastFrame = nowS();
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
          car = { ...tm.car || {}, d: tm.d, v: tm.v, x: tm.x || 0, pit: tm.pit, thr: (tm.car || {}).thr ?? 1, eng: tm.eng, sf: tm.sf || 0 };
          car.d = tm.pit ? tm.d : tm.d + tm.v * Math.max(0, Math.min(1.5, t - simT()));
          car._s = t;
          if (car.bat == null && tm.emg) car.bat = 0;
        }
        if (car) {
          // the picture follows the car smoothly across the track (a correction from the server glides, never jumps)
          ui.xs = ui.xs == null || car.pit ? car.x : ui.xs + (car.x - ui.xs) * Math.min(1, fdt * 14);
          if (!car.pit && !leReduced()) ui.pan = ((ui.pan || 0) + leCurve(car.d) * car.v * fdt * 0.6) % 100;
          race(c, car, tm, t, { tv: ui.mode !== "drive", xs: ui.xs, line: ui.mode === "drive" && !!car.ast });
          const big = (txt, sub, col) => {
            const ctx = c.ctx;
            ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineWidth = 6; ctx.lineJoin = "round"; ctx.strokeStyle = "rgba(15,23,42,.75)"; ctx.fillStyle = col || "#fff";
            let fs = Math.round(Math.min(c.w * 0.1, c.h * 0.11));
            ctx.font = "900 " + fs + "px system-ui, sans-serif";
            const tw = ctx.measureText(txt).width;
            if (tw > c.w * 0.94) { fs = Math.floor(fs * c.w * 0.94 / tw); ctx.font = "900 " + fs + "px system-ui, sans-serif"; }     // a long word fits the screen
            ctx.strokeText(txt, c.w / 2, c.h * 0.42); ctx.fillText(txt, c.w / 2, c.h * 0.42);
            if (sub) {                                         // the line below – wrapped when it is too long for the screen
              const ss = Math.round(Math.min(c.w * 0.045, 18)), lines = [];
              ctx.font = "700 " + ss + "px system-ui, sans-serif"; ctx.lineWidth = 4;
              for (const w of sub.split(" ")) { const l = lines.length ? lines[lines.length - 1] + " " + w : w; if (lines.length && ctx.measureText(l).width > c.w * 0.92) lines.push(w); else lines[Math.max(0, lines.length - 1)] = l; }
              lines.forEach((l, i) => { const y = c.h * 0.42 + 34 + i * (ss + 4); ctx.strokeText(l, c.w / 2, y); ctx.fillText(l, c.w / 2, y); });
            }
          };
          const small = (txt, col) => {
            const ctx = c.ctx, fs = Math.round(Math.min(c.w * 0.05, 18));
            ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.font = "800 " + fs + "px system-ui, sans-serif"; ctx.lineWidth = 4; ctx.strokeStyle = "rgba(15,23,42,.75)"; ctx.fillStyle = col;
            ctx.strokeText(txt, c.w / 2, c.h * 0.6); ctx.fillText(txt, c.w / 2, c.h * 0.6);
          };
          if (t < 1 && ui.mode === "drive") big(I18N.tr(T("GO!")), null, "#69db7c");
          else if (t >= limit()) big("🏁 " + I18N.tr(T("Finish!")));
          else if (car.bat != null && car.bat <= 0 && !car.pit) big("⚠️ " + I18N.tr(T("Emergency drive mode")), I18N.tr(T("Battery empty – crawling to the pits.")), "#ffa94d");
          else if (ui.mode === "drive" && ui.grind && nowS() - ui.grind < 1.6) big("💥 " + I18N.tr(T("Gearbox!")), I18N.tr(T("R only when stopped")), "#ff922b");
          else if (car.eng) big("💥 " + I18N.tr(T("Engine overheated!")), I18N.tr(T("Limp to the pits – it gets swapped.")), "#ff8787");
          else if (ui.mode === "drive" && (car.sf === 2 || (ui.offAt && nowS() - ui.offAt < 1.5))) big("🟫 " + I18N.tr(T("Off the track!")), I18N.tr(T("Too fast for the corner – brake earlier and steer back onto the track.")), "#ffd8a8");
          else if (ui.mode === "drive" && brakeHint(car, t)) big("🛑 " + I18N.tr(T("Brake!")), I18N.tr(T("Corner ahead")), "#ff8787");
          else if (ui.mode === "drive" && car.thr > 0 && car.bat < leNeed(car.d).mix && Math.floor(t * 3) % 2 === 0)
            big("🔋 " + I18N.tr(T("Save energy!")), I18N.tr(T("Lift off – the battery won't last the lap at full throttle.")), "#ffd43b");
          else if (ui.mode === "drive" && car.temp >= 92 && Math.floor(t * 4) % 2 === 0) big("🔥 " + I18N.tr(T("Let go!")), null, "#ff6b6b");
          else if ((car.tow || 0) > 0.05 && ui.mode === "drive") small("🌬️ " + I18N.tr(T("Slipstream!")), "#e7f5ff");
          if (ui.mode === "drive" && car.temp >= 92 && !car.eng && t - lastTempWarn > 1) { lastTempWarn = t; leBuzz(80); LeAudio.tone([900], "square", 0.08, 0.05); }
          if (ui.mode === "drive") LeAudio.engine(!document.hidden && !car.pit && t < limit(), Math.min(1, car.v / LE.VFULL * 0.7 + Math.max(0, car.thr) * 0.3));
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
  // «Brake!» for beginners without the assist: juniors always, everybody else in the first two laps – before a corner
  // while too fast
  function brakeHint(car, t) {
    if (car.ast || (!jr() && leLaps(car.d) >= 2)) return false;
    const [nc, dz] = leNextCorner(leLapPos(car.d));
    if (!nc) return false;
    const safe = leSafe(nc, car.tyre, leInWin(st.rain, t));
    return car.thr >= 0 && car.v > safe + 0.5 && dz <= (car.v * car.v - safe * safe) / (2 * LE.BRAKE) + car.v * 0.8 + 10;
  }
  const setTxt = (el, txt) => { if (el && el.textContent !== txt) el.textContent = txt; };
  // ---------- the bars: position, lap, clock, temperature, lap times and gaps, standings
  function hud(car, tm, t) {
    const hd = ui.hud;
    if (!hd || !tm) return;
    const pos = st.standings.indexOf(tm.i) + 1, tt = Math.max(0, Math.min(t, limit())), night = leDark(tt, limit()) > 0.5;
    setTxt(hd.pos, "P" + pos + "/" + st.teams.length);
    setTxt(hd.lap, I18N.tr(T("Lap {0}")).replace("{0}", leLaps(car.d) + 1));
    setTxt(hd.clock, (night ? "🌙 " : "☀️ ") + leClock(tt, limit()) + (leInWin(st.rain, tt) ? " 🌧️" : ""));
    setTxt(hd.left, "⏳ " + leRaceLeft(tt, limit()));
    hd.left.classList.toggle("le-final", tt >= limit() * 22 / 24);
    if (hd.cur) {                                              // the lap times, the gaps to the cars ahead / behind
      const c0 = tm.car || {}, ls_ = car.ls ?? c0.ls ?? 0, cur = car.pit || car.d < 0 ? 0 : Math.max(0, Math.min(t, limit()) - ls_);
      setTxt(hd.cur, "⏱ " + leLapTime(cur));
      setTxt(hd.best, "⭐ " + leLapTime(tm.best_lap || c0.best || 0));
      const dOf = o => (o.i === tm.i ? car.d : o.pit ? o.d : o.d + o.v * Math.max(0, Math.min(1.5, t - simT())));
      const k = st.standings.indexOf(tm.i), ahead = k > 0 ? st.teams[st.standings[k - 1]] : null, behind = st.teams[st.standings[k + 1]];
      const gap = dd => (dd >= LE.L ? "+" + Math.floor(dd / LE.L) + " " + I18N.tr(T("lap")) : (dd / 21).toFixed(1) + " s");
      setTxt(hd.ahead, ahead ? "▲ " + gap(Math.max(0, dOf(ahead) - car.d)) : "▲ –");
      setTxt(hd.behind, behind ? "▼ " + gap(Math.max(0, car.d - dOf(behind))) : "▼ –");
    }
    if (hd.temp) {
      const v = (car.temp - LE.TMIN) / (LE.RED - LE.TMIN) * 100;
      hd.temp.style.setProperty("--v", Math.max(0, Math.min(100, v)).toFixed(1) + "%");
      hd.temp.dataset.lvl = car.eng ? "red" : car.temp >= 92 ? "red" : car.temp >= LE.YELLOW ? "yellow" : "ok";
      setTxt(hd.speed, leKmh(car.v) + " km/h");
      setTxt(hd.tyre, car.tyre === "r" ? "🌧️" : "☀️");
      hd.tyre.classList.toggle("le-wrong", leGrip(car.tyre, leInWin(st.rain, tt)) < 1);
    }
    if (hd.gears) {                                            // the gears: the toggle, the shifter, the gear and the rev light
      const man = !!car.man, rain = leInWin(st.rain, tt), rv = leRev(car, rain);
      if (hd.gears.dataset.on !== String(man)) {
        hd.gears.dataset.on = String(man); hd.gears.classList.toggle("on", man); hd.gears.setAttribute("aria-pressed", String(man));
        if (ui.shift) ui.shift.el.hidden = !man;
      }
      if (ui.shift && man) ui.shift.sync(car.gear ?? 1);
      setTxt(hd.gear, rv.g < 0 ? "R" : rv.g === 0 ? "N" : man ? String(rv.g) : "A" + rv.g);
      const n = rv.g < 1 ? 0 : Math.max(1, Math.min(6, Math.round((rv.r - 0.4) / 0.57 * 6))), lvl = rv.lim ? "lim" : String(n);
      if (hd.rev.dataset.lvl !== lvl) { hd.rev.dataset.lvl = lvl; [...hd.rev.children].forEach((d, i) => { d.className = rv.lim ? "r" : i < n ? (i < 3 ? "g" : i < 5 ? "y" : "r") : ""; }); }
    }
    if (hd.assist) { const on = !!car.ast; if (hd.assist.dataset.on !== String(on)) { hd.assist.dataset.on = String(on); hd.assist.classList.toggle("on", on); hd.assist.setAttribute("aria-pressed", String(on)); } }
    if (hd.bat) {                                              // the battery: green, orange (it won't last the lap flat out), red
      const b = Math.max(0, car.bat ?? 0), need = leNeed(car.d), lvl = b <= 0 || b < need.lift ? "red" : b < need.mix ? "yellow" : "ok";
      hd.bat.style.setProperty("--v", Math.min(100, b).toFixed(1) + "%");
      hd.bat.dataset.lvl = lvl;
      setTxt(hd.batTxt, Math.ceil(b) + "%");
      hd.batTxt.dataset.lvl = lvl;
      hd.save.hidden = lvl === "ok" || car.pit;
      setTxt(hd.save, b <= 0 ? "⚠️ " + I18N.tr(T("Emergency drive mode")) : "🔋 " + I18N.tr(T("Save energy!")));
      hd.save.classList.toggle("le-emg", b <= 0);
    }
    if (hd.cast) setTxt(hd.cast, forecast(tt));
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
  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return !st.solo && !me.guest && st.status !== "done" ? "langstrecke" : null; }
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const tm = myTeam();
    const { mode, intro: introOn } = leScreen(st, myId, gameT());
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, mode, introOn, tm && tm.driver, mode === "pit" && tm.stop.t,
      mode === "crew" && tm.prep && tm.prep.need_eng, st.phase === "lobby" ? st.players.map(p => [p.id, p.team]) : 0, st.phase === "done" ? st.players.map(p => p.place) : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running); box.classList.toggle("le-scroll", mode === "lobby"); box.classList.toggle("le-drv", mode === "drive" && !introOn);
    ui = { go: ui.go ?? true, roared: ui.roared, mode, intro: introOn, xs: mode === "drive" ? ui.xs : null, pan: ui.pan };
    if (!st) return show(h("section.card.center", h("div.big-ic", LE_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const menu = gameMenu({ rules: () => langstreckeRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: invite(),
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", LE_ICON, " ", leName())));
    if (st.phase === "done") { LeAudio.engine(false); return show(head, result()); }
    if (st.phase === "lobby") return show(head, lobby());
    const cv = h("canvas.le-canvas"), wrap = h("div.le-wrap" + (mode === "drive" || introOn ? ".le-big" : mode === "pit" ? ".le-gar" : ".le-tv"), cv);
    ui.cv = { el: cv, ctx: cv.getContext("2d"), wrap, w: 0, h: 0, dpr: 0 };
    wrap.addEventListener("pointerdown", () => { if (gameT() < 0 && !introSkip) introSkip = true; });       // a tap skips the intro
    ui.hud = { pos: h("b.le-pos"), lap: h("span.le-lap"), clock: h("span.le-clock"), left: h("span.le-left") };
    const top = h("div.le-top", ui.hud.pos, ui.hud.lap, ui.hud.clock, ui.hud.left);
    ui.board = h("div.le-board");
    const teamTag = tm ? h("span.le-teamtag", { style: { "--tc": tm.color } }, leFlagEl(tm.country), " #" + tm.num, " ", C(tm.name)) : null;
    // the lap times and the gaps: this lap, the team's best lap, to the car ahead / behind
    const times = () => {
      Object.assign(ui.hud, { cur: h("span.le-cur"), best: h("span.le-bestlap"), ahead: h("span.le-gapa"), behind: h("span.le-gapb") });
      return h("div.le-times", { "aria-label": I18N.tr(T("Lap times")) }, ui.hud.cur, ui.hud.best, ui.hud.ahead, ui.hud.behind);
    };
    if (mode === "drive") {
      Object.assign(ui.hud, { speed: h("b.le-speed"), temp: h("div.le-gauge.le-temp"), crew: h("div.le-crewstrip"), tyre: h("span.le-tyre"), cast: h("span.le-cast"),
        bat: h("div.le-gauge.le-batg"), batTxt: h("b.le-battxt"), save: h("span.le-save", { hidden: true }),
        gear: h("b.le-gear"), rev: h("span.le-rev", { "aria-hidden": "true" }, ...Array.from({ length: 6 }, () => h("i"))) });
      const gauges = h("div.le-gauges", ui.hud.speed, h("span.le-gearbox", ui.hud.gear, ui.hud.rev), ui.hud.tyre, h("span.le-g", "🌡️", ui.hud.temp), h("span.le-g.le-gb", "🔋", ui.hud.bat, ui.hud.batTxt));
      wrap.append(ui.hud.crew, ui.hud.save);
      // the driving assist (auto-brake, steering help) – my own choice, remembered for my next stints
      ui.hud.assist = h("button.le-assist", { type: "button", "aria-pressed": "false", title: I18N.tr(T("Driving assist: the car brakes before the corners and helps to steer")),
        onclick: () => { const c = predicted(); if (c) input("a", c.ast ? 0 : 1); } }, "🧒 ", T("Assist"));
      // the gears «A / M» in the picture, above the shifter: switches at any time, mid-stint too (an adult and a child
      // can share a car) – the server remembers it per person for their next stints; manual engages the gear that fits
      ui.hud.gears = h("button.le-am", { type: "button", "aria-pressed": "false", "aria-label": I18N.tr(T("Gears: automatic or manual (H shifter)")),
        title: I18N.tr(T("Gears: automatic or manual (H shifter)")), onclick: e => { e.stopPropagation(); const c = predicted(); if (c) input("m", c.man ? 0 : 1); } },
        h("span.le-ama", "A"), h("span.le-amm", "M"));
      // the joystick bottom left on the picture – the picture gets the full height, no button bar below it
      const [joy, hint] = joystick();
      ui.joy = joy;
      wrap.classList.add("le-joywrap");
      ui.shift = shifter();
      ui.shift.el.hidden = !(tm && tm.car && tm.car.man);
      wrap.append(joy, hint, h("div.le-gearzone", ui.hud.gears, ui.shift.el));
      joy.classList.toggle("le-jgas", thrLocal > 0); joy.classList.toggle("le-jbrake", thrLocal < 0);
      show(head, top, ui.board, h("div.le-role", "🏎️ ", T("You drive!"), ui.hud.cast, ui.hud.assist, teamTag), gauges, times(), wrap);
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
        ui.crowd, wrap, h("div.le-watchrow", ui.watchHand, ui.watch), h("div.le-parts", ...ui.parts.map(x => x[0])), lapBoard(tm), change, next, low);
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
      show(head, top, ui.board, times(), wrap, h("p.center.muted.small", T("You are watching the leader.")));
    }
    drawBoard();
  }
  // the lap-time board after a stint: the team's last laps (who drove, the time, off the track, rain), the team's best
  // and the fastest lap of the race
  function lapBoard(tm) {
    const laps = (tm.laptimes || []).slice(-3).reverse();
    if (!laps.length) return null;
    const best = Math.min(...(tm.laptimes || []).map(l => l.time).filter(x => x > 0));
    const fast = st.teams.filter(o => o.best_lap > 0).sort((a, b) => a.best_lap - b.best_lap)[0];
    return h("div.le-laptimes", h("div.le-lthead", h("b", "⏱ ", T("Lap times")),
      fast ? h("span.small", "🏆 ", I18N.tr(T("Fastest lap")), " #" + fast.num, " ", leLapTime(fast.best_lap)) : null),
      ...laps.map(l => h("div.le-lt" + (l.time === best ? ".le-ltbest" : ""), h("span.le-ltn", I18N.tr(T("Lap {0}")).replace("{0}", l.n)),
        C(pName(l.driver), "span.grow"), l.rain ? h("span", { title: I18N.tr(T("Rain")) }, "🌧️") : null,
        l.offs ? h("span.le-ltoff", { title: I18N.tr(T("Off the track!")) }, "🟫" + (l.offs > 1 ? "×" + l.offs : "")) : null,
        h("b", leLapTime(l.time)), l.time === best ? h("span", "⭐") : null)));
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
    const assist = st.joined ? h("button.btn.small" + (st.assist ? "" : ".ghost") + ".le-assist-lobby", { type: "button", "aria-pressed": String(!!st.assist),
      onclick: () => act("look", { assist: !st.assist }) }, "🧒 ", I18N.tr(T("Driving assist")), ": ", I18N.tr(st.assist ? T("on") : T("off"))) : null;
    return [h("section.card.center", st.joined ? h("h2", T("Waiting for the start …")) : h("p", T("Play along on this device?")), story, roles,
      assist, st.joined ? h("p.small.muted", T("The assist brakes before the corners and helps to steer – good for younger drivers.")) : null,
      st.joined ? null : h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join")), inviteBtn(invite())),
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
        h("span.small", leLapsTxt(t.laps), h("br"), t.best_lap ? "⏱ " + leLapTime(t.best_lap) + " " : "", t.best_pit ? "🅿️ " + t.best_pit.toFixed(1) + " s" : ""),
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
