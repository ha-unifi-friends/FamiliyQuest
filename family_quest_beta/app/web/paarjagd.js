// «Paarjagd» – live pairs game for the family: everybody on their own device, bots, guests (familyquest/pairhunt.py).
// paarjagdLive(box, me, back) runs a table (family or alone against bots), paarjagdStartDialog(solo, onStarted) sets the rules.
// Uses PAIR_SETS / pairBack / pairFace / CARD_BACKS / botPicker() from cards.js and guestInvite() from community.js.
"use strict";

const PJ_ICON = "🧠";
const pjName = () => I18N.tr(T("Paarjagd"));
const pjCoins = list => list.join(" / ") + " 🪙";

function paarjagdRulesView(r, rewards) {
  const items = [T("On your turn, turn two cards. A pair? It is yours and you go again."),
    T("No pair: everybody sees the two cards for a moment, then they turn back and the next player goes."),
    T("When all pairs are found, the most pairs win. A tie shares the place."),
    rewards ? I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", pjCoins(rewards)) : null,
    T("Coins only at a family table with at least two people of the family – not alone against bots, not for guests or bots.")].filter(Boolean);
  return h("div.form", h("h2", "📜 ", T("Rules")), h("ul.small", ...items.map(x => h("li", I18N.tr(x)))));
}

async function paarjagdStartDialog(solo, onStarted) {
  let r = {};
  try { r = await api("community/paarjagd/rules"); } catch {}
  const photo = r.photo_sets || [];
  const sets = [...Object.entries(PAIR_SETS).map(([k, [n]]) => [k, I18N.tr(n), 20]), ...photo.map(s => [s.key, "📷 " + s.name, s.count])];
  const sel = (v, list) => h("select", ...list.map(([k, n]) => h("option", { value: k, selected: String(v) === String(k) }, n)));
  const set = sel(r.set || "animals", sets.map(([k, n]) => [k, n]));
  const pairs = h("select");
  const drawPairs = () => {
    const max = (sets.find(s => s[0] === set.value) || [0, 0, 20])[2];
    const ok = [6, 8, 12, 18].filter(n => n <= max);
    const cur = +pairs.value || r.pairs || 8;
    pairs.replaceChildren(...(ok.length ? ok : [6]).map(n => h("option", { value: n, selected: n === cur }, ok.length ? String(n) : String(max))));
  };
  set.onchange = drawPairs; drawPairs();
  const bots = sel(solo ? Math.max(1, r.bots ?? 2) : (r.bots ?? 0), (solo ? [1, 2, 3, 4, 5] : [0, 1, 2, 3, 4]).map(n => [n, String(n)]));
  const level = sel(r.level || "normal", [["easy", T("easy")], ["normal", T("normal")], ["hard", T("hard")]]);
  // card back: tap one – the chosen one is marked (the family crest when the parents made one)
  const backs = [...Object.keys(CARD_BACKS), ...(r.crest ? ["crest"] : [])];
  let back = backs.includes(r.back) ? r.back : "classic";
  const backPrev = h("div.row.back-pick");
  const drawBacks = () => backPrev.replaceChildren(...backs.map(b => h("button.back-opt" + (b === back ? ".on" : ""),
    { type: "button", title: I18N.tr(b === "crest" ? T("Family crest") : CARD_BACKS[b]), "aria-pressed": String(b === back), onclick: () => { back = b; drawBacks(); } },
    h("span.pj-backprev", pairBack(b, r.crest)))));
  drawBacks();
  const picker = botPicker(r.bot_ms);
  const rw = r.rewards || [0, 0, 0];
  const coins = solo ? h("p.small.muted", "🪙 ", T("Alone against bots there are no coins."))
    : rw.some(x => x > 0) ? h("p.small.pj-coins", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", pjCoins(rw)), h("br"),
      h("span.muted", T("Coins only at a family table with at least two people of the family – not alone against bots, not for guests or bots."))) : null;
  const m = modal(h("div.form", h("h2", PJ_ICON, " ", pjName(), solo ? " – " + I18N.tr(T("alone against bots")) : ""),
    h("div.grid2", h("label.field", T("Cards"), set), h("label.field", T("Pairs"), pairs),
      h("label.field", solo ? T("Bots") : T("Bots at the table"), bots), h("label.field", T("Bots play"), level)),
    picker.el,
    h("div.field", h("b", T("Card back")), backPrev),
    coins,
    h("p.small.muted", T("These rules are remembered for the next game.")),
    h("div.row", h("button.btn.big", { onclick: async () => {
      const body = { solo, set: set.value, pairs: +pairs.value, bots: Math.max(+bots.value, picker.ids().length), level: level.value, back, bot_ids: picker.ids(), bot_ms: picker.ms() };
      try { await api("community/paarjagd/start", { method: "POST", body }); m.close(); onStarted(); } catch (e) { toast(e.message, "bad"); }
    } }, "▶ ", solo ? T("Play") : T("Open the table")), h("button.btn.ghost", { onclick: () => m.close() }, T("Cancel")))));
}

function paarjagdLive(box, me, back) {
  let st = null, timer = null, alive = true, lastSig = "", cheered = false, busy = false, lastEvent = null;
  let grid = null, cards = [], gridKey = "";
  const myId = String(me.id);
  box.classList.add("pj-live");
  const board = h("div.pj-board");
  const isHost = () => st && (st.host === me.id || me.role === "parent");
  const show = (...xs) => box.replaceChildren(...xs.flat().filter(x => x != null && x !== false));
  const stop = () => { alive = false; clearTimeout(timer); box.classList.remove("quiz-full"); document.body.classList.remove("quiz-open"); removeEventListener("resize", fit); };
  window.addEventListener("hashchange", stop, { once: true });
  const act = async (path, body) => {
    try { st = await api("community/paarjagd/" + path, { method: "POST", body }); draw(true); }
    catch (e) { toast(e.message, "bad"); }
  };
  async function poll() {
    if (!alive || !box.isConnected) return stop();
    try { st = await api("community/paarjagd"); draw(); } catch {}
    timer = setTimeout(poll, 900);
  }
  const player = id => st.players.find(p => p.id === id) || {};
  const who = id => player(id).name || "?";

  // ---------- the cards: built once per game, then only their classes and faces change (so they turn over)
  const emojiOf = it => it.img ? it : it.e != null ? { emoji: (PAIR_SETS[st.rules.set] || PAIR_SETS.animals)[1].split(" ")[it.e] || "❓" } : { emoji: String((it.n ?? 0) + 1) };
  function buildGrid() {
    const key = st.game + ":" + st.count;
    if (key === gridKey && grid) return;
    gridKey = key;
    cards = Array.from({ length: st.count }, (_, i) => h("button.mm-card", { type: "button", "aria-label": String(i + 1), onclick: () => tap(i) },
      h("div.mm-in", pairBack(st.rules.back, st.crest), h("div.mm-face"))));
    grid = h("div.pj-grid", ...cards);
    board.replaceChildren(grid);
  }
  function fit() {
    if (!grid || !board.isConnected) return;
    const W = board.clientWidth, H = board.clientHeight, n = cards.length, gap = 5;
    if (!W || !H) return;
    let best = [4, 0];
    for (let cols = 2; cols <= 9; cols++) {                   // the most columns / rows that give the biggest cards
      const rows = Math.ceil(n / cols);
      const w = Math.min((W - (cols - 1) * gap) / cols, ((H - (rows - 1) * gap) / rows) * 0.75, 120);
      if (w > best[1]) best = [cols, w];
    }
    const [cols, w] = best;
    grid.style.gridTemplateColumns = `repeat(${cols}, ${Math.floor(w)}px)`;
    grid.style.setProperty("--cw", Math.floor(w) + "px");
  }
  addEventListener("resize", fit);
  function updateCards() {
    const found = st.found || {}, open = st.open || [], faces = st.faces || {};
    const last = st.last || {}, pair = last.pair || [];
    const fresh = last.t && last.t !== lastEvent;
    cards.forEach((c, i) => {
      const k = faces[i];
      const face = c.querySelector(".mm-face");
      if (k != null && face.dataset.k !== String(k)) {
        const it = emojiOf(st.items[k] || {});
        face.replaceWith(pairFace(it));
        c.querySelector(".mm-face").dataset.k = String(k);
      }
      const isOpen = open.includes(i), isFound = found[i] != null;
      c.classList.toggle("open", isOpen || isFound);
      c.classList.toggle("done", isFound);
      c.classList.toggle("miss", isOpen && open.length === 2 && last.match === false);
      c.classList.toggle("hit", isFound && pair.includes(i) && last.match === true && !!fresh);
      c.classList.toggle("mine", isFound && found[i] === myId);
      c.disabled = !(st.my_turn && !isOpen && !isFound);
    });
    if (fresh) {
      lastEvent = last.t;
      try { Sound.play(last.match === true ? "right" : last.match === false ? "wrong" : "tap"); } catch {}
    }
  }
  async function tap(i) {
    if (busy || !st || !st.my_turn) return;
    busy = true;
    try { await act("flip", { idx: i }); } finally { busy = false; }
  }

  function draw(force) {
    if (!alive || !box.isConnected) return;                            // the game was left meanwhile: a late answer
    if (st && !Array.isArray(st.players)) st = null;                 // not a game state (e.g. after «end»): no game

    turnCue("paarjagd", st && st.my_turn);
    const sig = JSON.stringify(st && [st.phase, st.status, st.turn, st.open, Object.keys(st.found || {}).length, st.joined, st.players.length,
      st.last && st.last.t]);
    if (sig === lastSig && !force) return;
    lastSig = sig;
    const running = st && st.status !== "done";
    box.classList.toggle("quiz-full", !!running); document.body.classList.toggle("quiz-open", !!running);
    if (!st) return show(h("section.card.center", h("div.big-ic", PJ_ICON), h("h2", T("No game right now")), h("button.btn", { onclick: back }, T("Back"))));
    const close = running ? h("button.icon-btn.quiz-close", { title: T("Close"), onclick: () => { stop(); back(); } }, "✕") : null;
    // ☰: rules, guests (everybody of the family at a family table), end for whoever leads, language
    const menu = gameMenu({ rules: () => paarjagdRulesView(st.rules, st.coins_on ? st.rewards : null),
      invite: !st.solo && !me.guest && st.status !== "done" ? "paarjagd" : null,
      actions: [{ ic: "⏹", label: T("End the game"), danger: true, hidden: !isHost() || st.status === "done", confirm: T("End the game?"),
        onclick: () => act("end").then(() => { stop(); back(); }) }],
      onLeave: running ? () => { stop(); back(); } : null });
    const head = h("div.quiz-head.dm-head", h("div.row.head-title", menu, h("h1", PJ_ICON, " ", pjName())), h("div.row",
      st.phase === "play" ? h("span.chip", I18N.tr(T("{0} of {1} pairs")).replace("{0}", Object.keys(st.found || {}).length / 2).replace("{1}", st.count / 2)) : null));
    // only the main action stays as a big button – everything else is in ☰
    const host = isHost() && st.phase === "lobby" && st.status !== "done" ? h("div.row.center.host-bar",
      h("button.btn", { onclick: async () => { try { const r = await beginGame("community/paarjagd/begin", st.players); if (r) { st = r; draw(true); } } catch (e) { toast(e.message, "bad"); } } }, "▶ ", T("Deal"))) : null;
    if (st.phase !== "lobby") starterBanner(st.starter, "paarjagd");
    if (st.phase === "done") return show(head, result());
    if (!st.joined) return show(close, head, h("section.card.center", h("p", T("Play along on this device?")),
      h("button.btn.big", { onclick: () => act("join") }, "🙋 ", T("Join"))), seats(), host);
    if (st.phase === "lobby") return show(close, head, h("section.card.center", h("h2", T("Waiting for the start …")),
      h("p.muted", T("Everybody joins on their own device.")), seats(),
      st.coins_on ? h("p.small", "🪙 ", I18N.tr(T("Coins for places 1 / 2 / 3: {0}")).replace("{0}", pjCoins(st.rewards))) : null), host);
    buildGrid();
    let msg;
    if (st.my_turn) msg = h("strong.pj-msg.turn", (st.open || []).length ? T("Turn a second card!") : T("Your turn – turn two cards!"));
    else if ((st.open || []).length === 2 && st.last && st.last.match === false) msg = h("span.pj-msg", T("No pair …"));
    else msg = h("span.pj-msg.muted", I18N.tr(T("{0} is playing …")).replace("{0}", who(st.turn)));
    show(close, head, seats(), h("p.center.small.pj-msgline", msg), board, host);
    updateCards();
    fit();
  }

  function result() {
    const ranked = [...st.players].sort((a, b) => (a.place || 99) - (b.place || 99));
    const mine = player(myId);
    if (mine.place === 1 && !cheered) { cheered = true; confetti(); try { Sound.play("done"); } catch {} }
    const medal = n => ["🥇", "🥈", "🥉"][n - 1] || n + ".";
    return h("section.card.center.pj-result",
      h("h2", "🏆 ", C(ranked.filter(p => p.place === 1).map(p => p.name).join(" & "))),
      h("ol.pk-rank", ...ranked.map(p => h("li", h("span.pj-medal", medal(p.place)), seatIcon(p, 30), C(p.name, "strong.grow"),
        h("span", I18N.tr(T("Pairs: {0}")).replace("{0}", p.pairs)), p.coins ? h("b.pj-plus", "+" + p.coins + " 🪙") : null))),
      st.coins_on ? null : h("p.small.muted", st.solo ? T("Alone against bots there are no coins.") : T("Coins only at a family table with at least two people of the family – not alone against bots, not for guests or bots.")),
      h("div.row.center", h("button.btn", { onclick: back }, T("Back"))));
  }

  function seatIcon(p, size) {
    return p.bot ? h("span.bot-av", { style: { width: size + "px", height: size + "px", fontSize: (size * 0.6) + "px", background: p.color || null } }, p.emoji || "🤖") : avatarSvg(p.avatar || {}, size);
  }
  function seats() {
    return h("div.dm-seats", ...st.players.map(p => h("div.dm-seat" + (st.phase === "play" && st.turn === p.id ? ".turn" : "") + (p.id === myId ? ".dm-me" : ""),
      seatIcon(p, 30), C(p.name, "strong.small.dm-name"),
      st.phase !== "lobby" ? h("span.small.dm-count", "🃏 " + p.pairs) : null)));
  }
  poll();
}

async function paarjagdView() {
  const box = h("div.pj-live");
  screen("games", box);
  paarjagdLive(box, S.profile, () => go("games"));
}

async function paarjagdFamilyCard() {
  const c = S.me && S.me.community, g = c && c.paarjagd;
  return h("section.card.quiz-card", h("h2", PJ_ICON, " ", pjName()),
    g ? [h("p", g.status === "lobby" ? T("A table is open – join in!") : T("A game is running.")),
         h("button.btn.big", { onclick: () => go("paarjagd") }, "🙋 ", g.joined ? T("Back to the game") : T("Join"))]
      : [h("p.muted", T("Find the pairs – everybody on their own device. Places 1 to 3 win coins at the family table!")),
         h("div.row.wrap", h("button.btn", { onclick: () => paarjagdStartDialog(true, () => go("paarjagd")) }, "🤖 ", T("Alone against bots")),
           h("button.btn.ghost", { onclick: () => paarjagdStartDialog(false, () => go("paarjagd")) }, "👨‍👩‍👧 ", T("Open a family table")))]);
}
