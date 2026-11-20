// «Schach» – chess with the full rules, live for the family (familyquest/schach.py, rules: schach_engine.py).
// A person can have several games at a time: against a bot, against somebody of the family on two devices (guests via
// QR code), or two people on one device (pass and play, the board turns). Games can be paused and continued later.
// schachPanel(me, open) lists the own games and the invitations, schachStartDialog(mode, onStarted) starts a game,
// schachLive(box, me, back, gid) plays one. The server knows the legal moves – this file draws the board.
"use strict";

const CH_ICON = "♟️";
const chName = () => I18N.tr(T("Chess"));
const CH_FILES = "abcdefgh";
// own simple piece drawings (100 × 100), filled with the colour of the side; details use currentColor
const CH_PIECES = {
  p: `<circle cx="50" cy="33" r="12"/><path d="M39 47h22l7 24H32z"/><rect x="25" y="71" width="50" height="15" rx="5"/>`,
  r: `<path d="M29 18h9v8h7v-8h10v8h7v-8h9v18h-7v30H36V36h-7z"/><rect x="25" y="66" width="50" height="20" rx="5"/><path d="M38 40h24" class="ch-d"/>`,
  n: `<path d="M30 86V74c0-10 6-17 12-24 4-5 5-9 4-12-4 5-9 7-14 7-5 0-8-4-6-8l8-12c3-5 8-10 14-12l3-8 6 7c13 3 20 16 19 32-1 10-4 18-4 30z"/><circle cx="43" cy="28" r="3.5" class="ch-e"/><rect x="25" y="74" width="50" height="12" rx="5"/>`,
  b: `<circle cx="50" cy="15" r="6"/><path d="M50 22c-13 9-17 22-15 31 2 7 7 11 15 11s13-4 15-11c2-9-2-22-15-31z"/><path d="M54 32l-9 13" class="ch-d"/><rect x="37" y="63" width="26" height="7" rx="3"/><rect x="25" y="70" width="50" height="16" rx="5"/>`,
  q: `<path d="M27 66l-6-37 14 18 6-27 9 25 9-25 6 27 14-18-6 37z"/><circle cx="21" cy="27" r="5"/><circle cx="41" cy="18" r="5"/><circle cx="59" cy="18" r="5"/><circle cx="79" cy="27" r="5"/><rect x="25" y="66" width="50" height="20" rx="5"/>`,
  k: `<rect x="46" y="6" width="8" height="24" rx="2"/><rect x="38" y="12" width="24" height="8" rx="2"/><path d="M33 66c-8-14-7-30 17-36 24 6 25 22 17 36z"/><rect x="25" y="66" width="50" height="20" rx="5"/>`,
};
const CH_VAL = { p: 1, n: 3, b: 3, r: 5, q: 9 };
const chCoins = n => n + " 🪙";

function chPieceSvg(c, x, y, size = 100, cls = "") {
  const white = c === c.toUpperCase();
  return `<g transform="translate(${x} ${y}) scale(${size / 100})" class="ch-pc ${white ? "ch-w" : "ch-b"} ${cls}">${CH_PIECES[c.toLowerCase()]}</g>`;
}
function chReason(r) {
  return { checkmate: T("checkmate"), stalemate: T("stalemate"), repetition: T("threefold repetition"), fifty: T("50-move rule"),
    material: T("not enough material"), resign: T("resigned"), timeout: T("time is up"), agreement: T("draw agreed"),
    ended: T("ended by a parent") }[r] || r;
}
function chLevel(l) { return { easy: T("easy"), normal: T("normal"), hard: T("hard") }[l] || l; }
function chClock(ms) {
  if (ms == null) return "";
  const s = Math.max(0, Math.ceil(ms / 1000));
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}

function schachRulesView(rw) {
  const items = [
    T("The usual rules of chess: the server checks every move – check, castling, en passant and promotion (you choose the piece)."),
    T("Tap a piece, then one of the marked squares. The last move is marked, a king in check glows red."),
    T("The game ends with checkmate or stalemate, after the same position three times, after 50 moves without a capture or a pawn move, when nobody can mate any more, when somebody resigns or a draw is agreed."),
    T("With a clock: who runs out of time loses – a draw if the other side has nothing left to mate with."),
    T("Pause: either player pauses the game, the clock stops – continue later from the list of your games. Who started the game or a parent can delete a paused game."),
    rw ? I18N.tr(T("Coins for the winner: {0} against somebody of the family, {1} against the hard bot, {2} against the normal bot – only after at least 10 own moves, not against the easy bot, not on one device, not against guests."))
      .replace("{0}", chCoins(rw[0])).replace("{1}", chCoins(rw[1])).replace("{2}", chCoins(rw[2])) : null,
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

// ---------------------------------------------------------------- starting a game
async function schachStartDialog(mode, onStarted) {
  let o = {};
  try { o = await api("community/schach"); } catch (e) { return toast(e.message, "bad"); }
  const r = o.rules || {}, rw = r.rewards || [0, 0, 0];
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const color = sel(r.color || "white", [["white", T("White")], ["black", T("Black")], ["random", T("Random")]]);
  const clock = sel(r.clock || 0, (r.clocks || [0, 5, 10, 15]).map(n => [n, n ? I18N.tr(T("{0} min per side")).replace("{0}", n) : T("No clock")]));
  const who = sel("", [["", "🌍 " + I18N.tr(T("Anybody (open seat, guests via QR code)"))], ...(o.family || []).map(p => [p.id, p.name])]);
  const coinsTxt = () => {
    if (mode === "local") return T("Two on one device: no coins.");
    if (mode === "bot") {
      const n = level.value === "hard" ? rw[1] : level.value === "normal" ? rw[2] : 0;
      return n ? I18N.tr(T("A win brings {0} (after at least 10 own moves).")).replace("{0}", chCoins(n)) : T("No coins against the easy bot.");
    }
    return rw[0] ? I18N.tr(T("A win against somebody of the family brings {0} (after at least 10 own moves) – not against guests.")).replace("{0}", chCoins(rw[0])) : "";
  };
  const coins = h("p.small.muted.pj-coins", "🪙 ", coinsTxt());
  level.onchange = () => coins.replaceChildren("🪙 ", coinsTxt());
  const title = { bot: T("Against the bot"), duel: T("Against somebody of the family"), local: T("Two on one device") }[mode];
  const m = modal(h("div.form", h("h2", CH_ICON, " ", chName(), " – ", I18N.tr(title)),
    mode === "local" ? h("p.small.muted", T("Pass and play: you take turns on this device, the board turns for whoever is to move.")) : null,
    mode === "duel" ? h("label.field", T("Opponent"), who) : null,
    h("div.grid2", mode === "bot" ? h("label.field", T("Bot"), level) : null, mode !== "local" ? h("label.field", T("Your colour"), color) : null,
      h("label.field", T("Clock"), clock)),
    coins,
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { mode, level: level.value, color: color.value, clock: +clock.value, opponent: mode === "duel" && who.value ? +who.value : null };
      try { const v = await api("community/schach/start", { method: "POST", body }); m.close(); onStarted(v.game); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Play")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

// ---------------------------------------------------------------- the list: my games, invitations, starting
async function schachPanel(me, open) {
  const box = h("div.ch-panel");
  const draw = o => {
    const mine = o.games || [], inv = (o.open || []).filter(g => g.host !== me.id), others = o.others || [];
    const del = async g => {
      if (!(await confirmDialog(I18N.tr(g.status === "lobby" ? T("Delete this invitation?") : T("Delete this paused game?"))))) return;
      try { draw(await api(`community/schach/${g.id}/delete`, { method: "POST", body: {} })); toast(T("Deleted"), "good"); } catch (e) { toast(e.message, "bad"); }
    };
    const label = g => {
      if (g.mode === "local") return I18N.tr(T("Two on one device"));
      if (g.status === "lobby") return g.invite ? I18N.tr(T("Waiting for {0}")).replace("{0}", g.invite) : I18N.tr(T("Waiting for an opponent"));
      const o2 = g.opp || {};
      return (o2.bot ? (o2.emoji || "🤖") + " " : "") + (o2.name || "?") + (o2.bot ? " (" + I18N.tr(chLevel(o2.level)) + ")" : "");
    };
    const state = g => g.status === "paused" ? h("span.ch-tag.paused", "⏸ ", T("paused"))
      : g.status === "lobby" ? h("span.ch-tag", "⏳")
      : g.my_turn ? h("span.ch-tag.turn", T("Your move")) : h("span.ch-tag", "…");
    const row = (g, mineRow) => h("div.ch-game",
      h("button.ch-open", { onclick: () => open(g.id) },
        h("span.ch-gic", { bot: "🤖", duel: "👥", local: "📱" }[g.mode]),
        h("span.ch-gtxt", C(mineRow ? label(g) : g.host_name + " → " + label(g), "strong.small"),
          h("span.small.muted", I18N.tr(T("Move {0}")).replace("{0}", g.moves + 1), g.clock ? " · ⏱ " + g.clock + "′" : "",
            g.status === "paused" && g.paused_by ? " · " + I18N.tr(T("paused by {0}")).replace("{0}", g.paused_by) : "")),
        state(g)),
      (g.status === "paused" || g.status === "lobby") && (g.host === me.id || me.role === "parent")
        ? h("button.icon-btn.ch-del", { title: T("Delete"), onclick: () => del(g) }, "🗑") : null);
    box.replaceChildren(...[
      mine.length ? h("div.ch-list", h("b.small", T("Your games")), ...mine.map(g => row(g, true))) : null,
      inv.length ? h("div.ch-list", h("b.small", T("Invitations")), ...inv.map(g => h("div.ch-game",
        h("span.ch-gic", "👥"), h("span.ch-gtxt.grow", C(g.host_name, "strong.small"), h("span.small.muted", g.invite ? T("invites you to a game") : T("is looking for an opponent"))),
        h("button.btn.small", { onclick: async () => { try { await api(`community/schach/${g.id}/join`, { method: "POST", body: {} }); open(g.id); } catch (e) { toast(e.message, "bad"); } } }, T("Join")),
        g.invite ? h("button.icon-btn.ch-del", { title: T("Decline"), onclick: () => del(g) }, "✕") : null))) : null,
      others.length ? h("details.ch-list", h("summary.small", T("All chess games of the family"), " (", others.length, ")"), ...others.map(g => row(g, false))) : null,
      me.guest ? null : h("div.row.wrap.ch-starts",
        botsOn("schach") ? h("button.btn", { onclick: () => schachStartDialog("bot", open) }, "🤖 ", T("Against the bot")) : null,
        h("button.btn.ghost", { onclick: () => schachStartDialog("duel", open) }, "👥 ", T("Against the family")),
        h("button.btn.ghost", { onclick: () => schachStartDialog("local", open) }, "📱 ", T("Two on one device")))].filter(Boolean));
  };
  try { draw(await api("community/schach")); } catch (e) { box.replaceChildren(h("p.bad", e.message)); }
  return box;
}

// ---------------------------------------------------------------- one game
function schachLive(box, me, back, gid) {
  let st = null, timer = null, tick = null, alive = true, busy = false, sel = null, lastSig = "", cheered = false, recvAt = 0, showMoves = false;
  box.classList.add("ch-live");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); clearInterval(tick); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  const leave = () => {
    // a game alone (bot / one device) with a clock pauses by itself when you leave it – the time would run on
    if (st && st.status === "running" && st.mode !== "duel" && st.clock && st.joined) api(`community/schach/${st.game}/pause`, { method: "POST", body: {} }).catch(() => {});
    stop();
  };
  window.addEventListener("hashchange", leave, { once: true });
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { st = await api(`community/schach/${gid}/${path}`, { method: "POST", body: body || {} }); recvAt = Date.now(); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try {
      if (!gid) {                                          // a guest: the game of the invitation
        const o = await api("community/schach");
        gid = (o.games[0] || {}).id;
        if (!gid) { st = null; draw(true); timer = setTimeout(poll, 2000); return; }
      }
      const s = await api(`community/schach/${gid}`);
      if (!busy) { st = s; recvAt = Date.now(); draw(); }
    } catch (e) { if (!st) { show(h("section.card.center", h("p.bad", e.message), h("button.btn", { onclick: () => { stop(); back(); } }, T("Back")))); return; } }
    timer = setTimeout(poll, st && st.status === "done" ? 4000 : 1000);
  }

  // ---------- the board
  const bottom = () => st.my_side || (st.mode === "local" ? st.turn : "w");
  const flip = () => bottom() === "b";
  const xy = sq => { const f = CH_FILES.indexOf(sq[0]), r = +sq[1] - 1; return flip() ? [(7 - f) * 100, r * 100] : [f * 100, (7 - r) * 100]; };
  const pieceAt = sq => st.board[(8 - +sq[1]) * 8 + CH_FILES.indexOf(sq[0])];
  const mineColor = c => c !== "." && (c === c.toUpperCase() ? "w" : "b") === st.turn;
  function boardSvg() {
    const p = [];
    for (let r = 0; r < 8; r++) for (let f = 0; f < 8; f++) {
      const sq = CH_FILES[f] + (r + 1), [x, y] = xy(sq);
      p.push(`<rect x="${x}" y="${y}" width="100" height="100" class="${(f + r) % 2 ? "ch-l" : "ch-dk"}"/>`);
    }
    for (const sq of st.last || []) { const [x, y] = xy(sq); p.push(`<rect x="${x}" y="${y}" width="100" height="100" class="ch-lastm"/>`); }
    if (sel) { const [x, y] = xy(sel); p.push(`<rect x="${x}" y="${y}" width="100" height="100" class="ch-sel"/>`); }
    if (st.check) { const [x, y] = xy(st.check); p.push(`<circle cx="${x + 50}" cy="${y + 50}" r="48" class="ch-check"/>`); }
    for (let i = 0; i < 8; i++) {                         // coordinates on the edge squares
      const fsq = CH_FILES[i] + (flip() ? 8 : 1), [fx, fy] = xy(fsq);
      p.push(`<text x="${fx + 94}" y="${fy + 94}" class="ch-coord" text-anchor="end">${CH_FILES[i]}</text>`);
      const rsq = (flip() ? "h" : "a") + (i + 1), [rx, ry] = xy(rsq);
      p.push(`<text x="${rx + 6}" y="${ry + 22}" class="ch-coord">${i + 1}</text>`);
    }
    for (let r = 0; r < 8; r++) for (let f = 0; f < 8; f++) {
      const c = st.board[r * 8 + f];
      if (c === ".") continue;
      const sq = CH_FILES[f] + (8 - r), [x, y] = xy(sq);
      p.push(chPieceSvg(c, x + 4, y + 4, 92));
    }
    if (sel) for (const t of (st.legal || {})[sel] || []) {
      const [x, y] = xy(t);
      p.push(pieceAt(t) !== "." || (pieceAt(sel).toLowerCase() === "p" && t[0] !== sel[0])
        ? `<circle cx="${x + 50}" cy="${y + 50}" r="44" class="ch-tgt cap"/>` : `<circle cx="${x + 50}" cy="${y + 50}" r="15" class="ch-tgt"/>`);
    }
    return `<svg viewBox="0 0 800 800" xmlns="http://www.w3.org/2000/svg" class="ch-svg" role="img" aria-label="${I18N.tr(T("Chess board"))}">${p.join("")}</svg>`;
  }
  function tapBoard(e) {
    if (!st || !st.my_turn || busy) return;
    const svg = box.querySelector(".ch-svg");
    const rc = svg.getBoundingClientRect();
    let f = Math.floor((e.clientX - rc.left) / rc.width * 8), r = Math.floor((e.clientY - rc.top) / rc.height * 8);
    if (f < 0 || f > 7 || r < 0 || r > 7) return;
    const sq = flip() ? CH_FILES[7 - f] + (r + 1) : CH_FILES[f] + (8 - r);
    if (sel && ((st.legal || {})[sel] || []).includes(sq)) return tryMove(sel, sq);
    sel = (st.legal || {})[sq] && mineColor(pieceAt(sq)) ? (sel === sq ? null : sq) : null;
    if (sel) try { Sound.play("tap"); } catch {}
    draw(true);
  }
  async function tryMove(frm, to) {
    const c = pieceAt(frm);
    let promo = null;
    if (c.toLowerCase() === "p" && (to[1] === "8" || to[1] === "1")) {
      promo = await new Promise(ok => {
        const white = c === "P";
        const m = modal(h("div.form.center", h("h2", T("Promotion")), h("p.small.muted", T("Which piece should the pawn become?")),
          h("div.ch-promo", ...["q", "r", "b", "n"].map(k => h("button.ch-pbtn", { onclick: () => { m.close(); ok(k); }, title: k,
            html: `<svg viewBox="0 0 100 100">${chPieceSvg(white ? k.toUpperCase() : k, 0, 0)}</svg>` }))),
          h("button.btn.ghost", { onclick: () => { m.close(); ok(null); } }, T("Cancel"))), { onClose: () => ok(null) });
      });
      if (!promo) return;
    }
    sel = null;
    const res = await act("move", { frm, to, promo });
    if (res) try { Sound.play(st.check ? "wrong" : "tap"); } catch {}
  }

  // ---------- the screen
  const who = side => (st.players || {})[side] || null;
  function strip(side) {
    const p = who(side);
    const icon = !p ? h("span.bot-av", { style: { width: "26px", height: "26px", fontSize: "15px" } }, "⏳")
      : p.bot ? h("span.bot-av", { style: { width: "26px", height: "26px", fontSize: "16px" } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, 26);
    const took = (st.captured || {})[side] || "";
    const adv = (side === "w" ? 1 : -1) * (st.material || 0);
    const caps = h("span.ch-caps", { html: [...took].map(c => `<svg viewBox="0 0 100 100">${chPieceSvg(c, 0, 0)}</svg>`).join("") }, adv > 0 ? h("b.small", "+" + adv) : null);
    const clk = st.clock ? h("span.ch-clock" + (st.ticking === side ? ".on" : "") + ((st.clock[side] || 0) < 30000 ? ".low" : ""), { "data-side": side }, chClock(st.clock[side])) : null;
    const nm = p ? (st.mode === "local" ? I18N.tr(side === "w" ? T("White") : T("Black")) : p.name) + (p.bot ? " · " + I18N.tr(chLevel(p.level)) : "") : (st.invite ? st.invite.name : I18N.tr(T("Waiting for an opponent")));
    return h("div.ch-strip" + (st.turn === side && st.status === "running" ? ".turn" : ""), icon,
      h("span.ch-dot." + (side === "w" ? "w" : "b")), C(nm, "strong.small.ch-name"), caps, clk);
  }
  function statusLine() {
    if (st.status === "lobby") return h("div.ch-msg", st.invite ? I18N.tr(T("Waiting for {0} …")).replace("{0}", st.invite.name) : T("Waiting for an opponent …"));
    if (st.status === "paused") return h("div.ch-msg.paused", "⏸ ", st.paused_by ? I18N.tr(T("Paused by {0}")).replace("{0}", st.paused_by) : T("Paused"));
    if (st.draw_offer && st.my_side && st.draw_offer !== st.my_side && st.mode === "duel") return h("div.ch-msg.offer", h("span", "½ ", T("Draw offered")),
      h("span.row", h("button.btn.small", { onclick: () => act("draw", { action: "accept" }) }, T("Accept")),
        h("button.btn.small.ghost", { onclick: () => act("draw", { action: "decline" }) }, T("Decline"))));
    const chk = st.check ? "⚠️ " + I18N.tr(T("Check!")) + " " : "";
    if (st.my_turn) return h("div.ch-msg.mine", chk, st.mode === "local" ? I18N.tr(st.turn === "w" ? T("White to move") : T("Black to move")) : I18N.tr(T("Your move")));
    const p = who(st.turn);
    return h("div.ch-msg", chk, p && p.bot ? I18N.tr(T("{0} is thinking …")).replace("{0}", p.name) : I18N.tr(T("{0} is to move")).replace("{0}", p ? p.name : "?"),
      st.draw_offer === st.my_side ? h("span.small.muted", " · ½ " + I18N.tr(T("you offered a draw"))) : null);
  }
  function moveList() {
    const ms = st.moves || [];
    const pairs = [];
    for (let i = 0; i < ms.length; i += 2) pairs.push(h("span.ch-mv", h("i", (i / 2 + 1) + "."), " " + ms[i] + (ms[i + 1] ? " " + ms[i + 1] : "")));
    const d = h("details.ch-moves", { open: showMoves, ontoggle: e => { showMoves = e.target.open; } },
      h("summary.small", "📜 ", I18N.tr(T("Moves: {0}")).replace("{0}", Math.ceil(ms.length / 2))), h("div.ch-mlist", { translate: "no" }, ...pairs));
    setTimeout(() => { const l = d.querySelector(".ch-mlist"); if (l) l.scrollTop = l.scrollHeight; }, 0);
    return d;
  }
  // draw and resign are part of the play and stay here – pause and delete are in ☰; «Continue» is the main action of a paused game
  function controls() {
    const playing = st.joined && (st.status === "running" || st.status === "paused");
    if (!playing) return null;
    return h("div.row.center.ch-ctl",
      st.status === "paused" ? h("button.btn.small", { onclick: () => act("resume") }, "▶ ", T("Continue")) : null,
      st.status === "running" && st.mode !== "local" ? h("button.btn.small.ghost", { disabled: st.draw_offer === st.my_side || st.draw_declined,
        onclick: async () => { if ((await confirmDialog(I18N.tr(T("Offer a draw?"))))) act("draw", { action: "offer" }); } }, "½ ", T("Offer draw")) : null,
      st.status === "running" && st.mode === "local" ? h("button.btn.small.ghost", { onclick: async () => { if ((await confirmDialog(I18N.tr(T("Agree to a draw?"))))) act("draw", { action: "offer" }); } }, "½ ", T("Draw by agreement")) : null,
      h("button.btn.small.ghost", { onclick: async () => { if ((await confirmDialog(I18N.tr(st.mode === "local" ? (st.turn === "w" ? T("White resigns?") : T("Black resigns?")) : T("Resign this game?"))))) act("resign"); } }, "🏳 ", T("Resign")));
  }
  function result() {
    const r = st.result || {};
    const winner = r.winner ? who(r.winner) : null;
    const mine = r.winner && st.my_side === r.winner && st.mode !== "local";
    if (mine && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const coin = st.coins && st.coins[st.me];
    const head = !r.winner ? "🤝 " + I18N.tr(T("It is a draw"))
      : st.mode === "local" ? "🏆 " + I18N.tr(r.winner === "w" ? T("White wins") : T("Black wins"))
      : "🏆 " + I18N.tr(T("Winner: {0}")).replace("{0}", winner ? winner.name : "?");
    return h("section.card.center.ch-result", h("h2", head), h("p.muted", I18N.tr(chReason(r.reason))),
      coin ? h("p", h("b.pj-plus", "+" + coin + " 🪙")) : null,
      mine && !coin && st.coins_on && r.reason !== "ended" ? h("p.small.muted", I18N.tr(T("No coins: a win brings coins only after at least {0} own moves.")).replace("{0}", st.min_moves)) : null,
      h("div.row.center", h("button.btn", { onclick: () => { stop(); back(); } }, T("Back"))));
  }
  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return st.status === "lobby" && !st.invite && !me.guest && st.host === me.id ? ["schach", st.game] : null; }
  function draw(force) {
    if (!alive || !box.isConnected) return;
    turnCue("schach", st && st.mode !== "local" && st.status === "running" && st.my_turn);
    const sig = JSON.stringify(st && [st.status, st.fen, st.draw_offer, st.paused_by, st.result, st.joined, sel, st.draw_declined]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const full = !!st;
    box.classList.toggle("quiz-full", full); document.body.classList.toggle("quiz-open", full);
    if (!st) return show(h("section.card.center", h("div.big-ic", CH_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: () => { stop(); back(); } }, T("Back"))));
    if (sel && !((st.legal || {})[sel])) sel = null;
    const close = h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { leave(); back(); } }, "✕");
    // ☰: rules, guests (an open seat), pause / delete, language – works in a paused game too
    const isLead = st.host === me.id || me.role === "parent";
    const menu = gameMenu({ rules: () => schachRulesView(st.rewards),
      invite: invite(),
      actions: [
        { ic: "⏸", label: T("Pause"), hidden: !st.joined || st.status !== "running", onclick: () => act("pause") },
        { ic: "▶", label: T("Continue"), hidden: !st.joined || st.status !== "paused", onclick: () => act("resume") },
        { ic: "🗑", label: T("Delete"), danger: true, hidden: st.status !== "paused" || !isLead, confirm: T("Delete this paused game?"),
          onclick: async () => { try { await api(`community/schach/${gid}/delete`, { method: "POST", body: {} }); stop(); back(); } catch (e) { toast(e.message, "bad"); } } }],
      onLeave: () => { leave(); back(); } });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", CH_ICON, " ", chName())));
    if (!st.joined && st.status === "lobby") {
      const from = (who("w") || who("b") || {}).name || "?";
      return show(close, head, h("section.card.center", h("p", I18N.tr(st.invite ? T("{0} invites you to a game") : T("{0} is looking for an opponent")).replace("{0}", from)),
        h("div.row.center", h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join")),
          st.invite ? h("button.btn.ghost", { onclick: async () => {
            try { await api(`community/schach/${gid}/delete`, { method: "POST", body: {} }); stop(); back(); } catch (e) { toast(e.message, "bad"); }
          } }, T("Decline")) : null)));
    }
    const top = flip() ? "w" : "b", bot = flip() ? "b" : "w";
    const board = h("div.ch-board", { html: boardSvg(), onclick: tapBoard });
    show(close, head, h("div.ch-area", strip(top), h("div.ch-mid", board), strip(bot)),
      st.status === "done" ? result() : statusLine(), invite() ? h("div.row.center", inviteBtn(invite())) : null, controls(), moveList());
  }
  // the clocks tick in the app between two looks at the server
  tick = setInterval(() => {
    if (!st || !st.clock || !st.ticking || st.status !== "running") return;
    const el = box.querySelector(`.ch-clock[data-side="${st.ticking}"]`);
    if (el) { const left = st.clock[st.ticking] - (Date.now() - recvAt); el.textContent = chClock(left); el.classList.toggle("low", left < 30000); }
  }, 250);
  poll();
}

async function schachView(gid) {
  const box = h("div.ch-live");
  if (gid) {
    screen("games", box);
    return schachLive(box, S.profile, () => go("games"), +gid);
  }
  screen("games", h("h1", CH_ICON, " ", chName()), await schachFamilyCard());
}

async function schachFamilyCard() {
  const panel = await schachPanel(S.profile, id => go("schach/" + id));
  return h("section.card.quiz-card.ch-card", h("h2", CH_ICON, " ", chName()),
    h("p.muted.small", T("Chess against the bot, against somebody of the family or two on one device – pause a game and continue it later.")), panel);
}
