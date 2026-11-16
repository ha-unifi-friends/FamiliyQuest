// Domino – a live family game: double-6 or double-9, «simple» or «Cuban» rules, teams, bots, guests (familyquest/domino.py).
// dominoLive(box, me, back) runs a table (family or alone against bots), dominoStartDialog(solo, onStarted) sets the rules.
// Uses botPicker() from cards.js and guestInvite() from community.js.
"use strict";

// double-9: every number in its own colour (readable on the light tile face in light and dark mode)
const DOMINO_COLORS = ["#868e96", "#e03131", "#1c7ed6", "#2b8a3e", "#f76707", "#7048e8", "#0b7285", "#e64980", "#8d5524", "#212529"];
const DOMINO_PIPS = [[], [4], [0, 8], [0, 4, 8], [0, 2, 6, 8], [0, 2, 4, 6, 8], [0, 2, 3, 5, 6, 8], [0, 2, 3, 4, 5, 6, 8],
  [0, 1, 2, 3, 5, 6, 7, 8], [0, 1, 2, 3, 4, 5, 6, 7, 8]];

// one tile as inline SVG: a (top / left) and b (bottom / right)
function dominoSvg(a, b, { vertical = false, colored = false } = {}) {
  const half = (n, ox, oy) => DOMINO_PIPS[n].map(i => {
    const x = ox + 25 + (i % 3) * 25, y = oy + 25 + Math.floor(i / 3) * 25;
    return `<circle cx="${x}" cy="${y}" r="${n > 6 ? 8.5 : 10}" fill="${colored ? DOMINO_COLORS[n] : "#1f2433"}"/>`;
  }).join("");
  const [w, hh] = vertical ? [100, 200] : [200, 100];
  const line = vertical ? `<line x1="12" y1="100" x2="88" y2="100"/>` : `<line x1="100" y1="12" x2="100" y2="88"/>`;
  return `<svg viewBox="0 0 ${w} ${hh}" xmlns="http://www.w3.org/2000/svg" aria-label="${a}–${b}">` +
    `<rect x="3" y="3" width="${w - 6}" height="${hh - 6}" rx="16" class="dm-face"/><g class="dm-mid">${line}</g>` +
    half(a, 0, 0) + (vertical ? half(b, 0, 100) : half(b, 100, 0)) + `</svg>`;
}

function dominoTile(a, b, opts = {}) {
  const cls = "span.dm-tile" + (opts.vertical ? ".v" : ".hz") + (opts.on ? ".on" : "") + (opts.dim ? ".dim" : "") + (opts.pick ? ".pick" : "") + (opts.end ? ".end" : "");
  return h(cls, { html: dominoSvg(a, b, opts), translate: "no", onclick: opts.onclick, title: `${a}–${b}` });
}

// positions of the line as a snake, in half-tile units: rows run right, then back left; a tile that does not fit
// any more stands upright at the row end (top half beside the row, bottom half above the next row's first half)
function dominoSnake(line, W) {
  const pos = [];
  let x = 0, y = 0, dir = 1, afterTurn = false;           // y = top of the current row's line (row line height 1)
  for (const [a, b] of line) {
    const dbl = a === b, cross = dbl && !afterTurn, len = cross ? 1 : 2;
    const fits = dir > 0 ? x + len <= W - 1 : x - len >= 1;
    if (!fits) {                                           // turn: upright tile at the row end, a on top
      const cx = dir > 0 ? x : x - 1;
      pos.push({ x: cx, y, v: true, flip: false });
      y += 2; x = dir > 0 ? x + 1 : x - 1; dir = -dir; afterTurn = true;
      continue;
    }
    if (cross) pos.push({ x: dir > 0 ? x : x - 1, y: y - 0.5, v: true, flip: false });
    else pos.push({ x: dir > 0 ? x : x - 2, y, v: false, flip: dir < 0 });   // running back: b|a so the halves touch
    x += dir * len; afterTurn = false;
  }
  const minY = Math.min(0, ...pos.map(p => p.y));
  for (const p of pos) p.y -= minY;
  const w = Math.max(1, ...pos.map(p => p.x + (p.v ? 1 : 2)));
  const hgt = Math.max(1, ...pos.map(p => p.y + (p.v ? 2 : 1)));
  return { pos, w, h: hgt };
}

function dominoRulesView(r) {
  const cuban = r.mode === "cuban";
  const items = [
    I18N.tr(T("Set: double-{0} ({1} tiles)")).replace("{0}", r.set).replace("{1}", r.set === 9 ? 55 : 28) + (r.set === 9 ? " · " + I18N.tr(T("every number has its own colour")) : ""),
    cuban ? T("Cuban rules: 10 tiles each, no drawing – who cannot play passes.") : T("Simple rules: 7 tiles each (10 with double-9)."),
    !cuban ? (r.draw ? T("Nothing fits? Draw from the boneyard until a tile fits – pass only when the boneyard is empty.") : T("Nothing fits? Pass.")) : null,
    r.teams ? T("Teams of two: partners sit opposite each other (seats 1 + 3 against 2 + 4). Teams need 4, 6 or 8 players.") : T("Everybody plays for themselves."),
    T("Lay a tile with a matching number on one of the two open ends. Fits on both ends? Choose left or right."),
    T("First round: who holds the highest double starts. Then the winning side starts – with teams any player of the team may lay the first tile."),
    cuban ? T("Who lays the last tile (domino) wins the round – the side scores the pips left in ALL other hands, the partner's too (Cuban scoring).")
      : T("Who lays the last tile (domino) wins the round – the side scores the pips left in the opponents' hands."),
    cuban ? T("Blocked (nobody can play any more): the side with the fewest pips wins and scores all pips left. A tie: no points, the round is repeated.")
      : T("Blocked (nobody can play any more): the side with the fewest pips wins and scores the opponents' pips. A tie: no points, the round is repeated."),
    I18N.tr(T("The first side with {0} points wins the match. Won while the others have 0 points: «Pollona»!")).replace("{0}", r.target),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function dominoStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/domino/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const mode = sel(r.mode || "cuban", [["cuban", T("Cuban")], ["simple", T("Simple")]]);
  const set = sel(r.set || 9, [[6, T("Double-6 (28 tiles)")], [9, T("Double-9 (55 tiles, coloured)")]]);
  const target = sel(r.target || 100, [[100, "100"], [150, "150"], [200, "200"]]);
  const bots = sel(solo ? 3 : 2, (solo ? [1, 2, 3, 4, 5] : [0, 1, 2, 3, 4]).map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")]]);
  const teams = h("input", { type: "checkbox", checked: r.teams !== false });
  const drawOn = h("input", { type: "checkbox", checked: !!r.draw });
  const drawLbl = h("label.check", drawOn, T("Draw from the boneyard when nothing fits"));
  const sync = () => { const cuban = mode.value === "cuban"; drawOn.disabled = cuban; drawLbl.classList.toggle("muted", cuban); if (cuban) drawOn.checked = false; };
  mode.onchange = () => {                     // the usual settings of each rule set
    const cuban = mode.value === "cuban";
    set.value = cuban ? "9" : "6"; teams.checked = cuban; drawOn.checked = !cuban; sync();
  };
  sync();
  const picker = botPicker(r.bot_ms);
  const m = modal(h("div.form", h("h2", "🁫 ", "Domino", solo ? " – " + I18N.tr(T("alone against bots")) : ""),
    h("div.grid3", h("label.field", T("Rules"), mode), h("label.field", T("Tiles"), set), h("label.field", T("Points to win"), target),
      h("label.field", solo ? T("Bots") : T("Bots at the table"), bots), h("label.field", T("Bots play"), level)),
    h("div.cards-rules", h("label.check", teams, T("Teams of two (with 4, 6 or 8 players)")), drawLbl),
    picker.el,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, mode: mode.value, set: +set.value, target: +target.value, teams: teams.checked, draw: drawOn.checked,
        bots: Math.max(+bots.value, picker.ids().length), level: level.value, bot_ids: picker.ids(), bot_ms: picker.ms() };
      try { await api("community/domino/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function dominoLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", choose = null, cheered = false;
  const myId = String(me.id);
  box.classList.add("dm-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    try { st = await api("community/domino/" + path, { method: "POST", body }); choose = null; draw(true); }
    catch (e) { toast(e.message, "bad"); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/domino"); draw(); } catch {}
    timer = setTimeout(poll, 900);
  }
  const player = id => st.players.find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const colored = () => st.rules.set === 9;
  const sideOf = s => (st.sides || []).find(x => x.id === s) || { members: [], score: 0 };
  const sideName = s => st.teams ? sideOf(s).members.map(who).join(" & ") : who(s);
  const mine = s => s === st.my_side;
  const turnOf = p => st.phase === "play" && (st.turn === p.id || st.turn === "team:" + p.side);
  const reasonTxt = x => x.tie ? I18N.tr(T("tie – no points")) : x.reason === "domino" ? "🁫 " + I18N.tr(T("domino")) : "🔒 " + I18N.tr(T("blocked"));

  function sheetView() {
    const sides = st.sides || [];
    const done = st.phase === "done";
    const dot = s => st.teams ? h("i.dm-dot.team" + s) : null;
    return h("div.form", h("h2", "📊 ", T("Score sheet")),
      done && st.pollona ? h("div.dm-pollona", "🏆 Pollona!") : null,
      h("ul.dm-sides", ...sides.map(s => h("li" + (mine(s.id) ? ".mine" : ""), dot(s.id), C(sideName(s.id), "span.grow"),
        h("b", String(s.score)), done && st.winner === s.id ? " 🏆" : ""))),
      (st.sheet || []).length ? h("div.dm-sheet-wrap", h("table.dm-sheet",
        h("thead", h("tr", h("th", "#"), h("th", T("Winner")), h("th", "+"), h("th", T("How")), h("th", T("Total")))),
        h("tbody", ...(st.sheet || []).map(x => h("tr", h("td", String(x.round)),
          h("td.dm-who", x.side != null ? [dot(x.side), C(sideName(x.side))] : "–"),
          h("td", String(x.points || 0)), h("td.small", reasonTxt(x)),
          h("td.dm-run", sides.map(s => String((x.totals || {})[s.id] ?? 0)).join(" : "))))))) : h("p.small.muted", T("No round finished yet.")),
      h("p.small.muted", I18N.tr(T("Target: {0} points")).replace("{0}", st.rules.target)));
  }
  const openModal = view => { const m = modal(h("div", view, h("button.btn", { onclick: () => m.close() }, T("Close")))); };

  function draw(force) {
    if (!alive || !box.isConnected) return;                            // the game was left meanwhile: a late answer
    if (st && !Array.isArray(st.players)) st = null;                 // not a game state (e.g. after «end»): no game
    const sig = JSON.stringify(st && [st.phase, st.turn, st.line.length, st.hand, st.round, st.joined, st.players.map(p => [p.tiles, p.passed]),
      (st.sheet || []).length, Math.ceil((st.next_ms || 0) / 1000)]) + choose;
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", "🁫"), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    const head = h("div.quiz-head.dm-head", h("h1", "🁫 Domino"), h("div.row",
      h("button.btn.small.ghost", { onclick: () => openModal(dominoRulesView(st.rules)), title: T("Rules") }, "📜"),
      st.round ? h("button.btn.small.ghost", { onclick: () => openModal(sheetView()), title: T("Score sheet") }, "📊") : null,
      st.round ? h("span.chip", I18N.tr(T("Round {0}")).replace("{0}", st.round)) : null));
    let host = isHost() && st.status !== "done" ? h("div.row.center.host-bar",
      st.phase === "lobby" ? h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Deal")) : null,
      !st.solo && !me.guest ? h("button.btn.ghost.small", { onclick: () => guestInvite("domino") }, "👥 ", T("Invite guests")) : null,
      h("button.btn.ghost.small", { onclick: () => { if (confirm(I18N.tr(T("End the game?")))) act("end").then(() => { stop(); back(); }); } }, T("End"))) : null;
    // everybody of the family who plays may invite guests – not only who leads the game
    if (!host && !me.guest && st.status !== "done" && !st.solo) host = h("div.row.center.host-bar", h("button.btn.ghost.small", { onclick: () => guestInvite("domino") }, "👥 ", T("Invite guests")));
    if (st.phase === "done") return show(head, result());
    if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), seats(), host);
    if (st.phase === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device.")), st.rules.teams ? h("p.small.muted", T("Teams of two (with 4, 6 or 8 players)")) : null, seats()), host);
    show(close, head, seats(), scoreBar(), table(), hand(), host);
  }

  function result() {
    const won = mine(st.winner);
    if (won && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const sides = [...(st.sides || [])].sort((a, b) => b.score - a.score);
    return h("section.card.center.dm-result",
      st.pollona ? h("div.dm-pollona", "🏆 Pollona!") : null,
      h("h2", "🏆 ", C(sideName(st.winner))),
      st.pollona ? h("p.small", T("Won while the others have 0 points.")) : null,
      h("ol.pk-rank", ...sides.map(s => h("li", ...s.members.map(id => seatIcon(player(id), 30)), C(sideName(s.id), "strong.grow"),
        h("span", I18N.tr(T("{0} points")).replace("{0}", s.score))))),
      h("div.row.center", h("button.btn.ghost", { onclick: () => openModal(sheetView()) }, "📊 ", T("Score sheet")), h("button.btn", { onclick: back }, T("Back"))));
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function seats() {
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (turnOf(p) ? ".turn" : "") + (p.id === myId ? ".dm-me" : "") + (st.teams ? ".team" + p.side : ""),
      seatIcon(p, 30), C(p.name, "strong.small.dm-name"),
      st.phase !== "lobby" ? h("span.small.dm-count", "▮ " + p.tiles) : null,
      p.passed ? h("span.dm-bubble", T("passes")) : null)));
  }
  function scoreBar() {
    if (!(st.sides || []).length) return null;
    return h("button.dm-scores", { onclick: () => openModal(sheetView()), title: T("Score sheet") },
      ...st.sides.map(s => h("span.dm-score" + (mine(s.id) ? ".mine" : "") + (st.teams ? ".team" + s.id : ""), C(st.teams ? sideName(s.id) : who(s.id), "span.dm-sn"), h("b", String(s.score)))),
      h("span.small.muted", "/ " + st.rules.target));
  }
  function table() {
    const line = st.line || [];
    const pick = choose && st.my_turn && line.length > 1;
    // the line snakes like on a real table: tiles touch end to end, doubles stand crosswise, at the row end a tile
    // stands upright and the next row runs back below it (dominoSnake – positions in half-tile units)
    const tbl = box.querySelector(".dm-table");
    const avail = Math.max(260, (tbl ? tbl.clientWidth : (box.clientWidth || innerWidth)) - 24);
    const per = innerWidth < 600 ? 6 : Math.max(6, Math.min(12, Math.floor(avail / 96)));
    const W = 2 * per + 1;
    const u = Math.max(18, Math.min(52, Math.floor(avail / W)));
    const lay = dominoSnake(line, W);
    const tiles = h("div.dm-snake", { style: { "--tw": 2 * u + "px", width: lay.w * u + "px", height: lay.h * u + "px" } },
      ...line.map((t, i) => {
        const p = lay.pos[i], first = i === 0, last = i === line.length - 1;
        const isNew = !!(st.last && st.last.tile) && (st.last.end === "left" ? first : last);
        const [x, y] = p.flip ? [t[1], t[0]] : t;
        const el = dominoTile(x, y, { vertical: p.v, colored: colored(), end: first || last, on: isNew, pick: pick && (first || last),
          onclick: pick && (first || last) ? () => act("play", { tile: choose, end: first ? "left" : "right" }) : null });
        el.style.left = p.x * u + "px"; el.style.top = p.y * u + "px";
        return el;
      }));
    let info = "";
    if (st.last) info = st.last.tile ? I18N.tr(T("{0} played")).replace("{0}", who(st.last.player))
      : st.last.passed ? I18N.tr(T("{0} passes")).replace("{0}", who(st.last.player)) : I18N.tr(T("{0} drew a tile")).replace("{0}", who(st.last.player));
    let res = null;
    if (st.phase === "between" && st.round_result) {
      const x = st.round_result;
      res = h("div.dm-round", x.tie ? h("strong", "🤝 ", T("A tie – no points, the round is repeated."))
        : h("strong", "🏆 ", I18N.tr(T("{0} won the round")).replace("{0}", sideName(x.side)), " · +" + x.points),
        h("div.small", reasonTxt(x)),
        h("div.small", I18N.tr(T("Next round in {0} s")).replace("{0}", Math.ceil((st.next_ms || 0) / 1000))));
    }
    return h("div.dm-table",
      res,
      h("div.dm-line", line.length ? tiles : h("span.dm-empty", st.turn && st.phase === "play" ? T("The first tile can be any tile.") : "")),
      h("div.dm-info.small", st.ends ? h("span", T("Open ends:"), " ", h("b.dm-endnum", String(st.ends[0])), " · ", h("b.dm-endnum", String(st.ends[1]))) : null,
        st.boneyard != null ? h("span", "🂠 ", I18N.tr(T("Boneyard: {0}")).replace("{0}", st.boneyard)) : null,
        info ? h("span.muted", info) : null));
  }
  function hand() {
    if (!st.hand) return null;
    const myTurn = st.my_turn && st.phase === "play";
    const playable = st.playable || {};
    const teamTurn = myTurn && String(st.turn).startsWith("team:");
    const tap = t => {
      if (!myTurn || !playable[t]) return;
      if (playable[t].length > 1) { choose = choose === t ? null : t; draw(true); return; }
      act("play", { tile: t });
    };
    let msg;
    if (!myTurn) msg = h("span.small.muted", st.phase === "play" ? (String(st.turn).startsWith("team:")
      ? I18N.tr(T("Team {0} starts …")).replace("{0}", sideName(st.turn.slice(5))) : I18N.tr(T("{0} is playing …")).replace("{0}", who(st.turn))) : "");
    else if (st.must_pass) msg = h("strong.dm-pass-msg", T("No tile fits – you must pass"));
    else if (st.can_draw) msg = h("strong.dm-pass-msg", T("No tile fits – draw from the boneyard"));
    else if (choose) msg = h("strong", T("Which end?"));
    else msg = h("strong", teamTurn ? T("Your team starts – lay any tile!") : (st.line || []).length ? T("Your turn!") : T("You start – lay any tile!"));
    return h("section.card.dm-mine" + (myTurn ? ".turn" : ""),
      h("p.center.dm-msg", msg),
      choose ? h("div.row.center.dm-choose",
        h("button.btn", { onclick: () => act("play", { tile: choose, end: "left" }) }, "◀ ", T("left")),
        h("button.btn", { onclick: () => act("play", { tile: choose, end: "right" }) }, T("right"), " ▶"),
        h("button.btn.ghost.small", { onclick: () => { choose = null; draw(true); } }, T("Cancel"))) : null,
      h("div.dm-hand", ...st.hand.map(t => { const [a, b] = t.split("-").map(Number);
        return dominoTile(a, b, { vertical: true, colored: colored(), on: myTurn && !!playable[t], dim: myTurn && !playable[t], pick: choose === t, onclick: () => tap(t) }); })),
      myTurn && (st.must_pass || st.can_draw) ? h("div.row.center",
        st.must_pass ? h("button.btn.big.dm-pass", { onclick: () => act("pass") }, "✋ ", T("Pass")) : null,
        st.can_draw ? h("button.btn.big", { onclick: () => act("draw") }, "🂠 ", T("Draw")) : null) : null);
  }
  poll();
}

async function dominoView() {
  const box = h("div.dm-live");
  screen("games", box);
  dominoLive(box, S.profile, () => go("games"));
}

async function dominoFamilyCard() {
  const c = S.me && S.me.community, g = c && c.domino;
  return h("section.card.quiz-card", h("h2", "🁫 Domino"),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("domino") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Lay matching tiles – simple or Cuban, in teams of two. First to 100 points!")),
         h("div.row.wrap", h("button.btn", { onclick: () => dominoStartDialog(true, () => go("domino")) }, "🤖 ", T("Alone against bots")),
           h("button.btn.ghost", { onclick: () => dominoStartDialog(false, () => go("domino")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}
