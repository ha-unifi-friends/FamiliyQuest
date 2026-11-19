// Game corner: small games that run on this device only – Tic-Tac-Toe, Sudoku, Patience, Ping-Pong and the cube solver (cube.js).
// Alone against the app or two players on one tablet. Nothing is sent to the server; best results stay in this browser.
"use strict";

const ARCADE = {
  ttt: { icon: "⭕", title: T("Tic-Tac-Toe"), text: T("Three in a row – against the app or a second player.") },
  sudoku: { icon: "🔢", title: T("Sudoku"), text: T("Every number once in each row, column and box. From 4×4 to 9×9.") },
  patience: { icon: "🃏", title: T("Patience"), text: T("Sort all cards by suit onto the four piles.") },
  pingpong: { icon: "🏓", title: T("Ping-Pong"), text: T("Bounce the ball back – against the app or face to face on one tablet.") },
  cube: { icon: "🧊", title: T("Cube solver"), text: T("Paint the colours of your puzzle cube and get the moves to solve it, step by step.") },
  slots: { icon: "🎰", title: T("One-armed bandit"), text: T("Pull the lever for 1 coin – three times a day. Three alike win, cherries too.") },
};

const arcadeStore = {
  key: () => "fq.arcade." + ((S.profile && S.profile.id) || 0),
  get() { try { return JSON.parse(localStorage.getItem(this.key())) || {}; } catch { return {}; } },
  set(k, v) { try { const d = this.get(); d[k] = v; localStorage.setItem(this.key(), JSON.stringify(d)); } catch {} },
};
const mmss = s => Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0");

function arcadeCard() {
  const open = Object.keys(ARCADE).filter(k => canPlay(k));
  const locked = Object.keys(ARCADE).filter(k => !canPlay(k) && lockedGame(k));      // a price not paid yet: 🔒 tile (kid.js)
  if (!open.length && !locked.length) return null;
  return h("section.card", h("h2", "🕹️ ", T("Game corner")),
    h("p.small.muted", T("Small games for in between.")),
    batteryHint(),                                                                       // what a start costs (kid.js)
    h("div.arcade-grid", ...Object.entries(ARCADE).filter(([k]) => open.includes(k) || locked.includes(k)).map(([k, g]) => locked.includes(k) ? lockedTile(k, lockedGame(k))
      : h("button.arcade-tile", { onclick: () => go("arcade/" + k) }, h("span.big-ic", g.icon), h("strong", g.title)))));
}

async function arcadeView(kind) {
  const g = ARCADE[kind];
  if (!g || !(canPlay(kind) || S.trial === kind)) return go("games");      // S.trial: opened on a free try (kid.js)
  // opening a game costs a battery segment (familyquest/battery.py) – and uses the free try of a locked game;
  // answering a duel / doubles invitation is free (S.arcadeJoin)
  if (Auth.kid) {
    const join = S.arcadeJoin === kind; S.arcadeJoin = null;
    try {
      const r = await api("me/games/try", { method: "POST", body: { game: kind, join } });
      if (S.me && r.battery) S.me.battery = r.battery;
    } catch (e) { toast(e.message, "bad"); return go("games"); }
  }
  // full screen like the family quiz: no menus, the game uses the whole height
  const box = h("div.arcade-box");
  screen("games", h("div.quiz-full.arcade-full",
    h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => go("games") }, "✕"),
    // ☰: the rules, language, theme, sound – also for the duels on two devices and the doubles (they draw into box)
    h("div.quiz-head", h("div.row.head-title", gameMenu({ rules: () => arcadeRulesView(kind), onLeave: () => go("games") }), h("h1", g.icon, " ", g.title))), box));
  document.body.classList.add("quiz-open");
  // daily game time (parent area › profile): every minute here counts – once it is used up the game corner closes
  const beat = async () => {
    if (!box.isConnected) return clearInterval(beatT);
    let r; try { r = await api("me/playtime", { method: "POST" }); } catch { return; }
    if (S.me) S.me.time_left = r.time_left;
    if (!r.ok && box.isConnected) { clearInterval(beatT); toast(T("Game time for today is used up – see you tomorrow!"), "bad"); go("games"); }
  };
  const beatT = setInterval(beat, 60000); beat();
  ({ ttt: tttGame, sudoku: sudokuGame, patience: patienceGame, pingpong: pingpongGame, slots: slotsGame, cube: cubeGame })[kind](box);
}

function arcadeRulesView(kind) {
  const g = ARCADE[kind];
  const more = { patience: [T("Tap a card: it moves to where it fits. If it fits nowhere, it stays marked – then tap where it should go.")],
    pingpong: [T("Move your paddle (bottom) with your finger. First to 7 points wins."),
      T("Two players, two devices: challenge somebody of the family – they get the invitation on their device.")],
    ttt: [T("Two players, two devices: challenge somebody of the family – they get the invitation on their device.")] }[kind] || [];
  return h("div.form", h("h2", "📜 ", T("Rules")), h("p", g.icon, " ", h("b", g.title)),
    h("ul.small", ...[g.text, ...more].map(x => h("li", I18N.tr(x)))));
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

// on the «Games» page with the family games: duels on two devices (only two players) – Tic-Tac-Toe and Ping-Pong
function tttDuelCard() {
  return h("section.card.game-card", h("h2", "⚔️ ", T("Duel for two")),
    h("p.small.muted", T("Two players, two devices: challenge somebody of the family – they get the invitation on their device.")),
    h("div.row.wrap",
      canPlay("ttt") ? h("button.btn", { onclick: () => { S.tttOnline = true; go("arcade/ttt"); } }, "⭕ ", T("Tic-Tac-Toe")) : null,
      canPlay("pingpong") ? h("button.btn", { onclick: () => { S.pongOnline = true; go("arcade/pingpong"); } }, "🏓 ", T("Ping-Pong")) : null,
      canPlay("pingpong") ? h("button.btn", { onclick: () => { S.pong4Online = true; go("arcade/pingpong"); } }, "🏓 ", T("Doubles (2 against 2)")) : null));
}

async function tttGame(box) {
  let duel = null;
  try { duel = await api("community/duel"); } catch {}
  if ((duel && duel.kind !== "pong") || S.tttOnline) { S.tttOnline = false; return tttOnline(box); }
  const saved = arcadeStore.get().ttt || {};
  const noBot = !botsOn("ttt");                   // parent area › Games: without bots – no games against the app
  let mode = noBot ? "two" : saved.mode || "easy", board, turn, starter = "X", done = null, score = { X: 0, O: 0, draw: 0 };
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
  const modes = segmented([...(noBot ? [] : [["easy", T("easy")], ["medium", T("medium")], ["hard", T("unbeatable")]]), ["two", "👥 " + I18N.tr(T("Two players"))],
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
    try { list = await api("community/duel/opponents?kind=ttt"); } catch (e) { toast(e.message, "bad"); }
    body.replaceChildren(h("h2", T("Who do you want to play with?")),
      list.length ? h("div.arcade-grid", ...list.map(o => h("button.arcade-tile", { disabled: o.busy, onclick: async () => {
        try { st = await api("community/duel", { method: "POST", body: { opponent: o.id } }); draw(true); } catch (e) { toast(e.message, "bad"); }
      } }, avatarSvg(o.avatar, 56), C(o.name, "strong"), o.busy ? h("span.small.muted", T("is playing")) : null)))
        : h("p.muted", T("Nobody else can play right now.")));
  };
  const draw = (force = false) => {
    turnCue("duel", st && st.status === "play" && st.turn === st.me);
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
async function pingpongGame(box) {
  let duel = null;
  try { duel = await api("community/duel"); } catch {}
  if ((duel && duel.kind === "pong") || S.pongOnline) { S.pongOnline = false; return pongOnline(box); }
  let table = null;
  try { table = await api("community/pong4"); } catch {}
  if (table || S.pong4Online) { S.pong4Online = false; return pong4Online(box); }
  const saved = arcadeStore.get().pingpong || {};
  const noBot = !botsOn("pingpong");              // parent area › Games: without bots – no games against the app
  let mode = noBot ? "two" : saved.mode || "medium", to = 7;
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
  const modes = segmented([...(noBot ? [] : [["easy", T("easy")], ["medium", T("medium")], ["hard", T("hard")]]), ["two", "👥 " + I18N.tr(T("Two players"))],
    ["online", "📱 " + I18N.tr(T("Two devices"))], ["four", "📱📱 " + I18N.tr(T("Doubles"))]], mode,
    v => { if (v === "online") return pongOnline(box); if (v === "four") return pong4Online(box); mode = v; arcadeStore.set("pingpong", { mode }); reset(); drawHint(); });
  drawHint();
  box.replaceChildren(h("section.card.pp-card", modes, h("div.pp-wrap", canvas), hint));
  reset(); requestAnimationFrame(loop);
}

// ---------------------------------------------------------------- one-armed bandit (familyquest/slots.py: drawn on the server)
async function slotsGame(box) {
  let st;
  try { st = await api("me/slots"); } catch (e) { return box.replaceChildren(h("p.bad", e.message)); }
  const SYM = st.symbols, order = Object.keys(SYM);
  const reels = [0, 1, 2].map((_, i) => h("div.ob-reel", h("div.ob-strip", h("div.ob-cell", SYM[order[[5, 4, 3][i]]]))));
  const msg = h("div.ob-msg");
  const info = h("div.ob-info");
  const lever = h("button.ob-lever", { title: T("Pull") }, h("span.ob-knob"));
  const play = h("button.btn.big.ob-play", "🎰 ", T("Pull the lever"), " · 1 🪙");
  let busy = false;
  const drawInfo = () => {
    info.replaceChildren(h("span", "🪙 ", String(Math.round(st.coins))), h("span", I18N.tr(T("Spins left today: {0} of {1}")).replace("{0}", st.left).replace("{1}", st.max)));
    const trial = !st.owned;              // a free try: one spin each (familyquest/gamepasses.py `preview`)
    if (trial) info.append(h("span.gp-try-tag", "🎁 ", I18N.tr(T("Free tries left: {0}")).replace("{0}", st.tries_left)));
    play.disabled = lever.disabled = busy || !st.left || st.coins < st.bet || (trial && !st.tries_left);
    buy.replaceChildren(...(trial && !st.tries_left && !busy ? [gamePassButtons(passOf(st), st.coins, () => slotsGame(box))] : []));
  };
  const buy = h("div.ob-buy");
  const passOf = x => ({ game: "slots", price: x.price, rent: x.rent, period: x.period, bought: false, rent_until: null, left_s: 0 });
  const spinReel = (el, sym, ms) => new Promise(res => {
    const strip = el.firstChild;
    const seq = Array.from({ length: 14 }, () => SYM[order[Math.floor(Math.random() * order.length)]]).concat(SYM[sym]);
    strip.replaceChildren(...seq.map(x => h("div.ob-cell", x)));
    strip.style.transition = "none"; strip.style.transform = "translateY(0)";
    void strip.offsetWidth;
    strip.style.transition = `transform ${ms}ms cubic-bezier(.15,.7,.25,1)`;
    strip.style.transform = `translateY(-${(seq.length - 1) * 100}%)`;
    setTimeout(() => { strip.replaceChildren(h("div.ob-cell", SYM[sym])); strip.style.transition = "none"; strip.style.transform = "translateY(0)"; res(); }, ms + 30);
  });
  const go = async () => {
    if (busy) return;
    busy = true; drawInfo(); msg.textContent = ""; msg.className = "ob-msg";
    lever.classList.add("pulled"); setTimeout(() => lever.classList.remove("pulled"), 450);
    let r;
    try { r = await api("me/slots/spin", { method: "POST" }); } catch (e) { busy = false; drawInfo(); return toast(e.message, "bad"); }
    await Promise.all(r.reels.map((sym, i) => spinReel(reels[i], sym, 900 + i * 450)));
    st = r; busy = false; drawInfo();
    if (r.win) {
      msg.className = "ob-msg win" + (r.jackpot ? " jackpot" : "");
      msg.textContent = r.win === 1 ? I18N.tr(T("You get your coin back!")) : I18N.tr(r.jackpot ? T("JACKPOT! +{0} coins") : T("You win {0} coins!")).replace("{0}", r.win);
      try { Sound.play("right"); } catch {}
      if (r.jackpot || r.win >= 10) confetti();
    } else {
      msg.textContent = I18N.tr(T("No luck this time"));
      try { Sound.play("wrong"); } catch {}
    }
  };
  play.onclick = go; lever.onclick = go;
  const table = h("div.ob-table", h("b", T("Pay table (1 coin)")),
    ...Object.entries(st.three).map(([k, v]) => h("div.ob-row", h("span", SYM[k].repeat(3)), h("b", "+" + v))),
    h("div.ob-row", h("span", SYM.cherry + SYM.cherry), h("b", "+" + st.cherries[2])),
    h("div.ob-row", h("span", SYM.cherry), h("b", "+" + st.cherries[1])));
  const machine = () => h("div.ob-machine",
    h("div.ob-top", "★ ", T("Lucky Star"), " ★"),
    h("div.ob-window", ...reels), lever, msg, info, play, buy, table);
  if (st.owned || st.tries_left > 0) { box.replaceChildren(machine()); drawInfo(); return; }
  // not bought / rented yet: the standard price of a game (kid.js gamePassButtons, familyquest/gamepasses.py)
  const o = passOf(st);
  box.replaceChildren(h("div.ob-machine.locked", h("div.ob-top", "★ ", T("Lucky Star"), " ★"),
    h("div.ob-window", ...reels), h("p.center", T("Your own one-armed bandit for the game corner: play three times a day for 1 coin.")),
    h("p.small.muted.center", "🪙 ", String(Math.round(st.coins))), gamePassButtons(o, st.coins, () => slotsGame(box)), table));
}

// ---------------------------------------------------------------- Ping-Pong on two devices (familyquest/duel.py, kind «pong»)
// The one who invited (X) moves the ball; both send their paddle about 20 times a second and see their own paddle at
// the bottom (the guest sees the table turned round). The ball between two updates is moved on locally.
function pongOnline(box) {
  const W = 400, H = 640, PW = 80, PH = 12, R = 9, TO = 7, SPEED = 300;
  let st = null, timer = null, sync = null, alive = true, cheered = -1, last = 0, recv = 0;
  let myPad = 0.5, ball = null, points = { X: 0, O: 0 }, wait = 0, sending = false;
  const body = h("div");
  const canvas = h("canvas.pp-canvas", { width: W, height: H }), ctx = canvas.getContext("2d");
  const stop = () => { alive = false; clearInterval(timer); clearInterval(sync); };
  const back = async () => { stop(); try { await api("community/duel/leave", { method: "POST" }); } catch {} pingpongGame(box); };
  const act = async (path, b) => { try { st = await api("community/duel/" + path, { method: "POST", body: b }); onState(true); } catch (e) { toast(e.message, "bad"); } };
  const host = () => st && st.me === "X";
  // the table as X sees it: X at the bottom (y = H − 30), O at the top (y = 30); the guest draws it turned round
  const serve = dir => { const a = Math.random() * 0.8 - 0.4; ball = { x: 0.5, y: 0.5, vx: Math.sin(a) * SPEED / W, vy: dir * Math.cos(a) * SPEED / H }; wait = 0.9; };
  const step = dt => {                                   // only on X
    if (!ball || st.status !== "play") return;
    if (wait > 0) { wait -= dt; return; }
    ball.x += ball.vx * dt; ball.y += ball.vy * dt;
    if (ball.x < R / W) { ball.x = R / W; ball.vx = Math.abs(ball.vx); } else if (ball.x > 1 - R / W) { ball.x = 1 - R / W; ball.vx = -Math.abs(ball.vx); }
    const pads = st.pong.pads, hit = (px, py, dirOut) => {
      const bx = ball.x * W, by = ball.y * H;
      if (Math.abs(bx - px * W) <= PW / 2 + R && Math.abs(by - py) <= PH / 2 + R && Math.sign(ball.vy) === -dirOut) {
        const off = (bx - px * W) / (PW / 2), sp = Math.min(Math.hypot(ball.vx * W, ball.vy * H) * 1.06, 900);
        ball.vx = Math.sin(off) * sp / W; ball.vy = dirOut * Math.cos(off) * sp / H; ball.y = (py + dirOut * (PH / 2 + R)) / H;
        try { Sound.play("tap"); } catch {}
      }
    };
    hit(myPad, H - 30, -1); hit(pads.O, 30, 1);
    if (ball.y * H > H + R) { points.O++; point(1); } else if (ball.y * H < -R) { points.X++; point(-1); }
  };
  let over = null;
  const point = dir => { if (points.X >= TO || points.O >= TO) { over = points.X >= TO ? "X" : "O"; ball = null; } else serve(dir); };
  const send = async () => {
    if (!alive || sending || !st || st.status !== "play") return;
    sending = true;
    const b = { pad: host() ? myPad : 1 - myPad };      // the guest's paddle in X's view (turned round)
    if (host()) Object.assign(b, { ball, points, over });
    try { st = await api("community/duel/pong", { method: "POST", body: b }); recv = performance.now(); onState(); } catch {}
    sending = false;
  };
  const view = (x, y) => host() ? [x * W, y * H] : [(1 - x) * W, (1 - y) * H];
  const render = () => {
    const p = st.pong, pts = host() ? points : p.points;
    ctx.fillStyle = "#14532d"; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 3; ctx.strokeRect(6, 6, W - 12, H - 12);
    ctx.setLineDash([10, 10]); ctx.beginPath(); ctx.moveTo(6, H / 2); ctx.lineTo(W - 6, H / 2); ctx.stroke(); ctx.setLineDash([]);
    const mine = st.me, other = mine === "X" ? "O" : "X";
    ctx.font = "bold 44px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.fillText(String(pts[other]), W / 2, H / 2 - 30); ctx.fillText(String(pts[mine]), W / 2, H / 2 + 70);
    const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#5b5bd6";
    ctx.fillStyle = css("--ans-2"); ctx.fillRect(myPad * W - PW / 2, H - 30 - PH / 2, PW, PH);            // me: always at the bottom
    const op = host() ? p.pads.O : 1 - p.pads.X;
    ctx.fillStyle = css("--ans-4"); ctx.fillRect(op * W - PW / 2, 30 - PH / 2, PW, PH);
    let b = host() ? ball : p.ball;
    if (b && !host() && st.status === "play") {           // between two updates: move it on
      const dt = Math.min(0.12, (performance.now() - recv) / 1000);
      b = { x: b.x + b.vx * dt, y: b.y + b.vy * dt };
    }
    if (b) { const [bx, by] = view(b.x, b.y); ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(bx, by, R, 0, Math.PI * 2); ctx.fill(); }
    ctx.font = "bold 16px system-ui, sans-serif"; ctx.fillStyle = "rgba(255,255,255,.8)";
    ctx.fillText(st.names[other], W / 2, 60); ctx.fillText(st.names[mine], W / 2, H - 52);
    if (st.status === "done") {
      ctx.fillStyle = "rgba(0,0,0,.45)"; ctx.fillRect(0, H / 2 - 60, W, 120); ctx.fillStyle = "#fff"; ctx.font = "bold 26px system-ui, sans-serif";
      ctx.fillText(I18N.tr(T("Winner: {0}")).replace("{0}", st.names[st.result]), W / 2, H / 2 + 9);
    }
  };
  const loop = t => {
    if (!alive || !box.isConnected) return stop();
    const dt = Math.min(0.033, (t - (last || t)) / 1000); last = t;
    if (st && st.status === "play" && st.pong) { if (host()) step(dt); render(); }
    requestAnimationFrame(loop);
  };
  const toPad = e => { const r = canvas.getBoundingClientRect(); myPad = Math.max(PW / 2 / W, Math.min(1 - PW / 2 / W, (e.clientX - r.left) / r.width)); };
  canvas.addEventListener("pointerdown", toPad); canvas.addEventListener("pointermove", toPad);
  const pickOpponent = async () => {
    let list = [];
    try { list = await api("community/duel/opponents?kind=pong"); } catch (e) { toast(e.message, "bad"); }
    body.replaceChildren(h("h2", T("Who do you want to play with?")),
      list.length ? h("div.arcade-grid", ...list.map(o => h("button.arcade-tile", { disabled: o.busy, onclick: async () => {
        try { st = await api("community/duel", { method: "POST", body: { opponent: o.id, kind: "pong" } }); onState(true); } catch (e) { toast(e.message, "bad"); }
      } }, avatarSvg(o.avatar, 56), C(o.name, "strong"), o.busy ? h("span.small.muted", T("is playing")) : null)))
        : h("p.muted", T("Nobody else can play right now.")));
  };
  let shown = "";
  const onState = (force = false) => {
    if (!st) { if (shown !== "pick") { shown = "pick"; pickOpponent(); } return; }
    const other = st.names[st.me === "X" ? "O" : "X"];
    const key = st.status;
    if (st.status === "play" && host() && !ball && !over && points.X + points.O === 0 && shown !== "play") serve(1);
    if (st.status === "done") {
      const round = st.score.X + st.score.O;
      if (st.result === st.me && round !== cheered) { cheered = round; confetti(); try { Sound.play("done"); } catch {} }
    }
    if (!force && key === shown && key !== "done") return;
    if (key === "done" && shown === "done" && !force) { render(); return; }
    shown = key;
    if (st.status === "invite") return body.replaceChildren(h("div.center",
      h("p.ttt-status", st.host ? I18N.tr(T("Waiting for {0} …")).replace("{0}", other) : I18N.tr(T("{0} invites you to Ping-Pong")).replace("{0}", other)),
      st.host ? h("button.btn.ghost", { onclick: back }, T("Cancel"))
        : h("div.row.center", h("button.btn", { onclick: () => act("accept") }, "▶ ", T("Play")), h("button.btn.ghost", { onclick: back }, T("No thanks")))));
    if (st.status === "declined" || st.status === "gone") return body.replaceChildren(h("div.center",
      h("p.ttt-status", I18N.tr(st.status === "declined" ? T("{0} does not want to play right now.") : T("{0} has left the game.")).replace("{0}", other)),
      h("button.btn", { onclick: back }, "← ", T("Back"))));
    if (st.status === "done") { render(); }
    body.replaceChildren(h("div.pp-wrap", canvas),
      h("p.small.muted.arcade-hint", T("Move your paddle (bottom) with your finger. First to 7 points wins.")),
      h("div.row.center", st.status === "done" ? h("button.btn", { onclick: () => { points = { X: 0, O: 0 }; over = null; ball = null; act("again"); } }, "🔄 ", T("New round")) : null,
        h("button.btn.ghost", { onclick: back }, T("Leave"))));
  };
  box.replaceChildren(h("section.card.pp-card", h("div.row", h("h2.grow", "📱 ", T("Two devices")),
    h("button.btn.ghost.small", { onclick: back }, "← ", T("Against the app"))), body));
  (async () => { try { st = await api("community/duel"); } catch {} if (st && st.kind !== "pong") st = null; onState(true); })();
  timer = setInterval(async () => {                      // invitation / lobby: slow; during the match the paddle sync carries the state
    if (!alive || !box.isConnected) return stop();
    if (st && st.status === "play") return;
    try { st = await api("community/duel"); if (st && st.kind !== "pong") st = null; onState(); } catch {}
  }, 1200);
  sync = setInterval(send, 50);
  requestAnimationFrame(loop);
}

// ---------------------------------------------------------------- Ping-Pong doubles on four devices (familyquest/pong4.py)
// Two teams of two: a back paddle at the baseline and a short front paddle near the net. The host (seat A1) moves the
// ball and the bots, like X in the duel; every device sends only its own paddle. Everybody sees the own team at the
// bottom (team B sees the table turned round). Seats without a person are played by bots on the host's device.
function pong4Online(box) {
  const W = 400, H = 640, PW = 80, PH = 12, R = 9, SPEED = 300, MAXSP = 820;
  const ROW = { A1: H - 30, A2: H / 2 + 90, B1: 30, B2: H / 2 - 90 };           // paddle rows as team A sees the table
  const front = s => s[1] === "2", len = s => front(s) ? PW * 0.55 : PW, dirOf = s => s[0] === "A" ? -1 : 1;
  const BOT = { easy: 150, normal: 230, hard: 340 }, AIM = { easy: 1.6, normal: 1.15, hard: 0.85 }, aim = {}, LVL = { easy: T("easy"), normal: T("normal"), hard: T("hard") };
  let st = null, timer = null, sync = null, alive = true, cheered = -1, last = 0, recv = 0, prev = "";
  let myPad = 0.5, ball = null, points = { A: 0, B: 0 }, wait = 0, over = null, sending = false, bots = {};
  const token = {}; S.p4Open = token; box.p4 = token;   // no invitation popup while the table is open
  const body = h("div");
  const canvas = h("canvas.pp-canvas", { width: W, height: H }), ctx = canvas.getContext("2d");
  const stop = () => { alive = false; if (S.p4Open === token) S.p4Open = null; clearInterval(timer); clearInterval(sync); };
  const back = async () => { stop(); try { await api("community/pong4/leave", { method: "POST" }); } catch {} pingpongGame(box); };
  const act = async (path, b) => { try { st = await api("community/pong4/" + path, { method: "POST", body: b }); onState(true); } catch (e) { toast(e.message, "bad"); } };
  const host = () => st && st.host;
  const flip = () => st && st.team === "B";
  const seatName = s => { const x = st.seats[s]; return x.bot ? "🤖 " + I18N.tr(LVL[x.bot]) : x.name; };
  const teamName = t => seatName(t + "1") + " + " + seatName(t + "2");
  // ---- the match (only on the host): ball, bots, points
  const serve = t => {                                   // the team that lost the point serves from its baseline
    const a = Math.random() * 0.6 - 0.3, d = t === "A" ? -1 : 1;
    ball = { x: 0.5, y: t === "A" ? (H - 70) / H : 70 / H, vx: Math.sin(a) * SPEED / W, vy: d * Math.cos(a) * SPEED / H }; wait = 0.9;
  };
  const padOf = s => s === st.me ? myPad : st.seats[s].state === "bot" ? (bots[s] ?? 0.5) : st.pong.pads[s];
  const moveBots = dt => {
    for (const s of ["A1", "A2", "B1", "B2"]) {
      const x = st.seats[s];
      if (x.state !== "bot") continue;
      const coming = ball && Math.sign(ball.vy) === -dirOf(s);
      // a bot aims with a part of its paddle (a new choice for every ball): returns get an angle, easy bots miss now and then
      if (!coming) delete aim[s]; else if (aim[s] == null) aim[s] = (Math.random() * 2 - 1) * AIM[x.bot] * len(s) / 2 / W;
      const target = coming ? ball.x - aim[s] : 0.5;
      const p = bots[s] ?? 0.5, m = BOT[x.bot] * dt / W, half = len(s) / 2 / W;
      bots[s] = Math.max(half, Math.min(1 - half, p + Math.max(-m, Math.min(m, target - p))));
    }
  };
  const hit = s => {
    const px = padOf(s) * W, py = ROW[s], dirOut = dirOf(s), half = len(s) / 2, bx = ball.x * W, by = ball.y * H;
    if (Math.abs(bx - px) <= half + R && Math.abs(by - py) <= PH / 2 + R && Math.sign(ball.vy) === -dirOut) {
      const off = Math.max(-1, Math.min(1, (bx - px) / half)), sp = Math.min(Math.hypot(ball.vx * W, ball.vy * H) * (front(s) ? 1.05 : 1.08), MAXSP);
      ball.vx = Math.sin(off) * sp / W; ball.vy = dirOut * Math.cos(off) * sp / H; ball.y = (py + dirOut * (PH / 2 + R)) / H;
      try { Sound.play("tap"); } catch {}
    }
  };
  const step = dt => {
    moveBots(dt);
    if (!ball || st.status !== "play") return;
    if (wait > 0) { wait -= dt; return; }
    for (let i = 0; i < 2; i++) {                        // two small steps: the fast ball does not slip through a paddle
      ball.x += ball.vx * dt / 2; ball.y += ball.vy * dt / 2;
      if (ball.x < R / W) { ball.x = R / W; ball.vx = Math.abs(ball.vx); } else if (ball.x > 1 - R / W) { ball.x = 1 - R / W; ball.vx = -Math.abs(ball.vx); }
      ["A1", "A2", "B1", "B2"].forEach(hit);
    }
    if (ball.y * H > H + R) { points.B++; point("A"); } else if (ball.y * H < -R) { points.A++; point("B"); }
  };
  const point = loser => { if (points.A >= st.to || points.B >= st.to) { over = points.A >= st.to ? "A" : "B"; ball = null; } else serve(loser); };
  const send = async () => {
    if (gone() || sending || !st || st.status !== "play") return;
    sending = true;
    const b = { pad: flip() ? 1 - myPad : myPad };       // always as team A sees the table
    if (host()) Object.assign(b, { bots, ball, points, over });
    try { st = await api("community/pong4/sync", { method: "POST", body: b }); recv = performance.now(); onState(); } catch {}
    sending = false;
  };
  // ---- drawing: my team at the bottom
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#5b5bd6";
  const render = () => {
    const p = st.pong, pts = host() ? points : p.points, mine = st.team, other = mine === "A" ? "B" : "A";
    const X = x => flip() ? (1 - x) * W : x * W, Y = y => flip() ? H - y : y;
    ctx.fillStyle = "#14532d"; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 3; ctx.strokeRect(6, 6, W - 12, H - 12);
    ctx.setLineDash([10, 10]); ctx.beginPath(); ctx.moveTo(6, H / 2); ctx.lineTo(W - 6, H / 2); ctx.stroke(); ctx.setLineDash([]);
    ctx.font = "bold 44px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.fillStyle = "rgba(255,255,255,.3)";
    ctx.fillText(String(pts[other]), W / 2, H / 4 - 20); ctx.fillText(String(pts[mine]), W / 2, H * 3 / 4 + 50);
    for (const s of ["A1", "A2", "B1", "B2"]) {
      const v = s === st.me ? (flip() ? 1 - myPad : myPad) : host() ? padOf(s) : p.pads[s];
      const l = len(s), x = X(v), y = Y(ROW[s]);
      ctx.fillStyle = css(s[0] === mine ? "--ans-2" : "--ans-4"); ctx.globalAlpha = front(s) ? 0.85 : 1;
      ctx.fillRect(x - l / 2, y - PH / 2, l, PH); ctx.globalAlpha = 1;
      if (s === st.me) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.strokeRect(x - l / 2 - 2, y - PH / 2 - 2, l + 4, PH + 4); }
    }
    let b = host() ? ball : p.ball;
    if (b && !host() && st.status === "play") {           // between two updates: move it on
      const dt = Math.min(0.12, (performance.now() - recv) / 1000);
      b = { x: b.x + b.vx * dt, y: b.y + b.vy * dt };
    }
    if (b && st.status === "play") { ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(X(b.x), Y(b.y * H), R, 0, Math.PI * 2); ctx.fill(); }
    ctx.font = "bold 15px system-ui, sans-serif"; ctx.fillStyle = "rgba(255,255,255,.85)";
    ctx.fillText(teamName(other), W / 2, H / 4 + 6); ctx.fillText(teamName(mine), W / 2, H * 3 / 4 + 76);
    if (st.status === "done") {
      ctx.fillStyle = "rgba(0,0,0,.45)"; ctx.fillRect(0, H / 2 - 60, W, 120); ctx.fillStyle = "#fff"; ctx.font = "bold 22px system-ui, sans-serif";
      ctx.fillText(I18N.tr(T("Winner: {0}")).replace("{0}", teamName(st.result)), W / 2, H / 2 + 8);
    }
  };
  const gone = () => !alive || !box.isConnected || box.p4 !== token;     // a newer view in the same place takes over
  const loop = t => {
    if (gone()) return stop();
    const dt = Math.min(0.033, (t - (last || t)) / 1000); last = t;
    if (st && (st.status === "play" || st.status === "done") && st.pong) { if (host() && st.status === "play") step(dt); render(); }
    requestAnimationFrame(loop);
  };
  const toPad = e => {
    if (!st || !st.me) return;
    const r = canvas.getBoundingClientRect(), half = len(st.me) / 2 / W;
    myPad = Math.max(half, Math.min(1 - half, (e.clientX - r.left) / r.width));
  };
  canvas.addEventListener("pointerdown", toPad); canvas.addEventListener("pointermove", toPad);
  // ---- setting up the table
  const SEAT_LABEL = { A1: T("You – back"), A2: T("Partner – front"), B1: T("Opponent – back"), B2: T("Opponent – front") };
  const choice = (list, cur, onchange) => h("select.p4-sel", { onchange: e => onchange(e.target.value) },
    ...(botsOn("pingpong") ? ["easy", "normal", "hard"] : []).map(l => h("option", { value: "bot:" + l, selected: cur === "bot:" + l }, "🤖 ", I18N.tr(T("Bot")), " · ", I18N.tr(LVL[l]))),
    ...list.map(o => h("option", { value: "pid:" + o.id, disabled: o.busy, selected: cur === "pid:" + o.id }, o.name, o.busy ? " · " + I18N.tr(T("is playing")) : "")));
  const spec = v => v.startsWith("bot:") ? { bot: v.slice(4) } : { pid: +v.slice(4) };
  const setup = async () => {
    let list = [];
    try { list = await api("community/pong4/players"); } catch (e) { toast(e.message, "bad"); }
    const free = list.filter(o => !o.busy);
    const fb = botsOn("pingpong") ? "bot:normal" : list[0] ? "pid:" + list[0].id : "";     // without bots: people only
    const pick = { A2: free[0] ? "pid:" + free[0].id : fb, B1: free[1] ? "pid:" + free[1].id : fb, B2: free[2] ? "pid:" + free[2].id : fb };
    let to = 7;
    body.replaceChildren(h("p.small.muted", T("Two against two: each team has a back paddle and a short front paddle near the net. Invite up to three family members – bots take the other seats.")),
      h("div.p4-seats", ...["A2", "B1", "B2"].map(s => h("label.p4-seat", h("span.p4-lbl", s[0] === "A" ? "🟦 " : "🟥 ", SEAT_LABEL[s]), choice(list, pick[s], v => { pick[s] = v; })))),
      h("div.row.p4-row", h("span.small", T("Points to win")), segmented([[5, "5"], [7, "7"], [11, "11"]], to, v => { to = v; })),
      h("div.row.center", h("button.btn.big", { onclick: async () => {
        try { st = await api("community/pong4", { method: "POST", body: { seats: { A2: spec(pick.A2), B1: spec(pick.B1), B2: spec(pick.B2) }, to } }); onState(true); }
        catch (e) { toast(e.message, "bad"); }
      } }, "🏓 ", T("Set up the table"))));
  };
  const lobby = async () => {
    const ready = ["A1", "A2", "B1", "B2"].every(s => ["host", "in", "bot"].includes(st.seats[s].state));
    const mine = st.seats[st.me];
    let list = [];
    if (host() && ["A2", "B1", "B2"].some(s => st.seats[s].state === "declined")) { try { list = await api("community/pong4/players"); } catch {} }
    const ICON = { host: "⭐ ", in: "✅ ", bot: "", invite: "⏳ ", declined: "✖️ " };
    const row = s => {
      const x = st.seats[s];
      const right = host() && x.state === "declined"
        ? choice(list.filter(o => !Object.values(st.seats).some(y => y.pid === o.id && y.state !== "declined")), "", v => act("seat", { seat: s, ...spec(v) }))
        : h("span.small.muted", x.state === "invite" ? T("waiting …") : x.state === "declined" ? T("No thanks") : "");
      if (right.tagName === "SELECT") right.prepend(h("option", { value: "", selected: true, disabled: true }, I18N.tr(T("Choose …"))));
      return h("div.p4-seat" + (s === st.me ? ".p4-me" : ""), h("span.p4-lbl", s[0] === "A" ? "🟦 " : "🟥 ", I18N.tr(front(s) ? T("front") : T("back")), ": ",
        h("b", ICON[x.state], seatName(s) || x.name)), right);
    };
    body.replaceChildren(h("p.ttt-status.center", I18N.tr(T("First to {0} points")).replace("{0}", st.to)),
      h("div.p4-seats", ...["A1", "A2", "B1", "B2"].map(row)),
      mine.state === "invite"
        ? h("div.row.center", h("button.btn.big", { onclick: () => act("accept") }, "▶ ", T("Play")), h("button.btn.ghost", { onclick: back }, T("No thanks")))
        : h("div.row.center", host() ? h("button.btn.big", { disabled: !ready, onclick: () => act("start") }, "▶ ", T("Start")) : h("p.small.muted", T("The host starts the match.")),
          h("button.btn.ghost", { onclick: back }, host() ? T("Cancel") : T("Leave"))));
  };
  let shown = "";
  const onState = (force = false) => {
    if (!st) { if (shown !== "pick") { shown = "pick"; setup(); } return; }
    if (host() && st.status === "play" && (prev === "lobby" || prev === "done" || prev === "")) {   // a new round: the host serves
      if (prev !== "" || (!ball && !over && points.A + points.B === 0)) { points = { A: 0, B: 0 }; over = null; bots = {}; serve("A"); }
    }
    prev = st.status;
    if (st.status === "done") {
      const round = st.score.A + st.score.B;
      if (st.result === st.team && round !== cheered) { cheered = round; confetti(); try { Sound.play("done"); } catch {} }
    }
    const key = st.status === "lobby" ? "lobby:" + JSON.stringify(st.seats) : st.status;
    if (!force && key === shown) return;
    shown = key;
    if (st.status === "lobby") return lobby();
    if (st.status === "gone") return body.replaceChildren(h("div.center",
      h("p.ttt-status", I18N.tr(T("{0} has left the game.")).replace("{0}", st.seats.A1.name)), h("button.btn", { onclick: back }, "← ", T("Back"))));
    body.replaceChildren(h("div.pp-wrap", canvas),
      h("p.small.muted.arcade-hint", I18N.tr(T("Move your paddle (white frame) with your finger. First to {0} points wins.")).replace("{0}", st.to)),
      h("div.row.center", st.status === "done" ? h("button.btn", { onclick: () => act("again") }, "🔄 ", T("New round")) : null,
        h("button.btn.ghost", { onclick: back }, T("Leave"))));
  };
  box.replaceChildren(h("section.card.pp-card", h("div.row", h("h2.grow", "🏓 ", T("Doubles")),
    h("button.btn.ghost.small", { onclick: back }, "← ", T("Against the app"))), body));
  (async () => { try { st = await api("community/pong4"); } catch {} onState(true); })();
  timer = setInterval(async () => {                      // set-up and lobby: slow; during the match the paddle sync carries the state
    if (gone()) return stop();
    if (st && st.status === "play") return;
    try { const n = await api("community/pong4"); if (n || shown !== "pick") { st = n; onState(); } } catch {}
  }, 1200);
  sync = setInterval(send, 66);
  requestAnimationFrame(loop);
}
