// «Kartenlauf» – live race board game with cards: marbles race around the board, cards say how far (familyquest/kartenlauf.py).
// kartenlaufLive(box, me, back) runs a table (family or alone against bots), kartenlaufStartDialog(solo, onStarted) sets the rules.
// Uses botPicker() from cards.js and guestInvite() from community.js.
"use strict";

const KL_ICON = "🏁";
const KL_COLORS = ["#e03131", "#1c7ed6", "#2f9e44", "#f08c00"];            // seat 0..3 (red, blue, green, orange)
const KL_RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"];
const KL_SUITS = { s: "♠︎", h: "♥︎", d: "♦︎", c: "♣︎" };
const KL_HINT = { A: "1 · 11 · ▶", K: "13 · ▶", Q: "12", J: "⇄", 4: "± 4", 7: "7 ✂", X: "★" };
const klName = () => I18N.tr(T("Card Race"));
const klCoins = list => list.join(" / ") + " 🪙";
const klRank = c => String(c || "").split(":")[1] || "";

// ---------------------------------------------------------------- the board (viewBox 0 0 400 400, the viewer's seat at the bottom)
const KL = { C: 200, R: 160, STEP: 360 / 64 };
function klAngle(f, mySeat) { return (90 + KL.STEP / 2 + (f - 16 * mySeat) * KL.STEP) * Math.PI / 180; }
function klRingXY(f, mySeat) { const a = klAngle(f, mySeat); return [KL.C + KL.R * Math.cos(a), KL.C + KL.R * Math.sin(a)]; }
function klHomeXY(seat, i, mySeat) {
  const a = (90 + (seat - mySeat) * 90) * Math.PI / 180, r = KL.R - 24 - i * 19;
  return [KL.C + r * Math.cos(a), KL.C + r * Math.sin(a)];
}
function klKennelXY(seat, i, mySeat) {
  const a = (90 + 42 + (seat - mySeat) * 90) * Math.PI / 180, r = KL.R + 14;
  const cx = KL.C + r * Math.cos(a) * 1.08, cy = KL.C + r * Math.sin(a) * 1.08;
  return [cx + (i % 2 ? 9.5 : -9.5), cy + (i < 2 ? -9.5 : 9.5)];
}
function klBoardSvg(mySeat, seatsUsed) {
  const parts = [`<circle cx="200" cy="200" r="${KL.R + 30}" class="kl-bg"/>`, `<circle cx="200" cy="200" r="${KL.R}" class="kl-track"/>`];
  for (let s = 0; s < 4; s++) {                           // a coloured quarter per seat (light), the home lane, the kennel
    const col = KL_COLORS[s], used = seatsUsed.includes(s);
    const [hx, hy] = klHomeXY(s, 3, mySeat), [ex, ey] = klHomeXY(s, -1, mySeat);
    parts.push(`<line x1="${ex}" y1="${ey}" x2="${hx}" y2="${hy}" stroke="${col}" stroke-width="16" stroke-linecap="round" style="opacity:${used ? 0.22 : 0.08}"/>`);
    const [kx, ky] = klKennelXY(s, 0, mySeat), [kx2, ky2] = klKennelXY(s, 3, mySeat);
    parts.push(`<rect x="${Math.min(kx, kx2) - 13}" y="${Math.min(ky, ky2) - 13}" width="${Math.abs(kx2 - kx) + 26}" height="${Math.abs(ky2 - ky) + 26}" rx="13" fill="${col}" opacity="${used ? 0.2 : 0.07}"/>`);
    for (let i = 0; i < 4; i++) {
      const [x, y] = klHomeXY(s, i, mySeat);
      parts.push(`<circle cx="${x}" cy="${y}" r="7.5" class="kl-field home" style="stroke:${col}"/>`);
      const [a, b] = klKennelXY(s, i, mySeat);
      parts.push(`<circle cx="${a}" cy="${b}" r="6.5" class="kl-field kennel" style="stroke:${col}"/>`);
    }
  }
  for (let f = 0; f < 64; f++) {
    const [x, y] = klRingXY(f, mySeat), s = Math.floor(f / 16);
    const start = f % 16 === 0;
    parts.push(start ? `<circle cx="${x}" cy="${y}" r="9" class="kl-field start" style="fill:color-mix(in srgb, ${KL_COLORS[s]} 35%, #fff);stroke:${KL_COLORS[s]}"/>`
      : `<circle cx="${x}" cy="${y}" r="6.3" class="kl-field${f % 16 === 15 ? " entry" : ""}"${f % 16 === 15 ? ` style="stroke:${KL_COLORS[(s + 1) % 4]}"` : ""}/>`);
  }
  parts.push(`<text x="200" y="196" class="kl-logo">🏁</text><text x="200" y="216" class="kl-logo-t">Kartenlauf</text>`);
  return parts.join("");
}

function klCard(code, opts = {}) {
  const [suit, rank] = String(code || ":").split(":");
  const joker = rank === "X";
  const cls = "button.kl-card" + (joker ? ".joker" : "") + (suit === "h" || suit === "d" ? ".red" : "") + (opts.on ? ".on" : "") + (opts.dim ? ".dim" : "")
    + (opts.sel ? ".sel" : "") + (opts.got ? ".got" : "") + (opts.small ? ".small" : "");
  return h(cls, { type: "button", translate: "no", onclick: opts.onclick, disabled: !opts.onclick, title: joker ? "Joker" : rank },
    h("b", joker ? "★" : rank), h("i", joker ? "Joker" : KL_SUITS[suit] || ""), opts.small ? null : h("small", KL_HINT[rank] || rank));
}

function kartenlaufRulesView(r, rewards) {
  const items = [
    T("Everybody has 4 marbles in the kennel. Bring them around the board and into your home – the first with all 4 home wins."),
    T("Cards: A = 1 or 11 or come out · K = 13 or come out · Q = 12 · J = swap one of your marbles with another marble · 4 = 4 forward or backward · 7 = split 7 steps among your marbles · 2, 3, 5, 6, 8, 9, 10 = that many forward · Joker = any card."),
    T("A marble that just came out is protected on its start field: nobody may pass it or land on it until it moves on."),
    T("Land exactly on a marble and it goes back to its kennel. With the 7 every marble you pass goes back too."),
    T("Into the home only forward, after the marble left its start field, with the exact number – no jumping over marbles in the home."),
    T("Rounds deal 6, 5, 4, 3, 2 cards, then again 6. Who cannot play throws the cards away for this round."),
    r.teams ? T("Teams of two: partners sit opposite. Every round each passes one card to the partner. With your 4 marbles home you play with your partner's marbles – the team with all 8 home wins.") : null,
    r.teams && r.seven_partner ? T("House rule: a 7 may also move the partner's marbles.") : null,
    !r.joker_last ? T("House rule: the joker may not bring the last marble home.") : null,
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", klCoins(rewards)) : null,
    T("Coins only at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function kartenlaufStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/kartenlauf/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const seats = sel(r.seats || 4, [[2, "2"], [3, "3"], [4, "4"]]);
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const teams = h("input", { type: "checkbox", checked: r.teams !== false });
  const seven = h("input", { type: "checkbox", checked: !!r.seven_partner });
  const joker = h("input", { type: "checkbox", checked: r.joker_last !== false });
  const teamLbl = h("label.check", teams, T("Teams of two (with 4 players, partners opposite)"));
  const sevenLbl = h("label.check", seven, T("A 7 may move the partner's marbles too"));
  const sync = () => { const four = seats.value === "4"; teams.disabled = !four; teamLbl.classList.toggle("muted", !four);
    seven.disabled = !four || !teams.checked; sevenLbl.classList.toggle("muted", seven.disabled); };
  seats.onchange = sync; teams.onchange = sync; sync();
  const picker = botPicker(r.bot_ms);
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", klCoins(rw)), h("br"),
      h("span.muted", T("Coins only at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", KL_ICON, " ", klName(), solo ? " – " + I18N.tr(T("alone against bots")) : ""),
    h("div.grid2", h("label.field", T("Players"), seats), h("label.field", T("Bots play"), level)),
    h("p.small.muted", solo ? T("Bots take the other seats.") : T("Free seats are taken by bots when the game starts.")),
    h("div.cards-rules", teamLbl, sevenLbl, h("label.check", joker, T("The joker may be the card that wins"))),
    picker.el,
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, seats: +seats.value, teams: teams.checked, seven_partner: seven.checked, joker_last: joker.checked,
        level: level.value, bot_ids: picker.ids(), bot_ms: picker.ms() };
      try { await api("community/kartenlauf/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("kartenlauf", null, level, picker.el);          // parent area › Games: without bots
}

function kartenlaufLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false;
  let sel = null;                       // { card, as, mode: "marble" | "target" | "seven" | "give", marble, split: [[id, n]] }
  let board = null, boardKey = "", marbleEls = {}, shown = {};
  const myId = String(me.id);
  box.classList.add("kl-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    if (busy) return;
    busy = true;
    try { st = await api("community/kartenlauf/" + path, { method: "POST", body }); sel = null; draw(true); }
    catch (e) { toast(e.message, "bad"); }
    finally { busy = false; }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/kartenlauf"); draw(); } catch {}
    timer = setTimeout(poll, 900);
  }
  const player = id => st.players.find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const seatOf = id => player(id).seat ?? 0;
  const colorOf = id => KL_COLORS[seatOf(id)];
  const marble = id => (st.marbles || []).find(m => m.id === id);

  // ---------- the board: built once per game, the marbles move (animated along the track)
  function xyOf(m) {
    const ms = st.my_seat ?? 0, s = seatOf(m.owner), i = +m.id.split(":").pop();
    if (m.pos < 0) return klKennelXY(s, i, ms);
    if (m.pos >= 64) return klHomeXY(s, m.pos - 64, ms);
    return klRingXY(m.pos, ms);
  }
  function pathOf(m, from) {                              // the fields a marble passes from its old place to the new one
    const ms = st.my_seat ?? 0, s = seatOf(m.owner), to = m.pos, entry = (16 * s + 63) % 64;
    if (from < 0 || to < 0) return null;
    const out = [];
    if (from < 64 && to < 64) {
      const fw = (to - from + 64) % 64, bw = (from - to + 64) % 64;
      if (fw && fw <= 13) for (let k = 1; k <= fw; k++) out.push(klRingXY((from + k) % 64, ms));
      else if (bw === 4) for (let k = 1; k <= 4; k++) out.push(klRingXY((from - k + 64) % 64, ms));
      else return null;
    } else if (from < 64) {
      const d = (entry - from + 64) % 64;
      for (let k = 1; k <= d; k++) out.push(klRingXY((from + k) % 64, ms));
      for (let i = 0; i <= to - 64; i++) out.push(klHomeXY(s, i, ms));
    } else for (let i = from - 64 + 1; i <= to - 64; i++) out.push(klHomeXY(s, i, ms));
    return out.length ? out : null;
  }
  function buildBoard() {
    const key = st.game + ":" + st.my_seat;
    if (board && key === boardKey) return;
    boardKey = key; marbleEls = {}; shown = {};
    const used = st.players.map(p => p.seat);
    board = h("div.kl-board", { html: `<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" class="kl-svg">${klBoardSvg(st.my_seat ?? 0, used)}<g class="kl-marbles"></g></svg>` });
    board.addEventListener("click", e => tapBoard(e));
  }
  function updateMarbles() {
    const g = board.querySelector(".kl-marbles");
    const pick = new Set(pickable()), chosen = sel && sel.marble, split = sel && sel.mode === "seven" ? Object.fromEntries(sel.split) : {};
    for (const m of st.marbles || []) {
      let el = marbleEls[m.id];
      if (!el) {
        el = document.createElementNS("http://www.w3.org/2000/svg", "g");
        el.setAttribute("class", "kl-m");
        el.innerHTML = `<circle r="12" class="kl-pick"/><circle r="7.6" fill="${colorOf(m.owner)}" class="kl-ball"/><circle r="2.6" cx="-2.4" cy="-2.6" class="kl-shine"/><text class="kl-badge" y="-11"></text>`;
        g.append(el);
        marbleEls[m.id] = el;
      }
      const [x, y] = xyOf(m);
      const old = shown[m.id];
      el.style.transform = `translate(${x}px, ${y}px)`;
      if (old && old.pos !== m.pos && el.animate) {
        const path = pathOf(m, old.pos);
        const frames = [old.xy, ...(path || []), [x, y]].map(([a, b]) => ({ transform: `translate(${a}px, ${b}px)` }));
        g.append(el);                                     // the moving marble on top
        try { el.animate(frames, { duration: Math.min(1400, 140 + frames.length * 85), easing: "ease-in-out" }); } catch {}
      }
      shown[m.id] = { pos: m.pos, xy: [x, y] };
      el.classList.toggle("fresh", !!m.fresh);
      el.classList.toggle("pick", pick.has(m.id));
      el.classList.toggle("chosen", chosen === m.id || !!split[m.id]);
      el.querySelector(".kl-badge").textContent = split[m.id] ? String(split[m.id]) : "";
    }
    board.classList.toggle("picking", pick.size > 0);
  }
  function tapBoard(e) {
    const svg = board.querySelector("svg");
    if (!svg || !st) return;
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = null, bd = 24 * 24;                         // the nearest marble that can be chosen (small marbles, big fingers)
    for (const id of pickable()) {
      const m = marble(id); if (!m) continue;
      const [x, y] = xyOf(m), d = (x - p.x) ** 2 + (y - p.y) ** 2;
      if (d < bd) { bd = d; best = id; }
    }
    if (best) tapMarble(best);
  }

  // ---------- choosing a move: card → marble → (option / target)
  const movesOf = () => !sel ? [] : (st.moves || []).filter(m => m.card === sel.card && (m.as || null) === (sel.as || null));
  function pickable() {
    if (!sel || !st || !st.my_turn) return [];
    if (sel.mode === "seven") {
      const used = sel.split.reduce((a, [, n]) => a + n, 0);
      return used < 7 ? st.seven_marbles || [] : [];
    }
    if (sel.mode === "target") return movesOf().filter(m => m.marble === sel.marble).map(m => m.target);
    if (sel.mode === "marble") return [...new Set(movesOf().map(m => m.marble))];
    return [];
  }
  function tapCard(card) {
    if (!st) return;
    if (st.phase === "exchange") {
      if (st.gave) return;
      sel = sel && sel.card === card ? null : { card, mode: "give" };
      return draw(true);
    }
    if (!st.my_turn) return;
    if (sel && sel.card === card) { sel = null; return draw(true); }
    const rk = klRank(card);
    if (rk === "X") return chooseJoker(card);
    startCard(card, null, rk);
  }
  function startCard(card, as, rk) {
    if (rk === "7") {
      if (!(st.seven || {})[card]) return toast(T("This card cannot be played now"), "bad");
      sel = { card, as, mode: "seven", split: [] };
      return draw(true);
    }
    sel = { card, as, mode: "marble" };
    if (!movesOf().length) { sel = null; toast(T("This card cannot be played now"), "bad"); }
    draw(true);
  }
  function chooseJoker(card) {
    const ok = KL_RANKS.filter(r => r === "7" ? (st.seven || {})[card] : (st.moves || []).some(m => m.card === card && m.as === r));
    if (!ok.length) return toast(T("This card cannot be played now"), "bad");
    const m = modal(h("div.form.center", h("h2", "★ ", T("The joker stands for …")),
      h("div.kl-ranks", ...ok.map(r => h("button.btn.kl-rank", { onclick: () => { m.close(); startCard(card, r, r); } }, h("b", r), h("small", KL_HINT[r] || r)))),
      h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel"))));
  }
  function tapMarble(id) {
    if (!sel) return;
    if (sel.mode === "seven") {
      const used = sel.split.reduce((a, [, n]) => a + n, 0);
      if (used >= 7) return;
      const e = sel.split.find(x => x[0] === id);
      if (e) e[1] += 1; else sel.split.push([id, 1]);
      try { Sound.play("tap"); } catch {}
      return draw(true);
    }
    if (sel.mode === "target") {
      const mv = movesOf().find(m => m.marble === sel.marble && m.target === id);
      if (mv) play(mv);
      return;
    }
    const opts = movesOf().filter(m => m.marble === id);
    if (!opts.length) return;
    if (opts[0].kind === "swap") { sel = { ...sel, mode: "target", marble: id }; return draw(true); }
    if (opts.length === 1) return play(opts[0]);
    sel = { ...sel, marble: id };
    draw(true);
    const both = s => opts.filter(o => o.kind === "move" && o.steps === s).length > 1;
    const label = o => o.kind === "out" ? ["▶ ", T("Bring out")] : o.kind === "back" ? ["↩ ", T("4 backwards")]
      : [o.steps + " ", both(o.steps) ? (o.home ? ["🏠 ", T("into the home")] : ["↻ ", T("on along the ring")]) : T("forward")];
    const m = modal(h("div.form.center", h("h2", T("How?")),
      h("div.kl-opts", ...opts.map(o => h("button.btn.big", { onclick: () => { m.close(); play(o); } }, ...label(o).flat()))),
      h("button.btn.ghost", { onclick: () => { m.close(); sel = { ...sel, marble: null }; draw(true); } }, T("Cancel"))));
  }
  async function begin() {
    if (busy) return;
    busy = true;
    try { const r = await beginGame("community/kartenlauf/begin", st.players); if (r) { st = r; sel = null; draw(true); } }
    catch (e) { toast(e.message, "bad"); }
    finally { busy = false; }
  }
  function play(mv) {
    const body = { card: mv.card, kind: mv.kind, marble: mv.marble, steps: mv.steps, home: mv.home, target: mv.target, split: mv.split };
    if (mv.as || (sel && sel.as)) body.as = mv.as || sel.as;
    act("play", body);
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;                            // the game was left meanwhile: a late answer
    if (st && !Array.isArray(st.players)) st = null;                 // not a game state (e.g. after «end»): no game
    turnCue("kartenlauf", st && st.phase !== "exchange" && st.my_turn);
    const sig = JSON.stringify(st && [st.phase, st.status, st.turn, st.hand, st.round, st.joined, st.players.length, st.gave,
      st.last && st.last.t, st.players.map(p => p.gave), Math.ceil((st.next_ms || 0) / 1000)]) + JSON.stringify(sel);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", KL_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    if (sel && st.phase !== "exchange" && !st.my_turn) sel = null;
    if (sel && !(st.hand || []).includes(sel.card)) sel = null;
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests, End (whoever leads), language – only the main action (Start) stays as a big button
    const menu = gameMenu({ rules: () => kartenlaufRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "kartenlauf" : null,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", KL_ICON, " ", klName())), h("div.row",
      st.round ? h("span.chip", I18N.tr(T("Round {0}")).replace("{0}", st.round)) : null));
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: begin }, "▶ ", T("Start"))) : null;
    if (st.phase !== "lobby") starterBanner(st.starter, "kartenlauf");
    if (st.phase === "done" && st.marbles) { buildBoard(); updateMarbles(); return show(head, result()); }
    if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      st.phase === "lobby" ? h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join")) : h("p.muted", T("The game has already started"))), lobbySeats(), host);
    if (st.phase === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device.")), lobbySeats(),
      st.rules.teams && st.rules.seats === 4 ? h("p.small.muted", T("Teams of two: partners sit opposite.")) : null,
      st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", klCoins(st.rewards))) : null), host);
    buildBoard();
    show(close, head, seats(), h("div.kl-mid", board, info()), hand(), host);
    updateMarbles();
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobbySeats() {
    const free = Array.from({ length: st.free || 0 }, () => h("div.dm-seat.kl-free", h("span.bot-av", { style: { width: "30px", height: "30px", fontSize: "18px" } }, "🤖"), h("span.small.muted", T("Bot"))));
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), seatIcon(p, 30), C(p.name, "strong.small.dm-name"))), ...free);
  }
  function seats() {
    return h("div.kl-seats", ...st.players.map(p => h("div.kl-seat" + (st.turn === p.id ? ".turn" : "") + (p.id === myId ? ".me" : ""),
      { style: { "--kc": KL_COLORS[p.seat] } },
      h("span.kl-dot"), seatIcon(p, 26),
      h("div.kl-sinfo", C(p.name, "strong.small.dm-name"),
        h("span.small.kl-stat", "🂠 " + p.cards, " · 🏠 " + p.home + "/4",
          st.teams ? h("b.kl-team.t" + p.side, p.side === "0" ? "A" : "B") : null,
          st.phase === "exchange" && p.gave ? " ✓" : "", st.dealer === p.id ? " 🎴" : "")))));
  }
  function lastText() {
    const l = st.last;
    if (!l) return "";
    if (l.exchange) return I18N.tr(T("Cards exchanged with the partner"));
    if (l.fold != null) return I18N.tr(T("No move possible: {0} throws the cards away")).replace("{0}", who(l.player));
    const card = klRank(l.card) === "X" ? "Joker (" + l.as + ")" : klRank(l.card);
    let txt = I18N.tr(T("Played by {0}: {1}")).replace("{0}", who(l.player)).replace("{1}", card);
    if (l.kind === "out") txt += " · " + I18N.tr(T("a marble comes out"));
    if (l.kind === "swap") txt += " · " + I18N.tr(T("swapped"));
    if ((l.home || []).length) txt += " · 🏠";
    if ((l.kicked || []).length) txt += " · 💥 " + I18N.tr(T("back to the kennel: {0}")).replace("{0}", l.kicked.length);
    return txt;
  }
  function info() {
    let msg;
    if (st.phase === "between") msg = h("strong", I18N.tr(T("Round {0} is over – new cards in {1} s")).replace("{0}", st.round).replace("{1}", Math.ceil((st.next_ms || 0) / 1000)));
    else if (st.phase === "exchange") msg = st.gave ? h("span.muted", T("Waiting for the others to give a card …"))
      : h("strong.kl-turnmsg", "🎁 ", I18N.tr(T("Choose a card for your partner {0}")).replace("{0}", who((player(myId) || {}).partner)));
    else if (st.my_turn) msg = h("strong.kl-turnmsg", sel ? selHint() : T("Your turn – tap a card!"));
    else msg = h("span.muted", I18N.tr(T("{0} is playing …")).replace("{0}", who(st.turn)));
    const ctl = (st.control || [])[0];
    return h("div.kl-info",
      h("div.kl-msg", msg),
      st.my_turn && ctl && ctl !== myId ? h("div.small.kl-partner", "🤝 ", I18N.tr(T("All your marbles are home – you now move the marbles of {0}")).replace("{0}", who(ctl))) : null,
      h("div.small.muted.kl-last", st.top ? klCard(st.top, { small: true }) : null, h("span", lastText())));
  }
  function selHint() {
    if (sel.mode === "seven") {
      const used = sel.split.reduce((a, [, n]) => a + n, 0);
      return I18N.tr(T("Split the 7: tap your marbles – {0} of 7 steps")).replace("{0}", used);
    }
    if (sel.mode === "target") return T("Now tap the marble to swap with");
    const kinds = new Set(movesOf().map(m => m.kind));
    return kinds.has("out") && kinds.size === 1 ? T("Tap a marble in your kennel") : T("Tap the marble to move");
  }
  function hand() {
    if (!st.hand) return null;
    const exch = st.phase === "exchange";
    const playable = new Set((st.moves || []).map(m => m.card).concat(Object.keys(st.seven || {}).filter(k => st.seven[k])));
    const myTurn = st.my_turn;
    let got = st.got;
    const cards = st.hand.map(c => {
      const isGot = !exch && got && c === got; if (isGot) got = null;
      return klCard(c, { on: (myTurn && playable.has(c)) || (exch && !st.gave), dim: myTurn && !playable.has(c), sel: sel && sel.card === c,
        got: isGot, onclick: (myTurn || (exch && !st.gave)) ? () => tapCard(c) : null });
    });
    const used = sel && sel.mode === "seven" ? sel.split.reduce((a, [, n]) => a + n, 0) : 0;
    const bar = sel && sel.mode === "seven" ? h("div.kl-seven",
      h("div.kl-split", ...sel.split.map(([id, n]) => h("span.kl-chip", { style: { "--kc": colorOf(id.split(":")[0]) } }, h("i.kl-dot"), " +" + n,
        h("button.btn.small.ghost", { onclick: () => { const e = sel.split.find(x => x[0] === id); e[1] -= 1; if (!e[1]) sel.split = sel.split.filter(x => x !== e); draw(true); } }, "−"))),
        h("span.kl-sum" + (used === 7 ? ".ok" : ""), used + " / 7")),
      h("div.row.center", h("button.btn", { disabled: used !== 7, onclick: () => play({ card: sel.card, kind: "seven", split: sel.split.map(([id, n]) => [id, n]) }) }, "✓ ", T("Play")),
        h("button.btn.ghost.small", { onclick: () => { sel.split = []; draw(true); } }, T("Reset")),
        h("button.btn.ghost.small", { onclick: () => { sel = null; draw(true); } }, T("Cancel")))) : null;
    const give = exch && sel && sel.mode === "give" ? h("div.row.center", h("button.btn", { onclick: () => act("give", { card: sel.card }) }, "🎁 ", T("Give to my partner")),
      h("button.btn.ghost.small", { onclick: () => { sel = null; draw(true); } }, T("Cancel"))) : null;
    const cancel = sel && (sel.mode === "marble" || sel.mode === "target") ? h("div.row.center", h("button.btn.ghost.small", { onclick: () => { sel = null; draw(true); } }, T("Cancel"))) : null;
    return h("section.card.kl-mine" + (myTurn || (exch && !st.gave) ? ".turn" : ""), h("div.kl-hand", ...cards), bar, give, cancel,
      !cards.length && st.phase === "play" ? h("p.small.muted.center", T("No cards left in this round.")) : null);
  }
  function result() {
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99));
    const mine = player(myId);
    if (mine.place === 1 && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    const winners = ranked.filter(p => p.place === 1).map(p => p.name).join(" & ");
    return h("section.card.center.kl-result",
      h("h2", "🏆 ", C(winners)),
      board ? h("div.kl-board.small-board", board.firstChild.cloneNode(true)) : null,
      h("ol.pk-rank", ...ranked.map(p => h("li", h("span.pj-medal", medal(p.place)), seatIcon(p, 30), C(p.name, "strong.grow"),
        st.teams ? h("b.kl-team.t" + p.side, p.side === "0" ? "A" : "B") : null,
        h("span", "🏠 " + p.home + "/4"), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.coins_on ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function kartenlaufView() {
  const box = h("div.kl-live");
  screen("games", box);
  kartenlaufLive(box, S.profile, () => go("games"));
}

async function kartenlaufFamilyCard() {
  const c = S.me && S.me.community, g = c && c.kartenlauf;
  return h("section.card.quiz-card", h("h2", KL_ICON, " ", klName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("kartenlauf") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Race your marbles around the board with cards – kick the others back to the kennel, play in teams. Places 1 to 3 win coins at the family table!")),
         h("div.row.wrap", botsOn("kartenlauf") ? h("button.btn", { onclick: () => kartenlaufStartDialog(true, () => go("kartenlauf")) }, "🤖 ", T("Alone against bots")) : null,
           h("button.btn.ghost", { onclick: () => kartenlaufStartDialog(false, () => go("kartenlauf")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}
