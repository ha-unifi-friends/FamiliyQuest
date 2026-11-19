// ---------------------------------------------------------------- 💡 Code Workshop (familyquest/codelab.py)
// Block programming for children, made for a phone in portrait: the stage on top (480 × 360, 0/0 in the middle,
// collapsible), the code as a vertical indented LIST (nesting = a coloured bracket), an insertion caret (tap a gap) and
// a drawer with big block cards (tap = insert at the caret). Long press on a block: a menu (duplicate, disable, move,
// delete) – or keep holding and drag it (with everything inside) to another gap. Values with a number pad and pickers.
// The engine is our own small interpreter (no eval, no JS of the child): every script is a cooperative thread
// (a generator) that yields once per frame in loops and waits; ▶ Start / ⏹ / 🐢 slow motion (the running block lights
// up) and 👣 step by step in the puzzles. Puzzles run on a grid (CwEngine with `grid`) with the rules of codelab.py
// `simulate` – the server checks a solution again.
"use strict";

const CW_W = 480, CW_H = 360, CW_BASE = 72;            // stage size; a sprite at 100 % is 72 × 72
const CW_MAX_SPRITES = 12, CW_MAX_THREADS = 100, CW_MAX_STEPS = 1000, CW_TICK_BUDGET = 2000;
// categories: icon, name, colour (own colours of the workshop)
const CW_CAT = () => ({
  event: ["⚡", T("Triggers"), "#d6336c"], motion: ["🏃", T("Motion"), "#1098ad"], looks: ["🎨", T("Looks"), "#ae3ec9"],
  control: ["🔁", T("Control"), "#2b8a3e"], sensing: ["❓", T("Sensing"), "#e67700"] });
// op: [category, kind (hat | cmd | c: with a body | e: body and else | bool | num), label, [[slot, type, default], …] in
// the order of {0} {1} … in the label] – the same blocks as codelab.py OPS
const CW_OPS = {
  ev_start: ["event", "hat", T("when ▶ Start is pressed"), []],
  ev_tap: ["event", "hat", T("when this sprite is tapped"), []],
  ev_key: ["event", "hat", T("when arrow {0} is pressed"), [["key", "key", "right"]]],
  ev_msg: ["event", "hat", T("when I receive ✉️ {0}"), [["msg", "msg", ""]]],
  broadcast: ["event", "cmd", T("send ✉️ {0} to all"), [["msg", "msg", ""]]],
  move: ["motion", "cmd", T("move {0} steps"), [["n", "num", 10]]],
  turn_r: ["motion", "cmd", T("turn ↻ {0} degrees"), [["deg", "num", 15]]],
  turn_l: ["motion", "cmd", T("turn ↺ {0} degrees"), [["deg", "num", 15]]],
  goto_xy: ["motion", "cmd", T("go to x: {0} y: {1}"), [["x", "num", 0], ["y", "num", 0]]],
  goto: ["motion", "cmd", T("go to {0}"), [["to", "target", "_random"]]],
  glide: ["motion", "cmd", T("glide {0} seconds to x: {1} y: {2}"), [["secs", "num", 1], ["x", "num", 0], ["y", "num", 0]]],
  point: ["motion", "cmd", T("point in direction {0}"), [["dir", "dir", 90]]],
  change_x: ["motion", "cmd", T("change x by {0}"), [["n", "num", 10]]],
  change_y: ["motion", "cmd", T("change y by {0}"), [["n", "num", 10]]],
  bounce: ["motion", "cmd", T("if on edge, bounce"), []],
  say: ["looks", "cmd", T("say {0} for {1} seconds"), [["text", "text", T("Hello!")], ["secs", "num", 2]]],
  think: ["looks", "cmd", T("think {0} for {1} seconds"), [["text", "text", T("Hmm …")], ["secs", "num", 2]]],
  costume: ["looks", "cmd", T("switch costume to {0}"), [["c", "costume", 1]]],
  next_costume: ["looks", "cmd", T("next costume"), []],
  backdrop: ["looks", "cmd", T("switch backdrop to {0}"), [["b", "backdrop", 1]]],
  size_add: ["looks", "cmd", T("change size by {0}"), [["n", "num", 10]]],
  size_set: ["looks", "cmd", T("set size to {0} %"), [["n", "num", 100]]],
  show: ["looks", "cmd", T("show"), []],
  hide: ["looks", "cmd", T("hide"), []],
  repeat: ["control", "c", T("repeat {0} times"), [["n", "num", 10]]],
  forever: ["control", "c", T("repeat forever"), []],
  if: ["control", "c", T("if {0} then"), [["cond", "bool", null]]],
  if_else: ["control", "e", T("if {0} then"), [["cond", "bool", null]]],
  wait: ["control", "cmd", T("wait {0} seconds"), [["secs", "num", 1]]],
  wait_until: ["control", "cmd", T("wait until {0}"), [["cond", "bool", null]]],
  stop: ["control", "cmd", T("stop everything"), []],
  touching: ["sensing", "bool", T("touching {0}?"), [["what", "touch", "_edge"]]],
  blocked: ["sensing", "bool", T("way blocked?"), []],
  random: ["sensing", "num", T("random number {0} to {1}"), [["a", "num", 1], ["b", "num", 10]]],
  eq: ["sensing", "bool", "{0} = {1}", [["a", "num", 0], ["b", "num", 0]]],
  lt: ["sensing", "bool", "{0} < {1}", [["a", "num", 0], ["b", "num", 10]]],
  gt: ["sensing", "bool", "{0} > {1}", [["a", "num", 0], ["b", "num", 10]]],
  and: ["sensing", "bool", T("{0} and {1}"), [["a", "bool", null], ["b", "bool", null]]],
  or: ["sensing", "bool", T("{0} or {1}"), [["a", "bool", null], ["b", "bool", null]]],
  not: ["sensing", "bool", T("not {0}"), [["a", "bool", null]]],
};
const CW_FREE_OPS = Object.keys(CW_OPS).filter(k => k !== "blocked");
const CW_KEYS = { left: "←", right: "→", up: "↑", down: "↓" };
const CW_KEY_DIR = { left: -90, right: 90, up: 0, down: 180 };
// own sprites (img/codelab/<key>-<n>.svg, codelab.py SPRITES): key → [name, costumes, rotation style]
const CW_SPRITES = () => ({ fox: [T("Fox"), 3, "lr"], cat: [T("Cat"), 3, "lr"], dog: [T("Dog"), 2, "lr"], robot: [T("Robot"), 3, "lr"],
  ball: [T("Ball"), 2, "all"], star: [T("Star"), 2, "all"], rocket: [T("Rocket"), 3, "all"], fish: [T("Fish"), 2, "lr"],
  dragon: [T("Dragon"), 3, "lr"], apple: [T("Apple"), 2, "none"], ghost: [T("Ghost"), 2, "lr"], bird: [T("Bird"), 3, "lr"],
  car: [T("Car"), 2, "lr"], frog: [T("Frog"), 2, "lr"], bee: [T("Bee"), 2, "lr"], stone: [T("Stone"), 2, "none"] });
// backdrops: the scenes of the library (img/stories) and the rooms of the adventure games (img/adventure)
const CW_ROOMS = { tower: T("Tower room"), library: T("Library"), hall: T("Stone hall"), hallway: T("Hallway"), cabin: T("Spaceship cabin"),
  corridor: T("Spaceship corridor"), bridge: T("Spaceship bridge"), engine: T("Engine room"), storage: T("Storage room"), dark: T("Dark room") };
const cwBackdrops = () => ({ ...(typeof SB_BGS === "function" ? SB_BGS() : {}), ...CW_ROOMS });
const cwBgUrl = bd => !bd ? null : typeof bd === "object" ? (bd.k === "svg" ? cwSvgUrl(bd.v) : null)
  : (CW_ROOMS[bd] ? "img/adventure/" : "img/stories/") + bd + ".svg";
const cwSvgUrl = svg => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
const cwCostumeUrl = c => !c ? null : c.k === "lib" ? "img/codelab/" + c.v + ".svg" : c.k === "svg" ? cwSvgUrl(c.v) : null;
const cwClamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const cwDir = d => { d = ((d + 180) % 360 + 360) % 360 - 180; return d === -180 ? 180 : d; };

// ---------------------------------------------------------------- the engine
const CW_BLK = 1, CW_FRAME = 2;
class CwEngine {
  /** proj: {stage, sprites}; opts.grid: a puzzle level (cols, rows, fox, star, stones) – the first sprite is the fox;
   *  opts.seq: scripts run one after the other (puzzles); onEnd(why) when a puzzle ends; rnd: Math.random */
  constructor(proj, opts = {}) {
    this.opts = opts;
    this.rnd = opts.rnd || Math.random;
    this.grid = opts.grid || null;
    this.seq = !!opts.seq || !!this.grid;
    this.mode = "normal";                          // normal | slow | step
    this.now = 0;
    this.stage = proj.stage || { backdrops: [], bd: 0 };
    this.bd = this.stage.bd || 0;
    this.sprites = (proj.sprites || []).map(s => ({ id: s.id, name: s.name, costumes: s.costumes, c: s.c || 0, x: s.x || 0, y: s.y || 0,
      dir: s.dir == null ? 90 : s.dir, size: s.size || 100, show: s.show !== false, rot: s.rot || "all", say: null, scripts: s.scripts || [], gx: null }));
    this.threads = [];
    this.on = false;
    this.ended = null;
    this.notice = null;                            // a hint for the child («this loop runs for ever …»)
    this.steps = 0;
    if (this.grid) this._gridInit();
  }
  // ---------- grid (puzzles): the same rules as codelab.py Grid
  _gridInit() {
    const g = this.grid, f = this.sprites[0];
    this.g = { c: g.fox[0], r: g.fox[1], dir: cwSnap(g.fox[2]) };
    if (f) { const [x, y] = this.cellXY(this.g.c, this.g.r); Object.assign(f, { x, y, dir: this.g.dir, size: 100 * Math.min(CW_W / g.cols, CW_H / g.rows) * 0.92 / CW_BASE }); }
  }
  cellXY(c, r) { const g = this.grid; return [-CW_W / 2 + (c + 0.5) * CW_W / g.cols, CW_H / 2 - (r + 0.5) * CW_H / g.rows]; }
  ahead(back = false) { const d = { 0: [0, -1], 90: [1, 0], 180: [0, 1], "-90": [-1, 0] }[this.g.dir], k = back ? -1 : 1; return [this.g.c + d[0] * k, this.g.r + d[1] * k]; }
  isStone(c, r) { return (this.grid.stones || []).some(s => s[0] === c && s[1] === r); }
  free(c, r) { return c >= 0 && r >= 0 && c < this.grid.cols && r < this.grid.rows && !this.isStone(c, r); }
  _step() { if (!this.grid) return; if (++this.steps > CW_MAX_STEPS) this.end("forever"); }
  end(why) {
    if (this.ended) return;
    this.ended = why;
    this.threads.forEach(t => { t.done = true; });
    this.threads = [];
    if (this.opts.onEnd) this.opts.onEnd(why);
  }
  // ---------- running
  start() {
    this.stop(false);
    this.on = true; this.ended = null; this.steps = 0;
    this.trigger("start");
  }
  stop(clear = true) {
    this.threads.forEach(t => { t.done = true; });
    this.threads = [];
    this.on = false;
    if (clear) this.sprites.forEach(s => { s.say = null; });
  }
  busy() { return this.threads.some(t => !t.done); }
  hats(kind, arg, sp) {
    const out = [];
    for (const s of this.sprites) {
      if (sp && s !== sp) continue;
      for (const h of s.scripts) {
        if (h.off) continue;
        const ok = (kind === "start" && h.op === "ev_start") || (kind === "tap" && h.op === "ev_tap") ||
          (kind === "key" && h.op === "ev_key" && h.args.key === arg) ||
          (kind === "msg" && h.op === "ev_msg" && String(h.args.msg).toLowerCase() === String(arg).toLowerCase());
        if (ok) out.push([s, h]);
      }
    }
    return out;
  }
  /** Start the scripts of an event: ▶ start, a tapped sprite, an arrow, a message. Keys do not restart a running script. */
  trigger(kind, arg = null, sp = null) {
    if (!this.on) return 0;
    let n = 0;
    for (const [s, h] of this.hats(kind, arg, sp)) {
      const old = this.threads.find(t => t.hat === h && !t.done);
      if (old && kind === "key") continue;
      if (old) old.done = true;
      if (this.threads.length >= CW_MAX_THREADS) break;
      const t = { sp: s, hat: h, cur: null, wait: 0, paused: false, done: false, spins: 0, waited: false };
      t.gen = this.runList(t, h.body || []);
      this.threads.push(t);
      n++;
    }
    this.threads = this.threads.filter(t => !t.done);
    return n;
  }
  step() { this.threads.forEach(t => { t.paused = false; }); }          // step mode: every paused thread runs one block
  curIds() { return new Set(this.threads.filter(t => !t.done && t.cur).map(t => t.cur)); }
  /** One frame at time `now` (ms): every thread runs until it yields a frame (a loop round, a wait, a glide …). */
  tick(now) {
    this.now = now;
    if (!this.on) return;
    let budget = CW_TICK_BUDGET * 4;
    const list = this.seq ? this.threads.filter(t => !t.done).slice(0, 1) : this.threads.slice();
    for (const t of list) {
      if (t.done || t.paused || t.wait > now) continue;
      let n = 0;
      for (;;) {
        if (this.ended || t.done) break;
        const r = t.gen.next();
        if (r.done) { t.done = true; t.cur = null; break; }
        if (r.value === CW_FRAME) break;
        if (++n > CW_TICK_BUDGET || --budget < 0) break;           // runaway protection: the next frame goes on
        if (this.mode === "slow") { t.wait = now + 450; break; }
        if (this.mode === "step") { t.paused = true; break; }
      }
    }
    this.threads = this.threads.filter(t => !t.done);
    if (this.grid && !this.ended && !this.threads.length && !this.grid.inputs) this.end("short");
  }
  // ---------- values
  val(t, v) {
    if (!v || typeof v !== "object") return v;
    const a = v.args || {};
    switch (v.op) {
      case "random": {
        let x = this.num(t, a.a), y = this.num(t, a.b);
        if (x > y) [x, y] = [y, x];
        return Number.isInteger(x) && Number.isInteger(y) ? x + Math.floor(this.rnd() * (y - x + 1)) : x + this.rnd() * (y - x);
      }
      case "eq": return this.num(t, a.a) === this.num(t, a.b);
      case "lt": return this.num(t, a.a) < this.num(t, a.b);
      case "gt": return this.num(t, a.a) > this.num(t, a.b);
      case "and": return !!this.val(t, a.a) && !!this.val(t, a.b);
      case "or": return !!this.val(t, a.a) || !!this.val(t, a.b);
      case "not": return !this.val(t, a.a);
      case "touching": return this.touching(t.sp, a.what);
      case "blocked": return this.grid ? !this.free(...this.ahead()) : false;
    }
    return 0;
  }
  num(t, v) { const n = Number(this.val(t, v)); return Number.isFinite(n) ? n : 0; }
  box(s, inset = 0.8) {
    const half = CW_BASE * s.size / 200 * inset;
    return [s.x - half, s.x + half, s.y - half, s.y + half];
  }
  touching(s, what) {
    if (!s.show) return false;
    const [x0, x1, y0, y1] = this.box(s);
    if (what === "_edge") return x0 < -CW_W / 2 || x1 > CW_W / 2 || y0 < -CW_H / 2 || y1 > CW_H / 2;
    const o = this.sprites.find(x => x.id === what);
    if (!o || o === s || !o.show) return false;
    const [a0, a1, b0, b1] = this.box(o);
    return x0 < a1 && a0 < x1 && y0 < b1 && b0 < y1;
  }
  fence(s) { s.x = cwClamp(s.x, -CW_W / 2 - 20, CW_W / 2 + 20); s.y = cwClamp(s.y, -CW_H / 2 - 20, CW_H / 2 + 20); }
  // ---------- blocks
  *runList(t, list) {
    for (const b of list) {
      if (b.off) continue;
      yield* this.exec(t, b);
      if (t.done) return;
    }
  }
  *waitSecs(t, secs) {
    const until = this.now + cwClamp(secs, 0, 3600) * 1000;
    t.waited = true;
    while (this.now < until) yield CW_FRAME;
  }
  *loopRound(t) {
    this._step();
    if (!t.waited && ++t.spins === 5000 && !this.grid) this.notice = "fast";
    t.waited = false;
    yield CW_FRAME;
  }
  *exec(t, b) {
    t.cur = b.id;
    this._step();
    yield CW_BLK;
    if (this.ended) return;
    const s = t.sp, a = b.args || {};
    switch (b.op) {
      case "move": {
        const n = this.num(t, a.n);
        if (this.grid && s === this.sprites[0]) { yield* this.gridMove(t, n); break; }
        const r = s.dir * Math.PI / 180, k = v => Math.round(v * 1e9) / 1e9;          // 90° moves stay whole numbers
        s.x += n * k(Math.sin(r)); s.y += n * k(Math.cos(r)); this.fence(s);
        break;
      }
      case "turn_r": case "turn_l": {
        const d = this.num(t, a.deg) * (b.op === "turn_r" ? 1 : -1);
        if (this.grid && s === this.sprites[0]) { this.g.dir = cwSnap(this.g.dir + d); s.dir = this.g.dir; }
        else s.dir = cwDir(s.dir + d);
        break;
      }
      case "point":
        if (this.grid && s === this.sprites[0]) { this.g.dir = cwSnap(this.num(t, a.dir)); s.dir = this.g.dir; }
        else s.dir = cwDir(this.num(t, a.dir));
        break;
      case "goto_xy": s.x = this.num(t, a.x); s.y = this.num(t, a.y); this.fence(s); break;
      case "goto": {
        const o = this.sprites.find(x => x.id === a.to);
        if (o) { s.x = o.x; s.y = o.y; } else { s.x = Math.round(this.rnd() * 440 - 220); s.y = Math.round(this.rnd() * 320 - 160); }
        break;
      }
      case "glide": {
        const secs = cwClamp(this.num(t, a.secs), 0, 3600), x1 = this.num(t, a.x), y1 = this.num(t, a.y), x0 = s.x, y0 = s.y, t0 = this.now;
        t.waited = true;
        while (this.now < t0 + secs * 1000) {
          const p = secs ? (this.now - t0) / (secs * 1000) : 1;
          s.x = x0 + (x1 - x0) * p; s.y = y0 + (y1 - y0) * p;
          yield CW_FRAME;
        }
        s.x = x1; s.y = y1; this.fence(s);
        break;
      }
      case "change_x": s.x += this.num(t, a.n); this.fence(s); break;
      case "change_y": s.y += this.num(t, a.n); this.fence(s); break;
      case "bounce": {
        const [x0, x1, y0, y1] = this.box(s, 1);
        if (x0 < -CW_W / 2 || x1 > CW_W / 2) { s.dir = cwDir(-s.dir); s.x += x0 < -CW_W / 2 ? -CW_W / 2 - x0 : CW_W / 2 - x1; }
        if (y0 < -CW_H / 2 || y1 > CW_H / 2) { s.dir = cwDir(180 - s.dir); s.y += y0 < -CW_H / 2 ? -CW_H / 2 - y0 : CW_H / 2 - y1; }
        break;
      }
      case "say": case "think": {
        const bubble = { text: String(this.val(t, a.text) ?? "").slice(0, 120), think: b.op === "think" };
        s.say = bubble.text ? bubble : null;
        const secs = this.num(t, a.secs);
        if (secs > 0) { yield* this.waitSecs(t, secs); if (s.say === bubble) s.say = null; }
        break;
      }
      case "costume": s.c = cwClamp(Math.round(this.num(t, a.c)) - 1, 0, s.costumes.length - 1); break;
      case "next_costume": s.c = (s.c + 1) % Math.max(1, s.costumes.length); break;
      case "backdrop": this.bd = cwClamp(Math.round(this.num(t, a.b)) - 1, 0, Math.max(0, (this.stage.backdrops || []).length - 1)); break;
      case "size_add": s.size = cwClamp(s.size + this.num(t, a.n), 5, 500); break;
      case "size_set": s.size = cwClamp(this.num(t, a.n), 5, 500); break;
      case "show": s.show = true; break;
      case "hide": s.show = false; break;
      case "repeat": {
        const n = cwClamp(Math.round(this.num(t, a.n)), 0, 100000);
        for (let i = 0; i < n && !t.done && !this.ended; i++) { yield* this.runList(t, b.body || []); yield* this.loopRound(t); }
        break;
      }
      case "forever":
        while (!t.done && !this.ended) { yield* this.runList(t, b.body || []); yield* this.loopRound(t); }
        break;
      case "if": if (this.val(t, a.cond)) yield* this.runList(t, b.body || []); break;
      case "if_else": yield* this.runList(t, this.val(t, a.cond) ? b.body || [] : b.else || []); break;
      case "wait": yield* this.waitSecs(t, this.num(t, a.secs)); break;
      case "wait_until": t.waited = true; while (!this.val(t, a.cond) && !t.done) yield CW_FRAME; break;
      case "broadcast": this.trigger("msg", a.msg); break;
      case "stop": if (this.grid) this.threads.forEach(x => { x.done = true; }); else this.stop(false); t.done = true; break;
    }
  }
  /** Puzzles: a move goes cell by cell (gliding) – a stone or the edge ends the try, the star wins. */
  *gridMove(t, n) {
    n = Math.round(cwClamp(n, -20, 20));
    const s = this.sprites[0];
    for (let i = 0; i < Math.abs(n); i++) {
      const [c, r] = this.ahead(n < 0);
      if (!(c >= 0 && r >= 0 && c < this.grid.cols && r < this.grid.rows)) { yield* this.bump(t, s, c, r); return this.end("edge"); }
      if (this.isStone(c, r)) { yield* this.bump(t, s, c, r); return this.end("stone"); }
      const [x0, y0] = [s.x, s.y], [x1, y1] = this.cellXY(c, r), t0 = this.now, dur = this.mode === "slow" ? 500 : 260;
      this.g.c = c; this.g.r = r;
      while (this.now < t0 + dur) { const p = (this.now - t0) / dur; s.x = x0 + (x1 - x0) * p; s.y = y0 + (y1 - y0) * p; yield CW_FRAME; }
      s.x = x1; s.y = y1;
      if (c === this.grid.star[0] && r === this.grid.star[1]) return this.end("win");
    }
  }
  *bump(t, s, c, r) {                                    // a little hop towards the obstacle
    const [x1, y1] = this.cellXY(cwClamp(c, -0.4, this.grid.cols - 0.6), cwClamp(r, -0.4, this.grid.rows - 0.6));
    const [x0, y0] = [s.x, s.y], t0 = this.now;
    while (this.now < t0 + 240) { const p = Math.sin(Math.PI * (this.now - t0) / 240) * 0.35; s.x = x0 + (x1 - x0) * p; s.y = y0 + (y1 - y0) * p; yield CW_FRAME; }
    s.x = x0; s.y = y0;
  }
}
function cwSnap(d) { const k = ((Math.round(d / 90) * 90) % 360 + 360) % 360; return { 0: 0, 90: 90, 180: 180, 270: -90 }[k]; }

// ---------------------------------------------------------------- drawing the stage
const cwImgs = new Map();
function cwImg(url) {
  if (!url) return null;
  let im = cwImgs.get(url);
  if (!im) {
    if (cwImgs.size > 200) cwImgs.clear();
    im = new Image(); im.src = url; cwImgs.set(url, im);
  }
  return im.complete && im.naturalWidth ? im : null;
}
function cwWrap(ctx, text, max) {
  const words = String(text).split(/\s+/), lines = [];
  let line = "";
  for (const w of words) {
    const tryLine = line ? line + " " + w : w;
    if (ctx.measureText(tryLine).width > max && line) { lines.push(line); line = w; } else line = tryLine;
  }
  if (line) lines.push(line);
  return lines.slice(0, 5);
}
function cwBubble(ctx, s, b) {
  ctx.font = "600 15px Nunito, system-ui, sans-serif";
  const lines = cwWrap(ctx, b.text, 150), w = Math.max(...lines.map(l => ctx.measureText(l).width)) + 20, hgt = lines.length * 18 + 14;
  const top = CW_BASE * s.size / 200;
  let x = CW_W / 2 + s.x + 10, y = CW_H / 2 - s.y - top - hgt - 8;
  x = cwClamp(x, 4, CW_W - w - 4); y = cwClamp(y, 4, CW_H - hgt - 4);
  ctx.fillStyle = "#fff"; ctx.strokeStyle = "#5c5f66"; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, hgt, 12) : ctx.rect(x, y, w, hgt); ctx.fill(); ctx.stroke();
  const tx = cwClamp(CW_W / 2 + s.x, x + 12, x + w - 12), ty = y + hgt;
  if (b.think) {
    [[6, 6], [3.5, 14]].forEach(([r, d]) => { ctx.beginPath(); ctx.arc(tx - d / 2, ty + d, r, 0, 7); ctx.fill(); ctx.stroke(); });
  } else {
    ctx.beginPath(); ctx.moveTo(tx - 6, ty - 1); ctx.lineTo(tx - 10, ty + 10); ctx.lineTo(tx + 4, ty - 1); ctx.fill();
    ctx.beginPath(); ctx.moveTo(tx - 6, ty); ctx.lineTo(tx - 10, ty + 10); ctx.lineTo(tx + 4, ty); ctx.stroke();
  }
  ctx.fillStyle = "#1f2433"; ctx.textBaseline = "top";
  lines.forEach((l, i) => ctx.fillText(l, x + 10, y + 8 + i * 18));
}
/** Draw the stage of an engine into a canvas (any size, 4:3). */
function cwDraw(cv, eng) {
  const ctx = cv.getContext("2d"), k = cv.width / CW_W;
  ctx.setTransform(k, 0, 0, k, 0, 0);
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, CW_W, CW_H);
  const bd = (eng.stage.backdrops || [])[eng.bd], bim = cwImg(cwBgUrl(bd));
  if (bim) ctx.drawImage(bim, 0, 0, CW_W, CW_H);
  const g = eng.grid;
  if (g) {
    const cw = CW_W / g.cols, ch = CW_H / g.rows;
    ctx.fillStyle = "#e9f7ef"; ctx.fillRect(0, 0, CW_W, CW_H);
    for (let c = 0; c < g.cols; c++) for (let r = 0; r < g.rows; r++) if ((c + r) % 2) { ctx.fillStyle = "#d3f0de"; ctx.fillRect(c * cw, r * ch, cw, ch); }
    const draw = (key, c, r, sc = 0.9) => { const im = cwImg("img/codelab/" + key + ".svg"); if (im) ctx.drawImage(im, c * cw + cw * (1 - sc) / 2, r * ch + ch * (1 - sc) / 2, cw * sc, ch * sc); };
    (g.stones || []).forEach(s => draw("stone-1", s[0], s[1]));
    draw(eng.ended === "win" ? "star-2" : "star-1", g.star[0], g.star[1], 0.8);
  }
  eng.sprites.forEach((s, i) => {
    if (!s.show) return;
    const im = cwImg(cwCostumeUrl(s.costumes[s.c] || s.costumes[0]));
    const half = CW_BASE * s.size / 200;
    ctx.save();
    ctx.translate(CW_W / 2 + s.x, CW_H / 2 - s.y);
    if (g && i === 0) {                                  // puzzles: where the fox looks
      const a = (s.dir - 90) * Math.PI / 180;
      ctx.save(); ctx.rotate(a); ctx.fillStyle = "rgba(214,51,108,.85)";
      ctx.beginPath(); ctx.moveTo(half + 12, 0); ctx.lineTo(half + 1, -8); ctx.lineTo(half + 1, 8); ctx.fill(); ctx.restore();
    }
    if (s.rot === "all") ctx.rotate((s.dir - 90) * Math.PI / 180);
    else if (s.rot === "lr" && s.dir < 0) ctx.scale(-1, 1);
    if (im) ctx.drawImage(im, -half, -half, half * 2, half * 2);
    else { ctx.fillStyle = "#adb5bd"; ctx.beginPath(); ctx.arc(0, 0, half * 0.6, 0, 7); ctx.fill(); }
    ctx.restore();
  });
  eng.sprites.forEach(s => { if (s.show && s.say) cwBubble(ctx, s, s.say); });
}

// ---------------------------------------------------------------- block helpers
const cwKind = op => (CW_OPS[op] || [])[1];
const cwCatOf = op => (CW_OPS[op] || ["control"])[0];
const cwColor = op => CW_CAT()[cwCatOf(op)][2];
const cwHasBody = op => ["c", "e"].includes(cwKind(op)) || cwKind(op) === "hat";
let cwSeq = 0;
const cwNewId = () => "b" + Date.now().toString(36).slice(-4) + (++cwSeq).toString(36);
function cwWalk(list, fn) { for (const b of list || []) { fn(b); cwWalk(b.body, fn); cwWalk(b.else, fn); } }
/** A compact block (templates): cwB(op, {args}, [body], [else]) – missing slots get their defaults. */
function cwB(op, args = {}, body = null, els = null) {
  const def = CW_OPS[op], b = { id: cwNewId(), op, args: {} };
  for (const [k, , d] of def[3]) b.args[k] = k in args ? args[k] : d;
  if (cwHasBody(op)) b.body = body || [];
  if (def[1] === "e") b.else = els || [];
  return b;
}
/** Every block of a list with an id (programs from the server or the levels file come without ids sometimes). */
function cwIds(list, seen = new Set()) {
  cwWalk(list, b => { if (!b.id || seen.has(b.id)) b.id = cwNewId(); seen.add(b.id); if (cwHasBody(b.op) && !b.body) b.body = []; if (cwKind(b.op) === "e" && !b.else) b.else = []; });
  return list;
}
const cwCount = list => { let n = 0; cwWalk(list, b => { if (cwKind(b.op) !== "hat") n++; }); return n; };
const cwClone = x => JSON.parse(JSON.stringify(x));
function cwReId(list) { cwWalk(list, b => { b.id = cwNewId(); }); return list; }
const cwFmt = n => { const v = Math.round(Number(n) * 1000) / 1000; return Number.isFinite(v) ? String(v).replace("-", "−") : "0"; };
const cwLabel = op => I18N.tr(CW_OPS[op][2]);

// ---------------------------------------------------------------- pickers (modal dialogs)
function cwPick(title, items, { cols = 3, extra = null } = {}) {
  return new Promise(resolve => {
    let got;
    const m = modal(h("div.cw-pick", h("h3", title),
      h("div.cw-pick-grid", { style: { "--cols": cols } }, ...items.map(it => h("button.cw-pick-it" + (it.on ? ".on" : ""), { type: "button",
        onclick: () => { got = it.value; m.close(); } }, it.img ? h("img", { src: it.img, alt: "" }) : null, it.icon ? h("span.cw-pick-ic", it.icon) : null,
        it.label != null ? h("span.cw-pick-l", it.notr ? { translate: "no" } : {}, it.label) : null))),
      extra ? extra(v => { got = v; m.close(); }) : null,
      h("div.row.cw-pick-foot", h("button.btn.ghost", { type: "button", onclick: () => m.close() }, T("Cancel")))), { onClose: () => resolve(got) });
  });
}

/** The big number pad (with arrows for a direction) – resolves with a number, a reporter block or undefined. */
function cwNumPad(value, { dir = false, reporters = [] } = {}) {
  return new Promise(resolve => {
    let text = typeof value === "number" ? String(value) : "0", fresh = true, got;
    const show = h("div.cw-np-show", { translate: "no" }, text);
    const set = v => { text = v; show.textContent = text.replace("-", "−"); };
    const key = k => {
      if (k === "⌫") return set(fresh ? "0" : text.length > 1 ? text.slice(0, -1) : "0"), fresh = false;
      if (k === "±") { fresh = false; return set(text.startsWith("-") ? text.slice(1) : text === "0" ? "-" : "-" + text); }
      if (k === ".") { if (fresh) { fresh = false; return set("0."); } return text.includes(".") ? null : set(text + "."); }
      if (fresh || text === "0") { fresh = false; return set(text === "-" ? "-" + k : k); }
      if (text.replace(/[-.]/g, "").length >= 7) return null;
      if (text === "-0") return set("-" + k);
      set(text + k);
    };
    const ok = () => { const n = Number(text); got = Number.isFinite(n) ? n : 0; m.close(); };
    const dirs = dir ? h("div.cw-np-dirs", ...[[-45, "↖"], [0, "↑"], [45, "↗"], [-90, "←"], [null, "•"], [90, "→"], [-135, "↙"], [180, "↓"], [135, "↘"]].map(([d, ic]) =>
      d == null ? h("span.cw-np-mid", "🧭") : h("button.cw-np-dir", { type: "button", "aria-label": String(d), onclick: () => { got = d; m.close(); } }, ic))) : null;
    const m = modal(h("div.cw-np", dirs, show,
      h("div.cw-np-keys", ...["7", "8", "9", "4", "5", "6", "1", "2", "3", "±", "0", "."].map(k => h("button.cw-np-k", { type: "button", onclick: () => key(k) }, k.replace("±", "+/−")))),
      h("div.cw-np-row", h("button.btn.ghost", { type: "button", "aria-label": T("Delete"), onclick: () => key("⌫") }, "⌫"),
        h("button.btn.good.cw-np-ok", { type: "button", onclick: ok }, "✓ ", T("OK"))),
      reporters.length ? h("div.cw-np-rep", h("span.small.muted", T("or a value block:")), ...reporters.map(op =>
        h("button.cw-card.cw-mini", { type: "button", style: { "--c": cwColor(op) }, onclick: () => { got = cwB(op); delete got.id; m.close(); } }, cwLabelPreview(cwB(op))))) : null),
      { onClose: () => resolve(got) });
    m.box.addEventListener("keydown", e => {
      if (/^[0-9]$/.test(e.key) || e.key === ".") key(e.key);
      else if (e.key === "-") key("±");
      else if (e.key === "Backspace") key("⌫");
      else if (e.key === "Enter") { e.preventDefault(); ok(); }
    });
  });
}
/** A label with its values as plain text (cards, previews) – the slots of reporters inside too. */
function cwLabelPreview(b, sprites = []) {
  const parts = cwLabel(b.op).split(/\{(\d)\}/);
  return h("span.cw-lbl", { translate: "no" }, ...parts.map((p, i) => {
    if (i % 2 === 0) return p;
    const [k, type] = CW_OPS[b.op][3][+p];
    return h("span.cw-val", cwValText(b.args[k], type, sprites));
  }));
}
function cwValText(v, type, sprites = [], costumes = []) {
  if (v && typeof v === "object") return "( " + I18N.tr(CW_OPS[v.op][2]).replace(/\{(\d)\}/g, (_, i) => { const [k, t] = CW_OPS[v.op][3][+i]; return cwValText(v.args[k], t, sprites); }) + " )";
  switch (type) {
    case "num": case "dir": return cwFmt(v);
    case "text": return "«" + String(v ?? "") + "»";
    case "key": return CW_KEYS[v] || "→";
    case "msg": return String(v || "");
    case "costume": case "backdrop": return "#" + (v || 1);
    case "target": return v === "_random" ? "🎲 " + I18N.tr(T("random place")) : (sprites.find(s => s.id === v) || {}).name || "?";
    case "touch": return v === "_edge" ? I18N.tr(T("edge")) : (sprites.find(s => s.id === v) || {}).name || "?";
    case "bool": return "◇";
  }
  return String(v ?? "");
}

// ---------------------------------------------------------------- the editor
/** The workshop screen: stage, sprite tabs, code list and the block drawer.
 *  mode «free» (own program, autosave), «puzzle» (a level, one fox) or «play» (a program of somebody else: run only). */
function cwEditor(o) {
  const ed = { mode: o.mode, proj: o.proj, cur: 0, caret: null, undo: [], redo: [], eng: null, running: false, slow: false,
    drawer: o.mode !== "play", cat: "event", collapsed: false, inputs: [], title: o.title || "", saveTimer: null, saving: null, dirty: false };
  const level = o.level || null, puzzle = ed.mode === "puzzle", play = ed.mode === "play";
  const pal = puzzle ? Object.fromEntries(level.palette.map(p => [p.op, p])) : null;
  const allowed = op => puzzle ? !!pal[op] : CW_FREE_OPS.includes(op);
  const fixed = (op, k) => puzzle && pal[op] && (pal[op].fixed || []).includes(k);
  const root = h("div.cw-full.cw-root" + (puzzle ? ".cw-puzzle" : "") + (play ? ".cw-play" : ""), { role: "application" });
  const sp = () => ed.proj.sprites[ed.cur];
  const scripts = () => (sp() || { scripts: [] }).scripts;

  // ---------- changes, undo, saving
  const snapshot = () => JSON.stringify(ed.proj);
  const change = (fn, { keepCaret = true } = {}) => {
    if (play) return;
    ed.undo.push(snapshot()); if (ed.undo.length > 80) ed.undo.shift(); ed.redo.length = 0;
    fn();
    if (!keepCaret) ed.caret = null;
    after();
  };
  const after = () => { ed.eng = null; renderCode(); renderTabs(); renderInfo(); updateUndo(); queueSave(); };
  const history = (from, to) => {
    if (!from.length) return;
    to.push(snapshot()); ed.proj = JSON.parse(from.pop());
    ed.cur = Math.min(ed.cur, ed.proj.sprites.length - 1); ed.caret = null;
    after();
  };
  const queueSave = () => {
    if (play || !o.save) return;
    ed.dirty = true; status("…");
    clearTimeout(ed.saveTimer);
    ed.saveTimer = setTimeout(saveNow, 1200);
  };
  const saveNow = async () => {
    clearTimeout(ed.saveTimer);
    if (!ed.dirty || !o.save) return;
    ed.dirty = false;
    try { await (ed.saving = o.save(ed.proj, ed.title)); status("✓"); }
    catch (e) { ed.dirty = true; status("⚠️"); toast(e.message, "bad"); }
  };
  const statusEl = h("span.cw-status", { "aria-live": "polite" });
  const status = t => { statusEl.textContent = t; };

  // ---------- finding blocks
  const find = (id, list = scripts(), parent = null, key = null) => {
    for (let i = 0; i < list.length; i++) {
      const b = list[i];
      if (b.id === id) return { b, list, i, parent, key };
      for (const k of ["body", "else"]) if (b[k]) { const r = find(id, b[k], b, k); if (r) return r; }
    }
    return null;
  };
  const caretList = () => {
    const c = ed.caret;
    if (!c) return null;
    if (c.p == null) return scripts();
    const f = find(c.p);
    return f ? f.b[c.k] : null;
  };
  const inside = (outer, id) => { let hit = false; cwWalk(outer.body, b => { if (b.id === id) hit = true; }); cwWalk(outer.else, b => { if (b.id === id) hit = true; }); return hit; };
  const allMsgs = () => { const s = new Set(); ed.proj.sprites.forEach(x => cwWalk(x.scripts, b => { if (b.args && typeof b.args.msg === "string" && b.args.msg) s.add(b.args.msg); })); return [...s]; };

  // ---------- inserting
  const insert = op => {
    if (play) return;
    const kind = cwKind(op);
    if (kind === "bool" || kind === "num") return toast(I18N.tr(T("Value blocks go into a slot: tap a ◇ or a number in a block.")));
    if (puzzle && level.max && kind !== "hat" && cwCount(scripts()) >= level.max) {
      Sound.play("wrong");
      return toast(I18N.tr(T("This level allows at most {0} blocks")).replace("{0}", level.max), "bad");
    }
    if (!sp()) return;
    const b = cwB(op, puzzle && pal[op] ? pal[op].args || {} : {});
    for (const [k, type, d] of CW_OPS[op][3]) {
      if (type === "text" && typeof d === "string") b.args[k] = I18N.tr(d);
      if (type === "msg") b.args[k] = allMsgs()[0] || I18N.tr(T("go"));
      if (type === "touch" || type === "target") { const other = ed.proj.sprites.find(x => x !== sp()); if (type === "touch" && other && op === "touching") b.args[k] = other.id; }
    }
    Sound.play("tap");
    change(() => {
      if (kind === "hat") {
        const at = ed.caret && ed.caret.p == null ? ed.caret.i : scripts().length;
        scripts().splice(at, 0, b);
        ed.caret = { p: b.id, k: "body", i: 0 };
        return;
      }
      let list = caretList();
      if (!list || (ed.caret && ed.caret.p == null)) {              // no place yet: at the end of the last script (or a new ▶ script)
        if (!scripts().length) scripts().push(cwB(puzzle ? level.palette.find(p => cwKind(p.op) === "hat").op : "ev_start"));
        const last = scripts()[scripts().length - 1];
        ed.caret = { p: last.id, k: "body", i: last.body.length };
        list = last.body;
      }
      list.splice(ed.caret.i, 0, b);
      ed.caret = cwHasBody(op) ? { p: b.id, k: "body", i: 0 } : { ...ed.caret, i: ed.caret.i + 1 };
    });
    requestAnimationFrame(scrollToCaret);
  };

  // ---------- block menu and moving
  const blockMenu = id => {
    const f = find(id);
    if (!f || play) return;
    const hat = cwKind(f.b.op) === "hat";
    let m;
    const act = (fn, opt) => () => { m.close(); change(fn, opt); };
    const btn = (ic, label, fn, dis = false) => h("button.cw-menu-it", { type: "button", disabled: dis, onclick: fn }, h("span.cw-menu-ic", ic), h("span", label));
    m = modal(h("div.cw-menu", h("div.cw-menu-head", { style: { "--c": cwColor(f.b.op) } }, cwLabelPreview(f.b, ed.proj.sprites)),
      btn("⧉", T("Duplicate"), act(() => {
        if (puzzle && level.max && !hat && cwCount(scripts()) + cwCount([f.b]) > level.max) return toast(I18N.tr(T("This level allows at most {0} blocks")).replace("{0}", level.max), "bad");
        f.list.splice(f.i + 1, 0, cwReId([cwClone(f.b)])[0]);
      })),
      btn(f.b.off ? "▶" : "⏸", f.b.off ? T("Switch on") : T("Switch off"), act(() => { if (f.b.off) delete f.b.off; else f.b.off = true; })),
      btn("⬆", T("Move up"), act(() => { f.list.splice(f.i - 1, 0, f.list.splice(f.i, 1)[0]); }), f.i === 0),
      btn("⬇", T("Move down"), act(() => { f.list.splice(f.i + 1, 0, f.list.splice(f.i, 1)[0]); }), f.i === f.list.length - 1),
      btn("🗑️", hat ? T("Delete the whole script") : T("Delete"), act(() => { f.list.splice(f.i, 1); Sound.play("trash"); }, { keepCaret: false })),
      h("button.btn.ghost.cw-menu-x", { type: "button", onclick: () => m.close() }, T("Cancel"))));
  };
  const moveTo = (id, gap) => {
    const f = find(id);
    if (!f) return;
    const hat = cwKind(f.b.op) === "hat";
    if (hat !== (gap.p == null)) return toast(I18N.tr(hat ? T("A script starts on its own – drop it between two scripts.") : T("Put blocks into a script (under an event).")));
    if (gap.p === id || (gap.p && inside(f.b, gap.p))) return;
    change(() => {
      const target = gap.p == null ? scripts() : find(gap.p).b[gap.k];
      let i = gap.i;
      if (target === f.list && f.i < i) i--;
      f.list.splice(f.i, 1);
      target.splice(i, 0, f.b);
      ed.caret = gap.p == null ? { p: f.b.id, k: "body", i: f.b.body.length } : { p: gap.p, k: gap.k, i: i + 1 };
    });
  };

  // ---------- slots
  const slotOf = (b, path) => {
    const keys = path.split(".");
    let obj = b, def = null, holder = null;
    for (const k of keys) { def = CW_OPS[obj.op][3].find(x => x[0] === k); holder = obj.args; obj = obj.args[k]; }
    return { type: def[1], value: obj, set: v => { holder[keys[keys.length - 1]] = v; }, key: keys[keys.length - 1], top: keys.length === 1 };
  };
  const reportersFor = type => Object.keys(CW_OPS).filter(op => cwKind(op) === (type === "bool" ? "bool" : "num") && allowed(op));
  const editSlot = async (id, path) => {
    const f = find(id);
    if (!f || play) return;
    const s = slotOf(f.b, path);
    if (s.top && fixed(f.b.op, s.key)) return toast(I18N.tr(T("This value is fixed in this level.")));
    const others = ed.proj.sprites.filter(x => x !== sp());
    let v;
    const removeBtn = typeof s.value === "object" && s.value
      ? done => h("button.btn.ghost.cw-pick-del", { type: "button", onclick: () => done(s.type === "bool" ? null : 0) }, "✕ ", T("Remove the value block")) : null;
    switch (s.type) {
      case "num": case "dir":
        if (s.value && typeof s.value === "object") {
          v = await cwPick(I18N.tr(T("Value block")), [{ icon: "🔢", label: I18N.tr(T("A number instead")), value: "num" }], { extra: removeBtn });
          if (v === "num") v = await cwNumPad(0, { dir: s.type === "dir" });
          break;
        }
        v = await cwNumPad(s.value, { dir: s.type === "dir", reporters: reportersFor("num") });
        break;
      case "bool":
        v = await cwPick(I18N.tr(T("Choose a condition")), reportersFor("bool").map(op => ({ label: cwLabelPreview(cwB(op), ed.proj.sprites), value: op })),
          { cols: 1, extra: removeBtn });
        if (typeof v === "string") { v = cwB(v); delete v.id; const other = others[0]; if (v.op === "touching" && other) v.args.what = other.id; }
        break;
      case "text": v = await promptDialog(T("What should it say?"), s.value, { maxLength: 120 }); if (v === null) v = undefined; break;
      case "key": v = await cwPick(I18N.tr(T("Which arrow?")), Object.entries(CW_KEYS).map(([k, ic]) => ({ icon: ic, value: k, on: k === s.value })), { cols: 4 }); break;
      case "msg": {
        const msgs = allMsgs();
        v = await cwPick(I18N.tr(T("Which message?")), [...msgs.map(x => ({ icon: "✉️", label: x, notr: true, value: x, on: x === s.value })),
          { icon: "➕", label: I18N.tr(T("New message")), value: "+" }], { cols: 2 });
        if (v === "+") { v = await promptDialog(T("Name of the new message"), "", { maxLength: 30 }); v = v && v.trim() ? v.trim() : undefined; }
        break;
      }
      case "costume":
        v = await cwPick(I18N.tr(T("Which costume?")), sp().costumes.map((c, i) => ({ img: cwCostumeUrl(c), label: "#" + (i + 1), value: i + 1, on: i + 1 === s.value })), { cols: 4 });
        break;
      case "backdrop": {
        const bds = ed.proj.stage.backdrops;
        if (!bds.length) return toast(I18N.tr(T("Add backdrops on the 🖼️ Stage tab first.")));
        v = await cwPick(I18N.tr(T("Which backdrop?")), bds.map((b, i) => ({ img: cwBgUrl(b), label: "#" + (i + 1), value: i + 1, on: i + 1 === s.value })), { cols: 3 });
        break;
      }
      case "target": case "touch":
        v = await cwPick(I18N.tr(s.type === "touch" ? T("Touching what?") : T("Go where?")),
          [s.type === "touch" ? { icon: "🔲", label: I18N.tr(T("edge")), value: "_edge" } : { icon: "🎲", label: I18N.tr(T("random place")), value: "_random" },
            ...others.map(x => ({ img: cwCostumeUrl(x.costumes[x.c]), label: x.name, notr: true, value: x.id }))], { cols: 3 });
        break;
    }
    if (v === undefined) return;
    change(() => s.set(v));
  };

  // ---------- the code list
  const code = h("div.cw-code", { "aria-label": T("Program") });
  let els = new Map();
  const gap = (p, k, i, empty = false) => {
    const on = ed.caret && ed.caret.p === p && ed.caret.k === k && ed.caret.i === i;
    return h("div.cw-gap" + (on ? ".on" : "") + (empty ? ".empty" : "") + (p == null ? ".top" : ""), { "data-p": p == null ? "" : p, "data-k": k || "", "data-i": i },
      on || empty ? h("span.cw-gap-l", on ? "＋ " : "", empty ? (p == null ? I18N.tr(T("Tap here, then choose an event ⚡ to start a script")) : I18N.tr(T("tap ＋ to add a block here"))) : "") : null);
  };
  const slotEl = (b, k, type, path, ownerOp) => {
    const v = b.args[k];
    if (v && typeof v === "object") return h("span.cw-rep" + (cwKind(v.op) === "bool" ? ".bool" : ""), { style: { "--c": cwColor(v.op) }, "data-b": path.b, "data-p": path.p },
      ...labelEls(v, { b: path.b, p: path.p }));
    const fx = fixed(ownerOp, k) && !path.p.includes(".");
    let content = cwValText(v, type, ed.proj.sprites);
    if (type === "costume" && sp() && sp().costumes[(v || 1) - 1]) content = [h("img.cw-thumb", { src: cwCostumeUrl(sp().costumes[(v || 1) - 1]), alt: "" }), "#" + v];
    if (type === "backdrop" && ed.proj.stage.backdrops[(v || 1) - 1]) content = [h("img.cw-thumb.bd", { src: cwBgUrl(ed.proj.stage.backdrops[(v || 1) - 1]), alt: "" }), "#" + v];
    return h((fx || play ? "span" : "button") + ".cw-slot." + type + (fx ? ".fixed" : ""), { type: fx || play ? null : "button", "data-b": path.b, "data-p": path.p, translate: "no" }, content);
  };
  const labelEls = (b, path) => {
    const parts = cwLabel(b.op).split(/\{(\d)\}/);
    return parts.map((p, i) => {
      if (i % 2 === 0) return p ? h("span.cw-t", { translate: "no" }, p) : null;
      const [k, type] = CW_OPS[b.op][3][+p];
      return slotEl(b, k, type, { b: path.b, p: path.p ? path.p + "." + k : k }, b.op);
    });
  };
  const rowEl = b => {
    const el = h("div.cw-blk." + cwKind(b.op) + (b.off ? ".off" : ""), { "data-id": b.id, style: { "--c": cwColor(b.op) } },
      cwKind(b.op) === "hat" ? h("span.cw-ic", CW_CAT()[cwCatOf(b.op)][0]) : null, ...labelEls(b, { b: b.id, p: "" }), b.off ? h("span.cw-off", "⏸") : null);
    els.set(b.id, el);
    return el;
  };
  const bodyEl = (b, key) => {
    const list = b[key] || [];
    return h("div.cw-body", { style: { "--c": cwColor(b.op) } },
      list.length ? [gap(b.id, key, 0), ...list.flatMap((x, i) => [blockEl(x), gap(b.id, key, i + 1)])] : gap(b.id, key, 0, true));
  };
  const blockEl = b => {
    const k = cwKind(b.op);
    if (k === "c" || k === "e") return h("div.cw-c" + (b.off ? ".off" : ""), { style: { "--c": cwColor(b.op) } }, rowEl(b), bodyEl(b, "body"),
      k === "e" ? [h("div.cw-else", h("span.cw-t", I18N.tr(T("else")))), bodyEl(b, "else")] : null, h("div.cw-cend"));
    return rowEl(b);
  };
  const renderCode = () => {
    els = new Map();
    const keep = code.scrollTop;
    if (ed.cur < 0) return renderStage();
    const s = sp();
    const list = s ? s.scripts : [];
    code.replaceChildren(...(list.length ? [gap(null, null, 0), ...list.flatMap((x, i) => [h("div.cw-script" + (x.off ? ".off" : ""), { style: { "--c": cwColor(x.op) } },
      rowEl(x), bodyEl(x, "body"), h("div.cw-cend")), gap(null, null, i + 1)])] : [gap(null, null, 0, true)]));
    code.scrollTop = keep;
    renderDrawer();
  };
  const scrollToCaret = () => { const g = code.querySelector(".cw-gap.on"); if (g) g.scrollIntoView({ block: "nearest", behavior: "smooth" }); };

  // ---------- the stage tab: backdrops
  const renderStage = () => {
    const bds = ed.proj.stage.backdrops;
    const addLib = async () => {
      const all = cwBackdrops();
      const v = await cwPick(I18N.tr(T("Choose a backdrop")), Object.entries(all).map(([k, n]) => ({ img: cwBgUrl(k), label: I18N.tr(n), value: k })), { cols: 3 });
      if (v) change(() => { if (bds.length < 10) { bds.push(v); ed.proj.stage.bd = bds.length - 1; } });
    };
    const draw = async (i = null) => {
      const svg = await svgPaint({ kind: "bg", svg: i != null && typeof bds[i] === "object" ? bds[i].v : null, endpoint: "codelab/svg" });
      if (svg) change(() => { if (i != null) bds[i] = { k: "svg", v: svg }; else if (bds.length < 10) { bds.push({ k: "svg", v: svg }); ed.proj.stage.bd = bds.length - 1; } });
    };
    code.replaceChildren(h("div.cw-stagepane",
      h("p.small.muted", T("The stage shows one backdrop at a time. The one with ✓ is there at the start; «switch backdrop to …» changes it.")),
      h("div.cw-bds", ...bds.map((b, i) => h("div.cw-bd" + (i === ed.proj.stage.bd ? ".on" : ""),
        h("button.cw-bd-img", { type: "button", "aria-label": T("Backdrop at the start"), onclick: () => change(() => { ed.proj.stage.bd = i; }) },
          h("img", { src: cwBgUrl(b), alt: "" }), h("span.cw-bd-n", (i === ed.proj.stage.bd ? "✓ " : "") + "#" + (i + 1))),
        h("div.cw-bd-acts", typeof b === "object" ? h("button.btn.small.ghost", { type: "button", "aria-label": T("Edit"), onclick: () => draw(i) }, "✏️") : null,
          h("button.btn.small.ghost", { type: "button", "aria-label": T("Remove"), onclick: () => change(() => { bds.splice(i, 1); ed.proj.stage.bd = Math.min(ed.proj.stage.bd, Math.max(0, bds.length - 1)); }) }, "🗑️"))))),
      bds.length < 10 ? h("div.row.wrap", h("button.btn.small", { type: "button", onclick: addLib }, "🖼️ ", T("From the library")),
        h("button.btn.small.ghost", { type: "button", onclick: () => draw() }, "✏️ ", T("Draw a backdrop"))) : null));
    renderDrawer();
  };

  // ---------- sprite tabs
  const tabs = h("div.cw-tabs", { role: "tablist" });
  const renderTabs = () => {
    if (puzzle) return;
    tabs.replaceChildren(
      h("button.cw-tab" + (ed.cur < 0 ? ".on" : ""), { type: "button", role: "tab", "aria-selected": String(ed.cur < 0), onclick: () => { ed.cur = -1; ed.caret = null; renderTabs(); renderCode(); } },
        h("span.cw-tab-ic", "🖼️"), h("span.cw-tab-n", T("Stage"))),
      ...ed.proj.sprites.map((s, i) => h("button.cw-tab" + (i === ed.cur ? ".on" : ""), { type: "button", role: "tab", "aria-selected": String(i === ed.cur),
        onclick: () => { if (i === ed.cur && !play) return spriteSheet(i); ed.cur = i; ed.caret = null; renderTabs(); renderCode(); } },
        h("img.cw-tab-img", { src: cwCostumeUrl(s.costumes[s.c]), alt: "" }), h("span.cw-tab-n", { translate: "no" }, s.name), i === ed.cur && !play ? h("span.cw-tab-more", "⚙️") : null)),
      play || ed.proj.sprites.length >= CW_MAX_SPRITES ? null : h("button.cw-tab.add", { type: "button", "aria-label": T("New sprite"), onclick: addSprite }, h("span.cw-tab-ic", "＋"), h("span.cw-tab-n", T("Sprite"))));
    const on = tabs.querySelector(".cw-tab.on");
    if (on) on.scrollIntoView({ block: "nearest", inline: "nearest" });
  };
  const libCostumes = key => Array.from({ length: CW_SPRITES()[key][1] }, (_, i) => ({ k: "lib", v: key + "-" + (i + 1) }));
  const addSprite = async () => {
    const lib = CW_SPRITES();
    const v = await cwPick(I18N.tr(T("New sprite")), [...Object.entries(lib).map(([k, [n]]) => ({ img: "img/codelab/" + k + "-1.svg", label: I18N.tr(n), value: k })),
      { icon: "✏️", label: I18N.tr(T("Draw your own")), value: "+" }], { cols: 4 });
    if (!v) return;
    let costumes, name, rot = "all";
    if (v === "+") {
      const svg = await svgPaint({ kind: "art", endpoint: "codelab/svg" });
      if (!svg) return;
      costumes = [{ k: "svg", v: svg }]; name = I18N.tr(T("Sprite"));
    } else { costumes = libCostumes(v); name = I18N.tr(lib[v][0]); rot = lib[v][2]; }
    const used = new Set(ed.proj.sprites.map(s => s.id));
    let n = 1; while (used.has("s" + n)) n++;
    change(() => {
      ed.proj.sprites.push({ id: "s" + n, name, costumes, c: 0, x: Math.round(Math.random() * 200 - 100), y: Math.round(Math.random() * 120 - 60), dir: 90, size: 100,
        show: true, rot, scripts: [cwB("ev_start")] });
      ed.cur = ed.proj.sprites.length - 1;
      ed.caret = { p: sp().scripts[0].id, k: "body", i: 0 };
    });
  };
  const spriteSheet = i => {
    const s = ed.proj.sprites[i];
    let m;
    const redraw = () => { m.close(); spriteSheet(i); };
    const name = h("input", { type: "text", value: s.name, maxLength: 20, onchange: () => change(() => { s.name = name.value.trim().slice(0, 20) || s.name; }) });
    const num = (label, key, lo, hi) => h("label.field.cw-num", h("span", label), h("button.btn.ghost.small", { type: "button", translate: "no",
      onclick: async () => { const v = await cwNumPad(s[key], { dir: key === "dir" }); if (typeof v === "number") { change(() => { s[key] = cwClamp(v, lo, hi); }); redraw(); } } }, cwFmt(s[key])));
    const addCostume = async () => {
      const keys = Object.keys(CW_SPRITES());
      const v = await cwPick(I18N.tr(T("New costume")), [...keys.flatMap(k => libCostumes(k).map(c => ({ img: cwCostumeUrl(c), value: c }))),
        { icon: "✏️", label: I18N.tr(T("Draw")), value: "+" }], { cols: 5 });
      if (!v) return;
      let c = v;
      if (v === "+") { const svg = await svgPaint({ kind: "art", endpoint: "codelab/svg" }); if (!svg) return; c = { k: "svg", v: svg }; }
      change(() => { if (s.costumes.length < 8) s.costumes.push(c); });
      redraw();
    };
    const editCostume = async j => {
      const svg = await svgPaint({ kind: "art", svg: s.costumes[j].v, endpoint: "codelab/svg" });
      if (svg) { change(() => { s.costumes[j] = { k: "svg", v: svg }; }); redraw(); }
    };
    m = modal(h("div.form.cw-sheet",
      h("h3", "⚙️ ", T("Sprite")),
      h("label.field", h("span", T("Name")), name),
      h("div.field", h("b", T("Costumes")), h("span.small.muted", T("Tap one: the sprite starts with it.")),
        h("div.cw-costumes", ...s.costumes.map((c, j) => h("div.cw-cos" + (j === s.c ? ".on" : ""),
          h("button.cw-cos-img", { type: "button", "aria-label": "#" + (j + 1), onclick: () => { change(() => { s.c = j; }); redraw(); } }, h("img", { src: cwCostumeUrl(c), alt: "" }), h("span", "#" + (j + 1))),
          c.k === "svg" ? h("button.cw-cos-x", { type: "button", "aria-label": T("Edit"), onclick: () => editCostume(j) }, "✏️") : null,
          s.costumes.length > 1 ? h("button.cw-cos-x", { type: "button", "aria-label": T("Remove"), onclick: () => { change(() => { s.costumes.splice(j, 1); s.c = Math.min(s.c, s.costumes.length - 1); }); redraw(); } }, "✕") : null)),
          s.costumes.length < 8 ? h("button.cw-cos.add", { type: "button", "aria-label": T("New costume"), onclick: addCostume }, "＋") : null)),
      h("div.cw-sheet-nums", num(I18N.tr(T("Size %")), "size", 5, 500), num(I18N.tr(T("Direction")), "dir", -180, 180), num("x", "x", -240, 240), num("y", "y", -180, 180)),
      h("label.check", h("input", { type: "checkbox", checked: s.show, onchange: e => change(() => { s.show = e.target.checked; }) }), " ", T("Visible at the start")),
      h("div.field", h("b", T("Turning")), h("div.sb-segs", ...[["all", "↻", T("all around")], ["lr", "↔", T("left / right")], ["none", "⊘", T("don't turn")]].map(([k, ic, n]) =>
        h("button.sb-seg" + (s.rot === k ? ".on" : ""), { type: "button", onclick: () => { change(() => { s.rot = k; }); redraw(); } }, ic, " ", n)))),
      h("div.row.wrap.cw-sheet-acts",
        ed.proj.sprites.length < CW_MAX_SPRITES ? h("button.btn.ghost.small", { type: "button", onclick: () => {
          m.close(); const used = new Set(ed.proj.sprites.map(x => x.id)); let n = 1; while (used.has("s" + n)) n++;
          change(() => { const c = cwClone(s); c.id = "s" + n; c.x += 30; cwReId(c.scripts); ed.proj.sprites.splice(i + 1, 0, c); ed.cur = i + 1; });
        } }, "⧉ ", T("Duplicate")) : null,
        h("button.btn.ghost.small.danger-text", { type: "button", onclick: async () => {
          if (!(await confirmDialog(T("Delete this sprite with its scripts?")))) return;
          m.close(); change(() => { ed.proj.sprites.splice(i, 1); ed.cur = Math.min(ed.cur, ed.proj.sprites.length - 1); }, { keepCaret: false });
        } }, "🗑️ ", T("Delete")),
        h("button.btn.small", { type: "button", onclick: () => m.close() }, "✓ ", T("Done")))));
  };

  // ---------- the drawer
  const drawer = h("div.cw-drawer");
  const ops = () => Object.keys(CW_OPS).filter(op => allowed(op) && !(puzzle && pal[op].hide));
  const renderDrawer = () => {
    if (play) return drawer.replaceChildren();
    if (ed.cur < 0) { drawer.hidden = true; root.classList.remove("drawer-open"); return; }
    drawer.hidden = false;
    const list = ops(), cats = [...new Set(list.map(cwCatOf))];
    if (!cats.includes(ed.cat)) ed.cat = cats[0];
    const top = !!(ed.caret && ed.caret.p == null);
    const chips = h("div.cw-chips", { role: "tablist" }, ...cats.map(c => { const [ic, n, col] = CW_CAT()[c];
      return h("button.cw-chip" + (c === ed.cat && ed.drawer ? ".on" : ""), { type: "button", role: "tab", style: { "--c": col }, "aria-selected": String(c === ed.cat && ed.drawer),
        onclick: () => { if (ed.cat === c && ed.drawer) ed.drawer = false; else { ed.cat = c; ed.drawer = true; } renderDrawer(); } }, h("span", ic), h("span.cw-chip-n", n)); }),
      h("button.cw-chip.close", { type: "button", "aria-label": ed.drawer ? T("Close the blocks") : T("Open the blocks"), onclick: () => { ed.drawer = !ed.drawer; renderDrawer(); } }, ed.drawer ? "▾" : "▴"));
    const shown = list.filter(op => cwCatOf(op) === ed.cat);
    const preview = op => { const b = cwB(op, puzzle && pal[op] ? pal[op].args || {} : {}); for (const [k, t, d] of CW_OPS[op][3]) if (t === "text") b.args[k] = I18N.tr(d); if (CW_OPS[op][3].some(x => x[1] === "msg")) b.args.msg = allMsgs()[0] || I18N.tr(T("go")); return b; };
    const cards = h("div.cw-cards", ...shown.map(op => {
      const kind = cwKind(op), dim = (top && kind !== "hat") || kind === "bool" || kind === "num";
      return h("button.cw-card." + kind + (dim ? ".dim" : ""), { type: "button", style: { "--c": cwColor(op) }, onclick: () => insert(op) },
        kind === "hat" ? h("span.cw-ic", CW_CAT()[cwCatOf(op)][0]) : null, cwLabelPreview(preview(op), ed.proj.sprites),
        kind === "c" || kind === "e" ? h("span.cw-card-c", "⤵") : null);
    }), ed.cat === "sensing" ? h("p.small.muted.cw-cards-note", T("Value blocks go into a slot: tap a ◇ or a number in a block.")) : null);
    drawer.replaceChildren(chips, ed.drawer ? cards : null);
    root.classList.toggle("drawer-open", ed.drawer);
  };

  // ---------- puzzle info
  const info = h("div.cw-info");
  let hintOpen = false;
  const renderInfo = () => {
    if (!puzzle) return;
    const n = cwCount(scripts()), [s3, s2] = level.stars;
    info.replaceChildren(
      h("div.cw-goal", "🎯 ", h("span", I18N.tr(level.goal))),
      h("div.row.cw-meta",
        h("span.cw-count" + (level.max && n >= level.max ? ".full" : ""), "🧱 ", h("b", { translate: "no" }, String(n)), level.max ? h("span", { translate: "no" }, " / " + level.max) : null),
        h("span.cw-starsinfo", { translate: "no" }, "⭐⭐⭐ ≤ " + s3, s2 > s3 ? " · ⭐⭐ ≤ " + s2 : ""),
        h("span.grow"),
        h("button.btn.small.ghost.cw-hintbtn", { type: "button", "aria-expanded": String(hintOpen), onclick: () => { hintOpen = !hintOpen; renderInfo(); } }, "💡 ", T("Hint"))),
      hintOpen ? h("p.cw-hint", I18N.tr(level.hint)) : null);
  };

  // ---------- stage and running
  const canvas = h("canvas.cw-canvas", { width: CW_W, height: CW_H, role: "img", "aria-label": T("Stage") });
  const fit = () => { const r = canvas.getBoundingClientRect(), k = Math.min(3, window.devicePixelRatio || 1); const w = Math.max(48, Math.round(r.width * k)); if (canvas.width !== w) { canvas.width = w; canvas.height = Math.round(w * 3 / 4); } };
  const keysUsed = () => puzzle ? level.inputs === "keys" : ed.proj.sprites.some(s => s.scripts.some(x => x.op === "ev_key"));
  const pad = h("div.cw-pad", ...[["left", "←"], ["up", "↑"], ["down", "↓"], ["right", "→"]].map(([k, ic]) =>
    h("button.cw-padk", { type: "button", "aria-label": ic, onpointerdown: e => { e.preventDefault(); keyPress(k); } }, ic)));
  const runBtn = h("button.btn.good.cw-run", { type: "button", onclick: () => run() }, "▶ ", h("span.cw-run-l", T("Start")));
  const stopBtn = h("button.btn.ghost.cw-stop", { type: "button", "aria-label": T("Stop"), onclick: () => stop() }, "⏹");
  const slowBtn = h("button.btn.ghost.cw-slow", { type: "button", "aria-pressed": "false", "aria-label": T("Slow motion"), onclick: () => {
    ed.slow = !ed.slow; slowBtn.setAttribute("aria-pressed", String(ed.slow)); slowBtn.classList.toggle("on", ed.slow);
    if (ed.eng && ed.eng.mode !== "step") ed.eng.mode = ed.slow ? "slow" : "normal"; } }, "🐢");
  const stepBtn = h("button.btn.ghost.cw-stepb", { type: "button", "aria-label": T("Step by step"), onclick: () => stepOnce() }, "👣");
  const foldBtn = h("button.btn.ghost.cw-fold", { type: "button", "aria-label": T("Show or hide the stage"), onclick: () => { ed.collapsed = !ed.collapsed; layout(); } }, "▴");
  const runRow = h("div.cw-runrow", runBtn, stopBtn, slowBtn, puzzle ? stepBtn : null, h("span.grow"), statusEl, foldBtn);
  const stageBox = h("div.cw-stagebox", h("div.cw-canvaswrap", canvas), runRow);
  const layout = () => {
    root.classList.toggle("collapsed", ed.collapsed);
    foldBtn.textContent = ed.collapsed ? "▾" : "▴";
    pad.hidden = !keysUsed();
  };
  const newEngine = () => {
    const e = new CwEngine(cwClone(ed.proj), puzzle ? { grid: level, onEnd: why => puzzleEnd(why) } : {});
    return e;
  };
  const preview = () => { if (!ed.eng || !ed.running) { if (!ed.eng || !ed.shown) ed.eng = newEngine(); } };
  const run = () => {
    saveNow();
    ed.eng = newEngine(); ed.shown = true;
    ed.eng.mode = ed.slow ? "slow" : "normal";
    ed.inputs = [];
    ed.running = true;
    ed.drawer = false; renderDrawer();
    if (ed.collapsed) { ed.collapsed = false; layout(); }
    ed.eng.start();
    Sound.play("tap");
    root.classList.add("running");
  };
  const stop = () => {
    if (ed.eng) ed.eng.stop();
    ed.running = false; root.classList.remove("running");
    highlight(new Set());
  };
  const stepOnce = () => {
    if (!ed.running) { run(); ed.eng.mode = "step"; return; }
    ed.eng.mode = "step"; ed.eng.step();
  };
  const keyPress = k => {
    if (!ed.running || !ed.eng) return;
    if (puzzle) { if (level.inputs !== "keys" || ed.eng.busy() || ed.eng.ended) return; ed.inputs.push("key:" + k); }
    ed.eng.trigger("key", k);
  };
  const puzzleEnd = async why => {
    ed.running = false; root.classList.remove("running");
    if (why === "win") {
      Sound.play("done");
      let r;
      try { r = await api("codelab/levels/" + encodeURIComponent(level.id) + "/solve", { method: "POST", body: { scripts: scripts(), inputs: ed.inputs } }); }
      catch (e) { return toast(e.message, "bad"); }
      if (!r.ok) return toast(I18N.tr(T("Not there yet – the program ended before the star.")), "bad");
      return o.onSolved && o.onSolved(r, () => { ed.eng = null; ed.shown = false; });
    }
    Sound.play("wrong");
    toast(I18N.tr({ stone: T("Ouch – a stone! Try again."), edge: T("Careful – the fox almost fell off the map!"),
      forever: T("This loop runs for ever – is that what you want? The fox did not find the star."),
      short: T("Not there yet – the program ended before the star.") }[why] || T("Try again")), "bad");
    setTimeout(() => { if (!ed.running) { ed.eng = null; ed.shown = false; } }, 1600);
  };
  // the stage: drag a sprite to its start place (stopped), tap a sprite / swipe (running)
  let press = null;
  const stageXY = e => { const r = canvas.getBoundingClientRect(); return [(e.clientX - r.left) / r.width * CW_W - CW_W / 2, CW_H / 2 - (e.clientY - r.top) / r.height * CW_H]; };
  const hit = (eng, x, y) => [...eng.sprites].reverse().find(s => { if (!s.show) return false; const [a, b, c, d] = eng.box(s, 1); return x >= a && x <= b && y >= c && y <= d; });
  canvas.addEventListener("pointerdown", e => {
    const [x, y] = stageXY(e);
    press = { x, y, sx: e.clientX, sy: e.clientY, moved: false, drag: null };
    if (!ed.running && !puzzle && !play && ed.eng) {
      const s = hit(ed.eng, x, y);
      if (s) { const i = ed.eng.sprites.indexOf(s); press.drag = { i, x0: ed.proj.sprites[i].x, y0: ed.proj.sprites[i].y, snap: snapshot() }; canvas.setPointerCapture(e.pointerId); }
    }
  });
  canvas.addEventListener("pointermove", e => {
    if (!press) return;
    if (Math.hypot(e.clientX - press.sx, e.clientY - press.sy) > 6) press.moved = true;
    if (press.drag && press.moved) {
      const [x, y] = stageXY(e), s = ed.proj.sprites[press.drag.i];
      s.x = Math.round(cwClamp(press.drag.x0 + x - press.x, -240, 240)); s.y = Math.round(cwClamp(press.drag.y0 + y - press.y, -180, 180));
      ed.eng = newEngine(); ed.shown = false;
    }
  });
  const pointerEnd = e => {
    const p = press; press = null;
    if (!p) return;
    if (p.drag) {
      if (p.moved) { ed.undo.push(p.drag.snap); ed.redo.length = 0; updateUndo(); queueSave(); }
      else if (p.drag.i !== ed.cur) { ed.cur = p.drag.i; ed.caret = null; renderTabs(); renderCode(); }
      return;
    }
    if (!ed.running || !ed.eng) return;
    const dx = e.clientX - p.sx, dy = e.clientY - p.sy;
    if (Math.hypot(dx, dy) > 30) return keyPress(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up"));
    const s = hit(ed.eng, p.x, p.y);
    if (!s) return;
    if (puzzle) { if (level.inputs !== "tap" || s !== ed.eng.sprites[0] || ed.eng.busy() || ed.eng.ended) return; ed.inputs.push("tap"); }
    ed.eng.trigger("tap", null, s);
  };
  canvas.addEventListener("pointerup", pointerEnd);
  canvas.addEventListener("pointercancel", () => { press = null; });
  const onKey = e => {
    if (!root.isConnected) return document.removeEventListener("keydown", onKey);
    if (document.querySelector(".modal-back")) return;
    const k = { ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down" }[e.key];
    if (k && ed.running) { e.preventDefault(); keyPress(k); }
  };
  document.addEventListener("keydown", onKey);

  // ---------- highlight of the running blocks
  let lit = new Set();
  const highlight = ids => {
    for (const id of lit) if (!ids.has(id)) { const el = els.get(id); if (el) el.classList.remove("run"); }
    for (const id of ids) if (!lit.has(id)) { const el = els.get(id); if (el) { el.classList.add("run"); if (ed.eng && ed.eng.mode !== "normal") el.scrollIntoView({ block: "nearest" }); } }
    lit = ids;
  };
  let raf = 0;
  const frame = ts => {
    if (!root.isConnected) { if (ed.dirty) saveNow(); return; }
    raf = requestAnimationFrame(frame);
    fit();
    preview();
    if (ed.running && ed.eng) {
      ed.eng.tick(ts);
      if (!ed.eng.on && !puzzle) { ed.running = false; root.classList.remove("running"); }
      if (ed.eng.notice === "fast") { ed.eng.notice = "told"; toast(I18N.tr(T("This loop runs for ever without a pause – is that what you want? ⏹ stops it."))); }
      highlight(ed.running ? ed.eng.curIds() : new Set());
    }
    cwDraw(canvas, ed.eng);
  };

  // ---------- long press: menu or drag
  let lp = null, suppress = false;
  const clearLp = () => { if (lp) { clearTimeout(lp.timer); if (lp.el) lp.el.classList.remove("lift"); if (lp.ghost) lp.ghost.remove(); code.querySelectorAll(".cw-gap.drop").forEach(g => g.classList.remove("drop")); } lp = null; clearInterval(autoScroll); };
  let autoScroll = null;
  const gapAt = (x, y) => {
    const el = document.elementFromPoint(x, y);
    let g = el && el.closest(".cw-gap");
    if (g) return g;
    const blk = el && el.closest(".cw-blk, .cw-cend, .cw-else");
    if (blk) { const r = blk.getBoundingClientRect(); const near = y < r.top + r.height / 2 ? blk.closest(".cw-c, .cw-script") && blk.classList.contains("cw-blk") && blk.parentElement.firstElementChild === blk ? blk.parentElement.previousElementSibling : blk.previousElementSibling : null; if (near && near.classList.contains("cw-gap")) return near; }
    const all = [...code.querySelectorAll(".cw-gap")];
    let best = null, bd = 1e9;
    for (const gg of all) { const r = gg.getBoundingClientRect(); const d = Math.abs(r.top + r.height / 2 - y); if (d < bd) { bd = d; best = gg; } }
    return best;
  };
  code.addEventListener("pointerdown", e => {
    if (play || e.button > 0) return;
    const blk = e.target.closest(".cw-blk");
    if (!blk || e.target.closest(".cw-slot, .cw-rep")) return;
    clearLp();
    lp = { id: blk.dataset.id, el: blk, x: e.clientX, y: e.clientY, lifted: false, drag: false, pid: e.pointerId };
    lp.timer = setTimeout(() => {
      if (!lp) return;
      lp.lifted = true; blk.classList.add("lift");
      try { navigator.vibrate && navigator.vibrate(15); } catch {}
    }, 420);
  });
  code.addEventListener("pointermove", e => {
    if (!lp) return;
    const d = Math.hypot(e.clientX - lp.x, e.clientY - lp.y);
    if (!lp.lifted) { if (d > 10) clearLp(); return; }
    if (!lp.drag && d > 8) {
      lp.drag = true;
      const src = lp.el.closest(".cw-c, .cw-script") && lp.el.parentElement.firstElementChild === lp.el ? lp.el.parentElement : lp.el;
      lp.ghost = h("div.cw-ghost", { style: { width: Math.min(src.getBoundingClientRect().width, 320) + "px" } }, src.cloneNode(true));
      root.append(lp.ghost);
      try { code.setPointerCapture(lp.pid); } catch {}
      autoScroll = setInterval(() => {
        if (!lp || !lp.drag) return;
        const r = code.getBoundingClientRect();
        if (lp.cy < r.top + 40) code.scrollTop -= 12; else if (lp.cy > r.bottom - 40) code.scrollTop += 12;
      }, 30);
    }
    if (lp.drag) {
      e.preventDefault();
      lp.cx = e.clientX; lp.cy = e.clientY;
      lp.ghost.style.transform = `translate(${e.clientX + 6}px, ${e.clientY - 18}px)`;
      lp.ghost.hidden = true;
      const g = gapAt(e.clientX, e.clientY);
      lp.ghost.hidden = false;
      code.querySelectorAll(".cw-gap.drop").forEach(x => { if (x !== g) x.classList.remove("drop"); });
      if (g) g.classList.add("drop");
      lp.gap = g;
    }
  });
  code.addEventListener("pointerup", () => {
    if (!lp) return;
    const l = lp;
    if (l.lifted) suppress = true;
    if (l.drag && l.gap) { const g = l.gap.dataset; clearLp(); moveTo(l.id, { p: g.p || null, k: g.k || null, i: +g.i }); return; }
    clearLp();
    if (l.lifted) blockMenu(l.id);
  });
  code.addEventListener("pointercancel", clearLp);
  code.addEventListener("touchmove", e => { if (lp && lp.lifted) e.preventDefault(); }, { passive: false });
  code.addEventListener("contextmenu", e => {
    const blk = e.target.closest(".cw-blk");
    if (!blk) return;
    e.preventDefault();
    if (e.pointerType === "touch" || (lp && lp.lifted)) return;          // touch: the long press opens it
    if (!play) blockMenu(blk.dataset.id);
  });
  code.addEventListener("click", e => {
    if (suppress) { suppress = false; return; }
    if (play) return;
    const slot = e.target.closest("button.cw-slot");
    if (slot) return editSlot(slot.dataset.b, slot.dataset.p);
    const rep = e.target.closest(".cw-rep");
    if (rep) return editSlot(rep.dataset.b, rep.dataset.p);
    const g = e.target.closest(".cw-gap");
    if (g) { ed.caret = { p: g.dataset.p || null, k: g.dataset.k || null, i: +g.dataset.i }; ed.drawer = true; renderCode(); return; }
    const blk = e.target.closest(".cw-blk");
    if (blk) {
      const f = find(blk.dataset.id);
      if (!f) return;
      ed.caret = cwHasBody(f.b.op) ? { p: f.b.id, k: "body", i: 0 } : f.parent ? { p: f.parent.id, k: f.key, i: f.i + 1 } : { p: null, k: null, i: f.i + 1 };
      ed.drawer = true; renderCode();
    }
  });

  // ---------- header
  const undoBtn = h("button.icon-btn", { type: "button", "aria-label": T("Undo"), onclick: () => history(ed.undo, ed.redo) }, "↶");
  const redoBtn = h("button.icon-btn", { type: "button", "aria-label": T("Redo"), onclick: () => history(ed.redo, ed.undo) }, "↷");
  const updateUndo = () => { undoBtn.disabled = !ed.undo.length; redoBtn.disabled = !ed.redo.length; };
  const titleEl = h("button.cw-title", { type: "button", translate: "no", disabled: !o.rename, onclick: async () => {
    const t = await promptDialog(T("Title of the program"), ed.title, { maxLength: 60 });
    if (t && t.trim()) { ed.title = t.trim(); titleEl.textContent = ed.title; ed.dirty = true; saveNow(); }
  } }, ed.title);
  const back = async () => { stop(); await saveNow(); if (ed.saving) try { await ed.saving; } catch {} o.onBack && o.onBack(); };
  const bar = h("div.cw-bar",
    h("button.icon-btn", { type: "button", "aria-label": T("Back"), onclick: back }, "←"),
    puzzle ? h("div.cw-title.lv", h("span.cw-lvn", { translate: "no" }, level.id), " ", h("span", I18N.tr(level.title))) : titleEl,
    h("span.grow"),
    play ? null : undoBtn, play ? null : redoBtn,
    ...(o.actions || []));

  root.append(bar, h("div.cw-main", h("div.cw-left", stageBox, pad), h("div.cw-right", puzzle ? info : tabs, code, drawer)));
  if (puzzle && !scripts().length) scripts().push(...cwIds(level.start.map(cwClone)));
  if (!puzzle && ed.proj.sprites.length && sp().scripts[0]) ed.caret = null;
  renderTabs(); renderInfo(); renderCode(); updateUndo(); layout();
  // a small screen in portrait: the stage gets smaller while the drawer is open (the code needs the room)
  raf = requestAnimationFrame(frame);
  return { root, ed, saveNow, stop, setTitle: t => { ed.title = t; titleEl.textContent = t; }, rerender: () => { ed.eng = null; ed.shown = false; renderCode(); } };
}

// ---------------------------------------------------------------- templates (made in the language of the app)
const CW_VIS = () => ({ me: ["🔒", T("Only me"), T("Only you can see and play it – also parents can't.")],
  kids: ["🧒", T("Other children"), T("All children of the family can play it and make a remix.")],
  family: ["👨‍👩‍👧", T("Whole family"), T("Children and parents can play it and make a remix.")] });
const cwLib = (key, n) => Array.from({ length: n }, (_, i) => ({ k: "lib", v: key + "-" + (i + 1) }));
const cwSprite = (id, key, extra = {}) => {
  const [name, n, rot] = CW_SPRITES()[key];
  return { id, name: I18N.tr(name), costumes: cwLib(key, n), c: 0, x: 0, y: 0, dir: 90, size: 100, show: true, rot, scripts: [], ...extra };
};
const cwTr = s => I18N.tr(s);
const CW_TEMPLATES = () => ({
  empty: ["🆕", T("Empty program"), T("A fox and a white stage – build what you like.")],
  dance: ["🐱", T("Dancing cat"), T("The cat dances to the beat – change the moves.")],
  catch: ["⭐", T("Catch the star"), T("Steer the rocket with the arrows and catch the star.")],
  card: ["💌", T("Greeting card"), T("A card that comes alive – tap the dragon.")] });
function cwTemplate(key) {
  const B = cwB;
  if (key === "dance") return { title: cwTr(T("Dancing cat")), data: { stage: { backdrops: ["kidsroom"], bd: 0 }, sprites: [
    cwSprite("s1", "cat", { y: -40, size: 140, scripts: [
      B("ev_start", {}, [B("say", { text: cwTr(T("Let's dance!")), secs: 2 }),
        B("forever", {}, [B("next_costume"), B("turn_r", { deg: 15 }), B("wait", { secs: 0.3 }), B("turn_l", { deg: 15 }), B("wait", { secs: 0.3 })])]),
      B("ev_tap", {}, [B("repeat", { n: 2 }, [B("size_add", { n: 20 }), B("wait", { secs: 0.2 }), B("size_add", { n: -20 }), B("wait", { secs: 0.2 })]),
        B("think", { text: "♪ ♫", secs: 1 })])] })] } };
  if (key === "catch") return { title: cwTr(T("Catch the star")), data: { stage: { backdrops: ["space"], bd: 0 }, sprites: [
    cwSprite("s1", "star", { x: 120, y: 80, size: 70, scripts: [
      B("ev_start", {}, [B("show"), B("forever", {}, [B("glide", { secs: 1.5, x: { op: "random", args: { a: -200, b: 200 } }, y: { op: "random", args: { a: -140, b: 140 } } })])]),
      B("ev_tap", {}, [B("say", { text: cwTr(T("Got me!")), secs: 1 })])] }),
    cwSprite("s2", "rocket", { x: -150, y: -100, size: 80, scripts: [
      B("ev_key", { key: "left" }, [B("point", { dir: -90 }), B("change_x", { n: -25 })]),
      B("ev_key", { key: "right" }, [B("point", { dir: 90 }), B("change_x", { n: 25 })]),
      B("ev_key", { key: "up" }, [B("point", { dir: 0 }), B("change_y", { n: 25 })]),
      B("ev_key", { key: "down" }, [B("point", { dir: 180 }), B("change_y", { n: -25 })]),
      B("ev_start", {}, [B("goto_xy", { x: -150, y: -100 }), B("forever", {}, [B("if", { cond: { op: "touching", args: { what: "s1" } } },
        [B("say", { text: cwTr(T("Caught!")), secs: 1 }), B("goto_xy", { x: -150, y: -100 })])])])] })] } };
  if (key === "card") return { title: cwTr(T("Greeting card")), data: { stage: { backdrops: ["clouds"], bd: 0 }, sprites: [
    cwSprite("s1", "dragon", { x: -120, y: -60, size: 150, scripts: [
      B("ev_start", {}, [B("say", { text: cwTr(T("Happy birthday!")), secs: 2 }), B("broadcast", { msg: cwTr(T("party")) })]),
      B("ev_tap", {}, [B("next_costume"), B("say", { text: cwTr(T("Have a great day!")), secs: 2 }), B("costume", { c: 1 })])] }),
    cwSprite("s2", "star", { x: 120, y: 90, size: 60, show: false, scripts: [
      B("ev_start", {}, [B("hide")]),
      B("ev_msg", { msg: cwTr(T("party")) }, [B("show"), B("repeat", { n: 36 }, [B("turn_r", { deg: 10 }), B("size_add", { n: 1 })])])] }),
    cwSprite("s3", "ball", { x: 140, y: -120, size: 60, scripts: [
      B("ev_msg", { msg: cwTr(T("party")) }, [B("glide", { secs: 2, x: 140, y: 120 }), B("think", { text: "🎈", secs: 1 }), B("goto_xy", { x: 140, y: -120 })])] })] } };
  return { title: cwTr(T("My program")), data: { stage: { backdrops: [], bd: 0 }, sprites: [cwSprite("s1", "fox", { scripts: [B("ev_start")] })] } };
}

// ---------------------------------------------------------------- learning time: a heartbeat while the workshop is open
let cwBeatTimer = null;
function cwBeat() {
  if (cwBeatTimer) return;
  const beat = async () => {
    if (!document.querySelector(".cw-root, .cw-home")) { clearInterval(cwBeatTimer); cwBeatTimer = null; return; }
    if (document.hidden) return;
    try {
      const r = await api("codelab/tick", { method: "POST" });
      if (r.learn_left === 0 && !document.querySelector(".cw-home")) {
        toast(I18N.tr(T("Learning time for today is used up – see you tomorrow!")), "bad");
        go("codelab");
      }
    } catch {}
  };
  beat();
  cwBeatTimer = setInterval(beat, 30000);
}

// ---------------------------------------------------------------- views of the kid app (#/codelab/…)
function cwVisPicker(value, onPick) {
  const box = h("div.sb-vispick");
  const draw = () => box.replaceChildren(
    h("div.sb-segs.sb-visseg", ...Object.entries(CW_VIS()).map(([k, [ic, n]]) => h("button.sb-seg" + (k === value ? ".on" : ""), { type: "button",
      onclick: () => { if (k === value) return; value = k; draw(); onPick(k); } }, ic, " ", n))),
    h("span.small.muted.sb-vishint", CW_VIS()[value][2]));
  draw();
  return box;
}
const cwStars = n => h("span.cw-stars", { "aria-label": n + " / 3" }, ...[0, 1, 2].map(i => h("i" + (i < n ? ".on" : ""), "★")));
const cwCover = p => p.cover ? h("img.cw-pcover", { src: "img/codelab/" + p.cover + ".svg", alt: "" }) : h("span.cw-pcover.ic", "💡");

async function codelabView() {
  const parts = location.hash.replace(/^#\/?/, "").split("/");
  const sub = parts[1] || "", id = parts[2] ? decodeURIComponent(parts[2]) : null;
  if (sub === "level" && id) return cwLevelView(id);
  if (sub === "edit" && id) return cwProjectView(+id, true);
  if (sub === "play" && id) return cwProjectView(+id, false);
  return cwHomeView(["puzzles", "mine", "family"].includes(sub) ? sub : "puzzles");
}

async function cwHomeView(tab) {
  let d;
  try { d = await api("codelab"); } catch (e) { toast(e.message, "bad"); return go("courses"); }
  const box = h("div.cw-home");
  const used = d.learn_left === 0;
  const tabBtn = (k, ic, n) => h("button.sb-seg" + (tab === k ? ".on" : ""), { type: "button", onclick: () => { history.replaceState(null, "", "#/codelab/" + k); cwHomeView(k); } }, ic, " ", n);
  const levelBtn = lv => h("button.cw-lv" + (lv.solved ? ".done" : "") + (lv.open ? "" : ".locked"), { type: "button", disabled: !lv.open || used,
    onclick: () => go("codelab/level/" + encodeURIComponent(lv.id)) },
    h("span.cw-lv-n", { translate: "no" }, lv.open ? lv.id : "🔒"), h("span.cw-lv-t", I18N.tr(lv.title)), cwStars(lv.stars));
  const puzzles = () => [
    h("p.muted", T("Bring the fox to the star – with as few blocks as possible. Every level teaches a new trick.")),
    d.reward.xp || d.reward.coins ? h("p.small.cw-rew", "🏅 ", I18N.tr(T("First solve of a level: {0}")).replace("{0}", [d.reward.xp ? d.reward.xp + " XP" : "", d.reward.coins ? d.reward.coins + " 🪙" : ""].filter(Boolean).join(" + "))) : null,
    ...d.worlds.map(w => { const lv = d.levels.filter(x => x.world === w.id);
      return h("section.card.cw-world", h("h2", w.emoji, " ", I18N.tr(w.title), h("span.small.muted.cw-wstars", { translate: "no" }, " ⭐ " + lv.reduce((a, x) => a + x.stars, 0) + " / " + lv.length * 3)),
        h("div.cw-lvs", ...lv.map(levelBtn))); })];
  const newProject = async () => {
    const tpls = CW_TEMPLATES();
    const key = await cwPick(I18N.tr(T("New program")), Object.entries(tpls).map(([k, [ic, n, info]]) => ({ icon: ic, label: h("span", h("b", I18N.tr(n)), h("br"), h("span.small.muted", I18N.tr(info))), value: k })), { cols: 1 });
    if (!key) return;
    const t = cwTemplate(key);
    try { const r = await api("codelab/projects", { method: "POST", body: { title: t.title, data: t.data, visibility: "family" } }); go("codelab/edit/" + r.id); }
    catch (e) { toast(e.message, "bad"); }
  };
  const card = (p, own) => h("div.card.cw-pcard",
    cwCover(p),
    h("div.grow", C(p.title, "strong"), h("div.small.muted", own ? [CW_VIS()[p.visibility][0], " ", I18N.tr(CW_VIS()[p.visibility][1])] : [C(p.author.name), " · ", CW_VIS()[p.visibility][0]],
      " · 🧱 " + p.blocks, p.remix_title ? [" · 🔀 ", C(p.remix_title)] : null)),
    h("div.row.cw-pacts",
      own ? h("button.btn.small", { type: "button", disabled: used, onclick: () => go("codelab/edit/" + p.id) }, "✏️ ", T("Open")) : null,
      h("button.btn.small" + (own ? ".ghost" : ""), { type: "button", disabled: used, onclick: () => go("codelab/play/" + p.id) }, "▶ ", T("Play"))));
  const mine = () => [
    h("div.row", h("p.muted.grow", T("Your own programs: games, stories, animations. They are saved by themselves.")),
      h("button.btn", { type: "button", disabled: used, onclick: newProject }, "＋ ", T("New program"))),
    d.projects.mine.length ? h("div.cw-plist", ...d.projects.mine.map(p => card(p, true))) : h("p.muted.cw-empty", T("No programs yet – start with a template!"))];
  const family = () => [
    h("p.muted", T("Programs the others share with you. Play them – or make a remix: your own copy to change.")),
    d.projects.others.length ? h("div.cw-plist", ...d.projects.others.map(p => card(p, false))) : h("p.muted.cw-empty", T("Nobody has shared a program yet."))];
  box.append(
    h("h1", "💡 ", T("Code Workshop")),
    used ? h("p.card.cw-used", "⏰ ", T("Learning time for today is used up – see you tomorrow!")) : null,
    h("div.sb-segs.cw-hometabs", { role: "tablist" }, tabBtn("puzzles", "🧩", T("Puzzles")), tabBtn("mine", "🎨", T("My programs")), tabBtn("family", "👨‍👩‍👧", T("Family programs"))),
    h("div.cw-homebody", ...(tab === "mine" ? mine() : tab === "family" ? family() : puzzles())));
  screen("courses", { back: () => go("courses") }, box);
  cwBeat();
}

function cwFull(editor) {
  screen("courses", editor.root);
  document.body.classList.add("quiz-open");
  cwBeat();
}
const cwBackTo = tab => () => { document.body.classList.remove("quiz-open"); go("codelab/" + tab); };

async function cwLevelView(lid) {
  if (learnUp()) { toast(T("Learning time for today is used up – see you tomorrow!"), "bad"); return go("codelab"); }
  let lv;
  try { lv = await api("codelab/levels/" + encodeURIComponent(lid)); } catch (e) { toast(e.message, "bad"); return go("codelab"); }
  const fox = cwSprite("s1", "fox", { scripts: cwIds(lv.program || []) });
  const proj = { stage: { backdrops: [], bd: 0 }, sprites: [fox] };
  const ed = cwEditor({ mode: "puzzle", proj, level: lv, onBack: cwBackTo("puzzles"),
    save: data => api("codelab/levels/" + encodeURIComponent(lid), { method: "PUT", body: { scripts: data.sprites[0].scripts } }),
    onSolved: (r, reset) => {
      confetti();
      const m = modal(h("div.cw-win",
        h("div.cw-win-stars", cwStars(r.stars)),
        h("h2", T("Solved!")),
        h("p", I18N.tr(T("Blocks used: {0}")).replace("{0}", r.blocks), r.stars < 3 ? [h("br"), h("span.small.muted", I18N.tr(T("⭐⭐⭐ with {0} blocks or fewer")).replace("{0}", lv.stars[0]))] : null),
        r.reward ? h("p.cw-win-rew", "🏅 ", [r.reward.xp ? "+" + r.reward.xp + " XP" : "", r.reward.coins ? " +" + r.reward.coins + " 🪙" : ""].join(" ")) : null,
        h("div.row.wrap.cw-win-acts",
          lv.next ? h("button.btn.big", { type: "button", onclick: () => { m.close(); go("codelab/level/" + encodeURIComponent(lv.next)); } }, T("Next level"), " ▶") :
            h("button.btn.big", { type: "button", onclick: () => { m.close(); cwBackTo("puzzles")(); } }, "🏆 ", T("All levels done!")),
          h("button.btn.ghost", { type: "button", onclick: () => { m.close(); reset(); } }, "↺ ", T("Try again")))));
      window.addEventListener("hashchange", () => m.close(), { once: true });           // left with the back button
    } });
  cwFull(ed);
}

async function cwProjectView(pid, edit) {
  if (learnUp()) { toast(T("Learning time for today is used up – see you tomorrow!"), "bad"); return go("codelab"); }
  let p;
  try { p = await api("codelab/projects/" + pid); } catch (e) { toast(e.message, "bad"); return go("codelab/" + (edit ? "mine" : "family")); }
  edit = edit && p.edit;
  const data = p.data;
  data.sprites.forEach(s => cwIds(s.scripts));
  let vis = p.visibility;
  const remix = async () => {
    try { const r = await api("codelab/projects/" + pid + "/remix", { method: "POST" }); toast(I18N.tr(T("Your remix is ready – change what you like!")), "good"); go("codelab/edit/" + r.id); }
    catch (e) { toast(e.message, "bad"); }
  };
  const more = () => {
    let m;
    m = modal(h("div.form.cw-sheet", h("h3", "⋯ ", C(ed.ed.title)),
      h("div.field", h("b", T("Who can see it?")), cwVisPicker(vis, async v => {
        try { await api("codelab/projects/" + pid, { method: "PUT", body: { visibility: v } }); vis = v; toast(T("Saved"), "good"); } catch (e) { toast(e.message, "bad"); }
      })),
      h("button.btn.ghost", { type: "button", onclick: () => { m.close(); go("codelab/play/" + pid); } }, "▶ ", T("Play full screen")),
      h("button.btn.ghost.danger-text", { type: "button", onclick: async () => {
        if (!(await confirmDialog(T("Delete this program for good?")))) return;
        try { await api("codelab/projects/" + pid, { method: "DELETE" }); m.close(); cwBackTo("mine")(); } catch (e) { toast(e.message, "bad"); }
      } }, "🗑️ ", T("Delete program")),
      h("button.btn", { type: "button", onclick: () => m.close() }, "✓ ", T("Done"))));
  };
  const actions = edit ? [h("button.icon-btn", { type: "button", "aria-label": T("More"), onclick: () => more() }, "⋯")]
    : [p.mine ? h("button.btn.small", { type: "button", onclick: () => go("codelab/edit/" + pid) }, "✏️ ", h("span.cw-hide-s", T("Edit")))
      : h("button.btn.small", { type: "button", onclick: remix }, "🔀 ", T("Remix"))];
  const ed = cwEditor({ mode: edit ? "free" : "play", proj: data, title: p.title, rename: edit, actions,
    onBack: cwBackTo(edit || p.mine ? "mine" : "family"),
    save: edit ? (d, title) => api("codelab/projects/" + pid, { method: "PUT", body: { data: d, title } }) : null });
  if (!edit) ed.root.querySelector(".cw-bar .cw-title").after(h("span.small.muted.cw-by", { translate: "no" }, "· " + p.author.name));
  cwFull(ed);
}

/** The tile on the learning page (kid.js coursesView). */
function codelabTile() {
  return h("section.card.cw-tile",
    h("div.cw-tile-head", h("span.cw-tile-ic", "💡"), h("div.grow", h("h2", T("Code Workshop")),
      h("p.small.muted", T("Program with blocks: puzzles with the fox and your own games and animations.")))),
    h("div.row.wrap.cw-tile-acts",
      h("button.btn", { type: "button", onclick: () => go("codelab/puzzles") }, "🧩 ", T("Puzzles")),
      h("button.btn.ghost", { type: "button", onclick: () => go("codelab/mine") }, "🎨 ", T("My programs")),
      h("button.btn.ghost", { type: "button", onclick: () => go("codelab/family") }, "👨‍👩‍👧 ", T("Family programs"))));
}

// tests (node): the engine without a browser
if (typeof module === "object" && module.exports) module.exports = { CwEngine, CW_OPS, cwSnap };
