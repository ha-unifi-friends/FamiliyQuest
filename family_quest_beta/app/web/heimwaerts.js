// «Heimwärts» – the classic cross-and-circle race board game, live for the family (familyquest/heimwaerts.py).
// Roll the die, bring your 4 pieces around the board and into your home; landing on another piece sends it back.
// heimwaertsLive(box, me, back) runs a table (family or alone against bots), heimwaertsStartDialog(solo, onStarted) sets
// the rules. The server rolls the die and knows the legal moves – this file draws the board and animates.
// Uses botPicker() from cards.js and guestInvite() from community.js.
"use strict";

const HW_ICON = "🏠";
const HW_COLORS = ["#f2545b", "#2f8fdd", "#33a852", "#f2b705"];          // seat 0..3 (coral, sky, leaf, sun)
const hwName = () => I18N.tr(T("Homeward"));
const hwCoins = list => list.join(" / ") + " 🪙";
const HW_PIPS = { 1: [[50, 50]], 2: [[28, 28], [72, 72]], 3: [[26, 26], [50, 50], [74, 74]], 4: [[28, 28], [72, 28], [28, 72], [72, 72]],
  5: [[26, 26], [74, 26], [50, 50], [26, 74], [74, 74]], 6: [[28, 24], [72, 24], [28, 50], [72, 50], [28, 76], [72, 76]] };

// ---------------------------------------------------------------- the board (11 × 11 cells of 40, viewBox 0 0 440 440)
// Seat 0 sits at the bottom; the other seats are the same layout turned clockwise. The viewer's seat is turned to the bottom.
const HW_TRACK0 = [[4, 10], [4, 9], [4, 8], [4, 7], [4, 6], [3, 6], [2, 6], [1, 6], [0, 6], [0, 5]];   // fields 0..9 (cells)
const HW_HOME0 = [[5, 9], [5, 8], [5, 7], [5, 6]];
const HW_YARD0 = [[1.45, 8.45], [2.55, 8.45], [1.45, 9.55], [2.55, 9.55]];                              // centres (cell units)
const hwCW = ([u, v], n) => { for (let k = 0; k < ((n % 4) + 4) % 4; k++) [u, v] = [11 - v, u]; return [u, v]; };
const hwPx = ([u, v]) => [u * 40, v * 40];
const hwCell = ([x, y]) => [x + 0.5, y + 0.5];
function hwFieldXY(f, ms) { const s = Math.floor(f / 10); return hwPx(hwCW(hwCell(HW_TRACK0[f % 10]), s - ms)); }
function hwHomeXY(seat, i, ms) { return hwPx(hwCW(hwCell(HW_HOME0[i]), seat - ms)); }
function hwYardXY(seat, i, ms) { return hwPx(hwCW(HW_YARD0[i], seat - ms)); }
function hwPosXY(seat, rel, i, ms) {
  if (rel < 0) return hwYardXY(seat, i, ms);
  if (rel >= 40) return hwHomeXY(seat, rel - 40, ms);
  return hwFieldXY((10 * seat + rel) % 40, ms);
}
function hwBoardSvg(ms, seatsUsed, benches) {
  const p = [`<rect x="4" y="4" width="432" height="432" rx="34" class="hw-bg"/>`];
  for (let f = 0; f < 40; f += 10) {                    // the way into each home
    const [x, y] = hwFieldXY((f + 39) % 40, ms), [x2, y2] = hwHomeXY(f / 10, 0, ms);
    p.push(`<line x1="${x}" y1="${y}" x2="${x2}" y2="${y2}" class="hw-entry" style="stroke:${HW_COLORS[f / 10]}"/>`);
  }
  for (let s = 0; s < 4; s++) {                         // the yards with 4 spots, the home fields
    const col = HW_COLORS[s], used = seatsUsed.includes(s), op = used ? 1 : 0.35;
    const corner = [[0.25, 7.25], [3.75, 7.25], [3.75, 10.75], [0.25, 10.75]].map(c => hwPx(hwCW(c, s - ms)));
    const xs = corner.map(c => c[0]), ys = corner.map(c => c[1]);
    const x0 = Math.min(...xs), y0 = Math.min(...ys), w = Math.max(...xs) - x0, hgt = Math.max(...ys) - y0;
    p.push(`<rect x="${x0}" y="${y0}" width="${w}" height="${hgt}" rx="22" class="hw-yard" style="fill:${col};opacity:${op * 0.22}"/>`);
    for (let i = 0; i < 4; i++) {
      const [x, y] = hwYardXY(s, i, ms);
      p.push(`<circle cx="${x}" cy="${y}" r="15" class="hw-spot" style="stroke:${col};opacity:${used ? 1 : 0.4}"/>`);
      const [hx, hy] = hwHomeXY(s, i, ms);
      p.push(`<circle cx="${hx}" cy="${hy}" r="15.5" class="hw-field hw-home" style="fill:color-mix(in srgb, ${col} ${used ? 38 : 16}%, #fff);stroke:${col}"/>`);
    }
  }
  for (let f = 0; f < 40; f++) {
    const [x, y] = hwFieldXY(f, ms), s = Math.floor(f / 10), k = f % 10;
    if (k === 0) {
      p.push(`<circle cx="${x}" cy="${y}" r="17" class="hw-field hw-start" style="fill:${HW_COLORS[s]};stroke:color-mix(in srgb, ${HW_COLORS[s]} 70%, #000)"/>`);
      p.push(`<text x="${x}" y="${y + 5}" class="hw-star">★</text>`);
    } else if (benches.includes(f)) {
      p.push(`<circle cx="${x}" cy="${y}" r="16" class="hw-field hw-bench"/><path d="M${x - 8} ${y + 1}h16M${x - 8} ${y - 4}h16M${x - 6} ${y + 1}v6M${x + 6} ${y + 1}v6" class="hw-benchic"/>`);
    } else p.push(`<circle cx="${x}" cy="${y}" r="15" class="hw-field"/>`);
  }
  p.push(`<circle cx="220" cy="220" r="17" class="hw-goal"/><text x="220" y="228" class="hw-goal-ic">🏠</text>`);
  return p.join("");
}
function hwDieSvg(v) {
  const pips = (HW_PIPS[v] || []).map(([x, y]) => `<circle cx="${x}" cy="${y}" r="9.5"/>`).join("");
  return `<svg viewBox="0 0 100 100" aria-hidden="true"><rect x="4" y="4" width="92" height="92" rx="22" class="hw-face"/>${pips}</svg>`;
}

function heimwaertsRulesView(r, rewards) {
  r = r || {};
  const items = [
    T("Everybody has 4 pieces in their yard. Roll the die and move one piece that many fields clockwise around the board."),
    T("A 6 brings a piece out onto your start field – and you roll again. Every 6 rolls again."),
    T("No piece out on the board? Then you have three tries to roll a 6."),
    T("Land on another player's piece and it goes back to its yard. Two of your own pieces never share a field."),
    r.bench ? T("Benches: on the start fields (★) and the benches nobody can be hit – and nobody may pass or land there. Only who comes out of the yard sends a piece on their own start field home.")
      : T("The start fields (★) are safe: a piece there cannot be hit, pieces of different colours may share it."),
    T("After a full round your pieces go into your home (4 fields) – never jumping over a piece in the home."),
    r.exact !== false ? T("You need the exact number to go into the home.") : T("Without the exact number a piece goes as deep into the home as it can."),
    r.play_on !== false ? T("The first with all 4 pieces home wins – the others play on for the next places.") : T("The first with all 4 pieces home wins – then the game ends."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", hwCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function heimwaertsStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/heimwaerts/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(solo ? Math.max(1, r.bots ?? 3) : 0, (solo ? [1, 2, 3] : [0, 1, 2, 3]).map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const chk = v => h("input", { type: "checkbox", checked: !!v });
  const bench = chk(r.bench), exact = chk(r.exact !== false), playOn = chk(r.play_on !== false);
  const picker = botPicker(r.bot_ms);
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", hwCoins(rw)), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", HW_ICON, " ", hwName(), solo ? " – " + I18N.tr(T("alone against bots")) : ""),
    h("p.small.muted", T("Roll the die and bring your 4 pieces around the board and home – send the others back to their yard!")),
    h("div.grid2", h("label.field", T("Bots"), bots), h("label.field", T("Bots play"), level)),
    solo ? null : h("p.small.muted", T("2 to 4 players: the family joins on their own devices, guests via QR code.")),
    h("div.cards-rules",
      h("label.check", bench, T("Benches (Eile mit Weile): safe fields nobody may pass")),
      h("label.check", exact, T("The exact number is needed to go into the home")),
      h("label.check", playOn, T("Play on for places 2 and 3 after the winner"))),
    picker.el,
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: +bots.value, level: level.value, bench: bench.checked, exact: exact.checked, play_on: playOn.checked,
        bot_ids: picker.ids(), bot_ms: picker.ms() };
      try { await api("community/heimwaerts/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("heimwaerts", bots, level, picker.el);          // parent area › Games: without bots
}

function heimwaertsLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, rolling = false;
  let board = null, boardKey = "", pieceEls = {}, shown = {}, seenSeq = null, seenRoll = null, autoTimer = null, autoKey = "";
  const myId = String(me.id);
  box.classList.add("hw-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); clearTimeout(autoTimer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const player = id => (st && st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const ms = () => st.my_seat ?? 0;
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { st = await api("community/heimwaerts/" + path, { method: "POST", body }); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { const s = await api("community/heimwaerts"); if (!rolling && !busy) { st = s; draw(); } } catch {}
    timer = setTimeout(poll, 800);
  }

  // ---------- the board: built once per game, the pieces move along the track
  function buildBoard() {
    const key = st.game + ":" + ms() + ":" + (st.benches || []).join(",");
    if (board && key === boardKey) return;
    boardKey = key; pieceEls = {}; shown = {};
    board = h("div.hw-board", { html: `<svg viewBox="0 0 440 440" xmlns="http://www.w3.org/2000/svg" class="hw-svg">${hwBoardSvg(ms(), st.players.map(p => p.seat), st.benches || [])}<g class="hw-targets"></g><g class="hw-pieces"></g></svg>` });
    board.addEventListener("click", tapBoard);
  }
  function piecesList() {
    const out = [];
    for (const p of st.players) (p.pieces || []).forEach((rel, i) => out.push({ id: p.id + ":" + i, owner: p.id, seat: p.seat, rel, i }));
    return out;
  }
  function placeOf(pc) {
    const [x, y] = hwPosXY(pc.seat, pc.rel, pc.i, ms());
    if (pc.rel < 0 || pc.rel >= 40) return [x, y];
    // pieces of different colours sharing a safe field: side by side
    const f = (10 * pc.seat + pc.rel) % 40;
    const same = piecesList().filter(q => q.rel >= 0 && q.rel < 40 && (10 * q.seat + q.rel) % 40 === f);
    if (same.length < 2) return [x, y];
    const k = same.findIndex(q => q.id === pc.id), off = (k - (same.length - 1) / 2) * 11;
    return [x + off, y - off * 0.4];
  }
  function pathOf(pc, from) {
    const out = [], to = pc.rel;
    if (from < 0 || to < from || to - from > 6) return null;
    for (let r = from + 1; r <= to; r++) out.push(hwPosXY(pc.seat, r, pc.i, ms()));
    return out;
  }
  const movesNow = () => (st && st.my_turn && st.stage === "move" ? st.moves || [] : []);
  function updatePieces() {
    const g = board.querySelector(".hw-pieces"), tg = board.querySelector(".hw-targets");
    const mv = movesNow(), pick = new Set(mv.map(m => myId + ":" + m.piece));
    tg.innerHTML = mv.map(m => {
      const [x, y] = hwPosXY(ms(), m.to, m.piece, ms());
      return `<circle cx="${x}" cy="${y}" r="15" class="hw-target${m.hit && m.hit.length ? " hit" : ""}"/>`;
    }).join("");
    for (const pc of piecesList()) {
      let el = pieceEls[pc.id];
      if (!el) {
        el = document.createElementNS("http://www.w3.org/2000/svg", "g");
        el.setAttribute("class", "hw-pc");
        const col = HW_COLORS[pc.seat];
        el.innerHTML = `<circle r="19" class="hw-pick"/><ellipse rx="12" ry="5" cy="9" class="hw-shadow"/>`
          + `<path d="M-10 9 Q-11 -2 -5 -5 A7.5 7.5 0 1 1 5 -5 Q11 -2 10 9 Z" fill="${col}" class="hw-pawn"/><circle r="2.6" cx="-2.5" cy="-11" class="hw-shine"/>`;
        g.append(el);
        pieceEls[pc.id] = el;
      }
      const [x, y] = placeOf(pc), old = shown[pc.id];
      el.style.transform = `translate(${x}px, ${y}px)`;
      if (old && old.rel !== pc.rel && el.animate) {
        const path = pc.rel >= 0 ? pathOf(pc, old.rel) : null;
        const frames = [old.xy, ...(path || []), [x, y]].map(([a, b]) => ({ transform: `translate(${a}px, ${b}px)` }));
        g.append(el);                                       // the moving piece on top
        try { el.animate(frames, { duration: pc.rel < 0 ? 650 : Math.min(1100, 120 + frames.length * 110), easing: "ease-in-out" }); } catch {}
      }
      shown[pc.id] = { rel: pc.rel, xy: [x, y] };
      el.classList.toggle("pick", pick.has(pc.id));
      el.classList.toggle("turn", !!st.turn && pc.owner === st.turn);
    }
    board.classList.toggle("picking", pick.size > 0);
  }
  function tapBoard(e) {
    const mv = movesNow();
    if (!mv.length || busy) return;
    const svg = board.querySelector("svg");
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = null, bd = 30 * 30;                          // the nearest piece that can move (or its target field)
    for (const m of mv) {
      const pc = piecesList().find(q => q.id === myId + ":" + m.piece);
      for (const [x, y] of [placeOf(pc), hwPosXY(ms(), m.to, m.piece, ms())]) {
        const d = (x - p.x) ** 2 + (y - p.y) ** 2;
        if (d < bd) { bd = d; best = m; }
      }
    }
    if (best) move(best.piece);
  }
  async function begin() {
    if (busy) return;
    busy = true;
    try { const r = await beginGame("community/heimwaerts/begin", st.players); if (r) st = r; }
    catch (e) { toast(e.message, "bad"); }
    finally { busy = false; draw(true); }
  }
  async function move(piece) {
    clearTimeout(autoTimer);
    const res = await act("move", { piece });
    if (res) try { Sound.play("tap"); } catch {}
  }
  async function roll() {
    if (!st || !st.can_roll || busy || rolling) return;
    rolling = true;
    const die = box.querySelector(".hw-die");
    const spin = die ? setInterval(() => { die.innerHTML = hwDieSvg(1 + Math.floor(Math.random() * 6)); }, 80) : null;
    if (die) die.classList.add("rolling");
    try { Sound.play("tap"); } catch {}
    const t0 = Date.now();
    let res = null, err = null;
    busy = true;
    try { res = await api("community/heimwaerts/roll", { method: "POST", body: {} }); } catch (e) { err = e; }
    busy = false;
    await new Promise(ok => setTimeout(ok, Math.max(0, 600 - (Date.now() - t0))));
    clearInterval(spin);
    rolling = false;
    if (err) toast(err.message, "bad");
    if (res) { st = res; seenRoll = st.roll_seq; }
    draw(true);
  }
  // only one way to move (all pieces in the yard count as one): move by itself after a moment
  function autoMove() {
    const mv = movesNow();
    const key = mv.length ? st.game + ":" + st.roll_seq : "";
    if (key === autoKey) return;
    autoKey = key;
    clearTimeout(autoTimer);
    if (!mv.length || new Set(mv.map(m => m.from + ">" + m.to)).size !== 1) return;
    autoTimer = setTimeout(() => { if (alive && st && st.my_turn && st.stage === "move" && st.game + ":" + st.roll_seq === autoKey) move(mv[0].piece); }, 750);
  }
  // what happened since the last look: a toast for hits on me and for a roll that cannot move
  function news() {
    const log = st.log || [];
    const lastSeq = log.length ? log[log.length - 1].seq : 0;
    if (seenSeq === null) { seenSeq = lastSeq; return; }
    for (const ev of log.filter(e => e.seq > seenSeq)) {
      if (ev.kind === "move" && (ev.hit || []).some(([o]) => o === myId)) { toast("💥 " + I18N.tr(T("{0} sent your piece back to the yard!")).replace("{0}", who(ev.player)), "bad"); try { Sound.play("wrong"); } catch {} }
      else if (ev.kind === "move" && ev.player === myId && (ev.hit || []).length) { toast("💥 " + I18N.tr(T("Hit! Back to the yard with {0}")).replace("{0}", ev.hit.map(([o]) => who(o)).join(", ")), "good"); try { Sound.play("right"); } catch {} }
      else if (ev.kind === "move" && ev.player === myId && ev.home) { try { Sound.play("right"); } catch {} }
      else if (ev.player === myId && ev.kind === "pass") toast(I18N.tr(T("{0} – no piece can move")).replace("{0}", ev.die));
      else if (ev.player === myId && ev.kind === "try") toast(I18N.tr(T("No 6 – try {0} of 3")).replace("{0}", ev.try + 1));
      else if (ev.player === myId && ev.kind === "again") toast(T("6 – roll again!"));
    }
    seenSeq = lastSeq;
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    turnCue("heimwaerts", st && st.my_turn && st.stage === "roll");
    if (rolling) return;
    const sig = JSON.stringify(st && [st.phase, st.status, st.turn, st.stage, st.roll_seq, st.joined, st.players.map(p => [p.id, p.pieces, p.place]), st.last && st.last.seq]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", HW_ICON), h("h2", T("No game right now")), noTableActions("heimwaerts", back)));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests, End (whoever leads), language – only the main action (Start) stays as a big button
    const menu = gameMenu({ rules: () => heimwaertsRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "heimwaerts" : null,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", HW_ICON, " ", hwName())));
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: begin }, "▶ ", T("Start"))) : null;
    if (st.phase !== "lobby") starterBanner(st.starter, "heimwaerts");
    if (st.phase === "done" && st.players[0] && st.players[0].pieces) { buildBoard(); updatePieces(); return show(head, result()); }
    if (st.phase === "done" || st.phase === "lobby" || !st.joined) {
      if (!st.joined && st.phase !== "lobby" && st.phase !== "done") { buildBoard(); show(close, head, seats(), h("div.hw-mid", board), h("p.muted.center", T("The game has already started")), host); updatePieces(); return; }
      if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), lobbySeats(), host);
      return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
        h("p.muted", T("Everybody joins on their own device.")), lobbySeats(),
        st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", hwCoins(st.rewards))) : null), host);
    }
    news();
    buildBoard();
    show(close, head, seats(), h("div.hw-mid", board), controls(), host);
    updatePieces();
    autoMove();
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobbySeats() {
    const free = Array.from({ length: st.bots || 0 }, () => h("div.dm-seat.hw-botseat", h("span.bot-av", { style: { width: "30px", height: "30px", fontSize: "18px" } }, "🤖"), h("span.small.muted", T("Bot"))));
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), seatIcon(p, 30), C(p.name, "strong.small.dm-name"))), ...free);
  }
  function seats() {
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    return h("div.hw-seats", ...st.players.map(p => h("div.hw-seat" + (st.turn === p.id ? ".turn" : "") + (p.id === myId ? ".me" : ""),
      { style: { "--hc": HW_COLORS[p.seat] } },
      seatIcon(p, 24),
      h("div.hw-sinfo", C(p.name, "strong.small.hw-sname"),
        h("span.hw-stat", p.finished ? medal(p.finished) + " " : "", "🏠 " + p.home + "/4")))));
  }
  function lastText() {
    const l = st.last;
    if (!l) return "";
    const n = who(l.player);
    if (l.kind === "pass") return I18N.tr(T("{0} rolled {1} – no piece can move")).replace("{0}", n).replace("{1}", l.die);
    if (l.kind === "try") return I18N.tr(T("{0} rolled {1} – try {2} of 3")).replace("{0}", n).replace("{1}", l.die).replace("{2}", l.try + 1);
    if (l.kind === "again") return I18N.tr(T("{0} rolled a 6 – roll again")).replace("{0}", n);
    if (l.kind === "roll") return I18N.tr(T("{0} rolled {1}")).replace("{0}", n).replace("{1}", l.die);
    let txt = I18N.tr(T("{0} moved a piece by {1}")).replace("{0}", n).replace("{1}", l.die);
    if (l.out) txt += " · " + I18N.tr(T("a piece comes out"));
    if (l.home) txt += " · 🏠";
    if ((l.hit || []).length) txt += " · 💥 " + I18N.tr(T("back to the yard: {0}")).replace("{0}", l.hit.map(([o]) => who(o)).join(", "));
    return txt;
  }
  function controls() {
    const mine = st.my_turn, tp = player(st.turn);
    let msg;
    if (mine && st.stage === "roll") msg = h("strong.hw-turnmsg", st.three_tries ? I18N.tr(T("Roll a 6 to come out – try {0} of 3")).replace("{0}", (st.tries || 0) + 1) : T("Your turn – roll the die!"));
    else if (mine) msg = h("strong.hw-turnmsg", new Set(movesNow().map(m => m.from + ">" + m.to)).size > 1 ? T("Tap a glowing piece to move it") : T("Your piece moves …"));
    else msg = h("span.muted", I18N.tr(T("{0} is playing …")).replace("{0}", who(st.turn)));
    if (st.roll_seq !== seenRoll && !mine && st.die) {           // somebody else rolled: a short tumble
      seenRoll = st.roll_seq;
      setTimeout(() => { const d = box.querySelector(".hw-die"); if (d) { d.classList.add("tumble"); setTimeout(() => d.classList.remove("tumble"), 450); } }, 0);
    }
    const die = h("button.hw-die" + (st.can_roll ? ".go" : ""), { type: "button", disabled: !st.can_roll, onclick: roll, title: T("Roll"),
      style: { "--hc": HW_COLORS[tp.seat ?? 0] }, html: hwDieSvg(st.die || 0) });
    return h("section.card.hw-ctl" + (mine ? ".turn" : ""), { style: { "--hc": HW_COLORS[tp.seat ?? 0] } }, die,
      h("div.hw-ctlinfo", h("div.hw-msg", msg), h("div.small.muted.hw-last", lastText()),
        st.can_roll ? h("button.btn.hw-roll", { onclick: roll }, "🎲 ", T("Roll")) : null));
  }
  function result() {
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99));
    const m = player(myId);
    if (m.place === 1 && st.complete && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    const winners = ranked.filter(p => p.place === 1).map(p => p.name).join(" & ");
    return h("section.card.center.hw-result",
      h("h2", "🏆 ", C(winners)),
      board ? h("div.hw-board.hw-small", board.firstChild.cloneNode(true)) : null,
      h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".hw-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 30), C(p.name, "strong.grow"),
        h("span", "🏠 " + p.home + "/4"), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function heimwaertsView() {
  const box = h("div.hw-live");
  screen("games", box);
  heimwaertsLive(box, S.profile, () => go("games"));
}

async function heimwaertsFamilyCard() {
  const c = S.me && S.me.community, g = c && c.heimwaerts;
  return h("section.card.quiz-card", h("h2", HW_ICON, " ", hwName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("heimwaerts") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Roll the die and race your 4 pieces home – send the others back to their yard! Places 1 to 3 win coins at the family table.")),
         h("div.row.wrap", botsOn("heimwaerts") ? h("button.btn", { onclick: () => heimwaertsStartDialog(true, () => go("heimwaerts")) }, "🤖 ", T("Alone against bots")) : null,
           h("button.btn.ghost", { onclick: () => heimwaertsStartDialog(false, () => go("heimwaerts")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}
