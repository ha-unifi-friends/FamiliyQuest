// Game corner: small games that run on this device only – Tic-Tac-Toe, Sudoku, Patience and Ping-Pong.
// Alone against the app or two players on one tablet. Nothing is sent to the server; best results stay in this browser.
"use strict";

const ARCADE = {
  ttt: { icon: "⭕", title: T("Tic-Tac-Toe"), text: T("Three in a row – against the app or a second player.") },
  sudoku: { icon: "🔢", title: T("Sudoku"), text: T("Every number once in each row, column and box. From 4×4 to 9×9.") },
  patience: { icon: "🃏", title: T("Patience"), text: T("Sort all cards by suit onto the four piles.") },
  pingpong: { icon: "🏓", title: T("Ping-Pong"), text: T("Bounce the ball back – against the app or face to face on one tablet.") },
  pairs: { icon: "🧩", title: T("Pairs"), text: T("Turn over two cards – find the pairs. Alone, against the app or with up to four players.") },
};

const arcadeStore = {
  key: () => "fq.arcade." + ((S.profile && S.profile.id) || 0),
  get() { try { return JSON.parse(localStorage.getItem(this.key())) || {}; } catch { return {}; } },
  set(k, v) { try { const d = this.get(); d[k] = v; localStorage.setItem(this.key(), JSON.stringify(d)); } catch {} },
};
const mmss = s => Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0");

function arcadeCard() {
  const open = Object.keys(ARCADE).filter(k => canPlay(k));
  if (!open.length) return null;
  return h("section.card", h("h2", "🕹️ ", T("Game corner")),
    h("p.small.muted", T("Small games for in between – alone or with two on one device.")),
    h("div.arcade-grid", ...Object.entries(ARCADE).filter(([k]) => open.includes(k)).map(([k, g]) => h("button.arcade-tile", { onclick: () => go("arcade/" + k) },
      h("span.big-ic", g.icon), h("strong", g.title)))));
}

function arcadeView(kind) {
  const g = ARCADE[kind];
  if (!g || !canPlay(kind)) return go("games");
  // full screen like the family quiz: no menus, the game uses the whole height
  const box = h("div.arcade-box");
  screen("games", h("div.quiz-full.arcade-full",
    h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => go("games") }, "✕"),
    h("div.quiz-head", h("h1", g.icon, " ", g.title), h("button.icon-btn", { title: T("Rules"), onclick: () => toast(I18N.tr(g.text)) }, "ℹ️")), box));
  document.body.classList.add("quiz-open");
  ({ ttt: tttGame, sudoku: sudokuGame, patience: patienceGame, pingpong: pingpongGame, pairs: pairsGame })[kind](box);
}

function segmented(options, value, onchange) {
  const wrap = h("div.seg");
  const draw = () => wrap.replaceChildren(...options.map(([v, label]) => h("button" + (v === value ? ".on" : ""), { onclick: () => { value = v; draw(); onchange(v); } }, label)));
  draw();
  return wrap;
}

// ---------------------------------------------------------------- Tic-Tac-Toe
const TTT_LINES = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]];
function tttWinner(b) {
  for (const l of TTT_LINES) if (b[l[0]] && b[l[0]] === b[l[1]] && b[l[0]] === b[l[2]]) return { who: b[l[0]], line: l };
  return b.every(Boolean) ? { who: "draw", line: [] } : null;
}
function tttBest(b, me) {             // minimax: the best cell for «me»
  const other = me === "X" ? "O" : "X";
  const score = (bb, turn, depth) => {
    const w = tttWinner(bb);
    if (w) return w.who === me ? 10 - depth : w.who === "draw" ? 0 : depth - 10;
    const vals = [];
    bb.forEach((v, i) => { if (!v) { bb[i] = turn; vals.push(score(bb, turn === "X" ? "O" : "X", depth + 1)); bb[i] = null; } });
    return turn === me ? Math.max(...vals) : Math.min(...vals);
  };
  let best = -99, cells = [];
  b.forEach((v, i) => { if (!v) { b[i] = me; const s = score(b, other, 1); b[i] = null; if (s > best) { best = s; cells = [i]; } else if (s === best) cells.push(i); } });
  return cells[Math.floor(Math.random() * cells.length)];
}

async function tttGame(box) {
  let duel = null;
  try { duel = await api("community/duel"); } catch {}
  if (duel) return tttOnline(box);
  const saved = arcadeStore.get().ttt || {};
  let mode = saved.mode || "easy", board, turn, starter = "X", done = null, score = { X: 0, O: 0, draw: 0 };
  const names = () => mode === "two" ? { X: T("Player 1"), O: T("Player 2") } : { X: T("You"), O: T("App") };
  const status = h("p.center.ttt-status"), grid = h("div.ttt-grid"), tally = h("div.row.center.wrap.ttt-tally");
  const reset = () => { board = Array(9).fill(null); turn = starter; done = null; draw(); botMove(); };
  const botMove = () => {
    if (mode === "two" || turn !== "O" || done) return;
    setTimeout(() => {
      const free = board.map((v, i) => v ? -1 : i).filter(i => i >= 0);
      const smart = mode === "hard" || (mode === "medium" && Math.random() < 0.7) || (mode === "easy" && Math.random() < 0.3);
      play(smart ? tttBest(board, "O") : free[Math.floor(Math.random() * free.length)]);
    }, 450);
  };
  const play = i => {
    if (board[i] || done) return;
    board[i] = turn; try { Sound.play("tap"); } catch {}
    done = tttWinner(board);
    if (done) {
      score[done.who]++; starter = starter === "X" ? "O" : "X";
      if (done.who === "X" || (mode === "two" && done.who === "O")) { confetti(); try { Sound.play("done"); } catch {} }
    } else turn = turn === "X" ? "O" : "X";
    draw(); botMove();
  };
  const draw = () => {
    const n = names();
    grid.replaceChildren(...board.map((v, i) => h("button.ttt-cell" + (v ? "." + v.toLowerCase() : "") + (done && done.line.includes(i) ? ".win" : ""),
      { disabled: !!v || !!done || (mode !== "two" && turn === "O"), onclick: () => play(i), "aria-label": String(i + 1) }, v === "X" ? "✕" : v === "O" ? "◯" : "")));
    status.replaceChildren(done ? (done.who === "draw" ? T("Draw!") : h("span", I18N.tr(T("Winner: {0}")).replace("{0}", I18N.tr(n[done.who])))) :
      h("span", I18N.tr(T("Turn: {0}")).replace("{0}", I18N.tr(n[turn])), " ", turn === "X" ? "✕" : "◯"));
    tally.replaceChildren(h("span.chip", "✕ ", n.X, ": ", String(score.X)), h("span.chip", T("Draw"), ": ", String(score.draw)), h("span.chip", "◯ ", n.O, ": ", String(score.O)));
  };
  const modes = segmented([["easy", T("easy")], ["medium", T("medium")], ["hard", T("unbeatable")], ["two", "👥 " + I18N.tr(T("Two players"))],
    ["online", "📱 " + I18N.tr(T("Two devices"))]], mode,
    v => { if (v === "online") return tttOnline(box); mode = v; arcadeStore.set("ttt", { mode }); score = { X: 0, O: 0, draw: 0 }; starter = "X"; reset(); });
  box.replaceChildren(h("section.card", modes, status, grid, tally,
    h("div.row.center", h("button.btn", { onclick: reset }, "🔄 ", T("New round")))));
  reset();
}

// Tic-Tac-Toe between two devices: invite somebody of the family, both see the same board (the server keeps it)
function tttOnline(box) {
  let st = null, last = "", timer = null, cheered = -1;
  const body = h("div");
  const stop = () => clearInterval(timer);
  const back = async () => { stop(); try { await api("community/duel/leave", { method: "POST" }); } catch {} tttGame(box); };
  const act = async (path, b) => { try { st = await api("community/duel/" + path, { method: "POST", body: b }); draw(true); } catch (e) { toast(e.message, "bad"); } };
  const poll = async () => {
    if (!box.isConnected) return stop();
    try { st = await api("community/duel"); draw(); } catch {}
  };
  const pickOpponent = async () => {
    let list = [];
    try { list = await api("community/duel/opponents"); } catch (e) { toast(e.message, "bad"); }
    body.replaceChildren(h("h2", T("Who do you want to play with?")),
      list.length ? h("div.arcade-grid", ...list.map(o => h("button.arcade-tile", { disabled: o.busy, onclick: async () => {
        try { st = await api("community/duel", { method: "POST", body: { opponent: o.id } }); draw(true); } catch (e) { toast(e.message, "bad"); }
      } }, avatarSvg(o.avatar, 56), C(o.name, "strong"), o.busy ? h("span.small.muted", T("is playing")) : null)))
        : h("p.muted", T("Nobody else can play right now.")));
  };
  const draw = (force = false) => {
    const key = JSON.stringify(st);
    if (!force && key === last) return;
    last = key;
    if (!st) return pickOpponent();
    const other = st.names[st.me === "X" ? "O" : "X"], mine = st.me === "X" ? "✕" : "◯";
    if (st.status === "invite") return body.replaceChildren(h("div.center",
      h("p.ttt-status", st.host ? I18N.tr(T("Waiting for {0} …")).replace("{0}", other) : I18N.tr(T("{0} invites you to Tic-Tac-Toe")).replace("{0}", other)),
      st.host ? h("button.btn.ghost", { onclick: back }, T("Cancel"))
        : h("div.row.center", h("button.btn", { onclick: () => act("accept") }, "▶ ", T("Play")), h("button.btn.ghost", { onclick: back }, T("No thanks")))));
    if (st.status === "declined" || st.status === "gone") return body.replaceChildren(h("div.center",
      h("p.ttt-status", I18N.tr(st.status === "declined" ? T("{0} does not want to play right now.") : T("{0} has left the game.")).replace("{0}", other)),
      h("button.btn", { onclick: back }, "← ", T("Back"))));
    const myTurn = st.status === "play" && st.turn === st.me;
    const round = st.score.X + st.score.O + st.score.draw;
    if (st.status === "done" && st.result === st.me && round !== cheered) { cheered = round; confetti(); try { Sound.play("done"); } catch {} }
    body.replaceChildren(
      h("p.center.ttt-status", st.status === "done" ? (st.result === "draw" ? T("Draw!") : I18N.tr(T("Winner: {0}")).replace("{0}", st.names[st.result]))
        : myTurn ? h("span", T("Your turn"), " ", mine) : I18N.tr(T("Turn: {0}")).replace("{0}", other)),
      h("div.ttt-grid", ...st.board.map((v, i) => h("button.ttt-cell" + (v ? "." + v.toLowerCase() : "") + (st.line.includes(i) ? ".win" : ""),
        { disabled: !myTurn || !!v, onclick: () => act("move", { cell: i }) }, v === "X" ? "✕" : v === "O" ? "◯" : ""))),
      h("div.row.center.wrap.ttt-tally", h("span.chip", "✕ ", C(st.names.X), ": ", String(st.score.X)), h("span.chip", T("Draw"), ": ", String(st.score.draw)),
        h("span.chip", "◯ ", C(st.names.O), ": ", String(st.score.O))),
      h("div.row.center", st.status === "done" ? h("button.btn", { onclick: () => act("again") }, "🔄 ", T("New round")) : null,
        h("button.btn.ghost", { onclick: back }, T("Leave"))));
  };
  box.replaceChildren(h("section.card", h("div.row", h("h2.grow", "📱 ", T("Two devices")),
    h("button.btn.ghost.small", { onclick: back }, "← ", T("Against the app"))), body));
  poll(); timer = setInterval(poll, 1200);
}

// ---------------------------------------------------------------- Sudoku
const SUDOKU_LEVELS = {
  mini: { n: 4, br: 2, bc: 2, givens: 6, label: T("4×4 for beginners") },
  six: { n: 6, br: 2, bc: 3, givens: 14, label: T("6×6") },
  easy: { n: 9, br: 3, bc: 3, givens: 38, label: T("9×9 easy") },
  medium: { n: 9, br: 3, bc: 3, givens: 31, label: T("9×9 medium") },
  hard: { n: 9, br: 3, bc: 3, givens: 26, label: T("9×9 hard") },
};

function sudokuCandidates(g, L, i) {
  const { n, br, bc } = L, r = Math.floor(i / n), c = i % n, used = new Set();
  for (let k = 0; k < n; k++) { used.add(g[r * n + k]); used.add(g[k * n + c]); }
  const r0 = r - r % br, c0 = c - c % bc;
  for (let y = 0; y < br; y++) for (let x = 0; x < bc; x++) used.add(g[(r0 + y) * n + c0 + x]);
  const out = [];
  for (let v = 1; v <= n; v++) if (!used.has(v)) out.push(v);
  return out;
}
// counts solutions up to «limit»; fills g with the first one when fill = true
function sudokuSolve(g, L, limit = 2, fill = false, random = false) {
  let count = 0;
  const rec = () => {
    let best = -1, cands = null;
    for (let i = 0; i < g.length; i++) if (!g[i]) {
      const c = sudokuCandidates(g, L, i);
      if (!c.length) return false;
      if (!cands || c.length < cands.length) { best = i; cands = c; if (c.length === 1) break; }
    }
    if (best < 0) { count++; return fill || count >= limit; }
    if (random) cands.sort(() => Math.random() - 0.5);
    for (const v of cands) { g[best] = v; if (rec()) return true; }
    g[best] = 0;
    return false;
  };
  rec();
  return count;
}
function sudokuNew(L) {
  const sol = Array(L.n * L.n).fill(0);
  sudokuSolve(sol, L, 1, true, true);
  const puzzle = sol.slice(), order = [...puzzle.keys()].sort(() => Math.random() - 0.5);
  let filled = puzzle.length;
  for (const i of order) {
    if (filled <= L.givens) break;
    const keep = puzzle[i]; puzzle[i] = 0;
    if (sudokuSolve(puzzle.slice(), L, 2) !== 1) puzzle[i] = keep; else filled--;
  }
  return { sol, puzzle };
}

function sudokuGame(box) {
  let level = arcadeStore.get().sudoku_level || "mini", L, game, cur, sel = -1, start, timer, mistakes = 0, won = false;
  const gridBox = h("div"), pad = h("div.sd-pad"), info = h("p.center.muted");
  const fresh = () => {
    L = SUDOKU_LEVELS[level]; game = sudokuNew(L); cur = game.puzzle.slice(); sel = -1; mistakes = 0; won = false; start = Date.now();
    clearInterval(timer); timer = setInterval(() => { if (!box.isConnected) return clearInterval(timer); if (!won) drawInfo(); }, 1000);
    draw();
  };
  const best = () => (arcadeStore.get().sudoku_best || {})[level];
  const drawInfo = () => info.replaceChildren(I18N.tr(T("Time")) + " " + mmss((Date.now() - start) / 1000), " · ", I18N.tr(T("Mistakes")) + " " + mistakes,
    best() ? " · 🏆 " + mmss(best()) : "");
  const put = v => {
    if (sel < 0 || game.puzzle[sel] || won) return;
    cur[sel] = v;
    if (v && v !== game.sol[sel]) { mistakes++; try { Sound.play("wrong"); } catch {} } else if (v) { try { Sound.play("tap"); } catch {} }
    if (cur.every((x, i) => x === game.sol[i])) {
      won = true; const secs = Math.round((Date.now() - start) / 1000);
      const b = arcadeStore.get().sudoku_best || {};
      if (!b[level] || secs < b[level]) { b[level] = secs; arcadeStore.set("sudoku_best", b); }
      confetti(); try { Sound.play("done"); } catch {}
      toast(I18N.tr(T("Solved in {0}!")).replace("{0}", mmss(secs)), "good");
    }
    draw();
  };
  const draw = () => {
    const { n, br, bc } = L, sv = sel >= 0 ? cur[sel] : 0;
    const grid = h("div.sd-grid", { style: { "--n": n } }, ...cur.map((v, i) => {
      const r = Math.floor(i / n), c = i % n, given = !!game.puzzle[i];
      const cls = (given ? ".given" : "") + (i === sel ? ".sel" : "") + (v && v === sv ? ".same" : "") + (v && !given && v !== game.sol[i] ? ".bad" : "") +
        ((c + 1) % bc === 0 && c < n - 1 ? ".br" : "") + ((r + 1) % br === 0 && r < n - 1 ? ".bb" : "") +
        (sel >= 0 && (Math.floor(sel / n) === r || sel % n === c) ? ".line" : "");
      return h("button.sd-cell" + cls, { onclick: () => { sel = i; draw(); } }, v ? String(v) : "");
    }));
    gridBox.replaceChildren(grid);
    const left = v => cur.filter(x => x === v).length >= n;
    pad.replaceChildren(...Array.from({ length: n }, (_, k) => h("button.btn" + (left(k + 1) ? ".ghost" : ""), { onclick: () => put(k + 1) }, String(k + 1))),
      h("button.btn.ghost", { title: T("Delete"), onclick: () => put(0) }, "⌫"));
    drawInfo();
  };
  const levels = h("select", { onchange: e => { level = e.target.value; arcadeStore.set("sudoku_level", level); fresh(); } },
    ...Object.entries(SUDOKU_LEVELS).map(([k, l]) => h("option", { value: k, selected: k === level }, I18N.tr(l.label))));
  box.replaceChildren(h("section.card.sd-card", h("div.row", h("label.field.grow", T("Level"), levels),
      h("button.btn.ghost", { onclick: fresh }, "🔄 ", T("New puzzle"))), info, gridBox, pad));
  document.addEventListener("keydown", function key(e) {
    if (!box.isConnected) return document.removeEventListener("keydown", key);
    if (/^[1-9]$/.test(e.key) && +e.key <= L.n) put(+e.key);
    else if (e.key === "Backspace" || e.key === "Delete" || e.key === "0") put(0);
    else if (sel >= 0 && e.key.startsWith("Arrow")) {
      const d = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -L.n, ArrowDown: L.n }[e.key];
      if (sel + d >= 0 && sel + d < cur.length) { sel += d; draw(); e.preventDefault(); }
    }
  });
  fresh();
}

// ---------------------------------------------------------------- Patience (Klondike)
const PT_SUITS = ["s", "h", "d", "c"];
const PT_SIGN = { s: "♠︎", h: "♥︎", d: "♦︎", c: "♣︎" };
const PT_RANK = r => ({ 1: "A", 11: "J", 12: "Q", 13: "K" })[r] || String(r);
const ptRed = c => c.s === "h" || c.s === "d";

function patienceGame(box) {
  let drawN = (arcadeStore.get().patience || {}).draw || 1, st, sel = null, undo = [], moves = 0, start, won = false, timer;
  const area = h("div.pt-area"), info = h("p.center.muted.small");
  const deal = () => {
    const deck = [];
    for (const s of PT_SUITS) for (let r = 1; r <= 13; r++) deck.push({ s, r, up: false });
    deck.sort(() => Math.random() - 0.5);
    const tab = [];
    for (let i = 0; i < 7; i++) { tab.push(deck.splice(0, i + 1)); tab[i][i].up = true; }
    st = { stock: deck, waste: [], found: [[], [], [], []], tab };
    sel = null; undo = []; moves = 0; start = Date.now(); won = false;
    clearInterval(timer); timer = setInterval(() => { if (!box.isConnected) return clearInterval(timer); if (!won) drawInfo(); }, 1000);
    draw();
  };
  const snap = () => { undo.push(JSON.stringify(st)); if (undo.length > 200) undo.shift(); };
  const flipTops = () => st.tab.forEach(col => { if (col.length && !col[col.length - 1].up) col[col.length - 1].up = true; });
  const fitsFound = (c, f) => f.length ? f[f.length - 1].s === c.s && f[f.length - 1].r === c.r - 1 : c.r === 1;
  const fitsTab = (c, col) => col.length ? (col[col.length - 1].up && ptRed(col[col.length - 1]) !== ptRed(c) && col[col.length - 1].r === c.r + 1) : c.r === 13;
  const cardsOf = s => s.from === "waste" ? [st.waste[st.waste.length - 1]] : s.from === "found" ? [st.found[s.col][st.found[s.col].length - 1]] : st.tab[s.col].slice(s.idx);
  const take = s => { if (s.from === "waste") st.waste.pop(); else if (s.from === "found") st.found[s.col].pop(); else st.tab[s.col].splice(s.idx); };
  const moveTo = (s, dest) => {          // dest: {to: "found"|"tab", col}
    const cards = cardsOf(s);
    if (!cards.length || !cards[0]) return false;
    if (dest.to === "found") { if (cards.length !== 1 || !fitsFound(cards[0], st.found[dest.col])) return false; }
    else if (s.from === "tab" && s.col === dest.col) return false;
    else if (!fitsTab(cards[0], st.tab[dest.col])) return false;
    snap(); take(s);
    (dest.to === "found" ? st.found[dest.col] : st.tab[dest.col]).push(...cards);
    moves++; flipTops(); sel = null; try { Sound.play("tap"); } catch {}
    checkWin(); return true;
  };
  const smart = s => {                   // the obvious move: a pile first, then another column (not an empty one for a king that is already at the bottom)
    const cards = cardsOf(s);
    if (cards.length === 1) for (let f = 0; f < 4; f++) if (moveTo(s, { to: "found", col: f })) return true;
    for (let k = 1; k <= 7; k++) {
      const col = s.from === "tab" ? (s.col + k) % 7 : k - 1;
      if (!st.tab[col].length && s.from === "tab" && s.idx === 0) continue;
      if (moveTo(s, { to: "tab", col })) return true;
    }
    return false;
  };
  const tapCard = s => {
    if (won) return;
    if (sel && !(sel.from === s.from && sel.col === s.col && sel.idx === s.idx)) {
      const dest = s.from === "found" ? { to: "found", col: s.col } : s.from === "tab" ? { to: "tab", col: s.col } : null;
      if (dest && moveTo(sel, dest)) return draw();
    }
    if (sel && sel.from === s.from && sel.col === s.col && sel.idx === s.idx) { sel = null; return draw(); }
    if (!smart(s)) { sel = s; try { Sound.play("wrong"); } catch {} }
    draw();
  };
  const tapEmpty = dest => { if (sel && moveTo(sel, dest)) return draw(); sel = null; draw(); };
  const tapStock = () => {
    if (won) return;
    snap(); sel = null;
    if (!st.stock.length) { st.waste.reverse().forEach(c => { c.up = false; }); st.stock = st.waste; st.waste = []; }
    else for (let i = 0; i < drawN && st.stock.length; i++) { const c = st.stock.pop(); c.up = true; st.waste.push(c); }
    moves++; draw();
  };
  const canFinish = () => !st.stock.length && !st.waste.length && st.tab.every(col => col.every(c => c.up));
  const finish = () => {
    const step = () => {
      for (let col = 0; col < 7; col++) {
        const t = st.tab[col]; if (!t.length) continue;
        for (let f = 0; f < 4; f++) if (fitsFound(t[t.length - 1], st.found[f])) { st.found[f].push(t.pop()); moves++; draw(); checkWin(); return won || setTimeout(step, 90); }
      }
    };
    snap(); step();
  };
  const checkWin = () => {
    if (won || st.found.some(f => f.length < 13)) return;
    won = true; const secs = Math.round((Date.now() - start) / 1000);
    const b = arcadeStore.get().patience_best;
    if (!b || secs < b) arcadeStore.set("patience_best", secs);
    confetti(); try { Sound.play("done"); } catch {}
    toast(I18N.tr(T("All sorted in {0}!")).replace("{0}", mmss(secs)), "good");
  };
  const card = (c, opts = {}) => c.up
    ? h("div.pt-card" + (ptRed(c) ? ".red" : "") + (opts.sel ? ".sel" : ""), { style: opts.style, translate: "no", onclick: opts.onclick },
        h("span.pt-ix", PT_RANK(c.r), PT_SIGN[c.s]), h("span.pt-big", PT_SIGN[c.s]))
    : h("div.pt-card.back", { style: opts.style, onclick: opts.onclick });
  const isSel = (from, col, idx) => sel && sel.from === from && sel.col === col && (from !== "tab" || idx >= sel.idx);
  const drawInfo = () => info.replaceChildren(I18N.tr(T("Time")) + " " + mmss((Date.now() - start) / 1000), " · ", I18N.tr(T("Moves")) + " " + moves,
    arcadeStore.get().patience_best ? " · 🏆 " + mmss(arcadeStore.get().patience_best) : "");
  const draw = () => {
    const w = st.waste;
    const top = h("div.pt-row",
      h("div.pt-slot" + (st.stock.length ? "" : ".empty"), { onclick: tapStock }, st.stock.length ? card({ up: false }) : h("span", "↻")),
      h("div.pt-slot.waste", w.length ? card(w[w.length - 1], { sel: isSel("waste"), onclick: () => tapCard({ from: "waste" }) }) : null),
      h("div"),
      ...st.found.map((f, i) => h("div.pt-slot.found", { onclick: f.length ? null : () => tapEmpty({ to: "found", col: i }) },
        f.length ? card(f[f.length - 1], { sel: isSel("found", i), onclick: () => tapCard({ from: "found", col: i }) }) : h("span", "A"))));
    const cols = h("div.pt-row.tab", ...st.tab.map((col, ci) => {
      let y = 0;
      return h("div.pt-col", { onclick: e => { if (e.target.classList.contains("pt-col")) tapEmpty({ to: "tab", col: ci }); } },
        ...col.map((c, i) => {
          const el = card(c, { sel: isSel("tab", ci, i), style: { top: y + "px" }, onclick: c.up ? () => tapCard({ from: "tab", col: ci, idx: i }) : null });
          y += c.up ? 24 : 9;
          return el;
        }));
    }));
    area.replaceChildren(top, cols);
    area.querySelectorAll(".pt-col").forEach((el, ci) => { const col = st.tab[ci]; el.style.minHeight = (col.reduce((a, c) => a + (c.up ? 24 : 9), 0) + 80) + "px"; });
    finBtn.hidden = won || !canFinish();
    undoBtn.disabled = !undo.length || won;
    drawInfo();
  };
  const finBtn = h("button.btn.good", { onclick: finish }, "⚡ ", T("Finish"));
  const undoBtn = h("button.btn.ghost", { onclick: () => { if (undo.length) { st = JSON.parse(undo.pop()); sel = null; draw(); } } }, "↶ ", T("Undo"));
  const drawSel = segmented([[1, T("draw 1")], [3, T("draw 3")]], drawN, v => { drawN = v; arcadeStore.set("patience", { draw: v }); deal(); });
  box.replaceChildren(h("section.card.pt-card-box", h("div.row.wrap", drawSel, h("span.grow"), undoBtn, h("button.btn.ghost", { onclick: deal }, "🔄 ", T("New game"))),
    info, area, h("div.row.center", finBtn),
    h("p.small.muted.arcade-hint", T("Tap a card: it moves to where it fits. If it fits nowhere, it stays marked – then tap where it should go."))));
  deal();
}

// ---------------------------------------------------------------- Ping-Pong
function pingpongGame(box) {
  const saved = arcadeStore.get().pingpong || {};
  let mode = saved.mode || "medium", to = 7;
  const W = 400, H = 640, PW = 80, PH = 12, R = 9;
  const canvas = h("canvas.pp-canvas", { width: W, height: H });
  const ctx = canvas.getContext("2d");
  let s, last = 0, paused = true;
  const reset = () => { s = { p1: W / 2, p2: W / 2, sc1: 0, sc2: 0, over: false }; serve(1); paused = true; render(); };
  const serve = dir => {                // dir 1: towards the bottom player
    const a = (Math.random() * 0.8 - 0.4);
    Object.assign(s, { bx: W / 2, by: H / 2, vx: Math.sin(a) * 260, vy: dir * Math.cos(a) * 260, wait: 0.8 });
  };
  const botSpeed = () => ({ easy: 170, medium: 260, hard: 400 })[mode] || 260;
  const step = dt => {
    if (s.over) return;
    if (s.wait > 0) { s.wait -= dt; return; }
    if (mode !== "two") {                 // the app plays the top paddle: follows the ball when it comes
      const target = s.vy < 0 ? s.bx + (mode === "easy" ? Math.sin(Date.now() / 300) * 30 : 0) : W / 2;
      const d = target - s.p2, m = botSpeed() * dt;
      s.p2 += Math.max(-m, Math.min(m, d));
    }
    s.bx += s.vx * dt; s.by += s.vy * dt;
    if (s.bx < R) { s.bx = R; s.vx = Math.abs(s.vx); } else if (s.bx > W - R) { s.bx = W - R; s.vx = -Math.abs(s.vx); }
    const hit = (px, py, dirOut) => {
      if (Math.abs(s.bx - px) <= PW / 2 + R && Math.abs(s.by - py) <= PH / 2 + R && Math.sign(s.vy) === -dirOut) {
        const off = (s.bx - px) / (PW / 2), speed = Math.min(Math.hypot(s.vx, s.vy) * 1.06, 900);
        const a = off * 1.0;
        s.vx = Math.sin(a) * speed; s.vy = dirOut * Math.cos(a) * speed; s.by = py + dirOut * (PH / 2 + R);
        try { Sound.play("tap"); } catch {}
      }
    };
    hit(s.p1, H - 30, -1); hit(s.p2, 30, 1);
    if (s.by > H + R) { s.sc2++; point(1); } else if (s.by < -R) { s.sc1++; point(-1); }
  };
  const point = dir => {
    if (s.sc1 >= to || s.sc2 >= to) {
      s.over = true;
      if (s.sc1 >= to || mode === "two") { confetti(); try { Sound.play("done"); } catch {} }
    } else serve(dir);
  };
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#5b5bd6";
  const render = () => {
    ctx.fillStyle = "#14532d"; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 3; ctx.strokeRect(6, 6, W - 12, H - 12);
    ctx.setLineDash([10, 10]); ctx.beginPath(); ctx.moveTo(6, H / 2); ctx.lineTo(W - 6, H / 2); ctx.stroke(); ctx.setLineDash([]);
    ctx.font = "bold 44px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.fillText(String(s.sc2), W / 2, H / 2 - 30); ctx.fillText(String(s.sc1), W / 2, H / 2 + 70);
    ctx.fillStyle = css("--ans-2"); ctx.fillRect(s.p1 - PW / 2, H - 30 - PH / 2, PW, PH);
    ctx.fillStyle = css("--ans-4"); ctx.fillRect(s.p2 - PW / 2, 30 - PH / 2, PW, PH);
    ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(s.bx, s.by, R, 0, Math.PI * 2); ctx.fill();
    if (paused || s.over) {
      ctx.fillStyle = "rgba(0,0,0,.45)"; ctx.fillRect(0, H / 2 - 60, W, 120); ctx.fillStyle = "#fff"; ctx.font = "bold 26px system-ui, sans-serif";
      const n1 = mode === "two" ? I18N.tr(T("Player 1")) : I18N.tr(T("You")), n2 = mode === "two" ? I18N.tr(T("Player 2")) : I18N.tr(T("App"));
      ctx.fillText(s.over ? I18N.tr(T("Winner: {0}")).replace("{0}", s.sc1 > s.sc2 ? n1 : n2) : I18N.tr(T("Tap to start")), W / 2, H / 2 + 9);
    }
  };
  const loop = t => {
    if (!box.isConnected) return;
    const dt = Math.min(0.033, (t - (last || t)) / 1000); last = t;
    if (!paused) step(dt);
    render();
    requestAnimationFrame(loop);
  };
  const toCanvas = e => { const r = canvas.getBoundingClientRect(); return [(e.clientX - r.left) * W / r.width, (e.clientY - r.top) * H / r.height]; };
  const movePointer = e => {
    const [x, y] = toCanvas(e), px = Math.max(PW / 2, Math.min(W - PW / 2, x));
    if (y > H / 2 || mode !== "two") s.p1 = px; else s.p2 = px;
  };
  canvas.addEventListener("pointerdown", e => { if (s.over) reset(); if (paused) { paused = false; last = 0; } movePointer(e); });
  canvas.addEventListener("pointermove", movePointer);
  const keys = new Set();
  const kd = e => { if (!box.isConnected) { document.removeEventListener("keydown", kd); document.removeEventListener("keyup", ku); return; }
    if (["ArrowLeft", "ArrowRight", "a", "d", " "].includes(e.key)) { e.preventDefault(); keys.add(e.key); if (e.key === " ") { if (s.over) reset(); paused = !paused; } } };
  const ku = e => keys.delete(e.key);
  document.addEventListener("keydown", kd); document.addEventListener("keyup", ku);
  const keyTimer = setInterval(() => {
    if (!box.isConnected) return clearInterval(keyTimer);
    const m = 9;
    if (keys.has("ArrowLeft")) s.p1 = Math.max(PW / 2, s.p1 - m); if (keys.has("ArrowRight")) s.p1 = Math.min(W - PW / 2, s.p1 + m);
    if (mode === "two") { if (keys.has("a")) s.p2 = Math.max(PW / 2, s.p2 - m); if (keys.has("d")) s.p2 = Math.min(W - PW / 2, s.p2 + m); }
  }, 16);
  const hint = h("p.small.muted.arcade-hint");
  const drawHint = () => hint.replaceChildren(mode === "two" ? T("Each player moves the paddle on their side with a finger (or the keys A/D and ←/→). First to 7 points wins.")
    : T("Move your paddle (bottom) with your finger or the arrow keys. First to 7 points wins."));
  const modes = segmented([["easy", T("easy")], ["medium", T("medium")], ["hard", T("hard")], ["two", "👥 " + I18N.tr(T("Two players"))]], mode,
    v => { mode = v; arcadeStore.set("pingpong", { mode }); reset(); drawHint(); });
  drawHint();
  box.replaceChildren(h("section.card.pp-card", modes, h("div.pp-wrap", canvas), hint));
  reset(); requestAnimationFrame(loop);
}

// ---------------------------------------------------------------- Pairs (memory) – emoji sets or the family's photo sets
const PAIR_SETS = {
  animals: [T("Animals"), "🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🐔 🐧 🦉 🦄 🐝"],
  fruit: [T("Fruit and vegetables"), "🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🥑 🥕 🌽 🥦"],
  vehicles: [T("Vehicles"), "🚗 🚕 🚌 🚎 🏎️ 🚓 🚑 🚒 🚐 🚚 🚜 🛵 🏍️ 🚲 🛴 🚂 ✈️ 🚀 🚁 ⛵"],
  sea: [T("In the sea"), "🐳 🐬 🐟 🐠 🐡 🦈 🐙 🦑 🦀 🦞 🦐 🐚 🪼 🐢 🦭 🦦 🦩 🦢 ⚓ 🏝️"],
};
const PAIR_BOTS = { easy: 0.35, medium: 0.65, hard: 0.95 };       // how likely the app remembers a card it saw

async function pairsGame(box) {
  let fam = { sets: [], crest: null };
  try { fam = await api("community/memory"); } catch {}
  const saved = { set: "animals", size: 8, mode: "solo", players: 2, back: fam.crest ? "crest" : "classic", ...(arcadeStore.get().pairs || {}) };
  const sets = { ...Object.fromEntries(Object.entries(PAIR_SETS).map(([k, [n, list]]) => [k, { name: I18N.tr(n), items: list.split(" ").map(e => ({ emoji: e })) }])),
    ...Object.fromEntries(fam.sets.map(st => ["photo:" + st.id, { name: "📷 " + st.name, items: st.photos.map(u => ({ img: u })) }])) };
  if (!sets[saved.set]) saved.set = "animals";
  if (saved.back === "crest" && !fam.crest) saved.back = "classic";
  const opt = (label, el) => h("label.field", label, el);
  const sel = (key, options, conv = String) => h("select", { onchange: e => { saved[key] = conv(e.target.value); arcadeStore.set("pairs", saved); setup(); } },
    ...options.map(([v, n]) => h("option", { value: v, selected: saved[key] === v }, n)));
  const backs = [...Object.entries(CARD_BACKS).map(([k, n]) => [k, I18N.tr(n)]), ...(fam.crest ? [["crest", I18N.tr(T("Family crest"))]] : [])];
  const backEl = () => h("div.mm-back.back-" + saved.back, saved.back === "crest" ? crestSvg(fam.crest, { ribbon: false }) : null);

  function setup() {
    const max = sets[saved.set].items.length;
    const sizes = [6, 8, 10, 12, 15, 18].filter(n => n <= max);
    if (!sizes.includes(saved.size)) saved.size = sizes[sizes.length - 1] || max;
    if (!sizes.length) sizes.push(max);
    box.replaceChildren(h("section.card.form",
      h("div.grid2", opt(T("Cards"), sel("set", Object.entries(sets).map(([k, st]) => [k, st.name]))),
        opt(T("Pairs"), sel("size", sizes.map(n => [n, String(n)]), Number))),
      h("div.grid2", opt(T("Who plays?"), sel("mode", [["solo", I18N.tr(T("Alone"))], ["easy", I18N.tr(T("Against the app – easy"))], ["medium", I18N.tr(T("Against the app – medium"))],
          ["hard", I18N.tr(T("Against the app – hard"))], ["multi", I18N.tr(T("Several players on this device"))]])),
        saved.mode === "multi" ? opt(T("Players"), sel("players", [2, 3, 4].map(n => [n, String(n)]), Number)) : opt(T("Back of the cards"), sel("back", backs))),
      saved.mode === "multi" ? opt(T("Back of the cards"), sel("back", backs)) : null,
      h("div.row.center", h("div.mm-card", { style: { width: "70px" } }, h("div.mm-in", backEl()))),
      fam.sets.length ? null : h("p.small.muted", T("Parents can add photo sets and a family crest in the parent area (Settings).")),
      h("button.btn.big", { onclick: play }, "▶ ", T("Start"))));
  }

  function play() {
    const items = sets[saved.set].items.slice().sort(() => Math.random() - 0.5).slice(0, saved.size);
    const deck = items.flatMap((it, k) => [{ k, it }, { k, it }]).sort(() => Math.random() - 0.5);
    const n = deck.length, cols = n <= 12 ? 4 : n <= 20 ? 5 : 6;
    const bot = PAIR_BOTS[saved.mode];
    const names = saved.mode === "solo" ? [I18N.tr(T("You"))] : bot ? [I18N.tr(T("You")), I18N.tr(T("App"))]
      : Array.from({ length: saved.players }, (_, i) => I18N.tr(T("Player {0}")).replace("{0}", i + 1));
    const score = names.map(() => 0), done = new Set(), memory = new Map();
    let turn = 0, open = [], moves = 0, busy = false, start = Date.now();
    const grid = h("div.mm-grid", { style: { "--cols": cols, "--rows": Math.ceil(n / cols) } }), head = h("div.mm-players"), info = h("p.center.muted.small");
    const cards = deck.map((c, i) => h("button.mm-card", { onclick: () => { if (!busy && !(bot && turn === 1)) flip(i); } },
      h("div.mm-in", backEl(), h("div.mm-face", c.it.img ? h("img", { src: c.it.img, alt: "" }) : h("span", { translate: "no" }, c.it.emoji)))));
    grid.replaceChildren(...cards);
    const drawHead = () => {
      head.replaceChildren(...names.map((nm, i) => h("span.chip" + (i === turn && names.length > 1 ? ".on" : ""), nm, ": ", String(score[i]))));
      info.replaceChildren(I18N.tr(T("Moves")) + " " + moves);
    };
    const remember = i => { if (!bot || Math.random() < bot) memory.set(i, deck[i].k); };
    const flip = i => {
      if (done.has(i) || open.includes(i) || open.length >= 2) return;
      open.push(i); cards[i].classList.add("open"); remember(i); try { Sound.play("tap"); } catch {}
      if (open.length < 2) return;
      moves++; busy = true;
      const [a, b] = open;
      if (deck[a].k === deck[b].k) {
        setTimeout(() => {
          done.add(a); done.add(b); cards[a].classList.add("done"); cards[b].classList.add("done"); memory.delete(a); memory.delete(b);
          score[turn]++; open = []; busy = false; try { Sound.play("right"); } catch {}
          drawHead(); if (done.size === n) return finish(); botTurn();
        }, 450);
      } else {
        setTimeout(() => {
          cards[a].classList.remove("open"); cards[b].classList.remove("open"); open = []; busy = false;
          turn = (turn + 1) % names.length; drawHead(); botTurn();
        }, 1100);
      }
      drawHead();
    };
    const botTurn = () => {
      if (!bot || turn !== 1 || done.size === n) return;
      const hidden = deck.map((_, i) => i).filter(i => !done.has(i));
      const unknown = hidden.filter(i => !memory.has(i));
      const known = [...memory.entries()].filter(([i]) => !done.has(i));
      const pair = known.find(([i, k]) => known.some(([j, l]) => j !== i && l === k));
      const pick = l => l[Math.floor(Math.random() * l.length)];
      let first = pair ? pair[0] : pick(unknown.length ? unknown : hidden);
      setTimeout(() => {
        flip(first);
        const mate = [...memory.entries()].find(([j, k]) => j !== first && k === deck[first].k && !done.has(j));
        const rest = hidden.filter(i => i !== first);
        const second = mate ? mate[0] : pick(rest.filter(i => !memory.has(i)).length ? rest.filter(i => !memory.has(i)) : rest);
        setTimeout(() => flip(second), 800);
      }, 700);
    };
    const finish = () => {
      const secs = Math.round((Date.now() - start) / 1000), top = Math.max(...score);
      const winners = names.filter((_, i) => score[i] === top);
      let msg;
      if (names.length === 1) {
        const key = saved.set.startsWith("photo:") ? "photo" : "emoji", b = arcadeStore.get().pairs_best || {}, id = key + saved.size;
        if (!b[id] || moves < b[id]) { b[id] = moves; arcadeStore.set("pairs_best", b); }
        msg = I18N.tr(T("All pairs found – {0} moves in {1}.")).replace("{0}", moves).replace("{1}", mmss(secs)) + " 🏆 " + b[id];
      } else msg = winners.length > 1 ? I18N.tr(T("Draw!")) : I18N.tr(T("Winner: {0}")).replace("{0}", winners[0]);
      if (!(bot && winners.length === 1 && winners[0] === names[1])) { confetti(); try { Sound.play("done"); } catch {} }
      box.append(h("section.card.center", h("h2", msg), h("div.row.center", h("button.btn", { onclick: play }, "🔄 ", T("Play again")),
        h("button.btn.ghost", { onclick: setup }, "⚙️ ", T("Settings")))));
      box.lastChild.scrollIntoView({ behavior: "smooth", block: "center" });
    };
    drawHead();
    box.replaceChildren(h("section.card", head, info, grid, h("div.row.center", h("button.btn.ghost.small", { onclick: setup }, "⚙️ ", T("Settings")))));
  }
  setup();
}
