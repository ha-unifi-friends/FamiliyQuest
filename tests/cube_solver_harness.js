// Test harness of the cube solver (family_quest/app/web/cubesolver.js), run by tests/test_cube_solver.py:
//   node tests/cube_solver_harness.js [count3] [count2]
// Solves random scrambles of the 3×3 and the 2×2 and checks the moves, then lets the check of the colours reject
// impossible cubes. Prints one JSON line with the results; exit code 1 on the first failure.
"use strict";
const path = require("path");
const C = require(path.join(__dirname, "..", "family_quest", "app", "web", "cubesolver.js"));

const count3 = +(process.argv[2] || 2000), count2 = +(process.argv[3] || 300);
let seed = 12345;                                          // reproducible random numbers
const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
const fail = (msg, extra) => { console.log(JSON.stringify({ ok: false, msg, extra })); process.exit(1); };
const out = { ok: true };

for (const [n, count] of [[3, count3], [2, count2]]) {
  let total = 0, max = 0, ms = Date.now();
  for (let i = 0; i < count; i++) {
    const sc = C.scramble(n === 2 ? 15 : 25, n, rnd), st = C.scrambledColors(n, sc);
    const r = C.solve(st, n);
    if (!r.ok) fail("valid cube rejected", { n, scramble: sc.join(" "), r });
    const moves = r.phases.flatMap(p => p.moves);
    if (!C.isSolved(C.applyAll(st, moves, n), n)) fail("not solved", { n, scramble: sc.join(" ") });
    if (moves.some(m => !/^[URFDLB]['2]?$/.test(m))) fail("bad move", { n, moves });
    if (n === 2 && moves.length > 11) fail("2x2 longer than 11 moves", { scramble: sc.join(" "), moves });
    total += moves.length; max = Math.max(max, moves.length);
  }
  out["n" + n] = { count, avg: +(total / Math.max(1, count)).toFixed(1), max, msPerSolve: +((Date.now() - ms) / Math.max(1, count)).toFixed(2) };
}

// the phases of the 3×3 in order
const r3 = C.solve(C.scrambledColors(3, C.scramble(25, 3, rnd)), 3);
const order = ["cross", "corners", "middle", "ycross", "yedges", "ycorners", "yorient"];
const keys = r3.phases.map(p => p.key);
if (keys.some((k, i) => i && order.indexOf(k) <= order.indexOf(keys[i - 1]))) fail("phase order", keys);
// a solved cube needs no moves
if (C.solve(C.solvedColors(3), 3).total !== 0 || C.solve(C.solvedColors(2), 2).total !== 0) fail("solved cube has moves");

// impossible cubes are rejected with the right code
const g = C.geom(3), base = C.scrambledColors(3, C.scramble(25, 3, rnd));
const expect = (st, n, code, what) => { const r = C.validate(st, n); if (r.ok || r.code !== code) fail("expected " + code + " for " + what, r); };
{ // one corner twisted
  const st = base.slice(), c = g.corners[0], [a, b, d] = c.map(i => st[i]); st[c[0]] = d; st[c[1]] = a; st[c[2]] = b;
  expect(st, 3, "twist", "twisted corner");
}
{ // one edge flipped
  const st = base.slice(), e = g.edges[0], a = st[e[0]]; st[e[0]] = st[e[1]]; st[e[1]] = a;
  expect(st, 3, "flip", "flipped edge");
}
{ // two edges swapped
  const st = base.slice(), [e1, e2] = [g.edges[0], g.edges[5]];
  for (let k = 0; k < 2; k++) { const x = st[e1[k]]; st[e1[k]] = st[e2[k]]; st[e2[k]] = x; }
  expect(st, 3, "parity", "two swapped edges");
}
{ // two stickers of a corner swapped (mirror)
  const st = C.solvedColors(3), c = g.corners[2], x = st[c[1]]; st[c[1]] = st[c[2]]; st[c[2]] = x;
  expect(st, 3, "corner-mirror", "mirrored corner");
}
{ // a corner with white and yellow: swap stickers between two corners
  const st = C.solvedColors(3), cu = g.corners.find(c => st[c[0]] === "Y"), cd = g.corners.find(c => st[c[0]] === "W");
  const x = st[cu[1]]; st[cu[1]] = st[cd[0]]; st[cd[0]] = x;
  expect(st, 3, "corner-impossible", "white-yellow corner");
}
{ // an edge red-orange
  const st = C.solvedColors(3), er = g.edges.find(e => st[e[1]] === "R" && st[e[0]] === "Y"), eo = g.edges.find(e => st[e[1]] === "O" && st[e[0]] === "Y");
  const x = st[er[0]]; st[er[0]] = st[eo[1]]; st[eo[1]] = x;
  expect(st, 3, "edge-impossible", "red-orange edge");
}
{ // wrong count and blanks
  const st = C.solvedColors(3); st[0] = "W"; expect(st, 3, "count", "too many white");
  const st2 = C.solvedColors(3); st2[5] = ""; expect(st2, 3, "blank", "unpainted sticker");
}
{ // 2×2: twisted corner
  const g2 = C.geom(2), st = C.scrambledColors(2, C.scramble(15, 2, rnd)), c = g2.corners[3], [a, b, d] = c.map(i => st[i]);
  st[c[0]] = d; st[c[1]] = a; st[c[2]] = b;
  expect(st, 2, "twist", "2x2 twisted corner");
  // 2×2 held in any position (a whole-cube turn of a solved cube) is valid and solved with no moves
  const turned = C.applyAll(C.solvedColors(2), ["U", "D'"], 2);
  if (C.solve(turned, 2).total !== 0) fail("turned 2x2");
  const r = C.solve(C.applyAll(C.solvedColors(2), ["R", "L'", "U"], 2), 2);
  if (!r.ok || r.total > 2) fail("2x2 R L' U", r);
}
out.rejects = 10;
console.log(JSON.stringify(out));
