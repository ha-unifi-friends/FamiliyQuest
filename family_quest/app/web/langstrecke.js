// «24h Endurance» (24-Stunden-Rennen) – a short, fast live team race on the fictional «Circuit des Tannes»
// (familyquest/langstrecke.py). Teams are racing stables with one car each. One short lap, then the car drives into
// the pits by itself and the next person of the team drives. The driver steers freely across the track with the virtual
// joystick bottom left on the picture (up gas, down brake – or the arrow keys), drifts with the handbrake and gives full
// gas (it heats the engine and drains the battery much faster – empty: the emergency drive mode). There are only
// drivers: at every stop the next person of the team does the stop on their phone (the battery first, then the 4 tyres,
// after an overheat the engine – a stopwatch for the whole team) and drives on; the one who came in watches. Sudden rain
// showers (slicks or rain tyres – chosen at the stop), day and night, cheering stands at the pits.
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
  STOP_BAT: 4, STOP_TYRE: 1, STOP_MAX: 10, STOP_ENG: 7, ENG_EXTRA: 3,
  WET_SLICK: 0.8, DRY_RAIN: 0.9, RAIN_C: 0.85,
  HW: 5.5, KERB: 1.5, XMAX: 11, STEER_V: 7, VSTEER: 10, WHEEL: 6, PUSH: 0.75, VGRASS: 9, GRASS_DEC: 16, KERB_F: 0.9,
  SLIP_D: 30, SLIP_W: 2.2, SLIP_V: 3.5, BUMP_D: 4.5, CAR_W: 1.9, NUDGE: 1.5, PIT_Z: 25,
  LINE_D: 40, LINE_OUT: 3.5, LINE_APEX: 3.5, LMAX: 4, ASSIST_K: 0.5, AK_ASSIST: 0.92,
  LUG: 0.35, EBRAKE: 7, LIM_HEAT: 1.5, NEUTRAL_DEC: 3, VREV_ON: 0.75, VREV: 2.5, VCREEP: 1, REV_ACC: 3, GRIND_DEC: 22, GRIND_HEAT: 30, AUTO_UP: 0.9, AUTO_DOWN: 0.75, AUTO_GAP: 0.2,
  // the pit lane on the right of the main straight (its metres = the lap's metres beside it; pl 0 racing, 1 entry up to
  // the line, 2 to the box, 3 out to the pit exit and back onto the track) – as in langstrecke.py
  PIT_IN: 580, PIT_ENTRY: 30, PIT_OUT: 60, PIT_MERGE: 15, PL_X: 9.5, PL_HW: 2, SIDE_X: 3.5, PIT_V: 100 / 7, KEEP_R: 1.5, KEEP_ST: 20,
  AP_LATE: 12, AP_K: 0.7, FUNNEL: 0.45, BOX0: 10, BOX_GAP: 6, BOX_DEC: 6,
  // the handbrake and the drift – as in langstrecke.py
  HB_LONG: 0.6, HB_DEC_SOFT: 6, HB_DEC: 15, DRIFT_PRE: 12, DRIFT_PRE_RAIN: 18, DRIFT_LATE: 0.35, DRIFT_VMIN: 0.85, DRIFT_VMIN_RAIN: 0.75,
  DRIFT_SPIN: 1.35, DRIFT_K: 1.06, DRIFT_K_RAIN: 1.03, DRIFT_ST: 25, DRIFT_ST_RAIN: 60, DRIFT_GRACE: 0.3, DRIFT_DEC: 9, DRIFT_LOSS: 3,
  DRIFT_HEAT: 1, DRIFT_YAW: 28, YAW_RATE: 140, SPIN_RATE: 540, SPIN_X: 6, SPIN_T: 2 };
LE.PZ_IN = LE.PIT_IN - LE.L;
// the gearbox (manual): the limiter, the low end (below: the gear lugs) and the pull of gears 1–6 – as in langstrecke.py
const LE_GEAR_TOP = [9, 13.5, 18, 22.5, 27, 30], LE_GEAR_LOW = [0, 5, 8.5, 12.5, 16.5, 21], LE_GEAR_ACC = [1.15, 1.1, 1.05, 1, 0.95, 0.9];
// the gear the automatic gearbox would be in at speed v
const leAutoGear = v => { for (let i = 0; i < LE_GEAR_TOP.length; i++) if (v < LE_GEAR_TOP[i] * LE.AUTO_UP) return i + 1; return LE_GEAR_TOP.length; };
// the corners: start, end (metres in the lap), angle (degrees, + = right), safe speed (m/s, dry, the right tyres)
const LE_CORNERS = [[90, 130, 90, 20], [210, 240, -45, 25], [300, 350, 150, 13], [420, 450, 75, 21], [500, 550, 90, 17]];
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
// the racing line as shown on the road at absolute d: the line the assist and the bots follow (leLine) – at the lap's
// end it bends over to the right into the pit lane and follows the lane to the exit (every lap ends in the pits)
function leLineShown(d) {
  const xl = leLapPos(d), pz = xl >= LE.PIT_IN - 30 ? xl - LE.L : xl;
  if (pz < LE.PZ_IN - 30 || pz > LE.PIT_OUT + LE.PIT_MERGE + 40) return leLine(xl);
  if (pz < LE.PZ_IN) return leLine(xl) + (LE.SIDE_X - leLine(xl)) * leEase((pz - LE.PZ_IN + 30) / 30);
  if (pz <= LE.PIT_OUT + LE.PIT_MERGE) return lePitX(pz);
  return LE.SIDE_X + (leLine(xl) - LE.SIDE_X) * leEase((pz - LE.PIT_OUT - LE.PIT_MERGE) / 40);
}
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
// how far the driver sees (metres; as view_dist() in langstrecke.py): 150 by day, 70 at night, 125 in the rain by day,
// 40 at night in the rain – the picture, the corner sign and the boards come that late (the bots slow down with it)
const leView = (dk, rain) => (rain ? 125 - 85 * dk : 150 - 80 * dk);
const leHour = (s, limit) => (16 + 24 * Math.max(0, s) / limit) % 24;     // the race starts at 16:00
function leDark(s, limit) {
  const hr = leHour(s, limit);
  if (hr >= 21.5 || hr < 5.5) return 1;
  if (hr >= 20.5 && hr < 21.5) return hr - 20.5;
  if (hr >= 5.5 && hr < 6.5) return 6.5 - hr;
  return 0;
}
// one input of the driver: "s" steering −100 … 100, "u" 1 gas / 0 lifted / −1 brake, "a" the assist on / off,
// "m" manual gears on / off (on: the gear that fits the speed), "g" the gear −1 R / 0 N / 1–6 (anything else: ignored),
// "h" the handbrake held 1 / released 0
function leApply(car, c, v) {
  if (c === "s") car.st = Math.max(-100, Math.min(100, Math.trunc(v)));
  else if (c === "u") car.thr = Math.trunc(v) > 0 ? 1 : Math.trunc(v) < 0 ? -1 : 0;
  else if (c === "a") { car.ast = Math.trunc(v) ? 1 : 0; car.ak = LE.AK_ASSIST; }
  else if (c === "m") { car.man = Math.trunc(v) ? 1 : 0; car.gear = leAutoGear(car.v); }
  else if (c === "g" && Math.trunc(v) >= -1 && Math.trunc(v) <= LE_GEAR_TOP.length) car.gear = Math.trunc(v);
  else if (c === "h") car.hb = Math.trunc(v) ? 1 : 0;
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
// the shift paddles: up N → 1 → … → 6 (6 stays), down 6 → … → 1 → N (N stays) – never into R (from R: up to N)
const lePaddle = (g, dir) => { g = Math.trunc(+g || 0); if (g < 0) return dir > 0 ? 0 : -1; return Math.max(0, Math.min(LE_GEAR_TOP.length, g + (dir > 0 ? 1 : -1))); };
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
  if (pl === 1 && !car.ap && pz >= LE.PZ_IN + LE.PIT_ENTRY - LE.AP_LATE && x0 < LE.SIDE_X) { car.ap = 1; ev.push("autopilot"); }
  const ap = pl > 0 && car.ap === 1, cn = leCornerAt(xl);
  let th = ap ? 0 : car.thr, stc = ap ? 0 : car.st / 100;   // the autopilot: lifted off – the limiter brings it to the pit speed
  const emg = car.bat <= 0;                          // the battery is empty: the emergency drive mode
  const bite = Math.min(1, 0.2 + Math.abs(v0) / LE.VSTEER);   // how much the steering bites at this speed
  // the handbrake and the drift (not in the pit lane, not by the autopilot) – as in langstrecke.py
  const hb = car.hb && !pl && !ap ? 1 : 0, hbt0 = car.hbt || 0;
  car.hbt = hb ? hbt0 + DT : 0;
  let dr = car.dr || 0, lose = false, spinx = 0;
  if (hb && hbt0 === 0 && dr === 0 && car.sf !== 2 && v0 > 0) {       // the tap: a drift, a spin – or just a small brake
    const [nc, dz] = leNextCorner(xl);
    if (nc !== null) {
      const sv = leSafe(nc, car.tyre, rain), u = cn !== null ? (xl - nc[0]) / (nc[1] - nc[0]) : -1;
      if (v0 >= sv * (rain ? LE.DRIFT_VMIN_RAIN : LE.DRIFT_VMIN)) {
        const entry = (cn === null && dz <= (rain ? LE.DRIFT_PRE_RAIN : LE.DRIFT_PRE)) || (cn !== null && u <= LE.DRIFT_LATE);
        const late = cn !== null && u > LE.DRIFT_LATE;
        if (late || (entry && v0 >= sv * LE.DRIFT_SPIN)) { dr = 2; ev.push("spin"); }
        else if (entry) { dr = 1; ev.push("drift"); }
        if (dr) { car.dc = LE_CORNERS.indexOf(nc); car.drt = 0; }
      }
    }
  }
  const dc = dr ? LE_CORNERS[car.dc || 0] : [0, 0, 0, 0], ddir = dc[2] > 0 ? 1 : -1, dsafe = leSafe(dc, car.tyre, rain) * (rain ? LE.DRIFT_K_RAIN : LE.DRIFT_K);
  if (dr === 1) {                                    // the drift: gas and steering into the corner hold it
    car.drt = (car.drt || 0) + DT;
    if (hbt0 + DT > LE.HB_LONG || car.sf === 2 || pl) dr = 0;
    else if (cn === null && xl >= dc[1]) dr = 0;
    else if (car.drt > LE.DRIFT_GRACE + 1e-9 && !(car.thr > 0 && car.st * ddir >= (rain ? LE.DRIFT_ST_RAIN : LE.DRIFT_ST))) { dr = 0; lose = true; }
  } else if (dr === 2) {                             // the spin: wide off the track, then the grass slows it down
    car.drt = (car.drt || 0) + DT;
    if (car.sf === 2 || v0 <= LE.VGRASS || car.drt > LE.SPIN_T) dr = 0;
    else spinx = -ddir * LE.SPIN_X;
  }
  car.dr = dr;
  let push = 0;                                      // a corner pushes outward, ∝ speed² (drifting: against the drift speed)
  if (cn !== null) { const q = v0 / (dr === 1 ? dsafe : leSafe(cn, car.tyre, rain)); push = (cn[2] > 0 ? -1 : 1) * LE.STEER_V * LE.PUSH * q * q; }
  if (ap) stc = leClamp((lePitX(pz) - x0) * LE.AP_K, -1, 1);   // the autopilot steers smoothly along the pit lane
  else if (car.ast && dr === 0) {                    // the assist (never while drifting): towards the racing line (the pit lane), brake before a corner
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
  if (dr === 1) { vt = Math.min(vt, dsafe); dec = Math.max(dec, LE.DRIFT_DEC); }   // drifting: the car settles at the drift speed
  else if (dr === 2) { vt = Math.min(vt, LE.VGRASS); dec = Math.max(dec, LE.GRASS_DEC); }
  else if (hb) { vt = Math.min(vt, LE.VBRAKE); dec = Math.max(dec, car.hbt > LE.HB_LONG + 1e-9 ? LE.HB_DEC : LE.HB_DEC_SOFT); }   // a tap brakes a little, held too long hard
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
  if (lose) v = Math.max(0, v - LE.DRIFT_LOSS);
  car.bc = Math.max(0, car.bc - DT);
  if (bump !== null && v > bump) {
    v = Math.max(0, bump);
    if (car.bc <= 0) { car.bc = 1; car.bumps += 1; ev.push("bump"); }
  } else nudge = 0;
  const [lo, hi] = pl ? lePitBounds(pz) : [-LE.XMAX, LE.XMAX];   // in the pit lane: its white line, the pit wall, the boxes
  let x = leClamp(x0 + (car.sw * LE.STEER_V * bite + push + nudge + spinx) * DT, lo, hi);   // across the track
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
  if (dr === 1) car.temp = Math.min(LE.RED, car.temp + LE.DRIFT_HEAT * DT);   // drifting heats the engine a little more
  if ((full || lim || grind) && car.temp >= LE.RED - 1e-9) { car.eng = 1; car.blows += 1; car.temp = 80; ev.push("blow"); }
  let yaw = car.yaw || 0;                            // the drift angle (the picture)
  if (dr === 1) yaw += leClamp(ddir * LE.DRIFT_YAW - yaw, -LE.YAW_RATE * DT, LE.YAW_RATE * DT);
  else if (dr === 2) { yaw += ddir * LE.SPIN_RATE * DT; if (yaw > 180) yaw -= 360; else if (yaw < -180) yaw += 360; }
  else yaw += leClamp(-yaw, -2 * LE.YAW_RATE * DT, 2 * LE.YAW_RATE * DT);
  car.yaw = yaw;
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
    car.pit = 1; car.sw = 0; car.sf = 0; car.tow = 0; car.ap = 0; car.dr = 0; car.yaw = 0; car.hbt = 0;
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
  const pts = [], nrm = [];
  let x = 0, y = 0, hd = 0;
  for (let d = 0; d <= LE.L; d += 4) {
    pts.push([x, y]); nrm.push([-Math.sin(hd), Math.cos(hd)]);   // the right-hand side (the pit lane's side)
    const c = leCornerAt(d + 2);
    if (c) hd += c[2] * Math.PI / 180 / (c[1] - c[0]) * 4;
    x += Math.cos(hd) * 4; y += Math.sin(hd) * 4;
  }
  const n = pts.length - 1, ex = pts[n][0] - pts[0][0], ey = pts[n][1] - pts[0][1];
  pts.forEach((p, i) => { p[0] -= ex * i / n; p[1] -= ey * i / n; });
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const x0 = Math.min(...xs), y0 = Math.min(...ys), w = Math.max(...xs) - x0, h = Math.max(...ys) - y0, s = Math.max(w, h);
  _leMap = { pts: pts.map(([a, b]) => [(a - x0) / s, (b - y0) / s]), nrm, w: w / s, h: h / s, m: s };
  return _leMap;
}
// a point of the minimap at d, `off` metres to the right of the track (the pit lane: drawn 1.8× wider to be seen)
const leMapAt = (d, off = 0) => { const m = leTrackMap(), u = leLapPos(d) / 4, i = Math.floor(u), f = u - i, a = m.pts[i], b = m.pts[Math.min(m.pts.length - 1, i + 1)], nr = m.nrm[i], k = off * 1.8 / m.m;
  return [a[0] + (b[0] - a[0]) * f + nr[0] * k, a[1] + (b[1] - a[1]) * f + nr[1] * k]; };
// where the pit lane is at absolute d (for the pictures): metres from the line of its stop, or null off the pit lane
const lePitAt = d => { const xl = leLapPos(d), pz = xl >= LE.PIT_IN - 10 ? xl - LE.L : xl; return pz >= LE.PZ_IN - 10 && pz <= LE.PIT_OUT + LE.PIT_MERGE + 12 ? pz : null; };
// a car's offset across the minimap / its pit-lane state for the pictures
const lePitHint = car => {
  if (!car || car.pit) return null;
  const xl = leLapPos(car.d), pl = car.pl || 0, pz = pl ? lePitZ(car.d, pl) : 0;
  if (pl && car.ap) return "ap";
  if (pl === 1 || (pl === 2)) return "lim";
  if (pl === 3) return pz < LE.PIT_OUT ? "lim" : "exit";
  return car.d >= 0 && xl >= LE.PIT_IN - 110 && xl < LE.PIT_IN ? "keep" : null;
};
// the curvature of the track at d (radians per metre, + = right) – the pseudo-3D picture bends with it
const leCurve = d => { const c = leCornerAt(leLapPos(d)); return c ? c[2] * Math.PI / 180 / (c[1] - c[0]) : 0; };
const leKmh = v => Math.round(v * 7);
const leLapTime = s => (s > 0 ? Math.floor(s / 60) + ":" + (s % 60).toFixed(1).padStart(4, "0") : "–:––.–");

// The server's clock on this device: offset = server time − performance.now() (in s). The sample with the shortest
// round trip is the most exact one – but a phone that slept (in the lobby, before the start) comes back with a
// performance.now() that stood still (iOS, Android), and later samples are slower (the canvas is busy) than the best
// one from the lobby. So a sample that PROVES the offset wrong – the server's time lies between sending (t1) and
// receiving (t2), the offset between now − t2 and now − t1 – replaces it at once. Else the app stays that far behind:
// the intro with the start lights for the whole race, the driver's inputs too old.
function leClockSample(ck, now, t1, t2) {
  const rtt = Math.max(0, t2 - t1), mid = now - (t1 + t2) / 2;
  if (ck.offset == null || ck.offset < now - t2 - 0.05 || ck.offset > now - t1 + 0.05) return { offset: mid, rtt };
  if (rtt <= ck.rtt * 1.15) return { offset: mid, rtt: Math.min(ck.rtt, rtt) };
  return { offset: ck.offset, rtt: ck.rtt * 1.01 };                // the best round trip ages: a slower network later counts again
}
// Which screen this player sees – decided in ONE place, from the server's roles and the race clock (t = game time,
// < 0 during the 6 s start countdown): lobby | done | watch | drive | rest (a break: the team's car on TV) | stop (I do
// the team's stop – I drive next) | pit (I watch the stop live). `intro`: the start lights are on the stage – for
// everybody at the start, never during a pit stop.
function leScreen(st, myId, t) {
  if (!st) return { mode: "none", intro: false };
  if (st.phase === "lobby" || st.phase === "done") return { mode: st.phase, intro: false };
  const tm = st.teams && st.my_team != null ? st.teams[st.my_team] : null;
  const intro = st.phase === "play" && st.status !== "done" && t < 0;
  if (!st.joined || !tm) return { mode: "watch", intro };
  if (tm.car && tm.car.pit && tm.stop) return { mode: tm.stop.jobs && tm.stop.next === String(myId) ? "stop" : "pit", intro: false };
  return { mode: tm.driver === String(myId) ? "drive" : "rest", intro };
}
// The driver's controls (joystick, shifter, paddles, A / M, handbrake) only when they can be used: driving, after the
// green light, before the finish, not standing in the box – never on the start grid, in the lobby, at a stop or for
// the others of the team on a break / spectators (they fade in at the green light and at the pit exit)
const leControls = (mode, intro, car, t, limit) => mode === "drive" && !intro && t >= 0 && t < limit && !!car && !car.pit;
// The driver's position card (top left on the picture): my place, the leader (not when I lead), the car ahead and the
// car behind (not when there is none) with the gap in seconds – or in laps for a lapped car. `dOf(team)`: its distance.
function leRaceCard(st, mine, dOf) {
  const k = st.standings.indexOf(mine), n = st.standings.length, at = j => st.teams[st.standings[j]], dm = dOf(st.teams[mine]);
  const gap = dd => (dd >= LE.L ? { laps: Math.floor(dd / LE.L) } : { s: Math.round(dd / 21 * 10) / 10 });
  const car = (o, dd) => ({ num: o.num, name: o.name, color: o.color, ...gap(Math.max(0, dd)) });
  return { pos: k + 1, n,
    leader: k > 1 ? car(at(0), dOf(at(0)) - dm) : null,
    ahead: k > 0 ? car(at(k - 1), dOf(at(k - 1)) - dm) : null,
    behind: k >= 0 && k < n - 1 ? car(at(k + 1), dm - dOf(at(k + 1))) : null };
}
// the team's stop at game time t from the server's jobs (the taps of the next driver – every job from its own tap, all
// at the same time): per job its state – "tap" | "run" (being fitted, p 0 … 1) | "ok" – for the battery (the server
// keeps its tap time), the 4 tyres and the engine after an overheat (their done times), and the stopwatch (el: seconds
// so far, cap: the most it takes)
function leStopJobs(stp, t) {
  const j = (stp && stp.jobs) || {};
  const one = (d, len) => (d == null ? { s: "tap", p: 0 } : t >= d ? { s: "ok", p: 1 } : { s: "run", p: leClamp((t - d + len) / len, 0, 1) });
  const bat = one(j.bat != null ? j.bat + LE.STOP_BAT : null, LE.STOP_BAT);
  const tyres = [0, 1, 2, 3].map(k => one((j.tyres || [])[k], LE.STOP_TYRE)), eng = stp && stp.eng ? one(j.eng, LE.STOP_ENG) : null;
  const over = !!stp && t >= stp.end;
  return { bat, tyres, eng,
    done: bat.s === "ok" && tyres.every(x => x.s === "ok") && (!eng || eng.s === "ok"), over,
    el: stp ? Math.max(0, Math.min(t, stp.end) - stp.t) : 0, cap: stp ? (stp.cap ?? stp.time) : 0 };
}

// ---------------------------------------------------------------- the rules, the start
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
    T("At the end of the lap the pit lane branches off to the right: keep right and steer in – or the autopilot takes the car in. The limiter holds 100 km/h in the pit lane, the car stops at its box."),
    T("Driver: the joystick bottom left on the picture – up gas, down brake, sideways steering (or the arrow keys). In the red the engine overheats – it has to be swapped at the stop."),
    T("Gears: «A / M» on the picture switches at any time – automatic, or manual with the H shifter bottom right (R | 1 2 | 3 4 | 5 6, keys 1–6, R, N). Every gear has its speed band – shift up when the light turns red, a gear too high pulls weakly. Shifted well, manual is a little faster. R only when stopped: at speed it grinds the gearbox and overheats the engine."),
    T("Five corners per lap: the sign shows the direction and the suggested speed, the boards 150 / 100 / 50 m. Brake before the corner and steer through it – too fast and the car runs wide onto the kerb and the grass."),
    T("Racing line: come in from the outside, touch the inside in the middle of the corner, let the car run out again."),
    T("Close behind another car on a straight you get the slipstream – more speed to overtake. Running into a car only slows you down."),
    T("Handbrake («HB» on the picture, or Space): tap it at the entry of a corner at speed to drift – full gas and steering into the corner hold it and the car comes through a little faster. Lifting ends it, too late it spins, held too long it brakes hard."),
    T("Driving assist (🧒, on for juniors): the car brakes before the corners and helps to steer. Everybody can switch it for themselves (☰ menu)."),
    T("Electric car: full throttle drains the battery much faster than cruising. Empty – emergency drive mode: the car crawls to the pits."),
    T("Only drivers: at every stop the next person of the team takes over – alone, you again. The one who came in has a break and watches."),
    T("The pit stop is done by the one who drives next, on their phone: tap everything at once – the battery takes 4 s (always a full one), each tyre 1 s, all at the same time. About 4 s done well – after 10 s it is done anyway. After an overheat also the engine (7 s – then 13 s at most)."),
    r.weather ?? 1 ? T("Sudden rain showers: pick slicks or rain tyres at the stop – watch the forecast. The wrong tyres are slower.") : null,
    T("In the rain every corner needs less speed – even less with slicks. At night the headlights only reach a short way. The race starts at 16:00 and runs through the night."),
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
    h("p.small.muted", T("Short laps and a pit stop after every lap: the next driver of the team does the stop – battery, tyres – and drives on.")),
    h("div.grid2", h("label.field", T("Race length"), minutes), h("label.field", T("Weather"), weather)),
    h("label.field", T("Difficulty"), diff),
    solo ? null : h("div.grid2", h("label.field", T("Teams of people"), teams), h("label.field", T("People per team"), size)),
    h("div.grid2", h("label.field", T("Bot teams"), bots), h("label.field", T("Bots play"), level)),
    solo ? h("p.small.muted", T("Alone: you drive and do every pit stop yourself.")) : h("p.small.muted", T("Everybody joins on their own device and picks a team – guests via QR code.")),
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
  if (o.yaw) {                                                       // drifting: turned a little, its flank in view
    const sn = Math.sin(o.yaw * Math.PI / 180), side = w * 0.34 * Math.abs(sn), dir = sn > 0 ? -1 : 1;
    ctx.translate(x, y); ctx.rotate(leClamp(o.yaw, -40, 40) * Math.PI / 180 * 0.18); ctx.translate(-x, -y);
    if (side > 1) {
      const ex = x + dir * w * 0.42;
      ctx.fillStyle = col; ctx.globalAlpha = (o.alpha ?? 1) * 0.9;
      ctx.beginPath(); ctx.moveTo(ex, y - hgt * 0.15); ctx.lineTo(ex + dir * side, y - hgt * 0.22); ctx.lineTo(ex + dir * side * 0.85, y - hgt * 0.66); ctx.lineTo(x + dir * w * 0.36, y - hgt * 0.72); ctx.closePath(); ctx.fill();
      ctx.fillStyle = "rgba(0,0,0,.28)"; ctx.fill();
      ctx.fillStyle = "#15171c"; ctx.fillRect(ex + dir * side * 0.55 - w * 0.07, y - hgt * 0.5, w * 0.14, hgt * 0.5);   // a front wheel
      ctx.globalAlpha = o.alpha ?? 1;
    }
  }
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
// trackside advertising (own, invented): «Family Quest» and «Snowman Tyres»
// with a snowman made of three tyres – a board of w × hh with its top left corner at x, y
function leBanner(ctx, kind, x, y, w, hh) {
  ctx.save();
  ctx.fillStyle = ["#5b5bd6", "#0b7285"][kind]; ctx.fillRect(x, y, w, hh);
  ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.lineWidth = Math.max(1, hh * 0.06); ctx.strokeRect(x, y, w, hh);
  const cy = y + hh / 2, s = hh * 0.7;
  ctx.textBaseline = "middle"; ctx.textAlign = "left";
  ctx.font = "900 " + Math.max(6, Math.round(hh * 0.42)) + "px system-ui, sans-serif";
  if (kind === 0) {
    ctx.fillStyle = "#ffd43b"; ctx.beginPath();                        // a star
    for (let k = 0; k < 10; k++) { const r = k % 2 ? s * 0.22 : s * 0.5, a = -Math.PI / 2 + k * Math.PI / 5; ctx.lineTo(x + hh * 0.55 + Math.cos(a) * r, cy + Math.sin(a) * r); }
    ctx.fill(); ctx.fillStyle = "#fff"; ctx.fillText("Family Quest", x + hh * 1.1, cy);
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
    const f = leReduced() ? 1 : 0.8 + 0.2 * Math.sin(t * 13 + k);
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

// the race picture's notice: a small one-line pill (about 12.5 px) at the very top – between the corner sign and the
// minimap (top.l … top.r at top.y0 – the driver: just under the speedometer, squeezed into the room with top.fit), or
// centred just under them (top.b) when it does not fit there
function leNotice(ctx, cw, top, txt, col, alpha) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.font = "700 12.5px system-ui, 'Apple Color Emoji', 'Noto Color Emoji', sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  const room = top.r - top.l, w = Math.min(cw - 16, ctx.measureText(txt).width + 18, top.fit ? Math.max(60, room) : 1e9), hh = 22;
  const x = w <= room ? top.l + (room - w) / 2 : (cw - w) / 2, y = w <= room ? top.y0 ?? 8 : Math.max(top.b, (top.y0 ?? 8));
  ctx.fillStyle = "rgba(15,23,42,.58)";
  ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, hh, hh / 2) : ctx.rect(x, y, w, hh); ctx.fill();
  ctx.fillStyle = col || "#fff"; ctx.fillText(txt, x + w / 2, y + hh / 2 + 0.5, w - 12);
  ctx.restore();
}
function langstreckeLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", busy = false, raf = 0, syncing = false, lastSync = 0, cheered = false;
  let ck = { offset: null, rtt: 1e9 };                          // the server's clock (leClockSample)
  let pend = [], inflight = [], thrLocal = 0;
  const fired = new Set();
  let ui = {}, introSkip = false, introSound = 0, finalCue = false, lastTempWarn = 0, wasDriver = false, stopSeen = null;
  const local = { pend: new Set() };                            // my taps at a stop on their way to the server
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
  const brakeSeen = {};                                       // the other cars' brake lights: from their deceleration between snapshots
  function setState(s) {
    if (s && !Array.isArray(s.players)) s = null;
    if (s && s.phase === "play" && Array.isArray(s.teams)) {
      const now = nowS();
      for (const o of s.teams) {
        const b = brakeSeen[o.i], dv = b && now - b.at > 0.05 ? (b.v - o.v) / (now - b.at) : 0;
        if (dv > 3 && !o.pit) brakeSeen[o.i] = { v: o.v, at: now, until: now + 0.45 };            // slowing down hard: braking
        else brakeSeen[o.i] = { v: o.v, at: now, until: b ? b.until : 0 };
      }
    }
    st = s;
    if (!st || st.phase !== "play") return;
    const t = myTeam();
    if (!t) return;
    const drv = t.driver === myId;
    if (drv && !wasDriver) { thrLocal = 0; held.gas = held.brake = held.jgas = held.jbrake = false; held.hb = 0; pend = []; inflight = []; steer.sent = 0; ui.xs = null; ui.skids = []; }      // my turn: the pedals start released
    if (!drv) { pend = []; inflight = []; }
    wasDriver = drv;
    if (t.stop && stopSeen !== t.stop.t) {                                     // the car is in: the stopwatch starts
      stopSeen = t.stop.t;
      local.pend.clear(); ui.cheered = false;
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
  const held = { gas: false, brake: false, jgas: false, jbrake: false, hb: 0 };
  const pedals = () => {
    const v = held.brake || held.jbrake ? -1 : held.gas || held.jgas ? 1 : 0;
    if (v !== thrLocal) input("u", v);
    if (ui.joy) { ui.joy.classList.toggle("le-jgas", v > 0); ui.joy.classList.toggle("le-jbrake", v < 0); }
  };
  const pedal = on => { held.gas = !!on; pedals(); };
  // the handbrake (the «HB» button, Space): held 1 / released 0 – a short tap at a corner's entry starts a drift
  const hbSet = on => { on = on ? 1 : 0; if (held.hb === on) return; held.hb = on; input("h", on); if (ui.hb) ui.hb.classList.toggle("le-hbon", !!on); if (on && !leReduced()) leBuzz(15); };
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
  const GAS = ["ArrowUp", "KeyW"], BRAKE = ["ArrowDown", "KeyS"];       // Space: the handbrake
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
  function paddleShift(dir) {
    const c = predicted();
    if (!c || !c.man) return;
    const g = lePaddle(c.gear ?? 1, dir);
    if (g !== (c.gear ?? 1)) shiftTo(g);
  }
  function onKey(e) {
    if (!alive || !box.isConnected || !amDriver()) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || "") || document.querySelector(".game-menu-back")) return;   // (☰ open: its keys)
    if (KEYS[e.code]) { e.preventDefault(); if (!e.repeat) { steer[KEYS[e.code]] = true; steerNow(); } }
    else if (GAS.includes(e.code)) { e.preventDefault(); if (!e.repeat) pedal(1); }
    else if (BRAKE.includes(e.code)) { e.preventDefault(); if (!e.repeat) brake(1); }
    else if (e.code === "Space") { e.preventDefault(); if (!e.repeat) hbSet(1); }
    else if (e.code === "KeyE" || e.code === "KeyQ") { const c = predicted(); if (c && c.man) { e.preventDefault(); if (!e.repeat) paddleShift(e.code === "KeyE" ? 1 : -1); } }   // the paddles: E up, Q down
    else if (GEARKEYS[e.code] != null) { const c = predicted(); if (c && c.man) { e.preventDefault(); if (!e.repeat) shiftTo(GEARKEYS[e.code]); } }
  }
  function onKeyUp(e) {
    if (KEYS[e.code]) { steer[KEYS[e.code]] = false; if (amDriver()) { e.preventDefault(); steerNow(); } return; }
    if (!amDriver()) return;
    if (GAS.includes(e.code)) { e.preventDefault(); pedal(0); } else if (BRAKE.includes(e.code)) { e.preventDefault(); brake(0); }
    else if (e.code === "Space") { e.preventDefault(); hbSet(0); }
  }
  window.addEventListener("keydown", onKey);
  window.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", () => { steer.kl = steer.kr = false; held.gas = held.brake = false; if (amDriver()) { steerNow(); pedals(); hbSet(0); } });
  // the first-drive hint under the joystick: until the gas was given with it once (remembered on this device)
  const JOY_SEEN = "fq-le-joy";
  const LINE_KEY = () => "fq-le-line-" + myId;                     // the racing line on the road: on unless this driver switched it off
  const lineOn = () => { try { return localStorage.getItem(LINE_KEY()) !== "0"; } catch { return true; } };
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
    const sh = h("div.le-shift", { role: "application", "aria-label": I18N.tr(T("Gear shifter: R, 1–6, N – keys 1–6, R, N")), title: I18N.tr(T("R only when stopped")) }, big, svg);
    let pid = null, pos = leGatePos(1), shown = null, nX = 0;
    const place = (x, y) => {
      pos = [x, y];
      const bx = X(x), by = Y(y);
      shaft.setAttribute("x1", bx); shaft.setAttribute("y1", by + 10); shaft.setAttribute("x2", bx); shaft.setAttribute("y2", by);
      for (const c of [ball, shine]) { c.setAttribute("cx", c === shine ? bx - 3.5 : bx); c.setAttribute("cy", c === shine ? by - 4 : by); }
    };
    const label = g => { const txt = g < 0 ? "R" : g === 0 ? "N" : String(g); if (big.textContent !== txt) big.textContent = txt; sh.dataset.g = String(g);
      for (const l of labels) l.classList.toggle("on", +l.dataset.g === g); };
    const at = e => { const b = svg.getBoundingClientRect(); return leGate((e.clientX - b.left) / b.width * 120 / 42 - 60 / 42, ((e.clientY - b.top) / b.height * 104 - 52) / 30); };
    let live = 0;
    const move = e => { const r = at(e); place(r.x, r.y); if (r.gear !== live) { live = r.gear; label(live); shiftTo(live, true); } };
    sh.addEventListener("pointerdown", e => {
      e.preventDefault(); e.stopPropagation();
      if (pid != null) return;
      pid = e.pointerId; try { sh.setPointerCapture(pid); } catch {}
      const c = predicted(); live = c ? (c.gear ?? 1) : 1;
      sh.classList.add("le-son"); move(e);
    });
    sh.addEventListener("pointermove", e => { if (e.pointerId === pid) { e.preventDefault(); move(e); } });
    const up = e => {
      if (e.pointerId !== pid) return;
      pid = null; sh.classList.remove("le-son");
      if (live) { const [x, y] = leGatePos(live); place(x, y); } else { nX = pos[0]; place(pos[0], 0); }   // snaps into the gear / onto the rail
    };
    for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) sh.addEventListener(ev, up);
    sh.addEventListener("contextmenu", e => e.preventDefault());
    place(...pos); label(1);
    // the shift paddles beside it (F1 style, simple): ▲ + up, ▼ − down (N → 1 … 6; 1 → N) – never R (R: the shifter only)
    const paddle = (dir, txt, aria) => {
      const b = h("button.le-paddle.le-p" + (dir > 0 ? "up" : "down"), { type: "button", "aria-label": I18N.tr(aria) }, txt);
      b.addEventListener("pointerdown", e => { e.preventDefault(); e.stopPropagation(); paddleShift(dir); });
      b.addEventListener("contextmenu", e => e.preventDefault());
      return b;
    };
    const el = h("div.le-shiftrow", sh, h("div.le-paddles", paddle(1, "▲ +", T("Shift up")), paddle(-1, "▼ −", T("Shift down"))));
    return { el, set(g, lever) { shown = g; label(g); if (!lever && pid == null) { const p = g === 0 ? [nX, 0] : leGatePos(g); place(...p); } },
      sync(g) { if (pid == null && g !== shown) this.set(g); } };
  }

  // the handbrake: a round button bottom right above the gears – its own pointerId, so it works while the left thumb
  // holds the joystick; held while pressed (a short tap at a corner's entry: a drift)
  function handbrake() {
    const b = h("button.le-hb", { type: "button", "aria-label": I18N.tr(T("Handbrake: tap it at the corner entry to drift (Space)")),
      title: I18N.tr(T("Handbrake: tap it at the corner entry to drift (Space)")) }, h("b", "HB"), h("small", T("Drift")));
    let pid = null;
    b.addEventListener("pointerdown", e => { e.preventDefault(); e.stopPropagation(); if (pid != null) return; pid = e.pointerId; try { b.setPointerCapture(pid); } catch {} hbSet(1); });
    const up = e => { if (e.pointerId !== pid) return; pid = null; hbSet(0); };
    for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) b.addEventListener(ev, up);
    b.addEventListener("contextmenu", e => e.preventDefault());
    return b;
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
    const oth = st.teams.filter(o => o.i !== t.i && !o.pit && !o.pl).map(o => [o.d, o.x || 0, o.v]);   // never the pit lane
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
    else if (e === "pitlane") { LeAudio.tone([700, 900], "triangle", 0.1, 0.06, 0.08); }
    else if (e === "autopilot") { ui.apAt = nowS(); LeAudio.tone([520, 660, 780], "sine", 0.12, 0.07, 0.09); leBuzz([30, 40, 30]); }
    else if (e === "drift") { ui.driftAt = nowS(); LeAudio.tone([900, 760, 820], "sawtooth", 0.16, 0.035, 0.07); leBuzz(25); }
    else if (e === "spin") { LeAudio.tone([500, 300, 180], "sawtooth", 0.22, 0.07, 0.1); leBuzz([80, 40, 80]); ui.flash = nowS(); }
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
    ctx.strokeStyle = "rgba(255,212,59,.9)"; ctx.lineWidth = Math.max(1.5, size * 0.022);   // the pit lane beside the main straight
    ctx.beginPath();
    for (let pz = LE.PZ_IN; pz <= LE.PIT_OUT + LE.PIT_MERGE + 1e-9; pz += 3) { const [a, b] = leMapAt(LE.L + pz, lePitX(pz)); pz === LE.PZ_IN ? ctx.moveTo(ox + a * s, oy + b * s) : ctx.lineTo(ox + a * s, oy + b * s); }
    ctx.stroke();
    const [sx, sy] = m.pts[0];                                       // the start / finish line and the pits
    ctx.fillStyle = "#ffd43b"; ctx.fillRect(ox + sx * s - 2, oy + sy * s - 4, 4, 8);
    const dot = (d, col, mine, o) => {
      const off = o && o.pl ? (o.x ?? lePitX(lePitZ(d, o.pl))) : 0;
      const [a, b] = leMapAt(d, off), px = ox + a * s, py = oy + b * s, r = mine ? size * 0.06 : size * 0.045;
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(px, py, r, 0, 7); ctx.fill();
      ctx.strokeStyle = mine ? "#fff" : "rgba(0,0,0,.5)"; ctx.lineWidth = mine ? 2 : 1; ctx.stroke();
    };
    for (const o of st.teams) if (o.i !== me.i) dot(o.pit ? o.d : o.d + o.v * Math.max(0, Math.min(1.5, t - simT())), o.color, false, o);
    dot(me.d, me.color, true, me);
    ctx.restore();
  }
  function race(c, car, team, t, opts = {}) {
    const ctx = c.ctx, cw = c.w, ch = c.h, red = leReduced();
    const dk = leDark(t, limit()), rain = leInWin(st.rain, t);
    const VIEW = Math.round(leView(dk, rain)), CAMZ = 5, F = 6, STEP = 3, lights = [];
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
    const sky = [[[95, 160, 230], [190, 220, 245]], [[2, 3, 9], [7, 9, 20]]];      // night: nearly black
    const mix = (a, b) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * dk)).join(",")})`;
    g.addColorStop(0, rain ? (dk > 0.5 ? "#1c2230" : "#7d8796") : mix(sky[0][0], sky[1][0])); g.addColorStop(1, rain ? (dk > 0.5 ? "#2b3242" : "#aab3bf") : mix(sky[0][1], sky[1][1]));
    ctx.fillStyle = g; ctx.fillRect(0, 0, cw, yh + 1);
    if (dk > 0.3 && !rain) { const r = leRand(11); ctx.fillStyle = `rgba(255,255,235,${0.6 * dk})`; for (let k = 0; k < 22; k++) ctx.fillRect(r() * cw, r() * yh * 0.85, 1.4, 1.4); }
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
    // a vertical wall along the track (x = xm metres across) from z1 to z2, hm metres high
    const wall = (z1, z2, xm, hm, h0 = 0) => { ctx.beginPath(); ctx.moveTo(X(z1, xm), Y(z1) - h0 * unit * sc(z1)); ctx.lineTo(X(z2, xm), Y(z2) - h0 * unit * sc(z2));
      ctx.lineTo(X(z2, xm), Y(z2) - hm * unit * sc(z2)); ctx.lineTo(X(z1, xm), Y(z1) - hm * unit * sc(z1)); ctx.fill(); };
    // beside the pit lane (per lap lp): the «PIT» boards with the arrow before the entry, the speed-limit sign at the
    // entry line and its end at the exit, the boxes in the team colours with people standing at them
    function pitItems(lp) {
      const line = (lp + 1) * LE.L, kmh = leKmh(LE.PIT_V);
      for (const m of [90, 55, 20]) at(lp * LE.L + LE.PIT_IN - m - d, LE.HW + LE.KERB + 2.4, (x, y, u) => {
        const bw = u * 2.8, bh = u * 1.5; if (bw < 7) return;
        ctx.fillStyle = "#495057"; ctx.fillRect(x - u * 0.07, y - bh * 1.6, u * 0.14, bh * 1.6);
        ctx.fillStyle = "#1864ab"; ctx.fillRect(x - bw / 2, y - bh * 2.6, bw, bh); ctx.strokeStyle = "#fff"; ctx.lineWidth = Math.max(1, u * 0.08); ctx.strokeRect(x - bw / 2, y - bh * 2.6, bw, bh);
        ctx.fillStyle = "#fff"; ctx.font = "900 " + Math.max(6, Math.round(bh * 0.5)) + "px system-ui, sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
        ctx.fillText("PIT", x - bw * 0.42, y - bh * 2.1);
        const ax = x + bw * 0.12, ay = y - bh * 1.85, al = bw * 0.28;            // the arrow: straight on, then off to the right
        ctx.strokeStyle = "#ffd43b"; ctx.lineWidth = Math.max(2, u * 0.16); ctx.lineCap = "round"; ctx.lineJoin = "round";
        ctx.beginPath(); ctx.moveTo(ax, ay + bh * 0.2); ctx.lineTo(ax, ay - bh * 0.15); ctx.lineTo(ax + al, ay - bh * 0.45); ctx.stroke();
        ctx.fillStyle = "#ffd43b"; ctx.beginPath(); ctx.moveTo(ax + al + u * 0.25, ay - bh * 0.55); ctx.lineTo(ax + al - u * 0.2, ay - bh * 0.62); ctx.lineTo(ax + al - u * 0.02, ay - bh * 0.22); ctx.fill();
        if (bh > 14) { ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.font = "700 " + Math.round(bh * 0.28) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.fillText(m + " m", x, y - bh * 1.25); }
      });
      for (const [zl, end] of [[lp * LE.L + LE.PIT_IN, false], [line + LE.PIT_OUT, true]]) at(zl - d, LE.PL_X + LE.PL_HW + 0.9, (x, y, u) => {
        const r = u * 0.75; if (r < 3) return;
        ctx.fillStyle = "#495057"; ctx.fillRect(x - u * 0.06, y - u * 2.4, u * 0.12, u * 2.4);
        ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(x, y - u * 2.6, r, 0, 7); ctx.fill();
        ctx.strokeStyle = end ? "#868e96" : "#e03131"; ctx.lineWidth = r * 0.22; ctx.beginPath(); ctx.arc(x, y - u * 2.6, r * 0.88, 0, 7); ctx.stroke();
        ctx.fillStyle = "#111"; ctx.font = "900 " + Math.max(5, Math.round(r * 0.8)) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(String(kmh), x, y - u * 2.58);
        if (end) { ctx.strokeStyle = "rgba(73,80,87,.9)"; ctx.lineWidth = r * 0.16; ctx.beginPath(); ctx.moveTo(x - r * 0.6, y - u * 2.6 + r * 0.6); ctx.lineTo(x + r * 0.6, y - u * 2.6 - r * 0.6); ctx.stroke(); }
      });
      const xf = LE.PL_X + LE.PL_HW + 2.6;                             // the garages' fronts
      st.teams.forEach((o, i) => {
        const bx = o.box ?? leBoxOf(i), za = Math.max(0.8, line + bx - LE.BOX_GAP / 2 + 0.2 - d + CAMZ), zb = line + bx + LE.BOX_GAP / 2 - 0.2 - d + CAMZ;
        if (zb < 1 || za > VIEW) return;
        const zm = (za + zb) / 2, mine = o === team;
        items.push({ z: zm + 0.02, f: () => {
          ctx.fillStyle = o.color; ctx.globalAlpha = 0.35; quad(zb, za, LE.PL_X + LE.PL_HW, xf, LE.PL_X + LE.PL_HW, xf); ctx.globalAlpha = 1;   // the team's spot
          ctx.fillStyle = dk > 0.5 ? "#16181c" : "#343a40"; wall(za, zb, xf, 3.4);
          ctx.fillStyle = dk > 0.5 ? "#6b5a2a" : "#ffe8a1"; wall(za + 0.4, zb - 0.4, xf, 2.4, 0.05);   // the lit box
          ctx.fillStyle = o.color; wall(za, zb, xf, 3.4, 2.5);                                  // the awning in the team colour
          const u = unit * sc(zm);
          if (u > 3) { ctx.fillStyle = "#fff"; ctx.font = "900 " + Math.max(6, Math.round(u * 0.7)) + "px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
            ctx.fillText("#" + o.num, X(zm, xf), Y(zm) - u * 2.95); }
        } });
        // at its box: my team's people on a break (their avatars), elsewhere two mechanics in the team colour
        const crew = mine ? o.members.filter(m => m !== o.driver).map(person).filter(Boolean) : [null, null];
        const wave = mine && car.pl >= 2;
        (crew.length ? crew : [null]).slice(0, 4).forEach((p, k) => {
          const zz = line + bx - 1.6 + k * 1.1 - d;
          at(zz, LE.PL_X + LE.PL_HW + 0.7 + (k % 2) * 0.6, (x, y, u) => {
            if (u < 3) return;
            const hop = wave && !leReduced() ? Math.abs(Math.sin(t * 7 + k)) * u * 0.25 : 0, yy = y - hop;
            ctx.fillStyle = o.color; ctx.fillRect(x - u * 0.28, yy - u * 1.15, u * 0.56, u * 0.75);       // the overall
            ctx.fillStyle = "#212529"; ctx.fillRect(x - u * 0.24, yy - u * 0.42, u * 0.18, u * 0.42); ctx.fillRect(x + u * 0.06, yy - u * 0.42, u * 0.18, u * 0.42);
            ctx.strokeStyle = o.color; ctx.lineWidth = Math.max(1, u * 0.14); ctx.lineCap = "round";
            const arm = wave ? Math.sin(t * 9 + k) * u * 0.25 : 0;
            ctx.beginPath(); ctx.moveTo(x - u * 0.26, yy - u * 1.05); ctx.lineTo(x - u * 0.5, yy - (wave ? u * 1.6 : u * 0.6) + arm);
            ctx.moveTo(x + u * 0.26, yy - u * 1.05); ctx.lineTo(x + u * 0.5, yy - (wave ? u * 1.6 : u * 0.6) - arm); ctx.stroke();
            const img = p && avatarImg(p);
            if (img && img.complete && img.naturalWidth) ctx.drawImage(img, x - u * 0.55, yy - u * 2.15, u * 1.1, u * 1.1);
            else { ctx.fillStyle = "#f8d7b8"; ctx.beginPath(); ctx.arc(x, yy - u * 1.42, u * 0.28, 0, 7); ctx.fill(); ctx.fillStyle = o.color; ctx.fillRect(x - u * 0.3, yy - u * 1.72, u * 0.6, u * 0.16); }
          });
        });
      });
    }
    // the pit lane in one slice (pz: metres from the line of the stop): its asphalt, the white entry line, the pit wall,
    // the speed-limit lines across it, the boxes' apron, the white pit-exit line merging back onto the track
    const pitAsph = dk > 0.5 ? ["#303339", "#33363d"] : rain ? ["#555a63", "#595e67"] : ["#7a7e87", "#757982"];
    function pitSlice(z1, z2, pz, k, inLane) {
      const pz1 = pz + STEP, c1 = lePitX(pz1), c2 = lePitX(pz), lo1 = c1 - LE.PL_HW, lo2 = c2 - LE.PL_HW;
      if (pz >= -STEP && pz < LE.BOX0 + LE.BOX_GAP * 8) { ctx.fillStyle = dk > 0.5 ? "#2b2e33" : "#a5a9b0"; quad(z1, z2, LE.PL_X + LE.PL_HW, LE.PL_X + LE.PL_HW + 6, LE.PL_X + LE.PL_HW, LE.PL_X + LE.PL_HW + 6); }
      if (!inLane) {
        if (pz > LE.PIT_OUT + LE.PIT_MERGE && pz < LE.PIT_OUT + LE.PIT_MERGE + 12) { ctx.fillStyle = "#fff"; quad(z1, z2, LE.SIDE_X - LE.PL_HW - 0.12, LE.SIDE_X - LE.PL_HW + 0.12, LE.SIDE_X - LE.PL_HW - 0.12, LE.SIDE_X - LE.PL_HW + 0.12); }
        return;
      }
      ctx.fillStyle = pitAsph[k % 2 ? 1 : 0]; quad(z1, z2, lo1, c1 + LE.PL_HW, lo2, c2 + LE.PL_HW);
      ctx.fillStyle = "rgba(255,255,255,.85)"; quad(z1, z2, c1 + LE.PL_HW - 0.15, c1 + LE.PL_HW, c2 + LE.PL_HW - 0.15, c2 + LE.PL_HW);
      if (pz < LE.PZ_IN + LE.PIT_ENTRY || pz >= LE.PIT_OUT) {          // the solid white entry / exit line on the lane's inner edge
        ctx.fillStyle = "#fff"; quad(z1, z2, lo1 - 0.12, lo1 + 0.18, lo2 - 0.12, lo2 + 0.18);
        if (pz < LE.PZ_IN + LE.PIT_ENTRY && k % 2) { ctx.fillStyle = "rgba(255,255,255,.55)"; quad(z1, z2, LE.HW, lo1 - 0.12, LE.HW, lo2 - 0.12); }   // the hatched gore
      } else {                                                         // the pit wall between the track and the lane
        ctx.fillStyle = dk > 0.5 ? "#5c6068" : "#ced4da"; wall(z1, z2, lo1 - 0.05, 0.9);
        ctx.fillStyle = k % 2 ? "#e03131" : "#f8f9fa"; wall(z1, z2, lo1 - 0.05, 0.25);
      }
      for (const zl of [LE.PZ_IN, LE.PIT_OUT]) if (pz <= zl && zl < pz1) { ctx.fillStyle = "#fff"; quad(z1, z2, lo1, c1 + LE.PL_HW, lo2, c2 + LE.PL_HW); }   // the limit starts / ends
    }
    for (let i = n - 1; i >= 0; i--) {
      const z1 = (i + 1) * STEP, z2 = i * STEP, k = Math.floor((cd + z2) / STEP), dd = cd + z2;
      if (z2 > VIEW) continue;
      ctx.fillStyle = grass[k % 2 ? 1 : 0]; quad(z1, z2, -40, 40, -40, 40);
      ctx.fillStyle = asphalt[k % 2 ? 1 : 0]; quad(z1, z2, -LE.HW, LE.HW, -LE.HW, LE.HW);
      const cn = leCornerAt(leLapPos(dd)) || leCornerAt(leLapPos(dd + 15)) || leCornerAt(leLapPos(dd - 15));
      if (cn) { ctx.fillStyle = k % 2 ? "#e03131" : "#f1f3f5"; quad(z1, z2, -LE.HW - LE.KERB, -LE.HW, -LE.HW - LE.KERB, -LE.HW); quad(z1, z2, LE.HW, LE.HW + LE.KERB, LE.HW, LE.HW + LE.KERB); }
      ctx.fillStyle = "rgba(255,255,255,.8)"; quad(z1, z2, -LE.HW - 0.25, -LE.HW, -LE.HW - 0.25, -LE.HW); quad(z1, z2, LE.HW, LE.HW + 0.25, LE.HW, LE.HW + 0.25);
      const pzS = lePitAt(dd), inLane = pzS != null && pzS >= LE.PZ_IN && pzS <= LE.PIT_OUT + LE.PIT_MERGE;
      if (opts.line && k % 4 < 2) {                    // the racing line: yellow dashes (into the pit lane at the lap's end)
        const l1 = leLineShown(cd + z1), l2 = leLineShown(dd), lw = 0.11;
        ctx.fillStyle = rain ? "rgba(255,212,59,.3)" : "rgba(255,212,59,.5)"; quad(z1, z2, l1 - lw, l1 + lw, l2 - lw, l2 + lw);
      }
      if (pzS != null) pitSlice(z1, z2, pzS, k, inLane);
      if (leLapPos(dd) > LE.L - STEP && leLapPos(dd) <= LE.L) {             // the start / finish line: chequered – across the pit lane too
        for (let q = 0; q < 12; q++) { ctx.fillStyle = q % 2 ? "#111" : "#fff"; const a = -LE.HW + q * LE.HW / 6; quad(z1, z2, a, a + LE.HW / 6, a, a + LE.HW / 6); }
        for (let q = 0; q < 4; q++) { ctx.fillStyle = q % 2 ? "#111" : "#fff"; const a = LE.PL_X - LE.PL_HW + q; quad(z1, z2, a, a + 1, a, a + 1); }
      }
    }
    // skid marks of my drift on the road (two dark lines behind the rear wheels)
    if (ui.skids && ui.skids.length > 1) {
      ctx.strokeStyle = dk > 0.5 ? "rgba(0,0,0,.35)" : "rgba(25,25,28,.26)"; ctx.lineCap = "round";
      for (let i = 1; i < ui.skids.length; i++) {
        const [d1, x1] = ui.skids[i - 1], [d2, x2] = ui.skids[i], z1 = d1 - d + CAMZ, z2 = d2 - d + CAMZ;
        if (d2 - d1 > 3 || d2 - d1 < 0.05 || z1 < 0.3 || z2 > VIEW) continue;
        ctx.lineWidth = Math.max(1, unit * sc(z1) * 0.12);
        for (const o of [-0.75, 0.75]) { ctx.beginPath(); ctx.moveTo(X(z1, x1 + o), Y(z1)); ctx.lineTo(X(z2, x2 + o), Y(z2)); ctx.stroke(); }
      }
    }
    // beside the track: trees, banners, camping fans, the braking boards; the other cars – far first
    const items = [];
    const at = (rel, xm, f) => { const z = rel + CAMZ; if (z > 0.5 && z < VIEW) items.push({ z, f: () => f(X(z, xm), Y(z), unit * sc(z), z) }); };
    for (let k = Math.floor((d - 10) / 24); k * 24 < d + VIEW; k++) {
      for (const side of [-1, 1]) if (side < 0 || lePitAt(k * 24) == null) at(k * 24 - d, side * (LE.HW + LE.KERB + 4 + (k % 3) * 2.5), (x, y, u) => {
        ctx.fillStyle = dk > 0.5 ? "#0b2018" : ["#1f6b3e", "#2b7f48"][((k % 2) + 2) % 2]; ctx.beginPath(); ctx.moveTo(x, y - u * 6); ctx.lineTo(x + u * 1.7, y); ctx.lineTo(x - u * 1.7, y); ctx.fill(); });
    }
    const lap0 = Math.floor(d / LE.L) - 1;
    for (let lp = lap0; lp <= lap0 + 2; lp++) {
      [20, 270, 590].forEach((x0, i) => {                           // now and then a banner (it changes from lap to lap)
        if (((lp + i) % 4 + 4) % 4 === 3) return;
        at(lp * LE.L + x0 - d, (i % 2 ? 1 : -1) * (LE.HW + LE.KERB + 3), (x, y, u) => { const bw = u * 6, bh = u * 1.05;
          ctx.fillStyle = "#495057"; ctx.fillRect(x - bw * 0.42, y - bh * 1.6, u * 0.1, bh * 1.6); ctx.fillRect(x + bw * 0.38, y - bh * 1.6, u * 0.1, bh * 1.6);
          if (bw > 30) leBanner(ctx, (((lp + i) % 2) + 2) % 2, x - bw / 2, y - bh * 1.9, bw, bh); });
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
    for (let lp = lap0; lp <= lap0 + 2; lp++) pitItems(lp);
    for (const o of st.teams) {                                      // the other cars where they are on the track (or in the pit lane, at their box)
      if (o === team) continue;
      let rel = leLapPos((o.d + (o.pit ? 0 : o.v) * Math.max(0, Math.min(1.5, t - simT()))) - d);
      if (rel > LE.L / 2) rel -= LE.L;
      if (rel < -CAMZ + 1 || rel > VIEW) continue;
      const haz = o.emg && Math.floor(t * 2.5) % 2 === 0;           // a car in the emergency drive mode: hazard lights
      const brk = !o.pit && !!brakeSeen[o.i] && nowS() < brakeSeen[o.i].until;
      at(rel, o.x || 0, (x, y, u, z) => { leCarRear(ctx, x, y, u * 2.8, o.color, o.num, { night: dk > 0.4, alpha: 0.97, flag: leFlag(o.country), hazard: haz, emg: haz, brake: brk, yaw: o.yaw || 0 });
        if (dk > 0.05) lights.push({ x, y, u, z, xm: o.x || 0, rel, pit: !!o.pit, brk }); });
    }
    items.sort((a, b) => b.z - a.z).forEach(it => it.f());
    if (dk > 0.02) nightLayer();                         // dusk, night, dawn: dark all around – the headlights light the road
    // The night as ONE overlay: a dark layer (an offscreen canvas) with holes cut out for the light – my headlight cone
    // (a trapezoid along the road fading with the distance, shorter and scattered in the rain), the other cars' own
    // glow, a few lamps at the pits – drawn over the picture; then the glints of the edge lines / kerbs just beyond the
    // cone and the tail lights on top. No per-pixel work; no flicker (nothing random over time).
    function nightLayer() {
      const dc = ui.dark || (ui.dark = document.createElement("canvas")), W = c.el.width, Hh = c.el.height;
      if (dc.width !== W || dc.height !== Hh) { dc.width = W; dc.height = Hh; }
      const g = dc.getContext("2d");
      g.setTransform(c.dpr, 0, 0, c.dpr, 0, 0); g.globalCompositeOperation = "source-over"; g.clearRect(0, 0, cw, ch);
      g.fillStyle = `rgba(1,2,7,${(rain ? 0.97 : 0.94) * dk})`; g.fillRect(0, 0, cw, ch);
      g.globalCompositeOperation = "destination-out";
      const reach = Math.min(VIEW, rain ? 28 : 60), zs = [];       // my headlights: the cone along the road
      for (let z = CAMZ; z <= reach + 1e-9; z += Math.max(2, reach / 12)) zs.push(z);
      const wAt = z => 2.0 + (z - CAMZ) * (rain ? 0.24 : 0.17);
      const cone = g.createLinearGradient(0, Y(CAMZ), 0, Y(reach));
      cone.addColorStop(0, "rgba(0,0,0,1)"); cone.addColorStop(rain ? 0.35 : 0.55, `rgba(0,0,0,${rain ? 0.7 : 0.9})`); cone.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = cone; g.beginPath();
      zs.forEach((z, i) => (i ? g.lineTo(X(z, car.x - wAt(z)), Y(z)) : g.moveTo(X(z, car.x - wAt(z)), Y(z))));
      for (let i = zs.length - 1; i >= 0; i--) g.lineTo(X(zs[i], car.x + wAt(zs[i])), Y(zs[i]));
      g.fill();
      const pool = (px, py, rx, ry, a) => { g.save(); g.translate(px, py); g.scale(1, ry / rx); const rg = g.createRadialGradient(0, 0, 0, 0, 0, rx);
        rg.addColorStop(0, `rgba(0,0,0,${a})`); rg.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = rg; g.beginPath(); g.arc(0, 0, rx, 0, 7); g.fill(); g.restore(); };
      pool(X(CAMZ + 2, car.x), Y(CAMZ + 2), unit * sc(CAMZ) * 4.5, unit * sc(CAMZ) * 1.6, 0.85);   // the light around my own car
      for (const lt of lights) if (!lt.pit) {               // the other cars' own headlight cones on the road ahead of them
        const za = lt.z + 1, zb = Math.min(VIEW, lt.z + (rain ? 10 : 18)), w0 = 1.1, w1 = rain ? 2.6 : 3.4;
        if (zb <= za) continue;
        const og = g.createLinearGradient(0, Y(za), 0, Y(zb)); og.addColorStop(0, `rgba(0,0,0,${rain ? 0.55 : 0.8})`); og.addColorStop(1, "rgba(0,0,0,0)");
        g.fillStyle = og; g.beginPath(); g.moveTo(X(za, lt.xm - w0), Y(za)); g.lineTo(X(zb, lt.xm - w1), Y(zb)); g.lineTo(X(zb, lt.xm + w1), Y(zb)); g.lineTo(X(za, lt.xm + w0), Y(za)); g.fill();
      }
      const lamps = [];                                      // the pit lane's lamps: pools of light on the lane and the boxes
      for (let lp = lap0; lp <= lap0 + 2; lp++) for (const pz of [-36, -12, 8, 26, 44, 62]) {
        const z = (lp + 1) * LE.L + pz - d + CAMZ;
        if (z > 0.8 && z < VIEW) { lamps.push(z); pool(X(z, LE.PL_X + 1), Y(z), unit * sc(z) * 7, unit * sc(z) * 3, rain ? 0.55 : 0.8); }
      }
      g.globalCompositeOperation = "source-over";
      ctx.drawImage(dc, 0, 0, cw, ch);
      // just beyond the cone: the reflectors on the edges and the kerbs glint a little – the corner's shape stays readable
      const ga = (rain ? 0.16 : 0.38) * dk;
      for (let z = reach; z < VIEW; z += 4) {
        const dd = cd + z, fade = 1 - (z - reach) / Math.max(1, VIEW - reach), kerb = leCornerAt(leLapPos(dd)), r = Math.max(1, unit * sc(z) * 0.22);
        ctx.fillStyle = `rgba(255,255,255,${ga * fade})`;
        for (const sd of [-1, 1]) { const xm = sd * (LE.HW + (kerb ? LE.KERB * 0.5 : 0.1)); ctx.fillRect(X(z, xm) - r / 2, Y(z) - r, r, r * 1.6); }
        if (kerb) { ctx.fillStyle = `rgba(255,80,80,${ga * fade})`; for (const sd of [-1, 1]) ctx.fillRect(X(z, sd * (LE.HW + LE.KERB)) - r / 2, Y(z) - r * 0.6, r, r); }
      }
      for (const z of lamps) {                                // the lamp heads
        const lx = X(z, LE.PL_X + LE.PL_HW + 1.6), ly = Y(z) - unit * sc(z) * 5, rr = Math.max(1.5, unit * sc(z) * 0.35);
        ctx.fillStyle = "rgba(73,80,87,.9)"; ctx.fillRect(lx - rr * 0.2, ly, rr * 0.4, Y(z) - ly);
        const lg = ctx.createRadialGradient(lx, ly, 0, lx, ly, rr * 4); lg.addColorStop(0, "rgba(255,236,170,.95)"); lg.addColorStop(1, "rgba(255,236,170,0)");
        ctx.fillStyle = lg; ctx.beginPath(); ctx.arc(lx, ly, rr * 4, 0, 7); ctx.fill();
      }
      for (const lt of lights) {                              // the other cars: tail lights (blurred in the rain), the spray
        const w = lt.u * 2.8, hgt = w * 0.5, ty = lt.y - hgt * 0.47, rr = Math.max(2, w * (rain ? 0.2 : 0.09));
        if (rain && !lt.pit) { const sp = ctx.createRadialGradient(lt.x, lt.y - hgt * 0.3, 0, lt.x, lt.y - hgt * 0.3, w * 0.9);
          sp.addColorStop(0, `rgba(170,180,195,${0.3 * dk})`); sp.addColorStop(1, "rgba(170,180,195,0)"); ctx.fillStyle = sp; ctx.beginPath(); ctx.arc(lt.x, lt.y - hgt * 0.3, w * 0.9, 0, 7); ctx.fill(); }
        if (lt.brk) {                                         // braking: a bright red flare and its reflection on the road (wet: stronger)
          const fr = w * (rain ? 0.95 : 0.75), fg = ctx.createRadialGradient(lt.x, ty, 0, lt.x, ty, fr);
          fg.addColorStop(0, `rgba(255,90,70,${0.85 * dk})`); fg.addColorStop(0.35, `rgba(255,30,30,${0.45 * dk})`); fg.addColorStop(1, "rgba(255,0,0,0)");
          ctx.fillStyle = fg; ctx.beginPath(); ctx.arc(lt.x, ty, fr, 0, 7); ctx.fill();
          const rl = w * (rain ? 1.6 : 0.7), ry = lt.y + rl * 0.5;
          ctx.save(); ctx.translate(lt.x, ry); ctx.scale(1, rl / (w * 0.7));
          const rg = ctx.createRadialGradient(0, 0, 0, 0, 0, w * 0.7);
          rg.addColorStop(0, `rgba(255,40,40,${(rain ? 0.55 : 0.28) * dk})`); rg.addColorStop(1, "rgba(255,40,40,0)");
          ctx.fillStyle = rg; ctx.beginPath(); ctx.arc(0, 0, w * 0.7, 0, 7); ctx.fill(); ctx.restore();
        }
        for (const sx of [-0.3, 0.3]) {                       // the tail lights: dim red – bright when braking
          const tr = rr * (lt.brk ? 3 : 2.2), tg = ctx.createRadialGradient(lt.x + sx * w, ty, 0, lt.x + sx * w, ty, tr);
          tg.addColorStop(0, lt.brk ? `rgba(255,140,120,${dk})` : `rgba(200,40,35,${0.75 * dk})`); tg.addColorStop(rain ? 0.5 : 0.3, `rgba(255,40,40,${(lt.brk ? 0.6 : 0.3) * dk})`); tg.addColorStop(1, "rgba(255,40,40,0)");
          ctx.fillStyle = tg; ctx.beginPath(); ctx.arc(lt.x + sx * w, ty, tr, 0, 7); ctx.fill();
        }
      }
      if (rain) {                                             // the rain haze eats the light: a soft veil over the cone
        const top = Y(reach) - 40, hz = ctx.createLinearGradient(0, top, 0, ch);
        hz.addColorStop(0, "rgba(120,130,145,0)"); hz.addColorStop(Math.min(0.9, 40 / Math.max(41, ch - top)), `rgba(120,130,145,${0.2 * dk})`); hz.addColorStop(1, `rgba(120,130,145,${0.05 * dk})`);
        ctx.fillStyle = hz; ctx.fillRect(0, top, cw, ch - top);
      }
    }
    // my car (or the team's car on the TV): rumble on the kerb, dust on the grass, wind lines in the slipstream
    const cx0 = X(CAMZ, opts.xs ?? car.x), cy0 = Y(CAMZ), cwid = unit * sc(CAMZ) * 2.8;
    const rumble = !red && (car.sf === 1 || (ui.rumble && nowS() - ui.rumble < 0.25)) ? Math.sin(t * 90) * 1.5 : 0;
    const grinding = !opts.tv && ui.grind && nowS() - ui.grind < 0.9;     // R at speed: the gearbox grinds – sparks, a hard shake
    const drifting = (car.dr || 0) > 0 && !car.pit;
    const shake = (car.v > 0 && !red ? Math.sin(t * 40) * 0.5 + rumble : 0) + (grinding && !red ? Math.sin(t * 110) * 4 : 0) + (drifting && !red ? Math.sin(t * 70) * 1.2 : 0);
    if (drifting && !opts.tv) {                                       // my drift leaves skid marks (world metres: they stay put)
      ui.skids = (ui.skids || []).filter(([sd]) => d - sd < 14).slice(-160);
      ui.skids.push([d - CAMZ * 0.2, car.x]);
    }
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
      hazard: haz, emg: haz, bat: car.bat, yaw: car.yaw || 0 });
    if (drifting) {                                                   // tyre smoke from the rear wheels (a still cloud with reduced motion)
      const r = leRand(red ? 9 : Math.floor(t * 16)), out = (car.yaw || 0) > 0 ? -1 : 1;
      for (let k = 0; k < 9; k++) {
        const a = r(), b = r(), sx = cx0 + (k % 2 ? 0.42 : -0.42) * cwid + out * a * cwid * 0.5, sy = cy0 - cwid * (0.05 + b * 0.3), rad = cwid * (0.12 + a * 0.16);
        ctx.fillStyle = `rgba(${dk > 0.5 ? "150,155,165" : "225,228,232"},${0.22 + 0.25 * (1 - b)})`;
        ctx.beginPath(); ctx.arc(sx, sy, rad, 0, 7); ctx.fill();
      }
    }
    if (rain) {
      ctx.strokeStyle = `rgba(200,215,235,${0.55 * (1 - 0.55 * dk)})`; ctx.lineWidth = 1;      // dimmer in the dark
      const r = leRand(red ? 5 : Math.floor(t * 12));
      ctx.beginPath(); for (let k = 0; k < 70; k++) { const x = r() * cw, y = r() * ch; ctx.moveTo(x, y); ctx.lineTo(x - 3, y + 12); } ctx.stroke();
    }
    if (ui.flash && nowS() - ui.flash < 0.35 && !opts.tv) { ctx.fillStyle = `rgba(242,84,91,${0.35 * (1 - (nowS() - ui.flash) / 0.35)})`; ctx.fillRect(0, 0, cw, ch); }
    // the minimap (top right) and the next corner (top left)
    const ms = Math.round(Math.min(110, Math.max(70, Math.min(cw, ch) * 0.26)));
    minimap(ctx, cw - ms - 6, 6, ms, t, { ...team, d, pit: car.pit, pl: car.pl || 0, x: car.x });
    const [nc, dz] = leNextCorner(leLapPos(d)), sw = Math.min(ms * 1.15, 120);
    const signOn = !!(nc && dz < Math.min(220, VIEW * 1.45) && !car.pit);   // later at night, much later at night in the rain
    ui.top = { l: signOn ? sw + 14 : 8, r: cw - ms - 14, b: Math.max(ms, signOn ? sw * 0.62 : 0) + 12, y0: 8 };   // the room for the notice (between them)
    if (signOn) {
      const vs = leSafe(nc, car.tyre, rain), kmh = Math.round(leKmh(vs * 0.95) / 5) * 5;
      const hot = car.v > vs * 1.02 && dz <= (car.v * car.v - vs * vs) / (2 * LE.BRAKE) + car.v * 0.6 + 8;
      cornerSign(ctx, 6, 6, sw, nc, dz, kmh, hot);
    }
    if (!opts.tv) {                                                    // the driver: the speedometer top centre, the position card top left
      const R = Math.floor(Math.min(leClamp(Math.min(cw, ch) * 0.13, 40, 62), (cw - ms - sw - 46) / 2)), gw = 2 * R + 22;
      const gx = leClamp(cw / 2, sw + 12 + gw / 2, cw - ms - 12 - gw / 2);
      const gb = speedo(ctx, gx, 6, R, car, t);
      const card = raceCard(ctx, 6, 6 + Math.round(sw * 0.62) + 6, Math.min(cw * 0.36, 210), { ...team, d }, t, ch < 420 ? 0.92 : cw > 900 ? 1.15 : 1);
      ui.top = { l: card.r + 6, r: cw - ms - 12, b: gb + 4, y0: gb + 4, fit: true };   // the notice: just under the speedometer
    }
  }
  const rr = (ctx, x, y, w, hh, r) => { ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, y, w, hh, r); else ctx.rect(x, y, w, hh); };
  const OVL = "rgba(15,23,42,.66)";                                  // the overlays' own background: readable by day, at night, in the rain
  // the speedometer (top centre on the driver's picture): an arc gauge with the needle (no easing – it shows the value),
  // the big km/h, the gear (A4 / M3 / N / R), the rev / shift light around the arc (red: shift up; the limiter blinks –
  // steady with reduced motion), below it the battery with %; the engine temperature and wrong tyres only as warnings
  function speedo(ctx, cx, y0, R, car, t) {
    const rain = leInWin(st.rain, t), rv = leRev(car, rain), red = leReduced(), v = Math.abs(car.v || 0);
    const cy = y0 + R + 6, w = 2 * R + 22, x0 = cx - w / 2, yb = cy + R * 0.76 + 6;
    const tw = car.eng || car.temp >= 92 ? "red" : car.temp >= LE.YELLOW ? "yellow" : null, wrong = leGrip(car.tyre, rain) < 1;
    const hgt = yb + 10 - y0 + 7 + (tw || wrong ? 17 : 0);
    ctx.save();
    ctx.fillStyle = OVL; rr(ctx, x0, y0, w, hgt, 14); ctx.fill();
    const A0 = Math.PI * 0.75, SW = Math.PI * 1.5, ang = x => A0 + SW * leClamp(x / (240 / 7), 0, 1);   // 0 … 240 km/h
    ctx.lineCap = "round"; ctx.lineWidth = Math.max(4, R * 0.1);
    ctx.strokeStyle = "rgba(255,255,255,.16)"; ctx.beginPath(); ctx.arc(cx, cy, R * 0.8, A0, A0 + SW); ctx.stroke();
    ctx.strokeStyle = "#74c0fc"; ctx.beginPath(); ctx.arc(cx, cy, R * 0.8, A0, Math.max(A0 + 0.01, ang(v))); ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.5)"; ctx.lineWidth = 1.5;
    for (let k = 0; k <= 6; k++) { const a = A0 + SW * k / 6; ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * R * 0.6, cy + Math.sin(a) * R * 0.6); ctx.lineTo(cx + Math.cos(a) * R * 0.68, cy + Math.sin(a) * R * 0.68); ctx.stroke(); }
    const N = 12, lit = rv.g < 1 ? 0 : Math.max(1, Math.min(N, Math.round((rv.r - 0.4) / 0.57 * N))), blink = rv.lim && !red && Math.floor(nowS() * 8) % 2 === 1;
    ctx.lineCap = "butt"; ctx.lineWidth = Math.max(3, R * 0.09);
    for (let k = 0; k < N; k++) {
      const on = rv.lim ? !blink : k < lit;
      ctx.strokeStyle = !on ? "rgba(255,255,255,.1)" : rv.lim || k >= 10 ? "#fa5252" : k >= 7 ? "#fab005" : "#40c057";
      ctx.beginPath(); ctx.arc(cx, cy, R * 0.98, A0 + SW * k / N + 0.03, A0 + SW * (k + 1) / N - 0.03); ctx.stroke();
    }
    const a = ang(v);                                                // the needle: only its outer part (the number stays clear)
    ctx.strokeStyle = "#ff6b6b"; ctx.lineWidth = Math.max(2, R * 0.06); ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * R * 0.5, cy + Math.sin(a) * R * 0.5); ctx.lineTo(cx + Math.cos(a) * R * 0.86, cy + Math.sin(a) * R * 0.86); ctx.stroke();
    ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = "#fff";
    ctx.font = "900 " + Math.round(R * 0.5) + "px system-ui, sans-serif"; ctx.fillText(String(leKmh(v)), cx, cy - R * 0.08);
    ctx.font = "700 " + Math.round(R * 0.17) + "px system-ui, sans-serif"; ctx.fillStyle = "rgba(255,255,255,.72)"; ctx.fillText("km/h", cx, cy + R * 0.24);
    ctx.font = "900 " + Math.round(R * 0.3) + "px system-ui, sans-serif"; ctx.fillStyle = rv.g < 0 ? "#ffa94d" : rv.g === 0 ? "#adb5bd" : "#ffd43b";
    ctx.fillText(rv.g < 0 ? "R" : rv.g === 0 ? "N" : (car.man ? "M" : "A") + rv.g, cx, cy + R * 0.6);
    const b = Math.max(0, car.bat ?? 0), need = leNeed(car.d), lvl = b <= 0 || b < need.lift ? "#fa5252" : b < need.mix ? "#fd7e14" : "#40c057";
    const bx = x0 + 22, bw = w - 22 - 40;
    ctx.font = "11px system-ui, 'Apple Color Emoji', 'Noto Color Emoji'"; ctx.fillText("🔋", x0 + 13, yb + 5);
    ctx.fillStyle = "rgba(255,255,255,.2)"; rr(ctx, bx, yb, bw, 10, 5); ctx.fill();
    ctx.fillStyle = lvl; rr(ctx, bx, yb, Math.max(5, bw * Math.min(100, b) / 100), 10, 5); ctx.fill();
    ctx.font = "800 11.5px system-ui, sans-serif"; ctx.textAlign = "right"; ctx.fillStyle = lvl === "#40c057" ? "#fff" : lvl;
    ctx.fillText(Math.ceil(b) + "%", x0 + w - 7, yb + 5.5);
    if (tw || wrong) {                                                // the warnings: only when they matter
      const yw = yb + 20, pulse = !red && tw === "red" ? 0.6 + 0.4 * Math.abs(Math.sin(nowS() * 6)) : 1;
      ctx.textAlign = "left"; ctx.font = "800 11.5px system-ui, 'Apple Color Emoji', 'Noto Color Emoji'";
      let x = x0 + 8;
      if (tw) {
        ctx.globalAlpha = pulse; ctx.fillStyle = tw === "red" ? "#ff6b6b" : "#ffd43b"; ctx.fillText("🌡️", x, yw); x += 18;
        const tb = wrong ? w - 62 : w - 34, f = leClamp((car.temp - LE.TMIN) / (LE.RED - LE.TMIN), 0.05, 1);
        ctx.fillStyle = "rgba(255,255,255,.2)"; rr(ctx, x, yw - 4, tb, 8, 4); ctx.fill();
        ctx.fillStyle = tw === "red" ? "#fa5252" : "#fab005"; rr(ctx, x, yw - 4, tb * (car.eng ? 1 : f), 8, 4); ctx.fill();
        ctx.globalAlpha = 1; x += tb + 6;
      }
      if (wrong) { ctx.fillStyle = "#ffa94d"; ctx.fillText((car.tyre === "r" ? "🌧️" : "☀️") + "!", x, yw); }
    }
    ctx.restore();
    return y0 + hgt;
  }
  // the position card (top left under the corner sign): «P2/5» big with my car, the leader (🏁, not when I lead), the
  // car ahead (▲ gap) and behind (▼ gap) – a lapped car «+1 lap» – and one small line with the lap and the race clock
  function raceCard(ctx, x, y, maxW, me, t, k) {
    const dOf = o => (o.i === me.i ? me.d : o.pit ? o.d : o.d + o.v * Math.max(0, Math.min(1.5, t - simT())));
    const rc = leRaceCard(st, me.i, dOf), pad = 7 * k, lh = 16 * k, emo = "'Apple Color Emoji', 'Noto Color Emoji'";
    const fSmall = "700 " + (11.5 * k).toFixed(1) + "px system-ui, " + emo + ", sans-serif", fBig = "900 " + Math.round(20 * k) + "px system-ui, sans-serif";
    const gapTxt = c => (c.laps ? "+" + leLapsTxt(c.laps) : c.s.toFixed(1) + " s");
    const tt = leClamp(t, 0, limit());
    const foot = I18N.tr(T("Lap {0}")).replace("{0}", leLaps(me.d) + 1) + " · ⏳ " + leRaceLeft(tt, limit());
    const chipW = num => { ctx.font = "800 " + (11 * k).toFixed(1) + "px system-ui, sans-serif"; return ctx.measureText("#" + num).width + 8 * k; };
    const rows = [];
    if (rc.leader) rows.push({ ic: "🏁", c: rc.leader, txt: rc.leader.name, col: "#fff", name: true });
    if (rc.ahead) rows.push({ ic: "▲", c: rc.ahead, txt: gapTxt(rc.ahead), col: "#ff8787" });
    if (rc.behind) rows.push({ ic: "▼", c: rc.behind, txt: gapTxt(rc.behind), col: "#8ce99a" });
    ctx.save();
    ctx.font = fBig; const posTxt = "P" + rc.pos + "/" + rc.n, pw = ctx.measureText(posTxt).width;
    let w = pad * 2 + pw + 6 * k + chipW(me.num);
    ctx.font = fSmall;
    for (const r of rows) r.w = 18 * k + chipW(r.c.num) + 5 * k + ctx.measureText(r.txt).width;
    w = Math.min(maxW, Math.max(w, ctx.measureText(foot).width + pad * 2, ...rows.map(r => r.w + pad * 2)));
    const hgt = pad + 22 * k + rows.length * lh + 15 * k + pad * 0.6;
    ctx.fillStyle = OVL; rr(ctx, x, y, w, hgt, 12); ctx.fill();
    const chip = (cx, cy, num, color, mine) => { ctx.font = "800 " + (11 * k).toFixed(1) + "px system-ui, sans-serif"; const cw_ = chipW(num), chh = 15 * k;
      ctx.fillStyle = color; rr(ctx, cx, cy - chh / 2, cw_, chh, 5); ctx.fill();
      if (mine) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke(); }
      ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.fillText("#" + num, cx + cw_ / 2, cy + 0.5); return cw_; };
    ctx.textBaseline = "middle"; ctx.textAlign = "left";
    let cy = y + pad + 11 * k;
    ctx.font = fBig; ctx.fillStyle = "#fff"; ctx.fillText(posTxt, x + pad, cy);
    chip(x + pad + pw + 6 * k, cy, me.num, me.color, true);
    cy += 11 * k + lh / 2 + 2 * k;
    for (const r of rows) {
      ctx.font = fSmall; ctx.textAlign = "left"; ctx.fillStyle = r.col; ctx.fillText(r.ic, x + pad, cy);
      const cx = x + pad + 18 * k, cw_ = chip(cx, cy, r.c.num, r.c.color, false), tx = cx + cw_ + 5 * k, room = x + w - pad - tx;
      ctx.font = fSmall; ctx.textAlign = "left"; ctx.fillStyle = r.col;
      let txt = r.txt;
      if (ctx.measureText(txt).width > room) { while (txt.length > 1 && ctx.measureText(txt + "…").width > room) txt = txt.slice(0, -1); txt += "…"; }
      ctx.fillText(txt, tx, cy);
      cy += lh;
    }
    ctx.font = "600 " + (10.5 * k).toFixed(1) + "px system-ui, sans-serif"; ctx.fillStyle = "rgba(255,255,255,.72)"; ctx.textAlign = "left";
    ctx.fillText(foot, x + pad, cy - 1 * k, w - pad * 2);
    ctx.restore();
    return { r: x + w, b: y + hgt };
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

  // ---------- the pit stop: done by the driver who drives next, on their phone – big targets around the car from above,
  // all tappable at once, every job runs from its own tap (progress rings): the battery (4 s), the 4 tyres (1 s each)
  // and after an overheat the engine (7 s); the tyres for the next lap (slicks / rain) with one toggle. The one who came
  // in watches the same panel live (no taps). Every tap goes to the server, which times and checks it.
  const sendTap = async (action, spot) => {
    try { const r = await req("/tap", { method: "POST", body: { action, spot } }); if (r && r.state) setState(r.state); return r; }
    catch (e) { toast(e.message, "bad"); return null; }
  };
  const SPOTS = [T("FL"), T("FR"), T("RL"), T("RR")], SPOT_ARIA = [T("Front left tyre"), T("Front right tyre"), T("Rear left tyre"), T("Rear right tyre")];
  function stopPanel(stp, mine) {
    const ring = (cls, ic, label, aria, onTap) => {
      const b = h("button.le-tgt" + cls, { type: "button", "aria-label": I18N.tr(aria), disabled: !mine }, h("span.le-tgtic", ic), h("small", label), h("i.le-tgtok", "✓"));
      if (mine) b.addEventListener("pointerdown", e => { e.preventDefault(); onTap(); });
      return b;
    };
    const tapJob = async (action, spot) => {
      const tm = myTeam(), stp_ = tm && tm.stop, js = leStopJobs(stp_, gameT()), key = action + (spot ?? "");
      if (!stp_ || js.over || local.pend.has(key)) return;
      local.pend.add(key); LeAudio.wrench(); leBuzz(20); stopTick(gameT());
      await sendTap(action, spot);
      local.pend.delete(key);
      stopTick(gameT());
    };
    const bat = ring(".le-tbat", "🔋", I18N.tr(T("Battery")), T("Battery"), () => tapJob("battery"));
    const tyres = [0, 1, 2, 3].map(k => ring(".le-ttyre.le-t" + k, "🛞", I18N.tr(SPOTS[k]), SPOT_ARIA[k], () => tapJob("tyre", k)));
    const eng = stp.eng ? ring(".le-teng", "🔧", I18N.tr(T("Engine")), T("Engine"), () => tapJob("engine")) : null;
    const hint = h("div.le-stophint", "👆 ", T("Tap everything!"));
    const comp = ["s", "r"].map(k => h("button.le-comp", { type: "button", "data-k": k, disabled: !mine, "aria-label": I18N.tr(k === "r" ? T("Rain tyres") : T("Slicks")),
      onclick: () => { const tm = myTeam(); if (mine && tm && tm.stop && tm.stop.tyre !== k) { LeAudio.tone([700], "triangle", 0.06, 0.06); sendTap(k === "r" ? "rain" : "slicks"); } } },
      k === "r" ? "🌧️" : "☀️", h("small", k === "r" ? T("Rain") : T("Dry"))));
    const pad = h("div.le-stoppad", { style: { "--tc": myTeam().color } }, h("div.le-stopcar", { "aria-hidden": "true" }), bat, ...tyres, eng);
    const el = h("div.le-stopwrap" + (mine ? "" : ".le-stopview"), pad,
      h("div.le-stopside", hint, h("div.le-comps", h("span.small", "🛞"), ...comp), h("div.le-watchrow", ui.watchHand = h("div.le-dial", h("i")), ui.watch = h("div.le-watch", "⏱ 0.0 s")),
        ui.cap = h("div.small.muted.center")));
    return { el, bat, tyres, eng, hint, comp };
  }
  // the panel and the stopwatch – from the server's jobs (my taps on the way: «…»)
  function stopTick(t) {
    const tm = myTeam(), stp = tm && tm.stop, pn = ui.panel;
    if (!stp || !pn) return;
    const js = leStopJobs(stp, t);
    const paint = (b, s, p, key) => {
      const pending = local.pend.has(key) && s === "tap";
      b.dataset.s = pending ? "wait" : s; b.style.setProperty("--p", (p * 100).toFixed(1) + "%");
    };
    paint(pn.bat, js.bat.s, js.bat.p, "battery");
    pn.tyres.forEach((b, k) => paint(b, js.tyres[k].s, js.tyres[k].p, "tyre" + k));
    if (pn.eng && js.eng) paint(pn.eng, js.eng.s, js.eng.p, "engine");
    setTxt(pn.hint, js.done || js.over ? "✓ " + I18N.tr(T("Done – go!")) : "👆 " + I18N.tr(T("Tap everything!")));
    pn.hint.classList.toggle("le-ok", js.done || js.over);
    pn.comp.forEach(b => b.classList.toggle("on", b.dataset.k === stp.tyre));
    if (ui.watch) {
      setTxt(ui.watch, (js.over ? "✓ " : "⏱ ") + js.el.toFixed(1) + " s");
      ui.watch.classList.toggle("le-done", js.over);
      ui.watchHand.style.setProperty("--a", (js.el % 10) * 36 + "deg");
      setTxt(ui.cap, I18N.tr(T("{0} s at most")).replace("{0}", String(js.cap)));
    }
    if (js.over && !ui.cheered) {                               // the stands cheer – loud for a fast stop
      ui.cheered = true;
      const fast = stp.done && stp.time <= 5 + (stp.eng ? LE.ENG_EXTRA : 0);     // tapped at once: about 4.2 s (+3 s engine)
      if (ui.crowd) ui.crowd.classList.add("cheer", ...(fast ? ["big"] : []));
      if (fast) { LeAudio.tone([523, 784, 1046], "triangle", 0.18, 0.1, 0.1); toast("🎉 " + I18N.tr(T("Super fast stop!")), "good"); }
      else LeAudio.ok();
    }
  }
  // the stands beside the pits: people and the flags of the teams, waving when a stop is done
  function crowd(tm) {
    const people = ["🙋", "🧒", "👩", "🧑", "👨", "👧", "🧓", "👦", "🙌", "👩‍🦰", "🧔", "👱"];
    const flags = leFlagOk() ? [...new Set(st.teams.map(o => leFlag(o.country)).filter(Boolean))] : [];
    const r = leRand(tm.num * 31 + 7);
    const ad = h("canvas.le-ad", { width: 360, height: 26, "aria-hidden": "true" });     // the pit wall: a banner (another one at every stop)
    const ctx = ad.getContext("2d");
    if (ctx) leBanner(ctx, (tm.stop ? tm.stop.n : 0) % 2, 0, 0, 360, 26);
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
    if (leScreen(st, myId, t).intro !== !!ui.intro) draw();     // the green light: the intro goes
    const team = myTeam();
    if (ui.go && t >= 0 && t < 0.2) { ui.go = false; LeAudio.light(true); leBuzz(120); }
    const c = ui.cv;
    if (c) {
      fit(c);
      if (ui.mode === "drive") c.wrap.classList.toggle("le-ctloff", ui.intro || !leControls("drive", false, predicted(Math.min(t, limit())), t, limit()));   // the controls: only when usable
      if (ui.intro) intro(c, t);
      else {
        let car, tm = team;
        if (ui.mode === "drive") car = predicted(Math.min(t, limit()));
        else {
          tm = team || st.teams[st.standings[0]];
          car = { ...tm.car || {}, d: tm.d, v: tm.v, x: tm.x || 0, pit: tm.pit, thr: (tm.car || {}).thr ?? 1, eng: tm.eng, sf: tm.sf || 0, pl: tm.pl || 0, ap: tm.ap || 0, box: tm.box, dr: tm.dr || 0, yaw: tm.yaw || 0 };
          car.d = tm.pit ? tm.d : tm.d + tm.v * Math.max(0, Math.min(1.5, t - simT()));
          car._s = t;
          if (car.bat == null && tm.emg) car.bat = 0;
        }
        if (car) {
          // the picture follows the car smoothly across the track (a correction from the server glides, never jumps)
          ui.xs = ui.xs == null || car.pit ? car.x : ui.xs + (car.x - ui.xs) * Math.min(1, fdt * 14);
          if (!car.pit && !leReduced()) ui.pan = ((ui.pan || 0) + leCurve(car.d) * car.v * fdt * 0.6) % 100;
          race(c, car, tm, t, { tv: ui.mode !== "drive", xs: ui.xs, line: ui.mode === "drive" && lineOn() });
          // ONE small notice at the top of the picture (icon + a few words, between the corner sign and the minimap, else
          // just under them): the most important one wins, it stays while its condition lasts and then fades out
          const drv = ui.mode === "drive", ph = t < limit() ? lePitHint(car) : null;
          const pitTxt = ph === "keep" ? ["➡ " + I18N.tr(T("Pit lane – keep right")), "#a5d8ff"] : ph === "ap" ? ["🤖 " + I18N.tr(T("Autopilot to the pits")), "#a5d8ff"]
            : ph === "lim" ? ["🅿️ " + I18N.tr(T("Pit limiter")) + " " + leKmh(LE.PIT_V) + " km/h", "#e9ecef"] : ph === "exit" ? ["↖ " + I18N.tr(T("Pit exit")), "#e9ecef"] : null;
          const want = t < 1 && drv ? [I18N.tr(T("GO!")), "#69db7c"]
            : t >= limit() ? ["🏁 " + I18N.tr(T("Finish!")), "#fff"]
            : car.bat != null && car.bat <= 0 && !car.pit ? ["⚠️ " + I18N.tr(T("Emergency drive mode")), "#ffa94d"]
            : drv && ui.grind && nowS() - ui.grind < 1.6 ? ["💥 " + I18N.tr(T("Gearbox!")), "#ff922b"]
            : car.eng ? ["💥 " + I18N.tr(T("Engine overheated!")), "#ff8787"]
            : car.dr === 2 ? ["🌀 " + I18N.tr(T("Spin!")), "#ffa94d"]
            : drv && (car.sf === 2 || (ui.offAt && nowS() - ui.offAt < 1.5)) ? ["🟫 " + I18N.tr(T("Off the track!")), "#ffd8a8"]
            : car.dr === 1 ? ["💨 " + I18N.tr(T("Drift!")), "#e599f7"]
            : drv && brakeHint(car, t) ? ["🛑 " + I18N.tr(T("Brake!")), "#ff8787"]
            : ph === "ap" || ph === "keep" ? pitTxt
            : drv && car.thr > 0 && car.bat < leNeed(car.d).mix ? ["🔋 " + I18N.tr(T("Save energy!")), "#ffd43b"]
            : drv && car.temp >= 92 ? ["🔥 " + I18N.tr(T("Let go!")), "#ff6b6b"]
            : pitTxt ? pitTxt
            : (car.tow || 0) > 0.05 && drv ? ["🌬️ " + I18N.tr(T("Slipstream!")), "#e7f5ff"] : null;
          if (want) ui.note = { txt: want[0], col: want[1], at: nowS() };
          if (ui.note) {
            const age = nowS() - ui.note.at, a = Math.max(0, Math.min(1, 1 - (age - 0.05) / 0.35));
            if (a <= 0) ui.note = null;
            else leNotice(c.ctx, c.w, ui.top || { l: 8, r: c.w - 8, b: 8 }, ui.note.txt, ui.note.col, a);
          }
          if (ui.mode === "drive" && car.temp >= 92 && !car.eng && t - lastTempWarn > 1) { lastTempWarn = t; leBuzz(80); LeAudio.tone([900], "square", 0.08, 0.05); }
          if (ui.mode === "drive") LeAudio.engine(!document.hidden && !car.pit && t < limit(), Math.min(1, car.v / LE.VFULL * 0.7 + Math.max(0, car.thr) * 0.3));
          else LeAudio.engine(false);
          hud(car, tm, t);
        }
      }
    }
    if (ui.mode !== "drive") LeAudio.engine(false);
    if (ui.mode === "pit" || ui.mode === "stop") stopTick(t);
    if (ui.mode === "rest") restTick(t);
    if (ui.clock7) ui.clock7.set(leClock(leClamp(t, 0, limit()), limit()));
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
  // ---------- the bars (the break, the stop, watching): position, lap, day / night, race time left, lap times and gaps,
  // the standings; the driver: only the gears (A / M, the shifter) – the rest is on the picture
  function hud(car, tm, t) {
    const hd = ui.hud;
    if (!hd || !tm) return;
    const pos = st.standings.indexOf(tm.i) + 1, tt = Math.max(0, Math.min(t, limit())), night = leDark(tt, limit()) > 0.5;
    if (hd.pos) {
      setTxt(hd.pos, "P" + pos + "/" + st.teams.length);
      setTxt(hd.lap, I18N.tr(T("Lap {0}")).replace("{0}", leLaps(car.d) + 1));
      setTxt(hd.clock, (night ? "🌙" : "☀️") + (leInWin(st.rain, tt) ? " 🌧️" : ""));
      setTxt(hd.left, "⏳ " + leRaceLeft(tt, limit()));
      hd.left.classList.toggle("le-final", tt >= limit() * 22 / 24);
    }
    if (hd.cur) {                                              // the lap times, the gaps to the cars ahead / behind
      const c0 = tm.car || {}, ls_ = car.ls ?? c0.ls ?? 0, cur = car.pit || car.d < 0 ? 0 : Math.max(0, Math.min(t, limit()) - ls_);
      setTxt(hd.cur, "⏱ " + leLapTime(cur));
      setTxt(hd.best, "⭐ " + leLapTime(tm.best_lap || c0.best || 0));
      const rc = leRaceCard(st, tm.i, o => (o.i === tm.i ? car.d : o.pit ? o.d : o.d + o.v * Math.max(0, Math.min(1.5, t - simT()))));
      const gap = c => (c.laps ? "+" + leLapsTxt(c.laps) : c.s.toFixed(1) + " s");
      setTxt(hd.ahead, rc.ahead ? "▲ " + gap(rc.ahead) : "▲ –");
      setTxt(hd.behind, rc.behind ? "▼ " + gap(rc.behind) : "▼ –");
    }
    if (hd.gears) {                                            // the gears: the toggle, the shifter
      const man = !!car.man;
      if (hd.gears.dataset.on !== String(man)) {
        hd.gears.dataset.on = String(man); hd.gears.classList.toggle("on", man); hd.gears.setAttribute("aria-pressed", String(man));
        if (ui.shift) ui.shift.el.hidden = !man;
      }
      if (ui.shift && man) ui.shift.sync(car.gear ?? 1);
    }
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
  // the standings strip at the top: P1, P2 … with the flag, the car number in the team colour and the gap to the car
  // ahead (seconds, or laps; «Leader» for P1, 🅿️ in the pit lane) – mine highlighted and scrolled into view (live)
  function drawBoard() {
    if (!ui.board || !st.teams) return;
    const t = gameT(), dOf = o => (o.pit ? o.d : o.d + o.v * Math.max(0, Math.min(1.5, t - simT())));
    const sig = JSON.stringify(st.standings.map(i => [i, st.teams[i].pit, st.teams[i].pl, Math.round(dOf(st.teams[i]) / 4)]));
    if (ui.board.dataset.sig === sig) return;
    ui.board.dataset.sig = sig;
    let mineEl = null;
    ui.board.replaceChildren(...st.standings.map((i, k) => {
      const o = st.teams[i], ahead = k ? st.teams[st.standings[k - 1]] : null, dd = ahead ? Math.max(0, dOf(ahead) - dOf(o)) : 0;
      const gap = !ahead ? I18N.tr(T("Leader")) : dd >= LE.L ? "+" + Math.floor(dd / LE.L) + " " + I18N.tr(T("lap")) : "+" + (dd / 21).toFixed(1) + " s";
      const el = h("div.le-chip" + (i === st.my_team ? ".le-mine" : ""), { style: { "--tc": o.color }, title: o.name },
        h("b.le-rank", "P" + (k + 1)), leFlagEl(o.country), h("span.le-num", String(o.num)),
        h("span.le-gap", gap), o.pit || o.pl ? h("span.le-inpit", "🅿️") : null);
      if (i === st.my_team) mineEl = el;
      return el;
    }));
    if (mineEl) { const b = ui.board, x = mineEl.offsetLeft - b.offsetLeft; if (x < b.scrollLeft || x + mineEl.offsetWidth > b.scrollLeft + b.clientWidth) b.scrollLeft = Math.max(0, x - 24); }
  }
  // ---------- the break: how far the car is from the pits (my stop comes when I drive next), the forecast
  function restTick(t) {
    const tm = myTeam();
    if (!tm) return;
    if (ui.cast) setTxt(ui.cast, forecast(Math.max(0, t)));
    if (ui.eta) {
      const left = tm.pl === 2 ? 0 : tm.d < 0 ? LE.L - tm.d : LE.L - (tm.d % LE.L) + (tm.pl === 3 ? 0 : tm.box ?? LE.BOX0), secs = Math.max(0, left / Math.max(10, tm.v || LE.VLIFT));
      ui.eta.style.setProperty("--v", Math.max(0, Math.min(100, (1 - left / LE.L) * 100)) + "%");
      setTxt(ui.etaTxt, t < 0 ? I18N.tr(T("Get ready!")) : I18N.tr(tm.next === myId ? T("Your stop in about {0} s") : T("The car is in in about {0} s")).replace("{0}", Math.round(secs)));
    }
  }
  // the race clock: the race's time of day (HH:MM) as a digital 7-segment display (inline SVG, unlit segments faint,
  // amber on dark – readable at night); the colon blinks once a second (lit with reduced motion, CSS); own look
  const SEG7 = { a: [2, 0.6, 8, 2], b: [9.4, 2.2, 2, 7.2], c: [9.4, 10.6, 2, 7.2], d: [2, 17.4, 8, 2], e: [0.6, 10.6, 2, 7.2], f: [0.6, 2.2, 2, 7.2], g: [2, 9, 8, 2] };
  const SEG_ON = ["abcdef", "bc", "abged", "abgcd", "fgbc", "afgcd", "afgedc", "abc", "abcdefg", "abcdfg"];
  function segClock(txt) {
    const NS = "http://www.w3.org/2000/svg";
    const digit = () => {
      const svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", "0 0 12 20"); svg.setAttribute("class", "le-seg"); svg.setAttribute("aria-hidden", "true");
      const segs = {};
      for (const [k, [x, y, w, hh]] of Object.entries(SEG7)) {
        const r = document.createElementNS(NS, "rect");
        for (const [a, v] of Object.entries({ x, y, width: w, height: hh, rx: 0.9 })) r.setAttribute(a, v);
        svg.append(r); segs[k] = r;
      }
      return { svg, segs, v: null };
    };
    const ds = [digit(), digit(), digit(), digit()];
    const el = h("span.le-segclock", { role: "timer", "aria-live": "off" }, ds[0].svg, ds[1].svg, h("i.le-segcolon", { "aria-hidden": "true" }), ds[2].svg, ds[3].svg);
    let cur = "";
    const set = s_ => {
      if (s_ === cur) return;
      [...s_.replace(":", "")].forEach((ch, i) => { const d = ds[i]; if (d.v === ch) return; d.v = ch;
        const on = SEG_ON[+ch] || ""; for (const [k, r] of Object.entries(d.segs)) r.classList.toggle("on", on.includes(k)); });
      cur = s_; el.setAttribute("aria-label", I18N.tr(T("Race time {0}")).replace("{0}", s_)); el.title = el.getAttribute("aria-label");
    };
    set(txt);
    return { el, set };
  }

  // ---------- the screen
  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return !st.solo && !me.guest && st.status !== "done" ? "langstrecke" : null; }
  // the ☰ menu's own entries while racing: for the driver the assist and the racing line (switches – the menu stays
  // open), for everybody the team, its car and the forecast
  function menuExtra() {
    const tm = myTeam();
    if (!st || st.phase !== "play" || !tm) return null;
    const out = [];
    if (ui.mode === "drive") {
      const tog = (ic, label, on, flip) => {
        const state = h("b.le-mstate"), b = h("button.drawer-item.le-mtog", { type: "button", role: "switch" }, h("span.foot-ic", ic), h("span.grow", I18N.tr(label)), state);
        const paint = v => { b.setAttribute("aria-checked", String(!!v)); b.classList.toggle("on", !!v); state.textContent = I18N.tr(v ? T("on") : T("off")); };
        b.addEventListener("click", () => paint(flip()));
        paint(on);
        return b;
      };
      const c = predicted();
      out.push(tog("🧒", T("Driving assist"), !!(c && c.ast), () => { const c2 = predicted(), v = c2 && c2.ast ? 0 : 1; input("a", v); return !!v; }));
      out.push(tog("〰️", T("Racing line"), lineOn(), () => { const on = !lineOn(); try { localStorage.setItem(LINE_KEY(), on ? "1" : "0"); } catch {} return on; }));
    }
    out.push(h("div.drawer-item.le-minfo", h("span.foot-ic", LE_ICON), h("span.le-teamtag", { style: { "--tc": tm.color } }, leFlagEl(tm.country), " #" + tm.num, " ", C(tm.name)),
      h("span.small.muted", " ", tm.members.map(id => pName(id)).join(", "))));
    out.push(h("div.drawer-item.le-minfo", h("span.foot-ic", "📡"), h("span", forecast(Math.max(0, gameT())))));
    return out;
  }
  function draw(force) {
    if (!alive || !box.isConnected) return;
    const tm = myTeam();
    const { mode, intro: introOn } = leScreen(st, myId, gameT());
    const sig = JSON.stringify(st && [st.game, st.phase, st.status, st.joined, mode, introOn, tm && tm.driver, (mode === "pit" || mode === "stop") && tm.stop.t,
      st.phase === "lobby" ? st.players.map(p => [p.id, p.team]) : 0, st.phase === "done" ? st.players.map(p => p.place) : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    box.classList.toggle("le-scroll", mode === "lobby" || mode === "pit" || mode === "stop"); box.classList.toggle("le-drv", mode === "drive" && !introOn);
    ui = { go: ui.go ?? true, roared: ui.roared, mode, intro: introOn, xs: mode === "drive" ? ui.xs : null, pan: ui.pan, skids: mode === "drive" ? ui.skids : [], cheered: ui.cheered };
    if (!st) return show(h("section.card.center", h("div.big-ic", LE_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const menu = gameMenu({ rules: () => langstreckeRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: invite(), extra: menuExtra,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { if (!st || st.phase !== "done") { stop(); back(); } }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    // the 7-segment race clock (the race's time of day) in the header row – the lobby shows the start, 16:00
    ui.clock7 = st.phase === "done" ? null : segClock(leClock(st.phase === "play" ? leClamp(gameT(), 0, limit()) : 0, limit()));
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", LE_ICON, " ", leName()), ui.clock7 && ui.clock7.el));
    if (st.phase === "done") { LeAudio.engine(false); return show(head, result()); }
    if (st.phase === "lobby") return show(head, lobby());
    ui.hud = { pos: h("b.le-pos"), lap: h("span.le-lap"), clock: h("span.le-clock"), left: h("span.le-left") };
    const top = h("div.le-top", ui.hud.pos, ui.hud.lap, ui.hud.clock, ui.hud.left);
    ui.board = h("div.le-board");
    const teamTag = tm ? h("span.le-teamtag", { style: { "--tc": tm.color } }, leFlagEl(tm.country), " #" + tm.num, " ", C(tm.name)) : null;
    if (mode === "stop" || mode === "pit") {                   // the stop: mine to do – or the partner's, live
      const stp = tm.stop, mine = mode === "stop";
      ui.cv = null;
      ui.panel = stopPanel(stp, mine);
      const who = mine ? h("div.le-change", "🔧 ", T("Your stop – then you drive!"))
        : h("div.le-change", "👀 ", I18N.tr(stp.jobs ? T("{0} does the stop and drives next") : T("{0} drives next")).replace("{0}", pName(stp.next)));
      const pithead = h("div.le-pithead", h("strong", "🅿️ ", I18N.tr(T("Pit stop {0}")).replace("{0}", stp.n)), teamTag);
      if (mine) show(head, pithead, who, ui.panel.el);
      else { ui.crowd = crowd(tm); show(head, top, pithead, who, ui.panel.el, ui.crowd, lapBoard(tm)); }
      stopTick(gameT());
      drawBoard();
      return;
    }
    const cv = h("canvas.le-canvas"), wrap = h("div.le-wrap" + (mode === "drive" || introOn ? ".le-big" : ".le-tv"), cv);
    ui.cv = { el: cv, ctx: cv.getContext("2d"), wrap, w: 0, h: 0, dpr: 0 };
    wrap.addEventListener("pointerdown", () => { if (gameT() < 0 && !introSkip) introSkip = true; });       // a tap skips the intro
    // the lap times and the gaps: this lap, the team's best lap, to the car ahead / behind
    const times = () => {
      Object.assign(ui.hud, { cur: h("span.le-cur"), best: h("span.le-bestlap"), ahead: h("span.le-gapa"), behind: h("span.le-gapb") });
      return h("div.le-times", { "aria-label": I18N.tr(T("Lap times")) }, ui.hud.cur, ui.hud.best, ui.hud.ahead, ui.hud.behind);
    };
    if (mode === "drive") {
      // the driver: the picture over the full height, only the header above it. On the picture the speedometer, the
      // position card, the minimap and the corner sign; the controls (joystick, handbrake, A / M, the shifter and the
      // paddles) only when usable – hidden on the grid, at a stop, fading in at the green light / the pit exit
      ui.hud = {};
      ui.hud.gears = h("button.le-am", { type: "button", "aria-pressed": "false", "aria-label": I18N.tr(T("Gears: automatic or manual (H shifter)")),
        title: I18N.tr(T("Gears: automatic or manual (H shifter)")), onclick: e => { e.stopPropagation(); const c = predicted(); if (c) input("m", c.man ? 0 : 1); } },
        h("span.le-ama", "A"), h("span.le-amm", "M"));
      const [joy, hint] = joystick();
      ui.joy = joy;
      ui.shift = shifter();
      ui.shift.el.hidden = !(tm && tm.car && tm.car.man);
      ui.hb = handbrake();
      wrap.classList.add("le-joywrap", "le-ctloff");
      wrap.append(joy, hint, h("div.le-gearzone", ui.hb, h("div.le-gearrow", ui.hud.gears, ui.shift.el)));
      joy.classList.toggle("le-jgas", thrLocal > 0); joy.classList.toggle("le-jbrake", thrLocal < 0);
      show(head, wrap);
    } else if (mode === "rest") {                              // a break: the team's car on TV, my stop comes when I drive next
      ui.eta = h("div.le-eta"); ui.etaTxt = h("span.small.le-etatxt"); ui.cast = h("span.le-cast");
      const next = tm.next === myId && tm.members.length > 1 ? h("span.le-nextme", "🏎️ ", T("You drive next!")) : null;
      show(head, top, ui.board, h("div.le-role", "☕ ", T("Break"), " · ", C(pName(tm.driver), "span.small"), " 🏎️", teamTag),
        introOn ? null : times(), wrap, h("div.le-etarow" + (introOn ? ".le-introrow" : ""), ui.eta, ui.etaTxt, next), introOn ? null : h("div.le-castrow", "📡 ", ui.cast),
        introOn ? null : h("p.small.muted.center.le-resthint", tm.next === myId ? T("At the next stop you do the pit stop on your phone – then you drive.") : T("Watch your team's car – the next driver does the stop.")));
      restTick(gameT());
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
    const roles = h("p.small", "🔄 ", T("After every lap the car comes into the pits: the next person of the team does the stop on their phone and drives on – the one who came in has a break."));
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
      : [h("p.muted", T("Short laps and a pit stop after every lap: the next driver of the team does the stop – battery, tyres – and drives on.")),
         gameStartRow(() => langstreckeStartDialog(true, () => go("langstrecke")), () => langstreckeStartDialog(false, () => go("langstrecke")))]);
}
