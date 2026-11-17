// Texas Hold'em at the family table – every player on their own device (guests via QR code), play chips only.
// pokerLive(box, me, back) runs the table in `box` (full-screen overlay); pokerStartDialog(onStarted) sets the rules.
"use strict";

const HAND_NAMES = { high_card: T("High card"), pair: T("Pair"), two_pair: T("Two pair"), three: T("Three of a kind"),
  straight: T("Straight"), flush: T("Flush"), full_house: T("Full house"), four: T("Four of a kind"), straight_flush: T("Straight flush") };
const SUIT_SIGN = { s: "♠︎", h: "♥︎", d: "♦︎", c: "♣︎" };

function pokerCard(code, size = "") {
  if (!code) return h("div.pk-card.back" + (size ? "." + size : ""));
  const r = code[0] === "T" ? "10" : code[0], s = code[1];
  return h("div.pk-card" + (s === "h" || s === "d" ? ".red" : "") + (size ? "." + size : ""), { translate: "no", "aria-label": r + s },
    h("b", r), h("i", SUIT_SIGN[s]));
}

async function pokerStartDialog(onStarted) {
  let r = {};
  try { r = await api("community/poker/rules"); } catch {}
  const num = (v, min, max, step = 1) => h("input", { type: "number", min, max, step, value: v });
  const f = {
    start_chips: num(r.start_chips ?? 1000, 100, 1000000, 50), small_blind: num(r.small_blind ?? 10, 1, 100000),
    big_blind: num(r.big_blind ?? 20, 2, 200000), ante: num(r.ante ?? 0, 0, 100000),
    blind_minutes: h("select", ...[[0, T("never")], [5, "5 min"], [10, "10 min"], [15, "15 min"], [20, "20 min"], [30, "30 min"]]
      .map(([v, n]) => h("option", { value: v, selected: (r.blind_minutes ?? 10) === v }, n))),
    turn_seconds: h("select", ...[[0, T("no limit")], [20, "20 s"], [30, "30 s"], [45, "45 s"], [60, "60 s"], [120, "2 min"]]
      .map(([v, n]) => h("option", { value: v, selected: (r.turn_seconds ?? 30) === v }, n))),
    mode: h("select", h("option", { value: "equal", selected: r.mode !== "bank" }, T("Everybody starts with the same chips – who has none is out")),
      h("option", { value: "bank", selected: r.mode === "bank" }, T("Game leader with a bank – gives chips (buy-ins) on request"))),
    rebuys: num(r.rebuys ?? 3, 0, 99), max_players: num(r.max_players ?? 9, 2, 10),
  };
  const bankRow = h("label.field", T("Re-buys per player"), f.rebuys);
  const sync = () => { bankRow.hidden = f.mode.value !== "bank"; };
  f.mode.onchange = sync; sync();
  const m = modal(h("div.form", h("h2", "🃏 Texas Hold'em"),
    h("p.small.muted", T("Played with play chips only – they have nothing to do with coins or points.")),
    h("label.field", T("Game mode"), f.mode), bankRow,
    h("div.grid3", h("label.field", T("Start chips"), f.start_chips), h("label.field", T("Small blind"), f.small_blind),
      h("label.field", T("Big blind"), f.big_blind), h("label.field", T("Ante"), f.ante),
      h("label.field", T("Blinds double every"), f.blind_minutes), h("label.field", T("Time per move"), f.turn_seconds),
      h("label.field", T("Players at most"), f.max_players)),
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = Object.fromEntries(Object.entries(f).map(([k, el]) => [k, el.tagName === "SELECT" && k === "mode" ? el.value : +el.value]));
      try { await api("community/poker/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function pokerRules(r) {
  return h("div.form", h("h2", "📜 ", T("Rules")),
    h("ul.small",
      h("li", T("Everybody gets two cards; five cards come to the middle (3, then 1, then 1). The best five of your seven cards count.")),
      h("li", T("Bet, call, raise or fold – four rounds. Who has the best hand at the end or is the last one in wins the pot.")),
      h("li", I18N.tr(T("Blinds {0} / {1}")).replace("{0}", r.small_blind).replace("{1}", r.big_blind) +
        (r.blind_minutes ? " · " + I18N.tr(T("they double every {0} minutes")).replace("{0}", r.blind_minutes) : "")),
      h("li", r.mode === "bank" ? I18N.tr(T("Bank: who has no chips asks the game leader (at most {0} re-buys).")).replace("{0}", r.rebuys)
        : T("Everybody starts with the same chips; who has none is out – the last one wins.")),
      r.turn_seconds ? h("li", I18N.tr(T("{0} seconds per move – then the app checks or folds.")).replace("{0}", r.turn_seconds)) : null),
    h("p.small", "🏆 ", Object.entries(HAND_NAMES).reverse().map(([, n]) => I18N.tr(n)).join(" › ")));
}

function pokerLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", raiseTo = 0;
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    try { st = await api("community/poker/" + path, { method: "POST", body }); draw(true); }
    catch (e) { toast(e.message, "bad"); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/poker"); draw(); } catch {}
    timer = setTimeout(poll, 1000);
  }
  const fmtC = n => fmt(n);
  function draw(force) {
    if (!alive || !box.isConnected) return;                            // the game was left meanwhile: a late answer
    if (st && !Array.isArray(st.players)) st = null;                 // not a game state (e.g. after «end»): no game
    const sig = JSON.stringify(st && [st.phase, st.hand_no, st.street, st.to_act, st.pot, st.board, st.paused, st.requests,
      st.players.map(p => [p.chips, p.bet, p.folded, p.last, p.out]), Math.ceil((st.turn_ms || 0) / 1000), Math.ceil((st.next_ms || 0) / 1000)]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", "🃏"), h("h2", T("No poker table right now")),
      h("p.muted", T("Open a table – everybody plays on their own device.")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    const head = h("div.quiz-head", h("h1", "🃏 Texas Hold'em"), h("div.row",
      h("button.btn.small.ghost", { onclick: () => { const m = modal(h("div", pokerRules(st.rules), h("button.btn", { onclick: () => m.close() }, T("Close")))); } }, "📜 ", T("Rules")),
      st.hand_no ? h("span.chip", "#" + st.hand_no) : null,
      h("span.chip", I18N.tr(T("Blinds {0} / {1}")).replace("{0}", st.blinds[0]).replace("{1}", st.blinds[1]))));
    let host = isHost() && st.status !== "done" ? h("div.row.center.host-bar",
      st.phase === "lobby" ? h("button.btn", { disabled: st.players.length < 2, onclick: () => act("begin") }, "▶ ", T("Deal")) :
        h("button.btn.small", { onclick: () => act("pause", { on: !st.paused }) }, st.paused ? "▶ " + I18N.tr(T("Go on")) : "⏸ " + I18N.tr(T("Pause"))),
      !me.guest && !st.solo ? h("button.btn.ghost.small", { onclick: () => guestInvite("poker") }, "👥 ", T("Invite guests")) : null,
      h("button.btn.ghost.small", { onclick: () => { if (confirm(I18N.tr(T("End the game?")))) act("end"); } }, T("End"))) : null;
    // everybody of the family who plays may invite guests – not only who leads the game
    if (!host && !me.guest && st.status !== "done" && !st.solo) host = h("div.row.center.host-bar", h("button.btn.ghost.small", { onclick: () => guestInvite("poker") }, "👥 ", T("Invite guests")));
    if (st.phase === "done") {
      const rank = st.players.slice().sort((a, b) => (a.place || 99) - (b.place || 99));
      if (rank[0] && rank[0].id === me.id) { confetti(); try { Sound.play("done"); } catch {} }
      return show(head, h("section.card.center", h("h2", "🏆 ", C(rank[0] ? rank[0].name : "")),
        h("ol.pk-rank", ...rank.map(p => h("li", p.bot ? h("span.bot-av", { style: { width: "32px", height: "32px", fontSize: "19px" } }, p.emoji || "🤖") : avatarSvg(p.avatar, 32), C(p.name, "strong.grow"), h("span", "🪙 " + fmtC(p.chips))))),
        h("button.btn", { onclick: back }, T("Back"))));
    }
    if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), seats(), host);
    if (st.phase === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device.")), h("p.small", I18N.tr(T("Start chips: {0}")).replace("{0}", fmtC(st.rules.start_chips)))), seats(), host);
    show(close, head, tableView(), st.paused ? h("p.center.warn-text", "⏸ ", T("Paused")) : null, seats(), mine(), bank(), host);
    // on a small screen: when it is my turn, my cards and buttons come into view
    if (st.to_act === me.id) { const m = box.querySelector(".pk-mine"); if (m && m.getBoundingClientRect().bottom > innerHeight - 70) m.scrollIntoView({ block: "end", behavior: "smooth" }); }
  }
  function tableView() {
    const slots = [0, 1, 2, 3, 4].map(i => st.board[i] ? pokerCard(st.board[i]) : h("div.pk-card.empty"));
    const res = st.phase === "between" ? st.players.filter(p => p.won) : [];
    return h("div.pk-table",
      h("div.pk-board", ...slots),
      h("div.pk-pot", "🪙 ", fmtC(st.pot), st.current_bet ? h("span.small.muted", " · " + I18N.tr(T("to call: {0}")).replace("{0}", fmtC(st.current_bet))) : null),
      res.length ? h("div.pk-result", ...res.map(p => h("div", "🏆 ", C(p.name, "strong"), " +", fmtC(p.won), p.hand ? " – " + I18N.tr(HAND_NAMES[p.hand]) : ""))) : null,
      st.phase === "between" && st.next_ms != null ? h("div.small.muted", I18N.tr(T("Next hand in {0} s")).replace("{0}", Math.ceil(st.next_ms / 1000))) : null,
      st.phase === "waiting" ? h("div.warn-text", T("Waiting for chips from the game leader …")) : null);
  }
  function seats() {
    return h("div.pk-seats", ...st.players.map(p => h("div.pk-seat" + (st.to_act === p.id ? ".turn" : "") + (p.folded ? ".folded" : "") + (p.out ? ".out" : "") + (p.id === me.id ? ".me" : ""),
      h("div.row", p.bot ? h("span.bot-av", { style: { width: "34px", height: "34px", fontSize: "20px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar, 34), h("div.grow", C(p.name, "strong.small"), h("div.small", "🪙 " + fmtC(p.chips)))),
      h("div.pk-tags", p.dealer ? h("span.pk-tag.d", "D") : null, p.sb ? h("span.pk-tag", "SB") : null, p.bb ? h("span.pk-tag", "BB") : null,
        p.allin ? h("span.pk-tag.allin", "ALL-IN") : null, p.folded ? h("span.pk-tag", I18N.tr(T("folded"))) : null,
        p.bet ? h("span.pk-bet", fmtC(p.bet)) : null, p.out ? h("span.pk-tag", "#" + (p.place || "")) : null),
      p.cards ? h("div.pk-shown", ...p.cards.map(c => pokerCard(c, "small")), p.hand ? h("span.small", I18N.tr(HAND_NAMES[p.hand])) : null) : null)));
  }
  function mine() {
    const meP = st.players.find(p => p.id === me.id);
    if (!meP || !st.my_cards) return meP && meP.chips === 0 && st.rules.mode === "bank" ? null : null;
    const L = st.legal || {};
    const myTurn = st.to_act === me.id && Object.keys(L).length;
    const buttons = [];
    if (myTurn) {
      if (L.fold) buttons.push(h("button.btn.bad", { onclick: () => act("act", { kind: "fold" }) }, T("Fold")));
      if (L.check) buttons.push(h("button.btn", { onclick: () => act("act", { kind: "check" }) }, T("Check (pass)")));
      if (L.call) buttons.push(h("button.btn", { onclick: () => act("act", { kind: "call" }) }, I18N.tr(T("Call {0}")).replace("{0}", fmtC(L.call))));
      if (L.raise) {
        raiseTo = Math.min(Math.max(raiseTo || L.raise.min, L.raise.min), L.raise.max);
        const out = h("b", fmtC(raiseTo));
        const slider = h("input.pk-slider", { type: "range", min: L.raise.min, max: L.raise.max, step: Math.max(1, st.blinds[0]), value: raiseTo,
          oninput: e => { raiseTo = +e.target.value; out.textContent = fmtC(raiseTo); } });
        const quick = (label, v) => h("button.btn.small.ghost", { onclick: () => { raiseTo = Math.min(Math.max(v, L.raise.min), L.raise.max); slider.value = raiseTo; out.textContent = fmtC(raiseTo); } }, label);
        buttons.push(h("div.pk-raise", h("div.row", quick("½ " + I18N.tr(T("pot")), st.current_bet + Math.round(st.pot / 2)), quick(I18N.tr(T("pot")), st.current_bet + st.pot), quick("All-in", L.raise.max)),
          slider, h("button.btn.good", { onclick: () => act("act", { kind: raiseTo >= L.raise.max ? "allin" : "raise", amount: raiseTo }) },
            st.current_bet ? I18N.tr(T("Raise to")) : I18N.tr(T("Bet")), " ", out)));
      }
    }
    const tl = myTurn && st.turn_ms != null ? h("div.quiz-time", h("i", { style: { width: Math.min(100, 100 * st.turn_ms / (st.rules.turn_seconds * 1000)) + "%" } })) : null;
    return h("section.card.pk-mine" + (myTurn ? ".turn" : ""),
      h("div.row.center", ...st.my_cards.map(c => pokerCard(c, "big")), st.best ? h("span.pk-best", I18N.tr(HAND_NAMES[st.best])) : null),
      myTurn ? h("p.center", h("strong", T("Your move!"))) : h("p.center.small.muted", meP.folded ? T("You folded – wait for the next hand.") : T("Wait for your turn …")),
      tl, h("div.row.center.wrap.pk-actions", ...buttons));
  }
  function bank() {
    if (st.rules.mode !== "bank") return null;
    const meP = st.players.find(p => p.id === me.id);
    const ask = meP && meP.chips === 0 ? h("div.center", meP.asks ? h("p.muted", "⏳ ", T("Asked the game leader for chips …"))
      : h("button.btn", { onclick: () => act("ask") }, "🙋 ", T("Ask for chips"))) : null;
    const reqs = isHost() && st.requests.length ? h("section.card", h("h3", "🏦 ", T("Chips wanted")),
      ...st.requests.map(id => { const p = st.players.find(x => String(x.id) === String(id)); return p ? h("div.row",
        C(p.name, "strong.grow"), h("span.small.muted", I18N.tr(T("buy-in {0}")).replace("{0}", p.buyins + 1)),
        h("button.btn.small.good", { onclick: () => act("give", { profile_id: p.id, ok: true }) }, "+ ", fmtC(st.rules.start_chips)),
        h("button.btn.small.ghost", { onclick: () => act("give", { profile_id: p.id, ok: false }) }, "✗")) : null; })) : null;
    return [ask, reqs];
  }
  poll();
}

async function pokerView() {
  const box = h("div.poker-live");
  screen("games", box);
  pokerLive(box, S.profile, () => go("games"));
}

async function pokerFamilyCard() {
  const c = S.me && S.me.community, p = c && c.poker;
  return h("section.card.quiz-card", h("h2", "🃏 Texas Hold'em"),
    p ? [h("p", p.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("poker") }, "🙋 ", p.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Poker with play chips – everybody on their own device.")),
         h("div.row.wrap", h("button.btn", { onclick: () => pokerSoloDialog(() => go("poker")) }, "🤖 ", T("Alone against bots")),
           h("button.btn.ghost", { onclick: () => pokerStartDialog(() => go("poker")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}

// alone against bots: how many, how well they play, the chips – the table is dealt right away
function pokerSoloDialog(onStarted) {
  const bots = h("select", ...[1, 2, 3, 4, 5].map(n => h("option", { value: n, selected: n === 3 }, String(n))));
  const level = h("select", ...[["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]].map(([v, n]) => h("option", { value: v, selected: v === "normal" }, I18N.tr(n))));
  const chips = h("select", ...[[500, "500 / 10–20"], [1000, "1000 / 10–20"], [2000, "2000 / 20–40"]].map(([v, n]) => h("option", { value: v, selected: v === 1000 }, n)));
  const picker = botPicker(1300);
  const m = modal(h("div.form", h("h2", "🤖 ", T("Alone against bots")),
    h("p.small.muted", T("Played with play chips only – they have nothing to do with coins or points.")),
    h("div.grid3", h("label.field", T("Bots"), bots), h("label.field", T("Bots play"), level), h("label.field", T("Start chips / blinds"), chips)),
    picker.el,
    h("div.row", h("button.btn.big", { onclick: async () => {
      const c = +chips.value, sb = c >= 2000 ? 20 : 10;
      try { await api("community/poker/start", { method: "POST", body: { solo: true, bots: Math.max(+bots.value, picker.ids().length), bot_ids: picker.ids(), level: level.value, bot_ms: picker.ms(), start_chips: c, small_blind: sb, big_blind: sb * 2 } }); m.close(); onStarted(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", T("Deal")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}
