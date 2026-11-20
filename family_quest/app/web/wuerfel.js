// «Fünf Würfel» – the dice game with five dice and a score sheet, live for the family (familyquest/wuerfel.py).
// Everybody rolls at the same time on their own device; 13 rounds, one box per round. wuerfelLive(box, me, back) runs a
// table (family or alone against bots), wuerfelStartDialog(solo, onStarted) sets the rules. The server rolls the dice –
// this file only animates them. Uses botPicker() from cards.js and guestInvite() from community.js.
"use strict";

const FW_ICON = "🎲";
const fwName = () => I18N.tr(T("Five Dice"));
const fwCoins = list => list.join(" / ") + " 🪙";
const FW_UPPER = ["ones", "twos", "threes", "fours", "fives", "sixes"];
const FW_CATS = {
  ones: T("Ones"), twos: T("Twos"), threes: T("Threes"), fours: T("Fours"), fives: T("Fives"), sixes: T("Sixes"),
  three_kind: T("3 of a kind"), four_kind: T("4 of a kind"), full_house: T("Full house"),
  small_straight: T("Small straight"), large_straight: T("Large straight"), fuenfling: T("Fünfling"), chance: T("Chance"),
};
const FW_HINT = { three_kind: "3× · Σ", four_kind: "4× · Σ", full_house: "3+2 · 25", small_straight: "4→ · 30", large_straight: "5→ · 40", fuenfling: "5× · 50", chance: "Σ" };
// pips of a face (viewBox 0 0 100 100)
const FW_PIPS = { 1: [[50, 50]], 2: [[28, 28], [72, 72]], 3: [[26, 26], [50, 50], [74, 74]], 4: [[28, 28], [72, 28], [28, 72], [72, 72]],
  5: [[26, 26], [74, 26], [50, 50], [26, 74], [74, 74]], 6: [[28, 24], [72, 24], [28, 50], [72, 50], [28, 76], [72, 76]] };

function fwFaceSvg(v) {
  const pips = (FW_PIPS[v] || []).map(([x, y]) => `<circle cx="${x}" cy="${y}" r="9.5"/>`).join("");
  return `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><rect x="3" y="3" width="94" height="94" rx="20" class="fw-face"/>${pips}</svg>`;
}
function fwDie(v, opts = {}) {
  const cls = "button.fw-die" + (opts.held ? ".held" : "") + (opts.mini ? ".mini" : "") + (!v ? ".blank" : "") + (opts.onclick ? ".tap" : "");
  return h(cls, { type: "button", disabled: !opts.onclick, onclick: opts.onclick, "aria-pressed": opts.onclick ? String(!!opts.held) : null,
    title: v ? String(v) : "", html: fwFaceSvg(v) });
}
const fwCatName = k => I18N.tr(FW_CATS[k] || k);

function wuerfelRulesView(r, rewards) {
  const items = [
    T("13 rounds. In every round everybody rolls their own five dice at the same time – up to 3 rolls. Tap a die to hold it: it is not rolled again."),
    T("Then fill one free box of your score sheet with the dice – or cross one out with 0. The next round starts when everybody has filled a box."),
    T("Ones to Sixes: the sum of the dice with that number. 63 points or more in this upper section give a bonus of 35."),
    T("Three / Four of a kind: 3 / 4 alike, the sum of all dice. Full house (3 + 2 alike): 25. Small straight (4 in a row): 30. Large straight (5 in a row): 40. Fünfling (5 alike): 50. Chance: the sum of all dice."),
    r && r.extra ? T("Extra: every further Fünfling gives +50 when the Fünfling box already holds 50.") : null,
    T("The highest total wins – a tie shares the place."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", fwCoins(rewards)) : null,
    T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."),
  ].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function wuerfelStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/wuerfel/rules"); } catch {}
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const bots = sel(solo ? Math.max(1, r.bots ?? 2) : 0, (solo ? [1, 2, 3, 4, 5] : [0, 1, 2, 3, 4]).map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  const extra = h("input", { type: "checkbox", checked: r.extra !== false });
  const picker = botPicker(r.bot_ms);
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", fwCoins(rw)), h("br"),
      h("span.muted", T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", FW_ICON, " ", fwName(), solo ? " – " + I18N.tr(T("alone against bots")) : ""),
    h("p.small.muted", T("Everybody rolls at the same time on their own device: 13 rounds, up to 3 rolls, one box of the score sheet per round.")),
    h("div.grid2", h("label.field", T("Bots"), bots), h("label.field", T("Bots play"), level)),
    solo ? null : h("p.small.muted", T("Up to 6 players: the family joins on their own devices, guests via QR code.")),
    h("div.cards-rules", h("label.check", extra, T("Extra: +50 for every further Fünfling"))),
    picker.el,
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, bots: +bots.value, level: level.value, extra: extra.checked, bot_ids: picker.ids(), bot_ms: picker.ms() };
      try { await api("community/wuerfel/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
  withoutBots("wuerfel", bots, level, picker.el);          // parent area › Games: without bots
}

function wuerfelLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, rolling = false;
  let held = [false, false, false, false, false], heldKey = "", pick = null, seenRound = 0;
  const myId = String(me.id);
  box.classList.add("fw-live");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  // the score sheet scrolls by itself on small screens (base.css): a new draw keeps where it was
  const show = (...xs) => {
    const old = box.querySelector(".fw-scroll"), top = old ? old.scrollTop : 0, left = old ? old.scrollLeft : 0;
    box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
    const now = box.querySelector(".fw-scroll");
    if (now && (top || left)) { now.scrollTop = top; now.scrollLeft = left; }
  };
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); };
  window.addEventListener("hashchange", stop, { once: true });
  const mine = () => st && st.players && st.players.find(p => p.id === myId);
  const who = id => (st.players.find(p => p.id === id) || {}).name || "?";
  const act = async (path, body) => {
    if (busy) return null;
    busy = true;
    try { st = await api("community/wuerfel/" + path, { method: "POST", body }); return st; }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { busy = false; draw(true); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { const s = await api("community/wuerfel"); if (!rolling && !busy) { st = s; draw(); } } catch {}
    timer = setTimeout(poll, 900);
  }

  // ---------- my dice: hold, roll (animated), choose a box
  function syncHeld() {
    const m = mine();
    if (!m) return;
    const key = st.game + ":" + st.round + ":" + m.rolls;
    if (key !== heldKey) { heldKey = key; held = m.rolls ? (m.held || []).slice(0, 5).map(Boolean) : [false, false, false, false, false]; pick = null; }
  }
  function tapDie(i) {
    held[i] = !held[i];
    try { Sound.play("tap"); } catch {}
    api("community/wuerfel/hold", { method: "POST", body: { held } }).catch(() => {});
    draw(true);
  }
  async function roll() {
    const m = mine();
    if (!m || busy || rolling || !st.can_roll) return;
    rolling = true;
    pick = null;
    const keep = m.rolls ? held.slice() : [false, false, false, false, false];
    const dice = [...box.querySelectorAll(".fw-tray .fw-die")];
    const spin = setInterval(() => dice.forEach((d, i) => { if (!keep[i]) d.innerHTML = fwFaceSvg(1 + Math.floor(Math.random() * 6)); }), 90);
    dice.forEach((d, i) => { if (!keep[i]) { d.classList.remove("held"); d.classList.add("rolling"); } });
    try { Sound.play("tap"); } catch {}
    const t0 = Date.now();
    let res = null, err = null;
    busy = true;
    try { res = await api("community/wuerfel/roll", { method: "POST", body: m.rolls ? { held: keep } : {} }); } catch (e) { err = e; }
    busy = false;
    await new Promise(ok => setTimeout(ok, Math.max(0, 650 - (Date.now() - t0))));
    clearInterval(spin);
    rolling = false;
    if (err) toast(err.message, "bad");
    if (res) st = res;
    draw(true);
    const n = mine();
    if (n && n.dice && new Set(n.dice).size === 1 && n.dice.length === 5) { try { Sound.play("done"); } catch {} toast("🎲 " + I18N.tr(T("Fünfling!")), "good"); }
  }
  async function choose(cat) {
    const pts = (st.options || {})[cat];
    const before = mine();
    const res = await act("choose", { cat });
    if (!res) return;
    pick = null;
    const after = (res.players || []).find(p => p.id === myId);
    const extra = after && before && after.extra > before.extra;
    try { Sound.play(pts > 0 ? "right" : "wrong"); } catch {}
    if (extra) toast("🎉 " + I18N.tr(T("Extra Fünfling: +50!")), "good");
  }

  // ---------- the screen
  // «Invite guests» (☰ and the button in the lobby box): the game key – null for solo tables, guests, finished games
  function invite() { return !st.solo && !me.guest && st.status !== "done" ? "wuerfel" : null; }
  function draw(force) {
    if (!alive || !box.isConnected) return;
    if (st && !Array.isArray(st.players)) st = null;
    if (rolling) return;
    const sig = JSON.stringify(st && [st.phase, st.status, st.round, st.joined, st.players.map(p => [p.id, p.rolls, p.dice, p.held, p.done, p.total, p.place])]) + JSON.stringify([held, pick]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", FW_ICON), h("h2", T("No game right now")), noTableActions("wuerfel", back)));
    if (st.phase === "play") syncHeld();
    if (st.phase === "play" && st.round !== seenRound) {
      if (seenRound && st.round > seenRound) toast(I18N.tr(T("Round {0} of {1}")).replace("{0}", st.round).replace("{1}", st.rounds));
      seenRound = st.round;
    }
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests, End (whoever leads), language – only the main action (Start) stays as a big button
    const menu = gameMenu({ rules: () => wuerfelRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: invite(),
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", FW_ICON, " ", fwName())), h("div.row",
      st.round && st.phase === "play" ? h("span.chip.fw-round", { title: I18N.tr(T("Round {0} of {1}")).replace("{0}", st.round).replace("{1}", st.rounds) }, st.round + " / " + st.rounds) : null));
    const host = isHost() && st.status !== "done" && st.phase === "lobby" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: () => act("begin") }, "▶ ", T("Start"))) : null;
    if (st.phase === "done") return show(head, result());
    if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      st.phase === "lobby" ? h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join")) : h("p.muted", T("The game has already started"))),
      st.phase === "lobby" ? lobbySeats() : sheet(), host);
    if (st.phase === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device.")), lobbySeats(), inviteBtn(invite()),
      st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", fwCoins(st.rewards))) : null), host);
    show(close, head, strip(), tray(), sheet(), host);
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function lobbySeats() {
    const free = Array.from({ length: st.bots || 0 }, () => h("div.dm-seat.fw-botseat", h("span.bot-av", { style: { width: "30px", height: "30px", fontSize: "18px" } }, "🤖"), h("span.small.muted", T("Bot"))));
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (p.id === myId ? ".dm-me" : ""), seatIcon(p, 30), C(p.name, "strong.small.dm-name"))), ...free);
  }
  // who is still rolling: one chip per player (others' dice small)
  function strip() {
    return h("div.fw-strip", ...st.players.filter(p => p.id !== myId).map(p => h("div.fw-pl" + (p.done ? ".done" : ""),
      seatIcon(p, 24),
      h("div.fw-plinfo", C(p.name, "strong.small.fw-plname"),
        h("span.fw-plstat", p.done ? "✓" : p.rolls ? "🎲 " + p.rolls + "/3" : "⏳", " · ", h("b", String(p.total)))),
      !p.done && p.dice && p.dice.length ? h("div.fw-mini", ...p.dice.map((v, i) => fwDie(v, { mini: true, held: p.held && p.held[i] }))) : null)));
  }
  function tray() {
    const m = mine();
    if (!m) return null;
    if (m.done) {
      const left = (st.waiting || []).filter(id => id !== myId).map(who);
      const last = m.last;
      return h("section.card.fw-tray.fw-wait",
        last ? h("div.fw-dice", ...(last.dice || []).map(v => fwDie(v, {}))) : null,
        last ? h("p.small", "✓ ", fwCatName(last.cat), ": ", h("b", String(last.pts)), last.extra ? " · +" + last.extra + " 🎉" : "") : null,
        h("p.fw-waitmsg", "⏳ ", left.length ? I18N.tr(T("Waiting for {0} …")).replace("{0}", left.join(", ")) : I18N.tr(T("Next round …"))));
    }
    const canHold = m.rolls > 0 && m.rolls < 3;
    const dice = m.rolls ? m.dice : [0, 0, 0, 0, 0];
    const p = pick && st.options && st.options[pick] != null ? pick : null;
    const n = m.rolls;
    return h("section.card.fw-tray" + (n === 0 ? ".fresh" : ""),
      h("div.fw-dice", ...dice.map((v, i) => fwDie(v, { held: n && held[i], onclick: canHold ? () => tapDie(i) : null }))),
      h("p.small.muted.center.fw-tip", n === 0 ? T("Roll the dice!") : canHold ? T("Tap dice to hold them, then roll again – or choose a box below.") : T("No more rolls – choose a box below.")),
      p ? h("div.row.center.fw-confirm",
        h("button.btn" + (st.options[p] > 0 ? ".good" : ".bad"), { onclick: () => choose(p) },
          st.options[p] > 0 ? "✓ " + I18N.tr(T("Enter {0} points in «{1}»")).replace("{0}", st.options[p]).replace("{1}", fwCatName(p))
            : "✗ " + I18N.tr(T("Cross out «{0}» (0 points)")).replace("{0}", fwCatName(p))),
        h("button.btn.ghost.small", { onclick: () => { pick = null; draw(true); } }, T("Cancel")))
        : h("div.row.center", h("button.btn.big.fw-roll", { disabled: !st.can_roll, onclick: roll },
          "🎲 ", I18N.tr(T("Roll ({0} of 3)")).replace("{0}", Math.min(3, n + 1)))));
  }
  function sheet() {
    const players = [...st.players].sort((a, b) => (a.id === myId ? -1 : b.id === myId ? 1 : 0));
    const opts = st.options || {};
    const playing = st.phase === "play";
    const cell = (p, k) => {
      const v = (p.sheet || {})[k];
      const isMe = p.id === myId;
      const fresh = p.last && p.last.cat === k && p.last.round >= st.round - (p.done ? 0 : 1);
      if (v != null) return h("td.fw-v" + (v === 0 ? ".zero" : "") + (fresh ? ".fresh" : ""), v === 0 ? "–" : String(v));
      if (isMe && playing && opts[k] != null) {
        return h("td.fw-opt" + (opts[k] > 0 ? ".ok" : ".nil") + (pick === k ? ".pick" : ""),
          h("button", { type: "button", onclick: () => { pick = pick === k ? null : k; try { Sound.play("tap"); } catch {} draw(true); } }, String(opts[k])));
      }
      return h("td.fw-empty", "");
    };
    const head = h("tr", h("th.fw-cat", ""), ...players.map(p => h("th.fw-ph" + (p.id === myId ? ".fw-mine" : ""), seatIcon(p, 22), C(p.name, "span.fw-phn"))));
    const upper = FW_UPPER.map(k => h("tr", h("th.fw-cat", h("span.fw-catdie", { html: fwFaceSvg(FW_UPPER.indexOf(k) + 1) }), " ", fwCatName(k)), ...players.map(p => cell(p, k))));
    const sumRow = h("tr.fw-sum", h("th.fw-cat", T("Upper section")), ...players.map(p => h("td", h("div.fw-up",
      h("span", p.upper + "/" + st.bonus_at), h("i.fw-bar", h("b", { style: { width: Math.min(100, p.upper / st.bonus_at * 100) + "%" } }))))));
    const bonusRow = h("tr.fw-sum", h("th.fw-cat", I18N.tr(T("Bonus (63+)"))), ...players.map(p => h("td" + (p.bonus ? ".fw-gotbonus" : ""), p.bonus ? "+" + p.bonus : "–")));
    const lower = ["three_kind", "four_kind", "full_house", "small_straight", "large_straight", "fuenfling", "chance"].map(k =>
      h("tr", h("th.fw-cat", fwCatName(k), h("small.fw-hint", FW_HINT[k])), ...players.map(p => cell(p, k))));
    const extraRow = st.rules && st.rules.extra ? h("tr.fw-sum", h("th.fw-cat", T("Extra Fünfling")), ...players.map(p => h("td", p.extra ? "+" + p.extra : "–"))) : null;
    const totalRow = h("tr.fw-total", h("th.fw-cat", T("Grand total")), ...players.map(p => h("td", h("b", String(p.total)))));
    return h("section.card.fw-sheet", h("div.fw-scroll", h("table.fw-table", h("thead", head), h("tbody", ...upper, sumRow, bonusRow, ...lower, extraRow, totalRow))));
  }
  function result() {
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99));
    const m = mine();
    if (m && m.place === 1 && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    const winners = ranked.filter(p => p.place === 1).map(p => p.name).join(" & ");
    return [h("section.card.center.fw-result",
      h("h2", "🏆 ", C(winners)),
      h("ol.pk-rank", ...ranked.map(p => h("li" + (p.id === myId ? ".fw-me" : ""), h("span.pj-medal", medal(p.place)), seatIcon(p, 30), C(p.name, "strong.grow"),
        h("b", String(p.total)), h("span.small.muted", T("points")), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.complete ? null : h("p.small.muted", T("The game was ended early – the sheets count as they stand, no coins.")),
      st.coins_on ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only for a game played to the end at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back")))), sheet()];
  }
  poll();
}

async function wuerfelView() {
  const box = h("div.fw-live");
  screen("games", box);
  wuerfelLive(box, S.profile, () => go("games"));
}

async function wuerfelFamilyCard() {
  const c = S.me && S.me.community, g = c && c.wuerfel;
  return h("section.card.quiz-card", h("h2", FW_ICON, " ", fwName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("wuerfel") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Roll five dice, hold the good ones and fill your score sheet – everybody at the same time. Places 1 to 3 win coins at the family table!")),
         gameStartRow(botsOn("wuerfel") ? () => wuerfelStartDialog(true, () => go("wuerfel")) : null, () => wuerfelStartDialog(false, () => go("wuerfel")))]);
}
