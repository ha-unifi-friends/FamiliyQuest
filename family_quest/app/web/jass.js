// «Jass» – the Swiss card game Schieber, live for the family (familyquest/jass.py).
// 4 players in 2 teams (partners opposite), choose the trump or push it to the partner, follow suit, Weis and Stöck.
// jassLive(box, me, back) runs a table (family or alone with 3 bots), jassStartDialog(solo, onStarted) sets the rules.
// The server deals, knows the legal cards and counts – this file draws the table. The cards are the ones of Tschau Sepp
// (shedCard() and the card backs from cards.js); botPicker() from cards.js, guestInvite() from community.js.
"use strict";

const JA_ICON = "♣️";
const JA_TEAM = ["#2f8fdd", "#f2545b"];                                   // team 0 (seats 1 + 3), team 1 (seats 2 + 4)
const jaName = () => I18N.tr(T("Jass"));
const jaCoins = n => n + " 🪙";
const JA_MODES = { obe: ["⬇", T("Obenabe")], une: ["⬆", T("Undeufe")] };

// the sign and the name of a game (a suit as trump, Obenabe, Undeufe)
function jaMode(mode) {
  if (JA_MODES[mode]) return [JA_MODES[mode][0], I18N.tr(JA_MODES[mode][1])];
  if (SWISS_SUITS[mode]) return [SWISS_SUITS[mode][0], SWISS_SUITS[mode][1]];
  if (FRENCH_SUITS[mode]) return [FRENCH_SUITS[mode][0], I18N.tr(FRENCH_SUITS[mode][1])];
  return ["?", ""];
}
const jaSuits = rules => rules.deck === "french" ? ["s", "h", "c", "d"] : ["schellen", "schilten", "rosen", "eicheln"];
const jaCard = (code, opts = {}) => shedCard("tschau", code, opts);

function jassRulesView(r, rewards) {
  r = r || {};
  const items = [
    T("4 players in 2 teams – your partner sits opposite. Free seats are taken by bots."),
    T("Who is on turn chooses the game: a suit as trump, Obenabe (the Ass is highest) or Undeufe (the 6 is highest) – or pushes it to the partner, who must then choose."),
    T("Follow suit if you can. You may always trump in instead – but never play a lower trump than one already in the trick, unless you only have trumps."),
    T("Trump order: Buur (Under / J) 20 points, Nell (9) 14, then Ass, König, Ober, 10, 8, 7, 6. The Buur never has to follow trump."),
    T("Points: Ass 11, König 4, Ober 3, Under 2, 10 10 – in Obenabe and Undeufe the 8 counts 8 (Undeufe: the 6 counts 11, the Ass nothing). The last trick +5: 157 per round, all 9 tricks (Match) +100."),
    r.weis !== false ? T("Weis with your first card: 3 in a row 20, 4 in a row 50, 5 in a row 100 (each more +50), 4 Under 200, 4 Nell 150, 4 Ass / König / Ober / 10 100. Only the team with the best Weis counts all of its Weis.") : null,
    r.stoeck !== false ? T("Stöck: König and Ober of trump in one hand – 20 points, always.") : null,
    r.mult ? T("Multipliers: Rosen / Schellen (♥ ♦) ×1, Schilten / Eicheln (♠ ♣) ×2, Obenabe / Undeufe ×3.") : null,
    r.goal === "rounds" ? I18N.tr(T("The team with more points after {0} rounds wins.")).replace("{0}", r.rounds)
      : I18N.tr(T("The first team with {0} points wins (counted at the end of a round).")).replace("{0}", r.target),
    rewards ? I18N.tr(T("Coins for each person of the family in the winning team: {0}")).replace("{0}", jaCoins(rewards[0])) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function jassStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/jass/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const deck = sel(r.deck || "swiss", [["swiss", T("Swiss cards (Schellen, Schilten, Rosen, Eicheln)")], ["french", T("French cards (♠ ♥ ♦ ♣)")]]);
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const goal = sel(r.goal === "rounds" ? "r" + r.rounds : "p" + (r.target || 1000),
    [...[500, 1000, 1500, 2500].map(n => ["p" + n, I18N.tr(T("{0} points")).replace("{0}", n)]),
     ...[1, 2, 4, 8, 12].map(n => ["r" + n, I18N.tr(n === 1 ? T("1 round") : T("{0} rounds")).replace("{0}", n)])]);
  if (![...goal.options].some(o => o.selected)) goal.value = "p1000";
  const chk = v => h("input", { type: "checkbox", checked: !!v });
  const weis = chk(r.weis !== false), stoeck = chk(r.stoeck !== false), mult = chk(r.mult), partners = chk(r.partners !== false);
  let back = CARD_BACKS[r.back] ? r.back : "classic";
  const backPrev = h("div.row.back-pick");
  const drawBacks = () => backPrev.replaceChildren(...Object.keys(CARD_BACKS).map(b => h("button.back-opt" + (b === back ? ".on" : ""),
    { type: "button", title: I18N.tr(CARD_BACKS[b]), "aria-pressed": String(b === back), onclick: () => { back = b; drawBacks(); } },
    jaCard(null, { back: b, small: true }))));
  drawBacks();
  const picker = botPicker(r.bot_ms);
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw[0] > 0 ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for each person of the family in the winning team: {0}")).replace("{0}", jaCoins(rw[0])), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", JA_ICON, " ", jaName(), solo ? " – " + I18N.tr(T("with 3 bots")) : ""),
    h("p.small.muted", T("The Swiss card game Schieber: 2 against 2, choose the trump or push it to your partner – who gets more points?")),
    h("label.field", T("Cards"), deck),
    h("div.grid2", h("label.field", T("Game to"), goal), h("label.field", T("Bots play"), level)),
    solo ? null : h("p.small.muted", T("4 seats: the family joins on their own devices, guests via QR code – bots take the free seats.")),
    h("div.cards-rules",
      h("label.check", weis, T("Weis (declared with the first card)")),
      h("label.check", stoeck, T("Stöck (König + Ober of trump: 20)")),
      h("label.check", mult, T("Multipliers: ×2 for Schilten / Eicheln (♠ ♣), ×3 for Obenabe / Undeufe")),
      solo ? null : h("label.check", partners, T("Two people with two bots play together as partners"))),
    picker.el,
    h("div.field", h("b", T("Card back")), backPrev),
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const g = goal.value, body = { solo, deck: deck.value, level: level.value, weis: weis.checked, stoeck: stoeck.checked, mult: mult.checked,
        partners: partners.checked, back, goal: g[0] === "r" ? "rounds" : "points", bot_ids: picker.ids(), bot_ms: picker.ms() };
      if (g[0] === "r") body.rounds = +g.slice(1); else body.target = +g.slice(1);
      try { await api("community/jass/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("jass", null, level, picker.el);          // parent area › Games: without bots
}

function jassLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false;
  let seenSeq = null, bubbles = {}, bubbleTimer = null, seenCards = new Set(), shownResult = null;
  const myId = String(me.id);
  box.classList.add("ja-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); clearTimeout(bubbleTimer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const player = id => (st && st.players || []).find(p => p.id === id) || {};
  const who = id => player(id).name || "?";
  const mySeat = () => st.my_seat ?? 0;
  const rel = p => ((p.seat - mySeat()) % 4 + 4) % 4;                     // 0 me (bottom), 1 right, 2 partner (top), 3 left
  const myTeam = () => st.my_team ?? 0;
  const teamName = t => st.joined ? (t === myTeam() ? I18N.tr(T("We")) : I18N.tr(T("They")))
    : st.players.filter(p => p.team === t).map(p => p.name).join(" & ");
  const openModal = view => { const m = modal(h("div", view, h("button.btn", { onclick: () => m.close() }, T("Close")))); };
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { st = await api("community/jass/" + path, { method: "POST", body }); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { const s = await api("community/jass"); if (!busy) { st = s; draw(); } } catch {}
    timer = setTimeout(poll, 700);
  }

  // ---------- what happened since the last look: speech bubbles at the seats (trump, «Schiebe», Weis, Stöck)
  function news() {
    const log = st.log || [];
    const lastSeq = log.length ? log[log.length - 1].seq : 0;
    if (seenSeq === null) { seenSeq = lastSeq; return; }
    const until = Date.now() + 2800;
    for (const ev of log.filter(e => e.seq > seenSeq)) {
      if (ev.kind === "push") bubbles[ev.player] = { text: I18N.tr(T("I push!")), until };
      else if (ev.kind === "trump") { const [ic, n] = jaMode(ev.mode); bubbles[ev.player] = { text: ic + " " + n, until: until + 600 }; }
      else if (ev.kind === "weis") bubbles[ev.player] = { text: I18N.tr(T("Weis {0}")).replace("{0}", ev.best), until };
      else if (ev.kind === "stoeck") { bubbles[ev.player] = { text: I18N.tr(T("Stöck!")), until }; try { Sound.play("right"); } catch {} }
      else if (ev.kind === "weis_win" && ev.team === myTeam() && st.joined) { try { Sound.play("right"); } catch {} }
      else if (ev.kind === "trick" && ev.player === myId) { try { Sound.play("tap"); } catch {} }
    }
    seenSeq = lastSeq;
    clearTimeout(bubbleTimer);
    const next = Math.min(...Object.values(bubbles).map(b => b.until));
    if (Number.isFinite(next)) bubbleTimer = setTimeout(() => { const now = Date.now(); for (const k in bubbles) if (bubbles[k].until <= now) delete bubbles[k]; draw(true); }, Math.max(50, next - Date.now()));
  }

  // ---------- the screen
  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    turnCue("jass", st && st.phase === "play" && st.my_turn);
    const sig = JSON.stringify(st && [st.phase, st.status, st.turn, st.round, st.mode, st.joined, st.hand, st.trick, st.totals, st.players.map(p => [p.id, p.cards, p.place]),
      st.log && st.log.length && st.log[st.log.length - 1].seq, st.seating, st.phase === "between" ? Math.ceil((st.next_ms || 0) / 1000) : 0]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", JA_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    const playing = st.phase !== "lobby" && st.phase !== "done";
    // ☰: rules, guests, the actions of whoever leads (mix the seats, end), language
    const lead = isHost() && st.status !== "done";
    const menu = gameMenu({ rules: () => jassRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "jass" : null,
      actions: [
        { ic: "🔀", label: T("Mix the seats"), hidden: !lead || st.phase !== "lobby" || st.players.length < 2, onclick: () => act("mix") },
        { ic: "⏹", label: T("End the game"), danger: true, hidden: !lead, confirm: T("End the game?"), onclick: () => act("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head.ja-head", h("div.row.head-title", menu, h("h1", JA_ICON, " ", jaName())), h("div.row",
      playing && st.last_trick ? h("button.btn.small.ghost", { onclick: () => openModal(lastTrickView()), title: T("Last trick") }, "🕘") : null,
      playing || st.phase === "done" ? h("button.btn.small.ghost", { onclick: () => openModal(tafel()), title: T("Score sheet") }, "📋") : null));
    // only the main action stays as a big button (who begins: the Schellen 7 – the server's own rule)
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Deal"))) : null;
    if (st.phase === "done") return show(head, result());
    if (st.phase === "lobby") {
      if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
        h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), lobbySeats(), host);
      return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
        h("p.muted", T("Everybody joins on their own device – bots take the free seats.")), lobbySeats(),
        st.coins_on && st.rewards[0] ? h("p.small", "🪙 ", I18N.tr(T("Coins for each person of the family in the winning team: {0}")).replace("{0}", jaCoins(st.rewards[0]))) : null), host);
    }
    news();
    show(close, head, scoreBar(), tableView(), message(), st.joined ? hand() : h("p.muted.center", T("The game has already started")), host);
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobbySeats() {
    const seats = st.seating || [];
    const one = (s, i) => {
      const p = s.id ? st.players.find(x => x.id === s.id) : null;
      return h("div.dm-seat.ja-lseat" + (s.id === myId ? ".dm-me" : "") + (p ? "" : ".ja-botseat"), { style: { "--tc": JA_TEAM[s.team] } },
        p ? seatIcon(p, 30) : h("span.bot-av", { style: { width: "30px", height: "30px", fontSize: "18px" } }, "🤖"),
        p ? C(p.name, "strong.small.dm-name") : h("span.small.muted", T("Bot")), h("span.small.muted", (i + 1) + ""));
    };
    return h("div.ja-lteams", ...[0, 1].map(t => h("div.ja-lteam", { style: { "--tc": JA_TEAM[t] } },
      h("b.small", I18N.tr(T("Team {0}")).replace("{0}", t === 0 ? "A" : "B")),
      ...seats.map((s, i) => [s, i]).filter(([s]) => s.team === t).map(([s, i]) => one(s, i)))));
  }
  function scoreBar() {
    const mine = st.joined ? myTeam() : 0;
    const pill = t => h("div.ja-sc" + (t === mine && st.joined ? ".mine" : ""), { style: { "--tc": JA_TEAM[t] } },
      C(teamName(t), "span.ja-scn"), h("b", String(st.totals[t])),
      st.phase === "play" ? h("span.ja-scr", "+" + (st.pts[t] + st.weis_pts[t] + st.stoeck_pts[t])) : null);
    const goal = st.rules.goal === "rounds" ? I18N.tr(T("Round {0} of {1}")).replace("{0}", st.round).replace("{1}", st.rules.rounds)
      : I18N.tr(T("to {0}")).replace("{0}", st.rules.target);
    const [ic, n] = st.mode ? jaMode(st.mode) : ["", ""];
    const trump = st.mode ? h("div.ja-trump" + (SWISS_SUITS[st.mode] ? ".swiss" : "") + (["h", "d"].includes(st.mode) ? ".red" : ""), { title: n },
      h("i", ic), h("span", C(n, "span.ja-tn"), st.mult > 1 ? h("b", " ×" + st.mult) : null)) : h("div.ja-trump.none", h("i", "?"), h("span.small", T("Trump")));
    return h("div.ja-score", pill(mine), trump, pill(1 - mine), h("div.ja-goal.small.muted", goal));
  }
  function seatView(p) {
    const r = rel(p), b = bubbles[p.id];
    const picker = st.picker === p.id;
    return h("div.ja-seat.ja-r" + r + (st.turn === p.id ? ".turn" : "") + (p.id === myId ? ".me" : ""), { style: { "--tc": JA_TEAM[p.team] } },
      b ? h("div.ja-bubble", C(b.text)) : null,
      seatIcon(p, r === 0 ? 24 : 32),
      h("div.ja-sinfo", C(p.name, "strong.ja-sname"),
        r === 0 ? null : h("div.ja-backs", ...Array.from({ length: Math.min(p.cards, 9) }, () => h("i.back-" + (st.rules.back || "classic"))))),
      picker && st.mode ? h("span.ja-pick", { title: I18N.tr(T("chose the trump")) }, jaMode(st.mode)[0]) : null);
  }
  function tableView() {
    const ps = [...st.players].sort((a, b) => rel(a) - rel(b));
    let trick = st.trick || [], done = false;
    if (!trick.length && st.last_trick && st.phase === "play") { trick = st.last_trick.cards; done = true; }
    const cards = trick.map(([pid, c]) => {
      const p = player(pid), k = st.round + ":" + c, isNew = !seenCards.has(k);
      seenCards.add(k);
      const win = done && st.last_trick.winner === pid;
      return h("div.ja-tc.ja-p" + rel(p) + (isNew && !done ? ".new" : "") + (win ? ".win" : "") + (done ? ".done" : ""), jaCard(c));
    });
    const mid = h("div.ja-mid", ...cards,
      done ? h("div.ja-took", I18N.tr(T("{0} takes the trick: +{1}")).replace("{0}", who(st.last_trick.winner)).replace("{1}", st.last_trick.points)) : null);
    let over = null;
    if (st.phase === "trump" && st.can_choose) over = choosePanel();
    else if (st.phase === "trump") over = h("div.ja-wait", h("span", I18N.tr(T("{0} chooses the trump …")).replace("{0}", who(st.turn))));
    else if (st.phase === "between") over = roundPanel();
    return h("div.ja-table", ...ps.map(seatView), mid, over);
  }
  function choosePanel() {
    const btn = m => { const [ic, n] = jaMode(m); return h("button.ja-mode" + (["h", "d"].includes(m) ? ".red" : "") + (SWISS_SUITS[m] ? ".swiss" : ""),
      { type: "button", onclick: () => act("trump", { mode: m }) }, h("i", ic), C(n, "span")); };
    return h("div.ja-choose", h("strong", st.pushed ? T("Your partner pushed – you choose!") : T("Choose the trump")),
      h("div.ja-modes", ...jaSuits(st.rules).map(btn), btn("obe"), btn("une")),
      st.can_push ? h("button.btn.ja-push", { type: "button", onclick: () => act("trump", { mode: "push" }) }, "👉 ", T("Push to my partner")) : null);
  }
  function roundPanel() {
    const rr = st.round_result || {}, mine = st.joined ? myTeam() : 0;
    const row = (label, vals) => vals[0] || vals[1] ? h("tr", h("td", label), h("td", String(vals[mine])), h("td", String(vals[1 - mine]))) : null;
    const [ic, n] = jaMode(rr.mode);
    const secs = Math.ceil((st.next_ms || 0) / 1000);
    if (shownResult !== st.round) {
      shownResult = st.round;
      if (rr.match != null) { toast("🎉 " + I18N.tr(T("Match! All 9 tricks for {0}")).replace("{0}", teamName(rr.match)), rr.match === mine ? "good" : ""); if (rr.match === mine && st.joined) confetti(); }
    }
    return h("div.ja-round", h("strong", I18N.tr(T("Round {0}")).replace("{0}", rr.round), " · ", ic, " ", C(n), rr.mult > 1 ? " ×" + rr.mult : ""),
      h("table.ja-rt", h("tr", h("th"), h("th", C(teamName(mine))), h("th", C(teamName(1 - mine)))),
        row(T("Cards"), rr.cards || [0, 0]), row(T("Match"), rr.match != null ? [rr.match === 0 ? 100 : 0, rr.match === 1 ? 100 : 0] : [0, 0]),
        row(T("Weis"), rr.weis || [0, 0]), row(T("Stöck"), rr.stoeck || [0, 0]),
        h("tr.ja-sum", h("td", T("Round")), h("td", String((rr.points || [0, 0])[mine])), h("td", String((rr.points || [0, 0])[1 - mine]))),
        h("tr.ja-sum", h("td", T("Total")), h("td", String(st.totals[mine])), h("td", String(st.totals[1 - mine])))),
      st.joined ? h("button.btn", { onclick: () => act("next") }, "▶ ", T("Next round"), secs ? " (" + secs + ")" : "") : null);
  }
  function message() {
    let msg;
    if (st.phase === "play" && st.my_turn) msg = h("strong.ja-turnmsg", st.trick.length ? T("Your turn – play a glowing card") : T("Your turn – lead a card"));
    else if (st.phase === "play") msg = h("span.muted", I18N.tr(T("{0} is playing …")).replace("{0}", who(st.turn)));
    else if (st.phase === "trump" && st.can_choose) msg = h("strong.ja-turnmsg", T("Look at your cards and choose"));
    else msg = h("span.muted", st.phase === "between" ? T("Round over") : "");
    const w = st.weis_win, tricks = (st.tricks || [0, 0])[0] + (st.tricks || [0, 0])[1];
    const weisBar = w && st.phase === "play" && tricks <= 2 ? h("div.ja-weis", h("b.small", I18N.tr(T("Weis {0}")).replace("{0}", w.points), " · ", C(teamName(w.team)), ":"),
      ...Object.values(w.shown).flat().map(x => h("span.ja-wcards", ...x.cards.map(c => jaCard(c, { small: true }))))) : null;
    return h("div.ja-msg", weisBar || msg);
  }
  function hand() {
    const cards = st.hand || [], n = cards.length;
    const legal = new Set(st.legal || []), myPlay = st.phase === "play" && st.my_turn;
    const fan = h("div.ja-hand", { style: { "--n": n } }, ...cards.map((c, i) => {
      const ok = myPlay && legal.has(c);
      const el = jaCard(c, { on: ok, dim: myPlay && !ok, onclick: () => { if (ok && !busy) { try { Sound.play("tap"); } catch {} act("play", { card: c }); } } });
      el.style.setProperty("--i", i - (n - 1) / 2);
      if (ok) { el.setAttribute("role", "button"); el.tabIndex = 0; el.addEventListener("keydown", e => { if (e.key === "Enter") act("play", { card: c }); }); }
      return el;
    }));
    return h("div.ja-mine" + (st.my_turn ? ".turn" : ""), { style: { "--tc": JA_TEAM[player(myId).team ?? 0] } }, fan);
  }
  function lastTrickView() {
    const lt = st.last_trick;
    return h("div.form", h("h2", "🕘 ", T("Last trick")),
      h("div.ja-lt", ...lt.cards.map(([pid, c]) => h("div.ja-ltc" + (pid === lt.winner ? ".win" : ""), jaCard(c), C(who(pid), "span.small")))),
      h("p.center", I18N.tr(T("{0} takes the trick: +{1}")).replace("{0}", who(lt.winner)).replace("{1}", lt.points)));
  }
  function tafel() {
    const mine = st.joined ? myTeam() : 0, log = st.rounds_log || [];
    return h("div.form", h("h2", "📋 ", T("Score sheet")),
      h("table.ja-tafel", h("tr", h("th", "#"), h("th", T("Trump")), h("th", C(teamName(mine))), h("th", C(teamName(1 - mine)))),
        ...log.map(rr => { const [ic, n] = jaMode(rr.mode); return h("tr", h("td", String(rr.round)), h("td", { title: n }, ic, rr.mult > 1 ? " ×" + rr.mult : "", rr.match != null ? " 🎉" : ""),
          h("td", String(rr.points[mine])), h("td", String(rr.points[1 - mine]))); }),
        h("tr.ja-sum", h("td"), h("td", T("Total")), h("td", String(st.totals[mine])), h("td", String(st.totals[1 - mine])))),
      log.length ? null : h("p.small.muted", T("No round played yet.")));
  }
  function result() {
    const m = player(myId);
    if (m.place === 1 && st.complete && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const tot = st.totals, win = tot[0] === tot[1] ? null : (tot[0] > tot[1] ? 0 : 1);
    const team = t => h("li" + (st.joined && t === myTeam() ? ".ja-me" : ""), { style: { "--tc": JA_TEAM[t] } },
      h("span.pj-medal", win === null || win === t ? "🥇" : "🥈"),
      h("span.ja-rteam", ...st.players.filter(p => p.team === t).map(p => h("span.ja-rp", seatIcon(p, 26), C(p.name, "strong.small")))),
      h("b", String(tot[t])), ...st.players.filter(p => p.team === t && p.coins).slice(0, 1).map(p => h("b.pj-plus", "+" + p.coins + " 🪙")));
    const order = win === 1 ? [1, 0] : [0, 1];
    return h("section.card.center.ja-result",
      h("h2", "🏆 ", win === null ? T("A tie!") : C(st.players.filter(p => p.team === win).map(p => p.name).join(" & "))),
      h("ol.pk-rank.ja-rank", ...order.map(team)),
      tafel(),
      st.complete ? null : h("p.small.muted", T("The game was ended early – ranked as it stood, no coins.")),
      st.coins_on ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }
  poll();
}

async function jassView() {
  const box = h("div.ja-live");
  screen("games", box);
  jassLive(box, S.profile, () => go("games"));
}

async function jassFamilyCard() {
  const c = S.me && S.me.community, g = c && c.jass;
  return h("section.card.quiz-card", h("h2", JA_ICON, " ", jaName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("jass") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("The Swiss card game Schieber: 2 against 2 with Trumpf, Obenabe and Undeufe, Weis and Stöck – with bots, the family and guests.")),
         h("div.row.wrap", botsOn("jass") ? h("button.btn", { onclick: () => jassStartDialog(true, () => go("jass")) }, "🤖 ", T("With 3 bots")) : null,
           h("button.btn.ghost", { onclick: () => jassStartDialog(false, () => go("jass")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}
