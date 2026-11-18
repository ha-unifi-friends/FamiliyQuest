// Cube solver of the game corner (UI in web/cube.js): the cube model, the check of the painted colours and the
// solvers – 3×3 layer by layer (beginner method, explained in phases), 2×2 the shortest way (IDA*).
// Runs in the page, as a Web Worker (postMessage {n, stickers}) and in node (tests/cube_solver_harness.js).
// No texts here: errors and phases are codes, the UI translates them.
(function (root) {
"use strict";

const FACES = "URFDLB";                                  // face ids 0..5 in this order
const U = 0, R = 1, F = 2, D = 3, L = 4, B = 5;
const NORMAL = [[0, 1, 0], [1, 0, 0], [0, 0, 1], [0, -1, 0], [-1, 0, 0], [0, 0, -1]];
const OPP = [D, L, B, U, R, F];
// colours of a standard cube held with yellow on top and green in front (the 3×3 centres are fixed like this)
const COLORS = ["Y", "O", "G", "W", "R", "B"];         // colour of face U, R, F, D, L, B
const FACE_OF_COLOR = { Y: U, O: R, G: F, W: D, R: L, B: B };
const SIDES = [F, R, B, L];                              // around the top, clockwise seen from above

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
// a quarter turn clockwise seen from the tip of axis a: v' = -(a×v) + a(a·v)
const rot = (v, a) => { const c = cross(a, v), d = dot(a, v); return [-c[0] + a[0] * d, -c[1] + a[1] * d, -c[2] + a[2] * d]; };
const triple = (a, b, c) => dot(a, cross(b, c));

// ---------------------------------------------------------------- geometry: stickers, pieces and move permutations
const GEOM = {};
function geom(n) {
  if (GEOM[n]) return GEOM[n];
  const k = n - 1, pos = [], face = [], lookup = new Map();
  for (let f = 0; f < 6; f++) for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
    const a = 2 * c - k, b = 2 * r - k;                // doubled coordinates: cubie centres at -k, -k+2, …, k
    const p = [[a, k, b], [k, -b, -a], [a, -b, k], [a, -k, -b], [-k, -b, a], [-a, -b, -k]][f];
    lookup.set(p.join(",") + "," + f, pos.length);
    pos.push(p); face.push(f);
  }
  const N = 6 * n * n, faceIdx = v => NORMAL.findIndex(x => x[0] === v[0] && x[1] === v[1] && x[2] === v[2]);
  const quarter = {};
  for (let m = 0; m < 6; m++) {
    const ax = NORMAL[m], to = new Int16Array(N);
    for (let i = 0; i < N; i++) {
      if (dot(pos[i], ax) !== k) { to[i] = i; continue; }
      to[i] = lookup.get(rot(pos[i], ax).join(",") + "," + faceIdx(rot(NORMAL[face[i]], ax)));
    }
    quarter[FACES[m]] = to;
  }
  const perms = {};                                     // move name → «to» array (sticker i goes to to[i])
  for (const f of FACES) {
    const q = quarter[f], q2 = new Int16Array(N), q3 = new Int16Array(N);
    for (let i = 0; i < N; i++) { q2[i] = q[q[i]]; q3[i] = q[q2[i]]; }
    perms[f] = q; perms[f + "2"] = q2; perms[f + "'"] = q3;
  }
  // pieces: stickers grouped by cubie; corners ordered clockwise starting with the U/D sticker, edges U/D (else F/B) first
  const byPos = new Map();
  pos.forEach((p, i) => { const key = p.join(","); if (!byPos.has(key)) byPos.set(key, []); byPos.get(key).push(i); });
  const corners = [], edges = [];
  for (const st of byPos.values()) {
    if (st.length === 3) {
      const first = st.find(i => face[i] === U || face[i] === D), [a, b] = st.filter(i => i !== first);
      corners.push(triple(NORMAL[face[first]], NORMAL[face[a]], NORMAL[face[b]]) < 0 ? [first, a, b] : [first, b, a]);
    } else if (st.length === 2 && n === 3) {
      const ud = st.find(i => face[i] === U || face[i] === D), fb = st.find(i => face[i] === F || face[i] === B);
      const first = ud !== undefined ? ud : fb;
      edges.push([first, st.find(i => i !== first)]);
    }
  }
  const centres = n === 3 ? [0, 1, 2, 3, 4, 5].map(f => f * 9 + 4) : [];
  return (GEOM[n] = { n, N, pos, face, perms, corners, edges, centres });
}

function apply(state, move, n) {
  const to = geom(n).perms[move], out = state.slice();
  for (let i = 0; i < to.length; i++) out[to[i]] = state[i];
  return out;
}
function applyAll(state, moves, n) { for (const m of moves) state = apply(state, m, n); return state; }
function solvedState(n) { return geom(n).face.slice(); }
function solvedColors(n) { return geom(n).face.map(f => COLORS[f]); }
function isSolved(state, n) {                           // every face one colour (whatever the colour)
  const nn = n * n;
  for (let f = 0; f < 6; f++) for (let i = 1; i < nn; i++) if (state[f * nn + i] !== state[f * nn]) return false;
  return true;
}
const inverse = m => m.endsWith("2") ? m : m.endsWith("'") ? m[0] : m + "'";
const invert = moves => moves.slice().reverse().map(inverse);
function scramble(len = 25, n = 3, rnd = Math.random) {
  const faces = n === 2 ? "URF" : FACES, out = [];
  while (out.length < len) {
    const f = faces[Math.floor(rnd() * faces.length)];
    if (out.length && out[out.length - 1][0] === f) continue;
    out.push(f + ["", "'", "2"][Math.floor(rnd() * 3)]);
  }
  return out;
}
// merge turns of the same face next to each other: R R → R2, U U' → nothing
function simplify(moves) {
  const out = [];
  for (const m of moves) {
    const q = m.endsWith("2") ? 2 : m.endsWith("'") ? 3 : 1;
    if (out.length && out[out.length - 1].f === m[0]) {
      const last = out[out.length - 1]; last.q = (last.q + q) % 4;
      if (!last.q) out.pop();
    } else out.push({ f: m[0], q });
  }
  return out.map(x => x.f + ["", "", "2", "'"][x.q]);
}

// ---------------------------------------------------------------- check of the painted colours
// stickers: colour letters W Y R O B G ("" = not painted). Answer {ok, code, colors, stickers, …}; with ok the face ids
// of the stickers (state, solved = every sticker on its own face) for the solver.
const sameAxis = (a, b) => a === b || OPP[a] === b;

function validate(stickers, n) {
  const g = geom(n), nn = n * n;
  if (!Array.isArray(stickers) || stickers.length !== g.N) return { ok: false, code: "blank", count: g.N, stickers: [] };
  const blank = [];
  stickers.forEach((c, i) => { if (!(c in FACE_OF_COLOR)) blank.push(i); });
  if (blank.length) return { ok: false, code: "blank", count: blank.length, stickers: blank };
  for (const c of ["W", "Y", "R", "O", "B", "G"]) {
    const have = stickers.filter(x => x === c).length;
    if (have !== nn) return { ok: false, code: "count", color: c, have, want: nn, stickers: stickers.map((x, i) => x === c ? i : -1).filter(i => i >= 0) };
  }
  const std = stickers.map(c => FACE_OF_COLOR[c]);       // as faces of a standard cube (yellow top, green front)
  if (n === 3) for (let f = 0; f < 6; f++) if (std[g.centres[f]] !== f) return { ok: false, code: "centre", stickers: [g.centres[f]] };
  // corners: three colours of different axes, turning the right way round, every corner once
  const seenC = new Map();
  for (const slot of g.corners) {
    const cols = slot.map(i => std[i]), colors = slot.map(i => stickers[i]);
    if (sameAxis(cols[0], cols[1]) || sameAxis(cols[0], cols[2]) || sameAxis(cols[1], cols[2]))
      return { ok: false, code: "corner-impossible", colors, stickers: slot };
    if (triple(NORMAL[cols[0]], NORMAL[cols[1]], NORMAL[cols[2]]) > 0) return { ok: false, code: "corner-mirror", colors, stickers: slot };
    const key = cols.slice().sort().join("");
    if (seenC.has(key)) return { ok: false, code: "corner-twice", colors, stickers: [...seenC.get(key), ...slot] };
    seenC.set(key, slot);
  }
  const seenE = new Map();
  for (const slot of g.edges) {
    const cols = slot.map(i => std[i]), colors = slot.map(i => stickers[i]);
    if (sameAxis(cols[0], cols[1])) return { ok: false, code: "edge-impossible", colors, stickers: slot };
    const key = cols.slice().sort().join("");
    if (seenE.has(key)) return { ok: false, code: "edge-twice", colors, stickers: [...seenE.get(key), ...slot] };
    seenE.set(key, slot);
  }
  // the reference: 3×3 – the centres; 2×2 – the corner at the back, bottom left stays where it is
  let ref = COLORS.slice();
  if (n === 2) {
    const dbl = g.corners.find(s => g.face[s[0]] === D && s.some(i => g.face[i] === B) && s.some(i => g.face[i] === L));
    const at = f => stickers[dbl.find(i => g.face[i] === f)];
    ref[D] = at(D); ref[B] = at(B); ref[L] = at(L);
    const opp = { W: "Y", Y: "W", R: "O", O: "R", B: "G", G: "B" };
    ref[U] = opp[ref[D]]; ref[F] = opp[ref[B]]; ref[R] = opp[ref[L]];
  }
  const faceOf = {}; ref.forEach((c, f) => { faceOf[c] = f; });
  const state = stickers.map(c => faceOf[c]);
  // twist, flip and the parity of the piece permutation
  let twist = 0, flip = 0;
  const homeC = g.corners.map(s => s.map(i => g.face[i]).sort().join(""));
  const permC = g.corners.map(s => homeC.indexOf(s.map(i => state[i]).sort().join("")));
  g.corners.forEach(s => { twist += s.findIndex(i => state[i] === U || state[i] === D); });
  if (twist % 3) return { ok: false, code: "twist", stickers: [] };
  if (n === 3) {
    const homeE = g.edges.map(s => s.map(i => g.face[i]).sort().join(""));
    const permE = g.edges.map(s => homeE.indexOf(s.map(i => state[i]).sort().join("")));
    g.edges.forEach(s => {
      const [a, b] = s.map(i => state[i]);
      const good = a === U || a === D || (b !== U && b !== D && (a === F || a === B));
      flip += good ? 0 : 1;
    });
    if (flip % 2) return { ok: false, code: "flip", stickers: [] };
    if (parity(permC) !== parity(permE)) return { ok: false, code: "parity", stickers: [] };
  }
  return { ok: true, state, ref };
}
function parity(p) {
  const seen = new Array(p.length).fill(false); let par = 0;
  for (let i = 0; i < p.length; i++) {
    if (seen[i]) continue;
    let j = i, len = 0;
    while (!seen[j]) { seen[j] = true; j = p[j]; len++; }
    par += len - 1;
  }
  return par % 2;
}

// ---------------------------------------------------------------- 3×3: layer by layer (yellow on top, white at the bottom)
// an algorithm written for the green front, done with another side in front (the cube is never turned)
function conj(front, alg) {
  const k = SIDES.indexOf(front), map = { U: "U", D: "D" };
  ["F", "R", "B", "L"].forEach((x, i) => { map[x] = FACES[SIDES[(k + i) % 4]]; });
  return alg.split(" ").map(m => map[m[0]] + m.slice(1));
}
const next = s => SIDES[(SIDES.indexOf(s) + 1) % 4], prev = s => SIDES[(SIDES.indexOf(s) + 3) % 4];
const ALG = {
  sexy: "R U R' U'",
  right: "U R U' R' U' F' U F",              // middle layer: edge from the top front to the right
  left: "U' L' U L U F U' F'",               // … to the left
  ycross: "F R U R' U' F'",
  yedges: "R U R' U R U2 R' U",
  ycorners: "U R U' L' U R' U' L",
  ycornersInv: "L' U R U' L U R' U'",
  twist: "R' D' R D",
};

function solve3(state) {
  const g = geom(3), phases = [];
  let s = state.slice(), cur = [];
  const run = moves => { for (const m of moves) { s = apply(s, m, 3); cur.push(m); } };
  const findEdge = (a, b) => g.edges.find(e => { const x = s[e[0]], y = s[e[1]]; return (x === a && y === b) || (x === b && y === a); });
  const findCorner = set => g.corners.find(c => c.map(i => s[i]).sort().join("") === set);
  const ok = st => st.every(i => s[i] === g.face[i]);
  const faces = st => st.map(i => g.face[i]);
  const done = key => { phases.push({ key, moves: simplify(cur) }); cur = []; };
  const fail = what => { throw new Error("cube solver: " + what); };
  const upTo = (st, target) => {                         // turn the top until a top piece is at the side «target»
    for (let t = 0; t < 4; t++) {
      if (faces(st()).includes(target)) return;
      run(["U"]);
    }
    fail("top turn");
  };

  // 1. white cross
  for (const X of SIDES) {
    for (let guard = 0; ; guard++) {
      if (guard > 6) fail("cross");
      const e = findEdge(D, X), fs = faces(e);
      if (ok(e)) break;
      if (fs.includes(D)) { run([FACES[fs.find(f => f !== D)] + "2"]); continue; }
      if (!fs.includes(U)) {                             // in the middle layer: take it up without losing the cross
        for (const m of [FACES[fs[0]], FACES[fs[0]] + "'", FACES[fs[1]], FACES[fs[1]] + "'"]) {
          const st = apply(s, m, 3), up = g.edges.find(x => x.some(i => st[i] === D) && x.some(i => st[i] === X));
          if (faces(up).includes(U)) { run([m, "U", inverse(m)]); break; }
        }
        continue;
      }
      upTo(() => findEdge(D, X), X);
      const e2 = findEdge(D, X);
      if (s[e2[0]] === D) run([FACES[X] + "2"]);         // white looks up: half turn of the side
      else run(conj(X, "U' R' F R"));                     // white looks to the side
    }
  }
  done("cross");
  // 2. white corners
  for (const X of SIDES) {
    const Y = next(X), set = [D, X, Y].sort().join("");
    for (let guard = 0; ; guard++) {
      if (guard > 3) fail("corners");
      const c = findCorner(set);
      if (ok(c)) break;
      const fs = faces(c);
      if (fs.includes(D)) { const P = SIDES.find(p => fs.includes(p) && fs.includes(next(p))); run(conj(P, ALG.sexy)); continue; }
      const above = () => { const fc = faces(findCorner(set)); return fc.includes(X) && fc.includes(Y); };
      for (let t = 0; t < 4 && !above(); t++) run(["U"]);   // turn the top until the corner is above its place
      if (!above()) fail("corner align");
      // repeat R U R' U' until the corner sits – 4 or 5 times are the same as 2 or 1 times backwards
      const sexy = conj(X, ALG.sexy), reps = repeatsUntil(s, sexy, st => findCornerIn(st, set).every(i => st[i] === g.face[i]));
      if (reps < 0) fail("corner insert");
      run(reps > 3 ? [].concat(...Array(6 - reps).fill(invert(sexy))) : [].concat(...Array(reps).fill(sexy)));
    }
  }
  done("corners");
  // 3. middle layer
  for (const X of SIDES) {
    const Y = next(X);
    for (let guard = 0; ; guard++) {
      if (guard > 4) fail("middle");
      const e = findEdge(X, Y);
      if (ok(e)) break;
      const fs = faces(e);
      if (!fs.includes(U)) { const P = SIDES.find(p => fs.includes(p) && fs.includes(next(p))); run(conj(P, ALG.right)); continue; }
      const side = () => { const x = findEdge(X, Y); return x.find(i => g.face[i] !== U); };
      for (let t = 0; t < 4 && s[side()] !== g.face[side()]; t++) run(["U"]);
      const ee = findEdge(X, Y), front = g.face[side()], top = s[ee.find(i => g.face[i] === U)];
      if (s[side()] !== front) fail("middle align");
      run(conj(front, top === next(front) ? ALG.right : ALG.left));
    }
  }
  done("middle");
  // 4.–6. the last layer with a small search over the beginner algorithms
  const topEdges = g.edges.filter(e => g.face[e[0]] === U), topCorners = g.corners.filter(c => g.face[c[0]] === U);
  const lower = g.edges.filter(e => g.face[e[0]] !== U).concat(g.corners.filter(c => g.face[c[0]] !== U));
  const f2l = st => lower.every(p => p.every(i => st[i] === g.face[i]));
  const turns = [["U"], ["U'"], ["U2"]];
  const allSides = alg => SIDES.map(x => conj(x, alg));
  const search = (macros, goal, maxDepth, what) => {
    const path = macroSearch(s, macros, goal, maxDepth);
    if (!path) fail(what);
    run(path);
  };
  search(turns.concat(allSides(ALG.ycross)), st => topEdges.every(e => st[e[0]] === U) && f2l(st), 4, "yellow cross");
  done("ycross");
  search(turns.concat(allSides(ALG.yedges)), st => topEdges.every(e => st[e[0]] === U && st[e[1]] === g.face[e[1]]) && f2l(st), 4, "yellow edges");
  done("yedges");
  const cornerHome = (st, c) => c.map(i => st[i]).sort().join("") === c.map(i => g.face[i]).sort().join("");
  search(allSides(ALG.ycorners).concat(allSides(ALG.ycornersInv)),
    st => topCorners.every(c => cornerHome(st, c)) && topEdges.every(e => st[e[0]] === U && st[e[1]] === g.face[e[1]]) && f2l(st), 3, "yellow corners");
  done("ycorners");
  // 7. turn the corners: R' D' R D at the front right until yellow looks up, then the next corner to the front
  const ufr = g.corners.find(c => g.face[c[0]] === U && faces(c).includes(F) && faces(c).includes(R));
  for (let k = 0; k < 4; k++) {
    const tw = ALG.twist.split(" "), reps = repeatsUntil(s, tw, st => st[ufr[0]] === U);
    if (reps < 0) fail("corner twist");
    run(reps > 3 ? [].concat(...Array(6 - reps).fill(invert(tw))) : [].concat(...Array(reps).fill(tw)));
    run(["U"]);
  }
  if (!s.every((x, i) => x === g.face[i])) fail("not solved");
  done("yorient");
  return phases;
}

// how often an algorithm has to be repeated (0–5) until goal is true; -1: never
function repeatsUntil(state, alg, goal) {
  let st = state;
  for (let r = 0; r < 6; r++) { if (goal(st)) return r; st = applyAll(st, alg, 3); }
  return -1;
}
const findCornerIn = (st, set) => geom(3).corners.find(c => c.map(i => st[i]).sort().join("") === set);

// breadth-first over whole algorithms (macros); of the shortest macro paths the one with the fewest moves
function macroSearch(start, macros, goal, maxDepth) {
  if (goal(start)) return [];
  let level = [{ st: start, path: [] }];
  const seen = new Set([start.join(",")]);
  for (let d = 1; d <= maxDepth; d++) {
    const nextLevel = []; let best = null;
    for (const node of level) for (const m of macros) {
      const st = applyAll(node.st, m, 3), key = st.join(",");
      if (seen.has(key)) continue;
      seen.add(key);
      const path = node.path.concat(m);
      if (goal(st)) { if (!best || simplify(path).length < simplify(best).length) best = path; continue; }
      nextLevel.push({ st, path });
    }
    if (best) return best;
    level = nextLevel;
  }
  return null;
}

// ---------------------------------------------------------------- 2×2: the shortest way with U, R and F (IDA*)
// the corner at the back, bottom left never moves; corners as permutation + twist, tables of the distance
let T2 = null;
function tables2() {
  if (T2) return T2;
  const g = geom(2), C = g.corners, moves = [];
  for (const m of ["U", "U'", "U2", "R", "R'", "R2", "F", "F'", "F2"]) {
    const to = g.perms[m], cp = [], co = [];
    C.forEach((slot, i) => {                              // the piece in slot i goes to slot j, its twist grows by t
      const dest = to[slot[0]], j = C.findIndex(s => s.includes(dest));
      cp[i] = j; co[i] = C[j].indexOf(dest);
    });
    moves.push({ name: m, face: m[0], cp, co });
  }
  const fact = [1, 1, 2, 6, 24, 120, 720, 5040, 40320];
  const permIdx = p => { let idx = 0; for (let i = 0; i < 8; i++) { let c = 0; for (let j = i + 1; j < 8; j++) if (p[j] < p[i]) c++; idx += c * fact[7 - i]; } return idx; };
  const oriIdx = o => { let idx = 0; for (let i = 0; i < 8; i++) idx = idx * 3 + o[i]; return idx; };
  // state: piece[slot] and twist[slot]; a move: piece of slot i goes to slot cp[i] with twist + co[i]
  const step = (p, o, mv) => { const np = new Array(8), no = new Array(8); for (let i = 0; i < 8; i++) { np[mv.cp[i]] = p[i]; no[mv.cp[i]] = (o[i] + mv.co[i]) % 3; } return [np, no]; };
  const bfs = (size, idxOf, startKey) => {
    const dist = new Int8Array(size).fill(-1);
    let frontier = [startKey]; dist[idxOf(startKey)] = 0;
    for (let d = 0; frontier.length; d++) {
      const nf = [];
      for (const st of frontier) for (const mv of moves) {
        const ns = startKey.p ? { p: step(st.p, st.p.map(() => 0), mv)[0] } : { o: step([0, 1, 2, 3, 4, 5, 6, 7], st.o, mv)[1] };
        const ix = idxOf(ns);
        if (dist[ix] < 0) { dist[ix] = d + 1; nf.push(ns); }
      }
      frontier = nf;
    }
    return dist;
  };
  const distP = bfs(40320, x => permIdx(x.p), { p: [0, 1, 2, 3, 4, 5, 6, 7] });
  const distO = bfs(6561, x => oriIdx(x.o), { o: [0, 0, 0, 0, 0, 0, 0, 0] });
  return (T2 = { C, moves, permIdx, oriIdx, step, distP, distO });
}

function solve2(state) {
  const t = tables2(), g = geom(2);
  const home = t.C.map(s => s.map(i => g.face[i]).sort().join(""));
  let p = t.C.map(s => home.indexOf(s.map(i => state[i]).sort().join("")));
  let o = t.C.map(s => s.findIndex(i => state[i] === U || state[i] === D));
  const h = (pp, oo) => Math.max(t.distP[t.permIdx(pp)], t.distO[t.oriIdx(oo)]);
  const path = [];
  const dfs = (pp, oo, depth, last) => {
    const est = h(pp, oo);
    if (est === 0) return true;
    if (est > depth) return false;
    for (const mv of t.moves) {
      if (mv.face === last) continue;
      const [np, no] = t.step(pp, oo, mv);
      path.push(mv.name);
      if (dfs(np, no, depth - 1, mv.face)) return true;
      path.pop();
    }
    return false;
  };
  for (let depth = 0; depth <= 14; depth++) if (dfs(p, o, depth, "")) return [{ key: "solve2", moves: path.slice() }];
  throw new Error("cube solver: 2×2 not found");
}

// stickers (colour letters) → {ok, phases:[{key, moves}], ref} or the error of validate
function solve(stickers, n) {
  const v = validate(stickers, n);
  if (!v.ok) return v;
  const phases = (n === 2 ? solve2 : solve3)(v.state).filter(p => p.moves.length);
  return { ok: true, phases, ref: v.ref, total: phases.reduce((a, p) => a + p.moves.length, 0) };
}
// stickers for a scrambled cube (tests, «mix» button)
function scrambledColors(n, moves) { return applyAll(solvedColors(n), moves, n); }

const API = { FACES, COLORS, geom, apply, applyAll, inverse, invert, simplify, scramble, solvedState, solvedColors,
  scrambledColors, isSolved, validate, solve, solve2, solve3, conj };
if (typeof module !== "undefined" && module.exports) module.exports = API;
else root.CubeSolver = API;
// as a Web Worker: {id, n, stickers} → {id, result}
if (typeof importScripts === "function" && typeof window === "undefined") {
  root.onmessage = e => {
    const { id, n, stickers } = e.data || {};
    let result;
    try { result = solve(stickers, n); } catch (err) { result = { ok: false, code: "error", message: String(err && err.message) }; }
    root.postMessage({ id, result });
  };
}
})(typeof self !== "undefined" ? self : this);
